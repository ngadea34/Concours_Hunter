# État du projet — à relire en premier après une interruption

Dernière mise à jour : 2026-11-20 (UTC)
Dépôt : https://github.com/ngadea34/concours_hunter — `main` = phase 0 ; branche `socle-produit` = produit complet (PR ouverte).

| Phase | Statut | Preuve |
|---|---|---|
| 0 Audit | ✅ | AUDIT_PHASE0.md, MODEL_ROUTING.md |
| 1 Fondations | ✅ | `python -m app.cli serve` démarre ; UI servie sur :8765 |
| 2 Base de données | ✅ | 21 tables, migrations versionnées, WAL, sauvegarde/restauration testées |
| 3 Découverte | ✅ (fixtures) | RSS, HTML générique, dédup, provenance — tests `test_discovery.py` |
| 4 Agrégateurs | ✅ revu | Audit réel 2026-11-20 : LDDJ intégré (structure réelle) ; Jeu-concours.biz et ToutGagner exclus (CGU) ; Concours du Net inexistant. Aucun RSS sur ces sites |
| 5 Intelligence | ✅ | règles R0 7 langues + Ollama R1/R2 optionnel avec citations vérifiées |
| 6 Frontend | ✅ | 9 pages, vérifiées dans Chromium (bureau 1280px + mobile 390px, 0 erreur console) |
| 7 Participation | ✅ | semi/manuel + auto encadré, testé sur formulaire de démo local (Playwright) |
| 8 Gains | ✅ | cycle gain → réclamation → reçu testé ; anti-phishing |
| 9 Automatisation | ✅ | APScheduler, quotas, verrou, reprise, arrêt d'urgence |
| 10 Sécurité | ✅ | voir SECURITY_REVIEW.md (risques résiduels listés) |
| 11 Tests | ✅ | TEST_REPORT.md |
| 12 Livraison | ✅ | install.ps1 exécuté sur le PC de Nico (Windows 10, Python 3.12) : OK, 33/33 tests, serveur répond |

## Validation réelle sur le PC de Nico (2026-11-20)
- Installation : `install.ps1 -Dev` OK (Python 3.12), 38/38 tests, serveur répond.
- Scan Le Démon du Jeu : 128 concours en 108 s, 0 erreur, 0 appel à /toconc.php, ~5 s entre requêtes.
- Enrichissement de 30 concours : 157 s, 7 règlements récupérés, 2 qualifiés, 125 à vérifier, 1 expiré.
- Constat : la plupart des concours restent « à vérifier » faute de règlement accessible (beaucoup de concours sur réseaux sociaux sans règlement en ligne). C'est voulu : aucune décision de gratuité/éligibilité sans preuve.

## Agrégateur maison (v0.2, décision D13)
- Connecteur `site` : lit les sitemaps (robots.txt ou /sitemap.xml), sinon le flux RSS et les liens « concours » de la page d'accueil ou de `config.listing_url`. Écarte règlements, listes de gagnants, concours administratifs, pages d'index, pages de plus de 120 jours. Titre réel lu sur la page (og:title / h1).
- Suggestions (Sources > « Sites d'organisateurs à surveiller ») : domaines des concours déjà trouvés, hors réseaux sociaux, formulaires, raccourcisseurs, agrégateurs et sites exclus.
- Sources `site` scannées une fois par jour (config `interval_minutes` pour changer).
- Type de jeu `game_type` (migration v2 avec classement des concours existants), filtre catalogue et badge.

## Reste à faire
1. Faire grandir l'agrégateur maison : suivre les sites suggérés (Sources), et en ajouter à la main.
2. Jeu-concours.biz : seulement avec autorisation écrite d'EKOJEU (démarche de Nico).
3. Optionnel : notifications hors application (e-mail / ntfy), connecteur « pages gagnants ».
