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
}

_INT_BOUNDS = {"plan_weekday": (0, 6), "plan_hour": (0, 23), "review_weekday": (0, 6), "review_hour": (0, 23), "daily_hour": (0, 23),
               "remind_close_hours": (1, 336), "alert_close_hours": (1, 168), "minutes_per_day": (0, 600), "weekly_goal": (0, 500),
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
