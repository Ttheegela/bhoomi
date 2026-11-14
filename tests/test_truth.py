"""Truth check (#16): our Atlantic City sea-level trend agrees with the one NOAA publishes. Offline, from a fixture."""
import json
from pathlib import Path

from earthtrends.data import coops
from earthtrends.stats import compute_trend

# NOAA relative sea level trend, station 8534720 Atlantic City, NJ, 1911-09 to 2025-12: 1.67 +/- 0.03 inches per decade
# (95% interval), i.e. 4.24 +/- 0.08 mm per year. Read 2026-11-14. The station page
# https://tidesandcurrents.noaa.gov/sltrends/sltrends_station.shtml?id=8534720 now redirects to a page that draws
# these figures with JavaScript from NOAA's own API, which is where they were read:
# https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi/product/sealvltrends.json?station=8534720
NOAA_IN_PER_DECADE, NOAA_ERR = 1.67, 0.03
WIDEN = 0.3  # mm/yr: our series runs to 2026-10, NOAA's to 2025-12

# Fixture: year, month and MSL from CO-OPS monthly_mean, datum MSL, metric, through 2026-10.
FIXTURE = Path(__file__).parent / "fixtures" / "coops_8534720_msl.json"


def test_atlantic_city_matches_noaa():
    times, values = coops.parse(json.loads(FIXTURE.read_text()), "Atlantic City")
    r = compute_trend({"variable": "sea_level", "units": "mm", "freq": "monthly",
                       "place": {"name": "Atlantic City", "lat": 39.36, "lon": -74.42},
                       "times": times, "values": values, "source": dict(coops.SOURCE), "notes": []})
    ours = r["slope_per_decade"] / 10  # mm per year
    lo = (NOAA_IN_PER_DECADE - NOAA_ERR) * 2.54 - WIDEN  # 1 inch per decade = 2.54 mm per year
    hi = (NOAA_IN_PER_DECADE + NOAA_ERR) * 2.54 + WIDEN
    assert lo <= ours <= hi, (ours, lo, hi)
    assert r["verdict"] == "rising"
