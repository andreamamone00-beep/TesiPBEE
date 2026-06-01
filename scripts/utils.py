"""Utility condivise tra gli script della pipeline."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import random
import time
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Costanti fisiche
# ---------------------------------------------------------------------------
R_GAS_KCAL = 1.987204e-3   # kcal / (mol * K)
T_STANDARD = 298.15        # K (25 °C)

# ---------------------------------------------------------------------------
# Layout di progetto
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
CACHE_DIR = DATA_DIR / "cache"
DOCS_DIR = PROJECT_ROOT / "docs"

DATASET_RAW = DATA_DIR / "dataset_raw.csv"
DATASET_CURATED = DATA_DIR / "dataset_curated.csv"
DATASET_NORMALIZED = DATA_DIR / "dataset_normalized.csv"
DATASET_FINAL = DATA_DIR / "dataset.csv"
METRICS_JSON = RESULTS_DIR / "metrics.json"


def ensure_dirs() -> None:
    for d in (DATA_DIR, RESULTS_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler()
    fmt = logging.Formatter("[%(asctime)s] %(levelname)-7s %(name)-20s %(message)s",
                            datefmt="%H:%M:%S")
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


# ---------------------------------------------------------------------------
# Conversioni termodinamiche
# ---------------------------------------------------------------------------
def kd_to_dg(kd_molar: float, temperature: float = T_STANDARD) -> float:
    """Converte Kd (in molare) in ΔG di legame (kcal/mol)."""
    if kd_molar <= 0:
        raise ValueError("Kd deve essere positivo")
    return R_GAS_KCAL * temperature * math.log(kd_molar)


def nm_to_molar(kd_nm: float) -> float:
    return kd_nm * 1e-9


def parse_affinity_string(s: str) -> float | None:
    """Parsa stringhe di affinità tipiche dei dataset (es. '3.2 nM', '1.5e-9 M').

    Ritorna il Kd in nanomolare, None se non parsabile.
    """
    if s is None:
        return None
    s = str(s).strip().replace(",", ".")
    if not s or s.lower() in ("nan", "none", "null", "n/a", "-"):
        return None

    unit_scales = {
        "mm": 1e6, "millimolar": 1e6,
        "um": 1e3, "μm": 1e3, "micromolar": 1e3,
        "nm": 1.0, "nanomolar": 1.0,
        "pm": 1e-3, "picomolar": 1e-3,
        "m": 1e9, "molar": 1e9,
    }
    # Estrai numero + unita'
    import re
    m = re.match(r"\s*([\d.]+(?:[eE][-+]?\d+)?)\s*([a-zA-ZμµM]*)\s*$", s)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2).lower().replace("µ", "u")
    scale = unit_scales.get(unit, 1.0)  # default: assume nM
    return value * scale


# ---------------------------------------------------------------------------
# Randomness riproducibile
# ---------------------------------------------------------------------------
def seeded_random(seed: int = 42) -> random.Random:
    return random.Random(seed)


# ---------------------------------------------------------------------------
# Cache su disco per le chiamate di rete
# ---------------------------------------------------------------------------
def cache_key(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def cached_json(key: str, fetcher: Callable[[], Any], ttl_hours: float = 168) -> Any:
    """Cache JSON su disco con TTL (default 7 giorni)."""
    ensure_dirs()
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if age_h < ttl_hours:
            try:
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    data = fetcher()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


# ---------------------------------------------------------------------------
# Sicurezza rete: rate-limit e timeout
# ---------------------------------------------------------------------------
class RateLimiter:
    """Limitatore di richieste per rispettare API pubbliche."""

    def __init__(self, min_interval_s: float = 0.35):
        self.min_interval = min_interval_s
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.monotonic()


def format_kd(kd_nm: float) -> str:
    if kd_nm is None:
        return "—"
    if kd_nm < 1:
        return f"{kd_nm:.2f}"
    if kd_nm < 10:
        return f"{kd_nm:.1f}"
    if kd_nm < 1000:
        return f"{kd_nm:.0f}"
    return f"{kd_nm:.0f}"
