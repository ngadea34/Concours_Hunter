from sqlalchemy.orm import Session

from .db.models import AuditLog


def audit(db: Session, actor: str, action: str, **detail) -> None:
    db.add(AuditLog(actor=actor, action=action, detail={k: v for k, v in detail.items() if v is not None}))
