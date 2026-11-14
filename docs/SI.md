# Use of AI (SI) in Trend Detective

Space Apps allows SI tools if we say clearly where and how we used them. This file collects that.
Regenerate the PR list before submitting:

```bash
gh pr list --state merged --limit 100 --json number,title,body \
  --jq '.[]|"- #\(.number) \(.title): \(.body|split("\n")|map(select(startswith("SI used")))|join(" ")|ltrimstr("SI used: "))"'
```

## Tools
- **Claude (Anthropic), through Claude Code:** writes and reviews code, tests, docs, PR text and slides. Every AI-assisted commit has a `Co-Authored-By: Claude` trailer, and every PR ends with an `SI used:` line.
- **An LLM through OpenRouter:** the agent inside the app. It chooses tools and words the answer; the numbers come only from our tools.
- **Claude auto-fix workflow:** makes one attempt at fixing a failing CI check. Those commits come from `claude[bot]` and start with `fix(ci):`.

## What people did
Chose the problem and audience, chose the method (deseasonalize, then Mann-Kendall with Sen's slope) and the data sources, set the expected answers in `evals/cases.toml` from independent references (NOAA, published papers), tested the live site by hand (#17), and reviewed and merged every PR.

## Images, video, audio
- Slides and the demo video carry a visible "Built with AI assistance" label. So does the app UI.
- AI voiceover: `TBD`, either none, or named here and in the video's description and file metadata.

## Merged PRs (as of Sat 11:40)
- #1 ci: run gitleaks on pull requests only: Claude wrote this change.
- #7 feat: /api/health/keys key check: Claude wrote this endpoint and its test.
- #8 docs: README live URL, agent connect, team: Claude drafted this README update.
- #10 docs: auto-merge and self-fix rules in CLAUDE.md: Claude wrote this rule change.
- #11 ci: Claude auto-fix for failing PR checks: Claude wrote this workflow.
- #13 docs: run sheet for Sat/Sun: Claude drafted the run sheet from the published local event schedule.
- #14 docs: agent team for the build: Claude drafted the agent definitions, the orchestration playbook and the doc edits from Tarun's role list.
- #15 Hour 0: freeze contracts, set lanes, AI label rule: Claude drafted the contract edit, the plan and rule lines, and the PR text from Tarun's hour-0 decisions.
- #19 Lanes: Sairam on evals questions, human QA, story: Claude drafted these doc edits and the PR text from Tarun's lane decision.
