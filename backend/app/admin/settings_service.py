"""Réglages applicatifs modifiables depuis l'UI (stockés en base, table settings)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import AppSetting

CATEGORIES = ["high_tech", "auto", "travel", "home", "voucher", "product", "culture", "leisure", "experience", "show", "restaurant", "cash", "other"]

DEFAULTS: dict = {
    "lan_mode": False,
    "llm_enabled": False,
    "ollama_url": "http://127.0.0.1:11434",
    "llm_model_small": "qwen2.5:3b",
    "llm_model_large": "qwen2.5:7b",
    "scan_interval_minutes": 180,
    "max_requests_per_domain_per_hour": 30,
    "interest_categories": {c: 5 for c in CATEGORIES},
    "ui_language": "fr",
    "llm_max_calls_per_day": 200,
}


def get_settings_dict(db: Session) -> dict:
    row = db.get(AppSetting, "app")
    data = dict(DEFAULTS)
    if row:
        data.update(row.value or {})
        data["interest_categories"] = {**DEFAULTS["interest_categories"], **(row.value or {}).get("interest_categories", {})}
    return data


def update_settings(db: Session, patch: dict) -> dict:
    current = get_settings_dict(db)
    for k, v in patch.items():
        if k not in DEFAULTS or v is None:
            continue
        if k == "interest_categories" and isinstance(v, dict):
            current[k] = {c: max(0, min(10, int(v.get(c, current[k].get(c, 5))))) for c in CATEGORIES}
        elif k == "scan_interval_minutes":
            current[k] = max(15, int(v))
        elif k == "max_requests_per_domain_per_hour":
            current[k] = max(1, min(600, int(v)))
        elif k == "llm_max_calls_per_day":
            current[k] = max(0, int(v))
        elif k == "ollama_url":
            s = str(v)
            if not s.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
                raise ValueError("Ollama doit rester local (127.0.0.1/localhost)")
            current[k] = s
        else:
            current[k] = type(DEFAULTS[k])(v)
    row = db.get(AppSetting, "app")
    if row is None:
        row = AppSetting(key="app", value=current)
        db.add(row)
    else:
        row.value = current
    db.commit()
    return current
