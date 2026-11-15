# Risk guidance: the rules

Every trend result carries a `guidance` object, computed in code by `earthtrends/stats/guidance.py` from the rules below and tested in `tests/test_guidance.py`. The page and the Ask agent show its strings as they are. Nobody else does the arithmetic.

## What guidance is not

- **Not a forecast.** The "If the past trend continues" ranges just carry the past rate forward. They ignore speed-ups, slow-downs and anything else the future may bring.
- **Not professional advice.** It is not financial, legal, engineering or insurance advice. Every guidance object ends with this disclaimer: "This guidance isn't perfect. It is based only on past records, and the future is not certain. Not professional financial or legal advice."

## Display units

| Variable | Result units | Shown as | Factor |
|---|---|---|---|
| sea_level | mm | cm | 0.1 |
| air_temp, air_temp_max | degC | °C | 1 |
| precip | mm/day | mm a year | 365.25 |
| water_storage | cm | cm | 1 |

`rate` is the slope per 10 years in display units: 2 significant figures, rounded half away from zero, always signed ("+8.3 cm", "+0.21 °C", "−1.4 cm"). It is null when there is no clear change. `rate.note` is always present and null, except for rainfall.

For rainfall the big number is the share of this place's usual rainfall: the same share, with the same rounding, that the `why` sentence prints. For example, `{"value": 4.8, "unit": "%", "text": "+4.8%", "per": "more rain every 10 years", "note": {"value": 60, "unit": "mm", "text": "about 60 mm more a year"}}`. When rain is falling, it reads "−4.8%" with "less rain every 10 years", and the note is `{"value": -60, ..., "text": "about 60 mm less a year"}`. The note is the slope per 10 years in mm a year, rounded the same way as `meaning.comparison`. Its `value` is signed; its text is unsigned, and a word carries the direction. `display` stays mm a year (factor 365.25) for the chart. A clear rain change with no usable average gets risk `unknown` and `rate` null.

## Risk levels

The checks run in this order:

1. **Unknown variable, unexpected units, or a slope or CI that isn't a finite number.** Risk `unknown`, `rate` null, `outlook` [].
2. **Not enough data.** If the record covers fewer than 20 years, the risk is `unknown` ("Not enough data") and the recommendation is: "The record here is too short to guide a decision. Try a nearby place with a longer record."
3. **No clear change.** If the verdict is `no_clear_change`, the risk is Low and `why` is "The record here shows no clear change."
4. **Clear change in the harmless direction** (sea falling, cooling, hottest days less hot, water storage rising). The risk is Low, and `why` says what is happening (for example "The sea here has been falling.").
5. **Clear change in the harmful direction**, judged per variable:

| Variable | Harmful direction | Compared with | High | Moderate | Low |
|---|---|---|---|---|---|
| sea_level | rising | world average (ratio) | ≥ 1.5 | 0.75 to 1.5 | < 0.75 |
| air_temp, air_temp_max | rising | world average (ratio) | ≥ 1.5 | 0.75 to 1.5 | < 0.75 |
| precip | both (wetter means flooding, drier means drought) | change per 10 years as a share of this place's own average rainfall | ≥ 10 % | 5 to 10 % | < 5 % |
| water_storage | falling | our fixed levels, cm of water a year | ≥ 1 | 0.5 to 1 | < 0.5 |

- **ratio** is the local rate ÷ the world rate, rounded to 1 decimal place (half away from zero). The level is judged on that rounded number, so the ratio shown and the level always agree. One side effect: a ratio from 1.45 up shows as 1.5 and counts as High.
- The rainfall share (2 significant figures) and the water fall (2 significant figures) are also judged as shown.
- For rainfall, the average is the mean of the raw series over the record, before the seasons are removed. `compute_trend` passes it in. If there is no average above 0, the risk is `unknown`.
- For rainfall and water storage, `ratio` is null and `reference.source` is null.

## References

| Used for | Figure | Period | Source | Checked |
|---|---|---|---|---|
| sea_level | 0.13 inches (3.4 mm) a year, world average from satellites | 1993 to present | NASA Sea Level Change Portal, FAQ "Is the rate of sea-level rise increasing?", https://sealevel.nasa.gov/faq/8/is-the-rate-of-sea-level-rise-increasing/ | 2026-11-15 |
| air_temp, air_temp_max | 0.20 °C (0.36 °F) per decade, combined land and ocean | since 1975 | NOAA Climate.gov, "Climate Change: Global Temperature", https://www.climate.gov/news-features/understanding-climate/climate-change-global-temperature | 2026-11-15 |

Note on temperature: the Climate.gov page (published 2025-05-29, archived 2025-06-25) gives 0.20 °C per decade in two places. The body text says "combined land and ocean temperature … per decade since 1975". The highlights box says "since 1982". We use the body text, because it is the one that names land and ocean together.

Reference texts as shown:
- sea_level: "World average: about 3.4 mm a year (NASA, satellites since 1993)."
- air_temp, air_temp_max: "World average for land and ocean together: about 0.20 °C every 10 years since 1975."
- precip: "Our rule: a change of 10% of this place's usual rainfall every 10 years or more is high; 5 to 10% is moderate."
- water_storage: "Our rule: a fall of 1 cm of water a year or more is high; 0.5 to 1 cm is moderate."

## Why (one sentence, plain words)

- sea_level, air_temp, air_temp_max: "{subject} about {ratio} times faster than the world average." Between 0.9 and 1.1 it says "about as fast as the world average". Below 0.9 it says "more slowly than the world average". The subjects are "The sea here is rising", "It is getting warmer here" and "The hottest days here are getting hotter".
- precip: "Rain here has been increasing (decreasing) by about {share}% of its usual amount every 10 years."
- water_storage: "Water stored in this region is falling by about {x} cm a year."

## Recommendations

| Variable | High | Moderate | Low |
|---|---|---|---|
| sea_level | For a long-term home or investment near the shore here, we'd advise against it unless the site sits well above flood level. | For a long-term home or investment near the shore here, check how high the site sits above flood level before you commit. | Past records give no special reason to avoid the shore here. Check the site's flood level as you would on any coast. |
| air_temp | Plan for hotter years here. For a home, a farm or outdoor work, budget for cooling, shade and water. | It has been getting warmer here. Build cooling and shade into long-term plans. | Past records give no special reason to change plans here because of heat. |
| air_temp_max | The hottest days here are getting hotter fast. For outdoor work, older relatives or crops, plan for stronger heat than today's. | The hottest days here have been getting hotter. Plan for somewhat stronger heat than today's. | Past records give no special reason to plan for hotter extremes here. |
| precip, wetter | Rain here has been increasing strongly. Before you build or plant, check drainage and the flood history of the site. | Rain here has been increasing. Check drainage and flood history before you build or plant. | No clear change: Past records show rain here holding steady enough that it gives no special reason to change plans. A clear change under 5 %: Rain here has changed, but only by a small share of its usual amount. Past records give no special reason to change plans. |
| precip, drier | Rain here has been decreasing strongly. For farming or a business that needs water, don't count on today's rainfall. | Rain here has been decreasing. Plan for less water than today if you farm or depend on rainfall. | (same as above) |
| water_storage | Water stored in this region is falling fast. For farming or a new well, we'd advise against relying on groundwater here without a secure supply. | Water stored in this region is falling. Before investing in a farm or a well, check local water levels and supply. | Past records give no special reason to worry about water supply in this region. |

## If the past trend continues (`outlook`)

The outlook is given only when the verdict is rising or falling and the record covers at least 20 years; otherwise it is []. A record of 20 to 29 years gets 2035 and 2050 only, and 30 years or more also gets 2075, because a look-ahead should not reach much further than the record is long. For 2035, 2050 and 2075 (years after the last data year only), each end of the range is (year − last data year) ÷ 10 × `ci_low` (or × `ci_high`), in display units, measured from today. Both ends are whole numbers when the larger end is 10 or more, and otherwise have 1 decimal. The text reads "+18 to +21 cm by 2050". When both ends round to the same number, it reads "about +5 cm by 2050". For rainfall the numbers are unsigned and a word carries the direction: "64 to 239 mm more rain a year by 2050", "183 to 365 mm less rain a year by 2050", "about 60 mm more rain a year by 2050" (`low`/`high` keep their signs). The word comes from the verdict (falling → "less", rising → "more"), never from a rounded number. A year whose two ends both round to 0 is left out; if every year is left out, `outlook` is []. The word "forecast" is never used.

Worked example: a trend of 8.3 cm per 10 years (CI 7.6 to 8.9), last data year 2026. 2050 is 2.4 decades on, giving 18.24 to 21.36, shown as "+18 to +21 cm by 2050".

## Future map link (`future_link`)

This is for sea_level only. Every other variable gets null.
- Inside the US coast boxes (lower 48, Alaska, Hawaii; same boxes as `US_BOXES` in `earthtrends/agent/resources.py`), the link is "Future flood map (NOAA)". It opens the NOAA Sea Level Rise Viewer centred on the place: `https://coast.noaa.gov/slr/#/layer/slr/0/{x}/{y}/10/satellite/none/0.8/2050/interHigh/midAccretion`. Here x and y are Web Mercator metres, rounded: x = lon × 20037508.34 / 180, and y = ln(tan((90 + lat) × π / 360)) / (π / 180) × 20037508.34 / 180.
- Elsewhere, the link is "Future sea level (NASA projection tool)", https://sealevel.nasa.gov/ipcc-ar6-sea-level-projection-tool.
