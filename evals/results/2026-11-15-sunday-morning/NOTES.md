# Sunday-morning check of the live model (run 2026-11-15, about 05:50 UTC)

Why: the pitch and project page quote a golden-question score, and the agent changed overnight (#100, plain answers;
#83, follow-ups). This run is the score they now quote.

- Commit of `main` used: `e235692` (Merge pull request #105), no local changes. One run, once.
- Model: `openrouter:anthropic/claude-haiku-5.5`, the production model (checked: `/api/ask` reports it).
- Command (from the repository root; keys come only from the env file):

  ```
  uv run --env-file ~/.config/bhoomi/dev.env python -m evals.run \
    --models openrouter:anthropic/claude-haiku-5.5 --openrouter-budget 1.0 --out <dir>
  ```

- Result: 18 of 19 cases. All 15 golden questions in `evals/cases.toml` pass. Of the 4 agent-lane cases in
  `evals/cases_agent.toml`, `manhattan-build-house` fails its must-say check only: the answer says "Past measurements
  cannot show how high the sea will get", and the case asks for "cannot tell". The answer was otherwise right (both
  official links, no advice, no statistics words).
- No invented numbers in any answer (19/19). Spend: OpenRouter $0.04.
- The `.jsonl` file of full answers is not committed; the `.json` file has them.
- After this run, `delhi-sea-level-inland` got verdict phrases in `must_not_say` (same PR). That one case was re-run
  alone with the new list and still passed (1/1).
