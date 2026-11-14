# Three tabs: Explore, Ask, Use in your AI (issue #6, part 2, revised 2026-11-14)

Builds on `web/DESIGN.md` (sections 6 tokens, 9 checklist and 10 decisions apply to everything here). Same rules: static files, no `innerHTML` (use `textContent`), no libraries, no CDN, no web fonts, no analytics, no external requests except same-origin `/api/...`. Every printed number comes from our API with its source link. "Built with AI assistance" stays visible in header and footer on every tab. Monochrome tokens from `style.css`, no new colours, no token changes. Sentence-case labels, targets at least 48 px, no probability claims. Reference patterns (structure and tone only, nothing copied): Magnific, Twenty, Mintlify (connect), Starlink, Moonlitt, Apple Weather, Linktree, Pinterest (results). Theme follows `prefers-color-scheme`; there is no theme switch.

# 1. Tab bar and URLs

## 1.1 Layout
Directly under the header (title row, AI label), above everything else. Not sticky. One file `index.html`; no `connect.html`.
```
375 px: [ Explore | Ask | Use in your AI ]   grid 1fr 1fr 1.5fr, labels may wrap to 2 lines, 48 px min height, no side scroll
1280 px: same bar, left-aligned, each tab auto width with 24 px side padding, container 960
```
- Tab: 16 px, regular; selected tab inverted (`--ink` fill, `--bg` text) and weight 700 (not colour alone); unselected `--bg` fill, 1 px `--line` border, `--ink` text. Radius 6. 12 px gap.
- Header lead line "Is it really changing here? Pick a place and a measurement." moves into the Explore panel (top). Header keeps h1 and AI label only.
- Panels: three `<div role="tabpanel" id="panel-explore|panel-ask|panel-connect">` in the same order as tabs. Hidden panels use `hidden`, never removed (the Ask thread and Explore result survive tab switches). Each panel starts with an h2: Explore "Is it really changing here?" (existing lead), Ask "Ask a question", Use in your AI "Use Trend Detective in your AI".
- Skip link text "Skip to the content"; its href points at the active panel's h2 (JS updates it).
- Document title: "Trend Detective" / "Trend Detective: Ask" / "Trend Detective: Use in your AI".

## 1.2 Behaviour (standard tabs pattern, automatic activation)
`role="tablist"` `aria-label="Sections"`; tabs `role="tab"`, `id="tab-…"`, `aria-selected`, `aria-controls`, roving `tabindex` (selected 0, others -1). Left/Right wrap, Home/End jump; moving focus activates. Tab from the tablist enters the panel (panels `tabindex="0"` only if they hold no focusable child; here they do, so no tabindex). Screen readers hear "Explore, tab, 1 of 3, selected".
Without JS: the three panels stack in order, each under its h2; the tablist is built by JS.

## 1.3 URL scheme (hash only; old links keep working)
- Explore: the existing `#variable=air_temp&lat=17.69&lon=83.22` (optional `&source=`). No `tab` key written for Explore, so every old link is unchanged. Missing or unknown `tab` means Explore.
- Ask: `#tab=ask`. Connect: `#tab=connect`, with app sub-tab `#tab=connect&app=claude|claude-code|chatgpt|cursor|vscode|other` (default `claude`; unknown value: `claude`).
- A hash with `tab=` and also `variable/lat/lon`: tab wins for what is shown; Explore state is still loaded.
- Switching tabs by click or key uses `history.pushState` (new entry). Choosing an app sub-tab uses `replaceState`. Explore's own hash writes stay as built (replace). `hashchange`/`popstate` re-select the tab, so Back returns to the previous tab with its state; the Ask thread is in memory so it survives Back/Forward within the page.
- Switching tab does not scroll; it moves nothing but focus rules in 1.2. A programmatic switch (the "Show on chart" link) pushes the Explore hash and runs the normal Explore flow, then focuses the verdict heading.

# 2. Ask tab (chat thread)

## 2.1 Layout (column max 720 px, left-aligned at 1280; same order at both widths)
```
h2 Ask a question
lead + privacy line (always visible)
[Go to the question box]   (link, only when the thread has 3+ answers; 375 px only)
thread (plain page flow, no inner scroll box): You / AI blocks, oldest first
status line (role=status)
composer: label, textarea (2 rows), [Ask] (full width at 375, beside the box at 1280)
helper + counter
```
- No sticky element. The composer sits after the last message in normal flow, so nothing covers content. On a long thread at 375 px the page just scrolls; the "Go to the question box" link (48 px, jumps to the textarea) is the shortcut. No nested scrolling.
- After sending: the new "You" block and the "Asking" block appear and the page scrolls so the new You block is at the top of the screen (instant if `prefers-reduced-motion`, else smooth is allowed). When the answer arrives the page does not jump; focus moves to the answer's label line (`tabindex="-1"`), which brings it into view.
- User block: 1 px solid `--line`, radius 8, padding 12, fill `--bg`, 14 px grey label "You", text 16 px.
- AI block: fill `--surface`, 1 px dashed `--line` left border (dashed = not our calculation), padding 12 to 16, 14 px grey label "Written by an AI model ({model})" with a small "AI" outline badge (`aria-hidden`), then text in `<p>`s (split on blank lines, plain text only, no links, no markup, 16 px).
- Thread container `role="log"` `aria-label="Conversation"`; new blocks are appended, not re-rendered. The "Asking" block has `role="status"` text; answers are not announced twice (the log announces the block; the status line only says the short phrases below).
- Thread lives in the browser tab only. Visible always, grey 14 px, under the lead: "Your conversation stays in this browser tab. Reloading clears it. Nothing is saved on our server."

## 2.2 Words on screen (idle)
- Lead (16 px): "Ask about a place in your own words. We look up public data and tell you whether it changed over time. We can't forecast the future."
- Privacy (14 px grey): "Your question is sent to an AI model provider so it can be answered. Don't include personal details."
- Textarea label (14 px grey): "Your question". Placeholder: "Is sea level rising in Atlantic City?". Button "Ask". Native `maxlength="500"`; counter "{n} of 500" from 400 characters (announced once at 450 and at 500 through the status line: "50 characters left." / "Limit reached: 500 characters."). Enter sends, Shift+Enter new line. Helper: "Press Enter to ask. Shift+Enter starts a new line."
- Empty state (no messages): the thread area shows "Try one of these:" and four example buttons (real `<button>`s, 48 px, full width at 375, wrap on desktop; click sends at once): "Is sea level rising in Atlantic City?" / "Is it getting hotter in Delhi?" / "Is it getting warmer in Princeton, New Jersey?" / "Has anything changed at 17.69, 83.22 since 1981?". After the first message the buttons are replaced by the follow-up hint under the last answer: "Ask a follow-up, for example: \"What about Delhi?\"". Hint is plain text, not a button.
- Until the history PR: after the first answer, grey 14 px line above the composer: "For now each question is answered on its own. Name the place again in a follow-up."

## 2.3 The API call (`POST /api/ask`, same origin)
- Request today: `{"question": string}` only (server rejects unknown fields with 422, so never send more). Trimmed, 1 to 500 characters.
- Request after the history PR (arrives with the history PR): `{"question": string, "history": [{"role": "user"|"assistant", "content": string}, ...]}`; at most 6 messages, oldest first, user then assistant alternating, assistant `content` = the answer text shown, with a total character cap set by the backend. One constant in `app.js` (`ASK_HISTORY = false`, `HISTORY_MAX_MSGS = 6`, `HISTORY_MAX_CHARS` = the backend's number) switches it on; the page drops oldest messages until both limits hold, and sends no history for the first question. Errors, cancelled turns and "could not finish" answers are not put in history. Until the flag is on, the line in 2.2 shows.
- Response fields used: `answer` (text), `model`, `tool_calls[]` (`name`, `arguments`, `result`, `error`), `latency_s`, `trace_id`. `usage`, `provider` and `cost_usd` are never shown. Show nothing about cost.
- Answers are plain text, about 120 words at most; no truncation by the page.

## 2.4 What an answer block holds
1. Label line (see 2.1).
2. The text.
3. When any `detect_trend` call succeeded (first one with `error` null; `result` has `place`, `period`, `variable`, `source`): a grey 14 px line "Looked up: {variable name} at {place}, {y0} to {y1}." (name from the loaded catalog by `result.variable`; years = first 4 characters of `period.start/end`; place = `result.place.name` else "the spot at {lat}, {lon}"). If more than one succeeded: add "The assistant checked {k} places. The first is shown here."
4. Source link on its own 48 px line: "Data: {result.source.name} ↗" (link only if `https://`, opens in the same tab). Required whenever the answer used data.
5. Grey 14 px: "The AI wrote the text above. The trend, range and verdict are our calculation from public data. To see them, open the chart." Followed by the link "Show on chart" (48 px) that goes to Explore with that place and variable (and `source` if the result has `source.id`): sets hash `#variable=..&lat=..&lon=..&source=..` (2 decimals), switches tab (see 1.3).
6. No tool call at all: grey 14 px line "No data was looked up for this answer, so treat any numbers in it as unchecked." No source line, no "Show on chart".
Every number in the AI text must also be checkable: the "Show on chart" card carries the verdict with the source. Never colour; never "X% chance".

## 2.5 States (exact copy; errors in the AI block position, `role="alert"`, 14 px bold text on `--bg` with 1 px `--line` box; the failed question stays in the thread and its text is put back in the box)
| State | What shows |
|---|---|
| Health off (`/api/health` returns `"ask": false`, or a 503 on send) | Composer, examples and privacy line hidden. Panel shows: "Asking questions isn't available right now." and "You can still pick a place and a measurement." with button "Go to Explore". Remembered for the page session. If `/api/health` itself fails, treat as on and let the send decide. |
| Empty | 2.2 |
| Sending | You block added. AI block shows "Reading your question and looking up the data. This usually takes 4 to 15 seconds." Button "Asking…" (`aria-disabled`, focus stays) plus a "Cancel" button (48 px). Textarea is read-only and keeps its text until the answer arrives, then clears. |
| After 15 s | Text becomes "Still working. Some questions take up to a minute." Announced once. |
| Cancel | Aborts (`AbortController`). Block says "Cancelled." Text returns to the box, focus to the textarea. |
| Stop at 150 s | "That took too long, so we stopped waiting. Try a shorter or simpler question." Button "Ask" ready. |
| Answer | 2.4. Box clears and focus goes to the answer label line. Status: "Answer ready." |
| Clarifying question (no tool call, text ends with "?") | Normal answer block without the "No data was looked up" line, plus "Answer in the box below to continue." Focus goes to the textarea (empty). If history is off, this line reads "Answer in the box below. Name the place and what to measure again." |
| Declined (no tool call, text does not end with "?") | Answer block with the no-data line, then "We can tell you whether something changed over time at a place. Try one of these:" and the four example buttons again. |
| "Could not finish" (answer starts with "Sorry, I could not finish") | Normal block plus "Try a shorter question, or pick a place on the Explore tab." and the button "Go to Explore". Not added to history. |
| All `detect_trend` calls have `error` | Text block plus "We couldn't get the data for that: {error}" (verbatim) and "Try another place or measurement." If the error mentions a tide gauge add "Tide gauges sit along US coasts." |
| 400 | The API `detail`, verbatim. |
| 422 | "Something went wrong with that question. Please try again." |
| 429 | "Too many questions right now. Please wait {n} seconds and try again." (`n` from `Retry-After`; if missing use `detail`). The limit is 10 a minute and 30 an hour per person; for waits over 90 seconds say "about {m} minutes". Button reads "Ask again in {n}s", counts down visually (not live), becomes "Ask" at 0. Text stays in the box. |
| 502 | "The assistant could not be reached. Please try again." Button "Try again" (same question). |
| Network failure | "We can't reach the server. Check your connection and try again." Button "Try again". |
Errors never remove earlier messages. "Try again" resends the same question and moves focus to the new block's label.

## 2.6 Keyboard and screen readers
Textarea has a visible label and `aria-describedby` (helper, privacy, counter, inline error). Tab order: tab bar, panel h2 area links, thread links, example buttons or "Go to the question box", textarea, Ask, Cancel (only while sending). The thread is `role="log"`; labels ("You", "Written by an AI model") are real text so screen readers hear who spoke. The "AI" badge is `aria-hidden`. "Empty submit": no request; inline "Type a question first." and focus to the textarea. At 200% zoom everything stays one column.

## 2.7 QA checklist (375 and 1280, light and dark)
- [ ] The three tabs fit at 375 px, no horizontal scroll, each at least 48 px; Left/Right/Home/End work; `#tab=ask` opens Ask; an old `#variable=air_temp&lat=17.69&lon=83.22` link still opens Explore with that place; Back returns to the previous tab.
- [ ] Ask with `"ask": false` health shows the off message and "Go to Explore".
- [ ] Example button sends at once; sending shows the exact text, Cancel keeps the question in the box.
- [ ] A sea-level answer shows label with model, text, "Looked up" line, a "Data: … ↗" link and "Show on chart" that opens Explore with the same place and variable.
- [ ] A forecast question shows the declined copy with four buttons; "Which Springfield?" keeps focus in the box.
- [ ] 400, 422, 429 (seconds counting down), 502, 503, offline each show the exact copy; reload clears the thread; thread text states that in one line.
- [ ] 8 questions at 375 px: nothing sticky, composer reachable by the jump link, no inner scroll box.
- [ ] Until `ASK_HISTORY` is on: the request body is exactly `{"question": ...}`.

# 3. Use in your AI tab

## 3.1 Layout (column max 720 px)
```
h2 Use Trend Detective in your AI
lead
Server address: read-only field + Copy
Pick your AI app: tabs (375: 3 columns x 2 rows; >=600: one row)
   panel: h3, numbered steps, address field + Copy, "{App} setup docs ↗", "Checked {date}" (grey 14 px)
For developers: JSON block + Copy config
What you can ask once connected: 3 tool rows + example questions
What it can and can't do
```
These app tabs are a second tablist inside the panel (`aria-label="AI apps"`), same pattern as 1.2, 48 px, selected inverted. Order: Claude, Claude Code, ChatGPT, Cursor, VS Code, Other. Without JS all six panels show stacked.

## 3.2 Words on screen
- Lead: "Connect an AI app to Trend Detective and ask it whether something is really changing at a place. The AI calls our tools. The trend, range and verdict are our calculation from public data, with the source named."
- Address field label: "Trend Detective server address". Value `https://trend-detective-six.vercel.app/mcp/` in an `<input readonly>`, `ui-monospace, Menlo, Consolas, monospace` 14 px, selects all on focus. Note: "This address is for AI apps. It is not a web page. It needs no key and no sign-in." The field appears once at the top and again in each app panel (same label).
- Copy button: text "Copy"; `aria-label` "Copy server address" (config: "Copy config"). Success: "Copied" for 2 s (fixed width); failure: "Copy failed" plus "Select the text and copy it yourself." and the text is selected. One `role="status"` says "Copied the server address." or "Copied the config." Button 48 x 48 minimum, beside the field.
- What it can and can't do (h2 "What it can and can't do"): "It can read public climate data from the sources named next to each result. It can't see your files, your chats or anything else on your device, and it can't change anything. It only reads."

## 3.3 Per-app steps (current official docs, checked 2026-11-14; the frontend prints each date as "Checked 14 November 2026" next to the link)
All six use the same address. Write each step as one short sentence.

**Claude** (claude.ai and Claude desktop). Docs: https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
1. Open Customize, then Connectors.
2. Click "+ Add", then "Add custom connector".
3. Enter the name "Trend Detective" and paste the server address, then click "Continue".
4. Under Authentication choose "No sign in", then click "Add".
5. In a chat, click "+" at the lower left, then "Connectors", and switch Trend Detective on.
Note under the steps: "Free plans can add one custom connector. On Team and Enterprise plans an owner has to add it." Wording of step 4 follows the doc's three choices ("Sign in now", "Sign in when needed", "No sign in").

**Claude Code** (terminal). Docs: https://code.claude.com/docs/en/mcp
1. In your terminal run the command in the box: `claude mcp add --transport http trend-detective https://trend-detective-six.vercel.app/mcp/`
2. Start Claude Code and type `/mcp`. Trend Detective should show as connected.
3. Optional: add `--scope user` to the command to use it in every project.
The command has its own Copy button ("Copy command"). `claude mcp list` also shows it.

**Cursor**. Docs: https://cursor.com/docs/context/mcp
The docs say to manage servers from the Customize page and to put custom servers in an `mcp.json` file; they give no menu path for entering a URL. So:
1. Create or open `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project).
2. Paste the entry from "For developers" below, using `url` and no `type` (Cursor's remote example has no `type`).
3. Open Customize and check that Trend Detective is listed and on.
Menu names for adding a server in the app were not confirmed; do not invent them.

**VS Code** (with GitHub Copilot). Docs: https://code.visualstudio.com/docs/copilot/customization/mcp-servers and https://code.visualstudio.com/docs/agents/reference/mcp-configuration
1. Open the Command Palette and run "MCP: Add Server".
2. Choose "HTTP (HTTP or Server-Sent Events)" and paste the server address.
3. Name it "trend-detective", then choose Global (or the workspace if you prefer).
4. Accept the trust prompt after reading it, then ask Copilot a question and look for Trend Detective's tools.
Or put the VS Code block from "For developers" in `.vscode/mcp.json`. VS Code uses `servers`, not `mcpServers`.

**ChatGPT**. Docs: https://developers.openai.com/api/docs/guides/developer-mode (the page the older developer-mode address now redirects to)
Only partly confirmed. The page describes adding a custom MCP server as a plugin on the web version; it does not state which plans can do it, and the page text we could read did not mention "developer mode". Show:
1. Open ChatGPT on the web and go to chatgpt.com/plugins.
2. Click the plus button, then "Add custom MCP server".
3. Enter the name "Trend Detective" and the server address.
4. Set authentication to "No authentication", accept the risk notice, and click "Create as a plugin".
5. Install it, then type `@` in a chat and pick Trend Detective.
Grey note: "ChatGPT's setup changes often and may depend on your plan. If these steps don't match your screen, use the docs link." QA or the frontend should recheck this tab against the live page before launch.

**Other.** "Any app that supports remote MCP servers over streamable HTTP can use the address above. Look for a setting called MCP servers, connectors or tools, choose \"HTTP\" or \"streamable HTTP\", paste the address, and choose no authentication." Link "About MCP ↗" to https://modelcontextprotocol.io (official site; the designer did not fetch it).

## 3.4 Config blocks (developers)
Intro: "Many apps read a config file. Field names differ between apps, so match yours." Three `<pre><code>` blocks in a small tab set "Claude Code" / "Cursor" / "VS Code" (same tab pattern, 48 px), each with "Copy config"; block `--surface`, 1 px `--line`, 14 px mono, scrolls sideways inside itself only.
Claude Code, project `.mcp.json` (docs show `"type": "http"`; Claude Code needs it, otherwise it treats a url-only entry as a stdio server):
```
{ "mcpServers": { "trend-detective": { "type": "http", "url": "https://trend-detective-six.vercel.app/mcp/" } } }
```
Cursor `mcp.json` (no `type`):
```
{ "mcpServers": { "trend-detective": { "url": "https://trend-detective-six.vercel.app/mcp/" } } }
```
VS Code `.vscode/mcp.json`:
```
{ "servers": { "trend-detective": { "type": "http", "url": "https://trend-detective-six.vercel.app/mcp/" } } }
```
Format them on several lines in the page; the above is shown on one line only to save space.

## 3.5 What you can ask once connected
h2 "What you can ask once connected". Three rows (name monospace left 200 px, plain words right; stacked at 375; hairline between rows):
- `list_variables`: "Lists what we can measure, such as air temperature and sea level, and where the data come from."
- `get_series`: "Gets the month-by-month values for a place."
- `detect_trend`: "Says whether it is changing at a place, how fast, and how sure we are, using the Mann-Kendall test and Sen's slope."
Then "Try asking" (plain list): "Is sea level rising in Atlantic City?" / "Is it getting hotter in Delhi?" / "Has anything changed at 17.69, 83.22 since 1981?" Note: "Your AI app may ask your permission before it calls a tool."

## 3.6 QA checklist
- [ ] 375 px: tabs and app tabs have no horizontal scroll; every target 48 px; JSON block scrolls inside itself.
- [ ] `#tab=connect&app=cursor` opens Cursor's panel; reload keeps it; arrow keys, Home, End switch app tabs.
- [ ] JS off: three panels and six app panels show in order; no Copy buttons, no empty boxes.
- [ ] Copy puts exactly the address (or command, or JSON) on the clipboard and shows "Copied" plus the status text.
- [ ] Each app panel has its docs link and "Checked" date; Cursor and ChatGPT carry their caveat notes; no menu name appears that is not in section 3.3.
- [ ] "What it can and can't do" is present; AI label and data sources visible.

# 4. Explore changes (frontend builds these with the tabs)
1. "No clear change", range fully above or below zero but p at least 0.05. Second paragraph replaces "too small or too noisy": "The 95% range ({lo} to {hi}) stays {above|below} zero, but the p-value is {p}, which is not below 0.05. We go by the stricter test, so we don't call this a clear change. Treat it as a hint, not a finding." (Keep the old wording only when the range includes zero.) The headline stays "≈ No clear change".
2. When the place or measurement changed and a new request runs: hide the old verdict and chart and show the grey placeholder block with "Looking up the data…". Keep the dimmed old card (`aria-busy`) only for "Try again" on the same request.
3. The ▸ / ▾ disclosure markers (`.mark`) are 16 px, in `--ink-2`, in a 24 px box.
4. Closed measurement select at 375 px shows a short name (catalog `name` without the parentheses, e.g. "Air temperature"); the open list keeps full names. Select max-width 480 px on desktop.
5. Chart legend: one item per row at 375 px, two-column grid from 600 px; item text 14 px, the same as other labels.
6. Vertical rhythm 24 px between the source link, legend, readout and caption at 375 px. The readout uses the caption style (14 px, `--ink-2`). The line "Raw values: {source} ↗. Trend and range: our calculation, the Mann-Kendall test with Sen's slope on monthly values with seasons removed." is 14 px grey and sits under the caption.
7. Sentence 1 leads with the period and holds the uncertainty: rising "From {y0} to {y1}, {name} at {place} rose about {slope} per decade, and the data support a range of {lo} to {hi}." falling "From {y0} to {y1}, {name} at {place} fell about {slope} per decade, and the data support a range of {lo} to {hi}." no clear change "From {y0} to {y1}, we can't tell {name} at {place} apart from no change: the data lean {up|down} about {slope} per decade, but the range runs from {lo} to {hi}." (Number rules as in DESIGN.md section 3.) The second paragraph and p-value line stay.
8. Label size: see "For Tarun's call" 2.
9. Verdict restyle that is still wanted, from the earlier plan (the build did none of it): big value under the inverted bar (36 px phone / 44 px desktop, weight 700; the slope with sign and unit; for no clear change the same size plus grey line "The data lean up, but the range includes zero."); fact rows as one `<dl>` inside the card (Period, Months of data, Range of trends the data support, p-value, Seasons removed, Adjusted for neighbouring months, Source ↗, Method), 48 px rows, hairline between; caveats in a bordered box inside the card (`--bg`, 1 px `--line`, radius 8, padding 12, label "Caveats"); the separate "The numbers" and "Caveats and notes" sections go. Chart: headline above it (18 px bold) "{Name} at {place}: {slope} per decade, {y0} to {y1}" with grey "Trend and range: our calculation."; the panel B zero line becomes a dashed "No change" line (1.5 px, `--ink-2`, dash 6 4, 12 px label with a `--bg` halo, legend entry "No-change line"). Contrast: all from existing tokens (see DESIGN.md section 6; `--ink-2` on `--surface` 8.1:1 light, 9.3:1 dark; `--line` on `--surface` 4.1:1 light, 5.2:1 dark, both above 3:1).

# 5. Needs from other lanes
- Backend: `history` field on `/api/ask` (at most 6 messages, character cap number to share with the page), and `extra="forbid"` means the page must not send it before then.
- Backend: a boolean `needs_clarification` in the `/api/ask` response would replace the trailing-"?" guess.
- Backend: confirm the Vercel function time limit is above the 150 s client stop, or a 504 shows as "We can't reach the server."
- Frontend: re-read each app's docs before launch (dates in 3.3 will age); ChatGPT steps need a live check.

# 6. Decisions (full lists in `web/DESIGN.md` section 10)
Chosen by the agent here: hash `tab=` key and Explore keeping a key-less hash; push for tab changes, replace for app sub-tabs; tab bar not sticky and one grid at 375; panels kept in the DOM; chat in normal page flow with no inner scroll and a jump link; examples as buttons only when empty; "Show on chart" opens Explore instead of changing it silently; send no `history` until the PR; 150 s stop; Cancel from the start; per-app steps and docs links in 3.3; two or three config blocks in tabs; "Checked" date beside each docs link.

# For Tarun's call (the frontend builds the default)
1. ChatGPT tab. Default: show the steps from the official page with a "may differ on your plan" note. Alternative: drop the ChatGPT tab for now and let ChatGPT users use "Other" until someone checks it on a live account.
