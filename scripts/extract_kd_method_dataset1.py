"""Script per estrarre kd_method da SAbDab per dataset1."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from sources import load_sabdab_summary

log = get_logger("extract_kd_method_dataset1")

def main():
    log.info("=== Estrazione kd_method da SAbDab per dataset1 ===")
    
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
    
    # Estrai kd_method da SAbDab
    results = []
    for row in rows:
        pdb_id = row.get("pdb", "").lower()
        
        # Cerca kd_method in SAbDab (affinity_method, non method)
        kd_method = ""
        for entry in sabdab_data:
            if entry.get('pdb', '').lower() == pdb_id:
                kd_method = entry.get('affinity_method', '')
                break
        
        results.append({
            "pdb": pdb_id,
            "kd_method": kd_method,
            "kd_nM": row.get("kd_nM", ""),
            "antigen": row.get("antigen", "")
        })
        
        if kd_method:
            log.info("%s: %s", pdb_id, kd_method)
        else:
            log.warning("%s: metodo non trovato in SAbDab", pdb_id)
    
    # Salva risultati
    output_path = data_dir / "dataset1_kd_methods.csv"
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pdb", "kd_method", "kd_nM", "antigen"])
        writer.writeheader()
        writer.writerows(results)
    
    log.info("Salvati %d record in %s", len(results), output_path)
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
