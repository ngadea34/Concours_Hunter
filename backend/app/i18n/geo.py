"""M06 : pays, langues, devises, mois. La résidence en France est la référence d'éligibilité."""
from __future__ import annotations

import re
import unicodedata

LANGUAGES = ["fr", "en", "es", "de", "it", "pt", "nl"]


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", strip_accents(s.lower())).strip()


# Noms de pays (7 langues, sans accents, minuscules) -> ISO 3166-1 alpha-2.
# Liste volontairement centrée sur les pays fréquents dans les règlements ; extensible.
_COUNTRIES: dict[str, list[str]] = {
    "FR": ["france", "france metropolitaine", "metropolitan france", "frankreich", "francia", "franca", "frankrijk", "hexagone", "corse"],
    "BE": ["belgique", "belgium", "belgica", "belgien", "belgio", "belgie"],
    "CH": ["suisse", "switzerland", "suiza", "schweiz", "svizzera", "suica", "zwitserland"],
    "LU": ["luxembourg", "luxemburgo", "luxemburg", "lussemburgo"],
    "MC": ["monaco", "principaute de monaco", "monaco"],
    "CA": ["canada", "kanada", "quebec"],
    "US": ["united states", "united states of america", "usa", "u.s.", "u.s.a.", "the 50 united states", "etats-unis", "estados unidos", "vereinigte staaten", "stati uniti", "verenigde staten"],
    "GB": ["united kingdom", "uk", "great britain", "royaume-uni", "reino unido", "vereinigtes konigreich", "regno unito", "verenigd koninkrijk", "england", "angleterre", "scotland", "wales"],
    "IE": ["ireland", "irlande", "irlanda", "irland", "ierland"],
    "DE": ["germany", "allemagne", "alemania", "deutschland", "germania", "alemanha", "duitsland"],
    "AT": ["austria", "autriche", "osterreich", "oostenrijk"],
    "ES": ["spain", "espagne", "espana", "spanien", "spagna", "espanha", "spanje"],
    "IT": ["italy", "italie", "italia", "italien", "italie", "itali"],
    "PT": ["portugal", "portogallo"],
    "NL": ["netherlands", "the netherlands", "pays-bas", "paises bajos", "niederlande", "paesi bassi", "paises baixos", "nederland", "holland", "hollande"],
    "AU": ["australia", "australie", "australien"],
    "NZ": ["new zealand", "nouvelle-zelande", "nueva zelanda", "neuseeland"],
    "BR": ["brazil", "bresil", "brasil", "brasilien"],
    "MX": ["mexico", "mexique", "mexiko"],
    "PL": ["poland", "pologne", "polonia", "polen"],
    "SE": ["sweden", "suede", "suecia", "schweden"],
    "DK": ["denmark", "danemark", "dinamarca", "danemark"],
    "NO": ["norway", "norvege", "noruega", "norwegen"],
    "FI": ["finland", "finlande", "finlandia", "finnland"],
}
NAME_TO_ISO: dict[str, str] = {name: iso for iso, names in _COUNTRIES.items() for name in names}

EU = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]
EEA = EU + ["IS", "LI", "NO"]

REGIONS: dict[str, list[str]] = {
    "WORLD": ["worldwide", "monde entier", "dans le monde entier", "all countries", "tous pays", "international", "todo el mundo", "weltweit", "in tutto il mondo", "mundo inteiro", "wereldwijd"],
    "EU": ["union europeenne", "european union", "union europea", "europaischen union", "unione europea", "uniao europeia", "europese unie", "ue", "eu"],
    "EEA": ["espace economique europeen", "european economic area", "eee", "eea"],
    "DOM": ["dom-tom", "dom tom", "drom", "outre-mer", "departements d'outre-mer"],
}

# Mois (7 langues, sans accents)
MONTHS: dict[str, int] = {}
for i, names in enumerate([
    ["janvier", "january", "jan", "enero", "januar", "gennaio", "janeiro", "januari"],
    ["fevrier", "february", "feb", "febrero", "februar", "febbraio", "fevereiro", "februari"],
    ["mars", "march", "mar", "marzo", "marz", "marco", "maart"],
    ["avril", "april", "apr", "abril", "aprile"],
    ["mai", "may", "mayo", "maggio", "maio", "mei"],
    ["juin", "june", "jun", "junio", "juni", "giugno", "junho"],
    ["juillet", "july", "jul", "julio", "juli", "luglio", "julho"],
    ["aout", "august", "aug", "agosto", "augustus"],
    ["septembre", "september", "sep", "sept", "septiembre", "settembre", "setembro"],
    ["octobre", "october", "oct", "octubre", "oktober", "ottobre", "outubro"],
    ["novembre", "november", "nov", "noviembre", "novembro"],
    ["decembre", "december", "dec", "diciembre", "dezember", "dicembre", "dezembro"],
], start=1):
    for n in names:
        MONTHS[n] = i

CURRENCY_SYMBOLS = {"€": "EUR", "eur": "EUR", "euros": "EUR", "euro": "EUR", "$": "USD", "usd": "USD", "us$": "USD",
                    "£": "GBP", "gbp": "GBP", "chf": "CHF", "cad": "CAD", "ca$": "CAD", "c$": "CAD", "aud": "AUD", "a$": "AUD",
                    "brl": "BRL", "r$": "BRL", "sek": "SEK", "dkk": "DKK", "nok": "NOK", "pln": "PLN", "mxn": "MXN"}

# Taux indicatifs EUR par unité (mis à jour par le job « rates » depuis la BCE si activé).
DEFAULT_RATES_TO_EUR = {"EUR": 1.0, "USD": 0.92, "GBP": 1.17, "CHF": 1.05, "CAD": 0.67, "AUD": 0.6, "BRL": 0.17,
                        "SEK": 0.087, "DKK": 0.134, "NOK": 0.086, "PLN": 0.23, "MXN": 0.05}
_rates = dict(DEFAULT_RATES_TO_EUR)


def set_rates(rates: dict[str, float]) -> None:
    _rates.update({k.upper(): float(v) for k, v in rates.items() if v})


def to_eur(value: float | None, currency: str | None) -> float | None:
    if value is None:
        return None
    rate = _rates.get((currency or "EUR").upper())
    return round(value * rate, 2) if rate else None


def find_countries(text: str) -> set[str]:
    """Retourne les codes ISO et régions (WORLD, EU, EEA, DOM) mentionnés dans un texte."""
    t = " " + norm(text) + " "
    found: set[str] = set()
    for name, iso in NAME_TO_ISO.items():
        if re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", t):
            found.add(iso)
    for region, names in REGIONS.items():
        for n in names:
            if len(n) <= 3:
                if re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", text.lower()) and n.upper() in text:
                    found.add(region)
            elif re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", t):
                found.add(region)
    # États américains ("50 United States and D.C.") : réduit à US
    return found


def region_includes_fr(codes: set[str]) -> bool:
    return bool(codes & {"FR", "WORLD", "EU", "EEA"})
