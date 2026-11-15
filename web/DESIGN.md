# Trend page design (issue #6)

The Explore tab is being rebuilt for a general audience. Its frame (structure, search box, the `window.TD` interface, link format, layout) is specified in `web/design/00-frame.md`; the other parts are in `web/design/` too. Where that folder and this file differ on Explore, `web/design/` wins; the rest of this file still holds.

Build: `web/index.html`, `web/style.css`, `web/app.js`. No build step, no libraries, no CDN, self-hosted web fonts only (Space Grotesk, Inter). Chart is hand-written SVG. Same-origin calls to `/api/...`. No NASA logos or branding; dataset names are plain text.

## 1. Flow and first load
1. Page opens on the empty start (a question, the place search box, the example chips, the "Pick a place to see the answer" card). Only `/api/variables` is fetched, and Air temperature is the selected measurement. A link with a place (`#variable=..&lat=..&lon=..`) runs it at once. One constant at the top of `web/app.js` (`FIRST_LOAD`) can bring back a default place. For a picked place: `/api/series` and `/api/trend` in parallel.
2. User searches for a place by name (`GET /api/places`), picks an example place chip, or (secondary, behind "Use coordinates instead") types lat/lon and presses "Show trend", or presses "Use my location".
3. User may change the measurement (select). Chip click and measurement change run at once. Typed coordinates run on button or Enter.
4. Page shows: verdict, chart, numbers, caveats, how to read it. A student gets the answer from the first card in under a minute.
5. Share state: write `#variable=..&lat=..&lon=..` (2 decimals), plus `source`, `start`, `end` and `place` when they apply (the full format is in `web/design/00-frame.md` section 4), to the URL hash and read it on load. Never write the hash after "Use my location".
6. Presets (chip label, lat, lon, default measurement): New York 40.71 -74.01 sea_level; Princeton, NJ 40.35 -74.66 air_temp; Delhi 28.58 77.21 air_temp_max; Visakhapatnam 17.69 83.22 air_temp; Mumbai 19.08 72.88 air_temp_max; Chennai 13.08 80.27 air_temp; London 51.51 -0.13 air_temp; Seattle 47.61 -122.33 sea_level. An old link to Atlantic City (`#variable=sea_level&lat=39.36&lon=-74.42`) still opens, with no chip pressed; a bad link falls back to the empty start. A chip sets place and its default measurement; the user can change the measurement after.
7. Keep the last good result on screen (dimmed, `aria-busy`) while a new request runs. Ignore stale responses (use an incrementing request id).

## 2. Layout
Source order = reading order (header, question and search, map slot, measurement, answer, how-to-read, ask slot, footer; the Explore frame is in `web/design/00-frame.md`, which wins over the diagram below for Explore). Container width and padding follow the breakpoints 600, 900, 1280 and 1536 px (frame section 8), sections 24 px apart (32 px desktop).
```
PHONE (375)                      DESKTOP (>= 900)
[Title]      [Built with AI]     [Title ........... Built with AI assistance]
Is it really changing here?      [Question line]
[chips: wrap, 2 per row]         [chips ................................... ]
[Lat][Lon]  (2 cols)             [Lat][Lon][Use my location][Measurement][Show]
[Use my location]
[Measurement select]             +-- verdict (360) --+ +-- chart (flex) ------+
[Show trend] (full width)        | OUR ANSWER        | | raw panel            |
[Verdict card]                   | ▲ Rising          | | deseasonalized panel |
[Chart + legend + readout]       | sentences         | | legend, readout      |
[The numbers]                    | source link       | | source, summary      |
[Caveats and notes]              +-------------------+ +----------------------+
[How to read this]               [The numbers (2 col dl)] [Caveats and notes]
[ask slot]                       [How to read this]  [ask slot]  [footer]
[Footer: AI label, sources]
```
- Desktop verdict column is sticky (top 16 px) beside the chart. Below 900 px all stacked.
- Header AI label: bordered text "Built with AI assistance", always visible in the header (not hidden at 375). Footer repeats it with the line "Data come from the sources named next to each number. Only public data."
- Controls: the "Show trend" button lives inside the coordinates section (a closed `<details>`); chips and the measurement select run at once. A chip can carry a small ▲ ▼ ≈ after its label (see the last section). The two help lines ("Good for" and the source) run together in one grey paragraph under the selects.
- Verdict card order: heading, the number row (the big number with its unit, "per decade" under it, and the sparkline on the right), the "our calculation" line, the source link line ("Raw data: {source.name} ↗"), sentence 1, the grey lean line (no clear change only), then the explanatory paragraphs and the p-value. Source links are block-level lines, 48 px tall, never inside a sentence.
- Ask slot: `<section id="ask" hidden aria-label="Ask a question"></section>` after "How to read this". Empty now.

## 3. Words on screen
- Title (h1): "Trend Detective". Question (h2, 22/24 px): "Is this really changing where I live?" (frame section 2).
- Controls: search box "Search for a place" (frame section 6); fieldset legend "Example places" (chips use `aria-pressed`); "Latitude" (help: "-90 to 90"); "Longitude" (help: "-180 to 180"); button "Use my location"; select label "Measurement" (options = catalog `name`; help under it = `good_for` and `resolution`, e.g. "Good for: heat, long-term warming. Covers a ~50 km grid."); select "Data source" appears only if the entry has more than one `sources`; button "Show trend".
- Client validation (inline, `aria-describedby`, no request sent): "Latitude must be a number from -90 to 90." / "Longitude must be a number from -180 to 180."
- Geolocation denied or unavailable: "We couldn't get your location. Type coordinates or pick an example place."
- Verdict card. Label (small caps, 14 px): "Our answer". Headline H2 with shape (shapes are `aria-hidden` inline SVG, word carries meaning): `▲ Rising` / `▼ Falling` / `≈ No clear change`. All three cards are the same size, weight and position; no clear change is not styled as weaker.
  - Terms: `name` = catalog name without trailing parentheses; `place` = `place.name` (or "lat, lon" if empty); years = first 4 chars of `period.start` / `period.end`; `slope`, `lo`, `hi` = `slope_per_decade`, `ci_low`, `ci_high` with sign (use "+" and the minus sign "−"), up to 2 decimals if |x| < 1 else 1 decimal, then `units`.
  - rising: "{name} at {place} is going up: {slope, no sign} per decade, from {y0} to {y1}." Then: "The 95% range is {lo} to {hi} per decade. Even the low end is above zero, so this is a clear rise."
  - falling: "{name} at {place} is going down: {slope, no sign} per decade, from {y0} to {y1}." Then: "The 95% range is {lo} to {hi} per decade. Even the high end is below zero, so this is a clear fall."
  - no_clear_change: "We can't tell {name} at {place} apart from no change, {y0} to {y1}." Then: "The data lean {up|down}: {slope, no sign} per decade. But the 95% range ({lo} to {hi}) {includes zero|is too wide to rule out no change}. That is an answer: over this period, any change is too small or too noisy to separate from normal ups and downs." ("includes zero" if lo <= 0 <= hi, else "is too wide...".) Lean word comes from the sign of the slope.
  - Last line for all: "Source: {source.name}" (link to `source.url`, opens in same tab, text "NASA POWER (MERRA-2)" etc.). If `period` is short, nothing extra.
- Evidence line (all verdicts): "p-value: {p_value}. The p-value says how easily luck alone could produce a trend this strong. Below 0.05 counts as a clear change." Show "p < 0.001" if under 0.001, else 3 decimals. Never write "% chance it's real".
- "The numbers" (dl; plain label, then stats term in grey): "How fast it's changing (Sen's slope)": {slope} per decade. "Range we're 95% sure it falls in (confidence interval)": {lo} to {hi}. "How easily luck explains it (p-value)": {p_value}. "Period": {period.start} to {period.end}. "Months used (n)": {n}. "Seasons removed (deseasonalized)": Yes/No. "Adjusted for neighbouring months (autocorrelation)": Yes/No. "Test": "Mann-Kendall test with Sen's slope" when `method` is `mann_kendall_sen`, else the raw `method`. Caption: "Source: {source.name}" (link).
- "Caveats and notes" (h2): bullet list, `caveats` first then series `notes`, verbatim. Heading is a `<details open>`; if both are empty, show "No extra caveats from the source."
- "How to read this" (h2), four short paragraphs: (a) "Seasons removed: we subtract each calendar month's average, so summer and winter don't hide a slow change." (b) "The shaded fan: the range of slopes the data can support. If a flat line fits inside it, we can't call the change real." (c) "p-value: smaller means harder to explain by luck alone. 0.05 is the usual line for calling a change clear." (d) "This shows whether a measurement changed here. It doesn't say why." Add (e) when `autocorrelation_adjusted` is true: "We adjusted for months that resemble their neighbours; without that the result would look surer than it is." Show when false: "We did not adjust for months that resemble their neighbours, so treat the result as less certain."
- Footer: "Built with AI assistance" and "Data: public datasets, named beside each number."

## 4. States (all replace the verdict + chart area; controls stay usable; use `role="status"` for loading, `role="alert"` for errors)
- Loading: verdict card text "Looking up the data…", chart area a flat grey block (no shimmer; no motion at all if `prefers-reduced-motion`). After 4 s add "Still working. This source can take a few seconds." Button reads "Working…" and is `aria-disabled`.
- 400 (any): heading "We can't answer that for this place." Body = the API `detail`, verbatim. Hint: "Try another place or measurement." Chips stay visible.
- 400 with `variable=sea_level` (no tide gauge within 100 km, or other): after `detail`, add "Tide gauges sit along US coasts." (only while sea level has a single source) plus buttons "Try New York" and "Show air temperature here" (same lat/lon, switches measurement).
- 422: heading "Something in the form isn't right." Body "Check the latitude and longitude and try again."
- 502: heading "The data source isn't answering." Body "That's on their end, not yours. Try again in a minute." Button "Try again" (repeats the same request, then moves focus to the new heading).
- Network failure or other 5xx: heading "We can't reach the server." Body "Check your connection and try again." Button "Try again".
- No data (series empty or every value null): heading "No data for this place." Body "{source.name} has no readings here for this measurement. Try another place or measurement." No chart, no numbers.
- Series ok, trend fails: show the chart and a verdict card holding the error text above with its button.
- Sources disagree: v1 shows one source at a time. If the user switches "Data source" and the verdict changes, nothing special; the new result simply replaces the old one with its own source link. Do not merge sources.
- Move focus to the verdict heading (`tabindex="-1"`) after each completed run triggered by the user, not on first load.

## 5. Chart
Container `figure`, width 100%, SVG `viewBox` scales with it. Two stacked panels sharing one x axis (so raw seasonal swings never flatten the trend):
- Panel A "Raw monthly values" (units on y axis): thin line.
- Panel B "Seasons removed, with trend" (y label "Change from the usual for that month ({units})"): deseasonalized line, trend line, uncertainty fan. Deseasonalized = value − its calendar month's mean over all non-null values.
- Sizes: viewBox width 340 at <= 599 px (panel A 126 tall, B 206), 640 at 600-899 px (A 166, B 246), 720 at >= 900 px (A 156, B 276); height = A + B + a gap of font size + 8 + the axis area (at least 40); each panel header is 3.25 x the font size. Min text in SVG 12 px on screen (scale font with the viewBox).
- Marks (distinct without colour): raw = 1 px solid line, grey `--chart-faint`. Seasons-removed monthly line = faint, 1 px, `--chart-faint`; yearly averages of it (years with at least 6 valid months) = dots in `--ink`. Trend = solid line, about 3.5 px, the verdict colour `--v-bg` (`--ink` with no verdict), drawn over the dots. Fan = flat fill in `--v-bg` at 22% opacity, no outline, plus 1.5 px dotted edges (2 3) so it reads in high contrast mode.
- Trend line: t in decades since first month; intercept = median(deseasonalized − slope_per_decade × t); y = intercept + slope × t. Fan: two lines through the pivot (median t, trend value there) with slopes `ci_low` and `ci_high`, filled between them across the whole x range. The browser draws only; printed numbers come from the API.
- Axes: x ticks by screen spacing: the smallest step from 1, 2, 5, 10, 20, 25, 50 years whose ticks are at least 56 screen px apart (a span of 2 years or more always shows at least two labels); labels "1980", "1990". y: 4 to 5 "nice" ticks, labels with up to 2 decimals, light 1 px grid `--hairline`. Panel B draws a heavier zero line. X axis title: "Year". Y axis in panel A: "{name} ({units})".
- Nulls: break the line (no interpolation, no dots). Say in the legend note: "Gaps in the line are months with no data."
- Legend (HTML, below chart, each item an SVG swatch drawn in the same stroke style plus words): "Raw monthly value" / "Seasons removed" / "Trend line" / "Range of the trend", grouped under "From the dataset" and "Our calculation".
- Readout instead of a floating tooltip (works on touch): a line under the chart, `aria-live="polite"`, empty text "Tap or hover the chart to read a month." On pointer move/tap, snap to the nearest month, draw a 1 px vertical rule, and show "Mar 2004: 24.1 degC raw, 0.3 degC above the usual March." Values come from the series; the difference is the plotted deseasonalized value. Chart `tabindex="0"`; Left/Right move the rule by 1 month, Shift+Left/Right by 12, Home/End jump, Esc clears.
- Text alternative: `role="img"` with `<title>` and `<desc>`; visible caption under the chart: "{name} at {place}, {period.start} to {period.end}. The trend line {rises|falls|stays flat at}, {slope} per decade (range of trends the data support: {lo} to {hi} per decade). Verdict: {rising|falling|no clear change}." ("rises by" / "falls by" / "moves by {slope} per decade, which we can't tell from zero".) The source is a block-level link line directly below the chart.
- `<details>` "Show the data as a table": columns Month, {name} ({units}); one row per `times` entry, empty cell shown as "no data"; `max-height` 320 px scroll, sticky header, `tabindex="0"` on the scroller, caption "Source: {source.name}" (link).

## 6. Tokens
Light: `--bg #FFFFFF`, `--surface #F4F4F4`, `--ink #111111` (18:1), `--ink-2 #4A4A4A` (8.9:1), `--line #767676` (4.5:1, control borders, icons), `--hairline #D6D6D6` (decorative only), `--chart-faint #767676`, `--focus #111111`.
Dark: `--bg #0D0D0D`, `--surface #1A1A1A`, `--ink #F2F2F2`, `--ink-2 #BDBDBD`, `--line #8C8C8C`, `--hairline #333333`, `--chart-faint #8C8C8C`, `--focus #FFFFFF`. Selected via `@media (prefers-color-scheme: dark)`; set `color-scheme: light dark`. SVG uses `currentColor` / the tokens, never hard-coded colours. Verdict card for rising/falling/no clear change: `--surface` fill, 2 px `--ink` border, headline row in the verdict colour with its text token (`--v-bg` / `--v-tx`; `--bg` on `--ink` with no verdict). The data colours are listed in the last section.
Type: Inter for the body, Space Grotesk (`--font-head`) for h1, h2, the banner, the big number and `.chart-head`, with `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` as the fallback; numbers `font-variant-numeric: tabular-nums`. Sizes px (phone/desktop): small 14, body 16, lead 18, h2 22/24, verdict headline 28/32 weight 700, h1 24/28 weight 700. Line height 1.5 body, 1.2 headings. Max line length 70 ch.
Space: 4, 8, 12, 16, 24, 32, 48. Radius: 6 (controls, chips), 8 (cards). Controls min height 44 px; chips 44 px tall, 12 px gap. Borders 1 px (controls), 2 px (verdict card). Focus: 3 px solid `--focus`, offset 2 px, never removed. No gradients. No shadows, except that the selected tab's 3 px underline is drawn as an inset `box-shadow`.

## 7. Accessibility checklist
- [ ] Landmarks: header, main, footer; one h1; headings in order; page `lang="en"`; skip link "Skip to the answer".
- [ ] Every input has a visible label and help via `aria-describedby`; chips are real buttons with `aria-pressed`.
- [ ] Everything works with keyboard only; focus ring visible on every control, the chart and the table scroller.
- [ ] Text contrast >= 4.5:1; borders, icons, chart lines >= 3:1 in light and dark.
- [ ] No meaning by colour alone: verdict = word + shape; chart series differ by stroke style and have a legend.
- [ ] Chart has `role="img"` + title/desc, the visible one-sentence summary, and the data table.
- [ ] Loading and errors announced (`role="status"` / `alert`); focus moves to the result heading after a user run.
- [ ] Reflows at 375 px with no horizontal page scroll (only the table scroller); zoom 200% works; targets >= 44 px.
- [ ] `prefers-reduced-motion`: no animation. Dark mode follows the system.
- [ ] Every number block has "Raw data: {name}" with a working link (error cards: "Source:"); "Built with AI assistance" visible in header and footer.

## 8. Done-check for QA (screenshots at 375 px and 1280 px, light and dark)
- [ ] First load (no link) shows the empty start and makes no data request. Picking New York with Sea level shows a verdict and chart; the verdict names its dataset (from the API) as a link.
- [ ] Visakhapatnam air temperature shows "No clear change" in a card the same size as the others, with the range and p-value in words.
- [ ] Delhi + Sea level shows the 400 `detail` text verbatim plus the two recovery buttons.
- [ ] Forced 502, network failure, empty series and bad latitude each show their exact copy above.
- [ ] Both chart panels, trend line (solid, about 3.5 px), yearly-average dots, fan and legend visible; a null gap is a break, not a line.
- [ ] Readout works by hover, tap and arrow keys. Table opens and scrolls.
- [ ] No hex colour outside the tokens, no external requests, no NASA logo; the AI label shows without scrolling at 375 px.
- [ ] Tab order follows reading order; ask slot is hidden and empty.

## Needs from other lanes
- Geocoding is out of scope; presets plus lat/lon cover it. For custom coordinates `place.name` may be empty; the UI falls back to "lat, lon".
- `/api/variables` should include `sources` and `good_for` per entry as in CONTRACTS (used for the optional source select and help text).
- Nice to have: `/api/trend` including a one-line `summary` so the chart caption and the agent say the same words. Not required; the UI builds the text from fields.

## 9. Review checklist (apply after every UI change)
1. No sample data is shown as real. A demo value is labelled "sample" or not shown. Every number names its source with a link, including numbers inside error cards.
2. What we computed is marked. The verdict, trend line, shaded band, yearly averages and "seasons removed" line carry a grey label: "Trend, range and verdict: our calculation." directly under the big number, then a "Raw data: {source} ↗" link. The legend groups "From the dataset" and "Our calculation".
3. The verdict sentence holds the number and the uncertainty in plain words, for example "rose by about 42.5 mm per decade; the shaded band shows where the true trend likely sits". Never "X% chance it's real" or "95% sure". Never claim more than the data show.
4. Contrast meets WCAG AA in light and dark. Text is at least 4.5:1. Borders, icons and chart lines are at least 3:1. Recompute from the tokens after any token change, and measure muted text on the surface and the verdict banner in both themes.
5. Labels are sentence case, grey, 14 px (12 px minimum), regular weight. No ALL CAPS, no small caps, no letter-spacing.
6. Colour appears only inside the data and always with a legend. Colour is for the data only (banner, trend line and band, year stripes, sparkline); everything else is black, white and grey.
7. At 375 px nothing sticky covers content. Tap targets (chips, buttons, inputs, select, summary, skip link, source links) are at least 48 px. The first-screen rule for the empty start is R1 in `web/design/00-frame.md` section 9; after a pick the answer is scrolled to the top (R2), and the verdict number, range and source are then on screen without further scrolling.
8. The chart has an accessible name that states place, variable, period, verdict, slope and range. Decorative marks are `aria-hidden`. Icon-only controls have a screen-reader name.
9. Chart: x tick labels at least 56 screen px apart; axis titles never touch a tick label; the trend line stays visible on a series of 1,400 points.
10. QA trap: in a hidden or background browser pane, CSS transitions freeze, so screenshots can look stale. While verifying, inject `*{transition:none!important;animation-duration:0s!important}` and remove it afterwards.

## 10. Decisions
### Decided by Tarun
- In sentences, the verb gives the direction and the number has no sign: "fell by about 0.25 °C per decade". The big number and the range keep their signs.
- A visible "Built with AI assistance" label.
- Every number names its data source with a link.
- No NASA logos or branding.
- Only public data.
- Tokens: black, white, greys, plus the data colours of the refresh; no gradients.
- Structure: tabs Explore, Ask, Use in your AI (his words, 2026-11-14, picked from visual options).
- Theme: follow the device setting (light or dark); no theme switch.
- Ask box: a chat thread with follow-up questions.
- Eight example places: New York, Princeton, Delhi, Visakhapatnam, Mumbai, Chennai, London and Seattle (his words, 2026-11-14: "instead of atlantic city add princeton,new york,vizag,delhi,bombay,chennai", plus London and Seattle).
- New York replaces Atlantic City as the example (follows from "instead of atlantic city"). That it no longer loads on its own is the agent's choice (see "Chosen by the agent").
- Tab bar on desktop: left-aligned.
- Grey labels stay at 14 px. This overrides the 'about 12 px' label rule from the Konam checklist.
- Use in your AI: framed as 'use Trend Detective in your own AI agent'; example agents (Claude, GitHub Copilot) named in one line only when their docs confirm remote MCP support; detailed tabs only for apps with verified steps; one 'Any other AI agent' tab; no ChatGPT tab.
- MCP page: both, tabs per AI app with steps, then a config block for developers.
- Map first, with a place search box; coordinates and "Use my location" are the secondary way (his approval of the general-audience redesign, 2026-11-14). The Explore tab starts from a question, a search box and a map; the answer is built from small parts. The design lives in `web/design/` (start with `00-frame.md`).
- Visual choices (his words, 2026-11-14: "go with the leans": 1B 2C 3C 4B 5C, picked from screenshots):
  1. Tabs versus chips (1B): the three main tabs are plain text on a thin line; the selected tab is bold with a 3 px underline and no fill. Example-place chips keep their filled pressed state. The app picker on "Use in your AI" follows the same tab style (his addition).
  2. Answer card (2C): same order as before; "Trend, range and verdict: our calculation." sits directly under the big number (the Mann-Kendall wording stays only in the Method row of the facts list); the source link has a grey "Raw data:" label.
  3. The AI's message on Ask (3C): no edge line; a quiet box in the page's surface tone. The "Written by an AI model" label and the AI badge stay.
  4. Code and settings blocks (4B): no wrapping; each block scrolls sideways inside itself with a visible scroll bar; a short hint line shows only when text is cut off ("Swipe sideways to see the whole line."). Copy still copies the whole text.
  5. Chart (5C): the source link sits under the chart headline; the legend follows the chart closely (6 px margin); the "No change" label goes to the end of the dashed line the trend line is clear of; the legend lines say "(upper chart)" and "(lower chart)".

### Chosen by the agent (swappable)
- The Explore frame (`web/design/00-frame.md`): no data request on first load (the old New York sea level start is one line: `FIRST_LOAD` at the top of `web/app.js`); Air temperature is the first selected measurement (it works everywhere; sea level fails inland); breakpoints 600, 900, 1280 and 1536 px with container widths 100% / 1200 / 1360 / 1680; search timings (350 ms wait, suggestions from 3 letters, Enter from 2, 30 cached searches, list closes 120 ms after the box loses focus); five empty module slots; the `window.TD` interface and its four events; the answer is scrolled to the top on phones after a pick.
- Single-page flow: question and search box, then the map slot, measurement, verdict and chart (it was: place chips, then measurement, then verdict and chart).
- Hand-written SVG chart and no JS libraries or CDN fonts.
- Two stacked chart panels (raw, then seasons removed with trend and band).
- Tab icon `web/favicon.svg`: a rising line, then a dot, white on a black rounded square (plain presentation attributes, no embedded style, so a strict Content-Security-Policy cannot block it; reads on light and dark tabs); no text, no NASA imagery. Link previews use title and description only (no og:image).
- Wrong address: `web/404.html` ("We can't find that page.", a link to the start page, the AI label), served with status 404 for any path outside /api/ and /mcp.
- Trend line drawn solid, about 3.5 px, over a faint 1 px monthly line, with yearly averages as dots (from Sairam's PR #28).
- Shaded band as a 22% fill in the verdict colour with dotted edges.
- Verdict shown as a word plus a shape (▲ ▼ ≈), in a headline bar in the verdict colour.
- "No clear change" styled at the same size and weight as the other verdicts.
- Readout line under the chart instead of a tooltip.
- Keyboard chart control: arrows, shift-arrows, Home, End and Esc.
- Chart x ticks chosen by screen spacing (at least 56 px).
- Chip order (New York, Princeton, Delhi, Visakhapatnam, Mumbai, Chennai, London, Seattle); which measurement each chip opens (table in section 1 item 6); Delhi at 28.58 (matches the eval case and the Safdarjung station). A chip is pressed only while both its place and its measurement are shown.
- Phone first screen (375 x 812; the numbers in this bullet describe the old page, which opened on an answer; the empty start now follows R1 in the frame): example places in one sideways-scrolling row (5 px padding so the focus ring shows, a chip cut off at the right edge); measurement and data source side by side in one row (equal columns, so "NASA POWER" and its arrow fit at 360 px) with short names in the closed selects; "Good for" and the source help as one merged grey line, full width under that row; header top padding 8 px; section gaps and tab bar margins 8 px; the grey "no clear change" lean line under sentence 1. Expected ends at 375 x 812: heading 561.0, source link 660.6, sentence 1 780.6 at worst (see the round 2 report; the last section has the newer values).
- Both the measurement and source lists use short names at every width, open or closed ("Air temperature", "Hottest day", "Rain", "Sea level"; "NASA POWER", "ERA5", "GHCN-Daily", "CO-OPS", "PSMSL"); the full names appear in the answer. Below 360 px the two selects stack.
- Desktop: measurement select (400 px) and source select (220 px) side by side, left-aligned; the merged help line under them.
- The source control shows the result's source; only a hand-chosen non-default source is written to the link or sent.
- Coordinates and "Use my location" in a closed section opened by the "Use coordinates instead" button next to the search label.
- Hash state `#variable=..&lat=..&lon=..` (two decimals).
- Breakpoints 600, 900, 1280 and 1536 px; container and padding as in `web/design/00-frame.md` section 8 (it was 960 px and 16/24 px).
- Type scale: 14 small, 16 body, 18 lead, 22/24 h2, 28/32 verdict.
- Greys: light #111 / #4A4A4A / #767676 / #F4F4F4; dark #F2F2F2 / #BDBDBD / #8C8C8C / #1A1A1A.
- Tap targets at least 48 px.
- Focus ring 3 px, offset 2 px.
- p-value wording: "Below 0.05 counts as a clear change."
- Confidence interval described as the range of trends the data support.
- Seasons removed by subtracting each calendar month's mean.
- Temperature shown as °C.
- Error and empty-state copy.
- Loading placeholder is a flat grey block with no motion.
- Show trend button inside the coordinates section.
- Source links as their own 48 px lines.
- Tabs live in one page; URL hash `tab=ask|connect` (Explore keeps the key-less hash), push for tab changes, replace for app sub-tabs; details in `web/DESIGN-ask-mcp.md`.
- Chat thread kept in memory only, rendered in page flow with no inner scroll box; "Show on chart" opens Explore.
- Ask sends no `history` until the backend history PR lands.
- Per-app MCP steps taken from each app's official docs (checked 2026-11-14).
- Period-first sentence 1 and a separate wording when the range misses zero but p is 0.05 or more.
- The settings-file picker on "Use in your AI" uses the same tab style as the app picker (same kind of control; his 1B addition named only the app picker).
- One source label, "Raw data:", on every link that names where numbers came from (answer card, chart, table, Ask answers), in grey before the name. This reconciles 2C ("Raw data:") with 5C (whose patch said "Data:"). Error cards keep "Source:". The facts list keeps its row label "Source" (a table row label, not a link label). The plain-text line "Raw values: {source}." in the chart caption and table caption is unchanged.
- One merged help line (`#pick-help`) follows both fields (markup order: field, field, help). Under 360 px the selects stack and the help line comes last; from 360 px the two fields share a row and the help line runs full width below. (Earlier versions had one help line per select.)
- The footer lists a source only when the catalog (`/api/variables`) lists it. The ERA5 entry carries Open-Meteo's attribution: "Weather data by Open-Meteo.com" (link), "ERA5 reanalysis", "CC BY 4.0" (link to creativecommons.org).
- A 429 from the data routes shows the API's own sentence in the problem card with "Try again".
- The grey lean line ("The data lean up, but ...") now sits after sentence 1 at every width (it did so only on phones before).
- When the catalog fails to load, the footer lists every known source except `grace`, which is known only through the catalog.
- The "No change" label is drawn last, over the lines and the band, with a 4 px halo in the page background colour (`.c-halo`, used only by that label), so data never shows through it.
- The footer's ERA5 entry is one list item that flows as one line of text: Open-Meteo link, ", ERA5 reanalysis, ", CC BY 4.0 link.
- Below 360 px a lone last item in the app picker takes the full row.
- The sideways-scroll hint on the code blocks says "Scroll sideways to see the whole line." on non-touch screens ("Swipe sideways..." on touch screens, from his option 4B).
- The server address field on "Use in your AI" stays on one line.

## 11. Trend picture and year stripes
- The picture (`web/scene.js`) shows direction only, never size. Rising and falling both move the level by one small fixed distance from the middle; "no clear change" rests inside a shaded band. The caption says so: "Picture shows direction only, not size." (for "no clear change" a second sentence follows about the band).
- Motion plays once (the level travels, the stripes fade in) and never loops. "Play again" replays it; it is not shown for "no clear change" (nothing travels) or when the reader asks for reduced motion.
- The picture never formats a number. Slope and range are the strings the answer card prints (`fmtVal`), passed in by `app.js` and used unchanged. Years are the first four characters of `period.start` and `period.end`, never taken from the yearly averages.
- The stripes take the verdict's five-step ramp (`--v-1` to `--v-5`, low year to high year); the trend picture `#scene` stays ink. The stripe shading lives in one function (`shade` in `scene.js`).
- Labels are 14 px, regular weight. The picture is drawn 268 units wide and shown at most that wide, so its text is 14 px. The head row never stacks: the title (up to two lines) on the left, "Play again" on the right, centred vertically at every width, to keep the block short.
- No drawing that suggests more than the data say: no skyline, no well (the satellites measure all water stored on land, not groundwater in a well).
- Where each sits: the picture is in the answer card after the p-value line and before the facts table (`#scene`); the year stripes are under the chart and its legend (`#year-stripes` in `#chart-wrap`).
- Year stripes: one stripe per year, seasons removed, with the first and last year of the period, a key ("lower year", "higher year"; true in light and dark mode), a caption, the tag "our calculation" and the source link. The stripes are hidden from screen readers; the key and caption are real text.
- Both mounts are optional: if either fails to draw, it is hidden and the answer card and chart are untouched.
- Desktop: the left column is sticky; checked, left as on `main` (a column taller than the window un-sticks at the end of its row). No inner scroll area.
- Known limit: below about 360 px wide the picture and its labels scale down together (about 12 px at 320 px); the words that carry the answer are in the card, not in the picture.

## 12. Colour for the data, fonts, number row, sparkline, chip arrows
Colour is for the data only. Words and shapes (▲ ▼ ≈) still carry every meaning.

### Tokens
Per verdict: `--up-*` rising, `--dn-*` falling, `--nc-*` no clear change. `-bg` is the banner fill, the trend line, the band and the sparkline line; `-tx` is the banner text; `-1` to `-5` are the stripe ramp, low year to high year. `--font-head` is the Space Grotesk stack. The existing tokens are unchanged.
| Token | Light | Dark |
|---|---|---|
| `--up-bg` / `--up-tx` | #D4620A / #111111 | #F2A04E / #111111 |
| `--up-1` to `--up-5` | #F2D0B5 #EBB48B #E39960 #DC7D35 #D4620A | #644526 #885C30 #AB723A #CF8944 #F2A04E |
| `--dn-bg` / `--dn-tx` | #1B3F73 / #FFFFFF | #2F6FC4 / #FFFFFF |
| `--dn-1` to `--dn-5` | #BBC5D5 #93A4BC #6B82A4 #43618C #1B3F73 | #314863 #3F6086 #4E78AA #5C90CD #6BA8F0 |
| `--nc-bg` / `--nc-tx` | #6B6B6B / #FFFFFF | #BDBDBD / #111111 |
| `--nc-1` to `--nc-5` | #D3D3D3 #B9B9B9 #9F9F9F #858585 #6B6B6B | #505050 #6B6B6B #868686 #A2A2A2 #BDBDBD |
The dark falling ramp ends lighter (#6BA8F0) than its banner (#2F6FC4) on purpose: a ramp running down from the banner colour cannot keep a visible step between stops. The no-hex rule still holds: these values live only in the token table, and print (below) uses the keywords `white` and `black`.

### The verdict marker
`renderVerdict` sets `data-verdict` to `rising`, `falling` or `none` (`no_clear_change`) on `#verdict-card` and `#chart-wrap`. CSS maps it to `--v-bg --v-tx --v-1` to `--v-5`. `show()` removes both attributes before each answer, so with no `data-verdict` (a failed trend) everything falls back to ink.

### What takes colour
- Takes the verdict colour: the banner (`.verdict-head`, `--v-bg` with `--v-tx`; the 2 px ink card border stays), the trend line, its band and dotted edges and their legend swatches (`.s-trend`, `.s-fan` at 22%, `.s-edge`), the year stripes with their key, and the sparkline.
- Stays ink or grey: the raw monthly line, the seasons-removed line, the yearly dots, the no-change line, axes, grid, the trend picture `#scene`, the chips, and everything else.

### Number row and first phone screen
- One merged help line: `<p id="pick-help" class="help span2"><span id="variable-help"></span> <span id="source-help"></span></p>`. The two ids stay (now spans), `aria-describedby` is unchanged. It saves 21 px.
- Phone only (up to 599 px): `.card-label` padding 8 16 4 (already on `main`), `.verdict-head` padding 8 16, `.card-body` padding-top 4, and `.numrow` has no bottom margin. The paddings added by this change save 12 px; the measured table is unchanged. Desktop: `.numrow` margin-bottom 4, other paddings unchanged.
- `.numrow` (flex, wrap, gap 8 12) holds `#verdict-big` and `#spark`. The number is 48 px Space Grotesk 700, line-height 1.1; its unit (the text after the first whitespace of `fmtVal`) is 24 px beside it; "per decade" is 16 px grey on its own line, line-height 1.3. If the number is wider than about 190 px the row wraps and the sparkline takes its own 40 px row.
- Measured at 375 x 812, scrolled to the top, on the old page that opened on an answer (the frame now scrolls the answer to the top after a pick: R2 in `web/design/00-frame.md`): bottoms of heading / source line / sentence 1, in px. The limit is 804.
| Case | Before | After |
|---|---|---|
| New York sea level (CO-OPS) | 561 / 681.6 / 777.6 | 532 / 678.6 / 774.6 |
| Delhi hottest day (POWER) | 561 / 681.6 / 777.6 | 532 / 678.6 / 774.6 |
| Delhi hottest day (weather station) | 540 / 660.6 / 780.6 | 532 / 678.6 / 798.6 |
| Visakhapatnam air temperature (POWER) | 561 / 681.6 / 801.6 | 532 / 678.6 / 798.6 |
| Mumbai sea level (PSMSL) | 561 / 681.6 / 777.6 | 532 / 678.6 / 774.6 |
Worst case 798.6, so 5.4 px spare. Light and dark are identical. Page width stays 375 at 375 and 1280 at 1280. Do not change a size, padding, margin, line-height or wording above sentence 1 without measuring again.

### Sparkline
- `renderSpark(t, series, word)`, mount `#spark` in `.numrow`; 96 x 40 px, no axes, no text, no numbers.
- It uses only the chart's helpers (`deseasonalize`, `yearlyAverages`, `trendIntercept`, `median`, `monthIndex`) and the same trend and band lines (`slope_per_decade`, `ci_low`, `ci_high`); x runs from the first to the last month, y from the lowest to the highest of the yearly averages and the band ends, 4 px inside the box. No statistics of its own.
- Layers: band (`.sp-band`, `--v-bg` at 22%), yearly averages as a 1 px `--chart-faint` line, trend line 3 px `--v-bg`.
- Text alternative: `role="img"`, `aria-label` "Small picture of the trend, {rising | falling | no clear change}: the line and its range from {first year} to {last year}. Shows direction only, no scale."
- Fewer than 3 yearly averages, or any exception: `#spark` is hidden and the answer card is untouched. `show()` also hides it at the start of every answer (as it does `#year-stripes`), so a failed request never leaves an old sparkline.

### Chip arrows
- An arrow is the verdict of an answer loaded in this visit, for one place and the current measurement and source. The key is measurement id + "|" + source id (empty when the source select is hidden).
- Set: after `renderVerdict` succeeds, `noteGlyph(trend, params)` finds the preset within 0.005 degrees of the answer's place (typed coordinates that match no preset set nothing); if the key differs from the stored one, all arrows are dropped first. Never set when the trend failed or there is no data.
- Cleared, all at once: the Measurement select changes; the Data source select changes; a chip is clicked whose measurement or source differs from the stored key.
- Look: `<span class="chip-g" aria-hidden="true">` with the ▲ ▼ ≈ shape, 14 x 14, after the label, 6 px left margin, `currentColor` (also in the pressed chip). Chips stay monochrome and 48 px tall.
- Screen readers: the chip gets `aria-label` "{place}, {rising | falling | no clear change}" (for example "Princeton, NJ, rising"), removed with the arrow. `aria-pressed` is untouched.

### Fonts
Self-hosted in `web/fonts/` with their SIL Open Font License texts: Inter (body and the rest) and Space Grotesk (`h1`, `h2`, the banner, the number and its unit, `.chart-head`). `@font-face` in `web/style.css`, `font-display: swap`, variable weight. No `@import`, no link tag, no CDN; `font-src` falls under `default-src 'self'`. Space Grotesk's "1" has a flag ("31.8").

### Stripes and browsers without `color-mix()`
`shade(k)` returns `color-mix(in srgb, var(--v-{j+2}) {u}%, var(--v-{j+1}))` with `j = min(3, floor(4k))`, `u = round(100(4k-j))`, set as `style.fill`, so it follows the theme with no redraw; the key swatches use k = 0 and k = 1. If `CSS.supports('color', 'color-mix(in srgb, red, blue)')` is false, `paint` in `scene.js` draws the stripes and key swatches in `--ink` at `fill-opacity` `0.06 + 0.88 k` instead, so the year order never flattens into one colour.

### Print and forced colours
- Print: banner `white` with `black` text and a 2 px black rule; trend, band and sparkline `black`. Print is the one place fixed black and white are used (the tokens follow the screen's theme; paper is always white). Stripes keep their colours; the ramps change in lightness one way, so they print as ordered greys.
- Forced colours: banner `Canvas` / `CanvasText` with a 2 px `CanvasText` rule; trend, band and sparkline `CanvasText`; `.sc-stripes` and `.sc-sw` use `forced-color-adjust: none` so the year order survives. Words, shapes, legend and key text are unchanged.

### Checks the palette passed (73 checks, 0 failed)
- Banner text against banner at least 4.5: 4.99, 10.47, 5.33 light; 8.91, 5.01, 10.05 dark.
- Banner against card at least 3: lowest 3.44. Line against page at least 3: lowest 3.78.
- Rising against falling banner under deuteranopia and protanopia (Machado 2009, linear RGB): dE 89 to 113 and dL* 18 to 33 (rule: dE at least 20 and dL* at least 15).
- Every ramp: L* changes one way, steps at least 6.4, in normal vision, in both simulations and in greyscale.
- Lowest stripe against the dark page #0D0D0D: 2.24 / 2.07 / 2.41 (rising / falling / no change); against white in light mode: 1.45 / 1.74 / 1.50.
