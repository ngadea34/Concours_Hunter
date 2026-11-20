"""Import volontaire par l'utilisateur (catégorie 5) : liste collée, fichier CSV, ou page partagée depuis le navigateur.

Les lignes sont enregistrées sans requête réseau ; le planificateur lira ensuite la page et le règlement de
l'organisateur au rythme habituel (enrich_backlog). Une adresse d'un site dont la lecture automatique est interdite
(catégorie 6) n'est jamais lue : on explique comment ajouter la page de l'organisateur à la place.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date

from sqlalchemy.orm import Session

from ..audit import audit
from ..intelligence.qualify import qualify
from ..security.sanitize import is_safe_http_url
from .base import RawContest
from .pipeline import upsert
from .policy import aggregator_profile, denial_reason

MAX_LINES = 300
_URL = re.compile(r"https?://[^\s;,<>\"']+")
_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
HEADER_ALIASES = {"url": ("url", "lien", "adresse", "link"), "title": ("title", "titre", "nom", "name"),
                  "end_date": ("end_date", "fin", "cloture", "clôture", "date de fin", "date_fin"),
                  "prize": ("prize", "lot", "lots", "dotation"), "organizer": ("organizer", "organisateur", "marque")}


def _date(s: str | None) -> str | None:
    if not s:
        return None
    m = _DATE.search(s)
    if not m:
        return None
    try:
        if m.group(1):
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        return date(int(m.group(6)), int(m.group(5)), int(m.group(4))).isoformat()
    except ValueError:
        return None


def parse(text: str) -> list[dict]:
    """CSV avec en-tête (url, titre, fin, lot, organisateur ; séparateur , ou ;) ou une adresse par ligne."""
    text = (text or "").strip()
    if not text:
        return []
    first = text.splitlines()[0].lower()
    rows: list[dict] = []
    if not _URL.search(first) and any(a in first for a in HEADER_ALIASES["url"]):
        delim = ";" if first.count(";") >= first.count(",") else ","
        reader = csv.DictReader(io.StringIO(text), delimiter=delim)
        cols = {}
        for h in reader.fieldnames or []:
            key = (h or "").strip().lower()
            for field, aliases in HEADER_ALIASES.items():
                if key in aliases:
                    cols[h] = field
        for i, r in enumerate(reader, start=2):
            row = {cols[k]: (v or "").strip() for k, v in r.items() if k in cols}
            row["line"] = i
            rows.append(row)
    else:
        for i, line in enumerate(text.splitlines(), start=1):
            m = _URL.search(line)
            if not line.strip():
                continue
            rest = line.replace(m.group(0), " ").strip(" ;,\t-|") if m else ""
            rows.append({"line": i, "url": m.group(0).rstrip(".)") if m else "", "title": re.sub(_DATE, "", rest).strip(" ;,\t-|") or None,
                         "end_date": rest})
    return rows[:MAX_LINES]


def import_rows(db: Session, rows: list[dict], origin: str = "user_import") -> dict:
    created, existing, skipped = [], [], []
    for r in rows:
        url = (r.get("url") or "").strip()
        if not url or not is_safe_http_url(url):
            skipped.append({"line": r.get("line"), "url": url, "reason": "Adresse absente ou invalide (http/https public uniquement)"})
            continue
        if denial_reason(url):
            prof = aggregator_profile(url) or {}
            skipped.append({"line": r.get("line"), "url": url, "reason": f"{prof.get('name', 'Ce site')} n'autorise pas la lecture automatique. "
                            + (prof.get("how_to") or "Ajoutez plutôt la page du site de l'organisateur.")})
            continue
        raw = RawContest(title=(r.get("title") or url)[:500], url=url, source_url=f"{origin}:{url}"[:1000], detail_url=url,
                         end_date=_date(r.get("end_date")), prize=r.get("prize") or None, organizer=r.get("organizer") or None,
                         extra={"origin": origin})
        contest, is_new = upsert(db, None, raw)
        if is_new:
            qualify(db, contest)
            created.append(contest.id)
        else:
            existing.append(contest.id)
    audit(db, "user", "import", origin=origin, created=len(created), existing=len(existing), skipped=len(skipped))
    db.commit()
    return {"created": created, "existing": existing, "skipped": skipped}
