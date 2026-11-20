"""Données de DÉMONSTRATION : concours fictifs (domaines .example), pour découvrir l'interface.

Ils sont préfixés [DÉMO] et ne doivent jamais faire l'objet d'une vraie participation.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import Contest
from .discovery.pipeline import fingerprint, record_answer
from .intelligence.qualify import add_rules, qualify
from .security.sanitize import canonical_url

D = Path(__file__).parent / "demo_rules"
DEMOS = [
    ("[DÉMO] Gagnez une PlayStation 5", "https://jouets.example/jeu-ps5", "fr_free.txt", {"2026": "2099"}),
    ("[DÉMO] Code gagnant boissons", "https://boissons.example/code", "alt_free.txt", {"2027": "2099"}),
    ("[DÉMO] Holiday Sweepstakes (USA)", "https://acme.example/sweeps", "us_only.txt", {"2026": "2099"}),
    ("[DÉMO] Grand jeu Super Marché", "https://supermarche.example/jeu", "purchase.txt", {"2027": "2099"}),
    ("[DÉMO] iPhone offert (arnaque type)", "https://promo-iphone.example/win", "injection.txt", {}),
]


def load_demo(db: Session) -> int:
    n = 0
    for title, url, f, rep in DEMOS:
        if db.scalars(select(Contest).where(Contest.title == title)).first():
            continue
        text = (D / f).read_text(encoding="utf-8")
        for a, b in rep.items():
            text = text.replace(a, b)
        c = Contest(title=title, url=url, canonical_url=canonical_url(url), fingerprint=fingerprint(title, "demo"), description=text[:400])
        db.add(c)
        db.flush()
        add_rules(db, c, text, url + "/reglement", "fetched")
        if "PlayStation" in title:
            record_answer(db, c, "Quelle est la couleur de la manette ?", "Blanche", "Démo")
        qualify(db, c)
        n += 1
    db.commit()
    return n
