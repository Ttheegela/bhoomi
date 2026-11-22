# 10 Foundation (rework PR1): one baseline, the answer card, the place chart, "How we calculated this" in the page

Build brief: `docs/REWORK-SPEC.md` (D1, D2, D5, D7, D8; PR1 items 3 and 5). Data: `docs/CONTRACTS.md` "Rework v2". This file wins over `09-rework.md` and `08-layout.md` where they differ. Expert projections (PR2/PR3) and the compare redesign (PR4) are out of scope; their slots are marked.

The owner saw a picture first: a static mock rendered at 1440 px, light theme (Princeton, NJ air temperature; New York / The Battery sea level; the card in every state; every step open). It lives outside the repo with the owner's notes; its numbers are illustrative. If the mock and this file differ, this file wins.

## 0. What PR1 removes
1. The "How we calculated this" `<dialog>` (modal, close button, backdrop, its CSS). Its parts move into the page (section 6) or go.
2. The card's "If the past trend continues" fact and the whole `facts2` row ("How sure we are" moves into the verdict line).
3. The compare chart's future: wedge, dashed lines, centre line, "today" rule, and the "If the past trend continues" legend key. Its 2000–2009 baseline and first-10-years fallback go too.
4. The compare table's "By {year} if the trend continues" column.
5. The sidebar's "Look ahead to" control (2035 / 2050 / 2075). Nothing reads it any more.
6. The dialog's upper "raw values" panel (raw values stay in the readout, the table, the CSV and the step 2 figure), the "The numbers" fact list, "How to read this", "How to read the chart" as a section (its legend moves under the chart), and the year stripes.
7. Orange outside the data: risk chips, the recommendation box (fill, orange rule, ALL-CAPS label) and the map's high-risk marker become ink and grey. Orange now means only "rising" in a chart.
8. The two-line wrap of sidebar pin lines ("every 10 years" becomes "per decade").

## 1. Page order (measurement window, desktop first)
Top bar and sidebar unchanged except section 4. Main column, top to bottom:
1. Page head (`h1`, question): unchanged.
2. `.row`: answer card `#rec` beside `#map-slot`. Columns `minmax(0, 1.25fr) minmax(0, 1fr)` from 1180 px (was `minmax(440px, 1fr) 1.15fr`); stacked below 1180.
3. Place chart card `section#place-chart.card` (new, section 5).
4. `section#how.card` "How we calculated this" (new, section 6).
5. Compare chart card, then compare table card (section 7).
6. Foot: "Data: {source link}. Trends: our calculation (Mann-Kendall test with Sen's slope, seasons removed against the 1995–2014 average)." Place-name credit unchanged.

The place chart and `#how` describe the selected pin and render only when it is `ok` (section 9 has the other states).

## 2. Notation
- `t` = TrendResult, `s` = TimeSeries (with `s.anomaly`), `pin.label` = the pin's name. Every number shown comes from these fields; the browser only formats, converts units and draws.
- `val(x)`: signed (`+`, true minus `−`), 2 decimals if |x| < 1 else 1 (today's `fmtNum`), a no-break space, then the unit. A value in `t.units` is shown in `t.guidance.display.unit` × `display.factor`, then the Units setting (°F ×1.8, inches). A value whose units are `%` stays `%`.
- `lvl(x)`: the same, unsigned, for absolute levels (`baseline.value`, seasonal highs and lows, raw values). In °F a level is ×1.8 + 32, not ×1.8.
- `rng(a, b)`: "{val(a)} to {val(b)}" with the sign on both ends and the unit once: "+0.22 to +0.40 °C".
- `M(YYYY-MM)` = "December 2025"; `Mo(…)` = "Dec 2025"; `Y(…)` = "2025"; `D(YYYY-MM-DD)` = "22 November 2026".
- `{measure}` = "air temperature", "the hottest day of the month", "rain", "sea level", "water storage". `{name}` = the window name ("Air temperature").
- `{src}` = today's card source text (`SOURCE_PLAIN`, plus " at {t.place.name}" for station sources), e.g. "NASA POWER", "NOAA tide gauge at The Battery".
- `{range}` = `t.range_kind` ("95% range"). Never write "confidence interval" on screen; never "X% chance it's real".
- Links: `https://` only; `record_url` falls back to `source.url` if missing. All text via `textContent`.

## 3. The answer card `#rec`
```
.where      h2#rec-h {pin.label}                                  [risk chip]
            p.meta  <a href=t.source.record_url>{src} ↗</a> · {t.latest.text, never split across lines}
.verdict    b [▲|▼|≈ aria-hidden] Rising | Falling | No clear change     span {conf}
p.say       {why}
p.world     {the world line}.                                       (only with a world figure)
.model      the model note [+ button "Compare with the nearest weather station"]   (below)
.reads      R1 | R2 | R3
.advice     "Our recommendation" + t.guidance.recommendation      (only when present)
.acts       button#how-open "How we calculated this ↓"
p.disc      t.guidance.disclaimer                                 (only with a recommendation)
```
- Risk chip: `t.guidance.risk_label` when it is a non-empty string; none for the hottest day (contract: `risk` null), and none when the label equals the verdict word ("No clear change"), because the headline already says it.
- `{conf}`: rising or falling "{t.meaning.confidence} · {round(t.record.years)} years of records"; no clear change "{round(t.record.years)} years of records". Add " (short record)" when `t.record.status` is `"short"`.
- `{why}`: `t.guidance.why` with the rain note in brackets (today's `whyOf`); if null, `t.meaning.headline`.
- Readouts (cells 14 px grey label, 26 px value in Inter 650 tabular, 14 px grey line under):
  - R1 label "Now, compared with {t.baseline.text}"; value `t.now.text` (with the Units setting, `val(t.now.value)`); line "Average of {t.now.label}". `now` is the measured average of the 12 latest months, never the end of the trend line. Rain (`now.kind` "12-month total"): line "Rain in {t.now.label}, % above or below a usual year". `baseline.method` `"fitted"`: add ". Baseline estimated from the fitted trend." `t.now` null: no R1 cell.
  - R2 label "Rate, {Y(t.fit.start)}–{Y(t.fit.end)}"; value `t.headline_rate.text` with its `per` ("a year", "per decade") printed smaller after the number (sea level "+3.1 mm a year", air temperature "+0.31 °C per decade"); line "{range} {t.headline_rate.range_text}". No clear change and the range holds 0: add ", which includes no change". Short record: add ". Short record."
  - R3 label "What experts project"; text `t.projection.why` (14 px grey). Sea level: then a link line `t.guidance.future_link.label ↗`. PR2/PR3 replace this cell when `projection.available` is true.
  - Three equal columns with hairlines when the card is at least 520 px wide (container query on `#rec`); narrower, each readout is a row: label and line on the left, value on the right.
- `.advice`: 3 px `--ink` left rule, no fill, no radius; label 14 px `--ink-2` weight 500, sentence case; text 16 px.
- The button is a `<button>` (the hash holds the route): it scrolls `#how` into view (instant under reduced motion) and focuses `#how-h`. It never opens a step.
- A re-render that removes the control that had focus in the card (the station button, a link) puts focus on the new card's heading, never on `<body>` (QA N5).
- Hottest day: verdict, `{why}` from `meaning.headline`, readouts, button; no chip, no advice, no disclaimer.
- The model note (QA B10), between the world line and the readouts; nothing is fetched for it:
  - NASA POWER air temperature or hottest day: "This comes from a weather model grid {size} wide. A weather station nearby can tell a different story." {size} is read from `t.explain.data.where` ("about 50 km"; no size when it names none). Then a button "Compare with the nearest weather station" (only when the measurement offers `ghcn`), which picks the weather station as the source, as the source select does.
  - A weather station answer, when the page already holds this place's NASA POWER answer: same verdict, "The weather station and the model agree here." (15 px grey); a different verdict, "The weather station and the model disagree here." (`.model.strong`, 16 px ink 600), then a plain line under it: "For the heat you feel day to day, the station is closer to the ground; the model covers a wider area." No POWER answer on the page, or ERA5: no note.

## 4. Sidebar and map
- Remove the "Look ahead to" label, `#seg-look` and `TDPrefs.lookAhead` (gone from `prefs.js`; nothing reads it).
- Pin line: "{fmt.rate(t)} per decade" (rain "+4.8% per decade"), else "No clear change"; one line, ellipsis if it overflows. Pin chip: the label without " risk" ("High", "Moderate", "Low", "Moderate to high"), and "Unclear" for "Risk level unclear (low to high)", 12 px.
- Chips everywhere (card, pins, table): High = `--ink` fill, `--surface` text. Moderate = 1.5 px `--ink` border, ink text. Low and Not enough data = 1.5 px `--control` border, `--ink-2` text. Words carry the meaning.
- Map: the high-risk marker uses `--ink` instead of orange (`map.css` `.map-mk.high`). Nothing else on the map changes in PR1.

## 5. The place chart `#place-chart`
```
.chead   h2 "{name} at {pin.label}[ ({t.place.name}) for station sources], {Y(period.start)} to {Y(period.end)}"   button "Download CSV"
         p   "Seasons removed: each month is compared with its own {t.baseline.text}." [sea level: " Measured against the land, so land sinking adds to the rise."] " Records: " <a record_url>{src} ↗</a> ". {t.latest.text}."
svg      (below)
.legend  "From the records:" Monthly value, seasons removed · [Preliminary month (may still change), only if any]   "Our calculation:" Yearly average · Trend line · 95% range of the trend · 1995–2014 average (zero)
p.readout  "Hover, tap or use the arrow keys to read a month."
p.summary  (the text summary, below)
details  "Show the data as a table"
```
- Rain: the sub-line ends "…its own {baseline.text}, as a share of the usual rain." Yearly data (`cadence` annual) or `deseasoned_upstream`: drop the "Seasons removed" sentence.
- Rain on yearly values (`t.yearly` present, with a baseline): the trend runs on yearly totals, so the chart plots them. One point a year at mid-year, `t.yearly[].value` in `fit.units`, as the faint line plus an ink dot each; `fit` is drawn through them; the x axis runs from the first January to the last December. Sub-line "Each dot is one year's rain, compared with {baseline.text}."; y title "Each year's rain, % above or below {baseline.text}"; the first legend key is "Each year's rain" (line and dot), with no "Yearly average" or preliminary key. Readout "{year}: {val(value)} compared with the usual year (1995–2014)."; hint "Hover, tap or use the arrow keys to read a year." Without `yearly` (an older answer): the monthly plot as above.
- One panel. Drawn at its box width (1 unit = 1 px, text 12 px minimum), height 330, margins left 52, right 150 (96 under 600 px wide), top 34, bottom 34.
- y-axis title, top left above the plot, 13 px ink 600: "{unit} compared with {t.baseline.text}" ("°C compared with the 1995–2014 average"; rain "% of the usual rain, compared with the 1995–2014 average"; water storage "cm of water compared with {baseline.text}"). A chart under 600 px wide uses a title of at most about 40 characters, so it is never cut (`ytitleNarrow`, QA B9): "{unit} compared with {baseline years}" ("°C compared with 1995–2014", "cm of water compared with 2004–2009"); rain "% above or below the 1995–2014 average"; no baseline keeps "{unit}, as measured".
- Marks, back to front: baseline years band (`baseline.years`, `--band`, label "1995–2014" 12 px grey at its top); grid; the 95% range (two lines through the middle of the fit, at level `fit.level_end − fit.change / 2`, with slopes `ci_low` and `ci_high` per decade, from `fit.start` to `fit.end` only; verdict colour at 20% fill, 1.5 px dotted edges `2 3`); monthly values (`s.anomaly.values`, 1 px `--chart-faint` at 45% opacity, broken at nulls); preliminary months (`s.flags`) as a 1.5 px ink dotted line `1.5 3` joined to the last regular month; the zero line (1.5 px `--ink-2`, dash `6 4`); yearly averages (ink dots r 3.4 at mid-year; a year needs 9 valid, non-preliminary months); the trend line from (`fit.start`, `level_end − change`) to (`fit.end`, `level_end`), 3.5 px verdict colour, round caps; an end dot r 5 in the verdict colour with a 2 px `--surface` ring.
- Right margin labels: at the end dot, `val(level_end)` 15 px bold ink, under it "trend line, {Mo(fit.end)}" 12 px grey; at zero, "0 = the 1995–2014" / "average" 12 px grey. If the two would touch (under 40 px apart) the end label moves away from zero; the zero label never moves. Under 600 px the second lines are dropped.
- No future, no "today" rule, no smoother in PR1. Ticks: today's rules (x by screen spacing; nice y ticks).
- Readout on a month (hover, tap, arrows as today): temperature, hottest day, rain "{M}: {lvl(value)} measured, {val(anomaly)} compared with the usual {Month} (1995–2014)."; sea level and water storage "{M}: {val(anomaly)} compared with the usual {Month} (1995–2014)." Add " Preliminary." for a flagged month.
- Text summary (visible, and the SVG's `aria-label`): "{name} at {place}, {M(period.start)} to {M(period.end)}, compared with {baseline.text}. The trend line {rises|falls} {abs value of slope} per decade ({range} {rng}) and stands at {val(level_end)} in {M(fit.end)}." No clear change: "The trend line moves {val(slope)} per decade, which we can't tell apart from no change ({range} {rng}), and stands at …". Then, if any: "{Month and Month YYYY} {is|are} preliminary." Then "Verdict: {rising|falling|no clear change}{, very clear|, clear}."
- Table (closed `details`): columns "Month", "{name} ({unit})", "Compared with {baseline.text} ({unit})", "Note" ("Preliminary"); a missing value reads "no data"; caption "Records: {src}. {t.latest.text}." Sticky header, 320 px scroller, oldest first (as today).
- Rain on yearly values: the table has the rows the chart plots, one a year: columns "Year", "Each year's rain, compared with {baseline.text}"; each value as the readout prints it (`yearly[].value`, "no data" when null); caption "Records: {src}. {t.latest.text}. One row a year, as the chart shows; the CSV has every month." The region's label is "Yearly data table".
- No baseline (`baseline.method` "none"): plot `s.values` as measured (monthly line and yearly dots), y title "{unit}, as measured", no band, zero line or trend; a grey line under the chart: "This record has too few years from 1995 to 2014 for an average, so the chart shows the values as measured, with no trend line. The rate on the card still holds."

## 6. "How we calculated this" `#how`
```
section#how.card  aria-labelledby=how-h
  h2#how-h tabindex=-1  "How we calculated this"
  p.lead "For {pin.label}. Every number below is the one the card and the chart use."
  ol.steps > li > details  (summary: number · title · short answer · chevron)
                           (body: words on the left, "The working" box on the right; one column under 900 px)
  p "Numbers are rounded, so the last digit of a sum can differ by 1."
```
- Steps 3, 4, 5 and 6 start open; 1, 2, 7, 8 and 9 start closed, at every width (the owner's choice). A closed step shows its short answer in grey on the summary row (under the title below 900 px); an open step hides it (`visibility: hidden`), so nothing is said twice. Every new answer renders the steps in this default state. Summary rows at least 52 px; the whole row toggles.
- The working box: `--work` fill, 8 px radius, 15 px, a 13 px grey label "The working".
- Months in words come from `MONTHS_LONG`. Pluralise counts ("1 month is missing").

| # | Title | Short answer (closed) | Words | The working | Link |
|---|---|---|---|---|---|
| 1 | The data | "{n_months} months from {src}, {M(start)} to {M(end)}" (`t.explain.data`) | "We used {n_months} monthly values of {measure} from {t.source.name}, for {explain.data.where}. They run from {M(start)} to {M(end)}. {n_missing} months are missing." (0: "No months are missing.") If flags: "{k} months are preliminary: the provider may still change them, so the trend leaves them out." | "How the provider made them: {source.method}" / "Dataset: {dataset_id}. Version: {version}. Retrieved {D(retrieved)}." (no "Version" when null) | "Open this exact record ↗" (`record_url`) |
| 2 | Seasons removed | "Highest in {high month}, lowest in {low month}: a swing of {lvl(swing)}" (`t.explain.seasons`) | Temperature, hottest day, rain: "Here {measure} is usually {lvl(high)} in {high month} and {lvl(low)} in {low month}: a seasonal swing of {lvl(swing)}." Sea level, water storage: "Here {measure} is usually highest in {high month} and lowest in {low month}: a seasonal swing of {lvl(swing)}." Then: "The change we look for is {val(fit.change)} over {round(fit.years)} years. So we compare each month with its own {baseline.text} first." Rain adds ", and write the difference as a share of the usual rain". | Last regular month m: "{M(m)}: {lvl(value)} − {lvl(normal)} (the usual {Month}) = {val(anomaly)}" (`normal` = `baseline.months[month]`). Sea level adds "Heights are against the gauge's own zero." Rain: "{M(m)}: ({lvl(value)} − {lvl(normal)}, the usual {Month}) ÷ {lvl(baseline.value)}, the usual rate = {val(anomaly)}". Under it a figure: two 56 px strips of the last 10 years, "As measured ({unit}), last 10 years" and "Seasons removed ({unit} compared with 1995–2014)" (rain, in the chart's words: "Seasons removed (% above or below the usual rain)"), ink 1.2 px, `aria-hidden`. | "Check it yourself: the CSV's anomaly column is each value minus its month's 1995–2014 average." + button "Download CSV" |
| 3 | One baseline | "Every level is compared with {baseline.text}[ here, {lvl(baseline.value)}]" (value only for temperature, hottest day, rain) | "Every level on this page is compared with {baseline.text} at this place[, {lvl(value)}], so 0 means that average. The card, the chart, the table and the CSV all use it. Expert projections from the IPCC use the same years, so past and future can share one axis." | Observed: "{years_covered} of the 20 years from 1995 to 2014 have at least 9 months of data. We need at least 15." Fitted: "{years_covered} of the 20 years have at least 9 months of data; we need 15. The record spans {round(record.years)} years, at least 5 of the 20 years are counted, and it has data both before 1995 and after 2014, so we fit the trend and the seasons together and take the line's 1995–2014 average ({baseline.label})." | none |
| 4 | The trend and its range | "{headline_rate.text}, {range} {headline_rate.range_text}" | "From {Y(fit.start)} to {Y(fit.end)}, {measure} here {rose\|fell} by about {headline_rate.text without its sign}[ (every 10 years), for a rate per decade]. The trend is very likely between {low} and {high} ({range})." (low and high from `headline_rate.range_text`). No clear change: "…changed by {headline_rate.text}[ (every 10 years)], which we can't tell apart from no change. The trend is very likely between…". New paragraph: "We use Sen's slope: the middle of the slopes between every pair of months. One odd month can't pull it far." Short record adds: "This is a short record ({round(record.years)} years). Its trend can move when new years arrive." | "Over the record: {the rate as the API gives it, no digit added or lost; in °F or inches converted, with the same decimals} {headline_rate.per} × {span ÷ 10, 2 decimals} decades \| {span} years = {fit.change in the rate's unit}[, which is {val(fit.change)}, when that unit differs: sea level's cm] ({range} {rng(change_low, change_high)})." The span is the months from `fit.start` to `fit.end` ÷ 12. / "The trend line ends at {val(level_end)} compared with {baseline.text}, in {M(fit.end)}." (only when `level_end` is not null) / "The card’s “Now”, {now value}, is the measured average of {now.label}, not a point on the line." (rain: "is the rain measured in {now.label}"; only when `now` is not null) | none |
| 5 | Is it real? | "{meaning.confidence}: by chance, {explain.real.in_100} in 100" | "If there were no real trend here, a trend at least this strong, up or down, would turn up by chance in {in_100} of 100 records like this one." New paragraph: `explain.real.rule` verbatim. No clear change adds: "That does not mean nothing changed. The data can't rule out anything from {headline_rate.range_text}." | "p-value {under 0.001 \| p to 3 decimals}, so {below \| not below} 0.05 · {range} {headline_rate.range_text}, {all above zero \| all below zero \| which includes zero} → {confidence in lower case}." If `real.widened` (it says what we did, not what the data are): "Months next to each other can be alike, and so can whole years in a row. We allow for that, so this range is wider than {explain.data.n_months} separate months would give." Sea level, always: "Slow swings in the ocean that last a decade or more can still make this range a little too narrow." Water storage, always: "Slow swings in rain and groundwater that last several years can still make this range a little too narrow." | none |
| 6 | Compared with the world | Available: "Since {Y(window.start)}: here {local_rate}, world {world_rate}[ ({ratio}×)]", rates with `world.unit`; the ratio only for a clear trend (no clear change shows the two rates alone). Else `world.why_none`, else `world.text`. | Available: `world.text` (with °F or inches, it ends " (in metric)."), then `why_none` when it is set (a world figure that did not rise: no ratio). Sea level adds a paragraph: "Satellites measure the height of the sea surface itself. The tide gauge measures the sea against the land, so if the land here is sinking, that adds to the local number." (never "land rebound" or "isostatic" in our words; the world-method line below is the API's text). Air temperature adds: "The world figure is built from weather stations on land."[ " The number here comes from a weather model, so the two are measured in different ways." when `source.id` is `power` or `era5`; not for `ghcn`]. Else `why_none` or `text` (rain and water storage print their own-place rule). | Available: "[{local_rate} ÷ {world_rate} = {ratio}× · {ratio_low} to {ratio_high} times ({range}) · ]{M(window.start)} to {M(window.end)} · {world.method}." The ratio part only with a ratio; its range only when `world.text` doesn't already give it. The division is always in metric, like `world.text` above it, so the step uses one unit (B5). / "1× is the same as the world. {high}× or more: high risk. {moderate}× to {high}×: moderate risk. Under {moderate}×: low risk. Here: {risk_label in lower case \| no risk level}." A two-level label ("Low to moderate risk") with the ratio's range shown ends instead ", because the {range} spans more than one level." "Risk level unclear (low to high)" ends instead "Here the {range} spans every level, so the risk level is unclear." Sea level adds: "The full record, {Y(fit.start)} to {Y(fit.end)}: {headline_rate.text}. It gets no world ratio, because satellites only start in 1993." and "The world figure: {world.source.method, first letter in lower case}" (it names what the satellites don't correct for). | "{world.source.name} ↗" (`world.source.record_url`) |
| 7 | What comes next | `t.projection.why` | `projection.why`, then "We never stretch the past trend into the future. Future values on this page come only from published expert projections." | none | Sea level: "{future_link.label} ↗" |
| 8 | Things to keep in mind | first note + " And {n − 1} more" (n counts caveats and notes, not the fixed last line) | A list: `t.caveats`, then `s.notes` (no repeats), then "This shows whether {measure} changed here. It doesn't say why." | none | none |
| 9 | Sources | "{t.source.name}[; world figure from {world.source.name}]" | A list: "Records: {source.name}, {dataset_id}[, version {version}] (a version that already starts with "Version" is printed as given; the same in step 1). Retrieved {D(retrieved)}. Open this exact record ↗"; if available "World figure: {world.source.name}. Retrieved {D(world.source.retrieved)}. Open it ↗"; "Our calculation: the Mann-Kendall test and Sen's slope on monthly values with seasons removed, against {baseline.text}." Then button "Download CSV". | none | in the list |

- Step 2 when `deseasoned_upstream`: short "Already removed by the provider"; words "The provider has already removed the seasons, so we use its values as they come."; no working, no figure. Yearly data: short "Yearly values: no seasons to remove"; words "These are yearly values, so there are no seasons to remove."
- Step 3 for `"provider"` (water storage): short "Every level is compared with {baseline.text}"; words "Every level on this page is compared with {baseline.text}: {baseline.label}. Water storage has no expert projection, so it keeps the provider's own reference."; no working. For `"none"`: short "No 1995–2014 average for this record"; words "This record has too few years from 1995 to 2014 to make that average, so this page shows no levels for it, only the rate."; working "{years_covered} of the 20 years have at least 9 months of data. We need at least 15, or a record of 30 years or more with at least 5 of the 20 years counted and data both before 1995 and after 2014." (The rule is contract `baseline.method` "fitted".)
- Rain on yearly values (`explain.data.n_years` present): step 1 short "{n_years} years from {src}, {Y(start)} to {Y(end)}"; words "We used {n_years} yearly values of rain from {source.name}, for {where}, built from {n_months} monthly values. They run from {Y(start)} to {Y(end)}. A year counts when at least 11 of its months have data. {k years are left out \| No year is left out}." (k = `n_missing_years`). Step 4's Sen's slope sentence says "every pair of years. One odd year can't pull it far." Step 5's widened line has no months clause: "Years next to each other can be alike. We allow for that, so this range is wider than {explain.data.n_years} separate years would give." Step 9 says "on yearly rain" for "on monthly values with seasons removed".
- Real or noise? moves into step 5's body, full width under the two columns, after a hairline. `noise.js` is unchanged; in step 5 its idle card loses border and padding and reads as one line plus its button (`noise.css`). The shell fires `td:load-end` when the selected pin's answer renders and `td:load-start` when the selected place changes (the dialog fired them before); the module still sends nothing until its button is pressed.

## 7. Compare chart and table (PR1 changes only; PR4 redesigns them)
- Each place's yearly means of `s.anomaly.values` (a year needs 9 months), then a centred 5-year average shown only where 4 of its 5 years exist (D6); it breaks at gaps. Delete `baseline()` and every `outlook`/wedge path. The x axis ends at the last plotted year.
- Head: h3 unchanged; caption "Five-year averages, in {unit}, each compared with its own {baseline.text}." then " {t.latest.text}." when every plotted place has the same `latest.month`, else " Records end at different months; the table has each one." Button "Download CSV" at the right.
- y-axis title as the place chart ("{unit} compared with the 1995–2014 average"); y tick labels take decimals from the step ("+0.5"). Legend: place keys only. `aria-label`: "Line chart: five-year averages in {unit}, each compared with its own 1995–2014 average, for {names}. Highest at the latest year: {name}." The table is the text version.
- A place whose `baseline.method` is "none" is left out: "Left out of the chart: {label} (no 1995–2014 average for its record)." A place with no record (a 400, or a series with no readings) is left out with "no tide gauge near enough" for sea level and "no usable record here" otherwise; a real failure (5xx, network) with "could not be loaded".
- Table columns: "Place", "Measured at", "Record" ("{Y(period.start)}–{Mo(latest.month)}", e.g. "1920–Oct 2025"), "Rate per decade", "× world, same years", "Risk". Ratio cell: "{world.ratio}×", for sea level "{ratio}× since {Y(world.window.start)}", "—" when `world.available` is false. A column whose every cell would be "—" is not shown (hottest day loses both "× world" and "Risk").
- Table caption: available "World figure for {selected label}: {world.text}[ {why_none}] Source: {world.source.name} ↗" (`why_none` whenever it is set); else "{selected label}: {why_none or text}".

## 8. CSV downloads (built in the browser from the fields; no new route)
- Place chart, step 2 and step 9 buttons, file `bhoomi-{window slug}-{place slug}.csv`:
```
# Bhoomi: {name} at {pin.label}
# Source: {source.name}
# Dataset: {dataset_id}; version: {version | not named by the provider}
# Record: {record_url}
# Station: {place.name}, lat {place.lat}, lon {place.lon}
# Baseline: {baseline.text} ({baseline.method}); anomaly = value minus the 1995–2014 mean of its calendar month
# Method: {source.method}
# Retrieved: {source.retrieved}
# Data through: {Month YYYY}
# Built with AI assistance. bhoomi.earth
time,value_{units},anomaly_{anomaly.units},flag
```
  The place line comes from `t.place`: "# Station: …" for station sources (tide gauges, weather stations), "# Grid point: [{place.name}, ]lat {lat}, lon {lon}" for grid sources, with no name when the name is only the coordinates; no line without coordinates. "# Data through:" is `t.latest.text` without its "Data through " (no line without `latest`). There is no datum line (the API has none; `source.method` names it in words). Header lines always start with "# " and are never quoted, so tools that skip "#" lines skip them: a double quote becomes ', line breaks and tabs become a space, and a piece after a comma that would start a formula (= + - @) gets a ' first. Text cells in the data rows (the compare CSV's place) get a ' when they start with = + - @, a tab or CR, and are quoted when they hold a comma, a quote or a line break; number cells are left alone.
  Rain's baseline line ends "anomaly = the difference from the 1995–2014 mean of its calendar month, as a % of the 1995–2014 average rate". No baseline: "# Baseline: none (too few years from 1995 to 2014)" and an empty anomaly column. Values in the record's own units, whatever the Units setting; nulls are empty fields; `flag` is "preliminary" or empty.
- Compare chart, file `bhoomi-{window slug}-your-places.csv`: lines 1 "# Bhoomi: {name} at your places", then the Baseline and "Built with" lines, then one "# Place: {label}; Source: …; Dataset: …; version: …; Record: …; Method: …; Retrieved: …" per plotted place in pin order, then `place,time,value_{units},anomaly_{units},flag`.

## 9. States (selected pin)
- No pin: card as today ("Pin a place to see its recommendation"); place chart and `#how` hidden.
- Loading: card as today (heading, progress bar, "Checking {source}. This usually takes about {n} seconds."). Place chart card shows its h2 and a flat `--work` block 330 px tall (no motion) with "Loading the records…"; `#how` hidden.
- Error (any 4xx/5xx, including a record under 20 years): the API `detail` word for word; place chart and `#how` hidden. Then the next step:
  - A "no record here" answer (a 400, or a series with no readings) from a source picked by hand, when the page already holds a working answer for this place from the measurement's default (a US coast where NOAA CO-OPS worked, then PSMSL picked by hand): a button "Try {the default source} instead", which picks the default again. Otherwise no button: the default found nothing here, or the page has no answer from it.
  - Sea level with no record here and no such button (B7, a step that needs no data): "Without a usable tide gauge nearby, our records can't tell you about this coast. For property here, check local flood maps and whether the land is sinking."
  - Anything else: "Try another place."
- Short record (20–29 years): shown in full, with the " (short record)" and ". Short record." additions above and the step 4 sentence.
- Fitted baseline, no baseline, rain, hottest day, no clear change: as written in sections 3, 5 and 6. No world figure: no ratio anywhere; step 6 prints `why_none` or the own-place rule. No projection (all of PR1): R3 and step 7 print `projection.why`.

## 10. Tokens and type (light first; dark in brackets)
- New: `--control` #767676 (#8C8C8C), the border of every control, chip and the AI label (4.5:1 on white, 5.2:1 on the dark surface); `--band` #EDEDE8 (#23272B), the baseline years; `--work` = `--bg`, the working box. Unchanged: `--bg` #F6F6F3, `--surface` #FFFFFF, `--ink` #141414, `--ink-2` #5A5A5A (6.4:1 on `--bg`), `--line` #E3E3DE (decorative only), the verdict and pin colours.
- Stop using `--accent`, `--risk-*` and `--advice-*` outside charts.
- Body 16/1.5 (was 15/1.45); lead `p.say` 18; labels and help 14 (pin chips 12, sidebar section labels unchanged); verdict word 40 Space Grotesk 700 with a 30 px shape; card h2 24; section h2 20; readout values 26 Inter 650 tabular.
- `.btn` and `.seg` buttons at least 44 px tall, 15 px text.
- The monthly line (45% of `--chart-faint`) is texture and below 3:1 on purpose: at full strength it hid the trend. The readable series are the ink yearly dots and the trend line; every month is in the table and the readout.

## 11. Checks for QA (1440 and 1920, light first; then 375)
- [ ] No "If the past trend continues", "by 2050", wedge, dashed future, "today" rule or "Look ahead to" anywhere.
- [ ] One zero: card R1, chart axis title and right label, step 3, table column and CSV header all name the 1995–2014 average (provider period for water storage). R1 is `now.text` (the 12 latest months), not the chart's end label; the chart's end label equals step 4's "The trend line ends at" line, and step 4's last line says which is which.
- [ ] Every range on screen says "95% range". p-value text never says "chance it's real".
- [ ] The card's source link and step 1's link open `record_url`. "Data through {Month YYYY}" shows on the card, the place chart and the compare chart.
- [ ] "How we calculated this ↓" scrolls to `#how` and focuses its heading; steps 3, 4, 5 and 6 open, the rest closed with short answers; keyboard toggles each step.
- [ ] Hottest day: no chip, no advice, no "× world" or "Risk" column; step 6 says there is no matching world figure.
- [ ] Both CSVs open in a spreadsheet with the header lines above; values match the table.
- [ ] No orange outside charts. Controls 44 px with `--control` borders. "Built with AI assistance" visible. At 375 px: readouts stacked, steps single column, no horizontal page scroll.

## 12. Left for later
- PR2/PR3 fill R3, step 7 and the chart's future (projection band, "today" rule). PR4 replaces the compare chart and table.
- Sea-level units (QA B5; the owner may change this): on screen, levels and changes are in cm (inches with the Units toggle), and rates are in mm a year, as NOAA reports them (`headline_rate`; never cm per decade). Every "The working" box uses the unit of the sentence it explains: step 4's over-the-record sum multiplies the mm-a-year rate and then gives the change in cm ("… = +322.3 mm, which is +32.2 cm"), the same cm as step 2. The data table and the CSV keep the source's mm, with the unit in the column header.
