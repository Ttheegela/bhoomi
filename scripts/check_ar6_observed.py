"""Built-in check of the sea-level projections (docs/REWORK-SPEC.md, PR2 item 8). Run by hand; never at run time.

For every mapped tide gauge with data, is the observed 2019-2021 mean, on the 1995-2014 baseline, inside IPCC AR6's
2020 5th-95th percentile there (SSP2-4.5 medium confidence)? A gauge outside points to a datum shift, a wrong
station-to-AR6 mapping, or land moving differently from AR6's estimate.

Gauges: every CO-OPS station in earthtrends/data/coops_to_psmsl.csv with an AR6 location (its CO-OPS monthly record),
and every PSMSL gauge in earthtrends/data/ar6_gauges.npz (its PSMSL RLR monthly record). The numbers come from the app's
own code (the fetchers, baseline.py and projection.py), so they are the ones the API shows as `projection.check`.

Requests are at least 0.75 s apart (at most 80 a minute) and each reply is cached in a scratch folder outside the
repository, so a rerun fetches nothing:
  uv run python scripts/check_ar6_observed.py [cache folder; default $TMPDIR/bhoomi-ar6-check]
Prints every gauge outside its range, then the counts. Writes nothing to the repository.
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from earthtrends.data import ar6, coops, psmsl  # noqa: E402
from earthtrends.stats.baseline import baseline  # noqa: E402
from earthtrends.stats.projection import GRID, _coops_rows, sea_level  # noqa: E402

GAP_S = 0.75
CACHE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("TMPDIR", "/tmp")) / "bhoomi-ar6-check"
_last = [0.0]


def cached(name: str, fetch) -> str:
    p = CACHE / name
    if not p.exists():
        time.sleep(max(0.0, _last[0] + GAP_S - time.monotonic()))
        _last[0] = time.monotonic()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(fetch())
    return p.read_text()


def gauges():
    """-> (source id, station id, name, lat, lon, fetch-and-parse) for every gauge to check."""
    for sid, r in _coops_rows().items():
        if r["ar6_id"]:
            yield ("coops", sid, r["coops_name"], float(r["coops_lat"]), float(r["coops_lon"]),
                   lambda sid=sid: coops.parse(json.loads(cached(f"coops/{sid}.json",
                                                                 lambda: json.dumps(coops.fetch(sid))))))
    d = ar6.load()
    for k, gid in enumerate(d["ids"].tolist()):
        if gid < GRID:
            yield ("psmsl", str(gid), str(d["names"][k]), float(d["lat"][k]), float(d["lon"][k]),
                   lambda gid=gid: psmsl.parse(cached(f"psmsl/{gid}.rlrdata", lambda: psmsl.fetch(gid)))[:2])


def main() -> None:
    outside, counts = [], Counter()
    for src, sid, name, lat, lon, read in gauges():
        try:
            times, values = read()
        except (ValueError, httpx.HTTPError) as e:
            counts[f"{src}: no record ({type(e).__name__})"] += 1
            continue
        url = coops.record_url(sid) if src == "coops" else psmsl.record_url(int(sid))
        s = {"variable": "sea_level", "units": "mm", "freq": "monthly", "place": {"name": name, "lat": lat, "lon": lon},
             "times": times, "values": values, "source": {"id": src, "record_url": url}}
        base = baseline(s)
        p = sea_level(s, base, None)  # only the check is read: no `now` needed
        c = p["check"] if p["available"] else None
        if c is None or c["observed_2019_2021"] is None:
            why = "no projection" if c is None else "no baseline" if base["value"] is None else "few 2019-2021 months"
            counts[f"{src}: {why}"] += 1
            continue
        counts[f"{src}: {'inside' if c['inside'] else 'OUTSIDE'}"] += 1
        if not c["inside"]:
            loc = p["location"]
            outside.append(f"{src} {sid} {name}: observed {c['observed_2019_2021']} mm, AR6 2020 p5-p95 "
                           f"{c['ar6_2020_p05']} to {c['ar6_2020_p95']} mm; AR6 {loc['kind']} {loc['id']} "
                           f"({loc['name']}, {loc['km']} km); baseline {base['method']}")
    print("\n".join(outside) or "every gauge checked is inside its range")
    for k in sorted(counts):
        print(f"{k}: {counts[k]}")


if __name__ == "__main__":
    main()
