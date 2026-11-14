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
- **The agent inside the app:** Claude Haiku 5.5 (`anthropic/claude-haiku-5.5`, the default in `earthtrends/agent/loop.py`) through OpenRouter, or the Anthropic API directly. It chooses tools and words the answer; the numbers come only from our tools. Production can switch it with `AGENT_MODEL`, so check the deployed value before submitting.
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
- AI voiceover: `TBD`, either none, or named here and in the video's description and file metadata.

## Merged PRs (as of Sat 15:10)
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
