# Guide utilisateur de Concours Hunter

Concours Hunter repère les jeux-concours gratuits, vérifie leur règlement, prépare vos participations et suit vos résultats. Tout reste sur votre ordinateur.

Ce que l'application fait : elle lit des pages publiques, analyse les règlements, classe les concours et vous aide à participer. Ce qu'elle ne fait jamais est décrit à la fin de ce guide.

## 1. Premier démarrage

1. Lancez l'application avec `scripts\start.bat` (voir INSTALLATION.md).
2. Ouvrez **Réglages**, puis remplissez votre **profil** : prénom, nom, e-mail, téléphone, date de naissance, adresse, code postal, ville, pays.
   Le profil est chiffré sur votre ordinateur. Il n'est envoyé à un site que dans un formulaire de participation que vous validez.
3. Dans **Réglages**, section **Consentements**, choisissez ce que vous autorisez :
   - **Participation automatique** : l'application peut soumettre seule un formulaire, uniquement si le règlement l'autorise clairement, sans CAPTCHA ni connexion. Décochée par défaut.
   - **Conservation des preuves** : l'application garde des captures d'écran de vos participations.
   - **Notifications par e-mail** : consentement enregistré, mais l'envoi d'e-mails n'est pas encore disponible dans cette version (notifications dans l'application uniquement).
4. Ouvrez **Sources**. La source Le Démon du Jeu est **désactivée** à l'installation : lisez sa note puis activez-la.
5. Avant d'activer une source, lisez sa **note sur les CGU** (conditions générales d'utilisation du site). Si les CGU interdisent la collecte automatisée, ne l'activez pas.
6. Activez ensuite les sources que vous acceptez. Le planificateur les parcourt automatiquement.

Jeu-concours.biz et ToutGagner sont exclus : leurs conditions d'utilisation interdisent la collecte automatique ou réservent le contenu aux abonnés. Concours du Net n'existe plus. Le robot ne suit jamais le lien « Voir le concours » de Le Démon du Jeu (interdit par son robots.txt) : vous pouvez, vous, cliquer dessus depuis la fiche.

## 1 bis. Votre agrégateur : surveiller les sites des marques

L'application ne dépend pas d'un seul site agrégateur. Dans **Sources**, la rubrique **« Sites d'organisateurs à surveiller »** liste les marques et médias dont elle a déjà trouvé des concours. Cliquez sur **Surveiller** : une fois par jour, l'application lira les pages de jeux publiées par ce site (son plan du site, son flux RSS ou sa page concours), dans le respect de son fichier robots.txt, et ajoutera ses nouveaux concours au catalogue. Vous pouvez aussi saisir un nom de domaine (ex. `marque.fr`).

Dans le **Catalogue**, le filtre **Type de jeu** trie les concours comme sur les sites spécialisés : tirage au sort, instant gagnant, quiz, créatif (photo, recette…), réseaux sociaux. Le type n'est affiché que lorsqu'il est établi par le texte du concours.

Jeu-concours.biz et ToutGagner ne sont pas lus par l'application : leurs conditions d'utilisation l'interdisent. Vous pouvez les consulter vous-même et ajouter un concours qui vous intéresse avec l'extension, depuis la page de l'organisateur.

## 1 ter. Ma semaine : votre programme

La page **Ma semaine** répond à la question « qu'est-ce que je fais cette semaine ? ».

- **En haut** : 8 indicateurs (participations prévues, faites, résultats attendus, clôtures proches, tâches, gains à réclamer…) et des flèches pour changer de semaine. La semaine va du lundi au dimanche.
- **Programme** : les meilleurs concours gratuits, ouverts en France, avec règlement, répartis jour par jour dans votre temps disponible (30 min par jour par défaut, réglable). Pour chacun : **Accepter**, **Refuser**, **Reporter**, **Favori**. **Marquer réalisé** demande une preuve (numéro de confirmation, texte du message reçu ou capture) : sans preuve, une participation n'est jamais comptée.
- **Résultats** : quand le tirage et la publication des gagnants sont prévus. Une date « estimée » n'a pas été trouvée dans le règlement. L'application n'annonce jamais un gain sans preuve officielle vérifiée.
- **Dernières chances** : ce qui ferme dans 24 h, 48 h, 7 jours, 14 jours.
- **Opportunités** : concours intéressants hors programme. « Suivre » ne fait que les garder à l'œil.
- **Shop & Promo** : offres de remboursement et concours avec achat. Les montants « conditionnels » ne sont pas encore reçus.
- **Tâches** : à faire, en cours, en attente, faite, annulée, expirée, avec historique. Vous pouvez ajouter les vôtres.
- **Rapports** : synthèse du lundi 8 h, bilan du dimanche 18 h, synthèse quotidienne si vous l'activez. Bouton **Imprimer** pour un PDF.
- **Réglages** : fuseau horaire, heures des synthèses, rappel 48 h et alerte 24 h avant clôture, minutes par jour, jours actifs, objectif de la semaine, intérêt et fiabilité minimum.

La barre de commande accepte `/hunter-week plan`, `results`, `deadlines`, `opportunities`, `tasks`, `report`, `next`, `settings minutes_per_day=45`. Les mêmes commandes existent en ligne de commande : `python -m app.cli hunter-week plan`.

## 2. Le cycle d'un concours

Chaque concours suit ce parcours :

| Étape | Statut affiché | Ce qui se passe |
|---|---|---|
| Découvert | Nouveau | Un scan a trouvé le concours dans une source. |
| Analysé | Qualifié | Les règles le jugent gratuit, accessible en France, non expiré, et sans obstacle. |
| Incertain | À vérifier | Un point critique est flou : c'est à vous de trancher. |
| Écarté | Rejeté | Un critère bloquant (achat obligatoire, pays exclu, etc.) a été trouvé. |
| Terminé | Expiré | La date de fin est dépassée. |
| Participé | Participé | Une participation existe. |
| Rangé | Archivé | Vous l'avez mis de côté. |

Ensuite, pour une participation :

| Étape | Statut | Signification |
|---|---|---|
| Préparée | Préparée | L'application a préparé les données. |
| En attente | En attente de vous | Vous devez soumettre le formulaire. |
| Soumise | Soumise | Vous avez indiqué avoir cliqué sur « Envoyer ». |
| Confirmée | Confirmée | Le site a confirmé la réception. |
| Échec | Échec | Une erreur a eu lieu. |
| Annulée | Annulée | Vous avez annulé la participation. |

Après le tirage, vous enregistrez le **résultat** (gagné, perdu, en attente). Si vous avez gagné, vous ouvrez une **réclamation** pour récupérer le lot (voir section 8).

## 3. Comprendre les scores

Chaque concours a deux scores sur 100.

- **Fiabilité** : l'organisateur est-il identifié, le règlement est-il présent, la gratuité et l'éligibilité en France sont-elles vérifiées, les dates et les lots sont-ils cohérents, la source est-elle sûre.
- **Intérêt** : valeur du lot, intérêt que vous avez indiqué pour sa catégorie, temps estimé, nombre de gagnants, complexité, absence de frais, livraison en France.

**Ces scores ne sont jamais une probabilité de gagner.** Un score élevé signifie seulement que le concours est bien documenté et qu'il vous intéresse. Vous pouvez régler votre intérêt par catégorie dans **Réglages**, section **Poids d'intérêt**.

## 4. Justifications et règlement

Chaque décision de l'application (gratuit, éligible, automatisation autorisée, etc.) est accompagnée d'une **justification** : la règle appliquée, l'extrait du règlement qui la fonde, et la méthode (règle automatique, IA locale, ou décision humaine).

Vérifiez toujours l'extrait avant de participer. Si l'extrait manque, la décision est considérée comme incertaine et le concours passe dans « À vérifier ».

## 5. La file « À vérifier » et la validation humaine

La page **À vérifier** regroupe les concours dont une décision critique n'est pas sûre. Pour chacun :

1. Lisez le règlement sur le site de l'organisateur.
2. Si besoin, collez le texte du règlement dans la fiche du concours et relancez l'analyse.
3. Validez vous-même le point incertain (gratuité ou éligibilité) avec votre décision et, si vous voulez, l'extrait qui la justifie.

L'application ne tranche jamais seule un point critique sans preuve.

## 6. Les trois modes de participation

Le mode est choisi pour chaque concours.

**Automatique.** L'application peut soumettre le formulaire seule. Ce mode n'est possible que si **toutes** ces conditions sont réunies :
- le règlement autorise explicitement les moyens automatisés ;
- vous avez coché le consentement « Participation automatique » ;
- il n'y a ni CAPTCHA, ni connexion, ni participation par réseau social.

Le planificateur tente les participations automatiques environ toutes les 30 minutes, cinq au maximum à la fois.

**Semi-automatique.** L'application prépare le formulaire (champs remplis) et vous le soumettez vous-même. C'est le cas le plus courant.

**Manuel.** Le concours exige une action humaine (CAPTCHA, connexion, participation par courrier ou SMS, réseau social). L'application affiche les informations et vous faites tout.

## 7. Utiliser l'extension du navigateur

L'extension (voir INSTALLATION.md, section 7) travaille sur la page du concours :

1. Dans l'application, préparez la participation (statut « En attente de vous »).
2. Ouvrez la page du concours et cliquez sur l'icône de l'extension.
3. Cliquez sur **Préremplir**. Les champs remplis sont entourés de vert, les champs requis non reconnus en orange.
4. Cochez vous-même les consentements, résolvez le CAPTCHA s'il y en a un, puis **envoyez le formulaire vous-même**.
5. Une fois le formulaire envoyé par vous, cliquez sur **J'ai soumis**. L'extension envoie une capture de l'onglet comme preuve (si vous avez accepté la conservation des preuves), puis l'application enregistre la soumission.

L'extension ne soumet jamais de formulaire, ne clique jamais sur un bouton d'envoi, et ne touche ni aux cases à cocher ni aux champs de mot de passe ou de CAPTCHA. Pour les formulaires en plusieurs étapes, relancez « Préremplir » à chaque étape. Les cases à cocher et les choix multiples restent à remplir à la main.

## 8. Double participation, gains et réclamations

**Double participation bloquée.** Pour une même période (une fois, par jour, etc.), l'application refuse une seconde participation au même concours. Elle refuse aussi un concours clôturé ou qui exige un achat.

**Enregistrer un résultat.** Dans la page **Résultats**, indiquez le résultat (gagné, perdu, en attente) et, si vous voulez, collez le message reçu et son expéditeur.

**Score anti-arnaque.** Chaque message de gain reçoit un score de suspicion sur 100 (100 = très suspect). Le score additionne des signaux repérés dans le message, par exemple :
- un paiement demandé pour recevoir le lot ;
- une demande de coordonnées bancaires, de carte ou de mot de passe ;
- un moyen de paiement difficile à tracer (mandat, cryptomonnaie, carte prépayée) ;
- une pression de temps (« sous 24 h ») ;
- un lien raccourci ;
- un expéditeur sur une messagerie gratuite, ou un domaine différent de celui de l'organisateur ;
- aucune participation enregistrée pour ce concours.

Un message suspect déclenche une notification. Un score élevé ne prouve pas une arnaque, mais il faut être très prudent : ne payez rien et ne transmettez aucune donnée bancaire pour « recevoir » un lot. Vérifiez le gain directement auprès de l'organisateur, sur son site officiel. Vous pouvez marquer le résultat comme vérifié.

**Réclamations.** Un gain peut donner lieu à une réclamation : nom du lot, date limite, frais éventuels, valeur. Statuts : à réclamer, réclamé, reçu, expiré, refusé. L'application vous rappelle les échéances. Vérifiez la date limite le plus tôt possible.

## 9. Notifications

La page **Notifications** regroupe les alertes : concours qui clôturent dans les 3 jours, messages de gain suspects, CAPTCHA à terminer, réclamations proches de l'échéance. Vous pouvez les marquer comme lues, une à une ou toutes ensemble.

## 10. Statistiques

La page **Tableau de bord** donne les chiffres principaux : concours trouvés, qualifiés, à vérifier, participations, temps passé, réclamations ouvertes.

Attention à deux notions différentes :
- la **valeur des lots auxquels vous avez participé** est la somme de la valeur des lots des concours où vous avez joué ;
- les **gains réellement obtenus** ne sont comptés que si vous avez enregistré un gain.

Une valeur élevée de lots joués ne signifie pas que vous avez gagné quoi que ce soit.

## 11. Arrêt d'urgence

Dans **Réglages**, section **Planificateur** :
- **Mettre en pause** arrête les tâches automatiques jusqu'à ce que vous cliquiez sur **Reprendre**.
- **ARRÊT D'URGENCE** met en pause immédiatement et interrompt les requêtes en cours. Il vous demande une confirmation.

Pour couper toute activité, utilisez l'arrêt d'urgence, puis fermez la fenêtre de commandes.

## 12. Ce que l'application ne fera jamais

- contourner un CAPTCHA, une connexion, un blocage géographique (géoblocage) ou les conditions générales d'un site ;
- acheter quoi que ce soit, ou participer à un concours qui exige un achat ;
- soumettre un formulaire sans votre consentement ;
- envoyer vos données ailleurs que dans un formulaire que vous validez ;
- présenter un score comme une chance de gagner.

Si un concours demande un CAPTCHA ou une connexion, l'application vous le signale et c'est à vous de finir.
