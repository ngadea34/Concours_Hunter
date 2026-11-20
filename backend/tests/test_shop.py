"""M14 Hunter Shop & Promo : les 15 cas obligatoires + règles de sécurité (validation, pas de remboursement non constaté)."""
import base64
from datetime import date, timedelta

import pytest

from app.db.models import Promotion, ShopClaim, ShopLedger
from app.shop import claims as CL
from app.shop import documents as D
from app.shop.analyze import analyze_offer, apply_to_promotion
from app.shop.finance import analysis
from app.shop.prefs import update_shop_prefs
from app.shop.products import ean_valid, match_product
from app.shop.recommend import recommendations

TODAY = date.today()
EAN = "3017620422003"
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()
PNG2 = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x01" * 64).decode()


def offer_text(start=None, end=None, deadline=None, full=True, retailers="Carrefour, Auchan et E.Leclerc", extra=""):
    start = start or TODAY - timedelta(days=10)
    end = end or TODAY + timedelta(days=20)
    deadline = deadline or end + timedelta(days=15)
    amount = "Votre produit vous est 100 % remboursé dans la limite de 5 €." if full else "2 € remboursés sur votre achat."
    return (f"Offre Café Arome. La société Café Exemple SAS, RCS Lyon 512 345 678, organise une offre de remboursement.\n"
            f"Produit concerné : Café Arome moulu, paquet 250 g, EAN {EAN}.\n"
            f"Pour bénéficier de l'offre, achetez le produit entre le {start:%d/%m/%Y} et le {end:%d/%m/%Y} dans les magasins participants : {retailers}.\n"
            f"{amount}\nInscrivez-vous sur https://www.cafe-exemple.fr/offre au plus tard le {deadline:%d/%m/%Y} et téléchargez la photo "
            f"de votre ticket de caisse et du code-barres.\nOffre limitée à une seule demande par foyer. Offre non cumulable avec d'autres promotions.\n"
            f"Le remboursement sera effectué par virement sous 6 à 8 semaines. {extra}")


def receipt_text(day=None, store="CARREFOUR LYON PART-DIEU", product="CAFE AROME MOULU 250G", price="4,50", ticket="0042"):
    day = day or TODAY - timedelta(days=2)
    return f"{store}\nLe {day:%d/%m/%Y} 10:42\nTicket n° {ticket}\n{product} {price}\nPAIN DE MIE 1,20\nTOTAL 5,70\nCB 5,70"


def make_promo(db, **kw):
    p = Promotion(title="Café Arome 100 % remboursé", product="Café Arome moulu 250 g", url="https://www.cafe-exemple.fr/offre",
                  rules_url="https://www.cafe-exemple.fr/offre", origin="user", status="to_watch", price_eur=4.5)
    text = kw.pop("text", None) or offer_text(**kw)
    data = analyze_offer(text, p.url)
    apply_to_promotion(p, data)
    p.kind = data["kind"]
    db.add(p)
    db.commit()
    return p


def claim_with(db, p, receipt=None, barcode_ean=EAN, data_url=PNG):
    c = CL.create_claim(db, p)
    if receipt is not None:
        r = D.store(db, "receipt", data_url, p.id)
        D.ocr(db, r, receipt)
        CL.attach(db, c, r)
    if barcode_ean is not None:
        b = D.store(db, "barcode", PNG2 if data_url == PNG else data_url[:-4] + "AAA=", p.id)
        D.set_user_fields(db, b, {"ean": barcode_ean})
        CL.attach(db, c, b)
    CL.run_checks(db, c)
    return c


def step(c, n):
    return c.checks[n - 1]


def send_ok(db, c):
    CL.request_validation(db, c)
    CL.validate(db, c, True, [d.id for d in CL.docs_of(db, c)])
    return CL.mark_sent(db, c, TODAY, "DOSSIER-123")


# ------------------------------------------------------------------ analyse
def test_offer_analysis_extracts_conditions():
    a = analyze_offer(offer_text(), "https://www.cafe-exemple.fr/offre")
    assert a["kind"] == "full_refund" and a["refund_max_eur"] == 5.0 and a["eans"] == [EAN]
    assert a["variant"]["quantity"] == "250 g" and a["retailers"] == ["Carrefour", "Auchan", "E.Leclerc"]
    assert a["limit_per"] == "household" and a["limit_count"] == 1 and a["cumulable"] is False
    assert a["channel"] == "platform" and a["channel_target"].startswith("https://www.cafe-exemple.fr")
    assert set(a["required_docs"]) >= {"receipt", "barcode"} and a["refund_delay_days"] == 56
    assert a["analysis"]["evidence"]["limit"].startswith("Offre limitée")


# ------------------------------------------------------------------ 15 cas obligatoires
def test_wrong_ean(db):
    assert not ean_valid("3017620422004") and ean_valid(EAN)
    p = make_promo(db)
    c = claim_with(db, p, receipt_text(), barcode_ean="4006381333931")  # EAN valide mais pas celui du règlement
    assert step(c, 5)["status"] == "fail" and "Produit non participant" in step(c, 5)["detail"]
    assert match_product([EAN], {}, {"ean": "3017620422004"})["status"] == "mismatch"  # clé fausse


def test_unreadable_receipt(db):
    p = make_promo(db)
    c = claim_with(db, p, "ILLISIBLE")
    assert step(c, 6)["status"] == "fail" and "illisible" in step(c, 6)["detail"]
    with pytest.raises(CL.ClaimError):
        CL.request_validation(db, c)


def test_incomplete_receipt(db):
    p = make_promo(db)
    c = claim_with(db, p, "CAFE AROME MOULU 250G 4,50\nTOTAL 4,50")  # ni date ni enseigne
    assert step(c, 6)["status"] == "fail" and "incomplet" in step(c, 6)["detail"].lower()
    rec = next(d for d in CL.docs_of(db, c) if d.kind == "receipt")
    D.set_user_fields(db, rec, {"purchase_date": (TODAY - timedelta(days=1)).isoformat(), "retailer": "Carrefour"})
    CL.sync_from_documents(db, c)
    CL.run_checks(db, c)
    assert step(c, 6)["status"] == "ok"
    assert rec.ocr_text.startswith("CAFE AROME")  # le justificatif lui-même n'est jamais modifié


def test_purchase_out_of_period(db):
    p = make_promo(db, start=TODAY - timedelta(days=5))
    c = claim_with(db, p, receipt_text(day=TODAY - timedelta(days=8)))
    assert step(c, 3)["status"] == "fail" and "hors période" in step(c, 3)["detail"]


def test_product_not_participating_and_retailer_restriction(db):
    p = make_promo(db)
    c = claim_with(db, p, receipt_text(store="LIDL VILLEURBANNE"))
    assert step(c, 5)["status"] == "fail" and "non participante" in step(c, 5)["detail"]
    # recommandation : produit disponible seulement dans certaines enseignes
    update_shop_prefs(db, {"retailers": ["Lidl", "Aldi"]})
    r = recommendations(db)
    assert not r["items"] and "seulement chez" in r["excluded"][0]["reason"]
    update_shop_prefs(db, {"retailers": ["Carrefour"]})
    assert [b["id"] for b in recommendations(db)["items"]] == [p.id]


def test_expired_offer(db):
    p = make_promo(db, start=TODAY - timedelta(days=60), end=TODAY - timedelta(days=30), deadline=TODAY - timedelta(days=15))
    c = claim_with(db, p, receipt_text(day=TODAY - timedelta(days=40)))
    assert step(c, 4)["status"] == "fail" and "expirée" in step(c, 4)["detail"]
    assert p.id in [x["id"] for x in recommendations(db)["excluded"]]


def test_partial_and_full_refund_profitability(db):
    full = make_promo(db)
    a = analysis(full)
    assert a["category"] == "A" and a["refund_announced_eur"] == 4.5 and a["net_cost_forecast_eur"] == 0.0 and a["refund_guaranteed"]
    part = make_promo(db, full=False)
    b = analysis(part)
    assert part.kind == "partial_refund" and b["refund_announced_eur"] == 2.0 and b["net_cost_forecast_eur"] == 2.5 and b["category"] == "B"


def test_purchase_game_is_never_a_saving(db):
    text = ("Jeu avec obligation d'achat. La société Céréales Exemple SAS organise un jeu : achetez un paquet et tentez de gagner une voiture "
            f"d'une valeur de 25 000 €. Achat entre le {TODAY - timedelta(days=3):%d/%m/%Y} et le {TODAY + timedelta(days=30):%d/%m/%Y}. "
            "Saisissez le code sous l'opercule sur https://www.cereales-exemple.fr/jeu. Une participation par personne.")
    p = make_promo(db, text=text)
    a = analysis(p, 3.2)
    assert p.kind == "purchase_game" and a["refund_announced_eur"] == 0.0 and a["net_cost_forecast_eur"] == 3.2
    assert a["random_prize_value_eur"] == 25000 and not a["refund_guaranteed"]


def test_double_request_blocked(db):
    p = make_promo(db)
    c1 = claim_with(db, p, receipt_text())
    send_ok(db, c1)
    c2 = claim_with(db, p, receipt_text(ticket="0099"), data_url="data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x02" * 64).decode())
    assert step(c2, 4)["status"] == "fail" and "Double demande" in step(c2, 4)["detail"]
    with pytest.raises(CL.ClaimError):
        CL.request_validation(db, c2)


def test_refused_claim(db):
    p = make_promo(db)
    c = claim_with(db, p, receipt_text())
    send_ok(db, c)
    CL.mark_refused(db, c, "Ticket non conforme selon l'organisateur")
    assert c.status == "refused" and p.status == "refused"
    assert db.query(ShopLedger).filter_by(kind="refund_refused").one().amount_eur == 4.5


def test_refund_received_only_when_observed(db, client):
    p = make_promo(db)
    c = claim_with(db, p, receipt_text())
    assert c.status == "ready"
    with pytest.raises(CL.ClaimError):
        CL.mark_sent(db, c)  # jamais sans validation explicite
    with pytest.raises(CL.ClaimError):
        CL.request_validation(db, c) and CL.validate(db, c, False, [])
    CL.validate(db, c, True, [d.id for d in CL.docs_of(db, c)])
    CL.mark_sent(db, c, TODAY, None)
    CL.confirm(db, c, "OK-1", 4.5)
    assert c.status == "refund_pending" and p.status == "refund_pending"
    r = client.post(f"/api/shop/claims/{c.id}/refunded", json={})
    assert r.status_code == 400 and c.status != "refunded"  # aucun remboursement sans montant constaté
    r = client.post(f"/api/shop/claims/{c.id}/refunded", json={"amount_eur": 4.5, "received_on": (TODAY + timedelta(days=2)).isoformat()})
    assert r.status_code == 400  # date future refusée
    r = client.post(f"/api/shop/claims/{c.id}/refunded", json={"amount_eur": 4.5, "received_on": TODAY.isoformat()}).json()
    assert r["status"] == "refunded"
    s = client.get("/api/shop/expenses").json()
    assert s["expenses_eur"] == 4.5 and s["savings_realized_eur"] == 4.5 and s["net_real_cost_eur"] == 0 and s["refunds_pending_eur"] == 0


def test_late_refund(db):
    p = make_promo(db)
    c = claim_with(db, p, receipt_text())
    send_ok(db, c)
    assert not CL.is_late(c, TODAY)
    assert CL.is_late(c, TODAY + timedelta(days=56 + 8))
    CL.run_checks(db, c, TODAY + timedelta(days=70))
    assert step(c, 12)["status"] == "warn" and "retard" in step(c, 12)["detail"]
    from app.db.models import Notification
    from app.scheduler.runner import Runner

    Runner._shop_daily(db, TODAY + timedelta(days=70))
    Runner._shop_daily(db, TODAY + timedelta(days=71))
    assert db.query(Notification).filter(Notification.title.like("Remboursement en retard%")).count() == 1  # signalé une seule fois


def test_cumulable_or_not(db):
    p = make_promo(db)
    p.extra_benefits_eur = 1.0
    a = analysis(p)
    assert a["extra_counted_eur"] is None and any("non compté" in n for n in a["notes"])  # non cumulable : jamais additionné
    p.cumulable = None
    assert analysis(p)["extra_counted_eur"] is None  # non précisé : jamais additionné non plus
    p.cumulable, p.price_eur, p.refund_percent, p.kind = True, 10.0, 50.0, "partial_refund"
    p.refund_max_eur = None
    a = analysis(p)
    assert a["extra_counted_eur"] == 1.0 and a["net_cost_forecast_eur"] == 4.0


def test_availability_never_claims_shelf_without_store_source(client, db):
    p = make_promo(db)
    b = client.get(f"/api/shop/promotions/{p.id}").json()
    assert b["availability"]["level"] == "unknown" and "à confirmer" in b["availability"]["text"]
    assert "temps réel" in b["availability"]["realtime_note"]
    assert client.post(f"/api/shop/promotions/{p.id}/availability", json={"retailer": "Carrefour", "level": "store_confirmed"}).status_code == 400
    r = client.post(f"/api/shop/promotions/{p.id}/availability", json={"retailer": "Carrefour", "level": "third_party", "source": "Open Food Facts"}).json()
    assert r["level"] == "third_party" and "non vérifié" in r["text"]
    r = client.post(f"/api/shop/promotions/{p.id}/availability",
                    json={"retailer": "Carrefour", "store": "Carrefour Part-Dieu", "level": "store_confirmed", "source": "vu en rayon par moi", "price_eur": 4.5}).json()
    assert r["level"] == "store_confirmed" and "Carrefour Part-Dieu" in r["text"]


# ------------------------------------------------------------------ sécurité, documents, parcours complet
def test_documents_original_kept_and_encrypted(db, env):
    d = D.store(db, "receipt", PNG)
    raw = (env / "data" / d.original_path).read_bytes()
    assert b"\x89PNG" not in raw  # chiffré au repos
    assert D.read_original(d).startswith(b"\x89PNG") and d.original_path != d.working_path
    d2 = D.store(db, "receipt", PNG)
    assert d2.extracted.get("duplicate_of") == d.id
    with pytest.raises(D.DocumentError):
        D.store(db, "receipt", "data:text/plain;base64,aGVsbG8=")


def test_sensitive_document_needs_confirmation(client, db):
    d = client.post("/api/shop/documents", json={"kind": "payment_proof", "data_url": PNG}).json()
    assert d["sensitive"] is True
    assert client.get(f"/api/shop/documents/{d['id']}/file").status_code == 403
    assert client.get(f"/api/shop/documents/{d['id']}/file", params={"confirm": True}).status_code == 200


def test_unverified_channel_blocks_transmission(db):
    p = make_promo(db)
    p.channel_target = "http://remboursement-cafe.xyz/form"
    db.commit()
    c = claim_with(db, p, receipt_text())
    assert step(c, 9)["status"] == "fail"
    with pytest.raises(CL.ClaimError):
        CL.request_validation(db, c)


def test_purchase_game_flow_creates_participation(db):
    from conftest import make_contest

    end = TODAY + timedelta(days=30)
    rules = ("La société Céréales Exemple SAS organise un jeu avec obligation d'achat. Achetez un paquet de céréales Exemple entre le "
             f"{TODAY - timedelta(days=3):%d/%m/%Y} et le {end:%d/%m/%Y} et tentez de gagner une voiture d'une valeur de 25 000 €. "
             "Saisissez le code sous l'opercule sur https://www.cereales-exemple.fr/jeu. Jeu ouvert aux résidents de France métropolitaine majeurs.")
    contest = make_contest(db, title="Gagnez une voiture avec Céréales Exemple", url="https://www.cereales-exemple.fr/jeu", rules_text=rules)
    assert contest.free_status == "purchase_required"
    from app.shop.discover import from_contests

    assert from_contests(db) == 1
    p = db.query(Promotion).filter_by(contest_id=contest.id).one()
    assert p.kind == "purchase_game"
    c = CL.create_claim(db, p)
    r = D.store(db, "receipt", PNG, p.id)
    D.ocr(db, r, receipt_text(product="CEREALES EXEMPLE 375G", price="3,20"))
    CL.attach(db, c, r)
    CL.run_checks(db, c)
    assert any("code" in x["detail"] for x in c.checks if x["status"] == "fail")
    c.codes = ["AB12CD"]
    db.commit()
    CL.run_checks(db, c)
    send_ok(db, c)
    assert c.participation_id and c.status == "confirmed"
    assert db.query(ShopLedger).filter_by(kind="expense").one().amount_eur == 3.2
    with pytest.raises(CL.ClaimError):
        CL.mark_refunded(db, c, 3.2, TODAY)  # un jeu avec achat ne se « rembourse » pas


def test_monthly_cap_and_no_purchase_ever(db):
    update_shop_prefs(db, {"monthly_cap_eur": 3})
    make_promo(db)
    r = recommendations(db)
    assert r["items"][0]["over_cap"] and any("plafond" in w for w in r["items"][0]["warnings"])
    assert "décision d'achat vous appartient" in r["note"]


def test_api_and_commands(client, db):
    r = client.post("/api/shop/analyze", json={"text": offer_text(), "url": "https://www.cafe-exemple.fr/offre", "save": True, "title": "Café Arome"}).json()
    assert r["category"] == "A" and r["ean_status"].startswith("EAN vérifié")
    out = client.post("/api/shop/command", json={"command": "/hunter-shop available"}).json()
    assert "Café Arome" in out["text"] and "temps réel" in out["text"]
    out = client.post("/api/shop/command", json={"command": f"/hunter-shop submit {r['id']}"}).json()
    assert "Dossier #" in out["text"]
    for sub in ("cashback", "contests", "track", "report", "analyze 100 % remboursé"):
        assert client.post("/api/shop/command", json={"command": "/hunter-shop " + sub}).status_code == 200
    d = client.get("/api/shop/dashboard").json()
    assert set(d) >= {"available", "to_buy", "full_refund", "purchase_games", "partial_refund", "ending_soon", "claims_to_complete",
                      "claims_sent", "refunds_awaiting", "refunds_received", "refused", "history"}
    assert client.put("/api/shop/preferences", json={"postal_code": "abc"}).status_code == 400
    assert db.query(ShopClaim).count() == 1
