# Architecture — Concours Hunter

Application web **local-first** : un seul processus Python (FastAPI + Uvicorn) sert l'API, l'interface React compilée et le planificateur. Données dans `data/` (SQLite + preuves + sauvegardes + clé de chiffrement).

```
navigateur PC / smartphone ──HTTP(S) LAN + jeton──► FastAPI (backend/app/main.py)
extension MV3 ──localhost + jeton──────────────────►   ├─ api/          routes REST /api/*
                                                       ├─ discovery/    M01 + M13 connecteurs (plugins)
                                                       ├─ intelligence/ M02 règles + Ollama optionnel, scores
                                                       ├─ participation/M04 + M11 politiques, préremplissage, Playwright
                                                       ├─ rewards/      M05 résultats, gains, réclamations, anti-phishing
                                                       ├─ notifications/M09
                                                       ├─ scheduler/    M10 APScheduler, quotas, arrêt d'urgence
                                                       ├─ weekly/       M15 programme de la semaine
                                                       ├─ analytics/    M08
                                                       ├─ security/     M07 chiffrement, jeton, assainissement
                                                       ├─ admin/        M12 sauvegarde, restauration, diagnostic
                                                       ├─ i18n/         M06 langues, pays, devises
                                                       └─ db/           M03 SQLAlchemy 2 + SQLite (WAL) + migrations
```

## Principes
- **Connecteurs = plugins** : une classe `Connector` par type (RSS, HTML générique, agrégateur). Les sources sont des lignes en base (`sources`) ; ajouter une source RSS/HTML ne touche pas au cœur. Un nouveau type = un fichier dans `discovery/connectors/` enregistré par décorateur.
- **Multisource** : chaque source a son connecteur et son mode d'accès (`discovery/policy.py` : API officielle, flux autorisé, données sous licence, source publique réutilisable, import utilisateur, import par partage navigateur, consultation assistée, référence externe). Une source en erreur est isolée, les autres continuent. Les sites dont l'extraction automatisée est interdite par contrat (catégorie 6) restent utiles en consultation assistée : l'utilisateur ouvre le site, puis ajoute la page de l'organisateur. Aucune copie d'une base protégée.
- **Respect des sites** : `robots.txt` vérifié avant chaque requête, User-Agent honnête, délai minimal par domaine, cache HTTP (ETag/Last-Modified + hash du contenu). Aucun contournement de CAPTCHA, login, paywall ou géoblocage : ces cas sont marqués `needs_human`.
- **Décisions justifiées** : chaque champ qualifié porte `evidence` (extrait littéral) et `method` (`rule`, `llm:<modèle>`, `human`). Une décision critique sans preuve → statut `to_verify`.
- **Cache d'analyse** : `contest_rules.content_hash` (SHA-256 du texte normalisé). Analyse réutilisée tant que le hash ne change pas ; changement → réanalyse + notification.
- **Participation** : politique par concours (`automation_policies`). `auto` seulement si le règlement n'interdit pas l'automatisation **et** que l'utilisateur a donné un consentement global **et** qu'il n'y a ni CAPTCHA ni connexion. Sinon `semi` (préremplissage, l'humain clique « valider ») ou `manual`.
- **Données personnelles** : profil chiffré (Fernet, clé locale `data/secret.key`), jamais envoyées hors du poste sauf dans un formulaire de participation validé.
- **Accès** : écoute `127.0.0.1` par défaut ; mode LAN (smartphone) activable, protégé par jeton.

## Modèle de données (M03)
Tables : contests, organizers, sources, source_connectors, contest_rules, eligibility, prizes, answers, participations, participation_proofs, results, claims, user_profile, consents, browser_sessions, automation_policies, scan_jobs, notifications, audit_logs, settings, schema_version ; M15 (migration v4) : weekly_preferences, weekly_plans, weekly_plan_items, weekly_results, weekly_tasks, weekly_task_history, weekly_notifications, weekly_reports, promotions.
Voir `backend/app/db/models.py`.

## Scores (Partie VI)
- Fiabilité /100 : organisateur identifié (15), règlement présent (20), gratuité vérifiée (20), éligibilité FR vérifiée (20), dates cohérentes (10), lots cohérents (5), source sûre HTTPS/réputation (10).
- Intérêt /100 : valeur du lot (30), intérêt personnel par catégorie (20), temps estimé (15), nombre de gagnants (15), complexité (10), absence de frais (5), livraison FR (5).
- Jamais présentés comme probabilité de gain.

## Programme de la semaine (M15)
- **Candidats prioritaires** : qualifié ou participé, gratuit (ou voie gratuite), éligible FR, non clos, fiabilité ≥ 60, intérêt ≥ 40 (réglables), règlement officiel présent, pas déjà joué sur la période.
- **Score** : 0,5·intérêt + 0,25·fiabilité + urgence (15/10/5) + 1,5·intérêt personnel + 8 si favori − pénalité de temps − complexité. Priorité haute ≥ 65, moyenne ≥ 45.
- **Planification** : sélection par score dans la capacité (minutes/jour × jours actifs) et l'objectif hebdomadaire, puis répartition au plus tôt (échéance la plus proche d'abord). Jamais complétée avec des concours peu intéressants.
- **Décisions reportées d'une semaine à l'autre** : refusé reste refusé, reporté revient à sa date, favori conservé.
- **Tâches** : générées avec une clé unique (`auto_key`) depuis les participations acceptées, les opportunités suivies, les résultats, les réclamations et les promotions ; échéance recalculée sur les données réelles sauf si l'utilisateur l'a modifiée ; expiration automatique.
- **Notifications** : clé de dédoublonnage incluant la date de clôture (une date modifiée → nouveau rappel). Alertes urgentes immédiates ; rappels non urgents groupés dans la synthèse quotidienne.

## Indice d'automatisabilité et difficulté
`intelligence/automatability.py` classe chaque concours : A1 formulaire web, A2 quiz, A3 e-mail, A4 réseau social, A5 créatif, A6 action humaine (CAPTCHA, compte, courrier, SMS, magasin), A7 achat, A8 impossible ou non vérifiable. Ordre de priorité des règles : A8, A7, A5, A4, A6, A3, A2, A1. Difficulté 1 à 5 = base de la classe + CAPTCHA / connexion / courrier. L'indice ne déclenche jamais seul une participation automatique : la politique d'automatisation reste prioritaire.
