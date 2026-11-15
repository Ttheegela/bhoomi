# Two more models on the same test (run 2026-11-15 00:32 UTC, filed with the 2026-11-14 shortlist)

Why: to add a third model family to the comparison. Two Google models were run on the same 15 cases, with
the same agent code, settings and budget guard as the five-model run in `../2026-11-14-shortlist/`.

- Commit of `main` used: `c200739`, the same commit as the five-model run (no local changes), so the agent code, the
  prompt and the cases are identical.
- Started: 2026-11-15 00:32 UTC, ended 00:42 UTC. One run, each model once.
- Models: `openrouter:google/gemini-4-hydrogen`, `openrouter:google/gemini-3.8-flash`. Both ids were checked against
  OpenRouter's public model list just before the run; both list tool support.
- Command (from the repository root; keys come only from the environment file, which is never printed):

  ```
  uv run --env-file <env file> python evalrun.py \
    --models openrouter:google/gemini-4-hydrogen,openrouter:google/gemini-3.8-flash \
    --out evals/results/2026-11-14-shortlist-gemini --openrouter-budget 1.00
  ```

  `evalrun.py` (kept outside the repository) replaces the ERA5 fetch with a request to the production site's
  `/api/series`, then calls `evals.run.main`; Open-Meteo was never called from this machine. Every other source ran the
  repository's own code.
- Spend: OpenRouter $0.68, under the $1.00 guard, which did not trip.
- The plain-language judge did not run (as in the five-model run). It never decides pass or fail.

## All seven models, same columns

| model | passed | mean s | slowest s | $ per question |
|---|---|---|---|---|
| Claude Haiku 5.5 (the default) | 13/15 | 12.7 | 26.7 | 0.0017 |
| Claude Sonnet 5.5 | 14/15 | 11.8 | 19.9 | 0.0289 |
| GLM 5.3 | 12/15 | 10.6 | 28.7 | 0.0037 |
| MiMo v2.6 pro | 13/15 | 17.2 | 40.7 | 0.0016 |
| DeepSeek v4 pro | 13/15 | 12.1 | 46.7 | 0.0060 |
| Gemini 4 Hydrogen | 14/15 | 25.8 | 42.3 | 0.0368 |
| Gemini 3.8 Flash | 14/15 | 12.7 | 28.5 | 0.0087 |

## Reading it

- The default model stays Claude Haiku 5.5; this run changes nothing.
- Both Gemini models failed one check, on the same case: `delhi-sea-level-inland` expects no tool call, and both looked
  for a tide gauge first, found none, and declined with no numbers. That is a correct answer; the case is too strict
  (noted on issue #16). Neither got a variable, a source or a verdict wrong, and neither wrote a number that was not in
  a tool result.
- Across all seven models, no model got a variable, source or verdict wrong. The pass counts differ by one or two checks,
  and most of those are the cases' strictness (a 50 km place tolerance for a 400 km groundwater average; the case
  above), not wrong answers. One run per model is too few to rank models that are this close.
- What does separate them is time and cost. Gemini 4 Hydrogen took about twice the default's time (25.8 s against
  12.7 s) and costs about twenty times the default per question. Gemini 3.8 Flash is as fast as the default and costs about five times as much.
- Limits of this test, stated plainly: the prompt was written and tuned while testing with the default model, and the
  other models run it unchanged; each model ran once; 15 cases.
- The seconds are longer than on the live site. On the machine that ran the tests, the tracing export was blocked, and
  each answer waited a few seconds for it before returning; this is the same for every model. On the live site the same
  night, two questions took 5.9 s (sea level in New York) and 13.1 s (Delhi's hottest days, three sources).

## Where a slow answer spends its time

The three slowest answers of the five-model run were asked again with a stopwatch on every step:

- None was slow the second time (41 s became 12 s and 8 s; 47 s became 9 s and 12 s; 27 s became 18 s and 13 s).
- The 47 s answer had waited 40 s for the weather-station service, which did not answer in time; the model was not the
  cause. The 41 s answer had two instant tool calls, so the time went to the model host that once.
- A typical three-source answer with the default model: choosing what to look up about 2 s; fetching data about 4 s the
  first time and nothing once cached; writing the answer 7 to 8 s, most of it the model's reasoning before the first
  word.
