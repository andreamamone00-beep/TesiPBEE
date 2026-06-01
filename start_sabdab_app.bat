@echo off
echo ========================================
echo    Ab/Ag PBEE Dashboard - SAbDab Data
echo ========================================
echo.
echo Avvio applicazione con dati SAbDab reali...
echo.

REM Vai alla directory del progetto
cd /d "C:\dev\ab_ag_pbee"

REM Attiva l'ambiente virtuale
if exist ".venv\Scripts\activate.bat" (
    echo Attivazione ambiente virtuale...
    call .venv\Scripts\activate.bat
) else (
    echo ERRORE: Ambiente virtuale non trovato!
    echo Eseguire prima: python -m venv .venv
    pause
    exit /b 1
)

REM Avvia la dashboard
echo.
echo Avvio dashboard...
echo La sara disponibile su: http://127.0.0.1:5000
echo.
python dashboard\app.py

echo.
echo Dashboard chiusa.
pause
