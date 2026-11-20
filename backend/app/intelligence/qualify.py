"""M02 : qualification d'un concours à partir de son règlement (ou de sa page à défaut).

Ordre : cache (hash du texte) → règles R0 → Ollama R1 → R2 (optionnels) → décision.
Règle d'or : aucune décision critique (gratuité, éligibilité FR) ne repose seulement sur un LLM :
une suggestion LLM non confirmée par une règle met le concours en « to_verify ».
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..admin.settings_service import get_settings_dict
from ..audit import audit
from ..db.models import AuditLog, AutomationPolicy, Contest, ContestRule, Eligibility, Organizer, Prize, utcnow
from ..i18n.geo import norm, to_eur
from ..notifications.service import notify
from ..participation.profile import get_profile, is_dom, profile_age
from ..security.sanitize import clean_text, detect_injection
from . import scoring
from .llm import OllamaClient, validate_llm_output
from .rules_extract import ANALYZER_VERSION, analyze_rules, classify_prize

log = logging.getLogger(__name__)


def content_hash(text: str) -> str:
    return hashlib.sha256(norm(text).encode()).hexdigest()


def add_rules(db: Session, contest: Contest, text: str, url: str | None, origin: str) -> tuple[ContestRule, bool]:
    """Ajoute un texte de règlement ; retourne (règle, changé?). Ne duplique pas un texte identique."""
    text = clean_text(text)
    h = content_hash(text)
    latest = contest.rules[0] if contest.rules else None
    if latest and latest.content_hash == h:
        return latest, False
    # réutilise une analyse identique d'un autre concours (même règlement publié sur plusieurs sources)
    twin = db.scalars(select(ContestRule).where(ContestRule.content_hash == h, ContestRule.analyzer_version == ANALYZER_VERSION)).first()
    rule = ContestRule(contest=contest, text=text, url=url, content_hash=h, origin=origin)
    if twin:
        rule.analysis, rule.analyzed_at, rule.analyzer_version = twin.analysis, twin.analyzed_at, twin.analyzer_version
    db.add(rule)
    db.flush()
    contest.rules.sort(key=lambda r: r.id or 0, reverse=True)
    changed = latest is not None
    if changed:
        notify(db, "rules_changed", f"Règlement modifié : {contest.title[:150]}", "Le règlement a changé, le concours a été requalifié.",
               contest.id, dedup_key=f"rules:{contest.id}:{h[:16]}")
    return rule, changed


def _llm_budget_ok(db: Session, limit: int) -> bool:
    since = datetime.combine(date.today(), datetime.min.time())
    n = db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "llm_extract", AuditLog.ts >= since)) or 0
    return n < limit


def analyze(db: Session, rule: ContestRule, force: bool = False) -> dict:
    if rule.analysis and rule.analyzer_version == ANALYZER_VERSION and not force:
        return rule.analysis
    a = analyze_rules(rule.text).to_dict()
    inj = detect_injection(rule.text)
    if inj:
        a["flags"].append("prompt_injection")
        a["injection_patterns"] = inj
    settings = get_settings_dict(db)
    needs_llm = a["free_status"] == "unknown" or a["fr_eligible"] == "unknown" or not a["end_date"] or not a["prizes"]
    if settings["llm_enabled"] and needs_llm and _llm_budget_ok(db, settings["llm_max_calls_per_day"]):
        client = OllamaClient(settings["ollama_url"])
        for model in (settings["llm_model_small"], settings["llm_model_large"]):
            data, metrics = client.extract(model, rule.text)
            audit(db, "llm", "llm_extract", contest_id=rule.contest_id, **metrics)
            if data is None:
                continue
            v = validate_llm_output(data, rule.text)
            if v:
                a["llm"] = {"model": model, "fields": v}
                break
    rule.analysis = a
    rule.analyzed_at = utcnow()
    rule.analyzer_version = ANALYZER_VERSION
    return a


def _just(field: str, decision: str, evidence: str | None, method: str) -> dict:
    return {"field": field, "decision": decision, "evidence": (evidence or None) and evidence[:500], "method": method}


def _get_or_create_organizer(db: Session, name: str, legal_id: str | None, website: str | None) -> Organizer:
    nn = norm(name)
    org = db.scalars(select(Organizer).where(Organizer.normalized_name == nn)).first()
    if org is None:
        org = Organizer(name=name, normalized_name=nn, legal_id=legal_id, website=website, country="FR" if legal_id else None)
        db.add(org)
        db.flush()
    elif legal_id and not org.legal_id:
        org.legal_id = legal_id
    return org


def qualify(db: Session, contest: Contest, force: bool = False, source_trust: int = 50) -> Contest:
    rule = contest.rules[0] if contest.rules else None
    has_rules = rule is not None and rule.origin in ("fetched", "user")
    if rule is None:
        rule, _ = add_rules(db, contest, contest.description or contest.title, contest.url, "page")
    a = analyze(db, rule, force=force)
    llm = (a.get("llm") or {}).get("fields", {})
    llm_method = f"llm:{a['llm']['model']}" if a.get("llm") else None
    just: list[dict] = []
    reasons: list[str] = []
    human = {j["field"]: j for j in (contest.justifications or []) if j.get("method") == "human"}
    settings = get_settings_dict(db)
    profile = get_profile(db)

    contest.language = contest.language or a.get("language")

    # --- gratuité (critique)
    free_status, free_verified = a["free_status"], a["free_status"] != "unknown"
    if "free" in human:
        free_status, free_verified = human["free"]["decision"], True
        just.append(human["free"])
    elif a["free_status"] != "unknown":
        just.append(_just("free", a["free_status"], a["free"]["evidence"], "rule"))
    elif llm.get("free_status"):
        free_status, free_verified = llm["free_status"], False
        just.append(_just("free", llm["free_status"], llm["free_quote"], llm_method))
        reasons.append("Gratuité suggérée par l'IA, à confirmer")
    else:
        reasons.append("Gratuité non établie")

    # --- éligibilité FR (critique)
    allowed, excluded, fr = a["countries_allowed"], a["countries_excluded"], a["fr_eligible"]
    elig_verified = fr != "unknown"
    elig_method = "rule"
    elig_evidence = a["eligibility"]["evidence"] if a.get("eligibility") else None
    if "eligibility" in human:
        fr, elig_verified, elig_method, elig_evidence = human["eligibility"]["decision"], True, "human", human["eligibility"].get("evidence")
        just.append(human["eligibility"])
    elif fr != "unknown":
        just.append(_just("eligibility", fr, elig_evidence, "rule"))
    elif llm.get("countries_allowed") is not None:
        allowed, excluded = llm["countries_allowed"], llm["countries_excluded"]
        s = set(allowed)
        fr = "no" if "FR" in excluded else ("yes" if s & {"FR", "WORLD", "EU", "EEA"} else ("no" if s else "unknown"))
        elig_verified, elig_method, elig_evidence = False, llm_method, llm["eligibility_quote"]
        just.append(_just("eligibility", fr, elig_evidence, llm_method))
        reasons.append("Éligibilité suggérée par l'IA, à confirmer")
    else:
        reasons.append("Éligibilité depuis la France non établie")
    if fr == "yes" and a.get("metropole_only") and is_dom(profile):
        fr = "no"
        just.append(_just("eligibility", "no", "Réservé à la France métropolitaine ; votre code postal est en outre-mer", "rule"))

    # --- âge
    min_age = a["min_age"] or llm.get("min_age")
    age = profile_age(profile)
    if min_age:
        just.append(_just("age", f">= {min_age} ans", a["age"]["evidence"] if a.get("age") else None, "rule" if a["min_age"] else llm_method))

    # --- dates
    def _d(v: str | None) -> date | None:
        try:
            return date.fromisoformat(v) if v else None
        except ValueError:
            return None

    start, end = _d(a["start_date"]), _d(a["end_date"])
    if end:
        just.append(_just("dates", f"{start or '?'} → {end}", a["dates"]["evidence"], "rule"))
    elif llm.get("end_date"):
        start, end = _d(llm.get("start_date")), _d(llm.get("end_date"))
        just.append(_just("dates", f"{start or '?'} → {end}", llm.get("dates_quote"), llm_method))
    contest.start_date = start or contest.start_date
    contest.end_date = end or contest.end_date

    # --- organisateur
    org_name = a["organizer_name"] or llm.get("organizer")
    if org_name:
        from urllib.parse import urlsplit

        contest.organizer = _get_or_create_organizer(db, org_name, a["organizer_legal_id"], f"https://{urlsplit(contest.url).hostname}")
        just.append(_just("organizer", org_name, a["organizer"]["evidence"] if a.get("organizer") else None, "rule" if a["organizer_name"] else llm_method))

    # --- lots
    prizes = a["prizes"] or [dict(p, category=classify_prize(p["name"]), fees_note=None, evidence=None) for p in llm.get("prizes", [])]
    if prizes:
        contest.prizes.clear()
        for p in prizes:
            contest.prizes.append(Prize(name=p["name"], category=p["category"], quantity=p["quantity"] or 1, value=p["value"],
                                        currency=p["currency"], value_eur=to_eur(p["value"], p["currency"]), fees_note=p.get("fees_note")))
        db.flush()
    pz = [{"value_eur": p.value_eur, "quantity": p.quantity, "category": p.category, "fees": p.fees_note} for p in contest.prizes]
    total = sum((p["value_eur"] or 0) * (p["quantity"] or 1) for p in pz) or None
    contest.total_prize_value_eur = round(total, 2) if total else contest.total_prize_value_eur
    if contest.prizes:
        best = max(contest.prizes, key=lambda p: p.value_eur or 0)
        contest.category = best.category if best.category != "other" else (contest.category or "other")
        contest.prize_summary = (contest.prize_summary or best.name)[:500]

    # --- éligibilité persistée
    if contest.eligibility is None:
        contest.eligibility = Eligibility()
    e = contest.eligibility
    e.min_age, e.countries_allowed, e.countries_excluded = min_age, allowed, excluded
    e.fr_eligible, e.evidence, e.method = fr, elig_evidence, elig_method
    contest.free_status, contest.fr_eligible = free_status, fr

    # --- signaux
    # drapeaux posés par l'exploration des pages (captcha, page inaccessible, enrichi) : conservés
    persistent = {f for f in (contest.flags or []) if f in ("captcha", "page_inaccessible", "enriched", "login_required")}
    flags = sorted(set(a["flags"]) | persistent)
    contest.flags = flags
    from .game_type import classify_game_type

    contest.game_type = classify_game_type(" ".join(filter(None, [contest.title, contest.description, rule.text])), contest.url, flags) or contest.game_type
    suspicious = list(a["suspicious_signals"])
    if "prompt_injection" in flags:
        suspicious.append("contenu tentant de manipuler l'analyse (injection)")
    if suspicious:
        just.append(_just("suspicious", "; ".join(suspicious), None, "rule"))
    if a["automation_forbidden"] is not None:
        just.append(_just("automation", "interdite" if a["automation_forbidden"] else "autorisée", a["automation"]["evidence"], "rule"))
    if a["claim_days"]:
        just.append(_just("claim", f"{a['claim_days']} jours pour réclamer", a["claim"]["evidence"], "rule"))
    if a["entry_limit"]:
        just.append(_just("entry_limit", a["entry_period"] or "", a["entry_limit"], "rule"))
        contest.entry_limit = a["entry_limit"][:200]
    if a["ambiguities"]:
        reasons.extend(a["ambiguities"])
    if not has_rules:
        reasons.append("Règlement inaccessible ou non trouvé")

    # --- politique d'automatisation
    if contest.policy is None:
        contest.policy = AutomationPolicy()
    pol = contest.policy
    pol.automation_forbidden_by_rules = a["automation_forbidden"]
    pol.period = a["entry_period"] or "once"
    pol_reasons = []
    if "captcha" in flags:
        pol_reasons.append("CAPTCHA : action humaine obligatoire")
    if "login_required" in flags:
        pol_reasons.append("Connexion à un compte requise")
    if "social_entry" in flags:
        pol_reasons.append("Participation via réseau social")
    if a["automation_forbidden"]:
        pol_reasons.append("Le règlement interdit les moyens automatisés")
    if not a["automation_allowed_explicit"] and "automation" not in human:
        pol_reasons.append("Automatisation non explicitement autorisée par le règlement")
    if contest.entry_method in ("mail", "sms"):
        pol_reasons.append("Participation par courrier/SMS")
    if pol_reasons:
        pol.mode = "manual" if any(r.startswith(("CAPTCHA", "Connexion", "Participation via", "Participation par")) for r in pol_reasons) else "semi"
    else:
        pol.mode = "auto"
    pol.reasons = pol_reasons
    contest.participation_mode = pol.mode

    # --- scores
    trust = contest.sightings[0].source.trust if contest.sightings and contest.sightings[0].source else source_trust
    contest.reliability_score, rb = scoring.reliability(
        url=contest.url, has_rules=has_rules, free_status=free_status, free_verified=free_verified, fr_eligible=fr,
        elig_verified=elig_verified, organizer_name=org_name, organizer_legal_id=a["organizer_legal_id"], start=start, end=contest.end_date,
        prizes=pz, suspicious=suspicious, source_trust=trust)
    winners = sum(p["quantity"] or 1 for p in pz)
    cat_w = settings["interest_categories"].get(contest.category or "other", 5)
    contest.interest_score, ib = scoring.interest(
        prizes=pz, category_weight=cat_w, personal=contest.personal_interest, entry_method=contest.entry_method, flags=flags,
        winners=winners, fees=any(p["fees"] for p in pz), delivery_fr=fr == "yes", total_value_eur=contest.total_prize_value_eur)
    contest.score_breakdown = {"reliability": rb, "interest": ib}
    from .automatability import apply as apply_automatability

    apply_automatability(contest, rule.text if rule is not None else "")

    # --- statut
    today = date.today()
    prev = contest.status
    if contest.status in ("participated", "archived"):
        pass
    elif contest.end_date and contest.end_date < today:
        contest.status = "expired"
    elif free_status == "purchase_required":
        contest.status, reasons = "rejected", ["Achat obligatoire sans voie gratuite"]
    elif fr == "no":
        contest.status, reasons = "rejected", ["Non accessible depuis la France"]
    elif min_age and age is not None and age < min_age:
        contest.status, reasons = "rejected", [f"Âge minimum {min_age} ans"]
    elif len(suspicious) >= 2 or "demande de données bancaires" in suspicious:
        contest.status = "to_verify"
        reasons.insert(0, "Signaux d'arnaque : " + "; ".join(suspicious))
    elif free_verified and elig_verified and free_status in ("free", "free_alternative") and fr == "yes" and not a["ambiguities"]:
        contest.status = "qualified"
    else:
        contest.status = "to_verify"
    contest.needs_human_reason = "; ".join(dict.fromkeys(reasons)) if contest.status == "to_verify" else (
        "; ".join(reasons) if contest.status == "rejected" else None)
    contest.justifications = just
    contest.qualified_at = utcnow()
    if contest.status == "to_verify" and prev != "to_verify":
        notify(db, "to_verify", f"À vérifier : {contest.title[:150]}", contest.needs_human_reason, contest.id, dedup_key=f"verify:{contest.id}:{rule.content_hash[:12]}")
    if contest.status == "qualified" and prev != "qualified":
        notify(db, "new_contest", f"Nouveau concours qualifié : {contest.title[:150]}", contest.prize_summary, contest.id, dedup_key=f"new:{contest.id}")
    audit(db, "intelligence", "qualify", contest_id=contest.id, status=contest.status, reliability=contest.reliability_score)
    return contest
