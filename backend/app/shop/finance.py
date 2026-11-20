"""Rentabilité d'une opération : coût réel = prix − remboursement attendu − avantages réellement cumulables (+ frais).

Un remboursement est garanti sous conditions ; un lot de jeu avec achat est aléatoire et n'est jamais déduit du coût.
Des promotions dont le cumul n'est pas explicitement autorisé ne sont jamais additionnées.
"""
from __future__ import annotations

from datetime import date

REFUND_KINDS = ("full_refund", "partial_refund", "voucher", "receipt_offer", "code_offer", "discount")
LABELS = {"A": "Opportunité excellente", "B": "Opportunité intéressante", "C": "Opportunité spéculative"}


def expected_refund(p, price: float | None = None) -> float | None:
    price = p.price_eur if price is None else price
    if p.kind == "purchase_game":
        return 0.0
    if p.refund_eur is not None:
        r = p.refund_eur
    elif p.refund_percent is not None and price is not None:
        r = price * p.refund_percent / 100
    else:
        return None
    if p.refund_max_eur is not None:
        r = min(r, p.refund_max_eur)
    if price is not None:
        r = min(r, price)
    return round(r, 2)


def analysis(p, price: float | None = None) -> dict:
    price = p.price_eur if price is None else price
    refund = expected_refund(p, price)
    extra = p.extra_benefits_eur or 0
    notes = []
    extra_counted = 0.0
    if extra:
        if p.cumulable is True:
            extra_counted = extra
        else:
            notes.append("Avantage complémentaire non compté : cumul non autorisé ou non précisé par le règlement")
    fees = p.fees_eur or 0
    net = None
    if price is not None:
        net = round(price - (refund or 0) - extra_counted + fees, 2)
    if p.kind == "purchase_game":
        notes.append("Gain aléatoire : la valeur du lot n'est jamais déduite du coût")
    if refund is None and p.kind in ("full_refund", "partial_refund"):
        notes.append("Montant du remboursement non établi")
    cat = category(p, price, refund, net)
    return {
        "price_eur": price, "refund_announced_eur": refund, "refund_guaranteed": p.kind != "purchase_game",
        "conditions": conditions(p), "extra_benefits_eur": extra or None, "extra_counted_eur": extra_counted or None,
        "fees_eur": fees or None, "net_cost_forecast_eur": net, "refund_delay_days": p.refund_delay_days,
        "random_prize_value_eur": p.prize_value_eur if p.kind == "purchase_game" else None,
        "category": cat, "category_label": LABELS[cat], "notes": notes,
        "disclaimer": ("Coût net prévisionnel : seulement si toutes les conditions sont remplies et le remboursement effectivement reçu."
                       if p.kind != "purchase_game" else "Achat motivé par un gain aléatoire : aucune économie certaine."),
    }


def conditions(p) -> list[str]:
    out = []
    if p.purchase_start or p.end_date:
        out.append(f"Achat {'du ' + p.purchase_start.strftime('%d/%m/%Y') + ' ' if p.purchase_start else ''}"
                   f"{'au ' + p.end_date.strftime('%d/%m/%Y') if p.end_date else ''}".strip())
    if p.send_deadline:
        out.append(f"Demande au plus tard le {p.send_deadline:%d/%m/%Y}")
    if p.request_delay_days:
        out.append(f"Demande dans les {p.request_delay_days} jours suivant l'achat")
    if p.eans:
        out.append("EAN exact : " + ", ".join(p.eans))
    v = p.variant or {}
    for k, lab in (("quantity", "Format"), ("flavor", "Variante"), ("edition", "Édition"), ("min_quantity", "Quantité minimale")):
        if v.get(k):
            out.append(f"{lab} : {v[k]}")
    if p.retailers:
        out.append("Enseignes : " + ", ".join(p.retailers))
    if p.limit_per:
        who = {"household": "foyer", "person": "personne", "ticket": "ticket", "product": "produit"}[p.limit_per]
        out.append(f"{p.limit_count or 1} demande(s) par {who}")
    if p.cumulable is False:
        out.append("Non cumulable")
    if p.required_docs:
        out.append("Justificatifs : " + ", ".join(DOC_LABELS.get(d, d) for d in p.required_docs))
    return out


DOC_LABELS = {"receipt": "ticket de caisse", "barcode": "code-barres (photo)", "barcode_original": "code-barres original découpé",
              "packaging": "photo de l'emballage", "qr": "QR code", "iban": "IBAN (saisi par vous)", "form": "formulaire",
              "payment_proof": "justificatif de paiement", "invoice": "facture"}


def category(p, price: float | None, refund: float | None, net: float | None) -> str:
    simple = len([d for d in (p.required_docs or []) if d != "iban"]) <= 3 and "barcode_original" not in (p.required_docs or [])
    identified = bool(p.eans) or bool((p.variant or {}).get("quantity"))
    verifiable = bool(p.rules_text or p.rules_url) and (p.reliability or 0) >= 60
    fully = (refund is not None and price is not None and refund >= price - 0.01) or (
        p.refund_percent == 100 and (price is None or p.refund_max_eur is None or price <= p.refund_max_eur))
    if p.kind == "full_refund" and fully and simple and identified and verifiable:
        return "A"
    if p.kind == "purchase_game":
        attractive = (p.prize_value_eur or 0) >= 500
        cheap = net is not None and net <= 10
        return "B" if attractive and cheap and verifiable and simple else "C"
    if not verifiable:
        return "C"
    if p.kind in ("full_refund", "partial_refund", "voucher", "receipt_offer", "code_offer", "discount"):
        share = (refund or 0) / price if price else (p.refund_percent or 0) / 100
        if share >= 0.3 or p.kind == "full_refund":
            return "B"
    return "C"


def is_open(p, today: date) -> bool:
    if p.end_date and p.end_date < today:
        return False
    if p.purchase_start and p.purchase_start > today:
        return True  # à venir
    return True
