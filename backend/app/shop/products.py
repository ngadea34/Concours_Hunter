"""Identification exacte des produits (agent SHOP) : codes EAN, formats, correspondance stricte.

Une promotion peut ne concerner qu'un format, un parfum, un EAN, une quantité minimale ou une édition spéciale.
On n'accepte jamais une correspondance fondée seulement sur une ressemblance de nom ou de marque.
"""
from __future__ import annotations

import re

from ..i18n.geo import norm

RETAILERS = {
    "carrefour": "Carrefour", "e.leclerc": "E.Leclerc", "leclerc": "E.Leclerc", "intermarche": "Intermarché", "auchan": "Auchan",
    "super u": "Super U", "hyper u": "Hyper U", "u express": "U Express", "magasins u": "Magasins U", "systeme u": "Magasins U",
    "lidl": "Lidl", "aldi": "Aldi", "monoprix": "Monoprix", "casino": "Casino", "franprix": "Franprix", "cora": "Cora",
    "netto": "Netto", "match": "Supermarchés Match", "grand frais": "Grand Frais", "picard": "Picard", "biocoop": "Biocoop",
    "leader price": "Leader Price", "action": "Action", "naturalia": "Naturalia", "spar": "Spar", "vival": "Vival",
}
DEFAULT_RETAILERS = ["Carrefour", "E.Leclerc", "Intermarché", "Auchan", "Super U", "Hyper U", "Lidl", "Aldi", "Monoprix"]
_RETAILER_RX = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(RETAILERS, key=len, reverse=True)) + r")\b")
_EAN_RX = re.compile(r"(?<!\d)(\d{13}|\d{8})(?!\d)")
_QTY_RX = re.compile(r"(\d+(?:[.,]\d+)?)\s?(kg|g|mg|l|cl|ml|x)\b", re.I)


def ean_valid(code: str | None) -> bool:
    """Contrôle de la clé EAN-8 / EAN-13 (GTIN)."""
    if not code or not code.isdigit() or len(code) not in (8, 13):
        return False
    digits = [int(c) for c in code]
    body, key = digits[:-1], digits[-1]
    weights = [3, 1] if len(code) == 13 else [3, 1]
    total = sum(d * weights[(len(body) - 1 - i) % 2] for i, d in enumerate(body))
    return (10 - total % 10) % 10 == key


def find_eans(text: str) -> list[str]:
    return list(dict.fromkeys(c for c in _EAN_RX.findall(text or "") if ean_valid(c)))


def find_retailers(text: str) -> list[str]:
    t = norm(text or "")
    return list(dict.fromkeys(RETAILERS[m] for m in _RETAILER_RX.findall(t)))


def canonical_retailer(name: str | None) -> str | None:
    if not name:
        return None
    found = find_retailers(name)
    return found[0] if found else name.strip()[:60]


def quantity(text: str) -> str | None:
    """Format normalisé : « 250 g », « 1 l », « 75 cl »."""
    m = _QTY_RX.search(text or "")
    if not m:
        return None
    num = m.group(1).replace(",", ".").rstrip("0").rstrip(".") if "." in m.group(1).replace(",", ".") else m.group(1)
    return f"{num} {m.group(2).lower()}"


def _grams(q: str | None) -> float | None:
    if not q:
        return None
    m = re.match(r"([\d.]+) (kg|g|mg|l|cl|ml)$", q)
    if not m:
        return None
    v = float(m.group(1))
    return v * {"kg": 1000, "g": 1, "mg": 0.001, "l": 1000, "cl": 10, "ml": 1}[m.group(2)]


def match_product(promo_eans: list[str], variant: dict, observed: dict) -> dict:
    """Compare un produit observé (ticket, code-barres, fiche) aux conditions de l'opération.

    observed : {ean?, label?, quantity?, count?}. Retourne {status: exact | mismatch | unverified, reasons[]}.
    - EAN listés par l'opération : seul un EAN identique vaut correspondance.
    - Sans EAN listé : format, parfum/variante et quantité minimale doivent tous être confirmés ; sinon « à vérifier ».
    """
    reasons = []
    ean = (observed.get("ean") or "").strip()
    if ean and not ean_valid(ean):
        return {"status": "mismatch", "reasons": [f"Code EAN {ean} invalide (clé de contrôle fausse)"]}
    if promo_eans:
        if not ean:
            return {"status": "unverified", "reasons": ["L'opération vise des EAN précis : photographiez le code-barres du produit"]}
        if ean in promo_eans:
            reasons.append(f"EAN {ean} identique à celui du règlement")
        else:
            return {"status": "mismatch", "reasons": [f"EAN {ean} absent de la liste du règlement ({', '.join(promo_eans)})"]}
    label = norm(observed.get("label") or "")
    want_q = variant.get("quantity")
    if want_q:
        got_q = observed.get("quantity") or quantity(observed.get("label") or "")
        if not got_q:
            if not promo_eans:
                return {"status": "unverified", "reasons": [f"Format exigé {want_q} : non lisible sur le justificatif"]}
        elif _grams(got_q) != _grams(want_q) and got_q != want_q:
            return {"status": "mismatch", "reasons": [f"Format {got_q} au lieu de {want_q}"]}
        else:
            reasons.append(f"Format {want_q} confirmé")
    for key, lab in (("flavor", "Parfum ou variante"), ("edition", "Édition")):
        want = variant.get(key)
        if want and not promo_eans:
            if norm(want) not in label:
                return {"status": "unverified", "reasons": [f"{lab} exigé(e) « {want} » non confirmé(e)"]}
            reasons.append(f"{lab} « {want} » confirmé(e)")
    mq = variant.get("min_quantity")
    if mq and (observed.get("count") or 1) < mq:
        return {"status": "mismatch", "reasons": [f"Quantité minimale {mq} non atteinte"]}
    if not promo_eans and not reasons:
        return {"status": "unverified", "reasons": ["Le règlement ne donne ni EAN ni format : vérifiez la référence exacte (le nom ou la marque ne suffisent pas)"]}
    return {"status": "exact", "reasons": reasons}
