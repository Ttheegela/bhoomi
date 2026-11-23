"""NOAA lists some UK stations just west of Greenwich with the longitude's minus sign lost (ghcn.LOST_MINUS)."""
import json
from math import cos, radians
from pathlib import Path

import httpx
import pytest

from earthtrends.data import ghcn
from earthtrends.data.coops import haversine_km

# NOAA's real station search reply for TMAX around London, 2026-11-22
LONDON = json.loads((Path(__file__).parent / "fixtures" / "ghcn_search_london.json").read_text())


def test_hampstead_is_west_of_greenwich_and_7_km_from_london():
    found = {s["id"]: s for s in ghcn.parse_search(LONDON)}
    raw = next(r for r in LONDON["results"] if r["stations"][0]["id"] == "UKE00105915")
    assert raw["boundingPoints"][0]["coordinates"] == [0.1789, 51.5608]  # as NOAA lists it
    assert round(haversine_km(51.51, -0.13, 51.5608, 0.1789)) == 22  # what the page said before
    assert (found["UKE00105915"]["lat"], found["UKE00105915"]["lon"]) == (51.5608, -0.1789)
    st, km, _ = ghcn.ranked(51.51, -0.13, list(found.values()), "air_temp_max")[0]  # London
    assert st["id"] == "UKE00105915" and round(km) == 7
    assert found["UKE00107650"]["lon"] == -0.4489  # Heathrow (ECA&D); NOAA's own UKM00003772 Heathrow is at -0.461
    assert found["UKE00105901"]["lon"] == 0.4308 and found["UKE00105657"]["lon"] == 0.46  # Writtle, Goudhurst: really east


def test_search_box_reaches_where_noaa_lists_them(monkeypatch):
    asked = []

    def get(url, params):
        asked.append([float(x) for x in params["bbox"].split(",")])  # N, W, S, E
        return httpx.Response(200, json=LONDON, request=httpx.Request("GET", url))
    monkeypatch.setattr(ghcn, "_get", get)
    found = ghcn.search.__wrapped__(51.24, -0.57, ("TMAX",))  # Guildford: Wisley is 10 km away, listed at +0.4744
    assert asked[-1][1] < -1.3 and asked[-1][3] == 1.0  # the box would end at 0.19 E
    st, km, _ = ghcn.ranked(51.24, -0.57, found, "air_temp_max")[0]
    assert st["id"] == "UKE00156884" and round(km) == 10
    ghcn.search.__wrapped__(47.61, -122.33, ("TMAX",))  # far from Greenwich: the box is unchanged
    dlon = ghcn.MAX_KM / 111 * 1.05 / cos(radians(47.61))
    assert asked[-1][1] == pytest.approx(-122.33 - dlon, abs=1e-3) and asked[-1][3] == pytest.approx(-122.33 + dlon, abs=1e-3)
