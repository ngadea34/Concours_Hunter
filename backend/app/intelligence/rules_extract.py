"""Extraction déterministe (niveau R0) des conditions d'un règlement, multilingue.

Chaque champ extrait est accompagné de la phrase source (preuve). Aucune décision sans preuve.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date

from ..i18n.geo import CURRENCY_SYMBOLS, MONTHS, find_countries, norm, region_includes_fr

ANALYZER_VERSION = "r0-1.0"


@dataclass
class Finding:
    value: object
    evidence: str
    method: str = "rule"


@dataclass
class RulesAnalysis:
    free_status: str = "unknown"  # free | free_alternative | purchase_required | unknown
    free: Finding | None = None
    paid_signals: list[str] = field(default_factory=list)
    free_signals: list[str] = field(default_factory=list)
    alternative_signals: list[str] = field(default_factory=list)
    countries_allowed: list[str] = field(default_factory=list)
    countries_excluded: list[str] = field(default_factory=list)
    metropole_only: bool = False
    fr_eligible: str = "unknown"
    eligibility: Finding | None = None
    min_age: int | None = None
    age: Finding | None = None
    start_date: str | None = None
    end_date: str | None = None
    dates: Finding | None = None
    prizes: list[dict] = field(default_factory=list)
    entry_limit: str | None = None
    entry_period: str | None = None  # once | daily | weekly | monthly
    automation_forbidden: bool | None = None
    automation_allowed_explicit: bool = False
    automation: Finding | None = None
    claim_days: int | None = None
    claim: Finding | None = None
    organizer_name: str | None = None
    organizer_legal_id: str | None = None
    organizer: Finding | None = None
    suspicious_signals: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    language: str | None = None
    ambiguities: list[str] = field(default_factory=list)
    analyzer_version: str = ANALYZER_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------- utilitaires
_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 3]


def _first(patterns: list[str], sents: list[str], sents_norm: list[str]) -> tuple[str, re.Match] | None:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for s, sn in zip(sents, sents_norm):
            m = rx.search(sn)
            if m:
                return s, m
    return None


def _all(patterns: list[str], sents: list[str], sents_norm: list[str]) -> list[tuple[str, str]]:
    out = []
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for s, sn in zip(sents, sents_norm):
            m = rx.search(sn)
            if m:
                out.append((s, m.group(0)))
    return out


def detect_language(text: str) -> str | None:
    t = " " + norm(text[:5000]) + " "
    markers = {
        "fr": [" le ", " la ", " les ", " des ", " jeu ", " concours ", " gagner ", " reglement "],
        "en": [" the ", " and ", " sweepstakes ", " giveaway ", " win ", " entry ", " rules "],
        "es": [" el ", " los ", " sorteo ", " concurso ", " ganar ", " bases "],
        "de": [" der ", " die ", " und ", " gewinnspiel ", " gewinnen ", " teilnahme "],
        "it": [" il ", " gli ", " concorso ", " vincere ", " regolamento ", " premio "],
        "pt": [" os ", " sorteio ", " ganhar ", " regulamento ", " premio ", " voce "],
        "nl": [" de ", " het ", " een ", " winactie ", " winnen ", " prijsvraag "],
    }
    scores = {lang: sum(t.count(w) for w in ws) for lang, ws in markers.items()}
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] >= 3 else None


# ----------------------------------------------------------------- gratuité
FREE_PATTERNS = [
    r"sans obligation d.?achat", r"gratuit(e)? et sans obligation", r"jeu (entierement )?gratuit", r"participation (est )?gratuite",
    r"no purchase (is )?(necessary|required)", r"free to enter", r"no purchase or payment",
    r"sin obligacion de compra", r"gratuito y sin obligacion", r"participacion (es )?gratuita",
    r"kein kauf erforderlich", r"ohne kaufverpflichtung", r"teilnahme ist kostenlos", r"kostenlose teilnahme",
    r"senza obbligo d.?acquisto", r"partecipazione (e )?gratuita",
    r"sem obrigacao de compra", r"participacao (e )?gratuita",
    r"geen aankoopverplichting", r"deelname is gratis", r"gratis deelname",
]
PAID_PATTERNS = [
    r"achat (est )?obligatoire", r"preuve d.?achat", r"ticket de caisse", r"code[- ]barres?", r"code (unique )?(figurant|present) sur",
    r"frais (d.?inscription|de participation|de dossier) (de|d.un montant)", r"sms surtaxe", r"numero surtaxe", r"appel surtaxe",
    r"purchase (is )?(necessary|required)", r"proof of purchase", r"entry fee", r"must purchase", r"with (any|every) purchase",
    r"compra (es )?obligatoria", r"prueba de compra", r"ticket de compra",
    r"kaufbeleg", r"kassenbon", r"teilnahmegebuhr",
    r"scontrino", r"prova d.?acquisto", r"acquisto obbligatorio",
    r"comprovativo de compra", r"compra obrigatoria",
    r"aankoopbewijs", r"kassabon", r"aankoop (is )?verplicht",
]
ALT_PATTERNS = [
    r"(participation|demande) gratuite (par|sur)", r"(participation|demande)s? (de code )?(par courrier|par voie postale|sur papier libre)", r"remboursement des frais",
    r"rembourse(ment|s)? (du|des) (timbre|frais|cout)", r"sans achat.{0,40}(possible|egalement)",
    r"alternate (method|means) of entry", r"\bamoe\b", r"mail[- ]in entry", r"to enter without (making a )?purchase",
    r"(possible|egalement|aussi) sans achat", r"sur (simple )?demande .{0,40}(courrier|papier libre)", r"papier libre", r"timbre rembourse",
    r"participar sin compra", r"ohne kauf teilnehmen", r"partecipare senza acquisto", r"participar sem compra", r"deelnemen zonder aankoop",
]
NEGATED_PAID = re.compile(r"(sans|no|not|aucun|nul|kein|senza|sem|geen|sin)\W+(\w+\W+){0,3}(achat|purchase|compra|kauf|acquisto|aankoop)", re.I)


def analyze_free(sents: list[str], sn: list[str], a: RulesAnalysis) -> None:
    free = _all(FREE_PATTERNS, sents, sn)
    paid = []
    for pat in PAID_PATTERNS:
        rx = re.compile(pat, re.I)
        for s, n in zip(sents, sn):
            for m in rx.finditer(n):
                ctx = n[max(0, m.start() - 30): m.end()]
                if NEGATED_PAID.search(ctx) and "obligatoire" not in m.group(0):
                    continue
                if re.search(r"(will not|ne (va|vas|permet) pas|n.augmente pas|does not) (increase|improve|augmenter)", n) and "purchase" in m.group(0):
                    continue
                paid.append((s, m.group(0)))
                break
    alt = _all(ALT_PATTERNS, sents, sn)
    a.free_signals = sorted({m for _, m in free})
    a.paid_signals = sorted({m for _, m in paid})
    a.alternative_signals = sorted({m for _, m in alt})
    if paid and (alt or free):
        # achat mentionné mais voie gratuite affirmée : voie alternative, à vérifier si aucune modalité explicite
        a.free_status = "free_alternative"
        a.free = Finding("free_alternative", (alt or free)[0][0])
        if not alt:
            a.ambiguities.append("Achat mentionné et gratuité affirmée sans modalité gratuite explicite")
    elif paid:
        a.free_status = "purchase_required"
        a.free = Finding("purchase_required", paid[0][0])
    elif free:
        a.free_status = "free"
        a.free = Finding("free", free[0][0])


# ----------------------------------------------------------------- éligibilité
ELIG_PATTERNS = [
    r"(ouvert|reserve|accessible|destine)e?s? (a|aux) .{0,160}(resid|domicili|demeurant|habitant)",
    r"(resid|domicili|demeurant)\w* (en|au|aux|dans) ",
    r"(open|available) (only )?to .{0,120}(resident|citizen|living)",
    r"legal residents? of", r"residents? of ",
    r"(abierto|dirigido) a .{0,120}(resident|domicili)", r"residentes en",
    r"(wohnsitz|teilnahmeberechtigt) .{0,120}(in|deutschland|osterreich)", r"mit wohnsitz in",
    r"(aperto|riservato) a .{0,120}(resident|domicil)", r"residenti in",
    r"(aberto|destinado) a .{0,120}(resident|domicil)", r"residentes em",
    r"(open voor|woonachtig in|ingezetenen van)",
]
EXCL_PATTERNS = [r"(a l.exclusion|a l.exception|sauf|hors|excluding|except|excluded|void in|excepto|ausgenommen|ad esclusione|exceto|met uitzondering)"]
METROPOLE = re.compile(r"france metropolitaine|metropolitan france", re.I)
DOM_INCLUDED = re.compile(r"(dom|drom|outre-mer|corse)[^.]{0,30}(inclus|compris)|y compris (les )?(dom|drom|outre-mer)", re.I)


def analyze_eligibility(sents: list[str], sn: list[str], a: RulesAnalysis) -> None:
    hits = _all(ELIG_PATTERNS, sents, sn)
    if not hits:
        return
    allowed: set[str] = set()
    excluded: set[str] = set()
    evidence = []
    for s, _ in hits[:6]:
        nrm = norm(s)
        m = re.search(EXCL_PATTERNS[0], nrm)
        head, tail = (nrm[: m.start()], nrm[m.start():]) if m else (nrm, "")
        allowed |= find_countries(head)
        excluded |= find_countries(tail)
        if METROPOLE.search(nrm) and not DOM_INCLUDED.search(nrm):
            a.metropole_only = True
        if s not in evidence:
            evidence.append(s)
    allowed -= {"DOM"}
    a.countries_allowed = sorted(allowed)
    a.countries_excluded = sorted(excluded)
    ev = " … ".join(evidence[:2])
    if "FR" in excluded:
        a.fr_eligible = "no"
    elif region_includes_fr(allowed):
        a.fr_eligible = "yes"
    elif allowed:
        a.fr_eligible = "no"
    else:
        a.ambiguities.append("Clause de résidence trouvée sans pays identifiable")
    a.eligibility = Finding(a.fr_eligible, ev)


AGE_PATTERNS = [
    r"(age|agee?s?|aged) d.?au moins (\d{2}) ans", r"(\d{2}) ans (revolus|ou plus|et plus|minimum)", r"plus de (\d{2}) ans",
    r"personnes? (physiques? )?majeures?", r"\bmajeur(e|s|es)?\b",
    r"(\d{2}) years (of age )?(or older|and older|or over)", r"at least (\d{2}) years", r"age of majority",
    r"mayores? de (\d{2})", r"mayores? de edad", r"mindestens (\d{2}) jahre", r"volljahrig", r"(\d{2}) jahren",
    r"maggiorenni", r"almeno (\d{2}) anni", r"maiores? de (\d{2})", r"maiores? de idade", r"(\d{2}) jaar of ouder", r"meerderjarig",
]


def analyze_age(sents: list[str], sn: list[str], a: RulesAnalysis) -> None:
    for pat in AGE_PATTERNS:
        rx = re.compile(pat, re.I)
        for s, n in zip(sents, sn):
            m = rx.search(n)
            if not m:
                continue
            nums = [int(g) for g in m.groups() if g and g.isdigit()]
            age = nums[0] if nums else 18
            if 12 <= age <= 25:
                a.min_age = age
                a.age = Finding(age, s)
                return


# ----------------------------------------------------------------- dates
_MONTH_RX = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_RX = re.compile(
    r"(?P<d1>\d{1,2})(er|st|nd|rd|th|º|°)?\s*(de\s+)?(?P<m1>" + _MONTH_RX + r")\.?\s*(de\s+)?(?P<y1>\d{4})"
    r"|(?P<m2>" + _MONTH_RX + r")\.?\s+(?P<d2>\d{1,2})(st|nd|rd|th)?,?\s+(?P<y2>\d{4})"
    r"|(?P<d3>\d{1,2})[/.\-](?P<m3>\d{1,2})[/.\-](?P<y3>\d{4}|\d{2})(?!\d)"
    r"|(?P<y4>\d{4})-(?P<m4>\d{2})-(?P<d4>\d{2})",
    re.I,
)
START_WORDS = re.compile(r"\b(du|a partir du|debute|commence|from|starts?|begins?|del|desde|vom|ab dem|dal|de|van|vanaf)\b", re.I)
END_WORDS = re.compile(r"\b(au|jusqu.?au|jusqu.?a|se termine|prend fin|cloture|fin|until|through|to|ends?|closes?|deadline|al|hasta|bis|zum|fino al|al|ate|tot en met|t/m|tot|avant|before|antes|vor|prima|voor)\b", re.I)


def parse_dates_in(text_norm: str, us_order: bool = False) -> list[tuple[int, date]]:
    out = []
    for m in DATE_RX.finditer(text_norm):
        try:
            if m.group("d1"):
                d = date(int(m.group("y1")), MONTHS[m.group("m1").lower()], int(m.group("d1")))
            elif m.group("m2"):
                d = date(int(m.group("y2")), MONTHS[m.group("m2").lower()], int(m.group("d2")))
            elif m.group("d3"):
                y = int(m.group("y3"))
                y = y + 2000 if y < 100 else y
                a_, b_ = int(m.group("d3")), int(m.group("m3"))
                day, mon = (b_, a_) if us_order else (a_, b_)
                if mon > 12 and day <= 12:
                    day, mon = mon, day
                d = date(y, mon, day)
            else:
                d = date(int(m.group("y4")), int(m.group("m4")), int(m.group("d4")))
        except (ValueError, KeyError):
            continue
        if 2000 <= d.year <= 2100:
            out.append((m.start(), d))
    return out


def analyze_dates(sents: list[str], sn: list[str], a: RulesAnalysis) -> None:
    us = a.language == "en" and "US" in a.countries_allowed
    period_kw = re.compile(r"(du|from|del|vom|dal|de|van)\b.{0,60}\b(au|to|through|until|al|bis|zum|ate|tot)\b|jusqu|until|ends?|cloture|se termine|prend fin|hasta|bis zum|fino al|ate|tot en met|deadline|date limite|avant le|before|antes del?|vor dem|prima del|voor", re.I)
    best: tuple[str, date | None, date | None] | None = None
    for s, n in zip(sents, sn):
        ds = parse_dates_in(n, us)
        if not ds:
            continue
        if period_kw.search(n) or re.search(r"\b(jeu|concours|sweepstakes|contest|giveaway|promotion|sorteo|gewinnspiel|concorso|passatempo|winactie)\b", n):
            if len(ds) >= 2:
                start, end = ds[0][1], ds[-1][1]
                if end < start:
                    start, end = end, start
                cand = (s, start, end)
            else:
                pos, d = ds[0]
                before = n[max(0, pos - 40): pos]
                cand = (s, None, d) if END_WORDS.search(before) or not START_WORDS.search(before) else (s, d, None)
            if best is None or (cand[2] and not best[2]):
                best = cand
            if best[1] and best[2]:
                break
    if best:
        s, start, end = best
        a.start_date = start.isoformat() if start else None
        a.end_date = end.isoformat() if end else None
        a.dates = Finding({"start": a.start_date, "end": a.end_date}, s)


# ----------------------------------------------------------------- lots
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "high_tech": ["iphone", "smartphone", "ordinateur", "laptop", "pc portable", "tablette", "ipad", "console", "playstation", "ps5", "xbox", "nintendo", "switch", "televiseur", "tv ", "television", "casque", "ecouteurs", "airpods", "camera", "appareil photo", "drone", "montre connectee", "smartwatch", "enceinte", "macbook", "samsung galaxy"],
    "auto": ["voiture", "vehicule", "car ", "auto ", "scooter", "moto", "trottinette", "velo electrique", "e-bike", "coche", "fahrzeug"],
    "travel": ["voyage", "sejour", "week-end", "weekend", "croisiere", "trip", "vacation", "holiday", "viaje", "reise", "viaggio", "viagem", "reis ", "billets d'avion", "nuits"],
    "home": ["electromenager", "aspirateur", "robot", "cafetiere", "machine a cafe", "thermomix", "mobilier", "canape", "literie", "matelas", "cuisine", "barbecue", "jardin"],
    "voucher": ["bon d'achat", "bons d'achat", "carte cadeau", "cartes cadeaux", "e-carte", "gift card", "voucher", "cheque cadeau", "tarjeta regalo", "gutschein", "buono", "vale", "cadeaubon", "waardebon"],
    "cash": ["cheque de", "virement", "cash", "argent", "especes", "euros en", "paypal"],
    "culture": ["livre", "livres", "bd ", "dvd", "blu-ray", "vinyle", "album", "abonnement", "magazine", "book", "libro", "buch"],
    "leisure": ["jeu de societe", "jouet", "lego", "parc", "disneyland", "entrees", "pass ", "loisir"],
    "experience": ["experience", "rencontre", "masterclass", "cours de", "bapteme", "vip", "visite"],
    "show": ["concert", "spectacle", "places pour", "invitations", "billets pour", "festival", "match", "theatre", "cinema", "avant-premiere"],
    "restaurant": ["restaurant", "diner", "dejeuner", "repas", "brunch", "gastronomique"],
    "product": ["produit", "produits", "coffret", "panier", "lot de", "box", "cosmetique", "parfum", "vin", "champagne", "chocolat", "kit"],
}


def classify_prize(name: str) -> str:
    n = " " + norm(name) + " "
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(k in n for k in kws):
            return cat
    return "other"


_CUR = r"(€|eur(?:os?)?|\$|us\$|usd|£|gbp|chf|cad|ca\$|aud|a\$|brl|r\$)"
_NUM = r"(\d{1,3}(?:[   .,]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
VALUE_RX = re.compile(rf"{_CUR}\s?{_NUM}|{_NUM}\s?{_CUR}", re.I)
VALUE_CONTEXT = re.compile(r"valeur|value|valued|worth|arv|valor|wert|valore|waarde|d.un montant|prix public|ttc", re.I)
QTY_RX = re.compile(r"(\d{1,4})\s*(x\s+|lots?\b|gagnants?\b|winners?\b|exemplaires?\b|prizes?\b|premios?\b|gewinne?\b|premi\b|premios\b|prijzen\b)", re.I)


def _to_float(num: str) -> float | None:
    s = num.replace(" ", " ").replace(" ", " ").strip()
    if re.search(r"[.,]\d{1,2}$", s):
        dec = s[-3:] if s[-3] in ".," else s[-2:]
        intpart = re.sub(r"[ .,]", "", s[: -len(dec)])
        s = intpart + "." + dec[1:]
    else:
        s = re.sub(r"[ .,]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def parse_money(text: str) -> tuple[float, str] | None:
    m = VALUE_RX.search(text)
    if not m:
        return None
    cur = (m.group(1) or m.group(4) or "").lower()
    num = m.group(2) or m.group(3)
    v = _to_float(num)
    if v is None:
        return None
    return v, CURRENCY_SYMBOLS.get(cur, "EUR")


PRIZE_LINE = re.compile(r"(lot|prize|premio|gewinn|premio|prémio|prijs|dotation|a gagner|to win|grand prize|1er prix|\d+\s*x\s)", re.I)


def analyze_prizes(sents: list[str], sn: list[str], a: RulesAnalysis) -> None:
    seen = set()
    for s, n in zip(sents, sn):
        if not PRIZE_LINE.search(n) or len(s) > 400:
            continue
        money = parse_money(s) if VALUE_CONTEXT.search(n) or VALUE_RX.search(s) else None
        qty_m = QTY_RX.search(n)
        if not qty_m:
            head = n[: VALUE_RX.search(n).start()] if VALUE_RX.search(n) else n
            qty_m = re.search(r"(?<![\d.,/])(\d{1,4})\s+(?!jours?|ans|days?|years?|%|h\b|heures?|mois|months?|€|eur|\d)[a-z]", head)
        if not money and not qty_m and not re.search(r"a gagner|to win|grand prize|1er prix", n):
            continue
        qty = int(qty_m.group(1)) if qty_m and 0 < int(qty_m.group(1)) < 10000 else 1
        name = re.sub(r"\s+", " ", s)[:200]
        key = norm(name)[:80]
        if key in seen:
            continue
        seen.add(key)
        fees = None
        if re.search(r"(frais|taxes?|fees?|shipping|livraison|port)\b.{0,40}(a la charge|charged|paid by|du gagnant|of the winner|non (pris|inclus))", n):
            fees = s
        a.prizes.append({"name": name, "category": classify_prize(name), "quantity": qty,
                         "value": money[0] if money else None, "currency": money[1] if money else None,
                         "fees_note": fees, "evidence": s})
        if len(a.prizes) >= 15:
            break


# ----------------------------------------------------------------- limites, automatisation, réclamation
LIMIT_PATTERNS = [
    (r"une (seule )?participation par (jour|24 ?h)", "daily"), (r"one entry per (person )?per day|once (a|per) day|daily entr", "daily"),
    (r"une participation par semaine|one entry per week|weekly entr", "weekly"),
    (r"une participation par mois|one entry per month", "monthly"),
    (r"une (seule )?participation par (personne|foyer|participant|adresse|famille)", "once"), (r"(limit|limited to) one entry|one entry per (person|household|email)", "once"),
    (r"una (sola )?participacion por (persona|hogar)", "once"), (r"nur einmal teilnehmen|eine teilnahme pro (person|haushalt)", "once"),
    (r"una (sola )?partecipazione per (persona|nucleo)", "once"), (r"uma (unica )?participacao por (pessoa|agregado)", "once"), (r"een deelname per (persoon|huishouden)", "once"),
]
AUTOMATION_FORBIDDEN = [
    r"(moyens?|procede|logiciels?|systemes?|scripts?|robots?) (automatis|de participation automatique)", r"participation automatis\w+ .{0,30}(interdit|prohib|exclu|nulle)",
    r"(robot|script|macro|bot)s?\b.{0,40}(interdit|prohib|exclu|nul)", r"automated (means|entries|entry|systems?|scripts?|devices?)",
    r"(bots?|macros?|scripts?)\b.{0,40}(prohibited|void|not (allowed|permitted|eligible))",
    r"(medios|sistemas) automatizados", r"automatisierte", r"mezzi automatizzati|sistemi automatici", r"meios automatizados", r"geautomatiseerde",
]
AUTOMATION_ALLOWED = [r"(participation|inscription)s? automatis\w+ (sont |est )?(autorise|permise)", r"automated entr(y|ies) (are|is) (permitted|allowed)"]
CLAIM_PATTERNS = [
    r"(dans un delai de|sous|dispose(nt)? de|de) (\d{1,3}) jours? .{0,80}(reclam|confirm|repond|accept|coordonnees|manifest)",
    r"(reclam|confirm|repond|accept|coordonnees|manifest).{0,80}(dans un delai de|sous|dans les) (\d{1,3}) jours?",
    r"within (\d{1,3}) days", r"(\d{1,3}) days (of|from|after) (notification|receipt|being notified)",
    r"(en un plazo de|dentro de) (\d{1,3}) dias", r"innerhalb von (\d{1,3}) tagen", r"entro (\d{1,3}) giorni", r"(no prazo de|dentro de) (\d{1,3}) dias", r"binnen (\d{1,3}) dagen",
]
ORG_PATTERNS = [
    r"(?i:la soci[eé]t[eé]|l.association|l.entreprise)\s+(?P<n>[A-Z0-9][\w&'’\- .]{1,80}?),?\s+(?i:sas|sasu|sa|sarl|eurl|sca|snc|inc|ltd|gmbh|srl|bv)\b",
    r"(?i:organis[eé] par|organisateur\s*:)\s*(?:(?i:la soci[eé]t[eé])\s+)?(?P<n>[A-Z0-9][\w&'’\- .]{1,80}?)(?:,|\(|\.|\s+(?i:sas|sa|sarl|inc|ltd)\b|\s+au capital|\s+dont)",
    r"(?i:sponsor|organizer|promoter)(?i: of (?:this|the) \w+)?(?i: is|:)\s+(?P<n>[A-Z0-9][\w&'’\- .]{1,80}?)(?:,|\(|\.|\s+(?i:inc|llc|ltd|corp)\b|\s+located)",
    r"(?i:organizado por|veranstalter(?: ist)?:?|organizzato da|promotor(?:a)?:?|organisator:?)\s+(?P<n>[A-Z0-9][\w&'’\- .]{1,80}?)(?:,|\(|\.)",
]
SIREN_RX = re.compile(r"(?:rcs|siren|siret)\D{0,40}?(\d{3}\s?\d{3}\s?\d{3}(?:\s?\d{5})?)", re.I)
SUSPICIOUS = [
    (r"(frais de (dossier|livraison|traitement|douane)|shipping fee|processing fee|handling fee).{0,60}(payer|regler|pay|verser|\d)", "frais demandés au gagnant"),
    # Un RIB peut être demandé légitimement pour verser un gain : seul compte un numéro de carte / code, ou un RIB lié à un paiement
    (r"(numero de (carte|cb)|card number|cvv|cryptogramme|code secret)|(coordonnees bancaires|iban|rib)\b.{0,80}(payer|regler|frais|verser une somme|paiement)|(payer|regler|frais|paiement).{0,80}(coordonnees bancaires|iban|rib)\b", "demande de données bancaires"),
    (r"(partage|share|like|j.aime).{0,40}(gagne|win).{0,40}(iphone|ps5|\d{3,} ?€)", "giveaway réseau social type « partage pour gagner »"),
    (r"(urgent|dernier rappel|final notice|act now|derniere chance).{0,60}(gain|prize|lot)", "pression temporelle"),
    (r"(western union|moneygram|bitcoin|crypto|carte prepayee|pcs|transcash|neosurf)", "moyen de paiement à risque"),
]


def analyze_misc(text: str, sents: list[str], sn: list[str], a: RulesAnalysis) -> None:
    for pat, period in LIMIT_PATTERNS:
        hit = _first([pat], sents, sn)
        if hit:
            a.entry_limit, a.entry_period = hit[0][:200], period
            break
    allow = _first(AUTOMATION_ALLOWED, sents, sn)
    forb = _first(AUTOMATION_FORBIDDEN, sents, sn)
    if allow and not forb:
        a.automation_allowed_explicit = True
        a.automation_forbidden = False
        a.automation = Finding("allowed", allow[0])
    elif forb:
        a.automation_forbidden = True
        a.automation = Finding("forbidden", forb[0])
    for pat in CLAIM_PATTERNS:
        hit = _first([pat], sents, sn)
        if hit:
            nums = [int(g) for g in hit[1].groups() if g and g.isdigit()]
            if nums:
                a.claim_days = nums[0]
                a.claim = Finding(nums[0], hit[0])
                break
    for pat in ORG_PATTERNS:
        m = re.search(pat, text)
        if m:
            name = m.group("n").strip(" ,.-")
            if 2 <= len(name) <= 80:
                a.organizer_name = name
                ctx = text[max(0, m.start() - 20): m.end() + 200]
                a.organizer = Finding(name, ctx.strip()[:300])
                break
    sm = SIREN_RX.search(text)
    if sm:
        a.organizer_legal_id = re.sub(r"\s", "", sm.group(1))
    for pat, label in SUSPICIOUS:
        if re.search(pat, norm(text)):
            a.suspicious_signals.append(label)
    low = norm(text)
    if re.search(r"captcha|recaptcha|hcaptcha|turnstile", low):
        a.flags.append("captcha")
    if re.search(r"(creer|create) (un|a|an) (compte|account)|(connexion|login|sign in) (requise|required|obligatoire)", low):
        a.flags.append("login_required")
    if re.search(r"(instagram|facebook|tiktok|twitter|x\.com|youtube)\b.{0,60}(commente|comment|abonne|follow|partage|share|tag|identifie)", low):
        a.flags.append("social_entry")


# ----------------------------------------------------------------- point d'entrée
def analyze_rules(text: str) -> RulesAnalysis:
    a = RulesAnalysis()
    a.language = detect_language(text)
    sents = sentences(text)
    sn = [norm(s) for s in sents]
    analyze_free(sents, sn, a)
    analyze_eligibility(sents, sn, a)
    analyze_age(sents, sn, a)
    analyze_dates(sents, sn, a)
    analyze_prizes(sents, sn, a)
    analyze_misc(text, sents, sn, a)
    return a
