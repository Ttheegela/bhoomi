# Space Apps project page text (draft)

Tarun pastes this into the Space Apps project page (he owns the team). Numbers below are from the live tool and the eval run on Sat 14 Nov; re-check them on Sunday. Aim to submit by Sun 18:00; the deadline is 23:59.

## Title
Trend Detective: is this really changing here?

## Short summary
Trend Detective is an AI agent and MCP server that answers one question for any place: *is this really changing here?* Ask in plain words, for example "Is sea level rising in Atlantic City?". It picks the right public NASA or NOAA dataset, pulls the time series, removes the seasonal cycle, and runs a proper significance test. Then it answers rising, falling, or no clear change, with the size of the change, an uncertainty range, and the data source. When datasets disagree, it says so. It's built for students and the public.

## How it works
1. **Ask.** A student types a question. The AI agent works out the place and what to measure.
2. **Fetch.** Through MCP tools (`list_variables`, `get_series`, `detect_trend`), it pulls a monthly time series from a public dataset.
3. **Test.** It removes the seasons, then runs the Mann-Kendall trend test with Sen's slope, adjusted for autocorrelation, to give a slope per decade with a 95% range.
4. **Answer.** Rising, falling, or no clear change. Every number names its source. The agent can't state a number that isn't in a tool result.
5. **Open.** Any MCP-capable AI assistant can use the same tools at `https://trend-detective-six.vercel.app/mcp/`.

## How we checked it
- Our Atlantic City sea-level trend is +42.5 mm per decade (95% range +41.1 to +44.0). NOAA publishes 1.67 ± 0.03 inches per decade for the same tide gauge (station 8534720), which is 42.4 ± 0.8 mm per decade. They match.
- Our statistics tests check that pure noise, seasonal-only data and autocorrelated noise all come back as "no clear change", so the tool doesn't cry wolf.
- The AI agent passes 11 of 12 golden questions (92%), with expected answers from independent references (NOAA, published papers). Nine models were compared on the same questions; results in `evals/results/2026-11-14-model-comparison.md`. Two groundwater questions wait for the GRACE data source.

## Data sources
- NASA POWER (MERRA-2): https://power.larc.nasa.gov/
- ERA5 reanalysis via the Open-Meteo archive: https://open-meteo.com/
- NOAA NCEI GHCN-Daily: https://www.ncei.noaa.gov/
- NOAA CO-OPS tide gauges: https://tidesandcurrents.noaa.gov/
- GRACE/GRACE-FO JPL mascon CRI RL06.3 v4 (PO.DAAC): https://podaac.jpl.nasa.gov/

Only the sources the final build actually uses stay in this list.

## Links
- Live app: https://trend-detective-six.vercel.app
- Code: https://github.com/Ttheegela/trend-detective
- Demo: 7-slide deck (PDF), or a video of 30 s or less (`docs/submission/video.md`). Final choice: `TBD`.
- Screenshots: `docs/submission/screenshots/` (Atlantic City on desktop, Delhi on a phone in dark mode).

## Use of AI (SI disclosure)
See `docs/SI.md`. Short version for the page: we used Claude (Anthropic) as a coding assistant to write and review most of the code, tests, docs and these slides, and an LLM through OpenRouter runs the agent inside the app. People chose the problem, the statistical method, the data sources and the expected answers in our evals, and reviewed every change. AI-made slides and video carry a visible "Built with AI assistance" label.
