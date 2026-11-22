# Contracts (frozen at hour 0, Sat 2026-11-14; Rework v2 added Sun 2026-11-22)

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

## Rework v2 (2026-11-22): self-describing series, one baseline, like-for-like comparisons

Build brief: `docs/REWORK-SPEC.md` (decisions D1–D8). These shapes replace the older fields where they overlap; every lane codes against them. Shapes added later in the rework (expert projections, PR2 and PR3) are marked "PR2/PR3" and are `null` until then.

### Source block (every TimeSeries and TrendResult) — data lane fills it

```json
"source": {
  "id": "power",
  "name": "NASA POWER (MERRA-2)",
  "url": "https://power.larc.nasa.gov/",
  "dataset_id": "NASA POWER monthly point data, parameter T2M (MERRA-2)",
  "version": "POWER API v2",
  "record_url": "https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=T2M&community=AG&latitude=40.35&longitude=-74.66&start=1981&end=2025&format=JSON",
  "retrieved": "2026-11-22",
  "method": "Monthly mean of the daily 2 m air temperature for the MERRA-2 grid cell (about 50 km).",
  "cadence": "monthly",
  "deseasoned_upstream": false
}
```

- `url` stays the provider's home page. `record_url` opens **this** record: the exact request we made, or the station or dataset page by ID, and the page it opens names our station or coordinates (REWORK-SPEC PR1 item 2 lists the form per source).
- `dataset_id`: a DOI (as `doi:10.…`) or the provider's catalogue name. `version`: the release or API version we read, as the provider names it, or `null` if the provider names none.
- `reference_period` (GRACE only): `[first_year, last_year]` of the provider's own reference mean for the release we ship, as the provider documents it; the stats lane uses it as the baseline (`method` `"provider"`).
- `retrieved`: UTC date (YYYY-MM-DD) the values were fetched from the provider (a cached value keeps its first fetch date).
- `method`: one plain sentence on how the provider made the values we use. `cadence`: the cadence of `values` (`"monthly"` | `"annual"`). `deseasoned_upstream`: true only when the provider has already removed the seasonal cycle.

### TimeSeries additions — data lane

- `flags`: same length as `values`; each `null` or `"preliminary"` (a value the provider says may still change). Stats leaves preliminary values out of the baseline and the trend fit; the chart marks them.
- `anomaly` (added by the stats lane in `get_series` and `/api/series`; the data lane does not fill it):

```json
"anomaly": {"kind": "difference", "units": "degC", "values": [-0.42, 0.18, null], "baseline": {"...": "the Baseline object below"}}
```

  - `kind`: `"difference"` (value minus the 1995–2014 mean of its calendar month) or `"percent"` (rainfall: the same difference as a percentage of the 1995–2014 annual mean rate, so dry months never divide by a small number). `values` is `null` wherever `values` is `null` or there is no baseline.

### Baseline object — stats lane

```json
"baseline": {
  "text": "the 1995–2014 average",
  "years": [1995, 2014],
  "method": "observed",
  "label": null,
  "years_covered": 20,
  "value": 11.84,
  "months": [0.4, 1.6, 5.9, 11.4, 16.9, 21.9, 24.6, 23.8, 19.9, 13.6, 8.2, 3.1],
  "projection_axis": true
}
```

- `method`: `"observed"` (at least 15 of the 20 years have 9 or more valid months), `"fitted"` (coverage short, but the record spans 30 or more years, starts in 1995 or earlier and runs to 2014 or later, so the fit never runs past the data: trend plus harmonics fitted, then its 1995–2014 mean; `label` is "baseline estimated from the fitted trend"), `"provider"` (GRACE only: the provider's own reference period in `years`, with `label` naming it), or `"none"` (no baseline possible; `value` and `months` are `null`).
- `value`: the baseline level in the series `units` (the mean of `months`). `months`: the twelve calendar-month normals, January first, or `null`. `annual_total_mm`: for rainfall only, the 1995–2014 mean rate × 365.25 in mm a year (1 decimal), so pages say "about 1,160 mm a year" without converting; `null` for every other measurement or without a baseline.
- `projection_axis`: false when the record starts after 2014, or `method` is `"none"` or `"provider"` (GRACE is not on the 1995–2014 axis). Such a record is shown on its own chart, never on the projection axis.

### TrendResult additions and changes — stats lane

- `source`: the full source block above (copied from the series).
- `baseline`: the Baseline object. Every level the page, the agent, the CSV or "How we calculated this" shows is against it. It is always computed from the whole series, whatever `start` and `end` the request asks for, so a windowed request shows levels against the same 1995–2014 average.
- `record`: `{"years": 44.9, "coverage": 0.98, "status": "ok", "trimmed_from": null}`. `years`: span of the fitted data; `coverage`: valid share of expected months in that span. `status` `"ok"`, or `"short"` for a 20–29 year record (shown, labelled "short record"). When coverage over the whole series is under 80%, the fit starts at the first value of the earliest calendar year from which coverage to the last month is at least 80%; `trimmed_from` is then the series' first valid month (otherwise `null`), and a caveat says where the trend starts. If no such window reaches 20 years (GRACE: 10), there is no trend: a 400 with a plain message, as for any other bad input. The baseline always uses the whole series.
- `range_kind`: `"95% range"`, the name of `ci_low`…`ci_high` wherever they are shown.
- `headline_rate`: the trend rate in the unit people read, with its 95% range, so no page or agent converts it: `{"value": 4.25, "low": 4.11, "high": 4.40, "unit": "mm", "per": "a year", "text": "+4.3 mm a year", "range_text": "+4.1 to +4.4 mm a year"}`. Sea level is always mm a year (the world's unit); air temperature and hottest day °C per decade; rainfall % of the 1995–2014 normal per decade; water storage cm of water a year. Every rate shown anywhere (card, sidebar, table, chart readout, "How we calculated this", agent) is this one. It is `null` only for rainfall without a 1995–2014 average above zero (no baseline, or an average of zero: no percent can be computed); show the verdict and the rate in mm a day there. Levels (`fit`, `anomaly`) keep the series units, except rainfall (in % of the 1995–2014 annual normal), and sea level may be displayed in cm.
- `fit`: the headline change, read from the fitted line, never from the last raw month: `{"start": "1981-01", "end": "2025-12", "years": 44.9, "change": 1.4, "change_low": 1.0, "change_high": 1.8, "level_end": 0.6, "units": "degC"}`. `change*` are slope × span; `level_end` is the fitted line's level at the last data month against the baseline (`null` without a baseline).
- `latest`: `{"month": "2025-12", "text": "Data through December 2025"}`: the last valid value, preliminary included.
- `world`: the like-for-like world comparison (D5).

```json
"world": {
  "available": true,
  "measure": "average for all land areas",
  "local_rate": 0.31, "world_rate": 0.29, "unit": "°C per decade",
  "window": {"start": "1981-01", "end": "2025-12"},
  "method": "Sen's slope of monthly anomalies, same months for both",
  "ratio": 1.1,
  "thresholds": {"moderate": 0.75, "high": 1.5},
  "source": {"name": "NOAA NCEI Climate at a Glance, global land", "dataset_id": "…", "record_url": "…", "retrieved": "2026-11-22"},
  "text": "Over the same years, the average for all land areas warmed 0.29 °C per decade. Here: 0.31 °C per decade.",
  "why_none": null
}
```

  - Air temperature: local Sen slope against the global land-only Sen slope over exactly the same months. `method` names the method and then the kinds of record, e.g. "Sen's slope of monthly anomalies, same months for both; different datasets: a grid cell here, station-based for the world". Sea level: the gauge's Sen slope over 1993 to its last month against satellite global mean sea level over the same months, in mm a year; needs at least 20 of those years. The full-record rate stays in `slope_per_decade` with no ratio.
  - `available: false` (with every number `null` and `why_none` one plain sentence) for hottest day ("There is no matching world figure for the hottest day of the month."), rainfall and water storage (own-place rules, printed in `text`), and a sea-level gauge with under 20 years since 1993.
- `projection` (PR2/PR3): the expert projection for this place. Until then `{"available": false, "why": "…"}`. For water storage it stays so, with `why` "There is no standard expert projection for total water storage, so we don't show one."
- `explain`: the extra numbers "How we calculated this" needs, from the same computation as everything above:

```json
"explain": {
  "data": {"n_months": 540, "n_missing": 3, "start": "1981-01", "end": "2025-12", "where": "a grid cell about 50 km wide"},
  "seasons": {"high_month": 7, "high": 24.6, "low_month": 1, "low": 0.4, "swing": 24.2, "units": "degC"},
  "real": {"p_value": 0.003, "in_100": "less than 1", "rule": "We call a change clear when that chance is under 5 in 100 and the whole 95% range is on one side of zero.", "widened": true}
}
```

  - `seasons` uses the baseline's calendar-month normals (`null` for `method` `"none"` or annual data). Rainfall seasons are in mm a month (`units` "mm a month"); rainfall `fit` is in % of the 1995–2014 annual normal, like `anomaly` and `headline_rate`, when there is a baseline; without one it stays in mm/day with `level_end` `null`. `real.widened`: true when the range was widened for months that are alike (autocorrelation).
- `guidance` changes: `outlook` and `outlook_label` are removed (D1: no future from a past trend). `ratio` and `reference` come from `world` (`null` when `world.available` is false). Hottest day of the month has no risk level: `risk` and `risk_label` are `null`, and so are `why` and `recommendation`; the verdict alone answers. A `no_clear_change` verdict is not evidence of low risk: `risk` is `null` and `risk_label` is "No clear change" (the recommendation and disclaimer stay). Every other key is unchanged and always present.

### World reference series — data lane, stats lane reads

`earthtrends.data.world.reference(name)` returns a TimeSeries (with the full source block) from a snapshot file kept in the repo and refreshed by `scripts/update_world.py`; nothing is fetched per request.

| name | What | Units |
|---|---|---|
| `land_temp` | Global land-only monthly air temperature anomaly, from a published series with an exact URL | degC |
| `gmsl` | Satellite global mean sea level, 1993 on, monthly | mm |

### CSV download — UI lane builds it from the fields above

```
# Bhoomi: Air temperature at Princeton, New Jersey
# Source: NASA POWER (MERRA-2)
# Dataset: NASA POWER monthly point data, parameter T2M (MERRA-2); version: POWER API v2
# Record: https://power.larc.nasa.gov/api/temporal/monthly/point?…
# Baseline: the 1995–2014 average (observed); anomaly = value minus the 1995–2014 mean of its calendar month
# Method: Monthly mean of the daily 2 m air temperature for the MERRA-2 grid cell (about 50 km).
# Retrieved: 2026-11-22
# Built with AI assistance. bhoomi.earth
time,value_degC,anomaly_degC,flag
1981-01,-0.8,-1.2,
```

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
    "why": "It is warming here about as fast as the average for all land areas over the same years.",
    "ratio": 1.0,
    "reference": {"text": "Over the same years, the average for all land areas warmed 0.29 °C per decade. Here: 0.31 °C per decade.", "source": {"name": "NOAA NCEI Climate at a Glance, global land", "url": "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/"}},
    "rate": {"value": 0.21, "unit": "°C", "text": "+0.21 °C", "per": "every 10 years", "note": null},
    "display": {"unit": "°C", "factor": 1},
    "recommendation": "It has been getting warmer here. Build cooling and shade into long-term plans.",
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
  - `comparison`: the rate per 10 years in familiar units, rounded to 1 significant figure (2 when the first digit is 1), half away from zero; sea level is shown in mm a year and water storage in cm of water a year (Rework v2, matching `headline_rate`), rainfall as mm a year. It is `""` when there is no clear change, the variable is unknown, the units are not the catalog's for that variable, the slope is 0 or not a finite number, or the slope's sign would contradict the verdict.
  - `limit`: one sentence on what past data cannot tell.
  - All four are strings and are always present. Show them as text; add no number of your own to them.
- `guidance` (added 2026-11-15, after `meaning`, always the last field): a risk level and a recommendation worded for decisions, computed in code (`earthtrends/stats/guidance.py`) from the fields above by the rules in `docs/RISK.md`. The page, the agent and outside clients show these strings as they are; nobody else works out a risk, a recommendation or a future figure.
  - `risk`: `"high"` | `"moderate"` | `"low"` | `"unknown"` | `null`; `risk_label`: `"High risk"` | `"Moderate risk"` | `"Low risk"` | `"Not enough data"` | `"No clear change"` | `null` (Rework v2: `null` risk with "No clear change" for an unclear trend; both `null` for the hottest day).
  - `why`: one plain sentence on the reason. `ratio`: the trend against the reference rate (a number), or `null` where the rule uses no world rate. `reference`: `{"text", "source": {"name", "url"} | null}` naming what the trend was compared with, or `null`.
  - `rate` (Rework v2: sea level and water storage read "a year", matching `headline_rate`): the change per 10 years in familiar units (`value`, `unit`, signed `text`, `per`, `note`), or `null` when there is no clear change. For rainfall it is the share of the place's usual rainfall, with the amount in `note`: `{"value": 4.8, "unit": "%", "text": "+4.8%", "per": "more rain every 10 years", "note": {"value": 60, "unit": "mm", "text": "about 60 mm more a year"}}` (falling: `"−4.8%"`, `"less rain every 10 years"`, a negative `note.value`, `"about 60 mm less a year"`). `note` is `null` for every other measurement. `display`: the familiar unit and the factor that turns values in `units` into it.
  - `recommendation`: one or two sentences for the risk level and measurement.
  - `outlook` and `outlook_label`: removed 2026-11-22 (Rework v2, D1).
  - `future_link`: `{"label", "url"}` to an official projection tool (sea level only), or `null`. Every URL it carries must answer 200 when checked (the NASA AR6 projection tool URL answered 404 on 2026-11-22 and is removed).
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
- Answers that looked something up end with the tool's own guidance for each result (risk level, why, recommendation, then the disclaimer once and any official future-map link; the 2050 outlook was removed 2026-11-22). Code inserts these strings from `guidance` word for word; the model adds no recommendation and no future number of its own (added 2026-11-15).
- Limits per network address: 30 questions a minute and 150 an hour (raised 2026-11-15 from 10 and 100, because the page's voice and text assistant asks on visitors' behalf from a few shared addresses); 200 an hour over all callers, unchanged.
- Any other top-level field is refused (422).
