"""M13 : connecteurs des agrégateurs spécialisés.

IMPORTANT (limitation documentée) : ces sites étaient inaccessibles depuis l'environnement de
développement (proxy). Les sélecteurs ci-dessous sont des points de départ NON VÉRIFIÉS sur les
vrais sites : ils sont configurables par source (Paramètres > Sources > config) et le connecteur
retombe sur l'heuristique générique si aucun élément ne correspond. Seules les pages publiques
autorisées par robots.txt sont lues ; aucune connexion, aucun espace membre, aucun contournement.
Avant d'activer une source, l'utilisateur doit vérifier les CGU du site (champ tos_note).
"""
from __future__ import annotations

from collections.abc import Iterator

from ..base import RawContest, register
from .html_listing import HtmlListingConnector

TOS = ("Usage personnel, pages publiques uniquement, robots.txt respecté, cadence limitée. "
       "Vérifiez les CGU du site avant activation ; désactivez la source si elles interdisent la collecte automatisée.")


class _Aggregator(HtmlListingConnector):
    tos_note = TOS
    community = True

    def discover(self) -> Iterator[RawContest]:
        items = list(super().discover())
        if not items and self.config.get("item"):
            # sélecteurs obsolètes : repli heuristique, signalé dans le statut de la source
            self.config = {**self.config, "item": None}
            self.source.last_status = "sélecteurs non trouvés, repli heuristique"
            items = list(super().discover())
        for it in items:
            it.extra["aggregator"] = self.kind
            yield it


@register
class JeuConcoursBiz(_Aggregator):
    kind = "aggregator:jeu-concours-biz"
    description = "Jeu-concours.biz (annuaire de concours)."
    default_config = {**HtmlListingConnector.default_config, "item": "article, .concours, .jeu", "title": "h2, h3, .titre", "end_date": ".date, .fin, time", "prize": ".lot, .dotation"}


@register
class LeDemonDuJeu(_Aggregator):
    kind = "aggregator:lddj"
    description = "Le Démon du Jeu (LDDJ), communauté avec réponses publiées."
    default_config = {**HtmlListingConnector.default_config, "item": "article, .concours, tr.jeu", "title": "h2, h3, .titre, a", "end_date": ".date, .fin, time", "prize": ".lot"}


@register
class ToutGagner(_Aggregator):
    kind = "aggregator:toutgagner"
    description = "ToutGagner.com."
    default_config = {**HtmlListingConnector.default_config, "item": "article, .concours, .jeu", "title": "h2, h3, .title", "end_date": ".date, time", "prize": ".lot, .gain"}


@register
class ConcoursDuNet(_Aggregator):
    kind = "aggregator:concoursdunet"
    description = "Concours du Net."
    default_config = {**HtmlListingConnector.default_config, "item": "article, .concours, .jeu", "title": "h2, h3, .titre", "end_date": ".date, .cloture, time", "prize": ".lot"}
