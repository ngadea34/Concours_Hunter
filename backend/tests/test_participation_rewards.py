import base64
from datetime import date, timedelta

import pytest
from conftest import make_contest, rules

from app.participation import service as ps
from app.participation.profile import save_consents, save_profile
from app.rewards import service as rs

RULES_OK = rules("fr_free.txt").replace("2026", "2099")


@pytest.fixture()
def contest(db):
    save_profile(db, {"first_name": "Camille", "last_name": "Test", "email": "camille@example.org", "birth_date": "1990-05-01", "postal_code": "69001"})
    return make_contest(db, rules_text=RULES_OK)


def test_double_participation_refused(db, contest):
    p = ps.prepare(db, contest)
    assert p.mode == "semi" and p.status == "awaiting_human"
    with pytest.raises(ps.ParticipationError, match="double"):
        ps.prepare(db, contest)
    ps.mark(db, p, "cancelled")
    ps.prepare(db, contest)  # une annulation libère la période


def test_daily_period_key():
    assert ps.period_key("daily", date(2026, 11, 20)) == "2026-11-20"
    assert ps.period_key("weekly", date(2026, 11, 20)) == "2026-W47"
    assert ps.period_key(None) == "once"


def test_prefill_and_submission_flow(db, contest):
    from app.discovery.pipeline import record_answer

    record_answer(db, contest, "Quelle est la couleur de la manette ?", "Blanche", "LDDJ")
    p = ps.prepare(db, contest)
    pf = ps.prefill(db, p)
    assert pf["fields"]["email"] == "camille@example.org"
    assert pf["answers"][0]["answer"] == "Blanche"
    assert any("non vérifiée" in w for w in pf["warnings"])
    with pytest.raises(ps.ParticipationError):
        ps.mark(db, p, "confirmed")  # pas de confirmation avant soumission
    ps.mark(db, p, "failed", error="Erreur 500 du site")
    assert p.error
    ps.mark(db, p, "submitted", minutes=3)
    ps.mark(db, p, "confirmed", note="Mail de confirmation reçu")
    assert p.status == "confirmed" and contest.status == "participated"


def test_proof_requires_consent_and_valid_png(db, contest):
    p = ps.prepare(db, contest)
    png = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 100).decode()
    with pytest.raises(ps.ParticipationError, match="Consentement"):
        ps.add_proof(db, p, "screenshot", png, None)
    save_consents(db, {"store_proofs": True})
    ps.add_proof(db, p, "screenshot", png, None)
    with pytest.raises(ps.ParticipationError):
        ps.add_proof(db, p, "screenshot", "data:image/png;base64," + base64.b64encode(b"<script>").decode(), None)
    assert len(p.proofs) == 1 and p.proofs[0].sha256


def test_auto_mode_never_exceeds_policy(db, contest):
    save_consents(db, {"auto_participation": True})
    p = ps.prepare(db, contest, "auto")  # le règlement interdit l'automatisation
    assert p.mode == "semi"


def test_win_cycle_with_claim_deadline(db, contest):
    p = ps.prepare(db, contest)
    ps.mark(db, p, "submitted")
    r = rs.record_result(db, contest_id=contest.id, participation_id=p.id, outcome="won",
                         message_text="Bonjour Camille, vous avez gagné la PS5 ! Répondez-nous pour la livraison.", sender="jeux@jouets-exemple.test")
    assert r.phishing_score < 50
    from app.db.models import Claim

    claim = db.query(Claim).filter_by(result_id=r.id).one()
    assert claim.deadline == date.today() + timedelta(days=15) and claim.value_eur == 549.99
    assert rs.check_deadlines(db, today=claim.deadline - timedelta(days=5)) == 1
    rs.update_claim(db, claim, {"status": "claimed"})
    rs.update_claim(db, claim, {"status": "received"})
    from app.analytics.stats import compute

    st = compute(db)
    assert st["gains_obtained_eur"] == 549.99 and st["prize_value_participated_eur"] >= 549.99


def test_claim_expires(db, contest):
    r = rs.record_result(db, contest_id=contest.id, participation_id=None, outcome="won", message_text="Vous avez gagné", sender="jeux@jouets-exemple.test")
    from app.db.models import Claim

    c = db.query(Claim).filter_by(result_id=r.id).first()
    if c is None:  # message jugé suspect (pas de participation) : pas de réclamation auto
        c = rs.create_claim(db, r.id, deadline=date.today() + timedelta(days=1))
    c.deadline = date.today() - timedelta(days=1)
    db.commit()
    rs.check_deadlines(db)
    assert c.status == "expired"


def test_fake_win_message(db, contest):
    r = rs.record_result(db, contest_id=contest.id, participation_id=None, outcome="won",
                         message_text="URGENT ! Cher gagnant, vous avez gagné un iPhone. Réglez 2,99 € de frais de livraison sous 24h via https://bit.ly/xx avec votre numéro de carte.",
                         sender="lots.gagnant@gmail.com")
    assert r.phishing_score >= 80
    assert any("bancaires" in f for f in r.phishing_flags)
    from app.db.models import Claim, Notification

    assert db.query(Claim).filter_by(result_id=r.id).count() == 0
    assert db.query(Notification).filter_by(kind="phishing").count() == 1


def test_profile_encrypted_at_rest(db, env):
    import sqlite3

    from app.config import get_settings

    save_profile(db, {"email": "secret@example.org"})
    raw = sqlite3.connect(get_settings().db_path).execute("select encrypted_data from user_profile").fetchone()[0]
    assert "secret@example.org" not in raw
