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
| D9 | 2026-11-20 | Jeu-concours.biz exclu (policy.py) | Mentions légales : extraction automatisée et outils de participation automatisée interdits sans autorisation écrite d'EKOJEU | L2 |
| D10 | 2026-11-20 | ToutGagner exclu | Organisateur/règlement/réponses réservés aux abonnés, reproduction interdite | L2 |
| D11 | 2026-11-20 | Concours du Net retiré | Domaine inexistant en DNS | L2 |
| D13 | 2026-11-20 | Agrégateur maison sur sources primaires : connecteur `site` (sitemaps + RSS + page concours du site organisateur), suggestions de sites à suivre tirées des concours déjà trouvés, type de jeu. On reprend l'organisation des agrégateurs (types de jeux, filtres, clôture proche), jamais leur contenu ; Jeu-concours.biz et ToutGagner ne sont ni lus ni rétro-analysés | Les CGU de ces deux sites interdisent l'extraction ; les pages des marques sont publiques et lues au rythme de robots.txt, une fois par jour | L2 |
| D12 | 2026-11-20 | LDDJ seul agrégateur actif, sans /toconc.php ; URL organisateur déduite de l'attribut de suivi si l'hôte correspond | robots.txt interdit /toconc.php ; aucune clause anti-extraction | L2 |
