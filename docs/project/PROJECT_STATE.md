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

## Reste à faire
1. Scan réel LDDJ sur le PC de Nico (connecteur calé sur la structure relevée, à confirmer en conditions réelles).
2. Trouver d'autres sources autorisées (RSS de médias/marques) : aucune des 3 sources joignables n'a de RSS.
3. Jeu-concours.biz : seulement avec autorisation écrite d'EKOJEU (démarche de Nico).
4. Optionnel : notifications e-mail/push (aujourd'hui : notifications dans l'application).
