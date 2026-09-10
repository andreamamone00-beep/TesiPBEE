"""Trova strutture anticorpo-antigene per sostituire PDB senza PBEE."""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SABDAB_SUMMARY = ROOT / "data" / "sabdab_summary.tsv"
OUTPUT_FILE = ROOT / "data" / "replacement_candidates.csv"

def find_replacement_candidates():
    """Cerca strutture anticorpo-antigene con dati sperimentali."""
    candidates = []

    with open(SABDAB_SUMMARY, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            # Filtra per anticorpo umano o murino
            heavy_species = row.get('heavy_species', '').lower()
            if 'human' not in heavy_species and 'mus' not in heavy_species:
                continue

            # Filtra per antigene proteico
            antigen_type = row.get('antigen_type', '').lower()
            if antigen_type != 'protein':
                continue

            # Filtra per presenza di dati di affinitÃƒÂ
            affinity = row.get('affinity')
            if not affinity or affinity == 'None':
                continue

            # Filtra per risoluzione decente (< 3.0 Ãƒâ€¦)
            try:
                resolution = float(row.get('resolution', 999))
                if resolution > 3.0:
                    continue
            except (ValueError, TypeError):
                continue

            # Escludi PDB giÃƒÂ  presenti in dataset1
            existing_pdbs = {'4jn2', '5sy8', '5myo', '3uzq', '4hpy', '4cmh', '4n8c',
                           '6ddm', '4al8', '2E+027', '2vxt', '4fqi', '5myk', '6b14',
                           '5tkk', '4qyo', '4r3s', '5myx', '5alc', '3ifl', '5kvg',
                           '4m1g', '4qxt', '5cin', '3wih', '5i8c', '4hs6', '5e2w',
                           '5kvf', '5kve', '3t0w', '4qy8', '3kdm', '3uyr', '1q72',
                           '3g5y', '5kvd', '5yy4', '5a2k', '5e2v', '5n88', '5a2j',
                           '2xzc', '3ggw', '3pp4', '2r1x', '2r1w', '2r1y', '2r2b', '2r23'}

            pdb_id = row.get('pdb', '').lower()
            if pdb_id in existing_pdbs:
                continue

            candidates.append({
                'pdb': row.get('pdb', ''),
                'antigen_name': row.get('antigen_name', ''),
                'antigen_species': row.get('antigen_species', ''),
                'heavy_species': row.get('heavy_species', ''),
                'light_species': row.get('light_species', ''),
                'affinity_nM': row.get('affinity', ''),
                'affinity_method': row.get('affinity_method', ''),
                'delta_g_kcal_mol': row.get('delta_g', ''),
                'resolution': row.get('resolution', ''),
                'method': row.get('method', ''),
                'pmid': row.get('pmid', ''),
                'temperature': row.get('temperature', ''),
            })

    # Ordina per risoluzione (migliore prima)
    candidates.sort(key=lambda x: float(x['resolution']) if x['resolution'] else 999)

    # Salva i candidati
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['pdb', 'antigen_name', 'antigen_species', 'heavy_species',
                     'light_species', 'affinity_nM', 'affinity_method',
                     'delta_g_kcal_mol', 'resolution', 'method', 'pmid', 'temperature']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    print(f"Trovati {len(candidates)} candidati")
    print(f"Salvati in {OUTPUT_FILE}")

    # Mostra i primi 10 candidati
    print("\nTop 10 candidati:")
    for i, c in enumerate(candidates[:10], 1):
        print(f"{i}. {c['pdb']}: {c['antigen_name']} ({c['antigen_species']}) - "
              f"Kd={c['affinity_nM']} nM, {c['affinity_method']}, "
              f"res={c['resolution']} Ãƒâ€¦")

if __name__ == "__main__":
    find_replacement_candidates()
