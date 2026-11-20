"""M08 : statistiques. La valeur des lots joués n'est JAMAIS présentée comme un gain."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Claim, Contest, ContestSighting, Participation, Result, Source


def compute(db: Session) -> dict:
    today = date.today()
    cnt = lambda q: db.scalar(select(func.count()).select_from(Contest).where(Contest.merged_into_id.is_(None), *q)) or 0  # noqa: E731
    valid = db.scalars(select(Participation).where(Participation.status.in_(("submitted", "confirmed")))).all()
    pending = db.scalar(select(func.count()).select_from(Participation).where(Participation.status.in_(("prepared", "awaiting_human")))) or 0
    played_value = sum((p.contest.total_prize_value_eur or 0) for p in valid)
    received = db.scalars(select(Claim).where(Claim.status == "received")).all()
    wins = db.scalar(select(func.count()).select_from(Result).where(Result.outcome == "won", Result.verified.is_(True))) or 0
    by_source = []
    for s in db.scalars(select(Source)):
        cids = set(db.scalars(select(ContestSighting.contest_id).where(ContestSighting.source_id == s.id)))
        parts = sum(1 for p in valid if p.contest_id in cids)
        w = db.scalar(select(func.count()).select_from(Result).where(Result.outcome == "won", Result.contest_id.in_(cids))) if cids else 0
        by_source.append({"source": s.name, "contests": len(cids), "participations": parts, "wins": w or 0})
    countries: Counter = Counter()
    for c in db.scalars(select(Contest).where(Contest.merged_into_id.is_(None))):
        for code in (c.eligibility.countries_allowed if c.eligibility else []) or ["?"]:
            countries[code] += 1
    cats = db.execute(select(Contest.category, func.count()).where(Contest.merged_into_id.is_(None)).group_by(Contest.category)).all()
    return {
        "contests_total": cnt([]),
        "contests_qualified": cnt([Contest.status == "qualified"]),
        "contests_to_verify": cnt([Contest.status == "to_verify"]),
        "contests_closing_soon": cnt([Contest.status == "qualified", Contest.end_date >= today, Contest.end_date <= today + timedelta(days=3)]),
        "participations_valid": len(valid),
        "participations_pending": pending,
        "time_spent_minutes": round(sum(p.time_spent_minutes or 0 for p in valid), 1),
        "prize_value_participated_eur": round(played_value, 2),
        "gains_obtained_eur": round(sum((c.value_eur or 0) - (c.fees_eur or 0) for c in received), 2),
        "wins": wins,
        "claims_open": db.scalar(select(func.count()).select_from(Claim).where(Claim.status.in_(("to_claim", "claimed")))) or 0,
        "by_source": by_source,
        "by_country": [{"country": k, "count": v} for k, v in countries.most_common(20)],
        "by_category": [{"category": k or "other", "count": v} for k, v in cats],
    }
