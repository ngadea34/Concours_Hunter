# Registre des consommations

Limite connue : fenêtre glissante « 5 heures » du compte Claude (pas de montant en euros visible). Comptage par sous-agent **non exposé de manière fiable** : les valeurs ci-dessous sont celles rapportées par l'outil quand elles existent, sinon « indisponible ».

| Date | Agent | Modèle | Tâche | Tokens in/out | Durée | Essais | Résultat |
|---|---|---|---|---|---|---|---|
| 2026-11-20 | principal | opus-5-5 | Phase 0 audit + docs | indisponible | ~10 min | 1 | OK |

Produit : les appels Ollama sont journalisés dans `audit_logs` (modèle, durée, tokens `prompt_eval_count`/`eval_count` renvoyés par Ollama).
| 2026-11-20 | BROWSER | sonnet | Extension MV3 + tests | 85 017 (total rapporté, in/out non séparés) | 189 s | 1 | OK, 8/8 tests vérifiés par le principal |
| 2026-11-20 | FRONTEND | sonnet | UI React 9 pages | 124 196 (total rapporté) | 365 s | 1 | tsc+build OK (à revérifier en intégration) |
| 2026-11-20 | DOCUMENTATION | haiku | 3 guides utilisateur | 113 609 (total rapporté) | 129 s | 1 | OK, 1 affirmation corrigée (e-mail) |
| 2026-11-20 | principal | opus-5-5 | backend, tests, intégration, revue sécurité | non mesuré par tâche (contexte de session uniquement) | ~1 h | — | OK |
