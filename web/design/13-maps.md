# 13 Maps (rework PR5): tide gauges coloured by their rate, a water-storage trend layer, the map that stops following

Build brief: `docs/REWORK-SPEC.md` PR5 and D8. Builds on `01-map.md`, `07-gauges.md` and `10-foundation.md` section 4; this file wins where they differ. Files: `web/map.js`, `web/map.css`, the tokens in `web/style.css`. Data: `web/data/gauge-trends.json` and `web/data/grace-trends.json`, built offline (data and stats lanes).
The owner sees pictures before code: static mocks at 1440, 1920, 375 and dark, outside the repo, every value labelled "sample". Pending decisions are in section 10; the recommended option is drawn everywhere else.

## 1. The base map: greys set in the style, not by a CSS filter
- Today `map.css` greys the canvas with `filter: grayscale(1)` (dark: `grayscale(1) invert(1) brightness(.9)`). A filter greys the data too, so coloured dots are impossible. Delete both filter rules.
- Instead, on every `style.load`, walk the style's layers and rewrite every paint property ending in `-color` (strings, `stops` and expressions alike). For each colour: g = its luminance as an sRGB grey (linear Y), alpha kept.
  - Light: fills, lines, background `255 − (255 − g) × 0.6`; text and halo `g`. Measured: land #F8F8F8, water #DDDDDD.
  - Dark: fills, lines, background `16 + (255 − g) × 0.45`; text `40 + (255 − g) × 0.75`; halo `255 − g`. Measured: land #151515, water #292929.
- A theme change reloads the style (`setStyle(url, {diff:false})`) and greys it again, then re-reads the data tokens (section 4).
- The detailed base map (Settings) is greyed the same way while a colour layer shows (Sea level with "Measuring stations" on, and Water storage); elsewhere it stays as it is.

## 2. Tide gauges coloured by their own rate (Sea level window)
**Which dots.** Read `gauge-trends.json` once, the first time Sea level is wanted (it replaces `/api/gauges` for the map). A dot is drawn only if its rate exists (`years` ≥ 20, `slope` not null). Its colour and hover must be the record a click opens, so with "Measured by: NOAA tide gauges" (the default) draw every CO-OPS gauge plus each PSMSL gauge with no CO-OPS station within 100 km (the server's own fall-through rule); with "Global gauges (PSMSL)" draw PSMSL gauges only.
**Look.** One circle layer, drawn above the base map's labels and below the DOM pins.
- Colour by `slope` (mm a year) in six steps, split exactly at 0, from one stops array: `[{to:−3,tok:'--dv-dn2'},{to:0,tok:'--dv-dn1'},{to:2,tok:'--dv-up1'},{to:4,tok:'--dv-up2'},{to:7,tok:'--dv-up3'},{to:∞,tok:'--dv-up4'}]`. `map.js` builds both the MapLibre `step` expression and the key's swatches from this one array (token values read with `getComputedStyle`). A value equal to a break takes the class above it.
- Clear rise or fall: filled dot, 1 px ring in `--dv-ring` (separates neighbours). No clear change: hollow ring, 2 px `--dv-nc`, transparent inside, same outer size.
- Radius by zoom (px, linear): 1 → 2.5, 3 → 3.5, 5 → 5, 8 → 6.5, 11 → 7. Short record (20 to 29 years): × 0.6. A ring's radius is 1 px less, so its outer edge matches.
- Draw order (`circle-sort-key`): rings first, then by size of the rate, so the fastest risers sit on top.
- Opacity 1 at every zoom (the old 0.65 world-zoom texture is gone; the colours need full strength). Fade in and out 200 ms (0 under reduced motion), as today.
**Hover** (hover devices only, from zoom 2; `.map-tip`, `aria-hidden`, max 34 ch, wraps, 8 × 10 px padding, 14 px):
```
{name}                                                       (600)
{Rising|Falling|No clear change}: {±x.x} mm a year, 95% range {±lo} to {±hi}[, which includes no change].
{start}–{end} · {years} years of records[ (short record)] · {NOAA CO-OPS|PSMSL}      (grey)
Click for the full answer.                                                           (grey)
```
Numbers use the card's own formatter (signs, true minus, 1 decimal; inches with the Units setting), so the hover equals the card's "Rate" readout.
**Click.** From zoom 2 (was 4): a click within 14 px of a dot (24 px on coarse pointers, a 48 px target) snaps to it and opens its answer, exactly as `07-gauges.md` section 2 (pin, label, Undo). Below zoom 2 a click pins the point.

## 3. The key under the sea-level map (`.map-key` replaces `.map-legend`; real text, 14 px, `--ink-2` unless said)
1. `--ink`: "How fast the sea is rising or falling at each tide gauge, relative to the land"
2. Six swatches in a row (equal widths, 14 px tall, 2 px gaps, max 420 px), `aria-hidden`; labels at the breaks "−3", "0" (ink, 600, with a 2 px ink tick), "+2", "+4", "+7"; under them "Falling" (left), "mm a year" (middle), "Rising" (right). Inches: the break labels convert to 2 decimals and the unit reads "in a year".
3. [grey ring] "No clear change"   [small dot] "Smaller dot: short record, 20 to 29 years"
4. Pointer: "Point at a dot to read its rate. Click it to open that gauge’s answer." Touch: "Tap a dot to open that gauge’s answer."
5. `--ink`, the text summary of the map, updated on `moveend` (not live-announced): "In view: {n} gauges. {r} rising, {f} falling, {c} no clear change. Fastest rise: {name}, {±x.x} mm a year." No rising gauge: drop the last sentence. None in view: "No gauges with 20 or more years of records in view. Zoom out or move the map."
6. "Rates: our calculation from {NOAA CO-OPS and PSMSL | PSMSL} records, each gauge's whole record, so the years differ. Relative to the land: where the land sinks, the sea rises faster. Gauges with under 20 years are not shown. Records to {data_through}."
- A visually hidden line carries the scale in words: "Colours: blue for falling (darker: 3 mm a year or more), orange to wine for rising, darker for faster: 0 to 2, 2 to 4, 4 to 7, 7 or more mm a year. A grey ring means no clear change."
- Credits: the attribution control and footer credit say "Gauge records: {source name}" with the source's link (was "Gauge locations:").

## 4. Water stored on land (Water storage window): the GRACE trend layer
**Data.** `grace-trends.json`, read once when Water storage is first shown. Always on in that window (no Settings switch).
**Blocks.** One fill layer: each mascon a block centred on its point, 1° tall, `area ÷ (111.32² × cos lat)` degrees wide, both × 1.04 so no hairline seams show. Insert it below the base map's boundaries and labels, then add a copy of the base map's water layer above it, so coasts cut the blocks.
- Colour by `slope` (cm of water a year): `[{to:−2,'--dv-dn3'},{to:−1,'--dv-dn2'},{to:0,'--dv-dn1'},{to:1,'--dv-up1'},{to:2,'--dv-up2'},{to:∞,'--dv-up3'}]`, opaque. Less water is blue, more water orange: the place chart's falling and rising colours (decision 3).
- No clear change: a flat pale block `--dv-ncfill`, no lean shown (follows decision 2).
**Hover** (from zoom 2, same `.map-tip`):
```
Near {lat}° N, {lon}° E                                      (600; S and W as needed, 1 decimal)
{Rising|Falling|No clear change}: {±x.x} cm of water a year, 95% range {±lo} to {±hi}[, which includes no change].
{Month YYYY} to {Month YYYY} · averaged over about 300 km · GRACE                  (grey)
Click for the full answer.                                                         (grey)
```
**Click** pins the clicked point, as today (it reads the same block).
**Key** (same parts as section 3):
1. "Change in water stored on land, in cm of water a year"
2. Six swatches; labels "−2", "−1", "0", "+1", "+2"; ends "Less water", "cm a year", "More water".
3. [pale block] "No clear change"
4. Pointer: "Point at a block to read it. Click it to open the answer for that spot." Touch: "Tap a block to open the answer for that spot."
5. `--ink`, weighted by block area: "In view, by area: {a}% losing water, {b}% gaining, {c}% no clear change."
6. "Each block is the satellites' average over about 300 km: read regions, not towns. A pale block is not proof of no change, and even with no real change anywhere, about 1 block in 20 would look clear by chance."
7. "Rates: our calculation from NASA GSFC GRACE and GRACE-FO mascons, {Month YYYY} to {Month YYYY}. Levels on this tab are compared with the provider's 2004–2009 average. Greenland, Antarctica and the Gulf of Alaska glaciers are left out."
- The page head says "an average over about 400 km" today; it changes to "about 300 km" so the page says one number (data lane to confirm, section 11).

## 5. Tokens (style.css; light, then dark) and the checks they passed
| Token | Light | Dark | Use |
|---|---|---|---|
| `--dv-dn3` `--dv-dn2` `--dv-dn1` | #003F72 #005D9A #047CB3 | #A8DBFE #71BBEF #3897D9 | falling / less water, strongest first |
| `--dv-up1` `--dv-up2` `--dv-up3` `--dv-up4` | #BF5A12 #B4371B #991629 #701232 | #D86D3C #EC8F41 #F8B457 #FDDC8F | rising / more water, weakest first |
| `--dv-nc` | #6B6B6B | #BDBDBD | no-clear-change ring |
| `--dv-ring` | #FFFFFF | #151515 | 1 px ring round filled dots |
| `--dv-ncfill` | #CFCFCB | #3A3A3A | pale no-clear-change block |
- Light: stronger is darker; dark: stronger is lighter, so every class stays readable on its map.
- Every fill against the greyed map, lowest of land and water: light 3.30 (`--dv-up1` on water) to 10.86; dark 4.28 to 13.75. Grey ring: 3.92 light, 7.74 dark. Swatches on the page: light ≥ 4.14, dark ≥ 5.56. All at least 3:1. The pale no-clear-change block is meant to recede (1.4:1 on light land); the key names it.
- Colour vision (Machado 2009, severity 1): within each side L* runs one way in normal, protan, deutan and tritan vision; smallest L* step 6.6; smallest difference between neighbouring classes ΔE2000 6.7 (tritan, light), 6.8 (deutan, dark); the two classes at 0 differ by ΔE 47 or more; the grey ring differs from every class by ΔE 15.5 or more. Shape (ring against dot) carries "no clear change" without colour.
- Text: key and hover use `--ink` and `--ink-2` on `--bg` (6.4:1 and up). Swatches use `forced-color-adjust: none`.

## 6. States
- File loading, failed, bad JSON or empty: no dots or blocks, no key, no message; the map and pins work as today. One more try at the next switch to the window.
- "Measuring stations" off (Settings): no dots, no key. Air temperature, Hottest days, Rain: no layer, no key (unchanged).
- Nothing in view: the in-view lines in sections 3 and 4.
- Sources disagree: a dot's rate is from the build (`Records to {data_through}`); a live card with newer months can differ in the last digit. Both print their years. CO-OPS and PSMSL at one spot never show two dots (section 2 rule).
- Dark theme: section 1 and the dark tokens. Reduced motion: no fades, no fly. Map failed: as `01-map.md`.

## 7. Phone (375) and keyboard
- The key sits under the map in page flow; nothing sticky is added; the scale shrinks to the column, labels wrap. Touch: hit radius 24 px; no hover; a tap opens the answer.
- Dots and blocks stay decoration (canvas `aria-hidden`); the key, the hidden scale line and the in-view line are real text, so the map has a text summary. Keyboard and screen-reader users get every rate through search, as today.
- The map group's label becomes "Map of your pinned places and the trend at each tide gauge (or water-storage block). The lines under the map sum up what is in view." "Built with AI assistance" stays in the header.

## 8. Fix: the map stops following the chosen place
- Cause (confirmed in the vendored MapLibre): `flyTo({padding})` leaves its padding on the map, and the next `fitBounds({padding})` subtracts the stored padding plus its own. At 1440 the map is 458 px wide; 2 × (40 + 190) = 460 px, so MapLibre warns "Map cannot fit within canvas" and does not move. It happens after any place with no pin within 1,000 km (Mumbai, Jakarta).
- How it must behave:
  1. No move leaves padding behind: every move starts from zero padding, so the view never depends on earlier picks.
  2. Room for the selected tag scales with the frame: right `min(190, 30% of width)`, other sides `min(40, 10%)`; under 420 px wide, 30 on every side.
  3. If a fit still cannot be made, centre on the selected place at zoom 5. Never keep the old view.
- Check at 1440, 1920 and 375: New York → Mumbai → Jakarta → Lower Manhattan → Delhi. The map centres on each; the console has no "Map cannot fit within canvas".

## 9. The personas, in their words (what QA should see)
- Investor, Sea level: "Jakarta": the map centres on Jakarta; pointing at its dot gives the card's rate. Two zoom-outs show Asia; dark red to wine dots stand out at Bangkok, Manila, Semarang, and the in-view line names the fastest. "Then Mumbai": the map flies there (section 8); Mumbai is pale orange, Okha a grey ring. Next: the card's recommendation, or pin both and compare.
- Builder: "Lower Manhattan": The Battery's dot is under the pin; its hover equals the card; Sandy Hook and Bergen Point are a step darker. Next: the card's 'Where to look next' links.
- Planner, Water storage: "Delhi": the blocks round Delhi are dark blue, as the card says ▼ Falling; the hover equals the card; the key says read regions, not towns. Next: "How we calculated this", or Princeton (pale: no clear change).

## 10. Decisions for the owner: decided by Tarun, 2026-11-22: A, A, A, A

His words: "for the map lets go with A,A,A,A".
- Gauge colours: six steps split at 0.
- No clear change: grey hollow ring; pale grey blocks on water storage.
- Water colours: as the card, blue for less water and orange for more. He picked this over B.
- The water layer sits on the Water storage tab's own map.

Two follow-ons:
- **Facts, not advice** (contract, 2026-11-22): §9's "Next: the card's flood-level advice" now reads "Next: the card's 'Where to look next' links". No hover or key text gives advice.
- **Footprint:** the map's caveat says "about 400 km", the same as the page head (`grace-trends.json` `footprint_km` 444, the point answer's 4° box), not 300 km.

The options as they were offered:
1. **Gauge colours.** A (recommended): six steps split at 0 (`d1-a-six-steps`, `01`, `06`, `09`). B: four steps, one blue (`d1-b-four-steps`). C: a smooth scale (`d1-c-smooth`; breaks "no gradients", and the hover and colour can disagree slightly).
2. **"No clear change".** A (recommended): grey hollow ring; water storage pale grey blocks (`d2-a-grey-ring`). B: ring in the colour it leans (`d2-b-lean-ring`). C: faded dot (`d2-c-faded-dot`; under 3:1 on purpose).
3. **Water-storage colours.** A (recommended): blue for less water, orange for more, as the place chart (`d3-a-same-as-card`). B: brown for less, blue for more; the place chart's water colours would change to match (`d3-b-brown-and-blue`).
4. **Where the water layer lives.** A (recommended): on the Water storage tab's own map, caveats in its key (`d4-a-on-the-tab-map`, `05`, `07`, `10`). B: its own world-map card under the answer (`d4-b-own-card`).

## 11. Chosen by the agent (swappable), left out, needs and risks
- Chosen: the breaks (−3, 0, 2, 4, 7 mm; ±1, ±2 cm) and token values; the grey conversion factors; sizes, rings, 24 px touch radius, zoom 2 for hover and snap; draw order by rate; hiding gauges under 20 years; the in-view line and its "Fastest rise"; hover and key words; the key under the map, not over it; the water layer always on; the detailed base map greyed under a colour layer; GRACE blocks under labels with water above.
- Left out: a histogram and stats row under the map (the in-view line says the shares in one sentence; no persona needs a distribution); numbers drawn on the map; clustering; a "fastest gauges" list (the line names the fastest); a reset-view button (a pick re-centres); a globe or equal-area projection (shares are by area, so numbers stay right); a Settings switch for the water layer; the world warming grid and "conditions now" (spec: after the release).
- Needs, data and stats lanes: `gauge-trends.json` lists every gauge in both lists with `id`, `lat`, `lon` (`slope`, `lo`, `hi`, `verdict` null under 20 years), plus `data_through` and each source's name and URL; rates from the same code as the point answer. `grace-trends.json` adds `lo`, `hi`, `lat`, `lon`, `area` per mascon, plus start and end months, source name and URL, and the reference period. Confirm 300 km against the page head's 400 km.
- Risks: (1) whole-record rates mix periods: a gauge that starts in 1984 looks faster partly because the sea rises faster now; the key says so and the hover shows the years. (2) The style walk may miss a colour a future OpenFreeMap style adds; QA looks for any hue in the base map. (3) A pin on top of a gauge (Lower Manhattan) must not block the gauge's hover; check the map still gets `mousemove` over the pin. (4) Tritan and deutan users see neighbouring classes close (ΔE 6.7); the hover gives the number. (5) Mercator makes northern blocks look bigger than they are. (6) Outside PR5 but against the owner's checks: the sidebar's ALL-CAPS labels, and the sticky top bar at 375.
