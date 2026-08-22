"""Script per popolare dataset2 con dati sperimentali da SAbDab e RCSB PDB."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from sources import load_sabdab_summary, fetch_pdb_metadata, parse_affinity_string, fetch_pdbbind_affinity

log = get_logger("populate_dataset2")

def get_sabdab_entry(pdb_id: str, sabdab_data: list[dict]) -> dict | None:
    """Cerca un PDB ID nel dataset SAbDab."""
    pdb_id_lower = pdb_id.lower()
    for entry in sabdab_data:
        if entry.get('pdb', '').lower() == pdb_id_lower:
            return entry
    return None

def get_pdb_resolution(pdb_id: str) -> float | None:
    """Recupera la risoluzione da RCSB PDB."""
    try:
        meta = fetch_pdb_metadata(pdb_id)
        if meta:
            entry = (meta.get("data") or {}).get("entry") or {}
            exptl = entry.get("exptl") or []
            for expt in exptl:
                method = expt.get("method", "")
                if method in ["X-RAY DIFFRACTION", "XRAY", "X-RAY"]:
                    # Per X-ray, cerca la risoluzione
                    for expt_detail in exptl:
                        if "diffrn" in expt_detail:
                            diffrn = expt_detail["diffrn"]
                            if isinstance(diffrn, list) and len(diffrn) > 0:
                                diffrn_item = diffrn[0]
                                if "diffrn_resolution_limit" in diffrn_item:
                                    res_data = diffrn_item["diffrn_resolution_limit"]
                                    if isinstance(res_data, list) and len(res_data) > 0:
                                        res_item = res_data[0]
                                        if isinstance(res_item, dict):
                                            res_value = res_item.get("d_resolution_high")
                                            if res_value:
                                                try:
                                                    return float(res_value)
                                                except (ValueError, TypeError):
                                                    pass
            # Fallback: cerca risoluzione in altri campi
            struct = (meta.get("data") or {}).get("struct") or {}
            res_value = struct.get("pdbx_entry_info", {}).get("resolution")
            if res_value:
                try:
                    return float(res_value)
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        log.warning("Errore recupero risoluzione per %s: %s", pdb_id, e)
    return None

def get_experimental_data(pdb_id: str, sabdab_data: list[dict]) -> dict:
    """Recupera dati sperimentali da SAbDab e PDBBind."""
    result = {
        "kd_nM": None,
        "method": None,
        "resolution": None,
        "antigen": None,
        "format": None,
    }
    
    # Prima prova SAbDab
    sabdab_entry = get_sabdab_entry(pdb_id, sabdab_data)
    if sabdab_entry:
        # Affinità
        affinity_str = sabdab_entry.get('affinity', '')
        if affinity_str:
            kd_nm = parse_affinity_string(affinity_str)
            if kd_nm and kd_nm > 0:
                result["kd_nM"] = kd_nm
        
        # Metodo
        method = sabdab_entry.get('method', '')
        if method:
            result["method"] = method
        
        # Antigene
        antigen = sabdab_entry.get('antigen_name', '')
        if antigen:
            result["antigen"] = antigen
        
        # Formato
        format_val = sabdab_entry.get('format', '')
        if format_val:
            result["format"] = format_val
        
        # Risoluzione
        res_str = sabdab_entry.get('resolution', '')
        if res_str:
            try:
                result["resolution"] = float(res_str)
            except (ValueError, TypeError):
                pass
    
    # Se non abbiamo KD da SAbDab, prova PDBBind
    if result["kd_nM"] is None:
        kd_nm, _ = fetch_pdbbind_affinity(pdb_id)
        if kd_nm and kd_nm > 0:
            result["kd_nM"] = kd_nm
    
    # Se non abbiamo risoluzione, prova RCSB PDB
    if result["resolution"] is None:
        res = get_pdb_resolution(pdb_id)
        if res:
            result["resolution"] = res
    
    return result

def main():
    log.info("=== Popolamento dataset2 con dati sperimentali ===")
    
    # Carica SAbDab summary
    sabdab_path = DATA_DIR / "sabdab_summary.tsv"
    if not sabdab_path.exists():
        log.error("File SAbDab summary non trovato: %s", sabdab_path)
        sys.exit(1)
    
    log.info("Caricamento SAbDab summary...")
    sabdab_data = load_sabdab_summary(sabdab_path)
    log.info("Caricati %d entry SAbDab", len(sabdab_data))
    
    # Leggi dataset2 corrente
    dataset2_path = DATA_DIR / "dataset2.csv"
    if not dataset2_path.exists():
        log.error("File dataset2.csv non trovato")
        sys.exit(1)
    
    with dataset2_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    log.info("Dataset2 corrente: %d record", len(rows))
    
    # Aggiorna ogni record con dati sperimentali
    updated_rows = []
    for row in rows:
        pdb_id = row.get("pdb", "")
        if not pdb_id:
            log.warning("Record senza PDB ID, saltato")
            updated_rows.append(row)
            continue
        
        log.info("Elaborazione %s...", pdb_id)
        
        # Recupera dati sperimentali
        exp_data = get_experimental_data(pdb_id, sabdab_data)
        
        # Aggiorna il record
        if exp_data["kd_nM"]:
            row["kd_nM"] = exp_data["kd_nM"]
            log.info("  Kd: %.3f nM", exp_data["kd_nM"])
        else:
            log.warning("  Kd non trovato")
        
        if exp_data["method"]:
            row["method"] = exp_data["method"]
            log.info("  Method: %s", exp_data["method"])
        else:
            log.warning("  Method non trovato")
        
        if exp_data["resolution"]:
            row["resolution"] = exp_data["resolution"]
            log.info("  Resolution: %.2f Å", exp_data["resolution"])
        else:
            log.warning("  Resolution non trovata")
        
        if exp_data["antigen"]:
            row["antigen"] = exp_data["antigen"]
        
        if exp_data["format"]:
            row["format"] = exp_data["format"]
        
        updated_rows.append(row)
    
    # Salva il dataset aggiornato
    output_path = DATA_DIR / "dataset2_updated.csv"
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    log.info("Salvati %d record in %s", len(updated_rows), output_path)
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
