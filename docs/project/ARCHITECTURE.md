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
                                                       ├─ analytics/    M08
                                                       ├─ security/     M07 chiffrement, jeton, assainissement
                                                       ├─ admin/        M12 sauvegarde, restauration, diagnostic
                                                       ├─ i18n/         M06 langues, pays, devises
                                                       └─ db/           M03 SQLAlchemy 2 + SQLite (WAL) + migrations
```

## Principes
- **Connecteurs = plugins** : une classe `Connector` par type (RSS, HTML générique, agrégateur). Les sources sont des lignes en base (`sources`) ; ajouter une source RSS/HTML ne touche pas au cœur. Un nouveau type = un fichier dans `discovery/connectors/` enregistré par décorateur.
- **Respect des sites** : `robots.txt` vérifié avant chaque requête, User-Agent honnête, délai minimal par domaine, cache HTTP (ETag/Last-Modified + hash du contenu). Aucun contournement de CAPTCHA, login, paywall ou géoblocage : ces cas sont marqués `needs_human`.
- **Décisions justifiées** : chaque champ qualifié porte `evidence` (extrait littéral) et `method` (`rule`, `llm:<modèle>`, `human`). Une décision critique sans preuve → statut `to_verify`.
- **Cache d'analyse** : `contest_rules.content_hash` (SHA-256 du texte normalisé). Analyse réutilisée tant que le hash ne change pas ; changement → réanalyse + notification.
- **Participation** : politique par concours (`automation_policies`). `auto` seulement si le règlement n'interdit pas l'automatisation **et** que l'utilisateur a donné un consentement global **et** qu'il n'y a ni CAPTCHA ni connexion. Sinon `semi` (préremplissage, l'humain clique « valider ») ou `manual`.
- **Données personnelles** : profil chiffré (Fernet, clé locale `data/secret.key`), jamais envoyées hors du poste sauf dans un formulaire de participation validé.
- **Accès** : écoute `127.0.0.1` par défaut ; mode LAN (smartphone) activable, protégé par jeton.

## Modèle de données (M03)
Tables : contests, organizers, sources, source_connectors, contest_rules, eligibility, prizes, answers, participations, participation_proofs, results, claims, user_profile, consents, browser_sessions, automation_policies, scan_jobs, notifications, audit_logs, settings, schema_version.
Voir `backend/app/db/models.py`.

## Scores (Partie VI)
- Fiabilité /100 : organisateur identifié (15), règlement présent (20), gratuité vérifiée (20), éligibilité FR vérifiée (20), dates cohérentes (10), lots cohérents (5), source sûre HTTPS/réputation (10).
- Intérêt /100 : valeur du lot (30), intérêt personnel par catégorie (20), temps estimé (15), nombre de gagnants (15), complexité (10), absence de frais (5), livraison FR (5).
- Jamais présentés comme probabilité de gain.
