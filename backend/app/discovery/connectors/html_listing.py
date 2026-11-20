"""Connecteur HTML générique piloté par configuration (sélecteurs CSS), avec repli heuristique."""
from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ...intelligence.rules_extract import parse_dates_in
from ...i18n.geo import norm
from ..base import Connector, RawContest, register

KEYWORDS = re.compile(r"concours|jeu|gagne[rz]?|tirage|a gagner|giveaway|sweepstake|contest|win\b|sorteo|concurso|gewinnspiel|verlosung|concorso|passatempo|sorteio|winactie|prijsvraag", re.I)


def _sel_text(node, sel: str | None) -> str | None:  # noqa: ANN001
    if not sel:
        return None
    el = node.select_one(sel)
    return el.get_text(" ", strip=True) if el else None


@register
class HtmlListingConnector(Connector):
    kind = "html"
    description = "Page publique listant des concours (sélecteurs CSS configurables)."
    default_config = {"item": None, "title": None, "link": "a[href]", "end_date": None, "prize": None, "next": None, "max_pages": 2, "max_items": 150}

    def parse(self, html: str, base_url: str) -> tuple[list[RawContest], str | None]:
        soup = BeautifulSoup(html, "lxml")
        out: list[RawContest] = []
        cfg = self.config
        if cfg.get("item"):
            for node in soup.select(cfg["item"]):
                a = node.select_one(cfg.get("link") or "a[href]")
                if not a or not a.get("href"):
                    continue
                title = _sel_text(node, cfg.get("title")) or a.get_text(" ", strip=True)
                end = _sel_text(node, cfg.get("end_date"))
                ds = parse_dates_in(norm(end)) if end else []
                href = urljoin(base_url, a["href"])
                out.append(RawContest(title=title[:500], url=href, source_url=href, detail_url=href,
                                      end_date=ds[-1][1].isoformat() if ds else None, prize=_sel_text(node, cfg.get("prize")),
                                      description=node.get_text(" ", strip=True)[:2000], language=self.source.language))
        else:
            seen = set()
            for a in soup.select("a[href]"):
                text = a.get_text(" ", strip=True)
                href = urljoin(base_url, a["href"])
                if len(text) < 12 or href in seen or not href.startswith("http") or not KEYWORDS.search(text + " " + href):
                    continue
                seen.add(href)
                parent = a.find_parent(["article", "li", "div"]) or a
                out.append(RawContest(title=text[:500], url=href, source_url=href, detail_url=href,
                                      description=parent.get_text(" ", strip=True)[:2000], language=self.source.language))
        nxt = None
        if cfg.get("next"):
            n = soup.select_one(cfg["next"])
            if n and n.get("href"):
                nxt = urljoin(base_url, n["href"])
        return out[: int(cfg.get("max_items", 150))], nxt

    def discover(self) -> Iterator[RawContest]:
        url: str | None = self.source.url
        for page in range(int(self.config.get("max_pages", 2))):
            if not url:
                break
            res = self.fetcher.get(url, *(self.source.etag, self.source.last_modified) if page == 0 else (None, None))
            if res.not_modified:
                return
            if page == 0:
                self.source.etag, self.source.last_modified = res.etag, res.last_modified
            items, url = self.parse(res.text, res.url)
            yield from items
