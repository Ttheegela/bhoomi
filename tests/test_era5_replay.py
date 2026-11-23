"""ERA5 replay (BHOOMI_ERA5_REPLAY): series recorded from production's /api/series, read instead of Open-Meteo."""
import gzip
import json
from pathlib import Path

import pytest

from earthtrends import data
from earthtrends.agent import tools
from earthtrends.data import era5, upstream

FOLDER = Path(__file__).parent / "fixtures" / "era5_replay"  # scripts/record_era5_replay.py


def read(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def write(folder: Path, variable: str, lat: float, lon: float, retrieved: str, times: list, values: list) -> None:
    rec = {"variable": variable, "lat": lat, "lon": lon, "retrieved": retrieved, "times": times, "values": values}
    (folder / era5.replay_name(variable, lat, lon)).write_bytes(gzip.compress(json.dumps(rec).encode()))


# conftest's no_network makes httpx.get raise, so a replay that reached for the network would fail these tests.


@pytest.fixture
def replay(monkeypatch):
    monkeypatch.setenv(era5.REPLAY, str(FOLDER))


def test_every_recording_replays_exactly_through_the_monthly_path(replay):
    files = sorted(FOLDER.glob("*.json.gz"))
    # the persona places at the points the page and the agent send: Delhi, Princeton, Chennai, Sydney, London, New York
    for point in ("28.61_77.21", "28.58_77.21", "40.35_-74.66", "13.08_80.27", "-33.87_151.21", "51.51_-0.13", "40.71_-74.01"):
        for variable in era5.PARAMS:
            assert FOLDER / f"{variable}_{point}.json.gz" in files, (variable, point)
    for path in files:
        rec = read(path)
        s = data.get_series(rec["variable"], rec["lat"], rec["lon"], source="era5")
        assert (s["times"], s["values"]) == (rec["times"], rec["values"]), path.name
        src = s["source"]
        assert src["retrieved"] == rec["retrieved"] and src["attribution"] == upstream.COPERNICUS
        assert src["record_url"] == era5.request_url(era5.PARAMS[rec["variable"]], rec["lat"], rec["lon"], era5.month_end(rec["times"][-1]))
        assert s["flags"] == era5.flags(rec["times"], rec["retrieved"]), path.name


def test_detect_trend_runs_offline_on_the_recording(replay):
    t = tools.detect_trend("air_temp", 28.6139, 77.2090, source="era5")  # Delhi, rounded to 28.61, 77.21
    assert t["source"]["id"] == "era5" and t["source"]["retrieved"] == read(FOLDER / "air_temp_28.61_77.21.json.gz")["retrieved"]
    assert t["verdict"] in {"rising", "falling", "no_clear_change"}


def test_replay_reads_the_recording_through_the_monthly_path(tmp_path, monkeypatch):
    times = [f"{y}-{m:02d}" for y in range(2000, 2003) for m in range(1, 13)]
    values = [None if i == 5 else round(20 + i / 7, 2) for i in range(36)]
    write(tmp_path, "precip", 28.61, 77.21, "2026-11-23", times, values)
    monkeypatch.setenv(era5.REPLAY, str(tmp_path))
    s = data.get_series("precip", 28.61, 77.21, source="era5")
    assert (s["times"], s["values"]) == (times, values) and s["source"]["retrieved"] == "2026-11-23"


def test_preliminary_months_survive_replay(tmp_path, monkeypatch):
    # recorded 2027-01-15 with data through December 2026: October to December may still hold ERA5T days
    times = [f"{y}-{m:02d}" for y in (2025, 2026) for m in range(1, 13)]
    values = [round(30 + i / 10, 2) for i in range(24)]
    write(tmp_path, "air_temp_max", 28.61, 77.21, "2027-01-15", times, values)
    monkeypatch.setenv(era5.REPLAY, str(tmp_path))
    monkeypatch.setattr(upstream, "utc_today", lambda: "2027-06-01")  # replayed months later
    s = data.get_series("air_temp_max", 28.61, 77.21, source="era5")
    assert era5.PRELIMINARY_MONTHS == 3 and s["flags"] == [None] * 21 + ["preliminary"] * 3
    assert s["values"] == values and s["source"]["retrieved"] == "2027-01-15"
    assert "end_date=2026-12-31" in s["source"]["record_url"]  # the request made then: through its last recorded month
    monkeypatch.delenv(era5.REPLAY)
    assert set(era5.flags(times, "2027-06-01")) == {None}  # a live fetch that day would flag nothing


def test_a_missing_recording_fails_clearly(tmp_path, monkeypatch):
    write(tmp_path, "air_temp", 28.61, 77.21, "2026-11-23", ["2025-01"], [1.0])
    monkeypatch.setenv(era5.REPLAY, str(tmp_path))
    with pytest.raises(ValueError, match=r"^No recorded ERA5 series for precip at 0\.0, 0\.0 in "):
        data.get_series("precip", 0, 0, source="era5")


def test_a_replay_folder_has_one_recording_date(tmp_path, monkeypatch):
    write(tmp_path, "air_temp", 1.0, 2.0, "2026-11-22", ["2025-01"], [1.0])
    write(tmp_path, "precip", 1.0, 2.0, "2026-11-23", ["2025-01"], [1.0])
    monkeypatch.setenv(era5.REPLAY, str(tmp_path))
    with pytest.raises(ValueError, match="must hold recordings from one date"):
        data.get_series("air_temp", 1, 2, source="era5")


def test_the_recorder_refuses_a_reply_from_open_meteo():
    import importlib.util

    import httpx
    spec = importlib.util.spec_from_file_location("rec", Path(__file__).parent.parent / "scripts" / "record_era5_replay.py")
    rec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rec)
    reply = httpx.Response(200, request=httpx.Request("GET", "https://archive-api.open-meteo.com/v1/archive?x=1"))
    with pytest.raises(SystemExit, match="Refusing archive-api.open-meteo.com"):
        rec.refuse_open_meteo(reply.url)
    rec.refuse_open_meteo(httpx.URL("https://bhoomi.earth/api/series"))  # the app passes
    # a redirect to Open-Meteo is refused before it is sent: only the app is ever asked
    asked = []

    def app(request):
        asked.append(request.url.host)
        return httpx.Response(302, headers={"Location": "https://archive-api.open-meteo.com/v1/archive?x=1"})
    with rec.make_client(transport=httpx.MockTransport(app)) as client:
        with pytest.raises(SystemExit, match="Refusing archive-api.open-meteo.com"):
            client.get("https://bhoomi.earth/api/series")
    assert asked == ["bhoomi.earth"]
