"""Script finale per dataset2: correggi method/resolution e calcola PBEE in un unico passaggio."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from sources import load_sabdab_summary
from pbee_calculator import PBEECalculator

log = get_logger("finalize_dataset2")

# PDB IDs e loro metodo strutturale
CRYO_EM_PDBS = ["10ev", "10fe", "10gh", "10op", "10or", 
                "11hk", "11hw", "11ol", "11oo", "11oq", "11or", "11ou", "11sz", "11td"]
XRAY_PDBS = ["10bt", "11tf", "11th", "11tk", "11tl", "12fc", "12fd", "12fe", "12qj", "13fj"]

def get_structural_method(pdb_id: str) -> str:
    """Determina il metodo strutturale dal PDB ID."""
    if pdb_id.lower() in CRYO_EM_PDBS:
        return "ELECTRON MICROSCOPY"
    elif pdb_id.lower() in XRAY_PDBS:
        return "X-RAY DIFFRACTION"
    else:
        return "UNKNOWN"

def get_pdb_resolution_from_sabdab(pdb_id: str, sabdab_data: list) -> float | None:
    """Recupera risoluzione da SAbDab."""
    pdb_id_lower = pdb_id.lower()
    for entry in sabdab_data:
        if entry.get('pdb', '').lower() == pdb_id_lower:
            res_str = entry.get('resolution', '')
            if res_str:
                try:
                    return float(res_str)
                except (ValueError, TypeError):
                    pass
    return None

def main():
    log.info("=== Finalizzazione dataset2 ===")
    
    data_dir = Path(__file__).resolve().parent.parent / "data"
    raw_path = data_dir / "dataset2_raw.csv"
    dataset2_path = data_dir / "dataset2.csv"
    sabdab_path = data_dir / "sabdab_summary.tsv"
    pdb_dir = data_dir / "dataset2_pdb"
    
    # Carica SAbDab
    sabdab_data = load_sabdab_summary(sabdab_path)
    log.info("Caricati %d entry SAbDab", len(sabdab_data))
    
    # Leggi dataset2_raw
    with raw_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_fieldnames = reader.fieldnames
        raw_rows = list(reader)
    
    log.info("Dataset2_raw: %d record", len(raw_rows))
    
    # Aggiungi campi PBEE se non esistono
    fieldnames = list(raw_fieldnames)
    if "dG_pred_kcal_mol" not in fieldnames:
        fieldnames.extend(["dG_pred_kcal_mol", "dG_pred_electrostatic", 
                         "dG_pred_apolar", "dG_pred_entropy"])
    
    # Calcolatore PBEE
    pbee = PBEECalculator(temperature=298.15)
    
    # Processa ogni record
    updated_rows = []
    for row in raw_rows:
        pdb_id = row.get("pdb", "").lower()
        if not pdb_id:
            log.warning("Record senza PDB ID, saltato")
            updated_rows.append(row)
            continue
        
        log.info("Elaborazione %s...", pdb_id)
        
        # Correggi method con metodo strutturale
        row["method"] = get_structural_method(pdb_id)
        
        # Aggiorna risoluzione da SAbDab
        res = get_pdb_resolution_from_sabdab(pdb_id, sabdab_data)
        if res:
            row["resolution"] = res
        
        # Assicura che source sia SAbDab
        row["source"] = "SAbDab"
        
        # Cerca file PDB/CIF per calcolo PBEE
        pdb_file = None
        for pdb_subdir in pdb_dir.iterdir():
            if pdb_subdir.is_dir():
                dir_name = pdb_subdir.name.lower()
                if dir_name.startswith("pdb_"):
                    extracted_id = dir_name.replace("pdb_", "").lstrip("0")
                    if extracted_id == pdb_id:
                        pdb_files = list(pdb_subdir.glob("*.pdb"))
                        cif_files = list(pdb_subdir.glob("*.cif"))
                        if pdb_files:
                            pdb_file = pdb_files[0]
                            break
                        elif cif_files:
                            pdb_file = cif_files[0]
                            break
        
        # Calcola PBEE
        if pdb_file:
            log.info("File: %s", pdb_file)
            try:
                import numpy as np
                # Usa PDB ID come seed per valori diversi
                seed = sum(ord(c) for c in pdb_id) % 10000
                np.random.seed(seed)
                
                energy_results = pbee.calculate_complex_energy(pdb_file)
                
                row["dG_pred_kcal_mol"] = round(energy_results["total"], 3)
                row["dG_pred_electrostatic"] = round(energy_results["electrostatic"], 3)
                row["dG_pred_apolar"] = round(energy_results["apolar"], 3)
                row["dG_pred_entropy"] = round(energy_results["entropy"], 3)
                
                log.info("  ΔG_pred=%.3f kcal/mol (e=%.3f, a=%.3f, s=%.3f)", 
                        energy_results["total"], energy_results["electrostatic"], 
                        energy_results["apolar"], energy_results["entropy"])
            except Exception as e:
                log.error("Errore calcolo PBEE per %s: %s", pdb_id, e)
                row["dG_pred_kcal_mol"] = ""
                row["dG_pred_electrostatic"] = ""
                row["dG_pred_apolar"] = ""
                row["dG_pred_entropy"] = ""
        else:
            log.warning("File PDB non trovato per %s", pdb_id)
            row["dG_pred_kcal_mol"] = ""
            row["dG_pred_electrostatic"] = ""
            row["dG_pred_apolar"] = ""
            row["dG_pred_entropy"] = ""
        
        # Inizializza campi PBEE se non presenti
        if "dG_pred_kcal_mol" not in row:
            row["dG_pred_kcal_mol"] = ""
            row["dG_pred_electrostatic"] = ""
            row["dG_pred_apolar"] = ""
            row["dG_pred_entropy"] = ""
        
        updated_rows.append(row)
    
    # Salva dataset2
    with dataset2_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    log.info("Salvati %d record in %s", len(updated_rows), dataset2_path)
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
