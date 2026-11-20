"""Découverte des opérations (agent DISCOVERY, réutilise M01) : pages des fabricants, marques et enseignes, et jeux avec
achat déjà repérés par la découverte des concours. Chaque opération est enregistrée avec sa source et son règlement."""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..db.models import Contest, Promotion, ScanJob, Source, utcnow
from ..discovery.base import load_connectors
from ..discovery.fetcher import FetchBlocked, Fetcher
from ..security.sanitize import html_to_text
from .analyze import KIND_PATTERNS, analyze_offer, apply_to_promotion

log = logging.getLogger(__name__)


def from_contests(db: Session, today: date | None = None) -> int:
    """Jeux-concours avec obligation d'achat déjà trouvés (M01/M02) → opérations « jeu avec achat »."""
    today = today or date.today()
    known = set(db.scalars(select(Promotion.contest_id).where(Promotion.contest_id.is_not(None))))
    n = 0
    for c in db.scalars(select(Contest).where(Contest.free_status == "purchase_required", Contest.merged_into_id.is_(None),
                                              (Contest.end_date.is_(None)) | (Contest.end_date >= today))):
        if c.id in known:
            continue
        rules = c.rules[0].text if c.rules else ""
        p = Promotion(title=c.title[:300], kind="purchase_game", url=c.url, origin="contest", contest_id=c.id, end_date=c.end_date,
                      rules_url=c.rules[0].url if c.rules else None, status="to_watch", prize_value_eur=c.total_prize_value_eur)
        apply_to_promotion(p, analyze_offer(rules or c.description or c.title, c.url, today))
        p.kind = "purchase_game"
        db.add(p)
        n += 1
    db.commit()
    return n


def upsert_page(db: Session, url: str, title: str, text: str, source: Source | None, today: date | None = None) -> Promotion | None:
    """Enregistre une page d'opération si son texte correspond à une offre ; met à jour sans écraser les saisies."""
    from ..i18n.geo import norm
    import re

    t = norm(text or "")
    if not any(re.search(rx, t) for _, rx in KIND_PATTERNS):
        return None
    p = db.scalars(select(Promotion).where(Promotion.url == url)).first()
    created = p is None
    if p is None:
        p = Promotion(title=(title or url)[:300], url=url, origin="discovery", status="to_watch")
        db.add(p)
    data = analyze_offer(text, url, today)
    apply_to_promotion(p, data)
    if source is not None:
        p.analysis = {**(p.analysis or {}), "source": source.name, "source_url": source.url}
    db.flush()
    p._created = created  # type: ignore[attr-defined]
    return p


def scan_source(db: Session, source: Source, fetcher: Fetcher | None = None, job: ScanJob | None = None) -> ScanJob:
    """Scan d'une source « promo_site » : pages d'offres → promotions (aucun concours créé)."""
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    job = job or ScanJob(source_id=source.id, kind="scan", status="running")
    db.add(job)
    db.commit()
    try:
        conn = load_connectors()["promo_site"](source, fetcher)
        for raw in conn.discover():
            job.found += 1
            try:
                res = fetcher.get(raw.url)
            except FetchBlocked:
                continue
            p = upsert_page(db, raw.url, raw.title, html_to_text(res.text), source)
            if p is not None and getattr(p, "_created", False):
                job.new += 1
            db.commit()
        job.status = "ok"
        source.last_status = conn.note or "ok"
    except FetchBlocked as e:
        db.rollback()
        job.status, job.error = "skipped", str(e)
        source.last_status = f"bloqué : {e}"[:200]
    except Exception as e:  # noqa: BLE001 - une source en panne n'arrête pas les autres
        db.rollback()
        log.exception("Scan promo %s", source.name)
        job.status, job.error = "error", str(e)[:1000]
        source.last_status = f"erreur : {e}"[:200]
    finally:
        job.finished_at = utcnow()
        source.last_scan_at = utcnow()
        audit(db, "discovery", "scan_promo", source=source.name, status=job.status, found=job.found)
        db.commit()
        if own:
            fetcher.close()
    return job


def discover_all(db: Session, fetcher: Fetcher | None = None) -> dict:
    n = from_contests(db)
    scanned = 0
    for s in db.scalars(select(Source).where(Source.kind == "promo_site", Source.enabled.is_(True))):
        scan_source(db, s, fetcher)
        scanned += 1
    return {"from_contests": n, "sources_scanned": scanned}
