"""Gestionnaire documentaire (agent DOCUMENTATION) : justificatifs, OCR local, extraction des champs d'un ticket.

- L'original est chiffré sur le disque, en lecture seule, jamais modifié ; une copie de travail distincte sert aux dossiers.
- Les corrections de l'utilisateur sont stockées à part (user_fields) : le justificatif lui-même n'est jamais altéré.
- OCR : modèle de vision local via Ollama si activé ; sinon l'utilisateur colle le texte ou saisit les champs.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..admin.settings_service import get_settings_dict
from ..config import get_settings
from ..db.models import ShopDocument
from ..i18n.geo import norm
from ..intelligence.rules_extract import _to_float, parse_dates_in
from ..security.crypto import decrypt_bytes, encrypt_bytes
from .products import find_eans, find_retailers

KINDS = ("receipt", "invoice", "packaging", "barcode", "qr", "promo_label", "payment_proof", "rules_capture", "other")
SENSITIVE_KINDS = ("payment_proof",)
MAX_BYTES = 10 * 1024 * 1024
MAGIC = [(b"\x89PNG\r\n\x1a\n", "image/png", "png"), (b"\xff\xd8\xff", "image/jpeg", "jpg"), (b"%PDF-", "application/pdf", "pdf"),
         (b"RIFF", "image/webp", "webp")]
_DATA_URL = re.compile(r"^data:(?P<m>[\w/+.-]+);base64,(?P<b>.+)$", re.S)


class DocumentError(ValueError):
    pass


def _dir(sub: str):
    d = get_settings().data_dir / "documents" / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def store(db: Session, kind: str, data_url: str, promotion_id: int | None = None, claim_id: int | None = None) -> ShopDocument:
    if kind not in KINDS:
        raise DocumentError(f"Type de document inconnu : {kind}")
    m = _DATA_URL.match(data_url or "")
    if not m:
        raise DocumentError("Fichier invalide (image PNG/JPEG/WEBP ou PDF en base64 attendu)")
    raw = base64.b64decode(m.group("b"), validate=False)
    if len(raw) > MAX_BYTES:
        raise DocumentError("Document trop volumineux (> 10 Mo)")
    mime = ext = None
    for magic, mt, e in MAGIC:
        if raw.startswith(magic):
            mime, ext = mt, e
    if not mime:
        raise DocumentError("Format non reconnu (PNG, JPEG, WEBP ou PDF)")
    sha = hashlib.sha256(raw).hexdigest()
    dup = db.scalars(select(ShopDocument).where(ShopDocument.sha256 == sha)).first()
    orig = _dir("originals") / f"{sha}.{ext}.enc"
    if not orig.exists():
        orig.write_bytes(encrypt_bytes(raw))
        try:
            os.chmod(orig, 0o400)  # original en lecture seule
        except OSError:
            pass
    work = _dir("working") / f"{sha[:16]}-{len(list(_dir('working').iterdir()))}.{ext}.enc"
    work.write_bytes(encrypt_bytes(raw))
    base = get_settings().data_dir
    doc = ShopDocument(kind=kind, promotion_id=promotion_id, claim_id=claim_id, original_path=str(orig.relative_to(base)),
                       working_path=str(work.relative_to(base)), sha256=sha, mime=mime, size=len(raw), sensitive=kind in SENSITIVE_KINDS,
                       extracted={"duplicate_of": dup.id} if dup else {})
    db.add(doc)
    db.commit()
    return doc


def read_original(doc: ShopDocument) -> bytes:
    raw = decrypt_bytes((get_settings().data_dir / doc.original_path).read_bytes())
    if hashlib.sha256(raw).hexdigest() != doc.sha256:
        raise DocumentError("Original altéré : empreinte SHA-256 différente")
    return raw


def read_working(doc: ShopDocument) -> bytes:
    return decrypt_bytes((get_settings().data_dir / doc.working_path).read_bytes())


# ------------------------------------------------------------------ OCR
OCR_PROMPT = ("Transcris fidèlement tout le texte visible de cette image (ticket de caisse, emballage ou étiquette), ligne par ligne, "
              "sans rien inventer ni corriger. Si un code-barres est visible, recopie les chiffres imprimés dessous. "
              "Si l'image est illisible, réponds exactement : ILLISIBLE.")


def ocr(db: Session, doc: ShopDocument, user_text: str | None = None) -> ShopDocument:
    """Extrait le texte : texte fourni par l'utilisateur, sinon modèle de vision local (Ollama) si activé."""
    if user_text is not None:
        doc.ocr_text, doc.ocr_method = user_text[:20_000], "user_text"
    else:
        st = get_settings_dict(db)
        if not st["llm_enabled"] or doc.mime == "application/pdf":
            doc.ocr_method = "none"
        else:
            model = st.get("llm_model_vision") or "qwen2.5vl:7b"
            try:
                img = base64.b64encode(read_working(doc)).decode()
                r = httpx.post(f"{st['ollama_url'].rstrip('/')}/api/chat", timeout=180,
                               json={"model": model, "stream": False, "options": {"temperature": 0},
                                     "messages": [{"role": "user", "content": OCR_PROMPT, "images": [img]}]})
                r.raise_for_status()
                doc.ocr_text, doc.ocr_method = r.json()["message"]["content"][:20_000], f"ollama:{model}"
            except Exception as e:  # noqa: BLE001
                doc.ocr_method = "none"
                doc.extracted = {**(doc.extracted or {}), "ocr_error": str(e)[:200]}
    parsed = parse_receipt(doc.ocr_text or "") if doc.kind in ("receipt", "invoice") else parse_generic(doc.ocr_text or "")
    doc.extracted = {**{k: v for k, v in (doc.extracted or {}).items() if k in ("duplicate_of", "ocr_error")}, **parsed}
    doc.readability = parsed["readability"] if doc.ocr_text else ("pending" if doc.ocr_method == "none" else "unreadable")
    db.commit()
    return doc


_TICKET = re.compile(r"(?:ticket|transaction|trans\.?|n°\s?ticket|no\s?ticket|caisse\s?\d+\s?ticket)\s*(?:n°|no|nr|num|:|#)?\s*(\d{3,})", re.I)
_TOTAL = re.compile(r"(?:total|montant|a payer|à payer|net a payer)[^\d\n]{0,25}(\d{1,4}[.,]\d{2})", re.I)
_LINE = re.compile(r"^\s*(?:(\d{1,2})\s*[xX*]\s*)?(?P<label>[A-Za-zÀ-ÿ0-9][^\n]{2,60}?)\s+(?:(\d{1,2})\s*[xX*]\s*\d+[.,]\d{2}\s+)?(?P<price>-?\d{1,4}[.,]\d{2})\s*(?:€|EUR|[A-Z]{1,2})?\s*$")
_SKIP = re.compile(r"total|tva|cb |carte|rendu|especes|espèces|sous-total|montant|a payer|à payer|merci|fidelite|fidélité|remise|avantage|cagnotte", re.I)


def parse_receipt(text: str) -> dict:
    """Champs d'un ticket de caisse. Ne devine rien : un champ illisible reste vide et est signalé."""
    t = text or ""
    if len(re.sub(r"\s", "", t)) < 15 or t.strip().upper().startswith("ILLISIBLE"):
        return {"readability": "unreadable", "missing": ["texte"], "lines": []}
    head = "\n".join(t.splitlines()[:8])
    retailers = find_retailers(head) or find_retailers(t)
    dates = [d for _, d in parse_dates_in(norm(t)) if d <= date.today()]
    tm = _TICKET.search(t)
    total = _TOTAL.search(t)
    lines = []
    for ln in t.splitlines():
        m = _LINE.match(ln)
        if m and not _SKIP.search(ln):
            qty = int(m.group(1) or m.group(3) or 1)
            lines.append({"label": m.group("label").strip(), "price_eur": _to_float(m.group("price")), "quantity": qty})
    out = {
        "retailer": retailers[0] if retailers else None,
        "store": t.strip().splitlines()[0].strip()[:120] if t.strip() else None,
        "purchase_date": dates[0].isoformat() if dates else None,
        "ticket_number": tm.group(1) if tm else None,
        "total_eur": _to_float(total.group(1)) if total else None,
        "lines": lines[:80],
        "eans": find_eans(t),
    }
    missing = [lab for k, lab in (("purchase_date", "date d'achat"), ("retailer", "enseigne"), ("total_eur", "total"),
                                  ("ticket_number", "numéro de ticket")) if not out[k]]
    if not lines:
        missing.append("lignes de produits")
    out["missing"] = missing
    critical = {"date d'achat", "enseigne", "lignes de produits"} & set(missing)
    out["readability"] = "ok" if not critical else ("unreadable" if len(critical) == 3 else "incomplete")
    return out


def parse_generic(text: str) -> dict:
    if not (text or "").strip() or text.strip().upper().startswith("ILLISIBLE"):
        return {"readability": "unreadable", "eans": []}
    return {"readability": "ok", "eans": find_eans(text), "retailers": find_retailers(text)}


def fields(doc: ShopDocument) -> dict:
    """Champs effectifs : extraction + corrections de l'utilisateur (le justificatif n'est pas modifié)."""
    return {**(doc.extracted or {}), **(doc.user_fields or {})}


def set_user_fields(db: Session, doc: ShopDocument, data: dict) -> ShopDocument:
    allowed = {"retailer", "store", "purchase_date", "ticket_number", "total_eur", "lines", "eans", "ean"}
    clean = {k: v for k, v in (data or {}).items() if k in allowed}
    if "purchase_date" in clean and clean["purchase_date"]:
        date.fromisoformat(str(clean["purchase_date"]))
    doc.user_fields = {**(doc.user_fields or {}), **clean}
    f = fields(doc)
    if doc.kind in ("receipt", "invoice"):
        crit = [k for k in ("purchase_date", "retailer") if not f.get(k)] + ([] if f.get("lines") else ["lines"])
        doc.readability = "ok" if not crit else "incomplete"
    elif f.get("eans") or f.get("ean"):
        doc.readability = "ok"
    db.commit()
    return doc
