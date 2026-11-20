"""Synthèses : programme du lundi, bilan quotidien facultatif, bilan du dimanche. Texte déterministe, historisé."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Claim, Contest, ContestSighting, Participation, Result, WeeklyNotification, WeeklyPlan, WeeklyReport, utcnow
from . import plan as P
from .timeutil import iso_week_label
from .view import context, week_bounds_utc, week_view

PRIO = {"high": "haute", "medium": "moyenne", "low": "basse"}
RES = {"draw_pending": "tirage à venir", "drawn": "tirage effectué (résultats non publiés)", "not_published": "résultats non publiés",
       "published": "résultats publiés", "winner": "gagnant identifié", "not_winner": "non gagnant confirmé", "unverifiable": "impossible à vérifier"}


def _d(s: str | None) -> str:
    return datetime.fromisoformat(s).strftime("%d/%m") if s else "date inconnue"


def _store(db: Session, kind: str, start: date, end: date, data: dict, text: str) -> WeeklyReport:
    r = db.scalars(select(WeeklyReport).where(WeeklyReport.kind == kind, WeeklyReport.period_start == start)).first()
    if r is None:
        r = WeeklyReport(kind=kind, period_start=start, period_end=end)
        db.add(r)
    r.data, r.text, r.generated_at = data, text, utcnow()
    db.commit()
    return r


def weekly_summary(db: Session, any_day: date | None = None, now_utc: datetime | None = None) -> WeeklyReport:
    v = week_view(db, any_day, now_utc)
    k = v["kpis"]
    todo = [i for i in v["priority"] if i["decision"] in ("proposed", "accepted")]
    L = [f"# Programme de la semaine {v['label']} (du {_d(v['week_start'])} au {_d(v['week_end'])})", "",
         "## A. Le programme de la semaine",
         f"{k['priority']} participations recommandées, {len(v['opportunities'])} opportunités à surveiller, "
         f"{k['closing']} concours qui ferment cette semaine, {k['results_expected']} résultats attendus.", "",
         "## B. Les concours à faire"]
    if todo:
        for i in todo[:25]:
            day = f"le {_d(i['scheduled_day'])}" if i["scheduled_day"] else "si vous avez du temps"
            L.append(f"- [{PRIO[i['priority']]}] {i['title']} — avant le {_d(i['end_date'])}, ~{i['est_minutes']} min, {day} — {i['url']}")
    else:
        L.append("Aucun concours ne remplit tous les critères cette semaine (gratuit, éligible, règlement accessible, organisateur fiable).")
    L += ["", "## C. Les résultats à surveiller"]
    L += [f"- {r['title']} — tirage {_d(r['draw_date'])}{' (estimé)' if r['draw_date_estimated'] else ''} — {RES[r['status']]}" for r in v["results"]] or ["Aucun résultat attendu."]
    L += ["", "## D. Les dernières chances"]
    lc = v["last_chances"]
    for key, label in (("h24", "moins de 24 h"), ("h48", "moins de 48 h"), ("d7", "moins de 7 jours")):
        for c in lc[key][:8]:
            L.append(f"- ({label}) {c['title']} — {c['url']}")
    if not any(lc[k_] for k_ in ("h24", "h48", "d7")):
        L.append("Aucun concours ne ferme dans les 7 jours.")
    sh = v["shop"]
    t = sh["totals"]
    L += ["", "## E. Shop & Promo",
          f"{len(sh['categories']['to_send'])} dossiers à envoyer, {len(sh['categories']['awaiting_refund'])} remboursements attendus "
          f"({t['refunds_awaiting_eur']:.2f} €, conditionnels), {t['refunds_received_eur']:.2f} € réellement reçus.",
          f"Achats envisagés : {t['planned_spend_eur']:.2f} €, coût net prévisionnel {t['net_cost_forecast_eur']:.2f} € si toutes les conditions sont remplies."]
    claims = db.scalars(select(Claim).where(Claim.status.in_(("to_claim", "claimed")))).all()
    L += ["", "## F. Les gains"]
    L += [f"- {c.prize_name or 'lot'} : {'à réclamer' + (f' avant le {c.deadline:%d/%m}' if c.deadline else '') if c.status == 'to_claim' else 'réclamé, à recevoir'}" for c in claims] or ["Aucun gain en cours."]
    p = v["plan"]
    L += ["", "## G. Objectifs de la semaine",
          f"Objectif : {p['weekly_goal']} participations. Temps disponible : {p['capacity_minutes']} min ({p['minutes_per_day']} min par jour actif). "
          f"Temps planifié : {p['planned_minutes']} min.",
          "Les lots sont des possibilités, jamais des gains probables."]
    data = {"view": v}
    return _store(db, "weekly", date.fromisoformat(v["week_start"]), date.fromisoformat(v["week_end"]), data, "\n".join(L))


def daily_report(db: Session, day: date | None = None, now_utc: datetime | None = None) -> WeeklyReport:
    ctx = context(db, day, now_utc)
    d = day or ctx["today"]
    v = week_view(db, d, now_utc)
    tasks_today = [t for t in v["tasks"] if t["due_at"] and t["due_at"][:10] == d.isoformat() and t["status"] != "expired"]
    late = [t for t in v["tasks"] if t["status"] == "expired"]
    actions = [i for i in v["priority"] if i["scheduled_day"] == d.isoformat() and i["decision"] in ("proposed", "accepted")]
    since = datetime.combine(d - timedelta(days=1), datetime.min.time())
    new_contests = db.scalar(select(func.count()).select_from(Contest).where(Contest.created_at >= since)) or 0
    published = [r for r in v["results"] if r["status"] in ("published", "winner", "not_winner")]
    pending = db.scalars(select(WeeklyNotification).where(WeeklyNotification.urgent.is_(False), WeeklyNotification.digested_in.is_(None))).all()
    L = [f"# Bilan du {d:%d/%m/%Y}", "", "## Actions du jour"]
    L += [f"- Participer : {i['title']} (~{i['est_minutes']} min)" for i in actions] + [f"- {t['title']}" for t in tasks_today] or ["Rien de prévu aujourd'hui."]
    L += ["", "## Concours qui ferment"] + ([f"- {c['title']}" for c in v["last_chances"]["h24"] + v["last_chances"]["h48"]] or ["Aucun dans les 48 h."])
    L += ["", "## Résultats publiés"] + ([f"- {r['title']} : {RES[r['status']]}" for r in published] or ["Aucun nouveau résultat."])
    L += ["", f"## Nouvelles opportunités\n{new_contests} concours découverts depuis hier."]
    sh = v["shop"]["categories"]
    L += ["", f"## Dossiers de remboursement\n{len(sh['to_send'])} à envoyer, {len(sh['awaiting_refund'])} en attente."]
    L += ["", "## Tâches en retard"] + ([f"- {t['title']}" for t in late] or ["Aucune."])
    if pending:
        L += ["", "## Rappels regroupés"] + [f"- {n.title}" for n in pending]
    r = _store(db, "daily", d, d, {"actions": actions, "tasks_today": tasks_today, "late": late, "published": published}, "\n".join(L))
    for n in pending:
        n.digested_in = r.id
    db.commit()
    return r


def week_review(db: Session, any_day: date | None = None, now_utc: datetime | None = None) -> WeeklyReport:
    """Bilan de fin de semaine. Les valeurs de lots ne sont jamais comptées comme des gains."""
    ctx = context(db, any_day, now_utc)
    ws, we, tz = ctx["ws"], ctx["we"], ctx["tz"]
    a, b = week_bounds_utc(ws, tz)
    discovered = db.scalars(select(Contest).where(Contest.created_at >= a, Contest.created_at < b)).all()
    plan = db.scalars(select(WeeklyPlan).where(WeeklyPlan.week_start == ws)).first()
    items = [i for i in (plan.items if plan else []) if i.section == "priority"]
    selected = [i for i in items if i.decision in ("accepted", "done")]
    parts = db.scalars(select(Participation).where(Participation.status.in_(("submitted", "confirmed")), Participation.submitted_at >= a,
                                                   Participation.submitted_at < b)).all()
    missed = [i for i in items if i.decision == "accepted" and i.contest.end_date and i.contest.end_date <= we
              and not P.participated_this_period(i.contest, i.contest.end_date)]
    results = db.scalars(select(Result).where(Result.received_at >= a, Result.received_at < b)).all()
    wins = [r for r in results if r.outcome == "won" and r.verified]
    claims_pending = db.scalars(select(Claim).where(Claim.status.in_(("to_claim", "claimed")))).all()
    received_value = sum(c.value_eur or 0 for c in db.scalars(select(Claim).where(Claim.status == "received", Claim.updated_at >= a, Claim.updated_at < b)))
    minutes = sum(p.time_spent_minutes or 0 for p in parts)
    src = Counter()
    for s in db.scalars(select(ContestSighting).where(ContestSighting.contest_id.in_([c.id for c in discovered] or [-1]))):
        src[s.source.name if s.source else "ajout manuel"] += 1
    sel_src = Counter()
    for i in selected:
        for s in i.contest.sightings:
            sel_src[s.source.name if s.source else "ajout manuel"] += 1
    from ..db.models import Promotion

    promos = db.scalars(select(Promotion)).all()
    asked = [p for p in promos if p.sent_date and ws <= p.sent_date <= we]
    got = [p for p in promos if p.status == "refunded" and p.received_date and ws <= p.received_date <= we]
    goal = ctx["prefs"]["weekly_goal"]
    advice = []
    if goal and len(parts) < goal:
        advice.append(f"{len(parts)} participations pour un objectif de {goal} : " +
                      ("trop peu de concours éligibles, suivez plus de sites dans Sources." if len(items) < goal else
                       "le temps a manqué : réduisez l'objectif ou augmentez le temps par jour."))
    if missed:
        advice.append(f"{len(missed)} concours acceptés n'ont pas été joués avant leur clôture : acceptez-en moins, ou plus tôt dans la semaine.")
    if not discovered:
        advice.append("Aucun nouveau concours cette semaine : vérifiez que les sources sont activées et que le planificateur tourne.")
    if not advice:
        advice.append("Objectifs tenus. Gardez le même rythme.")
    data = {"discovered": len(discovered), "selected": len(selected), "participations": len(parts), "missed": len(missed),
            "results": len(results), "wins_verified": len(wins), "claims_pending": len(claims_pending),
            "received_prize_value_eur": round(received_value, 2), "refunds_requested": len(asked),
            "refunds_received_eur": round(sum(p.refund_received_eur or 0 for p in got), 2), "minutes": round(minutes),
            "top_sources_discovered": src.most_common(5), "top_sources_selected": sel_src.most_common(5), "goal": goal, "advice": advice}
    L = [f"# Bilan de la semaine {iso_week_label(ws)} (du {ws:%d/%m} au {we:%d/%m})", "",
         f"- Concours découverts : {data['discovered']}", f"- Concours sélectionnés : {data['selected']}",
         f"- Participations réalisées : {data['participations']} (objectif {goal})", f"- Participations manquées : {data['missed']}",
         f"- Résultats reçus : {data['results']}, dont gains vérifiés : {data['wins_verified']}",
         f"- Gains en attente (à réclamer ou à recevoir) : {data['claims_pending']}",
         f"- Lots effectivement reçus cette semaine : {data['received_prize_value_eur']:.2f} € (valeur déclarée)",
         f"- Remboursements demandés : {data['refunds_requested']}, reçus : {data['refunds_received_eur']:.2f} €",
         f"- Temps consacré : {data['minutes']} min",
         "- Sources les plus productives : " + (", ".join(f"{n} ({c})" for n, c in data["top_sources_discovered"]) or "aucune"),
         "", "## Écarts et pistes pour la semaine prochaine"] + [f"- {x}" for x in advice] + [
         "", "Les valeurs des lots joués ne sont pas des gains : seuls les lots reçus comptent."]
    return _store(db, "review", ws, we, data, "\n".join(L))


def list_reports(db: Session, kind: str | None = None, limit: int = 60) -> list[WeeklyReport]:
    q = select(WeeklyReport).order_by(WeeklyReport.period_start.desc(), WeeklyReport.id.desc()).limit(limit)
    if kind:
        q = q.where(WeeklyReport.kind == kind)
    return list(db.scalars(q))

