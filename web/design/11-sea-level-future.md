# 11 Sea level future (rework PR2): past and future on one axis, the scenario control, what drives it, every decade

Build brief: `docs/REWORK-SPEC.md` (D1, D2, D4, D7, D8; PR2 items 4 to 7). Data: `docs/CONTRACTS.md` "Sea-level expert projection (PR2)". This file extends `10-foundation.md` (PR1) and wins where they differ. Sea level only: temperature, hottest day and rain get CMIP6 in PR3.

The owner sees a picture first: a static mock at 1440 px, light theme (The Battery with real AR6 values and a synthetic observed line; a regional estimate; the check outside; low confidence selected). It lives outside the repo with the owner's notes. If the mock and this file differ, this file wins.

## 0. What PR2 removes or moves (sea level with `projection.available` only)
1. Card R1 moves from the trend line's level (`fit.level_end`) to the 12-month average (`readouts.now`), so the card, the chart and "about 28 cm more than today" use one "now". The trend line's level stays in step 4.
2. Card R3 loses `projection.why` and its "Future flood map (NOAA) ↗" line. The 2050 readout replaces them; the link moves under the chart's readout line and into step 7.
3. Place chart: yearly dots go (the 12-month average replaces them); the trend line's end dot and its right-margin label ("+6.5 cm, trend line, Oct 2026") go; the trend line is 3 px (was 3.5).
4. Step 4's working loses "That is the first number on the card." (section 6).
5. Left out on purpose: 2110–2150 on the chart (table only), a 5th–95th percentile band on the chart (table and step 7), low-confidence medians that aren't selected, one card per scenario, a "show to 2150" toggle.

## 1. Page order (sea level, `projection.available`)
Page head · `#rec` beside `#map-slot` · `#place-chart` (now past and future) · `#future` "What experts project" (new) · `#how` · compare chart and table (unchanged until PR4) · foot. The foot adds " Future: <a href=p.source.record_url>IPCC AR6 sea level projections ↗</a> ({p.source.licence})." after the data link. With no projection the page is PR1 exactly.

## 2. Notation (adds to `10-foundation.md` §2)
- `p` = `t.projection`. `i(Y)` = `p.years.indexOf(Y)`. `X.p50@Y` = `X.p50[i(Y)]` (same for p05, p17, p83, p95).
- The scenario choice: `sel = {ssp, low}`, starting at `p.default_scenario`. `S` = the scenario whose id is `{ssp}_low` when `low` is on and that id exists, else `{ssp}_medium`. `S0` = the scenario with id `p.default_scenario`. One choice per browser tab, shared by the card, the chart, the readout line, the table and step 7; it survives switching pins and windows, never stored (a reload starts at the default).
- `{short}` = `S.name` without " emissions", first letter capitalised ("Intermediate", "Very high"). `{Name}` = `S.name` capitalised.
- `cm(mm)`: mm ÷ 10, 2 significant figures but at most 1 decimal, half away from zero, `+` or true minus, no-break space, "cm" (36, 8.0, 0.9, 104). Imperial: mm ÷ 25.4, same rounding, "in". `rngc(a, b)` = "{cm(a) without unit} to {cm(b)}": "+27 to +46 cm". Every projection number is formatted from its mm value with `cm()`; the server's `text` fields must come out equal (QA).
- `{more}` = `S.p50@2050 − p.readouts.now.value` → "about {cm(|more|) unsigned} more than today" (negative: "less"; 0: "about the same as today"). For `S0` it equals `readouts.more_than_today.text`.
- `{rk}` = `S.range_kind` ("likely range (about 2 in 3 chance)" or "17th to 83rd percentile"); `{rk short}` = "Likely" or "17th to 83rd percentile". `{lc}` = ", low confidence" when `S.confidence` is "low", else "".
- Old record: when `now.end` is more than 24 months before the current month (EST), "Now" reads "Latest" and "today" reads "in {Y(now.end)}" everywhere below.

## 3. The answer card `#rec`
- R1: label "Now, compared with {t.baseline.text}"; value `cm(now.value)`; line "Average of {now.label}" ("Average of the 12 months to October 2026"). `now` null: PR1's R1 (trend line).
- R2: unchanged.
- R3: label "By 2050, {S.name}"; value `cm(S.p50@2050)`; line "{S.code}{lc}. {rk short} {rngc(S.p17@2050, S.p83@2050)}. {More sentence}." The more sentence is "About {cm(|more|) unsigned} more than today." and is left out when `now` is null. Regional estimate: add " Regional estimate: local sinking may differ."
- The three cells share their rows (label, value, line; CSS subgrid), so the three values sit on one line however the labels wrap. Below 520 px the PR1 stacked rows stand.
- Everything else on the card is PR1.

## 4. The place chart `#place-chart` (past and future)
```
.chead    h2 "Sea level at {pin.label} ({t.place.name}), {Y(period.start)} to 2100"          button "Download CSV"
          p  PR1 sentence + " Future: <a p.source.record_url>IPCC AR6 sea level projections ↗</a> for {location.name}."
.scen     fieldset "Emissions scenario" (4 radios) · checkbox "Show the low-confidence version"
p         "Scenarios are possible paths for the world's emissions. Experts give no odds for which one will happen."
p#future-read (aria-live polite) · p.future-sub · [p.flag regional] · [p.flag check outside]
svg · .legend (3 rows) · p.gapnote · p.readout · p.summary · details "Show the data as a table" (PR1)
```
- Regional estimate: the sub-line ends " Future: <a>IPCC AR6 regional estimate ↗</a> for the {location.name}." (`location.name` is "1° area around 41°N, 73°W").
- **Scenario radios**: one segmented group (`role=radiogroup`; Tab enters at the checked one, arrows move and select), four buttons from `p.scenarios` with confidence "medium", low to very high. Each at least 52 px tall: a 22 px swatch (a `--surface` square with a 1 px `--control` border holding a 14 × 3 px line in `--scen-k`, dashed `4 2.5` when its low-confidence version is showing), then "{short}" 15 px 600 over "{code}" 13 px `--ink-2`. Checked: `--ink` fill, `--surface` text, code at 80% opacity. 1 px `--control` borders between buttons.
- **Checkbox** (native, 20 px, row at least 44 px): "Show the low-confidence version", under it 14 px grey "Adds ice-sheet changes that are hard to predict. The experts give no chance for its range." With it on and High checked, add: "High (SSP3-7.0) has no low-confidence version, so this shows its medium-confidence projection."
- **Readout line** (17 px): "<b>{cm(S.p50@2050)} by 2050</b> under {S.name} ({S.code}){lc}: {rk} {rngc(S.p17@2050, S.p83@2050)}. That is {more}." (the last sentence only when `now` is set). Under it, 14 px grey: "{p.caveat} For flood planning here: <a>{future_link.label} ↗</a>" (the link only when `future_link` is set).
- **Flags** (14 px, `--bg` fill, 3 px `--ink` left rule): regional estimate, `location.note` word for word; `check.inside` false, "Here the measured level for 2019 to 2021 is outside the experts' 2020 range. <a>Step 7 explains ↓</a>" (opens step 7, scrolls to it, focuses its summary).
- **Box**: drawn at its box width, height 400, margins left 52, right 170 (96 under 600 px), top 40, bottom 34. x from the record's first month to 2100; ticks by PR1's spacing rule (every 20 years at 1440). y covers the monthly anomalies, 0, and p17 to p83 of all four medium scenarios for 2020–2100, plus `S` when it is low confidence (then the axis grows once; switching among medium scenarios never moves it). y title, 13 px ink 600: "cm above {t.baseline.text}" (imperial "inches above …").
- **Marks, back to front**: baseline years band (PR1; its "1995–2014" label sits at the band's foot); grid; `S`'s band, a polygon through the decades 2020–2100 (p17 bottom, p83 top, straight segments, broken at nulls) filled `--scen-k` at `--scen-band`, 1 px edges in the same colour at 60%, dashed `4 3` for low confidence; the trend's 95% range (PR1); monthly values (PR1); zero line (PR1); the 12-month average, 1.6 px `--ink` (month m = mean of months m−6 … m+5 when 10 of the 12 are valid and not preliminary, drawn at the window's centre, broken where that fails, so it stops 6 months before the data); the trend line, 3 px verdict colour, `fit.start` to `fit.end`, no end dot; the "today" rule at the current month (EST), 1 px `--ink-2` dashed `3 3`, "Today" 12 px grey above the plot; the other three medium medians, 1.6 px in their colour at 75%; `S`'s median, 3 px, round caps, dashed `7 4` when low confidence; the 2050 dot on `S`'s median, r 4.5 in its colour with a 2 px `--surface` ring, labelled "{cm(S.p50@2050)} in 2050" 13 px 600 ink, centred 10 px above `S.p83@2050`; the Now dot at the middle of `now.start`…`now.end`, at `now.value`, r 5 `--ink` with a 2 px ring, labelled "Now {cm(now.value)}" 13 px 600 ink, 30 px up and 10 px left, end-anchored, with a 1 px ink leader. Text on the plot carries a 5 px `--surface` halo.
- **Right margin**: "In 2100:" 12 px grey above the top label; one label per drawn median at its 2100 height, "{short} {cm(p50@2100)}", 12.5 px, `S` in 650 ink, the others 400 `--ink-2`; a low-confidence `S` adds a second line "low confidence" 12 px grey. Labels at least 16 px apart (29 after a two-line label), pushed down; a 1 px leader in the line's colour joins each to its line end. Zero label as PR1. Under 600 px: names only.
- Projections are drawn as published from their own 2020 value (D4): never shifted, never joined to the observed line, nothing before 2020. Scenario colours never colour text.
- **Legend**, three rows, each led by a grey group word: "From the records:" Monthly value, seasons removed · 12-month average · Now [· Preliminary month (may still change)] / "Our calculation:" Trend line · 95% range of the trend · 1995–2014 average (zero) / "Experts (IPCC):" [four stacked 1.6 px stubs, one per scenario colour] Middle estimate for each scenario, named at the right · [band swatch, dashed edge for low confidence] {rk capitalised}, {short lower case}{lc} · [dashed stub] Today.
- **Gap note** (14 px grey): "The expert lines start at their own 2020 values, as published. We don't move them to meet the measured line, so a gap in 2020 is real; step 7 checks it."
- **Readout**: hint "Hover, tap or use the arrow keys to read a month, then each decade after the record ends." A month reads as PR1, plus " 12-month average: {cm}." where one exists. Past the last month the keys and pointer snap to decades (2020 too if the record ends before it); Right from the last month goes to the next decade, End to 2100, Home to the first month. A decade reads "{year}: {S.name} ({S.code}){lc} {cm(S.p50)}, {rk} {rngc(S.p17, S.p83)}. Others: {short} {cm(p50)}, …"
- **Text summary** (visible, and the SVG's `aria-label`): "Sea level at {place}, {M(period.start)} to {M(period.end)}, and IPCC projections to 2100, all compared with {baseline.text}. The trend line rises {headline_rate.text without sign} ({range} {headline_rate.range_text}). Now: {cm(now.value)} ({now.label}). Middle estimates for 2100: {name} ({code}) {cm}, … for the four medium scenarios. Shaded: the {rk} for {S.name}{lc}, {rngc(S.p17@2100, S.p83@2100)} in 2100. Verdict: {verdict}{, very clear|, clear}." No clear change: the PR1 wording for the trend sentence.

## 5. "What experts project" `#future` (new card, after the place chart)
- h2 "What experts project for {pin.label}" and button "Download CSV". Sub (15 px grey): gauge "IPCC AR6 sea level projections at the tide gauge {location.name}, {location.km} km from this one, compared with {p.baseline.text}."; regional "IPCC AR6 regional estimate for the {location.name} ({location.km} km from this gauge), compared with {p.baseline.text}." Then " Source: <a p.source.record_url>{p.source.name} ↗</a>, version {version}, {licence}."
- Two columns (drivers 1fr, decades 1.1fr, gap 36) when the card is at least 900 px wide; one column below.
- **What drives it**: h3 "What drives the rise by {drivers.year}". Sub 14 px grey: "{S0 Name} ({S0.code}), the one scenario this breakdown comes in. The bar is each part's likely range (about 2 in 3 chance); the dot is its middle estimate. The thin line is zero." A table, columns "Part", "Middle", "Likely range": one row per `drivers.parts` in contract order, then "Total" (`S0` p17/p50/p83 at `drivers.year`) after a 2 px ink rule, weight 650. The Part cell holds the name (regional: "Land rising or sinking here (regional estimate)") and under it an `aria-hidden` bar up to 260 px wide on one shared axis from min(0, every p17) to the largest p83 (total included): a 1 px `--ink-2` zero tick, an 8 px range bar (radius 2) in `--scen-k` of `S0` at 35% (total: `--ink` at 25%), a dot r 4.5 at p50 with a 1.5 px `--surface` ring. Middle `cm(p50)`; range `rngc(p17, p83)` 14 px grey. Under the table: "{drivers.note} The middle estimates add up to about the total, not exactly."
- **Every decade**: h3 "Every decade to {last of p.years}". Sub "{Name} ({S.code}){lc}, compared with {p.baseline.text}." Columns "Year", "Middle estimate", "{rk capitalised}", "{S.outer_kind capitalised}", "Rate, mm a year" (imperial "Rate, in a year", 2 decimals). Cells `cm(p50)`, `rngc(p17, p83)`, `rngc(p05, p95)`, `S.rate.p50` to 1 decimal; null → "no value". The 2050 row `--bg` fill, weight 650. After 2100, a full-width 13 px grey row: "After 2100 the experts used a different set of model runs, so values can jump between 2100 and 2110." Under the table, 15 px ink: `p.caveat`. Under 600 px the table scrolls sideways in its own box (`tabindex=0`, `aria-label` "Every decade to 2150, scrolls sideways"); the page never does.

## 6. "How we calculated this" (changes only)
- Step 4 working, line 2 when R1 shows `now`: "The trend line ends at {val(level_end)} compared with {baseline.text}, in {M(fit.end)}. The card's "Now" is the measured average of the last 12 months instead (step 7)."
- Step 7 "What comes next". Short: "{cm(S.p50@2050)} by 2050 under {S.name} ({S.code}){lc}, from the IPCC", plus " · Check: outside the experts' 2020 range" when `check.inside` is false. It opens by default when `check.inside` is false; otherwise it starts closed.
  - Words: (1) "For the future we use only published expert projections: the IPCC's sea level projections (AR6, 2021) {where}. They use the same 1995–2014 average as the rest of this page, so past and future share one axis." `{where}`: gauge "at the tide gauge {location.name}, {km} km from this one"; regional "for the {location.name}, because there is no AR6 tide gauge close enough. The land motion in it is AR6's regional estimate, and local sinking here may differ". (2) "Under {S.name} ({S.code}){lc}, the experts' middle estimate for 2050 is {cm(p50)}. Their {rk} is {rngc(p17, p83)}, and their {S.outer_kind} is {rngc(p05, p95)}." Low confidence adds: "This version adds ice-sheet changes that are hard to predict, so the experts give no chance for its range." (3) "Scenarios are possible paths for the world's emissions. The experts give no odds for which one will happen. {p.caveat}" (4) "We never stretch the past trend into the future."
  - The working: "Now: the 12 months to {M(now.end)} average {cm(now.value)} compared with {baseline.text}." / "2050, {S.code}: {cm(p50)} − {cm(now.value)} = {more}. Approximate: it takes a 12-month average from a projection." / "2020: the experts' middle estimate is {cm(S0.p50@2020)}; the measured average for 2019 to 2021 is {cm(check.observed_2019_2021)}. We plot the projection as published, so the gap of {cm(|difference|) unsigned} shows on the chart." / Check, inside: "Check: {cm(observed)} is inside the experts' 2020 range for {S0.code} ({S0.outer_kind} {rngc(check.ar6_2020_p05, check.ar6_2020_p95)}), so the record and the projection agree here." Outside (this line gets a 3 px ink left rule): "Check: {cm(observed)} is outside the experts' 2020 range for {S0.code} ({…}). About 1 in 7 tide gauges fall outside, mostly for real reasons such as an earthquake, fast land uplift or a recent regional surge. Read the projection here with extra care." Null: "Check: not possible here. The record has fewer than 24 of the 36 months from 2019 to 2021." / "After 2100 the experts used a different set of model runs, so the table can jump between 2100 and 2110." `now` null: the first two lines become "Now: fewer than 10 of the last 12 months have data, so there is no 12-month average to compare."
  - Links: "IPCC AR6 sea level projections ↗" (`p.source.record_url`) · "{future_link.label} ↗".
- Step 9: short adds "; future from IPCC AR6". List adds "Future: {p.source.name}, {dataset_id}, version {version}, {licence}. Open it ↗", then a closed `details` "How to cite the projections": each `p.source.citation` entry as a 13 px paragraph, then "Acknowledgement: {p.source.acknowledgement}". Then the PR1 CSV button.

## 7. Projection CSV (`#future` button and step 9; built in the browser, no new route)
File `bhoomi-sea-level-{place slug}-ipcc-ar6.csv`, every scenario, values in mm whatever the Units setting, PR1's formula guard and header quoting:
```
# Bhoomi: Sea level projections for {pin.label}
# Source: {p.source.name}
# Dataset: {dataset_id}; version: {version}; licence: {licence}
# Record: {p.source.record_url}
# Location: {location.name} ({location.kind}, {location.km} km from the gauge)[; {location.note}]
# Baseline: {p.baseline.text}; levels in mm as published, not shifted to meet the observations
# Ranges: p17-p83 is the likely range (about 2 in 3 chance) for medium confidence and the 17th to 83rd percentile for low confidence; p05-p95 is the 5th to 95th percentile
# Rates: the experts' own rate of rise for each decade, mm a year
# Cite: {citation[0]}
# Cite: {citation[1]}
# Cite: {citation[2]}
# Acknowledgement: {acknowledgement}
# Built with AI assistance. bhoomi.earth
scenario,name,confidence,year,p05_mm,p17_mm,p50_mm,p83_mm,p95_mm,rate_p50_mm_a_year
```

## 8. States
- Gauge (default): as above. Regional estimate: the sub-line, the flag, R3's extra sentence, the drivers' land label, step 7's `{where}` and the CSV location line.
- No projection (`available` false: Great Lakes, no AR6 location): PR1 exactly; no radios, no `#future`; R3 and step 7 print `p.why`.
- Check outside: the flag under the readout line, step 7 open with its short answer flagged, the ruled check line. Nothing else changes; the projection is still shown. Check null: step 7's null line.
- Record off the 1995–2014 axis (`baseline.projection_axis` false): the place chart is PR1's own chart. `#future` starts with the radios, the readout line (its last sentence becomes "This record has no 1995–2014 average, so we can't say how far that is above today.") and a projection-only chart (x 2020–2100, height 320, no observed marks, no Now dot), then the drivers and the table. R1 is PR1's; R3 drops the more sentence.
- `now` null (a gap in the last 12 months): R1 is PR1's, no Now dot, no more sentence anywhere, step 7's `now` lines. Old record: "Latest" and "in {year}" (§2).
- Low confidence on: dashed median and band edge, percentile names everywhere, the second label line, the y-axis may grow. A null AR6 value: the line and band break; the table says "no value". Sea level falling: signs and "less than today" carry it.
- Loading and error: PR1 (the projection comes in the same answer).

## 9. Tokens (light first; dark in brackets)
- `--scen-1` low #2B9877 (#A6E8CB), `--scen-2` intermediate #5A5FD0 (#B8B4FA), `--scen-3` high #A0307E (#D271CB), `--scen-4` very high #6A0F36 (#E5487C); `--scen-band` .15 (.22). A low-confidence scenario uses its SSP's colour, dashed. Nothing else changes.
- Contrast for lines (graphics need 3:1) on `--surface` #FFFFFF: 3.58, 5.27, 6.52, 12.11 (on `--bg` 3.31, 4.87, 6.03, 11.18). Dark on #181B1E: 12.37, 9.01, 5.74, 4.57. `--scen-1` is under 4.5:1, so scenario colours never colour text; labels are ink and `--ink-2`.
- Colour vision (Machado 2009 simulation, severity 1, CIEDE2000): smallest difference between two scenarios, light: normal 16.7, protan 14.8, deutan 16.2, tritan 14.4; dark: 17.5, 14.6, 9.9, 14.6. Lightness steps one way in every simulation (light 56 → 23 L*; dark 87 → 55), so the order reads without hue. Against the other chart colours the smallest is 4.9 (light: high vs the falling-trend navy, protan) and 7.7 (dark: low vs ink, deutan): they never share an x range (the trend ends with the record; scenarios start in 2020) and every line is named, so this stands. Rising orange and the monthly grey stay clear of all four (at least 12), ink at least 7.7.
- Type and controls: body 16; readout line 17; labels and help 14; on-chart labels 12 to 13; radios 52 px tall, checkbox row 44 px; every border on a control `--control`.

## 10. Checks for QA (1440 and 1920, light first; then dark and 375)
- [ ] The Battery, intermediate: card "+8.0 cm" (the 12 months to October 2026), "+36 cm", "SSP2-4.5. Likely +27 to +46 cm. About 28 cm more than today."; the chart's Now dot and 2050 label say the same; `cm()` equals `readouts.now.text` and `by_2050.text`.
- [ ] Every range on screen is named by its kind: "95% range" for the trend; "likely range (about 2 in 3 chance)" only for medium confidence; percentiles for low confidence and for 5th–95th. No odds for a scenario anywhere.
- [ ] Projection lines start at their 2020 values, unshifted; nothing future is drawn from the observed line or its smoother; the 12-month average stops 6 months before the data.
- [ ] Switching scenarios updates the card, the chart, the readout line, the table and step 7 together, and never moves the y-axis among medium scenarios. Keyboard: Tab into the radios, arrows change them; the checkbox toggles with Space.
- [ ] Every number names its source: records link, IPCC AR6 link (sub-line, `#future`, step 7, step 9, foot), citations and acknowledgement in step 9 and the CSV. "Built with AI assistance" visible; no NASA logos.
- [ ] Regional estimate and check-outside flags appear under the readout line; step 7 opens itself when the check fails.
- [ ] 375 px: radios in a 2 × 2 grid, chart labels names only, `#future` one column, the decade table scrolls in its own box, no page side-scroll.

## 11. Left for later
PR3 brings the same grammar to temperature, hottest day and rain (CMIP6). PR4 restyles the trend line and smoother for every window and redesigns the compare view.
