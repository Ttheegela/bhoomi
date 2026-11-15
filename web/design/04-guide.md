# 04 Guided first visit (own files: `web/guide.js`, `web/guide.css`)

Needs `00-frame.md`. Fills `#guide-slot`, unhides `#guide-reopen`, sets `data-guide="open"` on `<html>` while open (the frame then hides the example chips; the role chips replace them). Class prefix `guide-`. Two steps, every step skippable. Mock: `web/guide.js`, `web/guide.css` (reference only).

## 1. When it shows
- First visit: `localStorage` key `td.guide.v1` absent AND the address has no place link (`location.hash` has no `variable=`) AND the tab is Explore. Shown once; any of Skip, "Show me", "Choose a different place", Escape-free closing writes `td.guide.v1 = "done"`. Storage unavailable: shows once per page load (kept in a variable), never blocks anything.
- Reopen: the button `#guide-reopen` ("Quick start", frame-owned, `hidden` until this module loads) opens step 1 again at any time, even after dismissal; focus moves to the card heading.
- Opening a share link: not shown (and not remembered as dismissed).
- Closing: remove the card (`slot.hidden = true`, empty it), remove `data-guide`, focus returns to `#place` (skip, different place) or to the answer (the frame moves it after "Show me"). `TD.announce("Quick start closed.")` on skip.

## 2. Step 1: "Pick what describes you"
```
section#guide-slot[aria-label="Quick start"]
  div.card.quiet.guide-card
    p.guide-step      "Step 1 of 2"                           (14 px grey)
    h2#guide-h.guide-h[tabindex=-1]  "New here? Pick what describes you."   (20 px Space Grotesk 700)
    div.guide-chips[role=group][aria-labelledby=guide-h]   four button.chip.guide-chip
    p.guide-note      "This changes only the examples and the wording, not the data."
    button.btn.guide-skip  "Skip, just search"
```
- Chips (labels exact): "I'm a homeowner", "I'm a farmer", "I'm a student", "I'm a local planner". Buttons (not radios): 48 px tall min, 16 px padding, same look as `.chip` (1 px `--line`, 6 px radius, no pressed colour). Grid: phone 2 columns x 2 rows, 8 px gap; 600 and up: 4 in a row. Wide card max-width 760 px, left aligned.
- Skip: `.btn`, auto width, 48 px, text "Skip, just search"; closes the guide, focus to `#place`.
- Phone height budget: card about 290 px; the first-screen rule R1 (first visit) in the frame needs at least 96 px of the map below it (mock measures this).

## 3. Step 2: the ready-made question
Choosing a chip replaces the card's content (same card, no navigation; focus to `#guide-h`; `TD.announce` not needed, focus reads it):
```
p.guide-step   "Step 2 of 2"
h2#guide-h     {question}                          e.g. "Is the sea rising where I live?"
p.guide-plan   "We'll look at {measurement} for {place}."
p.guide-note   {role note, optional}
div.guide-actions  button.btn.primary "Show me"   button.btn "Choose a different place"   [button.btn alt]   button.linkbtn "Back"
p.guide-note   "This changes only the examples and the wording, not the data."
```
- "Show me": `TD.loadPlace({lat, lon, label, variable, origin:'guide'})`, then close the guide (remembered). The answer shows exactly what the same place and measurement show without the guide.
- "Choose a different place": closes the guide (remembered), focus to `#place`.
- "Back": returns to step 1. All four are real buttons; Back is `.linkbtn` (48 px).
- `alt` (farmer only): "Look at the hottest days instead" loads `air_temp_max` at the same place (question "Are the hottest days getting hotter?").

## 4. The four roles (all checked on the mock server on 15 Nov 2026; numbers shown here only to prove data exist, never shown by the guide)
| Chip | Place label (shown) | lat, lon | Measurement (id, words) | Question | Note under plan | Result seen |
|---|---|---|---|---|---|---|
| I'm a homeowner | Lower Manhattan, New York | 40.71, -74.01 | `sea_level`, "sea level" | "Is the sea rising where I live?" | "Tide gauges measure the sea against the land." | rising, 31.8 mm per decade, NOAA CO-OPS, 1900 to 2026 |
| I'm a farmer | Punjab, India (near Ludhiana) | 30.90, 75.85 | `water_storage`, "land water storage" | "Is the water stored in the land under my fields going down?" | "Satellites measure all water stored in the land, not the level in one well." | falling, about 40 cm per decade, GRACE, 2002 to 2026 |
| I'm a student | Chennai, Tamil Nadu, India | 13.08, 80.27 | `precip`, "rainfall" | "Is it raining more or less than it used to?" | "" | rising, 0.16 mm per day per decade, NASA POWER, 1981 to 2025 |
| I'm a local planner | Mumbai, Maharashtra, India | 19.08, 72.88 | `sea_level`, "sea level" | "How fast is the sea rising along our coast?" | "" | rising, 9.4 mm per decade, PSMSL, 1878 to 2024 |
Farmer `alt`: `air_temp_max` at 30.90, 75.85: seen falling, 0.36 per decade, NASA POWER: an honest result that may surprise; the card shows what the data say. Plan sentence uses the catalogue short name lower-cased where it reads as a name ("land water storage", "rainfall"); the exact words above are the ones to use. The place label is passed as the `label` (it becomes the "Showing:" line and the share link's `place`). Punjab has no stand-in in the mock `/api/places`; the guide uses coordinates, so it does not need the place search.
If a preset's request fails, the frame's normal problem card shows; the guide is already closed.

## 5. Events and calls
Listens: `td:ready` (decide whether to open; needs `TD.variables` only to check each preset's `variable` exists: a missing one hides that chip, fewer than 2 chips left = no guide). Calls: `TD.loadPlace` (origin 'guide'), `TD.announce`. Sets `html[data-guide]`. Does not touch the map or the link.

## 6. Accessibility
Card is a labelled region; focus moves to `#guide-h` when it opens by the reopen button and after step changes, not on first-visit load (do not steal focus from the page on arrival). Tab order: step text, chips, skip. No timers, no auto-advance, no animation. Contrast as tokens. Colour-free.

## 7. Needs from the frame
Nothing missing: `#guide-reopen`, `html[data-guide]` rule and the slot are in 00-frame.md section 7.

## 8. Done-check
- [ ] Empty `guide.js`: nothing shows, "Quick start" stays hidden.
- [ ] Fresh profile: card shows, example chips hidden; Skip closes it and it stays closed after reload; "Quick start" reopens it.
- [ ] Each role reaches an answer in 2 clicks (chip, Show me); the answer equals the unguided one.
- [ ] Opening a share link: no guide. localStorage blocked: guide shows once, no error.
- [ ] 375 x 812: R1 holds (frame). Keyboard only works end to end.

## 9. Differences from the build
- Opens from `TD.ready.then(...)` (the promise behind `td:ready`), so it also works when loaded late.
- Share link: the hash (`variable=`) is checked at start, plus a `td:place-pick` listener for origin share-link; neither remembers.
- The "Result seen" column in section 4 is the designer note from one test run; the page never shows it.
- Not Explore means the hash has `tab=` other than `explore`.
- "Show me" and the alt button remember the dismissal before calling `TD.loadPlace`.
