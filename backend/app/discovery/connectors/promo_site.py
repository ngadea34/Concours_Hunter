"""Connecteur « opérations promotionnelles » (M14) : pages d'offres de remboursement, « 100 % remboursé », jeux avec achat,
publiées par les sites des fabricants, marques et enseignes. Même mécanique que le connecteur « site » (sitemaps, RSS,
page des offres), avec un filtre d'URL propre aux promotions. Les pages trouvées deviennent des promotions (shop/discover.py).
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from ..base import register
from .site import EXCLUDE_PATH, SiteConnector

PROMO_PATH = re.compile(r"rembours|odr\b|offre[-_]de[-_]rembours|satisfait[-_]ou[-_]rembours|100[-_]?(pourcent|%25|%)|cashback|"
                        r"offres?[-_](promo|speciales?|du[-_]moment)|bons?[-_]plans?|operations?[-_]commerciales?|jeu[-_]avec[-_]achat|"
                        r"achetez[-_]et|ticket[-_]gagnant|promotions?/", re.I)
PROMO_TITLE = re.compile(r"rembours|satisfait ou|cashback|offre (de|découverte|speciale|spéciale)|achetez et|ticket gagnant|"
                         r"jeu avec achat|bon d.achat", re.I)
EXCLUDE = re.compile(r"mentions|cgu|cgv|privacy|cookies|recrutement|\.(pdf|jpe?g|png|gif|webp|mp4|xml|gz)$", re.I)


@register
class PromoSiteConnector(SiteConnector):
    kind = "promo_site"
    description = "Site d'un fabricant, d'une marque ou d'une enseigne : offres de remboursement et jeux avec achat (M14)."

    def is_target(self, url: str) -> bool:
        path = unquote(urlsplit(url).path).lower()
        if not path or path == "/" or EXCLUDE.search(path):
            return False
        return bool(PROMO_PATH.search(path))

    def title_ok(self, title: str) -> bool:
        return bool(PROMO_TITLE.search(title))


_ = EXCLUDE_PATH
