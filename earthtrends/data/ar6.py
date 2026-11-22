"""IPCC AR6 sea-level projections at tide gauges, no network at run time.

The data is a derived file shipped with the package: earthtrends/data/ar6_gauges.npz, built offline by
scripts/build_ar6.py from the AR6 regional confidence output (Garner et al. 2021, IPCC AR6 Sea Level Projections,
version 20210809, doi:10.5281/zenodo.6382554, CC-BY-4.0); its manifest, with the required citations, is ar6_gauges.json.
Values are as AR6 publishes them: levels in mm against the 1995-2014 mean, rates in mm a year (AR6's own rates).
Locations are PSMSL gauge IDs, plus the AR6 1-degree cells (IDs from 10**9) that coops_to_psmsl.csv uses.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

FILE = Path(__file__).resolve().parent / "ar6_gauges.npz"  # relative to this module, not the working directory
MANIFEST = FILE.with_suffix(".json")
FILL = -32768


@lru_cache(maxsize=1)
def load() -> dict:
    with np.load(FILE) as z:
        d = {k: z[k] for k in z.files}
    d["index"] = {int(i): k for k, i in enumerate(d["ids"])}
    d["manifest"] = json.loads(MANIFEST.read_text())
    return d


def values(a: np.ndarray, scale: float = 1) -> list:
    """Stored int16 values -> AR6's published ones: levels as they are (scale 1, mm), rates times 0.1 (mm a year);
    None for FILL."""
    return [None if v == FILL else (int(v) if scale == 1 else round(int(v) * scale, 1)) for v in a]

