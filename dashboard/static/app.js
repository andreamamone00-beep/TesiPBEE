(function () {
  "use strict";

  const el = (id) => document.getElementById(id);
  const state = { format: "all", method: "all", source: "all", res_max: 3.5, kd_max: 10000 };
  let scatterChart = null;
  let residualsChart = null;

  const mg = {
    datasetStatus: "mg-dataset-status",
    summaryStatus: "mg-summary-status",
    summaryRows: "mg-summary-rows",
    message: "mg-message",
    historyList: "history-list",
    btnFetchSummary: "btn-fetch-summary",
    btnRunPipeline: "btn-run-pipeline",
    btnSaveVersion: "btn-save-version",
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
      meta = await fetch("/api/metadata").then((r) => r.json());
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
  }

  async function postJson(url, body = {}) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return resp.json();
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
      renderHistory(status.history);
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
    params.set("format", state.format);
    params.set("method", state.method);
    params.set("source", state.source);
    params.set("res_max", state.res_max);
    if (state.kd_max < 10000) params.set("kd_max", state.kd_max);
    return params.toString();
  }

  async function refresh() {
    const data = await fetch("/api/dataset?" + queryString()).then((r) => r.json());
    updateMetrics(data.metrics);
    updateCharts(data.records);
    updateTable(data.records);
    el("btn-export").href = "/api/export.csv?" + queryString();
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
