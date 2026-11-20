"""Sauvegarde / restauration SQLite (API backup en ligne, cohérente même base ouverte)."""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from ..config import get_settings

NAME_RE = re.compile(r"^concours-\d{8}-\d{6}(-[a-z0-9-]+)?\.db$")


def create_backup(label: str | None = None) -> dict:
    s = get_settings()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = re.sub(r"[^a-z0-9-]", "", (label or "").lower())[:40]
    name = f"concours-{stamp}{'-' + safe if safe else ''}.db"
    dest = s.backups_dir / name
    i = 1
    while dest.exists():
        name = f"concours-{stamp}-{safe or 'b'}{i}.db"
        dest = s.backups_dir / name
        i += 1
    src = sqlite3.connect(s.db_path)
    try:
        dst = sqlite3.connect(dest)
        with dst:
            src.backup(dst)
        dst.close()
    finally:
        src.close()
    _verify(dest)
    _rotate()
    return {"name": name, "size": dest.stat().st_size}


def _verify(path: Path) -> None:
    con = sqlite3.connect(path)
    try:
        ok = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    if ok != "ok":
        raise RuntimeError(f"Sauvegarde corrompue : {ok}")


def _rotate() -> None:
    s = get_settings()
    files = sorted(s.backups_dir.glob("concours-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[s.max_backups:]:
        old.unlink(missing_ok=True)


def list_backups() -> list[dict]:
    s = get_settings()
    out = []
    for p in sorted(s.backups_dir.glob("concours-*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
        out.append({"name": p.name, "size": p.stat().st_size, "created_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat()})
    return out


def restore_backup(name: str) -> None:
    """Restaure une sauvegarde. Sauvegarde d'abord l'état courant (jamais de perte)."""
    if not NAME_RE.match(name):
        raise ValueError("Nom de sauvegarde invalide")
    s = get_settings()
    src_path = s.backups_dir / name
    if not src_path.is_file():
        raise FileNotFoundError(name)
    _verify(src_path)
    create_backup(label="pre-restore")
    from ..db.session import dispose_engine

    dispose_engine()
    src = sqlite3.connect(src_path)
    try:
        dst = sqlite3.connect(s.db_path)
        with dst:
            src.backup(dst)
        dst.close()
    finally:
        src.close()
    for suffix in ("-wal", "-shm"):
        p = Path(str(s.db_path) + suffix)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
