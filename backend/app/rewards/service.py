"""M05 : résultats, gains, réclamations, échéances."""
from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..db.models import Claim, Contest, Participation, Result
from ..notifications.service import notify
from .phishing import analyze_message

CLAIM_STATUSES = ("to_claim", "claimed", "received", "expired", "refused")


def record_result(db: Session, *, contest_id: int | None, participation_id: int | None, outcome: str, message_text: str | None, sender: str | None) -> Result:
    if outcome not in ("won", "lost", "pending"):
        raise ValueError("outcome invalide")
    contest = db.get(Contest, contest_id) if contest_id else None
    part = db.get(Participation, participation_id) if participation_id else None
    if part and not contest:
        contest = part.contest
    participated = bool(part) or bool(contest and any(p.status in ("submitted", "confirmed") for p in contest.participations))
    org_domain = None
    if contest:
        org_domain = (urlsplit(contest.url).hostname or "").lower().removeprefix("www.") or None
        if contest.organizer and contest.organizer.website:
            org_domain = (urlsplit(contest.organizer.website).hostname or "").lower().removeprefix("www.") or org_domain
    score, flags = analyze_message(message_text, sender, org_domain, participated)
    r = Result(contest_id=contest.id if contest else None, participation_id=part.id if part else None, outcome=outcome,
               message_text=message_text, sender=sender, phishing_score=score, phishing_flags=flags)
    db.add(r)
    db.flush()
    title = contest.title[:120] if contest else "concours inconnu"
    if outcome == "won":
        if score >= 50:
            notify(db, "phishing", f"Message de gain suspect ({score}/100) : {title}", "; ".join(flags), r.contest_id, dedup_key=f"phish:{r.id}")
        else:
            notify(db, "win", f"Gain annoncé : {title}", "Vérifiez puis réclamez votre lot.", r.contest_id, dedup_key=f"win:{r.id}")
            claim_days = None
            if contest:
                for j in contest.justifications or []:
                    if j.get("field") == "claim":
                        try:
                            claim_days = int(str(j["decision"]).split()[0])
                        except (ValueError, IndexError):
                            pass
            best = max(contest.prizes, key=lambda p: p.value_eur or 0) if contest and contest.prizes else None
            db.add(Claim(result_id=r.id, prize_name=best.name[:500] if best else None, value_eur=best.value_eur if best else None,
                         deadline=date.today() + timedelta(days=claim_days) if claim_days else None))
    audit(db, "user", "result_record", result_id=r.id, outcome=outcome, phishing=score)
    db.commit()
    return r


def create_claim(db: Session, result_id: int, **kw) -> Claim:
    if not db.get(Result, result_id):
        raise ValueError("Résultat introuvable")
    c = Claim(result_id=result_id, **{k: v for k, v in kw.items() if v is not None})
    db.add(c)
    db.commit()
    return c


def update_claim(db: Session, c: Claim, patch: dict) -> Claim:
    if "status" in patch and patch["status"] is not None:
        if patch["status"] not in CLAIM_STATUSES:
            raise ValueError("Statut invalide")
        c.status = patch["status"]
    for k in ("notes", "deadline", "fees_eur", "value_eur"):
        if patch.get(k) is not None:
            setattr(c, k, patch[k])
    audit(db, "user", "claim_update", claim_id=c.id, status=c.status)
    db.commit()
    return c


def check_deadlines(db: Session, today: date | None = None) -> int:
    """Alertes d'échéance (J-7, J-2) et expiration automatique."""
    t = today or date.today()
    n = 0
    for c in db.scalars(select(Claim).where(Claim.status == "to_claim", Claim.deadline.is_not(None))):
        left = (c.deadline - t).days
        if left < 0:
            c.status = "expired"
            notify(db, "claim_deadline", f"Réclamation expirée : {c.prize_name or 'lot'}", None, c.result.contest_id, dedup_key=f"claimexp:{c.id}")
            n += 1
        elif left <= 7:
            k = "2" if left <= 2 else "7"
            if notify(db, "claim_deadline", f"Réclamation à faire sous {left} j : {c.prize_name or 'lot'}", None, c.result.contest_id, dedup_key=f"claim{k}:{c.id}"):
                n += 1
    db.commit()
    return n
