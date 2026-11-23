"""ERA5 replay (BHOOMI_ERA5_REPLAY): series recorded from production's /api/series, read instead of Open-Meteo."""
import gzip
import json
from pathlib import Path

import httpx
import pytest

from earthtrends import data
from earthtrends.data import era5, upstream


def write(folder: Path, variable: str, lat: float, lon: float, retrieved: str, times: list, values: list) -> None:
    rec = {"variable": variable, "lat": lat, "lon": lon, "retrieved": retrieved, "times": times, "values": values}
    (folder / era5.replay_name(variable, lat, lon)).write_bytes(gzip.compress(json.dumps(rec).encode()))


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("replay must not touch the network"))


def test_replay_reads_the_recording_through_the_monthly_path(tmp_path, monkeypatch, offline):
    times = [f"{y}-{m:02d}" for y in range(2000, 2003) for m in range(1, 13)]
    values = [None if i == 5 else round(20 + i / 7, 2) for i in range(36)]
    write(tmp_path, "precip", 28.61, 77.21, "2026-11-23", times, values)
    monkeypatch.setenv(era5.REPLAY, str(tmp_path))
    s = data.get_series("precip", 28.61, 77.21, source="era5")
    assert (s["times"], s["values"]) == (times, values) and s["source"]["retrieved"] == "2026-11-23"


def test_preliminary_months_survive_replay(tmp_path, monkeypatch, offline):
    # recorded 2027-01-15 with data through December 2026: October to December may still hold ERA5T days
    times = [f"{y}-{m:02d}" for y in (2025, 2026) for m in range(1, 13)]
    values = [round(30 + i / 10, 2) for i in range(24)]
    write(tmp_path, "air_temp_max", 28.61, 77.21, "2027-01-15", times, values)
    monkeypatch.setenv(era5.REPLAY, str(tmp_path))
    monkeypatch.setattr(upstream, "utc_today", lambda: "2027-06-01")  # replayed months later
    s = data.get_series("air_temp_max", 28.61, 77.21, source="era5")
    assert era5.PRELIMINARY_MONTHS == 3 and s["flags"] == [None] * 21 + ["preliminary"] * 3
    assert s["values"] == values and s["source"]["retrieved"] == "2027-01-15"
    monkeypatch.delenv(era5.REPLAY)
    assert set(era5.flags(times, "2027-06-01")) == {None}  # a live fetch that day would flag nothing


def test_a_missing_recording_fails_clearly(tmp_path, monkeypatch, offline):
    write(tmp_path, "air_temp", 28.61, 77.21, "2026-11-23", ["2025-01"], [1.0])
    monkeypatch.setenv(era5.REPLAY, str(tmp_path))
    with pytest.raises(ValueError, match=r"^No recorded ERA5 series for precip at 0\.0, 0\.0 in "):
        data.get_series("precip", 0, 0, source="era5")


def test_a_replay_folder_has_one_recording_date(tmp_path, monkeypatch, offline):
    write(tmp_path, "air_temp", 1.0, 2.0, "2026-11-22", ["2025-01"], [1.0])
    write(tmp_path, "precip", 1.0, 2.0, "2026-11-23", ["2025-01"], [1.0])
    monkeypatch.setenv(era5.REPLAY, str(tmp_path))
    with pytest.raises(ValueError, match="must hold recordings from one date"):
        data.get_series("air_temp", 1, 2, source="era5")
