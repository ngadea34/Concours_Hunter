"""Scores de fiabilité et d'intérêt (/100). Ce ne sont JAMAIS des probabilités de gain."""
from __future__ import annotations

import math
import re
from datetime import date
from urllib.parse import urlsplit

SUSPICIOUS_HOSTS = re.compile(r"(blogspot|wixsite|weebly|sites\.google|bit\.ly|tinyurl|linktr\.ee|000webhost|\.xyz$|\.top$|\.click$|\.icu$)", re.I)


def reliability(*, url: str, has_rules: bool, free_status: str, free_verified: bool, fr_eligible: str, elig_verified: bool,
                organizer_name: str | None, organizer_legal_id: str | None, start: date | None, end: date | None,
                prizes: list[dict], suspicious: list[str], source_trust: int) -> tuple[int, dict]:
    b: dict[str, int] = {}
    b["organisateur"] = (8 if organizer_name else 0) + (7 if organizer_legal_id else 0)
    b["reglement"] = 20 if has_rules else 0
    b["gratuite"] = {"free": 20, "free_alternative": 14}.get(free_status, 0)
    if not free_verified:
        b["gratuite"] = int(b["gratuite"] * 0.75)
    b["eligibilite"] = 20 if fr_eligible == "yes" and elig_verified else (15 if fr_eligible == "yes" else 0)
    dates_ok = end is not None and (start is None or start <= end) and (end - (start or end)).days <= 400
    b["dates"] = 10 if dates_ok else (4 if end else 0)
    vals = [p.get("value_eur") for p in prizes if p.get("value_eur")]
    b["lots"] = 5 if prizes and (not vals or max(vals) < 200_000) else 0
    host = urlsplit(url).hostname or ""
    sec = 4 if url.startswith("https://") else 0
    sec += 0 if SUSPICIOUS_HOSTS.search(host) else 3
    sec += round(3 * source_trust / 100)
    b["source"] = sec
    total = sum(b.values())
    if suspicious:
        b["penalite_signaux_suspects"] = -min(40, 15 * len(suspicious))
        total += b["penalite_signaux_suspects"]
    return max(0, min(100, total)), b


ENTRY_MINUTES = {"form": 2, "instant": 1, "email": 3, "social": 4, "sms": 2, "mail": 15, "quiz": 4, None: 3}


def interest(*, prizes: list[dict], category_weight: int, personal: int | None, entry_method: str | None, flags: list[str],
             winners: int, fees: bool, delivery_fr: bool, total_value_eur: float | None) -> tuple[int, dict]:
    b: dict[str, int] = {}
    v = total_value_eur or 0
    b["valeur"] = min(30, round(30 * math.log10(1 + v) / math.log10(1 + 5000))) if v > 0 else 5
    w = personal if personal is not None else category_weight
    b["interet_personnel"] = round(20 * max(0, min(10, w)) / 10)
    minutes = ENTRY_MINUTES.get(entry_method, 3) + (3 if "login_required" in flags else 0) + (2 if "captcha" in flags else 0)
    b["temps"] = max(0, 15 - 2 * minutes)
    b["gagnants"] = min(15, round(5 * math.log10(1 + winners) * 2)) if winners else 3
    complexity = sum(1 for f in ("login_required", "captcha", "social_entry") if f in flags)
    b["complexite"] = max(0, 10 - 4 * complexity)
    b["frais"] = 0 if fees else 5
    b["livraison"] = 5 if delivery_fr else 2
    return max(0, min(100, sum(b.values()))), b


def estimated_minutes(entry_method: str | None, flags: list[str]) -> int:
    return ENTRY_MINUTES.get(entry_method, 3) + (3 if "login_required" in flags else 0) + (2 if "captcha" in flags else 0)
