# Sunday noon run (story lane, #16)

- Code: `main` at 1d8ba84 (after #112 guidance, #114, #115), Sun 15 Nov about 16:20 UTC.
- Model: `openrouter:anthropic/claude-haiku-5.5`, the production model. Command: `python -m evals.run --models openrouter:anthropic/claude-haiku-5.5 --openrouter-budget 1.0`.
- Files here are the runner's output, unedited.

## Result
- **Golden questions (`evals/cases.toml`): 15 of 15 pass**, including the two it must decline (rain tomorrow, sea level in Delhi). No invented numbers.
- All 30 cases: 29 of 30. The one failure is the agent-lane case `atlantic-city-many-measurements`, with no answer at all: `OpenRouter failed: HTTPStatusError`. It failed the same way on a second, single-case run.
- The same question asked on production (`/api/ask`) answered normally in about 36 s (Atlantic City sea level +42.54 mm per decade, Moderate risk), with about 8,400 output tokens. So the error comes from the local eval runner's path, not from the live site. That's agent-lane code; flagged to Tarun, not changed here.
