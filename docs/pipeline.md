# Documentazione tecnica della pipeline

Questo documento descrive in dettaglio il flusso di ciascuno step e come sostituire le parti simulate con dati reali.

## Architettura generale

```
                  ┌──────────────────┐
                  │ scripts/sources  │  ← API esterne con cache + rate-limit
                  │  • RCSB Search   │
                  │  • RCSB GraphQL  │
                  │  • PubMed        │
                  │  • BindingDB     │
                  │  • SAbDab TSV    │
                  └────────┬─────────┘
                           │
 ┌─────────────────────────┴──────────────────────────────────────┐
 │                                                                │
 │  01 build ─→ 02 curate ─→ 03 normalize ─→ 04 PBEE ─→ 05 analyze│
 │                                                                │
 └─────────────────────────┬──────────────────────────────────────┘
                           │
                     ┌─────┴─────┐
                     │ Flask app │  ← dashboard su http://127.0.0.1:5000
                     └───────────┘
```

Ogni step legge/scrive CSV in `data/` in modo che i passi siano ripetibili e ispezionabili.

## Step 1 — `01_build_dataset.py`

Tre modalità di esecuzione:

**`--mode online`** (con API reali)
1. Chiama RCSB Search API (`POST /rcsbsearch/v2/query`) per trovare complessi Ab-Ag con risoluzione ≤ 3 Å
2. Per ogni hit, chiama RCSB GraphQL (`POST /graphql`) per estrarre:
   - titolo, risoluzione, metodo sperimentale
   - descrizione delle entità polimeriche (per riconoscere VH/VL/antigene)
   - organismo sorgente
   - PubMed ID della citazione associata
3. Per ogni PubMed ID, scarica l'abstract via NCBI E-utilities (`/entrez/eutils/efetch.fcgi`)
4. Applica regex a ogni abstract per estrarre valori di Kd (pattern: "Kd = X nM", "KD of Y µM", "dissociation constant of Z pM", ecc.)
5. Se non trova Kd nell'abstract, interroga BindingDB
6. Salva il CSV con colonne: `pdb, format, antigen, kd_nM, method, source, resolution, temperature_K, ph, species, pubmed_id`

**`--mode sabdab`**
Legge un file TSV SAbDab preventivamente scaricato da `https://opig.stats.ox.ac.uk/webapps/newsabdab/sabdab/summary/all` e filtra solo le righe con affinità numerica parsabile.

**`--mode simulated`**
Genera 48 complessi fittizi con seed fisso. Serve per test offline e per garantire riproducibilità del prototipo.

### Come identifica formato anticorpo

La funzione `guess_format_and_antigen()` analizza le descrizioni delle entità polimeriche:
- Se trova "heavy chain" + "light chain" → **Fab**
- Se trova solo "heavy" (nessuna light/kappa/lambda) → **VHH** (nanobody)
- Se la sequenza contiene il linker `GGGGS` ripetuto → **scFv**

### Cache

Ogni chiamata remota viene memorizzata in `data/cache/<sha1>.json` con TTL di 7 giorni (30 giorni per il summary SAbDab). Per invalidare la cache: `rm -rf data/cache/`.

## Step 2 — `02_curate_structures.py`

Se biopython è disponibile e la rete risponde, lo script:
1. Scarica il file `.pdb` da `https://files.rcsb.org/download/{ID}.pdb`
2. Parsa con `Bio.PDB.PDBParser`
3. Conta residui per catena (proxy per residui Ab e Ag)
4. Elenca gli eterogeni presenti

In caso contrario (opzione `--no-download` o assenza di biopython/rete), genera valori simulati coerenti.

I campi aggiunti al record:
- `n_residues_ab`, `n_residues_ag`, `interface_area_A2`
- `missing_loops_modeled`, `heteroatoms_removed`, `clashes_fixed`, `hydrogens_added`
- `curation_source` (`biopython` o `simulated`)

## Step 3 — `03_normalize_affinity.py`

Converte Kd → ΔG usando `ΔG = RT·ln(Kd/1M)` a `T = 298.15 K`.

Nota: i dati sperimentali possono essere misurati a 20°C (SPR) o 37°C (condizioni fisiologiche). La normalizzazione assume ΔS costante (approssimazione comune quando ΔH non è noto). Per un'analisi più rigorosa si potrebbero includere le ΔH sperimentali da ITC.

Il pKd (`−log₁₀(Kd/1M)`) viene calcolato per facilitare classificazione e grafici.

## Step 4 — `04_compute_pbee.py`

**Modalità `simulated`**: genera ΔG predetti con un modello coerente con i risultati MMPBSA di letteratura:

```
ΔG_pred = ΔG_electrostatic + ΔG_apolar - T·ΔS + bias + noise

dove:
  ΔG_electrostatic = 0.55 · ΔG_exp + N(0, 0.8)
  ΔG_apolar        = 0.45 · ΔG_exp + N(0, 0.6)
  T·ΔS             ~ N(1.0, 0.5)
  bias             = -0.4 kcal/mol
  noise            ~ N(0, 0.8)
```

Questi numeri sono scelti per riprodurre approssimativamente l'accordo osservato in studi reali di MMPBSA su sistemi anticorpo-antigene (Pearson ~ 0.6–0.8, RMSE ~ 1.5–2.5 kcal/mol).

**Modalità `apbs`**: cerca il binario `apbs` nel PATH (o usa `--apbs-bin`). Se trovato, fa un test con `apbs --version`; se passa, esegue il calcolo tramite un ciclo termodinamico a 3 fasi:

```
ΔG_bind = G_solv(complex) − G_solv(Ab) − G_solv(Ag)
```

La versione attuale delega ancora al modello simulato (con seed deterministico basato sul PDB id) ma lo marca come `pbee_engine = "APBS (stub)"`. L'implementazione completa richiede:

1. Generare `.pqr` di complesso, Ab isolato, Ag isolato con `pdb2pqr`
2. Scrivere un `.in` APBS per ciascuno (dielettrici, forza ionica, griglia)
3. Chiamare `apbs file.in` e fare il parsing del log per estrarre `Total electrostatic energy`
4. Sommare al termine apolare SASA-dipendente
5. Eseguire il ciclo termodinamico

## Step 5 — `05_analyze_results.py`

Calcola metriche globali (RMSE, MAE, Pearson r, Spearman ρ, Kendall τ, bias medio e deviazione) e metriche stratificate per formato / metodo / fonte / classe di affinità.

Poi genera i 20 grafici documentati nel README principale. Tutti usano matplotlib (backend `Agg`, headless-safe) e salvano in `results/` come PNG 150 DPI.

## Installazione di APBS (opzionale, per calcoli reali)

**Ubuntu/Debian:**
```bash
sudo apt install apbs pdb2pqr
```

**macOS (Homebrew):**
```bash
brew install apbs
pip install pdb2pqr
```

**Windows / generale:**
Scarica da <https://github.com/Electrostatics/apbs/releases>

Poi verifica:
```bash
apbs --version
pdb2pqr --help
```

## Integrazione futura con ANDD

Il dataset ANDD (Wu et al. 2026) è il più grande attualmente disponibile (9.557 valori di Kd su 24.941 strutture). Al momento della stesura non ha un'API REST pubblica; quando il repository ANDD sarà disponibile (probabilmente come release Zenodo + script Python), si può aggiungere un parser in `scripts/sources.py` sullo stesso modello di `load_sabdab_summary()`.

## Troubleshooting

**"No module named 'flask'"**: il virtualenv non è attivo. Fai `source .venv/bin/activate` (o `.venv\Scripts\activate` su Windows).

**"Dataset non disponibile" nella dashboard**: esegui la pipeline prima (`./run.sh` o i 5 script in sequenza).

**Grafici mancanti nella galleria**: esegui `python scripts/05_analyze_results.py`. Richiede matplotlib (incluso nei requirements).

**API RCSB non risponde**: verifica la connessione internet. La pipeline cade sul fallback simulato se si passa `--fallback-simulated`.

**Cache corrotta**: svuota `data/cache/` e rilancia.
