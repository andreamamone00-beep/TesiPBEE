"""Script per verificare i campi disponibili in SAbDab."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import DATA_DIR, get_logger
from sources import load_sabdab_summary

log = get_logger("check_sabdab_fields")

def main():
    log.info("=== Verifica campi SAbDab ===")
    
    data_dir = Path(__file__).resolve().parent.parent / "data"
    sabdab_path = data_dir / "sabdab_summary.tsv"
    
    # Carica SAbDab
    sabdab_data = load_sabdab_summary(sabdab_path)
    log.info("Caricati %d entry SAbDab", len(sabdab_data))
    
    # Mostra tutti i campi disponibili
    if sabdab_data:
        fields = list(sabdab_data[0].keys())
        log.info("Campi disponibili in SAbDab:")
        for field in sorted(fields):
            log.info("  - %s", field)
    
    # Cerca entry con dati di affinità
    affinity_entries = [e for e in sabdab_data if e.get('affinity')]
    log.info("Entry con dati di affinità: %d", len(affinity_entries))
    
    if affinity_entries:
        sample = affinity_entries[0]
        log.info("Esempio entry con affinità:")
        for k, v in sample.items():
            if v:
                log.info("  %s: %s", k, v)

if __name__ == "__main__":
    main()
