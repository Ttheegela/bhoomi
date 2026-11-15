# Model comparison, 2026-11-15

- Git commit: `e235692`
- Cases run: 19 per model; not runnable yet: 0
- Judge (plain language only, never pass/fail): `anthropic:claude-haiku-5-5`, effort low (not run)
- Anthropic effort setting for candidates: medium; max_tokens 4000
- Spend: OpenRouter $0.0383, Anthropic $0.0000 (judge included; unknown costs counted at $0.02 per response)

| model | passed/ran (of total) | pass rate | right tool | right variable | right place | right source | verdict | verdict wording | no invented numbers | source named | must-say | enough places | plain words | known links | plain language (1-5) | mean latency s | cost per question $ | total cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openrouter:anthropic/claude-haiku-5.5` | 18/19 (of 19) | 95% | 19/19 | 15/15 | 14/14 | 7/7 | 7/7 | 13/13 | 19/19 | 14/14 | 12/13 | 1/1 | 14/14 | 19/19 | not run | 7.7 | 0.0020 | 0.0383 |

## Failed cases

- `openrouter:anthropic/claude-haiku-5.5`: ran 19 of 19 cases
  - manhattan-build-house: must_say

## Not runnable yet (left out of the pass rate)

- none

## Dropped models

- none

## Budget guards

- none tripped
