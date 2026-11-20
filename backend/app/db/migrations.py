"""Migrations versionnées minimalistes (décision D3).

Chaque migration est une fonction (connexion) -> None, appliquée une seule fois, dans l'ordre.
Une sauvegarde automatique est faite avant toute migration sur une base existante.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import Connection, text

from .models import Base
from .session import get_engine

log = logging.getLogger(__name__)


def _m001_initial(conn: Connection) -> None:
    Base.metadata.create_all(conn)


MIGRATIONS: list[tuple[int, str, Callable[[Connection], None]]] = [
    (1, "schéma initial", _m001_initial),
]

LATEST = MIGRATIONS[-1][0]


def current_version(conn: Connection) -> int:
    conn.execute(text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL, applied_at TEXT DEFAULT CURRENT_TIMESTAMP, label TEXT)"))
    v = conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar()
    return int(v or 0)


def migrate() -> int:
    engine = get_engine()
    with engine.begin() as conn:
        v = current_version(conn)
    if v >= LATEST:
        return v
    if v > 0:
        from ..admin.backup import create_backup

        create_backup(label=f"pre-migration-v{v}")
    with engine.begin() as conn:
        for version, label, fn in MIGRATIONS:
            if version > v:
                log.info("Migration %s : %s", version, label)
                fn(conn)
                conn.execute(text("INSERT INTO schema_version(version, label) VALUES (:v, :l)"), {"v": version, "l": label})
    return LATEST
