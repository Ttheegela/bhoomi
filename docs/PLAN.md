# Run sheet: Sat Nov 14 to Sun Nov 15

Venue: Princeton Public Library, Tech Center and Spark Lab, 65 Witherspoon St. Local lead: Venu Sri Sabbavarapu.

**Hard times:** local judging presentations **Sun 14:00**. Final submission **Sun 23:59**. There is no feature freeze: work continues until the submission deadline. The one protected window is the presentation: **no merges to `main` on Sun from 13:00 to 15:00** (a merge deploys to production).

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
| morning | The story first: the presentation and the 30 s video. Then fixes, evals green, rehearse the demo twice |
| before 13:00 | Production stable. After the last deploy, open every demo place, measurement and source once on production so the answers are already cached on stage |
| **13:00 to 15:00** | **No merges to `main`** (a merge deploys and clears the cache). At the library: final rehearsal |
| **14:00** | **Local judging presentation** |
| after judging | Fill the project page: title, summary, demo (7 slides or video of 30 s or less), repo link, SI disclosure. Aim to submit by 18:00, deadline 23:59 |

## Lanes (decided at hour 0)

- Tarun: all code lanes through his orchestrator (data #3, stats #4, agent #5, UI #6, eval runner and checks in #16), plus the automated reviewer and QA agents, merges and deploys
- Sairam (Claude Pro: Sonnet, one session, no `/orchestrate`, no edits in `earthtrends/` or `web/`): golden eval questions in `evals/cases.toml` (#16), human QA on each production deploy (#17), story and submission in `docs/submission/` (#18)

## How we work: agent team

- Tarun runs one orchestrator session on Fable: `/orchestrate #<issue>` (playbook in `.claude/commands/orchestrate.md`). Sairam works in a single session without the agent team.
- It splits the issue into task cards and runs builders in parallel, each in its own git worktree: `data-integrator`, `backend`, `ui-ux` (designs first), then `frontend`.
- Every PR goes draft, then `reviewer`, then `qa` (local and Vercel preview), then ready and auto-merge. After 2 fix rounds without a pass, the human decides.
- The humans freeze contracts, approve new dependencies and contract changes, and judge the demo.

## Judging (from the venue's slides, Sat Nov 14)

- Five criteria: Impact, Creativity, Validity, Relevance, Presentation.
- The panel includes software engineers and a UX designer, so UI polish and accessibility count as much as correctness.
- Presentation, Sun 14:00: 7 to 10 minutes including Q&A. Everyone on the team talks. A live demo, or a video of 30 s or less.
- Validity is what our checks are for: the eval runner and its results in `evals/results/`, the NOAA truth check (our Atlantic City sea-level trend 4.25 mm per year against NOAA's 4.24 ± 0.08) and the model comparison table. Keep them readable by a person.
- The submission needs the code to be open source in a public repo. When to make the repo public is Tarun's call.
- The production site must be stable and rehearsed before Sun 13:00, and nothing is deployed from 13:00 to 15:00.
- Delhi "sources disagree" demo: it uses the hottest day of the month (`air_temp_max`) from NASA POWER, ERA5 and the Safdarjung station. Quote the numbers the tool returns on the day; the "days at or above 40 °C" figures in older notes do not reproduce.

## Rules that cost points if missed

- SI disclosure: every PR ends with `SI used: ...`; collect them for the submission.
- AI-made images and video (UI screens, slides, demo video) carry a visible "Built with AI assistance" label. AI audio (voiceover) is disclosed in the description text and file metadata.
- No NASA logos or branding in anything we make.
- Every number on screen names its data source.
