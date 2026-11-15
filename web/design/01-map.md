# 01 Map module (own files: `web/map.js`, `web/map.css`; touches no other file)

Needs `00-frame.md` (slot `#map-slot`, `TD`, events). The map is an EXTRA for pointer and touch. Everything it does can be done through the search box; keyboard and screen-reader users lose nothing. The page is fully usable if the map, its tiles, WebGL or the network fail.
A working reference is in the mock: `web/map.js`, `web/map.css` (copy ideas, rewrite cleanly; it has two debug lines, `window.__map` and a CSP listener, to delete).

## 1. Library and loading
- MapLibre GL JS 6.18.0 (BSD-3-Clause), already in `web/vendor/maplibre-gl/`: `maplibre-gl.mjs`, `maplibre-gl-worker.mjs`, `maplibre-gl.css`; `maplibre-gl-shared.mjs` is 0 bytes in the package and not needed (leave it). Keep `LICENSE.txt` beside them. ES module only: load with `import('./vendor/maplibre-gl/maplibre-gl.mjs')` (dynamic import from the classic `map.js`, so `map.js` runs at once and never delays `ask.js`). The library finds its own worker beside itself; no worker setting needed (tested).
- Lazy: `map.js` builds the slot's static markup at once (frame, status row, credit), then loads the library only when `#map-slot` is within 300 px of the window (`IntersectionObserver`, fallback: load at once). About 1.1 MB: nothing is fetched while the map is far below the fold.
- `map.css` starts with `@import url("vendor/maplibre-gl/maplibre-gl.css");` (the library sheet), then the module rules (below). Class prefix `map-`.

## 2. Markup (all created by `map.js`, text only through `textContent`)
```
section#map-slot (frame-owned, hidden -> unhidden by map.js when it starts)
  div.map-frame[role=group][aria-label="Map. Optional: you can also search for a place above."]
    div#map-canvas.map-canvas       (the library's container)
    p.map-wait                       (loading or failure words, see 5)
  div.map-row
    p#map-status.help.map-status[role=status]
    button.linkbtn.map-undo[type=button][hidden]  "Undo"
  p.map-credit  a "OpenFreeMap © OpenMapTiles" (https://openfreemap.org/)   a "Data from OpenStreetMap" (https://www.openstreetmap.org/copyright)
```
Both credit links `rel="noopener"`, 48 px tall, 16 px apart, wrap on narrow screens (two lines at 375). This line is the required credit "OpenFreeMap © OpenMapTiles Data from OpenStreetMap"; it is always on screen with the map. The library's own attribution control is OFF (`attributionControl:false`).

## 3. Size, view, style
- Frame height `var(--map-h)` from the frame (280 phone, 360 at 600, 440 at 900, 520 at 1280, 600 at 1536); width = the slot; 1 px `--line` border, 8 px radius, `overflow:hidden`, `--surface` behind the canvas. `ResizeObserver` on `.map-frame` calls `map.resize()`.
- First view: no place yet: centre `[15, 28]`, zoom 0.4 (phone, under 600 px) or 1.1 (wider): a world overview so the user sees land. `minZoom 0.3`, `maxZoom 11`. With a place: centre on it, zoom `max(current, 4.5)` (a region, not a street), 900 ms `flyTo`; instant (`duration:0`, `fadeDuration:0`) under `prefers-reduced-motion`. `renderWorldCopies:true`; longitudes are wrapped to -180..180 before use; latitudes clamped to -85..85.
- Style: ONE style for both themes: `https://tiles.openfreemap.org/styles/positron` (OpenFreeMap's quiet pale grey; no key). Reason: the owner's rule is colour for the data only, so the base map must be neutral and low contrast; Bright and Liberty are colourful. Dark mode: the same style, drawn through CSS only (no second style, no reload): light = `filter: grayscale(1)` on `.maplibregl-canvas` (removes the faint blue of water), dark = `filter: grayscale(1) invert(1) brightness(.9)` under `@media (prefers-color-scheme: dark)`. Tested: reads as a dark grey map with light labels in the mock. The pin and the controls are separate DOM, not inverted.
- Options: `cooperativeGestures:true` (on touch one finger scrolls the page and two fingers move the map; on desktop the wheel scrolls the page and Ctrl or Cmd plus the wheel zooms: the map never traps scrolling). `locale` text for the overlay: "Use two fingers to move the map" / "Hold Ctrl and scroll to move the map" / "Hold ⌘ and scroll to move the map" (keys `CooperativeGesturesHandler.MobileHelpText`, `.WindowsHelpText`, `.MacHelpText`). `doubleClickZoom:false` (a double tap would pick twice), `dragRotate:false`, `touchPitch:false`, `pitchWithRotate:false`, `touchZoomRotate.disableRotation()`. Overlay colours from tokens only: `background: color-mix(in srgb, var(--ink) 82%, transparent); color: var(--bg)`. Do NOT set `opacity` on it (the library hides it with opacity 0).

## 4. Controls, pin, status
- Zoom buttons: `new NavigationControl({showCompass:false, visualizePitch:false})`, top right. CSS: group `--bg`, 1 px `--line`, 6 px radius, no shadow; buttons 48 x 48 (the default 29 px is too small), 1 px `--line` between; icons are the library's data-URI images (allowed by `img-src data:`), inverted in dark mode; focus ring 3 px `--focus` inset (-3 px offset). Keyboard users reach the two buttons in tab order (after the search box and chips, before the measurement select).
- The canvas itself is decoration: set `canvas.tabIndex = -1` and `canvas.setAttribute('aria-hidden','true')` after `load`. (Do NOT put `aria-hidden` on the container: it holds the two buttons.)
- Pin: `maplibregl.Marker` with one `div.map-pin[aria-hidden=true]`: 20 px circle, `--ink` fill, 3 px `--bg` border, plus a 2 px `--ink` ring (`box-shadow:0 0 0 2px var(--ink)`): reads on light and dark grey, no colour. One pin only. A marker's position is set by the library through CSSOM (allowed).
- `#map-status` (14 px grey, one `role=status` line, min height 24, 8 px margin above and below). Words: first view "Tap the map to pick a place, or search above." After a pick from the map: "Pinned {lat}° N, {lon}° E. We use the nearest data we have." After any other pick: "Showing {lat}° N, {lon}° E. We use the nearest data we have." (N/S and E/W, absolute values, two decimals; `TD.state` has no say here: take it from `td:place-pick`.) The honest reason for "nearest data": gridded sources average about 50 km, tide gauges can be 100 km away.

## 5. What a click or tap does, and how a wrong one is undone
- A single click or tap (`map.on('click')`; the library does not fire it after a drag or pinch) = pick: set the pin at once, remember the place shown before as `prev` (from `TD.state` before the call; null if none), then `TD.loadPlace({lat, lon, label:'Pinned spot ({lat}° N, {lon}° E)', origin:'map'})` with the measurement now selected. No reverse geocoding (no outside service); the label says what it is. The frame scrolls to the answer on phones.
- Undo: while the current place came from the map and `prev` exists, the "Undo" button shows right of the status (48 px, `.linkbtn`). It calls `TD.loadPlace({...prev, origin:'undo'})`, hides itself and moves the pin. Status then reads "Showing ...". Undo is one step deep. (Back-button history is not used: the page keeps `replaceState`.)
- Pick by other controls (`td:place-pick` with origin not 'map'): move the pin and fly there; origin 'map': pin only (already there), never re-fly. Pick with origin 'geo' also pins (the user asked for their own location; the pin is local, nothing is sent).
- A tap on the ocean or an unmapped place is allowed: the frame's own problem card answers ("We can't answer that for this place.", with recovery buttons). The map adds nothing.

## 6. Keyboard and screen-reader users (nothing lost)
The search box does everything. The map group has a label that says so (section 2). Pointer-only actions: pick and zoom by wheel or pinch. Zoom buttons are keyboard-operable. No "pick the map centre" button in this pass. The pin and canvas are hidden from screen readers; the status line speaks the result of a pick (it is `role=status`, so a screen reader hears "Pinned 40.71° N, 74.01° W. ..." and the frame's own announcements follow).

## 7. Failure states (page stays fully usable; the slot never collapses: keep the frame height)
- Loading (library or first tiles, until the map's `load`): `p.map-wait` centred in the frame: "Loading the map…" (16 px grey, no animation).
- No WebGL (constructor throws) or the library fails to import: `.map-wait` reads "Your browser can't show the map. Search for a place above." and `#map-status` reads "You can still search for a place above." Pin and controls are not created.
- Style or first tiles fail (the map's `error` event before `load`, a network failure, the tile host blocked): `.map-wait` reads "The map couldn't load. You can still search for a place above." plus a "Try again" button (48 px) that builds a new map once. Tile errors after `load` are ignored silently (partial tiles are normal on a slow line); the pin and clicks keep working.
- Offline: same as the style failure.
- Slow (over 8 s before `load`): add to `.map-wait`: "Still loading. The map is optional." The page is not blocked meanwhile.
- `prefers-reduced-motion`: no fly, no fade.
- Under `forced-colors` the pin keeps its ring (it is a border and a shadow: add `forced-color-adjust:none` is NOT needed; give it `border:3px solid Canvas; background:CanvasText` there).

## 8. Content policy additions (the only widening of the page policy)
Tested in Chrome in the mock with a meta policy `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' https://tiles.openfreemap.org`: the map loads (style, vector tiles, fonts, sprite) with no violation. So:
| Directive | Add | Why | Status |
|---|---|---|---|
| `connect-src` | `https://tiles.openfreemap.org` | style JSON, vector tiles, glyph (font) files, sprite, all by fetch | required (tested) |
| `img-src` | `https://tiles.openfreemap.org blob:` | a browser without `createImageBitmap` loads the sprite through an `Image`; `blob:` for decoded tile images | precaution, not needed in Chrome; QA checks Safari and Firefox with the Report-Only header and keeps it only if a violation shows |
| `worker-src` | `'self' blob:` | the worker `maplibre-gl-worker.mjs` is same-origin; a cross-origin fallback uses a blob | precaution, not needed in Chrome |
Style sheet (`style-src 'self'`): the library sets styles through the CSSOM and ships its CSS as a file: fine. No inline style attribute or `<style>` is written by us. No outside script or font. `vercel.json` is not in `web/`: the orchestrator edits it in the same PR (note it in the PR text).
Privacy line for `03-memory.md` (the tile host sees the visitor's network address; the tile addresses reveal the area looked at, not a name).

## 9. Done-check
- [ ] Empty `map.js`: slot hidden, page works. Full module: slot shown, no console error, no inline style written by us.
- [ ] First load shows the world, no pin; a tap pins and runs the answer; Undo restores the previous place; a search pick flies and pins.
- [ ] Dark mode map is grey, not blue or green; controls and pin readable in both themes; controls 48 px.
- [ ] Block `tiles.openfreemap.org` (devtools): failure words show, search and examples still work.
- [ ] One finger scrolls the page over the map on a phone; the overlay words show.
- [ ] Credit line visible and linked under the map at 375 and 1920.

## 10. Built differently from the text above (frame builder: read this)
- Content policy: only `https://tiles.openfreemap.org` was added, to `connect-src` and `img-src` (owner decision). No `blob:`, no `worker-src`. If Safari or Firefox report a violation in Report-Only, widen then.
- The pin is created after the map's `load` (a pick made before that is remembered and pinned, with the fly, at `load`).
- The failure line "You can still search for a place above." in `#map-status` is set only for "no WebGL / library did not import"; the style-or-tiles failure puts it inside `.map-wait`.
- "Try again" is offered once; a second failure leaves the words only.
- The slow line is appended to the loading words: "Loading the map… Still loading. The map is optional."
- The footer credit is also added with `TD.addCredit('map', ...)` (skipped if `TD.addCredit` is missing).
- The library is used through its named exports (`Map`, `Marker`, `NavigationControl`); it has no default export.
