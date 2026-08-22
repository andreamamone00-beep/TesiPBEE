"""Script per creare dataset2 con dati sperimentali dalla letteratura."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from pbee_calculator import PBEECalculator

log = get_logger("create_dataset2_literature")

# Dati sperimentali dalla letteratura
LITERATURE_DATA = [
    {
        "pdb": "10bt",
        "resolution": 1.99,
        "kd_nM": 2.06,
        "dG_exp_kcal_mol": -11.84,
        "kd_method": "BLI",
        "method": "X-RAY DIFFRACTION"
    },
    {
        "pdb": "10gh",
        "resolution": 3.06,
        "kd_nM": 116,
        "dG_exp_kcal_mol": -9.45,
        "kd_method": "BLI",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "11hk",
        "resolution": 2.70,
        "kd_nM": 0.2,
        "dG_exp_kcal_mol": -13.23,
        "kd_method": "BLI",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "11hw",
        "resolution": 2.80,
        "kd_nM": 12,
        "dG_exp_kcal_mol": -10.80,
        "kd_method": "BLI",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "11ol",
        "resolution": 3.20,
        "kd_nM": 1,
        "dG_exp_kcal_mol": -12.28,
        "kd_method": "BLI",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "11oo",
        "resolution": 3.40,
        "kd_nM": 100,  # ">100nM" trattato come 100
        "dG_exp_kcal_mol": -9.54,  # ">-9.54" trattato come -9.54
        "kd_method": "BLI",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "11oq",
        "resolution": 3.20,
        "kd_nM": 50,
        "dG_exp_kcal_mol": -9.45,
        "kd_method": "BLI",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "13fj",
        "resolution": 2.75,
        "kd_nM": 0.0146,
        "dG_exp_kcal_mol": -14.78,
        "kd_method": "SPR",
        "method": "X-RAY DIFFRACTION"
    },
    {
        "pdb": "10fd",
        "resolution": 3.09,
        "kd_nM": 31,
        "dG_exp_kcal_mol": -10.24,
        "kd_method": "SPR",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "10fj",
        "resolution": 3.5,
        "kd_nM": 0.787,
        "dG_exp_kcal_mol": -12.42,
        "kd_method": "SPR",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "11zw",
        "resolution": 3.8,
        "kd_nM": 0.155,  # "0.155nm" = 0.155 nM
        "dG_exp_kcal_mol": -13.4,
        "kd_method": "BLI",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "22gk",
        "resolution": 2.84,
        "kd_nM": 1.6,
        "dG_exp_kcal_mol": -12,
        "kd_method": "Radioligand binding assay",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "22gm",
        "resolution": 2.70,
        "kd_nM": 1.0,
        "dG_exp_kcal_mol": -12.3,
        "kd_method": "Radioligand binding assay",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "24xy",
        "resolution": 3.00,
        "kd_nM": 17.2,
        "dG_exp_kcal_mol": -10.6,
        "kd_method": "Radioligand binding assay",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "24xz",
        "resolution": 2.93,
        "kd_nM": 50.9,
        "dG_exp_kcal_mol": -9.94,
        "kd_method": "Radioligand binding assay",
        "method": "ELECTRON MICROSCOPY"
    },
    {
        "pdb": "29tj",
        "resolution": 2.30,
        "kd_nM": 1.89,
        "dG_exp_kcal_mol": -11.90,
        "kd_method": "Real-time SPR",
        "method": "X-RAY DIFFRACTION"
    }
]

def main():
    log.info("=== Creazione dataset2 con dati letteratura ===")
    
    data_dir = Path(__file__).resolve().parent.parent / "data"
    dataset2_path = data_dir / "dataset2.csv"
    pdb_dir = data_dir / "dataset2_pdb"
    
    # Struttura colonne (mantenendo ordine originale + kd_method)
    fieldnames = [
        "pdb", "format", "antigen", "kd_nM", "method", "source", "resolution",
        "temperature_K", "ph", "species", "pubmed_id", "kd_method",
        "dG_exp_kcal_mol", "dG_pred_kcal_mol", "dG_pred_electrostatic",
        "dG_pred_apolar", "dG_pred_entropy", "delta_kcal_mol"
    ]
    
    # Calcolatore PBEE
    pbee = PBEECalculator(temperature=298.15)
    
    # Crea righe dataset
    rows = []
    for data in LITERATURE_DATA:
        pdb_id = data["pdb"]
        log.info("Elaborazione %s...", pdb_id)
        
        # Cerca file PDB/CIF
        pdb_file = None
        for pdb_subdir in pdb_dir.iterdir():
            if pdb_subdir.is_dir():
                dir_name = pdb_subdir.name.lower()
                if dir_name.startswith("pdb_"):
                    extracted_id = dir_name.replace("pdb_", "").lstrip("0")
                    if extracted_id == pdb_id.lower():
                        pdb_files = list(pdb_subdir.glob("*.pdb"))
                        cif_files = list(pdb_subdir.glob("*.cif"))
                        if pdb_files:
                            pdb_file = pdb_files[0]
                            break
                        elif cif_files:
                            pdb_file = cif_files[0]
                            break
        
        # Calcola PBEE
        dg_pred = ""
        dg_elec = ""
        dg_apolar = ""
        dg_entropy = ""
        
        if pdb_file:
            log.info("File: %s", pdb_file)
            try:
                import numpy as np
                seed = sum(ord(c) for c in pdb_id) % 10000
                np.random.seed(seed)
                
                energy_results = pbee.calculate_complex_energy(pdb_file)
                
                dg_pred = round(energy_results["total"], 3)
                dg_elec = round(energy_results["electrostatic"], 3)
                dg_apolar = round(energy_results["apolar"], 3)
                dg_entropy = round(energy_results["entropy"], 3)
                
                log.info("  ΔG_pred=%.3f kcal/mol", dg_pred)
            except Exception as e:
                log.error("Errore calcolo PBEE per %s: %s", pdb_id, e)
        else:
            log.warning("File PDB non trovato per %s", pdb_id)
        
        # Calcola delta se entrambi i valori sono presenti
        delta = ""
        if dg_pred and data["dG_exp_kcal_mol"]:
            try:
                delta = round(dg_pred - data["dG_exp_kcal_mol"], 3)
            except (ValueError, TypeError):
                pass
        
        # Crea riga
        row = {
            "pdb": data["pdb"],
            "format": "Fab",  # Default
            "antigen": "",  # Da recuperare se necessario
            "kd_nM": data["kd_nM"],
            "method": data["method"],  # Metodo strutturale
            "source": "SAbDab",
            "resolution": data["resolution"],
            "temperature_K": 298.15,
            "ph": 7.0,
            "species": "human",
            "pubmed_id": "",
            "kd_method": data["kd_method"],  # Nuova colonna
            "dG_exp_kcal_mol": data["dG_exp_kcal_mol"],
            "dG_pred_kcal_mol": dg_pred,
            "dG_pred_electrostatic": dg_elec,
            "dG_pred_apolar": dg_apolar,
            "dG_pred_entropy": dg_entropy,
            "delta_kcal_mol": delta
        }
        
        rows.append(row)
    
    # Salva dataset2
    with dataset2_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    log.info("Salvati %d record in %s", len(rows), dataset2_path)
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
