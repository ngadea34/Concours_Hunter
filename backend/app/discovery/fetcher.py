"""Récupération HTTP respectueuse : robots.txt, délai par domaine, quota horaire, cache conditionnel.

Ne contourne jamais : authentification, CAPTCHA, paywall, géoblocage (403/451 → arrêt et signalement).
"""
from __future__ import annotations

import hashlib
import io
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from urllib import robotparser
from urllib.parse import urlsplit

import httpx

from ..config import get_settings
from ..security.sanitize import is_safe_http_url

log = logging.getLogger(__name__)

MAX_BYTES = 8_000_000
ALLOWED_TYPES = ("text/html", "application/xhtml", "application/xml", "text/xml", "application/rss", "application/atom", "application/pdf", "text/plain")


def resolves_to_private(host: str) -> bool:
    """Anti-SSRF : refuse un nom de domaine public qui pointe vers le réseau local."""
    import ipaddress
    import socket

    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False  # non résolu : la requête échouera d'elle-même
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


class FetchBlocked(Exception):
    """La récupération est interdite (robots, protection, quota) : ne pas réessayer en force."""


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    text: str
    content_hash: str
    not_modified: bool = False
    etag: str | None = None
    last_modified: str | None = None


class Fetcher:
    def __init__(self, max_per_hour: int = 30, client: httpx.Client | None = None):
        s = get_settings()
        self.ua = s.user_agent
        self.min_delay = s.min_delay_per_domain_s
        self.max_per_hour = max_per_hour
        self.client = client or httpx.Client(timeout=s.http_timeout, follow_redirects=True, headers={"User-Agent": self.ua, "Accept-Language": "fr,en;q=0.8"})
        self._robots: dict[str, tuple[float, robotparser.RobotFileParser | None]] = {}
        self._last: dict[str, float] = {}
        self._hist: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
        self.stopped = threading.Event()
        self.check_dns = client is None  # désactivé seulement avec un client de test injecté

    # -- robots
    def allowed(self, url: str) -> bool:
        p = urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        cached = self._robots.get(base)
        if cached is None or time.time() - cached[0] > 86400:
            rp = robotparser.RobotFileParser()
            try:
                r = self.client.get(base + "/robots.txt", timeout=10)
                if r.status_code in (401, 403):
                    rp = None  # robots inaccessible et protégé : prudence, on considère interdit
                elif r.status_code >= 400:
                    rp.parse([])
                else:
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp.parse([])
            self._robots[base] = (time.time(), rp)
            cached = self._robots[base]
        rp = cached[1]
        return rp is not None and rp.can_fetch(self.ua, url)

    def _throttle(self, host: str) -> None:
        with self._lock:
            now = time.time()
            hist = self._hist[host]
            while hist and now - hist[0] > 3600:
                hist.popleft()
            if len(hist) >= self.max_per_hour:
                raise FetchBlocked(f"Quota horaire atteint pour {host}")
            wait = self._last.get(host, 0) + self.min_delay - now
        if wait > 0:
            if self.stopped.wait(wait):
                raise FetchBlocked("Arrêt demandé")
        with self._lock:
            self._last[host] = time.time()
            self._hist[host].append(time.time())

    def get(self, url: str, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
        if self.stopped.is_set():
            raise FetchBlocked("Arrêt demandé")
        if not is_safe_http_url(url):
            raise FetchBlocked(f"URL refusée : {url}")
        if not self.allowed(url):
            raise FetchBlocked(f"Interdit par robots.txt : {url}")
        host = urlsplit(url).hostname or ""
        if self.check_dns and resolves_to_private(host):
            raise FetchBlocked(f"Domaine pointant vers le réseau local refusé : {host}")
        self._throttle(host)
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        with self.client.stream("GET", url, headers=headers) as r:
            final = str(r.url)
            if not is_safe_http_url(final):
                raise FetchBlocked(f"Redirection refusée : {final}")
            if r.status_code == 304:
                return FetchResult(url, 304, "", "", "", not_modified=True, etag=etag, last_modified=last_modified)
            if r.status_code in (401, 402, 403, 407, 429, 451):
                raise FetchBlocked(f"Accès refusé ({r.status_code}) : authentification, protection ou restriction géographique — non contourné")
            r.raise_for_status()
            ctype = r.headers.get("content-type", "").lower()
            if ctype and not ctype.startswith(ALLOWED_TYPES):
                raise FetchBlocked(f"Type de contenu refusé : {ctype}")
            buf = bytearray()
            for chunk in r.iter_bytes():
                buf.extend(chunk)
                if len(buf) > MAX_BYTES:
                    raise FetchBlocked("Document trop volumineux")
            data = bytes(buf)
            if "pdf" in ctype or data[:5] == b"%PDF-":
                text = pdf_to_text(data)
            else:
                text = data.decode(r.encoding or "utf-8", errors="replace")
            low = text[:20000].lower()
            if any(k in low for k in ("cf-challenge", "challenge-platform", "g-recaptcha", "h-captcha", "cf-turnstile")) and len(text) < 30000 and "<form" not in low:
                raise FetchBlocked("Page de vérification anti-robot détectée — non contournée")
            return FetchResult(final, r.status_code, ctype, text, hashlib.sha256(data).hexdigest(),
                               etag=r.headers.get("etag"), last_modified=r.headers.get("last-modified"))

    def close(self) -> None:
        self.client.close()


def pdf_to_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages[:40])
    except Exception as e:  # noqa: BLE001
        log.warning("PDF illisible : %s", e)
        return ""
