"""Sélection et planification : participations prioritaires, dernières chances, opportunités.

Calculs déterministes (SQL + règles). Le score sert à classer, ce n'est jamais une probabilité de gain.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..db.models import Contest, Participation, WeeklyPlan, WeeklyPlanItem, utcnow
from ..intelligence.scoring import estimated_minutes
from ..participation import service as ps
from .timeutil import hours_until_close, week_days

DONE_STATUSES = ("submitted", "confirmed")
OPEN_STATUSES = ("new", "qualified", "to_verify", "participated")


# ------------------------------------------------------------------ faits sur un concours
def period_of(c: Contest) -> str:
    return (c.policy.period if c.policy else None) or "once"


def participated_this_period(c: Contest, today: date) -> Participation | None:
    """Lu en base (et non via la relation chargée, qui peut être périmée dans la session)."""
    from sqlalchemy.orm import object_session

    key = ps.period_key(period_of(c), today)
    db = object_session(c)
    if db is None:
        return next((p for p in c.participations if p.status in DONE_STATUSES and p.period_key == key), None)
    return db.scalars(select(Participation).where(Participation.contest_id == c.id, Participation.period_key == key,
                                                  Participation.status.in_(DONE_STATUSES))).first()


def has_official_rules(c: Contest) -> bool:
    return any(r.origin in ("fetched", "user") for r in c.rules)


def end_date_verified(c: Contest) -> bool:
    return has_official_rules(c) and any(j.get("field") == "dates" and j.get("method") in ("rule", "human") for j in (c.justifications or []))


def conditions(c: Contest) -> list[str]:
    out = []
    out.append({"free": "Gratuit (règlement)", "free_alternative": "Gratuit par voie alternative"}.get(c.free_status, "Gratuité non établie"))
    out.append("Éligible depuis la France" if c.fr_eligible == "yes" else "Éligibilité France non établie")
    if c.eligibility and c.eligibility.min_age:
        out.append(f"{c.eligibility.min_age} ans minimum")
    if c.entry_limit:
        out.append("Limite : " + c.entry_limit[:120])
    elif period_of(c) != "once":
        out.append({"daily": "Une participation par jour", "weekly": "Une participation par semaine", "monthly": "Une participation par mois"}.get(period_of(c), ""))
    flags = c.flags or []
    if "captcha" in flags:
        out.append("CAPTCHA à résoudre vous-même")
    if "login_required" in flags:
        out.append("Compte requis sur le site")
    if "social_entry" in flags:
        out.append("Participation via un réseau social")
    if not end_date_verified(c):
        out.append("Date de clôture à confirmer sur le site officiel")
    return [x for x in out if x]


def brief(c: Contest, tz, today: date, now_utc: datetime | None = None) -> dict:
    flags = c.flags or []
    return {
        "contest_id": c.id, "title": c.title, "url": c.url, "organizer": c.organizer.name if c.organizer else None,
        "prize": c.prize_summary, "value_eur": c.total_prize_value_eur, "end_date": c.end_date.isoformat() if c.end_date else None,
        "end_date_verified": end_date_verified(c), "start_date": c.start_date.isoformat() if c.start_date else None,
        "days_left": (c.end_date - today).days if c.end_date else None,
        "hours_left": round(hours_until_close(c.end_date, tz, now_utc), 1) if c.end_date else None,
        "est_minutes": estimated_minutes(c.entry_method, flags), "status": c.status, "game_type": c.game_type,
        "reliability": c.reliability_score, "interest": c.interest_score, "conditions": conditions(c),
        "participated_this_period": participated_this_period(c, today) is not None, "period": period_of(c),
    }


# ------------------------------------------------------------------ participations prioritaires
def priority_candidates(db: Session, prefs: dict, today: date, favorites: set[int]) -> list[tuple[Contest, float, list[str]]]:
    stmt = select(Contest).where(Contest.merged_into_id.is_(None), Contest.status.in_(("qualified", "participated")),
                                 Contest.free_status.in_(("free", "free_alternative")), Contest.fr_eligible == "yes",
                                 Contest.end_date >= today)
    out = []
    for c in db.scalars(stmt):
        if (c.reliability_score or 0) < prefs["min_reliability"] or (c.interest_score or 0) < prefs["min_interest"]:
            continue
        if not has_official_rules(c) or participated_this_period(c, today):
            continue
        score, reasons = score_contest(c, today, c.id in favorites)
        out.append((c, score, reasons))
    out.sort(key=lambda x: (-x[1], x[0].end_date or date.max, x[0].id))
    return out


def score_contest(c: Contest, today: date, favorite: bool) -> tuple[float, list[str]]:
    interest, rel = c.interest_score or 0, c.reliability_score or 0
    flags = c.flags or []
    est = estimated_minutes(c.entry_method, flags)
    reasons = [f"Intérêt {interest}/100 (lot, valeur, catégorie)", f"Fiabilité {rel}/100"]
    s = 0.5 * interest + 0.25 * rel
    if c.total_prize_value_eur:
        reasons.append(f"Valeur estimée {c.total_prize_value_eur:.0f} €")
    days = (c.end_date - today).days if c.end_date else None
    if days is not None:
        u = 15 if days <= 2 else 10 if days <= 6 else 5 if days <= 13 else 0
        if u:
            s += u
            reasons.append(f"Clôture dans {days} j")
    if c.personal_interest:
        s += 1.5 * c.personal_interest
        reasons.append(f"Votre intérêt personnel : {c.personal_interest}/10")
    if favorite:
        s += 8
        reasons.append("Dans vos favoris")
    pen = min(10, max(0, est - 5))
    if pen:
        s -= pen
        reasons.append(f"Temps estimé {est} min")
    cx = (3 if "captcha" in flags else 0) + (4 if "login_required" in flags else 0)
    if cx:
        s -= cx
        reasons.append("Participation plus complexe (CAPTCHA ou compte)")
    if period_of(c) in ("daily", "weekly"):
        reasons.append("Participation renouvelable : " + ("chaque jour" if period_of(c) == "daily" else "chaque semaine"))
    return round(s, 1), reasons


def priority_level(score: float) -> str:
    return "high" if score >= 65 else "medium" if score >= 45 else "low"


def schedule(items: list[WeeklyPlanItem], prefs: dict, ws: date, today: date) -> tuple[int, int]:
    """Répartit les recommandations sur les jours restants sans dépasser le temps disponible ni l'objectif.

    1) sélection par score décroissant tant que le temps total et l'objectif le permettent ;
    2) placement par échéance croissante, au jour le plus tôt qui a encore du temps.
    Retourne (capacité, minutes planifiées). Les éléments non placés restent « si vous avez du temps ».
    """
    days = [d for d in week_days(ws) if d >= today and d.weekday() in prefs["active_days"]]
    left = {d: prefs["minutes_per_day"] for d in days}
    capacity = sum(left.values())
    for it in items:
        it.scheduled_day = None
    goal = prefs["weekly_goal"] or 10**6
    chosen, used = [], 0
    for it in sorted(items, key=lambda i: (i.decision != "accepted", -i.score)):
        if len(chosen) >= goal or used + it.est_minutes > capacity:
            continue
        chosen.append(it)
        used += it.est_minutes
    planned = 0
    for it in sorted(chosen, key=lambda i: (i.contest.end_date or date.max, -i.score)):
        last = min(it.contest.end_date or ws + timedelta(days=6), ws + timedelta(days=6))
        for d in days:
            if d <= last and left[d] >= it.est_minutes:
                it.scheduled_day = d
                left[d] -= it.est_minutes
                planned += it.est_minutes
                break
    return capacity, planned


def _carried_decisions(db: Session, ws: date) -> dict[int, WeeklyPlanItem]:
    """Dernière décision connue par concours (semaines précédentes)."""
    rows = db.scalars(select(WeeklyPlanItem).join(WeeklyPlan).where(WeeklyPlan.week_start < ws, WeeklyPlanItem.section == "priority")
                      .order_by(WeeklyPlan.week_start.asc(), WeeklyPlanItem.id.asc()))
    return {r.contest_id: r for r in rows}


def favorites(db: Session) -> set[int]:
    return set(db.scalars(select(WeeklyPlanItem.contest_id).where(WeeklyPlanItem.favorite.is_(True))))


def get_plan(db: Session, ws: date) -> WeeklyPlan | None:
    return db.scalars(select(WeeklyPlan).where(WeeklyPlan.week_start == ws)).first()


def generate_plan(db: Session, ws: date, prefs: dict, today: date) -> WeeklyPlan:
    """Crée ou actualise le programme de la semaine ws. Les semaines passées ne sont jamais recalculées."""
    plan = get_plan(db, ws)
    if plan and ws + timedelta(days=6) < today:
        return plan
    if plan is None:
        plan = WeeklyPlan(week_start=ws)
        db.add(plan)
        db.flush()
    ref_day = max(today, ws)
    favs = favorites(db)
    carried = _carried_decisions(db, ws)
    existing = {(i.contest_id, i.section): i for i in plan.items}
    seen = set()
    for rank, (c, score, reasons) in enumerate(priority_candidates(db, prefs, ref_day, favs)):
        prev = carried.get(c.id)
        it = existing.get((c.id, "priority"))
        if it is None:
            if prev and prev.decision == "refused":
                continue
            if prev and prev.decision == "postponed" and prev.postponed_to and prev.postponed_to > ws + timedelta(days=6):
                continue
            it = WeeklyPlanItem(plan=plan, contest=c, section="priority", favorite=c.id in favs)
            db.add(it)
        if it.decision == "postponed" and it.postponed_to and it.postponed_to <= ws + timedelta(days=6):
            pass  # reporté à un jour de cette même semaine : reste reporté jusqu'à ce jour
        it.rank, it.score, it.reasons, it.priority = rank, score, reasons, priority_level(score)
        it.est_minutes = estimated_minutes(c.entry_method, c.flags or [])
        seen.add(it.contest_id)
    for it in list(plan.items):
        if it.section != "priority" or it.contest_id in seen:
            continue
        p = participated_this_period(it.contest, ref_day)
        if p and it.decision != "done":
            it.decision, it.participation_id = "done", p.id
        elif it.decision in ("proposed", "postponed"):
            plan.items.remove(it)  # n'est plus recommandable (clôturé, rejeté, déjà fait...)
        elif it.decision == "accepted":
            it.decision = "obsolete"
            it.reasons = list(it.reasons or []) + [f"Retiré : concours {it.contest.status}"]
    db.flush()
    active = [i for i in plan.items if i.section == "priority" and (i.decision == "accepted" or
              (i.decision == "proposed") or (i.decision == "postponed" and i.postponed_to and i.postponed_to <= ref_day))]
    plan.capacity_minutes, plan.planned_minutes = schedule(active, prefs, ws, ref_day) if ws + timedelta(days=6) >= today else (0, 0)
    plan.generated_at = utcnow()
    db.commit()
    return plan


ITEM_ACTIONS = ("accept", "refuse", "postpone", "favorite", "unfavorite", "reset")


def act_on_item(db: Session, it: WeeklyPlanItem, action: str, postpone_to: date | None = None) -> WeeklyPlanItem:
    if action not in ITEM_ACTIONS:
        raise ValueError("Action inconnue")
    if it.decision == "done" and action in ("accept", "refuse", "postpone"):
        raise ValueError("Participation déjà enregistrée pour ce concours")
    if action == "accept":
        it.decision = "accepted"
    elif action == "refuse":
        it.decision = "refused"
    elif action == "postpone":
        if not postpone_to:
            raise ValueError("Date de report requise")
        if it.contest.end_date and postpone_to > it.contest.end_date:
            raise ValueError("Report impossible après la clôture du concours")
        it.decision, it.postponed_to = "postponed", postpone_to
    elif action == "favorite":
        it.favorite = True
    elif action == "unfavorite":
        for other in db.scalars(select(WeeklyPlanItem).where(WeeklyPlanItem.contest_id == it.contest_id)):
            other.favorite = False
    elif action == "reset":
        it.decision, it.postponed_to = "proposed", None
    audit(db, "user", "weekly_item", item_id=it.id, op=action)
    db.commit()
    return it


def mark_item_done(db: Session, it: WeeklyPlanItem, proof_note: str | None, data_url: str | None, minutes: float | None) -> WeeklyPlanItem:
    """« Déjà effectuée » : jamais sans preuve de soumission (note détaillée ou capture)."""
    note = (proof_note or "").strip()
    if len(note) < 10 and not data_url:
        raise ValueError("Preuve requise : décrivez la soumission (confirmation, e-mail reçu...) ou joignez une capture")
    c = it.contest
    existing = participated_this_period(c, date.today())
    if existing:
        p = existing
    else:
        db.expire(c, ["participations"])
        p = next((x for x in c.participations if x.status in ("prepared", "awaiting_human") and x.period_key == ps.period_key(period_of(c))), None)
        if p is None:
            p = ps.prepare(db, c, "manual")
        p = ps.mark(db, p, "submitted", note=note or "Capture de confirmation jointe", minutes=minutes)
    if data_url:
        ps.add_proof(db, p, "screenshot", data_url, note or None)
    it.decision, it.participation_id = "done", p.id
    audit(db, "user", "weekly_item_done", item_id=it.id, participation_id=p.id)
    db.commit()
    return it


# ------------------------------------------------------------------ dernières chances
BUCKETS = (("h24", 24), ("h48", 48), ("d7", 168), ("d14", 336))


def last_chances(db: Session, tz, today: date, now_utc: datetime | None = None, limit: int = 30) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {k: [] for k, _ in BUCKETS}
    stmt = select(Contest).where(Contest.merged_into_id.is_(None), Contest.status.in_(OPEN_STATUSES),
                                 Contest.free_status != "purchase_required", Contest.fr_eligible != "no",
                                 Contest.end_date >= today, Contest.end_date <= today + timedelta(days=14))
    rows = []
    for c in db.scalars(stmt):
        h = hours_until_close(c.end_date, tz, now_utc)
        if h <= 0 or participated_this_period(c, today):
            continue
        rows.append((c, h))
    rows.sort(key=lambda x: (x[0].status != "qualified", -(x[0].interest_score or 0), estimated_minutes(x[0].entry_method, x[0].flags or [])))
    for c, h in rows:
        for key, limit_h in BUCKETS:
            if h < limit_h:
                if len(out[key]) < limit:
                    out[key].append(brief(c, tz, today, now_utc))
                break
    return out


# ------------------------------------------------------------------ opportunités à surveiller
def followed(db: Session) -> set[int]:
    return set(db.scalars(select(WeeklyPlanItem.contest_id).where(WeeklyPlanItem.section == "opportunity", WeeklyPlanItem.favorite.is_(True))))


def dismissed_opportunities(db: Session) -> set[int]:
    return set(db.scalars(select(WeeklyPlanItem.contest_id).where(WeeklyPlanItem.section == "opportunity", WeeklyPlanItem.decision == "refused")))


def opportunities(db: Session, prefs: dict, tz, today: date, now_utc: datetime | None = None, limit: int = 60) -> list[dict]:
    """Concours intéressants sans décision de participation. Jamais transformés automatiquement en participation."""
    fol, dis = followed(db), dismissed_opportunities(db)
    out = []
    stmt = select(Contest).where(Contest.merged_into_id.is_(None), Contest.status.in_(("to_verify", "new", "qualified", "rejected")),
                                 (Contest.end_date.is_(None)) | (Contest.end_date >= today))
    for c in db.scalars(stmt):
        if c.id in dis and c.id not in fol:
            continue
        if any(j.get("field") == "suspicious" for j in (c.justifications or [])) and c.id not in fol:
            continue  # signaux d'arnaque : jamais proposé comme opportunité
        why = []
        interesting = (c.interest_score or 0) >= prefs["min_interest"]
        if c.id in fol:
            why.append("Vous suivez ce concours")
        if c.start_date and c.start_date > today and (c.start_date - today).days <= 21 and c.status != "rejected":
            why.append(f"Ouvre le {c.start_date:%d/%m}")
        if c.status == "to_verify" and interesting:
            why.append("À vérifier : " + (c.needs_human_reason or "règlement à approfondir")[:200])
        if c.status == "rejected" and c.free_status == "purchase_required" and (c.interest_score or 0) >= prefs["min_interest"] + 10:
            why.append("Achat obligatoire : coût à évaluer avant toute décision")
        if c.status in ("new", "qualified") and c.fr_eligible == "unknown" and interesting:
            why.append("Éligibilité depuis la France encore incertaine")
        if c.status == "qualified" and (c.reliability_score or 0) < prefs["min_reliability"] and interesting:
            why.append(f"Lot intéressant mais fiabilité {c.reliability_score}/100 : à examiner")
        if (c.total_prize_value_eur or 0) >= 1000 and c.status != "rejected" and not why:
            why.append(f"Lot de valeur ({c.total_prize_value_eur:.0f} €)")
        if not why:
            continue
        b = brief(c, tz, today, now_utc)
        b.update({"why": why, "followed": c.id in fol})
        out.append(b)
    out.sort(key=lambda b: (not b["followed"], -(b["interest"] or 0)))
    return out[:limit]


def set_follow(db: Session, plan: WeeklyPlan, contest: Contest, follow: bool | None, dismiss: bool = False) -> None:
    it = db.scalars(select(WeeklyPlanItem).where(WeeklyPlanItem.plan_id == plan.id, WeeklyPlanItem.contest_id == contest.id,
                                                 WeeklyPlanItem.section == "opportunity")).first()
    if it is None:
        it = WeeklyPlanItem(plan=plan, contest=contest, section="opportunity", decision="proposed")
        db.add(it)
    if follow is not None:
        for other in db.scalars(select(WeeklyPlanItem).where(WeeklyPlanItem.contest_id == contest.id, WeeklyPlanItem.section == "opportunity")):
            other.favorite = follow
        it.favorite = follow
    if dismiss:
        it.decision, it.favorite = "refused", False
    audit(db, "user", "weekly_follow", contest_id=contest.id, follow=follow, dismiss=dismiss)
    db.commit()
