# État du projet — à relire en premier après une interruption

Dernière mise à jour : 2026-11-20 (UTC)
Dépôt : https://github.com/ngadea34/concours_hunter — `main` = v0.2.1 (PR #1 à #6 fusionnées) ; branche `programme-semaine` = v0.3.0 (M15, PR #7) ; branche `politique-sources` = v0.4.0 (politique de sources, basée sur programme-semaine).

Ordre des directives de Nico (2026-11-20) : 1) M15 Programme de la semaine (fait, v0.3.0) ; 2) révision de la politique de sources (fait, v0.4.0) ; 3) M14 Shop & Promo.

| Phase | Statut | Preuve |
|---|---|---|
| 0 Audit | ✅ | AUDIT_PHASE0.md, MODEL_ROUTING.md |
| 1 Fondations | ✅ | `python -m app.cli serve` démarre ; UI servie sur :8765 |
| 2 Base de données | ✅ | 30 tables (v4), migrations versionnées, WAL, sauvegarde/restauration testées |
| 3 Découverte | ✅ (fixtures) | RSS, HTML générique, dédup, provenance — tests `test_discovery.py` |
| 4 Agrégateurs | ✅ revu (v0.4) | Audit A à J du 2026-11-20 (AUDIT_AGREGATEURS.md) : les 4 sites en consultation assistée, aucune lecture automatique sans accord écrit (Réglages). LDDJ suspendu car même réseau que Jeu-concours.biz. Aucun RSS ni API |
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

## Essai réel des sites d'organisateurs (PC de Nico, 2026-11-20)
- Migration v2 OK (sauvegarde auto), 46/46 tests (après avoir pointé PLAYWRIGHT_BROWSERS_PATH ; corrigé en 0.2.1).
- 15 sites suggérés depuis les 128 concours. 5 suivis et scannés en 8 min 47 : ici.fr 2 concours, leclub-bricolage.fr 1 (page de liste, corrigé), lillelanuit.com 5 (URL remplacée par une playlist Deezer, corrigé), arte.tv refusé par robots.txt (correct), francetelevisions.fr 0 (sitemap en www ignoré, corrigé).

## Programme de la semaine (M15, v0.3.0)
- Code : `backend/app/weekly/` (timeutil, prefs, plan, results, tasks, shop, view, reports, tick, commands), routes `api/weekly_routes.py`, page `frontend/src/pages/Week.tsx`.
- Tout est déterministe (aucun LLM). Heures stockées en UTC naïf, affichées dans le fuseau des préférences (Europe/Paris par défaut).
- Job `weekly` toutes les 15 min : rafraîchit, envoie les rappels, génère synthèse du lundi / bilan du dimanche (avec rattrapage si le PC était éteint).
- Garde-fous : participation « réalisée » seulement avec preuve ; « gagné » seulement avec résultat vérifié et score anti-phishing < 50 ; opportunité jamais convertie en participation ; remboursement « reçu » seulement avec montant constaté.
- 22 tests `test_weekly.py` couvrent les 16 cas de la directive.

## Politique de sources (v0.4.0)
- Audit A à J et matrice : AUDIT_AGREGATEURS.md. Accords écrits : réglage `written_authorizations` (Réglages), seul moyen de réactiver un site.
- `discovery/policy.py` : catégories d'usage 1 à 7, modes d'accès, fiche par agrégateur (`AGGREGATORS`), matrice. Audit : AUDIT_AGREGATEURS.md.
- `discovery/imports.py` : import CSV / liste d'adresses, sans requête réseau ; refuse les sites en consultation assistée avec explication.
- `discovery/quality.py` : contrôle qualité par source (GET /api/sources/{id}/quality).
- `intelligence/automatability.py` : A1 à A8 + difficulté, posés par `qualify` (migration v5 pour l'existant).
- Classement M15 : bonus A1 +6, A2 +5, A3 +2, A4 −3, A5/A6 −6 ; A7/A8 exclus ; part A4 plafonnée (`social_share_max`) ; filtres dans les préférences hebdo.
- Scheduler : chaque source isolée (try/except) ; un domaine en consultation assistée n'est jamais scanné.

## Reste à faire
0. M14 Shop & Promo (voir ROADMAP). Demandes d'accord écrit (Reflexe Media pour LDDJ + Jeu-concours.biz, ToutGagner, Concours du Net) : démarche de Nico, contacts dans AUDIT_AGREGATEURS.md.
1. Faire grandir l'agrégateur maison : suivre les sites suggérés (Sources), et en ajouter à la main.
2. Jeu-concours.biz : seulement avec autorisation écrite d'EKOJEU (démarche de Nico).
3. Optionnel : notifications hors application (e-mail / ntfy), connecteur « pages gagnants ».
