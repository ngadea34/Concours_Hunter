# Routage des modèles

## A. Développement (agents Claude Code)
| Niveau | Modèle | Usage | Effort |
|---|---|---|---|
| L0 | `haiku` | docs, traductions i18n, tests simples, fixtures, conventions | défaut |
| L1 | `sonnet` | composants frontend, extension, connecteurs isolés, tests d'intégration | défaut |
| L2 | `opus` (agent principal) | architecture, schéma BDD, sécurité, intégration, revue finale | moyen |
| L3 | `opus` effort élevé ou `fable` (niveau non documenté ici, non utilisé par défaut) | uniquement : corruption de données, faille critique, échecs répétés | élevé |

Escalade : L0 → L1 → L2 → L3, une marche à la fois, motif noté dans DECISIONS.md.
Chaque sous-agent reçoit un contrat de mission (AGENTS.md) et seulement les fichiers utiles.
Aucun résultat de sous-agent n'est accepté sans vérification par l'agent principal (fichiers, build, tests).

## B. Produit (à l'exécution, `backend/app/intelligence/llm.py`)
| Niveau | Moteur | Déclenchement |
|---|---|---|
| R0 | règles déterministes | toujours |
| R1 | Ollama petit modèle (`CH_LLM_MODEL_SMALL`) | champ non résolu par R0 |
| R2 | Ollama modèle moyen (`CH_LLM_MODEL_LARGE`) | R1 incohérent / non conforme au schéma |
| Humain | file « à vérifier » | R2 échoue ou décision critique (gratuité, pays) sans citation du règlement |

Règle : toute décision critique issue d'un LLM doit citer un extrait littéral du règlement présent dans le texte source, sinon elle est rejetée.
