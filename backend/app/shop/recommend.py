"""Recommandations et tableau de bord Shop & Promo.

Jamais « en rayon » sans source du magasin ; stocks en temps réel non accessibles : toujours signalé.
Aucune recommandation fondée sur la seule ressemblance de nom ou de marque : la référence exacte est affichée et contrôlée.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import PromoAvailability, Promotion, ShopClaim
from ..i18n.geo import norm
from . import finance
from .claims import OPEN, is_late
from .claims import out as claim_out
from .finance import DOC_LABELS
from .ledger import spent_in_month
from .prefs import get_shop_prefs
from .products import ean_valid

LEVELS = ["store_confirmed", "catalog_listed", "third_party", "unknown"]
LEVEL_TEXT = {
    "store_confirmed": "Stock confirmé par une source du magasin",
    "catalog_listed": "Produit référencé dans le catalogue (présence en rayon non vérifiée)",
    "third_party": "Signalé disponible par une source tierce (non vérifié)",
    "unknown": "Disponibilité inconnue : à confirmer auprès du magasin",
}
REALTIME_NOTE = "Les stocks en temps réel des magasins ne sont pas accessibles : la présence en rayon n'est jamais garantie."
INACTIVE = ("ignored", "expired", "refused", "refunded")


def availability(db: Session, p: Promotion, retailers: list[str]) -> dict:
    rows = list(db.scalars(select(PromoAvailability).where(PromoAvailability.promotion_id == p.id)))
    mine = [r for r in rows if not retailers or r.retailer in retailers] or rows
    if not mine:
        return {"level": "unknown", "text": LEVEL_TEXT["unknown"], "observations": [], "realtime_note": REALTIME_NOTE}
    best = min(mine, key=lambda r: (LEVELS.index(r.level), -(r.observed_at.timestamp() if r.observed_at else 0)))
    txt = LEVEL_TEXT[best.level]
    if best.level == "store_confirmed":
        txt += f" ({best.store or best.retailer}, {best.source or 'source du magasin'}, le {best.observed_at:%d/%m/%Y})"
    return {"level": best.level, "text": txt, "realtime_note": REALTIME_NOTE,
            "observations": [{"retailer": r.retailer, "store": r.store, "level": r.level, "price_eur": r.price_eur, "ean": r.ean,
                              "source": r.source, "observed_at": r.observed_at.isoformat() if r.observed_at else None} for r in mine]}


def _mentions(words: list[str], p: Promotion) -> bool:
    hay = norm(" ".join(filter(None, [p.title, p.product, p.brand, p.category])))
    return any(norm(w) in hay for w in words if w.strip())


def brief(db: Session, p: Promotion, prefs: dict, today: date) -> dict:
    prices = [r.price_eur for r in db.scalars(select(PromoAvailability).where(PromoAvailability.promotion_id == p.id)) if r.price_eur]
    price = p.price_eur if p.price_eur is not None else (min(prices) if prices else None)
    fin = finance.analysis(p, price)
    eans_ok = bool(p.eans) and all(ean_valid(e) for e in p.eans)
    claims = list(db.scalars(select(ShopClaim).where(ShopClaim.promotion_id == p.id)))
    open_claim = next((c for c in claims if c.status in OPEN), None)
    av = availability(db, p, prefs["retailers"])
    if open_claim:
        action = "Compléter et suivre le dossier" if open_claim.status in ("draft", "incomplete", "ready", "awaiting_validation", "validated") else "Suivre le remboursement"
    elif p.end_date and p.end_date < today:
        action = "Offre terminée"
    else:
        action = "Vérifier la disponibilité en magasin, puis décider de l'achat (aucun achat n'est fait par l'application)"
    return {
        "id": p.id, "title": p.title, "brand": p.brand, "product": p.product, "kind": p.kind, "status": p.status, "url": p.url,
        "rules_url": p.rules_url, "origin": p.origin, "contest_id": p.contest_id,
        "retailers": p.retailers or [], "retailers_note": None if p.retailers else "Enseignes participantes non précisées",
        "eans": p.eans or [], "ean_status": "EAN vérifié (clé de contrôle)" if eans_ok else ("EAN invalide" if p.eans else "Référence EAN non précisée : vérifiez le format exact"),
        "variant": p.variant or {}, "price_eur": price, "finance": fin, "category": fin["category"],
        "reliability": p.reliability, "required_docs": [DOC_LABELS.get(d, d) for d in (p.required_docs or [])],
        "end_date": p.end_date.isoformat() if p.end_date else None, "send_deadline": p.send_deadline.isoformat() if p.send_deadline else None,
        "days_left": (p.end_date - today).days if p.end_date else None, "availability": av, "action": action,
        "claim_id": open_claim.id if open_claim else None, "warnings": (p.analysis or {}).get("warnings", []),
        "evidence": (p.analysis or {}).get("evidence", {}),
    }


def recommendations(db: Session, today: date | None = None, kinds: tuple[str, ...] | None = None) -> dict:
    today = today or date.today()
    prefs = get_shop_prefs(db)
    spent = spent_in_month(db)
    cap = prefs["monthly_cap_eur"]
    items, excluded = [], []
    order = {"A": 0, "B": 1, "C": 2}
    for p in db.scalars(select(Promotion).where(Promotion.status.not_in(INACTIVE))):
        if kinds and p.kind not in kinds:
            continue
        why = None
        if p.end_date and p.end_date < today:
            why = "Offre expirée"
        elif prefs["refused_products"] and _mentions(prefs["refused_products"], p):
            why = "Produit ou marque que vous refusez"
        elif prefs["accepted_products"] and not _mentions(prefs["accepted_products"], p):
            why = "Hors de vos produits acceptés"
        elif prefs["categories"] and p.category and p.category not in prefs["categories"]:
            why = "Catégorie non souhaitée"
        elif p.retailers and prefs["retailers"] and not set(p.retailers) & set(prefs["retailers"]):
            why = "Disponible seulement chez " + ", ".join(p.retailers) + " (hors de vos enseignes)"
        b = brief(db, p, prefs, today)
        if not why and b["price_eur"] is not None and b["price_eur"] > prefs["max_price_eur"]:
            why = f"Prix supérieur à votre budget par produit ({prefs['max_price_eur']:.0f} €)"
        if not why and order[b["category"]] > order[prefs["min_category"]]:
            why = f"Catégorie {b['category']} sous votre minimum ({prefs['min_category']})"
        if why:
            excluded.append({"id": p.id, "title": p.title, "reason": why})
            continue
        b["over_cap"] = b["price_eur"] is not None and spent + b["price_eur"] > cap
        if b["over_cap"]:
            b["warnings"] = [*b["warnings"], f"Dépasserait votre plafond mensuel ({cap:.0f} €, déjà {spent:.2f} € ce mois-ci)"]
        items.append(b)
    items.sort(key=lambda b: (b["over_cap"], order[b["category"]], b["finance"]["net_cost_forecast_eur"] if b["finance"]["net_cost_forecast_eur"] is not None else 999,
                              -(b["reliability"] or 0), b["days_left"] if b["days_left"] is not None else 999))
    return {"items": items, "excluded": excluded, "spent_this_month_eur": spent, "monthly_cap_eur": cap, "realtime_note": REALTIME_NOTE,
            "note": "Recommandations seulement : la décision d'achat vous appartient. Un jeu avec achat n'est jamais une économie certaine."}


def dashboard(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    prefs = get_shop_prefs(db)
    rec = recommendations(db, today)
    promos = list(db.scalars(select(Promotion)))
    claims = list(db.scalars(select(ShopClaim).order_by(ShopClaim.id.desc())))
    b = {p.id: brief(db, p, prefs, today) for p in promos}
    active = [p for p in promos if p.status not in INACTIVE and not (p.end_date and p.end_date < today)]
    return {
        "available": rec["items"],
        "to_buy": [b[p.id] for p in active if p.status == "to_buy"],
        "full_refund": [b[p.id] for p in active if p.kind == "full_refund"],
        "purchase_games": [b[p.id] for p in active if p.kind == "purchase_game"],
        "partial_refund": [b[p.id] for p in active if p.kind in ("partial_refund", "voucher", "receipt_offer", "code_offer", "discount")],
        "ending_soon": [b[p.id] for p in active if p.end_date and p.end_date <= today + timedelta(days=7)],
        "claims_to_complete": [claim_out(c, today) for c in claims if c.status in ("draft", "incomplete", "ready", "awaiting_validation", "validated")],
        "claims_sent": [claim_out(c, today) for c in claims if c.status in ("sent", "confirmed")],
        "refunds_awaiting": [claim_out(c, today) for c in claims if c.status in ("sent", "confirmed", "refund_pending") and c.kind == "refund"],
        "refunds_late": [claim_out(c, today) for c in claims if is_late(c, today)],
        "refunds_received": [claim_out(c, today) for c in claims if c.status == "refunded"],
        "refused": [claim_out(c, today) for c in claims if c.status == "refused"] + [{"promotion_id": p.id, "promotion_title": p.title, "status": "refused"} for p in promos if p.status == "refused" and not any(c.promotion_id == p.id and c.status == "refused" for c in claims)],
        "history": [claim_out(c, today) for c in claims if c.status in ("refunded", "refused", "cancelled")],
        "excluded": rec["excluded"], "realtime_note": REALTIME_NOTE,
    }
