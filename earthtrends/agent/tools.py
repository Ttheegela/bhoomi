"""The features behind both doors: MCP tools (mcp_server.py) and /api/ routes (app.py)."""
from concurrent.futures import ThreadPoolExecutor

from earthtrends import data
from earthtrends.stats import compute_trend, records
from earthtrends.stats.baseline import anomaly, baseline


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


def _outcome(f):
    try:
        return f.result()
    except Exception as e:  # noqa: BLE001 - the row says what went wrong; the answer goes on
        return e


def detect_trend(variable: str, lat: float, lon: float, start: str | None = None,
                 end: str | None = None, source: str | None = None, compare: bool = True) -> dict:
    """The TrendResult. For air temperature, hottest day and rain it also sets the other records beside the main one
    (contract "Records for this place (PR4a)"): they are read in parallel threads while the main one is, from the
    same caches, and `compare=False` leaves the four fields null (the page draws the card first)."""
    entry = next((v for v in data.list_variables() if v["id"] == variable), None)
    order = entry["sources"] if compare and entry and variable in records.VARIABLES else []
    main = source or (order[0] if order else None)
    order = order if main in order else []  # a source the measurement doesn't have: the main read gives the 400
    pool = ThreadPoolExecutor(max_workers=max(len(order) - 1, 1)) if order else None
    try:
        others = {sid: pool.submit(_windowed, variable, lat, lon, start, end, sid) for sid in order if sid != main}
        s, full, base = _windowed(variable, lat, lon, start, end, source)
        r = compute_trend(s, base=base)
        # "now" and the projection: the whole record, not the window
        if full is not s and r["variable"] in ("sea_level", "air_temp", "air_temp_max", "precip"):
            whole = compute_trend(full, base=base)
            r["now"], r["projection"] = whole["now"], whole["projection"]
        extra = dict.fromkeys(("comparisons", "comparisons_window", "disagree", "drift"))
        if order:
            try:
                extra = records.compare(variable, [(main, (s, full, base))] +
                                        [(sid, _outcome(f)) for sid, f in others.items()], lat, lon)
            except Exception:  # noqa: BLE001 - the records block must never sink the main answer
                pass
    finally:
        if pool:
            pool.shutdown(wait=False, cancel_futures=True)  # a failed main read doesn't wait for the others
    tail = {k: r.pop(k) for k in ("meaning", "guidance")}  # the contract keeps these two last
    return {**r, **extra, **tail}
