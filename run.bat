@echo off
REM Avvio tutto-in-uno del prototipo Ab-Ag + PBEE (Windows)
cd /d "%~dp0"

echo ====================================
echo   Ab/ScFv-Ag + PBEE benchmark
echo ====================================

REM 1. Virtualenv
if not exist ".venv" (
  echo [setup] Creazione virtualenv...
  python -m venv .venv
  if errorlevel 1 goto error
)
call .venv\Scripts\activate.bat

REM 2. Dipendenze
echo [setup] Installazione dipendenze...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 goto error

REM 3. Pipeline (parametro opzionale: online)
REM Commentato per evitare sovrascrittura del dataset manuale
REM set MODE=%1
REM if "%MODE%"=="" set MODE=simulated
REM 
REM echo.
REM echo [pipeline] Esecuzione pipeline (modalita': %MODE%)...
REM if "%MODE%"=="online" (
REM   python scripts\01_build_dataset.py --mode online --n 50 --fallback-simulated
REM ) else (
REM   python scripts\01_build_dataset.py --mode simulated --n 48
REM )
REM if errorlevel 1 goto error
REM python scripts\02_curate_structures.py --no-download
REM if errorlevel 1 goto error
REM python scripts\03_normalize_affinity.py
REM if errorlevel 1 goto error
REM python scripts\04_compute_pbee.py
REM if errorlevel 1 goto error
REM python scripts\05_analyze_results.py
REM if errorlevel 1 goto error

REM 4. Dashboard
echo.
echo ====================================
echo   Avvio dashboard con dataset esistente.
echo   URL: http://127.0.0.1:5000
echo   Premere Ctrl+C per fermare.
echo ====================================
echo.
python dashboard\app.py
goto end

:error
echo.
echo ERRORE: uno degli step e' fallito. Controllare i messaggi sopra.
exit /b 1

:end
