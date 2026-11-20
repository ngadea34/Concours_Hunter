"""Assemble la vue « Mon programme de la semaine » (et les commandes /hunter-week)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Claim, Contest, Participation, WeeklyPlanItem, WeeklyResult, WeeklyTask
from . import plan as P
from . import results as R
from . import shop as SH
from . import tasks as T
from .prefs import get_prefs
from .timeutil import iso_week_label, now_local, week_start, zone


def context(db: Session, any_day: date | None = None, now_utc: datetime | None = None) -> dict:
    prefs = get_prefs(db)
    tz = zone(prefs["timezone"])
    nl = now_local(tz, now_utc)
    today = nl.date()
    ws = week_start(any_day or today)
    return {"prefs": prefs, "tz": tz, "today": today, "ws": ws, "we": ws + timedelta(days=6), "now_utc": now_utc}


def week_bounds_utc(ws: date, tz) -> tuple[datetime, datetime]:
    a = datetime.combine(ws, time(0, 0), tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    b = datetime.combine(ws + timedelta(days=7), time(0, 0), tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    return a, b


def item_out(it: WeeklyPlanItem, ctx: dict) -> dict:
    b = P.brief(it.contest, ctx["tz"], ctx["today"], ctx["now_utc"])
    b.update({"item_id": it.id, "priority": it.priority, "score": it.score, "reasons": it.reasons or [], "decision": it.decision,
              "favorite": it.favorite, "scheduled_day": it.scheduled_day.isoformat() if it.scheduled_day else None,
              "postponed_to": it.postponed_to.isoformat() if it.postponed_to else None, "participation_id": it.participation_id})
    return b


def result_out(w: WeeklyResult) -> dict:
    c = w.contest
    return {"id": w.id, "contest_id": c.id, "title": c.title, "organizer": c.organizer.name if c.organizer else None,
            "draw_date": w.draw_date.isoformat() if w.draw_date else None, "draw_date_estimated": w.draw_date_estimated,
            "publish_date": w.publish_date.isoformat() if w.publish_date else None,
            "prizes_count": sum(p.quantity or 1 for p in c.prizes) or None, "verify_url": w.verify_url, "status": w.status,
            "last_checked_at": w.last_checked_at.isoformat() if w.last_checked_at else None, "note": w.note,
            "participation_status": w.participation.status}


def task_out(t: WeeklyTask, tz) -> dict:
    return {"id": t.id, "title": t.title, "description": t.description, "priority": t.priority, "due_at": T.due_local_iso(t, tz),
            "status": t.status, "action": t.action, "contest_id": t.contest_id, "contest_title": t.contest.title if t.contest else None,
            "claim_id": t.claim_id, "promotion_id": t.promotion_id, "proof_note": t.proof_note, "auto": t.auto_key is not None}


def refresh(db: Session, ctx: dict) -> None:
    """Remet tout en phase avec les données réelles (dates de clôture, participations, résultats, gains)."""
    if ctx["we"] >= ctx["today"]:
        P.generate_plan(db, ctx["ws"], ctx["prefs"], ctx["today"])
    R.sync_results(db, ctx["today"])
    T.sync_auto_tasks(db, ctx["tz"], ctx["today"])
    T.expire_tasks(db, (ctx["now_utc"] or datetime.now(timezone.utc)).replace(tzinfo=None))
    db.commit()


def tasks_for(db: Session, ctx: dict, include_closed: bool = False) -> list[WeeklyTask]:
    q = select(WeeklyTask)
    if not include_closed:
        q = q.where(WeeklyTask.status.in_(T.OPEN + ("expired",)))
    rows = db.scalars(q).all()
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(rows, key=lambda t: (t.status == "expired", t.due_at is None, t.due_at or datetime.max, order.get(t.priority, 1)))


def week_view(db: Session, any_day: date | None = None, now_utc: datetime | None = None) -> dict:
    ctx = context(db, any_day, now_utc)
    refresh(db, ctx)
    ws, we, tz, today = ctx["ws"], ctx["we"], ctx["tz"], ctx["today"]
    plan = P.get_plan(db, ws)
    pri = [i for i in (plan.items if plan else []) if i.section == "priority" and i.decision != "refused"]
    pri.sort(key=lambda i: (i.decision in ("done", "obsolete"), i.scheduled_day is None, i.scheduled_day or date.max, -i.score))
    expected = R.expected_in_week(db, ws, today)
    lc = P.last_chances(db, tz, today, now_utc) if we >= today else {k: [] for k, _ in P.BUCKETS}
    opp = P.opportunities(db, ctx["prefs"], tz, today, now_utc)
    shop = SH.shop_section(db, ws, today)
    a, b = week_bounds_utc(ws, tz)
    done = db.scalar(select(func.count()).select_from(Participation).where(Participation.status.in_(("submitted", "confirmed")),
                                                                           Participation.submitted_at >= a, Participation.submitted_at < b)) or 0
    closing = db.scalar(select(func.count()).select_from(Contest).where(Contest.merged_into_id.is_(None), Contest.status.in_(P.OPEN_STATUSES),
                                                                        Contest.end_date >= max(ws, today), Contest.end_date <= we)) or 0
    cat = shop["categories"]
    promos = {b_["id"] for k in ("full_refund", "partial_refund", "ending") for b_ in cat[k] if b_.get("id")}
    kpis = {
        "priority": sum(1 for i in pri if i.decision in ("proposed", "accepted", "postponed")),
        "done": done,
        "closing": closing,
        "results_expected": len(expected),
        "results_published": sum(1 for w in expected if w.status in ("published", "winner", "not_winner")),
        "gains_to_claim": db.scalar(select(func.count()).select_from(Claim).where(Claim.status == "to_claim")) or 0,
        "promotions": len(promos),
        "refund_files": len(cat["to_send"]) + len(cat["awaiting_refund"]),
    }
    tasks = tasks_for(db, ctx)
    return {
        "week_start": ws.isoformat(), "week_end": we.isoformat(), "label": iso_week_label(ws), "today": today.isoformat(),
        "timezone": ctx["prefs"]["timezone"], "is_past": we < today, "is_current": ws <= today <= we,
        "plan": {"generated_at": plan.generated_at.isoformat() if plan else None, "capacity_minutes": plan.capacity_minutes if plan else 0,
                 "planned_minutes": plan.planned_minutes if plan else 0, "weekly_goal": ctx["prefs"]["weekly_goal"],
                 "minutes_per_day": ctx["prefs"]["minutes_per_day"]},
        "kpis": kpis,
        "priority": [item_out(i, ctx) for i in pri],
        "results": [result_out(w) for w in expected],
        "last_chances": lc,
        "opportunities": opp,
        "shop": shop,
        "tasks": [task_out(t, tz) for t in tasks],
    }
