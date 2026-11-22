"""Build the map's static trend files (docs/REWORK-SPEC.md, PR5). Run by hand; never at run time, never on Vercel.

  uv run python scripts/build_map_trends.py gauges [cache folder]  -> web/data/gauge-trends.json
  uv run python scripts/build_map_trends.py grace                  -> web/data/grace-trends.json

The map must agree with the point answer, so every number comes from tools.detect_trend, the function behind
/api/trend, called as the page calls it for that spot: same fetchers, deseasonalising, Mann-Kendall test, Sen's slope,
widening rule, verdict and whole-record window.

gauges: one entry per tide-gauge dot web/map.js draws (the /api/gauges list: NOAA CO-OPS, then PSMSL, first dot per
3-decimal place). Only api.tidesandcurrents.noaa.gov and psmsl.org are called, at least 0.75 s apart; each reply is
cached in the cache folder (default $TMPDIR/bhoomi-map-trends/<UTC date>), so a rerun the same day fetches nothing.
A reply that failed (an outage, a timeout) is not cached: run again until the counts print no "provider failure".
grace: per land mascon, from earthtrends/data/grace_gsfc_land.npz in the repo; no network.
"""
import base64
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from earthtrends.agent import tools  # noqa: E402
from earthtrends.data import coops, grace, psmsl, upstream  # noqa: E402
from earthtrends.data.upstream import why_not  # noqa: E402
from earthtrends.stats.trend import trend_problem  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "web" / "data"
HOSTS = ("api.tidesandcurrents.noaa.gov", "psmsl.org")
GAP_S = 0.75
THIN = "it has too few recent readings for a trend"  # coops.series and psmsl.series word it so
FILL = -32768
CLAMP = 32767  # a GRACE range end stored at +-CLAMP is at or beyond +-327.67 cm a year
SCALE = 0.01  # GRACE int16 step: 0.01 cm of water a year (0.1 mm)
SIG = {"no_clear_change": 0, "rising": 1, "falling": 2}
NO_DATA = 255
MAX_BYTES = 1_000_000


def cached_get(folder: Path):
    """httpx.get for the two allowed hosts only: each reply kept on disk, live requests at least GAP_S apart."""
    real, last = httpx.get, [0.0]

    def get(url, params=None, **kw):
        u = httpx.URL(url, params=params)
        if u.host not in HOSTS:
            raise RuntimeError(f"{u.host} is not a host this build may call")
        p = folder / hashlib.sha256(str(u).encode()).hexdigest()
        if not p.exists():
            time.sleep(max(0.0, last[0] + GAP_S - time.monotonic()))
            last[0] = time.monotonic()
            r = real(url, params=params, **kw)
            if r.status_code >= 500:
                r.raise_for_status()  # an outage is never cached
            folder.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"status": r.status_code, "text": r.text}))
        d = json.loads(p.read_text())
        return httpx.Response(d["status"], text=d["text"], request=httpx.Request("GET", u))

    return get


def tenth(per_decade: float) -> float:
    """A rate per decade from the API -> per year, to 0.1, half away from zero (the map's precision)."""
    return float((Decimal(repr(per_decade)) / 10).quantize(Decimal("0.1"), ROUND_HALF_UP)) + 0.0


def fixed3(x: float) -> str:
    """JavaScript's x.toFixed(3): web/map.js keys a dot by it and draws only the first dot per key."""
    return str(Decimal(x).quantize(Decimal("0.001"), ROUND_HALF_UP))


def dots():
    """The dots web/map.js draws -> (module, station row, lat, lon): /api/gauges' rows in its order."""
    seen = set()
    for mod, lon_key in ((coops, "lng"), (psmsl, "lon")):
        for s in mod.stations():
            lat, lon = round(float(s["lat"]), 4) + 0.0, round(float(s[lon_key]), 4) + 0.0
            if (key := (fixed3(lat), fixed3(lon))) not in seen:
                seen.add(key)
                yield mod, s, lat, lon


def own_problem(mod, s) -> str | None:
    """Why the point answer passes over this gauge, in the data modules' own words, or None. Provider failures raise."""
    if mod is coops:
        times, values, why, _ = coops._record(s["id"])
    else:
        times, values, _ = psmsl.parse(psmsl.fetch(s["id"]))
        why = why_not(times, values)
    if why is None and trend_problem({"variable": "sea_level", "times": times, "values": values}):
        why = THIN
    return why


def summary(x, w, verdicts) -> dict:
    """Weighted mean, percentiles (the lowest value with at least that share of the weight at or below it) and the
    share of the weight per verdict."""
    x, w, verdicts = np.asarray(x, float), np.asarray(w, float), np.asarray(verdicts)

    def share(v):
        return round(float(w[verdicts == v].sum() / w.sum()), 3)

    q = {f"p{p}": float(np.percentile(x, p, weights=w, method="inverted_cdf")) for p in (10, 50, 90)}
    return {"n": len(x), "mean": float(np.average(x, weights=w)), **q, "frac_rising": share("rising"),
            "frac_falling": share("falling"), "frac_no_change": share("no_clear_change")}


def build_gauges(retrieved: str) -> dict:
    gauges, skipped = [], []
    for mod, s, lat, lon in dots():
        net, sid = mod.SOURCE["id"], str(s["id"])
        try:
            why = own_problem(mod, s)
            if why is None:
                r = tools.detect_trend("sea_level", lat, lon)  # the page's own request when this dot is clicked
                if r["source"]["record_url"] != mod.record_url(s["id"]):
                    why = f"the answer at this spot uses another gauge: {r['place']['name']} ({r['source']['name']})"
        except httpx.HTTPStatusError as e:
            why = f"no usable data: the provider has no file for it (HTTP {e.response.status_code})"
        except httpx.DecodingError:
            why = "no usable data: its file could not be read"
        except httpx.HTTPError as e:
            why = f"provider failure ({type(e).__name__}); run the build again"
        except ValueError as e:  # the point answer's own 400 sentence
            why = str(e)
        if why:
            skipped.append({"id": sid, "network": net, "name": s["name"], "lat": lat, "lon": lon, "why": why})
            continue
        gauges.append({"id": sid, "network": net, "name": s["name"], "lat": lat, "lon": lon,
                       "slope": tenth(r["slope_per_decade"]), "lo": tenth(r["ci_low"]), "hi": tenth(r["ci_high"]),
                       "verdict": r["verdict"], "start": r["period"]["start"], "end": r["period"]["end"],
                       "years": math.floor(r["record"]["years"] + 0.5)})  # the page's Math.round
    st = summary([g["slope"] for g in gauges], [1] * len(gauges), [g["verdict"] for g in gauges])
    return {
        "v": 1, "kind": "gauge_trends", "units": "mm a year", "relative_to": "land",
        "source": [{"name": m.SOURCE["name"], "url": m.SOURCE["url"]} for m in (coops, psmsl)],
        "method": ("Each dot is the point answer for its spot (/api/trend for sea level at the dot), from the gauge's "
                   "monthly mean sea level: each month minus that calendar month's 1995–2014 average (the fitted "
                   "seasonal cycle where the record has no such average), then the Mann-Kendall test and Sen's "
                   "slope over the whole record from start to end (sparse early years left out, as the point answer "
                   "does), with the 95% range widened for months "
                   "that are alike. Rates are relative to the land at the gauge, in mm a year, to 0.1. A dot whose "
                   "record the point answer would not use, or whose spot is answered by another gauge, is in "
                   "skipped. Stats are plain counts of gauges, not weighted by area or coastline; percentiles are "
                   "the lowest rate with at least that share of gauges at or below it."),
        "retrieved": retrieved, "gauges": gauges, "skipped": skipped,
        "stats": {"n": st["n"], "median": st["p50"], "p10": st["p10"], "p90": st["p90"],
                  **{k: v for k, v in st.items() if k.startswith("frac_")}},
    }


def b64(a, dtype: str) -> str:
    return base64.b64encode(np.asarray(a, dtype).tobytes()).decode()


def unb64(s: str, dtype: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype)


def build_grace() -> dict:
    d = grace.load()
    # the centre rounded to 0.01 degrees, as get_series rounds a request: the spot whose answer the map shows
    lat = [round(round(float(x), 2) * 100) for x in d["lat"]]
    lon = [round(round(float(x), 2) * 100) for x in d["lon"]]
    area = np.rint(d["area"]).astype(int)  # km2, whole: the weights as stored, so the stats can be redone from the file
    slope, lo, hi, sig, periods, r = [], [], [], [], set(), None
    for la, lg in zip(lat, lon):
        try:
            r = tools.detect_trend("water_storage", la / 100, lg / 100)
        except ValueError:  # glacier box or too little land: the point answer gives no trend here
            slope.append(FILL), lo.append(FILL), hi.append(FILL), sig.append(NO_DATA)
            continue
        # cm a decade, 4 decimals -> steps of SCALE cm a year: x 10 exactly
        s, a, z = (int((Decimal(repr(r[k])) * 10).quantize(Decimal(1), ROUND_HALF_UP))
                   for k in ("slope_per_decade", "ci_low", "ci_high"))
        slope.append(s)  # never clamped: past int16, b64() fails the build
        # ponytail: a range end past +-327.67 cm a year (earthquake steps, Japan and Chile) is stored at +-CLAMP;
        # int32 lo/hi if the map must print those ends exactly
        lo.append(max(a, -CLAMP)), hi.append(min(z, CLAMP))
        sig.append(SIG[r["verdict"]])
        periods.add((r["period"]["start"], r["period"]["end"]))
    if len(periods) != 1 or periods != {(d["months"][0], d["months"][-1])}:
        raise SystemExit(f"mascon fit windows differ from the series months: {sorted(periods)}")
    (start, end), = periods
    sig_a, have = np.array(sig), np.array(sig) != NO_DATA
    names = {v: k for k, v in SIG.items()}
    st = summary(np.array(slope)[have] * SCALE, area[have], [names[c] for c in sig_a[have]])
    st = {k: round(v, 3) if isinstance(v, float) and not k.startswith("frac_") else v for k, v in st.items()}
    src, km = r["source"], round(2 * grace.HALF_BOX_DEG * 111)  # the point answer's box: 4 degrees, about 444 km
    return {
        "v": 1, "kind": "grace_trends", "units": "cm of water a year", "enc": "i16le-b64", "scale": SCALE,
        "fill": FILL, "clamp": CLAMP, "n": len(lat), "lat_lon_scale": 0.01, "area_units": "km2",
        "lat": b64(lat, "<i2"), "lon": b64(lon, "<i2"), "area": b64(area, "<i2"),
        "slope": b64(slope, "<i2"), "lo": b64(lo, "<i2"), "hi": b64(hi, "<i2"), "sig": b64(sig, "u1"),
        "sig_codes": {"0": "no_clear_change", "1": "rising", "2": "falling", "255": "no data"},
        "period": "the whole record", "start": start, "end": end,
        "reference": {"text": "the provider's 2004.0–2010.0 mean (January 2004 to December 2009)",
                      "years": list(grace.REFERENCE_PERIOD)},
        "footprint_km": km,
        "source": src["name"], "source_url": src["record_url"], "dataset_id": src["dataset_id"],
        "retrieved": src["retrieved"],
        "method": ("Each mascon is the point answer for its centre (/api/trend for water storage at the centre, "
                   "rounded to 0.01 degrees): the area-weighted average of the land mascons in a box about "
                   f"{km} km wide around it, against the provider's 2004.0–2010.0 mean; each month minus that "
                   "calendar month's 2004–2009 average, then the Mann-Kendall test and Sen's slope over the whole "
                   "record, with the 95% range widened for months that are alike. The mascons themselves are "
                   "1-degree equal-area cells, about 110 km; each value stands for the whole box, not a town. "
                   "slope, lo and hi (the 95% range): int16 little-endian in steps of `scale`, `fill` for no "
                   "data; a range end at +-`clamp` is at or beyond +-327.67. lat and lon: int16 in steps of 0.01 "
                   "degrees; area: int16 km2. Stats are weighted by mascon area over "
                   "mascons with a value; percentiles are the lowest rate with at least that share of the area at "
                   "or below it."),
        "stats": {"weights": "mascon area", **st},
    }


def write(name: str, obj: dict) -> Path:
    p = OUT / name
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    if p.stat().st_size > MAX_BYTES:
        raise SystemExit(f"{p} is {p.stat().st_size} bytes, over {MAX_BYTES}")
    return p


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    t0 = time.monotonic()
    if cmd == "gauges":
        today = upstream.utc_today()
        cache = Path(sys.argv[2]) if len(sys.argv) > 2 else (
            Path(os.environ.get("TMPDIR", "/tmp")) / "bhoomi-map-trends" / today)
        httpx.get = cached_get(cache)
        # every gauge's record first, so no lookup runs into the data modules' 40 s deadlines while fetching
        for mod in (coops, psmsl):
            for k, s in enumerate(mod.stations()):
                try:
                    mod.fetch(s["id"])
                except httpx.HTTPError:
                    pass  # built again below, where the failure is recorded
                if k % 100 == 0:
                    print(f"{mod.SOURCE['id']}: {k} fetched, {time.monotonic() - t0:.0f} s", flush=True)
        out = build_gauges(today)
        p = write("gauge-trends.json", out)
        print(Counter(g["network"] for g in out["gauges"]))
        print(Counter((x["network"], " ".join(x["why"].split()[:4])) for x in out["skipped"]))
        print(out["stats"])
    elif cmd == "grace":
        out = build_grace()
        p = write("grace-trends.json", out)
        print(Counter(unb64(out["sig"], "u1").tolist()), out["stats"])
    else:
        raise SystemExit(__doc__)
    print(f"{p}: {p.stat().st_size} bytes, {time.monotonic() - t0:.0f} s")


if __name__ == "__main__":
    main()
