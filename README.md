# Ab/ScFv–Ag dataset & PBEE benchmark

Prototipo funzionante per tesi triennale (Andrea Mamone): costruzione di un dataset strutturale anticorpo-antigene con dati sperimentali di affinità, e valutazione delle predizioni di energia libera di legame mediante PBEE.

## Caratteristiche

- **Pipeline Python in 5 step** (`scripts/01` → `scripts/05`)
- **Connessione reale alle API pubbliche**: RCSB PDB (Search + GraphQL), PubMed (NCBI E-utilities), BindingDB, SAbDab
- **Cache su disco** di tutte le chiamate di rete (directory `data/cache/`, TTL 7 giorni)
- **Rate-limit** automatico per rispettare le politiche delle API pubbliche
- **Fallback offline**: tutto funziona anche senza internet grazie alla modalità `simulated` con dati riproducibili
- **Dashboard Flask** con filtri dinamici, grafici interattivi (scatter + residui), tabella filtrabile, export CSV
- **20 grafici di ricerca** generati automaticamente (scatter, residui, Bland–Altman, Q–Q plot, ROC, calibration curve, decomposizione componenti, heatmap, ranking accuracy, ecc.)
- **Pagina di stato fonti** che verifica in tempo reale la raggiungibilità delle API

## Struttura del progetto

```
ab_ag_pbee/
├── README.md                    ← questo file
├── requirements.txt             ← dipendenze Python
├── run.sh / run.bat             ← avvio one-click (Linux/macOS / Windows)
├── data/
│   ├── dataset_raw.csv          ← generato dallo step 1
│   ├── dataset_curated.csv      ← generato dallo step 2
│   ├── dataset_normalized.csv   ← generato dallo step 3
│   ├── dataset.csv              ← dataset finale (dopo step 4)
│   └── cache/                   ← cache API esterne (JSON)
├── scripts/
│   ├── utils.py                 ← costanti fisiche, helper condivisi
│   ├── sources.py               ← client API (RCSB, PubMed, BindingDB, SAbDab)
│   ├── 01_build_dataset.py      ← costruzione dataset multi-sorgente
│   ├── 02_curate_structures.py  ← cura strutturale (biopython + fallback)
│   ├── 03_normalize_affinity.py ← Kd → ΔG a 298 K
│   ├── 04_compute_pbee.py       ← calcolo PBEE (simulato o APBS)
│   └── 05_analyze_results.py    ← 20 grafici + metriche complete
├── dashboard/
│   ├── app.py                   ← server Flask
│   ├── templates/               ← index.html, gallery.html, sources.html
│   └── static/                  ← style.css, app.js, chart.umd.min.js (opz.)
├── results/                     ← 20 grafici PNG + metrics.json + CSV di metriche
└── docs/
    └── pipeline.md              ← documentazione tecnica dettagliata
```

## Installazione

### Requisiti

- **Python 3.9+** (testato su 3.10–3.12)
- Nessun software esterno obbligatorio
- Per calcoli PBEE reali (opzionali): [APBS](https://www.poissonboltzmann.org) + [PDB2PQR](https://pdb2pqr.readthedocs.io)

### Avvio rapido

**Linux/macOS:**
```bash
chmod +x run.sh
./run.sh                # modalità simulata (default)
./run.sh online         # modalità online (usa API reali)
```

**Windows:**
```powershell
run.bat                 # modalità simulata
run.bat online          # modalità online
```

Lo script crea automaticamente il virtualenv, installa le dipendenze, esegue la pipeline completa e avvia la dashboard su `http://127.0.0.1:5000`.

### Installazione manuale

```bash
cd ab_ag_pbee
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

### Pipeline a passi separati

```bash
# Step 1: costruzione dataset
# Modalità simulata (offline, 48 complessi riproducibili con seed):
python scripts/01_build_dataset.py --mode simulated --n 48

# Modalità online (API reali, con cache e fallback):
python scripts/01_build_dataset.py --mode online --n 50 --fallback-simulated

# Modalità SAbDab (file TSV locale):
python scripts/01_build_dataset.py --mode sabdab --sabdab-path /path/to/summary.tsv

# Step 2: cura strutturale
python scripts/02_curate_structures.py              # scarica PDB veri via biopython
python scripts/02_curate_structures.py --no-download  # salta il download

# Step 3: normalizzazione Kd → ΔG a 298 K
python scripts/03_normalize_affinity.py

# Step 4: calcolo PBEE
python scripts/04_compute_pbee.py --mode simulated  # (default)
python scripts/04_compute_pbee.py --mode apbs       # usa APBS reale se installato

# Step 5: metriche + 20 grafici
python scripts/05_analyze_results.py

# Dashboard
python dashboard/app.py
```

### Dashboard

Apri `http://127.0.0.1:5000` dopo aver lanciato `dashboard/app.py`.

La dashboard ha 3 pagine:

1. **Dashboard** (`/`): 7 metriche live (N, RMSE, MAE, Pearson, Spearman, Kendall τ, bias), filtri dinamici (formato Ab, tecnica, fonte, risoluzione max, Kd max), scatter plot interattivo, istogramma residui, tabella complessi con codifica colore della discrepanza (verde <1, arancione 1-2, rosso >2 kcal/mol), export CSV filtrato
2. **Grafici** (`/gallery`): galleria dei 20 grafici PNG generati dallo step 5, con lightbox per ingrandire
3. **Fonti** (`/sources`): stato di connettività live delle API esterne (RCSB, PubMed, SAbDab, BindingDB), con pulsante di ri-verifica

## I 20 grafici di ricerca

Tutti salvati in `results/` come PNG a 150 DPI:

| # | File | Descrizione |
|---|------|-------------|
| 01 | `01_scatter_pred_vs_exp.png` | Scatter ΔG_pred vs ΔG_exp + retta y=x + fit lineare |
| 02 | `02_scatter_by_format.png` | Scatter stratificato per formato (Fab/scFv/VHH) |
| 03 | `03_residuals_hist.png` | Istogramma dei residui |
| 04 | `04_residuals_by_class.png` | Boxplot residui per classe di affinità (alta/media/bassa) |
| 05 | `05_residuals_vs_exp.png` | Residui vs ΔG_exp (check omoscedasticità) |
| 06 | `06_bland_altman.png` | Bland–Altman plot (bias ± 1.96σ) |
| 07 | `07_qq_residuals.png` | Q–Q plot normale sui residui |
| 08 | `08_kd_distribution.png` | Distribuzione log₁₀(Kd) |
| 09 | `09_kd_vs_resolution.png` | Kd vs risoluzione cristallografica |
| 10 | `10_metrics_by_format.png` | Bar chart RMSE/MAE/│r│ per formato |
| 11 | `11_metrics_by_method.png` | Bar chart RMSE/MAE/│r│ per tecnica |
| 12 | `12_decomposition_stack.png` | Stacked bar componenti ΔG PBEE (elettrostatico, apolare, entropico) |
| 13 | `13_ranking_accuracy.png` | Rank predetto vs rank sperimentale |
| 14 | `14_error_heatmap.png` | Heatmap RMSE per formato × tecnica |
| 15 | `15_source_coverage.png` | Pie chart contributi per fonte |
| 16 | `16_roc_highaffinity.png` | ROC per classificazione "alta affinità" (Kd<10 nM) |
| 17 | `17_calibration_curve.png` | Curva di calibrazione per bin di ΔG_exp |
| 18 | `18_venn_sources.png` | Bar chart contributi top-3 fonti |
| 19 | `19_timeline_dataset.png` | Crescita cumulativa del dataset |
| 20 | `20_summary_panel.png` | Pannello riassuntivo 2×2 |

Più: `metrics.json`, `metrics_by_format.csv`, `metrics_by_method.csv`, `metrics_by_source.csv`

## Modalità simulata vs reale

La **modalità simulata** genera dati coerenti con la letteratura MMPBSA:
- Kd distribuite su 5 decadi (0.1 nM – 10 µM)
- Bias sistematico ~ −0.4 kcal/mol (tipico di MMPBSA)
- Rumore gaussiano σ ~ 1.2 kcal/mol
- Decomposizione elettrostatica/apolare/entropica coerente
- Seed fissi → risultati riproducibili

La **modalità online** usa le API vere con cache. Le prime chiamate possono essere lente (1–2 minuti per 50 complessi), le successive sono istantanee grazie alla cache in `data/cache/`.

## Estensione a dati reali

Vedi `docs/pipeline.md` per istruzioni dettagliate su:

1. Scaricare SAbDab summary TSV
2. Installare APBS + PDB2PQR per i calcoli PBEE reali
3. Implementare le chiamate dirette ad APBS in `scripts/04_compute_pbee.py`
4. Integrare ANDD (quando il dataset sarà pubblicamente scaricabile)

## Licenza e citazioni

Uso accademico. Se usi il prototipo o parti di esso nella tesi, cita:

- **RCSB PDB**: Berman et al., Nucleic Acids Res. 28:235 (2000)
- **SAbDab**: Dunbar et al., Nucleic Acids Res. 42:D1140 (2014)
- **SAAINT-DB**: Huang et al., Acta Pharm Sin (2025)
- **ANDD**: Wu et al., Scientific Data (2026)
- **APBS**: Jurrus et al., Protein Sci. 27:112 (2018)
- **BindingDB**: Gilson et al., Nucleic Acids Res. 44:D1045 (2016)
