# Maintenance de Concours Hunter

Ce document explique comment protéger vos données, restaurer, mettre à jour, diagnostiquer et régler l'application. Les commandes se lancent dans PowerShell, depuis la racine du projet, sauf indication contraire.

## 1. Où sont vos données

Tout est dans le dossier `data\`, à la racine du projet :

| Élément | Rôle |
|---|---|
| `data\concours.db` | La base de données (concours, participations, résultats, réglages). |
| `data\secret.key` | La clé qui chiffre votre profil. |
| `data\token.txt` | Le jeton d'accès (smartphone, extension). |
| `data\proofs\` | Les captures de vos participations. |
| `data\backups\` | Les sauvegardes. |
| `data\concours-hunter.log` | Le journal technique. |

Le dossier `data\` ne doit jamais être supprimé pendant une mise à jour.

## 2. Sauvegardes

**Sauvegardes automatiques.** L'application crée une sauvegarde chaque jour, environ 5 minutes après son démarrage, puis toutes les 24 heures tant qu'elle tourne. Elles sont rangées dans `data\backups\` sous la forme `concours-AAAAMMDD-HHMMSS-auto.db`.

**Nombre conservé.** Dix sauvegardes sont conservées. Au-delà, les plus anciennes sont supprimées automatiquement.

**Sauvegarde manuelle.** Deux moyens :
- dans l'application : **Réglages**, section **Administration**, bouton **Créer une sauvegarde** ;
- en double-cliquant sur `scripts\backup.bat`, qui crée une sauvegarde et attend que vous fermiez la fenêtre.

Pour lister les sauvegardes existantes :

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.cli backups
cd ..
```

### Point important : copiez aussi la clé et le jeton

**Une sauvegarde de la base ne suffit pas.** Votre profil est chiffré avec `data\secret.key`. Sans cette clé, le profil est illisible, même avec la sauvegarde. Le jeton `data\token.txt` est nécessaire pour reconnecter votre smartphone et l'extension.

Les sauvegardes automatiques ne contiennent que la base. Pour une protection complète, copiez régulièrement sur un autre support (clé USB, disque externe, autre dossier) :
- `data\secret.key`
- `data\token.txt`
- le dossier `data\backups\`
- le dossier `data\proofs\` si vous souhaitez garder vos captures

Conservez la copie de `secret.key` séparément de la copie de la base si vous le pouvez : c'est la clé de votre profil personnel.

## 3. Restaurer une sauvegarde

Restaurer remplace les données actuelles par celles de la sauvegarde. **Avant de restaurer, l'application sauvegarde automatiquement l'état actuel** (nom contenant `pre-restore`), donc rien n'est perdu définitivement.

**Par l'interface.** Ouvrez **Réglages**, section **Administration**, choisissez la sauvegarde dans la liste **Sauvegardes**, cliquez sur **Restaurer** puis confirmez.

**Par la ligne de commande.** Fermez d'abord l'application (fenêtre de commandes fermée), puis :

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.cli restore concours-20261120-030000-auto.db
cd ..
```

Remplacez le nom par celui de votre sauvegarde (voir la commande `backups`). Relancez ensuite `scripts\start.bat`.

## 4. Mise à jour

Avant toute mise à jour, l'application sauvegarde déjà vos données. Vous pouvez aussi lancer `scripts\backup.bat` avant.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\update.ps1
```

Le script :
1. crée une sauvegarde ;
2. récupère le nouveau code avec Git (`git pull --ff-only`), si le projet a été cloné avec Git ;
3. met à jour les dépendances ;
4. applique les migrations de la base.

Si vous n'avez pas Git (téléchargement en ZIP), le script affiche un message et continue : vous devez alors remplacer vous-même les fichiers du projet par la nouvelle version. Gardez le dossier `data\` et le dossier `.venv\` : ne les remplacez pas. Relancez ensuite `scripts\update.ps1` pour les dépendances et les migrations.

En cas d'échec de `git pull`, c'est souvent parce que vous avez modifié des fichiers du projet. Ne forcez rien : demandez de l'aide avant de continuer.

## 5. Diagnostic

Pour vérifier l'installation :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\doctor.ps1
```

Le script affiche le système, la mémoire, la version de Node, l'état d'Ollama, puis un rapport de l'application : version, chemin des données, espace disque libre, intégrité de la base, version du schéma, modèles Ollama trouvés, présence de Playwright (participation automatique) et de l'interface compilée.

Si la base est signalée comme non intègre, arrêtez l'application et restaurez la dernière sauvegarde saine (section 3).

## 6. Journaux

- **Journal technique** : `data\concours-hunter.log`. Il tourne automatiquement à 2 Mo et garde trois anciennes versions. Joignez-le si vous demandez de l'aide.
- **Journal d'audit** : dans **Réglages**, section **Administration**, bouton **Charger les journaux**. Il affiche les 100 dernières actions enregistrées (par exemple ajout de source, arrêt d'urgence, enregistrement d'un résultat).

## 7. Sources : ajouter, activer, régler

### Ajouter une source RSS ou HTML

1. Ouvrez **Sources**, puis **Ajouter une source**.
2. Renseignez le nom, le type (**RSS** si le site propose un flux RSS, **HTML** sinon), l'adresse, la langue et le pays.
3. Vérifiez la note sur les CGU du site, puis activez la source si elle vous convient.
4. Cliquez sur **Lancer un scan** pour tester. L'historique des scans apparaît sous la liste.

### Les quatre agrégateurs

Jeu-concours.biz, Le Démon du Jeu, ToutGagner et Concours du Net sont livrés **désactivés**. Leurs connecteurs n'ont pas pu être testés sur les vrais sites pendant le développement. Activez-les un par un, après avoir lu leurs CGU, et contrôlez les premiers résultats.

### Quand un site change

Si un site change sa mise en page, le connecteur peut ne plus trouver les concours. L'application revient alors à une lecture générique et l'indique dans le statut de la source (« sélecteurs non trouvés, repli heuristique »). Dans ce cas :

- les **sélecteurs CSS** (item, title, link, end_date, prize, next, max_pages) sont stockés dans le champ `config` de la source ; leurs valeurs par défaut figurent dans `backend\app\discovery\connectors\html_listing.py` et `aggregators.py` ;
- le formulaire de l'interface ne propose pas de champ pour modifier ce champ `config`, à ma connaissance. Pour régler les sélecteurs, il faut passer par l'interface de programmation (API, voir `docs/project/API.md`) ou demander l'aide d'un développeur.

Sans réglage, le plus simple est de désactiver la source tant qu'elle ne fonctionne pas.

## 8. Réglages techniques et quotas

Dans **Réglages** :
- **Intervalle de scan** : durée minimale entre deux scans d'une même source (valeur par défaut 180 minutes, minimum 15).
- **Quota de requêtes** par domaine et par heure (valeur par défaut 30, entre 1 et 600). Il protège les sites visités.
- **Mode LAN** : voir INSTALLATION.md, section 6. Il prend effet au redémarrage.

Le délai minimal entre deux requêtes vers un même site est de 5 secondes par défaut (variable `CH_MIN_DELAY_PER_DOMAIN_S`, voir le tableau ci-dessous). Le réglage `llm_max_calls_per_day` (200 par défaut) limite les appels à l'IA locale par jour. Il n'apparaît pas dans l'interface : il ne se modifie qu'avec l'interface de programmation (API).

L'application respecte `robots.txt` et ne contourne ni CAPTCHA, ni connexion, ni blocage. Ne modifiez pas ces règles pour « accélérer » les scans.

### Variables de configuration (avancé)

L'application lit des variables `CH_...` dans l'environnement ou dans un fichier `.env` placé à la racine du projet. Ne les modifiez que si vous savez pourquoi :

| Variable | Défaut | Rôle |
|---|---|---|
| `CH_DATA_DIR` | `data\` | Dossier des données. |
| `CH_HOST` | `127.0.0.1` | Adresse d'écoute (le mode LAN passe à toutes les adresses). |
| `CH_PORT` | `8765` | Port de l'application. |
| `CH_LOG_LEVEL` | `INFO` | Niveau de détail du journal. |
| `CH_MAX_BACKUPS` | `10` | Nombre de sauvegardes conservées. |
| `CH_SCHEDULER_ENABLED` | `true` | Active le planificateur. |
| `CH_SEED_SOURCES` | `true` | Crée les quatre agrégateurs (désactivés) au premier lancement. |
| `CH_MIN_DELAY_PER_DOMAIN_S` | `5` | Délai minimal entre deux requêtes vers un même site. |
| `CH_HTTP_TIMEOUT` | `20` | Délai d'attente des requêtes, en secondes. |

## 9. Recompiler l'interface (développeurs)

L'interface compilée est déjà livrée dans le projet. Vous n'en avez besoin que si vous modifiez le code de l'interface. Il faut Node.js 18 ou plus récent.

```powershell
scripts\build-frontend.bat
```

Le script installe les dépendances de `frontend\` puis compile l'interface.

## 10. Lancer les tests (développeurs)

Tests du serveur :

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
cd ..
```

Tests de l'extension (Node.js requis, depuis la racine du projet) :

```powershell
node --test extension/test/
```

Les tests de l'extension incluent un test de bout en bout avec Chromium, ignoré si Playwright n'est pas installé.

## 11. Arrêter ou suspendre l'activité

- **Pause** et **Reprendre** : dans **Réglages**, section **Planificateur**.
- **ARRÊT D'URGENCE** : même section. Il interrompt les tâches et les requêtes en cours.
- Pour arrêter complètement, fermez la fenêtre de commandes lancée par `scripts\start.bat`.
