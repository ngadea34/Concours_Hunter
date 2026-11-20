"""Agrégateur maison : connecteur « site organisateur », suggestions de sites, type de jeu."""
import httpx
from conftest import rules

from app.db.models import Contest, Source
from app.discovery.connectors.site import is_contest_url, title_from_url
from app.discovery.fetcher import Fetcher
from app.discovery.pipeline import run_scan, upsert
from app.discovery.base import RawContest
from app.discovery.suggest import follow, suggestions
from app.intelligence.game_type import classify_game_type

HTML = {"content-type": "text/html; charset=utf-8"}
XML = {"content-type": "application/xml"}
RULES = rules("fr_free.txt").replace("2026", "2099")

SITEMAP_INDEX = """<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://marque.test/sitemap-produits.xml</loc></sitemap>
<sitemap><loc>https://marque.test/sitemap-jeux.xml</loc></sitemap>
<sitemap><loc>https://autre.test/sitemap.xml</loc></sitemap>
</sitemapindex>"""
SITEMAP_JEUX = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://marque.test/jeux-concours/gagnez-un-robot-patissier</loc><lastmod>2099-01-01</lastmod></url>
<url><loc>https://marque.test/jeux-concours/</loc></url>
<url><loc>https://marque.test/jeux-concours/reglement-robot</loc></url>
<url><loc>https://marque.test/jeux-concours/gagnants-2020</loc></url>
<url><loc>https://marque.test/jeu/vieux-concours-2019</loc><lastmod>2019-05-01</lastmod></url>
</urlset>"""
PAGE = """<html><head><meta property="og:title" content="Gagnez un robot pâtissier Marque"></head><body>
<h1>Jeu concours</h1><p>Tirage au sort parmi les participants.</p><a href="/reglement-robot.html">Règlement du jeu</a></body></html>"""


def router(req: httpx.Request) -> httpx.Response:
    u = str(req.url)
    if u == "https://marque.test/robots.txt":
        return httpx.Response(200, text="User-agent: *\nAllow: /\nSitemap: https://marque.test/sitemap_index.xml\n")
    if u.endswith("/robots.txt"):
        return httpx.Response(404)
    if u == "https://marque.test/sitemap_index.xml":
        return httpx.Response(200, text=SITEMAP_INDEX, headers=XML)
    if u == "https://marque.test/sitemap-jeux.xml":
        return httpx.Response(200, text=SITEMAP_JEUX, headers=XML)
    if u == "https://marque.test/sitemap-produits.xml":
        return httpx.Response(200, text='<?xml version="1.0"?><urlset><url><loc>https://marque.test/produit/robot</loc></url></urlset>', headers=XML)
    if u == "https://marque.test/jeux-concours/gagnez-un-robot-patissier":
        return httpx.Response(200, text=PAGE, headers=HTML)
    if u == "https://marque.test/reglement-robot.html":
        return httpx.Response(200, text="<html><body><pre>" + RULES + "</pre></body></html>", headers=HTML)
    # site sans sitemap : repli sur la page d'accueil (flux RSS annoncé + liens)
    if u == "https://media.test/":
        return httpx.Response(200, headers=HTML, text="""<html><head><link rel="alternate" type="application/rss+xml" href="/feed"></head><body>
        <a href="/concours/gagnez-des-places-de-cinema">Gagnez des places de cinéma pour le festival</a>
        <a href="https://ailleurs.test/concours/x">Concours partenaire chez un autre site</a>
        <a href="/actualites/politique">Actualité politique du jour</a></body></html>""")
    if u == "https://media.test/feed":
        return httpx.Response(200, headers={"content-type": "application/rss+xml"}, text="""<?xml version="1.0"?><rss version="2.0"><channel><title>M</title>
        <item><title>Jeu concours : un week-end à gagner</title><link>https://media.test/2099/weekend</link></item>
        <item><title>La météo de demain</title><link>https://media.test/2099/meteo</link></item></channel></rss>""")
    return httpx.Response(404)


def fetcher():
    return Fetcher(max_per_hour=100, client=httpx.Client(transport=httpx.MockTransport(router), follow_redirects=True))


def test_contest_url_filter():
    assert is_contest_url("https://m.test/jeux-concours/gagnez-un-velo")
    assert is_contest_url("https://m.test/jeu-instant-gagnant-noel")
    assert not is_contest_url("https://m.test/jeux-concours/")  # page d'index
    assert not is_contest_url("https://m.test/concours/reglement-velo")
    assert not is_contest_url("https://m.test/concours-fonction-publique-2099")
    assert not is_contest_url("https://m.test/produit/velo")
    assert title_from_url("https://m.test/jeux/gagnez-un-velo-12345.html") == "Gagnez un velo"


def test_site_connector_sitemap_end_to_end(db):
    s = Source(name="marque.test", kind="site", url="https://marque.test/", enabled=True, trust=60)
    db.add(s)
    db.commit()
    job = run_scan(db, s, fetcher())
    assert job.status == "ok", job.error
    assert job.found == 1  # index, règlement, gagnants, vieux concours, produit et sitemap d'un autre domaine écartés
    c = db.query(Contest).one()
    assert c.title == "Gagnez un robot pâtissier Marque"  # vrai titre lu sur la page
    assert c.rules and c.rules[0].origin == "fetched"
    assert c.status == "qualified", c.needs_human_reason
    assert c.game_type == "draw"


def test_site_connector_falls_back_to_home_page(db):
    s = Source(name="media.test", kind="site", url="https://media.test/", enabled=True)
    db.add(s)
    db.commit()
    job = run_scan(db, s, fetcher(), max_enrich=0)
    assert job.status == "ok", job.error
    urls = sorted(c.url for c in db.query(Contest))
    assert urls == ["https://media.test/2099/weekend", "https://media.test/concours/gagnez-des-places-de-cinema"]


def test_suggestions_and_follow(db, client):
    for title, url in [("Robot pâtissier", "https://www.marque.test/jeu/robot"), ("Mixeur", "https://marque.test/jeu/mixeur"),
                       ("Instagram", "https://www.instagram.com/p/abc"), ("Exclu", "https://www.jeu-concours.biz/x")]:
        upsert(db, None, RawContest(title=title + " à gagner", url=url, source_url=url))
    db.commit()
    sug = suggestions(db)
    assert [x["domain"] for x in sug] == ["marque.test"] and sug[0]["contests"] == 2
    r = client.post("/api/sources/follow", json={"domain": "marque.test"})
    assert r.status_code == 200 and r.json()["kind"] == "site"
    assert client.post("/api/sources/follow", json={"domain": "marque.test"}).status_code == 409
    assert client.post("/api/sources/follow", json={"domain": "jeu-concours.biz"}).status_code == 400
    assert client.post("/api/sources/follow", json={"domain": "pas un domaine"}).status_code == 400
    assert client.get("/api/sources/suggestions").json() == []


def test_follow_refuses_denied_site(db):
    import pytest

    with pytest.raises((PermissionError, ValueError)):
        follow(db, "toutgagner.com")


def test_game_type():
    assert classify_game_type("Jouez à notre instant gagnant de Noël") == "instant_win"
    assert classify_game_type("Concours photo : envoyez votre plus belle photo, un jury désignera") == "creative"
    assert classify_game_type("Répondez aux questions du quiz pour participer au tirage au sort") == "quiz"
    assert classify_game_type("Abonnez-vous et commentez la publication Instagram, tirage au sort") == "social"
    assert classify_game_type("Le gagnant sera désigné par tirage au sort") == "draw"
    assert classify_game_type("Gagnez un vélo", url="https://www.facebook.com/p/1") == "social"
    assert classify_game_type("Gagnez un vélo") is None  # jamais deviné


def test_contests_filter_by_game_type(client, db):
    from conftest import make_contest

    make_contest(db, title="Instant gagnant vélo", url="https://velo.test/jeu", rules_text=RULES + "\nInstant gagnant : découvrez immédiatement si vous avez gagné.")
    r = client.get("/api/contests", params={"game_type": "instant_win", "status": "new,qualified,to_verify"}).json()
    assert r["total"] == 1 and r["items"][0]["game_type"] == "instant_win"


def test_migration_v2_backfills_game_type(db):
    from sqlalchemy import text

    from app.db.migrations import LATEST, migrate
    from app.db.session import get_engine

    upsert(db, None, RawContest(title="Instant gagnant de Noël", url="https://n.test/jeu", source_url="https://n.test/jeu"))
    db.commit()
    db.close()
    with get_engine().begin() as conn:  # simule une base créée avant la version 2
        conn.execute(text("DROP INDEX ix_contests_game_type"))
        conn.execute(text("ALTER TABLE contests DROP COLUMN game_type"))
        conn.execute(text("DELETE FROM schema_version WHERE version >= 2"))
    assert migrate() == LATEST
    with get_engine().begin() as conn:
        assert conn.execute(text("SELECT game_type FROM contests")).scalar() == "instant_win"


SALLE = """<html><body><h2>Nos jeux</h2>
<div class="jeu"><a href="/jeux-concours/places-concert-opus">2x 2 places Opus Kink jusqu'au 27 Nov 2099 Je joue !</a></div>
<div class="jeu"><a href="/jeux-concours/invitations-impro">2x 2 invitations Match Impro jusqu'au 24 Nov 2099 Je joue !</a></div>
<a href="/nos-jeux-concours-c.html">Tous nos jeux concours en cours</a>
<footer>Suivez-nous sur Facebook et Instagram, partagez !</footer></body></html>"""
JEU = """<html><body><h1>Places Opus Kink</h1><p>Jeu gratuit sans obligation d'achat, tirage au sort.</p>
<a href="https://www.deezer.com/fr/playlist/1">Écouter la playlist</a><a href="https://agenda.test/play">Play</a>
<footer>Suivez-nous sur Facebook Instagram Partager</footer></body></html>"""


def salle_router(req: httpx.Request) -> httpx.Response:
    u = str(req.url)
    if u == "https://salle.test/robots.txt":  # sitemap déclaré sur www : même site
        return httpx.Response(200, text="User-agent: *\nSitemap: https://www.salle.test/sitemap.xml\n")
    if u == "https://www.salle.test/sitemap.xml":
        return httpx.Response(200, headers=XML, text='<?xml version="1.0"?><urlset><url><loc>https://www.salle.test/agenda</loc></url></urlset>')
    if u == "https://salle.test/":
        return httpx.Response(200, text=SALLE, headers=HTML)
    if u.startswith("https://salle.test/jeux-concours/"):
        return httpx.Response(200, text=JEU, headers=HTML)
    return httpx.Response(404)


def test_site_real_world_pitfalls(db):
    """Cas vus lors de l'essai réel : lien externe pris pour le jeu, bouton « Je joue ! » dans le titre,
    page de liste prise pour un concours, faux « réseaux sociaux » à cause du pied de page, scan vide silencieux."""
    s = Source(name="salle.test", kind="site", url="https://salle.test/", enabled=True)
    db.add(s)
    db.commit()
    f = Fetcher(max_per_hour=100, client=httpx.Client(transport=httpx.MockTransport(salle_router), follow_redirects=True))
    job = run_scan(db, s, f)
    assert job.status == "ok", job.error
    cs = sorted(db.query(Contest), key=lambda c: c.url)
    assert [c.url for c in cs] == ["https://salle.test/jeux-concours/invitations-impro", "https://salle.test/jeux-concours/places-concert-opus"]
    assert all(not c.title.lower().endswith("je joue !") for c in cs)
    assert all(c.game_type == "draw" for c in cs)
    assert "2 page(s)" in s.last_status

    empty = Source(name="vide.test", kind="site", url="https://vide.test/", enabled=True)
    db.add(empty)
    db.commit()
    run_scan(db, empty, Fetcher(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html></html>", headers=HTML) if r.url.path == "/" else httpx.Response(404)))))
    assert "aucune page de jeu" in empty.last_status


def test_listing_suffix_is_not_a_contest():
    assert not is_contest_url("https://www.leclub-bricolage.fr/jeux-concours-c.html")
    assert not is_contest_url("https://m.test/nos-jeux-concours")
    assert is_contest_url("https://m.test/jeux-concours/gagnez-un-perceuse")


def test_migration_v3_repairs_site_contests(db):
    from sqlalchemy import text

    from app.db.migrations import migrate
    from app.db.models import ContestSighting
    from app.db.session import get_engine

    s = Source(name="salle.test", kind="site", url="https://salle.test/")
    db.add(s)
    db.flush()
    for url, page in [("https://www.deezer.com/fr/playlist/1", "https://salle.test/jeux-concours/opus"),
                      ("https://salle.test/jeux-concours-c.html", "https://salle.test/jeux-concours-c.html")]:
        c = Contest(title="Suivez-nous sur Facebook Instagram partager " + page[-8:], url=url, canonical_url=url, fingerprint=page,
                    status="new", game_type="social")
        db.add(c)
        db.flush()
        db.add(ContestSighting(contest_id=c.id, source_id=s.id, source_url=page))
    db.commit()
    db.close()
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM schema_version WHERE version >= 3"))
    migrate()
    with get_engine().begin() as conn:
        rows = conn.execute(text("SELECT url, status, game_type FROM contests ORDER BY id")).all()
    assert rows[0] == ("https://salle.test/jeux-concours/opus", "new", None)
    assert rows[1][1] == "archived"
