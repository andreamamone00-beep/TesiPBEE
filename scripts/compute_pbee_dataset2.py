"""Script per calcolare PBEE per dataset2."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from pbee_calculator import calculate_pbee_for_complex

log = get_logger("pbee_dataset2")

def main():
    log.info("=== Calcolo PBEE per dataset2 ===")
    
    # Leggi dataset2 aggiornato
    dataset2_path = DATA_DIR / "dataset2_updated.csv"
    if not dataset2_path.exists():
        log.error("File dataset2_updated.csv non trovato")
        sys.exit(1)
    
    with dataset2_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    log.info("Dataset2: %d record", len(rows))
    
    # Directory dei file PDB
    pdb_dir = DATA_DIR / "dataset2_pdb"
    
    # Aggiungi campi PBEE se non presenti
    pbee_fields = ["dG_pred_kcal_mol", "dG_pred_electrostatic", "dG_pred_apolar", "dG_pred_entropy"]
    for field in pbee_fields:
        if field not in fieldnames:
            fieldnames.append(field)
    
    # Calcola PBEE per ogni record
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
        # Cerca in tutte le sottodirectory estraendo l'ID PDB dal nome
        for pdb_subdir in pdb_dir.iterdir():
            if pdb_subdir.is_dir():
                # Estrai PDB ID dal nome della directory(es: pdb_000010bt -> 10bt)
                dir_name = pdb_subdir.name.lower()
                # Rimuovi il prefisso "pdb_" e gli zeri iniziali
                if dir_name.startswith("pdb_"):
                    extracted_id = dir_name.replace("pdb_", "").lstrip("0")
                    if extracted_id == pdb_id:
                        # Cerca prima file PDB, poi CIF
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
            # Imposta valori nulli
            row["dG_pred_kcal_mol"] = ""
            row["dG_pred_electrostatic"] = ""
            row["dG_pred_apolar"] = ""
            row["dG_pred_entropy"] = ""
            updated_rows.append(row)
            continue
        
        log.info("File PDB: %s", pdb_file)
        
        try:
            # Calcola PBEE usando il calcolatore direttamente (senza Kd sperimentale)
            from pbee_calculator import PBEECalculator
            pbee = PBEECalculator(temperature=298.15)
            
            # Calcolo energia predetta senza Kd sperimentale
            energy_results = pbee.calculate_complex_energy(pdb_file)
            
            # Mappa i risultati ai campi attesi
            results = {
                "total": energy_results.get("total", 0.0),
                "electrostatic": energy_results.get("electrostatic", 0.0),
                "apolar": energy_results.get("apolar", 0.0),
                "entropy": energy_results.get("entropy", 0.0),
            }
            
            # Aggiorna il record
            row["dG_pred_kcal_mol"] = round(results["total"], 3)
            row["dG_pred_electrostatic"] = round(results["electrostatic"], 3)
            row["dG_pred_apolar"] = round(results["apolar"], 3)
            row["dG_pred_entropy"] = round(results["entropy"], 3)
            
            log.info("  ΔG_pred=%.3f kcal/mol (e=%.3f, a=%.3f, s=%.3f)", 
                    results["total"], results["electrostatic"], 
                    results["apolar"], results["entropy"])
            
        except Exception as e:
            log.warning("Errore calcolo PBEE per %s: %s", pdb_id, e)
            # Imposta valori nulli
            row["dG_pred_kcal_mol"] = ""
            row["dG_pred_electrostatic"] = ""
            row["dG_pred_apolar"] = ""
            row["dG_pred_entropy"] = ""
        
        updated_rows.append(row)
    
    # Salva il dataset con PBEE
    output_path = DATA_DIR / "dataset2_with_pbee.csv"
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    log.info("Salvati %d record in %s", len(updated_rows), output_path)
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
