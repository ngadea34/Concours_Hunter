"""Connecteur « site organisateur » : l'agrégateur maison, alimenté par les sites des marques et médias eux-mêmes.

Pour un domaine donné, il cherche les pages de jeux-concours publiées par le site lui-même :
1. les sitemaps déclarés dans robots.txt (ou /sitemap.xml), filtrés sur les URL de concours récentes ;
2. à défaut, les flux RSS annoncés par la page d'accueil et les liens « concours » de la page configurée.
Chaque page trouvée est ensuite lue (règlement compris) par l'enrichissement habituel, dans le respect
de robots.txt, du délai par domaine et du quota horaire. Aucun agrégateur tiers n'est lu par ce connecteur.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, timedelta
from urllib.parse import unquote, urljoin, urlsplit

import feedparser
from bs4 import BeautifulSoup

from ...security.sanitize import html_to_text
from ..base import Connector, RawContest, register
from ..fetcher import FetchBlocked
from .html_listing import KEYWORDS, HtmlListingConnector

# URL de page de jeu (et non de règlement, de liste de gagnants ou de concours administratif)
CONTEST_PATH = re.compile(r"jeux?[-_/]?concours|concours|a[-_]gagner|gagne[rz][-_]|tirage[-_]au[-_]sort|instant[-_]gagnant|giveaway|sweepstakes?|"
                          r"/jeux?/|/jeu[-_]|/win[-_]|gewinnspiel|sorteo|concorso|winactie", re.I)
EXCLUDE_PATH = re.compile(r"reglement|conditions|cgu|mentions|gagnants|resultats|winners|rules|terms|privacy|"
                          r"fonction[-_]publique|recrutement|concours[-_](administratif|interne|externe|infirmier|enseignant)|"
                          r"\.(pdf|jpe?g|png|gif|webp|mp4|xml|gz)$", re.I)
GENERIC_LAST = re.compile(r"^(jeux?[-_]?concours|concours|jeux|jeu|giveaway|index(\.\w+)?)$", re.I)


def is_contest_url(url: str) -> bool:
    path = unquote(urlsplit(url).path).lower()
    if not path or path == "/" or EXCLUDE_PATH.search(path):
        return False
    last = path.rstrip("/").rsplit("/", 1)[-1]
    if GENERIC_LAST.match(last):
        return False  # page d'index des concours : utile comme liste, pas comme concours
    return bool(CONTEST_PATH.search(path))


def title_from_url(url: str) -> str:
    last = unquote(urlsplit(url).path).rstrip("/").rsplit("/", 1)[-1]
    last = re.sub(r"\.(html?|php|aspx?)$", "", last, flags=re.I)
    last = re.sub(r"(^|[-_])\d{3,}($|[-_])", " ", last)
    words = re.sub(r"[-_+]+", " ", last).strip()
    return (words[:1].upper() + words[1:]) if words else url


@register
class SiteConnector(Connector):
    kind = "site"
    description = "Site d'un organisateur (marque, média, enseigne) : concours trouvés via ses sitemaps, flux RSS et page concours."
    default_config = {"listing_url": None, "max_age_days": 120, "max_items": 40, "max_sitemaps": 4}

    def _recent(self, lastmod: str | None) -> bool:
        if not lastmod:
            return True
        try:
            d = date.fromisoformat(lastmod.strip()[:10])
        except ValueError:
            return True
        return d >= date.today() - timedelta(days=int(self.config.get("max_age_days", 120)))

    def _from_sitemaps(self) -> list[RawContest]:
        base = self.source.url
        root = f"{urlsplit(base).scheme}://{urlsplit(base).netloc}"
        queue = self.fetcher.sitemaps(base) or [root + "/sitemap.xml"]
        seen_maps: set[str] = set()
        found: dict[str, RawContest] = {}
        budget = int(self.config.get("max_sitemaps", 4))
        while queue and budget > 0:
            sm = queue.pop(0)
            if sm in seen_maps or sm.lower().endswith(".gz") or urlsplit(sm).hostname != urlsplit(root).hostname:
                continue
            seen_maps.add(sm)
            budget -= 1
            try:
                res = self.fetcher.get(sm)
            except FetchBlocked:
                raise
            except Exception:  # noqa: BLE001 - sitemap absent ou illisible : on passe au repli
                continue
            soup = BeautifulSoup(res.text, "xml")
            children = [loc.get_text(strip=True) for s in soup.find_all("sitemap") if (loc := s.find("loc"))]
            # index : priorité aux sous-sitemaps qui parlent de jeux / articles / pages
            children.sort(key=lambda u: 0 if re.search(r"jeu|concours|contest|game|post|article|page|news", u, re.I) else 1)
            queue = children + queue
            for u in soup.find_all("url"):
                loc = u.find("loc")
                if not loc:
                    continue
                href = loc.get_text(strip=True)
                lm = u.find("lastmod")
                if href.startswith("http") and is_contest_url(href) and self._recent(lm.get_text(strip=True) if lm else None):
                    found.setdefault(href, RawContest(title=title_from_url(href), url=href, source_url=href, detail_url=href,
                                                      language=self.source.language, extra={"title_from_url": True}))
        return list(found.values())

    def _from_pages(self) -> list[RawContest]:
        out: dict[str, RawContest] = {}
        listing = self.config.get("listing_url") or self.source.url
        res = self.fetcher.get(listing)
        soup = BeautifulSoup(res.text, "lxml")
        feeds = [urljoin(res.url, l["href"]) for l in soup.select('link[rel="alternate"][href]')
                 if re.search(r"rss|atom", l.get("type", ""), re.I)]
        for f in feeds[:2]:
            try:
                fr = self.fetcher.get(f)
            except FetchBlocked:
                raise
            except Exception:  # noqa: BLE001
                continue
            for e in feedparser.parse(fr.text).entries[:100]:
                link, title = e.get("link"), (e.get("title") or "").strip()
                if link and title and (KEYWORDS.search(title) or is_contest_url(link)):
                    out.setdefault(link, RawContest(title=title[:500], url=link, source_url=link, detail_url=link, language=self.source.language,
                                                    description=html_to_text(e.get("summary") or "")[:5000]))
        host = urlsplit(res.url).hostname
        items, _ = HtmlListingConnector(self.source, self.fetcher).parse(res.text, res.url)
        for it in items:
            if urlsplit(it.url).hostname == host and is_contest_url(it.url):
                out.setdefault(it.url, it)
        return list(out.values())

    def discover(self) -> Iterator[RawContest]:
        items = [] if self.config.get("listing_url") else self._from_sitemaps()
        if not items:
            items = self._from_pages()
        self.source.last_status = f"{len(items)} page(s) de concours repérée(s)"
        yield from items[: int(self.config.get("max_items", 40))]
