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

from utils import CACHE_DIR, RateLimiter, cache_key, cached_json, get_logger, parse_affinity_string

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
    metadata = cached_json(key, fetcher)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    explicit_path = CACHE_DIR / f"{pdb_id}.json"
    try:
        with explicit_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return metadata


PDB_DOWNLOAD_URL = "https://files.rcsb.org/download/{pdb_id}.pdb"


def fetch_pdb_file(pdb_id: str) -> str:
    """Scarica e memorizza localmente il file PDB per un dato codice."""
    pdb_id = pdb_id.lower()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{pdb_id}.pdb"
    if path.exists():
        return str(path)
    raw = _http_get(PDB_DOWNLOAD_URL.format(pdb_id=pdb_id.upper()))
    path.write_bytes(raw)
    return str(path)


def extract_pdb_chains(pdb_path: str | Path, metadata: dict | None = None) -> dict[str, list[str] | str]:
    """Estrae gli identificatori di catena presenti nel file PDB e li classifica.
    
    Usa i metadati COMPND del file PDB per classificare le catene come anticorpo o antigene.
    Se i metadati COMPND non sono disponibili, usa metadati esterni (SAbDab/RCSB) o euristiche.
    
    Ritorna un dict con:
    - 'all': tutte le catene
    - 'antibody': catene anticorpali
    - 'antigen': catene antigeniche
    - 'description': descrizione del complesso (nomi delle molecole)
    """
    import re
    
    path = Path(pdb_path)
    if not path.exists():
        log.warning(f"PDB file non trovato: {pdb_path}")
        return {"all": [], "antibody": [], "antigen": [], "description": ""}
    
    # Prima estrai tutte le catene dal file
    chain_ids = []
    try:
        from Bio.PDB import PDBParser
        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("complex", str(path))
        chain_ids = sorted({chain.id for model in structure for chain in model})
        log.info(f"Estratte {len(chain_ids)} catene da {pdb_path} usando Bio.PDB")
    except Exception as e:
        log.warning(f"Bio.PDB fallito, fallback a parsing manuale: {e}")
        chains = set()
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith(("ATOM  ", "HETATM")) and len(line) >= 22:
                        chains.add(line[21])
        except Exception as e2:
            log.error(f"Impossibile estrarre catene: {e2}")
            return {"all": [], "antibody": [], "antigen": [], "description": ""}
        chain_ids = sorted(chains)
        log.info(f"Estratte {len(chain_ids)} catene da {pdb_path} usando parsing manuale")
    
    if not chain_ids:
        log.warning(f"Nessuna catena trovata in {pdb_path}")
        return {"all": [], "antibody": [], "antigen": [], "description": ""}
    
    # Prova a classificare usando i metadati COMPND del file PDB
    antibody_chains = []
    antigen_chains = []
    molecule_descriptions = []
    
    try:
        # Dizionario per mappare MOL_ID -> { 'molecola': str, 'catene': [] }
        molecole = {}
        corrente_mol_id = None
        
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for linea in f:
                # Ci interessano solo le righe di metadati COMPND
                if linea.startswith('COMPND'):
                    # Estrae il MOL_ID se presente nella riga
                    match_id = re.search(r'MOL_ID:\s*(\d+)', linea)
                    if match_id:
                        corrente_mol_id = int(match_id.group(1))
                        if corrente_mol_id not in molecole:
                            molecole[corrente_mol_id] = {'molecola': '', 'catene': []}
                    
                    if corrente_mol_id is not None:
                        # Estrae il nome della molecola
                        match_mol = re.search(r'MOLECULE:\s*([^;\n]+)', linea)
                        if match_mol:
                            molecole[corrente_mol_id]['molecola'] += match_mol.group(1).strip().upper()
                        
                        # Estrae le catene associate
                        match_chain = re.search(r'CHAIN:\s*([^;\n]+)', linea)
                        if match_chain:
                            # Pulisce le catene rimuovendo spazi e separando per virgola
                            catene_raw = match_chain.group(1).replace(' ', '').upper()
                            catene_lista = [c for c in catene_raw.split(',') if c]
                            molecole[corrente_mol_id]['catene'].extend(catene_lista)
        
        # Parole chiave per identificare l'anticorpo
        keyword_anticorpo = ['ANTIBODY', 'FAB FRAGMENT', 'VHH', 'NANOBODY', 'SINGLE-DOMAIN', 
                              'HEAVY CHAIN', 'LIGHT CHAIN', 'SCFV', 'IMMUNOGLOBULIN', 'FV']
        
        # Classificazione basata sulle keyword trovate
        for mol_id, info in molecole.items():
            nome_mol = info['molecola']
            catene = info['catene']
            
            # Salta record vuoti o molecole d'acqua/eteroatomi
            if not nome_mol or not catene or 'HOH' in nome_mol:
                continue
            
            # Aggiungi alla descrizione
            molecule_descriptions.append(f"{nome_mol} (catene: {', '.join(catene)})")
                
            # Controllo se è un anticorpo
            is_anticorpo = any(kw in nome_mol for kw in keyword_anticorpo)
            
            if is_anticorpo:
                antibody_chains.extend(catene)
            else:
                # Fallback: se non è un anticorpo, viene trattato come l'antigene/target del complesso
                antigen_chains.extend(catene)
        
        # Rimuovi eventuali duplicati preservando l'ordine
        antibody_chains = list(dict.fromkeys(antibody_chains))
        antigen_chains = list(dict.fromkeys(antigen_chains))
        
        # Filtra solo le catene che esistono realmente nel file
        antibody_chains = [c for c in antibody_chains if c in chain_ids]
        antigen_chains = [c for c in antigen_chains if c in chain_ids]
        
        if antibody_chains or antigen_chains:
            log.info(f"Classificazione COMPND: {len(antibody_chains)} anticorpi, {len(antigen_chains)} antigeni")
        else:
            log.info("COMPND non ha fornito classificazione utile, fallback a metadati esterni")
            
    except Exception as e:
        log.warning(f"Errore nel parsing COMPND: {e}, fallback a metadati esterni")
    
    # Se COMPND non ha funzionato, prova metadati esterni
    if not antibody_chains and not antigen_chains:
        # Prima prova a usare i metadati SAbDab se disponibili
        if metadata:
            sabdab_hchain = metadata.get("Hchain", "")
            sabdab_lchain = metadata.get("Lchain", "")
            if sabdab_hchain:
                antibody_chains.extend([c.strip() for c in sabdab_hchain.split(",") if c.strip()])
            if sabdab_lchain:
                antibody_chains.extend([c.strip() for c in sabdab_lchain.split(",") if c.strip()])
            log.info(f"Metadati SAbDab: Hchain={sabdab_hchain}, Lchain={sabdab_lchain}")
        
        # Se non abbiamo metadati SAbDab, prova a usare i metadati RCSB
        if not antibody_chains and metadata:
            entry = metadata.get("data", {}).get("entry") or metadata.get("entry")
            if entry:
                entities = entry.get("polymer_entities") or []
                ab_keywords = ("heavy chain", "light chain", "fab", "fv", "scfv", "immunoglobulin",
                               "antibody", "nanobody", "vhh", "variable region")
                for e in entities:
                    desc = ((e.get("rcsb_polymer_entity") or {}).get("pdbx_description") or "").lower()
                    if any(k in desc for k in ab_keywords):
                        asym_ids = ((e.get("rcsb_polymer_entity_container_identifiers") or {})
                                    .get("asym_ids") or [])
                        antibody_chains.extend(asym_ids)
                log.info(f"Metadati RCSB: trovate {len(antibody_chains)} catene anticorpali")
        
        # Fallback: usa pattern nei nomi delle catene
        if not antibody_chains:
            for chain in chain_ids:
                chain_upper = chain.upper()
                if chain_upper in ("H", "L") or chain_upper.startswith("H") or chain_upper.startswith("L"):
                    antibody_chains.append(chain)
            log.info(f"Fallback pattern: trovate {len(antibody_chains)} catene anticorpali")
        
        # Rimuovi duplicati e mantieni l'ordine originale
        antibody_chains = list(dict.fromkeys([c for c in antibody_chains if c in chain_ids]))
        antigen_chains = [c for c in chain_ids if c not in antibody_chains]
    
    # Crea descrizione del complesso
    description = "; ".join(molecule_descriptions) if molecule_descriptions else f"Complesso con {len(chain_ids)} catene"
    
    log.info(f"Classificazione finale: {len(chain_ids)} totali, {len(antibody_chains)} anticorpi, {len(antigen_chains)} antigeni")
    
    return {
        "all": chain_ids,
        "antibody": antibody_chains,
        "antigen": antigen_chains,
        "description": description
    }


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
