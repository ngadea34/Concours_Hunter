"""Sources initiales. Les agrégateurs sont créés DÉSACTIVÉS : l'utilisateur vérifie leurs CGU puis les active."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import Source, SourceConnector
from .discovery.base import load_connectors

SEED = [
    ("Jeu-concours.biz", "aggregator:jeu-concours-biz", "https://www.jeu-concours.biz/", "fr", "FR", 70),
    ("Le Démon du Jeu", "aggregator:lddj", "https://www.ledemondujeu.com/", "fr", "FR", 75),
    ("ToutGagner", "aggregator:toutgagner", "https://www.toutgagner.com/", "fr", "FR", 70),
    ("Concours du Net", "aggregator:concoursdunet", "https://www.concoursdunet.com/", "fr", "FR", 65),
]


def seed(db: Session) -> None:
    reg = load_connectors()
    for kind, cls in reg.items():
        if not db.scalars(select(SourceConnector).where(SourceConnector.kind == kind)).first():
            db.add(SourceConnector(kind=kind, description=cls.description, default_config=dict(cls.default_config)))
    for name, kind, url, lang, country, trust in SEED:
        if not db.scalars(select(Source).where(Source.url == url)).first():
            db.add(Source(name=name, kind=kind, url=url, language=lang, country=country, enabled=False, trust=trust, tos_note=reg[kind].tos_note))
    db.commit()
