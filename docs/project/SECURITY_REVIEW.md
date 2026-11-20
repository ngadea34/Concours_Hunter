# Revue de sécurité (L2, agent principal) — 2026-11-20

| Risque | Mesure | Test |
|---|---|---|
| Fuite des données personnelles | Profil chiffré (Fernet), clé locale `data/secret.key` | `test_profile_encrypted_at_rest` |
| Accès réseau non autorisé | Écoute 127.0.0.1 par défaut ; LAN = jeton obligatoire (comparaison à temps constant) | `test_security_middleware` |
| DNS rebinding | Requêtes sans jeton acceptées seulement avec Host local | idem |
| CSRF depuis un site tiers | Rejet des requêtes modifiantes dont l'Origin n'est ni locale ni une extension | idem |
| SSRF (découverte, ajout d'URL) | IP privées/loopback refusées, redirections revérifiées, résolution DNS contrôlée | `test_robots_and_protections_respected` |
| Injection de prompt dans les règlements | Texte = données, motifs neutralisés, éléments cachés supprimés, sortie JSON validée, citation exacte exigée, décision critique jamais sur LLM seul | `test_fake_organizer_and_injection` |
| XSS | React échappe ; URLs filtrées (`safeHref`), CSP stricte, X-Frame-Options DENY | revue |
| Téléchargements malveillants | Types de contenu limités, 8 Mo max, pas de téléchargement navigateur (`accept_downloads=False`), preuves PNG/JPEG vérifiées par signature | `test_proof_requires_consent_and_valid_png` |
| Traversée de chemin | Restauration par nom validé (regex), fichiers statiques confinés | `test_backup_and_restore`, `test_security_middleware` |
| Ollama détourné | URL Ollama forcée en local | `test_security_middleware` |
| Automatisation abusive | Triple condition (règlement explicite + consentement + pas de CAPTCHA/connexion), jamais au-delà de la politique | `test_auto_mode_never_exceeds_policy`, `test_auto_blocked_without_consent` |
| Isolation navigateur | Profil Playwright distinct par domaine (`data/browser/<domaine>`) | revue |

## Risques résiduels (non critiques)
- Toute extension installée dans le navigateur de l'utilisateur peut appeler l'API locale (origine `chrome-extension://`). Acceptable : une extension malveillante a déjà accès au navigateur.
- Le jeton LAN circule en HTTP sur le Wi-Fi local (pas de TLS). Recommandation : n'activer le mode LAN que sur un réseau de confiance.
- `data/secret.key` n'est pas protégée par un mot de passe ; elle repose sur la session Windows de l'utilisateur.
