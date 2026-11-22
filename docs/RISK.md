# Risk guidance: the rules

Every trend result carries a `guidance` object, computed in code by `earthtrends/stats/guidance.py` from the rules below and tested in `tests/test_guidance.py`. The world comparison it reads is the result's own `world` object, built in `earthtrends/stats/trend.py` and tested in `tests/test_baseline.py`. The page and the Ask agent show these strings as they are. Nobody else does the arithmetic.

Rework v2 (2026-11-22, `docs/REWORK-SPEC.md` D1, D5, D6) changed three things:
- the "If the past trend continues" ranges (`outlook`, `outlook_label`) are gone;
- the world comparison is like for like;
- hottest day of the month has no risk level.

## What guidance is not

- **Not a forecast.** Guidance never gives a future value. No future number is made from a past trend. Future values will come only from published expert projections, in the result's `projection` object (added in later work).
- **Not professional advice.** It is not financial, legal, engineering or insurance advice. Every guidance object ends with this disclaimer: "This guidance isn't perfect. It is based only on past records, and the future is not certain. Not professional financial or legal advice."

## Before guidance: the record must support a trend

`compute_trend` checks the record first (D6):
- **Coverage.** The fit window must have at least 80% of its months with a value. When the whole record falls short, the window starts at the first value of the earliest calendar year from which the record to its last value reaches 80%. Sparse early readings are then left out. `record.trimmed_from` names the record's first month, and the caveats say "Readings before {Month YYYY} are too sparse, so the trend starts there." `period`, `fit`, `record` and `explain.data` describe the window. The baseline still uses the whole series.
- **Length.** The window then needs at least 20 years from its first value to its last (land water storage: 10 years).
- If no window meets both rules, there is no result at all: a 400 with a plain message.

A record of 20 to 29 years is shown with `record.status` "short" and the caveat "Short record: under 30 years of data, so this trend is less certain." Land water storage counts as "ok" from 10 years. Preliminary values (`flags`) are left out of the baseline and the fit.

## Display units

| Variable | Result units | Shown as | Factor |
|---|---|---|---|
| sea_level | mm | cm | 0.1 |
| air_temp, air_temp_max | degC | °C | 1 |
| precip | mm/day | mm a year | 365.25 |
| water_storage | cm | cm | 1 |

`rate` is the slope per 10 years in display units. It has 2 significant figures, rounded half away from zero, and is always signed ("+8.3 cm", "+0.21 °C", "−1.4 cm"). It is null when there is no clear change. `rate.note` is always present and null, except for rainfall.

For rainfall the big number is the share of this place's 1995–2014 average rainfall: the same share, with the same rounding, that the `why` sentence prints. For example, `{"value": 4.8, "unit": "%", "text": "+4.8%", "per": "more rain every 10 years", "note": {"value": 60, "unit": "mm", "text": "about 60 mm more a year"}}`. When rain is falling, it reads "−4.8%" with "less rain every 10 years", and the note is `{"value": -60, ..., "text": "about 60 mm less a year"}`. The note is the slope per 10 years in mm a year, rounded the same way as `meaning.comparison`. Its `value` is signed; its text is unsigned, and a word carries the direction. `display` stays mm a year (factor 365.25) for the chart. A clear rain change with no usable average gets risk `unknown` and `rate` null.

## World comparison (`world`), like for like (D5)

| Variable | Numerator (here) | Denominator (world) | Window | Unit | Ratio |
|---|---|---|---|---|---|
| air_temp | Sen's slope of this record's monthly anomalies | Sen's slope of the global land-only monthly series (`earthtrends.data.world.reference("land_temp")`), rebased the same way | exactly the months both records have | °C per decade | yes |
| sea_level | Sen's slope of the gauge's monthly anomalies | Sen's slope of satellite global mean sea level (`reference("gmsl")`), rebased the same way | the months from 1993 to the gauge's last month that both records have; needs at least 20 years with 9 or more such months | mm a year | yes |
| air_temp_max | none | none | none | none | no: "There is no matching world figure for the hottest day of the month." |
| precip | none | none | none | none | no: this place's own rule, printed in `world.text` |
| water_storage | none | none | none | none | no: this region's own rule, printed in `world.text` |

- Both sides use the same method: anomalies against their own 1995–2014 calendar-month normals, then Sen's slope over the same months.
- The two rates are rounded to 2 significant figures as shown.
- **ratio** = the rate here ÷ the world rate, from those shown rates, rounded to 1 decimal place (half away from zero). The level is judged on that rounded number, so the ratio shown and the level always agree. A world rate of zero or less gives no ratio.
- For sea level, the full-record rate stays in `slope_per_decade`, with its own years and no ratio.
- Without the world reference series (the data lane's module is missing or fails), `world.available` is false and `why_none` reads "The world reference series is not available."
- When `world.available` is false, every number in `world` is null and `why_none` is one plain sentence.
- `guidance.ratio` is `world.ratio`. `guidance.reference` is `{"text": world.text, "source": {"name": world.source.name, "url": world.source.record_url}}`. Both are null when `world.available` is false.

`world.text` as shown:
- air_temp: "Over the same years, the average for all land areas warmed {world} °C per decade. Here: {here} °C per decade."
- sea_level: "Over the same months, {first year} to {last year}, global average sea level measured by satellites rose {world} mm a year. Here: {here} mm a year."
- precip: "Our rule: a change of 10% or more of this place's 1995–2014 average rainfall every 10 years is high; 5 to 10% is moderate."
- water_storage: "Our rule: a fall of 1 cm of water a year or more is high; 0.5 to 1 cm is moderate."

## Risk levels

The checks run in this order:

1. **Unknown variable, unexpected units, or a slope or CI that isn't a finite number.** Risk `unknown`, `rate` null.
2. **Not enough data.** If the record covers fewer than 20 years, the risk is `unknown` ("Not enough data") and the recommendation is: "The record here is too short to guide a decision. Try a nearby place with a longer record." (`compute_trend` already refuses such records; this rule guards direct callers.)
3. **No clear change.** If the verdict is `no_clear_change`, the risk is Low and `why` is "The record here shows no clear change."
4. **Clear change in the harmless direction** (sea falling, cooling, water storage rising). The risk is Low, and `why` says what is happening (for example "The sea here has been falling.").
5. **Clear change in the harmful direction**, judged per variable:

| Variable | Harmful direction | Compared with | High | Moderate | Low |
|---|---|---|---|---|---|
| sea_level | rising | `world.ratio` | ≥ 1.5 | 0.75 to 1.5 | < 0.75 |
| air_temp | rising | `world.ratio` | ≥ 1.5 | 0.75 to 1.5 | < 0.75 |
| precip | both (wetter means flooding, drier means drought) | change per 10 years as a share of this place's 1995–2014 average rainfall | ≥ 10 % | 5 to 10 % | < 5 % |
| water_storage | falling | our fixed levels, cm of water a year | ≥ 1 | 0.5 to 1 | < 0.5 |

- Sea level or air temperature rising with no world ratio (for example a gauge with under 20 years since 1993): risk `unknown` ("Not enough data"), `why` is `world.why_none`, and the recommendation is "We can't give guidance for this record." The rate is still shown.
- One side effect of judging the ratio as shown: a ratio from 1.45 up shows as 1.5 and counts as High.
- The rainfall share (2 significant figures) and the water fall (2 significant figures) are also judged as shown.
- For rainfall, the average is the 1995–2014 baseline value: the mean of the twelve calendar-month normals, in mm/day (`baseline.value`). `compute_trend` passes it in. With no baseline, or none above 0, the risk is `unknown`.

**Hottest day of the month (air_temp_max) has no risk level.** `risk`, `risk_label`, `why` and `recommendation` are null; the verdict alone answers. `rate`, `display`, `disclaimer` and every other key are unchanged and always present. The Ask agent inserts no guidance for it.

## Why (one sentence, plain words)

- sea_level: "The sea here is rising about {ratio} times faster than the world average over the same years." Between 0.9 and 1.1 it says "about as fast as", and below 0.9 "more slowly than".
- air_temp: "It is getting warmer here about {ratio} times faster than the average for all land areas over the same years." The same 0.9 and 1.1 rule applies.
- precip: "Rain here has been increasing (decreasing) by about {share}% of its usual amount every 10 years."
- water_storage: "Water stored in this region is falling by about {x} cm a year."

## Recommendations

| Variable | High | Moderate | Low |
|---|---|---|---|
| sea_level | For a long-term home or investment near the shore here, we'd advise against it unless the site sits well above flood level. | For a long-term home or investment near the shore here, check how high the site sits above flood level before you commit. | Past records give no special reason to avoid the shore here. Check the site's flood level as you would on any coast. |
| air_temp | Plan for hotter years here. For a home, a farm or outdoor work, budget for cooling, shade and water. | It has been getting warmer here. Build cooling and shade into long-term plans. | Past records give no special reason to change plans here because of heat. |
| precip, wetter | Rain here has been increasing strongly. Before you build or plant, check drainage and the flood history of the site. | Rain here has been increasing. Check drainage and flood history before you build or plant. | No clear change: Past records show rain here holding steady enough that it gives no special reason to change plans. A clear change under 5 %: Rain here has changed, but only by a small share of its usual amount. Past records give no special reason to change plans. |
| precip, drier | Rain here has been decreasing strongly. For farming or a business that needs water, don't count on today's rainfall. | Rain here has been decreasing. Plan for less water than today if you farm or depend on rainfall. | (same as above) |
| water_storage | Water stored in this region is falling fast. For farming or a new well, we'd advise against relying on groundwater here without a secure supply. | Water stored in this region is falling. Before investing in a farm or a well, check local water levels and supply. | Past records give no special reason to worry about water supply in this region. |

## Future map link (`future_link`)

This is for sea_level only. Every other variable gets null.
- Inside the US coast boxes (lower 48, Alaska, Hawaii; same boxes as `US_BOXES` in `earthtrends/agent/resources.py`), the link is "Future flood map (NOAA)". It opens the NOAA Sea Level Rise Viewer centred on the place: `https://coast.noaa.gov/slr/#/layer/slr/0/{x}/{y}/10/satellite/none/0.8/2050/interHigh/midAccretion`. Here x and y are Web Mercator metres, rounded: x = lon × 20037508.34 / 180, and y = ln(tan((90 + lat) × π / 360)) / (π / 180) × 20037508.34 / 180.
- Elsewhere, the link is "Future sea level (NASA projection tool)", https://sealevel.nasa.gov/ipcc-ar6-sea-level-projection-tool.
