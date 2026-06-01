# Istruzioni Complete - Ab/Ag PBEE Dataset & Benchmark

## 📋 Indice
1. [Requisiti di Sistema](#requisiti-di-sistema)
2. [Installazione](#installazione)
3. [Avvio dell'Applicazione](#avvio-dellapplicazione)
4. [Modalità di Funzionamento](#modalità-di-funzionamento)
5. [Uso della Dashboard](#uso-della-dashboard)
6. [Pipeline Dettagliata](#pipeline-dettagliata)
7. [File e Output](#file-e-output)
8. [Troubleshooting](#troubleshooting)
9. [Manutenzione e Aggiornamenti](#manutenzione-e-aggiornamenti)

---

## 🔧 Requisiti di Sistema

### Windows
- **Windows 10/11**
- **Python 3.9+** (consigliato 3.11)
- **8GB+ RAM** (per dataset grandi)
- **2GB+ spazio su disco**
- **Connessione internet** (per modalità online)

### Ubuntu/Linux
- **Ubuntu 20.04+** o equivalente
- **Python 3.9+**
- **Build tools**: `build-essential`, `python3-dev`
- **Connessione internet**

---

## 📦 Installazione

### Windows

#### Metodo 1: Automatico (consigliato)
```powershell
# Clona o scarica il progetto
cd C:\dev\
git clone <URL_REPOSITORY> ab_ag_pbee
cd ab_ag_pbee

# Esegui lo script di avvio
.\run.bat
```

#### Metodo 2: Manuale
```powershell
# 1. Installa Python da https://www.python.org/downloads/
# 2. Verifica installazione
python --version

# 3. Crea ambiente virtuale
python -m venv .venv

# 4. Attiva ambiente
.venv\Scripts\activate.bat

# 5. Installa dipendenze
pip install -r requirements.txt
```

### Ubuntu

#### Metodo 1: Script automatico
```bash
# Scarica il progetto
git clone <URL_REPOSITORY> ab_ag_pbee
cd ab_ag_pbee

# Rendi eseguibile e avvia
chmod +x run.sh
./run.sh
```

#### Metodo 2: Manuale
```bash
# 1. Aggiorna sistema
sudo apt update && sudo apt upgrade -y

# 2. Installa Python e strumenti
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip build-essential

# 3. Crea ambiente virtuale
python3.11 -m venv .venv

# 4. Attiva ambiente
source .venv/bin/activate

# 5. Installa dipendenze
pip install -r requirements.txt
```

---

## 🚀 Avvio dell'Applicazione

### Windows

#### Avvio Rapido
```powershell
# Modalità simulata (offline, veloce)
.\run.bat

# Modalità online (API reali)
.\run.bat online
```

#### Avvio Manuale
```powershell
# Attiva ambiente
.venv\Scripts\activate.bat

# Esegui pipeline completa
python scripts\01_build_dataset.py --mode simulated --n 48
python scripts\02_curate_structures.py --no-download
python scripts\03_normalize_affinity.py
python scripts\04_compute_pbee.py
python scripts\05_analyze_results.py

# Avvia dashboard
python dashboard\app.py
```

### Ubuntu

#### Avvio Rapido
```bash
# Modalità simulata
./run.sh

# Modalità online
./run.sh online
```

#### Avvio Manuale
```bash
# Attiva ambiente
source .venv/bin/activate

# Esegui pipeline
python scripts/01_build_dataset.py --mode simulated --n 48
python scripts/02_curate_structures.py --no-download
python scripts/03_normalize_affinity.py
python scripts/04_compute_pbee.py
python scripts/05_analyze_results.py

# Avvia dashboard
python dashboard/app.py
```

---

## 🎯 Modalità di Funzionamento

### 📊 Modalità Simulata (Default)
**Caratteristiche:**
- ✅ **Veloce**: 2-3 minuti totali
- ✅ **Offline**: Non richiede internet
- ✅ **Riproducibile**: Seed fisso, stessi risultati
- ✅ **Ideale per**: Sviluppo, test, dimostrazioni

**Dati generati:**
- 48 complessi anticorpo-antigene
- Kd distribuiti su 5 decadi (0.1 nM – 10 µM)
- Bias sistematico ~ -0.4 kcal/mol (realistico)
- Rumore gaussiano σ ~ 1.2 kcal/mol

### 🌐 Modalità Online
**Caratteristiche:**
- 🔄 **Dati reali**: Da RCSB PDB, PubMed, BindingDB, SAbDab
- 🕐 **Più lenta**: 5-15 minuti prima volta (cache dopo)
- 📡 **Richiede internet**
- 🎯 **Ideale per**: Produzione, ricerca, analisi reali

**API utilizzate:**
- **RCSB PDB**: Strutture 3D e metadati
- **PubMed**: Abstract e dati di affinità
- **BindingDB**: Database di affinità sperimentali
- **SAbDab**: Antibody Structure Database

---

## 🖥️ Uso della Dashboard

### Accesso
- **URL**: http://127.0.0.1:5000
- **Browser**: Chrome, Firefox, Safari, Edge

### Pagine della Dashboard

#### 1. Dashboard Principale (`/`)
**Metriche Live:**
- **N**: Numero di complessi
- **RMSE**: Root Mean Square Error (kcal/mol)
- **MAE**: Mean Absolute Error (kcal/mol)
- **Pearson (r)**: Correlazione lineare
- **Spearman (ρ)**: Correlazione per ranghi
- **Kendall (τ)**: Correlazione ordinale
- **Bias**: Errore sistematico medio

**Filtri Dinamici:**
- **Formato**: Fab, scFv, VHH
- **Tecnica**: SPR, ITC, BLI
- **Fonte**: SAbDab, SAAINT-DB, ANDD, Literature
- **Risoluzione massima**: 1.0-3.0 Å
- **Kd massimo**: 0.1-10000 nM

**Visualizzazioni:**
- **Scatter plot**: ΔG_pred vs ΔG_exp con retta y=x
- **Istogramma residui**: Distribuzione errori
- **Tabella filtrabile**: Tutti i dati con codice colore
  - 🟢 Verde: errore <1 kcal/mol
  - 🟠 Arancione: errore 1-2 kcal/mol
  - 🔴 Rosso: errore >2 kcal/mol

#### 2. Galleria Grafici (`/gallery`)
**20 grafici di ricerca automatici:**
1. Scatter predizione vs sperimentale
2. Scatter per formato anticorpale
3. Istogramma residui
4. Boxplot residui per classe
5. Residui vs valore sperimentale
6. Bland-Altman plot
7. Q-Q plot normale
8. Distribuzione Kd
9. Kd vs risoluzione
10. Metriche per formato
11. Metriche per tecnica
12. Decomposizione PBEE
13. Accuratezza ranking
14. Heatmap errori
15. Copertura fonti
16. ROC curve
17. Curva calibrazione
18. Contributi fonti
19. Timeline dataset
20. Pannello riassuntivo

#### 3. Stato Fonti (`/sources`)
**Monitoraggio API real-time:**
- 🟢 RCSB PDB: Strutture e metadati
- 🟢 PubMed: Letteratura scientifica
- 🟢 SAbDab: Database anticorpi
- 🟢 BindingDB: Dati affinità

**Funzionalità:**
- Test connettività immediato
- Dettagli errori e timeout
- Pulsante "Ricontrolla tutto"

---

## ⚙️ Pipeline Dettagliata

### Step 1: Costruzione Dataset (`01_build_dataset.py`)
```python
# Modalità simulata
python scripts/01_build_dataset.py --mode simulated --n 48

# Modalità online
python scripts/01_build_dataset.py --mode online --n 50 --fallback-simulated

# Modalità SAbDab (file locale)
python scripts/01_build_dataset.py --mode sabdab --sabdab-path /path/to/summary.tsv
```

**Output:** `data/dataset_raw.csv`

### Step 2: Cura Strutturale (`02_curate_structures.py`)
```python
# Download PDB reali
python scripts/02_curate_structures.py

# Skip download (usa file esistenti)
python scripts/02_curate_structures.py --no-download
```

**Output:** `data/dataset_curated.csv`

### Step 3: Normalizzazione Affinità (`03_normalize_affinity.py`)
```python
python scripts/03_normalize_affinity.py
```

**Converte:** Kd → ΔG a 298.15 K usando:
```
ΔG = RT * ln(Kd)
R = 1.987 cal/(mol·K)
T = 298.15 K
Kd in M (convertito da nM)
```

**Output:** `data/dataset_normalized.csv`

### Step 4: Calcolo PBEE (`04_compute_pbee.py`)
```python
# Modalità simulata (default)
python scripts/04_compute_pbee.py

# Modalità APBS reale (richiede APBS installato)
python scripts/04_compute_pbee.py --mode apbs
```

**Decomposizione PBEE:**
- **Elettrostatico**: Interazioni carica-carica
- **Apolare**: Effetti idrofobici
- **Entropico**: Perdita conformazionale

**Output:** `data/dataset.csv`

### Step 5: Analisi Risultati (`05_analyze_results.py`)
```python
python scripts/05_analyze_results.py
```

**Genera:**
- 20 grafici PNG in `results/`
- `metrics.json` con tutte le metriche
- File CSV per sotto-analisi

---

## 📁 File e Output

### Directory Structure
```
ab_ag_pbee/
├── data/
│   ├── dataset_raw.csv          # Step 1: dati grezzi
│   ├── dataset_curated.csv      # Step 2: dopo cura
│   ├── dataset_normalized.csv   # Step 3: dopo normalizzazione
│   ├── dataset.csv              # Step 4: finale con PBEE
│   └── cache/                   # Cache API (7 giorni TTL)
├── results/
│   ├── metrics.json             # Metriche complete
│   ├── 01_scatter_pred_vs_exp.png
│   ├── 02_scatter_by_format.png
│   └── ... (20 grafici totali)
├── dashboard/
│   ├── app.py                   # Server Flask
│   ├── templates/               # HTML templates
│   └── static/                  # CSS, JS
└── scripts/                     # Pipeline scripts
```

### Format Dataset CSV
```csv
pdb,format,antigen,kd_nM,method,source,resolution,temperature_K,ph,species,pubmed_id,dg_exp,dg_pred,pbee_elec,pbee_apolar,pbee_entropy
1e41,Fab,PD-1,157.447,BLI,SAbDab,2.8,310.15,7.0,mouse,12345678,-9.73,-8.42,-5.2,-3.1,2.1
```

---

## 🔧 Troubleshooting

### Problemi Comuni

#### ❌ "Python non trovato"
**Windows:**
```powershell
# Verifica installazione
python --version

# Se non trovato, reinstalla da https://www.python.org/downloads/
# Assicurati di spuntare "Add Python to PATH"
```

**Ubuntu:**
```bash
# Installa Python 3.11
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv
```

#### ❌ "Ambiente virtuale rotto"
```bash
# Windows
rmdir /s /q .venv
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt

# Ubuntu
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### ❌ "Porta 5000 già in uso"
```bash
# Windows
netstat -ano | findstr :5000
taskkill /F /PID <PID>

# Ubuntu
sudo lsof -i :5000
sudo kill -9 <PID>
```

#### ❌ "API non raggiungibili"
```python
# Test connettività
python -c "
import sys; sys.path.append('scripts')
from sources import check_connectivity
import json
status = check_connectivity()
print(json.dumps(status, indent=2))
"
```

#### ❌ "Dati online non funzionano"
**Soluzioni:**
1. **Controlla internet**
2. **Verifica firewall/proxy**
3. **Riprova più tardi** (API temporaneamente non disponibili)
4. **Usa fallback simulato**: `--fallback-simulated`

#### ❌ "Dashboard non si avvia"
```python
# Test diretto
python dashboard/app.py

# Controlla dipendenze
pip install flask pandas numpy matplotlib seaborn requests biopython
```

### Log e Debug

#### Abilita logging dettagliato
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Controlla cache API
```bash
# Svuota cache (se dati corrotti)
rm -rf data/cache/*
```

#### Verifica dataset
```python
import pandas as pd
df = pd.read_csv('data/dataset.csv')
print(df.head())
print(f"Totale record: {len(df)}")
print(f"Record con dati reali: {len(df[df['source'] != 'Literature'])}")
```

---

## 🔄 Manutenzione e Aggiornamenti

### Aggiornamento Codice
```bash
# Se usi Git
git pull origin main

# Reinstalla dipendenze
source .venv/bin/activate  # Ubuntu
# o
.venv\Scripts\activate.bat  # Windows
pip install -r requirements.txt
```

### Pulizia Cache
```bash
# Rimuovi cache API vecchie
find data/cache -name "*.json" -mtime +7 -delete

# Rimuovi tutti i risultati
rm -rf results/*
rm -f data/*.csv
```

### Backup Dati
```bash
# Script backup semplice
#!/bin/bash
BACKUP_DIR="$HOME/backups/abag-pbee-$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup dati e risultati
cp -r data results "$BACKUP_DIR/"

# Backup configurazione
cp requirements.txt run.sh run.bat "$BACKUP_DIR/"

echo "Backup completato in: $BACKUP_DIR"
```

### Monitoraggio Risorse
```bash
# Monitora utilizzo memoria/CPU
htop

# Monitora spazio disco
df -h

# Monitora dimensione cache
du -sh data/cache/
```

---

## 📞 Supporto e Contatti

### Documentazione
- **README.md**: Panoramica progetto
- **docs/pipeline.md**: Dettagli tecnici
- **AVVIO_AUTONOMO.md**: Comandi rapidi
- **INSTALLAZIONE_UBUNTU.md**: Guida Linux

### Risorse Esterne
- **RCSB PDB**: https://www.rcsb.org/
- **SAbDab**: https://opig.stats.ox.ac.uk/webapps/newsabdab/sabdab/
- **BindingDB**: https://www.bindingdb.org/
- **PubMed**: https://pubmed.ncbi.nlm.nih.gov/

### Troubleshooting Avanzato
Per problemi complessi:
1. Controlla i log nella console
2. Verifica la connettività delle API
3. Controlla la validità dei file CSV
4. Prova con un dataset più piccolo (`--n 5`)
5. Riavvia da ambiente virtuale pulito

---

## 🎯 Riepilogo Rapido

### Avvio Istantaneo
```bash
# Windows
.\run.bat

# Ubuntu  
./run.sh
```

### Accesso Dashboard
http://127.0.0.1:5000

### Modalità Disponibili
- **Simulata**: Veloce, offline, riproducibile
- **Online**: Dati reali, più lenta, richiede internet

### Output Principali
- **Dataset**: `data/dataset.csv`
- **Grafici**: `results/*.png` (20 grafici)
- **Metriche**: `results/metrics.json`
- **Dashboard**: http://127.0.0.1:5000

L'applicazione è ora pronta all'uso! 🚀
