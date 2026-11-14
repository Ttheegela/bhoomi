# Model comparison, 2026-11-14

- Git commit: `c200739`
- Cases run: 15 per model; not runnable yet: 0
- Judge (plain language only, never pass/fail): `anthropic:claude-haiku-5-5`, effort low (not run)
- Anthropic effort setting for candidates: medium; max_tokens 2000
- Spend: OpenRouter $0.6279, Anthropic $0.0000 (judge included; unknown costs counted at $0.01 per response)

| model | passed/ran (of total) | pass rate | right tool | right variable | right place | right source | verdict | verdict wording | no invented numbers | source named | must-say | plain language (1-5) | mean latency s | cost per question $ | total cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openrouter:anthropic/claude-haiku-5.5` | 13/15 (of 15) | 87% | 14/15 | 12/12 | 11/12 | 7/7 | 7/7 | 12/12 | 15/15 | 12/12 | 11/11 | not run | 12.7 | 0.0017 | 0.0259 |
| `openrouter:anthropic/claude-sonnet-5.5` | 14/15 (of 15) | 93% | 14/15 | 12/12 | 12/12 | 7/7 | 7/7 | 12/12 | 15/15 | 12/12 | 11/11 | not run | 11.8 | 0.0289 | 0.4336 |
| `openrouter:z-ai/glm-5.3` | 12/15 (of 15) | 80% | 15/15 | 12/12 | 11/12 | 7/7 | 7/7 | 10/12 | 15/15 | 12/12 | 11/11 | not run | 10.6 | 0.0037 | 0.0553 |
| `openrouter:xiaomi/mimo-v2.6-pro` | 13/15 (of 15) | 87% | 14/15 | 12/12 | 11/12 | 7/7 | 7/7 | 12/12 | 15/15 | 12/12 | 11/11 | not run | 17.2 | 0.0016 | 0.0237 |
| `openrouter:deepseek/deepseek-v4-pro-0813` | 13/15 (of 15) | 87% | 15/15 | 12/12 | 11/12 | 7/7 | 7/7 | 12/12 | 15/15 | 12/12 | 10/11 | not run | 12.1 | 0.0060 | 0.0894 |

## Failed cases

- `openrouter:anthropic/claude-haiku-5.5`: ran 15 of 15 cases
  - northwest-india-groundwater: place
  - delhi-sea-level-inland: tool
- `openrouter:anthropic/claude-sonnet-5.5`: ran 15 of 15 cases
  - delhi-sea-level-inland: tool
- `openrouter:z-ai/glm-5.3`: ran 15 of 15 cases
  - port-orford-sea-level-no-change: wording
  - northwest-india-groundwater: place
  - central-valley-groundwater: wording
- `openrouter:xiaomi/mimo-v2.6-pro`: ran 15 of 15 cases
  - central-valley-groundwater: place
  - delhi-sea-level-inland: tool
- `openrouter:deepseek/deepseek-v4-pro-0813`: ran 15 of 15 cases
  - northwest-india-groundwater: place
  - rain-tomorrow-forecast: must_say

## Not runnable yet (left out of the pass rate)

- none

## Dropped models

- none

## Budget guards

- none tripped
