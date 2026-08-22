"""Script per calcolare PBEE per dataset2 usando dataset2_raw.csv come base."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from pbee_calculator import PBEECalculator

log = get_logger("compute_pbee_dataset2")

def main():
    log.info("=== Calcolo PBEE per dataset2 (base: dataset2_raw.csv) ===")
    
    # Percorsi
    data_dir = Path(__file__).resolve().parent.parent / "data"
    dataset2_path = data_dir / "dataset2.csv"
    pdb_dir = data_dir / "dataset2_pdb"
    
    if not dataset2_path.exists():
        log.error("File dataset2.csv non trovato")
        sys.exit(1)
    
    # Leggi dataset2
    with dataset2_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        # Aggiungi campi per PBEE se non esistono
        if "dG_pred_kcal_mol" not in fieldnames:
            fieldnames.extend(["dG_pred_kcal_mol", "dG_pred_electrostatic", 
                             "dG_pred_apolar", "dG_pred_entropy"])
        rows = list(reader)
    
    log.info("Dataset2: %d record", len(rows))
    
    # Calcolatore PBEE
    pbee = PBEECalculator(temperature=298.15)
    
    # Aggiorna ogni record
    updated_rows = []
    for row in rows:
        pdb_id = row.get("pdb", "").lower()
        if not pdb_id:
            log.warning("Record senza PDB ID, saltato")
            updated_rows.append(row)
            continue
        
        log.info("Elaborazione %s...", pdb_id)
        
        # Cerca file PDB/CIF
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
        
        if not pdb_file:
            log.warning("File PDB non trovato per %s", pdb_id)
            row["dG_pred_kcal_mol"] = ""
            row["dG_pred_electrostatic"] = ""
            row["dG_pred_apolar"] = ""
            row["dG_pred_entropy"] = ""
            updated_rows.append(row)
            continue
        
        log.info("File: %s", pdb_file)
        
        try:
            # Calcola PBEE senza seed fisso per ottenere valori unici
            import numpy as np
            # Usa PDB ID come seed per riproducibilità ma valori diversi
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
        
        # Non modificare method, source, resolution - già corretti
        updated_rows.append(row)
    
    # Salva in dataset2.csv
    output_path = data_dir / "dataset2.csv"
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    log.info("Salvati %d record in %s", len(updated_rows), output_path)
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
