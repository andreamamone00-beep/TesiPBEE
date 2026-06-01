#!/usr/bin/env bash
# Avvio tutto-in-uno del prototipo Ab-Ag + PBEE
set -e
cd "$(dirname "$0")"

echo "===================================="
echo "  Ab/ScFv-Ag + PBEE benchmark"
echo "===================================="

# 1. Virtualenv
if [ ! -d ".venv" ]; then
  echo "[setup] Creazione virtualenv..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# 2. Dipendenze
echo "[setup] Installazione dipendenze..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# 3. Pipeline (default: modalità simulata; passare --online per API reali)
MODE="${1:-simulated}"
echo ""
echo "[pipeline] Esecuzione pipeline (modalità: $MODE)..."
if [ "$MODE" = "online" ]; then
  python scripts/01_build_dataset.py --mode online --n 50 --fallback-simulated
else
  python scripts/01_build_dataset.py --mode simulated --n 48
fi
python scripts/02_curate_structures.py --no-download
python scripts/03_normalize_affinity.py
python scripts/04_compute_pbee.py
python scripts/05_analyze_results.py

# 4. Dashboard
echo ""
echo "===================================="
echo "  Pipeline completata. Avvio dashboard."
echo "  URL: http://127.0.0.1:5000"
echo "  Premere Ctrl+C per fermare."
echo "===================================="
echo ""
python dashboard/app.py
