"""Analyse d'une offre ou d'un règlement d'opération commerciale (agent INTELLIGENCE, déterministe).

Chaque information retenue porte l'extrait du texte qui la justifie. Ce qui n'est pas écrit n'est jamais supposé :
cumul non précisé = non cumulable dans les calculs ; enseignes non précisées = à vérifier.
"""
from __future__ import annotations

import re
from datetime import date

from ..i18n.geo import norm
from ..intelligence.rules_extract import DATE_RX, _to_float, analyze_rules, parse_dates_in, sentences
from .products import find_eans, find_retailers, quantity

KIND_PATTERNS: list[tuple[str, str]] = [
    ("full_refund", r"100\s?% (rembourse|offert)|integralement rembourse|rembourse a 100|satisfait ou rembourse|totalement rembourse|"
                    r"remboursement integral|gratuit apres remboursement|offre decouverte.{0,40}rembourse"),
    ("purchase_game", r"jeu.{0,20}avec (obligation d.)?achat|achetez et (tentez|jouez)|tentez de gagner.{0,60}achat|ticket gagnant|"
                      r"pour participer.{0,80}(achat|acheter)|instants? gagnants?.{0,80}(achat|code)|code (unique )?(sous|dans|a l.interieur)"),
    ("partial_refund", r"offre de remboursement|remboursement differe|\d+(?:[.,]\d+)?\s?(€|euros?) rembourses?|rembourse (a hauteur|jusqu)|"
                       r"\d{1,2}\s?% rembourse|odr\b"),
    ("voucher", r"bon d.achat (offert )?apres achat|bon de reduction (offert|envoye) apres"),
    ("receipt_offer", r"(sur|avec) (presentation|envoi) (du|de votre) ticket de caisse|participation avec preuve d.achat"),
    ("code_offer", r"qr ?code|code promotionnel|code a saisir|code imprime"),
]
DOCS: list[tuple[str, str]] = [
    ("receipt", r"ticket de caisse|preuve d.achat|facture"),
    ("barcode", r"code[- ]barres?|code ean"),
    ("barcode_original", r"(original|decoupe).{0,30}code[- ]barres|code[- ]barres.{0,30}(original|decoupe)"),
    ("packaging", r"photo(graphie)? (du|de l.|de votre) (produit|emballage|paquet)|emballage"),
    ("qr", r"qr ?code"),
    ("iban", r"\b(rib|iban|bic)\b|coordonnees bancaires"),
    ("form", r"formulaire"),
    ("payment_proof", r"releve (bancaire|de compte)|justificatif de paiement"),
]
CHANNELS: list[tuple[str, str]] = [
    ("postal", r"par courrier|par voie postale|(envoyez|adressez).{0,60}(a l.adresse|cedex|bp \d)|timbre"),
    ("platform", r"plateforme|sur le site (dedie|de l.operation)|rendez-vous sur|connectez-vous sur|www\.|https?://"),
    ("email", r"par (e-?mail|courriel)"),
    ("app", r"(via|sur) l.application"),
]
_URL = re.compile(r"https?://[^\s<>\"')]+|www\.[a-z0-9.-]+\.[a-z]{2,}[^\s<>\"')]*", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_POSTAL = re.compile(r"(\d{5}\s+[A-Z][A-Z' -]{2,}(?:\s+CEDEX(?:\s+\d+)?)?)")


def _quote(sents: list[str], sn: list[str], rx: str) -> str | None:
    r = re.compile(rx)
    for s, n in zip(sents, sn):
        if r.search(n):
            return s.strip()[:300]
    return None


def analyze_offer(text: str, url: str | None = None, today: date | None = None) -> dict:
    """Retourne les champs d'une Promotion + `evidence` (extraits) + `warnings`."""
    today = today or date.today()
    text = (text or "").strip()
    sents = sentences(text)
    sn = [norm(s) for s in sents]
    t = norm(text)
    ev: dict[str, str] = {}
    warn: list[str] = []
    out: dict = {"rules_text": text[:100_000] or None}

    kind = None
    for k, rx in KIND_PATTERNS:
        q = _quote(sents, sn, rx)
        if q:
            kind, ev["kind"] = k, q
            break
    out["kind"] = kind or "discount"

    # remboursement
    m = re.search(r"(\d{1,3})\s?% (du prix )?rembourse", t)
    if out["kind"] == "full_refund":
        out["refund_percent"] = 100.0
    elif m:
        out["refund_percent"] = float(m.group(1))
        ev["refund"] = _quote(sents, sn, re.escape(m.group(0))) or m.group(0)
    m = re.search(r"(dans la limite de|plafonne a|jusqu.a|a hauteur de|maximum de)\s?(\d+(?:[.,]\d{1,2})?)\s?(€|euros?)", t)
    if m:
        out["refund_max_eur"] = _to_float(m.group(2))
        ev["refund_max"] = _quote(sents, sn, re.escape(m.group(0))) or m.group(0)
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)\s?(€|euros?) (vous seront |seront |sont )?rembourses?", t) or re.search(r"remboursement de (\d+(?:[.,]\d{1,2})?)\s?(€|euros?)", t)
    if m:
        out["refund_eur"] = _to_float(m.group(1))
        ev["refund"] = _quote(sents, sn, re.escape(m.group(0))) or m.group(0)
    m = re.search(r"prix (de vente )?(conseille|indicatif|constate)?\s?:?\s?(\d+(?:[.,]\d{1,2})?)\s?(€|euros?)", t)
    if m:
        out["price_eur"] = _to_float(m.group(3))

    # dates : période d'achat et période de demande
    pq = _quote(sents, sn, r"(achat|achete|achetes|acheter).{0,80}(entre le|du \d|du (lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)|au \d)")
    if pq:
        ds = [d for _, d in parse_dates_in(norm(pq))]
        if len(ds) >= 2:
            out["purchase_start"], out["end_date"] = min(ds), max(ds)
            ev["purchase_period"] = pq
    rq = _quote(sents, sn, r"(demande|dossier|envoi|envoyez|participation|inscri\w*|connectez|rendez-vous).{0,80}(au plus tard|avant le|jusqu.au)")
    if rq:
        ds = [d for _, d in parse_dates_in(norm(rq))]
        if ds:
            out["send_deadline"] = max(ds)
            ev["request_deadline"] = rq
    m = re.search(r"dans (les|un delai de) (\d{1,3}) jours (calendaires )?(suivant|qui suivent|apres|a compter de) (l.|votre |la date d.)?achat", t)
    if m:
        out["request_delay_days"] = int(m.group(2))
        ev["request_delay"] = _quote(sents, sn, re.escape(m.group(0))) or m.group(0)
    m = re.search(r"(sous|dans un delai (de|d.environ)|environ) (\d{1,2})(?: a (\d{1,2}))? (semaines|jours)", t)
    if m:
        n = int(m.group(4) or m.group(3))
        out["refund_delay_days"] = n * 7 if m.group(5) == "semaines" else n
        ev["refund_delay"] = _quote(sents, sn, re.escape(m.group(0))) or m.group(0)

    # produit exact
    out["eans"] = find_eans(text)
    if out["eans"]:
        ev["eans"] = ", ".join(out["eans"])
    variant: dict = {}
    pr = _quote(sents, sn, r"(produits? (concernes?|participants?|eligibles?)|reference|offre valable (sur|pour)|pour l.achat d)")
    if pr:
        q = quantity(pr)
        if q:
            variant["quantity"] = q
        ev["product"] = pr
    m = re.search(r"(pour l.achat (simultane )?de|achat de) (\d+|deux|trois|quatre) (produits?|paquets?|boites?|bouteilles?|references?)", t)
    if m:
        n = {"deux": 2, "trois": 3, "quatre": 4}.get(m.group(3)) or int(m.group(3))
        if n > 1:
            variant["min_quantity"] = n
    if re.search(r"edition (limitee|speciale)|pack promotionnel|emballage (portant|signale|avec) (le )?(logo|code|mention)", t):
        variant["edition"] = "édition ou emballage promotionnel"
        ev["edition"] = _quote(sents, sn, r"edition (limitee|speciale)|pack promotionnel|emballage (portant|signale|avec)") or ""
    out["variant"] = variant

    # enseignes
    rq2 = _quote(sents, sn, r"(magasins?|enseignes?|points de vente) (participants?|partenaires?)|(en vente|disponible|achete) (chez|dans|en magasin)|(carrefour|leclerc|intermarche|auchan|lidl|aldi|monoprix|super u|hyper u)")
    out["retailers"] = find_retailers(rq2 or "") or find_retailers(text)
    if out["retailers"]:
        ev["retailers"] = rq2 or ", ".join(out["retailers"])
    elif re.search(r"magasins? participants?|enseignes? participantes?", t):
        warn.append("Enseignes participantes non listées dans le texte : à vérifier sur le site de l'opération")

    # limites
    m = re.search(r"(une seule|1|un\b|une\b) (demande|participation|remboursement|offre)s? (par|/) (foyer|personne|famille|ticket|produit|adresse|participant)", t) or \
        re.search(r"limitee? a (une|1|deux|2|trois|3) (demande|participation|remboursement)s? par (foyer|personne|famille|ticket|produit|adresse)", t)
    if m:
        who = m.group(m.lastindex)
        out["limit_per"] = {"famille": "household", "adresse": "household", "foyer": "household", "personne": "person",
                            "participant": "person", "ticket": "ticket", "produit": "product"}[who]
        cnt = m.group(1)
        out["limit_count"] = {"une": 1, "un": 1, "une seule": 1, "1": 1, "deux": 2, "2": 2, "trois": 3, "3": 3}.get(cnt.strip(), 1)
        ev["limit"] = _quote(sents, sn, re.escape(m.group(0))) or m.group(0)

    # cumul
    if re.search(r"non cumulable|ne (peut|peuvent) (pas|etre) (etre )?cumule|pas cumulable", t):
        out["cumulable"] = False
        ev["cumulable"] = _quote(sents, sn, r"non cumulable|cumule|cumulable") or ""
    elif re.search(r"\bcumulable avec", t):
        out["cumulable"] = True
        ev["cumulable"] = _quote(sents, sn, r"cumulable avec") or ""
    else:
        out["cumulable"] = None

    # canal de transmission
    for ch, rx in CHANNELS:
        q = _quote(sents, sn, rx)
        if q:
            out["channel"] = ch
            ev["channel"] = q
            break
    urls = _URL.findall(text)
    emails = _EMAIL.findall(text)
    if out.get("channel") == "postal":
        m = _POSTAL.search(text)
        out["channel_target"] = (ev.get("channel") or "")[:500] if m else None
    elif out.get("channel") == "email" and emails:
        out["channel_target"] = emails[0]
    elif urls:
        u = urls[0]
        out["channel_target"] = u if u.startswith("http") else "https://" + u
    elif url:
        out["channel_target"] = url

    # justificatifs
    docs = []
    for d, rx in DOCS:
        if re.search(rx, t):
            docs.append(d)
    if "barcode_original" in docs and "barcode" in docs:
        docs.remove("barcode")
    out["required_docs"] = docs
    if "iban" in docs:
        warn.append("Coordonnées bancaires demandées : à saisir vous-même sur le canal officiel, jamais transmises par l'application")

    # frais et avantages
    if re.search(r"frais (d.envoi|de timbre|postaux|d.affranchissement) (ne sont pas|non) rembourses|timbre (a votre charge|non rembourse)", t):
        out["fees_eur"] = 1.29 if out.get("channel") == "postal" else None
        warn.append("Frais d'envoi non remboursés (timbre)")
    # jeu avec achat : valeur des lots (jamais une économie)
    ra = analyze_rules(text) if text else None
    if out["kind"] == "purchase_game" and ra:
        vals = [(p.get("value_eur") or (p.get("value") if p.get("currency") == "EUR" else None) or 0) for p in ra.prizes]
        out["prize_value_eur"] = max(vals) if vals else None
        out["contest_prizes"] = [p.get("name") for p in ra.prizes][:5]
    # organisateur
    m = re.search(r"(societe|la marque|l.organisateur)\s+([A-Z][\w&' .-]{2,60}?)(,| \(| organise| ci-apres| sas| sa\b| sarl)", text, re.I)
    org = m.group(2).strip() if m else None
    out["brand"] = (ra.organizer_name if ra and ra.organizer_name else None) or org

    out["analysis"] = {"evidence": ev, "warnings": warn}
    out["reliability"] = reliability(out, url)
    if out.get("end_date") and out["end_date"] < today:
        warn.append("Période d'achat terminée")
    if out.get("send_deadline") and out["send_deadline"] < today:
        warn.append("Date limite de demande dépassée")
    return out


def reliability(o: dict, url: str | None) -> int:
    """Fiabilité /100 de l'opération (pas une probabilité de remboursement)."""
    from ..intelligence.scoring import SUSPICIOUS_HOSTS
    from urllib.parse import urlsplit

    s = 0
    s += 25 if o.get("rules_text") and len(o["rules_text"]) > 300 else 10 if o.get("rules_text") else 0
    s += 15 if o.get("brand") else 0
    s += 15 if o.get("end_date") or o.get("send_deadline") else 0
    s += 15 if o.get("channel") and o.get("channel_target") else 5 if o.get("channel") else 0
    s += 10 if o.get("eans") or (o.get("variant") or {}).get("quantity") else 0
    s += 10 if o.get("retailers") else 0
    host = urlsplit(url or o.get("channel_target") or "").hostname or ""
    if url and url.startswith("https://") and not SUSPICIOUS_HOSTS.search(host):
        s += 10
    t = norm(o.get("rules_text") or "")
    if re.search(r"code (secret|confidentiel)|mot de passe|numero de carte|cryptogramme|frais de dossier a regler", t):
        s -= 40
    return max(0, min(100, s))


def apply_to_promotion(p, data: dict) -> None:
    """Copie l'analyse dans la promotion sans écraser ce que l'utilisateur a saisi lui-même."""
    for k in ("kind", "rules_text", "refund_percent", "refund_max_eur", "purchase_start", "end_date", "send_deadline", "request_delay_days",
              "refund_delay_days", "eans", "variant", "retailers", "limit_per", "limit_count", "cumulable", "channel", "channel_target",
              "required_docs", "fees_eur", "prize_value_eur", "reliability", "analysis"):
        if k in data and data[k] not in (None, [], {}) and getattr(p, k, None) in (None, [], {}, "discount"):
            setattr(p, k, data[k])
    for k in ("refund_eur", "price_eur", "brand"):
        if data.get(k) is not None and getattr(p, k) is None:
            setattr(p, k, data[k])
    p.analysis = data.get("analysis") or p.analysis
    p.reliability = data.get("reliability", p.reliability)


_ = DATE_RX  # réexport utile aux tests
