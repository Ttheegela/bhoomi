# Shortlist re-run, 2026-11-14

- Commit of `main` used: `c200739` (Merge pull request #66), no local changes.
- Started: Sat Nov 14 23:41:03 UTC 2026 (`date -u`), one run, each model once, in this order.
- Command (from the repository root; keys come only from the env file):

  ```
  uv run --env-file ~/.config/trend-detective/dev.env python $TMPDIR/rerun/evalrun.py \
    --models openrouter:anthropic/claude-haiku-5.5,openrouter:anthropic/claude-sonnet-5.5,openrouter:z-ai/glm-5.3,openrouter:xiaomi/mimo-v2.6-pro,openrouter:deepseek/deepseek-v4-pro-0813 \
    --out evals/results/2026-11-14-shortlist --openrouter-budget 1.00
  ```

  `evalrun.py` (kept outside the repository) replaces `earthtrends.data._fetch_full` for `source == "era5"` only, then calls
  `evals.run.main`. Every other source ran the repository's own code.
- How ERA5 was served: Open-Meteo was never called from this machine. Each ERA5 series was fetched once from the
  production site, `GET https://trend-detective-six.vercel.app/api/series?variable=…&lat=…&lon=…&source=era5`, keeping
  `variable, units, freq, place, times, values, source, notes`; the repository's own cache served repeats. 7 production
  requests in total.
- Cases: all 15 in `evals/cases.toml` ran for every model; none were skipped (the two GRACE cases are runnable now,
  unlike the earlier `2026-11-14-model-comparison` run, which had 12).
- Spend: OpenRouter $0.63 in total, under the $1.00 guard (`--openrouter-budget 1.00`), which did not trip.
- Plain-language judge did not run: the `anthropic` package (the `evals` group) is not installed, so that column says
  "not run". It never decides pass or fail.
- Langfuse tracing was refused by the sandbox; it only logged errors and did not affect any answer or score.
- Reading the table:
  - "mean latency s" is the whole question, data fetches included, not the model alone.
  - `chennai-rain`: the GHCN station call failed for every model (NOAA side); the case still passed on POWER and ERA5.
  - `delhi-sea-level-inland` fails "right tool" whenever a model calls `detect_trend` to look for a gauge, even if
    the call returns "no tide gauge within 100 km" and the answer declines with no numbers.
  - The GRACE cases' 50 km place tolerance fails models that split "Punjab and Haryana" into two points, or pick
    another point inside the Central Valley; GRACE averages over about 400 km.
  - The `.jsonl` run log in this folder is not committed.
