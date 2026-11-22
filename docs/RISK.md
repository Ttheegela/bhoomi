# Risk guidance: the rules

Every trend result carries a `guidance` object, computed in code by `earthtrends/stats/guidance.py` from the rules below and tested in `tests/test_guidance.py`. The world comparison it reads is the result's own `world` object, built in `earthtrends/stats/trend.py` and tested in `tests/test_baseline.py`. The page and the Ask agent show these strings as they are. Nobody else does the arithmetic.

Rework v2 (2026-11-22, `docs/REWORK-SPEC.md` D1, D5, D6) changed three things:
- the "If the past trend continues" ranges (`outlook`, `outlook_label`) are gone;
- the world comparison is like for like;
- hottest day of the month has no risk level.

The climate-scientist review of PR1 (2026-11-22) added:
- `now`, the measured level of the last 12 months, and a trend line through the mean (F1);
- a 95% range on the world ratio and on the rain share, with two-level labels when it crosses a threshold (F2);
- rainfall tested on calendar-year totals, and no % rule where rain is scarce (F4);
- advice that describes the evidence and says what to check, instead of advising against a purchase;
- caveats for station records and for NASA POWER temperatures (F5, F7);
- a widening rule for months that are alike, picked by Monte Carlo (it replaces the all-lags Hamed–Rao).

## What guidance is not

- **Not a forecast.** Guidance never gives a future value. No future number is made from a past trend. Future values will come only from published expert projections, in the result's `projection` object (added in later work).
- **Not professional advice.** It is not financial, legal, engineering or insurance advice. Every guidance object ends with this disclaimer: "This guidance isn't perfect. It is based only on past records, and the future is not certain. Not professional financial or legal advice."

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
   - **Rainfall** is tested on calendar years instead (domain review F4: monthly ranks weigh a dry month like a monsoon month). A year counts with at least 11 valid months. Its value is the day-weighted mean of its monthly anomalies: how far its total was from the usual total, as % of the 1995–2014 annual normal (a missing month is taken to be like the rest of its year). The p-value, the 95% range, the verdict and `headline_rate` come from these years; `slope_per_decade`, `ci_low` and `ci_high` are the same rates in mm/day. `n` and `explain.data.n_years` count the years, and `explain.data.n_missing_years` the years without enough months; `explain.data.n_months` still counts the monthly values. `yearly` carries exactly the values the test used, oldest first (`{"year", "value"}`, in `fit.units`, rounded to 4 decimals like `anomaly`); the chart plots them for rain, with the trend line through them. Other measurements have no `yearly` key.
3. The variance of the Mann–Kendall statistic is multiplied by a factor n/n* for values that are alike, never below 1. The rule was picked by a Monte Carlo (1,500 to 3,000 series per case). It replaced the all-lags Hamed & Rao (1998) correction, which covered only 85% of AR(1) series with φ = 0.6 and 77% of tide-gauge-like residuals.
   - The series is detrended with Sen's slope.
   - f₁ is Hamed & Rao's n/n* in its AR(1) form, ρ(k) = r^k, from the lag-1 correlation r of the detrended values: 1 + 2/(n(n−1)(n−2)) × Σ (n−k)(n−k−1)(n−k−2) r^k. It is 1 when r ≤ 0.
   - For monthly data, the values are also cut into blocks of 12 consecutive values. The variance ratio is 12 × var(block means) ÷ var(values), and f₂ is the AR(1) factor of the block means.
   - n/n* = max(f₁, variance ratio, 1) × max(f₂, 1). Yearly values (rainfall totals) use max(f₁, 1).
   - In the simulation this covered 95–99% of AR(1) and white-noise series, and 88–91% of tide-gauge-like ones.
4. The p-value and the 95% range of Sen's slope (Gilbert's rank method) both use that same corrected variance. `autocorrelation_adjusted` is true when the factor is above 1. `explain.real.widened` is true only when the factor (on the variance) is 1.2 or more, which widens the range by about 10%. So the page never says "we widened the range" about a 1% change.
5. `headline_rate` and `fit.change` are computed from the unrounded slope, range and span. Only the shown numbers are rounded.
6. **The trend line** has Sen's slope and passes through the mean of the anomalies at their mean time (not the median: domain review F1), on the same footing as the mean baseline. `fit.level_end` is that line at the last fitted month.
7. **`now`** is measured, never read off the line. It is the mean of the anomalies in the 12 calendar months to the last fitted month (preliminary values left out), when at least 10 of them have a value (`n`).
   - Rainfall: their day-weighted mean, the 12-month total's departure from the usual total as % of the 1995–2014 annual normal (`kind` "12-month total").
   - `text` is in the display unit to 2 significant figures ("+6.6 cm", "+0.49 °C", "+5.9%"); `label` is "the 12 months to October 2026".
   - `now` is null without a baseline, for annual data, or with fewer than 10 of those months.

## Caveats by kind of record

- NOAA GHCN-Daily stations: "Station records are not adjusted for changes in instruments, observing times or station moves." (domain review F5; the world land series is homogenized.)
- NASA POWER air temperature and hottest day: "NASA POWER comes from a weather model, MERRA-2, which does not use land thermometer readings; a nearby weather station can differ." (F7)

## Rates and display units

Every rate shown anywhere comes from the result's `headline_rate`, in the unit people read, with its 95% range:

| Variable | Result units | `headline_rate` | Levels (`display`) | Level factor |
|---|---|---|---|---|
| sea_level | mm | mm a year (the world's unit) | cm | 0.1 |
| air_temp, air_temp_max | degC | °C per decade | °C | 1 |
| precip | mm/day | % of the 1995–2014 average per decade | mm a year | 365.25 |
| water_storage | cm | cm of water a year | cm | 1 |

- `headline_rate` has `value`, `low` and `high` to 3 significant figures.
- Its `text` is 2 significant figures, signed with a true minus: "+4.3 mm a year".
- Its `range_text` shows both ends to the same decimals, with enough decimals that the ends differ: "+4.1 to +4.4 mm a year".
- Rainfall with no 1995–2014 average above 0 has `headline_rate` null.
- Levels (`fit`, `anomaly`) keep the series units, and the page may show them in the `display` unit.

`guidance.rate` is the rate for a clear change, to 2 significant figures, rounded half away from zero and always signed. It is null when there is no clear change, and `rate.note` is always present and null, except for rainfall.
- Sea level is in mm a year: `{"value": 4.3, "unit": "mm", "text": "+4.3 mm", "per": "a year"}`, the same number as `headline_rate.text`.
- Water storage is in cm of water a year: `{"value": -4.1, "unit": "cm", "text": "−4.1 cm", "per": "of water a year"}`, the same number as `headline_rate.text`.
- Temperature is per 10 years ("+0.21 °C", "every 10 years").
- `meaning.comparison` follows the same units: "About 4 mm higher each year." for sea level, and "About 4 cm less water each year, as a layer spread over the region." for water storage.

For rainfall the big number is the share of this place's 1995–2014 average rainfall: the same share, with the same rounding, that the `why` sentence prints. For example, `{"value": 4.8, "unit": "%", "text": "+4.8%", "per": "more rain every 10 years", "note": {"value": 60, "unit": "mm", "text": "about 60 mm more a year"}}`. When rain is falling, it reads "−4.8%" with "less rain every 10 years", and the note is `{"value": -60, ..., "text": "about 60 mm less a year"}`. The note is the slope per 10 years in mm a year, rounded the same way as `meaning.comparison`. Its `value` is signed; its text is unsigned, and a word carries the direction. `display` stays mm a year (factor 365.25) for the chart. A clear rain change with no usable average gets risk `unknown` and `rate` null.

## World comparison (`world`), like for like (D5)

| Variable | Numerator (here) | Denominator (world) | Window | Unit | Ratio |
|---|---|---|---|---|---|
| air_temp | Sen's slope of this record's monthly anomalies | Sen's slope of the global land-only monthly series (`earthtrends.data.world.reference("land_temp")`), rebased the same way | exactly the months both records have | °C per decade | yes |
| sea_level | Sen's slope of the gauge's monthly anomalies | Sen's slope of satellite global mean sea level (`reference("gmsl")`), rebased the same way | the months from 1993 to the gauge's last month that both records have; needs at least 20 years with 9 or more such months | mm a year | yes |
| air_temp_max | none | none | none | none | no: "There is no matching world figure for the hottest day of the month." |
| precip | none | none | none | none | no: this place's own rule, printed in `world.text` |
| water_storage | none | none | none | none | no: this region's own rule, printed in `world.text` |

- Both sides use the same method: anomalies against their own 1995–2014 calendar-month normals, then Sen's slope over the same months. `world.window` is the first and last of those shared months, per place.
- `world.method` names the method, "Sen's slope of monthly anomalies, same months for both", then, after "; ", the kinds of record when they differ:
  - air temperature from a grid (POWER, ERA5): "different datasets: a grid cell here, station-based for the world";
  - air temperature from GHCN: "different datasets: one weather station here, station-based for the world";
  - sea level: "different instruments: a tide gauge here (measured against the land), satellites for the world".

  The world land series (NOAAGlobalTemp, global land) is built from station records. Other sources get the method alone.
- The two rates are rounded to 2 significant figures as shown.
- **ratio** = the rate here ÷ the world rate, from those shown rates, rounded to 1 decimal place (half away from zero). The level is judged on that rounded number, so the ratio shown and the level always agree. A world rate of zero or less gives no ratio: for a rising or falling verdict, `world.available` stays true (the two rates and `text` are shown) and `why_none` is "The world figure did not rise over these years, so there is no ratio."
- **ratio_low** and **ratio_high** = the ends of the local rate's 95% range over the same months (the same Mann–Kendall and Sen computation as the trend, 2 significant figures) ÷ the world rate, rounded the same way.
- `ratio`, `ratio_low` and `ratio_high` are null unless the verdict is rising or falling: an unclear trend shows the two rates and no ratio.
- For sea level, the full-record rate stays in `slope_per_decade`, with its own years and no ratio.
- Without the world reference series (the data lane's module is missing or fails), `world.available` is false and `why_none` reads "The world reference series is not available."
- When `world.available` is false, every number in `world` is null and `why_none` is one plain sentence.
- `guidance.ratio` is `world.ratio`. `guidance.reference` is `{"text": world.text, "source": {"name": world.source.name, "url": world.source.record_url}}`. Both are null when `world.available` is false.

`world.text` as shown:
- air_temp: "Over the same years, the average for all land areas warmed {world} °C per decade. Here: {here} °C per decade."
- sea_level: "Over the same months, {first year} to {last year}, global average sea level measured by satellites rose {world} mm a year. Here: {here} mm a year."
- precip: "Our rule: a change of 10% or more of this place's 1995–2014 average rainfall every 10 years is high; 5 to 10% is moderate. It covers total rain, not heavy downpours or floods." Where the 1995–2014 annual normal is under 100 mm, `text` is null and `why_none` is "Rain here is too scarce for a percentage rule."
- water_storage: "Our rule: a fall of 1 cm of water a year or more is high; 0.5 to 1 cm is moderate."

## Risk levels

The checks run in this order:

1. **Unknown variable, unexpected units, or a slope or CI that isn't a finite number.** Risk `unknown`, `rate` null.
2. **Not enough data.** If the record covers fewer than 20 years (land water storage: fewer than 10, its trend minimum), the risk is `unknown` ("Not enough data") and the recommendation is: "The record here is too short to guide a decision. Try a nearby place with a longer record." (`compute_trend` already refuses such records; this rule guards direct callers.)
3. **No clear change.** If the verdict is `no_clear_change`, there is no risk level: a record that cannot show a change is not evidence of low risk. `risk` is null and `risk_label` is "No clear change". `why` is "The record here shows no clear change." The Low recommendation in the table below and the disclaimer stay.
4. **Clear change in the harmless direction** (sea falling, cooling, water storage rising). The risk is Low, and `why` says what is happening (for example "The sea here has been falling.").
5. **Clear change in the harmful direction**, judged per variable:

| Variable | Harmful direction | Compared with | High | Moderate | Low |
|---|---|---|---|---|---|
| sea_level | rising | `world.ratio` | ≥ 1.5 | 0.75 to 1.5 | < 0.75 |
| air_temp | rising | `world.ratio` | ≥ 1.5 | 0.75 to 1.5 | < 0.75 |
| precip | both (wetter means flooding, drier means drought) | change per 10 years as a share of this place's 1995–2014 average rainfall | ≥ 10 % | 5 to 10 % | < 5 % |
| water_storage | falling | our fixed levels, cm of water a year | ≥ 1 | 0.5 to 1 | < 0.5 |

- **A 95% range across a threshold.** Sea level and air temperature are judged on `ratio`, `ratio_low` and `ratio_high`; rainfall on its share and on the shares of both ends of its 95% range. When they fall on different levels:
  - `risk_label` names the lowest and the highest: "Moderate to high risk", "Low to moderate risk", or "Low to high risk" when the range crosses both thresholds;
  - `risk` is the lowest, and the recommendation is the lowest level's;
  - `why` keeps the central number.
- Sea level or air temperature rising with no world ratio (QA B3: Mumbai, 147 years but under 20 since 1993): no risk level. `risk` is null, `risk_label` is "No world comparison", `why` is `world.why_none`, and the recommendation needs no level (table below, "No world comparison"). The rate is still shown. "Not enough data" is kept for records too short to judge. A clear fall of the sea or a cooling stays Low (rule 4): that needs no world figure.
- One side effect of judging the ratio as shown: a ratio from 1.45 up shows as 1.5 and counts as High.
- The rainfall share (2 significant figures) and the water fall (2 significant figures) are also judged as shown.
- **Too little rain for a % rule.** Where the 1995–2014 annual normal is under 100 mm, a clear rain change has no risk level: `risk`, `risk_label` and `recommendation` are null, and `why` is "Rain here is too scarce for a percentage rule." The rate is still shown. `trend.py` decides this once and marks it in `world.why_none`; guidance reads that mark. An unclear trend still gets "No clear change" (rule 3), and a normal of zero has no % at all, so it is "Not enough data" (next point).
- For rainfall, the average is the 1995–2014 baseline value: the mean of the twelve calendar-month normals, in mm/day (`baseline.value`; `baseline.annual_total_mm` is the same in mm a year). `compute_trend` passes it in. With no baseline, or none above 0, the risk is `unknown`. Rainfall levels (`fit`, `anomaly`) are % of that average, and `explain.seasons` gives each month's usual rain in mm a month.

**Hottest day of the month (air_temp_max) has no risk level.** `risk`, `risk_label`, `why` and `recommendation` are null; the verdict alone answers. `rate`, `display`, `disclaimer` and every other key are unchanged and always present. The Ask agent inserts no guidance for it.

## Why (one sentence, plain words)

- sea_level: "The sea here is rising about {ratio} times as fast as the world average over the same years." Between 0.9 and 1.1 it says "about as fast as", and below 0.9 "more slowly than".
- air_temp: "It is getting warmer here about {ratio} times as fast as the average for all land areas over the same years." The same 0.9 and 1.1 rule applies.
- When `world.window` starts in a later year than the record (climate review L6: The Battery's record starts in 1920, the satellite comparison in 1993), the sentence names that year, taken from `world.window`: "Since 1993, the sea here has risen about 1.5 times as fast as the world average." Air temperature: "Since 1850, it has warmed here about 1.2 times as fast as the average for all land areas." So the full-record rate on the card is never read against a ratio from other years.
- precip: "Rain here has been increasing (decreasing) by about {share}% of its usual amount every 10 years."
- water_storage: "Water stored in this region is falling by about {x} cm a year."

## Recommendations

| Variable | High | Moderate | Low |
|---|---|---|---|
| sea_level | The sea here has been rising faster than the world average. Before you buy or build near the shore, check the site's height above flood level and the official flood maps. | The sea here has been rising at least about as fast as the world average. Before you buy or build near the shore, check the site's flood level as you would on any coast. | Past sea-level records here give no special reason to avoid the shore, but they say nothing about storm floods. Check the site's flood level as you would on any coast. |
| air_temp | Plan for hotter years here. For a home, a farm or outdoor work, budget for cooling, shade and water. | It has been getting warmer here. Build cooling and shade into long-term plans. | Past records give no special reason to change plans here because of heat. |
| precip, wetter | Rain here has been increasing strongly. Before you build or plant, check drainage and the flood history of the site. | Rain here has been increasing. Check drainage and flood history before you build or plant. | No clear change: Past records show rain here holding steady enough that it gives no special reason to change plans. A clear change whose lower level is Low (all under 5 %, or reaching higher, like Chennai's "Low to high risk"): Rain here has been increasing, though perhaps only by a small share of its usual amount. Before you build or plant, check drainage and the flood history of the site, as you would anywhere. |
| precip, drier | Rain here has been decreasing strongly. For farming or a business that needs water, don't count on today's rainfall. | Rain here has been decreasing. Plan for less water than today if you farm or depend on rainfall. | No clear change: as above. A clear change whose lower level is Low: Rain here has been decreasing, though perhaps only by a small share of its usual amount. If you farm or depend on rainfall, check how secure your water supply is, as you would anywhere. |
| water_storage | Water stored in this region is falling fast. Before you rely on groundwater for a farm or a new well, check local water levels and make sure of a secure supply. | Water stored in this region is falling. Before investing in a farm or a well, check local water levels and supply. | Past records give no special reason to worry about water supply in this region. |

No world comparison (rising, no world ratio; no level):
- sea_level: "The sea here has been rising. Before you buy or build near the shore, check the site's height above flood level and the official flood maps."
- air_temp: "It has been getting warmer here. Before you plan a home, a farm or outdoor work, check how hot the summers get and how you would keep cool."

The advice describes what the records show and what to check. A ratio of past rates says nothing about a site's height, storm surge or flood defences, so no level advises against a purchase. The sea-level moderate text says "at least about as fast" because a range from moderate to high gets the moderate text.

## Future map link (`future_link`)

This is for sea_level only. Every other variable gets null.
- Inside the US coast boxes (lower 48, Alaska, Hawaii; same boxes as `US_BOXES` in `earthtrends/agent/resources.py`), the link is "Future flood map (NOAA, intermediate-high scenario)", naming the scenario the viewer opens on. It opens the NOAA Sea Level Rise Viewer centred on the place: `https://coast.noaa.gov/slr/#/layer/slr/0/{x}/{y}/10/satellite/none/0.8/2050/interHigh/midAccretion`. Here x and y are Web Mercator metres, rounded: x = lon × 20037508.34 / 180, and y = ln(tan((90 + lat) × π / 360)) / (π / 180) × 20037508.34 / 180.
- Elsewhere, `future_link` is null. The NASA AR6 projection tool page we linked before answered 404 on 2026-11-22. Every URL `future_link` carries must answer 200 when checked; the NOAA viewer did on 2026-11-22.
