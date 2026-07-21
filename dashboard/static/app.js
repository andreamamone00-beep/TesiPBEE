(function () {
  "use strict";

  const el = (id) => document.getElementById(id);
  const state = { format: "all", method: "all", source: "all", res_max: 3.5, kd_max: 10000, dataset: "dataset1", viewMode: "single" };
  let scatterChart = null;
  let residualsChart = null;
  let pdbViewer = null;
  let pdbStructure = null;
  let currentPdbCode = null;
  let chainColorMap = {};
  let pendingSelection = null;
  let pollInterval = null;

  const mg = {
    datasetStatus: "mg-dataset-status",
    summaryStatus: "mg-summary-status",
    summaryRows: "mg-summary-rows",
    cacheStatus: "mg-cache-status",
    message: "mg-message",
    historyList: "history-list",
    btnFetchSummary: "btn-fetch-summary",
    btnRunPipeline: "btn-run-pipeline",
    btnSaveVersion: "btn-save-version",
    btnSearchPdb: "btn-search-pdb",
    btnRunPbee: "btn-run-pbee",
    pdbInput: "f-pdb",
    pdbDetails: "pdb-details",
    pdbChainList: "pdb-chain-list",
    pdbChainCheckboxes: "pdb-chain-checkboxes",
    pdbChainsADisplay: "pdb-chains-a-display",
    pdbChainsBDisplay: "pdb-chains-b-display",
    pdbViewer: "pdb-viewer",
    pdbChainA: "f-chains-a",
    pdbChainB: "f-chains-b",
    pdbKdInput: "f-kd",
    pdbComputeResult: "pdb-compute-result",
    pdbSearchResult: "pdb-search-result",
    btnExportDataset: "btn-export-dataset",
  };

  const COLORS = {
    blue: "#378ADD",
    blueDark: "#185FA5",
    blueLight: "rgba(55, 138, 221, 0.55)",
    gray: "#888780",
  };

  async function boot() {
    let meta;
    try {
      meta = await fetch("/api/metadata?dataset=" + state.dataset).then((r) => r.json());
    } catch (e) {
      console.error(e);
      el("empty-state").classList.remove("hidden");
      return;
    }
    if (meta.empty) {
      el("empty-state").classList.remove("hidden");
      return;
    }
    el("content").classList.remove("hidden");

    populateSelect("f-format", meta.formats);
    populateSelect("f-method", meta.methods);
    populateSelect("f-source", meta.sources);

    bindEvents();
    await refresh();
    await refreshManageStatus();
  }

  function populateSelect(id, values) {
    const sel = el(id);
    for (const v of values) {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      sel.appendChild(opt);
    }
  }

  function bindEvents() {
    el("f-view-mode").addEventListener("change", (e) => {
      state.viewMode = e.target.value;
      toggleViewMode();
      refresh();
    });
    el("f-dataset").addEventListener("change", async (e) => {
      state.dataset = e.target.value;
      // Refresh metadata when dataset changes
      const meta = await fetch("/api/metadata?dataset=" + state.dataset).then((r) => r.json());
      populateSelect("f-format", meta.formats);
      populateSelect("f-method", meta.methods);
      populateSelect("f-source", meta.sources);
      refresh();
    });
    el("f-format").addEventListener("change", (e) => { state.format = e.target.value; refresh(); });
    el("f-method").addEventListener("change", (e) => { state.method = e.target.value; refresh(); });
    el("f-source").addEventListener("change", (e) => { state.source = e.target.value; refresh(); });
    el("f-res").addEventListener("input", (e) => {
      state.res_max = parseFloat(e.target.value);
      el("res-out").textContent = state.res_max.toFixed(1);
      refresh();
    });
    el("f-kd-max").addEventListener("input", (e) => {
      const v = parseFloat(e.target.value);
      state.kd_max = v;
      el("kd-out").textContent = v >= 10000 ? "tutti" : v.toLocaleString("it-IT");
      refresh();
    });
    el("btn-reset").addEventListener("click", () => {
      state.format = "all"; state.method = "all"; state.source = "all";
      state.res_max = 3.5; state.kd_max = 10000;
      el("f-format").value = "all";
      el("f-method").value = "all";
      el("f-source").value = "all";
      el("f-res").value = 3.5;
      el("f-kd-max").value = 10000;
      el("res-out").textContent = "3.5";
      el("kd-out").textContent = "tutti";
      refresh();
    });
    el("btn-export").addEventListener("click", () => {
      el("btn-export").href = "/api/export.csv?" + queryString();
    });
    el(mg.btnFetchSummary).addEventListener("click", () => { manageAction("/api/manage/fetch_summary"); });
    el(mg.btnRunPipeline).addEventListener("click", () => { manageAction("/api/manage/run_pipeline", true); });
    el(mg.btnSaveVersion).addEventListener("click", () => { manageAction("/api/manage/save_version", false, { note: "manual_save" }); });
    el(mg.btnSearchPdb).addEventListener("click", searchPdb);
    const runPbeeButton = el(mg.btnRunPbee);
    if (runPbeeButton) {
      runPbeeButton.addEventListener("click", runPbeeCompute);
    }
    
    const uploadInput = el("f-upload-file");
    if (uploadInput) {
      uploadInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        el("selected-file-name").textContent = file ? file.name : "Nessun file";
        if (file && !el("f-upload-id").value.trim()) {
          const nameWithoutExt = file.name.replace(/\.[^/.]+$/, "").toLowerCase();
          el("f-upload-id").value = nameWithoutExt.replace(/[^a-z0-9_-]/g, "");
        }
      });
    }
    
    const uploadBtn = el("btn-upload-pdb");
    if (uploadBtn) {
      uploadBtn.addEventListener("click", uploadPdb);
    }

    window.addEventListener("resize", () => {
      if (pdbViewer && typeof pdbViewer.fitParent === "function") {
        pdbViewer.fitParent();
      }
    });
  }

  async function postJson(url, body = {}) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return resp.json();
  }

  function setPdbResult(message, success = true) {
    const elRes = el(mg.pdbSearchResult);
    if (!elRes) return;
    elRes.textContent = message;
    elRes.className = `pdb-search-result ${success ? "success" : "error"}`;
  }

  async function searchPdb() {
    clearPdbDetails();
    const pdb = el(mg.pdbInput).value.trim().toLowerCase();
    if (!/^[0-9a-z_-]{3,20}$/.test(pdb)) {
      setPdbResult("Inserisci un identificativo valido (3-20 caratteri).", false);
      return;
    }
    setPdbResult("Ricerca PDB in corso…", true);
    try {
      const result = await postJson("/api/manage/fetch_pdb", { pdb });
      if (!result.ok) {
        setPdbResult(result.message || "Errore durante la ricerca PDB.", false);
      } else {
        const title = result.metadata?.data?.entry?.struct?.title || "Titolo non disponibile";
        setPdbResult(`PDB ${pdb.toUpperCase()} caricato. ${title}`);
        showPdbDetails(result);
      }
    } catch (err) {
      console.error(err);
      setPdbResult("Errore di rete durante la ricerca PDB.", false);
    } finally {
      await refreshManageStatus();
    }
  }

  function clearPdbDetails() {
    const details = el(mg.pdbDetails);
    if (details) details.classList.add("hidden");
    const result = el(mg.pdbComputeResult);
    if (result) result.textContent = "";
    const chainsCheckboxes = el(mg.pdbChainCheckboxes);
    if (chainsCheckboxes) chainsCheckboxes.innerHTML = "";
    const chainsADisplay = el(mg.pdbChainsADisplay);
    const chainsBDisplay = el(mg.pdbChainsBDisplay);
    if (chainsADisplay) chainsADisplay.innerHTML = "";
    if (chainsBDisplay) chainsBDisplay.innerHTML = "";
    if (el(mg.pdbKdInput)) el(mg.pdbKdInput).value = "";
    if (pdbViewer && typeof pdbViewer.clear === "function") {
      pdbViewer.clear();
    }
    pdbViewer = null;
    pdbStructure = null;
    currentPdbCode = null;
    chainColorMap = {};
  }

  function showPdbDetails(result) {
    const details = el(mg.pdbDetails);
    if (!details) return;
    details.classList.remove("hidden");

    console.log("showPdbDetails - result:", result);
    console.log("showPdbDetails - result.chains:", result.chains);

    // Gestisci sia il vecchio formato (array) che il nuovo (oggetto)
    let allChains = [];
    let antibodyChains = [];
    let antigenChains = [];
    let description = "";
    
    if (Array.isArray(result.chains)) {
      // Vecchio formato: array di catene
      allChains = result.chains;
      // Classifica basandosi sui nomi delle catene - euristica più permissiva
      antibodyChains = allChains.filter(c => {
        const cu = c.toUpperCase();
        return cu === 'H' || cu === 'L' || cu.startsWith('H') || cu.startsWith('L') || 
               cu === 'VHH' || cu.startsWith('V');
      });
      antigenChains = allChains.filter(c => !antibodyChains.includes(c));
      
      if (antibodyChains.length === 0 && allChains.length >= 2) {
        antibodyChains = [allChains[0]];
        antigenChains = allChains.slice(1);
      }
      description = `Complesso con ${allChains.length} catene`;
    } else {
      // Nuovo formato: oggetto con all, antibody, antigen, description
      const chainsData = result.chains || { all: [], antibody: [], antigen: [], description: "" };
      allChains = chainsData.all || [];
      antibodyChains = chainsData.antibody || [];
      antigenChains = chainsData.antigen || [];
      description = chainsData.description || `Complesso con ${allChains.length} catene`;
    }
    
    console.log("showPdbDetails - allChains:", allChains);
    console.log("showPdbDetails - antibodyChains:", antibodyChains);
    console.log("showPdbDetails - antigenChains:", antigenChains);
    console.log("showPdbDetails - description:", description);
    
    if (!allChains.length) {
      const chainInfo = el("pdb-chain-info");
      if (chainInfo) chainInfo.textContent = "Catene non disponibili.";
      console.warn("Nessuna catena trovata nel PDB");
      return;
    }

    currentPdbCode = result.pdb || "";
    
    // Genera colori per le catene
    const colors = generateChainColors(allChains.length);
    allChains.forEach((chain, idx) => {
      chainColorMap[chain] = colors[idx];
    });

    // Popola la sezione descrizione complesso
    const chainInfo = el("pdb-chain-info");
    if (chainInfo) {
      chainInfo.innerHTML = `
        <div style="margin-bottom: 8px;"><strong>Descrizione:</strong></div>
        <div>${description}</div>
        <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border);">
          <strong>Catene totali:</strong> ${allChains.join(", ")}
        </div>
      `;
    }
    
    // Popola la descrizione sopra il viewer
    const pdbDescription = el("pdb-description");
    const pdbDescriptionText = el("pdb-description-text");
    if (pdbDescription && pdbDescriptionText) {
      pdbDescription.classList.remove("hidden");
      pdbDescriptionText.textContent = description;
    }

    // Crea checkbox per le catene nelle sezioni Partner A e Partner B
    const chainsAContainer = el(mg.pdbChainA);
    const chainsBContainer = el(mg.pdbChainB);
    
    if (!chainsAContainer || !chainsBContainer) {
      console.error("Elementi checkbox non trovati");
      return;
    }
    
    chainsAContainer.innerHTML = "";
    chainsBContainer.innerHTML = "";
    
    // Popola "Partner A (Anticorpo)" con solo catene anticorpali
    antibodyChains.forEach((chain) => {
      const color = chainColorMap[chain];
      const checkboxA = document.createElement("div");
      checkboxA.className = "chain-checkbox";
      checkboxA.innerHTML = `
        <input type="checkbox" id="chain-a-${chain}" value="${chain}" />
        <label for="chain-a-${chain}">
          <span class="chain-color" style="background-color: ${color};"></span>
          ${chain}
        </label>
      `;
      chainsAContainer.appendChild(checkboxA);
      const inputA = checkboxA.querySelector("input");
      inputA.addEventListener("change", (e) => {
        const cbB = chainsBContainer.querySelector(`input[value="${chain}"]`);
        if (cbB) cbB.checked = false;
        updateChainsDisplay();
      });
    });
    
    // Popola "Partner B (Antigene)" con solo catene antigeniche
    antigenChains.forEach((chain) => {
      const color = chainColorMap[chain];
      const checkboxB = document.createElement("div");
      checkboxB.className = "chain-checkbox";
      checkboxB.innerHTML = `
        <input type="checkbox" id="chain-b-${chain}" value="${chain}" />
        <label for="chain-b-${chain}">
          <span class="chain-color" style="background-color: ${color};"></span>
          ${chain}
        </label>
      `;
      chainsBContainer.appendChild(checkboxB);
      const inputB = checkboxB.querySelector("input");
      inputB.addEventListener("change", (e) => {
        const cbA = chainsAContainer.querySelector(`input[value="${chain}"]`);
        if (cbA) cbA.checked = false;
        updateChainsDisplay();
      });
    });
    
    // Mostra messaggi se non ci sono catene in una sezione
    if (!antibodyChains.length) {
      chainsAContainer.innerHTML = '<div style="padding: 8px; color: var(--text-hint); font-size: 12px;">Nessuna catena anticorpale identificata</div>';
    }
    if (!antigenChains.length) {
      chainsBContainer.innerHTML = '<div style="padding: 8px; color: var(--text-hint); font-size: 12px;">Nessuna catena antigenica identificata</div>';
    }

    if (result.previous_result) {
      setPdbComputeResult(`Risultato PBEE precedente disponibile.`, true);
      if (result.previous_result.result) {
        displayPbeeResults(currentPdbCode, result.previous_result.chain_ids_a, result.previous_result.chain_ids_b, result.previous_result.kd_nM, result.previous_result.result);
      }
    } else {
      const resultsPanel = el("pbee-results-panel");
      if (resultsPanel) resultsPanel.classList.add("hidden");
    }

    // Controlla se c'è una selezione pendente dallo storico
    if (pendingSelection && pendingSelection.pdb === currentPdbCode) {
      if (pendingSelection.kd_nM) {
        el(mg.pdbKdInput).value = pendingSelection.kd_nM;
      }
      
      // Seleziona le catene per Partner A
      pendingSelection.chains_a.forEach(chain => {
        const cbA = chainsAContainer.querySelector(`input[value="${chain}"]`);
        if (cbA) cbA.checked = true;
      });
      
      // Seleziona le catene per Partner B
      pendingSelection.chains_b.forEach(chain => {
        const cbB = chainsBContainer.querySelector(`input[value="${chain}"]`);
        if (cbB) cbB.checked = true;
      });
      
      updateChainsDisplay();
      
      if (pendingSelection.result) {
        displayPbeeResults(currentPdbCode, pendingSelection.chains_a, pendingSelection.chains_b, pendingSelection.kd_nM, pendingSelection.result);
      }
      pendingSelection = null;
    }

    // Carica il visualizzatore 3D
    loadPdbViewer(currentPdbCode, allChains);
    
    // Aggiungi event listener per i pulsanti di spostamento catene
    const btnMoveToB = el("btn-move-to-b");
    const btnMoveToA = el("btn-move-to-a");
    
    if (btnMoveToB) {
      btnMoveToB.addEventListener("click", () => moveSelectedChains(chainsAContainer, chainsBContainer));
    }
    if (btnMoveToA) {
      btnMoveToA.addEventListener("click", () => moveSelectedChains(chainsBContainer, chainsAContainer));
    }
  }
  
  function moveSelectedChains(fromContainer, toContainer) {
    const selectedCheckboxes = fromContainer.querySelectorAll("input:checked");
    if (selectedCheckboxes.length === 0) {
      alert("Seleziona almeno una catena da spostare");
      return;
    }
    
    selectedCheckboxes.forEach(cb => {
      const chain = cb.value;
      const color = chainColorMap[chain];
      
      // Rimuovi dal container originale
      cb.closest(".chain-checkbox").remove();
      
      // Aggiungi al container di destinazione
      const newCheckbox = document.createElement("div");
      newCheckbox.className = "chain-checkbox";
      newCheckbox.innerHTML = `
        <input type="checkbox" id="chain-${toContainer.id}-${chain}" value="${chain}" />
        <label for="chain-${toContainer.id}-${chain}">
          <span class="chain-color" style="background-color: ${color};"></span>
          ${chain}
        </label>
      `;
      toContainer.appendChild(newCheckbox);
      
      const newInput = newCheckbox.querySelector("input");
      newInput.addEventListener("change", (e) => {
        const allContainer = el(mg.pdbChainCheckboxes);
        const otherContainer = toContainer === chainsAContainer ? chainsBContainer : chainsAContainer;
        const cbAll = allContainer.querySelector(`input[value="${chain}"]`);
        const cbOther = otherContainer.querySelector(`input[value="${chain}"]`);
        if (cbAll) cbAll.checked = false;
        if (cbOther) cbOther.checked = false;
        updateChainsDisplay();
      });
    });
    
    updateChainsDisplay();
  }

  function generateChainColors(count) {
    const colors = [
      "#378ADD", "#F77B58", "#4ECDC4", "#FFD93D",
      "#6BCB77", "#FF6B6B", "#A78BFA", "#FB923C",
      "#34D399", "#F472B6", "#60A5FA", "#FBBF24"
    ];
    return colors.slice(0, count).concat(
      Array(Math.max(0, count - colors.length)).fill(0).map((_, i) => {
        const hue = (i * 360 / (count - colors.length)) % 360;
        return `hsl(${hue}, 70%, 60%)`;
      })
    );
  }

  function updateChainsDisplay() {
    const chainsAContainer = el(mg.pdbChainA);
    const chainsBContainer = el(mg.pdbChainB);
    const selectedA = chainsAContainer ? Array.from(chainsAContainer.querySelectorAll("input:checked")).map(cb => cb.value) : [];
    const selectedB = chainsBContainer ? Array.from(chainsBContainer.querySelectorAll("input:checked")).map(cb => cb.value) : [];
    if (!pdbViewer || !pdbStructure) return;

    pdbViewer.clear();
    const allChains = Object.keys(chainColorMap);
    const colorLib = pv?.color;
    
    // Colora ogni catena con un colore diverso (cartoon)
    allChains.forEach((chain) => {
      const selection = pdbStructure.select({ chain });
      if (!selection) return;
      const colorHex = chainColorMap[chain] || COLORS.gray;
      pdbViewer.cartoon(`chain-${chain}`, selection, {
        color: colorLib ? colorLib.uniform(colorHex) : colorHex,
        radius: 0.35,
        showRelated: '1',
      });
    });

    // Visualizza le interazioni tra catene selezionate con colori più visibili
    if (selectedA.length > 0 && selectedB.length > 0) {
      // Seleziona Partner A e Partner B usando atomSelect con predicato per compatibilità
      const selectionA = pdbStructure.atomSelect(function(atom) {
        return selectedA.includes(atom.residue().chain().name());
      });
      const selectionB = pdbStructure.atomSelect(function(atom) {
        return selectedB.includes(atom.residue().chain().name());
      });
      
      if (selectionA && selectionB && selectionA.atomCount() > 0 && selectionB.atomCount() > 0) {
        try {
          // Trova i residui a contatto (cutoff 4.5 Å) usando il metodo nativo selectWithin
          const interactingA = selectionA.selectWithin(selectionB, { radius: 4.5, matchResidues: true });
          const interactingB = selectionB.selectWithin(selectionA, { radius: 4.5, matchResidues: true });
          
          // Colori più vivaci per le interazioni
          const interactionColorA = '#FF0066'; // Rosa/rosso brillante per Partner A
          const interactionColorB = '#00CCFF'; // Ciano brillante per Partner B
          
          if (interactingA && interactingA.atomCount() > 0) {
            // Cartoon molto spesso e visibile
            pdbViewer.cartoon('interacting-cartoon-a', interactingA, {
              color: colorLib ? colorLib.uniform(interactionColorA) : interactionColorA,
              radius: 0.7,
            });
            // Sticks spessi con sfere grandi
            pdbViewer.ballsAndSticks('interacting-sticks-a', interactingA, {
              color: colorLib ? colorLib.uniform(interactionColorA) : interactionColorA,
              radius: 0.25,
              sphereRadius: 0.45,
            });
          }
          
          if (interactingB && interactingB.atomCount() > 0) {
            // Cartoon molto spesso e visibile
            pdbViewer.cartoon('interacting-cartoon-b', interactingB, {
              color: colorLib ? colorLib.uniform(interactionColorB) : interactionColorB,
              radius: 0.7,
            });
            // Sticks spessi con sfere grandi
            pdbViewer.ballsAndSticks('interacting-sticks-b', interactingB, {
              color: colorLib ? colorLib.uniform(interactionColorB) : interactionColorB,
              radius: 0.25,
              sphereRadius: 0.45,
            });
          }
        } catch (e) {
          console.warn("Impossibile calcolare/visualizzare le interazioni con selectWithin:", e);
        }
      }
    }
    
    if (typeof pdbViewer.autoZoom === "function") {
      pdbViewer.autoZoom();
    }
    if (typeof pdbViewer.requestRedraw === "function") {
      pdbViewer.requestRedraw();
    }
  }

  function loadPdbViewer(pdbCode, chains) {
    const viewerDiv = el(mg.pdbViewer);
    showViewerLoader(true);
    
    if (!viewerDiv) {
      console.error("Viewer div not found");
      showViewerLoader(false);
      return;
    }
    
    if (!window.pv) {
      console.error("PV library not loaded");
      viewerDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">PV library not loaded. Please refresh the page.</div>';
      showViewerLoader(false);
      return;
    }

    if (!pdbViewer) {
      try {
        pdbViewer = pv.Viewer(viewerDiv, {
          width: 'auto',
          height: 'auto',
          antialias: true,
          quality: 'high',
          style: 'phong',
          selectionColor: 'white',
          transparency: 'screendoor',
          outline: true,
          outlineWidth: 1.5,
          background: '#ffffff',
          animateTime: 200,
        });
      } catch (e) {
        console.error("Error initializing PV Viewer:", e);
        viewerDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">Error initializing viewer: ' + e.message + '</div>';
        showViewerLoader(false);
        return;
      }
    } else if (typeof pdbViewer.clear === "function") {
      pdbViewer.clear();
    }

    currentPdbCode = pdbCode;
    pdbStructure = null;
    const pdbUrl = `/api/pdb/${encodeURIComponent(pdbCode)}`;

    pv.io.fetchPdb(pdbUrl, function(structure) {
      showViewerLoader(false);
      pdbStructure = structure;
      updateChainsDisplay();
      if (typeof pdbViewer.autoZoom === "function") {
        pdbViewer.autoZoom();
      }
      if (typeof pdbViewer.fitParent === "function") {
        pdbViewer.fitParent();
      }
    }, function(error) {
      showViewerLoader(false);
      console.error("Error fetching PDB:", error);
      viewerDiv.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">Error loading PDB structure from server: ' + error + '</div>';
    });
  }

  function highlightInterface(chainA, chainB) {
    // Funzione per evidenziare l'interfaccia tra due catene
    // Nota: l'interfaccia viene già evidenziata attraverso i colori e gli sticks in updateChainsDisplay()
    // Questa funzione è mantenuta per compatibilità ma non fa nulla di critico
    if (!pdbViewer || !chainA || !chainB) return;
    // La visualizzazione dell'interfaccia è gestita in updateChainsDisplay()
  }

  function getSelectedChains(containerId) {
    const container = el(containerId);
    if (!container) return [];
    return Array.from(container.querySelectorAll("input:checked")).map((cb) => cb.value);
  }

  async function runPbeeCompute() {
    const pdb = el(mg.pdbInput).value.trim().toLowerCase();
    const chain_ids_a = getSelectedChains(mg.pdbChainA);
    const chain_ids_b = getSelectedChains(mg.pdbChainB);
    const kd_value = el(mg.pdbKdInput).value.trim();
    
    if (!chain_ids_a.length || !chain_ids_b.length) {
      setPdbComputeResult("Seleziona almeno una catena per ciascun partner.", false);
      return;
    }
    
    setPdbComputeResult("Avvio elaborazione PBEE...", true);
    setComputeBusy(true);
    
    try {
      const result = await postJson("/api/manage/compute_pdb", {
        pdb,
        chain_ids_a,
        chain_ids_b,
        kd_nM: kd_value || null,
      });
      if (!result.ok) {
        setPdbComputeResult(result.message || "Errore avviando PBEE.", false);
        setComputeBusy(false);
      } else {
        setPdbComputeResult("Elaborazione avviata in background sul server. Attesa...", true);
        startPollingTask(pdb, chain_ids_a, chain_ids_b, kd_value);
      }
    } catch (err) {
      console.error(err);
      setPdbComputeResult("Errore di rete durante l'elaborazione PBEE.", false);
      setComputeBusy(false);
    }
  }

  function setPdbComputeResult(message, success = true) {
    const elRes = el(mg.pdbComputeResult);
    if (!elRes) return;
    elRes.textContent = message;
    elRes.className = `pdb-search-result ${success ? "success" : "error"}`;
  }

  // --- Nuove funzioni di supporto frontend ---

  function showViewerLoader(show) {
    const loader = el("viewer-loader");
    if (loader) {
      if (show) loader.classList.remove("hidden");
      else loader.classList.add("hidden");
    }
  }

  async function uploadPdb() {
    const fileInput = el("f-upload-file");
    const idInput = el("f-upload-id");
    const file = fileInput.files[0];
    const pdb_id = idInput.value.trim().toLowerCase();
    
    if (!file) {
      setPdbResult("Seleziona prima un file PDB.", false);
      return;
    }
    if (!/^[0-9a-z_-]{3,20}$/.test(pdb_id)) {
      setPdbResult("Inserisci un identificativo valido (3-20 caratteri).", false);
      return;
    }
    
    setPdbResult("Caricamento PDB in corso...", true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("pdb_id", pdb_id);
    
    try {
      const resp = await fetch("/api/manage/upload_pdb", {
        method: "POST",
        body: formData
      });
      const result = await resp.json();
      if (!result.ok) {
        setPdbResult(result.message || "Errore durante il caricamento del PDB.", false);
      } else {
        setPdbResult(result.message);
        el(mg.pdbInput).value = pdb_id; // Imposta il codice PDB per il calcolo successivo
        showPdbDetails(result);
      }
    } catch (err) {
      console.error(err);
      setPdbResult("Errore di rete durante il caricamento.", false);
    } finally {
      await refreshManageStatus();
    }
  }

  function displayPbeeResults(pdbId, chainsA, chainsB, kd, result) {
    const panel = el("pbee-results-panel");
    if (!panel) return;
    
    panel.classList.remove("hidden");
    el("res-pdb-id").textContent = pdbId.toUpperCase();
    
    if (result && typeof result.total === "number") {
      el("res-dg-pred").textContent = result.total.toFixed(2);
      
      // Elettrostatica
      const elec = result.electrostatic || 0;
      el("res-comp-elec").textContent = elec.toFixed(2) + " kcal/mol";
      
      // Apolare
      const apolar = result.apolar || 0;
      el("res-comp-apolar").textContent = apolar.toFixed(2) + " kcal/mol";
      
      // Entropia
      const entropy = result.entropy || 0;
      el("res-comp-entropy").textContent = entropy.toFixed(2) + " kcal/mol";
      
      // Barre di progresso
      const maxVal = Math.max(Math.abs(elec), Math.abs(apolar), Math.abs(entropy), 10);
      const barElec = el("bar-elec");
      const barApolar = el("bar-apolar");
      const barEntropy = el("bar-entropy");
      
      barElec.style.width = Math.min(100, (Math.abs(elec) / maxVal) * 100) + "%";
      barApolar.style.width = Math.min(100, (Math.abs(apolar) / maxVal) * 100) + "%";
      barEntropy.style.width = Math.min(100, (Math.abs(entropy) / maxVal) * 100) + "%";
      
      barElec.className = "comp-bar " + (elec < 0 ? "favorable" : "unfavorable");
      barApolar.className = "comp-bar " + (apolar < 0 ? "favorable" : "unfavorable");
      barEntropy.className = "comp-bar unfavorable";
      
      // Dati sperimentali
      if (typeof result.dg_exp === "number") {
        el("res-dg-exp").textContent = result.dg_exp.toFixed(2);
        el("res-kd-exp").textContent = `Kd: ${kd ? parseFloat(kd).toLocaleString('it-IT') : '—'} nM`;
        
        const diff = result.total - result.dg_exp;
        const diffEl = el("res-dg-diff");
        diffEl.textContent = (diff > 0 ? "+" : "") + diff.toFixed(2);
        
        const absDiff = Math.abs(diff);
        if (absDiff < 1) {
          diffEl.className = "value good";
        } else if (absDiff < 2) {
          diffEl.className = "value warn";
        } else {
          diffEl.className = "value bad";
        }
      } else {
        el("res-dg-exp").textContent = "N/D";
        el("res-kd-exp").textContent = "Kd: non fornito";
        const diffEl = el("res-dg-diff");
        diffEl.textContent = "N/D";
        diffEl.className = "value";
      }
      
      el("res-chains-a").textContent = (chainsA || []).join(", ") || "Nessuna";
      el("res-chains-b").textContent = (chainsB || []).join(", ") || "Nessuna";
      el("res-atoms").textContent = result.n_atoms || "N/D";
      el("res-charges").textContent = result.n_charges || "N/D";
      
      // Scroll dei risultati per renderli visibili
      panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function renderSharedRuns(runs) {
    const body = el("shared-runs-body");
    if (!body) return;
    if (!runs || !runs.length) {
      body.innerHTML = '<tr><td colspan="8" style="padding:16px;text-align:center;color:var(--text-hint)">Nessun calcolo PBEE condiviso sul server</td></tr>';
      return;
    }
    body.innerHTML = runs.map((run) => {
      const created = run.created || "N/D";
      const pdb = run.pdb.toUpperCase();
      const chainsA = (run.chains_a || []).join(", ");
      const chainsB = (run.chains_b || []).join(", ");
      const kd = run.kd_nM ? parseFloat(run.kd_nM).toLocaleString("it-IT") : "N/D";
      const predDg = run.result && typeof run.result.total === "number" ? run.result.total.toFixed(2) : "—";
      const expDg = run.result && typeof run.result.dg_exp === "number" ? run.result.dg_exp.toFixed(2) : "—";
      
      return `<tr>
        <td class="pdb font-bold">${pdb}</td>
        <td>${created}</td>
        <td><span class="chain-badge select-a">${chainsA}</span></td>
        <td><span class="chain-badge select-b">${chainsB}</span></td>
        <td class="num">${kd}</td>
        <td class="num font-bold text-primary">${predDg}</td>
        <td class="num">${expDg}</td>
        <td style="text-align: center;">
          <button class="btn btn-sm btn-load-run" data-pdb="${run.pdb}">Carica nel 3D</button>
        </td>
      </tr>`;
    }).join("");
    
    body.querySelectorAll(".btn-load-run").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        const pdbId = event.currentTarget.getAttribute("data-pdb");
        loadSharedRun(pdbId, runs);
      });
    });
  }

  async function loadSharedRun(pdbId, runs) {
    const run = runs.find((r) => r.pdb === pdbId);
    if (!run) return;
    
    pendingSelection = {
      pdb: pdbId,
      chains_a: run.chains_a || [],
      chains_b: run.chains_b || [],
      kd_nM: run.kd_nM,
      result: run.result,
    };
    
    el(mg.pdbInput).value = pdbId;
    setPdbResult(`Caricamento calcolo storico per ${pdbId.toUpperCase()}...`, true);
    
    try {
      const result = await postJson("/api/manage/fetch_pdb", { pdb: pdbId });
      if (!result.ok) {
        setPdbResult(result.message || "Errore durante il caricamento del PDB.", false);
        pendingSelection = null;
      } else {
        setPdbResult(`Calcolo storico per ${pdbId.toUpperCase()} caricato.`);
        showPdbDetails(result);
      }
    } catch (err) {
      console.error(err);
      setPdbResult("Errore di rete durante il caricamento del PDB storico.", false);
      pendingSelection = null;
    }
  }

  function setComputeBusy(busy) {
    const btn = el(mg.btnRunPbee);
    if (btn) {
      btn.disabled = busy;
      if (busy) {
        btn.innerHTML = '<span class="spinner small"></span> Calcolo in corso...';
      } else {
        btn.textContent = "Avvia Calcolo PBEE";
      }
    }
  }

  function startPollingTask(pdb_id, chains_a, chains_b, kd) {
    if (pollInterval) clearInterval(pollInterval);
    
    pollInterval = setInterval(async () => {
      try {
        const status = await fetch("/api/manage/status").then((r) => r.json());
        const task = status.background_tasks[pdb_id.lower()];
        
        if (!task) {
          setPdbComputeResult("Stato dell'elaborazione non trovato.", false);
          stopPolling();
          return;
        }
        
        if (task.status === "done") {
          setPdbComputeResult("Calcolo completato con successo!", true);
          stopPolling();
          
          const runResult = status.pdb_results.find((r) => r.pdb === pdb_id.lower());
          if (runResult && runResult.result) {
            displayPbeeResults(pdb_id, chains_a, chains_b, kd, runResult.result);
          }
          
          await refresh();
          await refreshManageStatus();
        } else if (task.status === "failed") {
          setPdbComputeResult("Errore durante l'elaborazione: " + (task.message || "Errore inatteso"), false);
          stopPolling();
        } else {
          setPdbComputeResult(`Stato: ${task.message || "Elaborazione in corso..."}`, true);
        }
      } catch (err) {
        console.error("Errore durante il polling:", err);
      }
    }, 2000);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    setComputeBusy(false);
  }

  async function manageAction(url, refreshDataset = false, body = {}) {
    setManageMessage("In esecuzione...");
    setManageBusy(true);
    try {
      const result = await postJson(url, body);
      if (!result.ok) {
        setManageMessage(result.message || "Errore inatteso");
      } else {
        setManageMessage(result.message || "Operazione completata");
        if (refreshDataset) {
          await refresh();
        }
      }
    } catch (err) {
      console.error(err);
      setManageMessage("Errore di rete durante l'operazione.");
    } finally {
      setManageBusy(false);
      await refreshManageStatus();
    }
  }

  function setManageBusy(on) {
    [mg.btnFetchSummary, mg.btnRunPipeline, mg.btnSaveVersion].forEach((id) => {
      const button = el(id);
      if (button) button.disabled = on;
    });
  }

  function setManageMessage(text) {
    const elMsg = el(mg.message);
    if (elMsg) elMsg.textContent = text;
  }

  async function refreshManageStatus() {
    try {
      const status = await fetch("/api/manage/status").then((r) => r.json());
      el(mg.datasetStatus).textContent = status.dataset.exists ? `${status.dataset_count} record · aggiornato ${status.dataset.modified}` : "non disponibile";
      el(mg.summaryStatus).textContent = status.summary.exists ? `Salvato · aggiornato ${status.summary.modified}` : "non disponibile";
      el(mg.summaryRows).textContent = status.summary_rows || 0;
      if (el(mg.cacheStatus)) {
        el(mg.cacheStatus).textContent = status.cache?.count ? `${status.cache.count} PDB memorizzati` : "nessun PDB memorizzato";
      }
      renderHistory(status.history);
      renderSharedRuns(status.pdb_results);
    } catch (err) {
      console.error(err);
      setManageMessage("Impossibile leggere lo stato di gestione.");
    }
  }

  function renderHistory(versions) {
    const container = el(mg.historyList);
    if (!container) return;
    if (!versions || !versions.length) {
      container.innerHTML = '<div class="history-item"><em>Nessuna versione salvata</em></div>';
      return;
    }
    container.innerHTML = versions.map((version) => {
      return `
        <div class="history-item">
          <div><strong>${version.name}</strong></div>
          <div class="hint">Creato ${version.created} · ${Math.round(version.size / 1024)} KB</div>
          <button type="button" class="btn" data-version="${version.name}">Ripristina</button>
        </div>
      `;
    }).join("");
    container.querySelectorAll("button[data-version]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        const version = event.currentTarget.getAttribute("data-version");
        restoreVersion(version);
      });
    });
  }

  async function restoreVersion(version) {
    if (!confirm(`Ripristinare la versione ${version}?`)) return;
    setManageMessage("Ripristino in corso...");
    setManageBusy(true);
    try {
      const result = await postJson("/api/manage/restore_version", { version });
      if (!result.ok) {
        setManageMessage(result.message || "Errore durante il ripristino.");
      } else {
        setManageMessage(result.message || "Ripristino completato.");
        await refresh();
      }
    } catch (err) {
      console.error(err);
      setManageMessage("Errore di rete durante il ripristino.");
    } finally {
      setManageBusy(false);
      await refreshManageStatus();
    }
  }

  function queryString() {
    const params = new URLSearchParams();
    params.set("dataset", state.dataset);
    params.set("format", state.format);
    params.set("method", state.method);
    params.set("source", state.source);
    params.set("res_max", state.res_max);
    if (state.kd_max < 10000) params.set("kd_max", state.kd_max);
    return params.toString();
  }

  function toggleViewMode() {
    const singleMetrics = el("single-metrics");
    const comparisonMetrics = el("comparison-metrics");
    const datasetFilter = el("f-dataset-filter");

    if (state.viewMode === "comparison") {
      singleMetrics.classList.add("hidden");
      comparisonMetrics.classList.remove("hidden");
      datasetFilter.classList.add("hidden");
    } else {
      singleMetrics.classList.remove("hidden");
      comparisonMetrics.classList.add("hidden");
      datasetFilter.classList.remove("hidden");
    }
  }

  async function refresh() {
    if (state.viewMode === "comparison") {
      const data = await fetch("/api/datasets/both?" + queryString()).then((r) => r.json());
      updateComparisonMetrics(data);
    } else {
      const data = await fetch("/api/dataset?" + queryString()).then((r) => r.json());
      updateMetrics(data.metrics);
      updateCharts(data.records);
      updateTable(data.records);
      el("btn-export").href = "/api/export.csv?" + queryString();
    }
  }

  function updateComparisonMetrics(data) {
    // Update Dataset 1 metrics
    el("m1-count").textContent = data.dataset1.count;
    if (data.dataset1.metrics) {
      el("m1-rmse").textContent = data.dataset1.metrics.rmse?.toFixed(2) || "—";
      el("m1-mae").textContent = data.dataset1.metrics.mae?.toFixed(2) || "—";
      el("m1-pearson").textContent = data.dataset1.metrics.pearson?.toFixed(2) || "—";
      el("m1-spearman").textContent = data.dataset1.metrics.spearman?.toFixed(2) || "—";
      el("m1-kendall").textContent = data.dataset1.metrics.kendall?.toFixed(2) || "—";
      el("m1-bias").textContent = data.dataset1.metrics.bias?.toFixed(2) || "—";
    }

    // Update Dataset 2 metrics
    el("m2-count").textContent = data.dataset2.count;
    if (data.dataset2.metrics) {
      el("m2-rmse").textContent = data.dataset2.metrics.rmse?.toFixed(2) || "—";
      el("m2-mae").textContent = data.dataset2.metrics.mae?.toFixed(2) || "—";
      el("m2-pearson").textContent = data.dataset2.metrics.pearson?.toFixed(2) || "—";
      el("m2-spearman").textContent = data.dataset2.metrics.spearman?.toFixed(2) || "—";
      el("m2-kendall").textContent = data.dataset2.metrics.kendall?.toFixed(2) || "—";
      el("m2-bias").textContent = data.dataset2.metrics.bias?.toFixed(2) || "—";
    }
  }

  function fmt(v, digits = 2) {
    if (v === null || v === undefined) return "—";
    return typeof v === "number" ? v.toFixed(digits) : v;
  }

  function updateMetrics(m) {
    el("m-count").textContent = m.n ?? "—";
    el("m-rmse").textContent = fmt(m.rmse);
    el("m-mae").textContent = fmt(m.mae);
    el("m-pearson").textContent = fmt(m.pearson);
    el("m-spearman").textContent = fmt(m.spearman);
    el("m-kendall").textContent = fmt(m.kendall);
    el("m-bias").textContent = fmt(m.bias);
  }

  function updateCharts(records) {
    if (!records.length) {
      if (scatterChart) { scatterChart.destroy(); scatterChart = null; }
      if (residualsChart) { residualsChart.destroy(); residualsChart = null; }
      return;
    }
    if (typeof Chart === "undefined") {
      console.warn("Chart.js non disponibile");
      return;
    }
    const exp = records.map((r) => r.dG_exp_kcal_mol);
    const pred = records.map((r) => r.dG_pred_kcal_mol);
    const allVals = exp.concat(pred);
    const lo = Math.floor(Math.min(...allVals) - 1);
    const hi = Math.ceil(Math.max(...allVals) + 1);

    if (scatterChart) scatterChart.destroy();
    scatterChart = new Chart(el("scatter"), {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Complessi",
            data: records.map((r) => ({ x: r.dG_exp_kcal_mol, y: r.dG_pred_kcal_mol, pdb: r.pdb })),
            backgroundColor: COLORS.blueLight,
            borderColor: COLORS.blueDark,
            borderWidth: 1,
            pointRadius: 5,
            pointHoverRadius: 7,
          },
          {
            label: "y = x",
            type: "line",
            data: [{ x: lo, y: lo }, { x: hi, y: hi }],
            borderColor: COLORS.gray,
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => ctx.datasetIndex === 0
                ? `PDB ${ctx.raw.pdb}: exp ${ctx.parsed.x.toFixed(2)}, pred ${ctx.parsed.y.toFixed(2)}`
                : "",
            },
          },
        },
        scales: {
          x: { title: { display: true, text: "ΔG sperimentale (kcal/mol)" }, min: lo, max: hi },
          y: { title: { display: true, text: "ΔG predetto PBEE (kcal/mol)" }, min: lo, max: hi },
        },
      },
    });

    const errs = records.map((r) => r.dG_pred_kcal_mol - r.dG_exp_kcal_mol);
    const nBins = 12;
    const rLo = Math.min(...errs, -3);
    const rHi = Math.max(...errs, 3);
    const w = (rHi - rLo) / nBins;
    const bins = new Array(nBins).fill(0);
    const labels = [];
    for (let i = 0; i < nBins; i++) labels.push((rLo + w * (i + 0.5)).toFixed(1));
    errs.forEach((e) => {
      let idx = Math.floor((e - rLo) / w);
      if (idx >= nBins) idx = nBins - 1;
      if (idx < 0) idx = 0;
      bins[idx]++;
    });

    if (residualsChart) residualsChart.destroy();
    residualsChart = new Chart(el("residuals"), {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: "Frequenza",
          data: bins,
          backgroundColor: COLORS.blueLight,
          borderColor: COLORS.blueDark,
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { title: { display: true, text: "Residuo (kcal/mol)" } },
          y: {
            title: { display: true, text: "N complessi" },
            beginAtZero: true,
            ticks: { stepSize: 1, precision: 0 },
          },
        },
      },
    });
  }

  function updateTable(records) {
    el("tbl-n").textContent = records.length;
    const body = el("tbl-body");
    if (!records.length) {
      body.innerHTML = '<tr><td colspan="10" style="padding:16px;text-align:center;color:var(--text-muted)">Nessun complesso corrisponde ai filtri selezionati</td></tr>';
      return;
    }
    const sorted = records.slice().sort((a, b) => a.kd_nM - b.kd_nM);
    body.innerHTML = sorted.map((r) => {
      const diff = r.dG_pred_kcal_mol - r.dG_exp_kcal_mol;
      const cls = Math.abs(diff) < 1 ? "good" : Math.abs(diff) < 2 ? "warn" : "bad";
      const kd = r.kd_nM < 1 ? r.kd_nM.toFixed(2)
        : r.kd_nM < 10 ? r.kd_nM.toFixed(1)
        : Math.round(r.kd_nM).toLocaleString("it-IT");
      return `<tr>
        <td class="pdb">${r.pdb}</td>
        <td>${r.format}</td>
        <td class="antigen">${r.antigen}</td>
        <td class="num">${kd}</td>
        <td class="num">${r.dG_exp_kcal_mol.toFixed(2)}</td>
        <td class="num">${r.dG_pred_kcal_mol.toFixed(2)}</td>
        <td class="num diff ${cls}">${diff > 0 ? "+" : ""}${diff.toFixed(2)}</td>
        <td class="method">${r.method}</td>
        <td class="method">${r.source}</td>
        <td class="num">${r.resolution}</td>
      </tr>`;
    }).join("");
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
