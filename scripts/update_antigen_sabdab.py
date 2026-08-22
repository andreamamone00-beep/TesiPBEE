"""Script per aggiornare antigen info da SAbDab e RCSB PDB per dataset2."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from sources import load_sabdab_summary, fetch_pdb_metadata, guess_format_and_antigen

log = get_logger("update_antigen_sabdab")

def main():
    log.info("=== Aggiornamento antigen da SAbDab e RCSB PDB ===")
    
    data_dir = Path(__file__).resolve().parent.parent / "data"
    dataset2_path = data_dir / "dataset2.csv"
    sabdab_path = data_dir / "sabdab_summary.tsv"
    
    # Carica SAbDab
    sabdab_data = load_sabdab_summary(sabdab_path)
    log.info("Caricati %d entry SAbDab", len(sabdab_data))
    
    # Leggi dataset2
    with dataset2_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    # Aggiorna antigen
    updated_rows = []
    for row in rows:
        pdb_id = row.get("pdb", "").lower()
        
        # Cerca antigen in SAbDab
        antigen = ""
        source = "SAbDab"
        for entry in sabdab_data:
            if entry.get('pdb', '').lower() == pdb_id:
                antigen = entry.get('antigen_name', '')
                if not antigen:
                    antigen = entry.get('antigen_type', '')
                break
        
        # Se non trovato in SAbDab, prova RCSB PDB
        if not antigen:
            try:
                meta = fetch_pdb_metadata(pdb_id)
                if meta:
                    fmt, antigen, res = guess_format_and_antigen(meta)
                    source = "RCSB"
                    log.info("%s: trovato in RCSB: %s", pdb_id, antigen)
            except Exception as e:
                log.warning("Errore RCSB per %s: %s", pdb_id, e)
        
        row["antigen"] = antigen
        updated_rows.append(row)
        
        if antigen:
            log.info("%s: %s (%s)", pdb_id, antigen, source)
    
    # Salva dataset2 aggiornato
    with dataset2_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    log.info("Salvati %d record in %s", len(updated_rows), dataset2_path)
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
