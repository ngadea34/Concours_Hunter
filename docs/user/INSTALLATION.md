# Installer Concours Hunter sur Windows

Concours Hunter fonctionne entièrement sur votre ordinateur. Rien n'est installé comme un logiciel classique : le programme s'exécute depuis un dossier, dans une fenêtre de commandes, et s'affiche dans votre navigateur (Edge, Chrome, Firefox).

Ce guide suppose Windows 10 ou Windows 11. Vous n'avez pas besoin de droits administrateur.

## 1. Prérequis

| Élément | Obligatoire | Remarque |
|---|---|---|
| Python 3.11 ou plus récent | Oui | Installé depuis python.org ou avec winget. |
| Git | Non | Utile pour récupérer et mettre à jour le code. Sinon, téléchargez le dépôt en fichier ZIP. |
| Ollama | Non | Permet l'IA locale. Sans Ollama, tout fonctionne en mode règles. |
| Node.js 18 ou plus récent | Non | Nécessaire seulement pour recompiler l'interface (voir MAINTENANCE.md). |

Pour installer Python, ouvrez PowerShell et tapez :

```powershell
winget install Python.Python.3.12
```

Vous pouvez aussi télécharger Python sur https://www.python.org/downloads/. Pendant l'installation, cochez la case « Add python.exe to PATH ».

## 2. Récupérer le code

Option A : avec Git.

```powershell
cd $HOME\Documents
git clone https://github.com/ngadea34/concours_hunter
cd concours_hunter
```

Option B : sans Git. Ouvrez https://github.com/ngadea34/concours_hunter, cliquez sur « Code » puis « Download ZIP », décompressez l'archive dans un dossier de votre choix (par exemple `Documents\concours_hunter`).

## 3. Lancer l'installation

Dans PowerShell, placez-vous dans le dossier du projet et lancez :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

Le script :
1. cherche une version de Python 3.11 ou plus récente ;
2. crée l'environnement `.venv` à la racine du projet ;
3. installe les dépendances ;
4. installe le navigateur Chromium utilisé pour la participation automatique (environ 150 Mo) ;
5. prépare la base de données et lance un diagnostic.

Si vous ne voulez pas installer Chromium (la participation automatique ne fonctionnera pas, le reste reste disponible), ajoutez l'option `-NoBrowser` :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -NoBrowser
```

Attendez le message « Installation terminée ». En cas d'erreur en rouge, lisez la section Dépannage ci-dessous.

## 4. Démarrer l'application

1. Double-cliquez sur `scripts\start.bat` (ou lancez-le depuis PowerShell).
2. Une fenêtre de commandes reste ouverte : c'est normal, elle fait tourner l'application. Ne la fermez pas pendant que vous l'utilisez.
3. Votre navigateur s'ouvre à l'adresse **http://127.0.0.1:8765**. Si ce n'est pas le cas, copiez cette adresse dans la barre du navigateur.

Pour arrêter l'application, fermez la fenêtre de commandes.

## 5. Ajouter des données de démonstration (facultatif)

Pour découvrir l'interface avec des concours fictifs :

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.cli demo-data
cd ..
```

Les concours de démonstration portent le préfixe **[DÉMO]**. Ils sont fictifs : ne participez jamais à l'un d'eux.

## 6. Accéder depuis un smartphone (mode LAN)

Par défaut, l'application n'accepte que votre ordinateur. Pour l'utiliser depuis un téléphone connecté au même Wi-Fi :

1. Dans l'application, ouvrez **Réglages** et activez **Mode LAN**. N'activez ce mode que sur un réseau de confiance.
2. Fermez la fenêtre de commandes, puis relancez `scripts\start.bat`. Le changement n'est pris en compte qu'au redémarrage.
3. Récupérez votre jeton d'accès :

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.cli token
cd ..
```

4. Trouvez l'adresse IP de votre PC sur le Wi-Fi :

```powershell
ipconfig
```

Repérez la ligne « Adresse IPv4 » de la carte Wi-Fi (par exemple `192.168.1.25`).

5. Sur le téléphone, ouvrez le navigateur et tapez `http://192.168.1.25:8765` (avec votre adresse). Saisissez le jeton quand l'application le demande.

Pare-feu Windows : si Windows demande d'autoriser Python à accéder aux réseaux, cochez **Réseaux privés** et validez. Si vous avez refusé, le téléphone ne pourra pas se connecter. Le projet ne fournit pas de règle de pare-feu automatique ; ce réglage se fait dans la sécurité Windows.

Le jeton est un secret : ne le partagez pas.

## 7. Installer l'extension du navigateur (facultatif)

L'extension remplit les formulaires d'un concours avec les données préparées par l'application. Elle se charge en mode développeur, sans passer par un magasin d'extensions.

1. Ouvrez `chrome://extensions` (Chrome) ou `edge://extensions` (Edge).
2. Activez **Mode développeur**.
3. Cliquez sur **Charger l'extension non empaquetée** et choisissez le dossier `extension` du projet.
4. Ouvrez les réglages de l'extension : l'adresse du serveur est `http://127.0.0.1:8765` par défaut. Si vous utilisez le jeton, saisissez-le dans le champ prévu.

Le détail du fonctionnement est dans le fichier `extension\README.md`. Firefox peut aussi charger l'extension, en temporaire, depuis `about:debugging`.

## 8. IA locale (facultatif) : Ollama

L'IA locale aide à lire les règlements ambigus. Elle est facultative : sans elle, l'application utilise uniquement des règles, et les cas ambigus sont renvoyés vers la file « À vérifier ».

1. Installez Ollama depuis https://ollama.com.
2. Téléchargez les modèles (commandes standard d'Ollama) :

```powershell
ollama pull qwen3.5:4b
ollama pull qwen3:8b
```

3. Dans l'application, ouvrez **Réglages**, section **IA locale (Ollama)**, et cochez **Activer l'IA locale**.

Les modèles par défaut sont `qwen3.5:4b` (petit modèle) et `qwen3:8b` (grand modèle). L'adresse d'Ollama doit rester sur votre ordinateur (`http://127.0.0.1:11434`).

## 9. Dépannage

**Le port 8765 est déjà utilisé.** Une autre instance de Concours Hunter tourne peut-être encore. Fermez les fenêtres de commandes ouvertes, puis relancez `scripts\start.bat`. Si le problème persiste, redémarrez le PC.

**« Python 3.11+ introuvable ».** Installez Python (voir section 1), puis fermez et rouvrez PowerShell avant de relancer `install.ps1`. Vérifiez avec `python --version`.

**Python est introuvable alors qu'il est installé.** Cochez « Add python.exe to PATH » lors de l'installation, ou désinstallez Python et réinstallez-le avec cette case cochée.

**« Impossible d'exécuter des scripts » ou « ExecutionPolicy ».** Ne modifiez pas la configuration de Windows : lancez le script avec la commande de la section 3, qui contient `-ExecutionPolicy Bypass` et ne vaut que pour ce script.

**Le message « Lancez d'abord scripts\install.ps1 » s'affiche.** L'installation n'a pas abouti. Relancez `install.ps1` et lisez les messages d'erreur.

**Le diagnostic.** Lancez `scripts\doctor.ps1` pour voir les versions, l'état de la base et de l'espace disque (voir MAINTENANCE.md).

Pour toute autre erreur, gardez la fenêtre de commandes ouverte, copiez le message et consultez le journal `data\concours-hunter.log`.
