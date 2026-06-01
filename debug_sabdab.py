import sys
sys.path.append('scripts')
from sources import load_sabdab_summary

data = load_sabdab_summary()
print('Sample entries:')
for i, e in enumerate(data[:5]):
    print(f"{i+1}. PDB: {e.get('pdb')}, Affinity: '{e.get('affinity')}', Antigen: '{e.get('antigen_name')}'")

print(f"\nTotal entries: {len(data)}")
print("Affinity values found:")
affinity_values = [e.get('affinity') for e in data if e.get('affinity')]
print(f"Entries with affinity: {len(affinity_values)}")
print("Sample affinity values:")
for i, val in enumerate(affinity_values[:10]):
    print(f"{i+1}. '{val}'")
