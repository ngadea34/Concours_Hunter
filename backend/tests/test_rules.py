"""Scénarios obligatoires 12.1 (partie qualification)."""
from datetime import date, timedelta

from conftest import make_contest, rules

from app.intelligence.rules_extract import analyze_rules


def test_free_fr_contest_qualified(db):
    c = make_contest(db, rules_text=rules("fr_free.txt"))
    # date de fin 31/12/2026 : le test reste valable tant qu'on est avant
    assert c.free_status == "free" and c.fr_eligible == "yes"
    assert c.eligibility.min_age == 18
    assert c.organizer and c.organizer.legal_id == "512345678"
    assert c.status in ("qualified", "expired")
    assert c.policy.automation_forbidden_by_rules is True and c.participation_mode == "semi"
    assert all(j["evidence"] for j in c.justifications if j["field"] in ("free", "eligibility"))
    assert 0 <= c.reliability_score <= 100 and 0 <= c.interest_score <= 100


def test_purchase_required_rejected(db):
    c = make_contest(db, title="Grand jeu Super Marché", rules_text=rules("purchase.txt"))
    assert c.free_status == "purchase_required"
    assert c.status in ("rejected", "expired")


def test_free_alternative(db):
    a = analyze_rules(rules("alt_free.txt"))
    assert a.free_status == "free_alternative" and not a.ambiguities
    assert a.fr_eligible == "yes" and set(a.countries_allowed) >= {"FR", "BE", "CH"}


def test_us_only_rejected(db):
    c = make_contest(db, title="Holiday Sweepstakes", url="https://acme.test/sweeps", rules_text=rules("us_only.txt"))
    assert c.fr_eligible == "no"
    assert c.status in ("rejected", "expired")
    assert c.prizes[0].currency == "USD" and c.prizes[0].value_eur is not None


def test_expired(db):
    txt = rules("fr_free.txt").replace("2026", "2024")
    c = make_contest(db, title="Vieux jeu", rules_text=txt)
    assert c.status == "expired"


def test_rules_inaccessible_goes_to_verify(db):
    c = make_contest(db, title="Jeu sans règlement", description="Gagnez un séjour ! Participez vite.")
    assert c.status == "to_verify"
    assert "Règlement inaccessible" in (c.needs_human_reason or "")


def test_fake_organizer_and_injection(db):
    c = make_contest(db, title="iPhone offert", url="https://promo-iphone.xyz/win", rules_text=rules("injection.txt"))
    assert c.status == "to_verify"
    assert "prompt_injection" in c.flags
    assert "arnaque" in (c.needs_human_reason or "").lower()
    assert c.reliability_score < 30


def test_fees_detected_and_cache_reuse(db):
    from app.db.models import ContestRule

    c1 = make_contest(db, title="A", url="https://a.test/x", rules_text=rules("fr_free.txt"))
    c2 = make_contest(db, title="B", url="https://b.test/y", rules_text=rules("fr_free.txt"))
    r1, r2 = db.query(ContestRule).filter(ContestRule.contest_id.in_([c1.id, c2.id])).all()
    assert r1.content_hash == r2.content_hash and r2.analysis == r1.analysis


def test_rules_change_invalidates(db):
    from app.intelligence.qualify import add_rules, qualify

    c = make_contest(db, rules_text=rules("fr_free.txt"))
    _, changed = add_rules(db, c, rules("fr_free.txt") + "\nArticle 9 – Un achat est obligatoire. Achat obligatoire.", None, "fetched")
    assert changed
    qualify(db, c)
    assert c.free_status == "free_alternative"  # achat + gratuité affirmée → ambigu
    assert c.status in ("to_verify", "expired")


def test_multilingual_dates_and_age():
    de = analyze_rules("Teilnahmebedingungen. Teilnahmeberechtigt sind Personen mit Wohnsitz in Deutschland und Österreich, die mindestens 18 Jahre alt sind. Das Gewinnspiel läuft vom 1. Dezember 2026 bis zum 24.12.2026. Kein Kauf erforderlich.")
    assert de.free_status == "free" and de.fr_eligible == "no" and de.min_age == 18 and de.end_date == "2026-12-24"
    es = analyze_rules("Bases del sorteo. Sorteo gratuito y sin obligación de compra, abierto a residentes en España, Francia y Portugal mayores de 18 años. Del 1 de diciembre de 2026 al 15 de enero de 2027.")
    assert es.free_status == "free" and es.fr_eligible == "yes" and es.end_date == "2027-01-15"
    it = analyze_rules("Regolamento del concorso. Concorso senza obbligo d'acquisto, riservato a residenti in Italia. Dal 1 dicembre 2026 al 31 dicembre 2026.")
    assert it.fr_eligible == "no"


def test_ambiguous_rules_suspended(db):
    c = make_contest(db, title="Ambigu", rules_text="Règlement. Le jeu est ouvert aux résidents de la zone participante. Lot : une tablette d'une valeur de 300 €. Jusqu'au 30/12/2099.")
    assert c.status == "to_verify"


def test_human_verification_unlocks(db, client):
    c = make_contest(db, title="Ambigu2", rules_text="Règlement du concours. Lot : un vélo d'une valeur de 500 €. Jeu valable jusqu'au 30/12/2099.")
    r = client.post(f"/api/contests/{c.id}/verify", json={"field": "free", "decision": "yes", "evidence": "Vu sur le site"})
    assert r.status_code == 200
    r = client.post(f"/api/contests/{c.id}/verify", json={"field": "eligibility", "decision": "yes"})
    assert r.json()["status"] == "qualified"
