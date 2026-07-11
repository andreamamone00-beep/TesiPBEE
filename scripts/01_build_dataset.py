"""Step 1 — Costruzione del dataset anticorpo/ScFv–antigene.

Modalità:
  - online (default): usa esclusivamente SAbDab (summary TSV locale o remoto)
                      per selezionare i PDB id e le affinità, con metadata PDB ausiliari.
  - simulated:        genera 48 complessi fittizi con seed fisso (offline).
  - sabdab:           usa solo un file TSV SAbDab già scaricato.

Tutti i record sono salvati in data/dataset_raw.csv.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils import (DATA_DIR, DATASET_RAW, PROJECT_ROOT, ensure_dirs, get_logger,
                   parse_affinity_string, seeded_random)

from sources import fetch_pdbbind_affinity

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
    SOURCES = ["SAbDab"]
    SPECIES = ["human", "mouse"]

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
    """Usa il summary SAbDab remoto per selezionare i record del dataset."""
    from sources import (RemoteUnavailable, fetch_pdb_metadata,
                         guess_format_and_antigen, search_antibody_complexes,
                         load_sabdab_summary, parse_affinity_string)

    # Ottieni un pool più ampio di PDB ID da SAbDab online, poi verifichiamo KD su PDBBind.
    candidate_pool = max(150, max_hits * 5)
    pdb_ids = search_antibody_complexes(max_hits=candidate_pool, sabdab_path=None)
    log.info("SAbDab online: %d candidati", len(pdb_ids))

    # Carica il summary SAbDab online per convalidare l'esistenza dei PDB e i metadati.
    sabdab_data = load_sabdab_summary(tsv_path=None)
    online_set = {entry.get('pdb', '').lower() for entry in sabdab_data if entry.get('pdb')}
    sabdab_lookup = {}
    if sabdab_data:
        for entry in sabdab_data:
            pdb_id = entry.get('pdb', '').lower()
            if pdb_id:
                sabdab_lookup[pdb_id] = entry

    target_organisms = {'human', 'homo sapiens', 'mouse', 'mus musculus'}
    rows = []
    for i, pdb_id in enumerate(pdb_ids, start=1):
        meta = {}
        try:
            meta = fetch_pdb_metadata(pdb_id)
        except RemoteUnavailable as e:
            log.warning("  %s: meta non disponibile (%s)", pdb_id, e)

        fmt, antigen, resolution = guess_format_and_antigen(meta) if meta else ("unknown", "unknown", 3.0)
        
        sabdab_entry = sabdab_lookup.get(pdb_id)
        if not sabdab_entry:
            log.warning("  %s: skip (entry SAbDab locale non trovata)", pdb_id)
            continue
        # Se disponbile la lista online, assicurati che il PDB sia effettivamente presente su SAbDab
        if online_set and pdb_id not in online_set:
            log.warning("  %s: skip (non presente nella lista SAbDab online)", pdb_id)
            continue

        heavy_species = (sabdab_entry.get('heavy_species') or '').strip().lower()
        light_species = (sabdab_entry.get('light_species') or '').strip().lower()
        species_list = [s for s in (heavy_species, light_species) if s]
        if not any(spec in target_organisms for spec in species_list):
            log.warning("  %s: skip (species non umana/murina: %s)", pdb_id, species_list)
            continue
        species = species_list[0]

        affinity_str = sabdab_entry.get('affinity', '')
        kd_nm, kd_source = fetch_pdbbind_affinity(pdb_id)
        if kd_nm is None or kd_nm <= 0:
            kd_nm = parse_affinity_string(affinity_str) if affinity_str else None
            kd_source = "SAbDab"
        if kd_nm is None or kd_nm <= 0:
            log.warning("  %s: skip (nessuna affinità valida in PDBBind/SAbDab)", pdb_id)
            continue

        method = sabdab_entry.get('method', '')
        sabdab_antigen = sabdab_entry.get('antigen_name', '')
        if sabdab_antigen:
            antigen = sabdab_antigen
        sabdab_format = sabdab_entry.get('format', '')
        if sabdab_format:
            fmt = sabdab_format

        source = "SAbDab"

        # Estrai PubMed ID per riferimento
        entry = (meta.get("data") or {}).get("entry") or {}
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
            "kd_nM": float(kd_nm),
            "method": method or "SPR",  # usa metodo da SAbDab
            "source": source,
            "resolution": resolution or 3.0,
            "temperature_K": 298.15,
            "ph": 7.4,
            "species": species,
            "pubmed_id": pmid,
        })
        log.info("  %s  Kd=%.3f nM  fmt=%s  res=%s  method=%s  source=%s", pdb_id, kd_nm, fmt, resolution, method, kd_source)
        if len(rows) >= max_hits:
            break

    return rows


def build_from_sabdab(tsv_path: Path, max_hits: Optional[int] = None) -> list[dict]:
    """Parsa SAbDab summary TSV e filtra per specie umane/murine con affinità numerica."""
    from sources import load_sabdab_summary

    raw = load_sabdab_summary(tsv_path)
    log.info("SAbDab: %d righe caricate", len(raw))

    target_organisms = {'human', 'homo sapiens', 'mouse', 'mus musculus'}
    rows = []
    for r in raw:
        pdb_id = (r.get("pdb") or "").lower()
        if not pdb_id:
            continue

        # Fonte di verità: il TSV locale SAbDab; non usiamo PDBBind come requisito
        # per accettare un record.
        kd_nm = parse_affinity_string(r.get("affinity") or "")
        if kd_nm is None or kd_nm <= 0:
            # Tentativo best-effort da PDBBind se l'affinità SAbDab è assente o non parsabile
            kd_nm, _ = fetch_pdbbind_affinity(pdb_id)
        if kd_nm is None or kd_nm <= 0:
            continue
        heavy_species = (r.get("heavy_species") or "").strip().lower()
        light_species = (r.get("light_species") or "").strip().lower()
        species_list = [s for s in (heavy_species, light_species) if s]
        if not any(spec in target_organisms for spec in species_list):
            continue
        try:
            resolution = float(r.get("resolution") or "3.0")
        except ValueError:
            resolution = 3.0
        rows.append({
            "pdb": pdb_id,
            "format": "Fab" if r.get("Lchain") else "VHH",
            "antigen": (r.get("antigen_name") or "unknown")[:80],
            "kd_nM": float(kd_nm),
            "method": r.get("method") or "SPR",
            "source": "SAbDab",
            "resolution": resolution,
            "temperature_K": 298.15,
            "ph": 7.4,
            "species": species_list[0] if species_list else "unknown",
            "pubmed_id": "",
        })
    if max_hits is not None:
        rows = rows[:max_hits]
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Costruzione dataset Ab–Ag")
    parser.add_argument("--mode", choices=["online", "simulated", "sabdab"],
                        default="online", help="Modalità di costruzione")
    parser.add_argument("--n", type=int, default=50,
                        help="Numero complessi (simulated) o hit max (online)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sabdab-path", type=Path, default=None,
                        help="File TSV SAbDab (modalità sabdab)")
    args = parser.parse_args()

    if args.mode in ("online", "sabdab") and args.n < 50:
        args.n = 50

    ensure_dirs()
    log.info("=== Step 1: costruzione dataset (mode=%s, n=%d) ===", args.mode, args.n)

    rows: list[dict] = []
    if args.mode == "online":
        try:
            rows = build_from_rcsb(max_hits=args.n)
        except Exception as e:
            log.warning("Modalità online fallita: %s", e)
            rows = []
        if not rows:
            log.error("Modalità online non ha prodotto risultati usabili.")
            log.error("Rilancia con --mode sabdab e --sabdab-path <summary.tsv> oppure usa --mode simulated per dati di test.")
            sys.exit(2)
    elif args.mode == "sabdab":
        sabdab_path = args.sabdab_path
        if sabdab_path is None:
            sabdab_path = DATA_DIR / "sabdab_summary.tsv"
        if not sabdab_path.is_absolute():
            sabdab_path = (PROJECT_ROOT / sabdab_path).resolve()
        if not sabdab_path.exists():
            log.error("Specificare --sabdab-path con un file TSV esistente")
            sys.exit(2)
        rows = build_from_sabdab(sabdab_path, max_hits=args.n)
    else:
        rows = generate_simulated(n=args.n, seed=args.seed)

    if not rows:
        log.error("Nessun record prodotto.")
        sys.exit(2)

    if args.mode in ("online", "sabdab") and len(rows) < 50:
        log.error("Non sono stati generati almeno 50 record SAbDab umani/murini.")
        sys.exit(2)

    with DATASET_RAW.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    log.info("Scritti %d record in %s", len(rows), DATASET_RAW)
    log.info("=== Step 1: OK ===")


if __name__ == "__main__":
    main()
