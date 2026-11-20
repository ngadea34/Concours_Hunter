"""Réglages applicatifs modifiables depuis l'UI (stockés en base, table settings)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import AppSetting

CATEGORIES = ["high_tech", "auto", "travel", "home", "voucher", "product", "culture", "leisure", "experience", "show", "restaurant", "cash", "other"]

DEFAULTS: dict = {
    "lan_mode": False,
    "llm_enabled": False,
    "ollama_url": "http://127.0.0.1:11434",
    "llm_model_small": "qwen3.5:4b",
    "llm_model_large": "qwen3:8b",
    "scan_interval_minutes": 180,
    "max_requests_per_domain_per_hour": 30,
    "interest_categories": {c: 5 for c in CATEGORIES},
    "ui_language": "fr",
    "llm_max_calls_per_day": 200,
    # autorisations écrites d'éditeurs : [{"domain": "ledemondujeu.com", "date": "2026-12-01", "reference": "e-mail du …"}]
    "written_authorizations": [],
}


def get_settings_dict(db: Session) -> dict:
    row = db.get(AppSetting, "app")
    data = dict(DEFAULTS)
    if row:
        data.update(row.value or {})
        data["interest_categories"] = {**DEFAULTS["interest_categories"], **(row.value or {}).get("interest_categories", {})}
    from ..discovery.policy import set_authorizations

    set_authorizations(data.get("written_authorizations") or [])
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
        elif k == "written_authorizations":
            from ..discovery.policy import AGGREGATORS

            if not isinstance(v, list):
                raise ValueError("written_authorizations doit être une liste")
            clean = []
            for e in v:
                dom = str((e or {}).get("domain", "")).lower().removeprefix("www.").strip()
                ref = str((e or {}).get("reference", "")).strip()
                if dom not in AGGREGATORS or len(ref) < 5:
                    raise ValueError(f"Autorisation invalide pour {dom or '?'} : domaine audité et référence de l'accord écrit obligatoires")
                clean.append({"domain": dom, "date": str((e or {}).get("date", ""))[:10], "reference": ref[:300]})
            current[k] = clean
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
    from ..discovery.policy import set_authorizations

    set_authorizations(current["written_authorizations"])
    return current
