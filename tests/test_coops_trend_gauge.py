"""A CO-OPS gauge whose recent readings cannot give a trend (D6) is passed over for the next nearest, as PSMSL does
(tests/test_psmsl_trend_gauge.py), so the series and the trend pick the same gauge. Offline, synthetic gauge data."""
import pytest

from earthtrends.agent import tools
from earthtrends.data import coops

HERE = (40.70, -74.01)
GAUGES = [{"id": "8000001", "name": "Thin Point", "lat": 40.71, "lng": -74.02},
          {"id": "8000002", "name": "Dense Harbor", "lat": 40.90, "lng": -74.10}]


def reply(months):
    return {"data": [{"year": str(y), "month": str(m), "MSL": f"{0.002 * (y - 1900):.4f}"} for y, m in months]}


def thin_recent():
    """1900-1960 and 1991-2008 every month, then one to eleven months a year to 2024 and 2025-01 to 05: 30+ years and
    recent, so the old rule took it, but no stretch to the end has 80% of its months."""
    dense = [(y, m) for y in [*range(1900, 1961), *range(1991, 2009)] for m in range(1, 13)]
    sparse = [(y, m) for y in range(2009, 2025) for m in range(1, (y - 2009) % 11 + 2)]
    return reply(dense + sparse + [(2025, m) for m in range(1, 6)])


FILES = {"8000001": thin_recent(), "8000002": reply([(y, m) for y in range(1991, 2026) for m in range(1, 13)])}


@pytest.fixture
def harbor(monkeypatch):
    fetched = []
    monkeypatch.setattr(coops, "stations", lambda: GAUGES)
    monkeypatch.setattr(coops, "fetch", lambda sid: fetched.append(sid) or FILES[sid])
    return fetched


def test_the_next_gauge_answers_for_series_and_trend_alike(harbor):
    s = tools.get_series("sea_level", *HERE, source="coops")
    r = tools.detect_trend("sea_level", *HERE, source="coops")
    assert s["place"]["name"] == r["place"]["name"] == "Dense Harbor"
    skip = "Thin Point, the nearest gauge, has too few recent readings for a trend."
    assert skip in s["notes"] and skip in r["caveats"]
    assert s["notes"][0].startswith("Tide gauge Dense Harbor (8000002), 23 km")
    assert r["record"]["status"] == "ok" and r["period"]["start"] == "1991-01"
    assert harbor == ["8000001", "8000002"]  # each gauge read once


def test_the_nearest_gauge_is_kept_when_it_can_give_a_trend(monkeypatch):
    monkeypatch.setattr(coops, "stations", lambda: GAUGES)
    monkeypatch.setattr(coops, "fetch", lambda sid: FILES["8000002"])  # both dense
    _, _, place, notes, _ = coops.series(*HERE)
    assert place["name"] == "Thin Point" and not any("too few recent readings" in n for n in notes)


def test_no_gauge_that_can_give_a_trend_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(coops, "stations", lambda: GAUGES)
    monkeypatch.setattr(coops, "fetch", lambda sid: FILES["8000001"])
    with pytest.raises(coops.NoUsableGauge, match="Thin Point, 1 km away: it has too few recent readings for a trend"):
        coops.series(*HERE)
