"""Résultats attendus des participations réellement soumises.

Règles : une date de tirage ne veut pas dire que les résultats sont publiés ; une victoire n'est jamais annoncée
sans preuve (message de gain vérifié par l'utilisateur). Les dates viennent du règlement ; sinon elles sont
estimées et marquées comme telles.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Participation, Result, WeeklyResult, utcnow
from ..i18n.geo import norm
from ..intelligence.rules_extract import parse_dates_in

STATUSES = ("draw_pending", "drawn", "not_published", "published", "winner", "not_winner", "unverifiable")
MANUAL_STATUSES = ("published", "not_winner", "unverifiable", "not_published", "drawn", "draw_pending")
DEFAULT_DRAW_DELAY_DAYS = 7  # estimation prudente quand le règlement ne dit rien

DRAW_RX = re.compile(r"(tirage au sort|tirage|designation des gagnants|deliberation du jury|draw|drawing)\b[^.]{0,80}?"
                     r"(aura lieu|sera effectue|sera realise|interviendra|effectue|se deroulera|will take place|will be held|on or about|le|au plus tard)", re.I)
PUBLISH_RX = re.compile(r"(gagnants?|resultats?|winners?)\b[^.]{0,60}?(seront|sera|will be)\s+(publies?|annonces?|informes?|contactes?|prevenus?|avises?|notified|announced|posted)", re.I)
DELAY_RX = re.compile(r"dans (un delai de |les )?(\d{1,3}) jours", re.I)


def extract_draw_dates(rules_text: str | None, end: date | None) -> tuple[date | None, bool, date | None]:
    """(date du tirage, estimée ?, date de publication) depuis le règlement."""
    if not rules_text:
        return (end + timedelta(days=DEFAULT_DRAW_DELAY_DAYS) if end else None), True, None
    t = norm(rules_text)
    draw = publish = None
    for rx, kind in ((DRAW_RX, "draw"), (PUBLISH_RX, "publish")):
        for m in rx.finditer(t):
            window = t[m.start(): m.end() + 120]
            ds = [d for _, d in parse_dates_in(window)]
            if ds:
                if kind == "draw" and draw is None:
                    draw = ds[0]
                elif kind == "publish" and publish is None:
                    publish = ds[0]
            elif kind == "publish" and publish is None and draw and (dm := DELAY_RX.search(window)):
                publish = draw + timedelta(days=int(dm.group(2)))
    if draw:
        return draw, False, publish
    return (end + timedelta(days=DEFAULT_DRAW_DELAY_DAYS) if end else None), True, publish


def _derive_status(wr: WeeklyResult, results: list[Result], today: date) -> str:
    won = [r for r in results if r.outcome == "won"]
    if any(r.verified and r.phishing_score < 50 for r in won):
        return "winner"
    if any(r.outcome == "lost" for r in results):
        return "not_winner"
    if won:
        return "published"  # gain annoncé mais non vérifié : jamais présenté comme une victoire
    if wr.status_manual:
        return wr.status
    if wr.draw_date is None or today < wr.draw_date:
        return "draw_pending"
    if wr.publish_date and today >= wr.publish_date:
        return "not_published"
    return "drawn"


def sync_results(db: Session, today: date) -> list[WeeklyResult]:
    """Crée/actualise le suivi pour chaque participation soumise ; dates relues dans le règlement à chaque fois."""
    parts = db.scalars(select(Participation).where(Participation.status.in_(("submitted", "confirmed")))).all()
    known = {w.participation_id: w for w in db.scalars(select(WeeklyResult))}
    out = []
    for p in parts:
        c = p.contest
        wr = known.get(p.id)
        if wr is None:
            wr = WeeklyResult(participation_id=p.id, contest_id=c.id, verify_url=c.url)
            db.add(wr)
        rule = next((r for r in c.rules if r.origin in ("fetched", "user")), None)
        draw, est, publish = extract_draw_dates(rule.text if rule else None, c.end_date)
        wr.draw_date, wr.draw_date_estimated = draw, est
        wr.publish_date = publish or wr.publish_date
        wr.contest_id = c.id
        rs = db.scalars(select(Result).where((Result.participation_id == p.id) | (Result.contest_id == c.id))).all()
        wr.status = _derive_status(wr, rs, today)
        out.append(wr)
    db.flush()
    return out


def expected_in_week(db: Session, ws: date, today: date) -> list[WeeklyResult]:
    """Résultats prévus dans la semaine, plus ceux en retard encore non résolus."""
    we = ws + timedelta(days=6)
    rows = sync_results(db, today)
    out = []
    for w in rows:
        dates = [d for d in (w.draw_date, w.publish_date) if d]
        in_week = any(ws <= d <= we for d in dates)
        overdue = w.status in ("drawn", "not_published") and dates and max(dates) < ws and ws <= today
        if in_week or overdue:
            out.append(w)
    out.sort(key=lambda w: (w.publish_date or w.draw_date or date.max))
    return out


def set_manual_status(db: Session, wr: WeeklyResult, status: str, note: str | None, verify_url: str | None) -> WeeklyResult:
    if status not in MANUAL_STATUSES:
        raise ValueError("Pour un gain ou une perte, enregistrez le message reçu dans Gains (vérification anti-arnaque)")
    wr.status, wr.status_manual = status, True
    wr.note = (note or wr.note or None) and (note or wr.note)[:2000]
    if verify_url:
        wr.verify_url = verify_url[:1000]
    wr.last_checked_at = utcnow()
    db.commit()
    return wr


WINNERS_PAGE = re.compile(r"liste des gagnants|les gagnants (sont|du)|gagnants du (jeu|concours|tirage)|winners? (list|are|announced)|resultats du (jeu|concours|tirage)")


def check_result_pages(db: Session, fetcher, today: date, profile: dict, limit: int = 5) -> int:
    """Lit la page officielle de vérification (dans le respect de robots.txt) pour voir si les gagnants sont publiés.

    Ne déclare jamais un gain : si votre nom semble apparaître, une tâche urgente vous demande de vérifier.
    """
    from .tasks import ensure_task

    n = 0
    rows = db.scalars(select(WeeklyResult).where(WeeklyResult.status.in_(("drawn", "not_published")), WeeklyResult.verify_url.is_not(None))
                      .order_by(WeeklyResult.last_checked_at.asc().nulls_first()).limit(limit)).all()
    for wr in rows:
        try:
            res = fetcher.get(wr.verify_url)
        except Exception as e:  # noqa: BLE001 - page inaccessible : on garde le statut et on note
            wr.note = f"Vérification impossible le {today:%d/%m} : {str(e)[:150]}"
            wr.last_checked_at = utcnow()
            continue
        from ..security.sanitize import html_to_text

        text = norm(html_to_text(res.text) if "<" in res.text[:2000] else res.text)
        wr.last_checked_at = utcnow()
        n += 1
        if WINNERS_PAGE.search(text):
            wr.status, wr.status_manual = "published", True
            wr.note = f"Page des gagnants détectée le {today:%d/%m} : à consulter vous-même"
            last, first = norm(profile.get("last_name") or ""), norm(profile.get("first_name") or "")
            if len(last) >= 3 and re.search(r"(?<![a-z])" + re.escape(last) + r"(?![a-z])", text) and (not first or first[:1] in text):
                ensure_task(db, f"name-on-winners:{wr.id}", "Votre nom semble apparaître sur la page des gagnants",
                            f"Vérifiez sur {wr.verify_url}. Ce n'est pas une confirmation de gain : attendez le message officiel de l'organisateur.",
                            action="check_draw", priority="high", contest_id=wr.contest_id, participation_id=wr.participation_id)
    db.commit()
    return n
