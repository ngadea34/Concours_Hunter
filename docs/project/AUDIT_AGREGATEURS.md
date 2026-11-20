# Audit des agrégateurs, matrice des autorisations et étude des interfaces publiques

Date : 2026-11-20. Audit non intrusif réalisé depuis le PC de Nico (le conteneur de développement n'atteint pas ces sites).
Méthode : lecture seule, User-Agent honnête `ConcoursHunter-audit/0.3`, robots.txt lu avant toute page et appliqué (aucun chemin interdit demandé), au moins 6 s entre deux requêtes, au plus 12 requêtes par site, aucune connexion, aucun appel AJAX, aucun formulaire envoyé. Aucune liste de concours n'a été gardée : seules la structure des pages et les textes légaux ont été étudiés.

Les clauses des CGU sont résumées avec leur URL (le texte intégral reste sur le site). Chaque site est jugé séparément : les conditions de l'un ne sont pas supposées s'appliquer à l'autre, et une donnée publique n'est pas supposée libre de réutilisation.

## Catégories d'usage (directive « politique de sources »)

| # | Usage | Par défaut |
|---|---|---|
| 1 | Consultation normale des informations publiques | autorisé |
| 2 | Analyse technique du fonctionnement public | autorisé (cet audit) |
| 3 | Flux ou interfaces officiellement documentés | autorisé selon leurs conditions |
| 4 | API ou données sous licence | autorisé selon la licence |
| 5 | Import de données fournies par l'utilisateur | autorisé |
| 6 | Extraction automatisée soumise à restriction contractuelle | **non autorisé sans accord écrit** |
| 7 | Contournement de protections techniques | **toujours interdit** |

## Matrice des autorisations et restrictions

| | Jeu-concours.biz | Le Démon du Jeu (LDDJ) | ToutGagner | Concours du Net |
|---|---|---|---|---|
| Éditeur | SARL EKOJEU | SARL Reflexe Media | EURL PLUG'N PRESS | Concours du Net (auto-entrepreneur) |
| Clause contre l'extraction | Oui, détaillée (base de données, robots, sitemaps, outils dérivés, participation automatisée) | Pas de CGU ; « Tous droits réservés » | Oui (« script de parsing », extraction, copie) | Exploitation interdite sans accord écrit |
| robots.txt | Bloque nommément plusieurs robots de concours ; `/concours/`, `/goto.php` interdits | `/toconc.php`, `/toconcclos.php`, autocomplétion interdits | Ne bloque qu'un robot d'IA | Espace membre et `/ajax/` interdits |
| Flux RSS / Atom | Non | Non | Non | Non |
| API publique | Non (JSON-LD de référencement) | Non | Non | Non |
| Anti-robot visible | reCAPTCHA (formulaires) ; journalisation annoncée | reCAPTCHA (formulaires) | Blocage IP annoncé | Cloudflare Turnstile (formulaires) |
| Catégorie d'un scan automatique | 6 | 1 (pas de clause ; voir ci-dessous) | 6 | 6 |
| Mode retenu dans Concours Hunter | Consultation assistée, lien direct, ajout de la page organisateur | Source publique (listes publiques, robots.txt respecté), décision de Nico | Consultation assistée | Consultation assistée |
| Pour aller plus loin | Accord écrit via le formulaire de contact (sans réponse = refus, selon les CGU) | Accord écrit de Reflexe Media (une demande couvre LDDJ et Jeu-concours.biz) | Accord écrit (rédaction) | Formulaire de contact, objet « Organisateur / partenariat » |

**LDDJ.** Le site n'a pas de CGU écrites, mais il forme un réseau commercial unique avec Jeu-concours.biz : les deux pages « organisateurs » proposent une diffusion simultanée, avec le même contact commercial. Par ailleurs, une base de concours reste protégée par le droit des producteurs de bases de données (CPI L.341-1, L.342-1 et L.342-2), même sans clause : l'extraction répétée et systématique de parties non substantielles est interdite. Une suspension par prudence a été proposée ; Nico a choisi de maintenir la lecture automatique (décision D18). Le connecteur lit seulement les listes publiques, à cadence réduite, respecte robots.txt et n'appelle jamais `/toconc.php`. Si l'éditeur s'y oppose, il suffit de désactiver la source.

**Concours du Net.** `concoursdunet.com` n'existe pas et `concoursdunet.fr` est une page de parking. Le vrai site est `concours-du-net.com`.

## Fiches (A à J)

### Jeu-concours.biz
- **A. Conditions :** <https://www.jeu-concours.biz/mentionslegales.php>, section « Base de données & extraction ». Les fiches forment une base de données dont EKOJEU est le producteur. Sans autorisation écrite : extraction substantielle ou répétée interdite ; robots, scripts, navigateurs automatisés, API non officielles et sitemaps interdits pour collecter les fiches ; création d'un outil concurrent ou dérivé, « notamment un outil de participation automatisée », interdite. Usages permis : consultation normale, partage individuel d'une fiche à titre privé, courte citation avec lien, indexation par les moteurs qui respectent robots.txt. Accès automatisés journalisés 90 jours ; sanctions rappelées (CPI L.343-4).
- **B. Réutilisation :** interdite sans accord écrit, hors partage privé fiche par fiche et courte citation.
- **C. robots.txt :** blocage total de PrizzyBot, PersonalCompTracker, Declic, MyConcours, ConcoursBot, giveaway-bot, MitspielBot et d'autres ; pour tous : `/staging/`, `/deal/`, `/notif/`, `/concours/`, `/goto.php`, `/archives-jeux-concours.html`. Quatre sitemaps déclarés, sans index.
- **D. Flux :** aucun (`/feed`, `/rss` : 404).
- **E. API :** aucune ; JSON-LD de référencement (WebSite, Organization, FAQPage, CollectionPage, Event, Review).
- **F. Pages publiques :** accueil, listes par fréquence, par note, par date de clôture, par organisateur, par pays ; fiche `/{aaaa}/{mm}/{jj}/{slug}.html` ; participation `concours/{id}.html` (interdite aux robots).
- **G. Import manuel :** partage individuel autorisé ; boutons de partage social ; aucun export.
- **H. Outils automatisés :** interdits (CGU), robots de concours bloqués nommément ; pas de Cloudflare ; reCAPTCHA sur les formulaires ; aucun blocage pendant l'audit.
- **I. Contact :** formulaire <https://www.jeu-concours.biz/contact.php> ; page organisateurs <https://www.jeu-concours.biz/organisateurs.php>.
- **J. Technique :** PHP sans CMS, Apache, jQuery, Bootstrap 3, PWA. Carte `article.bloc-concours`, lots `div.concours-cadeaux`, mécanique `ul.picto-bulle`. Le lien vers l'organisateur passe toujours par la redirection interdite aux robots. Mises à jour : compteurs quotidiens, listes par date de clôture, `lastmod` des sitemaps.

### Le Démon du Jeu (LDDJ)
- **A. Conditions :** pas de CGU ; <https://www.ledemondujeu.com/mentions-legales.php> ne contient aucune clause sur l'extraction ou les robots ; pied de page « Tous droits réservés ».
- **B. Réutilisation :** aucune politique écrite, ce qui ne vaut pas autorisation (droit des bases de données ; réseau commun avec Jeu-concours.biz).
- **C. robots.txt :** `Disallow: /toconc.php`, `/toconcclos.php`, `/content/ajax/ajax-recherche-suggestions.php`. Pas de sitemap.
- **D. Flux :** aucun. **E. API :** aucune ; JSON-LD sur les fiches seulement. L'application mobile est une vue web.
- **F. Pages publiques :** nouveautés et clôtures par jour, listes par lot et par mécanique, fiche `/{domaine-organisateur}-{slug}.php`, participation `toconc.php?c={id}` (interdite aux robots).
- **G. Import manuel :** favoris réservés aux membres ; pas d'export.
- **H. Outils automatisés :** pas de clause ; reCAPTCHA sur les formulaires ; pas de Cloudflare.
- **I. Contact :** <https://www.ledemondujeu.com/contact.php> ; partenariats via la page <https://www.ledemondujeu.com/organisateurs.php> (même régie que Jeu-concours.biz).
- **J. Technique :** PHP, Apache, jQuery 3, Bootstrap 4. Carte `article.bloc-article`, pictos `li.bloc-article-pictos-item`. Le domaine de l'organisateur figure dans le slug de la fiche (c'est ce que le connecteur utilisait pour retrouver la page organisateur sans appeler `toconc.php`).

### ToutGagner
- **A. Conditions :** <https://toutgagner.com/guide/conditions.html>. Art. 3 : contenu propriété de l'éditeur, copie et intégration interdites, courtes citations permises avec lien ; navigation avec VPN, anonymiseur, « script de parsing » ou logiciel d'extraction interdite (comptes bloqués). Art. 4 : outils modifiant l'affichage interdits, blocage d'IP possible ; affichage des pages de jeux réservé aux inscrits à la newsletter. Pied de page : reproduction même partielle interdite.
- **B. Réutilisation :** interdite, hors courte citation avec lien.
- **C. robots.txt :** ne bloque que « The Knowledge AI ». robots.txt permissif n'est pas une autorisation : les CGU priment.
- **D. Flux :** aucun. **E. API :** aucune ; interface organisateurs privée chez l'éditeur.
- **F. Pages publiques :** listes par lot et par date d'ajout ; participation `/concours/c{id}.html` (redirection vers l'organisateur).
- **G. Import manuel :** bookmarklet de l'éditeur (non étudié), proposition de concours par les organisateurs ; aucun export.
- **H. Outils automatisés :** interdits (CGU), blocage IP annoncé ; pas de Cloudflare.
- **I. Contact :** <https://toutgagner.com/guide/contacts.html>.
- **J. Technique :** PHP, nginx, jQuery 3, Bootstrap 3. Carte `article.box`, bouton `a.btn.participer`.

### Concours du Net (concours-du-net.com)
- **A. Conditions :** pas de CGU ; <https://www.concours-du-net.com/mentions-legales>, section « Propriété intellectuelle » : reproduction, diffusion ou exploitation non autorisée du site ou de ses contenus interdite sauf autorisation écrite préalable.
- **B. Réutilisation :** interdite sans accord écrit.
- **C. robots.txt :** tout autorisé sauf `/adminnn/`, `/ajax/`, `/include/`, `/stripe/`, `/mes-concours`, `/mon-profil`, `/concoursplus-dashboard` ; index de sitemap déclaré (pages, concours, organisateurs).
- **D. Flux :** aucun. **E. API :** aucune ; endpoints `/ajax/` privés et interdits.
- **F. Pages publiques :** nouveautés datées, sélection, dernière chance, archives, organisateurs ; fiche `/jeu-concours-{organisateur}-{id}` ; participation par redirection suivie `/track.php`.
- **G. Import manuel :** bouton « Copier le lien » et partage sur chaque fiche ; aucun export.
- **H. Outils automatisés :** clause générale ; Cloudflare Turnstile sur les formulaires.
- **I. Contact :** <https://www.concours-du-net.com/contact>, objet « Organisateur / partenariat ».
- **J. Technique :** PHP, Tailwind, scripts maison ; carte `article.concours-card` avec attributs `data-participation-url`, `data-share-url`.

## Rapport d'étude des interfaces publiques (rétro-ingénierie légitime)
- Les quatre sites sont des applications PHP rendues côté serveur, sans API publique ni flux. Toutes les données structurées visibles (JSON-LD) servent au référencement, pas à la réutilisation.
- Le lien vers l'organisateur passe toujours par une redirection interne (`concours/{id}.html`, `toconc.php`, `/concours/c{id}.html`, `track.php`) ; deux de ces redirections sont interdites aux robots. Concours Hunter ne les suit jamais automatiquement.
- Les mécanismes de mise à jour visibles sont des pages datées (nouveautés du jour, clôtures du jour) et des `lastmod` de sitemap : c'est ce qu'un accord de flux pourrait exposer proprement.
- Aucune protection n'a été rencontrée ni contournée pendant l'audit.

## Ce que fait Concours Hunter
1. **Aucun collecteur automatique** pour Jeu-concours.biz, ToutGagner et Concours du Net sans accord écrit enregistré (LDDJ : voir D18). Le planificateur ignore ces domaines même si une source est activée par erreur ; le récupérateur les refuse.
2. **Consultation assistée** : page Sources, lien direct, explication. L'utilisateur ouvre le site lui-même.
3. **Import par l'utilisateur** : il ajoute la page de l'organisateur (extension « Ajouter cette page », ou import d'adresses). Coller l'adresse d'une fiche d'agrégateur renvoie une explication au lieu de lire la fiche.
4. **Sources primaires** : sites des organisateurs (sitemaps, flux RSS, pages concours) suivis depuis Sources, une fois par jour, dans le respect de robots.txt.
5. **Autorisation écrite** : saisie dans Réglages (site, date, référence). Elle réactive la lecture automatique de ce seul site.
