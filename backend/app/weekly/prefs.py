"""Préférences du programme hebdomadaire (table weekly_preferences, une seule ligne)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import WeeklyPreferences
from .timeutil import DEFAULT_TZ, zone

DEFAULTS: dict = {
    "timezone": DEFAULT_TZ,
    "plan_weekday": 0,          # lundi
    "plan_hour": 8,             # synthèse le lundi à 8 h
    "review_weekday": 6,        # dimanche
    "review_hour": 18,          # bilan le dimanche à 18 h
    "daily_enabled": False,     # bilan quotidien facultatif
    "daily_hour": 8,
    "notifications_enabled": True,
    "remind_close_hours": 48,   # rappel avant clôture
    "alert_close_hours": 24,    # alerte immédiate avant clôture
    "remind_results": True,
    "remind_claims": True,
    "minutes_per_day": 30,
    "active_days": [0, 1, 2, 3, 4, 5, 6],
    "weekly_goal": 10,          # participations visées par semaine
    "min_interest": 40,         # en dessous : jamais proposé (pas de remplissage artificiel)
    "min_reliability": 60,
    # filtres de sélection (politique de sources, phase 6)
    "automation_mode": "mixed",  # max : A1-A2 ; mixed : A1-A5 ; manual : A1-A6 (A7 achat et A8 jamais proposés)
    "hide_facebook": False,
    "hide_instagram": False,
    "hide_creative": False,
    "favor_quick_forms": False,
    "favor_instant_win": False,
    "favor_quiz": False,
    "favor_many_prizes": False,
    "social_share_max": 30,      # part maximale (%) de concours sur réseaux sociaux dans le programme
}
AUTOMATION_MODES = {"max": ("A1", "A2"), "mixed": ("A1", "A2", "A3", "A4", "A5"), "manual": ("A1", "A2", "A3", "A4", "A5", "A6")}

_INT_BOUNDS = {"plan_weekday": (0, 6), "plan_hour": (0, 23), "review_weekday": (0, 6), "review_hour": (0, 23), "daily_hour": (0, 23),
               "remind_close_hours": (1, 336), "alert_close_hours": (1, 168), "minutes_per_day": (0, 600), "weekly_goal": (0, 500), "social_share_max": (0, 100),
               "min_interest": (0, 100), "min_reliability": (0, 100)}


def get_prefs(db: Session) -> dict:
    row = db.get(WeeklyPreferences, 1)
    return {**DEFAULTS, **((row.value or {}) if row else {})}


def update_prefs(db: Session, patch: dict) -> dict:
    cur = get_prefs(db)
    for k, v in (patch or {}).items():
        if k not in DEFAULTS or v is None:
            continue
        if k in _INT_BOUNDS:
            lo, hi = _INT_BOUNDS[k]
            cur[k] = max(lo, min(hi, int(v)))
        elif k == "timezone":
            if zone(str(v)).key != str(v):
                raise ValueError(f"Fuseau horaire inconnu : {v}")
            cur[k] = str(v)
        elif k == "automation_mode":
            if v not in AUTOMATION_MODES:
                raise ValueError(f"Mode d'automatisation inconnu : {v} (max, mixed, manual)")
            cur[k] = v
        elif k == "active_days":
            days = sorted({int(x) for x in v if 0 <= int(x) <= 6})
            cur[k] = days
        else:
            cur[k] = bool(v)
    if cur["alert_close_hours"] > cur["remind_close_hours"]:
        cur["alert_close_hours"] = cur["remind_close_hours"]
    row = db.get(WeeklyPreferences, 1)
    if row is None:
        db.add(WeeklyPreferences(id=1, value=cur))
    else:
        row.value = cur
    db.commit()
    return cur
