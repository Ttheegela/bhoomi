"""The features behind both doors: MCP tools (mcp_server.py) and /api/ routes (app.py)."""
import time
from concurrent.futures import ThreadPoolExecutor, wait as wait_for

from earthtrends import data
from earthtrends.stats import compute_trend, records
from earthtrends.stats.baseline import anomaly, baseline


# Ask and MCP: how long detect_trend gives the other records (contract "Ask and MCP"); a row not back by then is
# "pending", and its read finishes in the background, which warms the cache. The page's /api/trend waits for all.
BUDGET_S = 8.0
MAIN_NOTE = "{} couldn't be read just now; showing {}."  # contract "Main record fallback"


def list_variables() -> list[dict]:
    return data.list_variables()


def _windowed(variable: str, lat: float, lon: float, start: str | None, end: str | None,
              source: str | None) -> tuple[dict, dict, dict]:
    """(the series for start/end, the whole series, its baseline). The baseline never depends on the window: a
    windowed request reads the full record again from the resolved source (the series cache makes that free), so the
    sea-level fallback to PSMSL lands on the same source."""
    s = data.get_series(variable, lat, lon, start=start, end=end, source=source)
    full = s if start is None and end is None else data.get_series(variable, lat, lon, source=s["source"]["id"])
    return s, full, baseline(full)


def get_series(variable: str, lat: float, lon: float, start: str | None = None,
               end: str | None = None, source: str | None = None) -> dict:
    """The data lane's TimeSeries plus `anomaly`: each value against the fixed 1995-2014 baseline."""
    s, _, base = _windowed(variable, lat, lon, start, end, source)
    return {**s, "anomaly": anomaly(s, base)}


def _outcome(f, done: bool):
    if not done:
        return records.Pending()
    try:
        return f.result()
    except Exception as e:  # noqa: BLE001 - the row says what went wrong; the answer goes on
        return e


def detect_trend(variable: str, lat: float, lon: float, start: str | None = None,
                 end: str | None = None, source: str | None = None, compare: bool = True,
                 wait: bool = False) -> dict:
    """The TrendResult. For air temperature, hottest day and rain it also sets the other records beside the main one
    (contract "Records for this place (PR4a)"): they are read in parallel threads while the main one is, from the
    same caches, for at most BUDGET_S from the call (Ask and MCP), or for as long as they take with `wait` (the
    page). `compare=False` leaves those fields null (the page draws the card first).
    Main record fallback: with no source named, a default record that can't be read (an outage or a refusal, not bad
    input and not "no data here") gives way to the next one in catalog order, and `main_note` says so."""
    deadline = time.monotonic() + BUDGET_S
    entry = next((v for v in data.list_variables() if v["id"] == variable), None)
    order = entry["sources"] if entry and variable in records.VARIABLES else []
    main = source or (order[0] if order else None)
    order = order if main in order else []  # a source the measurement doesn't have: the main read gives the 400
    reads = [sid for sid in order if sid != main] if compare else []
    pool = ThreadPoolExecutor(max_workers=max(len(reads), 1)) if reads else None
    try:
        got = {sid: pool.submit(_windowed, variable, lat, lon, start, end, sid) for sid in reads}
        note = None
        try:
            s, full, base = _windowed(variable, lat, lon, start, end, source)
        except Exception as e:
            if source is not None or len(order) < 2 or records.failed(e)[0] != "error":
                raise
            gone, main = main, order[1]
            s, full, base = got.pop(main).result() if main in got else _windowed(variable, lat, lon, start, end, main)
            note = MAIN_NOTE.format(records.LABEL[gone], records.LABEL[main])
            if compare:
                got[gone] = e  # its row reads "error"; the read is not tried again
        r = compute_trend(s, base=base)
        # "now" and the projection: the whole record, not the window
        if full is not s and r["variable"] in ("sea_level", "air_temp", "air_temp_max", "precip"):
            whole = compute_trend(full, base=base)
            r["now"], r["projection"] = whole["now"], whole["projection"]
        extra = dict.fromkeys(("comparisons", "comparisons_window", "disagree", "drift"))
        if got:
            futures = [f for f in got.values() if not isinstance(f, BaseException)]
            if not wait:
                wait_for(futures, timeout=max(0.0, deadline - time.monotonic()))
            rows = [(sid, got[sid] if isinstance(got[sid], BaseException) else _outcome(got[sid], wait or got[sid].done()))
                    for sid in order if sid != main]  # the main record first, then catalog order
            try:
                extra = records.compare(variable, [(main, (s, full, base))] + rows, lat, lon)
            except Exception:  # noqa: BLE001 - the records block must never sink the main answer
                pass
    finally:
        if pool:
            pool.shutdown(wait=False)  # a late or failed read finishes in the background and fills the cache
    tail = {k: r.pop(k) for k in ("meaning", "guidance")}  # the contract keeps these two last
    return {**r, "main_note": note, **extra, **tail}
