"""M11 : participation automatique via Playwright — uniquement si TOUTES les conditions sont réunies :

1. politique du concours = auto (règlement autorisant explicitement l'automatisation, pas de CAPTCHA, pas de connexion) ;
2. consentement « auto_participation » donné par l'utilisateur ;
3. aucun CAPTCHA détecté au moment du remplissage ;
4. tous les champs requis remplis.

Sinon : bascule en « awaiting_human » (l'utilisateur termine via l'extension / l'UI).
Chaque domaine a un profil navigateur isolé (data/browser/<domaine>). Le remplissage réutilise
exactement la logique de l'extension (extension/lib/fill-core.js + content/filler.js).
"""
from __future__ import annotations

import base64
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from ..config import ROOT, get_settings
from ..db.models import BrowserSession, Participation, utcnow
from ..notifications.service import notify
from .profile import get_consents
from .service import add_proof, mark, prefill

log = logging.getLogger(__name__)
EXT = ROOT / "extension"
CHROMIUM_FALLBACK = "/opt/pw-browsers/chromium"


def _scripts() -> str:
    return (EXT / "lib" / "fill-core.js").read_text(encoding="utf-8") + "\n" + (EXT / "content" / "filler.js").read_text(encoding="utf-8")


def _profile_dir(db: Session, url: str) -> Path:
    host = re.sub(r"[^a-z0-9.-]", "_", (urlsplit(url).hostname or "unknown").lower())
    d = get_settings().data_dir / "browser" / host
    d.mkdir(parents=True, exist_ok=True)
    bs = db.query(BrowserSession).filter_by(domain=host).first()
    if bs is None:
        db.add(BrowserSession(domain=host, profile_dir=str(d), last_used_at=utcnow()))
    else:
        bs.last_used_at = utcnow()
    return d


def can_auto(db: Session, p: Participation) -> tuple[bool, str]:
    if p.mode != "auto" or (p.contest.policy and p.contest.policy.mode != "auto"):
        return False, "politique non automatique"
    if not get_consents(db)["auto_participation"]:
        return False, "consentement absent"
    if set(p.contest.flags or []) & {"captcha", "login_required", "social_entry"}:
        return False, "CAPTCHA / connexion / réseau social"
    return True, "ok"


def run_auto(db: Session, p: Participation, headless: bool = True, allow_private_hosts: bool = False) -> Participation:
    ok, why = can_auto(db, p)
    if not ok:
        p.status = "awaiting_human"
        db.commit()
        return p
    from playwright.sync_api import sync_playwright

    from ..security.sanitize import is_safe_http_url

    url = p.contest.url
    if not allow_private_hosts and not is_safe_http_url(url):
        return mark(db, p, "failed", error="URL refusée")
    data = prefill(db, p)
    launch: dict = {"headless": headless}
    if os.path.exists(CHROMIUM_FALLBACK) and not os.environ.get("CH_USE_PLAYWRIGHT_BROWSER"):
        launch["executable_path"] = CHROMIUM_FALLBACK
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(_profile_dir(db, url)), accept_downloads=False, **launch)
        try:
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.add_script_tag(content=_scripts())
            res = page.evaluate("p => window.__chFill(p)", data)
            if res.get("captcha"):
                p.status = "awaiting_human"
                notify(db, "to_validate", f"CAPTCHA détecté : {p.contest.title[:150]}", "À terminer par vous.", p.contest_id, dedup_key=f"captcha:{p.id}")
                db.commit()
                return p
            if res.get("unrecognized"):
                p.status = "awaiting_human"
                notify(db, "to_validate", f"Champs non reconnus : {p.contest.title[:150]}", "Complétez et soumettez vous-même.", p.contest_id, dedup_key=f"unrec:{p.id}")
                db.commit()
                return p
            form_btn = page.locator("form button[type=submit], form input[type=submit]").first
            if form_btn.count() == 0:
                p.status = "awaiting_human"
                db.commit()
                return p
            form_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            png = page.screenshot(full_page=True)
            if get_consents(db)["store_proofs"]:
                add_proof(db, p, "screenshot", "data:image/png;base64," + base64.b64encode(png).decode(), "Capture après soumission automatique")
            return mark(db, p, "submitted", note=f"Soumission automatique ({res.get('filled', 0)} champs)")
        except Exception as e:  # noqa: BLE001
            log.exception("Participation auto %s", p.id)
            return mark(db, p, "failed", error=f"Erreur de soumission : {e}"[:500])
        finally:
            ctx.close()
