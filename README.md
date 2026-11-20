# Concours Hunter

Application web **locale** pour trouver, qualifier, organiser et suivre les jeux-concours **gratuits** accessibles depuis la France.
Tout tourne sur votre PC (Windows 10/11, Linux, macOS), sans abonnement ni service payant. Utilisable depuis un smartphone sur le même Wi-Fi.

## Ce que fait l'application
- **Découverte** : flux RSS, pages publiques, agrégateurs (Jeu-concours.biz, LDDJ, ToutGagner, Concours du Net) via des connecteurs extensibles, dans le respect de robots.txt et avec une cadence limitée.
- **Qualification** : lecture du règlement (FR, EN, ES, DE, IT, PT, NL, PDF compris), gratuité, éligibilité depuis la France, âge, dates, lots, limites, interdiction d'automatisation, délai de réclamation. Chaque décision cite l'extrait du règlement. IA locale (Ollama) facultative, jamais seule juge d'une décision critique.
- **Scores** de fiabilité et d'intérêt sur 100 (ce ne sont pas des probabilités de gain), détection d'arnaques et d'injections.
- **Déduplication** multi-sources avec provenance, base de réponses vérifiées par recoupement.
- **Participation** : préremplissage (interface + extension navigateur), anti double participation, preuves (captures), mode automatique uniquement si le règlement l'autorise explicitement, avec votre consentement et sans CAPTCHA.
- **Résultats et gains** : détection des faux messages de gain, réclamations avec échéances, statistiques (valeur jouée distincte des gains réels).
- **Planificateur** avec quotas, reprise après interruption et arrêt d'urgence ; **sauvegardes** automatiques et restauration.

## Démarrage rapide (Windows)
```powershell
git clone https://github.com/ngadea34/concours_hunter
cd concours_hunter
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
scripts\start.bat          # puis http://127.0.0.1:8765
```
Détails : [Installation](docs/user/INSTALLATION.md) · [Guide utilisateur](docs/user/GUIDE_UTILISATEUR.md) · [Maintenance](docs/user/MAINTENANCE.md) · [Extension](extension/README.md)

## Ce que l'application ne fera jamais
Contourner un CAPTCHA, une connexion, un géoblocage ou une limite de participation ; ignorer robots.txt ou les CGU ; acheter quoi que ce soit ; soumettre une participation sans votre consentement ; envoyer vos données ailleurs que dans un formulaire que vous avez validé.

## Structure
```
backend/    FastAPI + SQLite (app/), tests (pytest)
frontend/   React + TypeScript (compilé dans backend/app/static)
extension/  extension navigateur Manifest V3
scripts/    installation, démarrage, mise à jour, diagnostic, sauvegarde
docs/       project/ (état, architecture, décisions, routage IA) · user/ (guides)
```

## Développement
```bash
cd backend && ../.venv/bin/python -m pytest      # tests backend (dont participation automatique sur formulaire de démo)
node --test extension/test/                       # tests extension
cd frontend && npm ci && npm run dev              # interface en mode dev (proxy vers :8765)
```
