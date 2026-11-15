# Model comparison, 2026-11-15

- Git commit: `1d8ba84`
- Cases run: 30 per model; not runnable yet: 0
- Judge (plain language only, never pass/fail): `anthropic:claude-haiku-5-5`, effort low (not run)
- Anthropic effort setting for candidates: medium; max_tokens 4000
- Spend: OpenRouter $0.3353, Anthropic $0.0000 (judge included; unknown costs counted at $0.02 per response)

| model | passed/ran (of total) | pass rate | right tool | right variable | right place | right source | verdict | verdict wording | no invented numbers | source named | must-say | enough places | plain words | known links | plain language (1-5) | mean latency s | cost per question $ | total cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openrouter:anthropic/claude-haiku-5.5` | 29/30 (of 30) | 97% | 29/30 | 22/22 | 22/23 | 7/7 | 7/7 | 21/21 | 30/30 | 23/23 | 23/24 | 3/3 | 23/23 | 30/30 | not run | 19.2 | unknown | unknown |

## Failed cases

- `openrouter:anthropic/claude-haiku-5.5`: ran 30 of 30 cases
  - atlantic-city-many-measurements: tool, place, must_say, answered (OpenRouter failed: HTTPStatusError)

## Not runnable yet (left out of the pass rate)

- none

## Dropped models

- none

## Budget guards

- none tripped
