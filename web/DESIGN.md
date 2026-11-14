# Trend page design (issue #6)

Build: `web/index.html`, `web/style.css`, `web/app.js`. No build step, no libraries, no CDN, no web fonts. Chart is hand-written SVG. Same-origin calls to `/api/...`. No NASA logos or branding; dataset names are plain text.

## 1. Flow and first load
1. Page opens already showing a real answer: New York (40.71, -74.01), Sea level, source from the API. Fetch `/api/variables`, then `/api/series` and `/api/trend` in parallel.
2. User picks an example place chip, or types lat/lon and presses "Show trend", or presses "Use my location".
3. User may change the measurement (select). Chip click and measurement change run at once. Typed coordinates run on button or Enter.
4. Page shows: verdict, chart, numbers, caveats, how to read it. A student gets the answer from the first card in under a minute.
5. Optional share state: write `#variable=..&lat=..&lon=..` (2 decimals) to the URL hash and read it on load. Never write the hash after "Use my location".
6. Presets (chip label, lat, lon, default measurement): New York 40.71 -74.01 sea_level; Princeton, NJ 40.35 -74.66 air_temp; Delhi 28.58 77.21 air_temp_max; Visakhapatnam 17.69 83.22 air_temp; Mumbai 19.08 72.88 air_temp_max; Chennai 13.08 80.27 air_temp; London 51.51 -0.13 air_temp; Seattle 47.61 -122.33 sea_level. An old link to Atlantic City (`#variable=sea_level&lat=39.36&lon=-74.42`) still opens, with no chip pressed; a bad link falls back to New York. A chip sets place and its default measurement; the user can change the measurement after.
7. Keep the last good result on screen (dimmed, `aria-busy`) while a new request runs. Ignore stale responses (use an incrementing request id).

## 2. Layout
Source order = reading order (header, controls, verdict, chart, numbers, notes, how-to-read, ask slot, footer). Container max 960 px, side padding 16 px (phone) / 24 px (desktop), sections 24 px apart (32 px desktop).
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
- Controls: the "Show trend" button lives inside the coordinates section (a closed `<details>`); chips and the measurement select run at once.
- Verdict card order: heading, the source link line ("Data: {source.name} ↗"), sentence 1, the "our calculation" line, then the explanatory paragraphs and the p-value. Source links are block-level lines, 48 px tall, never inside a sentence.
- Ask slot: `<section id="ask" hidden aria-label="Ask a question"></section>` after "How to read this". Empty now.

## 3. Words on screen
- Title (h1): "Trend Detective". Question (p, 18 px): "Is it really changing here? Pick a place and a measurement."
- Controls: fieldset legend "Example places" (chips use `aria-pressed`); "Latitude" (help: "-90 to 90"); "Longitude" (help: "-180 to 180"); button "Use my location"; select label "Measurement" (options = catalog `name`; help under it = `good_for` and `resolution`, e.g. "Good for: heat, long-term warming. Covers a ~50 km grid."); select "Data source" appears only if the entry has more than one `sources`; button "Show trend".
- Client validation (inline, `aria-describedby`, no request sent): "Latitude must be a number from -90 to 90." / "Longitude must be a number from -180 to 180."
- Geolocation denied or unavailable: "We couldn't get your location. Type coordinates or pick an example place."
- Verdict card. Label (small caps, 14 px): "Our answer". Headline H2 with shape (shapes are `aria-hidden` inline SVG, word carries meaning): `▲ Rising` / `▼ Falling` / `≈ No clear change`. All three cards are the same size, weight and position; no clear change is not styled as weaker.
  - Terms: `name` = catalog name without trailing parentheses; `place` = `place.name` (or "lat, lon" if empty); years = first 4 chars of `period.start` / `period.end`; `slope`, `lo`, `hi` = `slope_per_decade`, `ci_low`, `ci_high` with sign (use "+" and the minus sign "−"), up to 2 decimals if |x| < 1 else 1 decimal, then `units`.
  - rising: "{name} at {place} is going up: {slope} per decade, from {y0} to {y1}." Then: "The 95% range is {lo} to {hi} per decade. Even the low end is above zero, so this is a clear rise."
  - falling: "{name} at {place} is going down: {slope} per decade, from {y0} to {y1}." Then: "The 95% range is {lo} to {hi} per decade. Even the high end is below zero, so this is a clear fall."
  - no_clear_change: "We can't tell {name} at {place} apart from no change, {y0} to {y1}." Then: "The data lean {up|down}: {slope} per decade. But the 95% range ({lo} to {hi}) {includes zero|is too wide to rule out no change}. That is an answer: over this period, any change is too small or too noisy to separate from normal ups and downs." ("includes zero" if lo <= 0 <= hi, else "is too wide...".) Lean word comes from the sign of the slope.
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
- Marks (distinct without colour): raw = 1 px solid line, grey `--chart-faint`. Seasons-removed monthly line = faint, 1 px, `--chart-faint`; yearly averages of it (years with at least 6 valid months) = dots in `--ink`. Trend = solid line, about 3.5 px, `--ink`, drawn over the dots. Fan = flat fill `--ink` at 22% opacity, no outline, plus 1.5 px dotted edges (2 3) so it reads in high contrast mode.
- Trend line: t in decades since first month; intercept = median(deseasonalized − slope_per_decade × t); y = intercept + slope × t. Fan: two lines through the pivot (median t, trend value there) with slopes `ci_low` and `ci_high`, filled between them across the whole x range. The browser draws only; printed numbers come from the API.
- Axes: x ticks by screen spacing: the smallest step from 1, 2, 5, 10, 20, 25, 50 years whose ticks are at least 56 screen px apart (a span of 2 years or more always shows at least two labels); labels "1980", "1990". y: 4 to 5 "nice" ticks, labels with up to 2 decimals, light 1 px grid `--hairline`. Panel B draws a heavier zero line. X axis title: "Year". Y axis in panel A: "{name} ({units})".
- Nulls: break the line (no interpolation, no dots). Say in the legend note: "Gaps in the line are months with no data."
- Legend (HTML, below chart, each item an SVG swatch drawn in the same stroke style plus words): "Raw monthly value" / "Seasons removed" / "Trend line" / "Range of the trend", grouped under "From the dataset" and "Our calculation".
- Readout instead of a floating tooltip (works on touch): a line under the chart, `aria-live="polite"`, empty text "Tap or hover the chart to read a month." On pointer move/tap, snap to the nearest month, draw a 1 px vertical rule, and show "Mar 2004: 24.1 degC raw, 0.3 degC above the usual March." Values come from the series; the difference is the plotted deseasonalized value. Chart `tabindex="0"`; Left/Right move the rule by 1 month, Shift+Left/Right by 12, Home/End jump, Esc clears.
- Text alternative: `role="img"` with `<title>` and `<desc>`; visible caption under the chart: "{name} at {place}, {period.start} to {period.end}. The trend line {rises|falls|stays flat at}, {slope} per decade (range of trends the data support: {lo} to {hi} per decade). Verdict: {rising|falling|no clear change}." ("rises by" / "falls by" / "moves by {slope} per decade, which we can't tell from zero".) The source is a block-level link line directly below the chart.
- `<details>` "Show the data as a table": columns Month, {name} ({units}); one row per `times` entry, empty cell shown as "no data"; `max-height` 320 px scroll, sticky header, `tabindex="0"` on the scroller, caption "Source: {source.name}" (link).

## 6. Tokens
Light: `--bg #FFFFFF`, `--surface #F4F4F4`, `--ink #111111` (18:1), `--ink-2 #4A4A4A` (8.9:1), `--line #767676` (4.5:1, control borders, icons), `--hairline #D6D6D6` (decorative only), `--chart-faint #767676`, `--focus #111111`.
Dark: `--bg #0D0D0D`, `--surface #1A1A1A`, `--ink #F2F2F2`, `--ink-2 #BDBDBD`, `--line #8C8C8C`, `--hairline #333333`, `--chart-faint #8C8C8C`, `--focus #FFFFFF`. Selected via `@media (prefers-color-scheme: dark)`; set `color-scheme: light dark`. SVG uses `currentColor` / the tokens, never hard-coded colours. Verdict card for rising/falling/no clear change: `--surface` fill, 2 px `--ink` border, headline row inverted (`--bg` text on `--ink`).
Type: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`; numbers `font-variant-numeric: tabular-nums`. Sizes px (phone/desktop): small 14, body 16, lead 18, h2 22/24, verdict headline 28/32 weight 700, h1 24/28 weight 700. Line height 1.5 body, 1.2 headings. Max line length 70 ch.
Space: 4, 8, 12, 16, 24, 32, 48. Radius: 6 (controls, chips), 8 (cards). Controls min height 44 px; chips 44 px tall, 12 px gap. Borders 1 px (controls), 2 px (verdict card). Focus: 3 px solid `--focus`, offset 2 px, never removed. No gradients, no shadows.

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
- [ ] Every number block has "Source: {name}" with a working link; "Built with AI assistance" visible in header and footer.

## 8. Done-check for QA (screenshots at 375 px and 1280 px, light and dark)
- [ ] First load shows New York sea level with a verdict and chart, no empty form. Verdict names its dataset (from the API) as a link.
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
2. What we computed is marked. The verdict, trend line, shaded band, yearly averages and "seasons removed" line carry a grey label: "Trend, range and verdict: our calculation (Mann-Kendall test, Sen's slope)" beside a "Data: {source} ↗" link. The legend groups "From the dataset" and "Our calculation".
3. The verdict sentence holds the number and the uncertainty in plain words, for example "about +42.5 mm per decade; the shaded band shows where the true trend likely sits". Never "X% chance it's real" or "95% sure". Never claim more than the data show.
4. Contrast meets WCAG AA in light and dark. Text is at least 4.5:1. Borders, icons and chart lines are at least 3:1. Recompute from the tokens after any token change, and measure muted text on the surface and the inverted verdict header in both themes.
5. Labels are sentence case, grey, 14 px (12 px minimum), regular weight. No ALL CAPS, no small caps, no letter-spacing.
6. Colour appears only inside the data and always with a legend. Today there is none; everything is monochrome.
7. At 375 px nothing sticky covers content. Tap targets (chips, buttons, inputs, select, summary, skip link, source links) are at least 48 px. The verdict number, range and source are on screen without scrolling on a first load.
8. The chart has an accessible name that states place, variable, period, verdict, slope and range. Decorative marks are `aria-hidden`. Icon-only controls have a screen-reader name.
9. Chart: x tick labels at least 56 screen px apart; axis titles never touch a tick label; the trend line stays visible on a series of 1,400 points.
10. QA trap: in a hidden or background browser pane, CSS transitions freeze, so screenshots can look stale. While verifying, inject `*{transition:none!important;animation-duration:0s!important}` and remove it afterwards.

## 10. Decisions
### Decided by Tarun
- A visible "Built with AI assistance" label.
- Every number names its data source with a link.
- No NASA logos or branding.
- Only public data.
- Monochrome tokens (black, white, greys; no gradients).
- Structure: tabs Explore, Ask, Use in your AI (his words, 2026-11-14, picked from visual options).
- Theme: follow the device setting (light or dark); no theme switch.
- Ask box: a chat thread with follow-up questions.
- Eight example places: New York, Princeton, Delhi, Visakhapatnam, Mumbai, Chennai, London and Seattle (his words, 2026-11-14: "instead of atlantic city add princeton,new york,vizag,delhi,bombay,chennai", plus London and Seattle).
- First load shows New York sea level instead of Atlantic City (follows from "instead of atlantic city").
- Tab bar on desktop: left-aligned.
- Grey labels stay at 14 px. This overrides the 'about 12 px' label rule from the Konam checklist.
- Use in your AI: framed as 'use Trend Detective in your own AI agent'; example agents (Claude, ChatGPT, GitHub Copilot) named in one line only when their docs confirm remote MCP support; detailed tabs only for apps with verified steps; one 'Any other AI agent' tab; no ChatGPT tab.
- MCP page: both, tabs per AI app with steps, then a config block for developers.

### Chosen by the agent (swappable)
- Single-page flow: place chips, then measurement, then verdict and chart.
- Hand-written SVG chart and no JS libraries or web fonts.
- Two stacked chart panels (raw, then seasons removed with trend and band).
- Trend line drawn solid, about 3.5 px, over a faint 1 px monthly line, with yearly averages as dots (from Sairam's PR #28).
- Shaded band as a 22% ink fill with dotted edges.
- Verdict shown as a word plus a shape (▲ ▼ ≈), in an inverted headline bar.
- "No clear change" styled at the same size and weight as the other verdicts.
- Readout line under the chart instead of a tooltip.
- Keyboard chart control: arrows, shift-arrows, Home, End and Esc.
- Chart x ticks chosen by screen spacing (at least 56 px).
- Chip order (New York, Princeton, Delhi, Visakhapatnam, Mumbai, Chennai, London, Seattle); which measurement each chip opens (table in section 1 item 6); Delhi at 28.58 (matches the eval case and the Safdarjung station). A chip is pressed only while both its place and its measurement are shown.
- Phone first screen (375 x 812): example places in one sideways-scrolling row (5 px padding so the focus ring shows, a chip cut off at the right edge); measurement and data source side by side in one row (equal columns, so "NASA POWER" and its arrow fit at 360 px) with short names in the closed selects; "Good for" and the source help line as full-width grey lines under that row; header top padding 8 px; section gaps and tab bar margins 8 px; the grey "no clear change" lean line under sentence 1. Expected ends at 375 x 812: heading 561.0, source link 660.6, sentence 1 780.6 at worst (see the round 2 report).
- Both the measurement and source lists use short names at every width, open or closed ("Air temperature", "Hottest day", "Precipitation", "Sea level"; "NASA POWER", "ERA5", "GHCN-Daily", "CO-OPS", "PSMSL"); the full names appear in the answer. Below 360 px the two selects stack.
- Desktop: measurement select (400 px) and source select (220 px) side by side, left-aligned; help lines under them.
- The source control shows the result's source; only a hand-chosen non-default source is written to the link or sent.
- Coordinates in a closed "Type coordinates or use my location" section.
- Hash state `#variable=..&lat=..&lon=..` (two decimals).
- Breakpoints 600 and 900 px; 960 px container; 16/24 px side padding.
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
