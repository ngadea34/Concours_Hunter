"""Conversion ORM → JSON conforme à docs/project/API.md."""
from __future__ import annotations

from datetime import date, datetime

from ..db.models import Answer, Claim, Contest, Notification, Participation, Prize, Result, ScanJob, Source


def _iso(v: date | datetime | None) -> str | None:
    return v.isoformat() if v else None


def contest_summary(c: Contest) -> dict:
    today = date.today()
    return {
        "id": c.id, "title": c.title, "url": c.url,
        "organizer_name": c.organizer.name if c.organizer else None,
        "source_names": sorted({s.source.name for s in c.sightings if s.source}),
        "status": c.status, "category": c.category, "prize_summary": c.prize_summary,
        "total_prize_value_eur": c.total_prize_value_eur, "end_date": _iso(c.end_date),
        "days_left": (c.end_date - today).days if c.end_date else None, "language": c.language,
        "countries_allowed": c.eligibility.countries_allowed if c.eligibility else [],
        "reliability_score": c.reliability_score, "interest_score": c.interest_score,
        "free_status": c.free_status, "fr_eligible": c.fr_eligible, "participation_mode": c.participation_mode,
        "participated": any(p.status in ("submitted", "confirmed") for p in c.participations),
        "needs_human_reason": c.needs_human_reason, "created_at": _iso(c.created_at),
    }


def prize(p: Prize) -> dict:
    return {"id": p.id, "name": p.name, "category": p.category, "quantity": p.quantity, "value": p.value,
            "currency": p.currency, "value_eur": p.value_eur, "fees_note": p.fees_note}


def answer(a: Answer) -> dict:
    return {"id": a.id, "question": a.question, "answer": a.answer, "source": a.source, "verified": a.verified, "confidence": a.confidence}


def participation(p: Participation) -> dict:
    return {"id": p.id, "contest_id": p.contest_id, "contest_title": p.contest.title, "contest_url": p.contest.url, "mode": p.mode,
            "status": p.status, "prepared_at": _iso(p.prepared_at), "submitted_at": _iso(p.submitted_at), "error": p.error,
            "time_spent_minutes": p.time_spent_minutes,
            "proofs": [{"id": x.id, "kind": x.kind, "note": x.note, "path": x.path, "created_at": _iso(x.created_at)} for x in p.proofs]}


def contest_detail(c: Contest) -> dict:
    d = contest_summary(c)
    r = c.rules[0] if c.rules else None
    d.update({
        "description": c.description, "start_date": _iso(c.start_date), "entry_limit": c.entry_limit, "notes": c.notes,
        "personal_interest": c.personal_interest, "min_age": c.eligibility.min_age if c.eligibility else None,
        "countries_excluded": c.eligibility.countries_excluded if c.eligibility else [],
        "rules": {"url": r.url, "excerpt": r.text[:3000], "content_hash": r.content_hash, "analyzed_at": _iso(r.analyzed_at)} if r else None,
        "prizes": [prize(p) for p in c.prizes], "answers": [answer(a) for a in c.answers],
        "justifications": c.justifications or [], "score_breakdown": c.score_breakdown or {"reliability": {}, "interest": {}},
        "participations": [participation(p) for p in c.participations],
        "provenance": [{"source_name": s.source.name if s.source else "ajout manuel", "source_url": s.source_url, "seen_at": _iso(s.seen_at)} for s in c.sightings],
        "flags": c.flags or [],
    })
    return d


def result(r: Result) -> dict:
    return {"id": r.id, "contest_id": r.contest_id, "contest_title": r.contest.title if r.contest else None, "outcome": r.outcome,
            "message_text": r.message_text, "sender": r.sender, "received_at": _iso(r.received_at), "phishing_score": r.phishing_score,
            "phishing_flags": r.phishing_flags or [], "verified": r.verified}


def claim(c: Claim) -> dict:
    return {"id": c.id, "result_id": c.result_id, "contest_title": c.result.contest.title if c.result and c.result.contest else None,
            "prize_name": c.prize_name, "status": c.status, "deadline": _iso(c.deadline),
            "days_left": (c.deadline - date.today()).days if c.deadline else None, "fees_eur": c.fees_eur, "value_eur": c.value_eur, "notes": c.notes}


def notification(n: Notification) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "contest_id": n.contest_id, "created_at": _iso(n.created_at), "read": n.read}


def source(s: Source, contests_found: int = 0) -> dict:
    return {"id": s.id, "name": s.name, "kind": s.kind, "url": s.url, "enabled": s.enabled, "language": s.language, "country": s.country,
            "last_scan_at": _iso(s.last_scan_at), "last_status": s.last_status, "contests_found": contests_found, "tos_note": s.tos_note}


def scan_job(j: ScanJob) -> dict:
    return {"id": j.id, "source_id": j.source_id, "source_name": j.source.name if j.source else None, "status": j.status,
            "started_at": _iso(j.started_at), "finished_at": _iso(j.finished_at), "found": j.found, "new": j.new, "error": j.error}
