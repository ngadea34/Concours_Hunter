"""M09 : notifications locales (dédupliquées). Canal e-mail/webhook : extension future, non activée."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Notification

KINDS = {"new_contest", "closing_soon", "to_validate", "to_verify", "confirmation", "draw", "win", "claim_deadline", "rules_changed", "phishing", "system"}


def notify(db: Session, kind: str, title: str, body: str | None = None, contest_id: int | None = None, dedup_key: str | None = None) -> Notification | None:
    if dedup_key and db.scalars(select(Notification).where(Notification.dedup_key == dedup_key)).first():
        return None
    n = Notification(kind=kind, title=title[:300], body=body, contest_id=contest_id, dedup_key=dedup_key)
    db.add(n)
    db.flush()
    return n
