"""Rubrique Shop & Promo du programme (données du module M14, table promotions).

Un remboursement promis reste conditionnel tant qu'il n'est pas reçu ; un lot de jeu avec achat n'est jamais un remboursement.
Aucun achat n'est déclenché : seulement des rappels et des calculs.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Contest, Promotion

PENDING_FILE = ("to_send",)  # dossier à compléter
WAITING_REFUND = ("sent", "refund_pending")
ACTIVE = ("to_watch", "to_buy")


def promo_brief(p: Promotion, today: date) -> dict:
    price, refund = p.price_eur, p.refund_eur
    net = round(price - (refund or 0), 2) if price is not None and p.kind in ("full_refund", "partial_refund", "discount") else price
    return {"id": p.id, "title": p.title, "brand": p.brand, "kind": p.kind, "url": p.url, "product": p.product, "status": p.status,
            "price_eur": price, "refund_eur": refund, "refund_received_eur": p.refund_received_eur, "net_cost_forecast_eur": net,
            "end_date": p.end_date.isoformat() if p.end_date else None, "send_deadline": p.send_deadline.isoformat() if p.send_deadline else None,
            "days_left": (p.end_date - today).days if p.end_date else None, "contest_id": p.contest_id}


def shop_section(db: Session, ws: date, today: date) -> dict:
    we = ws + timedelta(days=6)
    rows = db.scalars(select(Promotion)).all()
    cat = {k: [] for k in ("full_refund", "partial_refund", "purchase_game", "ending", "to_send", "awaiting_refund", "received", "to_buy_this_week")}
    for p in rows:
        b = promo_brief(p, today)
        if p.status in ACTIVE and p.kind in ("full_refund", "partial_refund", "purchase_game"):
            cat[p.kind].append(b)
        if p.status in ACTIVE and p.end_date and today <= p.end_date <= we:
            cat["ending"].append(b)
        if p.status in PENDING_FILE or p.status == "bought":
            cat["to_send"].append(b)
        if p.status in WAITING_REFUND:
            cat["awaiting_refund"].append(b)
        if p.status == "refunded":
            cat["received"].append(b)
        if p.status == "to_buy" and (not p.end_date or p.end_date >= today):
            cat["to_buy_this_week"].append(b)
    # jeux avec achat repérés par la découverte (concours rejetés pour achat obligatoire)
    for c in db.scalars(select(Contest).where(Contest.free_status == "purchase_required", Contest.merged_into_id.is_(None),
                                              (Contest.end_date.is_(None)) | (Contest.end_date >= today)).limit(30)):
        if not any(p.contest_id == c.id for p in rows):
            cat["purchase_game"].append({"id": None, "contest_id": c.id, "title": c.title, "kind": "purchase_game", "status": "detected",
                                         "url": c.url, "end_date": c.end_date.isoformat() if c.end_date else None,
                                         "note": "Lot aléatoire : jamais compté comme une économie"})
    to_buy = cat["to_buy_this_week"]
    planned_spend = round(sum(b["price_eur"] or 0 for b in to_buy), 2)
    conditional_refunds = round(sum(b["refund_eur"] or 0 for b in to_buy if b["kind"] in ("full_refund", "partial_refund")), 2)
    received = round(sum(p.refund_received_eur or 0 for p in rows if p.status == "refunded"), 2)
    awaiting = round(sum(p.refund_eur or 0 for p in rows if p.status in WAITING_REFUND), 2)
    return {"categories": cat, "totals": {
        "planned_spend_eur": planned_spend,
        "conditional_refunds_eur": conditional_refunds,
        "net_cost_forecast_eur": round(planned_spend - conditional_refunds, 2),
        "refunds_awaiting_eur": awaiting,
        "refunds_received_eur": received,
    }, "note": "Coût net prévisionnel : seulement si toutes les conditions de remboursement sont remplies. Aucun achat n'est fait par l'application."}
