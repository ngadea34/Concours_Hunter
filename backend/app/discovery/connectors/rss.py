from __future__ import annotations

from collections.abc import Iterator

import feedparser

from ...security.sanitize import html_to_text
from ..base import Connector, RawContest, register


@register
class RssConnector(Connector):
    kind = "rss"
    description = "Flux RSS/Atom public (sites de concours, médias, marques)."

    def discover(self) -> Iterator[RawContest]:
        res = self.fetcher.get(self.source.url, self.source.etag, self.source.last_modified)
        if res.not_modified:
            return
        self.source.etag, self.source.last_modified = res.etag, res.last_modified
        feed = feedparser.parse(res.text)
        for e in feed.entries[: int(self.config.get("max_items", 100))]:
            link = e.get("link")
            title = (e.get("title") or "").strip()
            if not link or not title:
                continue
            summary = html_to_text(e.get("summary") or e.get("description") or "")
            yield RawContest(title=title[:500], url=link, source_url=link, detail_url=link, description=summary[:5000],
                             language=self.source.language)
