# Extension Concours Hunter (MV3, L1)

Préremplit, sur la page d'un concours, les champs d'une participation **préparée** dans Concours Hunter. JavaScript pur, sans dépendance ni build.

## Installation (Chrome / Edge, mode développeur)
1. Ouvrir `chrome://extensions` (ou `edge://extensions`), activer **Mode développeur**.
2. **Charger l'extension non empaquetée** et choisir ce dossier `extension/`.
3. Ouvrir les réglages de l'extension : URL du serveur (défaut `http://127.0.0.1:8765`) et jeton `X-CH-Token` si nécessaire. Pour un serveur LAN (hors 127.0.0.1/localhost), le navigateur demandera l'autorisation d'accès à cette origine à l'enregistrement.
4. Firefox 115+ : `about:debugging` > Charger un module complémentaire temporaire > `manifest.json`.

## Utilisation
1. Dans Concours Hunter, préparer la participation (statut `prepared` / `awaiting_human`).
2. Ouvrir la page du concours, cliquer sur l'icône de l'extension : les participations correspondant à l'URL s'affichent.
3. **Préremplir** : champs remplis entourés de vert, champs requis non reconnus en orange. Les événements `input`/`change` sont déclenchés.
4. Cocher vous-même les consentements, résoudre le CAPTCHA éventuel, puis **soumettre le formulaire vous-même**.
5. **J'ai soumis** : capture de l'onglet envoyée en preuve (`POST /proofs`), puis `POST /submitted`.

## Garanties
- Ne soumet jamais un formulaire, ne clique jamais sur un bouton d'envoi.
- Ne touche jamais aux champs password, fichier, cases à cocher/radios (consentements, newsletter, CGU) ni aux champs CAPTCHA.
- Un champ déjà rempli n'est pas écrasé.
- CAPTCHA (reCAPTCHA, hCaptcha, Turnstile, « captcha » dans name/id/class) : avertissement, rien de plus.
- Permissions : `activeTab`, `scripting`, `storage` ; hôtes `http://127.0.0.1/*`, `http://localhost/*` ; hôtes LAN en option, à la demande. Le code n'est injecté qu'à la demande, sur l'onglet actif. Aucun `eval`, aucun `innerHTML`.

## Tests
`node --test extension/test/` (logique pure + e2e Chromium via Playwright, ignoré si absent). Page manuelle : `test/form.html`. Icônes : `node tools/make-icons.mjs`.

## Limites
- Seul le document principal est rempli (pas les iframes, ex. formulaires embarqués d'un autre domaine ; ni le shadow DOM fermé).
- Cases à cocher et boutons radio jamais remplis, y compris pour des questions à choix : à faire à la main.
- Correspondance question/champ approximative (recouvrement de mots) : vérifier les réponses.
- Formulaires multi-étapes : relancer « Préremplir » à chaque étape.
- La page doit être en http/https ; les pages internes du navigateur et le magasin d'extensions sont refusés.
- La capture est celle de la zone visible de l'onglet, en PNG (limite serveur 5 Mo).
- Le serveur Concours Hunter doit être lancé ; les serveurs HTTPS distants ne sont pas pris en charge sans le mettre en optional_host_permissions.
