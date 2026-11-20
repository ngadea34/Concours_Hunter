# Registre des consommations

Limite connue : fenêtre glissante « 5 heures » du compte Claude (pas de montant en euros visible). Comptage par sous-agent **non exposé de manière fiable** : les valeurs ci-dessous sont celles rapportées par l'outil quand elles existent, sinon « indisponible ».

| Date | Agent | Modèle | Tâche | Tokens in/out | Durée | Essais | Résultat |
|---|---|---|---|---|---|---|---|
| 2026-11-20 | principal | opus-5-5 | Phase 0 audit + docs | indisponible | ~10 min | 1 | OK |

Produit : les appels Ollama sont journalisés dans `audit_logs` (modèle, durée, tokens `prompt_eval_count`/`eval_count` renvoyés par Ollama).
