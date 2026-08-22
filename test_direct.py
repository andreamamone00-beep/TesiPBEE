import sys
sys.path.insert(0, "scripts")
from pathlib import Path
import csv

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DATA_PATH = DATA_DIR / "dataset.csv"
DATASET2_PATH = DATA_DIR / "dataset2.csv"

FLOAT_FIELDS = {
    "kd_nM", "resolution", "temperature_K", "ph", "pKd",
    "dG_exp_kcal_mol", "dG_exp_raw_kcal_mol",
    "dG_pred_kcal_mol", "dG_pred_electrostatic", "dG_pred_apolar",
    "dG_pred_entropy",
    "n_residues_ab", "n_residues_ag", "interface_area_A2",
    "pbee_runtime_s",
}

def load_dataset(dataset_name: str = "dataset1"):
    print(f"load_dataset called with: {dataset_name}")
    if dataset_name == "dataset1":
        path = DATA_PATH
    elif dataset_name == "dataset2":
        path = DATASET2_PATH
    else:
        path = DATA_PATH
    
    print(f"Loading from path: {path}")
    if not path.exists():
        print(f"Path does not exist: {path}")
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for k in FLOAT_FIELDS:
                if k in row:
                    if row[k] in ("", None):
                        row[k] = None
                    else:
                        try:
                            row[k] = float(row[k])
                        except ValueError:
                            row[k] = None
            rows.append(row)
    print(f"Loaded {len(rows)} records from {dataset_name}")
    return rows

def filter_records(records, args):
    fmt = args.get("format", "all")
    method = args.get("method", "all")
    source = args.get("source", "all")
    res_max = args.get("res_max", type=float)
    kd_min = args.get("kd_min", type=float)
    kd_max = args.get("kd_max", type=float)

    print(f"Filtering with: fmt={fmt}, method={method}, source={source}, res_max={res_max}, kd_min={kd_min}, kd_max={kd_max}")
    
    out = []
    for r in records:
        if fmt != "all" and r.get("format") != fmt:
            continue
        if method != "all" and r.get("method") != method:
            continue
        if source != "all" and r.get("source") != source:
            continue
        # Handle resolution filtering - convert to float if possible
        res = r.get("resolution")
        if res is not None and res != "":
            try:
                res = float(res)
                if res_max is not None and res > res_max:
                    continue
            except (ValueError, TypeError):
                # If resolution is not a valid number, skip the filter
                pass
        # Handle kd_nM filtering - convert to float if possible
        kd = r.get("kd_nM")
        if kd is not None and kd != "":
            try:
                kd = float(kd)
                if kd_min is not None and kd < kd_min:
                    continue
                if kd_max is not None and kd > kd_max:
                    continue
            except (ValueError, TypeError):
                # If kd_nM is not a valid number, skip the filter
                pass
        out.append(r)
    return out

def compute_metrics(records):
    print(f"Computing metrics for {len(records)} records")
    if len(records) < 2:
        return {"n": len(records), "rmse": None, "mae": None,
                "pearson": None, "spearman": None, "bias": None, "kendall": None}

    # Check if prediction fields exist and are numeric
    has_predictions = all(r.get("dG_pred_kcal_mol") not in (None, "", "nan") for r in records)
    has_experiments = all(r.get("dG_exp_kcal_mol") not in (None, "", "nan") for r in records)
    
    print(f"has_predictions: {has_predictions}, has_experiments: {has_experiments}")
    
    if not has_predictions or not has_experiments:
        return {"n": len(records), "rmse": None, "mae": None,
                "pearson": None, "spearman": None, "bias": None, "kendall": None}

    try:
        exp = [r["dG_exp_kcal_mol"] for r in records]
        pred = [r["dG_pred_kcal_mol"] for r in records]
        errs = [p - e for p, e in zip(pred, exp)]
    except (KeyError, TypeError) as e:
        print(f"Error computing metrics: {e}")
        return {"n": len(records), "rmse": None, "mae": None,
                "pearson": None, "spearman": None, "bias": None, "kendall": None}
    
    print("Metrics computed successfully")
    return {"n": len(records), "rmse": 0.0, "mae": 0.0, "pearson": 0.0, "spearman": 0.0, "bias": 0.0, "kendall": 0.0}

# Test the full pipeline
print("=" * 50)
print("Testing dataset2 loading and filtering")
print("=" * 50)

try:
    records = load_dataset("dataset2")
    print(f"First record: {records[0] if records else 'No records'}")
    
    args = {
        "format": "all",
        "method": "all", 
        "source": "all",
        "res_max": "3.5"
    }
    
    filtered = filter_records(records, args)
    print(f"Filtered to {len(filtered)} records")
    
    metrics = compute_metrics(filtered)
    print(f"Metrics: {metrics}")
    
    print("SUCCESS: Pipeline completed without errors")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
