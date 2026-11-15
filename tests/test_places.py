import json
from pathlib import Path

import httpx
import pytest

from earthtrends.data import places, search_places

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "places_search.json").read_text())  # written from the documented shape


@pytest.fixture(autouse=True)
def fresh_cache():
    places._lookup.cache_clear()
    yield
    places._lookup.cache_clear()


def fake(monkeypatch, body=FIXTURE, status=200, calls=None):
    def get(url, params=None, timeout=None):
        if calls is not None:
            calls.append(params)
        content = body if isinstance(body, bytes) else json.dumps(body).encode()
        return httpx.Response(status, content=content, request=httpx.Request("GET", url))
    monkeypatch.setattr(places.httpx, "get", get)


def test_shape_and_missing_fields(monkeypatch):
    fake(monkeypatch)
    r = search_places("princeton")
    assert r["source"] == places.SOURCE
    assert r["results"][0] == {"name": "Princeton", "admin1": "New Jersey", "country": "United States",
                               "country_code": "US", "lat": 40.34872, "lon": -74.65905}
    assert r["results"][2] == {"name": "Oceanless Place", "admin1": None, "country": None, "country_code": None, "lat": 10.5, "lon": 20.25}


def test_no_results_key(monkeypatch):
    fake(monkeypatch, {"generationtime_ms": 0.4})
    assert search_places("zzzz")["results"] == []


def test_bad_items_skipped_and_capped(monkeypatch):
    good = {"name": "A", "latitude": 1, "longitude": 2}
    bad = [{"latitude": 1, "longitude": 2}, {"name": "", "latitude": 1, "longitude": 2}, {"name": "B", "latitude": 91, "longitude": 0},
           {"name": "C", "latitude": 0, "longitude": 181}, {"name": "D", "latitude": "1", "longitude": 2}, {"name": "E", "latitude": None, "longitude": 2},
           {"name": "F", "latitude": float("nan"), "longitude": 2}, "junk", {"name": "G", "latitude": True, "longitude": 2}, {"name": "H", "latitude": 10**400, "longitude": 0}]
    fake(monkeypatch, {"results": bad + [good] * 8})
    r = search_places("anything")["results"]
    assert len(r) == 5 and all(x["name"] == "A" for x in r)


@pytest.mark.parametrize("q", ["", " a ", "x" * 81, None])
def test_bad_length_refused(q):
    with pytest.raises(ValueError):
        search_places(q)


def test_cache_and_param(monkeypatch):
    calls = []
    fake(monkeypatch, calls=calls)
    search_places("  New   York & Co #1 ")
    search_places("New York & Co #1")
    assert len(calls) == 1 and calls[0]["name"] == "New York & Co #1" and calls[0]["count"] == 10


def test_long_text_is_cut(monkeypatch):
    fake(monkeypatch, {"results": [{"name": "n" * 500, "admin1": "a" * 500, "country": "c" * 500, "country_code": "k" * 500, "latitude": 1, "longitude": 2}]})
    r = search_places("long")["results"][0]
    assert [len(r[k]) for k in ("name", "admin1", "country", "country_code")] == [100] * 4


def test_failures_raise_and_are_not_cached(monkeypatch):
    fake(monkeypatch, status=500)
    with pytest.raises(httpx.HTTPStatusError):
        search_places("princeton")
    fake(monkeypatch, body=b"<html>maintenance</html>")
    with pytest.raises(httpx.DecodingError):
        search_places("princeton")
    fake(monkeypatch, body=b'{"results": [{"name": "A", "latitude": 1' + b"0" * 5000 + b', "longitude": 2}]}')  # past the integer-digit limit
    with pytest.raises(httpx.DecodingError):
        search_places("princeton")
    fake(monkeypatch, body=b"[" * 200000 + b"]" * 200000)  # nesting too deep for the parser
    with pytest.raises(httpx.DecodingError):
        search_places("princeton")
    fake(monkeypatch, body=[1, 2])
    with pytest.raises(httpx.DecodingError):
        search_places("princeton")
    fake(monkeypatch)
    assert search_places("princeton")["results"]


def hit(name, pop="absent", admin1=None):
    h = {"name": name, "admin1": admin1, "latitude": 1, "longitude": 2}
    if pop != "absent":
        h["population"] = pop
    return h


def test_ranking_princeton(monkeypatch):  # a real reply, in upstream order: type first, so New Jersey came sixth
    rows = [("Indiana", 8626), ("Illinois", 7594), ("Kentucky", 6174), ("West Virginia", 6035), ("Missouri", 1133),
            ("New Jersey", 29603), ("Texas", 8939), ("Minnesota", 4680), ("Massachusetts", 3412), ("North Carolina", 1284)]
    fake(monkeypatch, {"results": [hit("Princeton", p, a) for a, p in rows]})
    r = search_places("princeton")["results"]
    assert [x["admin1"] for x in r] == ["New Jersey", "Texas", "Indiana", "Illinois", "Kentucky"]
    assert all("population" not in x for x in r)


def test_exact_name_beats_bigger_prefix_match(monkeypatch):
    fake(monkeypatch, {"results": [hit("Yorktown", 200000), hit("York", 150000)]})
    assert [x["name"] for x in search_places("  york ")["results"]] == ["York", "Yorktown"]


def test_odd_populations_count_as_zero(monkeypatch):
    fake(monkeypatch, {"results": [hit("Ab", None, "n"), hit("Ab", 10**400, "huge"), hit("Ab", True, "bool"), hit("Ab", -5, "neg"),
                                   hit("Ab", "9", "str"), hit("Ab", float("nan"), "nan"), hit("Ab", 3, "three"), hit("Ab", 0, "zero")]})
    r = search_places("ab")["results"]
    assert [x["admin1"] for x in r] == ["three", "n", "huge", "bool", "neg"]  # then upstream order for the zeros


def test_fewer_than_five_all_returned(monkeypatch):
    fake(monkeypatch, {"results": [hit("Ab", 1), hit("Ab", 2)]})
    assert len(search_places("ab")["results"]) == 2
