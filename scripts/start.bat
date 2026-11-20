@echo off
REM Demarre Concours Hunter et ouvre l'interface.
cd /d "%~dp0..\backend"
if not exist "..\.venv\Scripts\python.exe" (
  echo Lancez d'abord scripts\install.ps1
  pause
  exit /b 1
)
start "" http://127.0.0.1:8765
"..\.venv\Scripts\python.exe" -m app.cli serve
