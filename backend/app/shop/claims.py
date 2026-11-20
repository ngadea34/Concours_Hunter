"""REIMBURSEMENT MANAGER et parcours « jeu avec achat » (agent REIMBURSEMENT).

12 contrôles par dossier. Aucune transmission sans validation explicite de l'utilisateur. Rien n'est déclaré
remboursé tant que le montant reçu et sa date ne sont pas constatés. Les doubles demandes sont bloquées.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..db.models import Promotion, ShopClaim, ShopDocument, utcnow
from ..i18n.geo import norm
from ..intelligence.scoring import SUSPICIOUS_HOSTS
from . import ledger
from .documents import fields
from .finance import expected_refund
from .products import match_product

STEPS = ["Règlement identifié", "Conditions extraites", "Période d'achat", "Période et limite de demande", "Produit exact",
         "Ticket de caisse", "Justificatifs requis", "Dossier préparé", "Canal de transmission", "Suivi de la demande",
         "Confirmation enregistrée", "Remboursement effectif"]
OPEN = ("draft", "incomplete", "ready", "awaiting_validation", "validated", "sent", "confirmed", "refund_pending")
DEFAULT_REFUND_DELAY = 56
DOC_FOR = {"receipt": ("receipt", "invoice"), "invoice": ("invoice", "receipt"), "barcode": ("barcode", "packaging"),
           "packaging": ("packaging",), "qr": ("qr", "packaging"), "payment_proof": ("payment_proof",)}


class ClaimError(ValueError):
    pass


def _log(c: ShopClaim, event: str, detail: str | None = None) -> None:
    c.history = [*(c.history or []), {"at": utcnow().isoformat(), "event": event, "detail": detail}]


def docs_of(db: Session, c: ShopClaim) -> list[ShopDocument]:
    return list(db.scalars(select(ShopDocument).where(ShopDocument.claim_id == c.id).order_by(ShopDocument.id)))


def create_claim(db: Session, p: Promotion, kind: str | None = None) -> ShopClaim:
    c = ShopClaim(promotion=p, kind=kind or ("purchase_game" if p.kind == "purchase_game" else "refund"), status="draft",
                  channel=p.channel, amount_requested_eur=None)
    _log(c, "created")
    db.add(c)
    db.flush()
    audit(db, "user", "shop_claim_create", claim_id=c.id, promotion_id=p.id)
    db.commit()
    return c


def attach(db: Session, c: ShopClaim, doc: ShopDocument) -> None:
    doc.claim_id, doc.promotion_id = c.id, c.promotion_id
    _log(c, "document", f"{doc.kind} #{doc.id}")
    sync_from_documents(db, c)
    db.commit()


def sync_from_documents(db: Session, c: ShopClaim) -> None:
    """Reporte date, enseigne, n° de ticket et montant payé depuis le ticket (sans toucher au document)."""
    rec = next((d for d in docs_of(db, c) if d.kind in ("receipt", "invoice")), None)
    if not rec:
        return
    f = fields(rec)
    if f.get("purchase_date"):
        c.purchase_date = date.fromisoformat(f["purchase_date"])
    c.retailer = f.get("retailer") or c.retailer
    c.ticket_number = f.get("ticket_number") or c.ticket_number
    line = _product_line(c.promotion, f.get("lines") or [])
    if line and line.get("price_eur") is not None:
        c.amount_paid_eur = line["price_eur"]
    if c.kind == "refund":
        c.amount_requested_eur = expected_refund(c.promotion, c.amount_paid_eur)


def _product_line(p: Promotion, lines: list[dict]) -> dict | None:
    """Ligne du ticket qui correspond au produit (mots du produit ou de la marque) ; sert au prix, pas à la preuve d'EAN."""
    words = [w for w in re.findall(r"[a-z0-9]{3,}", norm(" ".join(filter(None, [p.product, p.brand, p.title])))) if w not in ("offre", "rembourse", "gagnez")]
    best, score = None, 0
    for ln in lines:
        lab = norm(ln.get("label") or "")
        s = sum(1 for w in words if w in lab)
        if s > score:
            best, score = ln, s
    return best if score >= 1 else None


def _deadline(p: Promotion, c: ShopClaim) -> date | None:
    ds = [d for d in (p.send_deadline, c.purchase_date + timedelta(days=p.request_delay_days) if c.purchase_date and p.request_delay_days else None) if d]
    return min(ds) if ds else None


def is_late(c: ShopClaim, today: date) -> bool:
    if c.status not in ("sent", "confirmed", "refund_pending") or not c.sent_at:
        return False
    delay = c.promotion.refund_delay_days or DEFAULT_REFUND_DELAY
    return c.sent_at.date() + timedelta(days=delay + 7) < today


def channel_check(p: Promotion) -> tuple[str, str]:
    if not p.channel:
        return "fail", "Canal de transmission non identifié dans le règlement"
    if p.channel in ("platform", "form", "app"):
        u = p.channel_target or ""
        host = urlsplit(u).hostname or ""
        if not u.startswith("https://") or not host:
            return "fail", "Adresse du formulaire officiel absente ou non sécurisée (https)"
        if SUSPICIOUS_HOSTS.search(host):
            return "fail", f"Domaine {host} non vérifié : aucune transmission"
        return "ok", f"Formulaire officiel : {host}"
    if p.channel == "email":
        return ("ok", f"Courriel officiel : {p.channel_target}") if p.channel_target and "@" in p.channel_target else ("fail", "Adresse e-mail officielle absente")
    if p.channel == "postal":
        return ("ok", "Courrier postal à l'adresse du règlement") if p.channel_target else ("warn", "Adresse postale à recopier depuis le règlement")
    return "warn", p.channel


def run_checks(db: Session, c: ShopClaim, today: date | None = None) -> list[dict]:
    today = today or date.today()
    p = c.promotion
    docs = docs_of(db, c)
    res: list[tuple[str, str]] = []

    # 1 règlement
    res.append(("ok", "Règlement enregistré") if (p.rules_text or p.rules_url) else ("fail", "Règlement non identifié : ajoutez le texte ou le lien"))
    # 2 conditions
    miss = [lab for ok, lab in ((p.kind == "purchase_game" or expected_refund(p, c.amount_paid_eur or p.price_eur) is not None, "montant du remboursement"),
                                (bool(p.channel), "canal"), (bool(p.end_date or p.send_deadline), "dates")) if not ok]
    res.append(("ok", "Conditions extraites") if not miss else ("warn", "À compléter : " + ", ".join(miss)))
    # 3 période d'achat
    if not c.purchase_date:
        res.append(("pending", "Date d'achat inconnue (ticket à fournir)"))
    elif (p.purchase_start and c.purchase_date < p.purchase_start) or (p.end_date and c.purchase_date > p.end_date):
        res.append(("fail", f"Achat hors période ({c.purchase_date:%d/%m/%Y})"))
    else:
        res.append(("ok", f"Achat le {c.purchase_date:%d/%m/%Y}, dans la période"))
    # 4 période de demande + limites (double demande)
    others = [o for o in db.scalars(select(ShopClaim).where(ShopClaim.promotion_id == p.id, ShopClaim.id != c.id))
              if o.status not in ("cancelled", "refused", "draft", "incomplete")]
    dl = _deadline(p, c)
    dup = None
    if p.limit_per in ("household", "person") and len(others) >= (p.limit_count or 1):
        dup = f"Double demande : limite de {p.limit_count or 1} par {'foyer' if p.limit_per == 'household' else 'personne'} déjà atteinte"
    if c.ticket_number and any(o.ticket_number == c.ticket_number for o in others):
        dup = f"Double demande : le ticket n° {c.ticket_number} a déjà servi pour cette opération"
    rec_sha = {d.sha256 for d in docs if d.kind in ("receipt", "invoice")}
    if rec_sha and db.scalars(select(ShopDocument).where(ShopDocument.sha256.in_(rec_sha), ShopDocument.claim_id.is_not(None),
                                                          ShopDocument.claim_id != c.id, ShopDocument.promotion_id == p.id)).first():
        dup = "Double demande : ce ticket est déjà joint à un autre dossier de cette opération"
    if dup:
        res.append(("fail", dup))
    elif c.status not in ("sent", "confirmed", "refund_pending", "refunded") and ((dl and today > dl) or (p.end_date and not c.purchase_date and today > p.end_date)):
        res.append(("fail", "Offre expirée : délai de demande dépassé" + (f" ({dl:%d/%m/%Y})" if dl else "")))
    else:
        res.append(("ok", f"Demande possible jusqu'au {dl:%d/%m/%Y}") if dl else ("warn", "Date limite de demande non précisée"))
    # 5 produit exact (+ enseigne)
    rec = next((d for d in docs if d.kind in ("receipt", "invoice")), None)
    rf = fields(rec) if rec else {}
    eans = [e for d in docs if d.kind in ("barcode", "packaging", "qr") for e in (fields(d).get("eans") or []) + ([fields(d)["ean"]] if fields(d).get("ean") else [])]
    eans += rf.get("eans") or []
    line = _product_line(p, rf.get("lines") or [])
    observed = {"ean": eans[0] if eans else None, "label": (line or {}).get("label") or "", "count": (line or {}).get("quantity") or 1}
    if p.eans and eans:
        observed["ean"] = next((e for e in eans if e in p.eans), eans[0])
    m = match_product(p.eans or [], p.variant or {}, observed)
    status = {"exact": "ok", "mismatch": "fail", "unverified": "warn"}[m["status"]]
    detail = "; ".join(m["reasons"])
    retailer = c.retailer or rf.get("retailer")
    if p.retailers and retailer and retailer not in p.retailers:
        status, detail = "fail", f"Enseigne {retailer} non participante (participantes : {', '.join(p.retailers)})"
    if m["status"] == "mismatch":
        detail = "Produit non participant : " + detail
    res.append((status, detail))
    # 6 ticket
    if "receipt" not in (p.required_docs or []) and "invoice" not in (p.required_docs or []) and not rec:
        res.append(("ok", "Ticket non exigé"))
    elif not rec:
        res.append(("pending", "Photographiez votre ticket de caisse"))
    elif rec.readability == "unreadable":
        res.append(("fail", "Ticket illisible : reprenez la photo ou saisissez les informations"))
    elif rec.readability in ("incomplete", "pending"):
        res.append(("fail", "Ticket incomplet : " + ", ".join(rf.get("missing") or ["à lire ou à saisir"])))
    else:
        res.append(("ok", f"Ticket lisible ({rf.get('retailer') or '?'}, {rf.get('purchase_date') or '?'})"))
    # 7 justificatifs
    have = {d.kind for d in docs}
    missing = []
    for need in p.required_docs or []:
        if need in ("iban", "form"):
            continue
        if need == "barcode_original":
            continue  # pièce physique à envoyer par courrier : rappelée dans le dossier
        if not set(DOC_FOR.get(need, (need,))) & have:
            missing.append(need)
    if c.kind == "purchase_game" and re.search(r"\bcode", norm(p.rules_text or "")) and not c.codes:
        missing.append("code(s) à saisir")
    res.append(("ok", "Justificatifs complets") if not missing else ("fail", "Manquant : " + ", ".join(missing)))
    # 8 dossier
    blocking = [s for s, _ in res if s in ("fail", "pending")]
    res.append(("ok", "Dossier prêt") if not blocking else ("pending", "Dossier incomplet"))
    # 9 canal
    res.append(channel_check(p))
    # 10-12 suivi
    res.append(("ok", f"Transmis le {c.sent_at:%d/%m/%Y}") if c.sent_at else ("pending", "Pas encore transmis"))
    res.append(("ok", f"Confirmation : {c.confirmation_ref}") if c.confirmation_ref else ("pending", "Aucune confirmation enregistrée"))
    if c.status == "refunded":
        res.append(("ok", f"Reçu {c.amount_received_eur:.2f} € le {c.received_date:%d/%m/%Y}"))
    elif c.status == "refused":
        res.append(("fail", "Refusé : " + (c.refusal_reason or "")))
    elif is_late(c, today):
        res.append(("warn", "Remboursement en retard : relancez l'organisateur"))
    else:
        res.append(("pending", "Remboursement non constaté"))
    if c.kind == "purchase_game":
        res[11] = ("ok" if c.participation_id else "pending", "Participation archivée, résultats suivis" if c.participation_id else "Résultat à surveiller après transmission")
    c.checks = [{"step": i + 1, "label": STEPS[i], "status": s, "detail": d} for i, (s, d) in enumerate(res)]
    if c.status in ("draft", "incomplete", "ready"):
        c.status = "ready" if res[7][0] == "ok" and res[8][0] != "fail" else ("incomplete" if docs else "draft")
    db.commit()
    return c.checks


def preview(db: Session, c: ShopClaim) -> dict:
    """Ce qui sera transmis, à valider par l'utilisateur (aucun envoi ici)."""
    p = c.promotion
    docs = docs_of(db, c)
    st, chan = channel_check(p)
    return {"claim_id": c.id, "channel": p.channel, "channel_target": p.channel_target, "channel_status": st, "channel_detail": chan,
            "documents": [{"id": d.id, "kind": d.kind, "sensitive": d.sensitive, "size": d.size} for d in docs],
            "personal_data": ["nom", "prénom", "adresse", "e-mail"] + (["IBAN (à saisir vous-même sur le canal officiel)"] if "iban" in (p.required_docs or []) else []),
            "physical_items": ["code-barres original découpé"] if "barcode_original" in (p.required_docs or []) else [],
            "codes": c.codes, "amount_requested_eur": c.amount_requested_eur,
            "warning": "Rien n'est transmis sans votre validation. Les données bancaires ne sont jamais envoyées par l'application."}


def request_validation(db: Session, c: ShopClaim) -> dict:
    checks = run_checks(db, c)
    fails = [x for x in checks[:9] if x["status"] in ("fail", "pending")]
    if fails:
        raise ClaimError("Dossier non prêt : " + " ; ".join(f"{x['label']} : {x['detail']}" for x in fails))
    c.status = "awaiting_validation"
    _log(c, "validation_requested")
    db.commit()
    return preview(db, c)


def validate(db: Session, c: ShopClaim, confirm: bool, document_ids: list[int]) -> ShopClaim:
    """Validation explicite avant toute transmission de documents personnels."""
    if c.status != "awaiting_validation":
        raise ClaimError("Demandez d'abord la validation (aperçu du dossier)")
    if confirm is not True:
        raise ClaimError("Validation explicite requise (confirm=true)")
    ids = {d.id for d in docs_of(db, c)}
    if not set(document_ids) <= ids:
        raise ClaimError("Documents étrangers à ce dossier")
    c.validated_at, c.validated_docs, c.status = utcnow(), sorted(set(document_ids)), "validated"
    _log(c, "validated", f"documents {sorted(set(document_ids))}")
    audit(db, "user", "shop_claim_validated", claim_id=c.id, documents=sorted(set(document_ids)))
    db.commit()
    return c


def mark_sent(db: Session, c: ShopClaim, sent_on: date | None = None, confirmation_ref: str | None = None, note: str | None = None) -> ShopClaim:
    """Enregistre la transmission faite par le canal officiel (après validation)."""
    if not c.validated_at or c.status != "validated":
        raise ClaimError("Transmission impossible sans validation explicite du dossier")
    c.sent_at = datetime.combine(sent_on or date.today(), datetime.min.time())
    c.status = "sent"
    c.confirmation_ref = (confirmation_ref or None) and confirmation_ref[:200]
    if c.confirmation_ref:
        c.status = "confirmed"
    p = c.promotion
    p.status, p.sent_date = "sent", c.sent_at.date()
    if c.amount_paid_eur and not any(e.kind == "expense" for e in _entries(db, c)):
        ledger.record(db, "expense", c.amount_paid_eur, c.purchase_date, p.id, c.id, "Achat (ticket)")
    if c.kind == "refund" and c.amount_requested_eur:
        ledger.record(db, "refund_requested", c.amount_requested_eur, c.sent_at.date(), p.id, c.id)
    if c.kind == "purchase_game":
        _archive_participation(db, c, note)
    _log(c, "sent", c.confirmation_ref)
    audit(db, "user", "shop_claim_sent", claim_id=c.id)
    db.commit()
    return c


def _entries(db: Session, c: ShopClaim):
    from ..db.models import ShopLedger

    return list(db.scalars(select(ShopLedger).where(ShopLedger.claim_id == c.id)))


def _archive_participation(db: Session, c: ShopClaim, note: str | None) -> None:
    """Jeu avec achat : la transmission devient une participation M04, suivie ensuite par les résultats (M05/M15)."""
    p = c.promotion
    if not p.contest_id:
        return
    from ..db.models import Contest
    from ..participation import service as ps

    contest = db.get(Contest, p.contest_id)
    if contest is None:
        return
    try:
        part = ps.prepare(db, contest, "manual", purchase_flow=True)
    except ps.ParticipationError as e:
        _log(c, "participation_refused", str(e))
        return
    ps.mark(db, part, "submitted", note=(note or f"Participation avec achat transmise (dossier #{c.id})")[:500], minutes=5)
    c.participation_id = part.id


def confirm(db: Session, c: ShopClaim, ref: str | None, amount: float | None) -> ShopClaim:
    if c.status not in ("sent", "confirmed"):
        raise ClaimError("Le dossier n'a pas été transmis")
    c.confirmation_ref = (ref or c.confirmation_ref or "")[:200] or None
    if amount is not None:
        c.amount_confirmed_eur = round(amount, 2)
        ledger.record(db, "refund_confirmed", amount, date.today(), c.promotion_id, c.id)
    c.status = "refund_pending" if c.kind == "refund" else "confirmed"
    c.promotion.status = "refund_pending" if c.kind == "refund" else c.promotion.status
    _log(c, "confirmed", c.confirmation_ref)
    db.commit()
    return c


def mark_refunded(db: Session, c: ShopClaim, amount: float | None, received_on: date | None) -> ShopClaim:
    """Seul moyen de déclarer un remboursement : montant et date de réception constatés."""
    if c.kind != "refund":
        raise ClaimError("Un jeu avec achat ne se rembourse pas : enregistrez un éventuel gain dans Gains")
    if c.status not in ("sent", "confirmed", "refund_pending"):
        raise ClaimError("Le dossier n'a pas été transmis")
    if amount is None or amount <= 0 or received_on is None or received_on > date.today():
        raise ClaimError("Indiquez le montant effectivement reçu et la date de réception (constatée, pas future)")
    c.amount_received_eur, c.received_date, c.status = round(amount, 2), received_on, "refunded"
    p = c.promotion
    p.status, p.refund_received_eur, p.received_date = "refunded", round((p.refund_received_eur or 0) + amount, 2), received_on
    ledger.record(db, "refund_received", amount, received_on, p.id, c.id)
    _log(c, "refunded", f"{amount:.2f} €")
    audit(db, "user", "shop_claim_refunded", claim_id=c.id, amount=amount)
    db.commit()
    return c


def mark_refused(db: Session, c: ShopClaim, reason: str) -> ShopClaim:
    if c.status not in ("sent", "confirmed", "refund_pending", "validated", "awaiting_validation"):
        raise ClaimError("Seul un dossier en cours peut être refusé")
    c.status, c.refusal_reason = "refused", (reason or "Refus de l'organisateur")[:1000]
    c.promotion.status = "refused"
    if c.amount_requested_eur and c.kind == "refund":
        ledger.record(db, "refund_refused", c.amount_requested_eur, date.today(), c.promotion_id, c.id, c.refusal_reason[:200])
    _log(c, "refused", c.refusal_reason)
    db.commit()
    return c


def cancel(db: Session, c: ShopClaim) -> ShopClaim:
    if c.status in ("sent", "confirmed", "refund_pending", "refunded"):
        raise ClaimError("Un dossier transmis ne peut plus être annulé")
    c.status = "cancelled"
    _log(c, "cancelled")
    db.commit()
    return c


def record_purchase(db: Session, c: ShopClaim, amount: float, on: date) -> ShopClaim:
    """L'utilisateur déclare son achat (fait par lui). Sert au registre des dépenses."""
    if amount <= 0:
        raise ClaimError("Montant invalide")
    if not any(e.kind == "expense" for e in _entries(db, c)):
        ledger.record(db, "expense", amount, on, c.promotion_id, c.id, "Achat déclaré")
    c.amount_paid_eur, c.purchase_date = round(amount, 2), c.purchase_date or on
    if c.kind == "refund":
        c.amount_requested_eur = expected_refund(c.promotion, c.amount_paid_eur)
    c.promotion.status = "bought" if c.promotion.status in ("to_watch", "to_buy") else c.promotion.status
    db.commit()
    return c


def out(c: ShopClaim, today: date | None = None) -> dict:
    today = today or date.today()
    return {"id": c.id, "promotion_id": c.promotion_id, "promotion_title": c.promotion.title, "kind": c.kind, "status": c.status,
            "late": is_late(c, today), "purchase_date": c.purchase_date.isoformat() if c.purchase_date else None, "retailer": c.retailer,
            "ticket_number": c.ticket_number, "amount_paid_eur": c.amount_paid_eur, "amount_requested_eur": c.amount_requested_eur,
            "amount_confirmed_eur": c.amount_confirmed_eur, "amount_received_eur": c.amount_received_eur,
            "received_date": c.received_date.isoformat() if c.received_date else None, "codes": c.codes, "checks": c.checks,
            "validated_at": c.validated_at.isoformat() if c.validated_at else None, "sent_at": c.sent_at.isoformat() if c.sent_at else None,
            "confirmation_ref": c.confirmation_ref, "refusal_reason": c.refusal_reason, "participation_id": c.participation_id,
            "history": c.history, "channel": c.promotion.channel, "channel_target": c.promotion.channel_target}
