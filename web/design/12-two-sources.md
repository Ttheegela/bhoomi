# 12 Records side by side (rework PR4a): one main record, the others beside it

The owner's decisions (relayed 22 Nov 2026) are fixed. ERA5 is the main record for air temperature and the hottest day. NASA POWER stays main for rain. The other records sit beside it as comparison rows: NASA POWER or ERA5, and the nearest weather station within 25 km. When their verdicts differ, the card lists plain reasons, the POWER drift line among them. Facts only: no risk level, no advice, no "which record to trust". This file replaces the draft in 8c43a61 (two-column pair card, two-record chart, `/api/station`, `pair` block, risk span); none of that was built. It wins over `10-foundation.md`, `14-facts.md` and `15-cmip6.md` where they differ.

Pictures: `rework-pr4-records-design/` in the side-session notes (static mock, "sample" numbers). If the mock and this file differ, this file wins.

## 0. What changes
1. Main record per measurement (§1); the catalog's `sources` order changes (data lane).
2. Card: a new block "Records for this place" after `.reads` (§3), and a link on the verdict line when the records disagree.
3. Goes, for these three measurements: the model note `.model`, its button "Compare with the nearest weather station", and the station answer's agree/disagree lines (`modelNote` in `explain.js`).
4. Place chart: unchanged (main record only). Its sub-line gains the preliminary sentence (§7).
5. Sidebar: the label reads "Main record", with new help lines (§6). New step 8 "Other records"; old 8 and 9 become 9 and 10, so steps 1 to 7 keep their numbers (§9). CSV header lines (§10).
6. Unchanged: map, compare chart and table (main record only), sea level, water storage.

## 1. Main record and rows
| Measurement | Main (chart, 95% band, card, projection baseline) | Rows beside it, in this order |
|---|---|---|
| Air temperature, Hottest days | ERA5 | NASA POWER, then the weather station |
| Rain | NASA POWER (PRECTOTCORR, gauge-corrected) | ERA5, then the weather station |
- Weather station: the nearest GHCN-Daily station within 25 km with 30 years since 1981, by today's `ghcn` ranking. The radius is 25 km everywhere: page, Ask and MCP.
- When the visitor makes another record main (§6), the other two become the rows: the main record first, then the other model, then the station.

## 2. Data flow (recommendation)
**One shape, computed on the server**, so the page, Ask and MCP see the same rows and the same "records disagree". The page never works out agreement, a reason or a drift.
- `detect_trend` and `/api/trend` for `air_temp`, `air_temp_max` and `precip` add `comparisons`, `disagree` and `drift` (§11). The server fetches the other two records in parallel threads with the main one, using the existing per-point caches.
- `/api/trend` gains `compare` (default `true`). `compare=false` returns the same TrendResult with those three fields `null`. MCP `detect_trend` gets no new input and always compares.
- Page, per pin: `/api/series` and `/api/trend?…&compare=false` as today, to draw the card and chart. When that succeeds, it calls `/api/trend?…` and merges only `comparisons`, `disagree` and `drift` into the stored result (no chart redraw). The second call comes after the first, so the main record is already cached and nothing upstream is fetched twice.
- Why two calls: cold, a station's daily file takes 5 to 20 s (ERA5 1 to 2 s, POWER 2 to 5 s). One call would hold the whole card for the slowest record. Why not one call per source from the page: Ask and MCP need "records disagree" too, and drift needs both records' monthly series, which only the server has.
- Latency: the first paint is as today. The block fills max(other two) later: under 1 s warm, up to about 20 s cold. Ask and MCP: one tool call waits for all three (cold up to about 20 s a place; the agent can ask for two places in parallel). The other records' series are never sent to the page.

## 3. The answer card
```
.where    h2#rec-h {pin.label}
          p.meta   {main src} ↗ · {latest.text}[ ({months} preliminary)]          §7
.verdict  {▲|▼|≈} {word}   {conf}[ · <a href="#rec-oth">Other records disagree ↓</a>]
p.say · p.world · .reads R1|R2|R3                                                   main record, unchanged
.oth      Records for this place                                                    new
.next · .acts · p.disc                                                              unchanged
```
- The verdict link appears only when `disagree.any`. It is 15 px `--ink-2`, underlined, and moves focus to `h3#rec-oth` (`tabindex=-1`).
- `.oth`, margin 0 0 18 px:
  - `h3#rec-oth` "Records for this place": Inter 16 px, weight 650, margin 0 0 4 px.
  - `table`: full width, `table-layout: fixed`, 15 px, line-height 1.35. Visually hidden caption: "Records for {pin.label}: the main record first, then the others, each with its own trend." Rain adds " Rates are % of each record's own usual yearly rain."
  - Columns: "Record" 34%, "Trend" 30%, "Rate per decade" 18%, "Years" 18%. Header cells: 14 px `--ink-2`, regular weight, bottom-aligned, 1 px `--line` under, `position: static` (the global sticky `thead th` must not apply).
  - One row per `comparisons[]` entry, in order. Cell padding 10 10 10 0, top-aligned, 1 px `--line` under each row.
    - Record (`th scope=row`): the link "{label} ↗" to `source.record_url`, opening a new tab. Plain text when the URL is not https; no link when `status` is "none". Under it, 14 px `--ink-2`: `where`; on the main row "Main record · {where}".
    - Trend: `[▲|▼|≈]` (`aria-hidden`, 6 px gap), then "Rising", "Falling" or "No clear change".
    - Rate per decade: `headline_rate.text`, no-wrap, tabular figures; °F follows the Units setting as PR1 does, rain stays %.
    - Years: `years`, then 14 px `--ink-2` "{n_missing} months missing" when above 0.
    - Main row (class `is-main`, never `main`, which is the page column's class): every cell weight 650, a 1.5 px `--ink` rule under it.
    - `available` false: the Record cell as above, then one cell spanning the other three, 14 px `--ink-2`, `why` verbatim.
  - Under the table: §4's words, then every listed record's `source.limit` (14 px `--ink-2`, margin 8 px 0 0).

## 4. Agree, disagree, drift (server strings; the page prints them as given)
**Agree** (`disagree.any` false): `p.agr` (15 px ink, margin 10 px 0 0) `disagree.line`: "All three records agree: rising." / "… falling." / "… no clear change.", or "Both records agree: …" when two rows have a trend. With `drift` set, `drift.text` follows as a second `p.agr` (Sydney).

**Disagree** (any two verdicts differ):
```
p.dh  "The records disagree here."     16 px 650 ink, margin 12 0 2
p.dl  "Why records can differ:"        14 px --ink-2, margin 0 0 4
ul    disagree.reasons[].text          15 px ink, line-height 1.45, 4 px apart, 2 to 4 items
p.dn  "The records can't tell us which of these reasons applies here, so we show every record as it is."   14 px --ink-2
```
**Reasons**, server rules, in this order; the first 4 that apply. A disagreement always gets `point_vs_grid` (station in it) or `two_models` (models only), so the list is never empty.

| id | Applies when | Text (temperature and hottest day / rain) | Data the server must supply |
|---|---|---|---|
| `model_drift` | `drift` is set | `drift.text` | monthly anomalies of every row (already fetched); Sen's slope and MK of each model-minus-other difference |
| `station_gaps` | the station row misses ≥ 10% of the months in its fit span, or `record.status` is "short" | "The station's record has gaps: {n} of its {N} months are missing. Stations also move and change instruments, and NOAA doesn't adjust these daily records for that." Short: "The station's record is short: {years} years. Stations also move …" | station `explain.data.n_missing`, `n_months`, `record` |
| `near_line` | a row's `p_value` is between 0.01 and 0.15 | "Some of these trends sit close to the line we use for a clear change, so one unusual year can move a record across it." | every row's `p_value` |
| `point_vs_grid` | a station row has a trend | "The weather station is one thermometer at one spot, {km} km away, and roads and buildings around it can warm it. The weather models give the average over a grid cell {25 to 50} km wide." / "The weather station is one rain gauge at one spot, {km} km away; one storm can miss it or hit only it. The weather models give the average over a grid cell {25 to 50} km wide." | station `km`; grid size per source (ERA5 25, POWER 50; one size when one model has a trend) |
| `two_models` | ERA5 and POWER both have a trend and their verdicts differ | "ERA5 and NASA POWER are two different weather models. Each fills in the weather between observations in its own way, so their long-term trends can differ." / "ERA5 and NASA POWER are two different weather models. NASA POWER's rain is corrected every day to rain-gauge maps; ERA5's is not." | verdicts |

**Drift** (`drift`). Rule: for each model (ERA5, POWER), subtract each other row's anomaly from its own. Monthly anomalies are each record's value minus its own 1995–2014 calendar-month normal; rain uses yearly % anomalies. Run Sen's slope and the page's MK with its autocorrelation adjustment on each difference. Flag the model when every difference is a clear change in the same direction and at least 0.1 °C (rain: 2% of the usual yearly rain) per decade. Delhi, hottest day: POWER minus ERA5 is −0.39 °C per decade (−0.52 to −0.25). Text, the owner's line with the model named because three records are on screen: "Weather models can drift over decades at some places; at this spot {label} has been {cooling | warming | getting drier | getting wetter} relative to the other records." With two models only: "Weather models can drift over decades at some places; at this spot ERA5 and NASA POWER have drifted apart." (`drift.source` null). It shows as a reason when the records disagree and as its own line when they agree.

**Rain caveat** (`source.limit`, data lane; null for every other source and measurement): "NASA POWER's rain is corrected every day to rain-gauge maps. Where gauges are few (much of Africa, inland Australia, South America and the far north), it can drift." Above 62.5° latitude, add "This far north it gets no gauge correction."; between 42.5° and 62.5°, add "At this latitude the correction is only partial." It prints under the block whether POWER is main or a row, in step 9 when POWER is main, and in Ask and MCP output.

## 5. Block states (mock 06)
| State | The block shows |
|---|---|
| Compare call pending | h3 and the main row only, then `p.st role=status` (15 px `--ink-2`): "Reading the other records for this place: {NASA POWER \| ERA5} and the nearest weather station within 25 km. A weather station takes 5 to 20 seconds the first time. {n} s so far." `n` ticks each second, as the card's loading line does. No verdict link yet. |
| Compare call fails (5xx, network) | The main row, "We couldn't read the other records just now." and a button "Try again", which re-sends the compare call. A 429 shows the API's sentence, then "Try again". |
| No station within 25 km (`status` "none") | Row "Weather station", with no link and no `where` line. Spanning cell `why`: "No weather station within 25 km has 30 years of daily {mean temperature \| high temperature \| rain} data since 1981." |
| Station too short (`status` "short") | "Weather station ↗" and "{name}, {km} km away". Spanning cell `why`, e.g. "This station has fewer than 30 years of daily rain data since 1981, and no other station within 25 km does either." |
| One record couldn't be read (`status` "error") | Its spanning cell: "We couldn't read this record just now." Under the table, a button "Try the other records again". |
| Fewer than two rows with a trend | Rows only; `disagree` is null, so there is no line and no reasons. |
- The block's arrival never moves focus. A re-render that removes a focused retry button sends focus to `h3#rec-oth`. The card's `aria-busy` is false once the main record is drawn.

## 6. Sidebar "Main record"
- The control stays where it is, as a segmented control. On Air temperature, Hottest days and Rain it is labelled "Main record"; on Sea level it keeps "Measured by". Options follow catalog order: "ERA5 | NASA POWER | Weather station" (rain: "NASA POWER | ERA5 | Weather station").
- Help lines (14 px `--ink-2`), each followed by " The other records are listed on the card.":
  - ERA5: "ERA5: a European weather model of past weather, on a grid about 25 km wide."
  - NASA POWER: "NASA POWER: a NASA weather model on a grid about 50 km wide." Rain adds ", its rain corrected every day to rain-gauge maps" before the full stop.
  - Weather station: "The nearest weather station within 25 km with 30 years of records."
- Picking a record works as today (`pickSource`): the two calls for that source run, and results are keyed by source, so switching back costs nothing. A non-default main goes into the link as today. The pin line and the compare table follow the main record.

## 7. ERA5T preliminary months
- The data lane already flags a month `"preliminary"` when it ends less than 3 months before retrieval (`era5.py`). Stats already leaves those months out of the baseline, the trend, `now` and the yearly dots (9 regular months).
- Card meta: after `latest.text`, a second no-wrap span " ({months} preliminary)". Within one year: "(October preliminary)", "(August to October preliminary)". Across two years: "(November 2026 to January 2027 preliminary)".
- Chart sub-line, after "{latest.text}.": "{August to October 2026} {is|are} an early release that ERA5's makers may still correct, so the trend and the dots leave {it|them} out." A monthly chart keeps the dashed `s-pre` line and its legend key. The text summary keeps "… are preliminary."
- Table under the chart: Note "Preliminary" (existing). CSV: `flag` "preliminary" (existing) plus `# Preliminary: {months}; ERA5T, an early release that may still change; left out of the trend`. Step 1 keeps its line. The ERA5 row's years come from `fit`, so they leave the preliminary months out.

## 8. Naming the main record
- Step 3 short: "Every level is compared with {main}'s 1995–2014 average here, {lvl}". The words add " in {main}, the main record," after "at this place" and end with "The other records in step 8 each use their own 1995–2014 average." `{main}` is the PLAIN name: ERA5, NASA POWER, or "the NOAA weather station at {name}".
- Step 7's working already names `projection.baseline_record` ("This place's 1995–2014 average from ERA5: …"); keep it. R3 is unchanged: its 2050 value is a change from 1995–2014, so it doesn't depend on the record, and "more than today" already uses the main record's `now`.
- Lead of "How we calculated this": "For {pin.label}. Steps 1 to 7 use the main record, {main}; step 8 sets the other records beside it. Every number below is the one the card and the chart use."
- Step 10 Sources adds one entry per row with a trend: "Other record: {source.name}, {dataset_id}. Retrieved {date}. Open this exact record ↗". Its short lists every record, main first.

## 9. Step 8 "Other records" (mock 09)
- Short: agree "All three agree: {verdict}", plus "; {label} has been drifting {drier | wetter | cooler | warmer}" when `drift` is set. Disagree: "They disagree: {label} {verdict}, …", in row order, lower case. The step opens by default when `disagree.any` or `drift` is set.
- One column (`step-b one`). Words:
  1. "We ran steps 1 to 6 on {two more records | one more record} for this place, each against its own 1995–2014 average. {main}, the main record, leads the card and the chart; the others are here so you can see whether they agree."
  2. `disagree.line`, then `disagree.say`.
  3. When they disagree: "The reasons are listed on the card."
- Working, full width (`.work`; under 600 px it scrolls sideways in its own box with `tabindex=0` and an `aria-label`). A table with the records as columns, main first with " (main)". Its rows:
  - Months used: "{n}, {Mon YYYY} to {Mon YYYY}".
  - Months missing; ERA5 adds " ({k} preliminary)".
  - 1995–2014 average.
  - Rate per decade.
  - 95% range.
  - By chance, in 100.
  - Trend: "{verdict}, {confidence in lower case}".
  A record without a trend has "—" in its column and its `why` under the table. Then the drift line: "Drift, month by month, each record against its own 1995–2014 average: {label} minus {other} {rate} per decade (95% range {low} to {high}); …. We flag a model when it drifts the same way against every other record." Without drift: "No drift flagged at this spot."
- Step 9 "Things to keep in mind": the main record's caveats, now including its `source.limit`.

## 10. CSV (place CSV, main record's months as today)
After `# Retrieved:`, add these header lines:
- `# Main record: {source.name} (chart, trend and projection baseline)`.
- One line per other row: `# Other record: {source.name}[, station {name} ({id}), {km} km away]; {years}[, {n} months missing]; {headline_rate.text} per decade (95% range {range_text}); {verdict}; {record_url}`. A row without a trend: `# Other record: {label}: {why}`.
- `# Records agree: yes|no`.
- `# Drift: {drift.text}` when set.
- The preliminary line (§7).

Numbers use the ASCII hyphen-minus, with PR1's formula guard.

## 11. Contract additions (the orchestrator writes them into `docs/CONTRACTS.md`)
```json
"comparisons": [
  {"main": true, "source": {"id": "era5", "name": "ERA5 reanalysis via Open-Meteo archive", "record_url": "https://…"},
   "label": "ERA5", "kind": "grid", "where": "Weather model, grid cell about 25 km wide", "km": null, "station": null,
   "status": "ok", "available": true, "why": null, "years": "1981–2026", "n_months": 549, "n_missing": 0, "n_preliminary": 3,
   "baseline_value": 33.6, "verdict": "no_clear_change", "confidence": "Not clear", "p_value": 0.09, "in_100": "9",
   "headline_rate": {"value": 0.13, "low": -0.02, "high": 0.27, "unit": "°C", "per": "per decade", "text": "+0.13 °C", "range_text": "−0.02 to +0.27 °C per decade"}},
  {"main": false, "source": {"id": "ghcn", "…": "…"}, "label": "Weather station", "kind": "station", "where": "New Delhi Safdarjung, 3 km away",
   "km": 3.4, "station": {"id": "IN022021900", "name": "New Delhi Safdarjung"}, "status": "ok", "n_missing": 77, "…": "…"}],
"disagree": {"any": true, "line": "The records disagree here.",
  "say": "ERA5 shows no clear change. NASA POWER shows the hottest days getting less hot. The weather station shows them getting hotter.",
  "reasons": [{"id": "model_drift", "text": "…"}, {"id": "station_gaps", "text": "…"}]},
"drift": {"source": "power", "label": "NASA POWER", "direction": "cooling", "unit": "°C", "per": "per decade",
  "pairs": [{"against": "era5", "rate": -0.39, "low": -0.52, "high": -0.25}, {"against": "ghcn", "rate": -0.41, "low": -0.60, "high": -0.22}],
  "text": "Weather models can drift over decades at some places; at this spot NASA POWER has been cooling relative to the other records."}
```
- `comparisons`: the main record first (the same numbers as the top-level fields), then the other model, then the station. `null` for sea level and water storage, and with `compare=false`. `status`: "ok", "none", "short" or "error"; `available` is true when `status` is "ok"; otherwise `why` is one sentence (`ghcn`'s messages at 25 km; error: "We couldn't read this record just now."). `years`: "{Y(fit.start)}–{Y(fit.end)}". `km`: 1 decimal.
- `disagree`: `null` with fewer than two rows with a trend. `any`: the verdicts differ. `say`: "{label} shows {phrase}." for each row. Phrases: air temperature "it getting warmer" / "it getting cooler"; hottest day "the hottest days getting hotter" / "the hottest days getting less hot"; rain "more rain" / "less rain"; otherwise "no clear change". `reasons`: `[]` when they agree; otherwise §4.
- `drift`: `null` unless §4's rule fires. `source.limit`: data lane, a string or `null`.
- Also: `ghcn` `MAX_KM` becomes 25, with its messages. Station results carry `place.km`. Catalog `sources` become `air_temp` and `air_temp_max` ["era5", "power", "ghcn"] and `precip` ["power", "era5", "ghcn"]. `/api/trend` gets `compare`. Ask and MCP pass each row's `label`, `where`, `years`, `verdict` and `headline_rate.text`, plus `disagree.line`, `say`, the reason texts, `drift.text` and `source.limit`. Prompt (agent lane): when `disagree.any`, say the records disagree, give each verdict and the first reason, and never say which record is right. Voice: "If the records disagree, say so and give the first reason."

## 12. Phone, contrast, accessibility
- Card under 520 px (container query; 375 px in mock 05 and 08):
  - `thead` is visually hidden.
  - Each row is a grid block, padded 10 px 0, with a hairline under it: the name and `where` on the left, the verdict on the right; then on row 3 the rate with " per decade" (14 px `--ink-2`) on the left and the years and missing months (14 px `--ink-2`) on the right.
  - The main row keeps its 1.5 px `--ink` rule. A `why` cell spans the full width.
  - Explicit roles (`table`, `rowgroup`, `row`, `rowheader`, `cell`) stay, because Safari drops table semantics under `display: block`.
  - Measured page width: 375 at 375, 1440 at 1440, 1920 at 1920.
- Contrast, light (dark): `--ink` on `--surface` 18.42 (15.45); `--ink-2` on `--surface` 6.90 (8.67); `--ink-2` on `--bg` (the working table) 6.37 (9.48). The main-row rule is `--ink`, 18.42 (15.45). The `--line` hairline, 1.29 (1.36), is decoration; spacing also separates the rows. Button borders (`--control`) 4.54 (5.14). No new colours: the shapes are ink, and the word carries the verdict.
- Keyboard reaches the verdict link, each row link, the retry buttons and step 8. Screen readers get a real table with row headers and a caption, the reasons as a list, and the pending line as `role=status`.

## 13. Personas (under a minute each, no statistics words needed)
- **Planner, "Has it been getting hotter in Delhi or Princeton?"** I pin Princeton: Rising, very clear, +0.31 °C per decade, and "All three records agree: rising" (NASA POWER +0.34, a station 12 km away +0.29), so it isn't one dataset's quirk. Around 2050: +1.9 °C. Then Delhi: ERA5 says rising, but "Other records disagree ↓" takes me to NASA POWER showing no clear change, with the reason that it has been cooling against the others. Two of three say warmer, and I know why the third doesn't. Next: my national weather service.
- **Student, "Is Chennai really getting more rain?"** NASA POWER: Rising, clear, +5.5% per decade; ERA5 also rising (+6.9%); the station row says Madras Minambakkam has fewer than 30 years. "Both records agree: rising." The gauge note tells me where this kind of record is weaker. It isn't just this year.
- **Delhi hottest-day demo.** ERA5: No clear change, then "Other records disagree ↓": NASA POWER falling, the station 3 km away rising. Four reasons, drift first. The presenter says "three records, three answers, and here is why"; the chart stays on ERA5 with the CMIP6 boxes.
- **Sydney rain, the drift case.** All three show no clear change, but the rates differ: −5.4% (NASA POWER), +0.4% (ERA5), +2.9% (station). The drift line says NASA POWER has been getting drier relative to the others, and the gauge note follows. Step 8 gives the drift numbers.

## 14. Open questions
1. **ERA5 end date.** `era5.py` asks through December of last year, so ERA5T months show only from January to March. Today nothing is preliminary. Asking through the latest complete month would always show 3 preliminary months, and ERA5 would end about 10 months after POWER. The mocks show this second option. Owner's call; data lane.
2. **The drift line names the model** ("NASA POWER"), where the owner's words say "the model": three records are on screen.
3. **Thresholds.** Drift: 0.1 °C or 2% per decade, clear against every other record. `near_line`: p between 0.01 and 0.15. The stats lane should check them on the persona places. Expected: Delhi and Chennai hottest day and Sydney rain fire; Princeton doesn't.
4. **"Roads and buildings around it can warm it"** is a general possible reason, not measured here. Keep it, or let the domain reviewer cut it.
5. **The main record as the table's first row** (the brief said one row per other record), so the rates line up in one column.
6. **The UK GHCN longitude-sign guard** (Hampstead) feeds the "{km} km away" text. It should land in PR4a.

## 15. Checks for QA (1440 and 1920 light first; then dark and 375)
- [ ] Delhi, Hottest days: ERA5 card "No clear change" with "Other records disagree ↓"; rows NASA POWER falling and the station rising; "The records disagree here." with 4 reasons, drift first. No chip, risk or "trust" anywhere.
- [ ] Princeton, Air temperature: "All three records agree: rising." and no reasons. Sydney, Rain: the agree line, the drift line and the gauge note. Chennai, Rain: the station "too short" row and "Both records agree: rising."
- [ ] The card shows as fast as before; the block fills later without moving focus. Switching the main record, or coming back to a pin, asks the server nothing new.
- [ ] Preliminary months show in the meta, the chart sub-line, the table and the CSV. Every row links its own record. The footer carries the Open-Meteo credit on these three tabs, whichever record is main.
- [ ] 375: no sideways page scroll; rows show as blocks. Dark mode works. The keyboard reaches every link and button. Ask: "Is Delhi's hottest day getting hotter?" says the records disagree and gives a reason. MCP output carries `comparisons`, `disagree` and `drift`.
