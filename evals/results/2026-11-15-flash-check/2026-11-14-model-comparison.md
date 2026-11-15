# Model comparison, 2026-11-14

- Git commit: `65bb7ee`
- Cases run: 15 per model; not runnable yet: 0
- Judge (plain language only, never pass/fail): `anthropic:claude-haiku-5-5`, effort low (not run)
- Anthropic effort setting for candidates: medium; max_tokens 2000
- Spend: OpenRouter $0.1564, Anthropic $0.0000 (judge included; unknown costs counted at $0.01 per response)

| model | passed/ran (of total) | pass rate | right tool | right variable | right place | right source | verdict | verdict wording | no invented numbers | source named | must-say | plain language (1-5) | mean latency s | cost per question $ | total cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openrouter:google/gemini-3.8-flash` | 14/15 (of 15) | 93% | 14/15 | 12/12 | 12/12 | 7/7 | 7/7 | 12/12 | 15/15 | 12/12 | 11/11 | not run | 17.6 | 0.0086 | 0.1293 |
| `openrouter:anthropic/claude-haiku-5.5` | 14/15 (of 15) | 93% | 14/15 | 12/12 | 12/12 | 7/7 | 7/7 | 12/12 | 15/15 | 12/12 | 11/11 | not run | 12.0 | 0.0018 | 0.0271 |

## Failed cases

- `openrouter:google/gemini-3.8-flash`: ran 15 of 15 cases
  - delhi-sea-level-inland: tool
- `openrouter:anthropic/claude-haiku-5.5`: ran 15 of 15 cases
  - delhi-sea-level-inland: tool

## Not runnable yet (left out of the pass rate)

- none

## Dropped models

- none

## Budget guards

- none tripped
