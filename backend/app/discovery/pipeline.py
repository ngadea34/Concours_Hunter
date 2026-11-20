"""Chaîne de découverte : connecteur → normalisation → déduplication → enrichissement → règlement → qualification."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..admin.settings_service import get_settings_dict
from ..audit import audit
from ..db.models import Answer, Contest, ContestSighting, ScanJob, Source, utcnow
from ..i18n.geo import norm
from ..intelligence.qualify import add_rules, qualify
from ..intelligence.rules_extract import detect_language
from ..security.sanitize import canonical_url, html_to_text
from .base import RawContest, load_connectors
from .fetcher import Fetcher, FetchBlocked

log = logging.getLogger(__name__)

RULES_LINK = re.compile(r"r[eè]glement|conditions (du jeu|de participation)|official rules|terms and conditions|t&c|bases (legales|del concurso)|teilnahmebedingungen|regolamento|regulamento|actievoorwaarden|spelregels", re.I)
PARTICIPATE_LINK = re.compile(r"particip|jouer|je joue|tenter ma chance|acc[eé]der au (jeu|concours)|enter|play|participar|teilnehmen|partecipa|deelnemen|site du jeu|voir le jeu", re.I)
QA_RX = re.compile(r"(?:question|q)\s*(?:\d+)?\s*[:\-–]\s*(?P<q>[^\n]{5,300}?)\s*(?:\n|\s)+(?:r[ée]ponse|answer|respuesta|antwort|risposta|resposta|antwoord|r)\s*[:\-–]\s*(?P<a>[^\n]{1,200})", re.I)
STOPWORDS = {"jeu", "concours", "gagnez", "gagner", "tentez", "de", "la", "le", "les", "un", "une", "des", "du", "a", "et", "pour", "win", "the", "giveaway", "sweepstakes", "contest", "votre", "vos", "avec", "chez", "sur", "en", "au", "aux", "your", "with", "at", "on", "jeu-concours", "remportez", "offert", "offre"}


def key_tokens(title: str) -> list[str]:
    return sorted({t for t in re.findall(r"[a-z0-9]+", norm(title)) if t not in STOPWORDS and len(t) > 1})


def fingerprint(title: str, domain: str | None) -> str:
    toks = key_tokens(title)
    return hashlib.sha256((" ".join(toks) + "|" + (domain or "")).encode()).hexdigest()


def _domain(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def find_duplicate(db: Session, raw: RawContest, canon: str, fp: str) -> Contest | None:
    c = db.scalars(select(Contest).where(Contest.canonical_url == canon, Contest.merged_into_id.is_(None))).first()
    if c:
        return c
    c = db.scalars(select(Contest).where(Contest.fingerprint == fp, Contest.merged_into_id.is_(None))).first()
    if c:
        return c
    # rapprochement approximatif : même date de fin et titres très proches (sources différentes)
    if raw.end_date:
        try:
            end = date.fromisoformat(raw.end_date)
        except ValueError:
            return None
        for cand in db.scalars(select(Contest).where(Contest.end_date == end, Contest.merged_into_id.is_(None)).limit(200)):
            a_, b_ = " ".join(key_tokens(raw.title)), " ".join(key_tokens(cand.title))
            if min(len(a_.split()), len(b_.split())) >= 2 and fuzz.token_set_ratio(a_, b_) >= 90:
                return cand
    return None


def upsert(db: Session, source: Source | None, raw: RawContest) -> tuple[Contest, bool]:
    canon = canonical_url(raw.url)
    fp = fingerprint(raw.title, _domain(raw.url) if source is None or _domain(raw.url) != _domain(source.url) else None)
    c = find_duplicate(db, raw, canon, fp)
    created = c is None
    if c is None:
        c = Contest(title=raw.title.strip()[:500], url=raw.url, canonical_url=canon, fingerprint=fp, description=raw.description,
                    language=raw.language or detect_language((raw.title or "") + " " + (raw.description or "")),
                    prize_summary=(raw.prize or None) and raw.prize[:500], entry_method=raw.entry_method)
        db.add(c)
    else:
        # l'URL la plus proche de l'organisateur l'emporte sur celle d'un agrégateur
        if source and _domain(c.url) == _domain(source.url) and _domain(raw.url) != _domain(source.url):
            c.url, c.canonical_url = raw.url, canon
        if raw.description and len(raw.description or "") > len(c.description or ""):
            c.description = raw.description
        c.prize_summary = c.prize_summary or raw.prize
    if raw.end_date and not c.end_date:
        try:
            c.end_date = date.fromisoformat(raw.end_date)
        except ValueError:
            pass
    db.flush()
    sid = source.id if source else None
    exists = db.scalars(select(ContestSighting).where(ContestSighting.contest_id == c.id, ContestSighting.source_id == sid,
                                                      ContestSighting.source_url == raw.source_url)).first()
    if exists:
        exists.seen_at = utcnow()
    else:
        db.add(ContestSighting(contest_id=c.id, source_id=sid, source_url=raw.source_url, raw={"title": raw.title, "end_date": raw.end_date, "prize": raw.prize}))
    for q, a in raw.answers:
        record_answer(db, c, q, a, source.name if source else "page")
    return c, created


def record_answer(db: Session, contest: Contest, question: str, answer: str, source_name: str) -> Answer:
    qn = norm(question)[:500]
    an = norm(answer)
    existing = db.scalars(select(Answer).where(Answer.contest_id == contest.id, Answer.question_norm == qn)).all()
    for e in existing:
        if norm(e.answer) == an:
            if source_name not in e.source.split(", "):
                e.source = f"{e.source}, {source_name}"[:200]
                e.votes += 1
                e.verified = e.votes >= 2  # vérification indépendante : deux sources concordantes
                e.confidence = min(0.95, 0.5 + 0.2 * e.votes)
            return e
    conflict = bool(existing)
    a = Answer(contest_id=contest.id, question=question[:2000], question_norm=qn, answer=answer[:2000], source=source_name,
               verified=False, confidence=0.3 if conflict else 0.5)
    db.add(a)
    db.flush()
    return a


def verify_answers_against_page(db: Session, contest: Contest, page_text: str) -> None:
    """Une réponse retrouvée littéralement sur la page de l'organisateur est considérée vérifiée."""
    pt = norm(page_text)
    for a in contest.answers:
        if not a.verified and len(norm(a.answer)) >= 3 and norm(a.answer) in pt:
            a.verified, a.confidence = True, max(a.confidence, 0.8)
            a.source = (a.source + ", page organisateur")[:200]


def enrich(db: Session, fetcher: Fetcher, contest: Contest, raw: RawContest, source: Source | None) -> None:
    """Lit la fiche (agrégateur) puis la page organisateur et son règlement, si autorisé."""
    page_url = raw.detail_url or contest.url
    contest.flags = sorted(set(contest.flags or []) | {"enriched"})
    try:
        res = fetcher.get(page_url)
    except (FetchBlocked, Exception) as e:  # noqa: BLE001
        contest.flags = sorted(set(contest.flags or []) | {"page_inaccessible"})
        log.info("Fiche inaccessible %s : %s", page_url, e)
        return
    soup = BeautifulSoup(res.text, "lxml") if "<" in res.text[:2000] else None
    text = html_to_text(res.text) if soup else res.text
    for m in QA_RX.finditer(text):
        record_answer(db, contest, m.group("q").strip(), m.group("a").strip(), source.name if source else "page")
    rules_url = raw.rules_url
    if soup is not None:
        src_dom = _domain(page_url)
        for a in soup.select("a[href]"):
            label = a.get_text(" ", strip=True) + " " + (a.get("title") or "")
            href = urljoin(res.url, a["href"])
            if not href.startswith("http"):
                continue
            if not rules_url and RULES_LINK.search(label):
                rules_url = href
            if source and _domain(href) != src_dom and PARTICIPATE_LINK.search(label) and _domain(contest.url) == _domain(source.url):
                contest.url, contest.canonical_url = href, canonical_url(href)
    if not contest.description or len(contest.description) < 200:
        contest.description = text[:5000]
    # page organisateur (si différente de la fiche) : vérifie les réponses, cherche le règlement
    if _domain(contest.url) != _domain(page_url):
        try:
            org = fetcher.get(contest.url)
            org_text = html_to_text(org.text)
            verify_answers_against_page(db, contest, org_text)
            if not rules_url:
                osoup = BeautifulSoup(org.text, "lxml")
                for a in osoup.select("a[href]"):
                    if RULES_LINK.search(a.get_text(" ", strip=True)):
                        rules_url = urljoin(org.url, a["href"])
                        break
            if re.search(r"g-recaptcha|h-captcha|cf-turnstile|captcha", org.text, re.I):
                contest.flags = sorted(set(contest.flags or []) | {"captcha"})
        except Exception as e:  # noqa: BLE001
            log.info("Page organisateur inaccessible %s : %s", contest.url, e)
    if rules_url:
        try:
            r = fetcher.get(rules_url)
            rtext = html_to_text(r.text) if "<" in r.text[:2000] else r.text
            if len(rtext) > 300:
                add_rules(db, contest, rtext, rules_url, "fetched")
        except Exception as e:  # noqa: BLE001
            log.info("Règlement inaccessible %s : %s", rules_url, e)


def run_scan(db: Session, source: Source, fetcher: Fetcher | None = None, max_enrich: int | None = None, job: ScanJob | None = None) -> ScanJob:
    settings = get_settings_dict(db)
    own = fetcher is None
    fetcher = fetcher or Fetcher(max_per_hour=settings["max_requests_per_domain_per_hour"])
    job = job or ScanJob(source_id=source.id, kind="scan", status="running")
    prev = db.scalars(select(ScanJob).where(ScanJob.source_id == source.id).order_by(ScanJob.id.desc())).first()
    if prev and prev.status == "interrupted" and prev.checkpoint:
        job.checkpoint = dict(prev.checkpoint)  # reprise après interruption : on saute ce qui a déjà été traité
    db.add(job)
    db.commit()
    max_enrich = 20 if max_enrich is None else max_enrich
    enriched = 0
    try:
        cls = load_connectors().get(source.kind)
        if cls is None:
            raise ValueError(f"Connecteur inconnu : {source.kind}")
        conn = cls(source, fetcher)
        done = set(job.checkpoint.get("done", []))
        for raw in conn.discover():
            if raw.url in done:
                continue
            job.found += 1
            contest, created = upsert(db, source, raw)
            if created:
                job.new += 1
            has_rules = any(r.origin in ("fetched", "user") for r in contest.rules)
            if not has_rules and "enriched" not in (contest.flags or []) and enriched < max_enrich:
                enrich(db, fetcher, contest, raw, source)
                enriched += 1
            if created or contest.status in ("new", "to_verify"):
                qualify(db, contest, source_trust=source.trust)
            done.add(raw.url)
            job.checkpoint = {"done": sorted(done)[-500:]}
            db.commit()
        job.status = "ok"
        source.last_status = source.last_status if source.last_status and "repli" in source.last_status else "ok"
    except FetchBlocked as e:
        db.rollback()
        job.status, job.error = "skipped", str(e)
        source.last_status = f"bloqué : {e}"[:200]
    except Exception as e:  # noqa: BLE001
        db.rollback()
        log.exception("Scan %s", source.name)
        job.status, job.error = "error", str(e)[:1000]
        source.last_status = f"erreur : {e}"[:200]
    finally:
        job.finished_at = utcnow()
        source.last_scan_at = utcnow()
        audit(db, "discovery", "scan", source=source.name, status=job.status, found=job.found, new=job.new)
        db.commit()
        if own:
            fetcher.close()
    return job


def add_contest_by_url(db: Session, url: str, title: str | None, fetcher: Fetcher | None = None) -> Contest:
    raw = RawContest(title=title or url, url=url, source_url=url, detail_url=url)
    contest, _ = upsert(db, None, raw)
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    try:
        enrich(db, fetcher, contest, raw, None)
        if not title and contest.description:
            first = contest.description.strip().split("\n")[0][:200]
            if len(first) > 8:
                contest.title = first
    finally:
        if own:
            fetcher.close()
    qualify(db, contest)
    db.commit()
    return contest


def enrich_backlog(db: Session, fetcher: Fetcher, limit: int = 20) -> int:
    """Complète progressivement les concours encore sans règlement (pas seulement ceux du dernier scan)."""
    from sqlalchemy import or_

    today = date.today()
    n = 0
    cands = db.scalars(select(Contest).where(Contest.status.in_(("new", "to_verify")), Contest.merged_into_id.is_(None),
                                             or_(Contest.end_date.is_(None), Contest.end_date >= today))
                       .order_by(Contest.end_date.asc().nulls_last()).limit(limit * 5))
    for c in cands:
        if n >= limit or fetcher.stopped.is_set():
            break
        if "enriched" in (c.flags or []) or any(r.origin in ("fetched", "user") for r in c.rules):
            continue
        detail = c.sightings[0].source_url if c.sightings else c.url
        raw = RawContest(title=c.title, url=c.url, source_url=detail, detail_url=detail)
        try:
            enrich(db, fetcher, c, raw, c.sightings[0].source if c.sightings else None)
            qualify(db, c)
            db.commit()
        except FetchBlocked:
            db.rollback()
            break
        n += 1
    return n
