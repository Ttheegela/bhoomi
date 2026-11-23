"""Record ERA5 series for offline replay (BHOOMI_ERA5_REPLAY, see earthtrends/data/era5.py). Run by hand:

  uv run python scripts/record_era5_replay.py [folder] [app]   (defaults tests/fixtures/era5_replay, https://bhoomi.earth)

Nothing here calls Open-Meteo: every series comes from the app's /api/series, which fetches ERA5 from Open-Meteo
server-side. The app returns monthly values, not Open-Meteo's daily reply, so the monthly series is what is recorded,
and era5.replay() feeds it back through the same parse and daily-to-monthly path. The span is the app's: a deployment
running this code gives 1981 to the latest complete month; one running older code may stop at last December.
Requests are at least GAP_S apart; a 429 or 502 waits and tries again (see get()). Every file of one run carries the run's UTC date
as `retrieved` (a replay folder has one recording date). Production may answer from its own cache (12 h in the app,
1 h at the CDN), so its Open-Meteo fetch can be up to about a day before that date.
"""
import gzip
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from earthtrends.data import era5, upstream  # noqa: E402

APP = "https://bhoomi.earth"
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "era5_replay"
GAP_S = 5.0  # 2 s gave a 502 after 7 requests: each one is 45 years of daily data for production's Open-Meteo quota
VARIABLES = ("air_temp", "air_temp_max", "precip")
# The task's points, then the points the page or the agent sends for the same place where they round differently:
# web/app.js default pins, /api/places' first hit (the page sends it on), evals/cases*.toml.
PLACES = [
    ("Delhi", 28.6139, 77.2090), ("Delhi, page pin", 28.58, 77.21), ("Delhi, place search", 28.65, 77.23),
    ("Princeton", 40.3573, -74.6672), ("Princeton, page pin and place search", 40.35, -74.66),
    ("Chennai", 13.0827, 80.2707), ("Chennai, place search", 13.09, 80.28),
    ("Seattle", 47.6062, -122.3321), ("Sydney", -33.8688, 151.2093), ("New York", 40.7128, -74.0060),
    ("London", 51.5074, -0.1278), ("Mumbai", 19.0760, 72.8777), ("Mumbai, place search", 19.07, 72.88),
    ("Riverside", 33.9806, -117.3755), ("Riverside, place search", 33.95, -117.40),
]


def refuse_open_meteo(url: httpx.URL | str) -> None:
    """This script records through the app, never from Open-Meteo directly: checked on the app address and on every
    reply's final URL, after redirects."""
    if "open-meteo" in httpx.URL(url).host:
        sys.exit(f"Refusing {httpx.URL(url).host}: record through the app, never from Open-Meteo directly.")


def get(client: httpx.Client, api: str, params: dict) -> httpx.Response:
    """A 429 waits for its Retry-After; a 502 (production could not reach Open-Meteo, often its rate limit) waits longer each time."""
    for i in range(5):
        r = client.get(api, params=params)
        refuse_open_meteo(r.url)
        if r.status_code not in (429, 502):
            r.raise_for_status()
            return r
        wait = int(r.headers.get("Retry-After", "60")) + 1 if r.status_code == 429 else 30 * 2 ** i
        print(f"  {r.status_code}, waiting {wait} s", flush=True)
        time.sleep(wait)
    sys.exit(f"Still failing after 5 tries: {params}")


def main(out: Path, app: str) -> None:
    refuse_open_meteo(app)
    out.mkdir(parents=True, exist_ok=True)
    retrieved = upstream.utc_today()
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        for place, lat, lon in PLACES:
            lat, lon = round(lat, 2) + 0.0, round(lon, 2) + 0.0  # get_series' rounding: the replay key
            for variable in VARIABLES:
                path = out / era5.replay_name(variable, lat, lon)
                old = json.loads(gzip.decompress(path.read_bytes())) if path.is_file() else {}
                if old.get("retrieved") == retrieved and old["via"].startswith(app + "/"):
                    continue  # a rerun the same day only fetches what is missing
                r = get(client, f"{app}/api/series", {"variable": variable, "lat": lat, "lon": lon, "source": "era5"})
                s = r.json()
                if s["source"]["id"] != "era5" or [s["place"]["lat"], s["place"]["lon"]] != [lat, lon] or len(s["times"]) != len(s["values"]):
                    sys.exit(f"Unexpected reply for {variable} at {lat}, {lon}: {str(s)[:200]}")
                rec = {"variable": variable, "lat": lat, "lon": lon, "place": place, "retrieved": retrieved,
                       "via": str(r.request.url), "times": s["times"], "values": s["values"]}
                path.write_bytes(gzip.compress(json.dumps(rec, separators=(",", ":")).encode(), mtime=0))
                print(f"{path.name}: {s['times'][0]} to {s['times'][-1]}, {path.stat().st_size} bytes", flush=True)
                time.sleep(GAP_S)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT, sys.argv[2].rstrip("/") if len(sys.argv) > 2 else APP)
