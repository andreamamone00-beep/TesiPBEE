"""Dashboard Flask per il dataset Ab-Ag + PBEE benchmark.

Funzionalità:
  - lettura dataset da data/dataset.csv
  - filtri dinamici (formato, metodo, fonte, risoluzione, Kd)
  - API JSON per dati e metriche
  - galleria dei 20 grafici statici generati da scripts/05_analyze_results.py
  - pagina di stato connessione alle fonti (RCSB, SAbDab, PubMed, BindingDB)
  - export CSV filtrato

Avvio: python dashboard/app.py
URL:   http://127.0.0.1:5000
"""
from __future__ import annotations

import csv
import datetime
import io
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import (Flask, Response, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)

# Rendo importabili gli script della pipeline
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DATA_DIR = ROOT / "data"
DATA_PATH = DATA_DIR / "dataset.csv"
RESULTS_DIR = ROOT / "results"
METRICS_PATH = RESULTS_DIR / "metrics.json"
SABDAB_SUMMARY_PATH = DATA_DIR / "sabdab_summary.tsv"
HISTORY_DIR = DATA_DIR / "history"
PDB_CACHE_DIR = DATA_DIR / "cache"
PDB_RESULTS_DIR = DATA_DIR / "pdb_results"
PDB_SEARCH_LOG = DATA_DIR / "pdb_searches.json"
SNAPSHOT_PREFIX = "dataset_snapshot_"

BACKGROUND_TASKS: dict[str, dict] = {}

app = Flask(__name__, static_folder="static", template_folder="templates")


# ---------------------------------------------------------------------------
# Caricamento dati
# ---------------------------------------------------------------------------
FLOAT_FIELDS = {
    "kd_nM", "resolution", "temperature_K", "ph", "pKd",
    "dG_exp_kcal_mol", "dG_exp_raw_kcal_mol",
    "dG_pred_kcal_mol", "dG_pred_electrostatic", "dG_pred_apolar",
    "dG_pred_entropy",
    "n_residues_ab", "n_residues_ag", "interface_area_A2",
    "pbee_runtime_s",
}


def load_dataset() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    rows = []
    with DATA_PATH.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for k in FLOAT_FIELDS:
                if k in row and row[k] not in ("", None):
                    try:
                        row[k] = float(row[k])
                    except ValueError:
                        pass
            rows.append(row)
    return rows


def filter_records(records, args):
    fmt = args.get("format", "all")
    method = args.get("method", "all")
    source = args.get("source", "all")
    res_max = args.get("res_max", type=float)
    kd_min = args.get("kd_min", type=float)
    kd_max = args.get("kd_max", type=float)

    out = []
    for r in records:
        if fmt != "all" and r.get("format") != fmt:
            continue
        if method != "all" and r.get("method") != method:
            continue
        if source != "all" and r.get("source") != source:
            continue
        if res_max is not None and r.get("resolution", 99) > res_max:
            continue
        if kd_min is not None and r.get("kd_nM", 0) < kd_min:
            continue
        if kd_max is not None and r.get("kd_nM", 0) > kd_max:
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Metriche
# ---------------------------------------------------------------------------
def compute_metrics(records):
    if len(records) < 2:
        return {"n": len(records), "rmse": None, "mae": None,
                "pearson": None, "spearman": None, "bias": None, "kendall": None}

    # Check if prediction fields exist and are numeric
    has_predictions = all(r.get("dG_pred_kcal_mol") not in (None, "", "nan") for r in records)
    
    if not has_predictions:
        return {"n": len(records), "rmse": None, "mae": None,
                "pearson": None, "spearman": None, "bias": None, "kendall": None}

    exp = [r["dG_exp_kcal_mol"] for r in records]
    pred = [r["dG_pred_kcal_mol"] for r in records]
    errs = [p - e for p, e in zip(pred, exp)]

    def _mean(xs): return sum(xs) / len(xs)

    def _pearson(xs, ys):
        mx, my = _mean(xs), _mean(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
        dy = math.sqrt(sum((y - my) ** 2 for y in ys))
        return num / (dx * dy) if dx and dy else 0.0

    def _rank(a):
        idx = sorted(enumerate(a), key=lambda p: p[1])
        r = [0.0] * len(a)
        for k, (i, _) in enumerate(idx):
            r[i] = k + 1
        return r

    def _kendall(xs, ys):
        n = len(xs); conc = disc = 0
        for i in range(n):
            for j in range(i + 1, n):
                a = (xs[i] - xs[j]) * (ys[i] - ys[j])
                if a > 0: conc += 1
                elif a < 0: disc += 1
        denom = 0.5 * n * (n - 1)
        return (conc - disc) / denom if denom else 0.0

    return {
        "n": len(records),
        "rmse": round(math.sqrt(_mean([e ** 2 for e in errs])), 2),
        "mae": round(_mean([abs(e) for e in errs]), 2),
        "pearson": round(_pearson(exp, pred), 2),
        "spearman": round(_pearson(_rank(exp), _rank(pred)), 2),
        "kendall": round(_kendall(exp, pred), 2),
        "bias": round(_mean(errs), 2),
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/gallery")
def gallery():
    return render_template("gallery.html")


@app.route("/sources")
def sources_page():
    return render_template("sources.html")


@app.route("/api/dataset")
def api_dataset():
    records = load_dataset()
    filtered = filter_records(records, request.args)
    return jsonify({"records": filtered, "metrics": compute_metrics(filtered)})


@app.route("/api/metadata")
def api_metadata():
    records = load_dataset()
    if not records:
        return jsonify({"empty": True,
                        "message": "Dataset non trovato. Esegui la pipeline."})
    formats = sorted({r["format"] for r in records if r.get("format")})
    methods = sorted({r["method"] for r in records if r.get("method")})
    sources_list = sorted({r["source"] for r in records if r.get("source")})

    global_metrics = None
    if METRICS_PATH.exists():
        with METRICS_PATH.open("r", encoding="utf-8") as f:
            global_metrics = json.load(f)

    return jsonify({
        "empty": False,
        "formats": formats,
        "methods": methods,
        "sources": sources_list,
        "total": len(records),
        "global_metrics": global_metrics,
    })


@app.route("/api/connectivity")
def api_connectivity():
    """Verifica connettività alle fonti. Timeout breve per non bloccare."""
    try:
        from sources import check_connectivity
    except Exception as e:
        return jsonify({"error": str(e), "status": {}})
    return jsonify({"status": check_connectivity()})


@app.route("/api/export.csv")
def export_csv():
    records = load_dataset()
    filtered = filter_records(records, request.args)
    if not filtered:
        return Response("", mimetype="text/csv")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=filtered[0].keys())
    writer.writeheader()
    writer.writerows(filtered)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=dataset_filtered.csv"},
    )


def ensure_history_dir() -> None:
    if not HISTORY_DIR.exists():
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _file_info(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(sep=" ", timespec="seconds"),
        "size": stat.st_size,
    }


def _list_history_versions() -> list[dict]:
    ensure_history_dir()
    versions = []
    for path in sorted(HISTORY_DIR.glob(f"{SNAPSHOT_PREFIX}*.csv"), reverse=True):
        versions.append({
            "name": path.name,
            "created": datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(sep=" ", timespec="seconds"),
            "size": path.stat().st_size,
        })
    return versions


def _save_dataset_snapshot(note: str | None = None) -> dict:
    ensure_history_dir()
    if not DATA_PATH.exists():
        return {"ok": False, "message": "Dataset non disponibile"}
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{SNAPSHOT_PREFIX}{timestamp}.csv"
    target = HISTORY_DIR / filename
    shutil.copy2(DATA_PATH, target)
    return {"ok": True, "version": filename, "note": note}


def _ensure_cache_dir() -> None:
    if not PDB_CACHE_DIR.exists():
        PDB_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _list_cached_pdb_ids() -> list[str]:
    _ensure_cache_dir()
    ids = set()
    for path in PDB_CACHE_DIR.glob("*.json"):
        ids.add(path.stem.lower())
    for path in PDB_CACHE_DIR.glob("*.pdb"):
        ids.add(path.stem.lower())
    return sorted(ids)


def _load_pdb_search_history() -> list[dict]:
    if not PDB_SEARCH_LOG.exists():
        return []
    try:
        with PDB_SEARCH_LOG.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _record_pdb_search(pdb_id: str, success: bool, note: str | None = None) -> None:
    entries = _load_pdb_search_history()
    entry = {
        "pdb": pdb_id.lower(),
        "success": bool(success),
        "note": note or "",
        "created": datetime.datetime.now().isoformat(sep=" ", timespec="seconds"),
    }
    entries.insert(0, entry)
    entries = entries[:50]
    try:
        with PDB_SEARCH_LOG.open("w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _ensure_pdb_results_dir() -> None:
    if not PDB_RESULTS_DIR.exists():
        PDB_RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _pdb_result_path(pdb_id: str) -> Path:
    return PDB_RESULTS_DIR / f"{pdb_id.lower()}_pbee.json"


def _save_pdb_result(pdb_id: str, data: dict) -> None:
    _ensure_pdb_results_dir()
    path = _pdb_result_path(pdb_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_pdb_result(pdb_id: str) -> dict | None:
    path = _pdb_result_path(pdb_id)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _list_pdb_results() -> list[dict]:
    _ensure_pdb_results_dir()
    results = []
    for path in sorted(PDB_RESULTS_DIR.glob("*_pbee.json"), reverse=True):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        results.append({
            "pdb": data.get("pdb", path.stem.replace("_pbee", "")),
            "created": data.get("created", datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(sep=" ", timespec="seconds")),
            "status": data.get("status", "done"),
            "chains_a": data.get("chain_ids_a", []),
            "chains_b": data.get("chain_ids_b", []),
            "kd_nM": data.get("kd_nM"),
            "result": data.get("result", {}),
        })
    return results


def _find_dataset_kd(pdb_id: str) -> float | None:
    for record in load_dataset():
        if (record.get("pdb") or "").lower() == pdb_id.lower() and record.get("kd_nM"):
            return float(record["kd_nM"])
    return None


def _update_task_status(pdb_id: str, status: str, message: str | None = None) -> None:
    BACKGROUND_TASKS[pdb_id.lower()] = {
        "status": status,
        "updated": datetime.datetime.now().isoformat(sep=" ", timespec="seconds"),
        "message": message or "",
    }


def _run_pdb_compute_task(pdb_id: str,
                         chain_ids_a: list[str],
                         chain_ids_b: list[str],
                         kd_nM: float | None) -> None:
    _update_task_status(pdb_id, "running", "Calcolo PBEE in corso...")
    try:
        from sources import fetch_pdb_file
        from pbee_calculator import calculate_pbee_for_complex
    except Exception as e:
        _update_task_status(pdb_id, "failed", f"Errore import: {e}")
        return

    try:
        pdb_path = Path(fetch_pdb_file(pdb_id))
        if not pdb_path.exists():
            raise FileNotFoundError(f"File PDB non trovato: {pdb_path}")

        if kd_nM is None:
            kd_nM = _find_dataset_kd(pdb_id) or 1.0

        results = calculate_pbee_for_complex(
            pdb_path,
            kd_nM,
            chain_ids_a=chain_ids_a,
            chain_ids_b=chain_ids_b,
        )

        saved = {
            "pdb": pdb_id.lower(),
            "created": datetime.datetime.now().isoformat(sep=" ", timespec="seconds"),
            "status": "done",
            "kd_nM": kd_nM,
            "chain_ids_a": chain_ids_a,
            "chain_ids_b": chain_ids_b,
            "result": results,
        }
        _save_pdb_result(pdb_id, saved)
        _update_task_status(pdb_id, "done", "Calcolo PBEE completato.")
    except Exception as e:
        _update_task_status(pdb_id, "failed", str(e))


@app.route("/api/pdb/<pdb_id>")
def api_get_pdb(pdb_id):
    pdb_id = pdb_id.strip().lower()
    _ensure_cache_dir()
    path = PDB_CACHE_DIR / f"{pdb_id}.pdb"
    if not path.exists():
        return jsonify({"ok": False, "message": "File PDB non trovato sul server."}), 404
    return send_from_directory(PDB_CACHE_DIR, f"{pdb_id}.pdb", mimetype="text/plain")


@app.route("/api/manage/upload_pdb", methods=["POST"])
def api_manage_upload_pdb():
    if "file" not in request.files:
        return jsonify({"ok": False, "message": "Nessun file inviato."}), 400
    file = request.files["file"]
    pdb_id = request.form.get("pdb_id", "").strip().lower()
    if not pdb_id or not re.fullmatch(r"[0-9a-z_-]{3,20}", pdb_id):
        return jsonify({"ok": False, "message": "Inserisci un codice PDB valido (3-20 caratteri alfanumerici, trattino o underscore)."}), 400
    
    if not file.filename.endswith(".pdb"):
        return jsonify({"ok": False, "message": "Il file deve avere estensione .pdb."}), 400
        
    _ensure_cache_dir()
    pdb_path = PDB_CACHE_DIR / f"{pdb_id}.pdb"
    file.save(pdb_path)
    
    try:
        from sources import extract_pdb_chains, fetch_pdb_metadata
        metadata = {}
        base_id = pdb_id[:4]
        if re.fullmatch(r"[0-9a-z]{4}", base_id):
            try:
                metadata = fetch_pdb_metadata(base_id)
            except Exception:
                pass
        
        chains = extract_pdb_chains(pdb_path, metadata)
        
        pdb_result = _load_pdb_result(pdb_id)
        _record_pdb_search(pdb_id, True, f"File caricato manualmente: {file.filename}")
        
        return jsonify({
            "ok": True,
            "message": f"PDB '{pdb_id.upper()}' caricato con successo sul server.",
            "pdb": pdb_id,
            "metadata": metadata,
            "cached_file": str(pdb_path),
            "chains": chains,
            "previous_result": pdb_result,
        })
    except Exception as e:
        return jsonify({"ok": False, "message": f"Errore nell'estrazione delle catene: {e}"}), 500


@app.route("/api/manage/status")
def api_manage_status():
    dataset_count = len(load_dataset())
    status = {
        "dataset": _file_info(DATA_PATH),
        "summary": _file_info(SABDAB_SUMMARY_PATH),
        "history": _list_history_versions(),
        "dataset_count": dataset_count,
        "summary_rows": 0,
    }
    if status["summary"]["exists"]:
        try:
            with SABDAB_SUMMARY_PATH.open("r", encoding="utf-8", errors="replace") as f:
                status["summary_rows"] = sum(1 for _ in f) - 1
        except Exception:
            status["summary_rows"] = 0
    status["cache"] = {
        "count": len(_list_cached_pdb_ids()),
        "ids": _list_cached_pdb_ids(),
    }
    status["pdb_search_history"] = _load_pdb_search_history()
    status["pdb_results"] = _list_pdb_results()
    status["pdb_results_count"] = len(status["pdb_results"])
    status["background_tasks"] = BACKGROUND_TASKS
    return jsonify(status)


@app.route("/api/manage/fetch_summary", methods=["POST"])
def api_manage_fetch_summary():
    try:
        from sources import _http_get
    except Exception as e:
        return jsonify({"ok": False, "message": f"Impossibile caricare sources: {e}"}), 500
    try:
        raw = _http_get("https://opig.stats.ox.ac.uk/webapps/newsabdab/sabdab/summary/all")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SABDAB_SUMMARY_PATH.write_bytes(raw)
        return jsonify({"ok": True, "message": "Summary SAbDab salvato localmente.", "summary_rows": sum(1 for _ in raw.decode("utf-8", errors="replace").splitlines()) - 1})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/manage/fetch_pdb", methods=["POST"])
def api_manage_fetch_pdb():
    if not request.is_json:
        return jsonify({"ok": False, "message": "Richiesta JSON richiesta."}), 400
    pdb_id = str(request.json.get("pdb", "")).strip().lower()
    if not re.fullmatch(r"[0-9a-z]{4}", pdb_id):
        return jsonify({"ok": False, "message": "Inserisci un codice PDB valido di 4 caratteri."}), 400
    try:
        from sources import RemoteUnavailable, fetch_pdb_file, fetch_pdb_metadata, extract_pdb_chains
    except Exception as e:
        return jsonify({"ok": False, "message": f"Impossibile caricare sources: {e}"}), 500
    try:
        metadata = fetch_pdb_metadata(pdb_id)
        pdb_path = fetch_pdb_file(pdb_id)
        chains = extract_pdb_chains(pdb_path, metadata)
        pdb_result = _load_pdb_result(pdb_id)
        _record_pdb_search(pdb_id, True, f"Cached file {pdb_path}")
        return jsonify({
            "ok": True,
            "message": f"PDB {pdb_id.upper()} scaricato e memorizzato sul server.",
            "pdb": pdb_id,
            "metadata": metadata,
            "cached_file": str(pdb_path),
            "chains": chains,
            "previous_result": pdb_result,
        })
    except RemoteUnavailable as e:
        _record_pdb_search(pdb_id, False, str(e))
        return jsonify({"ok": False, "message": str(e)}), 502
    except Exception as e:
        _record_pdb_search(pdb_id, False, str(e))
        return jsonify({"ok": False, "message": str(e)}), 500


@app.route("/api/manage/compute_pdb", methods=["POST"])
def api_manage_compute_pdb():
    if not request.is_json:
        return jsonify({"ok": False, "message": "Richiesta JSON richiesta."}), 400
    data = request.json
    pdb_id = str(data.get("pdb", "")).strip().lower()
    chain_ids_a = [str(x).strip().upper() for x in data.get("chain_ids_a", []) if str(x).strip()]
    chain_ids_b = [str(x).strip().upper() for x in data.get("chain_ids_b", []) if str(x).strip()]
    kd_nM = data.get("kd_nM")
    if not re.fullmatch(r"[0-9a-z_-]{3,20}", pdb_id):
        return jsonify({"ok": False, "message": "Inserisci un identificativo valido (3-20 caratteri alfanumerici, trattino o underscore)."}), 400
    if not chain_ids_a or not chain_ids_b:
        return jsonify({"ok": False, "message": "Seleziona almeno una catena per ciascun partner."}), 400
    try:
        kd_nM = float(kd_nM) if kd_nM is not None and str(kd_nM).strip() else None
    except ValueError:
        return jsonify({"ok": False, "message": "Kd non valido."}), 400
    task_key = pdb_id.lower()
    if BACKGROUND_TASKS.get(task_key, {}).get("status") == "running":
        return jsonify({"ok": False, "message": "Elaborazione già in corso per questo PDB."}), 409
    thread = threading.Thread(
        target=_run_pdb_compute_task,
        args=(pdb_id, chain_ids_a, chain_ids_b, kd_nM),
        daemon=True,
    )
    thread.start()
    _update_task_status(pdb_id, "queued", "Elaborazione PBEE avviata in background.")
    return jsonify({"ok": True, "message": "Elaborazione PBEE avviata in background.", "pdb": pdb_id})


@app.route("/api/manage/run_pipeline", methods=["POST"])
def api_manage_run_pipeline():
    if not SABDAB_SUMMARY_PATH.exists():
        return jsonify({"ok": False, "message": "Prima scarica il summary SAbDab."}), 400
    commands = [
        [sys.executable, str(ROOT / "scripts" / "01_build_dataset.py"), "--mode", "sabdab", "--sabdab-path", str(SABDAB_SUMMARY_PATH)],
        [sys.executable, str(ROOT / "scripts" / "02_curate_structures.py")],
        [sys.executable, str(ROOT / "scripts" / "03_normalize_affinity.py")],
        [sys.executable, str(ROOT / "scripts" / "04_compute_pbee.py"), "--mode", "simulated"],
    ]
    log = []
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1200)
        log.append({"command": cmd, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
        if proc.returncode != 0:
            return jsonify({"ok": False, "message": "Pipeline interrotta.", "log": log}), 500
    snapshot = _save_dataset_snapshot("pipeline_complete")
    return jsonify({"ok": True, "message": "Pipeline completata.", "snapshot": snapshot, "log": log})


@app.route("/api/manage/save_version", methods=["POST"])
def api_manage_save_version():
    result = _save_dataset_snapshot(request.json.get("note") if request.is_json else None)
    if not result["ok"]:
        return jsonify(result), 400
    return jsonify(result)


@app.route("/api/manage/versions")
def api_manage_versions():
    return jsonify({"versions": _list_history_versions()})


@app.route("/api/manage/restore_version", methods=["POST"])
def api_manage_restore_version():
    if not request.is_json:
        return jsonify({"ok": False, "message": "Richiesta JSON richiesta."}), 400
    version = request.json.get("version")
    if not version:
        return jsonify({"ok": False, "message": "Versione non specificata."}), 400
    source = HISTORY_DIR / version
    if not source.exists():
        return jsonify({"ok": False, "message": "Versione non trovata."}), 404
    shutil.copy2(source, DATA_PATH)
    snapshot = _save_dataset_snapshot(f"restore_from_{version}")
    return jsonify({"ok": True, "message": "Versione ripristinata.", "snapshot": snapshot})


@app.route("/results/<path:filename>")
def results_file(filename):
    """Servi i file in results/ (grafici e CSV delle metriche)."""
    return send_from_directory(RESULTS_DIR, filename)


@app.route("/api/plots")
def api_plots():
    """Lista dei grafici disponibili in results/."""
    if not RESULTS_DIR.exists():
        return jsonify({"plots": []})
    plots = []
    descriptions = {
        "01_scatter_pred_vs_exp.png": "Scatter ΔG_pred vs ΔG_exp con retta y=x e fit lineare",
        "02_scatter_by_format.png": "Scatter stratificato per formato anticorpo (Fab/scFv/VHH)",
        "03_residuals_hist.png": "Distribuzione dei residui (predetto − sperimentale)",
        "04_residuals_by_class.png": "Boxplot dei residui per classe di affinità",
        "05_residuals_vs_exp.png": "Residui vs ΔG_exp: verifica omoscedasticità",
        "06_bland_altman.png": "Bland–Altman plot con limiti ±1.96σ",
        "07_qq_residuals.png": "Q–Q plot dei residui standardizzati vs N(0,1)",
        "08_kd_distribution.png": "Distribuzione log₁₀(Kd) del dataset",
        "09_kd_vs_resolution.png": "Affinità vs risoluzione cristallografica",
        "10_metrics_by_format.png": "RMSE, MAE, |r| per formato anticorpo",
        "11_metrics_by_method.png": "RMSE, MAE, |r| per tecnica sperimentale",
        "12_decomposition_stack.png": "Decomposizione componenti ΔG PBEE vs ΔG_exp",
        "13_ranking_accuracy.png": "Ranking accuracy: rank predetto vs rank sperimentale",
        "14_error_heatmap.png": "Heatmap RMSE per formato × tecnica",
        "15_source_coverage.png": "Copertura del dataset per fonte",
        "16_roc_highaffinity.png": "ROC per classificazione Kd<10 nM",
        "17_calibration_curve.png": "Curva di calibrazione per bin di ΔG_exp",
        "18_venn_sources.png": "Contributi delle top-3 fonti",
        "19_timeline_dataset.png": "Crescita cumulativa del dataset",
        "20_summary_panel.png": "Pannello riassuntivo 2×2",
    }
    for name in sorted(RESULTS_DIR.glob("*.png")):
        plots.append({
            "filename": name.name,
            "url": url_for("results_file", filename=name.name),
            "description": descriptions.get(name.name, name.name),
        })
    return jsonify({"plots": plots})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not DATA_PATH.exists():
        print("\n" + "=" * 60)
        print("  ATTENZIONE: dataset.csv non trovato")
        print("  Esegui prima la pipeline:")
        print("    python scripts/01_build_dataset.py")
        print("    python scripts/02_curate_structures.py")
        print("    python scripts/03_normalize_affinity.py")
        print("    python scripts/04_compute_pbee.py")
        print("    python scripts/05_analyze_results.py")
        print("  oppure usa lo script run.sh / run.bat")
        print("=" * 60 + "\n")
    print("Dashboard attiva su http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
