"""Fiche produit par code EAN via Open Food Facts (base ouverte, licence ODbL, API publique documentée : catégorie 3/4).

Sert à confirmer la référence exacte (nom, marque, format). Les magasins listés par Open Food Facts sont contributifs :
ils ne valent que « signalé par une source tierce », jamais « en rayon ».
"""
from __future__ import annotations

import json

from ..discovery.fetcher import FetchBlocked, Fetcher
from .products import ean_valid

API = "https://world.openfoodfacts.org/api/v2/product/{ean}.json?fields=product_name,brands,quantity,stores,countries_tags"
SOURCE = "Open Food Facts (base contributive, licence ODbL)"


def lookup(ean: str, fetcher: Fetcher | None = None) -> dict:
    if not ean_valid(ean):
        return {"ean": ean, "found": False, "error": "Code EAN invalide (clé de contrôle)"}
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    try:
        res = fetcher.get(API.format(ean=ean))
        data = json.loads(res.text)
    except (FetchBlocked, ValueError) as e:
        return {"ean": ean, "found": False, "error": str(e)[:200]}
    except Exception as e:  # noqa: BLE001
        return {"ean": ean, "found": False, "error": f"Source injoignable : {e}"[:200]}
    finally:
        if own:
            fetcher.close()
    p = data.get("product") or {}
    if data.get("status") != 1 or not p:
        return {"ean": ean, "found": False, "error": "Produit inconnu d'Open Food Facts"}
    stores = [s.strip() for s in (p.get("stores") or "").split(",") if s.strip()]
    return {"ean": ean, "found": True, "name": p.get("product_name"), "brand": p.get("brands"), "quantity": p.get("quantity"),
            "stores": stores, "sold_in_france": "en:france" in (p.get("countries_tags") or []), "source": SOURCE}
