# Journal des décisions

| # | Date | Décision | Raison | Niveau |
|---|---|---|---|---|
| D1 | 2026-11-20 | Pas de Docker, installation `venv` + PowerShell | Cible Windows 10, simplicité | L2 |
| D2 | 2026-11-20 | Pas de Scrapy ; httpx + BeautifulSoup + feedparser | Volume faible, moins de dépendances, async simple | L2 |
| D3 | 2026-11-20 | SQLite WAL + migrations maison versionnées (pas Alembic) | Une seule base locale, migrations simples, zéro outil en plus | L2 |
| D4 | 2026-11-20 | Un seul processus (API + UI + planificateur) | Installation et reprise simples | L2 |
| D5 | 2026-11-20 | LLM local optionnel (Ollama HTTP), règles d'abord | 0 €/mois, fonctionne sans GPU | L2 |
| D6 | 2026-11-20 | Dépôt Git local en attendant un dépôt GitHub | Aucun dépôt attaché au projet | L2 |
| D7 | 2026-11-20 | Connecteurs agrégateurs testés sur fixtures | Sites bloqués par le proxy du conteneur | L2 |
| D8 | 2026-11-20 | L'extension ne soumet jamais seule : préremplit, l'humain valide | Respect des CGU et du consentement | L2 |
