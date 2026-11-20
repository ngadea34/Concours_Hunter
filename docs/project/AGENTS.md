# Agents et contrats de mission

L'agent principal (COORDINATOR + ARCHITECT + BACKEND + SECURITY, modèle L2) écrit le cœur : il est seul à toucher `backend/app/db`, `security`, `api`.
Sous-agents mobilisés seulement sur des périmètres de fichiers disjoints :

| Agent | Modèle | Périmètre (fichiers) | Statut |
|---|---|---|---|
| FRONTEND | sonnet (L1) | `frontend/**` | voir TASKS.md |
| BROWSER (extension) | sonnet (L1) | `extension/**` | voir TASKS.md |
| DOCUMENTATION | haiku (L0) | `docs/user/**` | voir TASKS.md |
| QA, DISCOVERY, INTELLIGENCE, REWARDS | agent principal | backend | intégrés |

Format de contrat : objectif, périmètre, fichiers, dépendances (contrat d'API `docs/project/API.md`), niveau, livrables, tests, critères d'acceptation, compte rendu ≤ 15 lignes.
