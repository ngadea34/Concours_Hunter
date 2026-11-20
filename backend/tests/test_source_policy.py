"""Politique de sources : catégories, consultation assistée, import, indice A1 à A8, filtres, contrôle qualité, isolation."""
from datetime import date, timedelta

from weekly_helpers import qualified

from app.db.models import Contest, Source
from app.discovery import policy as P
from app.intelligence.automatability import classify
from app.weekly import plan as PL
from app.weekly.prefs import update_prefs
from app.weekly.view import week_view

BASE = dict(url="https://marque.test/jeu", text="", game_type=None, entry_method=None, flags=[], free_status="free",
            fr_eligible="yes", has_rules=True)


def cls(**kw):
    return classify(**{**BASE, **kw})["class"]


def test_automatability_classes():
    assert cls() == "A1"
    assert cls(game_type="instant_win") == "A1"
    assert cls(game_type="quiz") == "A2"
    assert cls(has_answers=True) == "A2"
    assert cls(text="Pour participer, envoyez un e-mail à jeu@marque.test avec vos coordonnées") == "A3"
    assert cls(game_type="social", url="https://www.instagram.com/p/abc") == "A4"
    assert classify(**{**BASE, "game_type": "social", "text": "Abonne-toi et commente sur Instagram"})["platform"] == "instagram"
    assert cls(game_type="creative") == "A5"
    assert cls(flags=["captcha"]) == "A6"
    assert cls(entry_method="mail") == "A6"
    assert cls(free_status="purchase_required") == "A7"
    assert cls(fr_eligible="no") == "A8"
    assert cls(flags=["page_inaccessible"], has_rules=False) == "A8"


def test_difficulty_index():
    easy = classify(**BASE)
    hard = classify(**{**BASE, "game_type": "creative", "flags": ["login_required"]})
    assert easy["difficulty"] == 1 and easy["difficulty_label"] == "très facile"
    assert hard["difficulty"] == 5


def test_qualify_sets_class_and_catalog_filter(db, client):
    a1 = qualified(db, "Gagnez un vélo")
    assert a1.automation_class == "A1" and a1.difficulty == 1
    q = qualified(db, "Quiz cinéma : gagnez des places", game_type="quiz")
    q.automation_class = "A2"
    db.commit()
    r = client.get("/api/contests", params={"automation_class": "A2"}).json()
    assert [c["id"] for c in r["items"]] == [q.id]
    assert r["items"][0]["automation_class"] == "A2"


def test_categories_and_matrix(client):
    r = client.get("/api/sources/policy").json()
    allowed = {c["id"]: c["allowed_by_default"] for c in r["categories"]}
    assert allowed == {1: True, 2: True, 3: True, 4: True, 5: True, 6: False, 7: False}
    doms = {m["domain"]: m for m in r["matrix"]}
    assert set(doms) == {"jeu-concours.biz", "toutgagner.com", "ledemondujeu.com", "concours-du-net.com"}
    assert doms["ledemondujeu.com"]["automated_extraction"] is False  # même réseau que Jeu-concours.biz
    assert doms["jeu-concours.biz"]["automated_extraction"] is False
    refs = {x["domain"] for x in r["references"]}
    assert refs == {"jeu-concours.biz", "toutgagner.com", "concours-du-net.com", "ledemondujeu.com"}  # consultation assistée + lien direct


def test_denied_site_never_fetched_but_explained(client, db):
    r = client.post("/api/contests", json={"url": "https://www.jeu-concours.biz/concours-12345.html"})
    assert r.status_code == 422 and "organisateur" in r.json()["detail"]
    assert db.query(Contest).count() == 0
    assert P.access_mode("html", "https://www.toutgagner.com/x") == "assisted"
    assert P.access_mode("rss", "https://marque.test/feed") == "authorized_feed"


def test_user_import_csv_and_lines(client, db):
    end = (date.today() + timedelta(days=12)).isoformat()
    csv = f"url;titre;fin;lot\nhttps://marque-a.test/jeu;Gagnez un week-end;{end};Séjour 2 personnes\nhttps://www.jeu-concours.biz/c-1.html;Copie;;\npas une url;;;\n"
    r = client.post("/api/contests/import", json={"text": csv}).json()
    assert len(r["created"]) == 1 and len(r["skipped"]) == 2
    assert any("lecture automatique" in s["reason"] for s in r["skipped"])
    c = db.get(Contest, r["created"][0])
    assert c.title == "Gagnez un week-end" and c.end_date.isoformat() == end and c.prize_summary == "Séjour 2 personnes"
    # deuxième import : aucun doublon
    lines = "https://marque-a.test/jeu Gagnez un week-end\nhttps://marque-b.test/concours ; Quiz été ; 31/12/2030"
    r2 = client.post("/api/contests/import", json={"text": lines, "origin": "browser_share"}).json()
    assert r2["existing"] == [c.id] and len(r2["created"]) == 1
    assert db.get(Contest, r2["created"][0]).end_date == date(2030, 12, 31)


def _plan_ids(db):
    return [i["contest_id"] for i in week_view(db)["priority"] if i.get("scheduled_day")]


def test_a1_a2_first_and_social_capped(db):
    update_prefs(db, {"minutes_per_day": 120, "weekly_goal": 10, "social_share_max": 30})
    forms = [qualified(db, f"Gagnez un lot formulaire {i}") for i in range(3)]
    socials = []
    for i in range(6):
        s = qualified(db, f"Gagnez un lot Instagram {i}", url=f"https://marque-social.test/insta{i}")
        s.automation_class, s.social_platform = "A4", "instagram"
        socials.append(s)
    db.commit()
    s1, r1 = PL.score_contest(forms[0], date.today(), False)
    s4, r4 = PL.score_contest(socials[0], date.today(), False)
    assert s1 > s4 and any(x.startswith("A1") for x in r1)
    ids = _plan_ids(db)
    assert all(f.id in ids for f in forms)
    assert sum(1 for s in socials if s.id in ids) == int(9 * 30 / 100)  # pas de monopole, mais pas exclus


def test_user_filters(db):
    update_prefs(db, {"minutes_per_day": 120})
    form = qualified(db, "Gagnez une trottinette")
    insta = qualified(db, "Gagnez un sac Instagram", url="https://marque-social.test/sac")
    insta.automation_class, insta.social_platform = "A4", "instagram"
    crea = qualified(db, "Concours photo : gagnez un appareil", url="https://marque-photo.test/c")
    crea.automation_class = "A5"
    quiz = qualified(db, "Gagnez une montre", url="https://marque-quiz.test/q")
    quiz.automation_class = "A2"
    db.commit()
    assert {form.id, insta.id, crea.id, quiz.id} <= set(_plan_ids(db))
    update_prefs(db, {"hide_instagram": True, "hide_creative": True})
    ids = set(_plan_ids(db))
    assert form.id in ids and insta.id not in ids and crea.id not in ids
    update_prefs(db, {"hide_instagram": False, "hide_creative": False, "automation_mode": "max"})
    ids = set(_plan_ids(db))
    assert ids == {form.id, quiz.id}
    base = PL.score_contest(quiz, date.today(), False, {})[0]
    assert PL.score_contest(quiz, date.today(), False, {"favor_quiz": True})[0] == base + 6


def test_a7_a8_never_planned(db):
    c = qualified(db, "Gagnez un robot")
    c.automation_class = "A8"
    db.commit()
    assert c.id not in _plan_ids(db)


def test_one_failing_source_never_blocks_others(db, monkeypatch):
    from app.discovery import base as B
    from app.discovery import pipeline
    from app.discovery.base import RawContest
    from app.scheduler.runner import Runner

    @B.register
    class Boom(B.Connector):
        kind = "test_boom"

        def discover(self):
            raise RuntimeError("panne du fournisseur")

    @B.register
    class Fine(B.Connector):
        kind = "test_fine"

        def discover(self):
            yield RawContest(title="Gagnez un vélo électrique", url="https://organisateur-ok.test/jeu", source_url="https://organisateur-ok.test/")

    monkeypatch.setattr(pipeline, "enrich", lambda *a, **k: None)
    monkeypatch.setattr("app.scheduler.runner.enrich_backlog", lambda *a, **k: 0)
    db.add_all([Source(name="A panne", kind="test_boom", url="https://panne.test/"), Source(name="B ok", kind="test_fine", url="https://organisateur-ok.test/"),
                Source(name="Exclu", kind="html", url="https://www.jeu-concours.biz/")])
    db.commit()
    Runner().job_scan()
    db.expire_all()
    srcs = {s.name: s for s in db.query(Source)}
    assert srcs["A panne"].last_status.startswith("erreur")
    assert srcs["B ok"].last_status == "ok"
    assert srcs["Exclu"].last_scan_at is None  # consultation assistée : jamais lue, même activée
    assert db.query(Contest).filter(Contest.url == "https://organisateur-ok.test/jeu").count() == 1


def test_source_quality_report(client, db):
    s = Source(name="Marque", kind="site", url="https://marque-q.test/")
    db.add(s)
    db.commit()
    from app.discovery.base import RawContest
    from app.discovery.pipeline import upsert

    upsert(db, s, RawContest(title="Gagnez un vélo", url="https://marque-q.test/jeu-velo", source_url="https://marque-q.test/"))
    upsert(db, s, RawContest(title="Gagnez un sac", url="https://marque-q.test/jeu-sac", source_url="https://marque-q.test/", end_date="2030-01-01"))
    db.commit()
    r = client.get(f"/api/sources/{s.id}/quality").json()
    assert r["metrics"]["contests"] == 2 and r["metrics"]["missing_end_date"] == 1
    assert r["access_mode"] == "public_source"
    assert any("date de clôture" in i for i in r["issues"])
    assert client.get("/api/sources/9999/quality").status_code == 404


def test_migration_backfills_class(env):
    from sqlalchemy import text

    from app.db.migrations import _m005_automatability
    from app.db.session import SessionLocal, get_engine

    db = SessionLocal()
    c = qualified(db, "Gagnez un livre")
    db.execute(text("UPDATE contests SET automation_class = NULL, difficulty = NULL"))
    db.commit()
    with get_engine().begin() as conn:
        _m005_automatability(conn)
    db.expire_all()
    assert db.get(Contest, c.id).automation_class == "A1"
    db.close()


def test_written_authorization_unlocks_only_with_reference(db, client):
    from app.admin.settings_service import update_settings
    from app.discovery.policy import denial_reason

    url = "https://www.ledemondujeu.com/nouveaux-jeux-concours.html"
    assert denial_reason(url)
    r = client.put("/api/settings", json={"written_authorizations": [{"domain": "ledemondujeu.com"}]})
    assert r.status_code in (400, 422) and denial_reason(url)
    r = client.put("/api/settings", json={"written_authorizations": [{"domain": "exemple.fr", "reference": "accord oral"}]})
    assert r.status_code in (400, 422)
    update_settings(db, {"written_authorizations": [{"domain": "ledemondujeu.com", "date": "2026-12-01", "reference": "E-mail de Reflexe Media du 01/12"}]})
    assert denial_reason(url) is None and denial_reason("https://www.jeu-concours.biz/") is not None
    m = {x["domain"]: x for x in client.get("/api/sources/policy").json()["matrix"]}
    assert m["ledemondujeu.com"]["authorized_in_writing"] is True
    update_settings(db, {"written_authorizations": []})
    assert denial_reason(url)
