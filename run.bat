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
set MODE=%1
if "%MODE%"=="" set MODE=simulated

echo.
echo [pipeline] Esecuzione pipeline (modalita': %MODE%)...
if "%MODE%"=="online" (
  python scripts\01_build_dataset.py --mode online --n 50 --fallback-simulated
) else (
  python scripts\01_build_dataset.py --mode simulated --n 48
)
if errorlevel 1 goto error
python scripts\02_curate_structures.py --no-download
if errorlevel 1 goto error
python scripts\03_normalize_affinity.py
if errorlevel 1 goto error
python scripts\04_compute_pbee.py
if errorlevel 1 goto error
python scripts\05_analyze_results.py
if errorlevel 1 goto error

REM 4. Dashboard
echo.
echo ====================================
echo   Pipeline completata. Avvio dashboard.
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
