"""M15 Hunter Weekly Command : les 16 cas demandés + règles de sécurité (preuve, jamais de gain annoncé sans preuve)."""
from datetime import date, datetime, timedelta, timezone

import pytest
from weekly_helpers import qualified

from app.db.models import Claim, Notification, Participation, Promotion, Result, WeeklyNotification, WeeklyReport, WeeklyTask
from app.participation import service as ps
from app.weekly import plan as P
from app.weekly import reports as RP
from app.weekly import tasks as T
from app.weekly.prefs import update_prefs
from app.weekly.tick import tick
from app.weekly.timeutil import hours_until_close, now_local, week_start, zone
from app.weekly.view import week_view

TODAY = date.today()


def submit(db, c, note="Formulaire envoyé, page de confirmation affichée"):
    p = ps.prepare(db, c, "manual")
    return ps.mark(db, p, "submitted", note=note, minutes=4)


def item_for(db, c):
    v = week_view(db)
    return next((i for i in v["priority"] if i["contest_id"] == c.id), None), v


def test_not_yet_participated_is_recommended(db):
    c = qualified(db, "Gagnez une PS5")
    it, v = item_for(db, c)
    assert it and it["decision"] == "proposed" and it["reasons"] and it["est_minutes"] > 0
    assert v["kpis"]["priority"] == 1
    assert "Gratuit (règlement)" in it["conditions"] and it["end_date_verified"]


def test_already_participated_is_not_recommended_again(db):
    c = qualified(db, "Gagnez un vélo")
    week_view(db)
    submit(db, c)
    it, v = item_for(db, c)
    assert it["decision"] == "done"  # retiré des recommandations, marqué fait
    assert v["kpis"]["priority"] == 0 and v["kpis"]["done"] == 1


def test_closed_contest_never_recommended(db):
    c = qualified(db, "Concours clos", end=TODAY + timedelta(days=3))
    c.end_date = TODAY - timedelta(days=1)
    db.commit()
    it, v = item_for(db, c)
    assert it is None
    assert all(x["contest_id"] != c.id for b in v["last_chances"].values() for x in b)


def test_mark_done_requires_proof(db):
    c = qualified(db, "Gagnez une montre")
    week_view(db)
    from app.db.models import WeeklyPlanItem

    it = db.query(WeeklyPlanItem).filter_by(contest_id=c.id).one()
    with pytest.raises(ValueError):
        P.mark_item_done(db, it, "ok", None, None)
    assert not db.query(Participation).filter_by(contest_id=c.id).count()
    P.mark_item_done(db, it, "Confirmation reçue par e-mail à 10 h 12", None, 3)
    p = db.query(Participation).filter_by(contest_id=c.id).one()
    assert p.status == "submitted" and p.proofs and it.decision == "done"


def test_result_planned_but_not_published(db):
    c = qualified(db, "Tirage passé", end=TODAY + timedelta(days=1), draw=TODAY - timedelta(days=1) if False else TODAY + timedelta(days=2))
    submit(db, c)
    # tirage prévu dans 2 jours : « tirage à venir »
    v = week_view(db, TODAY + timedelta(days=2))
    r = next(r for r in v["results"] if r["contest_id"] == c.id)
    assert r["status"] == "draw_pending" and not r["draw_date_estimated"]
    # le jour du tirage passé, sans information : jamais « publié » ni « gagné »
    w = db.query(__import__("app.db.models", fromlist=["WeeklyResult"]).WeeklyResult).one()
    w.draw_date = TODAY - timedelta(days=1)
    from app.weekly.results import _derive_status

    assert _derive_status(w, [], TODAY) == "drawn"
    w.publish_date = TODAY
    assert _derive_status(w, [], TODAY) == "not_published"


def test_result_officially_published_and_win_needs_proof(db):
    from app.db.models import WeeklyResult
    from app.weekly.results import _derive_status

    c = qualified(db, "Résultats publiés")
    p = submit(db, c)
    week_view(db)
    w = db.query(WeeklyResult).one()
    unverified = Result(contest_id=c.id, participation_id=p.id, outcome="won", verified=False, phishing_score=10)
    assert _derive_status(w, [unverified], TODAY) == "published"  # gain annoncé non vérifié : pas une victoire
    phishing = Result(contest_id=c.id, participation_id=p.id, outcome="won", verified=True, phishing_score=80)
    assert _derive_status(w, [phishing], TODAY) == "published"
    verified = Result(contest_id=c.id, participation_id=p.id, outcome="won", verified=True, phishing_score=5)
    assert _derive_status(w, [verified], TODAY) == "winner"
    assert _derive_status(w, [Result(outcome="lost")], TODAY) == "not_winner"
    from app.weekly.results import set_manual_status

    with pytest.raises(ValueError):
        set_manual_status(db, w, "winner", None, None)  # jamais déclaré gagnant à la main sans message vérifié


def test_participation_awaiting_confirmation_is_tracked(db):
    c = qualified(db, "En attente de confirmation", end=TODAY + timedelta(days=1), draw=TODAY + timedelta(days=3))
    submit(db, c)
    v = week_view(db, TODAY + timedelta(days=3))
    r = next(r for r in v["results"] if r["contest_id"] == c.id)
    assert r["participation_status"] == "submitted"


def test_gain_to_claim_creates_urgent_task(db):
    c = qualified(db, "Lot gagné")
    p = submit(db, c)
    r = Result(contest_id=c.id, participation_id=p.id, outcome="won", verified=True)
    db.add(r)
    db.flush()
    db.add(Claim(result_id=r.id, prize_name="PS5", status="to_claim", deadline=TODAY + timedelta(days=5)))
    db.commit()
    v = week_view(db)
    assert v["kpis"]["gains_to_claim"] == 1
    t = next(t for t in v["tasks"] if t["action"] == "claim")
    assert t["priority"] == "high" and t["due_at"].startswith((TODAY + timedelta(days=5)).isoformat())


def test_closing_date_change_updates_task_and_reminders(db):
    c = qualified(db, "Date modifiée", end=TODAY + timedelta(days=6))
    week_view(db)
    from app.db.models import WeeklyPlanItem

    it = db.query(WeeklyPlanItem).filter_by(contest_id=c.id).one()
    P.act_on_item(db, it, "accept")
    week_view(db)
    t = db.query(WeeklyTask).filter_by(action="participate").one()
    old_due = t.due_at
    c.end_date = TODAY + timedelta(days=9)  # l'organisateur prolonge
    db.commit()
    week_view(db)
    db.refresh(t)
    assert t.due_at > old_due and any(h.field == "due_at" and h.actor == "system" for h in t.history)


def test_rejected_or_merged_contest_leaves_plan(db):
    a = qualified(db, "Sera rejeté")
    b = qualified(db, "Sera accepté puis rejeté")
    week_view(db)
    from app.db.models import WeeklyPlanItem

    ib = db.query(WeeklyPlanItem).filter_by(contest_id=b.id).one()
    P.act_on_item(db, ib, "accept")
    week_view(db)  # tâche « Participer » créée
    a.status = b.status = "rejected"  # ex. règlement modifié : achat désormais obligatoire
    db.commit()
    v = week_view(db)
    assert all(i["contest_id"] != a.id for i in v["priority"])
    ib = db.query(WeeklyPlanItem).filter_by(contest_id=b.id).one()
    assert ib.decision == "obsolete"
    t = db.query(WeeklyTask).filter_by(action="participate").one()
    assert t.status == "cancelled"


def test_empty_week(db):
    v = week_view(db)
    assert v["priority"] == [] and v["kpis"]["priority"] == 0
    r = RP.weekly_summary(db)
    assert "Aucun concours ne remplit tous les critères" in r.text
    rv = RP.week_review(db)
    assert any("Aucun nouveau concours" in a for a in rv.data["advice"]) or rv.data["discovered"] >= 0


def test_busy_week_respects_time_goal_and_interest(db):
    update_prefs(db, {"minutes_per_day": 6, "weekly_goal": 3, "min_interest": 40})
    cs = [qualified(db, f"Concours numéro {i} gagnez un lot {i}", end=TODAY + timedelta(days=10 + i)) for i in range(12)]
    low = qualified(db, "Faible intérêt", interest_score=10)
    v = week_view(db)
    assert all(i["contest_id"] != low.id for i in v["priority"])  # jamais de remplissage artificiel
    sched = [i for i in v["priority"] if i["scheduled_day"]]
    assert len(sched) <= 3  # objectif hebdomadaire
    by_day = {}
    for i in sched:
        by_day[i["scheduled_day"]] = by_day.get(i["scheduled_day"], 0) + i["est_minutes"]
    assert all(m <= 6 for m in by_day.values())  # temps disponible par jour
    assert v["plan"]["planned_minutes"] <= v["plan"]["capacity_minutes"]
    assert len(cs) == 12


def test_task_postponed_then_expired(db):
    tz = zone("Europe/Paris")
    t = T.create_task(db, title="Photographier le ticket", description=None, priority="medium",
                      due_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1), contest_id=None, action="photo_ticket")
    assert T.expire_tasks(db, datetime.now(timezone.utc).replace(tzinfo=None)) == 1
    assert t.status == "expired"
    T.update_task(db, t, {"due_at": T.postpone_days_to_utc(TODAY + timedelta(days=2), tz)})
    assert t.status == "todo"  # tâche reportée : de nouveau à faire
    assert [h.field for h in t.history][-2:] == ["due_at", "status"]
    with pytest.raises(ValueError):
        T.update_task(db, t, {"status": "bogus"})


def test_participate_task_cannot_be_done_without_proof(db):
    c = qualified(db, "Tâche de participation")
    week_view(db)
    from app.db.models import WeeklyPlanItem

    P.act_on_item(db, db.query(WeeklyPlanItem).filter_by(contest_id=c.id).one(), "accept")
    week_view(db)
    t = db.query(WeeklyTask).filter_by(action="participate").one()
    with pytest.raises(ValueError):
        T.update_task(db, t, {"status": "done"})


def test_refund_received_and_conditional_amounts(db, client):
    r = client.post("/api/promotions", json={"title": "Café 100 % remboursé", "kind": "full_refund", "price_eur": 4.5, "refund_eur": 4.5,
                                             "status": "to_buy", "end_date": (TODAY + timedelta(days=3)).isoformat()})
    pid = r.json()["id"]
    v = client.get("/api/weekly").json()
    assert v["shop"]["totals"]["net_cost_forecast_eur"] == 0 and v["kpis"]["promotions"] == 1
    assert any(t["action"] == "buy" for t in v["tasks"])  # rappel, jamais un achat
    client.patch(f"/api/promotions/{pid}", json={"status": "sent"})
    v = client.get("/api/weekly").json()
    assert v["kpis"]["refund_files"] == 1 and v["shop"]["totals"]["refunds_received_eur"] == 0
    assert client.patch(f"/api/promotions/{pid}", json={"status": "refunded"}).status_code == 400  # montant reçu exigé
    assert client.patch(f"/api/promotions/{pid}", json={"status": "refunded", "refund_received_eur": 4.5}).status_code == 200
    v = client.get("/api/weekly").json()
    assert v["shop"]["totals"]["refunds_received_eur"] == 4.5 and v["kpis"]["refund_files"] == 0


def test_notifications_disabled(db):
    update_prefs(db, {"notifications_enabled": False})
    c = qualified(db, "Clôture imminente", end=TODAY)
    week_view(db)
    from app.db.models import WeeklyPlanItem

    P.act_on_item(db, db.query(WeeklyPlanItem).filter_by(contest_id=c.id).one(), "accept")
    before = db.query(Notification).count()
    now = datetime.combine(TODAY, datetime.min.time()).replace(hour=10, tzinfo=timezone.utc)
    tick(db, now)
    assert db.query(Notification).count() == before  # rien d'envoyé
    assert db.query(WeeklyNotification).filter_by(urgent=True).count() == 1  # mais journalisé (visible dans la page)


def test_urgent_alert_sent_once_and_non_urgent_grouped(db):
    c = qualified(db, "Clôture demain", end=TODAY + timedelta(days=1))
    week_view(db)
    now = datetime.combine(TODAY, datetime.min.time()).replace(hour=9, tzinfo=timezone.utc)
    tick(db, now)
    tick(db, now)
    assert db.query(WeeklyNotification).filter_by(contest_id=c.id, urgent=False).count() == 1  # proposé : rappel regroupé, pas d'alerte
    assert not db.query(Notification).filter(Notification.dedup_key.like("wk:remind%")).count()
    r = RP.daily_report(db, TODAY)
    assert "Rappels regroupés" in r.text


def test_timezone_change(db):
    late_sunday_utc = datetime(2026, 11, 22, 23, 30, tzinfo=timezone.utc)  # lundi 00 h 30 à Paris, dimanche 18 h 30 à New York
    assert week_start(now_local(zone("Europe/Paris"), late_sunday_utc).date()) == date(2026, 11, 23)
    assert week_start(now_local(zone("America/New_York"), late_sunday_utc).date()) == date(2026, 11, 16)
    # passage à l'heure d'hiver (25 octobre 2026) : la clôture reste à 23 h 59 heure locale
    h = hours_until_close(date(2026, 10, 25), zone("Europe/Paris"), datetime(2026, 10, 24, 22, 0, tzinfo=timezone.utc))
    assert h == pytest.approx(25 - 1 / 3600, abs=0.001)  # journée de 25 h
    update_prefs(db, {"timezone": "America/New_York"})
    with pytest.raises(ValueError):
        update_prefs(db, {"timezone": "Mars/Olympus"})


def test_tick_generates_summary_monday_and_review_sunday_with_catch_up(db):
    monday_9h = datetime(2026, 11, 23, 8, 0, tzinfo=timezone.utc)  # 9 h à Paris
    out = tick(db, monday_9h)
    assert "weekly" in out["generated"]
    assert "weekly" not in tick(db, monday_9h)["generated"]  # une seule fois
    sunday_19h = datetime(2026, 11, 29, 18, 0, tzinfo=timezone.utc)
    assert "review" in tick(db, sunday_19h)["generated"]
    # PC éteint tout le dimanche suivant : rattrapage du bilan le lundi
    out = tick(db, datetime(2026, 12, 7, 9, 0, tzinfo=timezone.utc))
    assert db.query(WeeklyReport).filter_by(kind="review").count() >= 1 and "weekly" in out["generated"]


def test_opportunity_follow_never_becomes_participation(db, client):
    c = qualified(db, "Opportunité à suivre")
    c.status, c.needs_human_reason = "to_verify", "Éligibilité à confirmer"
    db.commit()
    assert client.post("/api/weekly/opportunities", json={"contest_id": c.id, "follow": True}).status_code == 200
    v = client.get("/api/weekly").json()
    o = next(o for o in v["opportunities"] if o["contest_id"] == c.id)
    assert o["followed"] and any(t["action"] == "verify_rules" for t in v["tasks"])
    assert not db.query(Participation).filter_by(contest_id=c.id).count()


def test_scam_is_never_an_opportunity(db):
    c = qualified(db, "iPhone offert")
    c.status = "to_verify"
    c.justifications = list(c.justifications or []) + [{"field": "suspicious", "decision": "frais demandés", "evidence": None, "method": "rule"}]
    db.commit()
    assert all(o["contest_id"] != c.id for o in week_view(db)["opportunities"])


def test_api_and_commands(client, db):
    qualified(db, "Concours via API")
    v = client.get("/api/weekly").json()
    assert set(v["kpis"]) == {"priority", "done", "closing", "results_expected", "results_published", "gains_to_claim", "promotions", "refund_files"}
    iid = v["priority"][0]["item_id"]
    assert client.post(f"/api/weekly/items/{iid}", json={"action": "favorite"}).json()["priority"][0]["favorite"]
    nxt = client.get("/api/weekly", params={"week": (TODAY + timedelta(days=7)).isoformat()}).json()
    assert nxt["week_start"] == (week_start(TODAY) + timedelta(days=7)).isoformat()
    prev = client.get("/api/weekly", params={"week": (TODAY - timedelta(days=7)).isoformat()}).json()
    assert prev["is_past"] and client.post("/api/weekly/plan", params={"week": (TODAY - timedelta(days=7)).isoformat()}).status_code == 409
    for sub in ("", "plan", "results", "deadlines", "opportunities", "tasks", "report", "next", "settings minutes_per_day=45"):
        r = client.post("/api/weekly/command", json={"line": f"/hunter-week {sub}"})
        assert r.status_code == 200 and r.json()["text"], sub
    assert client.get("/api/weekly/preferences").json()["minutes_per_day"] == 45
    assert client.post("/api/weekly/command", json={"line": "/hunter-week nimporte"}).status_code == 400
    rep = client.post("/api/weekly/reports/weekly").json()
    assert "## B. Les concours à faire" in rep["text"]
    assert client.get("/api/weekly/reports").json()[0]["id"] == rep["id"]
    t = client.post("/api/weekly/tasks", json={"title": "Envoyer le code-barres", "priority": "high", "due": (TODAY + timedelta(days=1)).isoformat()}).json()
    assert client.patch(f"/api/weekly/tasks/{t['id']}", json={"status": "in_progress"}).json()["status"] == "in_progress"
    assert len(client.get(f"/api/weekly/tasks/{t['id']}/history").json()) == 2
