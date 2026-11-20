"""Politique de sources (révision du 2026-11-20).

On distingue sept catégories d'usage (directive « politique de sources ») :
  1. consultation normale d'informations publiques ;
  2. analyse technique du fonctionnement public d'un site ;
  3. flux ou interfaces officiellement documentés ;
  4. API ou données sous licence ;
  5. import de données fournies volontairement par l'utilisateur ;
  6. extraction automatisée soumise à restriction contractuelle ;
  7. contournement de protections techniques.
Les catégories 1 à 5 sont exploitables dans les limites de leurs conditions. La 6 n'est jamais autorisée par
défaut (il faut une autorisation écrite de l'éditeur, consignée dans DECISIONS.md). La 7 est toujours interdite.

Chaque source a un mode d'accès (ACCESS_MODES). Un site dont l'extraction automatisée est interdite reste utile :
consultation assistée (lien direct ouvert par l'utilisateur) et import volontaire de la page de l'organisateur.
"""
from __future__ import annotations

from urllib.parse import urlsplit

USAGE_CATEGORIES: dict[int, str] = {
    1: "Consultation normale des informations publiques",
    2: "Analyse technique du fonctionnement public",
    3: "Flux ou interfaces officiellement documentés",
    4: "API ou données sous licence",
    5: "Import de données fournies par l'utilisateur",
    6: "Extraction automatisée soumise à restriction contractuelle",
    7: "Contournement de protections techniques",
}
ALLOWED_BY_DEFAULT = {1, 2, 3, 4, 5}

ACCESS_MODES: dict[str, str] = {
    "official_api": "API officielle",
    "authorized_feed": "Flux autorisé",
    "licensed_data": "Données sous licence",
    "public_source": "Source publique réutilisable",
    "user_import": "Import utilisateur",
    "browser_share": "Import par partage navigateur",
    "assisted": "Consultation assistée",
    "external_link": "Référence externe avec lien direct",
}
# mode d'accès par type de connecteur
KIND_MODE = {"rss": "authorized_feed", "site": "public_source", "html": "public_source", "import": "user_import",
             "api": "official_api", "licensed": "licensed_data"}

# Fiches des agrégateurs (audit 2026-11-20, docs/project/AUDIT_AGREGATEURS.md). Chaque site est jugé séparément.
AGGREGATORS: dict[str, dict] = {
    "jeu-concours.biz": {
        "name": "Jeu-concours.biz", "editor": "EKOJEU",
        "modes": ["assisted", "external_link", "browser_share"],
        "automated_extraction": False, "category_of_scan": 6,
        "reason": "Les mentions légales interdisent sans autorisation écrite l'extraction automatisée et nomment les outils de participation automatisée ; /concours/ interdit à tous les robots.",
        "how_to": "Ouvrez le site vous-même, choisissez un concours, suivez le lien vers le site de l'organisateur, puis ajoutez cette page (extension « Ajouter cette page » ou « Ajouter un concours »).",
        "unlock": "Autorisation écrite d'EKOJEU (formulaire de contact du site).",
        "home": "https://www.jeu-concours.biz/",
    },
    "toutgagner.com": {
        "name": "ToutGagner", "editor": "ToutGagner",
        "modes": ["assisted", "external_link", "browser_share"],
        "automated_extraction": False, "category_of_scan": 6,
        "reason": "Contenu réservé aux abonnés (organisateur, règlement, réponses) et reproduction même partielle interdite par les conditions d'utilisation.",
        "how_to": "Consultez le site avec votre propre compte ; quand un concours vous intéresse, ouvrez la page de l'organisateur et ajoutez-la.",
        "unlock": "Licence ou autorisation écrite de l'éditeur.",
        "home": "https://www.toutgagner.com/",
    },
    "ledemondujeu.com": {
        "name": "Le Démon du Jeu", "editor": "Reflexe Media",
        "modes": ["assisted", "external_link", "browser_share"],
        "automated_extraction": False, "category_of_scan": 6,
        "reason": "Pas de CGU écrites, mais même réseau commercial que Jeu-concours.biz (contact Reflexe Media) dont les CGU interdisent l'extraction et les outils dérivés ; une base de concours reste protégée par le droit des producteurs de bases de données (CPI L.341-1 et L.342-2) même sans clause. Lecture automatique suspendue jusqu'à autorisation écrite.",
        "how_to": "Consultez le site vous-même ; ouvrez la page de l'organisateur d'un concours qui vous plaît et ajoutez-la. Le connecteur reste prêt : il se réactive dès qu'une autorisation écrite est enregistrée dans Réglages.",
        "unlock": "Autorisation écrite de Reflexe Media, une seule demande pour Le Démon du Jeu et Jeu-concours.biz (formulaire de contact ; sans réponse, c'est un refus).",
        "home": "https://www.ledemondujeu.com/",
    },
    "concours-du-net.com": {
        "name": "Concours du Net", "editor": None,
        "modes": ["assisted", "external_link", "browser_share"],
        "automated_extraction": False, "category_of_scan": 6,
        "reason": "Les mentions légales interdisent toute exploitation du contenu sans accord écrit ; formulaires protégés par Cloudflare Turnstile. (concoursdunet.com n'existe pas, concoursdunet.fr est une page parking.)",
        "how_to": "Consultez le site vous-même ; quand un concours vous intéresse, ouvrez la page de l'organisateur et ajoutez-la.",
        "unlock": "Accord écrit de l'éditeur (contact indiqué dans ses mentions légales).",
        "home": "https://www.concours-du-net.com/",
    },
}

DENIED_DOMAINS: dict[str, str] = {d: a["reason"] for d, a in AGGREGATORS.items() if not a["automated_extraction"] and a["modes"]}

# Autorisations écrites obtenues par l'utilisateur (réglage « written_authorizations »), chargées au démarrage
# et à chaque modification des réglages. Seule voie pour lever une restriction contractuelle (catégorie 6).
_AUTHORIZED: set[str] = set()


def set_authorizations(entries: list) -> None:
    _AUTHORIZED.clear()
    for e in entries or []:
        dom = (e.get("domain") if isinstance(e, dict) else str(e)).lower().removeprefix("www.").strip()
        ref = (e.get("reference") if isinstance(e, dict) else "") or ""
        if dom in AGGREGATORS and (not isinstance(e, dict) or len(ref.strip()) >= 5):
            _AUTHORIZED.add(dom)


def is_authorized(domain: str) -> bool:
    return domain in _AUTHORIZED


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _match(url: str) -> str | None:
    host = _host(url)
    for dom in AGGREGATORS:
        if host == dom or host.endswith("." + dom):
            return dom
    return None


def denial_reason(url: str) -> str | None:
    """Raison du refus de lecture automatique (catégorie 6), ou None si le site peut être lu."""
    dom = _match(url)
    if not dom or dom in _AUTHORIZED:
        return None
    return DENIED_DOMAINS.get(dom)


def aggregator_profile(url: str) -> dict | None:
    dom = _match(url)
    return {"domain": dom, **AGGREGATORS[dom]} if dom else None


def access_mode(kind: str, url: str) -> str:
    if denial_reason(url):
        return "assisted"
    if kind.startswith("aggregator"):
        return "public_source"
    return KIND_MODE.get(kind, "public_source")


def references() -> list[dict]:
    """Sites consultables seulement par l'utilisateur (consultation assistée + lien direct)."""
    out = []
    for dom, a in AGGREGATORS.items():
        if "assisted" in a["modes"] and dom not in _AUTHORIZED:
            out.append({"domain": dom, "name": a["name"], "url": a["home"], "reason": a["reason"], "how_to": a["how_to"],
                        "unlock": a["unlock"], "modes": [ACCESS_MODES[m] for m in a["modes"]]})
    return out


def matrix() -> list[dict]:
    """Matrice des autorisations et restrictions, une ligne par agrégateur audité."""
    rows = []
    for dom, a in AGGREGATORS.items():
        rows.append({"domain": dom, "name": a["name"], "automated_extraction": a["automated_extraction"] or dom in _AUTHORIZED,
                     "authorized_in_writing": dom in _AUTHORIZED,
                     "category_of_scan": a["category_of_scan"], "modes": [ACCESS_MODES[m] for m in a["modes"]],
                     "reason": a["reason"], "unlock": a["unlock"]})
    return rows
