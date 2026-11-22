# Bhoomi rework spec: expert projections, one baseline, honest math

Status: approved direction from Tarun, 2026-11-22. This file is the build brief, copied into the repo in the first PR.

The research reports it names (`research/slr-earth/reports/…`) are kept outside this repository: they quote the site we studied, which is not ours to publish. Builders read them locally; nothing from them is copied into the repo.

## Why

Outside reviews of bhoomi.earth (Nov 22) found three faults. All three are confirmed in code on `origin/main` (85f9fe4):

1. **Future lines look wildly variable.** `web/compare.js` starts the future wedge at the last point of a centred 5-year average. Near the end of a record that point averages only 3 years. `guidance.py::_outlook` widens the wedge by the slope's 95% range × decades ahead. That is a straight-line extrapolation that only covers slope uncertainty, and it ignores autocorrelation, acceleration and physics.
2. **The math makes no sense.** Each view uses a different zero:
   - the dialog chart uses calendar-month means over the whole record (`trend.py` L27–35), which moves as data grows;
   - the compare chart uses 2000–2009;
   - the card uses the last data year.

   The "How we calculated this" dialog never derives the card's "by 2050" range. The "× world" risk ratio compares unlike things:
   - land warming against the 0.20 °C/decade land+ocean average;
   - a tide gauge's whole-record rate against the 1993+ satellite rate of 3.4 mm/yr;
   - hottest-day trends against the mean-temperature reference.
3. **Source links open homepages.** NASA POWER opens https://power.larc.nasa.gov/, not the record we used.

The bar is oceanrise.earth (slr.earth), built by the NASA Sea Level Change Team. We studied every module. Reports are in `research/slr-earth/reports/` next to this file:
- `indicators.md`: charts and math;
- `maps.md`;
- `ar6.md`: projections and data access;
- `explorers.md`: past plus future on one chart;
- `explainers.md`: teaching, page grammar and design.

Read the report section named in each work item before building it.

**Rule:** ideas only. Do not copy oceanrise code, text, colours or logo. Our code, our words, our palette.

## Decisions (fixed; do not reopen without asking)

- **D1. Future values come only from published expert projections. Never extend a past trend.**
  - Sea level: IPCC AR6 per tide gauge.
  - Air temperature, hottest day and precipitation: CMIP6 multi-model projections (IPCC AR6 Atlas data).
  - Land water storage (GRACE): no projection exists, so no future line. Say so in one sentence.
  - Delete `_outlook`, the "If the past trend continues" ranges, and the compare-chart wedge.
- **D2. One baseline: the 1995–2014 average**, the same reference AR6 and the AR6 Atlas use. Chart axis, card, table, CSV, agent answers and "How we calculated this" all state levels against it.
  - Seasonal anomalies are taken against fixed 1995–2014 calendar-month means. Never against a whole-record mean.
  - GRACE is the only exception. Use the provider's own reference period: verify it for the GSFC mascon release we ship and state it.
- **D3. Baseline coverage rule.**
  - Use whole years only. A year counts when at least 9 of its 12 months are valid. The baseline needs at least 15 of the 20 years.
  - If coverage is short but the record spans 30 or more years and starts before 2005: fit trend plus harmonics, take the fitted 1995–2014 mean, and label it "baseline estimated from the fitted trend".
  - If the record starts after 2014: show it on its own chart, never on the projection axis.
- **D4. Projections are plotted exactly as published.** Never shift a projection to meet the last observation, and never anchor anything on a smoothed endpoint. The gap between the observed level and the projection at 2020 is information, not an error.
- **D5. Like-for-like world comparisons only.**
  - **Air temperature:** local Sen slope against the global **land-only** average slope over the **same years**, same method.
    - Source: a published land-only monthly series with an exact URL, e.g. NOAA NCEI Climate at a Glance global land, or Berkeley Earth land. Verify before use.
  - **Sea level:** local gauge Sen slope over 1993–latest against NASA satellite GMSL Sen slope over the same 1993–latest window.
    - The gauge needs at least 20 of those years; otherwise no ratio.
    - Show the full-record local rate separately, with its years and no ratio.
  - **Hottest day, precipitation, GRACE:** no world ratio. Hottest day says "no matching world figure". Precipitation and GRACE keep their own-place rules (share of usual rain; cm of water a year), and the rule is printed.
  - Risk levels keep the 0.75 / 1.5 thresholds for temperature and sea level. The dialog prints numerator, denominator, window and thresholds.
  - Hottest day loses its risk level: the verdict only.
- **D6. Minimum records.**
  - Headline trend: at least 30 years with at least 80% monthly coverage. 20–29 years: show it, labelled "short record". Under 20 years: no trend.
  - GRACE: at least 10 years.
  - Running means need 80% of the window and break at gaps.
- **D7. Name every range by its kind**:
  - "95% range" for our trend;
  - "likely range (about 2 in 3 chance)" only for AR6 medium-confidence 17–83%;
  - "range across climate models (10th–90th percentile)" for CMIP6 spread;
  - percentile names for anything else, including AR6 low-confidence scenarios.
- **D8. UI stays monochrome**: Tarun's standing preference is ink, white and grey. Colour is used only to encode data, from one token set with a light-first and dark theme. `explainers.md` §6(c) has a candidate data palette with measured contrast. Adapt it, check it with a colour-vision simulator, and keep brand and links ink.

## Integration and release

- Branch `rework/expert-projections` from `origin/main`. The local checkout is 139 commits behind, so fetch first. Every work-item PR targets that branch; its Vercel preview is the test site.
- One final PR into `main`. **It merges only on Tarun's explicit OK.** No production deploys, Vercel changes or secret changes without him.
- Use Opus 5.5 everywhere: this session and every subagent (`model: "opus"` on every Agent call, overriding the sonnet defaults in `.claude/agents/*.md`). In the first PR, change `.claude/commands/orchestrate.md` line 6 from Fable to Opus 5.5. Never use Fable.
- Standing repo rules still apply:
  - the commit trailer;
  - PR body ending plus the `SI used:` line;
  - "Built with AI assistance" on every screen;
  - no NASA logos or branding;
  - secrets never in chat or files;
  - times in EST;
  - fork PRs never run with dev keys;
  - no private lab code or unpublished lab data (the AR6 and Atlas data are public, CC-BY-4.0).

## Work items (PRs into the integration branch)

### PR1 — Foundation: contract, baseline, links, explanation
Read `indicators.md` §6, `explainers.md` §6(a)(b)(d).

1. **Self-describing series.** Every series in API responses carries:
   - `baseline` as text and as `[1995, 2014]`;
   - `source`, `dataset_id`, `version`, `record_url`, `retrieved`, `method`, `cadence`, `units`, `deseasoned_upstream`;
   - per-point `flags` for preliminary months.

   The chart, table, CSV header and dialog read only these fields. Update `docs/CONTRACTS.md`.
2. **Exact-record links.** `record_url` opens the specific record:
   - **POWER:** the exact API request with lat, lon, parameter and dates.
   - **ERA5:** the dataset DOI plus the cell coordinates. If the Open-Meteo archive request is what we actually fetched, link that exact request.
   - **GHCN:** the NCEI station record by ID.
   - **CO-OPS:** the station page by ID.
   - **PSMSL:** the station page by numeric ID.
   - **GRACE:** the dataset page plus the granule or file name.

   Verify each type: HTTP 200, and the response names our station or coordinates.
3. **CSV download** per chart. The header lines carry title, place, source, record_url, dataset ID and version, baseline, method and retrieved date.
4. **Stats changes** (`earthtrends/stats/trend.py`, `guidance.py`):
   - the fixed 1995–2014 climatology (D2/D3);
   - precipitation as % of the 1995–2014 normal;
   - D6 minimum rules;
   - trend CIs that account for autocorrelation (confirm Sen CI uses an effective n; Hamed–Rao already covers the MK p-value);
   - headline changes read from the fitted line, never from the last raw month;
   - delete `_outlook`;
   - D5 world comparisons and risk.
5. **"How we calculated this" becomes an in-page section** (`#how`; the button scrolls there). Use the nine-step worked example in `explainers.md` §6(a), with the place's own numbers, all from the one stats object the card and chart use:
   - data, seasons removed, baseline, trend and range, "is it real?", world comparison, expert future, caveats, sources.
   - Step 7 shows only the expert projection (D1). Drop the "(a) if the trend continued" option.
   - Use the writing rules in `explainers.md` §6(d).
6. Change `orchestrate.md` from Fable to Opus 5.5, and commit this spec as `docs/REWORK-SPEC.md`.

### PR2 — Sea level future: IPCC AR6 per tide gauge
Read `ar6.md` §1, §4, §5 and `explorers.md` §6.1, §6.3. The reference scripts are in `research/slr-earth/scripts/` (`zipcd.py`, `unzipentry.py`, `verify_nyc.py`) and `research/slr-earth/zenodo/` (`rc_listing.tsv`, `location_list.lst`).

1. **`scripts/build_ar6.py` (offline only, never on Vercel).**
   - Range-fetch the 51 needed entries from Zenodo record 6382554, `ar6-regional-confidence.zip` (total, the six processes, rates; SSP1-2.6/2-4.5/3-7.0/5-8.5 medium; SSP1-2.6/2-4.5/5-8.5 low).
   - Keep the PSMSL gauges, the quantiles 0.05/0.167/0.5/0.833/0.95 and the decades 2020–2150.
   - Write int16 `earthtrends/data/ar6_gauges.npz` with a manifest: DOI, version 20210809, md5s, baseline, units, confidence per scenario, citations.
   - Build fails unless:
     - PSMSL 12 / SSP2-4.5 / 2050 equals 209, 266, 358, 464, 545 mm and its rate median equals 8.6 mm/yr;
     - quantiles are non-decreasing;
     - VLM is equal across scenarios.

   Expected size is about 4–6 MB.
2. **CO-OPS → PSMSL mapping, `earthtrends/data/coops_to_psmsl.csv`.**
   - Nearest AR6 gauge: accept within 3 km; within 15 km if a name token matches; otherwise a hand-checked override.
   - If none: the nearest valid AR6 1° cell, labelled "regional estimate".
3. **API.** Each sea-level answer carries AR6 levels and rates for every scenario plus the process breakdown, on the 1995–2014 baseline. The observed series is rebased by D2/D3: CO-OPS is metres on the 1983–2001 epoch, convert to mm and re-zero; PSMSL RLR uses −99999 for missing years.
4. **Chart: past and future on one axis.**
   - Observed monthly values as a faint line; a 12-month centred mean (display only; it stops half a window before the end).
   - AR6 medians from 2020 for each scenario, as published.
   - The selected scenario's band:
     - medium confidence: 17–83% likely range at about 15% fill;
     - low confidence: dashed median with the 17–83 percentile band named by percentiles.
   - A dashed "today" rule; direct labels at line ends.
   - Y-axis title "cm above the 1995–2014 average"; x-axis from the record start to 2100 (2150 optional, with a break at 2100).
5. **Readouts on the same baseline.**
   - Now: +X cm, as the 12-month mean to Month YYYY.
   - By 2050 under the chosen scenario: +Y cm (likely a–b).
   - About Y−X cm more than today, labelled approximate.
6. **"What drives it" bars for 2050:** sterodynamic, Greenland, Antarctica, glaciers, land water and vertical land motion. Include the likely ranges and a note that the parts' ranges don't add to the total's.
7. **Decade table** with columns median, likely, 5–95 and rate, plus CSV. Add one caveat line: faster ice-sheet loss could push this higher, outside the range. Cite the three works plus the acknowledgement required by the Rutgers-ESSP README (see `ar6.md` §4.7).
8. **Built-in check (a test).** For every mapped gauge with data, the observed 2019–2021 mean on the 1995–2014 baseline lies inside AR6 2020 p5–p95. List failures in the PR. The Battery passes: about 80 mm against a likely range of 66–139.

### PR3 — Temperature, hottest day, rain future: CMIP6
Read `explorers.md` §6.2.

1. **Source.** The IPCC AR6 Interactive Atlas gridded CMIP6 data (IPCC-DDC / DIGITAL.CSIC): `tas`, `TXx` and `pr`, monthly, about 1°, SSP1-2.6/2-4.5/3-7.0/5-8.5.
   - **First verify and report back to the coordinator before bulk download:**
     - exact URLs and sizes;
     - that 1995–2014 is usable;
     - the model list;
     - the licence.
   - Do not use the Open-Meteo Climate API in production (single scenario, ends 2050, terms). If the Atlas data are unworkable, stop and report; do not switch sources silently.
2. **`scripts/build_cmip6.py` (offline).** For each land cell, SSP and 20-year window (2021–2040, 2041–2060, 2081–2100), compute the model **change** against each model's own 1995–2014 mean:
   - a difference for `tas`/`TXx`, a ratio for `pr`;
   - store p10/p50/p90 across models and, for `pr`, the share of models agreeing on the sign;
   - int16 `npz` with a manifest.

   Expect about 3–12 MB per variable.
3. **Delta method.** Projected level = this place's observed 1995–2014 mean + change percentile; for rain, × ratio and shown as %. Never splice raw model values onto observations.
4. **Chart.**
   - Observed annual anomalies as dots, plus the observed fit inside the record.
   - Projections as 20-year-window medians at the window centres, with the selected SSP's model range.
   - Same "today" rule and baseline title as sea level.
   - No annual model wiggles. An optional separate band of observed year-to-year spread may be added, labelled as such.
   - For rain, say "models disagree on wetter or drier" when fewer than 80% agree.

### PR4 — Charts, compare view, design
Read `indicators.md` §4, §6.1–6.4, `explainers.md` §6(c).

1. **Single-place chart grammar.**
   - Raw values thin and always visible; the smoother dashed; the fit dotted and inside the data only.
   - The y-axis names units and baseline; "Data through Month YYYY".
   - Legend swatches match the strokes; the tooltip snaps to observations; data table plus CSV.
2. **Compare view.** Replace the six-line spaghetti with:
   - (a) one emphasised place against faint others, all on 1995–2014;
   - (b) a rate chart: one dot with its 95% range per place, same window for all, same units.
3. **Acceleration** (sea level only): only for gauges with 50 or more years.
   - Fit a quadratic with harmonics and an ENSO index; the test is 90%, AR(1)-adjusted.
   - Show "rate at the start vs rate now" only if it passes. Otherwise: "this record can't yet show a change in rate".
4. **Design tokens.** D8: monochrome UI, data colours from one token set. Body text 16 px; controls ≥ 44 px with borders ≥ 3:1. Update `web/DESIGN.md` to match what ships.

### PR5 — Maps
Read `maps.md` §4.

1. **Tide-gauge dots coloured by their Sen slope**, using the same code as the point answer.
   - Diverging scale with neutral exactly at 0, built from one stops array shared by the MapLibre expression and the CSS legend.
   - "No clear change" drawn as a hollow ring.
   - Hover: slope ± range, years, verdict.
   - Legend says "relative to the land".
2. **GRACE land-water trend layer**, computed offline in `scripts/build_grace.py`, with "no clear change" faded. State the footprint (~300 km) and the reference period.
3. Static JSON only (int16 base64 plus metadata, as in `maps.md` §4.2). Nothing computed per request. Means and percentiles weighted by area.
4. *Later, after the release:* a world warming-trend grid and a "conditions now" anomaly map against one stated normal.

### PR6 — Agent, voice, evals, sources pages

1. Update the in-app agent's tool outputs and prompts for:
   - expert projections (scenario, baseline, range kind);
   - D5 comparisons;
   - the hottest-day change.

   Keep the `invented_numbers` guard.
2. Update `evals/cases.toml` and `cases_agent.toml` golden numbers and rerun.
3. List the exact ElevenLabs prompt changes needed in the PR body (wording for risk, future and disclaimer). The coordinator applies them.
4. Add a **Data sources** page (each dataset, distributor, ID or DOI, licence, link, update rhythm) and a **Reference rates** page (the world figures we compare against, with period and surface).

## Verification gate (all must pass before asking Tarun for the release OK)

1. Unit tests for:
   - the baseline coverage rules;
   - rebasing;
   - the AR6 lookup and mapping;
   - the delta method;
   - the minimum-record rules;
   - the D5 windows.
2. `build_ar6.py` and `build_cmip6.py` self-checks pass.
3. **Independent recompute.** A separate script (not importing `earthtrends.stats`) recomputes five places and diffs them against the API: New York/The Battery, Princeton NJ, Delhi, London, Sydney.
   - Cross-check against outside published numbers:
     - NOAA's published sea-level trend for station 8518750;
     - AR6 values for PSMSL 12;
     - the Atlas web viewer for one cell;
     - the published global land trend for our window.
   - Put the table in the PR.
4. **Link check.** Every `record_url` type returns 200 and names our station or coordinates. Click-test in the browser for the five places.
5. **Domain-scientist review** by an Opus reviewer, against this checklist:
   - one baseline everywhere;
   - same-period, same-surface comparisons;
   - no future line from a smoothed endpoint;
   - projections unshifted;
   - every range named by its kind;
   - axis titles name baselines;
   - "Data through" shown;
   - CSV headers complete.
6. **Persona walk-throughs** at 1440 and 1920 px, light theme, on the Vercel preview: student, investor, coastal builder, planner. Written as the visitor, with screenshots in the PR.
7. The voice agent answers one question per factor correctly after the ElevenLabs update.

## Open items to report back (do not guess)

- The GRACE GSFC reference period.
- The Atlas data access details (PR3 step 1).
- Whether the hottest-day world comparison can be like-for-like (ERA5 world-land mean of monthly max daily max); otherwise none.
- Whether `coops_to_psmsl` needs overrides for any demo stations.
