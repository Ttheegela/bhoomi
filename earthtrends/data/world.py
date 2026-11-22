"""World reference series for like-for-like comparisons (docs/CONTRACTS.md, "World reference series").

Read from the snapshot files in world/, refreshed by hand with scripts/update_world.py; nothing is fetched per request.
"""
import copy
import json
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parent / "world"
NAMES = ("land_temp", "gmsl")


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return json.loads((DIR / f"{name}.json").read_text(encoding="utf-8"))


def reference(name: str) -> dict:
    """`land_temp` (global land-only monthly air temperature anomaly, degC) or `gmsl` (satellite global mean sea level,
    monthly, mm) as a TimeSeries with its full source block. Any other name: ValueError."""
    if name not in NAMES:
        raise ValueError(f"Unknown world series {name!r}. Choose one of: {', '.join(NAMES)}.")
    return copy.deepcopy(_load(name))
