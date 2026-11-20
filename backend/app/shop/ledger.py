"""Registre des dépenses et statistiques mensuelles (M08 ANALYTICS pour Shop & Promo).

Distingue strictement : économies réellement réalisées (remboursements reçus), remboursements en attente, refusés,
dépenses engagées et gains aléatoires. Aucun achat n'est jamais effectué par l'application.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import ShopClaim, ShopLedger
from .prefs import get_shop_prefs


def record(db: Session, kind: str, amount: float, at: date | None = None, promotion_id: int | None = None, claim_id: int | None = None,
           note: str | None = None) -> ShopLedger:
    e = ShopLedger(kind=kind, amount_eur=round(float(amount), 2), at=at or date.today(), promotion_id=promotion_id, claim_id=claim_id,
                   note=(note or None) and note[:300])
    db.add(e)
    return e


def month_bounds(month: str | None) -> tuple[date, date]:
    d = date.fromisoformat((month or date.today().strftime("%Y-%m")) + "-01")
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return d, nxt


def spent_in_month(db: Session, month: str | None = None) -> float:
    a, b = month_bounds(month)
    return round(sum(e.amount_eur for e in db.scalars(select(ShopLedger).where(ShopLedger.kind == "expense", ShopLedger.at >= a,
                                                                                 ShopLedger.at < b))), 2)


def monthly_stats(db: Session, month: str | None = None) -> dict:
    a, b = month_bounds(month)
    rows = list(db.scalars(select(ShopLedger).where(ShopLedger.at >= a, ShopLedger.at < b)))

    def total(k: str) -> float:
        return round(sum(e.amount_eur for e in rows if e.kind == k), 2)

    spent = total("expense")
    received = total("refund_received")
    claims = list(db.scalars(select(ShopClaim)))
    pending = round(sum((c.amount_confirmed_eur or c.amount_requested_eur or 0) for c in claims
                        if c.status in ("sent", "confirmed", "refund_pending")), 2)
    refused = total("refund_refused")
    cap = get_shop_prefs(db)["monthly_cap_eur"]
    return {
        "month": a.strftime("%Y-%m"),
        "expenses_eur": spent,
        "savings_realized_eur": received,
        "refunds_pending_eur": pending,
        "refunds_refused_eur": refused,
        "random_gains_eur": total("random_gain"),
        "net_real_cost_eur": round(spent - received, 2),
        "monthly_cap_eur": cap,
        "cap_left_eur": round(cap - spent, 2),
        "entries": [{"at": e.at.isoformat(), "kind": e.kind, "amount_eur": e.amount_eur, "promotion_id": e.promotion_id,
                     "claim_id": e.claim_id, "note": e.note} for e in sorted(rows, key=lambda e: (e.at, e.id))],
        "note": "Économies réalisées = remboursements effectivement reçus. Les remboursements en attente et les gains aléatoires n'en font pas partie.",
    }


def history(db: Session, months: int = 12) -> list[dict]:
    today = date.today()
    out = []
    y, m = today.year, today.month
    for _ in range(months):
        s = monthly_stats(db, f"{y:04d}-{m:02d}")
        s.pop("entries")
        out.append(s)
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out
