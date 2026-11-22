"""coops.fetch asks for a gauge's whole record in requests of at most 73,000 days (NOAA's limit for monthly means),
going back from today, and joins them oldest first with no gap and no duplicate month. Offline: a synthetic server."""
from datetime import date

import httpx
import pytest

from earthtrends.data import coops

TODAY = date.today()


def server(monkeypatch, first_year, older=None):
    """A fake CO-OPS datagetter for a gauge with monthly means from January first_year to last December: each request
    gets the rows in its range, or NOAA's 400 "No data was found" reply; with `older` (status, body), every request
    after the first gets that instead. Returns the requests' (begin, end) dates."""
    asked = []

    def get(url, params, timeout):
        b, e = date.fromisoformat(params["begin_date"]), date.fromisoformat(params["end_date"])
        assert params["datum"] == "MSL" and params["units"] == "metric" and params["product"] == "monthly_mean"
        asked.append((b, e))
        if older and len(asked) > 1:
            return httpx.Response(older[0], json=older[1], request=httpx.Request("GET", url))
        rows = [{"year": str(y), "month": str(m), "MSL": "0.1"} for y in range(max(first_year, b.year), min(TODAY.year - 1, e.year) + 1)
                for m in range(1, 13)]
        body = ({"metadata": {"id": params["station"]}, "data": rows} if rows else
                {"error": {"message": "No data was found. This product may not be offered at this station at the requested time."}})
        return httpx.Response(200 if rows else 400, json=body, request=httpx.Request("GET", url))
    monkeypatch.setattr(coops.httpx, "get", get)
    return asked


def check(asked, first_year):
    assert asked[0][1] == TODAY  # the newest request ends today
    for b, e in asked:
        assert b <= e and (e - b).days < 73000  # within NOAA's limit
    for (b_new, _), (_, e_old) in zip(asked, asked[1:]):
        assert (b_new - e_old).days == 1  # each older request ends the day before the newer one begins: no gap, no overlap
    assert asked[-1][0].year <= first_year  # the requests reach the gauge's first month


def test_one_request_covers_a_gauge_from_the_1850s(monkeypatch):
    asked = server(monkeypatch, 1856)
    times, values = coops.parse(coops.fetch("8518750"))
    assert asked == [(date(TODAY.year - 198, 1, 1), TODAY)]  # no extra request: 1828 is before every CO-OPS gauge
    check(asked, 1856)
    assert times[0] == "1856-01" and times[-1] == f"{TODAY.year - 1}-12" and len(times) == len(set(times)) == (TODAY.year - 1856) * 12


def test_a_record_older_than_one_request_is_fetched_in_chunks_and_joined_in_order(monkeypatch):
    asked = server(monkeypatch, 1700)
    reply = coops.fetch("8518750")
    assert len(asked) == 2  # the second request's data starts after its first January: no third request
    check(asked, 1700)
    keys = [(int(r["year"]), int(r["month"])) for r in reply["data"]]
    assert keys == sorted(keys) and len(keys) == len(set(keys)) and reply["metadata"] == {"id": "8518750"}
    times, values = coops.parse(reply)
    assert times[0] == "1700-01" and len(times) == len(set(times)) == (TODAY.year - 1700) * 12 and values[0] == 100.0


def test_a_record_starting_on_a_chunk_boundary_stops_at_noaas_no_data_reply(monkeypatch):
    first = TODAY.year - 198  # data in the first request's first January: one more request, which has nothing
    asked = server(monkeypatch, first)
    times, _ = coops.parse(coops.fetch("8518750"))
    assert len(asked) == 2
    check(asked, first)
    assert times[0] == f"{first}-01" and len(times) == len(set(times)) == (TODAY.year - first) * 12


def test_an_older_request_failing_another_way_raises_instead_of_cutting_the_record_short(monkeypatch):
    """Only NOAA's "No data was found" ends the record early. Any other reply to an older request (a 400 with another
    error, a 200 carrying `error`, a 200 without a data list) raises parse()'s error, as the first request's would;
    _record makes it a provider failure, so a record cut short is never cached as the gauge's whole record."""
    first = TODAY.year - 198  # data in the first request's first January: the second request is made
    for n, older in enumerate([(400, {"error": {"message": "Wrong Station ID"}}),
                               (200, {"error": {"message": "Internal error"}}), (200, {"metadata": {}})]):
        asked = server(monkeypatch, first, older)
        with pytest.raises(ValueError, match="^No monthly sea level at this station: "):
            coops.fetch("8518750")
        assert len(asked) == 2, older
        server(monkeypatch, first, older)
        with pytest.raises(httpx.DecodingError):
            coops._record(f"older-fails-{n}")
