# 14 Facts, not advice (rework PR2b): the card states what the records show; no risk levels, no recommendations

Content: `docs/CONTRACTS.md` "Facts, not advice (owner, 2026-11-22)". The owner's words: "Remove both, state facts". Bhoomi is not a house-buying or investment tool. This file wins over `10-foundation.md` and `11-sea-level-future.md` where they differ. Every number below is from the local API on 2026-11-22. Pictures: §13.

## 0. What goes
1. The card's risk chip (`.where .risk`) and every chip rule (10 §3 "Risk chip", 10 §4 "Pin chip" and "Chips everywhere").
2. The "Our recommendation" box (`.advice` and its CSS).
3. The sidebar's pin chips. On the map: the risk classes (`.map-mk.high`, `.moderate`, `.low`), the `--mk-low` token, and the risk words in the selected tag and in each marker's `aria-label`.
4. The compare table's "× world, same years" and "Risk" columns.
5. Step 6's thresholds line ("1.5× or more: high risk. …").
6. In code: `riskShort`, `riskClass`, `riskOf`, `C.chip`, the `.risk` CSS. `chat.js` stops reading `risk_label` (§6).
7. Words that frame Bhoomi as a property tool. The sea-level question loses "build or invest". The no-gauge error loses "For property here, …". "Recommendation" leaves the empty card and the sidebar hint.
8. Step 6 and the compare caption stop printing `world.text` when `world.available` is false (rain's text still states risk levels: §12.3).

## 1. The answer card `#rec`: new order
```
.where    h2#rec-h {pin.label}                               (no chip)
          p.meta   {src} ↗ · {latest.text}                     (unchanged)
.verdict  ▲ Rising   {conf}                                    (unchanged)
p.say     {guidance.fact}                                      (takes {why}'s place)
p.world   the world line, §3                                   (only when §3 gives one)
.model    the model note                                       (unchanged)
.reads    R1 | R2 | R3                                         (unchanged)
.next     Where to look next: {look_next}                      (takes .advice's place, §4)
.acts     How we calculated this ↓                             (unchanged)
p.disc    {guidance.disclaimer}                                (now always, §5)
```
- `fact` sits right under the verdict line, in `{why}`'s slot and style (18 px `--ink`, line-height 1.45). It is printed as given, with `textContent`. Without `fact` (an answer cached before PR2b) it falls back to `meaning.headline`, as today.
- `fact` replaces the "Since 1993, the sea here has risen about 1.5 times as fast…" sentence, which said the same thing. Nothing else on the card repeats the ratio or the fact's years: the world line (§3) drops both.
- With the Units setting on inches or °F, a fact that holds mm, cm or °C ends " (in metric)." (`TDX.metric`, as step 6 does for `world.text`). Ratio-only facts have no unit and are unchanged.
- The rain note (`guidance.rate.note`, "about 70 mm more a year") no longer appears on the card; it was glued to `why`.
- The hottest-day card now has `.next` and `p.disc` too. A no-clear-change card looks like any other: same size and weight.

## 2. The words of `fact`
The stats lane writes them; the page never builds or edits them. The copy for each case is in §9. It assumes the two contract amendments in §12 (the range in the same sentence, no sign after the verb).

## 3. The world line `p.world`
15 px `--ink-2`, PR1's position and margins. It never repeats the fact's ratio or years.

| Answer | Line |
|---|---|
| Clear verdict, `world.ratio` ≥ 0 | "Over those years: here {here}, world {world}. World figure: {W} ↗" |
| Clear verdict, `world.ratio` < 0 | "Over those years: here {here}. World figure: {W} ↗" (the fact already gives the world's rate) |
| World rates but no ratio (no clear change, or a world figure that did not rise) | "Since {Y(world.window.start)}: here {here}, world {world}. World figure: {W} ↗" |
| `world.available` false, sea level or air temperature | `world.why_none` as given, no link |
| Rain, hottest day, water storage | no line |

- `{here}` and `{world}` come from `worldParts`, as today (signed, with unit and the Units setting).
- `{W}` is the link to `world.source.record_url` (https only, else plain text). Its text is "NASA satellite record" for sea level and "NOAA global land record" for air temperature, otherwise `world.source.name`. The link is 14 px `--ink-2`, underlined. This puts the world figure's source on the card; before, only step 6 had it.

## 4. Where to look next `.next`
- It sits after `.reads` and before `.acts`, with margin 0 0 18 px, in the slot the advice box had. No box, no rule, no fill.
- The label "Where to look next:" is 14 px `--ink-2`, regular weight, sentence case. Items are 15 px `--ink`, in contract order:
  - A `url` that starts with `https://` is a link, underlined, with the text "{label} ↗" (a no-break space before the arrow), `target=_blank rel=noopener`.
  - A `url` that is null or not https is plain text.
- Markup: `<div class="next"><span class="nl">Where to look next:</span> <ul><li>…</li></ul></div>`. Labels go in with `textContent`.
  - Card at least 520 px wide (container query, like `.reads`): label and items run as one line that wraps. Items are joined by a "·" in `--ink-2` with 8 px on each side, drawn by `li + li::before` so screen readers skip it.
  - Under 520 px: the label sits on its own line and each item is a row at least 44 px tall, with no separators.
- An empty or missing `look_next` means no `.next`.

## 5. Disclaimer
`p.disc` shows on every answered card whenever `guidance.disclaimer` is a string, the hottest day included. The style is unchanged (14 px `--ink-2`, hairline above). The text is printed as given.

## 6. Sidebar, map and small words
- Pin row: the name, then the pin line. The line is `fmt.rate(t)` when the verdict is rising or falling, otherwise "No clear change". There is no chip: the rate the line already shows is enough.
- Compare table "Rate" cell: the same rule as the pin line.
- Map: every pin marker looks the same, the current "moderate" look (`--mk-mod` fill, 2 px white border, 1 px `--ink` ring). The selected pin is 20 px with a 2 px ring, as today. The tag and the `aria-label` are `{label}` only.
- Words:
  - Sidebar hint: "Pin up to 6 places to compare. Click one to see what its records show."
  - Empty card: "Pin a place to see what its records show"
  - Sea-level question: "Is the sea rising where you live? Some tide gauges have measured it for more than a century."
  - No-gauge error (10 §9): "Without a usable tide gauge nearby, our records can't tell you about this coast." Then a `.next` line: "Where to look next: Your local planning office" (plain text).
- `chat.js` context: the selected pin is "{window} {rate}. {fact}" (without `fact`, the same with no risk words). Others: "Also pinned: {label} ({pin line}), …".

## 7. Step 6 "Compared with the world"
- The short answer is unchanged. The words are unchanged when there is a world figure. With `world.available` false, only `why_none` is printed and `world.text` is dropped (this supersedes 11 §11a "then `world.text`").
- The working:
  - Line 1 is unchanged: "5.0 ÷ 3.3 = 1.5× · 1.0 to 2.0 times (95% range) · January 1993 to April 2025 · {world.method}."
  - Line 2 replaces the thresholds. With a ratio of 0 or more: "1× is the same pace as the world; 2× is twice as fast." With a ratio below 0: "1× is the same pace as the world. Below 0, the change here went the other way." With no ratio: no line 2.
  - Sea level's full-record line and world-method line are unchanged.
- No step anywhere names a risk level or a threshold.

## 8. Compare table
- Columns: "Place", "Measured at", "Record", "Rate", "Here, same years", "Compared with the world". Headers are sentence case, 14 px `--ink-2`, regular weight, with no capitals or letter-spacing (review rule 5; they were 12 px capitals).
- "Compared with the world" holds two lines. Line 1 is 15 px ink and does not wrap from 600 px up (min-width 14em). Line 2 is 14 px `--ink-2`.

| Row | Line 1 | Line 2 |
|---|---|---|
| Clear verdict, ratio ≥ 0 | "{ratio}× ({range_kind} {ratio_low} to {ratio_high})": "1.5× (95% range 1.0 to 2.0)" | "world +3.3 mm a year" |
| Clear verdict, ratio < 0 | "Falling here, world rising" | "world +3.3 mm a year" |
| World rates, no ratio | none | "world +0.35 °C per decade" |
| No world figure | "—" | none |

- Ratios are printed as the API gives them (2 significant figures). "Here, same years" is unchanged ("+5.0 mm a year since 1993", or "—").
- A column whose every cell would be "—" is not shown (10 §7), so rain, hottest day and water storage lose both world columns.
- The caption is unchanged when there is a world figure. Otherwise it is "{label}: {why_none}", without `world.text`.
- Under 600 px: one block per place and no sideways scroll.
  - `thead` is visually hidden but kept for screen readers.
  - Each row is a block (padding 10 0 12 px) with a bottom hairline. The Place cell comes first, 16 px, weight 600.
  - Every other cell is a two-column grid: an 8.5em label, then the value as one element. The label is the column header, from a `data-label` attribute, 14 px `--ink-2`.
  - The selected row's block gets the `--bg` fill and 8 px side padding. Rows still select on click, Enter or Space.
  - Keep explicit roles (`table`, `rowgroup`, `row`, `columnheader`, `cell`), because Safari drops table semantics under `display: block`.

## 9. Exact copy per case (metric; the card shows `fact`, the world line, Where to look next, then the disclaimer)
| Case | `fact` | World line | Where to look next |
|---|---|---|---|
| The Battery, sea level, rising, with a ratio | "Rising about 1.5 times as fast as the world average (1993 to April 2025; 95% range 1.0 to 2.0 times)." | "Over those years: here +5.0 mm a year, world +3.3 mm a year. World figure: NASA satellite record ↗" | "Official flood maps (FEMA Flood Map Service Center) ↗ · Your local planning office" |
| Juneau, sea level, falling while the world rose | "Falling here, while the world average rose 3.3 mm a year over the same years (1993 to April 2025)." | "Over those years: here −15.0 mm a year. World figure: NASA satellite record ↗" | as The Battery |
| Mumbai, sea level, no world comparison | "Rising about 0.94 mm a year (1878 to 2024; 95% range +0.7 to +1.2 mm a year)." | "This gauge has fewer than 20 years of readings since 1993, so it is not compared with the world average." | "Your local planning office" |
| Chennai, rain (NASA POWER) | "Rising about 5.5% of the usual yearly rain every 10 years (1981 to 2025; 95% range +0.4 to +10.7%)." | none | "Your national weather service" |
| Delhi, hottest day (NASA POWER) | "Falling about 0.25 °C per decade (1981 to 2025; 95% range −0.48 to −0.02 °C per decade)." | none | "Your national weather service" |
| No clear change: Visakhapatnam, air temperature | "No clear change (1981 to 2025; 95% range −0.01 to +0.11 °C per decade)." | "Since 1981: here +0.05 °C per decade, world +0.35 °C per decade. World figure: NOAA global land record ↗" | "Your national weather service" |

The disclaimer has two forms. With a projection (all three sea-level rows): "This shows past measurements and IPCC projections, which depend on how much the world emits. It is not a prediction and not professional advice." Without one (the other rows): "This shows past measurements only. It is not a prediction and not professional advice."

## 10. States
- Loading, error and no pin are as in PR1, with the new words in §6. An error card has no `.next` and no disclaimer, except the no-gauge line in §6.
- `look_next` empty: no `.next`. A world `record_url` that is not https: `{W}` is plain text. No `disclaimer`: no `p.disc`.
- Sources disagree (the model note): unchanged. Each answer shows its own `fact`; nothing is merged.

## 11. Tokens and contrast (light; dark in brackets)
- No new colours. Deleted: `--mk-low`, the `.risk*` and `.advice*` rules. New classes: `.next`, `.next .nl`, `.cmp-tbl td.cw .l1/.l2`, all on existing tokens.
- Text: `--ink-2` on `--surface` 6.90 (8.67); on `--bg`, the selected table row, 6.37 (9.48). `--ink` on `--surface` 18.4 (15.5). Links are `--ink` or `--ink-2`, underlined, never colour alone.
- Borders and marks: `--control` 4.54 (5.14). The map marker's `--ink` ring on the basemap is at least 12 (12.6).
- "Built with AI assistance" stays in the top bar. Every number names its source: the records in `.meta`, the world figure in the world line (new), and IPCC AR6 in R3.

## 12. Needs from the stats lane (contract changes; not made here, the orchestrator decides)
1. **Uncertainty in the same sentence.** The templates for "no world ratio", rain, hottest day and no clear change carry no range. Proposal: add "; {range_kind} {headline_rate.range_text}" inside the brackets (the §9 copy assumes it). Without it the page still works and R2 shows the range one line lower. Juneau's fact has no range in either case: there is no field for the local rate's range since 1993.
2. **No sign after the verb.** The owner's rule (DESIGN.md §10, "Decided by Tarun"): in a sentence the verb gives the direction and the number has no sign. "{Rising|Falling} about {headline_rate.text}" prints "Rising about +0.94 mm", "Falling about −0.25 °C". Proposal: an unsigned number after the verb; the range keeps its signs.
3. **Rain's and water storage's `world.text` still state risk levels** ("Our rule: a change of 10% or more … is high; 5 to 10% is moderate."). The page stops printing it (§0.8), but the agent and MCP still pass it on. Proposal: drop the rule, and move "It covers total rain, not heavy downpours or floods." into `caveats`.
4. "Hottest day: the verdict sentence" is read here as the no-world template (Delhi in §9).

## 13. Pictures (design mocks: the current page served locally with no keys, its DOM edited; each is marked "Design mock")
Folder `~/Library/Application Support/Claude/side-session-notes/local_8b4caae1-79fa-4ffe-8a8c-6b359ae8ea6c/rework-facts-design/`:
- `01-battery-1440-light.png`, `02-battery-1920-light.png`, `03-battery-1440-dark.png`: the card, sidebar and map.
- `04-mumbai-1440-light.png`, `05-chennai-rain-1440-light.png`, `06-delhi-hottest-1440-light.png`: the card for each case.
- `07-compare-table-1440-light.png`, `08-compare-table-375-light.png`: the table.
- `09-battery-step6-1440-light.png`: step 6. `10-battery-card-375-light.png`: the card at 375 px.

## 14. Checks for QA (1440 and 1920, light first; then dark and 375)
- [ ] In every window's rendered text: no "risk", "recommend", "invest", "buy", "avoid", "High", "Moderate" or "Low" as a level, in the card, sidebar, map tags, marker labels, steps, table, CSV or Ask context.
- [ ] `fact` sits under the verdict, verbatim. No "Since 1993, …" sentence, and no other card text repeats the ratio.
- [ ] "Where to look next": links open their https URLs in a new tab; null URLs are plain text; under 520 px each item is a row at least 44 px tall.
- [ ] Disclaimer on every answered card, hottest day included; the projection wording only with a projection.
- [ ] Step 6 has no thresholds, and the rain and water-storage steps have no "Our rule". The table has six columns at 1440, blocks at 375, and no page side-scroll.
- [ ] Contrast as in §11. Keyboard reaches every link in `.next` and every table row.
