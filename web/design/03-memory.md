# 03 Memory without accounts (own files: `web/memory.js`, `web/memory.css`)

Needs `00-frame.md`. Fills `#saved-slot` (saved places and recents), `#share-slot` (Save and Share buttons in the answer bar) and `#privacy-slot` (footer). No sign-in, ever. Everything stays in this browser (`localStorage`). Class prefix `mem-`. Mock: `web/memory.js`, `web/memory.css` (reference only).

## 1. Storage (wrap every read and write in try/catch)
- `td.saved.v1`: JSON array, newest first, at most 6: `{lat, lon, label, variable, source|null, start|null, end|null, verdict:'rising'|'falling'|'none'|null, checked:'YYYY-MM-DD'}`.
- `td.recent.v1`: same shape, newest first, at most 4, never holds a place that is saved (it moves out when saved), one entry per key.
- Key of a place = `lat(2 decimals)|lon(2 decimals)|variable|source||''`. The window (`start`, `end`) is part of the saved entry (so a share link and a saved card reopen the same thing) but not of the key.
- Written text is cleaned with `TD.cleanPlace`. Read data is validated (numbers in range, `variable` string, verdict one of three or null); a bad entry is dropped, a bad file is ignored and replaced.
- Recents are added on `td:load-end` with `ok:true` and `detail.origin` not 'undo'. A saved entry's `verdict` and `checked` are refreshed when its place loads. "Use my location" results are NEVER stored (origin 'geo'): privacy.
- Storage unavailable or full (private window, blocked, throws): the module still builds the share control; saved places and recents are not shown; the Save button is replaced by one grey line (14 px) in `#share-slot`: "Saving isn't available in this browser. Sharing still works." Nothing breaks.

## 2. Save and Share (in `#share-slot`, right side of `#answer-bar`)
`div.mem-actions` (flex, gap 8, wrap, right-aligned; below 360 px full-width stacked). Two buttons, 48 px tall, `.btn` look, auto width, 16 px padding:
- **"Save this place"** (not saved) / **"Remove from saved"** (saved). Click toggles. Confirmation words in `#mem-status` (`role=status`, 14 px grey, directly under the buttons, `TD.announce` not needed): "Saved. It is kept in this browser only." / "Removed from saved places." Saving a 7th place drops the oldest and says "Saved. The oldest saved place was removed (up to 6 are kept)."
- **"Share this result"**: copies `TD.linkFor()` (reopens the same place, measurement, source and years) with `navigator.clipboard.writeText`. Success: the button text becomes "Link copied" for 3 seconds and `#mem-status` says "Link copied. It reopens this place, measurement and years. It holds nothing about you." No clipboard (insecure page, denied): show a read-only text field `input.mem-link` (48 px, full width, label "Link to copy") already selected, with `#mem-status`: "Copy this link." Keyboard: Enter and Space work (real buttons).
- Origin 'geo': the frame writes no link for "Use my location". Hide Share and say in `#mem-status`: "We don't make a link for your own location, to keep it private. Search for the place by name to share it." Save is hidden too (rule above).
- No social icons, no email, no sign-in prompt. Hidden while the first load runs and after a failed load (`td:load-end` with `ok:false`).

## 3. Saved places and recents (`#saved-slot`)
Hidden when both lists are empty. Order: saved list first, then recents.
```
section#saved-slot[aria-label="Saved places"]
  h2.mem-h "Saved places"            (18 px Space Grotesk 700)  + ul.mem-list > li.mem-card ...
  h2.mem-h "Recent results"          (only when recents exist)   + ul.mem-list
```
Card (li, `--surface` fill, 1 px `--line` border, 8 px radius, 4 px padding, flex): 
- main button `button.mem-open` (flex 1, min-height 64, left aligned, no border, transparent, padding 8 12): line 1 `{label}` 16 px weight 700 (one line, ellipsis); line 2, 14 px grey: `{Measurement short name} · {verdict word}` where the verdict word is `rising`, `falling` or `no clear change` plus a ▲ ▼ ≈ shape (`aria-hidden`, 14 px, ink, no colour) and, when known, ` · checked {d Mon yyyy}` (the verdict is as of that date, not live: the grey line says so). Accessible name = "{label}, {measurement}, {verdict word}, checked {date}. Open." Click = `TD.loadPlace({lat,lon,label,variable,source,start,end,origin:'saved'})` (recents: 'recent').
- secondary button 48 x 48 at the right: saved card = "Remove" (icon-only x, `aria-label="Remove {label} from saved places"`, 20 px glyph `aria-hidden`); recent card = "+" (`aria-label="Save {label}"`). Focus after Remove: the next card's main button, else the "Saved places" heading (`tabindex=-1`). `#mem-status` words: "{label} removed." / "{label} saved."
- Layout: phone one column; 600 to 899 two columns; 900 and up one column (the map column is 340 px wide at 900 to 1279). Gap 8. No red dots, no badges, no counts that nag.
- Verdict is never coloured here (monochrome, words and shapes only).

## 4. "Your data and privacy" (`#privacy-slot`, in the footer, after the sources list)
`<details class="mem-privacy"><summary>Your data and privacy</summary> ... </details>`; summary 48 px tall, 16 px, underlined text with the page's disclosure triangle (same `.mark` pattern as "Show the data as a table"). Closed by default. Exact text (14 to 16 px, `--ink-2`, bullets):
- "No account. We never ask you to sign in."
- "Saved places and recent results stay in this browser, on this device. Nothing is sent to us."
- "Place names you type in the search box go to our server, and from there to Open-Meteo's place search."
- "The map loads its tiles from OpenFreeMap, which sees your network address, like any website you visit."
- "A question you type in Ask, and the earlier messages of that chat, are sent to an AI model provider so it can be answered. Questions and answers are also recorded by a quality-checking service (Langfuse). Nothing else about you is kept."
- "Our server counts requests from each network address for a short time, to stop overuse."
Then a button "Clear saved places and recent results" (48 px, `.btn`, auto width). Two steps in place, no dialog: click turns the row into "Clear everything saved in this browser?" with buttons "Yes, clear" and "Cancel" (focus on Cancel); Yes clears both keys, hides `#saved-slot`, `#mem-status` says "Cleared." Hidden if storage is unavailable.
(Owner confirmed the Langfuse line. If the facts change, only this text changes.)

## 5. Events and calls
Listens: `td:ready` (build, read storage), `td:place-pick` (none needed), `td:load-end` (add recent, refresh buttons, show or hide Save and Share). Calls: `TD.loadPlace` (origins 'saved', 'recent'), `TD.linkFor()`, `TD.cleanPlace`. It never writes the page link, the controls or another module's slot. A late module reads `TD.state` once.
`#mem-status` lives inside `#share-slot` (frame slot, a div): create it there; it is hidden when empty.

## 6. Needs from the frame
Nothing missing. The frame keeps `#share-slot` empty (it takes no space when empty).

## 7. Done-check
- [ ] Empty `memory.js`: footer has no privacy note, no Save or Share; page works.
- [ ] Save, reload the page: card shows with label, measurement, verdict word and date; click reopens the same place and years; Remove works with keyboard; focus lands sensibly.
- [ ] Share: paste the copied link in a new tab, it opens the same place, measurement, source and window (try a 10-year window).
- [ ] "Use my location": nothing stored, no link, the words above.
- [ ] localStorage blocked (DevTools): no errors, Save replaced by the one grey line, Share works.
- [ ] Clear works in two steps. 375 px: buttons wrap, none under 48 px, nothing sticky.

## 8. Built differently from the text above
- Measurement short names: the two overrides the page's own pickers use ("Hottest day", "Water storage"), else the catalogue name without its bracketed part.
- A stored `checked` that is not a date becomes unknown (the card omits "checked ..."), instead of dropping the entry. A stored `source` is passed through `TD.cleanPlace`.
- "Cleared." is also shown as a grey line under the Clear button in the footer, and spoken with `TD.announce` when the answer bar is hidden, because `#mem-status` is not visible before the first result.
- After "+" on a recent card, focus goes to the "Saved places" heading. After Remove with no next card: the "Saved places" heading if any saved remain, else the "Recent results" heading, else the Save button.
- "Link to copy" is a visible 14 px grey label above the field. Unavailable storage is detected by a test write at start; a failed write later also turns saving off.
- A module loaded late treats a loaded place named "your location" as the geo case (origin is not known then).
- Fix round 1: a place labelled "your location" is the visitor's own location for every origin (not stored, no Save or Share, privacy sentence shown) and stored items with that label are dropped. A saved card's verdict and date refresh only when the loaded window equals the saved window. A date needs month 01 to 12 and day 01 to 31 or it counts as unknown. When a write fails after saving, the "Saving isn't available" sentence replaces "Saved." (also for "+"), and "+" says the oldest-removed sentence when it pushes one out.
