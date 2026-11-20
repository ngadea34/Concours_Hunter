import httpx
from conftest import FIX, rules

from app.db.models import Contest, Source
from app.discovery.fetcher import Fetcher, FetchBlocked
from app.discovery.pipeline import run_scan, upsert
from app.discovery.base import RawContest

SITES = FIX / "sites"
RULES_PS5 = rules("fr_free.txt").replace("2026", "2099")


def router(request: httpx.Request) -> httpx.Response:
    u = str(request.url)
    html = {"content-type": "text/html; charset=utf-8"}
    if u.endswith("/robots.txt"):
        if "blocked.test" in u:
            return httpx.Response(200, text="User-agent: *\nDisallow: /")
        return httpx.Response(404)
    if u == "https://agg.test/":
        return httpx.Response(200, text=(SITES / "listing.html").read_text(encoding="utf-8"), headers=html)
    if u == "https://agg.test/fiche/ps5":
        return httpx.Response(200, text=(SITES / "fiche_ps5.html").read_text(encoding="utf-8"), headers=html)
    if u == "https://agg.test/fiche/us":
        return httpx.Response(200, text="<html><a href='https://acme.test/sweeps'>Enter now</a><a href='https://acme.test/rules'>Official Rules</a></html>", headers=html)
    if u == "https://acme.test/sweeps":
        return httpx.Response(200, text="<html>Sweepstakes</html>", headers=html)
    if u == "https://acme.test/rules":
        return httpx.Response(200, text="<html><body>" + rules("us_only.txt").replace("2026", "2099") + "</body></html>", headers=html)
    if u == "https://jouets-exemple.test/jeu-ps5":
        return httpx.Response(200, text=(SITES / "org_ps5.html").read_text(encoding="utf-8"), headers=html)
    if u == "https://jouets-exemple.test/reglement-ps5":
        return httpx.Response(200, text="<html><body><pre>" + RULES_PS5 + "</pre></body></html>", headers=html)
    if "geo.test" in u:
        return httpx.Response(451, text="Not available in your country")
    if "captcha.test" in u:
        return httpx.Response(200, text="<html><div class='cf-turnstile'></div>challenge-platform</html>", headers=html)
    return httpx.Response(404)


def fetcher():
    return Fetcher(max_per_hour=100, client=httpx.Client(transport=httpx.MockTransport(router), follow_redirects=True))


def test_aggregator_scan_end_to_end(db):
    s = Source(name="Agg", kind="html", url="https://agg.test/", enabled=True, trust=70,
               config={"item": "article.concours", "title": "h2", "end_date": ".date", "prize": ".lot", "max_pages": 1})
    db.add(s)
    db.commit()
    job = run_scan(db, s, fetcher())
    assert job.status == "ok", job.error
    assert job.found == 2 and job.new == 2
    ps5 = db.query(Contest).filter(Contest.title.like("%PlayStation%")).one()
    assert ps5.url == "https://jouets-exemple.test/jeu-ps5"  # URL organisateur préférée à l'agrégateur
    assert ps5.rules and ps5.rules[0].origin == "fetched"
    assert ps5.status == "qualified", ps5.needs_human_reason
    assert ps5.sightings[0].source_url == "https://agg.test/fiche/ps5"  # provenance
    ans = ps5.answers[0]
    assert ans.answer == "Blanche" and ans.verified  # retrouvée sur la page organisateur
    us = db.query(Contest).filter(Contest.title.like("%Holiday%")).one()
    assert us.status == "rejected" and us.fr_eligible == "no"
    # second scan : pas de doublon
    job2 = run_scan(db, s, fetcher())
    assert job2.new == 0 and db.query(Contest).count() == 2


def test_dedup_across_sources(db):
    a = Source(name="A", kind="html", url="https://a.test/", trust=50)
    b = Source(name="B", kind="html", url="https://b.test/", trust=50)
    db.add_all([a, b])
    db.flush()
    c1, new1 = upsert(db, a, RawContest(title="Gagnez une PS5 avec Jouets", url="https://jouets.test/jeu?utm_source=a", source_url="https://a.test/1", end_date="2099-12-31"))
    c2, new2 = upsert(db, b, RawContest(title="Jouets : gagnez une PS5 !", url="https://www.jouets.test/jeu/", source_url="https://b.test/2", end_date="2099-12-31"))
    assert new1 and not new2 and c1.id == c2.id and len(c1.sightings) == 2
    c3, new3 = upsert(db, b, RawContest(title="Jeu concours : gagnez une PS5 chez Jouets", url="https://autre.test/x", source_url="https://b.test/3", end_date="2099-12-31"))
    assert not new3 and c3.id == c1.id  # rapprochement approximatif titre + date


def test_robots_and_protections_respected(env):
    f = fetcher()
    for url, msg in [("https://blocked.test/page", "robots"), ("https://geo.test/page", "451"), ("https://captcha.test/", "anti-robot"), ("http://127.0.0.1/admin", "refusée")]:
        try:
            f.get(url)
            raise AssertionError(url)
        except FetchBlocked as e:
            assert msg in str(e)


def test_hourly_quota(env):
    f = Fetcher(max_per_hour=2, client=httpx.Client(transport=httpx.MockTransport(router)))
    f.get("https://agg.test/")
    f.get("https://agg.test/")
    try:
        f.get("https://agg.test/")
        raise AssertionError("quota")
    except FetchBlocked as e:
        assert "Quota" in str(e)


def test_rss_connector(db):
    rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
    <item><title>Concours : gagnez un voyage</title><link>https://media.test/voyage</link><description>Tentez votre chance jusqu'au 30/12/2099</description></item>
    </channel></rss>"""

    def r(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text=rss, headers={"content-type": "application/rss+xml", "etag": "abc"})

    s = Source(name="RSS", kind="rss", url="https://media.test/feed", trust=50)
    db.add(s)
    db.commit()
    job = run_scan(db, s, Fetcher(client=httpx.Client(transport=httpx.MockTransport(r))), max_enrich=0)
    assert job.status == "ok" and job.new == 1 and s.etag == "abc"


LDDJ_LIST = """<html><body>
<article class="bloc-article ombre" id="article-concours-id-382789">
 <h3 class="bloc-article-titre"><a href="jeux-concours-moulinex.fr.html" data-concours-nom="moulinex.fr">moulinex.fr</a></h3>
 <span class="bloc-article-dates"><strong>Clôture le 22/11/2099</strong></span>
 <span class="bloc-article-dates-ajout">Ajouté le 20/11/2026</span>
 <ul><li class="bloc-article-pictos-item"><img alt="Tirage au sort" src="x.png"></li></ul>
 <div class="bloc-article-no"><a href="jeu-moulinex.fr-gagnez-aspirateurs-22-novembre-2099.php">382789</a></div>
 <h4 class="bloc-article-text-titre">Cadeaux à gagner</h4><p class="bloc-article-text-text">3 aspirateurs Moulinex (599€)</p>
 <h4 class="bloc-article-text-titre">Principe</h4><p class="bloc-article-text-text">Remplir le formulaire.</p>
 <h4 class="bloc-article-text-titre">Conditions</h4><p class="bloc-article-text-text">France métropolitaine, majeurs.</p>
 <a class="toolbar-link sansdegrade" href="toconc.php?c=382789" rel="nofollow" target="_blank" onclick="_gaq.push(['_trackEvent','moulinex.fr','/votre-jeu.moulinex.fr/quiz/noel',''])">VOIR LE CONCOURS</a>
</article>
<article class="bloc-article ombre"><h3 class="bloc-article-titre"><a data-concours-nom="evil.test">evil.test</a></h3>
 <div class="bloc-article-no"><a href="jeu-evil.php">1</a></div>
 <a class="toolbar-link" href="toconc.php?c=1" onclick="_gaq.push(['_trackEvent','evil.test','/autre-domaine.com/x',''])">VOIR</a></article>
</body></html>"""


def test_lddj_connector_real_structure(db):
    calls = []

    def r(req):
        u = str(req.url)
        calls.append(u)
        if u.endswith("/robots.txt"):
            return httpx.Response(200, text="User-agent: *\nDisallow: /toconc.php\n")
        if u.endswith("/nouveaux-jeux-concours.html"):
            return httpx.Response(200, text=LDDJ_LIST, headers={"content-type": "text/html; charset=utf-8"})
        return httpx.Response(404)

    s = Source(name="LDDJ", kind="aggregator:lddj", url="https://www.ledemondujeu.com/nouveaux-jeux-concours.html", trust=75)
    db.add(s)
    db.commit()
    job = run_scan(db, s, Fetcher(client=httpx.Client(transport=httpx.MockTransport(r))), max_enrich=5)
    assert job.status == "ok", job.error
    assert job.found == 2
    c = db.query(Contest).filter(Contest.title.like("moulinex%")).one()
    assert c.url == "https://votre-jeu.moulinex.fr/quiz/noel"  # URL organisateur déduite, sans passer par toconc.php
    assert str(c.end_date) == "2099-11-22" and c.entry_method == "form"
    assert c.sightings[0].source_url.endswith("jeu-moulinex.fr-gagnez-aspirateurs-22-novembre-2099.php")
    evil = db.query(Contest).filter(Contest.title.like("evil%")).one()
    assert "ledemondujeu.com" in evil.url  # hôte incohérent avec l'organisateur : pas de devinette
    assert not any("toconc.php" in u for u in calls)  # robots.txt respecté


def test_denied_sites(client, db):
    r = client.post("/api/sources", json={"name": "JCB", "kind": "html", "url": "https://www.jeu-concours.biz/"})
    assert r.status_code == 409
    try:
        fetcher().get("https://www.toutgagner.com/x")
        raise AssertionError("doit être bloqué")
    except FetchBlocked as e:
        assert "exclu" in str(e)


def test_seed_retires_excluded_sources(db):
    from app.seed import seed

    db.add(Source(name="JCB", kind="aggregator:jeu-concours-biz", url="https://www.jeu-concours.biz/", enabled=True))
    db.add(Source(name="LDDJ", kind="aggregator:lddj", url="https://www.ledemondujeu.com/"))
    db.commit()
    seed(db)
    jcb = db.query(Source).filter_by(kind="aggregator:jeu-concours-biz").one()
    assert not jcb.enabled and "Exclu" in jcb.last_status
    assert db.query(Source).filter_by(kind="aggregator:lddj").one().url.endswith("nouveaux-jeux-concours.html")
