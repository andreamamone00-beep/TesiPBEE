from pathlib import Path
import csv
import sys

root = Path.cwd()
sys.path.insert(0, str(root / 'scripts'))

from utils import DATASET_RAW
import importlib.util

spec = importlib.util.spec_from_file_location('build_dataset', root / 'scripts' / '01_build_dataset.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

rows = mod.build_from_sabdab(root / 'data' / 'sabdab_summary.tsv', max_hits=50)
with DATASET_RAW.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f'Wrote {len(rows)} rows to {DATASET_RAW}')
