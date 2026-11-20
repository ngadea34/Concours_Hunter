"""Sources initiales. Créées DÉSACTIVÉES : l'utilisateur lit la note CGU puis les active."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import Source, SourceConnector
from .discovery.base import load_connectors

SEED = [
    ("Le Démon du Jeu", "aggregator:lddj", "https://www.ledemondujeu.com/nouveaux-jeux-concours.html", "fr", "FR", 75),
]
RETIRED = {  # sources des versions précédentes, désactivées définitivement (non supprimées)
    "aggregator:jeu-concours-biz": "Exclu : extraction automatisée interdite par les mentions légales du site",
    "aggregator:toutgagner": "Exclu : contenu réservé aux abonnés, reproduction interdite",
    "aggregator:concoursdunet": "Retiré : concoursdunet.com inexistant ; concours-du-net.com interdit l'exploitation sans accord écrit (consultation assistée)",
}


def seed(db: Session) -> None:
    reg = load_connectors()
    for kind, cls in reg.items():
        if not db.scalars(select(SourceConnector).where(SourceConnector.kind == kind)).first():
            db.add(SourceConnector(kind=kind, description=cls.description, default_config=dict(cls.default_config)))
    for src in db.scalars(select(Source).where(Source.kind.in_(list(RETIRED)))):
        src.enabled = False
        src.last_status = RETIRED[src.kind]
    old = db.scalars(select(Source).where(Source.url == "https://www.ledemondujeu.com/")).first()
    if old:
        old.url = SEED[0][2]
    for name, kind, url, lang, country, trust in SEED:
        existing = db.scalars(select(Source).where(Source.url == url)).first()
        if existing:
            existing.tos_note = reg[kind].tos_note  # note CGU tenue à jour (audit des sources)
        else:
            db.add(Source(name=name, kind=kind, url=url, language=lang, country=country, enabled=False, trust=trust, tos_note=reg[kind].tos_note))
    db.commit()
