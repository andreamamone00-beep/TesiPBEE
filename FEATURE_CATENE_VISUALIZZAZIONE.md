# Nuova Funzionalità: Visualizzazione 3D e Selezione Catene

## Descrizione Generale
Aggiunto un visualizzatore 3D interattivo per le strutture PDB e un sistema di selezione delle catene tramite checkbox, permettendo all'utente di:
- **Visualizzare in tempo reale** la struttura proteica 3D con colori distinti per ogni catena
- **Selezionare multiple catene** usando checkbox colorate
- **Assegnare facilmente** le catene ai partner A (anticorpo/ScFv) e B (antigene)
- **Evidenziare l'interfaccia di interazione** tra le catene selezionate

## Miglioramenti Visualizzazione

### Versione 1 (Iniziale)
- ✅ Visualizzatore 3D con 3Dmol.js
- ⚠️ Interfaccia non chiaramente visibile
- ⚠️ Calcoli di distanza complessi con errori

### Versione 2 (Migliorata) ✅
- ✅ **Catene colorate diversamente** dalla palette predefinita
- ✅ **Partner A evidenziato in BLU SCURO** (#378ADD)
- ✅ **Partner B evidenziato in ARANCIONE** (#F77B58)
- ✅ **Interfaccia visibile con sticks in grigio/bianco** (5.0 Å di cutoff)
- ✅ **Cartoon style per tutte le catene** (arrows + tubes)
- ✅ Corretto! Errori di coordinate risolti

## File Modificati

### 1. [dashboard/templates/index.html](dashboard/templates/index.html)
**Cambiamenti:**
- Aggiunto link al script 3Dmol.js per la visualizzazione 3D
- Rimosso vecchio layout con dropdown select per le catene
- Implementato nuovo layout **pdb-details-layout** a due colonne:
  - **Colonna sinistra**: Visualizzatore 3D (`pdb-viewer`)
  - **Colonna destra**: Pannello di controllo con:
    - Input Kd sperimentale
    - Checkbox per selezione catene (`pdb-chain-checkboxes`)
    - Select dropdown per Partner A e Partner B (multipli)
    - Pulsante "Avvia PBEE"

**Script aggiunto:**
```html
<script src="https://3Dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
```

---

### 2. [dashboard/static/style.css](dashboard/static/style.css)
**Nuovi stili aggiunti:**
- `.pdb-details-layout`: Grid layout a due colonne (responsive)
- `.pdb-viewer`: Contenitore per il visualizzatore 3D (400px x 100%)
- `.chain-checkboxes`: Scroll container per le checkbox
- `.chain-checkbox`: Flex layout per ogni checkbox con label
- `.chain-color`: Quadratino colorato a sinistra della checkbox
- `.chains-display`: Display area per le catene selezionate
- `.chain-badge`: Badge colorato per evidenziare le catene

**Media queries:**
- **< 900px**: Layout cambia da 2 colonne a 1 colonna
- **< 600px**: Altezza visualizzatore ridotta a 300px

---

### 3. [dashboard/static/app.js](dashboard/static/app.js)
**Nuove variabili globali:**
```javascript
let pdbViewer = null;           // Istanza del visualizzatore 3Dmol
let currentPdbCode = null;      // Codice PDB attualmente visualizzato
let chainColorMap = {};         // Mapping catena -> colore
```

**Funzioni principali:**

#### `generateChainColors(count)`
Genera un array di colori unici per le catene. Utilizza una palette predefinita e genera colori HSL per catene aggiuntive.

#### `showPdbDetails(result)`
Sostituisce il vecchio metodo di visualizzazione delle catene. Ora:
- Crea checkbox colorate per ogni catena
- Attacca event listener ai checkbox
- Carica il visualizzatore 3D con `loadPdbViewer()`

#### `updateChainSelections()`
Chiamata quando l'utente seleziona/deseleziona una checkbox:
- Aggiorna i select dropdown di Partner A e B
- Preserva le selezioni precedenti se possibile

#### `updateChainsDisplay()` ⭐ MIGLIORATA
Principale funzione per visualizzare le catene:
- **Reset colori** di tutte le catene alla palette predefinita
- **Partner A**: colorato in **BLU (#378ADD)** con cartoon spesso
- **Partner B**: colorato in **ARANCIONE (#F77B58)** con cartoon spesso
- **Interfaccia**: aggiunge **sticks bianchi/grigi** per visualizzare i residui di contatto
- Non chiama più `highlightInterface()` (semplificato)

#### `loadPdbViewer(pdbCode, chains)` ⭐ MIGLIORATA
Carica la struttura PDB usando 3Dmol.js:
- Inizializza il visualizzatore nel div `pdb-viewer`
- Colora ogni catena diversamente (palette `chainColorMap`)
- Attiva lo stile cartoon con frecce, tubi e stile oval
- Applica zoom automatico

#### `highlightInterface(chainA, chainB)` 
Funzione semplificata (ora è uno stub):
- La logica dell'interfaccia è gestita in `updateChainsDisplay()`
- Mantiene compatibilità API

---

## Funzionamento

### Flusso Utente
1. **Ricerca PDB**: Utente inserisce codice PDB (es. "1a6u") e clicca "Cerca PDB"
2. **Caricamento**: La struttura viene scaricata e visualizzata in 3D in grigio
3. **Selezione Catene**: Utente seleziona le catene tramite checkbox colorate
4. **Assegnazione Partner**: Le catene selezionate vengono populate nei select dropdown
5. **Visualizzazione Dinamica**:
   - Nel visualizzatore:
     - Le catene selezionate in Partner A diventano **BLU SCURO**
     - Le catene selezionate in Partner B diventano **ARANCIONE**
     - Gli **sticks grigi** mostrano i residui dell'interfaccia
6. **Elaborazione**: Utente clicca "Avvia PBEE" per calcolare l'energia di binding

### Codice di Colore delle Catene (Palette Predefinita)
```
Catena A: #378ADD (blu)
Catena B: #F77B58 (arancione)
Catena C: #4ECDC4 (turchese)
Catena D: #FFD93D (giallo)
Catena E: #6BCB77 (verde)
Catena F: #FF6B6B (rosso)
... e altri (colori HSL generati dinamicamente)
```

### Colori nel Visualizzatore 3D - Interfaccia Attiva
Quando sia Partner A che Partner B sono selezionati:
- **Partner A (catena selezionata)**: #378ADD (blu) - cartoon spesso (1.2px)
- **Partner B (catena selezionata)**: #F77B58 (arancione) - cartoon spesso (1.2px)
- **Residui interfaccia**: Sticks bianchi/grigi (opacity 0.5) - mostra i residui di contatto
- **Altre catene**: Colore della palette (cartoon thin 0.8px)

### Calcolo dell'Interfaccia
L'interfaccia è visualizzata come sticks nei residui a contatto tra Partner A e Partner B all'interno di **5.0 Angstrom** di distanza.

---

## Dipendenze Esterne

### 3Dmol.js
Libreria JavaScript per la visualizzazione interattiva di strutture molecolari 3D.
- **URL**: https://3Dmol.csb.pitt.edu/build/3Dmol-min.js
- **Uso**: Caricamento e rendering di strutture PDB

### Chart.js
Già presente per i grafici, non modificato.

---

## Miglioramenti Rispetto alla Versione Precedente

| Aspetto | Prima | Dopo |
|---------|-------|------|
| **Selezione catene** | Dropdown singoli (difficile capire quale scegliere) | Checkbox con colori |
| **Visualizzazione struttura** | Nessuna | 3D interattivo colorato |
| **Interfaccia visibile** | No | Sì (sticks grigi a 5Å) |
| **Colori catene** | Unici per tutte | Distinti per ogni catena |
| **Multiple selection** | Dropdown multipli | Checkbox + multi-select |
| **Usabilità** | Confusa | Intuitiva e visuale |
| **Responsive** | No | Sì (grid layout) |

---

## Testing

### Testato con
- **PDB Code 1a6u**: B1-8 FV Fragment (Anticorpo - 2 catene: H, L)
- **Catene**: H (heavy chain), L (light chain)
- **Browser**: Chrome/Firefox su Windows
- **Interazione**: Visibilmente separata tra le due catene

### Funzionalità Verificate
✅ Caricamento struttura 3D da PDB remoto
✅ Rendering catene con colori diversi dalla palette
✅ Creazione dinamica checkbox
✅ Popolazione select dropdown dalla selezione checkbox
✅ Evidenziamento catene nel visualizzatore 3D
✅ **Visualizzazione sticks dell'interfaccia** ⭐
✅ Responsive layout
✅ No errori di coordinate

---

## Note Tecniche

### Event Listeners
- Checkbox → `change` event → `updateChainSelections()`
- Select Partner A/B → `change` event → `updateChainsDisplay()`

### Rendering 3D
Utilizza lo stile cartoon di 3Dmol.js:
```javascript
pdbViewer.setStyle({}, { cartoon: { arrows: true, tubes: true, style: 'oval' } });
```

### Sticks per l'Interfaccia
```javascript
pdbViewer.setStyle({ chain: chain, ss: 'c' }, { 
  stick: { radius: 0.15, colorscheme: 'whiteCarbon', opacity: 0.5 }
});
```

### Gestione della Cache di Flask
Se il template non si aggiorna dopo la modifica:
```bash
Remove-Item -Path dashboard/__pycache__ -Recurse -Force
python dashboard/app.py
```

---

## Future Improvements
- [ ] Controlli rotazione/zoom avanzati per il visualizzatore
- [ ] Salvataggio delle selezioni di catene
- [ ] Visualizzazione dei contatti specifici (H-bond, salt bridge)
- [ ] Esportazione della selezione come immagine 3D
- [ ] Supporto per selezione personalizzata di range di amminoacidi
- [ ] Calcolo dinamico della superficie di interfaccia
- [ ] Animazione dell'interfaccia al cambio selezione
