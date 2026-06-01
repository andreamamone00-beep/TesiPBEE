# Installazione e Avvio su Ubuntu - Ab/Ag PBEE Dataset & Benchmark

## Requisiti di Sistema

- Ubuntu 20.04+ (testato su 20.04, 22.04, 24.04)
- Python 3.9+ (consigliato 3.11)
- 2GB+ RAM
- 1GB+ spazio su disco
- Connessione internet (per modalità online)

## Installazione Completa

### 1. Aggiornamento sistema

```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Installazione Python e strumenti di sviluppo

```bash
# Installa Python 3.11+ e strumenti essenziali
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip python3.11-distutils

# Installa dipendenze di sistema per i pacchetti Python
sudo apt install -y build-essential python3-dev libffi-dev libssl-dev

# Verifica installazione
python3.11 --version
```

### 3. Installazione Git (se non presente)

```bash
sudo apt install -y git
```

### 4. Clone del repository

```bash
# Se hai il repository su GitHub/GitLab
git clone <URL_REPOSITORY>
cd ab_ag_pbee

# Oppure se hai i file localmente, copiali nella directory di lavoro
mkdir -p ~/ab_ag_pbee
# Copia i file nella directory ~/ab_ag_pbee
cd ~/ab_ag_pbee
```

### 5. Creazione ambiente virtuale

```bash
# Crea ambiente virtuale con Python 3.11
python3.11 -m venv .venv

# Attiva l'ambiente virtuale
source .venv/bin/activate

# Verifica di essere nell'ambiente virtuale
which python  # dovrebbe mostrare ~/ab_ag_pbee/.venv/bin/python
```

### 6. Installazione dipendenze Python

```bash
# Aggiorna pip
pip install --upgrade pip

# Installa le dipendenze del progetto
pip install -r requirements.txt

# Verifica installazione
pip list
```

### 7. Test dell'installazione

```bash
# Test rapido con dataset simulato piccolo
python scripts/01_build_dataset.py --mode simulated --n 5
python scripts/02_curate_structures.py --no-download
python scripts/03_normalize_affinity.py
python scripts/04_compute_pbee.py
python scripts/05_analyze_results.py

# Se tutto funziona, procedi con il dataset completo
```

## Avvio dell'Applicazione

### Script di avvio per Ubuntu

Crea lo script di avvio `run.sh`:

```bash
cat > run.sh << 'EOF'
#!/bin/bash
set -e

echo "===================================="
echo "  Ab/ScFv-Ag + PBEE benchmark"
echo "===================================="

# 1. Virtualenv
if [ ! -d ".venv" ]; then
  echo "[setup] Creazione virtualenv..."
  python3.11 -m venv .venv
fi
source .venv/bin/activate

# 2. Dipendenze
echo "[setup] Installazione dipendenze..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# 3. Pipeline (parametro opzionale: online)
MODE=${1:-simulated}

echo
echo "[pipeline] Esecuzione pipeline (modalità: $MODE)..."
if [ "$MODE" = "online" ]; then
  python scripts/01_build_dataset.py --mode online --n 50 --fallback-simulated
else
  python scripts/01_build_dataset.py --mode simulated --n 48
fi
python scripts/02_curate_structures.py --no-download
python scripts/03_normalize_affinity.py
python scripts/04_compute_pbee.py
python scripts/05_analyze_results.py

# 4. Dashboard
echo
echo "===================================="
echo "  Pipeline completata. Avvio dashboard."
echo "  URL: http://127.0.0.1:5000"
echo "  Premere Ctrl+C per fermare."
echo "===================================="
echo
python dashboard/app.py
EOF

# Rendi eseguibile
chmod +x run.sh
```

### Avvio rapido

```bash
# Modalità simulata (default)
./run.sh

# Modalità online (usa API reali)
./run.sh online
```

### Avvio manuale

```bash
# Attiva ambiente virtuale
source .venv/bin/activate

# Esegui pipeline completa
python scripts/01_build_dataset.py --mode simulated --n 48
python scripts/02_curate_structures.py --no-download
python scripts/03_normalize_affinity.py
python scripts/04_compute_pbee.py
python scripts/05_analyze_results.py

# Avvia dashboard
python dashboard/app.py
```

## Configurazione Firewall

Se usi un server remoto, apri la porta 5000:

```bash
# Per UFW (Ubuntu default)
sudo ufw allow 5000/tcp

# Per iptables
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT
```

## Accesso Remoto (opzionale)

Per accedere alla dashboard da altri computer:

```bash
# Avvia dashboard su tutte le interfacce
python dashboard/app.py --host 0.0.0.0 --port 5000

# Oppure modifica dashboard/app.py e aggiungi:
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=False)
```

## Installazione APBS (opzionale)

Per calcoli PBEE reali:

```bash
# Installa dipendenze APBS
sudo apt install -y gcc gfortran libopenmpi-dev

# Scarica e compila APBS
cd /tmp
wget https://github.com/Electrostatics/apbs/releases/download/v3.5.1/apbs-3.5.1.tar.gz
tar xzf apbs-3.5.1.tar.gz
cd apbs-3.5.1
mkdir build && cd build
cmake ..
make -j$(nproc)
sudo make install

# Installa PDB2PQR
pip install pdb2pqr

# Verifica installazione
apbs --version
pdb2pqr --version
```

## Servizio Systemd (avvio automatico)

Crea un servizio systemd per avvio automatico:

```bash
sudo tee /etc/systemd/system/abag-pbee.service > /dev/null << EOF
[Unit]
Description=Ab/Ag PBEE Dashboard
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/ab_ag_pbee
Environment=PATH=$HOME/ab_ag_pbee/.venv/bin
ExecStart=$HOME/ab_ag_pbee/.venv/bin/python dashboard/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Abilita e avvia il servizio
sudo systemctl daemon-reload
sudo systemctl enable abag-pbee.service
sudo systemctl start abag-pbee.service

# Controlla stato
sudo systemctl status abag-pbee.service
```

## Troubleshooting Ubuntu

### Problemi comuni

#### Python 3.11 non disponibile
```bash
# Su Ubuntu 20.04/22.04, aggiungi il repository PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

#### Permessi negati
```bash
# Correggi permessi della directory
sudo chown -R $USER:$USER ~/ab_ag_pbee
chmod +x run.sh
```

#### Porta 5000 già in uso
```bash
# Trova processo sulla porta 5000
sudo lsof -i :5000

# Termina il processo
sudo kill -9 <PID>
```

#### Dipendenze mancanti
```bash
# Reinstalla tutto da capo
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --force-reinstall
```

#### Problemi con matplotlib (headless)
```bash
# Installa backend per server senza GUI
sudo apt install -y xvfb
export DISPLAY=:99
Xvfb :99 -screen 0 1024x768x24 &
```

### Log e Debug

```bash
# Log della dashboard
tail -f ~/.local/share/abag-pbee.log

# Log del servizio systemd
sudo journalctl -u abag-pbee.service -f

# Test ambiente virtuale
source .venv/bin/activate
python -c "import flask, pandas, numpy; print('All imports OK')"
```

## Aggiornamento

```bash
# Aggiorna il codice
git pull origin main

# Aggiorna le dipendenze
source .venv/bin/activate
pip install --upgrade -r requirements.txt

# Riavvia il servizio (se usi systemd)
sudo systemctl restart abag-pbee.service
```

## Backup

```bash
# Script di backup semplice
#!/bin/bash
BACKUP_DIR="$HOME/backups/abag-pbee-$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup dati e risultati
cp -r data results "$BACKUP_DIR/"

# Backup configurazione
cp requirements.txt run.sh "$BACKUP_DIR/"

echo "Backup completato in: $BACKUP_DIR"
```

## Performance e Ottimizzazione

```bash
# Limita l'uso della CPU (utile su hardware limitato)
cpulimit -l 50 -p $(pgrep -f "dashboard/app.py") &

# Monitoraggio risorse
htop
iotop
```

## Sicurezza

```bash
# Crea utente dedicato per il servizio
sudo useradd -r -s /bin/false abagpbee
sudo chown -R abagpbee:abagpbee /opt/abag-pbee

# Usa HTTPS con nginx come reverse proxy
sudo apt install -y nginx
# Configura nginx per proxy verso http://127.0.0.1:5000
```
