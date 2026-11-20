"""Gestionnaire d'actions : tâches personnelles ou générées depuis les concours, résultats, gains et promotions."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Claim, Promotion, WeeklyPlanItem, WeeklyResult, WeeklyTask, WeeklyTaskHistory, utcnow
from .timeutil import end_of_day_utc

STATUSES = ("todo", "in_progress", "waiting", "done", "cancelled", "expired")
OPEN = ("todo", "in_progress", "waiting")
PRIORITIES = ("high", "medium", "low")
ACTIONS = ("custom", "verify_rules", "participate", "photo_ticket", "send_barcode", "send_proof", "check_draw", "claim",
           "confirm_receipt", "buy", "follow_refund")


def _hist(t: WeeklyTask, field: str, old, new, actor: str = "user") -> None:
    t.history.append(WeeklyTaskHistory(field=field, old=None if old is None else str(old)[:300], new=None if new is None else str(new)[:300], actor=actor))


def ensure_task(db: Session, key: str, title: str, description: str | None = None, *, action: str = "custom", priority: str = "medium",
                due_at: datetime | None = None, contest_id: int | None = None, participation_id: int | None = None,
                claim_id: int | None = None, promotion_id: int | None = None, plan_item_id: int | None = None) -> WeeklyTask:
    """Crée une tâche générée une seule fois (clé unique). Une tâche annulée ou terminée n'est jamais recréée.
    Si la tâche existe encore ouverte, son échéance suit la donnée réelle (ex. date de clôture modifiée)."""
    t = db.scalars(select(WeeklyTask).where(WeeklyTask.auto_key == key)).first()
    if t is None:
        t = WeeklyTask(auto_key=key, title=title[:300], description=description, action=action, priority=priority, due_at=due_at,
                       contest_id=contest_id, participation_id=participation_id, claim_id=claim_id, promotion_id=promotion_id,
                       plan_item_id=plan_item_id)
        db.add(t)
        _hist(t, "status", None, "todo", "system")
    elif t.status in OPEN + ("expired",) and due_at and t.due_at != due_at and not any(h.field == "due_at" and h.actor == "user" for h in t.history):
        _hist(t, "due_at", t.due_at, due_at, "system")
        t.due_at = due_at
        if t.status == "expired" and due_at > utcnow():
            _hist(t, "status", "expired", "todo", "system")
            t.status = "todo"  # échéance repoussée par l'organisateur : la tâche redevient à faire
    return t


def _close(t: WeeklyTask, status: str, why: str) -> None:
    if t.status in OPEN:
        _hist(t, "status", t.status, status, "system")
        t.status = status
        t.proof_note = t.proof_note or why
        if status == "done":
            t.completed_at = utcnow()


def sync_auto_tasks(db: Session, tz, today: date) -> None:
    # 1) participations acceptées dans le programme
    for it in db.scalars(select(WeeklyPlanItem).where(WeeklyPlanItem.section == "priority", WeeklyPlanItem.decision.in_(("accepted", "done", "obsolete")))):
        c = it.contest
        key = f"participate:{it.id}"
        if it.decision == "accepted" and c.end_date and c.end_date >= today:
            ensure_task(db, key, f"Participer : {c.title[:200]}", c.url, action="participate", priority=it.priority,
                        due_at=end_of_day_utc(c.end_date, tz), contest_id=c.id, plan_item_id=it.id)
        else:
            t = db.scalars(select(WeeklyTask).where(WeeklyTask.auto_key == key)).first()
            if t:
                _close(t, "done" if it.decision == "done" else "cancelled",
                       "Participation enregistrée" if it.decision == "done" else "Concours retiré du programme")
    # 2) opportunités suivies encore à vérifier
    for it in db.scalars(select(WeeklyPlanItem).where(WeeklyPlanItem.section == "opportunity", WeeklyPlanItem.favorite.is_(True))):
        c = it.contest
        key = f"verify:{c.id}"
        if c.status == "to_verify" and (not c.end_date or c.end_date >= today):
            ensure_task(db, key, f"Vérifier le règlement : {c.title[:200]}", c.needs_human_reason, action="verify_rules", priority="medium",
                        due_at=end_of_day_utc(c.end_date - timedelta(days=2) if c.end_date and c.end_date - timedelta(days=2) >= today else (c.end_date or today + timedelta(days=7)), tz),
                        contest_id=c.id)
        elif (t := db.scalars(select(WeeklyTask).where(WeeklyTask.auto_key == key)).first()):
            _close(t, "done" if c.status in ("qualified", "rejected", "participated") else "cancelled", f"Concours désormais : {c.status}")
    # 3) résultats à vérifier
    for wr in db.scalars(select(WeeklyResult)):
        key = f"draw:{wr.participation_id}"
        when = wr.publish_date or wr.draw_date
        if wr.status in ("draw_pending", "drawn", "not_published") and when:
            ensure_task(db, key, f"Vérifier le tirage : {wr.contest.title[:200]}", wr.verify_url, action="check_draw", priority="medium",
                        due_at=end_of_day_utc(max(when, today) + timedelta(days=3), tz), contest_id=wr.contest_id, participation_id=wr.participation_id)
        elif wr.status in ("published", "winner", "not_winner", "unverifiable"):
            if (t := db.scalars(select(WeeklyTask).where(WeeklyTask.auto_key == key)).first()):
                _close(t, "done", "Résultat connu")
    # 4) gains : réclamer, puis confirmer la réception
    for cl in db.scalars(select(Claim)):
        cid = cl.result.contest_id if cl.result else None
        if cl.status == "to_claim":
            ensure_task(db, f"claim:{cl.id}", f"Réclamer le gain : {cl.prize_name or 'lot'}", "Ne payez jamais de frais pour recevoir un lot.",
                        action="claim", priority="high", due_at=end_of_day_utc(cl.deadline, tz) if cl.deadline else None, contest_id=cid, claim_id=cl.id)
        elif cl.status == "claimed":
            if (t := db.scalars(select(WeeklyTask).where(WeeklyTask.auto_key == f"claim:{cl.id}")).first()):
                _close(t, "done", "Réclamation envoyée")
            ensure_task(db, f"receipt:{cl.id}", f"Confirmer la réception : {cl.prize_name or 'lot'}", None, action="confirm_receipt",
                        priority="low", contest_id=cid, claim_id=cl.id)
        else:
            for k in (f"claim:{cl.id}", f"receipt:{cl.id}"):
                if (t := db.scalars(select(WeeklyTask).where(WeeklyTask.auto_key == k)).first()):
                    _close(t, "done" if cl.status == "received" else "cancelled", f"Gain : {cl.status}")
    # 5) promotions (aucun achat n'est jamais déclenché : seulement des rappels)
    for pr in db.scalars(select(Promotion)):
        if pr.status == "to_buy" and pr.end_date and pr.end_date >= today:
            ensure_task(db, f"buy:{pr.id}", f"Décider de l'achat : {pr.title[:200]}", "Achat à faire vous-même, si vous le souhaitez.",
                        action="buy", priority="medium", due_at=end_of_day_utc(pr.end_date, tz), promotion_id=pr.id, contest_id=pr.contest_id)
        elif (t := db.scalars(select(WeeklyTask).where(WeeklyTask.auto_key == f"buy:{pr.id}")).first()) and pr.status != "to_buy":
            _close(t, "done" if pr.status in ("bought", "to_send", "sent", "refund_pending", "refunded") else "cancelled", f"Promotion : {pr.status}")
        if pr.status in ("bought", "to_send"):
            ensure_task(db, f"proof:{pr.id}", f"Envoyer le dossier de remboursement : {pr.title[:200]}",
                        "Photographier le ticket, découper le code-barres, remplir le formulaire.", action="send_proof", priority="high",
                        due_at=end_of_day_utc(pr.send_deadline, tz) if pr.send_deadline else None, promotion_id=pr.id, contest_id=pr.contest_id)
        elif pr.status in ("sent", "refund_pending", "refunded", "refused", "cancelled", "expired"):
            if (t := db.scalars(select(WeeklyTask).where(WeeklyTask.auto_key == f"proof:{pr.id}")).first()):
                _close(t, "done" if pr.status in ("sent", "refund_pending", "refunded") else "cancelled", f"Promotion : {pr.status}")
        if pr.status in ("sent", "refund_pending"):
            ensure_task(db, f"refund:{pr.id}", f"Suivre le remboursement : {pr.title[:200]}", None, action="follow_refund", priority="low",
                        promotion_id=pr.id, contest_id=pr.contest_id)
        elif pr.status in ("refunded", "refused") and (t := db.scalars(select(WeeklyTask).where(WeeklyTask.auto_key == f"refund:{pr.id}")).first()):
            _close(t, "done", f"Promotion : {pr.status}")
    db.flush()


def expire_tasks(db: Session, now_utc: datetime) -> int:
    n = 0
    for t in db.scalars(select(WeeklyTask).where(WeeklyTask.status.in_(OPEN), WeeklyTask.due_at.is_not(None), WeeklyTask.due_at < now_utc)):
        _hist(t, "status", t.status, "expired", "system")
        t.status = "expired"
        n += 1
    db.flush()
    return n


def create_task(db: Session, *, title: str, description: str | None, priority: str, due_at: datetime | None, contest_id: int | None, action: str) -> WeeklyTask:
    if priority not in PRIORITIES or action not in ACTIONS:
        raise ValueError("Priorité ou action invalide")
    t = WeeklyTask(title=title[:300], description=description, priority=priority, due_at=due_at, contest_id=contest_id, action=action)
    db.add(t)
    _hist(t, "status", None, "todo")
    db.commit()
    return t


def update_task(db: Session, t: WeeklyTask, patch: dict) -> WeeklyTask:
    if "status" in patch and patch["status"] is not None:
        st = patch["status"]
        if st not in STATUSES:
            raise ValueError("Statut invalide")
        if st == "done" and t.action == "participate":
            # une participation n'est jamais « réalisée » sans preuve : passer par « déjà effectuée » dans le programme
            from ..db.models import Participation

            p = t.plan_item_id and db.get(WeeklyPlanItem, t.plan_item_id)
            if not (p and p.decision == "done") and not (t.participation_id and (pp := db.get(Participation, t.participation_id)) and pp.status in ("submitted", "confirmed")):
                raise ValueError("Pour une participation, utilisez « Déjà effectuée » avec une preuve de soumission")
        if st != t.status:
            _hist(t, "status", t.status, st)
            t.status = st
            t.completed_at = utcnow() if st == "done" else None
    for k in ("title", "description", "priority", "due_at", "proof_note"):
        if k in patch and patch[k] is not None:
            v = patch[k]
            if k == "priority" and v not in PRIORITIES:
                raise ValueError("Priorité invalide")
            if v != getattr(t, k):
                _hist(t, k, getattr(t, k), v)
                setattr(t, k, v)
                if k == "due_at" and t.status == "expired" and v > utcnow():
                    _hist(t, "status", "expired", "todo")
                    t.status = "todo"  # tâche reportée : de nouveau à faire
    db.commit()
    return t


def postpone_days_to_utc(d: date, tz) -> datetime:
    return end_of_day_utc(d, tz)


def due_local_iso(t: WeeklyTask, tz) -> str | None:
    if not t.due_at:
        return None
    from datetime import timezone

    return t.due_at.replace(tzinfo=timezone.utc).astimezone(tz).isoformat()

