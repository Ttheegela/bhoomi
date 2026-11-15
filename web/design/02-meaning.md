# 02 "What this means for you" card (own files: `web/meaning.js`, `web/meaning.css`)

Needs `00-frame.md`. Fills `#meaning-slot` (inside `#answer`, above the existing verdict card). Owner-confirmed data: `trend.meaning = { headline, confidence, comparison, limit }` inside the `/api/trend` reply, all four computed on the server. `confidence` is exactly `"Very clear"`, `"Clear"` or `"Not clear"`; `comparison` is `""` when there is no clear change. Example: headline "Sea level here has clearly been rising."; comparison "About 3 cm higher every 10 years."; limit "This is what tide gauges have already measured. It cannot tell you how high the sea will get."
Rule: the page adds NO words or numbers to these strings. Only fixed labels (below), the confidence marker and the source line are ours. Every string goes in with `textContent`.

## 1. When it shows
- `td:load-end` with `ok` and `trend.meaning` having a non-empty `headline` and `limit` and a `confidence` of the three words: build the card, unhide the slot.
- Missing or malformed `meaning`, `ok:false`, or a failed trend: hide the slot (the old verdict card is then the answer, as before). Never show a card with a blank line.
- `td:load-start`: first load of a visit: slot stays hidden. A later load: keep the old card, dimmed: `#answer[aria-busy="true"] #meaning-slot { opacity:.5 }` (same as `#result`). If the new place fails, the card is hidden on `td:load-end`.
- Late module: read `TD.state` once at start; if `status:'loaded'`, build from `TD.state.trend`.

## 2. Markup
```
section#meaning-slot[aria-label="What this means for you"]
  div.card.mean
    p.card-label            "What this means for you"
    h2#meaning-heading.mean-head[tabindex=-1]   {headline}
    p.mean-compare[hidden if comparison is ""]  {comparison}
    div.mean-conf
      p.mean-conf-label     "How sure we are"
      p.mean-conf-word      {confidence}  + span.mean-marks[aria-hidden=true] (three bars)
    div.mean-limit
      p.mean-limit-label    "What past data can't tell you"
      p.mean-limit-text     {limit}
    p.source                "Our calculation from public data."
    div.srcline             "Raw data: {trend.source.name} ↗" (link to trend.source.url, https only; plain text if not https)
```
`id="meaning-heading"` is required: the frame focuses it after a user-started load. The `.card`, `.card-label`, `.srcline`, `.srclink`, `.source` rules already exist in `style.css`: reuse them, add only `mean-*` rules in `meaning.css`.

## 3. Look
- Card: `--surface` fill, 2 px `--ink` border, 8 px radius, same as the verdict card; inner padding 16 (12 top). No colour anywhere in this card: colour stays with the verdict banner below.
- Headline: Space Grotesk 22 px (24 at 900+), weight 700, line-height 1.25, `--ink`, max 24 ch per line is not forced; it wraps freely (phone: 3 lines at most for a 60-character sentence).
- Comparison: 18 px Inter, weight 600, margin-top 8.
- Confidence row: label 14 px `--ink-2` regular; word 18 px weight 700; marker: three 16 x 8 px bars, 4 px apart, 6 px left of the word. Filled bar = `--ink` fill; empty = 1 px `--line` outline, no fill. Very clear = 3 filled, Clear = 2, Not clear = 1. Meaning is carried by the word; the marker is decoration (`aria-hidden`). Same size and weight for all three words: "Not clear" is not styled as weaker or as a warning.
- Limit: label 14 px grey, text 16 px `--ink-2`; a 1 px `--hairline` rule above the block (decorative), 12 px padding.
- Spacing between blocks 12 px; source line 14 px grey, source link 48 px tall. At 375 px the card must end with the verdict banner still starting above 804 px at R2 (see frame section 9): if the measured card is taller than 340 px, drop the paddings by 4 px each before dropping content.
- Wide: card fills the answer column; text lines stay under 70 ch (`max-width:70ch` on the text paragraphs).

## 4. Words (fixed labels; everything else is server text)
"What this means for you", "How sure we are", "What past data can't tell you", "Our calculation from public data.", "Raw data: {source} ↗". No percentages, no "chance", no warnings.

## 5. Accessibility
- Slot is a labelled region; the h2 is the card's heading (the page's h1 is the title, the hero h2 stays; this is another h2: that is fine).
- Reading order: label, headline, comparison, confidence, limit, source. Confidence reads as "How sure we are: Clear".
- No `aria-live` of its own: focus moves to `#meaning-heading` (frame), which reads the headline; do not also call `TD.announce`.
- Contrast: `--ink` on `--surface` 16:1 light; 4.5:1 or better for the grey lines (`--ink-2` on `--surface` is 7.7:1 light, 9:1 dark).
- Print: card keeps its border; marker bars print as filled or outline.

## 6. Where the detail goes
Unchanged and below: the verdict card keeps the banner, big number, "our calculation" line, source link, rate and 95% range sentences, p-value, facts and caveats. This card replaces none of them. If the server later moves the strings to another route, only `getMeaning(detail)` in `meaning.js` changes (keep that one function).

## 7. Needs from the frame
Nothing missing. Note for the frame builder (not a change request): `#loading` text "Looking up the data…" also shows during the first load; this card stays hidden then, so there is no double message.

## 8. Done-check
- [ ] Empty `meaning.js`: slot hidden, answer unchanged.
- [ ] Sea level New York: headline, comparison, "Very clear" with three filled bars, limit sentence, source link; no word of ours inside the three server strings.
- [ ] A no-clear-change result (Princeton air temperature, last 10 years): no comparison line, no gap; "Not clear" with one filled bar, same card size.
- [ ] Response without `meaning`: slot hidden. Reload for another place: old card dimmed, then replaced.
- [ ] 375 px: card plus verdict banner visible by 804 px after a pick (R2). Light and dark checked.

## Differences from the specification as built
- `#meaning-heading` gets a 3 px `--focus` ring when the frame focuses it.
- The source line is left out when `trend.source.name` is missing (nothing to name).
- A reply whose four strings are not all strings, or whose `confidence` is not one of the three words, hides the card (old cached replies have no `meaning`).
- `td:load-start` now hides and empties the card when `TD.state.trend` is null (the frame cleared the old answer for a new place), because an old card naming no place would be the only result on screen. When the frame keeps the old answer dimmed, the card stays dimmed as specified.
- High-contrast mode (`forced-colors: active`): filled bars keep a `CanvasText` fill so they do not look empty.
- Gap before the source line is 12 px.
