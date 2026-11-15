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
  },
  "guidance": {
    "risk": "moderate",
    "risk_label": "Moderate risk",
    "why": "It is warming here about as fast as the world average.",
    "ratio": 1.0,
    "reference": {"text": "World average for land and ocean together: about 0.20 °C every 10 years since 1975.", "source": {"name": "NOAA Climate.gov: Climate Change: Global Temperature", "url": "https://www.climate.gov/news-features/understanding-climate/climate-change-global-temperature"}},
    "rate": {"value": 0.21, "unit": "°C", "text": "+0.21 °C", "per": "every 10 years"},
    "display": {"unit": "°C", "factor": 1},
    "recommendation": "It has been getting warmer here. Build cooling and shade into long-term plans.",
    "outlook_label": "If the past trend continues",
    "outlook": [{"year": 2050, "low": 0.3, "high": 0.7, "unit": "°C", "text": "+0.3 to +0.7 °C by 2050"}],
    "future_link": null,
    "disclaimer": "This guidance isn't perfect. It is based only on past records, and the future is not certain. Not professional financial or legal advice."
  }
}
```

- `verdict`: `"rising"` | `"falling"` | `"no_clear_change"` (p ≥ 0.05 or CI crosses 0).
- `slope_per_decade` is in `units` per decade.
- `meaning` (added 2026-11-14, always the last field): the result in plain words, computed in code from the fields above (`earthtrends/stats/meaning.py`), so the page, the agent and outside clients show the same words and no one redoes the arithmetic.
  - `headline`: one sentence by variable and verdict.
  - `confidence`: `"Very clear"` (rising or falling with p < 0.001) | `"Clear"` (any other rising or falling verdict) | `"Not clear"` (no clear change).
  - `comparison`: the rate per 10 years in familiar units, rounded to 1 significant figure (2 when the first digit is 1), half away from zero; sea level of 10 mm or more is shown in cm, rainfall as mm a year. It is `""` when there is no clear change, the variable is unknown, the units are not the catalog's for that variable, the slope is 0 or not a finite number, or the slope's sign would contradict the verdict.
  - `limit`: one sentence on what past data cannot tell.
  - All four are strings and are always present. Show them as text; add no number of your own to them.
- `guidance` (added 2026-11-15, after `meaning`, always the last field): a risk level and a recommendation worded for decisions, computed in code (`earthtrends/stats/guidance.py`) from the fields above by the rules in `docs/RISK.md`. The page, the agent and outside clients show these strings as they are; nobody else works out a risk, a recommendation or a future figure.
  - `risk`: `"high"` | `"moderate"` | `"low"` | `"unknown"`; `risk_label`: `"High risk"` | `"Moderate risk"` | `"Low risk"` | `"Not enough data"`.
  - `why`: one plain sentence on the reason. `ratio`: the trend against the reference rate (a number), or `null` where the rule uses no world rate. `reference`: `{"text", "source": {"name", "url"} | null}` naming what the trend was compared with, or `null`.
  - `rate`: the change per 10 years in familiar units (`value`, `unit`, signed `text`, `per`), or `null` when there is no clear change. `display`: the familiar unit and the factor that turns values in `units` into it.
  - `recommendation`: one or two sentences for the risk level and measurement.
  - `outlook`: for 2035, 2050 and 2075, the range the past trend would reach if it simply continued (`ci_low` and `ci_high` × the decades from the last data year), with `text` ready to show under the label `outlook_label` ("If the past trend continues"). It is `[]` unless the verdict is rising or falling and the record spans at least 30 years. It is not a forecast and is never called one.
  - `future_link`: `{"label", "url"}` to an official projection tool (sea level only), or `null`.
  - `disclaimer`: one sentence, always present, shown wherever `recommendation` is shown.
  - All keys are always present. Show the strings as text; add no number of your own to them.

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

The UI calls the same three functions through `/api/variables`, `/api/series` and `/api/trend`, so the UI and outside agents see identical results.

## Web routes that are not MCP tools — served by `earthtrends/app.py`, UI lane consumes

The page calls these three routes on its own origin. Outside agents use the MCP tools above instead.

### `GET /api/places?q=<text>` — place search by name (data lane's `search_places`)

```json
{
  "results": [
    {"name": "Princeton", "admin1": "New Jersey", "country": "United States", "country_code": "US", "lat": 40.34872, "lon": -74.65905}
  ],
  "source": {"name": "Open-Meteo Geocoding API (GeoNames)", "url": "https://open-meteo.com/en/docs/geocoding-api"}
}
```

- At most 5 results: places whose name equals the typed text first, then the largest population first (the upstream service is asked for 10 and orders by place type, which can put the largest place past the fifth). `admin1`, `country` and `country_code` can be `null`. Text fields are cut to 100 characters and are untrusted text: show them as text, never as HTML.
- No match: `"results": []` with status 200. Every 200 answer carries `source`.
- `q` is trimmed and single-spaced; fewer than 2 or more than 80 characters is a 400. A missing `q` is a 422. An upstream failure is a 502. The data rate limit applies (429 with `Retry-After`). Never a 500.

### `GET /api/gauges` — where tide gauges are, for the map (data lane's station lists)

```json
{
  "gauges": [
    {"name": "The Battery", "lat": 40.7006, "lon": -74.0142, "source": "coops"},
    {"name": "NEW YORK (THE BATTERY)", "lat": 40.7, "lon": -74.0133, "source": "psmsl"}
  ],
  "sources": [
    {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/"},
    {"id": "psmsl", "name": "Permanent Service for Mean Sea Level (PSMSL), RLR monthly means", "url": "https://psmsl.org/"}
  ]
}
```

- No parameters. CO-OPS gauges first, then PSMSL, each in its list's own order; about 2,000 in all. A gauge in both lists appears twice. Latitude and longitude are rounded to 4 decimals. Names are as the lists give them (PSMSL names are in capitals).
- It says where gauges are. It does not say whether a gauge has enough years of readings for a trend: `detect_trend` and `/api/trend` decide which gauge answers.
- One list unavailable: status 200 with the other list alone, only its entry in `sources`, and a short cache time. Both unavailable: 502. The data rate limit applies (429 with `Retry-After`).

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

- `question`: a string of 1 to 500 characters after trimming; outside that is a 400; missing is a 422.
- `history` (optional): earlier turns of the same chat, oldest first. At most 6 messages and 4,000 characters in total; whole pairs in order (`user`, then `assistant`); each `content` a non-empty string; no other keys. Anything outside these limits is a 400 with a plain message; nothing is trimmed. Leaving it out, `null`, or `[]` means a question on its own.
- Earlier turns are text only. They are used to understand the question (which place, measurement, period or source); every number in the answer comes from this turn's tool results.
- Answers that looked something up end with the tool's own guidance for each result (risk level, why, recommendation, the 2050 outlook, then the disclaimer once and any official future-map link). Code inserts these strings from `guidance` word for word; the model adds no recommendation and no future number of its own (added 2026-11-15).
- Limits per network address: 30 questions a minute and 150 an hour (raised 2026-11-15 from 10 and 100, because the page's voice and text assistant asks on visitors' behalf from a few shared addresses); 200 an hour over all callers, unchanged.
- Any other top-level field is refused (422).
