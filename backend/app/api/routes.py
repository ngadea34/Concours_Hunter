"""Routes REST /api (contrat : docs/project/API.md)."""
from __future__ import annotations

import platform
import shutil
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import __version__
from ..admin import backup as bk
from ..admin.settings_service import get_settings_dict, update_settings
from ..analytics.stats import compute
from ..audit import audit
from ..config import get_settings
from ..db.models import Answer, AuditLog, Claim, Contest, ContestSighting, Notification, Participation, Result, ScanJob, Source
from ..db.session import get_db
from ..discovery.base import load_connectors
from ..discovery.pipeline import add_contest_by_url, run_scan
from ..i18n.geo import norm
from ..intelligence.llm import OllamaClient
from ..intelligence.qualify import add_rules, qualify
from ..participation import service as ps
from ..participation.profile import get_consents, get_profile, save_consents, save_profile
from ..rewards import service as rs
from ..scheduler.runner import runner
from ..security.sanitize import is_safe_http_url
from . import serializers as S

router = APIRouter(prefix="/api")


def _404(obj: Any, what: str = "Ressource") -> Any:
    if obj is None:
        raise HTTPException(404, f"{what} introuvable")
    return obj


def _contest(db: Session, cid: int) -> Contest:
    return _404(db.get(Contest, cid), "Concours")


# ------------------------------------------------------------------ santé / auth
@router.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/auth/check")
def auth_check(request: Request) -> dict:
    return {"ok": True, "needs_token": not getattr(request.state, "trusted", False) and not getattr(request.state, "token_ok", False)}


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    return compute(db)


# ------------------------------------------------------------------ concours
SORTS = {"end_date": Contest.end_date.asc().nulls_last(), "-interest": Contest.interest_score.desc().nulls_last(),
         "-reliability": Contest.reliability_score.desc().nulls_last(), "-created": Contest.created_at.desc()}


@router.get("/contests")
def list_contests(q: str | None = None, status: str | None = None, category: str | None = None, free_status: str | None = None,
                  fr_eligible: str | None = None, closing_within_days: int | None = None, min_reliability: int | None = None,
                  sort: str = "-interest", page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100), db: Session = Depends(get_db)) -> dict:
    stmt = select(Contest).where(Contest.merged_into_id.is_(None))
    if q:
        like = f"%{q.strip()[:100]}%"
        stmt = stmt.where(or_(Contest.title.ilike(like), Contest.prize_summary.ilike(like), Contest.description.ilike(like)))
    if status:
        stmt = stmt.where(Contest.status.in_(status.split(",")))
    else:
        stmt = stmt.where(Contest.status.not_in(("rejected", "expired", "archived")))
    if category:
        stmt = stmt.where(Contest.category == category)
    if free_status:
        stmt = stmt.where(Contest.free_status == free_status)
    if fr_eligible:
        stmt = stmt.where(Contest.fr_eligible == fr_eligible)
    if closing_within_days is not None:
        from datetime import timedelta

        stmt = stmt.where(Contest.end_date >= date.today(), Contest.end_date <= date.today() + timedelta(days=closing_within_days))
    if min_reliability is not None:
        stmt = stmt.where(Contest.reliability_score >= min_reliability)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(SORTS.get(sort, SORTS["-interest"]), Contest.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [S.contest_summary(c) for c in items], "total": total, "page": page, "page_size": page_size}


class NewContest(BaseModel):
    url: str = Field(max_length=1000)
    title: str | None = Field(None, max_length=500)


@router.post("/contests")
def create_contest(body: NewContest, db: Session = Depends(get_db)) -> dict:
    if not is_safe_http_url(body.url):
        raise HTTPException(400, "URL invalide (http/https public uniquement)")
    c = add_contest_by_url(db, body.url, body.title)
    audit(db, "user", "contest_add", contest_id=c.id)
    db.commit()
    return S.contest_detail(c)


@router.get("/contests/{cid}")
def get_contest(cid: int, db: Session = Depends(get_db)) -> dict:
    return S.contest_detail(_contest(db, cid))


class ContestPatch(BaseModel):
    status: str | None = None
    notes: str | None = Field(None, max_length=5000)
    personal_interest: int | None = Field(None, ge=0, le=10)


@router.patch("/contests/{cid}")
def patch_contest(cid: int, body: ContestPatch, db: Session = Depends(get_db)) -> dict:
    c = _contest(db, cid)
    if body.status:
        if body.status not in ("new", "qualified", "to_verify", "rejected", "expired", "participated", "archived"):
            raise HTTPException(400, "Statut invalide")
        if body.status == "qualified" and (c.free_status not in ("free", "free_alternative") or c.fr_eligible != "yes"):
            raise HTTPException(400, "Validez d'abord la gratuité et l'éligibilité (vérification humaine)")
        c.status = body.status
    if body.notes is not None:
        c.notes = body.notes
    if body.personal_interest is not None:
        c.personal_interest = body.personal_interest
        qualify(db, c)
    audit(db, "user", "contest_patch", contest_id=cid, **body.model_dump(exclude_none=True, exclude={"notes"}))
    db.commit()
    return S.contest_detail(c)


class Requalify(BaseModel):
    rules_text: str | None = Field(None, max_length=200_000)


@router.post("/contests/{cid}/requalify")
def requalify(cid: int, body: Requalify, db: Session = Depends(get_db)) -> dict:
    c = _contest(db, cid)
    if body.rules_text and len(body.rules_text.strip()) > 50:
        add_rules(db, c, body.rules_text, None, "user")
    if c.status in ("rejected", "to_verify", "new"):
        c.status = "new"
    qualify(db, c, force=True)
    db.commit()
    return S.contest_detail(c)


class Verify(BaseModel):
    field: str
    decision: str
    evidence: str | None = Field(None, max_length=2000)


@router.post("/contests/{cid}/verify")
def verify(cid: int, body: Verify, db: Session = Depends(get_db)) -> dict:
    c = _contest(db, cid)
    maps = {"free": {"yes": "free", "no": "purchase_required", "free": "free", "free_alternative": "free_alternative", "purchase_required": "purchase_required"},
            "eligibility": {"yes": "yes", "no": "no"}, "automation": {"yes": "allowed", "no": "forbidden"}}
    if body.field not in maps or body.decision not in maps[body.field]:
        raise HTTPException(400, "Champ ou décision invalide")
    decision = maps[body.field][body.decision]
    just = [j for j in (c.justifications or []) if not (j.get("field") == body.field and j.get("method") == "human")]
    just.append({"field": body.field, "decision": decision, "evidence": body.evidence or "Validé par l'utilisateur", "method": "human"})
    c.justifications = just
    if c.status in ("to_verify", "rejected", "new"):
        c.status = "new"
    qualify(db, c)
    audit(db, "user", "verify", contest_id=cid, field=body.field, decision=decision)
    db.commit()
    return S.contest_detail(c)


@router.get("/review-queue")
def review_queue(db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(select(Contest).where(Contest.status == "to_verify", Contest.merged_into_id.is_(None)).order_by(Contest.end_date.asc().nulls_last()).limit(200))
    return [S.contest_summary(c) for c in items]


# ------------------------------------------------------------------ participations
class NewParticipation(BaseModel):
    mode: str | None = None


def _part(db: Session, pid: int) -> Participation:
    return _404(db.get(Participation, pid), "Participation")


@router.post("/contests/{cid}/participations")
def create_participation(cid: int, body: NewParticipation, db: Session = Depends(get_db)) -> dict:
    try:
        p = ps.prepare(db, _contest(db, cid), body.mode)
    except ps.ParticipationError as e:
        raise HTTPException(409, str(e)) from e
    if p.mode == "auto" and p.status == "prepared":
        runner.run_now("auto")
    return S.participation(p)


@router.get("/participations")
def list_participations(status: str | None = None, url: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    if url:
        return [S.participation(p) for p in ps.find_by_url(db, url)]
    stmt = select(Participation).order_by(Participation.id.desc()).limit(300)
    if status:
        stmt = stmt.where(Participation.status.in_(status.split(",")))
    return [S.participation(p) for p in db.scalars(stmt)]


@router.get("/participations/{pid}/prefill")
def get_prefill(pid: int, db: Session = Depends(get_db)) -> dict:
    p = _part(db, pid)
    audit(db, "user", "prefill_read", participation_id=pid)
    db.commit()
    return ps.prefill(db, p)


class Mark(BaseModel):
    note: str | None = Field(None, max_length=2000)
    time_spent_minutes: float | None = None
    error: str | None = Field(None, max_length=1000)


def _mark(db: Session, pid: int, status: str, body: Mark) -> dict:
    try:
        return S.participation(ps.mark(db, _part(db, pid), status, note=body.note, error=body.error, minutes=body.time_spent_minutes))
    except ps.ParticipationError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/participations/{pid}/submitted")
def p_submitted(pid: int, body: Mark, db: Session = Depends(get_db)) -> dict:
    return _mark(db, pid, "submitted", body)


@router.post("/participations/{pid}/confirmed")
def p_confirmed(pid: int, body: Mark, db: Session = Depends(get_db)) -> dict:
    return _mark(db, pid, "confirmed", body)


@router.post("/participations/{pid}/failed")
def p_failed(pid: int, body: Mark, db: Session = Depends(get_db)) -> dict:
    return _mark(db, pid, "failed", body)


@router.post("/participations/{pid}/cancel")
def p_cancel(pid: int, db: Session = Depends(get_db)) -> dict:
    return _mark(db, pid, "cancelled", Mark())


class Proof(BaseModel):
    kind: str = "note"
    data_url: str | None = Field(None, max_length=7_000_000)
    note: str | None = Field(None, max_length=2000)


@router.post("/participations/{pid}/proofs")
def p_proof(pid: int, body: Proof, db: Session = Depends(get_db)) -> dict:
    try:
        return S.participation(ps.add_proof(db, _part(db, pid), body.kind, body.data_url, body.note))
    except ps.ParticipationError as e:
        raise HTTPException(400, str(e)) from e


# ------------------------------------------------------------------ résultats / gains
class NewResult(BaseModel):
    contest_id: int | None = None
    participation_id: int | None = None
    outcome: str
    message_text: str | None = Field(None, max_length=20000)
    sender: str | None = Field(None, max_length=300)


@router.get("/results")
def list_results(db: Session = Depends(get_db)) -> list[dict]:
    return [S.result(r) for r in db.scalars(select(Result).order_by(Result.id.desc()).limit(300))]


@router.post("/results")
def create_result(body: NewResult, db: Session = Depends(get_db)) -> dict:
    try:
        return S.result(rs.record_result(db, **body.model_dump()))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class VerifyResult(BaseModel):
    verified: bool


@router.post("/results/{rid}/verify")
def verify_result(rid: int, body: VerifyResult, db: Session = Depends(get_db)) -> dict:
    r = _404(db.get(Result, rid), "Résultat")
    r.verified = body.verified
    if body.verified and r.outcome == "won" and not db.scalars(select(Claim).where(Claim.result_id == r.id)).first():
        rs.create_claim(db, r.id)
    audit(db, "user", "result_verify", result_id=rid, verified=body.verified)
    db.commit()
    return S.result(r)


@router.get("/claims")
def list_claims(db: Session = Depends(get_db)) -> list[dict]:
    return [S.claim(c) for c in db.scalars(select(Claim).order_by(Claim.deadline.asc().nulls_last(), Claim.id.desc()))]


class NewClaim(BaseModel):
    result_id: int
    prize_name: str | None = None
    deadline: date | None = None
    fees_eur: float | None = None
    value_eur: float | None = None


@router.post("/claims")
def new_claim(body: NewClaim, db: Session = Depends(get_db)) -> dict:
    try:
        return S.claim(rs.create_claim(db, body.result_id, prize_name=body.prize_name, deadline=body.deadline, fees_eur=body.fees_eur, value_eur=body.value_eur))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


class ClaimPatch(BaseModel):
    status: str | None = None
    notes: str | None = None
    deadline: date | None = None
    fees_eur: float | None = None
    value_eur: float | None = None


@router.patch("/claims/{cid}")
def patch_claim(cid: int, body: ClaimPatch, db: Session = Depends(get_db)) -> dict:
    try:
        return S.claim(rs.update_claim(db, _404(db.get(Claim, cid), "Réclamation"), body.model_dump()))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/answers")
def list_answers(q: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Answer).order_by(Answer.id.desc()).limit(200)
    if q:
        stmt = stmt.where(Answer.question_norm.contains(norm(q)[:100]))
    return [S.answer(a) for a in db.scalars(stmt)]


# ------------------------------------------------------------------ notifications
@router.get("/notifications")
def list_notifications(unread_only: bool = False, db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Notification).order_by(Notification.id.desc()).limit(200)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    return [S.notification(n) for n in db.scalars(stmt)]


@router.post("/notifications/read-all")
def read_all(db: Session = Depends(get_db)) -> dict:
    for n in db.scalars(select(Notification).where(Notification.read.is_(False))):
        n.read = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/{nid}/read")
def read_one(nid: int, db: Session = Depends(get_db)) -> dict:
    _404(db.get(Notification, nid), "Notification").read = True
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ sources
def _source_out(db: Session, s: Source) -> dict:
    n = db.scalar(select(func.count(func.distinct(ContestSighting.contest_id))).where(ContestSighting.source_id == s.id)) or 0
    return S.source(s, n)


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)) -> list[dict]:
    return [_source_out(db, s) for s in db.scalars(select(Source).order_by(Source.name))]


class NewSource(BaseModel):
    name: str = Field(max_length=200)
    kind: str
    url: str = Field(max_length=1000)
    language: str | None = None
    country: str | None = None
    config: dict | None = None


@router.post("/sources")
def new_source(body: NewSource, db: Session = Depends(get_db)) -> dict:
    if body.kind not in load_connectors():
        raise HTTPException(400, f"Type inconnu. Types : {', '.join(load_connectors())}")
    if not is_safe_http_url(body.url):
        raise HTTPException(400, "URL invalide")
    if db.scalars(select(Source).where(Source.url == body.url)).first():
        raise HTTPException(409, "Source déjà présente")
    cls = load_connectors()[body.kind]
    s = Source(name=body.name, kind=body.kind, url=body.url, language=body.language, country=body.country, config=body.config or {}, tos_note=cls.tos_note)
    db.add(s)
    audit(db, "user", "source_add", name=body.name, kind=body.kind)
    db.commit()
    return _source_out(db, s)


class SourcePatch(BaseModel):
    enabled: bool | None = None
    name: str | None = None
    config: dict | None = None


@router.patch("/sources/{sid}")
def patch_source(sid: int, body: SourcePatch, db: Session = Depends(get_db)) -> dict:
    s = _404(db.get(Source, sid), "Source")
    if body.enabled is not None:
        s.enabled = body.enabled
    if body.name:
        s.name = body.name
    if body.config is not None:
        s.config = body.config
    audit(db, "user", "source_patch", source_id=sid, enabled=body.enabled)
    db.commit()
    return _source_out(db, s)


@router.post("/sources/{sid}/scan")
def scan_source(sid: int, db: Session = Depends(get_db)) -> dict:
    s = _404(db.get(Source, sid), "Source")
    if db.scalars(select(ScanJob).where(ScanJob.source_id == sid, ScanJob.status == "running")).first():
        raise HTTPException(409, "Scan déjà en cours pour cette source")
    job = ScanJob(source_id=sid, kind="scan", status="running")
    db.add(job)
    db.commit()
    job_id = job.id

    def _bg() -> None:
        from ..db.session import session_scope

        with session_scope() as db2:
            run_scan(db2, db2.get(Source, sid), job=db2.get(ScanJob, job_id))

    import threading

    threading.Thread(target=_bg, daemon=True).start()
    return S.scan_job(job)


@router.get("/scan-jobs")
def scan_jobs(db: Session = Depends(get_db)) -> list[dict]:
    return [S.scan_job(j) for j in db.scalars(select(ScanJob).order_by(ScanJob.id.desc()).limit(50))]


# ------------------------------------------------------------------ profil, consentements, réglages
@router.get("/profile")
def r_get_profile(db: Session = Depends(get_db)) -> dict:
    return get_profile(db)


@router.put("/profile")
def r_put_profile(body: dict, db: Session = Depends(get_db)) -> dict:
    audit(db, "user", "profile_update")
    return save_profile(db, body)


@router.get("/consents")
def r_get_consents(db: Session = Depends(get_db)) -> dict:
    return get_consents(db)


@router.put("/consents")
def r_put_consents(body: dict, db: Session = Depends(get_db)) -> dict:
    audit(db, "user", "consents_update", **{k: v for k, v in body.items() if isinstance(v, bool)})
    return save_consents(db, body)


@router.get("/settings")
def r_get_settings(db: Session = Depends(get_db)) -> dict:
    return get_settings_dict(db)


@router.put("/settings")
def r_put_settings(body: dict, db: Session = Depends(get_db)) -> dict:
    try:
        out = update_settings(db, body)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e)) from e
    audit(db, "user", "settings_update", keys=sorted(body))
    db.commit()
    return out


# ------------------------------------------------------------------ planificateur
@router.get("/scheduler/status")
def sched_status() -> dict:
    return runner.status()


@router.post("/scheduler/pause")
def sched_pause() -> dict:
    runner.pause()
    return runner.status()


@router.post("/scheduler/resume")
def sched_resume() -> dict:
    runner.resume()
    return runner.status()


@router.post("/scheduler/stop-all")
def sched_stop() -> dict:
    runner.stop_all()
    return runner.status()


@router.post("/scheduler/run/{job_id}")
def sched_run(job_id: str) -> dict:
    try:
        runner.run_now(job_id)
    except KeyError as e:
        raise HTTPException(404, "Tâche inconnue") from e
    return runner.status()


# ------------------------------------------------------------------ administration
@router.post("/admin/backup")
def admin_backup() -> dict:
    return bk.create_backup(label="manual")


@router.get("/admin/backups")
def admin_backups() -> list[dict]:
    return bk.list_backups()


class Restore(BaseModel):
    name: str


@router.post("/admin/restore")
def admin_restore(body: Restore) -> dict:
    runner.pause()
    try:
        bk.restore_backup(body.name)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e)) from e
    finally:
        runner.resume()
    return {"ok": True}


@router.get("/admin/diagnostics")
def diagnostics(db: Session = Depends(get_db)) -> dict:
    s = get_settings()
    st = get_settings_dict(db)
    client = OllamaClient(st["ollama_url"])
    models = client.models()
    return {"python": platform.python_version(), "platform": platform.platform(), "db_path": str(s.db_path),
            "db_size": s.db_path.stat().st_size if s.db_path.exists() else 0,
            "ollama": {"reachable": bool(models), "models": models}, "disk_free_gb": round(shutil.disk_usage(s.data_dir).free / 1e9, 1),
            "version": __version__, "connectors": sorted(load_connectors())}


@router.get("/admin/logs")
def admin_logs(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)) -> list[dict]:
    return [{"ts": a.ts.isoformat(), "actor": a.actor, "action": a.action, "detail": a.detail}
            for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))]
