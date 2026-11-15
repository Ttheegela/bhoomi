# 00 Frame: the general-audience page (build this first, one builder)

Builds on `web/DESIGN.md` (tokens, type, chart, verdict card, tabs, Ask, Use in your AI stay as they are). This file changes only the Explore tab. Files the frame builder touches: `web/index.html`, `web/style.css`, `web/app.js` and five new EMPTY files (section 7). Never `web/ask.js`. `ask.js` still needs the globals `showOnChart`, `tabState`, `writeHash`: keep those names.
North star (the test for every line): a non-expert asks "Is this really changing where I live?" and gets an honest answer in plain words. A step that needs a coordinate, a statistics term or a second read fails.

## 1. Page structure (Explore tab, DOM order = reading order, phone and wide)
```
header (title, "Built with AI assistance")      tabbar (unchanged)
#panel-explore
  #hero            h2#h-explore, p#hero-lead, form#controls (search, #examples, #coords)
  #guide-slot      module 04     (hidden until its module fills it)
  #map-slot        module 01     (hidden until its module fills it)
  #pick            measurement + data source (the existing selects, moved out of the form)
  #saved-slot      module 03     (hidden until filled)
  #answer-wrap
    #empty         frame: shown until the first result
    #answer        (existing section, aria-busy, loading, grey block)
      #answer-bar  frame: p#answer-place + #share-slot (module 03)   [hidden until a result]
      #meaning-slot module 02
      #result.grid (existing: .col-verdict card, #problem, .col-chart)
    #noise-slot    module 05, AFTER #result, inside #answer-wrap (not in .grid)
  #more (How to read this, existing)
footer: AI label, sources list, #privacy-slot (module 03), credits
p#td-live.sr-only[role=status]  (one global polite line, filled by TD.announce)
```
- Every slot is `<section id=".." hidden aria-label="..">` (or `<div>` where noted) and EMPTY in the frame HTML. A module unhides its slot only when it has content. A slot never has padding or margin while hidden or empty (`[hidden]{display:none!important}` already exists).
- `#pick` is `<div id="pick" class="fields pick">` with the two existing fields and `#pick-help`; its labels: "Measurement", "Data source" (words unchanged). Default measurement on first load: Air temperature (works everywhere; sea level fails inland).
- `#empty`: `<div id="empty" class="card quiet"><h2 id="empty-h">Pick a place to see the answer</h2><p>Search for your town, tap the map, or try an example. We show what the public records say, in plain words.</p></div>`. Quiet card: `--surface` fill, 1 px `--line` border, 8 px radius (not the 2 px ink border of an answer). Removed (`hidden`) when a request starts; back when the page has no place (never after the first request).
- `#answer-bar` (only after the first result, hidden while loading the first one): flex row, gap 12, min-height 48. `p#answer-place` (16 px, weight 700, `margin:0`): "Showing: {place label}" for example "Showing: New York, New York, United States" (place label = search label, else the link's `place`, else the trend reply's `place.name`, else "{lat}° N, {lon}° E" with N/S and E/W, 2 decimals). `#share-slot` (div, right-aligned, empty until module 03). Wraps under 360 px.

## 2. Words on screen (frame only)
- h2#h-explore (22/24 px Space Grotesk, weight 700; was 18 px lead): **"Is this really changing where I live?"** Replaces the old question line. Tab title and `<meta name=description>`: "Is this really changing where you live? Search for a place and see what public records say." (og/twitter copy the same).
- `p#hero-lead` (16 px, `--ink-2`; hidden below 600 px with `display:none` to save the phone first screen): "Search for your town or tap the map. We check public NASA and NOAA records and tell you in plain words." (plain text, no logo, no brand mark).
- Search: label "Search for a place"; placeholder "Type a city or town"; secondary link-button on the label row, right: "Use coordinates instead" (existing toggle, `aria-expanded`). Credit: "Place search: Open-Meteo Geocoding API (GeoNames) ↗" (link, shown while suggestions or a "no place" message are shown, 14 px grey).
- `#examples`: legend (sr-only) "Example places", label above the row (14 px grey): "Or try an example". Chips and their order exactly as DESIGN.md section 1 item 6 (New York, Princeton, Delhi, Visakhapatnam, Mumbai, Chennai, London, Seattle); ▲ ▼ ≈ arrows as DESIGN.md section 12. A chip click = `TD.loadPlace({... origin:'example'})` with the chip's default measurement.
- Coordinates (secondary, closed by default): fields "Latitude", "Longitude", "Use my location", "Show trend" exactly as today (messages unchanged).
- Footer sources list gains: "Place names: Open-Meteo Geocoding API (GeoNames) ↗" and, only when the map is on screen, "Map: OpenFreeMap © OpenMapTiles Data from OpenStreetMap ↗" (module 01 adds that second item with `TD.addCredit`; see 3).

## 3. Script interface (names fixed; the frame defines, modules use)
Scripts: classic `<script defer src>`, in the order of section 7, all after `app.js`. All run before `DOMContentLoaded`; the frame fires its first event only on `DOMContentLoaded`, so every module has attached its listeners by then. `app.js` defines one global `window.TD` and no other new global; every module is one IIFE, touches no other module's ids, and prefixes its CSS classes with its name (`map-`, `mean-`, `mem-`, `guide-`, `noise-`).
```
TD.ready                 Promise, resolves with the variables array once /api/variables loaded (never rejects; [] on failure)
TD.variables             array from /api/variables ([] until ready)
TD.state                 getter: copy of { place:{lat,lon,label}|null, variable, source|null, start|null, end|null,
                         status:'idle'|'loading'|'loaded'|'error', series, trend, error:{status,heading}|null }
TD.loadPlace(spec)       spec = { lat, lon, label?, variable?, source?, start?, end?, origin }. Validates (lat -90..90, lon -180..180,
                         variable known), fills controls, writes the link, scrolls (section 5), fires the events below.
                         Returns a Promise that resolves to the load-end detail. Never rejects. Bad input: resolves {ok:false}, fires nothing.
TD.fetchTrend(params)    Promise<{ok,status,body,retryAfter}>: GET /api/trend with params {variable,lat,lon,source?,start?,end?}. Shares the
                         frame's error handling; does NOT touch the page or the events (used by module 05 for windows).
TD.linkFor(state?)       string: absolute share URL (section 4) for the given or current state
TD.announce(text)        puts text in #td-live (cleared then set, so repeats are read)
TD.cleanPlace(s)         string|null: strips control chars and < >, trims, 60 chars max (text only, never HTML)
TD.addCredit(id, text, url?)   adds or replaces one item in the footer list (id = 'map'); text and url are set as textContent/href (https only)
TD.originOf              the list of origin words: 'search','map','saved','recent','guide','example','geo','coords','share-link','undo','window'
```
`origin` is informational (analytics-free); modules use it to avoid echo (for example the map does not re-fly after its own click).
Events, all `CustomEvent` on `document`, `bubbles:false`:
| Event | When | `detail` |
|---|---|---|
| `td:ready` | once, after the catalogue loaded (also when it failed) | `{variables}` |
| `td:place-pick` | a place was chosen by any control, before the request | `{lat,lon,label,variable,source,start,end,origin}` |
| `td:load-start` | a request pair (series and trend) started; the latest request id | `{id,params,place,origin}` |
| `td:load-end` | the latest request finished (stale ones are dropped silently) | `{id,ok,params,place,series,trend,error,origin}`; `trend` carries the module-02 strings in `trend.meaning` when the server sent them; `error` = `{status,heading}` or null |
`params` = `{variable,lat,lon,source?,start?,end?}` exactly as sent. After `td:load-end`, `TD.state.status` is final; a module that loads late reads `TD.state` once and acts as if it had just seen the last event.
Frame listens to nothing from modules. Modules never touch `#result`, `#answer-bar` text, `#pick`, `#controls`, the chart, the tabs or the link; they call `TD.loadPlace` for every action that changes the place.
The frame, not a module, moves focus: after a user-started load it focuses the first of `#meaning-heading` (if module 02 filled it), else the verdict heading (as today); not on first load or a share-link load.

## 4. Link format (hash, no server change)
`#variable=sea_level&lat=40.71&lon=-74.01[&source=psmsl][&start=2016][&end=2025-06][&place=Lower%20Manhattan]` (lat, lon two decimals; `source` only when hand-chosen and not the default; `start`/`end` "YYYY" or "YYYY-MM", valid years 1850 to 2100 and start before end, else dropped; `place` cleaned text, 60 chars max, shown only through `textContent`). Old links keep working. `tab=ask|connect` links unchanged. Opening a place link: runs it (origin 'share-link'), does not scroll, does not focus, hides the first-visit guide for that visit (not remembered). A bad link falls back to the empty start (no automatic New York any more). Hash is rewritten with `replaceState` after every pick (as today, never after "Use my location": coordinates stay private). `TD.linkFor` = `location.origin + location.pathname + '#' + hash`.

## 5. Behaviour the frame owns
- First load without a link: no request. Show `#empty`, the examples, the map (if present). Opening `#variable=..` runs it. (Owner option B: also run New York sea level on first load. Not chosen: it answers a question nobody asked and pushes the map-first idea.)
- Search box: complete spec in section 6.
- After any pick (not for a share link): below 900 px the frame scrolls `#answer-wrap` to the top of the window (8 px gap) once, when the request starts (`scrollIntoView({block:'start'})`, `behavior:'smooth'`, instant under `prefers-reduced-motion`); from 900 px nothing scrolls unless `#answer-wrap` top is off screen (then the same). `scroll-margin-top: 8px` on `#answer-wrap`. A "Search again" link-button (48 px, "Change the place", `href="#h-explore"`, moves focus to `#place`) sits as the last item of `#answer-bar` on phones only (below 900 px).
- Loading: existing text "Looking up the data…" and grey block; `#meaning-slot` shows its own loading state (module 02). Old result stays dimmed (`aria-busy`) while a new request runs, as today.
- Errors, no data, sources disagree: unchanged from DESIGN.md section 4 (the problem card). `#meaning-slot` and `#noise-slot` hide themselves on `td:load-end` with `ok:false`.
- Stale answers: incrementing request id as today; also covers requests started by modules through `TD.loadPlace`.
- Resize: chart re-draws as today; the map and modules react to CSS size only.

## 6. The search box (frame, complete)
Markup (as in the mock): `div#search.search` > `div.search-head` (label#place-label "Search for a place", button#coords-toggle) + `div.combo` > `input#place[type=text][role=combobox][aria-autocomplete=list][aria-expanded=false][aria-controls=place-list][aria-describedby=place-status][autocomplete=off][autocapitalize=off][spellcheck=false][enterkeyhint=search][maxlength=80]` + `ul#place-list[role=listbox][aria-labelledby=place-label][hidden]`; then `p#place-status.help[role=status]`, `p#place-credit.help[hidden]`. Empty `#place-status` takes no space.
- Typing: debounce 350 ms, suggestions from 3 characters (message below 3: "Type at least 3 letters to see suggestions."); Enter searches now from 2 characters ("Type at least 2 letters, then press Enter."). The newest reply wins (sequence counter); replies cached per text for the visit (30 entries).
- Keys: Down/Up open or move (wrap), `aria-activedescendant` follows; Enter on an active option picks it; Enter with none active runs the search now (one result: pick it; several: open the list); Escape closes the list, a second Escape clears the box; Tab closes the list. Blur closes after 120 ms. Options are `li[role=option][aria-selected]`, min 56 px, two lines (name; "admin1, country" 14 px grey); `aria-label` = "name, admin1, country". Pointer down on an option does not blur the box.
- Status words (one `role=status` line): "Looking for places…"; "{n} places found. Use the up and down arrow keys, then Enter." ("1 place found."); no match: `No place found for “{q}”. Check the spelling, or try a bigger town nearby.`; 400/422: "Please type between 2 and 80 characters."; 429: "Too many searches. Please wait {n} seconds and try again." (n from `Retry-After`; "a minute" when missing); 502 or other: "Place search isn't working right now. You can use coordinates instead."; offline: "We can't reach the server. Check your connection and try again."
- A pick calls `TD.loadPlace({lat,lon,label:'name, admin1, country',origin:'search'})` with the current measurement; the box then shows the label; the credit stays hidden after a pick.
- "Use my location" (inside the closed coordinates section): origin 'geo'; the link and the box stay empty (privacy); label "your location".
- Coordinates: typed lat/lon plus "Show trend" = origin 'coords', label empty. Validation text unchanged.

## 7. Module files (names fixed; the frame links and creates them EMPTY, one comment line each)
Order in `index.html`: `<link rel="stylesheet">` for each CSS after `style.css`; scripts after `app.js`, before `connect.js` and `ask.js`.
| Module | Files | Slots it fills | Listens | Calls | Spec |
|---|---|---|---|---|---|
| 01 map | `map.js`, `map.css` | `#map-slot`, footer credit | place-pick, load-end | `TD.loadPlace` (origin 'map'/'undo'), `TD.addCredit` | 01-map.md |
| 02 meaning | `meaning.js`, `meaning.css` | `#meaning-slot` | load-start, load-end | `TD.announce` | 02-meaning.md |
| 03 memory | `memory.js`, `memory.css` | `#saved-slot`, `#share-slot`, `#privacy-slot` | load-end | `TD.loadPlace` ('saved'/'recent'), `TD.linkFor`, `TD.announce` | 03-memory.md |
| 04 guide | `guide.js`, `guide.css` | `#guide-slot`, `#guide-reopen` | ready, load-end | `TD.loadPlace` ('guide') | 04-guide.md |
| 05 noise | `noise.js`, `noise.css` | `#noise-slot` | load-start, load-end | `TD.fetchTrend`, `TD.announce` | 05-noise.md |
Chart label fix (`06-wide-and-labels.md`) edits only `renderChart` and the `.c-*`/`#chart-*` rules: built AFTER the frame, never at the same time as it.
**Every module missing or empty = the page still works**: slots stay hidden, `#empty` shows the start, search, chips, coordinates, measurement, the answer card, chart, table and Ask all run. The frame ships with the five empty pairs and must pass this test (QA runs it).
`#guide-reopen`: `<button id="guide-reopen" class="linkbtn" hidden>Quick start</button>` in the hero's label row (right of "Use coordinates instead" on wide; under the search on phones); module 04 unhides it. Frame CSS: `html[data-guide="open"] #examples{display:none}` (module 04 sets `data-guide="open"` on `<html>` while its card is open; the role chips replace the example chips then).

## 8. Layout (`.wrap` max-width and padding by width; breakpoints 600, 900, 1280, 1536)
Tokens as DESIGN.md plus: `--map-h` map height, `--map-col` map column. 8/16/24/32 spacing. Container: <900: 100%, pad 16 (phone) / 24 (600 to 899); 900 to 1279: 1200 max, pad 24; 1280 to 1535: 1360 max, pad 32; 1536 and up: 1680 max, pad 32. Header and tabbar use the same `.wrap`.
| Width | Columns | `--map-h` | Answer inside |
|---|---|---|---|
| < 600 | 1 | 280 | stacked: meaning, verdict card, chart, noise |
| 600 to 899 | 1 | 360 | stacked, chart full width |
| 900 to 1279 | map col 340 + 32 gap + answer (rest) | 440 | stacked |
| 1280 to 1535 | map col 380 + 32 + answer | 520 | verdict 340 + 24 + chart (rest) |
| 1536 and up | map col 520 + 32 + answer | 600 | verdict 380 + 24 + chart (rest) |
Wide grid (from 900): `#panel-explore` is `display:grid; grid-template-columns: var(--map-col) minmax(0,1fr); column-gap:32px; row-gap:24px; grid-template-rows: auto auto auto auto auto 1fr; grid-template-areas: "hero hero" "guide guide" "map answer" "pick answer" "saved answer" ". answer"`. `#answer-wrap` spans rows 3 to 6 (`grid-area: answer`). If `#map-slot` is hidden the left column holds `#pick` and `#saved-slot`. Left column is NOT sticky (it fits one screen at 1440). Lines of text stay at most 70 ch (`p{max-width:70ch}` already); the verdict card keeps its width; the map and the chart take the extra room; the hero search input is at most 560 px wide.
Phone order is plain DOM order. No fixed or sticky bar anywhere at <900 (nothing covers content).

## 9. First-screen rule (new; the old "sentence 1 ends by 804 px" is retired for Explore)
Measured at 375 x 812, scrollY 0, light and dark equal. Values filled from the mock; see section 10 table.
- **R1 (first load, no link):** the h2 question, the whole search box, and either (first visit) the guide's four role chips with at least 96 px of the map below them, or (guide closed) the whole example row and at least 240 px of the map are inside 812 px. The status line and credit take no space while empty.
- **R2 (after a pick):** the frame has scrolled `#answer-wrap` to the top; the meaning headline, the confidence word and the verdict banner ("▲ Rising", bottom edge) are fully visible by 804 px. If module 02 is missing, the old rule applies from the same scroll position (sentence 1 by 804 px).
- Page never scrolls sideways at 375, 768, 1024, 1280, 1440, 1920 (`documentElement.scrollWidth` = innerWidth).

## 10. Measurements (mock, `web/mock-tools/measure2.js`)
See the table at the end of this file (filled after the mock runs). Targets until then: R1 first visit: search bottom <= 300, map top <= 520; R1 return: map top <= 360; R2: banner bottom <= 804.

## 11. Content policy (whole page; the map adds the details in 01-map.md)
Today (vercel.json, report-only): `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'`. No inline `style` attributes and no `<style>` blocks anywhere (set sizes from script with `el.style.x` only where a module spec allows it; prefer classes). No outside script, font or stylesheet. Only the map widens the policy, and only to `https://tiles.openfreemap.org`.

## 12. Done-check for the frame (QA)
- [ ] All five module files empty: page works at 375 and 1280, no console error, no 404.
- [ ] First load: no request but `/api/variables`; `#empty` visible; R1 holds.
- [ ] Search by keyboard only reaches a result; Escape, Tab, 400, 429, 502, offline, no match words as in section 6.
- [ ] A link `#variable=air_temp&lat=40.35&lon=-74.66&start=2016` shows the 2016 window; `ask.js` "Show on chart" still opens Explore.
- [ ] Wide grid as in section 8 at 900, 1024, 1280, 1440, 1920; no sideways scroll.
- [ ] `TD` events fire in order place-pick, load-start, load-end for example, search, coordinates and share link.

## 13. Built differently from the text above (frame builder's notes)
- Grid (section 8): a seventh row, `"more more"`, holds `#more` ("How to read this") under both columns; without it `#more` would fall into an implicit row in the map column. Row gaps are margins on each item (a hidden slot leaves no gap), not `row-gap`.
- Page title (section 2): `<title>` and the Explore tab title stay "Trend Detective" (the question is the h2); `<meta name=description>`, og and twitter copy use the new sentence.
- `#guide-reopen` sits in the same label row as "Use coordinates instead" at every width; on a narrow phone the two wrap onto a second line under the label rather than moving under the search box.
- Search status for one place is "1 place found." (the whole sentence); "Please wait 1 second" is singular for n = 1.
- A measurement or source change with no place yet only changes the selection (no request); with a place it re-runs it and fires place-pick again with the same origin and label.
- `td:load-start` and `td:load-end` carry `place` as `{lat, lon, label}` (same shape as `TD.state.place`); `label` is "" when the place has no name. If typed coordinates fail validation while a request is running, a `td:load-end` with `ok:false` and `error.status` 422 ends it.
- `TD.state.series` and `.trend` are the reply objects themselves; the rest is a fresh copy.
- Search results with a missing name or a coordinate out of range are dropped before they are listed.
