"""Indice d'automatisabilité (A1 à A8) et indice de difficulté de participation (1 à 5).

Classement déterministe à partir des faits déjà établis (type de jeu, mode de participation, drapeaux,
gratuité, éligibilité, accès au règlement). Il ne décide jamais seul d'une participation automatique :
la politique d'automatisation (règlement + consentement + absence de CAPTCHA) reste prioritaire.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from ..i18n.geo import norm

CLASSES: dict[str, str] = {
    "A1": "Formulaire web standard",
    "A2": "Quiz ou formulaire avec réponses",
    "A3": "Participation par e-mail",
    "A4": "Participation sur réseau social",
    "A5": "Concours créatif",
    "A6": "Interaction humaine particulière",
    "A7": "Achat nécessaire",
    "A8": "Impossible ou non vérifiable",
}
DIFFICULTY_LABELS = {1: "très facile", 2: "facile", 3: "moyenne", 4: "difficile", 5: "très difficile"}
_BASE_DIFFICULTY = {"A1": 1, "A2": 2, "A3": 2, "A4": 3, "A5": 4, "A6": 4, "A7": 4, "A8": 5}

PLATFORMS = ("facebook", "instagram", "tiktok", "x", "youtube")
_HOST_PLATFORM = re.compile(r"(^|\.)(facebook|fb|instagram|tiktok|twitter|x|youtube)\.com$")
_TEXT_PLATFORM = [("instagram", re.compile(r"\binstagram\b")), ("facebook", re.compile(r"\bfacebook\b")),
                  ("tiktok", re.compile(r"\btiktok\b")), ("x", re.compile(r"\btwitter\b|\bsur x\b")), ("youtube", re.compile(r"\byoutube\b"))]
_EMAIL_ENTRY = re.compile(r"(envoye[rz]|adresse[rz]?|par) (un |votre )?(e-?mail|courriel|mail)\b.{0,60}(a l.adresse|a :|@)|participation par (e-?mail|courriel)")
_HUMAN_ENTRY = re.compile(r"en magasin|sur place|borne|bulletin papier|par courrier|par voie postale|par sms|appel(ez|er) le|par telephone|"
                          r"carte postale|urne")
_SOCIAL_ACTION = re.compile(r"\b(commente[rz]?|abonne[rz]?-?(toi|vous)?|identifie[rz]?|tague[rz]?|partage[rz]?|like[rz]?|repost)\b")


def social_platform(url: str | None, text: str) -> str | None:
    host = (urlsplit(url or "").hostname or "").lower().removeprefix("www.").removeprefix("m.")
    m = _HOST_PLATFORM.search(host)
    if m:
        p = m.group(2)
        return {"fb": "facebook", "twitter": "x"}.get(p, p)
    t = norm(text or "")
    if _SOCIAL_ACTION.search(t):
        for name, rx in _TEXT_PLATFORM:
            if rx.search(t):
                return name
    return None


def classify(*, url: str | None, text: str, game_type: str | None, entry_method: str | None, flags: list[str],
             free_status: str, fr_eligible: str, has_rules: bool, has_answers: bool = False) -> dict:
    """Retourne {class, label, reason, difficulty, difficulty_label, platform}."""
    t = norm(text or "")
    fl = set(flags or [])
    platform = social_platform(url, text) if game_type == "social" or entry_method == "social" else None
    if not platform:
        host_platform = social_platform(url, "")
        if host_platform:
            platform = host_platform

    if not url or fr_eligible == "no" or ("page_inaccessible" in fl and not has_rules):
        cls, why = "A8", ("Non accessible depuis la France" if fr_eligible == "no" else "Page ou règlement inaccessible : participation non vérifiable")
    elif free_status == "purchase_required":
        cls, why = "A7", "Achat obligatoire sans voie gratuite"
    elif game_type == "creative":
        cls, why = "A5", "Création demandée (photo, texte, recette, vidéo…)"
    elif game_type == "social" or entry_method == "social" or platform:
        cls, why = "A4", f"Participation sur {platform.capitalize() if platform else 'un réseau social'}"
    elif entry_method in ("mail", "sms") or "captcha" in fl or "login_required" in fl or _HUMAN_ENTRY.search(t):
        bits = [b for b, ok in (("CAPTCHA", "captcha" in fl), ("compte à créer ou connexion", "login_required" in fl),
                                ("courrier ou SMS", entry_method in ("mail", "sms"))) if ok] or ["démarche hors formulaire (magasin, courrier, téléphone…)"]
        cls, why = "A6", "Action humaine nécessaire : " + ", ".join(bits)
    elif entry_method == "email" or _EMAIL_ENTRY.search(t):
        cls, why = "A3", "Participation en envoyant un e-mail"
    elif game_type == "quiz" or entry_method == "quiz" or has_answers:
        cls, why = "A2", "Formulaire avec questions"
    else:
        cls, why = "A1", "Formulaire web standard" + (" (instant gagnant)" if game_type == "instant_win" else "")

    d = _BASE_DIFFICULTY[cls]
    d += ("captcha" in fl and cls != "A6") + ("login_required" in fl and cls != "A6")
    if entry_method == "mail":
        d += 1
    d = max(1, min(5, d))
    return {"class": cls, "label": CLASSES[cls], "reason": why, "difficulty": d, "difficulty_label": DIFFICULTY_LABELS[d], "platform": platform}


def apply(contest, rule_text: str = "") -> dict:
    """Calcule et enregistre la classification sur le concours."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import object_session

    from ..db.models import Answer

    has_rules = any(r.origin in ("fetched", "user") for r in (contest.rules or []))
    # requête directe : charger la relation ici la figerait (réponses ajoutées ensuite par contest_id invisibles)
    db = object_session(contest)
    has_answers = bool(db.scalar(select(func.count()).select_from(Answer).where(Answer.contest_id == contest.id))) if db and contest.id else False
    text = " ".join(filter(None, [contest.title, contest.description, rule_text or (contest.rules[0].text if contest.rules else "")]))
    r = classify(url=contest.url, text=text, game_type=contest.game_type, entry_method=contest.entry_method, flags=contest.flags or [],
                 free_status=contest.free_status, fr_eligible=contest.fr_eligible, has_rules=has_rules, has_answers=has_answers)
    contest.automation_class = r["class"]
    contest.difficulty = r["difficulty"]
    contest.social_platform = r["platform"]
    return r
