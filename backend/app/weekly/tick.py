"""Tâche périodique M15 (toutes les 15 min) : synchronise, rappelle, génère les synthèses à l'heure choisie.

Rattrapage : si le PC était éteint lundi à 8 h, la synthèse est générée au démarrage suivant de la semaine.
Alertes immédiates : seulement les échéances critiques (clôture < 24 h d'un concours accepté), les gains et
les réclamations urgentes. Le reste est regroupé dans le bilan du jour (ou visible dans la page).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Claim, WeeklyNotification, WeeklyPlanItem, WeeklyReport, WeeklyResult
from ..notifications.service import notify
from . import reports
from .timeutil import hours_until_close, week_start
from .view import context, refresh


def _remember(db: Session, key: str, kind: str, title: str, urgent: bool, prefs: dict, contest_id: int | None = None, body: str | None = None) -> bool:
    if db.scalars(select(WeeklyNotification).where(WeeklyNotification.key == key)).first():
        return False
    n = None
    if prefs["notifications_enabled"] and urgent:
        n = notify(db, kind, title, body, contest_id, dedup_key=f"wk:{key}"[:200])
    db.add(WeeklyNotification(key=key[:150], kind=kind, title=title[:300], urgent=urgent, contest_id=contest_id,
                              notification_id=n.id if n else None))
    db.flush()
    return True


def reminders(db: Session, ctx: dict) -> int:
    prefs, tz, today, now_utc = ctx["prefs"], ctx["tz"], ctx["today"], ctx["now_utc"]
    n = 0
    items = db.scalars(select(WeeklyPlanItem).where(WeeklyPlanItem.section == "priority", WeeklyPlanItem.decision.in_(("accepted", "proposed"))))
    for it in items:
        c = it.contest
        if not c.end_date:
            continue
        h = hours_until_close(c.end_date, tz, now_utc)
        if h <= 0:
            continue
        end = c.end_date.isoformat()  # la clé change si l'organisateur modifie la date : nouveau rappel
        if h <= prefs["alert_close_hours"] and it.decision == "accepted":
            n += _remember(db, f"alert:{c.id}:{end}", "closing_soon", f"Clôture dans moins de {prefs['alert_close_hours']} h : {c.title[:150]}",
                           True, prefs, c.id, c.url)
        elif h <= prefs["remind_close_hours"]:
            n += _remember(db, f"remind:{c.id}:{end}", "closing_soon", f"Clôture dans moins de {prefs['remind_close_hours']} h : {c.title[:150]}",
                           False, prefs, c.id)
    if prefs["remind_results"]:
        for w in db.scalars(select(WeeklyResult).where(WeeklyResult.status.in_(("draw_pending", "drawn", "not_published")))):
            d = w.publish_date or w.draw_date
            if d and d == today:
                n += _remember(db, f"results:{w.id}:{d}", "draw", f"Résultats prévus aujourd'hui : {w.contest.title[:150]}", False, prefs, w.contest_id)
    if prefs["remind_claims"]:
        for cl in db.scalars(select(Claim).where(Claim.status == "to_claim", Claim.deadline.is_not(None))):
            left = (cl.deadline - today).days
            if 0 <= left <= 2:
                n += _remember(db, f"claim:{cl.id}:{cl.deadline}", "claim_deadline", f"Réclamation à faire sous {left} j : {cl.prize_name or 'lot'}",
                               True, prefs, cl.result.contest_id if cl.result else None)
    db.commit()
    return n


def _exists(db: Session, kind: str, start) -> bool:
    return db.scalars(select(WeeklyReport).where(WeeklyReport.kind == kind, WeeklyReport.period_start == start)).first() is not None


def tick(db: Session, now_utc: datetime | None = None) -> dict:
    now_utc = now_utc or datetime.now(timezone.utc)
    ctx = context(db, None, now_utc)
    prefs, tz = ctx["prefs"], ctx["tz"]
    refresh(db, ctx)
    out = {"reminders": reminders(db, ctx), "generated": []}
    nl = now_utc.astimezone(tz)
    ws = week_start(nl.date())
    plan_at = ws + timedelta(days=prefs["plan_weekday"])
    if (nl.date() > plan_at or (nl.date() == plan_at and nl.hour >= prefs["plan_hour"])) and not _exists(db, "weekly", ws):
        reports.weekly_summary(db, nl.date(), now_utc)
        out["generated"].append("weekly")
        if prefs["notifications_enabled"]:
            notify(db, "system", "Votre programme de la semaine est prêt", None, None, dedup_key=f"wk:plan:{ws}")
    review_at = ws + timedelta(days=prefs["review_weekday"])
    if (nl.date() > review_at or (nl.date() == review_at and nl.hour >= prefs["review_hour"])) and not _exists(db, "review", ws):
        reports.week_review(db, nl.date(), now_utc)
        out["generated"].append("review")
        if prefs["notifications_enabled"]:
            notify(db, "system", "Le bilan de votre semaine est prêt", None, None, dedup_key=f"wk:review:{ws}")
    prev = ws - timedelta(days=7)  # rattrapage du bilan de la semaine passée (PC éteint le dimanche soir)
    from ..db.models import WeeklyPlan

    if not _exists(db, "review", prev) and db.scalars(select(WeeklyPlan).where(WeeklyPlan.week_start == prev)).first():
        reports.week_review(db, prev, now_utc)
        out["generated"].append("review-catch-up")
    if prefs["daily_enabled"] and nl.hour >= prefs["daily_hour"] and not _exists(db, "daily", nl.date()):
        reports.daily_report(db, nl.date(), now_utc)
        out["generated"].append("daily")
        if prefs["notifications_enabled"]:
            notify(db, "system", "Votre bilan du jour est prêt", None, None, dedup_key=f"wk:daily:{nl.date()}")
    db.commit()
    return out
