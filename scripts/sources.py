"""Client per le API pubbliche usate dalla pipeline.

Fonti integrate:
  - RCSB PDB Search API + Data API  (dati strutturali)
  - PDBe REST API                    (dettagli secondari)
  - NCBI E-utilities (PubMed)        (letteratura associata)
  - BindingDB REST                   (dati di affinità per UniProt)
  - SAbDab summary TSV               (anticorpi con affinità curate)

Ogni client è progettato per funzionare anche OFFLINE: se la rete non è
raggiungibile, viene sollevata un'eccezione RemoteUnavailable e la pipeline
può fare fallback su dati simulati.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils import RateLimiter, cache_key, cached_json, get_logger, parse_affinity_string

log = get_logger("sources")

HTTP_TIMEOUT = 15  # secondi
USER_AGENT = "AbAg-PBEE-Prototype/1.0 (tesi Andrea Mamone; didattico)"


class RemoteUnavailable(RuntimeError):
    """Rete non disponibile o endpoint non raggiungibile."""


def _http_get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError) as e:
        raise RemoteUnavailable(f"GET {url}: {e}") from e


def _http_post_json(url: str, payload: dict, headers: dict | None = None) -> bytes:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json",
                 **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError) as e:
        raise RemoteUnavailable(f"POST {url}: {e}") from e


# ---------------------------------------------------------------------------
# RCSB PDB
# ---------------------------------------------------------------------------
RCSB_SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
RCSB_GRAPHQL = "https://data.rcsb.org/graphql"

_limiter_rcsb = RateLimiter(0.4)


def search_antibody_complexes(max_hits: int = 50) -> list[str]:
    """Cerca strutture PDB di complessi anticorpo-antigene da SAbDab.

    Strategy: Usa SAbDab come fonte primaria:
    1. Download SAbDab summary TSV (~10MB)
    2. Filtra per strutture con dati di affinità
    3. Estrai PDB ID di complessi validi
    4. Ritorna max_hits PDB ID di veri complessi Ab-Ag con affinità
    """
    
    # Carica dati SAbDab
    sabdab_data = load_sabdab_summary()
    if not sabdab_data:
        log.warning("SAbDab non disponibile: fallback a simulazione")
        return []
    
    # Filtra per strutture con dati di affinità reali e PDB disponibili
    valid_entries = {}
    for entry in sabdab_data:
        if entry.get('pdb') and entry.get('affinity') and entry.get('affinity') != '' and entry.get('affinity') != 'None':
            pdb_id = entry['pdb'].lower()
            # Controlla che sia un complesso (antigene definito)
            if entry.get('antigen_name') and entry.get('antigen_name') != '':
                # Usa un dict per evitare duplicati, mantieni il migliore (miglior risoluzione)
                if pdb_id not in valid_entries:
                    valid_entries[pdb_id] = {
                        'pdb': pdb_id,
                        'antigen': entry.get('antigen_name', ''),
                        'affinity': entry.get('affinity', ''),
                        'method': entry.get('method', ''),
                        'resolution': entry.get('resolution', ''),
                        'format': entry.get('format', ''),
                        'hchain': entry.get('Hchain', ''),
                        'lchain': entry.get('Lchain', '')
                    }
    
    # Ordina per risoluzione (preferisce strutture ad alta risoluzione)
    def get_resolution(res_str):
        try:
            if res_str and res_str != '' and res_str != 'NOT':
                return float(res_str)
            return 999
        except ValueError:
            return 999
    
    sorted_entries = sorted(valid_entries.values(), key=lambda x: get_resolution(x['resolution']))
    
    # Prendi i primi max_hits
    selected_entries = sorted_entries[:max_hits]
    pdb_ids = [entry['pdb'] for entry in selected_entries]
    
    log.info(f"SAbDab: trovati {len(sabdab_data)} totali, {len(valid_entries)} con affinità, selezionati {len(pdb_ids)}")
    
    return pdb_ids


def fetch_pdb_metadata(pdb_id: str) -> dict[str, Any]:
    """Recupera metadati di una entry PDB via GraphQL Data API."""
    pdb_id = pdb_id.lower()
    query = """
    query($id: String!) {
      entry(entry_id: $id) {
        rcsb_id
        struct { title }
        rcsb_entry_info {
          resolution_combined
          experimental_method
          polymer_entity_count_protein
        }
        polymer_entities {
          rcsb_polymer_entity { pdbx_description }
          entity_poly { pdbx_seq_one_letter_code_can }
          rcsb_entity_source_organism { scientific_name }
          rcsb_polymer_entity_container_identifiers { asym_ids auth_asym_ids }
        }
        citation { pdbx_database_id_PubMed title journal_abbrev }
      }
    }
    """

    def fetcher():
        _limiter_rcsb.wait()
        raw = _http_post_json(RCSB_GRAPHQL, {"query": query, "variables": {"id": pdb_id.upper()}})
        return json.loads(raw)

    key = cache_key("rcsb_entry", pdb_id)
    return cached_json(key, fetcher)


def guess_format_and_antigen(meta: dict) -> tuple[str, str, float | None]:
    """Da un record GraphQL RCSB deduce formato anticorpo, antigene, risoluzione."""
    entry = (meta or {}).get("data", {}).get("entry") or meta.get("entry")
    if not entry:
        return "Fab", "unknown", None

    info = entry.get("rcsb_entry_info") or {}
    resolution = None
    res_list = info.get("resolution_combined")
    if isinstance(res_list, list) and res_list:
        resolution = float(res_list[0])
    elif isinstance(res_list, (int, float)):
        resolution = float(res_list)

    entities = entry.get("polymer_entities") or []
    ab_keywords = ("heavy chain", "light chain", "fab", "fv", "scfv", "immunoglobulin",
                   "antibody", "nanobody", "vhh", "variable region")
    ag_candidate = "unknown"
    has_heavy = False
    has_light = False
    has_linker = False

    for e in entities:
        desc = ((e.get("rcsb_polymer_entity") or {}).get("pdbx_description") or "").lower()
        seq = ((e.get("entity_poly") or {}).get("pdbx_seq_one_letter_code_can") or "")
        if any(k in desc for k in ab_keywords):
            if "heavy" in desc or "vh" in desc:
                has_heavy = True
            if "light" in desc or "vl" in desc or "kappa" in desc or "lambda" in desc:
                has_light = True
            # Un linker "GGGGS" ripetuto è segno di scFv
            if "ggggs" in seq.lower():
                has_linker = True
        else:
            if ag_candidate == "unknown" and desc:
                ag_candidate = desc.split(",")[0][:60]

    if has_linker:
        fmt = "scFv"
    elif has_heavy and not has_light:
        fmt = "VHH"
    elif has_heavy and has_light:
        fmt = "Fab"
    else:
        fmt = "Fab"  # default prudenziale
    return fmt, ag_candidate, resolution


# ---------------------------------------------------------------------------
# PubMed (NCBI E-utilities)
# ---------------------------------------------------------------------------
EUTIL_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_limiter_ncbi = RateLimiter(0.4)  # NCBI: 3 req/sec senza API key


def fetch_pubmed_abstract(pmid: str) -> str:
    """Scarica un abstract PubMed."""
    if not pmid:
        return ""

    def fetcher():
        _limiter_ncbi.wait()
        url = (f"{EUTIL_BASE}/efetch.fcgi?db=pubmed&id={pmid}"
               f"&rettype=abstract&retmode=text")
        raw = _http_get(url)
        return {"text": raw.decode("utf-8", errors="replace")}

    key = cache_key("pubmed_abstract", pmid)
    try:
        return cached_json(key, fetcher).get("text", "")
    except RemoteUnavailable:
        return ""


def extract_kd_from_text(text: str) -> float | None:
    """Estrae un valore di Kd da un testo libero (abstract/methods).

    Ricerca pattern tipo 'Kd = 3.2 nM', 'KD of 0.5 µM', '2.1e-9 M', ecc.
    Ritorna Kd in nanomolare oppure None.
    """
    if not text:
        return None
    import re
    patterns = [
        r"K[dD]\s*(?:of|=|~)?\s*([\d.]+(?:[eE][-+]?\d+)?)\s*(nM|µM|uM|pM|mM|M)",
        r"dissociation\s+constant\s*(?:of|=|~)?\s*([\d.]+)\s*(nM|µM|uM|pM|mM|M)",
        r"affinity\s*(?:of|=|~)?\s*([\d.]+)\s*(nM|µM|uM|pM|mM|M)",
    ]
    unit_to_nm = {"nm": 1.0, "um": 1e3, "µm": 1e3, "pm": 1e-3, "mm": 1e6, "m": 1e9}
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            try:
                value = float(m.group(1))
                unit = m.group(2).lower().replace("µ", "u")
                return value * unit_to_nm.get(unit, 1.0)
            except ValueError:
                continue
    return None


def parse_affinity_string(affinity_str: str) -> float | None:
    """Parse affinity string from SAbDab format.
    
    SAbDab provides affinity in scientific notation (e.g., "9.6e-09" = 9.6×10⁻⁹ M)
    Convert to nanomolar.
    """
    if not affinity_str or affinity_str == 'None':
        return None
    
    try:
        # Try to parse as float (scientific notation)
        value_m = float(affinity_str)
        # Convert from M to nM (multiply by 10⁹)
        value_nm = value_m * 1e9
        return value_nm
    except ValueError:
        # Fallback to the original text parser
        return extract_kd_from_text(affinity_str)


# ---------------------------------------------------------------------------
# BindingDB (opzionale, per dati di affinità)
# ---------------------------------------------------------------------------
BINDINGDB_BY_PDB = "https://bindingdb.org/rwd/bind/BindingDB-PDB-by-PDBIDRest.jsp"
_limiter_bindingdb = RateLimiter(0.5)


def _parse_bindingdb_response(text: str) -> list[dict]:
    text = text.strip()
    if not text:
        return []

    # Se la risposta è già JSON valido, usalo direttamente
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "data" in data:
            return data.get("data") or []
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Cerca un array JSON incorporato nell'HTML
    import re
    match = re.search(r"(\[\s*\{[\s\S]*\}\s*\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Parser di fallback da HTML tabellare
    table_match = re.search(r"<table.*?>([\s\S]*?)</table>", text, re.I)
    if table_match:
        table_html = table_match.group(1)
        headers = [re.sub(r"<.*?>", "", h).strip().lower()
                   for h in re.findall(r"<th.*?>(.*?)</th>", table_html, re.S | re.I)]
        rows = []
        for tr_html in re.findall(r"<tr.*?>(.*?)</tr>", table_html, re.S | re.I)[1:]:
            cells = [re.sub(r"<.*?>", "", c).strip()
                     for c in re.findall(r"<t[dh].*?>(.*?)</t[dh]>", tr_html, re.S | re.I)]
            if headers and len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
        return rows

    return []


def _extract_bindingdb_entry_affinity(entry: dict) -> tuple[float | None, str]:
    """Estrae il valore di affinità da un record BindingDB, in nM."""
    if not entry:
        return None, ""
    normalized = {str(k).strip().lower(): str(v).strip() for k, v in entry.items() if v is not None}
    # Cerca il primo campo utile in ordine di preferenza
    preferred_keys = ["kd", "k_d", "kd_nM", "kd_nm", "k_d_n_m", "ki", "ic50", "ic_50"]
    for name in preferred_keys:
        if name in normalized:
            kd_nm = parse_affinity_string(normalized[name])
            if kd_nm is not None:
                return kd_nm, name

    for key, value in normalized.items():
        if any(token in key for token in ("kd", "ki", "ic50", "ic_50")):
            kd_nm = parse_affinity_string(value)
            if kd_nm is not None:
                return kd_nm, key

    return None, ""


def get_best_bindingdb_affinity(entries: list[dict]) -> tuple[float | None, dict | None, str]:
    best_kd = None
    best_entry = None
    best_key = ""
    for entry in entries:
        kd_nm, key = _extract_bindingdb_entry_affinity(entry)
        if kd_nm is None:
            continue
        if best_kd is None or kd_nm < best_kd:
            best_kd = kd_nm
            best_entry = entry
            best_key = key
    return best_kd, best_entry, best_key


def fetch_bindingdb_for_pdb(pdb_id: str) -> list[dict]:
    """Cerca dati di affinità in BindingDB per un PDB id."""
    def fetcher():
        _limiter_bindingdb.wait()
        url = f"{BINDINGDB_BY_PDB}?pdb={pdb_id.upper()}&response=application/json"
        try:
            raw = _http_get(url)
            text = raw.decode("utf-8", errors="replace")
            return {"data": _parse_bindingdb_response(text)}
        except RemoteUnavailable:
            return {"data": []}

    key = cache_key("bindingdb_pdb", pdb_id.lower())
    try:
        return cached_json(key, fetcher).get("data", [])
    except RemoteUnavailable:
        return []


# ---------------------------------------------------------------------------
# SAbDab summary TSV (opzionale, se scaricato localmente)
# ---------------------------------------------------------------------------
SABDAB_SUMMARY_URL = "https://opig.stats.ox.ac.uk/webapps/newsabdab/sabdab/summary/all"


def load_sabdab_summary(tsv_path: Path | None = None) -> list[dict]:
    """Carica il summary SAbDab da file locale (preferito) o scaricandolo.

    Il file è tipicamente ~10 MB. Le colonne includono: pdb, Hchain, Lchain,
    antigen_name, antigen_type, affinity, method, resolution.
    """
    def parse(text: str) -> list[dict]:
        lines = text.strip().splitlines()
        if not lines:
            return []
        header = lines[0].split("\t")
        out = []
        for row in lines[1:]:
            fields = row.split("\t")
            if len(fields) != len(header):
                continue
            out.append(dict(zip(header, fields)))
        return out

    if tsv_path and tsv_path.exists():
        log.info("SAbDab: carico file locale %s", tsv_path)
        return parse(tsv_path.read_text(encoding="utf-8", errors="replace"))

    def fetcher():
        log.info("SAbDab: scarico summary dal server (può essere lento)")
        raw = _http_get(SABDAB_SUMMARY_URL)
        return {"raw": raw.decode("utf-8", errors="replace")}

    key = cache_key("sabdab_summary_v1")
    try:
        data = cached_json(key, fetcher, ttl_hours=720)  # 30 giorni
        return parse(data["raw"])
    except RemoteUnavailable:
        log.warning("SAbDab non raggiungibile e nessun file locale: lista vuota")
        return []


# ---------------------------------------------------------------------------
# Prova di connettività
# ---------------------------------------------------------------------------
def check_connectivity() -> dict[str, bool]:
    """Verifica la raggiungibilità delle fonti. Ritorna un dict {fonte: ok}."""
    endpoints = {
        "rcsb": "https://data.rcsb.org/rest/v1/holdings/current/entry_ids",
        "pubmed": f"{EUTIL_BASE}/einfo.fcgi",
        "sabdab": "https://opig.stats.ox.ac.uk/webapps/newsabdab/sabdab",
        "bindingdb": "https://bindingdb.org",
    }
    status = {}
    for name, url in endpoints.items():
        try:
            _http_get(url)
            status[name] = True
        except RemoteUnavailable:
            status[name] = False
    return status
