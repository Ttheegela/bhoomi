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

- `method`: `"observed"` (at least 15 of the 20 years have 9 or more valid months), `"fitted"` (coverage short, but the record spans 30 or more years, at least 5 of the 20 years count, and there are data before 1995 and after 2014, so the fit never runs past the data: trend plus harmonics fitted, then its 1995–2014 mean; `label` is "baseline estimated from the fitted trend"), `"provider"` (GRACE only: the provider's own reference period in `years`, with `label` naming it), or `"none"` (no baseline possible; `value` and `months` are `null`). An `"observed"` baseline with fewer than 20 counted years is trend-adjusted (domain review F6): each month's normal is shifted by slope × (2004.5 − that month's mean counted year), the slope a least-squares line plus harmonics over the counted 1995–2014 values.
- `value`: the baseline level in the series `units` (the mean of `months`; for rainfall the day-weighted mean, February 28.25 days, so it is the 1995–2014 annual total / 365.25). `months`: the twelve calendar-month normals, January first, or `null`. `annual_total_mm`: for rainfall only, the 1995–2014 mean rate × 365.25 in mm a year (1 decimal), so pages say "about 1,160 mm a year" without converting; `null` for every other measurement or without a baseline.
- `projection_axis`: false when the record starts after 2014, or `method` is `"none"` or `"provider"` (GRACE is not on the 1995–2014 axis). Such a record is shown on its own chart, never on the projection axis.

### TrendResult additions and changes — stats lane

- `source`: the full source block above (copied from the series).
- `baseline`: the Baseline object. Every level the page, the agent, the CSV or "How we calculated this" shows is against it. It is always computed from the whole series, whatever `start` and `end` the request asks for, so a windowed request shows levels against the same 1995–2014 average.
- `record`: `{"years": 44.9, "coverage": 0.98, "status": "ok", "trimmed_from": null}`. `years`: span of the fitted data; `coverage`: valid share of expected months in that span. `status` `"ok"`, or `"short"` for a 20–29 year record (shown, labelled "short record"). When coverage over the whole series is under 80%, the fit starts at the first value of the earliest calendar year from which coverage to the last month is at least 80%; `trimmed_from` is then the series' first valid month (otherwise `null`), and a caveat says where the trend starts. If no such window reaches 20 years (GRACE: 10), there is no trend: a 400 with a plain message, as for any other bad input. The baseline always uses the whole series.
- `range_kind`: `"95% range"`, the name of `ci_low`…`ci_high` wherever they are shown.
- `headline_rate`: the trend rate in the unit people read, with its 95% range, so no page or agent converts it: `{"value": 4.25, "low": 4.11, "high": 4.40, "unit": "mm", "per": "a year", "text": "+4.3 mm a year", "range_text": "+4.1 to +4.4 mm a year"}`. Sea level is always mm a year (the world's unit); air temperature and hottest day °C per decade; rainfall % of the 1995–2014 normal per decade; water storage cm of water a year. Every rate shown anywhere (card, sidebar, table, chart readout, "How we calculated this", agent) is this one. It is `null` only for rainfall without a 1995–2014 average above zero (no baseline, or an average of zero: no percent can be computed); show the verdict and the rate in mm a day there. Levels (`fit`, `anomaly`) keep the series units, except rainfall (in % of the 1995–2014 annual normal), and sea level may be displayed in cm.
- `fit`: the headline change, read from the fitted line, never from the last raw month: `{"start": "1981-01", "end": "2025-12", "years": 44.9, "change": 1.4, "change_low": 1.0, "change_high": 1.8, "level_end": 0.6, "units": "degC"}`. `change*` are slope × span; `level_end` is the fitted line's level at the last data month against the baseline (`null` without a baseline). The line has the Sen slope and passes through the mean of the anomalies at their mean time (not the median).
- `latest`: `{"month": "2025-12", "text": "Data through December 2025"}`: the last valid value, preliminary included.
- `now` (domain review F1): the measured level today, `{"value": 98, "units": "mm", "kind": "12-month mean", "start": "2025-11", "end": "2026-10", "n": 12, "text": "+9.8 cm", "label": "the 12 months to October 2026"}`: the mean of the 12 latest monthly anomalies against the baseline (at least 10 present), never the end of the trend line. Rainfall: `kind` "12-month total", the day-weighted mean of the 12 latest monthly % anomalies, i.e. how far the 12-month total is above or below the 1995–2014 annual normal, as % of that normal (0 in a normal year). Preliminary values are left out, so `now.end` can be earlier than `latest`. `null` without a baseline or with fewer than 10 of those months. The card's "Now" readout reads `now`; `fit` keeps "change over the record" and the drawn line.
- `world`: the like-for-like world comparison (D5).

```json
"world": {
  "available": true,
  "measure": "average for all land areas",
  "local_rate": 0.31, "world_rate": 0.29, "unit": "°C per decade",
  "window": {"start": "1981-01", "end": "2025-12"},
  "method": "Sen's slope of monthly anomalies, same months for both",
  "ratio": 1.1,
  "source": {"name": "NOAA NCEI Climate at a Glance, global land", "dataset_id": "…", "record_url": "…", "retrieved": "2026-11-22", "method": "…"},
  "text": "Over the same years, the average for all land areas warmed 0.29 °C per decade. Here: 0.31 °C per decade.",
  "why_none": null
}
```

  - Air temperature: local Sen slope against the global land-only Sen slope over exactly the same months. `method` names the method and then the kinds of record, e.g. "Sen's slope of monthly anomalies, same months for both; different datasets: a grid cell here, station-based for the world". Sea level: the gauge's Sen slope over 1993 to its last month against satellite global mean sea level over the same months, in mm a year; needs at least 20 of those years. The full-record rate stays in `slope_per_decade` with no ratio.
  - `ratio_low`, `ratio_high` (domain review F2): the ratio of the local rate's 95% range ends to the world rate over the same window. *(Superseded 2026-11-22 by "Facts, not advice": no risk levels; the ratio and its range are shown as facts.)* When they fall on different sides of a threshold (0.75 or 1.5), `guidance.risk_label` names both levels ("Moderate to high risk", "Low to moderate risk", or "Risk between low and high (wide range)" when the range spans both thresholds, so it reads as one idea next to a clear verdict (owner, 2026-11-22)), `guidance.risk` is the lower of the two, and the recommendation is the lower level's. `ratio` and both ends are `null` unless the verdict is rising or falling (no ratio for an unclear trend). Rainfall has no world ratio; its levels come from its own 95% range of the % rate against the rain thresholds, with the same two-level labels.
  - `available: false` (with every number `null` and `why_none` one plain sentence) for hottest day ("There is no matching world figure for the hottest day of the month."), rainfall and water storage (own-place rules, printed in `text`), and a sea-level gauge with under 20 years since 1993.
  - `available: true` with `why_none` set (rising or falling verdict only): the world rate over the same months is zero or negative, so `ratio`, `ratio_low` and `ratio_high` are `null` and `why_none` is "The world figure did not rise over these years, so there is no ratio." Both rates and `text` still show. Step 6 and the compare caption show `why_none` whenever it is set, not only when `available` is false.
- `projection` (PR2/PR3): the expert projection for this place. Until then `{"available": false, "why": "…"}`. For water storage it stays so, with `why` "There is no standard expert projection for total water storage, so we don't show one."
- `explain`: the extra numbers "How we calculated this" needs, from the same computation as everything above:

```json
"explain": {
  "data": {"n_months": 540, "n_missing": 3, "start": "1981-01", "end": "2025-12", "where": "a grid cell about 50 km wide"},
  "seasons": {"high_month": 7, "high": 24.6, "low_month": 1, "low": 0.4, "swing": 24.2, "units": "degC"},
  "real": {"p_value": 0.003, "in_100": "less than 1", "rule": "We call a change clear when that chance is under 5 in 100 and the whole 95% range is on one side of zero.", "widened": true}
}
```

  - `seasons` uses the baseline's calendar-month normals (`null` for `method` `"none"` or annual data). Rainfall's trend, verdict and `headline_rate` come from yearly totals (calendar years with at least 11 valid months), as % of the 1995–2014 annual normal per decade (domain review F4: monthly ranks overweight dry months); where the 1995–2014 annual normal is under 100 mm, `world.why_none` says so (see below). Rainfall seasons are in mm a month (`units` "mm a month"); rainfall `fit` is in % of the 1995–2014 annual normal, like `anomaly` and `headline_rate`, when there is a baseline; without one it stays in mm/day with `level_end` `null`. Rainfall also carries `yearly`: the values the test used, oldest first, `[{"year": 1981, "value": 3.2}]` in `fit.units` (% of the 1995–2014 annual normal, or mm/day without a baseline); the chart plots these for rain, with `fit` drawn through them. Other measurements have no `yearly` key. For rainfall, `n` counts calendar years, and `explain.data` adds `n_years` and `n_missing_years`; fewer than 20 calendar years with 11 or more valid months is a 400 with a plain message. Where the annual normal is under 100 mm, `world.why_none` is "Rain here averages under 100 mm a year, so a small change in millimetres is a large percentage." (facts, not advice: no level rule exists; a 1995–2014 normal of zero has no % at all and gives "Not enough data"). `real.widened`: true when the factor on Var(S) is at least 1.2 (range about 10% or more wider). The factor is the larger of the lag-1 AR(1) factor and the variance ratio of 12-value block means, times the AR(1) factor of those block means, each floored at 1 (chosen by simulation: 95–99% coverage for short memory, about 90% for tide-gauge-like records; annual series use the lag-1 factor alone).
- *(Superseded 2026-11-22 by "Facts, not advice" for `risk`, `risk_label`, `why` and `recommendation`.)* `guidance` changes: `outlook` and `outlook_label` are removed (D1: no future from a past trend). `ratio` and `reference` come from `world` (`null` when `world.available` is false). Hottest day of the month has no risk level: `risk` and `risk_label` are `null`, and so are `why` and `recommendation`; the verdict alone answers. A `no_clear_change` verdict is not evidence of low risk: `risk` is `null` and `risk_label` is "No clear change" (the recommendation and disclaimer stay). A clear rising verdict for a measurement compared with the world (a falling sea or cooling is "Low risk" without the world figure), when `world.available` is false (QA B3: Mumbai, 147 years but under 20 since 1993): `risk` is `null`, `risk_label` is "No world comparison", `why` comes from `world.why_none`, and the recommendation is one that doesn't depend on a level. "Not enough data" is kept for records too short to judge. Every other key is unchanged and always present.

### Sea-level expert projection (PR2) — stats lane fills `projection` for `sea_level`

From IPCC AR6 relative sea level at the tide gauge (`earthtrends/data/ar6_gauges.npz`, built offline by `scripts/build_ar6.py`). Plotted and quoted exactly as published (D4): never shifted to meet the observations. All levels in mm against the 1995–2014 average; the page shows cm.

```json
"projection": {
  "available": true,
  "kind": "sea_level_ar6",
  "source": {"name": "IPCC AR6 sea level projections (Garner et al. 2021)", "dataset_id": "doi:10.5281/zenodo.6382554", "version": "20210809", "record_url": "https://doi.org/10.5281/zenodo.6382554", "licence": "CC BY 4.0", "citation": ["…", "…", "…"], "acknowledgement": "…"},
  "location": {"kind": "gauge", "id": 12, "name": "NEW YORK (THE BATTERY)", "km": 0.4, "note": null},
  "baseline": {"text": "the 1995–2014 average", "years": [1995, 2014]},
  "units": "mm",
  "years": [2020, 2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100, 2110, 2120, 2130, 2140, 2150],
  "default_scenario": "ssp245_medium",
  "scenarios": [
    {"id": "ssp245_medium", "code": "SSP2-4.5", "name": "intermediate emissions", "confidence": "medium",
     "range_kind": "likely range (about 2 in 3 chance)", "outer_kind": "5th to 95th percentile",
     "p05": [], "p17": [], "p50": [], "p83": [], "p95": [],
     "rate": {"units": "mm a year", "p05": [], "p17": [], "p50": [], "p83": [], "p95": []}}
  ],
  "drivers": {"year": 2050, "scenario": "ssp245_medium", "parts": [
     {"id": "sterodynamic", "name": "Ocean warming and currents", "p17": 0, "p50": 181, "p83": 0},
     {"id": "greenland", "name": "Greenland ice", "p17": 0, "p50": 13, "p83": 0},
     {"id": "antarctica", "name": "Antarctic ice", "p17": 0, "p50": 34, "p83": 0},
     {"id": "glaciers", "name": "Mountain glaciers", "p17": 0, "p50": 46, "p83": 0},
     {"id": "land_water", "name": "Water stored on land", "p17": 0, "p50": 9, "p83": 0},
     {"id": "land_motion", "name": "Land rising or sinking here", "p17": 0, "p50": 68, "p83": 0}],
     "note": "Each part's range is its own; the parts' ranges don't add up to the total's."},
  "readouts": {
    "now": {"value": 65.6083, "units": "mm", "kind": "12-month mean", "start": "2025-11", "end": "2026-10", "n": 12, "text": "+6.6 cm", "label": "the 12 months to October 2026"},
    "by_2050": {"scenario": "ssp245_medium", "p50": 358, "low": 266, "high": 464, "range_kind": "likely range (about 2 in 3 chance)", "text": "+36 cm (likely +27 to +46 cm)"},
    "more_than_today": {"value": 292, "text": "about 29 cm more than today", "approximate": true}},
  "check": {"observed_2019_2021": 80, "ar6_2020_p05": 0, "ar6_2020_p95": 0, "kind": "2019-2021", "latest": null, "inside": true},
  "caveat": "Faster ice-sheet loss could push this higher, outside this range.",
  "why": null
}
```

- Scenarios, named as the IPCC names them: SSP1-2.6 ("low emissions"), SSP2-4.5 ("intermediate emissions"), SSP3-7.0 ("high emissions"), SSP5-8.5 ("very high emissions") at medium confidence, plus SSP1-2.6, SSP2-4.5 and SSP5-8.5 at low confidence (ids end `_low`, `range_kind` "17th to 83rd percentile", never "likely"). Arrays follow `years`; `null` where AR6 has no value.
- `location.kind`: `"gauge"` (the AR6 PSMSL gauge: the PSMSL id itself; for a PSMSL gauge AR6 doesn't list, the AR6 gauge within 3 km, or within 15 km when the names share a word; for a CO-OPS station, its row in `coops_to_psmsl.csv`) or `"regional estimate"` (the AR6 1° cell; `note` says the land motion is AR6's regional estimate and local sinking may differ). A Great Lakes station, or a place with no AR6 location: `available` false with `why` "Sea level projections don't cover the Great Lakes." / "There is no expert projection for this tide gauge."
- `readouts.now`: the mean of the 12 latest monthly anomalies (against the same 1995–2014 baseline as the chart), with its months; `null` if fewer than 10 of those 12 months have values. `by_2050`: the default scenario's 2050 median and range. `more_than_today`: `by_2050.p50` minus `now.value`; its `text` says "than today", or "than in {year}" when the record ended more than 2 years ago (the server chooses, the page prints it as given), labelled approximate (different kinds of number: a 12-month mean and a 2050 projection). Rounded for text to 2 significant figures.
- `check`: the observed 2019–2021 mean on the baseline (needs at least 24 of the 36 months; otherwise `observed_2019_2021` and `inside` are `null`) against AR6's 2020 5th–95th percentile at this location (`inside` false is shown in "How we calculated this", never hidden: about 1 in 7 gauges fall outside, mostly for real reasons such as earthquakes, fast land uplift or a recent regional surge).
- `check.kind`: `"2019-2021"` when that check ran; `"latest 12 months"` when 2019–2021 has fewer than 24 months and the check falls back to `now` (QA B1, e.g. Mumbai): `latest` is then `{"value": now in whole mm, "year": the 12-month window's mid-year (2 decimals), "ar6_p05", "ar6_p95"}`, AR6's 5th–95th percentile for the default scenario linearly interpolated to that year; `null` when neither could run (no `now`, off the projection axis, or a mid-year before 2020). `inside` comes from whichever check ran.
- `drivers`: the default scenario's 2050 parts with their own 17th–83rd percentiles.
- Every sea-level answer keeps `world`, `fit` and the rest of PR1 unchanged; `projection` only adds. One exception: when `projection.available` is true, `guidance.disclaimer` says the future values are IPCC projections that depend on emission scenarios and are not predictions (domain review of the PR2 design); without a projection it stays as in PR1. `readouts.now` equals the TrendResult's `now` (the same 12-month mean, same keys). Like the baseline, `now` and `projection` always come from the whole series, whatever `start` and `end` the request asks for: "now" means the latest 12 months, never the end of a window. `more_than_today.value` is whole mm. Charts break the axis at 2100: AR6 values after 2100 come from a different set of model runs.

### CMIP6 expert projection (PR3) — stats lane fills `projection` for `air_temp`, `air_temp_max` and `precip`

From the IPCC AR6 Interactive Atlas's CMIP6 monthly data (`earthtrends/data/cmip6_atlas.npz` with its manifest `cmip6_atlas.json`, built offline by `scripts/build_cmip6.py` from the Copernicus copy, whose values were checked bit for bit against the CSIC originals; the example's numbers are illustrative). For each 1° cell, scenario and 20-year window, the change of each model's 20-year mean against that model's own 1995–2014 mean, then the 10th, 50th and 90th percentile across models (D7: "range across climate models (10th–90th percentile)"). Delta method (D4): the projected level is this place's observed 1995–2014 mean plus the change, so on the chart's 1995–2014 anomaly axis it is the change itself; never a raw model value, never shifted to meet the observations.

```json
"projection": {
  "available": true,
  "kind": "cmip6_atlas",
  "source": {"name": "IPCC AR6 Interactive Atlas, CMIP6 projections", "dataset_id": "doi:10.20350/digitalCSIC/15492", "version": "v2.0-final", "record_url": "https://digital.csic.es/handle/10261/332744",
             "retrieved_from": {"name": "Gridded monthly climate projection dataset underpinning the IPCC AR6 Interactive Atlas (Copernicus Climate Data Store)", "dataset_id": "doi:10.24381/cds.5292a2b0", "url": "https://cds.climate.copernicus.eu/datasets/projections-climate-atlas"},
             "licence": "CC BY 4.0", "citation": ["…"], "acknowledgement": "…"},
  "location": {"kind": "land cell", "lat": 40.5, "lon": -74.5, "km": 31, "land_pct": 78, "note": null},
  "baseline": {"text": "the 1995–2014 average", "years": [1995, 2014]},
  "units": "degC",
  "change_kind": "difference",
  "windows": [{"start": 2021, "end": 2040, "mid": 2030}, {"start": 2041, "end": 2060, "mid": 2050}, {"start": 2081, "end": 2100, "mid": 2090}],
  "default_scenario": "ssp245",
  "scenarios": [
    {"id": "ssp245", "code": "SSP2-4.5", "name": "intermediate emissions",
     "range_kind": "range across climate models (10th–90th percentile)",
     "p10": [0.9, 1.3, 2.1], "p50": [1.1, 1.7, 2.7], "p90": [1.4, 2.2, 3.6], "models": [33, 33, 33],
     "agree": null, "disagree": null}
  ],
  "readouts": {
    "now": {"value": 0.62, "units": "degC", "kind": "12-month mean", "start": "2025-07", "end": "2026-06", "n": 12, "text": "+0.62 °C", "label": "the 12 months to June 2026"},
    "by_2050": {"scenario": "ssp245", "window": [2041, 2060], "p50": 1.7, "low": 1.3, "high": 2.2, "range_kind": "range across climate models (10th–90th percentile)", "text": "+1.7 °C (range across climate models +1.3 to +2.2 °C)", "disagree": null},
    "more_than_today": {"value": 1.1, "text": "about 1.1 °C more than today", "approximate": true}},
  "caveat": "A 1° grid cell is about 100 km wide, so hills or a coast nearby can make the change here differ.",
  "models_note": "These are the climate models' raw results. The IPCC's assessed warming, which also uses past observations, is a little lower for the world as a whole.",
  "baseline_record": {"id": "power", "name": "NASA POWER (MERRA-2)"},
  "why": null
}
```

- `source`: the stats lane sets `name` "IPCC AR6 Interactive Atlas, CMIP6 projections", `version` "v2.0-final" and `licence` "CC BY 4.0" (as sea level writes it); `dataset_id`, `record_url`, `retrieved_from` (the dataset's own title, DOI and URL), `citation` and `acknowledgement` come from the manifest via `earthtrends/data/cmip6.py` `at()`, copied exactly.
- Scenarios, named as for sea level: `ssp126` SSP1-2.6 ("low emissions"), `ssp245` SSP2-4.5 ("intermediate emissions"), `ssp370` SSP3-7.0 ("high emissions"), `ssp585` SSP5-8.5 ("very high emissions"); default `ssp245`. No confidence levels (CMIP6 spread is not AR6's assessed likely range). Arrays follow `windows`; `null` where the cell has no value. `models`: how many models are behind each window's percentiles.
- `units` and `change_kind`: `air_temp` "degC" and "difference" (the change of the 20-year mean of daily mean temperature); `air_temp_max` "degC" and "difference" (the change of the 20-year mean of each month's hottest day, the same "hottest day of the month" the record measures); `precip` "%" and "percent" (the change of the 20-year mean as % of the model's own 1995–2014 mean, on the same 0-centred axis as the rain chart's yearly values). Text rounds to 2 significant figures with the page's rules (°C with a true minus; rain "+4%"); a range's two ends share the same decimals, by the same rule as `headline_rate.range_text` (Chennai rain "+11% (range across climate models −3 to +24%)"). Values under 1 keep 2 significant figures ("−0.040 °C").
- `agree` and `disagree` (rain only; `null` otherwise): per window, the share of models agreeing on the sign of the change (`max(wetter, models − wetter) / models`, 2 decimals), and `disagree` true when that share is under 0.8. The page then says "Models disagree on wetter or drier" for that window, and `readouts.by_2050.disagree` carries the 2041–2060 value.
- `location`: from `earthtrends/data/cmip6.py` `nearest_land_cell` (the Atlas's rule: a cell is land when at least 50% of it is land). `kind` "land cell" (the place's own cell), "nearest land cell" (one of its 8 neighbours, when the place's cell is mostly ocean; `note` "The place's own grid cell is mostly ocean, so this uses the nearest land cell.") or "regional estimate (mostly ocean cell)" (`note`: temperature and hottest day "The models' grid cell here is mostly ocean, which warms less than land."; rain "The models' grid cell here is mostly ocean, so the change over land nearby can differ."). `lat`/`lon` are the cell centre, `km` the distance from the place to it (whole km), `land_pct` the cell's land share.
- `caveat`: temperature and hottest day "A 1° grid cell is about 100 km wide, so hills or a coast nearby can make the change here differ."; rain "Climate models disagree more about rain than about temperature, and a 1° grid cell is about 100 km wide, so hills or a coast nearby can make the change here differ."
- `models_note` (domain review of the PR3 design): temperature and hottest day "These are the climate models' raw results. The IPCC's assessed warming, which also uses past observations, is a little lower for the world as a whole."; rain `null`. The Atlas uses the raw, unweighted CMIP6 ensemble, whose world-mean SSP5-8.5 2081–2100 median (+3.87 °C against 1995–2014 in our pack) is above AR6's assessed best estimate (about +3.5 °C against 1995–2014). The page shows it under the projection's readout line and in "Things to keep in mind"; MCP passes it on with the projection. Ask does not see the projection yet (PR6 adds it there).
- `baseline_record`: the record whose observed 1995–2014 mean the delta method starts from: the answer's own main record (`id` and `name` as in the source list: ERA5, NASA POWER or a station), never fixed to one dataset. Step 7 names it.
- `readouts.now`: the TrendResult's `now` (same keys). `by_2050`: the default scenario's 2041–2060 window. `more_than_today`: `by_2050.p50` minus `now.value`, labelled approximate (a 12-month mean against a 20-year projection), "than today" or "than in {year}" as for sea level; `null` for rain and for hottest day (one year's rain or hottest days swing more than the change: Delhi's hottest day read "about 2.9 °C more than today" after a cool year, QA of PR3) and when `now` is `null`. So only air temperature carries it.
- `available: false` with every other key `null` and `why` one plain sentence when the record has no 1995–2014 average to start from (`projection_axis` false, or rain whose 1995–2014 normal is 0 or missing): "This record has no 1995–2014 average to start the projection from, so we don't show one."; and when the cell has no value, including when the default scenario's 2041–2060 value is missing even if other scenarios or windows have one (about 20 rain cells): "The climate models have no value for this place." Water storage keeps its PR1 `why`; sea level is PR2's.
- When `projection.available` is true, `guidance.disclaimer` is the projection disclaimer, as for sea level. Like sea level, `now` and `projection` come from the whole series whatever `start` and `end` the request asks for. The chart shows the three windows' medians at their mid-years with the selected scenario's 10th–90th range, after the observed record; no annual model values.

### Records for this place (PR4a, owner's decisions 2026-11-22) — stats lane fills it; UI, agent and MCP show it

The owner's decisions: **air temperature and the hottest day** take ERA5 as the main record (chart, 95% band, card, the projection's `baseline_record`), with NASA POWER and the nearest weather station within 25 km beside it; **rain** keeps NASA POWER (gauge-corrected) as the main record, with ERA5 and the station beside it. Facts only: the answer never says which record to trust. Design and exact strings: `web/design/12-two-sources.md` (§3–§11).

For `air_temp`, `air_temp_max` and `precip`, `detect_trend` and `/api/trend` add three fields. The server fetches the other two records in parallel with the main one, from the same per-point caches; the other records' series are never sent to the page.

```json
"comparisons": [
  {"main": true, "source": {"id": "era5", "name": "ERA5 reanalysis via Open-Meteo archive", "record_url": "https://…"},
   "label": "ERA5", "kind": "grid", "where": "Weather model, grid cell about 25 km wide", "km": null, "station": null,
   "status": "ok", "available": true, "why": null, "years": "1981–2026", "n_months": 549, "n_missing": 0, "n_preliminary": 3,
   "baseline_value": 33.6, "verdict": "no_clear_change", "confidence": "Not clear", "p_value": 0.09, "in_100": "9",
   "headline_rate": {"value": 0.13, "low": -0.02, "high": 0.27, "unit": "°C", "per": "per decade", "text": "+0.13 °C per decade", "range_text": "−0.02 to +0.27 °C per decade"}, "note": null, "counted": true},
  {"main": false, "source": {"id": "ghcn", "…": "…"}, "label": "Weather station", "kind": "station", "where": "New Delhi Safdarjung, 3 km away",
   "km": 3.4, "station": {"id": "IN022021900", "name": "New Delhi Safdarjung"}, "status": "ok", "n_missing": 77,
   "note": null, "counted": true, "…": "…"}],
"disagree": {"any": true, "line": "The records disagree here.",
  "say": "ERA5 shows no clear change. NASA POWER shows the hottest days getting less hot. The weather station shows them getting hotter.",
  "reasons": [{"id": "model_drift", "text": "…"}, {"id": "station_gaps", "text": "…"}]},
"drift": {"source": "power", "label": "NASA POWER", "direction": "cooling", "unit": "°C", "per": "per decade",
  "pairs": [{"against": "era5", "rate": -0.39, "low": -0.52, "high": -0.25}],
  "text": "Weather models can drift over decades at some places; at this spot NASA POWER has been cooling relative to the other records."}
```
(Illustrative numbers.)

- **Default and order.** Catalog `sources`: `air_temp` and `air_temp_max` `["era5", "power", "ghcn"]`; `precip` `["power", "era5", "ghcn"]`. A request without `source` uses the first. The visitor can still make another record main (`source=`); the rows then follow the same order with that record first.
- **Main record fallback (2026-11-23, Open-Meteo's free limit):** when the caller names no source and the default main record can't be read (ERA5 for heat), the answer uses the next record in catalog order and sets top-level `main_note`: "ERA5 couldn't be read just now; showing NASA POWER." (`null` otherwise). Its comparison row for ERA5 is then status "error". A named source never falls back. The page prints `main_note` under the source line; Ask and MCP pass it.
- **Same years (domain review, D5 like-for-like; revised 2026-11-23):** every row's rate, range and verdict are computed over the same window, so the rows compare like with like; the card's headline keeps the main record's own full window. The window is set by the two gridded records only: the whole years common to ERA5 and NASA POWER. A station never shrinks it. The station row is computed inside the window from whatever months it has. A station year counts when it has at least 9 usable months; a model year needs all 12. `comparisons_window`: `{"start": 1981, "end": 2025, "label": "Same years for all: 1981 to 2025"}`, or `null` with `comparisons`.
- **`comparisons`:** the main record first (its numbers over the shared window, which can differ from the headline over its own full window), then the other model, then the station. `null` for sea level and water storage, and with `compare=false`. `status` is "ok", "none", "short", "error" or "pending" (Ask and MCP only, below); `available` is true only for "ok", otherwise `why` is one sentence (the station lane's messages at 25 km; an error is "We couldn't read this record just now."; pending is "Not loaded yet."). `years` is "{first year of fit}–{last year of fit}" (preliminary months excluded). `km` has 1 decimal. Each row's `headline_rate` follows the same rounding rules and text as the top-level one (`text` includes "per decade").
- **Thin station and `counted` (domain review 2026-11-23):** a station row with a trend is *thin* when it has fewer than 9 usable months in more than 2 of the window's last 10 years, or covers less than 80% of the window's months. A thin row stays in the table with its own verdict and a `note`, and is left out of agree/disagree and drift. `note`, first that applies: "Few readings after {last year with 9 or more months} ({min} to {max} months a year), so this row covers less and isn't counted when we compare." (when every later year in the window is short but has a reading; a station that simply stopped, with no reading in the window's last year, gets "Covers only …"), "Few readings in {n} of the last 10 years, so this row covers less and isn't counted when we compare.", "Covers only {years} of these years, so it isn't counted when we compare." ({years} is the row's own `years`), "Misses {pct}% of these years, so it isn't counted when we compare."; `null` otherwise. Every row has `counted`: true for an "ok" row that is not thin, false otherwise.
- **`disagree`:** built from counted rows only. `null` when fewer than two counted rows have a trend. `any` is true when any two counted verdicts differ. `line`: agree "All three records agree: {rising|falling|no clear change}." (or "Both records agree: …" with two counted rows); disagree "The records disagree here." `say`: one sentence per counted row, "{label} shows {phrase}." Phrases: air temperature "it getting warmer" / "it getting cooler"; hottest day "the hottest days getting hotter" / "the hottest days getting less hot"; rain "more rain" / "less rain"; otherwise "no clear change". `reasons`: `[]` when they agree; otherwise the first four that apply, in this order: `model_drift` (when `drift` is set; its text), `station_gaps` (the counted station row misses 10% or more of the months in its fit span), `near_line` (a counted row's `p_value` is between 0.01 and 0.15), `point_vs_grid` (a counted station row has a trend), `two_models` (both models have a trend and their verdicts differ). A disagreement always gets `point_vs_grid` or `two_models`, so the list is never empty. Exact texts: design 12 §4.
- **`drift` (threshold revised by domain review 2026-11-23):** needs both models counted; a gap against a station alone never fires it, because stations have their own breaks. For each model, subtract each other counted row's anomaly from its own (monthly anomalies against each record's own 1995–2014 calendar-month normal; rain uses yearly % anomalies), then Sen's slope and the trend test with its autocorrelation adjustment. Flag the model when every difference, the other model included, is clear (p < 0.05 and the 95% range excludes 0), in the same direction, and at least 0.1 °C (rain: 2% of the usual yearly rain) per decade. Text: "Weather models can drift over decades at some places; at this spot {label} has been {cooling | warming | getting drier | getting wetter} relative to the other records."; when both models are flagged, or with no counted station: "Weather models can drift over decades at some places; at this spot ERA5 and NASA POWER have drifted apart." (`source` null). `direction` is the word in the text ("cooling", "warming", "getting drier", "getting wetter"). It is a reason when the records disagree and its own line when they agree (Sydney rain). `null` unless the rule fires.
- **One record (`single_note`, domain review 2026-11-23):** top-level `single_note`. When `comparisons` is set, `thin_note` is null, and fewer than two rows are counted (ERA5 couldn't be read, the station is thin or missing, a row is still pending, or any mix): "Only one record could be compared here, so this answer rests on a single weather model." ("…rests on a single weather station." when the one counted row is a station; with no row counted, the main row's kind decides). `null` otherwise, and with `compare=false`. The verdict itself stays as it is. The page prints it under the verdict; Ask and MCP pass it.
- **Thin main record (`thin_note`, domain review 2026-11-23):** top-level `thin_note`. When the main row has a trend but is thin (so `counted` is false; only a station picked as main can be), it is "This record has few readings in recent years, so it isn't counted when we compare." (no layout words, so it reads the same on the page, in MCP and in voice). When `thin_note` is set, `single_note` is `null`: the table rows already show what is missing. `null` otherwise, and with `compare=false`. The page prints it under the verdict; Ask and MCP pass it.
- **Copernicus attribution (domain review):** ERA5 (also via Open-Meteo) and the CMIP6 Atlas files retrieved from the Copernicus Climate Data Store are Copernicus products. Their `source` blocks (ERA5's `source`, every ERA5 row's `source`, and the CMIP6 `projection.source`) carry `attribution`: "Contains modified Copernicus Climate Change Service information 2026." The page prints it in the footer data line and in the Sources step, and the CSV header carries it for ERA5 records and CMIP6 projection rows; Open-Meteo's own credit stays. `attribution` is `null` for every other source.
- **`source.limit`** (data lane): for NASA POWER rain, "NASA POWER's rain is corrected every day to rain-gauge maps. Where gauges are few (much of Africa, inland Australia, South America and the far north), it can drift.", plus "This far north it gets no gauge correction." above 62.5° N ("This far south …" below 62.5° S) or "At this latitude the correction is only partial." between 42.5° and 62.5°. `null` for every other source and measurement.
- **ERA5T:** ERA5 is fetched through the latest complete month; months that end less than 3 months before retrieval are flagged "preliminary" (data lane) and, as today, left out of the baseline, the trend, `now` and the yearly values. The page names them (design 12 §7).
- **Stations:** the nearest-station radius is 25 km everywhere (`ghcn` `MAX_KM`), and station results carry `place.km` and `place.id`.
- **Caching:** an answer with `main_note` set or any row "error" or "pending" is sent `no-store`; only complete answers get the normal cache.
- **`/api/trend`** gains `compare` (default `true`); `compare=false` returns the same answer with `comparisons`, `comparisons_window`, `disagree`, `drift`, `thin_note` and `single_note` `null` (the page draws the card first, then fills the rows). MCP `detect_trend` always compares.
- **Ask and MCP** never wait for comparison rows (domain review 2026-11-23). Ask (since PR6) and MCP both compare. `detect_trend` answers from the main record and projection, fetching the other two records in parallel within a budget of about 8 s. A row not back in time is status "pending", `counted` false, and left out of agree/disagree and drift. The page's `/api/trend` (compare=true) still waits for every row. Voice stays under about 10 s end to end on a warm cache; warm the demo places' caches before any demo. Ask and MCP pass each row's `label`, `where`, `years`, `verdict`, `note` and `headline_rate.text`, plus `disagree.line`, `say`, the reason texts, `drift.text`, `thin_note`, `single_note` and `source.limit`. When `disagree.any`, the answer says the records disagree, gives each verdict and the first reason, and never says which record is right.

### Facts, not advice (owner, 2026-11-22) — stats lane fills it; UI, agent and MCP show it

Tarun's decision: "Remove both, state facts". Bhoomi is not a house-buying or investment tool. Nothing anywhere (page, agent, MCP, voice, evals) gives a risk level, a recommendation, or buy, build, avoid or invest advice. This supersedes the risk levels in `docs/RISK.md`, "Keep 'advise against'" and the PR4 "span or none" risk rule.

```json
"guidance": {
  "fact": "Rising about 1.5 times as fast as the world average (1993 to April 2025; 95% range 1.0 to 2.0 times).",
  "ratio": 1.5,
  "reference": {"text": "…", "source": {"name": "…", "url": "…"}},
  "rate": {"value": 3.2, "unit": "mm", "text": "+3.2 mm", "per": "a year", "note": null},
  "display": {"unit": "mm", "factor": 1},
  "look_next": [
    {"label": "Official flood maps (FEMA Flood Map Service Center)", "url": "https://msc.fema.gov/portal/home"},
    {"label": "Your local planning office", "url": null}
  ],
  "future_link": {"label": "…", "url": "…"},
  "disclaimer": "This shows past measurements and IPCC projections, which depend on how much the world emits. It is not a prediction and not professional advice."
}
```

- **Removed:** `risk`, `risk_label`, `why`, `recommendation`, and `world.thresholds`. No other key replaces them.
- `fact`: one plain sentence saying what the records show, with its uncertainty in the same sentence. It uses only numbers already in `headline_rate`, `world`, `fit` and `record`, so the invented-numbers guard passes. It ends with the years and the 95% range in brackets.
  - The verb gives the direction, so the number after "Rising about" or "Falling about" has no sign. Range ends keep their signs.
  - Rising or falling, with a world ratio:
    - "Rising about {ratio} times as fast as {world.measure} ({window}; 95% range {ratio_low} to {ratio_high} times)."
    - Sea level reads "the world average"; air temperature reads "the average for all land areas".
    - Ratios are shown to 2 significant figures, as `world.ratio` is.
  - Falling while the world rose (a ratio below 0, e.g. Juneau): "Falling here, while {world.measure} rose {world_rate} {unit} over the same years ({window})." There is no range: no field holds the local range since 1993.
  - `world.why_none` set, or `world.available` false, and every measurement with no world figure (rainfall, water storage, hottest day of the month): "{Rising|Falling} about {headline_rate value, unsigned} {unit and per} ({fit.start year} to {fit.end year}; 95% range {headline_rate.range_text})." Examples:
    - "Rising about 0.94 mm a year (1878 to 2024; 95% range +0.7 to +1.2 mm a year)."
    - "Rising about 5.5% of the usual yearly rain every 10 years (1981 to 2025; 95% range +0.4 to +10.7%)."
    - "Falling about 0.25 °C per decade (1981 to 2025; 95% range −0.48 to −0.02 °C per decade)."
  - No clear change: "No clear change ({fit.start year} to {fit.end year}; 95% range {headline_rate.range_text})."
- `world.text` states facts only. Rainfall's and water storage's own-place rule sentences ("…is high; 5 to 10% is moderate") are removed, and "It covers total rain, not heavy downpours or floods." moves to `caveats`. The page, the agent and MCP never show a level rule.
- `look_next`: neutral pointers, in order. A label never says what to do with a property. Every non-null `url` must answer 200 when checked.
  - Sea level, a NOAA CO-OPS gauge: "Official flood maps (FEMA Flood Map Service Center)" (https://msc.fema.gov/portal/home), then "Your local planning office" (`url` null).
  - Sea level elsewhere: "Your local planning office" only. Add a national agency link only once it is on a reviewed list.
  - Air temperature, hottest day, rainfall: "Your national weather service" (`url` null).
  - Water storage: "Your local water authority" (`url` null).
- `disclaimer`, always present:
  - Without a projection: "This shows past measurements only. It is not a prediction and not professional advice."
  - With a projection: "This shows past measurements and IPCC projections, which depend on how much the world emits. It is not a prediction and not professional advice."
- `world` keeps `ratio`, `ratio_low` and `ratio_high` as facts. Step 6 shows them without any threshold.
- **Page:**
  - The "Our recommendation" box goes; the card shows `fact`, then a "Where to look next" line built from `look_next`, then `disclaimer`.
  - Risk chips go from the sidebar and the compare table. The table's last column becomes "Compared with the world", showing the ratio and its range, or "—".
- **Agent, MCP and voice:**
  - Tool outputs carry `fact`, `look_next` and `disclaimer` instead of the removed keys.
  - Prompts never state a risk level or advice.
  - The voice prompt's "Say the risk level, the recommendation and the closing disclaimer" becomes "Say the fact, where to look next, and the closing disclaimer". It is listed in the PR body; the coordinator applies it.

### Plain-language layer (PR6, owner 2026-11-23: "ok plain words") — stats lane writes it; UI, Ask, voice and MCP print it verbatim

Every answer leads with short lines a general audience can follow: (1) what is expected, (2) how sure the experts are, in everyday words, (3) what it means day to day. Exact templates, slots and worked strings: `web/design/16-plain-language.md` §1 (it wins where this section is shorter). The words are written only in `earthtrends/stats/plain.py`; nobody else builds or edits them.

| Field | Type | Rule |
|---|---|---|
| `projection.scenarios[k].plain` | list of 1–3 str | That row's lines (sea level at 2050; CMIP6 at 2041–2060), from its `p50`, `p17`/`p83` (sea) or `p10`/`p90` (CMIP6), `confidence`, `rate.p50` (sea), `disagree` (rain), `name`, and `projection.caveat`. A middle value that rounds to 0 drops line 3; a null value at that year gives one line ("By 2050, the experts give no value here on {path}." / "Around 2050, the climate models have no value here on {path}."). |
| `plain` (TrendResult) | list of 2–3 str, always present | With a projection: the default scenario's `plain`. Without (`projection.available` false, or no projection): `[projection.why or the no-projection sentence, the how-sure sentence for meaning.confidence, meaning.comparison]`, an empty comparison dropped. |
| `projection.check.text` (sea level) | str or null | "Measured levels here are already above the experts' range for recent years." ("below"); null unless `check.inside` is false. |

- **Record-free:** with a projection the lines use only projection fields: no `now`, baseline value, verdict or `check`. They read the same whichever record is main and whichever source the visitor picks.
- **Range names:** AR6 sea level, medium confidence: "about a 2 in 3 chance … on that path". CMIP6 10th–90th percentile: "8 in 10 climate models put it …", then "That shows how much the models agree, not how likely it is." Never "chance" or "odds" for CMIP6, and "likely" only inside that fixed sentence.
- **Spoken form:** "1995 to 2014", "2041 to 2060" (no dashes); no brackets or signs (the direction word carries the sign); numbers with the server's own rounding (`sig2`, range ends to the same decimals).
- **Facts, not advice:** no "you should", no buy, build, move, avoid or insure, no risk word.
- **Invented numbers:** every number in `plain` is in a `projection` field or the fixed reference "100 mm"; Ask adds `plain` to `MODEL_FIELDS`.
- **Page:** an "In plain words" box replaces card R3 when the projection is available and the selected scenario has `plain`; otherwise no box and R3 stays (`projection.why`). "About … more than today" leaves the card; it stays in the chart readout and MCP `today_level.vs_typical`.
- **Ask:** the plain lines come first, written by code and outside the word count, after a past clause (`meaning.headline`, or "Our records here disagree about the past." when the picked results' verdicts differ). A request for simple words gives the plain lines, one sentence naming the sources, then `[GUIDANCE]` without `fact`. Voice forwards every question with "Explain in simple words."
- **MCP `get_projection`:** design 16 §5, with `high_end` (never "plan for") and `model_range` for CMIP6 (`likely_range` only for AR6 sea level). `detect_trend`'s description adds: "It also carries plain: two or three short lines for the public. Start with meaning.headline, then plain, word for word."

### Sources pages (PR6, owner 2026-11-23: "ok sources") — data lane states licences; UI lane builds the pages

- Two static pages, `/sources/` (one card per dataset) and `/sources/world/` (the world figures we compare against). Design: `web/design/17-sources-pages.md`. No top-bar link; reached from the footer data line, the Sources step, the world-comparison step and Ask. No fixed world rate on the page.
- **Licences and credits in code:** every data module's `SOURCE` (NASA POWER, NOAA GHCN-Daily, NOAA CO-OPS, PSMSL, GRACE, and the ERA5, CMIP6 and AR6 sources that already carry one) states `licence` (the provider's own terms, short form, e.g. "CC BY 4.0", "Public domain (US Government work)", or the provider's wording when there is no standard licence) and `credit` (the credit line the provider asks for, verbatim where it gives one). Each comes from the provider's own terms page, cited in a code comment with its URL. The pages print them; a drift test checks the pages against the code.
- **Bhoomi's own charts and text:** CC BY 4.0, credited "Bhoomi (bhoomi.earth), built with AI assistance", plus the dataset credits. The code stays Apache-2.0.
- **Links checked:** a "Links checked on {date}" line, set at each release link check; `scripts/check_links.py` covers every outbound link on both pages.

### World reference series — data lane, stats lane reads

`earthtrends.data.world.reference(name)` returns a TimeSeries (with the full source block) from a snapshot file kept in the repo and refreshed by `scripts/update_world.py`; nothing is fetched per request.

| name | What | Units |
|---|---|---|
| `land_temp` | Global land-only monthly air temperature anomaly, from a published series with an exact URL | degC |
| `gmsl` | Satellite global mean sea level, 1993 on, monthly | mm |

### CSV download — UI lane builds it from the fields above

Text cells (place names, notes) that start with `=`, `+`, `-`, `@`, a tab or a return get a leading `'` so spreadsheets never run them; header lines start with `#` and are never quoted, so tools that skip `#` comment lines (pandas `comment='#'`, R `comment.char`) skip them, and a line starting with `#` is never read as a formula.

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
    "recommendation": "It has been getting warmer here at least about as fast as the average for all land areas. Before you plan a home, a farm or outdoor work, check how hot the summers get and how you would keep cool.",
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
- *(Superseded 2026-11-22: see "Facts, not advice" above. `risk`, `risk_label`, `why` and `recommendation` are removed; `fact` and `look_next` are added; the example above shows the old shape.)* `guidance` (added 2026-11-15, after `meaning`, always the last field): a risk level and a recommendation worded for decisions, computed in code (`earthtrends/stats/guidance.py`) from the fields above by the rules in `docs/RISK.md`. The page, the agent and outside clients show these strings as they are; nobody else works out a risk, a recommendation or a future figure.
  - `risk`: `"high"` | `"moderate"` | `"low"` | `"unknown"` | `null`; `risk_label`: `"High risk"` | `"Moderate risk"` | `"Low risk"` | `"Moderate to high risk"` | `"Low to moderate risk"` | `"Risk between low and high (wide range)"` | `"No world comparison"` | `"Not enough data"` | `"No clear change"` | `null` (Rework v2: `null` risk with "No clear change" for an unclear trend; both `null` for the hottest day).
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
| `get_projection` (PR6) | `variable`, `lat`, `lon`, `scenario?`, `year?`, `source?` | the projection answer in `web/design/16-plain-language.md` §5 (`plain` first; `high_end`; `model_range` for CMIP6, `likely_range` for AR6 sea level only); unknown variable or scenario, a year not offered, or no tide gauge within 100 km give a `ToolError` with a plain message. MCP only: the page reads `projection` from `/api/trend`. |

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
- Answers that looked something up end with the tool's own guidance for each result (*superseded 2026-11-22 by "Facts, not advice":* each result's `fact`, then "Where to look next" from `look_next`, then any official future-map link, then the disclaimer once; no risk level or recommendation). Code inserts these strings from `guidance` word for word; the model adds no advice and no future number of its own (added 2026-11-15).
- Limits per network address: 30 questions a minute and 150 an hour (raised 2026-11-15 from 10 and 100, because the page's voice and text assistant asks on visitors' behalf from a few shared addresses); 200 an hour over all callers, unchanged.
- Any other top-level field is refused (422).
- **Voice (PR6):** a request header `X-Bhoomi-Voice: 1` (or `true`, `yes`) marks a spoken answer. The body shape is unchanged.
- **Sources line (PR6):** "All our data sources, with licences: bhoomi.earth/sources" ends an answer only on the first answer of a chat (no earlier assistant turn) or when the question asks about sources, licences, citing or where the data comes from. Never in a voice answer.
