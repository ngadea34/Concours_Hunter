"""Participation automatique sur un formulaire de DÉMONSTRATION local + API + sécurité + sauvegardes."""
import http.server
import threading
from functools import partial

import pytest
from conftest import FIX, make_contest, rules

from app.participation import service as ps
from app.participation.profile import save_consents, save_profile

RULES_AUTO = (rules("fr_free.txt").replace("2026", "2099")
              .replace("Toute participation effectuée par des moyens automatisés (robots, scripts) est interdite et entraînera la nullité.",
                       "Les participations automatisées sont autorisées pour ce jeu de démonstration."))


class Handler(http.server.SimpleHTTPRequestHandler):
    posts: list = []

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("content-length", 0))
        Handler.posts.append(self.rfile.read(n).decode())
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<html><body><h1>Merci, participation enregistrée</h1></body></html>".encode())

    def log_message(self, *a):
        pass


@pytest.fixture()
def demo_server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(FIX / "sites")))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _pw_available():
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _pw_available(), reason="Playwright absent")
def test_auto_participation_on_demo_form(db, demo_server):
    from app.discovery.pipeline import record_answer
    from app.participation.browser_runner import run_auto

    save_profile(db, {"first_name": "Camille", "last_name": "Test", "email": "camille@example.org"})
    save_consents(db, {"auto_participation": True, "store_proofs": True})
    c = make_contest(db, title="Démo auto", url=demo_server + "/demo_form.html", rules_text=RULES_AUTO)
    assert c.policy.mode == "auto", c.policy.reasons
    record_answer(db, c, "Quelle est la couleur de la manette ?", "Blanche", "test")
    p = ps.prepare(db, c, "auto")
    assert p.mode == "auto" and p.status == "prepared"
    Handler.posts.clear()
    run_auto(db, p, allow_private_hosts=True)
    assert p.status == "submitted", p.error
    body = Handler.posts[0]
    assert "prenom=Camille" in body and "email=camille%40example.org" in body and "q1=Blanche" in body
    assert "newsletter" not in body  # case marketing jamais cochée
    assert any(x.kind == "screenshot" and x.sha256 for x in p.proofs)


def test_auto_blocked_without_consent(db, demo_server):
    from app.participation.browser_runner import can_auto

    c = make_contest(db, title="Démo auto 2", url=demo_server + "/demo_form.html", rules_text=RULES_AUTO)
    p = ps.prepare(db, c, "auto")
    assert p.mode == "semi"
    assert not can_auto(db, p)[0]


def test_captcha_contest_is_manual(db):
    c = make_contest(db, title="Captcha", rules_text=RULES_AUTO + "\nUn captcha (reCAPTCHA) protège le formulaire.")
    assert c.participation_mode == "manual"
    assert any("CAPTCHA" in r for r in c.policy.reasons)


def test_api_full_flow(client, db):
    c = make_contest(db, rules_text=rules("fr_free.txt").replace("2026", "2099"))
    r = client.get("/api/contests").json()
    assert r["total"] == 1 and r["items"][0]["free_status"] == "free"
    d = client.get(f"/api/contests/{c.id}").json()
    assert d["justifications"] and d["provenance"] is not None and d["score_breakdown"]["reliability"]
    client.put("/api/profile", json={"first_name": "Camille", "email": "c@example.org"})
    p = client.post(f"/api/contests/{c.id}/participations", json={}).json()
    assert p["status"] == "awaiting_human"
    assert client.post(f"/api/contests/{c.id}/participations", json={}).status_code == 409
    assert client.get(f"/api/participations/{p['id']}/prefill").json()["fields"]["first_name"] == "Camille"
    found = client.get("/api/participations", params={"url": "https://www.jouets-exemple.test/jeu"}).json()
    assert [x["id"] for x in found] == [p["id"]]
    assert client.post(f"/api/participations/{p['id']}/submitted", json={"time_spent_minutes": 2}).json()["status"] == "submitted"
    res = client.post("/api/results", json={"contest_id": c.id, "outcome": "won", "message_text": "Bravo, vous avez gagné", "sender": "x@jouets-exemple.test"}).json()
    assert res["phishing_score"] < 50
    claims = client.get("/api/claims").json()
    assert claims and claims[0]["days_left"] == 15
    assert client.patch(f"/api/claims/{claims[0]['id']}", json={"status": "received"}).json()["status"] == "received"
    st = client.get("/api/stats").json()
    assert st["participations_valid"] == 1 and st["gains_obtained_eur"] == 549.99
    assert client.get("/api/notifications").json()
    assert client.post("/api/notifications/read-all").json()["ok"]
    assert client.get("/api/admin/logs").json()


def test_security_middleware(client):
    # CSRF : une page tierce ne peut rien modifier
    r = client.post("/api/notifications/read-all", headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    # DNS rebinding / LAN : Host non local sans jeton → refus
    assert client.get("/api/stats", headers={"host": "evil.example"}).status_code == 401
    from app.security.crypto import get_api_token

    assert client.get("/api/stats", headers={"host": "192.168.1.10", "x-ch-token": get_api_token()}).status_code == 200
    assert client.get("/api/stats", headers={"host": "192.168.1.10", "x-ch-token": "faux"}).status_code == 401
    assert client.get("/api/health").headers["x-frame-options"] == "DENY"
    # SSRF : ajout manuel vers le réseau local refusé
    assert client.post("/api/contests", json={"url": "http://192.168.0.1/admin"}).status_code == 400
    assert client.put("/api/settings", json={"ollama_url": "http://attacker.example:11434"}).status_code == 400
    assert client.get("/../../etc/passwd").status_code in (200, 404)  # sert index.html, jamais un fichier hors static
    assert "root:" not in client.get("/..%2f..%2fetc/passwd").text


def test_backup_and_restore(client, db):
    c = make_contest(db, title="Avant sauvegarde", rules_text=rules("fr_free.txt"))
    b = client.post("/api/admin/backup").json()
    db.delete(c)
    db.commit()
    assert client.get("/api/contests", params={"status": "qualified,expired,to_verify,rejected"}).json()["total"] == 0
    assert client.post("/api/admin/restore", json={"name": b["name"]}).json()["ok"]
    from app.db.session import SessionLocal
    from app.db.models import Contest

    s = SessionLocal()
    assert s.query(Contest).filter_by(title="Avant sauvegarde").count() == 1
    s.close()
    names = [x["name"] for x in client.get("/api/admin/backups").json()]
    assert any("pre-restore" in n for n in names)  # l'état courant est sauvegardé avant restauration
    assert client.post("/api/admin/restore", json={"name": "../../concours.db"}).status_code == 400


def test_scheduler_interruption_recovery(env, db):
    from app.db.models import ScanJob, Source
    from app.scheduler.runner import Runner

    s = Source(name="S", kind="rss", url="https://x.test/feed")
    db.add(s)
    db.flush()
    db.add(ScanJob(source_id=s.id, status="running", checkpoint={"done": ["https://x.test/a"]}))
    db.commit()
    r = Runner()
    r.start()
    try:
        db.expire_all()
        assert db.query(ScanJob).one().status == "interrupted"
        st = r.status()
        assert st["running"] and {j["id"] for j in st["jobs"]} == {"scan", "daily", "weekly", "auto", "backup"}
        r.stop_all()
        assert r.status()["paused"]
        r._wrap("daily", lambda: (_ for _ in ()).throw(RuntimeError("ne doit pas tourner")))  # en pause : ignoré
        assert "daily" not in r.last
    finally:
        r.shutdown()
