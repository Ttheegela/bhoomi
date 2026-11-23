# Guidance: facts, not advice

Every trend result carries a `guidance` object, computed in code by `earthtrends/stats/guidance.py` from the rules below and tested in `tests/test_guidance.py`. The world comparison it reads is the result's own `world` object, built in `earthtrends/stats/trend.py` and tested in `tests/test_baseline.py`. The page, the Ask agent and the MCP tools show these strings as they are. Nobody else does the arithmetic.

The owner's decision (2026-11-22, `docs/CONTRACTS.md` "Facts, not advice"): "Remove both, state facts". Bhoomi is not a house-buying or investment tool. Nothing gives a risk level, a recommendation, or advice to buy, build, avoid or invest. The risk levels, the `why` sentences and the recommendation tables that used to be here are gone, and so is `world.thresholds`.

Rework v2 (2026-11-22, `docs/REWORK-SPEC.md` D1, D5, D6) also holds:
- there is no "If the past trend continues" range (`outlook`, `outlook_label` are gone);
- the world comparison is like for like.

The climate-scientist review of PR1 (2026-11-22) added:
- `now`, the measured level of the last 12 months, and a trend line through the mean (F1);
- a 95% range on the world ratio (F2);
- rainfall tested on calendar-year totals (F4);
- caveats for station records and for NASA POWER temperatures (F5, F7);
- a widening rule for months that are alike, picked by Monte Carlo (it replaces the all-lags Hamed–Rao).

## What guidance is not

- **Not a forecast.** Guidance never gives a future value. No future number is made from a past trend. Future values come only from published expert projections, in the result's `projection` object (sea level since PR2).
- **Not advice.** It is not financial, legal, engineering or insurance advice, and it never says what to do with a property. Every guidance object ends with a disclaimer (below).

## The guidance object

```json
{"fact": "…", "ratio": 1.5, "reference": {"text": "…", "source": {"name": "…", "url": "…"}},
 "rate": {"value": 3.2, "unit": "mm", "text": "+3.2 mm", "per": "a year", "note": null},
 "display": {"unit": "mm", "factor": 1},
 "look_next": [{"label": "…", "url": "…"}], "future_link": {"label": "…", "url": "…"}, "disclaimer": "…"}
```

All keys are always present, in this order.

### `fact`: what the records show

One plain sentence with its uncertainty in it. It uses only numbers already in `headline_rate`, `world`, `fit` and `record`, printed as their own text fields print them, so the agent's invented-numbers check passes. It ends with the years and the 95% range in brackets. The verb gives the direction, so the number after "Rising about" or "Falling about" has no sign; range ends keep theirs. The checks run in this order:

1. **Not enough data.** An unknown measurement, units that are not the catalog's, a slope or range that is not a finite number, an unknown verdict, a record shorter than 20 years (land water storage: 10, its trend minimum; `compute_trend` already refuses such records, this guards direct callers), or a clear rain change with no 1995–2014 average above zero: "Not enough data (2010 to 2025)." The years are left out when the record's years can't be read.
2. **No clear change.** "No clear change ({fit start year} to {fit end year}; 95% range {headline_rate.range_text})." Every measurement, the hottest day included: "No clear change (1981 to 2025; 95% range −0.12 to +0.09 °C per decade)." Rainfall keeps its whole `range_text` ("… % of the 1995–2014 average per decade"), since no rate words before it say what the % is of. A record that cannot show a change is not evidence of anything else.
3. **Rising or falling, with a world ratio** (sea level and air temperature, `world.available` true and `world.ratio` set):
   - rising, ratio above 0: "Rising about {ratio} times as fast as {the world average | the average for all land areas} ({window}; 95% range {ratio_low} to {ratio_high} times)." The Battery: "Rising about 1.5 times as fast as the world average (1993 to April 2025; 95% range 1.0 to 2.0 times)."
   - falling, ratio below 0 (the world rose, the sea here fell: Juneau): "Falling here, while the world average rose {world_rate} {unit} over the same years ({window})." There is no range: no field holds the local range over the world's months.
   - The ratio and its ends are `world.ratio`, `world.ratio_low` and `world.ratio_high` as given (1 decimal place, which is 2 significant figures from 1.0 to 9.9). `world_rate` is printed as `world.text` prints it (2 significant figures).
   - `{window}` is `world.window`: a start in January or an end in December is the year alone, any other month is named ("1993 to April 2025").
   - The ratio is over the world's months, the verdict over the whole record, so their signs can differ (or the ratio can round to 0). Then the fact is the record's own rate (next rule), so it never contradicts the verdict.
4. **Rising or falling without a world ratio** (`world.why_none` set, `world.available` false, the hottest day, rainfall, water storage): "{Rising | Falling} about {headline_rate.text without its sign} ({fit start year} to {fit end year}; 95% range {headline_rate.range_text})."
   - Mumbai: "Rising about 0.94 mm a year (1878 to 2024; 95% range +0.7 to +1.2 mm a year)."
   - Hottest day of the month, the same template with no world clause: "Falling about 0.25 °C per decade (1981 to 2025; 95% range −0.48 to −0.02 °C per decade)."
   - Rainfall reads its share of the usual rain, and its range drops the per that the rate's words already say: "Rising about 5.5% of the usual yearly rain every 10 years (1981 to 2025; 95% range +0.4 to +10.7%)."
   - Rainfall under 100 mm a year (`world.why_none` "Rain here averages under 100 mm a year, so a small change in millimetres is a large percentage.") is the same sentence: the rate as the headline shows it.
   - A direct caller with no `headline_rate` gets the verdict word and the years only ("Rising (1990 to 2025).").

### `look_next`: where to look next

Neutral pointers, in order. A label never says what to do with a property. Every non-null `url` must answer 200 when checked.

| Measurement | `look_next` |
|---|---|
| sea_level, at a NOAA CO-OPS gauge | "Official flood maps (FEMA Flood Map Service Center)" (https://msc.fema.gov/portal/home), then "Your local planning office" (`url` null) |
| sea_level, anywhere else | "Your local planning office" only. A national agency link is added only once it is on a reviewed list. |
| air_temp, air_temp_max, precip | "Your national weather service" (`url` null) |
| water_storage | "Your local water authority" (`url` null) |
| anything else | `[]` |

"US" is decided from the result itself: a CO-OPS gauge (`source.id` "coops") is a US gauge. The result's `place` carries no country (name, lat and lon only), and the rough US boxes used for `future_link` also take in Vancouver, Toronto and Montreal, so they don't decide it. A PSMSL gauge in the US gets "Your local planning office" only.

### `disclaimer`

- Without a projection: "This shows past measurements only. It is not a prediction and not professional advice."
- With a projection (`projection.available` true): "This shows past measurements and IPCC projections, which depend on how much the world emits. It is not a prediction and not professional advice."

### The keys that stay

- `ratio` is `world.ratio`. `reference` is `{"text": world.text, "source": {"name": world.source.name, "url": world.source.record_url}}`. Both are null when `world.available` is false.
- `rate`, `display` and `future_link`: below.

## Before guidance: the record must support a trend

`compute_trend` checks the record first (D6):
- **Coverage.** The fit window must have at least 80% of its months with a value. When the whole record falls short, the window starts at the first value of the earliest calendar year from which the record to its last value reaches 80%. The scan goes by whole calendar years, never from a month inside a year. Sparse early readings are then left out. `record.trimmed_from` names the record's first month, and the caveats say "Readings before {Month YYYY} are too sparse, so the trend starts there." `period`, `fit`, `record` and `explain.data` describe the window. The baseline still uses the whole series, and it never depends on the request's `start` or `end` either: a windowed request reads the whole record for it.
- **Length.** The window then needs at least 20 years from its first value to its last (land water storage: 10 years).
- If no window meets both rules, there is no result at all: a 400 with a plain message.
  - A long record whose recent stretch is too thin says so: "Too few recent readings for a trend: the record runs from {first} to {last}, but only {start} on ({years} years) has a value in at least 80% of its months. A trend needs at least 20 such years."
  - A record that is short overall says "The record here is too short for a trend: …".
- **Tide gauges (PSMSL and NOAA CO-OPS).** A gauge that fails this check is passed over for the next nearest within 100 km. The series and the trend take the same gauge, read once. Its caveats name the gauge passed over, for example "Sheerness, the nearest gauge, has too few recent readings for a trend." (a farther one: "…, 61 km away, has …").
- **Rainfall** is tested on calendar years (below), so it also needs at least 20 calendar years with 11 or more valid months; otherwise a 400: "Too few whole years of rain for a trend: …".

A record of 20 to 29 years is shown with `record.status` "short" and the caveat "Short record: under 30 years of data, so this trend is less certain." Land water storage counts as "ok" from 10 years. Preliminary values (`flags`) are left out of the baseline and the fit.

## How the trend and its range are computed

1. Each monthly value minus its calendar month's 1995–2014 normal.
   - When the baseline is observed but fewer than all 20 years count, each month's normal is moved along the trend to the middle of 1995–2014: plus slope × (2004.5 − the mean year of that month's counted values). The slope is the least-squares line (with annual and semiannual harmonics) through the counted 1995–2014 values. Without this, missing years at one end would make the "1995–2014 average" the average of the years present.
   - A fitted baseline (coverage short) also needs at least 5 of the 20 years to count, and valid data both before 1995 and after 2014; otherwise there is no baseline (`method` "none").
2. The Mann–Kendall test and Sen's slope (the median of all pairwise slopes) on those anomalies.
   - **Rainfall** is tested on calendar years instead (domain review F4: monthly ranks weigh a dry month like a monsoon month). A year counts with at least 11 valid months. Its value is the day-weighted mean of its monthly anomalies: how far its total was from the usual total, as % of the 1995–2014 annual normal (a missing month is taken to be like the rest of its year). That normal (`baseline.value`, the denominator of every rain %) weights each month's normal by its days, February 28.25 (a 365.25-day year), so `annual_total_mm` is the sum of the twelve monthly normal totals. The p-value, the 95% range, the verdict and `headline_rate` come from these years; `slope_per_decade`, `ci_low` and `ci_high` are the same rates in mm/day. `n` and `explain.data.n_years` count the years, and `explain.data.n_missing_years` the years without enough months; `explain.data.n_months` still counts the monthly values. `yearly` carries exactly the values the test used, oldest first (`{"year", "value"}`, in `fit.units`, rounded to 4 decimals like `anomaly`); the chart plots them for rain, with the trend line through them. Other measurements have no `yearly` key.
3. The variance of the Mann–Kendall statistic is multiplied by a factor n/n* for values that are alike, never below 1. The rule was picked by a Monte Carlo (1,500 to 3,000 series per case). It replaced the all-lags Hamed & Rao (1998) correction, which covered only 85% of AR(1) series with φ = 0.6 and 77% of tide-gauge-like residuals.
   - The series is detrended with Sen's slope.
   - f₁ is Hamed & Rao's n/n* in its AR(1) form, ρ(k) = r^k, from the lag-1 correlation r of the detrended values: 1 + 2/(n(n−1)(n−2)) × Σ (n−k)(n−k−1)(n−k−2) r^k. It is 1 when r ≤ 0.
   - For monthly data, the values are also cut into blocks of 12 consecutive values. The variance ratio is 12 × var(block means) ÷ var(values), and f₂ is the AR(1) factor of the block means.
   - n/n* = max(f₁, variance ratio, 1) × max(f₂, 1). Yearly values (rainfall totals) use max(f₁, 1).
   - In the simulation this covered 95–99% of AR(1) and white-noise series, and 88–91% of tide-gauge-like ones.
4. The p-value and the 95% range of Sen's slope (Gilbert's rank method) both use that same corrected variance. `autocorrelation_adjusted` is true when the factor is above 1. `explain.real.widened` is true only when the factor (on the variance) is 1.2 or more, which widens the range by about 10%. So the page never says "we widened the range" about a 1% change.
5. `headline_rate` is computed from `slope_per_decade`, `ci_low` and `ci_high` as shown (4 decimals), so its text, its range, `guidance.rate` and the fact all round the same numbers: a slope of −10.5 cm per decade reads "−1.1 cm of water a year", never "−1.0" from an unrounded −10.499996. `fit.change` is the unrounded slope times the unrounded span, rounded once.
6. **The trend line** has Sen's slope and passes through the mean of the anomalies at their mean time (not the median: domain review F1), on the same footing as the mean baseline. `fit.level_end` is that line at the last fitted month.
7. **`now`** is measured, never read off the line. It is the mean of the anomalies in the 12 calendar months to the last fitted month (preliminary values left out), when at least 10 of them have a value (`n`).
   - Rainfall: their day-weighted mean, the 12-month total's departure from the usual total as % of the 1995–2014 annual normal (`kind` "12-month total").
   - `text` is in the display unit to 2 significant figures ("+6.6 cm", "+0.49 °C", "+5.9%"); `label` is "the 12 months to October 2026".
   - `now` is null without a baseline, for annual data, or with fewer than 10 of those months.

## Caveats by kind of record

- NOAA GHCN-Daily stations: "Station records are not adjusted for changes in instruments, observing times or station moves." (domain review F5; the world land series is homogenized.)
- NASA POWER air temperature and hottest day: "NASA POWER comes from a weather model, MERRA-2, which does not use land thermometer readings; a nearby weather station can differ." (F7)
- Every rainfall record: "It covers total rain, not heavy downpours or floods." (moved here from `world.text`, design review 2026-11-22)

## Rates and display units

Every rate shown anywhere comes from the result's `headline_rate`, in the unit people read, with its 95% range:

| Variable | Result units | `headline_rate` | Levels (`display`) | Level factor |
|---|---|---|---|---|
| sea_level | mm | mm a year (the world's unit) | cm | 0.1 |
| air_temp, air_temp_max | degC | °C per decade | °C | 1 |
| precip | mm/day | % of the 1995–2014 average per decade | mm a year | 365.25 |
| water_storage | cm | cm of water a year | cm | 1 |

- `headline_rate` has `value`, `low` and `high` to 3 significant figures.
- Its `text` is 2 significant figures, signed with a true minus: "+4.3 mm a year". For rainfall it is the share worked out from the 4-decimal `slope_per_decade`, so it always matches `guidance.rate.text`: 0.049496 mm/day per decade on a 1.0 mm/day average reads "+5.0%", not "+4.9%".
- Its `range_text` shows both ends to the same decimals, with enough decimals that the ends differ: "+4.1 to +4.4 mm a year". A rainfall end that would read on or across 5% or 10% shows the share as `guidance.rate` works it out, to 2 significant figures ("+4.5 to +17%", not "+5 to +17%"); a leftover of the old rain levels, harmless now.
- Rainfall with no 1995–2014 average above 0 has `headline_rate` null.
- Levels (`fit`, `anomaly`) keep the series units, and the page may show them in the `display` unit.

`guidance.rate` is the rate for a clear change, to 2 significant figures, rounded half away from zero and always signed. It is null when there is no clear change or not enough data, and `rate.note` is always present and null, except for rainfall.
- Sea level is in mm a year: `{"value": 4.3, "unit": "mm", "text": "+4.3 mm", "per": "a year"}`, the same number as `headline_rate.text`.
- Water storage is in cm of water a year: `{"value": -4.1, "unit": "cm", "text": "−4.1 cm", "per": "of water a year"}`, the same number as `headline_rate.text`.
- Temperature is per 10 years ("+0.21 °C", "every 10 years").
- `meaning.comparison` follows the same units: "About 4 mm higher each year." for sea level, and "About 4 cm less water each year, as a layer spread over the region." for water storage.

For rainfall the big number is the share of this place's 1995–2014 average rainfall, for example `{"value": 4.8, "unit": "%", "text": "+4.8%", "per": "more rain every 10 years", "note": {"value": 60, "unit": "mm", "text": "about 60 mm more a year"}}`. When rain is falling, it reads "−4.8%" with "less rain every 10 years", and the note is `{"value": -60, ..., "text": "about 60 mm less a year"}`. The note is the slope per 10 years in mm a year, rounded the same way as `meaning.comparison`. Its `value` is signed; its text is unsigned, and a word carries the direction. `display` stays mm a year (factor 365.25) for the chart. The average is the 1995–2014 baseline value in mm/day (`baseline.value`; `baseline.annual_total_mm` is the same in mm a year); `compute_trend` passes it in.

## World comparison (`world`), like for like (D5)

| Variable | Numerator (here) | Denominator (world) | Window | Unit | Ratio |
|---|---|---|---|---|---|
| air_temp | Sen's slope of this record's monthly anomalies | Sen's slope of the global land-only monthly series (`earthtrends.data.world.reference("land_temp")`), rebased the same way | exactly the months both records have | °C per decade | yes |
| sea_level | Sen's slope of the gauge's monthly anomalies | Sen's slope of satellite global mean sea level (`reference("gmsl")`), rebased the same way | the months from 1993 to the gauge's last month that both records have; needs at least 20 years with 9 or more such months | mm a year | yes |
| air_temp_max | none | none | none | none | no: "There is no matching world figure for the hottest day of the month." |
| precip | none | none | none | none | no: "Rainfall is compared with this place's own usual rainfall, not with a world figure." |
| water_storage | none | none | none | none | no: "Water storage is judged on this region's own change, not against a world figure." |

- Both sides use the same method: anomalies against their own 1995–2014 calendar-month normals, then Sen's slope over the same months. `world.window` is the first and last of those shared months, per place.
- `world.method` names the method, "Sen's slope of monthly anomalies, same months for both", then, after "; ", the kinds of record when they differ:
  - air temperature from a grid (POWER, ERA5): "different datasets: a grid cell here, station-based for the world";
  - air temperature from GHCN: "different datasets: one weather station here, station-based for the world";
  - sea level: "different instruments: a tide gauge here (measured against the land), satellites for the world".

  The world land series (NOAAGlobalTemp, global land) is built from station records. Other sources get the method alone.
- The two rates are rounded to 2 significant figures as shown.
- **ratio** = the rate here ÷ the world rate, from those shown rates, rounded to 1 decimal place (half away from zero). A world rate of zero or less gives no ratio: for a rising or falling verdict, `world.available` stays true (the two rates and `text` are shown) and `why_none` is "The world figure did not rise over these years, so there is no ratio."
- **ratio_low** and **ratio_high** = the ends of the local rate's 95% range over the same months (the same Mann–Kendall and Sen computation as the trend, 2 significant figures) ÷ the world rate, rounded the same way. They are shown as facts, with no threshold.
- `ratio`, `ratio_low` and `ratio_high` are null unless the verdict is rising or falling: an unclear trend shows the two rates and no ratio.
- For sea level, the full-record rate stays in `slope_per_decade`, with its own years and no ratio.
- Without the world reference series (the data lane's module is missing or fails), `world.available` is false and `why_none` reads "The world reference series is not available."
- When `world.available` is false, every number in `world` is null and `why_none` is one plain sentence.
- `world.source` is the reference's `name`, `dataset_id`, `record_url`, `retrieved` and `method`. For sea level the method keeps the data lane's note that the world figure (NASA GSFC GMSL v5.2, ending April 2025) is corrected for glacial isostatic adjustment, which adds about 0.24 mm a year.

`world.text` states facts only (design review, 2026-11-22: no level rule anywhere):
- air_temp: "Over the same years, the average for all land areas warmed {world} °C per decade. Here: {here} °C per decade."
- sea_level: "Over the same months, {first year} to {last year}, global average sea level measured by satellites rose {world} mm a year. Here: {here} mm a year."
- precip, water_storage, air_temp_max: null; `why_none` says why there is no world figure. Where the 1995–2014 annual normal is under 100 mm, rain's `why_none` is "Rain here averages under 100 mm a year, so a small change in millimetres is a large percentage." The old own-place rule sentences ("… is high; 5 to 10% is moderate") are gone, and rain's "It covers total rain, not heavy downpours or floods." is a caveat.

## Future map link (`future_link`)

This is for sea_level only. Every other variable gets null.
- Inside the US coast boxes (lower 48, Alaska, Hawaii; same boxes as `US_BOXES` in `earthtrends/agent/resources.py`), the link is "Future flood map (NOAA, intermediate-high scenario)", naming the scenario the viewer opens on. It opens the NOAA Sea Level Rise Viewer centred on the place: `https://coast.noaa.gov/slr/#/layer/slr/0/{x}/{y}/10/satellite/none/0.8/2050/interHigh/midAccretion`. Here x and y are Web Mercator metres, rounded: x = lon × 20037508.34 / 180, and y = ln(tan((90 + lat) × π / 360)) / (π / 180) × 20037508.34 / 180.
- Elsewhere, `future_link` is null. The NASA AR6 projection tool page we linked before answered 404 on 2026-11-22. Every URL `future_link` carries must answer 200 when checked; the NOAA viewer did on 2026-11-22.

## The Ask agent

The agent's answer ends with each result's guidance, put in by code word for word (`earthtrends/agent/guidance.py`): per place and measurement, the default source's `fact` (plus any other source there whose verdict differs, named), then "Where to look next: …" from `look_next` (each label once, with its url in brackets when it has one), then the future links, then the disclaimer once. The model adds no risk level, recommendation or advice of its own.
