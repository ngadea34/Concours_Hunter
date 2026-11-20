"""Profil du participant (chiffré) et consentements."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Consent, UserProfile
from ..security.crypto import decrypt_json, encrypt_json

PROFILE_FIELDS = ["first_name", "last_name", "email", "phone", "birth_date", "address", "postal_code", "city", "country"]
CONSENT_KEYS = {
    "auto_participation": "J'autorise Concours Hunter à soumettre automatiquement des participations uniquement lorsque le règlement l'autorise clairement, sans CAPTCHA ni connexion.",
    "store_proofs": "J'autorise la conservation locale de captures d'écran et preuves de participation.",
    "email_notifications": "J'accepte de recevoir des notifications par e-mail (si configuré).",
}


def get_profile(db: Session) -> dict:
    row = db.scalars(select(UserProfile)).first()
    data = decrypt_json(row.encrypted_data) if row else {}
    out = {k: data.get(k) for k in PROFILE_FIELDS}
    if not out["country"]:
        out["country"] = "FR"
    return out


def save_profile(db: Session, data: dict) -> dict:
    clean = {k: (str(data[k]).strip()[:300] if data.get(k) not in (None, "") else None) for k in PROFILE_FIELDS}
    row = db.scalars(select(UserProfile)).first()
    if row is None:
        db.add(UserProfile(encrypted_data=encrypt_json(clean)))
    else:
        row.encrypted_data = encrypt_json(clean)
    db.commit()
    return get_profile(db)


def profile_age(profile: dict, today: date | None = None) -> int | None:
    bd = profile.get("birth_date")
    if not bd:
        return None
    try:
        b = date.fromisoformat(bd[:10])
    except ValueError:
        return None
    t = today or date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def is_dom(profile: dict) -> bool:
    pc = (profile.get("postal_code") or "").strip()
    return pc.startswith(("971", "972", "973", "974", "975", "976", "977", "978", "98"))


def get_consents(db: Session) -> dict:
    rows = {c.key: c for c in db.scalars(select(Consent))}
    out = {k: bool(rows[k].granted) if k in rows else False for k in CONSENT_KEYS}
    ts = [r.updated_at for r in rows.values() if r.updated_at]
    out["updated_at"] = max(ts).isoformat() if ts else None
    return out


def save_consents(db: Session, data: dict) -> dict:
    rows = {c.key: c for c in db.scalars(select(Consent))}
    for k, text in CONSENT_KEYS.items():
        if k in data and data[k] is not None:
            if k in rows:
                rows[k].granted = bool(data[k])
                rows[k].text = text
            else:
                db.add(Consent(key=k, granted=bool(data[k]), text=text))
    db.commit()
    return get_consents(db)
