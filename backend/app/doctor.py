"""Diagnostic de l'installation (utilisé par la CLI et scripts/doctor.ps1)."""
from __future__ import annotations

import platform
import shutil
import sqlite3

from . import __version__
from .config import get_settings


def report() -> dict:
    s = get_settings()
    out: dict = {"version": __version__, "python": platform.python_version(), "os": platform.platform(), "data_dir": str(s.data_dir)}
    out["disk_free_gb"] = round(shutil.disk_usage(s.data_dir).free / 1e9, 1)
    try:
        con = sqlite3.connect(s.db_path)
        out["db_integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0]
        out["schema_version"] = con.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        con.close()
    except sqlite3.Error as e:
        out["db_integrity"] = f"erreur : {e}"
    try:
        import httpx

        r = httpx.get("http://127.0.0.1:11434/api/tags", timeout=2)
        out["ollama_models"] = [m["name"] for m in r.json().get("models", [])]
    except Exception:  # noqa: BLE001
        out["ollama_models"] = "Ollama non joignable (optionnel)"
    try:
        import playwright  # noqa: F401

        out["playwright"] = "installé (navigateur : python -m playwright install chromium)"
    except ImportError:
        out["playwright"] = "absent (participation automatique indisponible, le reste fonctionne)"
    from pathlib import Path

    out["frontend_built"] = (Path(__file__).parent / "static" / "index.html").exists()
    return out
