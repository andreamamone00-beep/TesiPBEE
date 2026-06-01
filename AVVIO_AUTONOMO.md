# Avvio Autonomo Applicazione Ab/Ag PBEE

## Comandi per avvio manuale (Windows)

### Prerequisiti
- Python 3.9+ installato e nel PATH
- Git (opzionale, per clonare il repository)

### Avvio rapido completo

```powershell
# Naviga nella directory del progetto
cd C:\dev\ab_ag_pbee

# Attiva l'ambiente virtuale
.venv\Scripts\activate.bat

# Esegui la pipeline completa in modalità simulata
python scripts\01_build_dataset.py --mode simulated --n 48
python scripts\02_curate_structures.py --no-download
python scripts\03_normalize_affinity.py
python scripts\04_compute_pbee.py
python scripts\05_analyze_results.py

# Avvia la dashboard
python dashboard\app.py
```

### Avvio rapido con script batch

```powershell
# Modalità simulata (default)
.\run.bat

# Modalità online (usa API reali)
.\run.bat online
```

### Avvio solo dashboard (se dataset già esiste)

```powershell
cd C:\dev\ab_ag_pbee
.venv\Scripts\activate.bat
python dashboard\app.py
```

### Modalità disponibili

#### Modalità Simulata (offline)
- **Vantaggi**: Veloce, non richiede internet, dati riproducibili
- **Uso**: Sviluppo, test, dimostrazioni
- **Comando**: `python scripts\01_build_dataset.py --mode simulated --n 48`

#### Modalità Online (API reali)
- **Vantaggi**: Dati reali da RCSB PDB, PubMed, BindingDB, SAbDab
- **Svantaggi**: Richiede internet, più lento la prima volta
- **Uso**: Produzione, analisi su dati reali
- **Comando**: `python scripts\01_build_dataset.py --mode online --n 50 --fallback-simulated`

### File generati

```
data/
├── dataset_raw.csv          # Step 1: dataset grezzo
├── dataset_curated.csv      # Step 2: dopo cura strutturale
├── dataset_normalized.csv   # Step 3: dopo normalizzazione Kd→ΔG
└── dataset.csv              # Step 4: dataset finale con PBEE

results/
├── metrics.json             # Metriche complete
├── *.csv                    # Metriche per formato/tecnica/fonte
└── *.png                    # 20 grafici di analisi
```

### Accesso dashboard

- **URL**: http://127.0.0.1:5000
- **Pagine**:
  - `/` - Dashboard principale con metriche live
  - `/gallery` - Galleria dei 20 grafici
  - `/sources` - Stato connettività API

### Troubleshooting

#### Python non trovato
```powershell
# Verifica installazione
python --version
py --version

# Se non trovato, installa da:
# https://www.python.org/downloads/
```

#### Ambiente virtuale rotto
```powershell
# Ricrea ambiente virtuale
rmdir /s /q .venv
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

#### Dipendenze mancanti
```powershell
# Reinstalla tutte le dipendenze
pip install --upgrade pip
pip install -r requirements.txt
```

#### Porta 5000 già in uso
```powershell
# Trova processo sulla porta 5000
netstat -ano | findstr :5000

# Termina il processo (sostituisci PID)
taskkill /F /PID <PID>
```

### Comandi utili

```powershell
# Verifica stato ambiente virtuale
.venv\Scripts\python.exe --version

# Lista pacchetti installati
.venv\Scripts\pip.exe list

# Test singolo step della pipeline
.venv\Scripts\python.exe scripts\01_build_dataset.py --mode simulated --n 5

# Pulisci cache API
rmdir /s /q data\cache
```
