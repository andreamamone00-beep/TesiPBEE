"""Script per aggiungere kd_method a dataset1."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from sources import load_sabdab_summary

log = get_logger("add_kd_method_dataset1")

def main():
    log.info("=== Aggiunta kd_method a dataset1 ===")
    
    data_dir = Path(__file__).resolve().parent.parent / "data"
    dataset1_path = data_dir / "dataset.csv"
    sabdab_path = data_dir / "sabdab_summary.tsv"
    
    # Carica SAbDab
    sabdab_data = load_sabdab_summary(sabdab_path)
    log.info("Caricati %d entry SAbDab", len(sabdab_data))
    
    # Leggi dataset1
    with dataset1_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    # Aggiungi kd_method se non esiste
    if "kd_method" not in fieldnames:
        fieldnames.insert(fieldnames.index("pubmed_id") + 1, "kd_method")
    
    # Aggiorna kd_method
    updated_rows = []
    for row in rows:
        pdb_id = row.get("pdb", "").lower()
        
        # Cerca kd_method in SAbDab (affinity_method)
        kd_method = ""
        for entry in sabdab_data:
            if entry.get('pdb', '').lower() == pdb_id:
                kd_method = entry.get('affinity_method', '')
                break
        
        row["kd_method"] = kd_method
        updated_rows.append(row)
        
        if kd_method and kd_method != "Unknown":
            log.info("%s: %s", pdb_id, kd_method)
    
    # Salva dataset1 aggiornato
    with dataset1_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    log.info("Salvati %d record in %s", len(updated_rows), dataset1_path)
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
