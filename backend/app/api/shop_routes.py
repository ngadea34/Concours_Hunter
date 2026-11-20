"""API M14 Hunter Shop & Promo. Aucun achat, aucune transmission sans validation explicite."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..db.models import PromoAvailability, Promotion, ShopClaim, ShopDocument
from ..db.session import get_db
from ..shop import claims as CL
from ..shop import documents as D
from ..shop import ledger
from ..shop.analyze import analyze_offer, apply_to_promotion
from ..shop.commands import run as run_command
from ..shop.prefs import get_shop_prefs, update_shop_prefs
from ..shop.products import canonical_retailer, ean_valid
from ..shop.recommend import LEVELS, availability, brief, dashboard, recommendations

router = APIRouter(prefix="/api/shop")


def _get(db: Session, model: Any, key: int, msg: str) -> Any:
    obj = db.get(model, key)
    if obj is None:
        raise HTTPException(404, msg)
    return obj


def _err(fn, *a, **k):  # noqa: ANN001, ANN002, ANN003
    try:
        return fn(*a, **k)
    except (CL.ClaimError, D.DocumentError, ValueError) as e:
        raise HTTPException(400, str(e)) from e


def _doc_out(d: ShopDocument) -> dict:
    return {"id": d.id, "kind": d.kind, "promotion_id": d.promotion_id, "claim_id": d.claim_id, "sha256": d.sha256, "mime": d.mime,
            "size": d.size, "sensitive": d.sensitive, "ocr_method": d.ocr_method, "ocr_text": d.ocr_text, "readability": d.readability,
            "extracted": d.extracted, "user_fields": d.user_fields, "fields": D.fields(d), "created_at": d.created_at.isoformat()}


# ------------------------------------------------------------------ tableau de bord, recommandations, préférences
@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)) -> dict:
    return dashboard(db)


@router.get("/recommendations")
def get_recommendations(kind: str | None = None, db: Session = Depends(get_db)) -> dict:
    return recommendations(db, kinds=tuple(kind.split(",")) if kind else None)


@router.get("/preferences")
def get_preferences(db: Session = Depends(get_db)) -> dict:
    return get_shop_prefs(db)


@router.put("/preferences")
def put_preferences(body: dict, db: Session = Depends(get_db)) -> dict:
    return _err(update_shop_prefs, db, body)


@router.post("/command")
def command(body: dict, db: Session = Depends(get_db)) -> dict:
    return run_command(db, str(body.get("command", ""))[:20_000])


@router.post("/discover")
def discover(db: Session = Depends(get_db)) -> dict:
    from ..shop.discover import discover_all

    return discover_all(db)


# ------------------------------------------------------------------ opérations
class AnalyzeIn(BaseModel):
    text: str = Field(max_length=200_000)
    url: str | None = Field(None, max_length=1000)
    title: str | None = Field(None, max_length=300)
    save: bool = False


@router.post("/analyze")
def analyze(body: AnalyzeIn, db: Session = Depends(get_db)) -> dict:
    data = analyze_offer(body.text, body.url)
    if not body.save:
        data.pop("rules_text", None)
        return {"analysis": data}
    p = Promotion(title=(body.title or data.get("brand") or "Opération")[:300], url=body.url, rules_url=body.url, origin="user", status="to_watch")
    apply_to_promotion(p, data)
    p.kind = data["kind"]
    db.add(p)
    db.flush()
    audit(db, "user", "shop_promotion_analyze", promotion_id=p.id)
    db.commit()
    return brief(db, p, get_shop_prefs(db), date.today())


@router.get("/promotions/{pid}")
def get_promotion(pid: int, db: Session = Depends(get_db)) -> dict:
    p = _get(db, Promotion, pid, "Opération introuvable")
    b = brief(db, p, get_shop_prefs(db), date.today())
    b["documents"] = [_doc_out(d) for d in db.scalars(select(ShopDocument).where(ShopDocument.promotion_id == pid))]
    b["claims"] = [CL.out(c) for c in db.scalars(select(ShopClaim).where(ShopClaim.promotion_id == pid))]
    return b


EDITABLE = {"title", "brand", "product", "price_eur", "refund_eur", "refund_percent", "refund_max_eur", "eans", "variant", "retailers",
            "cumulable", "extra_benefits_eur", "fees_eur", "category", "status", "channel", "channel_target", "required_docs",
            "end_date", "purchase_start", "send_deadline", "request_delay_days", "refund_delay_days", "limit_per", "limit_count", "kind", "url", "rules_url"}


@router.patch("/promotions/{pid}")
def patch_promotion(pid: int, body: dict, db: Session = Depends(get_db)) -> dict:
    p = _get(db, Promotion, pid, "Opération introuvable")
    for k, v in body.items():
        if k not in EDITABLE:
            continue
        if k == "status" and v not in ("to_watch", "to_buy", "ignored", "expired"):
            raise HTTPException(400, "Statut modifiable : à surveiller, à acheter, ignorée, expirée (le reste suit les dossiers)")
        if k == "eans":
            bad = [e for e in v if not ean_valid(str(e))]
            if bad:
                raise HTTPException(400, f"EAN invalide : {', '.join(bad)}")
        if k == "retailers":
            v = [canonical_retailer(str(x)) for x in v]
        if k in ("end_date", "purchase_start", "send_deadline") and v:
            v = date.fromisoformat(v)
        setattr(p, k, v)
    db.commit()
    return brief(db, p, get_shop_prefs(db), date.today())


class AvailIn(BaseModel):
    retailer: str = Field(max_length=60)
    store: str | None = Field(None, max_length=200)
    level: str
    price_eur: float | None = Field(None, ge=0, le=10_000)
    ean: str | None = None
    source: str | None = Field(None, max_length=300)
    product_label: str | None = Field(None, max_length=300)


@router.post("/promotions/{pid}/availability")
def add_availability(pid: int, body: AvailIn, db: Session = Depends(get_db)) -> dict:
    p = _get(db, Promotion, pid, "Opération introuvable")
    if body.level not in LEVELS:
        raise HTTPException(400, "Niveau : store_confirmed, catalog_listed, third_party ou unknown")
    if body.level != "unknown" and not (body.source or "").strip():
        raise HTTPException(400, "Indiquez la source de l'information (ex. « vu en rayon par moi », « catalogue en ligne Carrefour »)")
    if body.ean and not ean_valid(body.ean):
        raise HTTPException(400, "EAN invalide")
    db.add(PromoAvailability(promotion_id=p.id, retailer=canonical_retailer(body.retailer) or body.retailer, store=body.store, level=body.level,
                             price_eur=body.price_eur, ean=body.ean, source=body.source, product_label=body.product_label))
    db.commit()
    return availability(db, p, get_shop_prefs(db)["retailers"])


@router.get("/ean/{ean}")
def ean_lookup(ean: str) -> dict:
    from ..shop.off import lookup

    return lookup(ean)


# ------------------------------------------------------------------ documents
class DocIn(BaseModel):
    kind: str
    data_url: str = Field(max_length=15_000_000)
    promotion_id: int | None = None
    claim_id: int | None = None


@router.get("/documents")
def list_documents(promotion_id: int | None = None, db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(ShopDocument).order_by(ShopDocument.id.desc())
    if promotion_id:
        stmt = stmt.where(ShopDocument.promotion_id == promotion_id)
    return [_doc_out(d) for d in db.scalars(stmt.limit(200))]


@router.post("/documents")
def add_document(body: DocIn, db: Session = Depends(get_db)) -> dict:
    d = _err(D.store, db, body.kind, body.data_url, body.promotion_id, None)
    if body.claim_id:
        CL.attach(db, _get(db, ShopClaim, body.claim_id, "Dossier introuvable"), d)
    audit(db, "user", "shop_document_add", document_id=d.id, kind=d.kind)
    db.commit()
    return _doc_out(d)


@router.post("/documents/{did}/ocr")
def ocr_document(did: int, body: dict | None = None, db: Session = Depends(get_db)) -> dict:
    d = _get(db, ShopDocument, did, "Document introuvable")
    D.ocr(db, d, (body or {}).get("text"))
    if d.claim_id:
        c = db.get(ShopClaim, d.claim_id)
        CL.sync_from_documents(db, c)
        CL.run_checks(db, c)
    return _doc_out(d)


@router.patch("/documents/{did}")
def patch_document(did: int, body: dict, db: Session = Depends(get_db)) -> dict:
    d = _get(db, ShopDocument, did, "Document introuvable")
    _err(D.set_user_fields, db, d, body)
    if d.claim_id:
        c = db.get(ShopClaim, d.claim_id)
        CL.sync_from_documents(db, c)
        CL.run_checks(db, c)
    return _doc_out(d)


@router.get("/documents/{did}/file")
def document_file(did: int, confirm: bool = False, db: Session = Depends(get_db)) -> Response:
    """Copie de travail (pour la joindre vous-même sur le site officiel). Document sensible : confirm=true obligatoire."""
    d = _get(db, ShopDocument, did, "Document introuvable")
    if d.sensitive and not confirm:
        raise HTTPException(403, "Document sensible : confirmation explicite requise")
    audit(db, "user", "shop_document_export", document_id=d.id)
    db.commit()
    return Response(D.read_working(d), media_type=d.mime, headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ dossiers
@router.get("/claims")
def list_claims(db: Session = Depends(get_db)) -> list[dict]:
    return [CL.out(c) for c in db.scalars(select(ShopClaim).order_by(ShopClaim.id.desc()))]


@router.post("/claims")
def new_claim(body: dict, db: Session = Depends(get_db)) -> dict:
    p = _get(db, Promotion, int(body.get("promotion_id") or 0), "Opération introuvable")
    c = CL.create_claim(db, p)
    for did in body.get("document_ids") or []:
        CL.attach(db, c, _get(db, ShopDocument, int(did), "Document introuvable"))
    CL.run_checks(db, c)
    return CL.out(c)


@router.get("/claims/{cid}")
def get_claim(cid: int, db: Session = Depends(get_db)) -> dict:
    c = _get(db, ShopClaim, cid, "Dossier introuvable")
    o = CL.out(c)
    o["documents"] = [_doc_out(d) for d in CL.docs_of(db, c)]
    return o


@router.post("/claims/{cid}/{action}")
def claim_action(cid: int, action: str, body: dict | None = None, db: Session = Depends(get_db)) -> dict:
    c = _get(db, ShopClaim, cid, "Dossier introuvable")
    b = body or {}

    def day(k: str) -> date | None:
        return date.fromisoformat(b[k]) if b.get(k) else None

    if action == "check":
        CL.run_checks(db, c)
    elif action == "attach":
        CL.attach(db, c, _get(db, ShopDocument, int(b.get("document_id") or 0), "Document introuvable"))
        CL.run_checks(db, c)
    elif action == "purchase":
        _err(CL.record_purchase, db, c, float(b.get("amount_eur") or 0), day("date") or date.today())
        CL.run_checks(db, c)
    elif action == "codes":
        c.codes = [str(x).strip()[:60] for x in b.get("codes") or [] if str(x).strip()][:20]
        db.commit()
        CL.run_checks(db, c)
    elif action == "preview":
        return {"claim": CL.out(c), "preview": _err(CL.request_validation, db, c)}
    elif action == "validate":
        _err(CL.validate, db, c, b.get("confirm"), [int(x) for x in b.get("document_ids") or []])
    elif action == "sent":
        _err(CL.mark_sent, db, c, day("sent_on"), b.get("confirmation_ref"), b.get("note"))
        CL.run_checks(db, c)
    elif action == "confirm":
        _err(CL.confirm, db, c, b.get("confirmation_ref"), float(b["amount_eur"]) if b.get("amount_eur") is not None else None)
        CL.run_checks(db, c)
    elif action == "refunded":
        _err(CL.mark_refunded, db, c, float(b["amount_eur"]) if b.get("amount_eur") is not None else None, day("received_on"))
        CL.run_checks(db, c)
    elif action == "refused":
        _err(CL.mark_refused, db, c, str(b.get("reason") or ""))
        CL.run_checks(db, c)
    elif action == "cancel":
        _err(CL.cancel, db, c)
    else:
        raise HTTPException(404, "Action inconnue")
    return CL.out(c)


# ------------------------------------------------------------------ dépenses
@router.get("/expenses")
def expenses(month: str | None = None, db: Session = Depends(get_db)) -> dict:
    return _err(ledger.monthly_stats, db, month)


@router.get("/expenses/history")
def expenses_history(db: Session = Depends(get_db)) -> list[dict]:
    return ledger.history(db)


@router.post("/gains")
def random_gain(body: dict, db: Session = Depends(get_db)) -> dict:
    """Gain aléatoire constaté (jeu avec achat) : compté à part, jamais comme une économie."""
    amount = float(body.get("amount_eur") or 0)
    if amount <= 0:
        raise HTTPException(400, "Montant invalide")
    ledger.record(db, "random_gain", amount, date.fromisoformat(body["date"]) if body.get("date") else date.today(),
                  body.get("promotion_id"), None, str(body.get("note") or "")[:300])
    db.commit()
    return ledger.monthly_stats(db)
