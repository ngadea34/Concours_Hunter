# Mise à jour : sauvegarde, récupération du code, dépendances, migrations.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Push-Location backend
& ..\.venv\Scripts\python.exe -m app.cli backup
Pop-Location
if (Test-Path ".git") { git pull --ff-only } else { Write-Host "Pas de dépôt git : remplacez les fichiers par la nouvelle version (le dossier data\ est conservé)." }
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt --quiet
Push-Location backend
& ..\.venv\Scripts\python.exe -m app.cli migrate
Pop-Location
Write-Host "Mise à jour terminée." -ForegroundColor Green
