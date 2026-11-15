# Bhoomi

Bhoomi answers one question about a place: is this really changing here? People say the summers are hotter or the sea is higher than it used to be. A line drawn through noisy data always slopes one way or the other, so a chart alone can't tell a real change from a bad year. Bhoomi pulls the record for the place from public data (NASA, NOAA and other open providers), removes the seasons, runs a significance test, and answers "rising", "falling" or "no clear change". Every answer gives the size of the change, a 95% range and the data source. It is a web page, an AI agent and an MCP server for students and the public. It was built at the NASA Space Apps Challenge 2026 (challenge: *Be An Earth System Trend Detective!*).

## Try it

Live site: https://bhoomi.earth

The page has three tabs:

- **Explore.** Pick an example place or type coordinates, then pick a measurement and a data source. You get a chart, the trend and the verdict. This tab does not use an AI model.
- **Ask.** Type a question in your own words, for example "Is sea level rising in Atlantic City?". An AI agent works out the place and the measurement, calls the same tools, and answers in plain words. This tab is rate limited, because every question costs money: 30 questions a minute and 150 an hour per client, and 200 an hour in total. The data routes and the MCP endpoint are limited to 120 requests a minute and 1,200 an hour per client.
- **Use in your AI.** Steps to connect your own AI app to the MCP server below.

MCP endpoint (streamable HTTP, no key, no sign-in): `https://bhoomi.earth/mcp/`. Keep the trailing slash.

```bash
claude mcp add --transport http bhoomi https://bhoomi.earth/mcp/
```

The endpoint offers four tools:

| Tool | Inputs | Returns |
|---|---|---|
| `ping` | none | `pong`, to check the server is reachable |
| `list_variables` | none | the measurements below, with units and sources |
| `get_series` | `variable`, `lat`, `lon`, optional `start`, `end`, `source` | the monthly time series, its source and notes |
| `detect_trend` | the same | slope per decade, 95% range, p-value, verdict, source and caveats |

The web page calls the same functions through `/api/variables`, `/api/series` and `/api/trend`, so the page and an outside AI agent get identical results. The data shapes are in `docs/CONTRACTS.md`.

## What you can ask

| Measurement | Id | Units | Sources (the first is the default) | Record |
|---|---|---|---|---|
| Air temperature (2 m) | `air_temp` | °C | NASA POWER, ERA5, GHCN-Daily weather station | 1981 on |
| Hottest day of the month (2 m air temperature) | `air_temp_max` | °C | NASA POWER, ERA5, GHCN-Daily weather station | 1981 on |
| Precipitation | `precip` | mm/day | NASA POWER, ERA5, GHCN-Daily weather station | 1981 on |
| Sea level (monthly mean, relative to land) | `sea_level` | mm | NOAA CO-OPS tide gauge (US coasts), PSMSL tide gauge (worldwide) | The gauge's whole record (CO-OPS is asked for data from 1900 on) |
| Land water storage (change from its 2004 to 2009 average) | `water_storage` | cm of water | NASA GSFC GRACE and GRACE-FO mascons | April 2002 to June 2026 |

- All series are monthly values of past observations. There are no forecasts.
- NASA POWER and ERA5 are grids (cells about 50 km and about 25 km wide), so they cover any point.
- A weather station is used only if it is within 50 km of the point and has at least 30 years of data since 1981.
- A tide gauge is used only if it is within 100 km of the point. Sea level uses NOAA CO-OPS first. If CO-OPS has no gauge that close, the nearest usable PSMSL gauge is used, and the result says so. A PSMSL gauge is usable if it has at least 30 years of valid monthly values and its last valid month is no more than 5 years before the end of last year.
- A place with no tide gauge nearby gets a plain "no data" answer, never an estimate.
- Sea level is relative to the land at the gauge, so land that sinks or rises is included.
- Land water storage comes from the GRACE satellites, which measure gravity. A value is the average over the land about 400 km across around the point, not the exact spot. It is all water on land together (soil moisture, groundwater, snow and ice, lakes and rivers), so it cannot tell groundwater from surface water. There is no data from mid-2017 to mid-2018, between the two satellite pairs. Open ocean, ice sheets, small islands and the large glacier regions get a plain message, not a value.

## How it decides

1. **Seasons removed.** For each calendar month, the average of that month over the whole record is subtracted. What is left is how unusual each month was.
2. **Mann-Kendall test.** It asks whether later values tend to be higher (or lower) than earlier ones more often than chance would give. The result is a p-value. The test is corrected for tied values. It is also adjusted when neighbouring months resemble each other (positive autocorrelation), which makes it more cautious.
3. **Sen's slope.** The size of the change is the median of the slopes between every pair of points. It is reported per decade with a 95% range.
4. **Verdict.** One of three:
   - **rising**: the p-value is below 0.05 and the whole 95% range is above zero.
   - **falling**: the p-value is below 0.05 and the whole 95% range is below zero.
   - **no clear change**: anything else. The data does not show a clear change. This is a real answer, not a failure.

A series needs at least 10 valid points. A record shorter than 10 years gets a caveat that short trends are unreliable. The code is in `earthtrends/stats/trend.py`.

**When several sources exist.** In the Ask tab, the agent runs the test once for each source of the measurement (unless you name one). If the verdicts match, it says so. If they differ, it says first that the sources disagree, then gives one line per source. It does not pick a winner or average them. In the Explore tab you switch the source yourself.

The agent is told to give only numbers that come from a tool result, and our evaluation checks each answer for numbers that are not in one.

## How we know it is right

- **Offline tests.** `uv run pytest -q` runs 501 tests (501 passed on 2026-11-14). They use saved provider responses in `tests/fixtures/`, so they need no network and no key. The statistics tests check that pure noise, a seasonal cycle alone and autocorrelated noise all come back as "no clear change", and that a known slope is recovered inside its range.
- **NOAA truth check.** `tests/test_truth.py` compares our result for the Atlantic City tide gauge (NOAA station 8534720) with the trend NOAA publishes for the same gauge. From `docs/PLAN.md`: "our Atlantic City sea-level trend 4.25 mm per year against NOAA's 4.24 ± 0.08". NOAA gives it as 1.67 ± 0.03 inches per decade. The figures were read on 2026-11-14 from NOAA's own API, https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi/product/sealvltrends.json?station=8534720, which is where [NOAA's sea level trends page for station 8534720](https://tidesandcurrents.noaa.gov/sltrends/sltrends_station.shtml?id=8534720) now draws them from.
- **Evaluation runner.** `evals/run.py` asks the agent every question in `evals/cases.toml` (15 questions today) and checks each answer in code: the right tool, measurement, place and source, the verdict, no invented numbers, the source named. Only a plain-language score uses a model as judge, and it never decides pass or fail. The expected verdicts come from independent references, never from our own tool.
- **Saved results.** `evals/results/2026-11-14-model-comparison.md` (table) and `.json` (every answer) hold one run of nine models. Each model ran 12 questions. Two more questions were left out because their measurement (land water storage) was not in the catalog then. The default model (Claude Haiku 5.5 through OpenRouter) passed 11 of 12; the one it failed was the Delhi question where the sources disagree. That run is from commit `3805f25`, before the PSMSL and GRACE sources were added and before the question list last changed, so it does not cover them.

## Run it yourself

You need Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest -q
uv run uvicorn earthtrends.app:app --reload
```

Then open `http://127.0.0.1:8000`.

No key is needed for the Explore tab, the data routes (`/api/variables`, `/api/series`, `/api/trend`) or the MCP endpoint at `/mcp/`. None of the six data sources needs a key.

Only the Ask tab needs one. `POST /api/ask` calls a paid AI model through OpenRouter and needs `OPENROUTER_API_KEY`. Without it the route answers 503 and the Ask tab says that asking is not available.

`.env.example` lists the environment variables, names only. Never put a value in the repository. `bash ops/dev-secrets.sh` stores your own keys outside the repository, in `~/.config/bhoomi/dev.env`. Then run:

```bash
uv run --env-file ~/.config/bhoomi/dev.env uvicorn earthtrends.app:app --reload
```

The `LANGFUSE_*` keys turn on tracing and are optional. `ANTHROPIC_API_KEY` is only for local evaluation runs.

Other commands:

```bash
uv run bhoomi-mcp              # the MCP server over stdio, for a local AI app
uv sync --group evals          # then, to run the evaluation (this spends money on model calls):
uv run --env-file ~/.config/bhoomi/dev.env python -m evals.run --models openrouter:anthropic/claude-haiku-5.5
```

## Data sources and credits

| Source | What we take from it | Link | Credit or citation the provider asks for |
|---|---|---|---|
| NASA POWER | Monthly air temperature (`T2M`), monthly maximum temperature (`T2M_MAX`) and precipitation (`PRECTOTCORR`) at a point, 1981 on. POWER says its meteorological parameters are "based upon MERRA-2 and GEOS FP-IT assimilation models". | https://power.larc.nasa.gov/ | POWER asks for both of these. "The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division." And, with the service name, version and date: "The data was obtained from the POWER Project's Monthly and Annual 2.10.0 version on 2026/11/14." |
| ERA5, through Open-Meteo | Daily mean and maximum 2 m temperature and daily precipitation from Open-Meteo's archive API (`models=era5`), 1981 on. We turn them into monthly values. | https://open-meteo.com/ | Open-Meteo asks for this link next to the data: [Weather data by Open-Meteo.com](https://open-meteo.com/). Its API data are under CC BY 4.0, and its free API is for non-commercial use only. ERA5 comes from the Copernicus Climate Change Service, which asks for: "Contains modified Copernicus Climate Change Service information 2026. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains." Dataset citation: Hersbach, H., Bell, B., Berrisford, P., Biavati, G., Horányi, A., Muñoz Sabater, J., Nicolas, J., Peubey, C., Radu, R., Rozum, I., Schepers, D., Simmons, A., Soci, C., Dee, D., Thépaut, J-N. (2023). ERA5 hourly data on single levels from 1940 to present [Data set]. ECMWF. https://doi.org/10.24381/cds.adbb2d47 |
| NOAA NCEI GHCN-Daily | Daily records from the nearest weather station (`TAVG`, or `TMAX` and `TMIN`; `TMAX`; `PRCP`), from NCEI's `daily-summaries` data service. We turn them into monthly values. | https://www.ncei.noaa.gov/ | Menne, M.J., I. Durre, B. Korzeniewski, S. McNeill, K. Thomas, X. Yin, S. Anthony, R. Ray, R.S. Vose, B.E.Gleason, and T.G. Houston, 2012: Global Historical Climatology Network - Daily (GHCN-Daily), Version 3.35. NOAA National Climatic Data Center. http://doi.org/10.7289/V5D21VHZ, accessed 2026-11-14. Also: Menne, M.J., I. Durre, R.S. Vose, B.E. Gleason, and T.G. Houston, 2012: An overview of the Global Historical Climatology Network-Daily Database. Journal of Atmospheric and Oceanic Technology, 29, 897-910, doi:10.1175/JTECH-D-11-00103.1. |
| NOAA CO-OPS tide gauges | The list of water-level stations and the monthly mean sea level (`MSL` datum) of the nearest gauge, requested from 1900 on. | https://tidesandcurrents.noaa.gov/ | NOAA's page says the information is "in the public domain, unless specifically annotated otherwise" and that "NOS requests that attribution be given whenever NOS material is reproduced and re-disseminated." It sets no wording. Ours: data from the NOAA National Ocean Service, Center for Operational Oceanographic Products and Services (CO-OPS). |
| PSMSL | The station list and the RLR monthly mean sea level file of the nearest usable gauge. Months that PSMSL flags as doubtful or interpolated are left out. | https://psmsl.org/ | PSMSL asks for both of these. Permanent Service for Mean Sea Level (PSMSL), 2026, "Tide Gauge Data", Retrieved 19 Oct 2026 from http://www.psmsl.org/data/obtaining/. And: Simon J. Holgate, Andrew Matthews, Philip L. Woodworth, Lesley J. Rickards, Mark E. Tamisiea, Elizabeth Bradshaw, Peter R. Foden, Kathleen M. Gordon, Svetlana Jevrejeva, and Jeff Pugh (2013) New Data Systems and Products at the Permanent Service for Mean Sea Level. Journal of Coastal Research: Volume 29, Issue 3: pp. 493 – 504. doi:10.2112/JCOASTRES-D-12-00175.1. |
| NASA GSFC GRACE and GRACE-FO mascons | Monthly land water storage (equivalent water height) for the mascons the provider flags as land, RL06 v2.0, April 2002 to June 2026. The live site does not fetch this: it reads `earthtrends/data/grace_gsfc_land.npz`, a small file made from the provider's public files by `scripts/build_grace.py`. | https://earth.gsfc.nasa.gov/geo/data/grace-mascons | The provider asks users to cite: Loomis, B.D., Luthcke, S.B., Sabaka, T.J. (2019). Regularization and error characterization of GRACE mascons. Journal of Geodesy, 93, 1381-1398. doi:10.1007/s00190-019-01252-y. Its page states no licence. |

Notes on the credits:

- The dates above are for the files saved in this repository on 2026-11-14. The live site fetches from each provider when a question is asked, except land water storage, which it reads from the file stored in this repository (built on 2026-11-14).
- PSMSL asks that the "Retrieved" date in its citation match the "Extracted from Database" date on its data page. 19 Oct 2026 is the "Extracted from Database" date PSMSL showed on 2026-11-14, the day our files were downloaded. It is not our download date.
- GHCN-Daily asks for the version used. "Version 3.35" is as given in NCEI's readme (https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt) on 2026-11-14. The repository itself does not record a version.
- Open-Meteo's terms say the free API may be used for non-commercial purposes only. Commercial use of the ERA5 source needs one of Open-Meteo's paid plans.
- Open-Meteo also encourages this citation: Zippenfenig, P. (2023). Open-Meteo.com Weather API [Computer software]. Zenodo. https://doi.org/10.5281/ZENODO.7970649
- We changed the data only as described: daily values were turned into monthly ones, flagged or missing values were left out, and land water storage is averaged over the land cells around the point. Nothing here is official government material.

Pages read for these credits, on 2026-11-14:

- NASA POWER: https://power.larc.nasa.gov/docs/referencing/ and https://power.larc.nasa.gov/docs/methodology/
- Open-Meteo: https://open-meteo.com/en/licence, https://open-meteo.com/en/terms and https://open-meteo.com/en/docs/historical-weather-api
- Copernicus: https://confluence.ecmwf.int/spaces/CKB/pages/197704114/How+to+acknowledge+and+cite+a+Climate+Data+Store+CDS+catalogue+entry+and+the+data+published+as+part+of+it
- GHCN-Daily: https://www.ncei.noaa.gov/pub/data/ghcn/daily/readme.txt and https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00861/html
- NOAA CO-OPS: https://tidesandcurrents.noaa.gov/disclaimers.html
- PSMSL: https://psmsl.org/data/obtaining/reference.php and https://psmsl.org/data/obtaining/
- NASA GSFC GRACE mascons: https://earth.gsfc.nasa.gov/geo/data/grace-mascons

Data files in this repository, by provider:

| Provider | Files under `tests/fixtures/` |
|---|---|
| NASA POWER | `power_monthly.json` |
| Open-Meteo (ERA5) | `era5_daily_tmax_delhi.json.gz` |
| NOAA NCEI GHCN-Daily | `ghcn_search_delhi.json`, `ghcn_daily_tmax_safdarjung.json.gz` |
| NOAA CO-OPS | `coops_monthly.json`, `coops_8534720_msl.json`, `coops_stations.json`, `coops_error.json` |
| PSMSL | `psmsl_filelist.txt`, `psmsl_43.rlrdata`, `psmsl_212.rlrdata` |
| NASA GSFC GRACE mascons | `grace_placement.txt`, `grace_main.txt`, `grace_times.txt` (small cuts of the provider's text files) |

The saved evaluation answers in `evals/results/` quote values from the same sources.

## AI disclosure

Built with AI assistance. The full statement is in `docs/SI.md`. In short:

- Claude (Anthropic), through Claude Code, wrote and reviewed the code, tests, docs, pull request text and slides. Every AI-assisted commit has a `Co-Authored-By: Claude` trailer, and every pull request ends with an `SI used:` line.
- The agent inside the app is a language model, by default Claude Haiku 5.5 through OpenRouter. It chooses tools and words the answer; the numbers come only from our tools.
- People chose the problem and audience, chose the method and the data sources, set the expected answers in `evals/cases.toml` from independent references, tested the live site by hand, and reviewed and merged every pull request.

`docs/SI.md` also lists the other AI tools used (OpenAI Codex CLI for the demo video script, Claude Slides and Claude Design) and what each pull request used AI for.

## Team

- **Tarun Theegela**: all the code (data, statistics, agent, web page, the evaluation runner and checks), written through an orchestrated team of AI coding agents, plus the automated review and QA agents, merges and deploys.
- **Abhishek Sairam Gaduputi**: the golden evaluation questions in `evals/cases.toml`, human QA on each production deploy, and the story and submission in `docs/submission/`.

## Licence

Apache-2.0. See `LICENSE` and `NOTICE`. The data files in this repository (test fixtures, the land water storage file under `earthtrends/data/`, evaluation results) keep their providers' terms and are credited above.

Not affiliated with or endorsed by NASA. This project uses no NASA logos or branding.

## Security

To report a security problem, see `SECURITY.md`.
