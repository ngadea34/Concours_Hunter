"""Sites exclus de toute collecte automatique (décision fondée sur leurs CGU / robots.txt, vérifiés le 2026-11-20).

Un domaine listé ici ne peut être ni scanné ni activé comme source. Pour le réintégrer, il faut une
autorisation écrite de l'éditeur (à consigner dans docs/project/DECISIONS.md).
"""
from urllib.parse import urlsplit

DENIED_DOMAINS: dict[str, str] = {
    "jeu-concours.biz": "Les mentions légales interdisent sans autorisation écrite l'extraction automatisée et nomment les outils de participation automatisée ; /concours/ interdit à tous les robots.",
    "toutgagner.com": "Contenu réservé aux abonnés (organisateur, règlement, réponses) et reproduction même partielle interdite par les conditions d'utilisation.",
}


def denial_reason(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    for dom, why in DENIED_DOMAINS.items():
        if host == dom or host.endswith("." + dom):
            return why
    return None
