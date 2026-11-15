# Use of AI (SI) in Trend Detective

Space Apps allows SI tools if we say clearly where and how we used them. This file collects that.
Regenerate the PR list before submitting:

```bash
gh pr list --state merged --limit 100 --json number,title,body \
  --jq '.[]|"- #\(.number) \(.title): \(.body|split("\n")|map(select(startswith("SI used")))|join(" ")|ltrimstr("SI used: "))"'
```

## Tools
- **Claude (Anthropic), through Claude Code:** writes and reviews code, tests, docs, PR text and slides. Every AI-assisted commit has a `Co-Authored-By: Claude` trailer, and every PR ends with an `SI used:` line.
- **OpenAI Codex CLI:** drafted the demo video script (`docs/submission/video.md`) from a brief; Claude reviewed and edited it (#36).
- **Claude Slides and Claude Design (artifacts on claude.ai):** the pitch deck and a UI design study.
- **The agent inside the app:** Claude Haiku 5.5 (`anthropic/claude-haiku-5.5`) through OpenRouter. It is the default in `earthtrends/agent/loop.py`, and production sets `AGENT_MODEL=openrouter:anthropic/claude-haiku-5.5` (the owner's decision on 2026-11-15 UTC; a live answer that day names this model). It chooses tools and words the answer; the numbers come only from our tools. Production tried Gemini 3.8 Flash for about an hour on 2026-11-15 before that decision (`evals/results/2026-11-15-flash-check/`). `AGENT_MODEL` can still switch the model, so check the deployed value before submitting.
- **Reference checks:** Claude looked up the papers we cite for expected answers and validity claims in Crossref and PubMed (title, journal, and the abstract's figures where available) before they went into `evals/cases.toml`, the pitch or the project page. People decide which references to use.
- **Claude auto-fix workflow:** makes one attempt at fixing a failing CI check. Those commits come from `claude[bot]` and start with `fix(ci):`.

## Citations (APA 7th edition, format for generative AI)
Check each version against what was actually used on the day before submitting.

- Anthropic. (2026). *Claude Code* (Version 2.1.302) [Computer software; AI coding assistant using Claude Opus 5.5]. https://claude.com/claude-code
- Anthropic. (2026). *Claude Haiku 5.5* [Large language model]. Accessed through OpenRouter. https://openrouter.ai/anthropic/claude-haiku-5.5
- Anthropic. (2026). *Claude* (Slides and Design artifacts, Opus 5.5) [Large language model]. https://claude.ai
- OpenAI. (2026). *Codex CLI* (Version 0.162.1, model gpt-6.1-sol) [Computer software; AI coding agent]. https://github.com/openai/codex

In-text, for example: "The demo script was drafted with Codex CLI (OpenAI, 2026) and edited by the team."

## What people did
Chose the problem and audience, chose the method (deseasonalize, then Mann-Kendall with Sen's slope) and the data sources, set the expected answers in `evals/cases.toml` from independent references (NOAA, published papers), tested the live site by hand (#17), and reviewed and merged every PR.

## Images, video, audio
- Slides and the demo video carry a visible "Built with AI assistance" label. So does the app UI.
- AI voiceover: none planned; the video uses captions only. If an AI voice is added, name it here and in the video's description and file metadata.
- Screenshots in `docs/submission/screenshots/` are real captures of the live site, taken by Claude Code's built-in browser; nothing in them is edited.

## Merged PRs (as of Sat 19:15 EST)
- #1 ci: run gitleaks on pull requests only: Claude wrote this change.
- #7 feat: /api/health/keys key check: Claude wrote this endpoint and its test.
- #8 docs: README live URL, agent connect, team: Claude drafted this README update.
- #10 docs: auto-merge and self-fix rules in CLAUDE.md: Claude wrote this rule change.
- #11 ci: Claude auto-fix for failing PR checks: Claude wrote this workflow.
- #13 docs: run sheet for Sat/Sun: Claude drafted the run sheet from the published local event schedule.
- #14 docs: agent team for the build (orchestrator + 6 subagents): Claude drafted the agent definitions, the orchestration playbook and the doc edits from Tarun's role list (frontend, backend, data integration, UI/UX, reviewer, QA).
- #15 Hour 0: freeze contracts (optional source), set lanes, AI label rule: Claude drafted the contract edit, the plan and rule lines, and this PR text from Tarun's hour-0 decisions.
- #19 Lanes: Sairam on evals questions, human QA, story (Claude Pro): Claude drafted these doc edits and the PR text from Tarun's lane decision.
- #20 data: NASA POWER and NOAA CO-OPS fetchers, variable catalog: Claude wrote the POWER and CO-OPS fetchers, the catalog and the offline tests, trimmed the fixtures from saved raw responses and one live station-list fetch, and ran the live checks. After AI review and AI QA it added error-body handling, a gap-filled sorted CO-OPS axis, lat/lon coercion, strict date parsing and int-year support, each with tests.
- #21 stats: Mann-Kendall + Sen's slope with autocorrelation adjustment: Claude wrote the stats module (deseasonalizing, Mann-Kendall with tie correction, Sen's slope, the Hamed-Rao AR(1) correction and the Gilbert CI) and its synthetic-data tests, and ran the calibration check. After AI review and AI QA it added time sorting, the duplicate-time and length checks, shared value coercion and no -0.0, each with a test confirmed to fail on the old code.
- #22 evals: golden questions for the agent (part of #16): Claude wrote the case file, pulled NOAA's published sea-level trends to choose the expected verdicts, and picked literature references for GRACE; Sairam reviewed it.
- #23 story: draft pitch, project page and SI disclosure (part of #18): Claude drafted the pitch script, the project page text and SI.md from #18, #2 and the merged PRs' SI lines; Sairam reviews and rehearses it.
- #24 data: relabel air_temp_max as the hottest day of the month: Claude edited the catalog name, added the POWER note and wired it into the TimeSeries notes, wrote one offline test, and ran the test suite. AI review and AI QA checked it.
- #25 agent: MCP tools and /api routes over the data and stats lanes: Claude wrote the shared tool functions, the MCP tools and their docstrings, the API routes, error handling, cache header and static mount, plus the offline tests, and ran the live check. After AI review it added the `/mcp` redirect under the static mount, the 502 mapping for non-JSON upstream replies and the `health_keys` fix; AI QA then tested it on a local server.
- #26 evals: match variable ids to the data catalog (part of #16): Claude compared the eval cases with the data catalog and updated the variable ids; Sairam reviewed it.
- #27 ui: trend page (design and build): AI agents wrote the design spec, built the HTML, CSS and JS from it, reviewed the code four times, and tested the page in a real browser three times with screenshots.
- #30 agent: question-to-answer loop, Langfuse tracing, POST /api/ask with a rate limit: Claude Code wrote the agent loop, the OpenRouter provider and seam, the system prompt, Langfuse tracing, the `/api/ask` route and its offline tests, ran one live check, then made the reviewer's fixes and wrote the in-memory rate limiter with its tests. AI review and AI QA checked it.
- #32 ci: skip Vercel previews for story/* branches (workaround for #29): Claude wrote vercel.json and this PR text after Sairam asked for a way around the failing Vercel check; Sairam reviewed it.
- #33 docs: QA agent checks dark-theme contrast and avoids stale screenshots: Claude wrote the two added QA checks from lessons the project owner passed on from another app.
- #34 agent: time budget over tool calls, plain-text answers, per-client hourly cap: Claude agents wrote the code and tests, reviewed it four times, ran the offline suite and 17 live questions, and checked each answer's numbers against the tool result.
- #36 story: demo video script and pitch deck link (part of #18): OpenAI Codex (CLI) drafted video.md from a brief Claude wrote; Claude reviewed and trimmed it, built the 7-slide deck in a Claude Slides artifact, and pulled NOAA's published trend for the truth check; Sairam reviewed it.
- #37 agent: eval runner and Anthropic provider: Claude agents wrote the eval runner, the Anthropic provider and the tests, reviewed them three times, and ran the offline suite and a three-case live smoke run.
- #38 data: ERA5 and GHCN station sources for air_temp, air_temp_max, precip: Claude agents read the provider docs, probed the Open-Meteo and NCEI APIs live, wrote the two fetchers, the daily-to-monthly helper and the tests, reviewed the code three times, and tested the API, the MCP tools and the page live.
- #39 docs: Delhi demo uses hottest day of the month; judging section in the plan: Claude (orchestrator) edited the three documents from Tarun's decisions and the numbers the tool returned in PR #38's live check.
- #40 ui: three tabs (Explore, Ask, Use in your AI): AI agents wrote the three-tab design with every state's wording and the per-app steps from official documentation, built the HTML, CSS and JS from it, and checked the pure logic in node; Claude reviewer, QA and designer agents checked the diff over four rounds and measured the page in a browser over three; the orchestrator session wrote this description.
- #41 data: weather-station source: longer cold-call timeout, outages as 502: Claude agents read the API's error mapping, reworked the station source's timeouts, error types and row checks with tests, reviewed the code three times, and ran 160 live calls against a local server.
- #42 story: AI citations, refreshed SI list, live Delhi numbers (part of #18): Claude pulled the live Delhi trends from production, wrote the APA citations from the installed tool versions and code, regenerated the SI list and updated the pitch notes and slide; Sairam reviewed it.
- #44 agent: check every source and say when they disagree: Claude (backend agent) wrote the multi-source prompt rules, the parallel tool execution, the eval scoring, the digit-free failure reasons and the offline tests; Claude reviewer and QA agents checked the diff over seven rounds and ran about 30 live questions, checking every number against its tool result; the orchestrator session wrote this description.
- #45 evals: first model comparison results; plan: no feature freeze: Claude (orchestrator) ran the eval runner against nine models with the project's keys, committed its unedited output, and edited the plan from Tarun's correction.
- #47 data: in-memory series cache; station period notes: Claude (data-integrator agent) read Open-Meteo's pricing, terms and archive documentation and built the cache, the station period notes and the error wording with offline tests; Claude reviewer and QA agents checked the diff and compared cached, uncached and production answers; the orchestrator session wrote this description.
- #48 data: worldwide sea level from PSMSL tide gauges; error-text cap (contract change): Claude (data-integrator agent) read PSMSL's documentation, wrote the new source, the fallback, the two contract edits, the error-text cap and the offline tests, fetched the fixtures, and merged in the series cache; Claude reviewer and QA agents checked the diff over four rounds and compared live answers with PSMSL's own files and with production; the orchestrator session wrote this description.
- #49 story: project page numbers and screenshots (part of #18): Claude read the eval results, filled the project page numbers, took the production screenshots in the in-app browser and updated slide 6; Sairam reviewed it.
- #51 evals: Delhi inland sea-level case, Delhi heat case on air_temp_max (closes #46): Claude wrote the two cases from #46 and the #16 decision, ran them through the eval runner and traced the Delhi failure into #50; Sairam reviewed it.
- #52 story: Impact slide and real numbers in the pitch (part of #18): Claude wrote the Impact slide and script section from Tarun's points, filled the numbers from the eval results and live tool, and updated the deck; Sairam reviewed it.
- #53 ui: cosmetic fixes after the three tabs (select names, wrapped labels, doubled sentence): Claude (frontend agent) made the cosmetic fixes and design-document updates from the browser QA findings; Claude reviewer and QA agents checked the diff twice and measured the page in a browser at 12 widths; the orchestrator session wrote this description.
- #54 agent: agreeing sources named without their numbers; answers no longer cut off by the token cap: Claude (backend agent) rewrote the multi-source prompt rules, added the cut-off retry and the eval checks with their tests over four fix rounds; reviewer and QA agents checked each round; the orchestrator session found the production answer and wrote this description.
- #56 ci: auto-fix only for this repository's branches; actions pinned to commits; read-only token: Claude (orchestrator session) made the three workflow edits from the audit's findings and looked up the commit SHAs through GitHub's API; a Claude reviewer agent checks the diff next.
- #57 docs: rule for pull requests from forks: Claude (orchestrator session) wrote the added lines from the public-prep audit's finding.
- #58 ui: the owner's visual choices (1B 2C 3C 4B 5C), ready for water storage, 429 card: Claude (frontend builder agent) read the design note, the option patches and screenshots, then wrote the CSS, JS and markup changes and the design-doc updates; the orchestrator session wrote this description.
- #59 app: health-keys route off in production, rate limit on data routes and /mcp/, security headers: Claude (backend builder agent) read the app, limiter, MCP and web code and the Vercel docs, then wrote the production 404, the rate limit, the headers and the tests; the orchestrator session wrote this description.
- #60 data: land water storage from NASA GSFC GRACE mascons (contract change: grace source row): Claude (data builder agent) read the provider's page and files, wrote the offline build script, the run-time source, the tests and the contract edit, and ran the validity checks; Tarun approved the source and the wording of the notes; the orchestrator session wrote this description.
- #61 docs: Apache-2.0 licence, NOTICE, security policy and a public README: Claude (builder agent) read the code and docs, fetched the Apache licence text and each provider's credit page, wrote NOTICE, SECURITY.md and the README, made the pyproject, .gitignore and PLAN.md edits, and ran the lock, test, ignore and link checks; the orchestrator session wrote this description.
- #62 agent: when sources agree, the code writes the "agrees" sentence: Claude (backend agent) wrote the agree-case code in the agent loop, rewrote the prompt rule, updated the eval scorer and wrote the offline tests over four fix rounds; reviewer and QA agents checked each round; the orchestrator session wrote this description.
- #63 docs: README and NOTICE cover land water storage: Claude (orchestrator session) wrote the added lines from the reviewed GRACE pull request.
- #64 evals: GRACE cases runnable, Mumbai answered from PSMSL (part of #16): Claude Code (Opus 5.5) edited the cases, checked the Mumbai reference's title and journal on Crossref, and ran the three changed cases (3/3 passed); Sairam asked for it and reviewed it.
- #65 story: GRACE and worldwide tide gauges in the pitch, project page and SI (part of #18): Claude Code (Opus 5.5) checked the numbers on production, looked up the references in Crossref and PubMed, re-ran the evals and edited the docs and slides; Sairam asked for it and reviews it.
- #66 ui: no minus or plus sign after a direction word in the answer sentence: Claude (frontend builder agent) edited the sentence builder in `web/app.js` and the design notes and ran the checks; the orchestrator session wrote this description.
- This PR, story: final pitch, video script, project page and SI for the new demo flow (part of #18): Claude Code (Opus 5.5) ran the demo questions on production, rewrote the pitch and video script around Tarun's demo flow, took the new screenshots in its built-in browser, finished the project page and this list, and updated the slides; Sairam asked for it and reviews it.
