# 09 Rework: the shell and the module contract

Supersedes the Explore / Ask / Use in your AI tabs and the layout notes in `08-layout.md`. The look is the owner-approved mock (light, desktop first); this file says what the structure is and what the modules may rely on.

## Structure (`web/index.html`)
- Top bar (sticky, 64 px): brand, nav (Sea level, Air temperature, Hottest days, Rain, Water storage), Settings link, "Built with AI assistance". Below 900 px it wraps and the nav scrolls sideways.
- Routes (hash): `#sea-level`, `#air-temperature`, `#hottest-days`, `#rain`, `#water-storage`, `#settings`; default `#sea-level`. Old `#variable=…&lat=…&lon=…` links open that window and pin the place (the name from such a link is never used in a sentence, only shown). `tab=connect` opens Settings. An unusable link shows "That link is out of date." in `#status-line`.
- One measurement window (`#win-measure`) serves all five: sidebar (search, pinned places, hint, "Measured by", Units, "Look ahead to") and main (page head, `#rec` card beside `#map-slot`, `.card.ch > #compare-chart-slot`, `.card.tb > #compare-table-slot`, foot line with `#footer-sources`).
- `#win-settings > #settings-slot` is the whole Settings body. `#chat-slot` is the last child of `<body>`.
- `<dialog id="how-dialog">` holds the detail (monthly chart, exact rate and range, p-value paragraph, facts, caveats, chart help, year stripes, Real or noise, data table) for the selected place. It opens from the card's "How we calculated this" button.

## Scripts and styles
`prefs.js` (head, blocking), then deferred: `scene.js`, `app.js`, `map.js`, `compare.js`, `settings.js`, `noise.js`, `chat.js`. Styles: `style.css`, `map.css`, `compare.css`, `settings.css`, `noise.css`, `chat.css`. A missing file is a 404 and nothing else.

## `window.TDPrefs` (prefs.js)
`get()` returns `{theme: 'light'|'dark'|'device', units: 'metric'|'imperial', lookAhead: 2035|2050|2075, maps: {<variable id>: {base: 'light'|'detailed', labels, stations}}}`. `set(patch)` merges (`maps` per window), stores `td.prefs.v1`, fires `td:prefs`. It sets `<html data-theme="light|dark">` before first paint. Light is the default.

## `window.TD` (app.js)
`ready`, `variables`, `windows`, `window`, `pins()`, `select(key)`, `addPlace({label, lat, lon})` (Promise `{ok, reason}`), `removePlace(key)`, `fmt.rate|outlook|value|years|unit`, `context()`, `announce`, `cleanPlace`, `addCredit`. Events on `document`: `td:ready`, `td:route {window}`, `td:pins {window, pins, selected}`, `td:prefs`.
- Pins (max 6 per window) live in localStorage `td.pins.v2`; each has a stable `slot` 0 to 5 (colour `--p1` to `--p6`); the selected place is drawn in `--ink`. At most 3 pins are requested at once. Results are kept per window, source and place, so switching windows does not re-request.
- A pin's `status` is `loading`, `ok` or `error`; `trend` and `series` are the API replies, read-only.
- On Settings `pins()` is `[]` and `td:pins` fires once with no pins.

## Built differently from the contract
- `TD.select(key, {focus: false})` skips moving focus to the card's heading (the default is to move it).
- Real or noise needs the old page's events. The shell keeps a small compatibility layer: `TD.state` describes the selected place (as before), `TD.fetchTrend(params)` and `TD.loadPlace(spec)` still exist (`loadPlace` pins the place and closes the dialog), and a `td:load-end` is fired when the dialog opens (not when data lands), so the section fetches only when someone asks. A `td:load-start` fires when it closes.
- The sidebar's "Measured by" is a segmented control built from the catalogue's sources; changing it requests every pin again.
- Without `guidance` in the reply the card shows `meaning.headline`, `meaning.comparison`, `meaning.confidence` and the verdict word, with no risk chip and no recommendation box; the sidebar line is `meaning.comparison`.
- Extra tokens (not in the contract): `--advice-ink`, `--advice-mod-bg`, `--advice-mod-line`, `--advice-low-bg`, `--advice-low-line`, `--hairline` (same as `--line`). The legacy `--s1` to `--s7` spacing tokens stay for the module stylesheets (`--s3` is gone).
- The grid class is `.shell` (the 404 page still uses `.wrap`).
