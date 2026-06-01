"""Step 3 — Normalizzazione dei dati sperimentali a T = 298.15 K."""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (DATASET_CURATED, DATASET_NORMALIZED, R_GAS_KCAL, T_STANDARD,
                   ensure_dirs, get_logger, kd_to_dg, nm_to_molar)

log = get_logger("03_normalize")


def normalize_record(record: dict) -> dict:
    kd_nm = float(record["kd_nM"])
    try:
        t_exp = float(record.get("temperature_K") or T_STANDARD)
    except (TypeError, ValueError):
        t_exp = T_STANDARD

    dg_exp_raw = R_GAS_KCAL * t_exp * math.log(nm_to_molar(kd_nm))
    dg_exp_standard = kd_to_dg(nm_to_molar(kd_nm), T_STANDARD)

    record["dG_exp_raw_kcal_mol"] = round(dg_exp_raw, 3)
    record["dG_exp_kcal_mol"] = round(dg_exp_standard, 3)
    record["normalized_T_K"] = T_STANDARD
    record["pKd"] = round(-math.log10(nm_to_molar(kd_nm)), 3)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalizzazione affinità")
    parser.parse_args()

    ensure_dirs()
    log.info("=== Step 3: normalizzazione ===")

    if not DATASET_CURATED.exists():
        log.error("File %s non trovato. Esegui prima 02_curate_structures.py", DATASET_CURATED)
        sys.exit(2)

    rows = []
    with DATASET_CURATED.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(normalize_record(row))

    with DATASET_NORMALIZED.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    log.info("Normalizzati %d record a T=%.2f K", len(rows), T_STANDARD)
    log.info("=== Step 3: OK ===")


if __name__ == "__main__":
    main()
