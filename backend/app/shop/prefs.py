"""Préférences d'achat (Réglages Shop & Promo), stockées dans la table settings (clé « shop »)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import AppSetting
from .products import DEFAULT_RETAILERS, canonical_retailer

DEFAULTS: dict = {
    "retailers": list(DEFAULT_RETAILERS),   # enseignes habituelles
    "stores": [],                           # magasins préférés : [{"retailer": "Carrefour", "name": "Carrefour Lyon Part-Dieu"}]
    "postal_code": "",                      # zone de recherche
    "radius_km": 10,                        # rayon de déplacement
    "categories": [],                       # catégories de produits souhaitées ([] = toutes)
    "max_price_eur": 30.0,                  # budget maximal par produit
    "monthly_cap_eur": 60.0,                # plafond mensuel d'achat
    "accepted_products": [],                # produits ou marques acceptés ([] = tous)
    "refused_products": [],                 # produits ou marques refusés
    "min_category": "C",                    # A, B ou C : catégorie minimale affichée dans les recommandations
}


def get_shop_prefs(db: Session) -> dict:
    row = db.get(AppSetting, "shop")
    return {**DEFAULTS, **((row.value or {}) if row else {})}


def update_shop_prefs(db: Session, patch: dict) -> dict:
    cur = get_shop_prefs(db)
    for k, v in (patch or {}).items():
        if k not in DEFAULTS or v is None:
            continue
        if k == "retailers":
            cur[k] = list(dict.fromkeys(filter(None, (canonical_retailer(str(x)) for x in v))))[:30]
        elif k == "stores":
            cur[k] = [{"retailer": canonical_retailer(str(s.get("retailer", ""))) or "", "name": str(s.get("name", ""))[:200]}
                      for s in v if isinstance(s, dict) and s.get("name")][:30]
        elif k in ("categories", "accepted_products", "refused_products"):
            cur[k] = [str(x).strip()[:80] for x in v if str(x).strip()][:100]
        elif k in ("max_price_eur", "monthly_cap_eur"):
            cur[k] = max(0.0, min(10_000.0, float(v)))
        elif k == "radius_km":
            cur[k] = max(0, min(200, int(v)))
        elif k == "postal_code":
            s = str(v).strip()
            if s and not (s.isdigit() and len(s) == 5):
                raise ValueError("Code postal : 5 chiffres")
            cur[k] = s
        elif k == "min_category":
            if v not in ("A", "B", "C"):
                raise ValueError("Catégorie minimale : A, B ou C")
            cur[k] = v
    row = db.get(AppSetting, "shop")
    if row is None:
        db.add(AppSetting(key="shop", value=cur))
    else:
        row.value = cur
    db.commit()
    return cur
