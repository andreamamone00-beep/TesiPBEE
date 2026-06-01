import sys
sys.path.append('scripts')
from sources import search_antibody_complexes, load_sabdab_summary, parse_affinity_string

# Test the selection process
pdb_ids = search_antibody_complexes(10)
print(f"Selected PDB IDs: {pdb_ids}")

# Load SAbDab data and check affinity for selected IDs
sabdab_data = load_sabdab_summary()
sabdab_lookup = {entry.get('pdb', '').lower(): entry for entry in sabdab_data if entry.get('pdb')}

print("\nChecking affinity for selected PDBs:")
for pdb_id in pdb_ids:
    entry = sabdab_lookup.get(pdb_id)
    if entry:
        affinity = entry.get('affinity', '')
        parsed = parse_affinity_string(affinity)
        print(f"{pdb_id}: affinity='{affinity}', parsed={parsed}")
    else:
        print(f"{pdb_id}: NOT FOUND in SAbDab")
