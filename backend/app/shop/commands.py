"""Commande /hunter-shop (interface web, API et ligne de commande)."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..db.models import Promotion
from . import claims as CL
from . import ledger
from .analyze import analyze_offer
from .recommend import dashboard, recommendations

SUBCOMMANDS = {"discover": "Recherche les offres promotionnelles", "available": "Produits des opérations dans vos enseignes",
               "cashback": "Produits remboursés intégralement ou partiellement", "contests": "Jeux-concours avec achat obligatoire",
               "analyze": "Analyse une offre ou un règlement (texte collé)", "submit": "Prépare un dossier (n° de l'opération)",
               "track": "Suit les remboursements et participations en cours", "report": "Bilan financier du mois"}
TAB = {"discover": "available", "available": "available", "cashback": "available", "contests": "available", "analyze": "analyze",
       "submit": "claims", "track": "claims", "report": "expenses"}


def _fmt(b: dict) -> str:
    f = b["finance"]
    net = f["net_cost_forecast_eur"]
    return (f"[{b['category']}] {b['title']} · {', '.join(b['retailers']) or 'enseignes non précisées'} · "
            f"prix {b['price_eur'] if b['price_eur'] is not None else '?'} € · coût net prévisionnel {net if net is not None else '?'} € · "
            f"{b['availability']['text']} · {b['action']}")


def run(db: Session, text: str) -> dict:
    parts = (text or "").strip().split(maxsplit=1)
    if parts and parts[0].lstrip("/") in ("hunter-shop", "shop"):
        parts = parts[1].split(maxsplit=1) if len(parts) > 1 else []
    sub = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""
    if sub not in SUBCOMMANDS:
        return {"tab": "available", "text": "Sous-commandes : " + " · ".join(f"{k} ({v})" for k, v in SUBCOMMANDS.items()), "data": None}
    if sub == "discover":
        from .discover import discover_all

        r = discover_all(db)
        return {"tab": TAB[sub], "text": f"{r['from_contests']} jeu(x) avec achat ajouté(s), {r['sources_scanned']} site(s) d'offres lu(s).", "data": r}
    if sub in ("available", "cashback", "contests"):
        kinds = {"available": None, "cashback": ("full_refund", "partial_refund", "voucher", "receipt_offer", "code_offer"),
                 "contests": ("purchase_game",)}[sub]
        r = recommendations(db, kinds=kinds)
        lines = [_fmt(b) for b in r["items"]] or ["Aucune opération ne correspond à vos réglages."]
        return {"tab": TAB[sub], "text": "\n".join(lines + ["", r["realtime_note"], r["note"]]), "data": r}
    if sub == "analyze":
        if not arg.strip():
            return {"tab": "analyze", "text": "Collez le texte de l'offre ou du règlement après la commande.", "data": None}
        a = analyze_offer(arg)
        a.pop("rules_text", None)
        return {"tab": "analyze", "text": "\n".join(f"{k} : {v}" for k, v in a.items() if k != "analysis"), "data": a}
    if sub == "submit":
        if not arg.strip().isdigit():
            d = dashboard(db)
            return {"tab": "claims", "text": "Indiquez le numéro de l'opération : /hunter-shop submit 12\nDossiers à compléter : "
                    + (", ".join(f"#{c['id']} {c['promotion_title']}" for c in d["claims_to_complete"]) or "aucun"), "data": None}
        p = db.get(Promotion, int(arg))
        if p is None:
            return {"tab": "claims", "text": "Opération introuvable.", "data": None}
        c = CL.create_claim(db, p)
        checks = CL.run_checks(db, c)
        return {"tab": "claims", "text": f"Dossier #{c.id} créé.\n" + "\n".join(f"{x['step']}. {x['label']} : {x['status']} · {x['detail']}" for x in checks),
                "data": CL.out(c)}
    if sub == "track":
        d = dashboard(db)
        rows = d["claims_sent"] + [c for c in d["refunds_awaiting"] if c not in d["claims_sent"]]
        lines = [f"#{c['id']} {c['promotion_title']} · {c['status']}{' · EN RETARD' if c['late'] else ''}" for c in rows]
        return {"tab": "claims", "text": "\n".join(lines) or "Aucun dossier en cours.", "data": d}
    s = ledger.monthly_stats(db, arg.strip() or None)
    return {"tab": "expenses", "text": (f"{s['month']} · dépenses {s['expenses_eur']} € · économies réalisées {s['savings_realized_eur']} € · "
                                        f"en attente {s['refunds_pending_eur']} € · refusés {s['refunds_refused_eur']} € · gains aléatoires "
                                        f"{s['random_gains_eur']} € · coût net réel {s['net_real_cost_eur']} € · plafond restant {s['cap_left_eur']} €"),
            "data": s}


_ = date
