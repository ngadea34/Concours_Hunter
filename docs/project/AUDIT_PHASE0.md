# Rapport d'audit — Phase 0 (2026-11-20)

## 1. Environnement de développement (conteneur cloud où je travaille)
| Élément | Constat (mesuré) |
|---|---|
| OS | Linux x86_64 (conteneur éphémère) |
| CPU / RAM | 4 vCPU, 15 Go RAM, pas de swap |
| Disque | ~61 Go disponibles |
| Python | 3.13 (+ `uv`) |
| Node / npm | 22.x / 10.9 |
| Git | 2.43, **aucun dépôt GitHub attaché au projet** → dépôt Git local |
| Navigateur | Chromium + Playwright préinstallés |
| Docker | présent mais **non utilisé** (cible Windows 10, pas de dépendance Docker) |
| Ollama | absent du conteneur |
| Réseau | PyPI et npm accessibles. **Les sites de concours (jeu-concours.biz, ledemondujeu.com, toutgagner.com, concoursdunet.com) sont bloqués par le proxy du conteneur** (code 000). Les connecteurs ne peuvent donc pas être validés contre les vrais sites depuis ici : ils sont testés sur des fixtures HTML/RSS et devront être validés sur la machine de Nico. |

## 2. Machine cible (poste de Nico, observé via le lien appareil)
| Élément | Constat |
|---|---|
| Nom / OS | DESKTOP-V2HV765, **Windows (win32 x64)** |
| Ollama | dossier `~/.ollama` présent → Ollama probablement installé. **Modèles installés non vérifiés** (aucun dossier partagé, je n'ai pas lu le contenu). |
| Python / Node / RAM / disque / GPU | **Non mesurés** (nécessite une session sur le poste). Le script `scripts/doctor.ps1` les mesure à l'installation. |

## 3. Modèles IA et délégation (mesuré dans cette session)
| Capacité | Constat |
|---|---|
| Modèle principal | `claude-opus-5-5` (contexte 1M, fenêtre effective ~480k avec compaction auto) |
| Sous-agents | Outil `Agent` disponible, sélection de modèle par agent : `haiku`, `sonnet`, `opus`, `fable` |
| Niveau de raisonnement | réglable par agent (`low` → `max`) — utilisé uniquement si nécessaire |
| Parallélisation | sous-agents en arrière-plan, isolation possible en *git worktree* |
| Agent Teams | pas de mécanisme dédié observé ; équivalent = sous-agents + worktrees |
| Comptage des tokens | contexte global de la session visible ; **coût par sous-agent non exposé de façon fiable** → noté « estimé » ou « indisponible » dans TOKEN_BUDGET.md |
| Limites | limite glissante « 5 heures » du compte (statut : *allowed* au démarrage) ; pas de budget en euros visible |
| Reprise | fichiers de suivi dans le dépôt + mémoire de projet partagée |

## 4. Modèles IA du produit (à l'exécution chez Nico, 0 €/mois)
- Couche 0 : règles déterministes (regex multilingues, listes de pays, motifs d'achat) — toujours active.
- Couche 1 : petit modèle Ollama local (ex. `qwen3.5:4b`) — optionnel.
- Couche 2 : modèle Ollama moyen (ex. `qwen3:8b` / `llama3.1:8b`) — optionnel, seulement si la couche 1 échoue.
- Aucune API payante. Si Ollama est absent, le produit fonctionne en mode règles seules (les cas ambigus partent en vérification humaine).

## 5. Conclusions
- Stack de référence retenue (Python/FastAPI/SQLite/SQLAlchemy/React/TS/APScheduler/Playwright/MV3), sans Docker, sans Scrapy (httpx + BeautifulSoup suffisent, Scrapy n'apporte rien au volume visé).
- Limitation majeure : sites agrégateurs inaccessibles depuis le cloud → connecteurs livrés et testés sur fixtures, validation réelle à faire sur le poste.

## Addendum 2026-11-20 — PC de Nico (mesuré)
Windows 10 Famille 19045 · i9-9900 (8c/16t) · 64 Go RAM · RTX 2060 SUPER 8 Go · 506 Go libres sur C: · Python 3.11/3.12/3.14 · Node 26 · Git 2.55.
Ollama : qwen3:30b-a3b, qwen3:14b, qwen3.5:9b, qwen3:8b, qwen3.5:4b. Recommandation : R1 = qwen3.5:4b, R2 = qwen3:8b (tiennent dans les 8 Go de VRAM).
