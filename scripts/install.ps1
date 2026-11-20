# Installation de Concours Hunter sous Windows 10/11 (sans Docker, sans droits administrateur).
# Usage : clic droit > Exécuter avec PowerShell, ou :  powershell -ExecutionPolicy Bypass -File scripts\install.ps1 [-NoBrowser]
param([switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Find-Python {
    foreach ($c in @("py -3.13", "py -3.12", "py -3.11", "python")) {
        try {
            $v = & cmd /c "$c -c ""import sys;print(sys.version_info[0]*100+sys.version_info[1])""" 2>$null
            if ($v -and [int]$v -ge 311) { return $c }
        } catch {}
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "Python 3.11+ introuvable. Installez-le : winget install Python.Python.3.12  (ou https://www.python.org/downloads/)" -ForegroundColor Yellow
    exit 1
}
Write-Host "Python trouvé : $py"

if (-not (Test-Path ".venv")) { & cmd /c "$py -m venv .venv" }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt --quiet
if (-not $NoBrowser) {
    Write-Host "Installation du navigateur Chromium pour la participation automatique (optionnelle, ~150 Mo)..."
    & .\.venv\Scripts\python.exe -m playwright install chromium
}
Push-Location backend
& ..\.venv\Scripts\python.exe -m app.cli migrate
& ..\.venv\Scripts\python.exe -m app.cli doctor
Pop-Location
Write-Host ""
Write-Host "Installation terminée. Lancez scripts\start.bat puis ouvrez http://127.0.0.1:8765" -ForegroundColor Green
