"""Step 1 — Costruzione del dataset anticorpo/ScFv–antigene.

Modalità:
  - online (default): interroga RCSB PDB + PubMed + BindingDB in tempo reale,
                      con cache locale, ricade su SAbDab se disponibile.
  - simulated:        genera 48 complessi fittizi con seed fisso (offline).
  - sabdab:           usa solo un file TSV SAbDab già scaricato.

Tutti i record sono salvati in data/dataset_raw.csv.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (DATA_DIR, DATASET_RAW, ensure_dirs, get_logger,
                   parse_affinity_string, seeded_random)

log = get_logger("01_build")


def generate_simulated(n: int = 48, seed: int = 42) -> list[dict]:
    rng = seeded_random(seed)
    ANTIGENS = [
        "HIV-1 gp120", "SARS-CoV-2 RBD", "HER2 ECD", "Influenza HA",
        "PD-1", "PD-L1", "Lysozyme", "VEGF-A", "TNF-alpha", "CD20",
        "EGFR", "IL-6", "CTLA-4", "IL-17A", "RSV F", "CD19",
        "BCMA", "CD38", "IL-4Ra", "GITR", "TIGIT", "LAG-3",
    ]
    FORMATS = ["Fab", "scFv", "VHH"]
    METHODS = ["SPR", "ITC", "BLI"]
    SOURCES = ["SAbDab", "SAAINT-DB", "ANDD", "Literature"]
    SPECIES = ["human", "mouse", "llama"]

    out = []
    for _ in range(n):
        kd_nm = 10 ** (rng.uniform(-1, 4))   # 0.1 nM – 10 µM
        out.append({
            "pdb": f"{rng.randint(1, 9):x}{rng.choice('abcdefghij')}{rng.randint(10, 99)}",
            "format": rng.choice(FORMATS),
            "antigen": rng.choice(ANTIGENS),
            "kd_nM": round(kd_nm, 3),
            "method": rng.choice(METHODS),
            "source": rng.choice(SOURCES),
            "resolution": round(rng.uniform(1.7, 3.3), 1),
            "temperature_K": rng.choice([293.15, 298.15, 310.15]),
            "ph": round(rng.uniform(7.0, 7.5), 1),
            "species": rng.choice(SPECIES),
            "pubmed_id": "",
        })
    log.info("Generati %d complessi simulati", n)
    return out


def build_from_rcsb(max_hits: int) -> list[dict]:
    """Interroga SAbDab e costruisce i record con dati di affinità."""
    from sources import (RemoteUnavailable, fetch_pdb_metadata,
                         guess_format_and_antigen, search_antibody_complexes,
                         load_sabdab_summary, fetch_bindingdb_for_pdb,
                         get_best_bindingdb_affinity, parse_affinity_string)

    # Ottieni PDB ID da SAbDab
    from utils import DATA_DIR
    sabdab_path = DATA_DIR / "sabdab_summary.tsv"
    pdb_ids = search_antibody_complexes(max_hits=max_hits, sabdab_path=sabdab_path)
    log.info("SAbDab: %d candidati", len(pdb_ids))
    
    # Carica dati completi SAbDab per ottenere affinità
    sabdab_data = load_sabdab_summary(tsv_path=sabdab_path)
    sabdab_lookup = {}
    if sabdab_data:
        for entry in sabdab_data:
            pdb_id = entry.get('pdb', '').lower()
            if pdb_id:
                sabdab_lookup[pdb_id] = entry

    rows = []
    for i, pdb_id in enumerate(pdb_ids, start=1):
        meta = {}
        try:
            meta = fetch_pdb_metadata(pdb_id)
        except RemoteUnavailable as e:
            log.warning("  %s: meta non disponibile (%s)", pdb_id, e)

        fmt, antigen, resolution = guess_format_and_antigen(meta) if meta else ("unknown", "unknown", 3.0)
        
        # Usa dati di affinità da SAbDab o, in mancanza, da BindingDB.
        kd_nm = None
        method = ""
        source = ""
        
        sabdab_entry = sabdab_lookup.get(pdb_id)
        if sabdab_entry:
            # Estrai affinità da SAbDab
            affinity_str = sabdab_entry.get('affinity', '')
            if affinity_str:
                kd_nm = parse_affinity_string(affinity_str)
            
            # Estrai metodo da SAbDab
            method = sabdab_entry.get('method', '')
            
            # Usa antigene da SAbDab se disponibile
            sabdab_antigen = sabdab_entry.get('antigen_name', '')
            if sabdab_antigen and sabdab_antigen != '':
                antigen = sabdab_antigen
            
            # Usa formato da SAbDab se disponibile
            sabdab_format = sabdab_entry.get('format', '')
            if sabdab_format and sabdab_format != '':
                fmt = sabdab_format

        if kd_nm is None:
            bd_entries = fetch_bindingdb_for_pdb(pdb_id)
            if bd_entries:
                bd_kd, bd_entry, bd_key = get_best_bindingdb_affinity(bd_entries)
                if bd_kd is not None:
                    kd_nm = bd_kd
                    method = method or f"BindingDB ({bd_key})"
                    source = "BindingDB"
                    log.info("  %s: affinity trovata in BindingDB %s = %.3f nM", pdb_id, bd_key, kd_nm)

        if kd_nm is None:
            log.warning("  %s: skip (no affinity found in SAbDab/BindingDB)", pdb_id)
            continue

        if not source:
            source = "SAbDab"

        # Usa specie dell'anticorpo da SAbDab se disponibile, altrimenti fallback a PDB metadata
        if sabdab_entry:
            heavy_species = sabdab_entry.get('heavy_species', '').lower()
            light_species = sabdab_entry.get('light_species', '').lower()
            species = heavy_species or light_species or "unknown"
        else:
            # Fallback: estrai specie dai metadati PDB
            entry = (meta.get("data") or {}).get("entry") or {}
            species = "unknown"
            for e in (entry.get("polymer_entities") or []):
                org = (e.get("rcsb_entity_source_organism") or [{}])
                if org and isinstance(org, list) and org[0].get("scientific_name"):
                    species = org[0]["scientific_name"].split()[0].lower()
                    break

        # Estrai PubMed ID per riferimento
        citations = entry.get("citation") or []
        pmid = ""
        for c in citations:
            if c.get("pdbx_database_id_PubMed"):
                pmid = str(c["pdbx_database_id_PubMed"])
                break

        rows.append({
            "pdb": pdb_id,
            "format": fmt,
            "antigen": antigen,
            "kd_nM": round(float(kd_nm), 3),
            "method": method or "SPR",  # usa metodo da SAbDab o fallback
            "source": source,
            "resolution": resolution or 3.0,
            "temperature_K": 298.15,
            "ph": 7.4,
            "species": species,
            "pubmed_id": pmid,
        })
        log.info("  %s  Kd=%.3f nM  fmt=%s  res=%s  method=%s", pdb_id, kd_nm, fmt, resolution, method)

    return rows


def build_from_sabdab(tsv_path: Path) -> list[dict]:
    """Parsa SAbDab summary TSV e filtra per affinità numerica."""
    from sources import load_sabdab_summary

    raw = load_sabdab_summary(tsv_path)
    log.info("SAbDab: %d righe caricate", len(raw))

    rows = []
    for r in raw:
        kd_nm = parse_affinity_string(r.get("affinity") or "")
        if kd_nm is None:
            continue
        try:
            resolution = float(r.get("resolution") or "3.0")
        except ValueError:
            resolution = 3.0
        rows.append({
            "pdb": (r.get("pdb") or "").lower(),
            "format": "Fab" if r.get("Lchain") else "VHH",
            "antigen": (r.get("antigen_name") or "unknown")[:80],
            "kd_nM": round(kd_nm, 3),
            "method": r.get("method") or "SPR",
            "source": "SAbDab",
            "resolution": resolution,
            "temperature_K": 298.15,
            "ph": 7.4,
            "species": (r.get("heavy_species") or "unknown").lower(),
            "pubmed_id": "",
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Costruzione dataset Ab–Ag")
    parser.add_argument("--mode", choices=["online", "simulated", "sabdab"],
                        default="online", help="Modalità di costruzione")
    parser.add_argument("--n", type=int, default=48,
                        help="Numero complessi (simulated) o hit max (online)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sabdab-path", type=Path, default=None,
                        help="File TSV SAbDab (modalità sabdab)")
    parser.add_argument("--fallback-simulated", action="store_true",
                        help="Se online fallisce, usa dati simulati")
    args = parser.parse_args()

    ensure_dirs()
    log.info("=== Step 1: costruzione dataset (mode=%s) ===", args.mode)

    rows: list[dict] = []
    if args.mode == "online":
        try:
            rows = build_from_rcsb(max_hits=args.n)
        except Exception as e:
            log.warning("Modalità online fallita: %s", e)
            rows = []
        if len(rows) < 5 and args.fallback_simulated:
            log.warning("Poche hit (%d): fallback a dati simulati", len(rows))
            rows = generate_simulated(n=args.n, seed=args.seed)
        elif not rows:
            log.error("Modalità online non ha prodotto risultati usabili.")
            log.error("Rilancia con --mode simulated oppure --fallback-simulated")
            sys.exit(2)
    elif args.mode == "sabdab":
        if not args.sabdab_path or not args.sabdab_path.exists():
            log.error("Specificare --sabdab-path con un file TSV esistente")
            sys.exit(2)
        rows = build_from_sabdab(args.sabdab_path)
    else:
        rows = generate_simulated(n=args.n, seed=args.seed)

    if not rows:
        log.error("Nessun record prodotto.")
        sys.exit(2)

    with DATASET_RAW.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    log.info("Scritti %d record in %s", len(rows), DATASET_RAW)
    log.info("=== Step 1: OK ===")


if __name__ == "__main__":
    main()
