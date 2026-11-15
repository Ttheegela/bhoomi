# Gemini 3.8 Flash against Claude Haiku 5.5, same commit, same night (run 2026-11-15, about 01:12 to 01:20 UTC)

Why: the owner tried Gemini 3.8 Flash as the model on the live site for about an hour and asked what it does worse
than the default before deciding. Decision, 2026-11-15: production stays on Claude Haiku 5.5 through OpenRouter
(`AGENT_MODEL=openrouter:anthropic/claude-haiku-5.5`), which is also the code default.

The result files carry the runner's own date in their names and title (2026-11-14, the local date of the machine).

## The 15 test cases

- Commit of `main` used: `65bb7ee`, no local changes. Both models ran on it, one after the other, each once.
- Models: `openrouter:google/gemini-3.8-flash`, `openrouter:anthropic/claude-haiku-5.5`.
- Run the same way as `../2026-11-14-shortlist-gemini/`: the same helper outside the repository replaces only the ERA5
  fetch with a request to the production site's `/api/series`, then calls `evals.run.main`; Open-Meteo was never
  called from this machine; keys came only from the environment file, which is never printed.
- Spend: OpenRouter $0.16. No budget guard tripped. The plain-language judge did not run; it never decides pass or fail.
- At this commit the answer cap was 2,000 tokens (it is 4,000 since #79).

| model | passed | mean s | slowest s | $ per question |
|---|---|---|---|---|
| Claude Haiku 5.5 | 14/15 | 12.0 | 19.9 | 0.0018 |
| Gemini 3.8 Flash | 14/15 | 17.6 | 46.2 | 0.0086 |

- Both miss the same case, `delhi-sea-level-inland`, on the "right tool" check: each looked for a tide gauge near Delhi,
  found none, and declined with no numbers. That is a correct answer. The case already carries the field that accepts
  such a lookup (#76, in this commit), but the runner only reads it since #78, merged later the same night; these
  results were not scored again.
- No case passes for Haiku and fails for Flash, and neither model got a variable, a source or a verdict wrong.
- Flash's slowest answers: `phoenix-air-temp` 46.2 s, `london-air-temp` 31.8 s, `mumbai-sea-level-psmsl` 24.4 s,
  `chennai-rain` 21.9 s. Haiku's slowest: `mumbai-sea-level-psmsl` 19.9 s.
- The seconds are 3 to 5 s too high for both models: on the test machine the tracing export is blocked and each answer
  waits for it. Compare the two rows with each other, not with the live site.
- One run per model on 15 cases: enough to see a large difference in time and cost, too few to rank two models on
  correctness.

## Ten real questions on the live site while it ran Flash (answers not kept in this folder)

| question | seconds | words (limit) | result |
|---|---|---|---|
| Are Delhi's hottest days getting hotter? (twice) | 21.6, 27.0 | 132, 142 (180) | sources disagree, each with its own numbers and period |
| Is sea level rising in New York? (twice) | 8.8, 8.4 | 134, 155 (180) | correct, with the "agrees" sentence |
| Is sea level rising in Mumbai? (twice) | 19.6, 19.2 | 94, 103 (120) | correct |
| Is groundwater running out in Delhi? | 16.5 | 126 (120) | correct, 6 words over the limit |
| Is sea level rising in Delhi? | 6.4 | 42 (120) | declines, no numbers |
| Is it getting hotter in Springfield? | 5.7 | 22 (120) | asks which Springfield |
| Will it rain tomorrow? | 3.3 | 40 (120) | declines |

Every number in these answers is in a tool result, and every period belongs to its source. For comparison, Haiku on the
live site: New York 6 to 9 s, Delhi's hottest days 12 to 13 s.

What Flash did that Haiku does not:

1. New York, both times: it added "Both use the tide gauge at The Battery, 1 km away." The prompt says not to state what
   the sources share. The sentence is true, but no tool returned it as one fact. The scorer missed this wording; #80
   fixed the scorer.
2. Delhi's hottest days, both times: the ERA5 trend is written "0.12 °C per decade". The tool's value is 0.125; the
   Explore card shows +0.13, and Haiku writes 0.13. So the answer and the card differ by one digit on the main demo
   question.
3. Mumbai, both times: the answer opens with the source that had no data and gives the verdict second.
4. About 1.5 to 2 times slower than Haiku on questions with several sources, and about 5 times the cost.

What Flash did as well or better: the same pass count; shorter answers that needed no "please shorten" retry.

## Reported separately (not measured in this folder)

The owner's own session then ran the three demo questions three times each on the current `main` with a warm cache. It
reported: for Haiku, the Anthropic API directly was no faster than OpenRouter (median 9.4 s against 9.6 s), and Flash
gave one 75.5 s answer of 12,350 tokens on the Mumbai question.

## Not built

The code could hand the model each number already rounded the way the Explore card rounds it, so an answer and the card
could not differ by a digit with any model.
