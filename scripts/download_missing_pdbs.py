"""Script per scaricare file PDB mancanti da RCSB PDB."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from sources import fetch_pdb_file

log = get_logger("download_missing_pdbs")

# PDB mancanti
MISSING_PDBS = ["10fd", "10fj", "11zw", "22gk", "22gm", "24xy", "24xz", "29tj"]

def main():
    log.info("=== Download PDB mancanti ===")
    
    data_dir = Path(__file__).resolve().parent.parent / "data"
    pdb_dir = data_dir / "dataset2_pdb"
    
    for pdb_id in MISSING_PDBS:
        log.info("Download %s...", pdb_id)
        
        try:
            # Scarica file PDB in cache
            cached_file = fetch_pdb_file(pdb_id)
            if cached_file:
                # Crea directory target
                dir_name = f"pdb_0000{pdb_id.lower()}"
                target_dir = pdb_dir / dir_name
                target_dir.mkdir(exist_ok=True)
                
                # Copia file nella directory target
                target_file = target_dir / f"pdb_0000{pdb_id.lower()}_sabdab.pdb"
                import shutil
                shutil.copy(cached_file, target_file)
                log.info("Scaricato: %s", target_file)
            else:
                log.warning("Download fallito per %s", pdb_id)
        except Exception as e:
            log.error("Errore download %s: %s", pdb_id, e)
    
    log.info("=== Completato ===")

if __name__ == "__main__":
    main()
