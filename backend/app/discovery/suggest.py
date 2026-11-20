"""Construit l'agrégateur maison : repère les sites d'organisateurs déjà rencontrés et propose de les surveiller.

Chaque concours trouvé (via Le Démon du Jeu, l'extension ou un ajout manuel) pointe vers le site de la
marque qui l'organise. Les marques relancent souvent des jeux : surveiller leur site directement permet
de trouver les prochains sans dépendre d'un agrégateur tiers.
"""
from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Contest, Source
from .policy import denial_reason

# réseaux sociaux, raccourcisseurs, plateformes de formulaires et agrégateurs : pas un « site organisateur »
NOT_ORGANIZER = {
    "facebook.com", "fb.com", "instagram.com", "tiktok.com", "twitter.com", "x.com", "youtube.com", "youtu.be", "linkedin.com",
    "pinterest.com", "pinterest.fr", "snapchat.com", "threads.net", "whatsapp.com", "t.co", "bit.ly", "tinyurl.com", "linktr.ee",
    "lnkd.in", "goo.gl", "forms.gle", "ow.ly", "google.com", "typeform.com", "jotform.com", "gleam.io", "woobox.com",
    "kingsumo.com", "shortstack.com", "ledemondujeu.com", "jeu-concours.biz", "toutgagner.com",
}
DOMAIN_RX = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")


def not_organizer(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in NOT_ORGANIZER)


def site_domain(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def followed_domains(db: Session) -> set[str]:
    return {site_domain(s.url) for s in db.scalars(select(Source))}


def suggestions(db: Session, limit: int = 50) -> list[dict]:
    followed = followed_domains(db)
    groups: dict[str, list[Contest]] = defaultdict(list)
    for c in db.scalars(select(Contest).where(Contest.merged_into_id.is_(None))):
        d = site_domain(c.url)
        if not d or d in followed:
            continue
        if not_organizer(d) or denial_reason(c.url):
            continue
        groups[d].append(c)
    out = []
    for d, cs in groups.items():
        orgs = sorted({c.organizer.name for c in cs if c.organizer})
        out.append({"domain": d, "contests": len(cs), "organizer_names": orgs[:3],
                    "examples": [c.title[:120] for c in sorted(cs, key=lambda c: c.id, reverse=True)[:3]]})
    out.sort(key=lambda x: (-x["contests"], x["domain"]))
    return out[:limit]


def follow(db: Session, domain: str) -> Source:
    d = domain.strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]
    if not DOMAIN_RX.match(d):
        raise ValueError("Nom de domaine invalide")
    if not_organizer(d):
        raise ValueError("Ce site n'est pas un site d'organisateur (réseau social, formulaire ou agrégateur)")
    url = f"https://{d}/"
    why = denial_reason(url)
    if why:
        raise PermissionError(why)
    if d in followed_domains(db):
        raise FileExistsError("Site déjà surveillé")
    s = Source(name=d, kind="site", url=url, enabled=True, language="fr", trust=60,
               tos_note="Site de l'organisateur : seules ses pages publiques de jeux sont lues, au rythme fixé par robots.txt et le quota.")
    db.add(s)
    db.flush()
    return s
