from sources import load_sabdab_summary
import csv

def main():
    online = load_sabdab_summary(tsv_path=None)
    online_set = {e.get('pdb','').lower() for e in online if e.get('pdb')}
    missing = []
    with open('data/dataset_raw.csv', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        pdb = (r.get('pdb') or '').lower()
        if pdb and pdb not in online_set:
            missing.append(pdb)
    print('missing_count=', len(missing))
    if missing:
        print('\n'.join(sorted(set(missing))))

if __name__ == '__main__':
    main()
