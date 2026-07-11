import sys
from pathlib import Path
sys.path.insert(0, str(Path('scripts').resolve()))
from sources import load_sabdab_summary
raw = load_sabdab_summary(Path('data/sabdab_summary.tsv'))
print('count', len(raw))
print('head', [r.get('pdb') for r in raw[:10]])
