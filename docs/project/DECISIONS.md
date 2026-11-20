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
| D11 | 2026-11-20 | Concours du Net retiré (revu en D16 : le vrai site est concours-du-net.com, consultation assistée) | concoursdunet.com inexistant en DNS | L2 |
| D13 | 2026-11-20 | Agrégateur maison sur sources primaires : connecteur `site` (sitemaps + RSS + page concours du site organisateur), suggestions de sites à suivre tirées des concours déjà trouvés, type de jeu. On reprend l'organisation des agrégateurs (types de jeux, filtres, clôture proche), jamais leur contenu ; Jeu-concours.biz et ToutGagner ne sont ni lus ni rétro-analysés | Les CGU de ces deux sites interdisent l'extraction ; les pages des marques sont publiques et lues au rythme de robots.txt, une fois par jour | L2 |
| D12 | 2026-11-20 | (confirmé par D18) LDDJ seul agrégateur actif, sans /toconc.php ; URL organisateur déduite de l'attribut de suivi si l'hôte correspond | robots.txt interdit /toconc.php ; aucune clause anti-extraction | L2 |
| D14 | 2026-11-20 | M15 entièrement déterministe, heures stockées en UTC et calculées en UTC | Résultats reproductibles et testables ; pas de décalage d'une heure aux changements d'heure | L2 |
| D15 | 2026-11-20 | « Réalisée » exige une preuve (≥ 10 caractères ou capture), « gagné » exige un résultat vérifié | Directive M15 : jamais de participation ni de gain déclaré sans preuve | L2 |
| D16 | 2026-11-20 | Politique de sources révisée : 7 catégories, modes d'accès, consultation assistée pour Jeu-concours.biz et ToutGagner (lien direct + import de la page organisateur), jamais d'extraction automatisée de ces deux sites sans autorisation écrite | Directive de Nico : distinguer analyse publique, flux documentés, import volontaire, restriction contractuelle et contournement | L2 |
| D17 | 2026-11-20 | Indice A1 à A8 : bonus de classement à A1/A2, part A4 plafonnée (30 % par défaut), A7/A8 hors programme | Viser des participations réalisables plutôt qu'un volume de concours détectés | L2 |
| D18 | 2026-11-20 | LDDJ : lecture automatique maintenue par décision de Nico (proposition de suspension refusée), robots.txt respecté, /toconc.php jamais appelé ; Concours du Net = concours-du-net.com, consultation assistée | Audit : pas de clause sur LDDJ, mais même réseau que Jeu-concours.biz et droit des producteurs de bases de données (risque signalé à Nico) ; mentions légales de Concours du Net exigent un accord écrit | Nico |
| D19 | 2026-11-20 | M14 déterministe, sans LLM pour l'analyse ; lecture d'image optionnelle par modèle de vision local | Résultats reproductibles et testables, fonctionne sans GPU, aucune donnée envoyée hors du PC | L2 |
| D20 | 2026-11-20 | L'application prépare les dossiers mais ne les transmet jamais : l'utilisateur envoie lui-même sur le canal officiel puis enregistre l'envoi | Directive M14 : validation humaine avant toute transmission ; données bancaires jamais manipulées | L2 |
| D21 | 2026-11-20 | Open Food Facts compté comme « source tierce » seulement | Ses données de magasins sont collaboratives, pas une preuve de présence en rayon | L2 |
