"""Type de jeu, comme le présentent les sites agrégateurs : tirage au sort, instant gagnant, quiz, créatif, réseaux sociaux."""
from __future__ import annotations

import re

from ..i18n.geo import norm

GAME_TYPES = ("instant_win", "creative", "quiz", "social", "draw")

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("instant_win", re.compile(r"instants? gagnants?|instant win|ticket gagnant|jeu de grattage|carte a gratter|roue de la fortune|tournez la roue|spin the wheel|sofortgewinn")),
    ("creative", re.compile(r"concours (photo|video|de dessin|de recette|creatif|d.ecriture)|meilleure? (photo|recette|video)|envoyez (votre|vos) (photo|dessin|recette|video|creation)|jury|photo contest|"
                            r"vote du public|votes? des internautes")),
    ("quiz", re.compile(r"\bquiz\b|questionnaire|repondez (a|aux) (la |les )?questions?|bonnes? reponses?|question subsidiaire|trivia")),
    ("social", re.compile(r"(instagram|facebook|tiktok)\b.{0,80}\b(commente[rz]?|commentaire|identifie[rz]?|tague[rz]?|mentionne[rz]?)\b|"
                          r"\b(commente[rz]?|abonne-toi|abonnez-vous|identifie[rz]?|tague[rz]?|likez?|aimez)\b.{0,80}(instagram|facebook|tiktok|publication|post\b)")),
    ("draw", re.compile(r"tirage au sort|tire au sort|tirage|sweepstakes?|drawing|sorteo|verlosung|estrazione|sorteio|loting")),
]
_SOCIAL_HOSTS = re.compile(r"(^|\.)(facebook|instagram|tiktok|twitter|x|youtube)\.com$")


def classify_game_type(text: str, url: str | None = None, flags: list[str] | None = None) -> str | None:
    """Premier type reconnu par ordre de spécificité ; None si rien n'est établi (jamais deviné)."""
    t = norm(text or "")
    for kind, rx in _RULES:
        if rx.search(t):
            return kind
    from urllib.parse import urlsplit

    # (le drapeau social_entry n'est pas utilisé : trop sensible aux pieds de page « suivez-nous sur Facebook »)
    if url and _SOCIAL_HOSTS.search((urlsplit(url).hostname or "").lower()):
        return "social"
    return None
