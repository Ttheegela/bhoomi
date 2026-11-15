# Contracts (frozen at hour 0, Sat 2026-11-14)

Every lane codes against these shapes, so nobody waits on anybody. To change one after the freeze: open a PR that edits only this file (plus the code that must follow), and tag every lane that uses the shape.

Numbers in the examples are illustrative, not real results.

## Source ids

One variable can come from several sources. Tools take an optional `source`; results say which one they used.

| id | Dataset | Covers |
|---|---|---|
| `power` | NASA POWER (MERRA-2), https://power.larc.nasa.gov/ | any point, 1981 on |
| `era5` | ERA5 reanalysis via Open-Meteo archive, https://open-meteo.com/ | any point, 1940 on |
| `ghcn` | NOAA NCEI GHCN-Daily, nearest station, https://www.ncei.noaa.gov/ | weather stations worldwide |
| `coops` | NOAA CO-OPS tide gauges, nearest station, https://tidesandcurrents.noaa.gov/ | US coasts |
| `psmsl` | Permanent Service for Mean Sea Level (PSMSL), RLR monthly means, nearest tide gauge, https://psmsl.org/ | tide gauges worldwide |
| `grace` | NASA GSFC GRACE and GRACE-FO mascons, RL06 v2.0, https://earth.gsfc.nasa.gov/geo/data/grace-mascons | land, 2002 on; a value is a regional average about 400 km across |

## TimeSeries — data lane produces, stats lane consumes

```json
{
  "variable": "air_temp",
  "units": "degC",
  "freq": "monthly",
  "place": {"name": "Visakhapatnam", "lat": 17.69, "lon": 83.22},
  "times": ["1981-01", "1981-02", "..."],
  "values": [24.1, 25.3, null],
  "source": {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"},
  "notes": ["Grid cell about 50 km wide, not a single station."]
}
```

- `freq`: `"daily"` | `"monthly"` | `"annual"`. `times` are ISO strings at that resolution.
- `values`: same length as `times`; `null` for missing.
- For a station source (`ghcn`, `coops`), `place.name` is the station name and `notes` says how far it is from the point asked for.

## TrendResult — stats lane produces, agent and UI lanes consume

```json
{
  "variable": "air_temp",
  "units": "degC",
  "place": {"name": "Visakhapatnam", "lat": 17.69, "lon": 83.22},
  "period": {"start": "1981-01", "end": "2025-12"},
  "n": 540,
  "deseasonalized": true,
  "method": "mann_kendall_sen",
  "slope_per_decade": 0.21,
  "ci_low": 0.12,
  "ci_high": 0.30,
  "p_value": 0.003,
  "autocorrelation_adjusted": true,
  "verdict": "rising",
  "source": {"id": "power", "name": "NASA POWER (MERRA-2)", "url": "https://power.larc.nasa.gov/"},
  "caveats": ["Grid cell about 50 km wide, not a single station."],
  "meaning": {
    "headline": "It has clearly been getting warmer here.",
    "confidence": "Clear",
    "comparison": "About 0.2 °C warmer every 10 years.",
    "limit": "This is what has already been measured. It cannot tell you how hot it will get."
  }
}
```

- `verdict`: `"rising"` | `"falling"` | `"no_clear_change"` (p ≥ 0.05 or CI crosses 0).
- `slope_per_decade` is in `units` per decade.
- `meaning` (added 2026-11-14, always the last field): the result in plain words, computed in code from the fields above (`earthtrends/stats/meaning.py`), so the page, the agent and outside clients show the same words and no one redoes the arithmetic.
  - `headline`: one sentence by variable and verdict.
  - `confidence`: `"Very clear"` (rising or falling with p < 0.001) | `"Clear"` (any other rising or falling verdict) | `"Not clear"` (no clear change).
  - `comparison`: the rate in familiar units, rounded to about one significant figure; `""` when there is no clear change, when the units are not the catalog's for that variable, or when the slope's sign would contradict the verdict.
  - `limit`: one sentence on what past data cannot tell.
  - All four are strings and are always present. Show them as text; add no number of your own to them.

## Variable catalog entry — data lane maintains

```json
{"id": "air_temp", "name": "Air temperature (2 m)", "units": "degC", "sources": ["power", "era5", "ghcn"], "start_year": 1981, "resolution": "~50 km grid", "good_for": "heat, long-term warming"}
```

- `sources`: source ids that have this variable. The first one is the default.

## MCP tools — agent lane exposes (names and inputs are the contract)

| Tool | Inputs | Returns |
|---|---|---|
| `list_variables` | none | list of catalog entries |
| `get_series` | `variable`, `lat`, `lon`, `start?`, `end?`, `source?` | `TimeSeries` |
| `detect_trend` | `variable`, `lat`, `lon`, `start?`, `end?`, `source?` | `TrendResult` |

- `source` left out: use the variable's default source; for `sea_level`, if the default source has no tide gauge within 100 km of the point, the next source in the variable's list is used. A point with no gauge in any source gives a clear 4xx. A source the variable doesn't have, an unknown variable, a bad lat/lon, or a point with no data gives a clear 4xx error, never a 500.

The UI calls the same functions through FastAPI routes under `/api/`, so the UI and outside agents see identical results.

## Web routes that are not MCP tools — agent lane exposes, UI lane consumes

The page calls these two routes on its own origin. Outside agents use the MCP tools above instead.

### `GET /api/places?q=<text>` — place search by name (data lane's `search_places`)

```json
{
  "results": [
    {"name": "Princeton", "admin1": "New Jersey", "country": "United States", "country_code": "US", "lat": 40.34872, "lon": -74.65905}
  ],
  "source": {"name": "Open-Meteo Geocoding API (GeoNames)", "url": "https://open-meteo.com/en/docs/geocoding-api"}
}
```

- At most 5 results, in the upstream order. `admin1`, `country` and `country_code` can be `null`. Text fields are cut to 100 characters and are untrusted text: show them as text, never as HTML.
- No match: `"results": []` with status 200. Every answer carries `source`.
- `q` is trimmed and single-spaced; fewer than 2 or more than 80 characters is a 400. A missing `q` is a 422. An upstream failure is a 502. The data rate limit applies (429 with `Retry-After`). Never a 500.

### `POST /api/ask` — a question for the agent

Request:

```json
{
  "question": "ok what about Jakarta?",
  "history": [
    {"role": "user", "content": "Is sea level rising in New York?"},
    {"role": "assistant", "content": "Yes. Sea level is clearly rising at The Battery ..."}
  ]
}
```

- `question`: 1 to 500 characters.
- `history` (optional): earlier turns of the same chat, oldest first. At most 6 messages and 4,000 characters in total; whole pairs in order (`user`, then `assistant`); each `content` a non-empty string; no other keys. Anything outside these limits is a 400 with a plain message; nothing is trimmed. Leaving it out, or `[]`, means a question on its own.
- Earlier turns are text only. They are used to understand the question (which place, which measurement); every number in the answer comes from this turn's tool results.
- Any other top-level field is refused (422).
