"""Contrôle qualité par connecteur : doublons, dates, lots, liens officiels, conditions, respect des restrictions."""
from __future__ import annotations

from datetime import date
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Contest, ContestSighting, ScanJob, Source
from .policy import access_mode, denial_reason


def _dom(u: str) -> str:
    return (urlsplit(u or "").hostname or "").lower().removeprefix("www.")


def source_quality(db: Session, s: Source) -> dict:
    ids = set(db.scalars(select(ContestSighting.contest_id).where(ContestSighting.source_id == s.id)))
    contests = [c for c in db.scalars(select(Contest).where(Contest.id.in_(ids)))] if ids else []
    live = [c for c in contests if c.merged_into_id is None]
    today = date.today()
    src_dom = _dom(s.url)
    n = len(live) or 1

    def pct(k: int) -> int:
        return round(100 * k / n) if live else 0

    m = {
        "contests": len(contests),
        "merged_duplicates": len(contests) - len(live),
        "missing_end_date": sum(1 for c in live if not c.end_date),
        "inconsistent_dates": sum(1 for c in live if c.start_date and c.end_date and c.start_date > c.end_date),
        "expired": sum(1 for c in live if c.end_date and c.end_date < today),
        "missing_prize": sum(1 for c in live if not c.prizes and not c.prize_summary),
        "official_link": sum(1 for c in live if _dom(c.url) and (s.kind == "site" or _dom(c.url) != src_dom)),
        "with_rules": sum(1 for c in live if any(r.origin in ("fetched", "user") for r in c.rules)),
        "qualified": sum(1 for c in live if c.status == "qualified"),
        "to_verify": sum(1 for c in live if c.status == "to_verify"),
        "conditions_known": sum(1 for c in live if c.free_status != "unknown" and c.fr_eligible != "unknown"),
    }
    jobs = list(db.scalars(select(ScanJob).where(ScanJob.source_id == s.id).order_by(ScanJob.id.desc()).limit(10)))
    issues = []
    if denial_reason(s.url):
        issues.append("Site en consultation assistée : la lecture automatique ne doit pas être activée")
    if live and pct(m["official_link"]) < 50:
        issues.append(f"Lien officiel de l'organisateur trouvé pour {pct(m['official_link'])} % des concours seulement")
    if live and pct(m["missing_end_date"]) > 30:
        issues.append(f"{pct(m['missing_end_date'])} % sans date de clôture")
    if m["inconsistent_dates"]:
        issues.append(f"{m['inconsistent_dates']} concours avec début après la fin")
    if live and pct(m["missing_prize"]) > 30:
        issues.append(f"{pct(m['missing_prize'])} % sans lot identifié")
    if live and pct(m["with_rules"]) < 30:
        issues.append(f"Règlement récupéré pour {pct(m['with_rules'])} % des concours")
    errors = [j for j in jobs if j.status == "error"]
    if len(errors) >= 3:
        issues.append(f"{len(errors)} erreurs sur les 10 derniers scans : la source est isolée, les autres continuent")
    blocked = [j for j in jobs if j.status == "skipped"]
    return {
        "source_id": s.id, "name": s.name, "kind": s.kind, "access_mode": access_mode(s.kind, s.url), "metrics": m,
        "percent": {k: pct(v) for k, v in m.items() if k not in ("contests", "merged_duplicates")},
        "restrictions": {"blocked_scans": len(blocked), "last_block": blocked[0].error if blocked else None,
                         "note": "Les pages interdites par robots.txt, les CAPTCHA et les connexions ne sont jamais forcés : le scan est marqué « bloqué »."},
        "last_scans": [{"status": j.status, "found": j.found, "new": j.new, "error": j.error,
                        "finished_at": j.finished_at.isoformat() if j.finished_at else None} for j in jobs],
        "issues": issues,
    }
