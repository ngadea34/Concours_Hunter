# Journal des modifications

## 0.3.0 — 2026-11-20
Programme de la semaine (M15, « Hunter Weekly Command ») : page **Ma semaine** avec 8 indicateurs et navigation entre semaines (lundi → dimanche, fuseau configurable, passage heure d'été/hiver correct) ; participations prioritaires planifiées dans le budget de temps (30 min/jour par défaut) avec accepter / refuser / reporter / favori / marquer réalisé (preuve obligatoire) ; résultats attendus (dates de tirage et de publication lues dans le règlement, sinon estimées et signalées comme telles ; « gagné » seulement avec un résultat vérifié) ; dernières chances 24 h / 48 h / 7 j / 14 j ; opportunités (jamais converties en participation) ; section Shop & Promo (remboursements conditionnels distincts des remboursements reçus) ; gestionnaire de tâches avec historique ; synthèse du lundi 8 h, bilan du dimanche 18 h, synthèse quotidienne optionnelle, impression/PDF ; rappels 48 h et alertes 24 h sans doublon ; commandes `/hunter-week` (interface et CLI). Migration v4 : 9 tables (`weekly_*`, `promotions`). Dépendance `tzdata` pour Windows.

## 0.2.1 — 2026-11-20
Corrections après l'essai réel sur 5 sites d'organisateurs : l'URL d'un jeu trouvé sur un site suivi n'est plus remplacée par un lien externe de la page (playlist, agenda) ; « Je joue ! » retiré des titres ; pages de liste (« jeux-concours-c.html ») écartées ; sitemaps en www reconnus ; statut explicite quand un site ne donne aucune page de jeu ; type « réseaux sociaux » plus déclenché par les pieds de page ; navigateurs Playwright du dossier `.playwright-browsers` trouvés sans variable d'environnement. Migration v3 : répare les concours concernés et recalcule les types.

## 0.2.0 — 2026-11-20
Agrégateur maison : connecteur « site organisateur » (sitemaps, flux RSS, page concours ; une visite par jour), suggestions de sites de marques à surveiller à partir des concours déjà trouvés, type de jeu (tirage au sort, instant gagnant, quiz, créatif, réseaux sociaux) avec filtre et badge, migration v2 qui classe les concours existants.

## 0.1.0 — 2026-11-20
Première version complète : découverte (RSS, HTML, 4 agrégateurs), qualification multilingue des règlements avec justifications, scores, déduplication, base de réponses, participation assistée et automatique encadrée, extension navigateur, gains et réclamations, anti-phishing, notifications, planificateur, sauvegardes, interface web responsive, installateur Windows, documentation.
