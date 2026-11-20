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


def _m002_game_type(conn: Connection) -> None:
    cols = {r[1] for r in conn.execute(text("PRAGMA table_info(contests)"))}
    if "game_type" not in cols:
        conn.execute(text("ALTER TABLE contests ADD COLUMN game_type VARCHAR(20)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contests_game_type ON contests (game_type)"))
    _classify_existing(conn, only_missing=True)


def _classify_existing(conn: Connection, only_missing: bool) -> None:
    """Classe les concours déjà en base (sans aucune requête réseau)."""
    import json

    from ..intelligence.game_type import classify_game_type

    rows = conn.execute(text("SELECT c.id, c.title, c.description, c.url, c.flags, "
                             "(SELECT r.text FROM contest_rules r WHERE r.contest_id = c.id ORDER BY r.id DESC LIMIT 1) "
                             "FROM contests c" + (" WHERE c.game_type IS NULL" if only_missing else ""))).all()
    for cid, title, desc, url, flags, rtext in rows:
        try:
            fl = json.loads(flags) if isinstance(flags, str) else (flags or [])
        except ValueError:
            fl = []
        gt = classify_game_type(" ".join(filter(None, [title, desc, rtext])), url, fl)
        if gt or not only_missing:
            conn.execute(text("UPDATE contests SET game_type = :g WHERE id = :i"), {"g": gt, "i": cid})


def _m003_fix_site_contests(conn: Connection) -> None:
    """Concours venus d'un site suivi : l'URL du jeu redevient la page du site (et non un lien externe trouvé dessus),
    les pages qui listent les jeux sont archivées, et tous les types de jeu sont recalculés."""
    from urllib.parse import urlsplit

    from ..discovery.connectors.site import is_contest_url
    from ..security.sanitize import canonical_url

    def bare(u: str) -> str:
        return (urlsplit(u).hostname or "").lower().removeprefix("www.")

    rows = conn.execute(text("SELECT c.id, c.url, s.source_url FROM contests c JOIN contest_sightings s ON s.contest_id = c.id "
                             "JOIN sources src ON src.id = s.source_id WHERE src.kind = 'site'")).all()
    for cid, url, page in rows:
        if bare(url) != bare(page):
            conn.execute(text("UPDATE contests SET url = :u, canonical_url = :c WHERE id = :i"), {"u": page, "c": canonical_url(page), "i": cid})
        if not is_contest_url(page):
            conn.execute(text("UPDATE contests SET status = 'archived' WHERE id = :i AND status IN ('new', 'to_verify')"), {"i": cid})
    _classify_existing(conn, only_missing=False)


MIGRATIONS: list[tuple[int, str, Callable[[Connection], None]]] = [
    (1, "schéma initial", _m001_initial),
    (2, "type de jeu (tirage, instant gagnant, quiz...)", _m002_game_type),
    (3, "corrections du premier essai des sites d'organisateurs", _m003_fix_site_contests),
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
