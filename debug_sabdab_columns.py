import sys
sys.path.append('scripts')
from sources import load_sabdab_summary

data = load_sabdab_summary()
if data:
    print("Column names:")
    print(list(data[0].keys()))
    
    print("\nLooking for affinity-related columns:")
    all_keys = set()
    for entry in data[:100]:
        all_keys.update(entry.keys())
    
    affinity_keys = [k for k in all_keys if 'affin' in k.lower() or 'kd' in k.lower() or 'bind' in k.lower()]
    print("Affinity-related columns:", affinity_keys)
    
    print("\nSample data for affinity columns:")
    for i, entry in enumerate(data[:5]):
        print(f"Entry {i+1}:")
        for key in affinity_keys:
            if key in entry:
                print(f"  {key}: '{entry[key]}'")
