"""Traitement sûr des contenus web (M07).

- Le texte des pages est toujours traité comme DONNÉE, jamais comme instruction.
- Les motifs d'injection de prompt sont détectés, journalisés et neutralisés avant tout envoi à un LLM.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup

MAX_TEXT = 60_000

INJECTION_PATTERNS = [
    r"ignore (all |the )?(previous|above|prior) (instructions|prompts?)",
    r"ignore(z)? (toutes )?les instructions",
    r"disregard (the )?(system|previous)",
    r"you are now",
    r"tu es (maintenant|désormais)",
    r"system prompt",
    r"<\s*/?\s*(system|assistant|user)\s*>",
    r"\b(act|behave) as\b",
    r"reveal (your|the) (prompt|instructions)",
    r"mark (this|the) contest as (free|eligible|verified)",
]
_INJ = re.compile("|".join(INJECTION_PATTERNS), re.I)
_ZW = re.compile("[​-‏‪-‮⁠-⁤﻿]")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "template", "svg", "iframe"]):
        t.decompose()
    # éléments cachés : souvent utilisés pour des injections invisibles
    for t in soup.select('[hidden], [aria-hidden="true"], [style*="display:none"], [style*="display: none"], [style*="visibility:hidden"]'):
        t.decompose()
    text = soup.get_text("\n")
    return clean_text(text)


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ZW.sub("", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()[:MAX_TEXT]


def detect_injection(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in _INJ.finditer(text)})


def neutralize_for_llm(text: str) -> str:
    """Remplace les motifs d'injection et encadre le texte comme données."""
    return _INJ.sub("[motif supprimé]", text)


def canonical_url(url: str) -> str:
    """URL normalisée pour la déduplication (sans tracking ni fragment)."""
    parts = urlsplit(url.strip())
    scheme = "https" if parts.scheme in ("http", "https") else parts.scheme
    host = (parts.hostname or "").lower().removeprefix("www.")
    q = "&".join(
        kv for kv in parts.query.split("&")
        if kv and not re.match(r"(utm_[a-z]+|fbclid|gclid|mc_[a-z]+|ref|xtor)=", kv, re.I)
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, q, ""))


def is_safe_http_url(url: str) -> bool:
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    host = p.hostname.lower()
    # pas de requêtes du moteur de découverte vers le réseau local (SSRF)
    if host in ("localhost",) or host.endswith(".local") or host.endswith(".internal"):
        return False
    import ipaddress

    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
    except ValueError:
        return True
