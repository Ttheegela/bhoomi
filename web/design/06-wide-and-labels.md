# 06 Wide layout details, chart label fix, measurements, and corrections to 00-frame

Edits `renderChart` and its `.c-*` rules in `web/app.js` / `web/style.css` only. Build it AFTER the frame has merged (the frame builder owns the rest of those files). The mock has this fix in `web/app.js` (search for "the drawing is as wide as its box"); copy the idea, not the diff.

## 1. Needs from the frame (corrections found by building the mock; 00-frame.md is not edited, apply these in the frame)
1. `#guide-reopen` moves out of the search label row (too tight at 375: the label "Search for a place" wrapped). Put it on the "Or try an example" label row, right side: `<div class="ex-head"><p id="ex-label" class="ex-label">Or try an example</p><button id="guide-reopen" class="linkbtn" hidden>Quick start</button></div>`; `#examples` becomes `<div id="examples" role="group" aria-labelledby="ex-label">` (no fieldset). While the guide is open `#examples` is hidden (same rule), so "Quick start" is hidden then too. `.ex-label` 14 px `--ink-2`. On wide screens `#examples` is `max-width:960px`.
2. Selectors: every frame script that looks for chips must use `#chips .chip` (never bare `.chip`): module 04 once used that class and `markChips` threw. Module 04 now uses `btn guide-chip`.
3. Scrolling to the answer (frame section 5): do it at `td:load-start` AND again 60 ms after `td:load-end` (a `setTimeout`, not `requestAnimationFrame`, which pauses in background tabs), unless the user has moved the page in between (`wheel`, `touchmove`, `keydown` set a flag cleared at each user-started load). Reason: at load-start the page is too short to scroll the answer to the top, so one early scroll stops short (measured: stopped about 330 px short). Use `behavior:'auto'` (instant): a smooth scroll also stops short when the height changes under it. Modules must not change the layout above `#answer-wrap` after calling `TD.loadPlace` (module 04 closes its card first, then loads).
4. Layout numbers (replace frame section 8 table where they differ): map column 340 at 900 to 1279, 360 at 1280 to 1535, 520 at 1536 and up (frame said 380 at 1280). Answer column then measures 604 (1024), 840 (1280), 920 (1440), 1080 (1920).
5. Default measurement on first load is Air temperature (as in the frame); the empty card `#empty` and the examples are the first-load content (as in the frame). Owner option B (run New York sea level on load) is one line in `init()` if chosen.
6. `html[data-guide="open"] #examples{display:none}` stays. The guide card is a normal grid item above the map at every width.
7. The place-search credit sits under the listbox in the flow, so an open list covers it on phones; the footer carries the same credit as a permanent item (frame section 2), which is enough. No change needed, noted so QA does not file it.

## 2. Wide layout (from 900 px): what was built and measured (mock, 15 Nov 2026)
Grid areas, row-gap 0, bottom margins 24 on each left item (frame section 8). `#more` ("How to read this") spans both columns below. Left column holds map, pick (measurement and source stacked, single column), saved places. At 1280 and up the answer's `.grid` is verdict 340 | chart 1fr; from 1536 verdict 380 | chart 1fr; below 1280 verdict then chart stacked (`.col-verdict` not sticky below 1280; sticky at 1280 and up as before).
| Width | Container | Map frame (drawn) | Answer col | Chart box (drawn) | Sideways scroll |
|---|---|---|---|---|---|
| 375 | 343 | 343 x 280 | 343 | 343 x 396 | none (375 = 375) |
| 768 | 720 | 720 x 360 (set by CSS, not read back) | 720 | not measured | none (768 = 768) |
| 1024 | 976 | 340 x 440 | 604 | 604 x 496 | none |
| 1280 | 1216 | 360 x 520 | 840 | 468 x 496 | none |
| 1440 | 1296 | 360 x 520 | 920 | 548 x 496 | none |
| 1920 | 1616 | 520 x 600 | 1080 | 668 x 496 | none |
Text lines: paragraphs stay under 70 ch; the verdict card keeps its width. At 1280 the chart is narrower (468) than the old 520: option for the owner: below 1440 stack verdict above chart (chart 840 wide, taller page) instead of side by side. Mock chose side by side so the chart and verdict are on one screen.
Hero search input is at most 560 px wide; the hero lead paragraph is hidden below 600 px.

## 3. First-screen rule: the numbers (375 x 812, scroll 0; light and dark identical, the layout does not depend on the theme)
| Case | Measured |
|---|---|
| R1 first visit (guide open) | h2 bottom 180.6; search input bottom 284.6; guide card bottom 604.6; map top 620.6; 191 px of the map visible (rule: at least 96) |
| R1 return visit (guide closed) | search input bottom 284.6; examples row bottom 398.6 (chips 48 px tall); map top 414.6; whole 280 px map visible (rule: at least 240) |
| R2 homeowner (Lower Manhattan, sea level) after pick | answer top 8; meaning headline bottom 230; confidence row bottom 352; limit block bottom 470; verdict banner bottom 642 (limit 804) |
| R2 farmer (Punjab, land water storage) | headline 230; confidence 352; banner bottom 618 |
| R2 student (Chennai, rainfall) | headline 230; confidence 352; banner bottom 618 |
The page scrolls itself to the answer (section 1, item 3). 162 px of room remain under the banner at the worst case, so the big number is on screen too. Changing a size above the banner needs a new measurement.

## 4. Chart label fix
Cause (measured with `web/mock-tools/col.js`): the drawing used a fixed 720 viewBox in a 548 px box, so the font was scaled to 16 px; titles and ticks collided.
Before (sea level at The Battery, label boxes overlapping by more than 1 px): 375: 1 collision ("−400" tick vs "1900" label); 1024: 1; 1440: 3 (panel title touching the y-axis title in both panels, and the tick vs year label). Font on screen 12 / 14 / 16 px.
Fix (all in `renderChart`):
1. `fs = 12` always. `vw = max(280, round(box.clientWidth))`: the viewBox is as wide as the box, so 1 unit = 1 px and the font is 12 px on screen at every width.
2. Re-draw when the box width changes by 8 px or more: a `ResizeObserver` on `#chart-box` (replaces the band-only resize listener, which stays for the heights).
3. Header height per panel `round(3.5 * fs)` = 42 (was 3.25); panel title baseline at `y0 + fs`; y-axis title baseline at `y0 + round(2.3 * fs)` = 28 (was 2.15).
4. y tick count by space: `n = clamp(floor(panelHeight / (1.6 * fs)), 3, 5)` passed to `niceTicks`, so ticks are at least 19 px apart; panelHeight = the plot height (A: hA - 4 - header; B: hB - header).
5. x axis: year labels baseline at `bot + round(1.5 * fs) + 2` = 20 below the panel bottom (was fs + 3); the "Year" title at `bot + round(2.9 * fs) + 4`; axis area height `max(40, round(3.2 * fs) + 6)`. The lowest y tick label (centred 0.35 fs below its line) now clears the first year label.
6. "No change" label: if drawn above the zero line, keep it at least 0.9 * fs below the panel's top (`max(B.top + 0.9 * fs, zeroY - 5)`); its halo box is unchanged (`.c-halo`). This addresses the owner's report of a small box riding over the y-axis title.
7. x ticks keep the existing rule (labels at least 56 screen px apart): now screen px = viewBox units.
After (same page, label boxes overlapping): 375: 0; 1024: 0; 1280: 0; 1440: 0; 1920: 0 (font 12 px on screen at all five).
Not reproduced: a small box covering the y-axis title at the owner's width; it may have been the "No change" halo; rule 6 and the removal of font scaling remove the cause either way. QA: run `col.js` at 375, 600, 768, 900, 1024, 1280, 1440, 1920 on sea level (Battery), air temperature (Princeton) and water storage (Punjab) and expect 0.

## 5. Other desktop refinements
- Examples row stays one line up to 960 px; chips 48 px tall.
- The meaning card and the verdict card keep 2 px ink borders; the empty card, guide card, noise card use the quiet card (1 px `--line`).
- `#answer-bar` on wide screens has no "Change the place" link.
- Print: unchanged; map, guide, saved places and the noise block are hidden in print (`@media print {#map-slot,#guide-slot,#saved-slot,#noise-slot,#share-slot{display:none}}`).

## 6. Built (by the frontend builder)
Section 4: all seven rules built as written in `renderChart` (`fs = 12`, `vw = max(280, round(box width))`, header 42, y title baseline 28, tick count by space, year labels 20 below and "Year" 39 below the panel bottom, axis area 44, "No change" kept 0.9 fs below the panel top, x ticks now measured in real pixels because the drawing is 1 unit = 1 px). `layoutFor` is unchanged: its heights still follow the window band, and its `vw` is now only the band id for the old resize listener and the fallback width for a box that is not laid out yet.
Differences: the `ResizeObserver` is one observer for the page's life, guarded by `if (window.ResizeObserver)`; `renderChart` records the width it drew at, so the 8 px rule compares against the last drawing. The mock's `lastW` variable is not used.
Section 5: already in the frame: the `.ex-head` row, the quiet card for `#empty` (1 px `--line`), no "Change the place" link at 900 and up. Built here: `#examples` max-width 960 px from 900 px; the print rule that hides `#map-slot`, `#guide-slot`, `#saved-slot`, `#noise-slot`, `#share-slot`. Not built (outside the three files): quiet borders for the guide and noise cards come from their own module CSS; `#examples` is still a `<fieldset>` in `index.html` (section 1 item 1 says a `div` with `role="group"`).
Section 2: the frame's CSS matches the table for the map column (340 / 360 / 520), the verdict column (340 / 380) and the container (1200 / 1360 / 1680 maximum). One difference, not changed: the frame's page grid has `column-gap: 32px`, so by arithmetic the answer column is 604 at 1024 (as in the table) but 824 / 904 / 1064 at 1280 / 1440 / 1920, where the table says 840 / 920 / 1080 (a 16 px gap). Decide which gap is meant; the chart box inside is correspondingly 16 px narrower than the table's 468 / 548 / 668.
