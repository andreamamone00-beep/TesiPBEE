import sys
sys.path.append('scripts')
from sources import load_sabdab_summary

data = load_sabdab_summary()
print("Looking for entries with real affinity data (not 'None'):")

real_entries = []
for entry in data:
    affinity = entry.get('affinity', '')
    if affinity and affinity != 'None':
        real_entries.append(entry)

print(f"Found {len(real_entries)} entries with real affinity data")
print("\nFirst 10 entries with real affinity:")
for i, entry in enumerate(real_entries[:10]):
    print(f"{i+1}. PDB: {entry.get('pdb')}, Affinity: '{entry.get('affinity')}', Method: '{entry.get('method')}', Antigen: '{entry.get('antigen_name')}'")

if real_entries:
    print("\nAnalyzing affinity format:")
    sample_affinities = [entry.get('affinity') for entry in real_entries[:20]]
    for i, aff in enumerate(sample_affinities):
        print(f"{i+1}. '{aff}'")
