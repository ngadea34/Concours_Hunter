"""API M15 « Mon programme de la semaine » (+ suivi des promotions utilisé par la rubrique Shop & Promo)."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..db.models import Contest, Promotion, WeeklyPlanItem, WeeklyReport, WeeklyResult, WeeklyTask
from ..db.session import get_db
from ..participation.service import ParticipationError
from ..weekly import plan as P
from ..weekly import reports as RP
from ..weekly import results as R
from ..weekly import tasks as T
from ..weekly.prefs import get_prefs, update_prefs
from ..weekly.shop import promo_brief
from ..weekly.timeutil import local_to_utc, zone
from ..weekly.view import context, task_out, week_view

router = APIRouter(prefix="/api")


def _day(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError as e:
        raise HTTPException(400, "Date invalide (AAAA-MM-JJ)") from e


def _get(db: Session, model: Any, key: int, msg: str) -> Any:
    obj = db.get(model, key)
    if obj is None:
        raise HTTPException(404, msg)
    return obj


def _bad(e: Exception) -> HTTPException:
    return HTTPException(400, str(e))


@router.get("/weekly")
def get_week(week: str | None = None, db: Session = Depends(get_db)) -> dict:
    return week_view(db, _day(week))


@router.post("/weekly/plan")
def make_plan(week: str | None = None, db: Session = Depends(get_db)) -> dict:
    ctx = context(db, _day(week))
    if ctx["we"] < ctx["today"]:
        raise HTTPException(409, "Semaine passée : le programme n'est plus recalculé (consultez l'historique)")
    P.generate_plan(db, ctx["ws"], ctx["prefs"], ctx["today"])
    audit(db, "user", "weekly_plan", week=ctx["ws"].isoformat())
    db.commit()
    return week_view(db, ctx["ws"])


class ItemAction(BaseModel):
    action: str
    postpone_to: str | None = None


@router.post("/weekly/items/{iid}")
def item_action(iid: int, body: ItemAction, db: Session = Depends(get_db)) -> dict:
    it = _get(db, WeeklyPlanItem, iid, "Élément introuvable")
    try:
        P.act_on_item(db, it, body.action, _day(body.postpone_to))
    except ValueError as e:
        raise _bad(e) from e
    return week_view(db, it.plan.week_start)


class Done(BaseModel):
    proof_note: str | None = Field(None, max_length=2000)
    data_url: str | None = Field(None, max_length=7_000_000)
    minutes: float | None = None


@router.post("/weekly/items/{iid}/done")
def item_done(iid: int, body: Done, db: Session = Depends(get_db)) -> dict:
    it = _get(db, WeeklyPlanItem, iid, "Élément introuvable")
    try:
        P.mark_item_done(db, it, body.proof_note, body.data_url, body.minutes)
    except (ValueError, ParticipationError) as e:
        raise _bad(e) from e
    return week_view(db, it.plan.week_start)


class Follow(BaseModel):
    contest_id: int
    follow: bool | None = None
    dismiss: bool = False


@router.post("/weekly/opportunities")
def follow_opportunity(body: Follow, db: Session = Depends(get_db)) -> dict:
    c = _get(db, Contest, body.contest_id, "Concours introuvable")
    ctx = context(db)
    plan = P.get_plan(db, ctx["ws"]) or P.generate_plan(db, ctx["ws"], ctx["prefs"], ctx["today"])
    P.set_follow(db, plan, c, body.follow, body.dismiss)
    return {"ok": True}


class ResultPatch(BaseModel):
    status: str
    note: str | None = Field(None, max_length=2000)
    verify_url: str | None = Field(None, max_length=1000)


@router.patch("/weekly/results/{rid}")
def patch_result(rid: int, body: ResultPatch, db: Session = Depends(get_db)) -> dict:
    w = _get(db, WeeklyResult, rid, "Suivi introuvable")
    if body.verify_url and not body.verify_url.startswith(("http://", "https://")):
        raise HTTPException(400, "Lien invalide")
    try:
        R.set_manual_status(db, w, body.status, body.note, body.verify_url)
    except ValueError as e:
        raise _bad(e) from e
    return {"ok": True}


# ------------------------------------------------------------------ tâches
def _due(s: str | None, tz) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as e:
        raise HTTPException(400, "Échéance invalide") from e
    if len(s) <= 10:
        dt = datetime.combine(dt.date(), time(23, 59, 59))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return local_to_utc(dt)


@router.get("/weekly/tasks")
def list_tasks(all: bool = False, db: Session = Depends(get_db)) -> list[dict]:  # noqa: A002
    from ..weekly.view import refresh, tasks_for

    ctx = context(db)
    refresh(db, ctx)
    return [task_out(t, ctx["tz"]) for t in tasks_for(db, ctx, include_closed=all)]


class NewTask(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    description: str | None = Field(None, max_length=4000)
    priority: str = "medium"
    due: str | None = None
    contest_id: int | None = None
    action: str = "custom"


@router.post("/weekly/tasks")
def new_task(body: NewTask, db: Session = Depends(get_db)) -> dict:
    tz = zone(get_prefs(db)["timezone"])
    try:
        t = T.create_task(db, title=body.title, description=body.description, priority=body.priority, due_at=_due(body.due, tz),
                          contest_id=body.contest_id, action=body.action)
    except ValueError as e:
        raise _bad(e) from e
    return task_out(t, tz)


class TaskPatch(BaseModel):
    title: str | None = Field(None, max_length=300)
    description: str | None = Field(None, max_length=4000)
    priority: str | None = None
    status: str | None = None
    due: str | None = None
    proof_note: str | None = Field(None, max_length=2000)


@router.patch("/weekly/tasks/{tid}")
def patch_task(tid: int, body: TaskPatch, db: Session = Depends(get_db)) -> dict:
    t = _get(db, WeeklyTask, tid, "Tâche introuvable")
    tz = zone(get_prefs(db)["timezone"])
    patch: dict[str, Any] = body.model_dump(exclude_none=True)
    if "due" in patch:
        patch["due_at"] = _due(patch.pop("due"), tz)
    try:
        T.update_task(db, t, patch)
    except ValueError as e:
        raise _bad(e) from e
    return task_out(t, tz)


@router.get("/weekly/tasks/{tid}/history")
def task_history(tid: int, db: Session = Depends(get_db)) -> list[dict]:
    t = _get(db, WeeklyTask, tid, "Tâche introuvable")
    return [{"at": h.at.isoformat(), "field": h.field, "old": h.old, "new": h.new, "actor": h.actor} for h in t.history]


# ------------------------------------------------------------------ préférences et synthèses
@router.get("/weekly/preferences")
def r_get_prefs(db: Session = Depends(get_db)) -> dict:
    return get_prefs(db)


@router.put("/weekly/preferences")
def r_put_prefs(body: dict, db: Session = Depends(get_db)) -> dict:
    try:
        p = update_prefs(db, body)
    except (ValueError, TypeError) as e:
        raise _bad(e) from e
    audit(db, "user", "weekly_prefs")
    db.commit()
    return p


def _report_out(r: WeeklyReport, full: bool = False) -> dict:
    d = {"id": r.id, "kind": r.kind, "period_start": r.period_start.isoformat(), "period_end": r.period_end.isoformat(),
         "generated_at": r.generated_at.isoformat()}
    if full:
        d.update({"text": r.text, "data": {k: v for k, v in (r.data or {}).items() if k != "view"}})
    return d


@router.get("/weekly/reports")
def r_list_reports(kind: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    return [_report_out(r) for r in RP.list_reports(db, kind)]


@router.post("/weekly/reports/{kind}")
def r_make_report(kind: str, week: str | None = None, db: Session = Depends(get_db)) -> dict:
    gen = {"weekly": RP.weekly_summary, "daily": RP.daily_report, "review": RP.week_review}.get(kind)
    if not gen:
        raise HTTPException(400, "Type : weekly, daily ou review")
    return _report_out(gen(db, _day(week)), full=True)


@router.get("/weekly/reports/{rid}")
def r_get_report(rid: int, db: Session = Depends(get_db)) -> dict:
    r = _get(db, WeeklyReport, rid, "Synthèse introuvable")
    return _report_out(r, full=True)


# ------------------------------------------------------------------ promotions (données M14)
PROMO_KINDS = ("full_refund", "partial_refund", "purchase_game", "discount")
PROMO_STATUSES = ("to_watch", "to_buy", "bought", "to_send", "sent", "refund_pending", "refunded", "refused", "expired", "cancelled")


class PromoIn(BaseModel):
    title: str | None = Field(None, max_length=300)
    brand: str | None = Field(None, max_length=200)
    kind: str | None = None
    url: str | None = Field(None, max_length=1000)
    product: str | None = Field(None, max_length=300)
    price_eur: float | None = Field(None, ge=0)
    refund_eur: float | None = Field(None, ge=0)
    refund_received_eur: float | None = Field(None, ge=0)
    end_date: str | None = None
    send_deadline: str | None = None
    status: str | None = None
    contest_id: int | None = None
    notes: str | None = Field(None, max_length=4000)


def _apply_promo(p: Promotion, body: PromoIn) -> None:
    data = body.model_dump(exclude_none=True)
    if "kind" in data and data["kind"] not in PROMO_KINDS:
        raise HTTPException(400, "Type invalide")
    if "status" in data and data["status"] not in PROMO_STATUSES:
        raise HTTPException(400, "Statut invalide")
    if data.get("status") == "refunded" and not (data.get("refund_received_eur") or p.refund_received_eur):
        raise HTTPException(400, "Indiquez le montant réellement reçu : un remboursement n'est « reçu » qu'une fois constaté")
    if data.get("url") and not data["url"].startswith(("http://", "https://")):
        raise HTTPException(400, "Lien invalide")
    for k in ("end_date", "send_deadline"):
        if k in data:
            data[k] = _day(data[k])
    today = date.today()
    st = data.get("status")
    if st == "bought" and not p.purchase_date:
        p.purchase_date = today
    if st == "sent" and not p.sent_date:
        p.sent_date = today
    if st == "refunded" and not p.received_date:
        p.received_date = today
    for k, v in data.items():
        setattr(p, k, v)


@router.get("/promotions")
def list_promos(db: Session = Depends(get_db)) -> list[dict]:
    today = date.today()
    return [promo_brief(p, today) for p in db.scalars(select(Promotion).order_by(Promotion.id.desc()))]


@router.post("/promotions")
def new_promo(body: PromoIn, db: Session = Depends(get_db)) -> dict:
    if not body.title:
        raise HTTPException(400, "Titre requis")
    p = Promotion(title=body.title)
    _apply_promo(p, body)
    db.add(p)
    audit(db, "user", "promotion_add")
    db.commit()
    return promo_brief(p, date.today())


@router.patch("/promotions/{pid}")
def patch_promo(pid: int, body: PromoIn, db: Session = Depends(get_db)) -> dict:
    p = _get(db, Promotion, pid, "Promotion introuvable")
    _apply_promo(p, body)
    audit(db, "user", "promotion_patch", promotion_id=pid, status=body.status)
    db.commit()
    return promo_brief(p, date.today())


class Command(BaseModel):
    line: str = Field(max_length=500)


@router.post("/weekly/command")
def r_command(body: Command, db: Session = Depends(get_db)) -> dict:
    from ..weekly.commands import run as run_week

    try:
        return run_week(db, body.line)
    except ValueError as e:
        raise _bad(e) from e
