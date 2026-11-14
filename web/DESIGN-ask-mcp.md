# Ask box, connect page, verdict restyle (issue #6, part 2)

Builds on `web/DESIGN.md` after fix round 2 (sections 9 and 10 there, the review checklist and decisions, apply to everything here). Same rules: static files, no `innerHTML` (use `textContent`), no libraries, no CDN, no web fonts, no analytics, no external requests except `POST /api/ask`. Every printed number comes from our API, with its source link. "Built with AI assistance" label visible on every screen. Monochrome tokens from `style.css`; sentence-case labels; targets at least 48 px; no probability claims. Reference patterns (structure and wording only, nothing copied): Starlink, Moonlitt, Apple Weather, Linktree, Pinterest, Magnific, Twenty, Mintlify.

Header on both pages (new): a text link "Use in your AI" (trend page, to `/connect.html`) or "Back to the trend page" (connect page, to `/`), in the title row beside the h1, 48 px tall, `<nav aria-label="Main">`. The AI label stays visible; if the link pushes it to a second row at 375 px, check that the verdict number, range and source are still on screen on first load, and if not, shorten the lead line before anything else.

# Part 1. The question box

## 1.1 Where it sits
Directly after `#answer` and before `#more` (replace the hidden `#ask` slot, keep its id and move it). Reason: a first screen at 375 px must show the verdict. It is not above the chips. Discovery: the header gets no extra link; the box is the first thing after the chart. The place chips stay the main path.
```
375 px                           1280 px (container 960)
...verdict card                  verdict (360) | chart
...chart + legend                ----------------------------------
[Or ask in your own words]       [Or ask in your own words]  (full width, max 70ch text)
[textarea, 2 rows]               [textarea, 2 rows        ][Ask]
[Ask]  (full width)              [chip][chip][chip]
[chip] [chip] [chip] (stacked)   helper + privacy
helper, privacy                  [answer card]
[answer card]                    ...
```
Section: `<section id="ask" aria-labelledby="ask-h">`, plain bordered box (1 px `--line`, 8 px radius, 16 px padding, `--bg` fill) so it reads as secondary to the verdict card.

## 1.2 Words on screen (idle)
- h2: "Or ask in your own words"
- Label (14 px, grey, visible, tied to the textarea): "Your question"
- Placeholder: "Is sea level rising in Atlantic City?"
- Button: "Ask"
- Chips (real buttons; click fills the box and asks at once): "Is sea level rising in Atlantic City?" / "Is it getting hotter in Delhi?" / "Is it getting warmer in Princeton, New Jersey?"
- Helper (14 px, grey, `aria-describedby`): "Name a place and what to measure. We can say whether it changed over time. We can't forecast the future. Press Enter to ask; Shift+Enter starts a new line."
- Counter: shown only from 400 characters, "{n} of 500". Native `maxlength="500"`. Not a live region, except it is announced once at 450 and once at 500 through the shared status region: "50 characters left." / "Limit reached: 500 characters."
- Privacy line (14 px, grey, always visible): "Your question is sent to an AI model provider so it can be answered. Don't include personal details."

## 1.3 How an answer is shown
Two things appear, and they have different authority.
1. The page's own verdict card, chart and numbers (the normal flow) update from `tool_calls[]`. Take the first call named `detect_trend` whose `error` is null. Run the normal flow with its `arguments` (`variable`, `lat`, `lon`; `source` if present; `start`/`end` only if `/api/trend` accepts them, see Needs). The page fetches from our API again; it does not paint numbers out of `result` or out of the model's text. Controls update to match (chips unpressed unless the place matches a preset, measurement select set, hash written). Place name: the API `place.name`, else the preset name within 0.005°, else "the spot at {lat}, {lon}".
2. The model's text appears in an "AI answer card" in the ask section, under the box, marked as AI text. Plain text only: split on blank lines into `<p>`, no markup, no links.

AI answer card:
- Label (14 px, grey, with a small "AI" outline badge, `aria-hidden`; the words carry the meaning): "Written by an AI model ({model})". `model` is the response field as given.
- The text, 16 px, regular weight, in a `--surface` block with a 1 px dashed `--line` left border (dashed = not our calculation).
- Grey 14 px line, always, when a tool result ran: "The verdict, chart and numbers above are our calculation from public data. If this text reads differently from them, trust the card above." Then "Data: {source.name} ↗" using `result.source` (link only if `https://`).
- When the model text and the card could be read differently (any time, including a different place, period or variable than the question): the card wins, and the page adds a "What we looked up" row above the text: "We looked up {name} at {place}, {y0} to {y1}." built from the card's own fields, so a student sees at once what was actually measured. If more than one `detect_trend` call succeeded, add "The assistant checked {k} places. The card shows the first." (k from the count.)
- No tool call: no card update; under the text, grey line "No data was looked up for this answer, so treat any figures in it as unchecked."

Focus after a finished answer: with a tool result, to the verdict heading (as the existing flow, `tabindex="-1"`); without one, to the AI answer card's label line (`tabindex="-1"`). The status region (`role="status"`, in the ask section, always present) says "Answer ready." (with result) or "Answer ready. No data was looked up." Keep the user's text in the box in every case; the box is never cleared.

## 1.4 States (exact copy; errors use `role="alert"` inside the ask section, below the box; the old AI card is cleared whenever a new run starts)
| State | What shows |
|---|---|
| Idle | 1.2 |
| Asking | Button reads "Asking…" and is `aria-disabled` (not `disabled`, so focus stays); next to it a secondary button "Cancel". Status line (`role="status"`): "Reading your question and looking up the data. This usually takes about 5 seconds." Verdict card and chart stay as they were (dimmed, `aria-busy`), not replaced. |
| After 4 s | Status line becomes: "Still working. Some questions take up to a minute." |
| After 15 s | "This is taking longer than usual. You can keep waiting or cancel." (Cancel is already there; nothing new announced twice.) |
| Cancel | Aborts the request (`AbortController`). Box keeps the text. Status: "Cancelled. Your question is still in the box." Focus returns to the textarea. |
| Client stop at 150 s | Alert: "That took too long, so we stopped waiting. Try a shorter or simpler question." Button "Ask" again. |
| Empty submit | No request. Inline under the box (`aria-describedby`): "Type a question first." Focus to the textarea. |
| Answer with a tool result | 1.3. |
| Clarifying question (no tool call, text ends with "?") | AI card plus line: "To answer, add the missing detail to your question and ask again." Focus to the textarea (not the card), caret at the end, text kept. |
| Cannot answer (no tool call, text does not end with "?") | AI card plus: "We can answer whether something changed over time at a place. Try one of these:" and the three example chips again. |
| Tool error inside the answer (all `detect_trend` calls have `error`) | Page flow not run. AI card, then alert text: "We couldn't get the data for that: {error}" (verbatim) and "Try another place or measurement." If the error mentions a missing tide gauge, add "Tide gauges sit along US coasts." |
| 400 | Alert: the API `detail`, verbatim. Text kept. |
| 422 | "Something went wrong with that question. Please try again." |
| 429 | "Too many questions right now. Please wait {n} seconds and try again." with `n` from `Retry-After` (fall back to the `detail` text if the header is missing). Button reads "Ask again in {n}s" and counts down visually (not live); it becomes "Ask" at 0. |
| 502 | "The assistant could not be reached. Please try again." Button "Try again". |
| 503 | Hide the form, chips and privacy line. Show h2 plus: "Asking questions isn't available right now. You can still pick a place and a measurement above." Remember for the page session. |
| Network failure | "We can't reach the server. Check your connection and try again." Button "Try again". |
Errors never remove the verdict card of an earlier good run.

## 1.5 Accessibility
Textarea has a visible label and `aria-describedby` (helper, privacy, counter, inline error). Enter submits, Shift+Enter newline, the Ask button is also in tab order. Chips are buttons. One shared `role="status"` region for progress and "Answer ready."; one `role="alert"` for errors. Focus rules above. Targets at least 48 px. The AI label does not rely on colour. At 200% zoom the box stays one column.

## 1.6 Done-check for QA (375 and 1280, light and dark)
- [ ] First load: verdict number, range and source on screen at 375 px; the box is below the chart, not above.
- [ ] Chip "Is sea level rising in Atlantic City?" shows the busy state, then the verdict card matches the AI text's place, and the AI card is labelled "Written by an AI model".
- [ ] After 4 s and 15 s the status text changes; Cancel keeps the text.
- [ ] A forecast question shows the cannot-answer copy with three chips; "Which Springfield?"-type replies keep focus in the box.
- [ ] 400, 429 (seconds shown), 502, 503 (box hidden), offline each show the exact copy.
- [ ] No number in the AI card is the only place a number appears: every figure is also in the card above with its source link.

# Part 2. The connect page (`web/connect.html`, shares `style.css`)

## 2.1 Layout
Same header, footer and AI label as the trend page. One column, container 720 px.
```
[Trend Detective]        [Back to the trend page]   [Built with AI assistance]
h1 Use Trend Detective in your AI
lead
[1 Server address]  read-only field + Copy
[2 Pick your AI app] tabs ........... (375: 3 columns x 2 rows; >=600: one row)
   panel: numbered steps / server address field + Copy / "Official setup docs ↗"
[3 For developers]   JSON block + Copy
[What it can do]     3 rows: tool name | plain words        (375: stacked)
[Try asking]         3 example questions
footer (datasets named, AI label)
```
Section headings are h2. At 1280 the tool rows are two columns (name 200 px left, words right, hairline between rows), like Mintlify's calm rows. No sidebar.

## 2.2 Words on screen
- h1: "Use Trend Detective in your AI"
- Lead: "Connect an AI app to Trend Detective and ask it whether something is really changing at a place. The AI calls our tools. The trend, range and verdict are our calculation from public data, shown with their source."
- h2 "Server address". Field label: "Trend Detective server (MCP, no login)". Value: `https://trend-detective-six.vercel.app/mcp/` in a read-only `<input readonly>`, monospace system stack (`ui-monospace, Menlo, Consolas, monospace`), selects all on focus. Note: "This address is for AI apps. It is not a web page."
- h2 "Pick your AI app". Tabs, in order: "Claude", "Claude Code", "ChatGPT", "Cursor", "VS Code", "Others".
- Each panel, same layout, no steps written from memory:
  - h3 "Connect {client}"
  - Numbered list (`<ol>`, 2 to 4 items): placeholder text "Steps to be confirmed from the official docs." The frontend writes the real steps only after reading that client's current official documentation, and keeps each to one short sentence.
  - Field and Copy button (a second copy of the address; same label).
  - Link "{client} setup docs ↗" to that client's official page (frontend fills the URL from the official source; opens in the same tab; `https://` only). "Others" panel: text "Any app that supports remote MCP servers over streamable HTTP can use the address above." and a link "About MCP ↗" to the official MCP site.
- h2 "For developers". Intro: "Many apps read a config file. A typical entry looks like this. Field names differ between apps, so check your app's docs." Block (`<pre><code>`, `--surface`, 1 px `--line`, scroll-x inside the block only):
```
{
  "mcpServers": {
    "trend-detective": {
      "type": "http",
      "url": "https://trend-detective-six.vercel.app/mcp/"
    }
  }
}
```
  Button "Copy config". The frontend checks `type` against the docs and fixes this block if needed.
- h2 "What it can do" (three rows, name in monospace, words plain):
  - `list_variables`: "Lists what we can measure, such as air temperature and sea level, and where the data come from."
  - `get_series`: "Gets the month-by-month values for a place."
  - `detect_trend`: "Says whether it is changing at a place, how fast, and how sure we are, using the Mann-Kendall test and Sen's slope."
- h2 "Try asking" (plain list, not chips): "Is sea level rising in Atlantic City?" / "Is it getting hotter in Delhi?" / "Has anything changed at 17.69, 83.22 since 1981?" Note: "Your AI app may ask your permission before it calls a tool."
- Footer: AI label, "Only public data. Datasets are named next to each result.", and the two dataset links as on the trend page.

## 2.3 Tabs behaviour
- Pattern: `role="tablist"` with `aria-label="AI apps"`, tabs `role="tab"`, `aria-selected`, `aria-controls`, roving `tabindex` (open tab 0, others -1); panels `role="tabpanel"`, `aria-labelledby`, `tabindex="0"`. Left/Right (wrap), Home, End move focus and activate (automatic activation). Tab from the tablist goes into the panel.
- Open first: Claude. Deep link by hash: `#claude`, `#claude-code`, `#chatgpt`, `#cursor`, `#vscode`, `#others`. Hash on load selects the tab and scrolls the tabs into view; selecting a tab updates the hash with `history.replaceState` (no scroll jump). Unknown hash: Claude.
- JavaScript off: the HTML is already complete. All six panels show in order, each under its own h3 "Connect {client}", the field is a selectable read-only input, and the Copy buttons are `hidden` (JS unhides them and builds the tablist from the panels). Headings stay in the DOM when tabs are active but are visually hidden.
- Tab size 48 px min height, 16 px text, selected tab inverted (`--ink` fill, `--bg` text, plus weight 700, so not colour alone). 375 px: 3 columns by 2 rows grid, no horizontal scroll, 12 px gap.

## 2.4 Copy button
Visible text "Copy" (config block: "Copy config"). `aria-label` "Copy server address" / "Copy config", both contain the visible word. Uses `navigator.clipboard.writeText`. States: idle "Copy"; success "Copied" for 2 s then back (width fixed so it does not jump); failure "Copy failed" plus a line: "Select the text and copy it yourself." and the field text is selected. A single `role="status"` region on the page says "Copied the server address." or "Copied the config." Button is 48 px by 48 px minimum, beside the field on one row at all widths (field flexes).

## 2.5 Done-check for QA
- [ ] 375 px: no horizontal page scroll, tabs 3 by 2, every target 48 px, JSON block scrolls inside itself.
- [ ] 1280 px: one tab row, tool rows two columns.
- [ ] Arrow keys, Home, End switch tabs; `/connect.html#cursor` opens Cursor; reload keeps it.
- [ ] JS off: all six panels visible in order, no Copy buttons, no empty boxes.
- [ ] Copy shows "Copied" and the status text; the clipboard holds exactly the address.
- [ ] Header link goes both ways; AI label and sources visible; no steps invented (placeholders until docs are checked).

# Part 3. Verdict area and chart annotations (apply after fix round 2 lands)
Only what changes. The verdict sentence, the "Data: ... our calculation" line, 48 px targets, the two-row legend, `°C` all stay.

## 3.1 Verdict card (replaces the order in fix round B4; the card gets 4 blocks)
```
Our answer                         (14 px grey label)
[ ▲ Rising ]                       (inverted bar, as now)
+42.5 mm per decade                (big value: 36 px phone / 44 px desktop, weight 700, ink on surface)
{sentence 1, with the range in it} (16 px)
Data: {source} ↗. Trend, range and verdict: our calculation ...   (14 px grey, fix round D1)
{second paragraph}  {p-value explanation, no number}
---- fact rows (dl, label left, value right, hairline between, 48 px rows) ----
Period                                   1911 to 2026
Months of data                           1,383
Range of trends the data support         41.1 to 44.0 mm per decade
p-value                                  < 0.001
Seasons removed                          Yes
Adjusted for neighbouring months         Yes
Source                                   {source.name} ↗
Method                                   Mann-Kendall test with Sen's slope (our calculation)
---- caveats box ----
(i) Caveats
 - ...
```
- Big value: the API slope with sign (U+2212 for negative, "+" for positive) and unit, `°C` for `degC`, 1 decimal if |x| >= 1 else 2. For "no clear change" the big value is the same slope, with a second line in the same size and weight, not smaller: "No clear change" stays in the bar. Add under it a 14 px grey line: "The data lean up, but the range includes zero." (or down). Never colour.
- Fact rows are one `<dl>` inside the card; at 375 px the label and value stack if they do not fit on one line (value right-aligned when they fit). Remove the old "The numbers" section; its rows now live here. The p-value row shows "p < 0.001" style as in fix round. Keep the grey stats term only in the Range row label.
- Caveats box: fill `--bg`, 1 px `--line` border, 8 px radius, 12 px padding, inside the card, below the rows. Label "Caveats" 14 px grey with an "i" glyph in a circle (`aria-hidden`, drawn inline in SVG). Contents: `caveats` first, then series `notes`, verbatim, as a list. Empty: "No extra caveats from the source." The old separate "Caveats and notes" `<details>` goes away (the box is not collapsible).
- Source appears three times (calc line, Source row, chart footnote). That is deliberate; keep.

## 3.2 Chart
- Headline above the chart (h2-level text inside `figure`, 18 px weight 700): "{Name} at {place}: {slope} per decade, {y0} to {y1}" and under it the grey 14 px "Trend and range: our calculation." Same text, same numbers as the card.
- Panel B: the zero line becomes a dashed "no change" reference: 1.5 px, `--ink-2`, dash `6 4`, label "No change" at 12 px (scaled with the viewBox) right-aligned inside the plot 4 units above the line, with a `--bg` halo (`paint-order: stroke; stroke: var(--bg); stroke-width: 3px`) so it stays readable over data. It does not touch tick labels. Add to the legend, "Our calculation" row: dashed swatch, "No-change line".
- Info footnote directly under the legend note: an "i" glyph (`aria-hidden`) then 14 px grey text: "Raw values: {source.name} ↗. Trend and range: our calculation, the Mann-Kendall test with Sen's slope on monthly values with seasons removed." This replaces the "Raw values: ... Trend and range: our calculation" ending that fix round D3 adds to the caption (keep the caption's first sentence; keep the table caption ending).
- Partial or estimated data (Pinterest pattern): does not apply. We draw no estimated or projected data. Gaps stay breaks, with the existing note "Gaps in the line are months with no data." Dashes are reserved for the no-change line; the fan edges stay dotted (2 3). If a later data source adds estimates, add a dashed segment and a legend entry then.

## 3.3 Theme and tokens
Keep following the device setting (light or dark). Do not default to dark: a forced dark page breaks the students and teachers who print or use bright rooms, and the card style already reads calm in dark. No token changes. Contrast of what the restyle uses (computed from existing tokens): `--ink-2` on `--surface`: light #4A4A4A on #F4F4F4 8.1:1, dark #BDBDBD on #1A1A1A 9.3:1. Caveats box text `--ink-2` on `--bg`: 8.9:1 light, 10.4:1 dark. Box and row borders `--line` on `--surface`: light 4.1:1, dark 5.2:1 (needs 3:1). Code block `--ink` on `--surface`: 17.2:1 light, 15.6:1 dark. New sizes only: big value 36/44 px, chart headline 18 px, mono 14 px.

## 3.4 Done-check for QA
- [ ] At 375 px first load: bar, big value, sentence 1 (with range) and the source line on screen without scrolling.
- [ ] The Visakhapatnam card shows the same big value size and "No clear change" in the bar plus the lean line.
- [ ] Fact rows and caveats box present in light and dark; no ALL CAPS, no colour.
- [ ] The dashed "No change" line and label visible, not overlapping ticks; legend has the dashed swatch.
- [ ] Footnote under the chart names the source with a link and "our calculation".
- [ ] No separate "The numbers" or "Caveats and notes" sections remain.

# Needs from other lanes
- Backend: `/api/ask` has no field that says "this is a clarifying question"; the UI guesses from a trailing "?". A boolean `needs_clarification` would be better.
- Backend: do `/api/series` and `/api/trend` accept `start` and `end`? If not, the UI drops them and, when the model used a different period than the card shows, the "What we looked up" row shows the card's period (so the mismatch is visible). Ask for them if the agent often uses them.
- Backend: the 503 state is only found by asking. A flag (for example `ask_enabled` in `/api/variables` or the health route) would let the page hide the box before the first try.
- Backend: Vercel's function limit may be shorter than the 2 to 3 minute hard stop. The UI stops at 150 s; check the limit is not lower, or a 504 shows as "We can't reach the server."
- Frontend/docs: each client's real setup steps and docs URLs must be taken from official docs when the connect page is built. JSON key names (`type`, `url`) too.
- The model name and provider come from the response; the UI shows `model` only and never the provider.

# Decisions
## Decided by Tarun
- Visible "Built with AI assistance" label on every screen; every number names its data source with a link; no NASA logos or branding; only public data; monochrome tokens, no gradients.
- No external libraries, CDN, web fonts or analytics; static files only (project rules).
- He chose these references: Starlink, Moonlitt, Apple Weather, Linktree, Pinterest (results and chart honesty); Magnific (best fit), Twenty, Mintlify (connect page).
- The page asks in plain words first; no "X% chance it's real".
- Connect page lives at `/connect.html` (the path `/mcp/` is the server).

## Chosen by the agent (swappable)
- Ask box below the chart, not in the first screen; header link "Use in your AI".
- Textarea with Enter to submit; counter from 400; three example chips; chips ask at once.
- Model text in a dashed-left-border "AI answer card"; the page's own card is the authority, built by re-running the normal flow with the tool arguments.
- First successful `detect_trend` call drives the card; others only counted.
- Cancel available from the start; client stop at 150 s; 503 hides the form.
- Tabs wrap 3 by 2 at 375 px; Claude open first; automatic activation; JS-built tablist over complete HTML.
- Read-only field plus Copy at 48 px; config block labelled with a field-names warning.
- Verdict card order, big value 36/44 px, fact rows, caveats in a bordered box inside the card.
- "No change" dashed line in panel B; info footnote under the chart; no dashed partial-data segment.
- Follow device theme; no token changes.

# For Tarun's call
1. Where the question box sits. A: below the chart (this spec; the verdict stays on the first screen). B: a one-row bar at the very top above the place chips (more visible, pushes the verdict about 110 px down at 375 px).
2. The big number. A: word in the inverted bar, number below it in ink on grey (this spec). B: the number itself inside the inverted bar in large white-on-black type, with the word as a small label above it.
3. Theme. A: follow the device (this spec). B: always dark, calm like the space apps, with no light version.
