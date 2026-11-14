# Model comparison, 2026-11-14

- Git commit: `3805f25`
- Cases run: 12 per model; not runnable yet: 2
- Judge (plain language only, never pass/fail): `anthropic:claude-haiku-5-5`, effort low
- Anthropic effort setting for candidates: medium; max_tokens 2000
- Spend: OpenRouter $0.7527, Anthropic $0.1815 (judge included; unknown costs counted at $0.01 per response)

| model | passed/ran (of total) | pass rate | right tool | right variable | right place | right source | verdict | verdict wording | no invented numbers | source named | must-say | plain language (1-5) | mean latency s | cost per question $ | total cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `openrouter:anthropic/claude-haiku-5.5` | 11/12 (of 12) | 92% | 11/12 | 8/9 | 8/9 | 4/4 | 4/4 | 8/8 | 11/12 | 8/8 | 7/8 | 3.7 | 11.2 | 0.0009 | 0.0104 |
| `openrouter:deepseek/deepseek-v4-pro-0813` | 11/12 (of 12) | 92% | 11/12 | 8/9 | 8/9 | 4/4 | 4/4 | 8/8 | 12/12 | 8/8 | 7/8 | 3.6 | 9.1 | 0.0028 | 0.0336 |
| `openrouter:moonshotai/kimi-k3.1-pro` | 11/12 (of 12) | 92% | 12/12 | 9/9 | 9/9 | 4/4 | 4/4 | 9/9 | 11/12 | 9/9 | 7/8 | 3.8 | 11.6 | 0.0180 | 0.2158 |
| `openrouter:qwen/qwen3.8-max-0902` | 7/12 (of 12) | 58% | 9/12 | 6/9 | 6/9 | 1/4 | 1/4 | 6/6 | 12/12 | 6/6 | 3/8 | 3.2 | 19.1 | unknown | unknown |
| `openrouter:z-ai/glm-5.3` | 11/12 (of 12) | 92% | 12/12 | 9/9 | 9/9 | 4/4 | 4/4 | 9/9 | 11/12 | 9/9 | 7/8 | 3.3 | 3.1 | 0.0013 | 0.0150 |
| `openrouter:xiaomi/mimo-v2.6-pro` | 11/12 (of 12) | 92% | 12/12 | 9/9 | 9/9 | 4/4 | 4/4 | 9/9 | 11/12 | 9/9 | 7/8 | 3.5 | 11.4 | 0.0007 | 0.0083 |
| `openrouter:tencent/hy4` | 2/12 (of 12) | 17% | 11/12 | 9/9 | 9/9 | 4/4 | 4/4 | 0/9 | 12/12 | 0/9 | 3/8 | 4.3 | 36.0 | 0.0051 | 0.0613 |
| `anthropic:claude-sonnet-5-5` | 11/12 (of 12) | 92% | 12/12 | 9/9 | 9/9 | 4/4 | 4/4 | 9/9 | 11/12 | 9/9 | 7/8 | 3.8 | 3.9 | 0.0136 | 0.1633 |
| `anthropic:claude-haiku-5-5` | 11/12 (of 12) | 92% | 12/12 | 9/9 | 9/9 | 4/4 | 4/4 | 9/9 | 11/12 | 9/9 | 7/8 | 3.6 | 5.7 | 0.0010 | 0.0122 |

## Failed cases

- `openrouter:anthropic/claude-haiku-5.5`: ran 12 of 12 cases
  - delhi-hot-days-sources-disagree: tool, variable, place, numbers, must_say
- `openrouter:deepseek/deepseek-v4-pro-0813`: ran 12 of 12 cases
  - delhi-hot-days-sources-disagree: tool, variable, place, must_say
- `openrouter:moonshotai/kimi-k3.1-pro`: ran 12 of 12 cases
  - delhi-hot-days-sources-disagree: numbers, must_say
- `openrouter:qwen/qwen3.8-max-0902`: ran 12 of 12 cases
  - juneau-sea-level-falling: tool, variable, place, source, verdict, must_say, answered (OpenRouter failed: ConnectError)
  - astoria-sea-level-no-change: tool, variable, place, source, verdict, must_say, answered (OpenRouter failed: ConnectError)
  - port-orford-sea-level-no-change: tool, variable, place, source, verdict, must_say, answered (OpenRouter failed: ConnectError)
  - delhi-hot-days-sources-disagree: must_say
  - rain-tomorrow-forecast: must_say
- `openrouter:z-ai/glm-5.3`: ran 12 of 12 cases
  - delhi-hot-days-sources-disagree: numbers, must_say
- `openrouter:xiaomi/mimo-v2.6-pro`: ran 12 of 12 cases
  - delhi-hot-days-sources-disagree: numbers, must_say
- `openrouter:tencent/hy4`: ran 12 of 12 cases
  - atlantic-city-sea-level: wording, source_named, must_say, answered
  - juneau-sea-level-falling: wording, source_named, must_say, answered
  - astoria-sea-level-no-change: wording, source_named, must_say, answered
  - port-orford-sea-level-no-change: wording, source_named, must_say, answered
  - delhi-hot-days-sources-disagree: wording, source_named, must_say, answered
  - phoenix-air-temp: wording, source_named, answered
  - london-air-temp: wording, source_named, answered
  - chennai-rain: wording, source_named, answered
  - visakhapatnam-air-temp: wording, source_named, answered
  - mumbai-sea-level-no-gauge: tool
- `anthropic:claude-sonnet-5-5`: ran 12 of 12 cases
  - delhi-hot-days-sources-disagree: numbers, must_say
- `anthropic:claude-haiku-5-5`: ran 12 of 12 cases
  - delhi-hot-days-sources-disagree: numbers, must_say

## Not runnable yet (left out of the pass rate)

- northwest-india-groundwater: variable 'water_storage' is not in the catalog yet
- central-valley-groundwater: variable 'water_storage' is not in the catalog yet

## Dropped models

- none

## Budget guards

- none tripped
