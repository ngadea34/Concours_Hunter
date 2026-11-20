"""M04 : participations (préparation, anti-doublon, validation humaine, preuves)."""
from __future__ import annotations

import base64
import hashlib
import re
from datetime import date
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import get_settings
from ..db.models import Contest, Participation, ParticipationProof, utcnow
from ..notifications.service import notify
from ..security.sanitize import canonical_url
from .profile import PROFILE_FIELDS, get_consents, get_profile

ACTIVE = ("prepared", "awaiting_human", "submitted", "confirmed")
MAX_PROOF_BYTES = 5_000_000


class ParticipationError(ValueError):
    pass


def period_key(period: str | None, today: date | None = None) -> str:
    t = today or date.today()
    if period == "daily":
        return t.isoformat()
    if period == "weekly":
        y, w, _ = t.isocalendar()
        return f"{y}-W{w:02d}"
    if period == "monthly":
        return t.strftime("%Y-%m")
    return "once"


def prepare(db: Session, contest: Contest, requested_mode: str | None = None, purchase_flow: bool = False) -> Participation:
    """purchase_flow : parcours « jeu avec achat » de M14 (achat fait par l'utilisateur, dossier validé par lui) ; toujours manuel."""
    purchase_ok = purchase_flow and contest.free_status == "purchase_required"
    if contest.status in ("expired", "archived") or (contest.status == "rejected" and not purchase_ok):
        raise ParticipationError(f"Participation impossible : concours {contest.status}")
    if contest.end_date and contest.end_date < date.today():
        raise ParticipationError("Concours clôturé")
    if contest.free_status == "purchase_required" and not purchase_ok:
        raise ParticipationError("Achat obligatoire : participation refusée")
    if purchase_ok:
        requested_mode = "manual"
    period = contest.policy.period if contest.policy else "once"
    key = period_key(period)
    dup = db.scalars(select(Participation).where(Participation.contest_id == contest.id, Participation.period_key == key,
                                                Participation.status.in_(ACTIVE))).first()
    if dup:
        raise ParticipationError(f"Déjà une participation pour cette période ({key}) : double participation refusée")
    policy_mode = contest.policy.mode if contest.policy else "manual"
    consents = get_consents(db)
    mode = requested_mode or policy_mode
    order = {"manual": 0, "semi": 1, "auto": 2}
    if order.get(mode, 0) > order[policy_mode]:
        mode = policy_mode  # on ne peut jamais dépasser la politique du concours
    if mode == "auto" and not consents["auto_participation"]:
        mode = "semi"
    if contest.status == "to_verify" and mode == "auto":
        mode = "semi"
    p = Participation(contest_id=contest.id, mode=mode, period_key=key, status="prepared" if mode == "auto" else "awaiting_human")
    db.add(p)
    db.flush()
    if p.status == "awaiting_human":
        notify(db, "to_validate", f"Participation à valider : {contest.title[:150]}", "Préremplissage prêt ; la soumission se fait par vous.",
               contest.id, dedup_key=f"validate:{p.id}")
    audit(db, "user", "participation_prepare", contest_id=contest.id, participation_id=p.id, mode=mode)
    db.commit()
    return p


def prefill(db: Session, p: Participation) -> dict:
    profile = get_profile(db)
    fields = {k: v for k, v in profile.items() if v}
    warnings = []
    missing = [k for k in ("first_name", "last_name", "email") if not profile.get(k)]
    if missing:
        warnings.append("Profil incomplet : " + ", ".join(missing))
    answers = sorted(p.contest.answers, key=lambda a: (not a.verified, -a.confidence))
    seen, out = set(), []
    for a in answers:
        if a.question_norm in seen:
            continue
        seen.add(a.question_norm)
        out.append({"question": a.question, "answer": a.answer})
        if not a.verified:
            warnings.append(f"Réponse non vérifiée : « {a.question[:80]} » (source : {a.source})")
    flags = p.contest.flags or []
    if "captcha" in flags:
        warnings.append("CAPTCHA présent : à résoudre par vous")
    if "login_required" in flags:
        warnings.append("Connexion à un compte requise sur le site")
    if p.contest.status == "to_verify":
        warnings.append("Concours non entièrement vérifié : " + (p.contest.needs_human_reason or ""))
    return {"contest_url": p.contest.url, "fields": {k: fields[k] for k in PROFILE_FIELDS if k in fields}, "answers": out, "warnings": warnings}


def mark(db: Session, p: Participation, status: str, note: str | None = None, error: str | None = None, minutes: float | None = None) -> Participation:
    allowed = {
        "submitted": ("prepared", "awaiting_human", "failed"),
        "confirmed": ("submitted",),
        "failed": ("prepared", "awaiting_human", "submitted"),
        "cancelled": ("prepared", "awaiting_human", "failed"),
    }
    if p.status not in allowed[status]:
        raise ParticipationError(f"Transition {p.status} → {status} impossible")
    p.status = status
    if status == "submitted":
        p.submitted_at = utcnow()
        p.error = None
        if minutes is not None:
            p.time_spent_minutes = max(0.0, min(600.0, float(minutes)))
        if p.contest.status not in ("archived",):
            p.contest.status = "participated"
    elif status == "confirmed":
        p.confirmed_at = utcnow()
        notify(db, "confirmation", f"Participation confirmée : {p.contest.title[:150]}", note, p.contest_id, dedup_key=f"confirm:{p.id}")
    elif status == "failed":
        p.error = (error or "Erreur non précisée")[:1000]
    if note:
        db.add(ParticipationProof(participation=p, kind="note", note=note[:2000]))
    audit(db, "user", f"participation_{status}", participation_id=p.id)
    db.commit()
    return p


_DATA_URL = re.compile(r"^data:image/(png|jpeg);base64,(?P<b>[A-Za-z0-9+/=\s]+)$")


def add_proof(db: Session, p: Participation, kind: str, data_url: str | None, note: str | None) -> Participation:
    path = sha = None
    if data_url:
        if not get_consents(db)["store_proofs"]:
            raise ParticipationError("Consentement « conservation des preuves » requis (Paramètres > Consentements)")
        m = _DATA_URL.match(data_url)
        if not m:
            raise ParticipationError("Image invalide (PNG/JPEG base64 attendu)")
        raw = base64.b64decode(m.group("b"), validate=False)
        if len(raw) > MAX_PROOF_BYTES:
            raise ParticipationError("Preuve trop volumineuse (> 5 Mo)")
        if not (raw[:8] == b"\x89PNG\r\n\x1a\n" or raw[:3] == b"\xff\xd8\xff"):
            raise ParticipationError("Le contenu n'est pas une image PNG/JPEG")
        sha = hashlib.sha256(raw).hexdigest()
        ext = "png" if raw[:4] == b"\x89PNG" else "jpg"
        d = get_settings().proofs_dir / str(p.id)
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{sha[:16]}.{ext}"
        f.write_bytes(raw)
        path = str(f.relative_to(get_settings().data_dir))
    db.add(ParticipationProof(participation=p, kind=kind if kind in ("screenshot", "note", "email", "html") else "note", path=path, sha256=sha, note=(note or None) and note[:2000]))
    db.commit()
    db.refresh(p)
    return p


def find_by_url(db: Session, url: str) -> list[Participation]:
    cu = canonical_url(url)
    host = urlsplit(cu).hostname or ""
    path = urlsplit(cu).path
    out = []
    for p in db.scalars(select(Participation).where(Participation.status.in_(("prepared", "awaiting_human", "failed"))).order_by(Participation.id.desc()).limit(200)):
        c = p.contest
        for u in [c.canonical_url] + [canonical_url(s.source_url) for s in c.sightings]:
            ph, pp = urlsplit(u).hostname or "", urlsplit(u).path
            if ph == host and (pp == path or path.startswith(pp.rstrip("/") + "/") or pp.startswith(path.rstrip("/") + "/") or pp == "/"):
                out.append(p)
                break
    return out
