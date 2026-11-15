# 07 Tide gauge dots on the map (builder writes `web/design/07-gauges.md` from this; edits only `web/map.js`, `web/map.css`)

Builds on `web/design/01-map.md` (map as built). Dots say where tide gauges are. They never change what a tap means except as in section 2.

## Needs from the frame
Nothing required. The module reads the measurement by listening to `change` on `#variable` (read only; `#variable.value` after `td:ready`) because `td:place-pick` does not fire when the measurement changes with no place chosen. If the frame later adds a `td:variable-change` event, switch to it. `TD.addCredit` and `TD.loadPlace` already exist.

## 1. When the dots show
Only while the measurement is `sea_level`. Reason: dots mean nothing for rain or heat; the farmer and the student get today's clean map.
- Switching to sea level (select, guide, example chip, saved place, link): show. Switching away: hide. Layer `circle-opacity` fades 200 ms (0 ms under `prefers-reduced-motion`), then `visibility:none`.
- The list is fetched once, the first time sea level is wanted (not on page load: the route is slow on a cold start). Cached in memory for the visit. `GET /api/gauges`, 30 s abort. One GeoJSON source `gauges`, one circle layer `gauges-dots`, added after the map's `load` (if the list arrives first, add it on `load`).
- Gauges at the same spot (same lat and lon to 3 decimals, in both lists) become one dot. Dots have no colour or shape difference by source (nothing the visitor can act on).

## 2. What a tap does
- Dots visible and zoom at least 4: a tap within 14 px of a dot (nearest one, by `queryRenderedFeatures` on a 28 x 28 px box) snaps to that gauge: pin at the gauge's own position, `prev` remembered exactly as for a plain tap, then `TD.loadPlace({lat: gauge.lat, lon: gauge.lon, label: <gauge name>, origin: 'map'})`. No `variable` (the current sea level stays). Label: the route's `name`; if it has no lowercase letter, convert to Title Case; `TD.cleanPlace` limits it to 60 characters.
- Dots hidden, or zoom under 4, or no dot within 14 px: unchanged: pick the exact tapped point, label "Pinned spot (...)".
- Status after a snap: "Pinned the tide gauge at {name}." The server decides which gauge answers; the answer card already names it.
- Undo works as today (one step, restores the previous place; the pin goes back). The snapped pick is just another map pick.
- Below zoom 4 dots are a texture only (they are 2 to 4 px); the user zooms in with the buttons or a pinch and taps.

## 3. Looks (canvas paint; the canvas already has a CSS filter)
The tile canvas is greyscale in light and `grayscale(1) invert(1) brightness(.9)` in dark. Draw the dots ONCE in a fixed dark fill with a white ring: the dark-mode filter turns them into light dots with a dark ring, so no second style and no theme code.
- `circle-color` `#111111` (map paint literal: a canvas paint cannot read CSS tokens; the only hex values this module adds), `circle-stroke-color` `#ffffff`, `circle-stroke-width` 1.
- `circle-radius` by zoom (px): 0.3 → 1.5, 3 → 2.5, 4 → 4, 6 → 5, 11 → 6 (linear interpolation). `circle-opacity` 0.9 from zoom 4, 0.65 below it, `circle-stroke-opacity` same. At world zoom about 2,000 dots stay a light texture, not a blanket.
- Contrast: dot against positron land about 17:1 and water about 11:1 in light; in dark after the filter about 13:1 (both over 3:1). The pin is a DOM marker above the canvas, 20 px with a 3 px ring, so it is never confused with a dot (dots are at most 12 px across).
- Pointer, hover-capable device only (`(hover: hover)`): over a dot at zoom 4 or more the cursor is `pointer` (set with `canvas.style.cursor`, allowed) and a small label shows the gauge name: `maplibregl.Popup` with class `map-tip`, no close button, offset 10, `aria-hidden="true"`, 14 px `--ink` on `--bg`, 1 px `--line` border, 6 px radius, 4 x 8 px padding, no arrow, no shadow, one line, ellipsis at 28 ch. Touch devices: no label (a tap picks).

## 4. The words
- Legend line (14 px `--ink-2`, `p.map-legend`, `aria-hidden="true"`, between `.map-row` and `.map-credit`, only while dots are visible): a 10 px dot icon (inline SVG `aria-hidden`, drawn like the canvas dot: `--ink` fill, `--bg` ring) then "Tide gauge. Zoom in and tap one. A gauge with only a few years of readings cannot give a clear answer."
- First status line while dots are visible and no place is picked: "Tap the map to pick a place, or search above." (unchanged; the legend carries the dot explanation).
- Credits: for each source in the route's `sources` that has at least one gauge in the list: a link in `.map-credit`, text "Gauge locations: {source.name}", `href` its `url` (https only, 48 px tall, wraps) and `TD.addCredit('gauges-' + id, 'Gauge locations: ' + name, url)`. Names come from the route verbatim. If only one list arrives, only its credit shows. The in-map links show only while dots show; the footer line from `addCredit` stays (it is a true source line).

## 5. Loading and failure
Show nothing while loading and nothing on failure (no text, no spinner, no error). Network error, non-200, bad JSON, empty list: no dots, no legend, no credit, map exactly as today. Try again at most once more, the next time sea level is selected. One list only: draw it. A dot with a missing or non-numeric lat or lon is skipped. More than 5,000 features: use the first 5,000 (a guard, not an expected case).

## 6. Accessibility
Dots are decorative: the canvas is already `aria-hidden`, the label and legend are `aria-hidden`, nothing announces them, and no dot is focusable. Keyboard and screen-reader users reach the same result through the search box (a sea-level search already finds the nearest gauge on the server). The only spoken text is the existing `role="status"` line after a snap pick. Meaning is never colour: the dot is one shape, ink on tile; there is no colour code.

## 7. Phone (375 px, map 280 px high)
Dots show from the first view as a faint texture and are tappable from zoom 4: at 280 px a world view with 2 px dots cannot be tapped accurately, so the legend line says "Zoom in and tap one" and the plain tap keeps working at every zoom.

## The builder must not
- add a dependency, an outside host, a tile layer or clustering; change the policy; fetch gauges on page load or per tap; fetch while the measurement is not sea level.
- colour dots by source or record; write any text, number or "years" figure on the map; say "record length" or "RLR"; claim a gauge will give an answer.
- snap when dots are hidden or below zoom 4; change the `TD.loadPlace` call except `label` and the lat and lon; skip `prev` for a snap (Undo must work).
- use inline `style` attributes or `<style>` blocks (CSSOM cursor only); give dots tab stops, ARIA roles or announcements.
- touch `web/app.js`, `web/index.html`, `web/style.css`, `web/ask.js`.

## Check in a browser
- [ ] Air temperature selected: no dots, no legend, no `/api/gauges` request. Select Sea level: dots fade in, one request; back to Air temperature: dots fade out; again: no second request.
- [ ] Dark and light: dots visible, dark-on-light and light-on-dark, ring visible; the pin never looks like a dot.
- [ ] Zoom 5 on New York: tap a dot: pin on the gauge, label shown on hover, status line as above, answer loads; Undo returns to the previous place and pin.
- [ ] Zoom 1: tap near a dot: exact tapped point (no snap).
- [ ] Block `/api/gauges` (offline or 502) and delay it 20 s: map and picks work, nothing extra shown; a gauge in both lists shows one dot and both credits.
- [ ] 375 px: no sideways scroll; legend wraps; credits wrap; screen reader reads no dot text.

## Built differently
- Where the measurement is read: `change` on `#variable`, `TD.ready`, and the `variable` in `td:place-pick` (the frame sets the select by script, which fires no `change`, so a guide, chip, saved place or link pick is caught by the pick event). Only a switch to or from sea level counts, so a repeated sea-level pick never asks again.
- The tap and the hover use one function (`nearest`): it queries a 28 x 28 px box, then takes the dot with the smallest screen distance of at most 14 px, using the gauge's own coordinates from the validated list (not the tile geometry) and its world copy nearest the pointer.
- A gauge whose `url` does not start with `https://` is shown as plain text, not a link.
- A list that arrives empty or without a valid gauge counts as a failure (retry allowed once more at the next switch to sea level).
- The hover label gets `max-width: 28ch` with `text-overflow: ellipsis` on the popup's own content box.
- The status after a snap and the legend no longer promise "the nearest gauge that has enough years": the server answers United States (NOAA CO-OPS) gauges from the nearest one whatever its length, and only the PSMSL source skips short records.
