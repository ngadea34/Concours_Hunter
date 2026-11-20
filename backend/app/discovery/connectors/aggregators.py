"""M13 : connecteurs des agrégateurs spécialisés.

Audit réel du 2026-11-20 (depuis le PC de l'utilisateur, lecture seule) :
- Le Démon du Jeu (ledemondujeu.com) : pas de clause anti-extraction ; robots.txt interdit /toconc.php
  (redirection vers l'organisateur) → jamais suivi par le robot. Connecteur ci-dessous calé sur la vraie structure.
- Jeu-concours.biz : extraction automatisée interdite par les mentions légales → exclu (policy.py).
- ToutGagner : données clés réservées aux abonnés, reproduction interdite → exclu (policy.py).
- Concours du Net : concoursdunet.com inexistant ; le vrai site concours-du-net.com interdit toute exploitation sans accord écrit → consultation assistée (policy.py).
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ...i18n.geo import norm
from ...intelligence.rules_extract import parse_dates_in
from ..base import RawContest, register
from .html_listing import HtmlListingConnector

DOMAIN_RX = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", re.I)


def organizer_guess(onclick: str | None, name: str | None) -> str | None:
    """Le lien organisateur passe par /toconc.php (interdit aux robots). L'attribut de suivi
    analytique contient en clair « /hote/chemin » : on en déduit une URL candidate, seulement si
    l'hôte correspond au nom d'organisateur affiché."""
    if not onclick:
        return None
    m = re.search(r"'(/[^']+)'", onclick.split(",", 1)[-1])
    if not m:
        return None
    parts = m.group(1).lstrip("/").split("/", 1)
    host = parts[0].lower()
    if not DOMAIN_RX.match(host):
        return None
    base = (name or "").lower().removeprefix("www.")
    if base and not (host == base or host.endswith("." + base)):
        return None
    return f"https://{host}/" + (parts[1] if len(parts) > 1 else "")


@register
class LeDemonDuJeu(HtmlListingConnector):
    kind = "aggregator:lddj"
    description = "Le Démon du Jeu (LDDJ) : liste quotidienne des nouveaux concours."
    tos_note = ("Audit du 2026-11-20 : pas de CGU ni de clause anti-extraction ; robots.txt respecté (/toconc.php jamais appelé). "
                "Même réseau commercial que Jeu-concours.biz (Reflexe Media), dont les CGU interdisent l'extraction : lecture maintenue "
                "à votre demande, à cadence réduite. Désactivez la source si l'éditeur s'y oppose.")
    default_config = {"max_items": 200}

    def parse(self, html: str, base_url: str) -> tuple[list[RawContest], str | None]:
        soup = BeautifulSoup(html, "lxml")
        out: list[RawContest] = []
        for art in soup.select("article.bloc-article"):
            org_a = art.select_one("h3.bloc-article-titre a")
            fiche_a = art.select_one("div.bloc-article-no a")
            if not org_a or not fiche_a or not fiche_a.get("href"):
                continue
            org_name = (org_a.get("data-concours-nom") or org_a.get_text(strip=True)).strip()
            fiche = urljoin(base_url, fiche_a["href"])
            sections: dict[str, str] = {}
            for h4 in art.select("h4.bloc-article-text-titre"):
                p = h4.find_next_sibling("p")
                if p:
                    sections[norm(h4.get_text(strip=True))] = p.get_text("\n", strip=True)
            prize = sections.get("cadeaux a gagner")
            dates = art.select_one("span.bloc-article-dates")
            ds = parse_dates_in(norm(dates.get_text(" ", strip=True))) if dates else []
            go = art.select_one("a.toolbar-link")
            guess = organizer_guess(go.get("onclick") if go else None, org_name)
            types = [img.get("alt", "") for img in art.select("li.bloc-article-pictos-item img")]
            title = f"{org_name} : {prize.splitlines()[0][:150]}" if prize else org_name
            desc = "\n\n".join(f"{k}\n{v}" for k, v in sections.items())
            entry = "instant" if any("instant" in norm(t) for t in types) else ("quiz" if any("quiz" in norm(t) or "question" in norm(t) for t in types) else "form")
            out.append(RawContest(
                title=title[:500], url=guess or fiche, source_url=fiche, detail_url=fiche, description=desc[:5000],
                end_date=ds[-1][1].isoformat() if ds else None, prize=prize[:500] if prize else None, organizer=org_name,
                entry_method=entry, language="fr",
                extra={"aggregator": self.kind, "human_link": urljoin(base_url, go["href"]) if go and go.get("href") else None,
                       "organizer_url_is_guess": bool(guess), "types": types}))
        return out[: int(self.config.get("max_items", 200))], None

    def discover(self) -> Iterator[RawContest]:
        url = self.source.url
        if urlsplit(url).path in ("", "/"):
            url = urljoin(url, "/nouveaux-jeux-concours.html")
        res = self.fetcher.get(url, self.source.etag, self.source.last_modified)
        if res.not_modified:
            return
        self.source.etag, self.source.last_modified = res.etag, res.last_modified
        items, _ = self.parse(res.text, res.url)
        if not items:
            self.source.last_status = "aucun concours reconnu : la structure du site a peut-être changé"
        yield from items
