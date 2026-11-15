# 05 "Real or noise?" (own files: `web/noise.js`, `web/noise.css`)

Needs `00-frame.md`. Fills `#noise-slot` (after the chart, full width of the answer column). The challenge's own idea: shorten the record and watch the verdict wobble on short stretches and hold on long ones. Numbers come from the server (`GET /api/trend` with `start`, one request per stretch, through `TD.fetchTrend`). The one sentence is built by code from those results (templates in section 5). Class prefix `noise-`. Mock: `web/noise.js`, `web/noise.css` (reference only).

## 1. What the user sees (idle)
```
section#noise-slot[aria-label="Real or noise?"]
  div.card.quiet.noise-card
    h2.noise-h        "Real or noise?"
    p.noise-lead      "A short stretch of data can mislead: normal ups and downs weigh more. Try shorter stretches of this record and see whether the answer holds."
    button.btn.noise-go   "Try shorter stretches"          (48 px, auto width)
    p#noise-status.help[role=status]
```
Shown after a successful load with a record long enough (section 3). Hidden while the first load runs, after a failed load, and when no stretch qualifies. It does nothing on its own: no request until the button is pressed (requests are not free and the place search and trend routes are rate limited).

## 2. After the button
Requests (through `TD.fetchTrend`, three at a time, never more than 4 in all per place): for N in 10, 20, 30 years that qualify: `start = {last year of the full record - N + 1}` (a "YYYY" string; `end` is omitted so it runs to the end of the record). The "Full record" row is the trend already loaded when `params.start` and `params.end` are empty; if the loaded answer is itself a window (`start` set), fetch the full record once more (the fourth request). Results are kept in memory per `lat|lon|variable|source` for the visit: pressing the button again for the same place re-uses them (no new requests).
Rows (a `ul.noise-list`, shortest stretch first, "Full record" last, so the eye goes from shaky to steady):
```
li.noise-row[data-v=rising|falling|none]
  div.noise-top   span.noise-label  "Last 10 years, 2017 to 2026"       span.noise-verdict  "▲ Rising" | "▼ Falling" | "≈ No clear change"
  svg.noise-bar[aria-hidden=true]       (section 4)
  p.noise-num   "{slope with sign} {units} per decade. 95% range {lo} to {hi}."
  button.linkbtn.noise-show   "Show this on the chart"   (48 px)
```
- Label: "Last {N} years, {y0} to {y1}" with `y0`,`y1` the first four characters of the reply's `period.start`/`period.end`; the last row: "Full record, {y0} to {y1}".
- Number formats: exactly the page's: sign with "+" and "−", two decimals if under 1 else one, `units` from the reply with `degC` shown as "°C"; the sentence "95% range" is the page's own wording. These strings come from the same formatter as the verdict card (`fmtVal` in `app.js`); the module may not import it, so it ships a 6-line copy (keep behaviour identical, a QA check compares them).
- "Show this on the chart": `TD.loadPlace({lat,lon,label,variable,source,start,end,origin:'window'})` where `start` = the row's request `start` (empty for the full record). The whole answer then shows that stretch and the share link holds `start`.
- Verdict word for a row: from the reply's `verdict` (`rising`, `falling`, `no_clear_change`): "Rising", "Falling", "No clear change". Never "X% chance".
- All text through `textContent`; numbers formatted by code from the reply only.
- After all requests finish: `TD.announce` is NOT used; `#noise-status` (a `role=status` line) says "Compared {n} stretches." and the sentence of section 5 is inserted as the first paragraph under the title (`p#noise-sentence.noise-sentence`, 18 px, weight 600).

## 3. Which stretches qualify
Let `L` = years from the full record's `period.start` to `period.end` (round). Offer N only when `L >= N + 5` (so each stretch is clearly shorter than the record). Fewer than one qualifying stretch (L under 15): the slot stays hidden. Water storage (2002 to 2026, L about 24): only "Last 10 years" and "Full record" (20 needs 25). Sea level at a long gauge (L over 100): 10, 20, 30 and the full record. Records are never padded or extended.

## 4. The bar (the wobble, without colour alone)
- One SVG per row, `viewBox` width = the container width (set by script from `clientWidth`, so the text stays 12 px and shapes do not stretch), height 36. All rows share ONE scale: `min = lowest ci_low of all rows (and 0)`, `max = highest ci_high of all rows (and 0)`, 6 % padding.
- Drawn: a dashed vertical line at 0 (the "no change" line, 1 px `--chart-faint`, dash 3 3, full height); the range as a 10 px tall bar from `ci_low` to `ci_high` (fill = the verdict token `--up-bg`, `--dn-bg` or `--nc-bg` at 100 %, 1 px `--ink` outline so it shows in forced colours and print); a dot (r 5, `--ink` fill with a 2 px `--bg` ring) at `slope_per_decade`. A bar that crosses the dashed line is a stretch whose range includes "no change": the row says so in words (section 2 verdict). Bars are wide on short stretches and narrow on long ones: that IS the lesson.
- Legend under the list (14 px, grey, one `p`): "Each bar is the range of trends the data support (95% range). The dot is our best estimate. The dashed line is no change. All bars share one scale." plus the tag "Our calculation." and the source link `Raw data: {source name} ↗` (48 px, from the loaded trend's `source`).
- Verdict colours are data colours (allowed); the word and shape always show beside them. Dark mode tokens switch automatically.

## 5. The sentence (code builds it from the rows' verdicts and rates; fixed templates)
Let `V` = the set of verdict words, `short` = the shortest row, `full` = the last row.
- All rows rising or all falling, rates within a factor of 1.5 of each other (by `|slope|`): "Every stretch gives the same answer: {rising|falling}. That is what a real change looks like."
- All rows the same verdict but rates differ by more than 1.5: "Every stretch points the same way: {rising|falling}. Short stretches give a shakier rate, from {min} to {max} per decade; the full record is steadier." ({min}, {max} = the smallest and largest slope with units, formatted as above.)
- All rows "no clear change": "No stretch shows a clear change. Over this record, any change is too small or too noisy to separate from normal ups and downs."
- Mixed (short differs from full): "The answer changes with the length of the record: {short label lower-case} says {word}, the full record says {word}. Short stretches wobble because normal ups and downs weigh more; longer ones hold steady, so trust the longer record more." ("{word}" is "rising", "falling" or "no clear change".)
Never write "real" or "fake" except in the first template's closing phrase; never a probability.

## 6. States
- Loading (after the click): the button becomes "Checking…" (`aria-disabled="true"`), `#noise-status` "Checking shorter stretches…", and each row's slot shows a grey placeholder row (flat `--surface`, no animation) with the label only; rows fill in as replies arrive; focus stays on the button.
- A stretch fails (400 not enough data): row text = the server `detail`, verbatim, no bar, no number. 429: "Too many requests. Wait a moment and try again." 502, network or other: "We couldn't check this stretch."
- All fail: no sentence; `#noise-status` "We couldn't compare stretches right now. Try again in a minute." and the button returns as "Try again".
- The place changes (any `td:load-start`): drop all rows, return to idle (the kept replies stay in memory for that place).
- Slow (over 8 s): add "Still working. This can take a few seconds."
- Reduced motion: nothing animates anyway.

## 7. Accessibility
Heading h2; the list is a real `ul`; each row reads: "Last 10 years, 2017 to 2026. Rising. +76.4 mm per decade. 95% range +23.4 to +128.7. Show this on the chart." (the SVG is hidden). The sentence is real text. Tap targets 48 px. No colour-only meaning (word and shape in every row). Contrast per tokens; bar outline 1 px `--ink`.

## 8. Layout and size
Card spans the answer column at every width. Phone: one column, row about 120 px (label and verdict on one line when they fit, else stacked; bar full width; number line; link). 600 and up: label and verdict on the left, bar in the middle (flex 1, min 200 px), number line under both; wide: same. The card is below the chart and the year stripes; never above.

## 9. Events and calls
Listens: `td:load-end` (decide visibility, remember `params`, `trend`), `td:load-start` (reset). Calls: `TD.fetchTrend`, `TD.loadPlace` (origin 'window'), `TD.announce` (not used, see above). Needs `TD.state.trend.period` and `source`.

## 10. Needs from the frame
Nothing missing. (`TD.fetchTrend` returns `retryAfter` for the 429 case; the words above do not use it.)

## 11. Examples checked on the mock server (15 Nov 2026), to build the QA
- Princeton air temperature (40.35, -74.66): full 1981 to 2025 rising +0.41 °C per decade (range +0.29 to +0.52); last 30 years rising +0.42 (+0.19 to +0.65); last 20 years rising +0.41 (+0.00 to +0.83); last 10 years NO CLEAR CHANGE +0.58 (−0.24 to +1.38). Mixed sentence: short stretch wobbles, long ones hold.
- New York sea level (40.71, -74.01): full 1900 to 2026 rising +31.8 mm (+30.6 to +33.0); last 30 years +47.2 (+36.4 to +58.1); last 20 years +54.2 (+35.4 to +73.2); last 10 years +76.4 (+23.4 to +128.7): all rising, rates differ by more than 1.5: second template.
- Chennai rainfall: rising in all (10 years: +1.28 mm per day per decade, range +0.32 to +2.37).

## 12. Done-check
- [ ] Empty `noise.js`: slot hidden, page works. No request until the button is pressed; at most 3 (or 4) requests per place.
- [ ] Princeton: four rows, the 10-year row says "≈ No clear change", the others "▲ Rising", mixed sentence; bars shrink as the stretch grows; one shared scale and a dashed no-change line.
- [ ] "Show this on the chart" changes the answer to that stretch; the share link keeps `start`.
- [ ] Failures show the words above; place change resets; keyboard and 375 px fine; light and dark.

## 13. Built differently from the specification
- The mixed sentence names the stretch as "last 10 years" (the label without its years), so the sentence reads cleanly. If the full-record row failed, or the shortest and full verdicts are equal while a middle one differs, no sentence is shown (the templates do not cover those cases).
- Bars are drawn only when all replies are in (the shared scale needs every row); rows show their words and numbers as they arrive.
- Only valid replies are kept in memory; a failed stretch is requested again on "Try again". Requests run three at a time through a small queue.
- The stretches are worked out from the full record's period when it is known (kept replies), so the card stays after "Show this on the chart". A loaded answer with `end` set and no kept full record hides the card.
- Numbers use the page's formatter rules, including the non-breaking space between number and unit; the range shows the unit once, on the slope.
- The place label for "Show this on the chart" is the `label` of the last `td:load-end` place.
- Pure logic is between `/* PURE START */` and `/* PURE END */` in `noise.js`, tested by `tests/test_noise_js.py` (skipped without `node`).
