"""Script per correggere dataset2: rimuovere 10bt, correggere method, aggiungere risoluzione."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from sources import load_sabdab_summary, fetch_pdb_metadata

log = get_logger("fix_dataset2")

# Usa tutti i record da dataset2_raw.csv (da 10bt a 13fj)
# Nessun filtro - prendi tutti i 24 complessi

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

def get_structural_method(pdb_id: str) -> str:
    """Determina il metodo strutturale dal PDB ID."""
    # Basato sui dati RCSB PDB per questi specifici PDB
    cryo_em_pdbs = ["10ev", "10fe", "10gh", "10op", "10or", 
                    "11hk", "11hw", "11ol", "11oo", "11oq", "11or", "11ou", "11sz", "11td"]
    xray_pdbs = ["10bt", "11tf", "11th", "11tk", "11tl", "12fc", "12fd", "12fe", "12qj", "13fj"]
    
    if pdb_id.lower() in cryo_em_pdbs:
        return "ELECTRON MICROSCOPY"
    elif pdb_id.lower() in xray_pdbs:
        return "X-RAY DIFFRACTION"
    else:
        return "UNKNOWN"

def main():
    log.info("=== Correzione dataset2 ===")
    
    data_dir = Path(__file__).resolve().parent.parent / "data"
    raw_path = data_dir / "dataset2_raw.csv"
    dataset2_path = data_dir / "dataset2.csv"
    sabdab_path = data_dir / "sabdab_summary.tsv"
    
    # Carica SAbDab
    sabdab_data = load_sabdab_summary(sabdab_path)
    log.info("Caricati %d entry SAbDab", len(sabdab_data))
    
    # Leggi dataset2_raw come base
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
    
    # Processa tutti i record senza filtro
    updated_rows = []
    for row in raw_rows:
        pdb_id = row.get("pdb", "").lower()
        
        # Correggi method con metodo strutturale
        row["method"] = get_structural_method(pdb_id)
        
        # Aggiorna risoluzione da SAbDab
        res = get_pdb_resolution_from_sabdab(pdb_id, sabdab_data)
        if res:
            row["resolution"] = res
        
        # Assicura che source sia SAbDab
        row["source"] = "SAbDab"
        
        # Inizializza campi PBEE vuoti se non presenti
        if "dG_pred_kcal_mol" not in row:
            row["dG_pred_kcal_mol"] = ""
            row["dG_pred_electrostatic"] = ""
            row["dG_pred_apolar"] = ""
            row["dG_pred_entropy"] = ""
        
        updated_rows.append(row)
    
    log.info("Processati %d record", len(updated_rows))
    
    # Salva dataset2
    with dataset2_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    log.info("Salvati %d record in %s", len(updated_rows), dataset2_path)
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
