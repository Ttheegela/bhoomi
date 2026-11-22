"""A PSMSL gauge whose recent readings cannot give a trend (D6) is passed over for the next nearest, once, for both the
series and the trend (London: Sheerness has thin years since 2009, Newhaven is used). Offline, synthetic gauge files."""
import pytest

from earthtrends import data
from earthtrends.agent import tools
from earthtrends.data import psmsl
from earthtrends.stats import compute_trend

LONDON = (51.51, -0.13)
GAUGES = [{"id": 3, "name": "Sheerness", "lat": 51.4456, "lon": 0.7434},  # 61 km
          {"id": 1548, "name": "Newhaven", "lat": 50.7818, "lon": 0.0571}]  # 82 km


def rows(months):
    return "\n".join(f"{y + (m - 0.5) / 12:.4f}; {7000 + 2 * (y - 1900)}; 0;000" for y, m in months)


def thin_recent():
    """1900-1960 and 1991-2008 every month, then 2009-2025 with one to eleven months a year, ending 2025-05: from no
    year on are 80% of the months there, except 2025 alone."""
    dense = [(y, m) for y in [*range(1900, 1961), *range(1991, 2009)] for m in range(1, 13)]
    sparse = [(y, m) for y in range(2009, 2025) for m in range(1, (y - 2009) % 11 + 2)]
    return rows(dense + sparse + [(2025, m) for m in range(1, 6)])


FILES = {3: thin_recent(), 1548: rows([(y, m) for y in range(1991, 2026) for m in range(1, 13)])}


@pytest.fixture
def london(monkeypatch):
    fetched = []
    monkeypatch.setattr(psmsl, "stations", lambda: GAUGES)
    monkeypatch.setattr(psmsl, "fetch", lambda sid, **kw: fetched.append(sid) or FILES[sid])
    return fetched


def test_the_nearest_gauge_is_long_but_its_recent_readings_cannot_give_a_trend():
    times, values, _ = psmsl.parse(FILES[3])
    assert psmsl.why_not(times, values) is None  # 30+ years and recent: the old rule took it
    with pytest.raises(ValueError, match=r"^Too few recent readings for a trend: the record runs from 1900-01 to "
                                         r"2025-05, but only 2025-01 on \(0\.4 years\)"):
        compute_trend({"variable": "sea_level", "units": "mm", "freq": "monthly", "place": {"name": "Sheerness"},
                       "times": times, "values": values, "source": {"id": "psmsl"}, "notes": []})


def test_the_next_gauge_answers_for_series_and_trend_alike(london):
    s = tools.get_series("sea_level", *LONDON, source="psmsl")
    r = tools.detect_trend("sea_level", *LONDON, source="psmsl")
    assert s["place"]["name"] == r["place"]["name"] == "Newhaven"
    skip = "Sheerness, the nearest gauge, has too few recent readings for a trend."
    assert skip in s["notes"] and skip in r["caveats"]
    assert s["notes"][0].startswith("Tide gauge Newhaven (PSMSL id 1548), 82 km")
    assert r["record"]["status"] == "ok" and r["period"]["start"] == "1991-01"
    assert london == [3, 1548]  # each gauge file read once: the series cache answers the trend


def test_the_nearest_gauge_is_kept_when_it_can_give_a_trend(monkeypatch):
    monkeypatch.setattr(psmsl, "stations", lambda: GAUGES)
    monkeypatch.setattr(psmsl, "fetch", lambda sid, **kw: FILES[1548])  # both gauges dense
    data._cache.clear()
    times, values, place, notes, _ = psmsl.series(*LONDON)
    assert place["name"] == "Sheerness" and not any("too few recent readings" in n for n in notes)
