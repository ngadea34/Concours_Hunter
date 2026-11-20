# Diagnostic : versions, base, Ollama, espace disque, interface compilée.
$Root = Split-Path -Parent $PSScriptRoot
Write-Host "Système :" (Get-CimInstance Win32_OperatingSystem).Caption
Write-Host ("RAM : {0:N1} Go" -f ((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB))
try { Write-Host "Node :" (node --version) } catch { Write-Host "Node : absent (inutile pour l'utilisation)" }
try { ollama list } catch { Write-Host "Ollama : absent (optionnel)" }
Push-Location "$Root\backend"
& ..\.venv\Scripts\python.exe -m app.cli doctor
Pop-Location
