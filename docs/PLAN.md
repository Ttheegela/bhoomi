# Run sheet: Sat Nov 14 to Sun Nov 15

Venue: Princeton Public Library, Tech Center and Spark Lab, 65 Witherspoon St. Local lead: Venu Sri Sabbavarapu.

**Hard times:** local judging presentations **Sun 14:00**. Final submission **Sun 23:59**. Feature freeze **Sun 12:00**.

## Saturday

| Time | What | Done when |
|---|---|---|
| before 10:00 | Sairam finishes #9 (repo, keys, tests pass) | `uv run pytest -q` passes on his laptop |
| 10:15 | Registration | |
| 10:30 | Intro and **judging criteria**: write them into #2 | criteria noted |
| 10:45 to 11:30 | Hour 0 (#2): freeze `docs/CONTRACTS.md`, pick lanes, add CODEOWNERS | contracts PR merged |
| 11:30 to 14:00 | Build 1: POWER + tide-gauge fetchers (#3), deseasonalize + Mann-Kendall + Sen (#4), MCP tools on contract stubs (#5), UI on example JSON (#6) | each lane has one merged PR |
| 14:00 | Check-in | `detect_trend` for Atlantic City sea level works end to end on a preview |
| 14:00 to 17:00 | Build 2: agent loop + evals, chart page, GRACE series, second source (ERA5 via Open-Meteo, NOAA station) | agent answers the sea-level question with numbers and a source |
| 17:00 | Check-in, production deploy | live URL answers the flagship question |
| evening | Polish, Delhi "sources disagree" case, demo script, slides or 30 s video draft | rough demo recorded |

## Sunday

| Time | What |
|---|---|
| morning | Fixes, evals green, rehearse the demo twice |
| **12:00** | **Feature freeze**: only bug fixes after this |
| 13:00 | At the library: final rehearsal |
| **14:00** | **Local judging presentation** |
| after judging | Fill the project page: title, summary, demo (7 slides or video of 30 s or less), repo link, SI disclosure. Aim to submit by 18:00, deadline 23:59 |

## Lanes (decided at hour 0)

- Tarun: all four lanes for now (data #3, stats #4, agent #5, UI and story #6), merges and deploys
- Sairam: set up and ready; picks up a lane when we split the work

## How we work: agent team

- Each of us runs one orchestrator session on Fable: `/orchestrate #<issue>` (playbook in `.claude/commands/orchestrate.md`).
- It splits the issue into task cards and runs builders in parallel, each in its own git worktree: `data-integrator`, `backend`, `ui-ux` (designs first), then `frontend`.
- Every PR goes draft, then `reviewer`, then `qa` (local and Vercel preview), then ready and auto-merge. After 2 fix rounds without a pass, the human decides.
- The humans freeze contracts, approve new dependencies and contract changes, and judge the demo.

## Rules that cost points if missed

- SI disclosure: every PR ends with `SI used: ...`; collect them for the submission.
- AI-made images and video (UI screens, slides, demo video) carry a visible "Built with AI assistance" label. AI audio (voiceover) is disclosed in the description text and file metadata.
- No NASA logos or branding in anything we make.
- Every number on screen names its data source.
