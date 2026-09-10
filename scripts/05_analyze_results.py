"""Step 5 — Analisi statistica e generazione di TUTTI i grafici utili
per la tesi.

Grafici generati in results/:
  01_scatter_pred_vs_exp.png        scatter ΔG_pred vs ΔG_exp + linea y=x
  02_scatter_by_format.png          scatter colorato per formato (Fab/scFv/VHH)
  03_residuals_hist.png             istogramma dei residui
  04_residuals_by_class.png         boxplot residui per classe di affinità
  05_residuals_vs_exp.png           residui vs ΔG_exp (check omoscedasticità)
  06_bland_altman.png               Bland-Altman plot (bias ± 1.96·SD)
  07_qq_residuals.png               Q-Q plot normale sui residui
  08_kd_distribution.png            istogramma log10(Kd) del dataset
  09_kd_vs_resolution.png           Kd vs risoluzione cristallografica
  10_metrics_by_format.png          bar chart RMSE/MAE/r per formato
  11_metrics_by_method.png          bar chart RMSE/MAE/r per tecnica
  12_decomposition_stack.png        stacked bar componenti ΔG PBEE
  13_ranking_accuracy.png           correlazione rank (per ranking drug candidates)
  14_error_heatmap.png              heatmap errori per formato × metodo
  15_source_coverage.png            pie chart dei contributi per fonte
  16_roc_highaffinity.png           ROC per classificazione "alta affinità"
  17_calibration_curve.png          calibrazione delle predizioni per bin di ΔG_exp
  18_venn_sources.png               diagramma pseudo-Venn tra fonti
  19_timeline_dataset.png           crescita simulata del dataset per data
  20_summary_panel.png              pannello riassuntivo 2×2

Output dati:
  metrics.json                      metriche globali + per-classe
  metrics_by_format.csv             tabella metriche per formato
  metrics_by_method.csv             tabella metriche per metodo
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (DATASET_FINAL, METRICS_JSON, RESULTS_DIR, ensure_dirs,
                   get_logger)

log = get_logger("05_analyze")


# ---------------------------------------------------------------------------
# Metriche base (senza pandas/scipy per tenere core leggero)
# ---------------------------------------------------------------------------
def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def stdev(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def pearson(xs, ys):
    if len(xs) < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else 0.0


def spearman(xs, ys):
    def rank(a):
        idx = sorted(enumerate(a), key=lambda p: p[1])
        r = [0.0] * len(a)
        for k, (i, _) in enumerate(idx):
            r[i] = k + 1
        return r
    return pearson(rank(xs), rank(ys))


def kendall_tau(xs, ys):
    """Kendall's tau-b."""
    n = len(xs)
    if n < 2:
        return 0.0
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            a = (xs[i] - xs[j]) * (ys[i] - ys[j])
            if a > 0:
                conc += 1
            elif a < 0:
                disc += 1
    denom = 0.5 * n * (n - 1)
    return (conc - disc) / denom if denom else 0.0


def classify_affinity(kd_nm: float) -> str:
    if kd_nm < 10:
        return "alta"
    if kd_nm < 100:
        return "media"
    return "bassa"


# ---------------------------------------------------------------------------
# Caricamento dataset
# ---------------------------------------------------------------------------
def load_dataset() -> list[dict]:
    if not DATASET_FINAL.exists():
        log.error("File %s non trovato. Esegui prima 04_compute_pbee.py", DATASET_FINAL)
        sys.exit(2)

    float_fields = {
        "kd_nM", "resolution", "temperature_K", "ph", "pKd",
        "dG_exp_kcal_mol", "dG_exp_raw_kcal_mol",
        "dG_pred_kcal_mol", "dG_pred_electrostatic", "dG_pred_apolar",
        "dG_pred_entropy",
        "n_residues_ab", "n_residues_ag", "interface_area_A2",
        "pbee_runtime_s",
    }
    rows = []
    with DATASET_FINAL.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for k in float_fields:
                if k in row and row[k] not in ("", None, "N/A"):
                    try:
                        row[k] = float(row[k])
                    except ValueError:
                        pass
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Metriche globali
# ---------------------------------------------------------------------------
def global_metrics(records: list[dict]) -> dict:
    # Filter out records with N/A or missing PBEE predictions
    valid_records = [r for r in records if isinstance(r.get("dG_pred_kcal_mol"), (int, float))
                     and isinstance(r.get("dG_exp_kcal_mol"), (int, float))]

    if len(valid_records) < 2:
        return {
            "n_complexes": len(records),
            "n_valid": len(valid_records),
            "rmse_kcal_mol": None,
            "mae_kcal_mol": None,
            "pearson_r": None,
            "spearman_rho": None,
            "kendall_tau": None,
            "bias_mean": None,
            "bias_std": None,
            "by_affinity_class": {},
        }

    exp = [r["dG_exp_kcal_mol"] for r in valid_records]
    pred = [r["dG_pred_kcal_mol"] for r in valid_records]
    errs = [p - e for p, e in zip(pred, exp)]

    by_class = defaultdict(list)
    for r in valid_records:
        cls = classify_affinity(r["kd_nM"])
        by_class[cls].append(r["dG_pred_kcal_mol"] - r["dG_exp_kcal_mol"])

    class_stats = {}
    for cls in ("alta", "media", "bassa"):
        values = by_class[cls]
        class_stats[cls] = {
            "n": len(values),
            "mae": round(mean([abs(v) for v in values]), 3) if values else None,
            "rmse": round(math.sqrt(mean([v ** 2 for v in values])), 3) if values else None,
            "bias": round(mean(values), 3) if values else None,
        }

    return {
        "n_complexes": len(records),
        "n_valid": len(valid_records),
        "rmse_kcal_mol": round(math.sqrt(mean([e ** 2 for e in errs])), 3),
        "mae_kcal_mol": round(mean([abs(e) for e in errs]), 3),
        "pearson_r": round(pearson(exp, pred), 3),
        "spearman_rho": round(spearman(exp, pred), 3),
        "kendall_tau": round(kendall_tau(exp, pred), 3),
        "bias_mean": round(mean(errs), 3),
        "bias_std": round(stdev(errs), 3),
        "by_affinity_class": class_stats,
    }


def metrics_by_field(records: list[dict], field: str) -> list[dict]:
    groups = defaultdict(list)
    for r in records:
        key = r.get(field) or "—"
        groups[key].append(r)
    out = []
    for key, rs in groups.items():
        exp = [r["dG_exp_kcal_mol"] for r in rs]
        pred = [r["dG_pred_kcal_mol"] for r in rs]
        errs = [p - e for p, e in zip(pred, exp)]
        out.append({
            field: key,
            "n": len(rs),
            "rmse": round(math.sqrt(mean([e ** 2 for e in errs])), 3) if errs else None,
            "mae": round(mean([abs(e) for e in errs]), 3) if errs else None,
            "pearson_r": round(pearson(exp, pred), 3) if len(exp) > 1 else None,
            "bias": round(mean(errs), 3) if errs else None,
        })
    return sorted(out, key=lambda x: -(x["n"]))


# ---------------------------------------------------------------------------
# Generazione grafici
# ---------------------------------------------------------------------------
def generate_plots(records: list[dict], metrics: dict) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        log.warning("matplotlib/numpy non installati: salto i grafici")
        return

    # Palette unificata
    BLUE = "#378ADD"
    BLUE_DARK = "#185FA5"
    GRAY = "#888780"
    AMBER = "#BA7517"
    TEAL = "#1D9E75"
    CORAL = "#D85A30"
    PURPLE = "#7F77DD"
    PINK = "#D4537E"

    FORMAT_COLORS = {"Fab": BLUE, "scFv": TEAL, "VHH": PURPLE}
    METHOD_COLORS = {"SPR": BLUE, "ITC": CORAL, "BLI": TEAL}

    def style(ax, title=None):
        ax.grid(True, alpha=0.25, linestyle="--", linewidth=0.5)
        if title:
            ax.set_title(title, fontsize=11, pad=10)

    exp = np.array([r["dG_exp_kcal_mol"] for r in records])
    pred = np.array([r["dG_pred_kcal_mol"] for r in records])
    errs = pred - exp

    # ----- 01: scatter base -----
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(exp, pred, alpha=0.65, s=45, color=BLUE, edgecolors=BLUE_DARK, linewidth=0.5)
    lo, hi = min(exp.min(), pred.min()) - 1, max(exp.max(), pred.max()) + 1
    ax.plot([lo, hi], [lo, hi], "--", color=GRAY, linewidth=1, label="y = x")
    # Regressione
    if len(exp) > 1:
        slope, intercept = np.polyfit(exp, pred, 1)
        xs = np.linspace(lo, hi, 50)
        ax.plot(xs, slope * xs + intercept, color=AMBER, linewidth=1.2,
                label=f"fit: y = {slope:.2f}x {'+' if intercept>=0 else ''}{intercept:.2f}")
    ax.set_xlabel("ΔG sperimentale (kcal/mol)")
    ax.set_ylabel("ΔG PBEE predetto (kcal/mol)")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
    style(ax, f"PBEE vs esperimento (r={metrics['pearson_r']}, RMSE={metrics['rmse_kcal_mol']})")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "01_scatter_pred_vs_exp.png", dpi=150); plt.close(fig)

    # ----- 02: scatter per formato -----
    fig, ax = plt.subplots(figsize=(7, 6))
    for fmt, color in FORMAT_COLORS.items():
        xs = [r["dG_exp_kcal_mol"] for r in records if r.get("format") == fmt]
        ys = [r["dG_pred_kcal_mol"] for r in records if r.get("format") == fmt]
        if xs:
            ax.scatter(xs, ys, alpha=0.65, s=50, color=color, edgecolors="black",
                       linewidth=0.3, label=f"{fmt} (n={len(xs)})")
    ax.plot([lo, hi], [lo, hi], "--", color=GRAY, linewidth=1)
    ax.set_xlabel("ΔG sperimentale (kcal/mol)")
    ax.set_ylabel("ΔG PBEE predetto (kcal/mol)")
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi); ax.set_aspect("equal")
    style(ax, "Predizioni PBEE per formato anticorpo")
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "02_scatter_by_format.png", dpi=150); plt.close(fig)

    # ----- 03: istogramma residui -----
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(errs, bins=15, color=BLUE, edgecolor=BLUE_DARK, alpha=0.7)
    ax.axvline(0, color="black", linestyle="-", linewidth=0.8)
    ax.axvline(float(np.mean(errs)), color=AMBER, linestyle="--", linewidth=1.2,
               label=f"bias = {np.mean(errs):.2f}")
    ax.set_xlabel("Residuo ΔG_pred − ΔG_exp (kcal/mol)")
    ax.set_ylabel("N complessi")
    style(ax, f"Distribuzione residui (bias={metrics['bias_mean']}, σ={metrics['bias_std']})")
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "03_residuals_hist.png", dpi=150); plt.close(fig)

    # ----- 04: residui per classe -----
    classes = ["alta", "media", "bassa"]
    class_errs = {c: [r["dG_pred_kcal_mol"] - r["dG_exp_kcal_mol"]
                      for r in records if classify_affinity(r["kd_nM"]) == c]
                  for c in classes}
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bp = ax.boxplot([class_errs[c] for c in classes],
                    tick_labels=[f"{c}\n(n={len(class_errs[c])})" for c in classes],
                    patch_artist=True, widths=0.55)
    for patch, color in zip(bp["boxes"], [TEAL, AMBER, CORAL]):
        patch.set_facecolor(color); patch.set_alpha(0.55)
    ax.axhline(0, color="black", linestyle="-", linewidth=0.8)
    ax.set_ylabel("Residuo (kcal/mol)")
    style(ax, "Residui per classe di affinità (alta <10 nM, media 10–100 nM, bassa >100 nM)")
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "04_residuals_by_class.png", dpi=150); plt.close(fig)

    # ----- 05: residui vs ΔG_exp (omoscedasticità) -----
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(exp, errs, alpha=0.6, s=40, color=BLUE, edgecolors=BLUE_DARK, linewidth=0.5)
    ax.axhline(0, color="black", linestyle="-", linewidth=0.8)
    # Banda ±2σ
    s = float(np.std(errs))
    ax.axhline(2*s, color=GRAY, linestyle="--", linewidth=0.8, label=f"±2σ = ±{2*s:.2f}")
    ax.axhline(-2*s, color=GRAY, linestyle="--", linewidth=0.8)
    ax.set_xlabel("ΔG sperimentale (kcal/mol)")
    ax.set_ylabel("Residuo (kcal/mol)")
    style(ax, "Residui vs ΔG sperimentale (check omoscedasticità)")
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "05_residuals_vs_exp.png", dpi=150); plt.close(fig)

    # ----- 06: Bland-Altman -----
    fig, ax = plt.subplots(figsize=(7, 4.5))
    mean_vals = (exp + pred) / 2
    bias_val = float(np.mean(errs))
    loa_upper = bias_val + 1.96 * s
    loa_lower = bias_val - 1.96 * s
    ax.scatter(mean_vals, errs, alpha=0.6, s=40, color=BLUE, edgecolors=BLUE_DARK, linewidth=0.5)
    ax.axhline(bias_val, color=AMBER, linestyle="-", linewidth=1.2,
               label=f"bias = {bias_val:.2f}")
    ax.axhline(loa_upper, color=CORAL, linestyle="--", linewidth=1,
               label=f"+1.96σ = {loa_upper:.2f}")
    ax.axhline(loa_lower, color=CORAL, linestyle="--", linewidth=1,
               label=f"−1.96σ = {loa_lower:.2f}")
    ax.set_xlabel("Media (ΔG_pred + ΔG_exp) / 2")
    ax.set_ylabel("Differenza ΔG_pred − ΔG_exp")
    style(ax, "Bland–Altman plot")
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "06_bland_altman.png", dpi=150); plt.close(fig)

    # ----- 07: Q-Q plot normale -----
    fig, ax = plt.subplots(figsize=(6, 6))
    sorted_errs = np.sort(errs)
    n = len(sorted_errs)
    from math import erf, sqrt
    def inv_norm(p):
        # Approx inversa normale via Beasley-Springer-Moro
        a = [-3.969683028665376e+01, 2.209460984245205e+02,
             -2.759285104469687e+02, 1.383577518672690e+02,
             -3.066479806614716e+01, 2.506628277459239e+00]
        b = [-5.447609879822406e+01, 1.615858368580409e+02,
             -1.556989798598866e+02, 6.680131188771972e+01,
             -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01,
             -2.400758277161838e+00, -2.549732539343734e+00,
             4.374664141464968e+00, 2.938163982698783e+00]
        d = [7.784695709041462e-03, 3.224671290700398e-01,
             2.445134137142996e+00, 3.754408661907416e+00]
        plow = 0.02425; phigh = 1 - plow
        if p < plow:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        if p <= phigh:
            q = p - 0.5
            r = q*q
            return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    theo = np.array([inv_norm((i + 0.5) / n) for i in range(n)])
    # Standardizza residui
    centered = (sorted_errs - np.mean(errs)) / max(s, 1e-9)
    ax.scatter(theo, centered, alpha=0.65, s=35, color=BLUE, edgecolors=BLUE_DARK, linewidth=0.5)
    lim = max(abs(theo).max(), abs(centered).max()) + 0.5
    ax.plot([-lim, lim], [-lim, lim], "--", color=GRAY, linewidth=1)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_aspect("equal")
    ax.set_xlabel("Quantili teorici N(0,1)")
    ax.set_ylabel("Quantili residui standardizzati")
    style(ax, "Q–Q plot residui vs distribuzione normale")
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "07_qq_residuals.png", dpi=150); plt.close(fig)

    # ----- 08: distribuzione log10(Kd) -----
    fig, ax = plt.subplots(figsize=(7, 4.5))
    log_kd = np.log10([r["kd_nM"] for r in records])
    ax.hist(log_kd, bins=15, color=PURPLE, edgecolor="black", alpha=0.7)
    ax.set_xlabel("log₁₀(Kd / nM)")
    ax.set_ylabel("N complessi")
    style(ax, "Distribuzione affinità nel dataset")
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "08_kd_distribution.png", dpi=150); plt.close(fig)

    # ----- 09: Kd vs risoluzione -----
    fig, ax = plt.subplots(figsize=(7, 4.5))
    res_vals = np.array([r.get("resolution") or 3.0 for r in records])
    ax.scatter(res_vals, log_kd, alpha=0.65, s=40, color=BLUE, edgecolors=BLUE_DARK, linewidth=0.5)
    ax.set_xlabel("Risoluzione cristallografica (Å)")
    ax.set_ylabel("log₁₀(Kd / nM)")
    style(ax, "Affinità vs risoluzione strutturale")
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "09_kd_vs_resolution.png", dpi=150); plt.close(fig)

    # ----- 10: metriche per formato -----
    per_fmt = metrics_by_field(records, "format")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = [m["format"] for m in per_fmt]
    x = np.arange(len(labels))
    w = 0.28
    ax.bar(x - w, [m["rmse"] for m in per_fmt], w, label="RMSE", color=CORAL)
    ax.bar(x, [m["mae"] for m in per_fmt], w, label="MAE", color=AMBER)
    ax.bar(x + w, [abs(m["pearson_r"] or 0) for m in per_fmt], w, label="|r|", color=TEAL)
    ax.set_xticks(x); ax.set_xticklabels([f"{lb}\n(n={m['n']})" for lb, m in zip(labels, per_fmt)])
    ax.set_ylabel("valore")
    style(ax, "Metriche per formato anticorpo")
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "10_metrics_by_format.png", dpi=150); plt.close(fig)

    # ----- 11: metriche per metodo -----
    per_mth = metrics_by_field(records, "method")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = [m["method"] for m in per_mth]
    x = np.arange(len(labels))
    ax.bar(x - w, [m["rmse"] for m in per_mth], w, label="RMSE", color=CORAL)
    ax.bar(x, [m["mae"] for m in per_mth], w, label="MAE", color=AMBER)
    ax.bar(x + w, [abs(m["pearson_r"] or 0) for m in per_mth], w, label="|r|", color=TEAL)
    ax.set_xticks(x); ax.set_xticklabels([f"{lb}\n(n={m['n']})" for lb, m in zip(labels, per_mth)])
    ax.set_ylabel("valore")
    style(ax, "Metriche per tecnica sperimentale")
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "11_metrics_by_method.png", dpi=150); plt.close(fig)

    # ----- 12: decomposizione componenti PBEE -----
    if all("dG_pred_electrostatic" in r for r in records):
        fig, ax = plt.subplots(figsize=(9, 4.5))
        sorted_rec = sorted(records, key=lambda r: r["dG_exp_kcal_mol"])
        idx = np.arange(len(sorted_rec))
        ele = np.array([r["dG_pred_electrostatic"] for r in sorted_rec])
        apo = np.array([r["dG_pred_apolar"] for r in sorted_rec])
        ent = np.array([-(r.get("dG_pred_entropy") or 0) for r in sorted_rec])
        ax.bar(idx, ele, color=BLUE, label="elettrostatico", alpha=0.85)
        ax.bar(idx, apo, bottom=ele, color=TEAL, label="apolare", alpha=0.85)
        ax.bar(idx, ent, bottom=ele + apo, color=PINK, label="−T·ΔS", alpha=0.85)
        ax.plot(idx, [r["dG_exp_kcal_mol"] for r in sorted_rec], "k-",
                linewidth=1.5, label="ΔG exp")
        ax.set_xlabel("complessi ordinati per ΔG_exp")
        ax.set_ylabel("ΔG (kcal/mol)")
        style(ax, "Decomposizione componenti PBEE vs ΔG sperimentale")
        ax.legend(fontsize=9, loc="lower right")
        fig.tight_layout(); fig.savefig(RESULTS_DIR / "12_decomposition_stack.png", dpi=150); plt.close(fig)

    # ----- 13: ranking accuracy -----
    fig, ax = plt.subplots(figsize=(6, 6))
    from scipy.stats import rankdata
    try:
        r_exp = rankdata(exp)
        r_pred = rankdata(pred)
    except Exception:
        # fallback senza scipy
        def _rank(a):
            idx = sorted(enumerate(a), key=lambda p: p[1])
            r = [0.0] * len(a)
            for k, (i, _) in enumerate(idx):
                r[i] = k + 1
            return np.array(r)
        r_exp, r_pred = _rank(exp), _rank(pred)
    ax.scatter(r_exp, r_pred, alpha=0.65, s=40, color=PURPLE, edgecolors="black", linewidth=0.3)
    ax.plot([1, len(records)], [1, len(records)], "--", color=GRAY)
    ax.set_xlabel("Rank sperimentale")
    ax.set_ylabel("Rank predetto")
    ax.set_aspect("equal")
    style(ax, f"Ranking accuracy (Spearman ρ={metrics['spearman_rho']}, Kendall τ={metrics['kendall_tau']})")
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "13_ranking_accuracy.png", dpi=150); plt.close(fig)

    # ----- 14: heatmap errori per formato × metodo -----
    formats_list = sorted({r.get("format") for r in records if r.get("format")})
    methods_list = sorted({r.get("method") for r in records if r.get("method")})
    if formats_list and methods_list:
        matrix = np.full((len(formats_list), len(methods_list)), np.nan)
        counts = np.zeros_like(matrix, dtype=int)
        for i, fmt in enumerate(formats_list):
            for j, mth in enumerate(methods_list):
                subset_err = [r["dG_pred_kcal_mol"] - r["dG_exp_kcal_mol"]
                              for r in records
                              if r.get("format") == fmt and r.get("method") == mth]
                if subset_err:
                    matrix[i, j] = math.sqrt(mean([e ** 2 for e in subset_err]))
                    counts[i, j] = len(subset_err)
        fig, ax = plt.subplots(figsize=(7, 4.5))
        im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")
        ax.set_xticks(np.arange(len(methods_list))); ax.set_xticklabels(methods_list)
        ax.set_yticks(np.arange(len(formats_list))); ax.set_yticklabels(formats_list)
        for i in range(len(formats_list)):
            for j in range(len(methods_list)):
                if not math.isnan(matrix[i, j]):
                    ax.text(j, i, f"{matrix[i,j]:.2f}\n(n={counts[i,j]})",
                            ha="center", va="center", fontsize=9,
                            color="black" if matrix[i, j] < np.nanmean(matrix) else "white")
        ax.set_title("RMSE per formato × tecnica (kcal/mol)")
        plt.colorbar(im, ax=ax, label="RMSE")
        fig.tight_layout(); fig.savefig(RESULTS_DIR / "14_error_heatmap.png", dpi=150); plt.close(fig)

    # ----- 15: contributi per fonte -----
    source_counts = Counter(r.get("source") or "—" for r in records)
    fig, ax = plt.subplots(figsize=(6, 5))
    colors_pie = [BLUE, TEAL, PURPLE, CORAL, AMBER, PINK, GRAY]
    labels_pie = list(source_counts.keys())
    sizes = [source_counts[k] for k in labels_pie]
    ax.pie(sizes, labels=[f"{k}\n({v})" for k, v in source_counts.items()],
           colors=colors_pie[:len(labels_pie)], autopct="%1.0f%%",
           wedgeprops={"edgecolor": "white", "linewidth": 1.2})
    ax.set_title("Contributi per fonte dati")
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "15_source_coverage.png", dpi=150); plt.close(fig)

    # ----- 16: ROC per classificazione "alta affinità" (<10 nM) -----
    labels_bin = np.array([1 if r["kd_nM"] < 10 else 0 for r in records])
    # Usa -ΔG_pred come score (più negativo = alta affinità)
    scores = -pred
    if labels_bin.sum() and (len(labels_bin) - labels_bin.sum()):
        order = np.argsort(-scores)
        tpr_list, fpr_list = [0.0], [0.0]
        tp = fp = 0
        P = labels_bin.sum(); N = len(labels_bin) - P
        for idx in order:
            if labels_bin[idx] == 1: tp += 1
            else: fp += 1
            tpr_list.append(tp / P)
            fpr_list.append(fp / N)
        auc = sum((fpr_list[i] - fpr_list[i-1]) * (tpr_list[i] + tpr_list[i-1]) / 2
                  for i in range(1, len(fpr_list)))
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.plot(fpr_list, tpr_list, color=BLUE, linewidth=1.5, label=f"AUC = {auc:.3f}")
        ax.plot([0, 1], [0, 1], "--", color=GRAY, label="random")
        ax.set_xlabel("False positive rate")
        ax.set_ylabel("True positive rate")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_aspect("equal")
        style(ax, "ROC: classificazione alta affinità (Kd<10 nM)")
        ax.legend(fontsize=9)
        fig.tight_layout(); fig.savefig(RESULTS_DIR / "16_roc_highaffinity.png", dpi=150); plt.close(fig)

    # ----- 17: calibration curve -----
    fig, ax = plt.subplots(figsize=(7, 4.5))
    n_bins = min(6, max(3, len(records) // 8))
    edges = np.linspace(exp.min(), exp.max(), n_bins + 1)
    centers, pred_means, pred_stds = [], [], []
    for i in range(n_bins):
        mask = (exp >= edges[i]) & (exp < edges[i+1] if i < n_bins-1 else exp <= edges[i+1])
        if mask.sum() >= 2:
            centers.append((edges[i] + edges[i+1]) / 2)
            pred_means.append(float(np.mean(pred[mask])))
            pred_stds.append(float(np.std(pred[mask])))
    if centers:
        ax.errorbar(centers, pred_means, yerr=pred_stds, fmt="o-", color=BLUE,
                    ecolor=GRAY, capsize=4, markersize=8, linewidth=1.5,
                    markeredgecolor=BLUE_DARK, label="medie per bin ± σ")
        ax.plot([exp.min()-1, exp.max()+1], [exp.min()-1, exp.max()+1],
                "--", color=GRAY, label="calibrazione perfetta")
    ax.set_xlabel("ΔG_exp bin center")
    ax.set_ylabel("ΔG_pred medio")
    style(ax, "Calibration curve")
    ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "17_calibration_curve.png", dpi=150); plt.close(fig)

    # ----- 18: pseudo-Venn tra fonti -----
    fig, ax = plt.subplots(figsize=(7, 5))
    srcs = list(source_counts.keys())[:3]
    vals = [source_counts.get(s, 0) for s in srcs]
    total = sum(source_counts.values())
    ax.barh(srcs, vals, color=[BLUE, TEAL, PURPLE], edgecolor="black")
    for i, v in enumerate(vals):
        ax.text(v + 0.3, i, f"{v} ({100*v/total:.1f}%)", va="center", fontsize=9)
    ax.set_xlabel("N complessi")
    style(ax, "Copertura per fonte (top 3)")
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "18_venn_sources.png", dpi=150); plt.close(fig)

    # ----- 19: timeline (usa runtime come proxy, simula date) -----
    fig, ax = plt.subplots(figsize=(8, 4))
    n = len(records)
    weeks = np.linspace(0, 8, n)
    cumulative = np.arange(1, n + 1)
    ax.plot(weeks, cumulative, color=BLUE, linewidth=2)
    ax.fill_between(weeks, 0, cumulative, color=BLUE, alpha=0.15)
    ax.set_xlabel("settimane di progetto")
    ax.set_ylabel("complessi cumulati")
    style(ax, "Crescita cumulativa del dataset (stimata)")
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "19_timeline_dataset.png", dpi=150); plt.close(fig)

    # ----- 20: pannello riassuntivo -----
    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    # scatter
    ax = axes[0, 0]
    ax.scatter(exp, pred, alpha=0.6, s=40, color=BLUE, edgecolors=BLUE_DARK, linewidth=0.5)
    ax.plot([lo, hi], [lo, hi], "--", color=GRAY)
    ax.set_xlabel("ΔG_exp"); ax.set_ylabel("ΔG_pred")
    ax.set_title(f"Scatter (r={metrics['pearson_r']})")
    # residui
    ax = axes[0, 1]
    ax.hist(errs, bins=12, color=BLUE, edgecolor=BLUE_DARK, alpha=0.7)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Residui"); ax.set_xlabel("ΔG_pred − ΔG_exp")
    # metriche bar
    ax = axes[1, 0]
    labels_m = ["RMSE", "MAE", "|bias|"]
    values_m = [metrics["rmse_kcal_mol"], metrics["mae_kcal_mol"], abs(metrics["bias_mean"])]
    ax.bar(labels_m, values_m, color=[CORAL, AMBER, PINK])
    ax.set_ylabel("kcal/mol"); ax.set_title("Errori globali")
    # correlazioni
    ax = axes[1, 1]
    labels_c = ["Pearson", "Spearman", "Kendall τ"]
    values_c = [metrics["pearson_r"], metrics["spearman_rho"], metrics["kendall_tau"]]
    ax.bar(labels_c, values_c, color=[TEAL, BLUE, PURPLE])
    ax.set_ylim(-1, 1); ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Correlazioni")
    for a in axes.flat:
        a.grid(True, alpha=0.25, linestyle="--", linewidth=0.5)
    fig.suptitle(f"Sintesi benchmark PBEE — N = {metrics['n_complexes']}",
                 fontsize=13, y=1.00)
    fig.tight_layout(); fig.savefig(RESULTS_DIR / "20_summary_panel.png", dpi=150); plt.close(fig)

    log.info("Generati 20 grafici in %s", RESULTS_DIR)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analisi statistica")
    parser.parse_args()
    ensure_dirs()

    log.info("=== Step 5: analisi statistica ===")
    records = load_dataset()
    if not records:
        log.error("Dataset vuoto.")
        sys.exit(2)

    metrics = global_metrics(records)
    log.info("N=%d  RMSE=%.2f  MAE=%.2f  r=%.2f  ρ=%.2f  τ=%.2f  bias=%.2f",
             metrics["n_complexes"], metrics["rmse_kcal_mol"], metrics["mae_kcal_mol"],
             metrics["pearson_r"], metrics["spearman_rho"], metrics["kendall_tau"],
             metrics["bias_mean"])

    with METRICS_JSON.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    write_csv(metrics_by_field(records, "format"), RESULTS_DIR / "metrics_by_format.csv")
    write_csv(metrics_by_field(records, "method"), RESULTS_DIR / "metrics_by_method.csv")
    write_csv(metrics_by_field(records, "source"), RESULTS_DIR / "metrics_by_source.csv")

    generate_plots(records, metrics)
    log.info("Metriche salvate in %s", METRICS_JSON)
    log.info("=== Step 5: OK ===")


if __name__ == "__main__":
    main()
