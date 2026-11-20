"""Commandes /hunter-week (ligne de commande et barre de commande de l'interface)."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import reports as RP
from .prefs import DEFAULTS, get_prefs, update_prefs
from .reports import PRIO, RES, _d
from .view import week_view

SUBCOMMANDS = {"": "Synthèse de la semaine", "plan": "Génère le programme", "results": "Résultats attendus", "deadlines": "Échéances proches",
               "opportunities": "Opportunités à surveiller", "tasks": "Tâches à effectuer", "report": "Bilan de la semaine précédente",
               "next": "Semaine suivante", "settings": "Objectifs et temps disponible (clé=valeur pour modifier)"}
TAB = {"": "program", "plan": "program", "results": "results", "deadlines": "deadlines", "opportunities": "opportunities", "tasks": "tasks",
       "report": "reports", "next": "program", "settings": "settings"}


def parse(line: str) -> tuple[str, list[str]]:
    parts = line.strip().split()
    if parts and parts[0].lstrip("/") in ("hunter-week", "hunter_week"):
        parts = parts[1:]
    sub = parts[0].lower() if parts else ""
    if sub not in SUBCOMMANDS:
        raise ValueError("Sous-commande inconnue. Disponibles : " + ", ".join(k or "(aucune)" for k in SUBCOMMANDS))
    return sub, parts[1:]


def run(db: Session, line: str) -> dict:
    sub, args = parse(line)
    if sub in ("", "plan"):
        r = RP.weekly_summary(db)
        return {"tab": TAB[sub], "text": r.text, "week": None}
    if sub == "next":
        v = week_view(db, date.today() + timedelta(days=7))
        lines = [f"Semaine {v['label']} (du {_d(v['week_start'])} au {_d(v['week_end'])})"]
        lines += [f"- [{PRIO[i['priority']]}] {i['title']} — avant le {_d(i['end_date'])}" for i in v["priority"]] or ["Rien encore de recommandé."]
        return {"tab": "program", "text": "\n".join(lines), "week": v["week_start"]}
    v = week_view(db)
    if sub == "results":
        lines = [f"- {r['title']} — tirage {_d(r['draw_date'])}{' (estimé)' if r['draw_date_estimated'] else ''} — {RES[r['status']]}" for r in v["results"]]
        return {"tab": "results", "text": "\n".join(lines) or "Aucun résultat attendu cette semaine.", "week": None}
    if sub == "deadlines":
        lines = []
        for k, label in (("h24", "< 24 h"), ("h48", "< 48 h"), ("d7", "< 7 j"), ("d14", "< 14 j")):
            lines += [f"- ({label}) {c['title']} — {c['url']}" for c in v["last_chances"][k]]
        return {"tab": "deadlines", "text": "\n".join(lines) or "Aucune échéance dans les 14 jours.", "week": None}
    if sub == "opportunities":
        lines = [f"- {o['title']} : {'; '.join(o['why'])}" for o in v["opportunities"]]
        return {"tab": "opportunities", "text": "\n".join(lines) or "Aucune opportunité à surveiller.", "week": None}
    if sub == "tasks":
        lines = [f"- [{PRIO.get(t['priority'], t['priority'])}] {t['title']}" + (f" — {t['due_at'][:16].replace('T', ' ')}" if t["due_at"] else "")
                 + (" (en retard)" if t["status"] == "expired" else "") for t in v["tasks"]]
        return {"tab": "tasks", "text": "\n".join(lines) or "Aucune tâche.", "week": None}
    if sub == "report":
        r = RP.week_review(db, date.today() - timedelta(days=7))
        return {"tab": "reports", "text": r.text, "week": None}
    # settings
    patch = {}
    for a in args:
        if "=" in a:
            k, val = a.split("=", 1)
            cur = DEFAULTS.get(k)
            if isinstance(cur, bool):
                patch[k] = val.lower() in ("1", "true", "oui", "yes", "on")
            elif isinstance(cur, list):
                patch[k] = [int(x) for x in val.split(",") if x != ""]
            elif isinstance(cur, int):
                patch[k] = int(val)
            else:
                patch[k] = val
    p = update_prefs(db, patch) if patch else get_prefs(db)
    return {"tab": "settings", "text": "\n".join(f"{k} = {v}" for k, v in p.items()), "week": None}
