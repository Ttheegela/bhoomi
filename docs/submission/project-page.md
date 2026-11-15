# Space Apps project page text (final, ready to paste)

Tarun pastes this into the Space Apps project page (he owns the team). Numbers below were checked on production on Sun 15 Nov at about 17:15 UTC, on the reworked site (#113). Aim to submit by Sun 18:00; the deadline is 23:59. Each section below matches one field of the page; paste the text without the headings.

## Title
Bhoomi: is this really changing here?

## Short summary
Bhoomi is an AI agent and MCP server that answers one question for any place: *is this really changing here?* Ask in plain words, for example "Is sea level rising in New York?" (rising, about 32 mm per decade at The Battery tide gauge since 1900, from NOAA). It picks the right public NASA or NOAA dataset, pulls the time series, removes the seasonal cycle, and runs a proper significance test. Then it answers rising, falling, or no clear change, with the size of the change, an uncertainty range, and the data source. It covers air temperature, the hottest day of the month, rainfall, sea level at tide gauges worldwide, and water stored on land, weighed from space by NASA's GRACE satellites. When datasets disagree, it says so; when there is no data for a place, it says that too, with no made-up number. Each measurement has its own window. You search for your town or tap the map (on Sea level the dots are tide gauges), pin up to six places, and a recommendation card says what it means: for New York, "Moderate risk, +3.2 cm every 10 years, about as fast as the world average", what to check before you buy near the shore, "+7.3 to +7.9 cm by 2050 if the past trend continues", how sure we are, and the warning that it is based only on past records. The risk level is computed in code from the measured rate against a published reference (NASA's world-average sea-level rise, for example), never by the model. A chart and table compare your pinned places. On weather, you can switch between NASA POWER, ERA5 and the nearest weather station and see whether they agree. An assistant on every window answers questions in words, typed or spoken; its one tool is our checked agent. It's built for students and the public, and for anyone who needs a local trend they can trust.

## How it works
1. **Pick or ask.** Open a measurement's window and search for a place or tap the map, or ask the assistant in words. For a question, the AI agent works out the place and what to measure.
2. **Fetch.** Through MCP tools (`list_variables`, `get_series`, `detect_trend`), it pulls a monthly time series from a public dataset.
3. **Test.** It removes the seasons, then runs the Mann-Kendall trend test with Sen's slope, adjusted for autocorrelation, to give a slope per decade with a 95% range.
4. **Answer.** Rising, falling, or no clear change. Every number names its source. The agent can't state a number that isn't in a tool result.
5. **Guide.** Code (not the model) turns the rate into a risk level against a published reference, a suggestion, and an "if the past trend continues" range, labelled as based only on past records.
6. **Open.** Any MCP-capable AI assistant can use the same tools at `https://bhoomi.earth/mcp/`.

## How we checked it
- Our Atlantic City sea-level trend is +42.5 mm per decade (95% range +41.1 to +44.0). NOAA publishes 1.67 ± 0.03 inches per decade for the same tide gauge (station 8534720), which is 42.4 ± 0.8 mm per decade. They match.
- Our statistics tests check that pure noise, seasonal-only data and autocorrelated noise all come back as "no clear change", so the tool doesn't cry wolf.
- The AI agent on the live site (Claude Haiku 5.5) passes all 15 golden questions (Sun 15 Nov, 06:00 UTC and again at about 16:20 UTC after the guidance feature, on the live code), with expected answers from independent references (NOAA, published papers), and never invented a number. Results: `evals/results/2026-11-15-sunday-morning/` and `evals/results/2026-11-15-sunday-noon/`. Other models were compared on the same questions in `evals/results/`.
- For north-west India, August 2002 to October 2008, our GRACE land water trend is a fall of 5.3 cm of water a year (range 3.9 to 6.9); Rodell, Velicogna and Famiglietti (2009, *Nature*, doi:10.1038/nature08238) report groundwater there falling 4.0 ± 1.0 cm a year over the same months. The ranges overlap.

## Data sources
- NASA POWER (MERRA-2): https://power.larc.nasa.gov/
- ERA5 reanalysis via the Open-Meteo archive: https://open-meteo.com/
- NOAA NCEI GHCN-Daily: https://www.ncei.noaa.gov/
- NOAA CO-OPS tide gauges: https://tidesandcurrents.noaa.gov/
- PSMSL tide gauges, worldwide (Permanent Service for Mean Sea Level): https://psmsl.org/
- NASA GSFC GRACE and GRACE-FO mascons, RL06 v2.0 (Loomis, Luthcke and Sabaka 2019, *J. Geodesy* 93, doi:10.1007/s00190-019-01252-y): https://earth.gsfc.nasa.gov/geo/data/grace-mascons

All six are used by the live build (checked Sun 15 Nov).

## Links
- Live app: https://bhoomi.earth
- Code: https://github.com/Ttheegela/bhoomi
- Demo video (30 s or less, recorded from the live site; script in `docs/submission/video.md`): New York sea level, Delhi's three sources, Delhi land water, Mumbai since 1878 from the assistant. Upload the MP4 to the page.
- Slides: the 10-slide pitch deck as PDF (exported from Claude Slides). At local judging we demo live and keep the deck as backup.
- Screenshots (`docs/submission/screenshots/`, taken Sun 15 Nov on the reworked site), in this order:
  1. `new-york-sea-level-desktop.jpg`: Sea level window, New York: Moderate risk, +3.2 cm every 10 years, the recommendation and the look-ahead to 2050, NOAA tide gauge at The Battery, with the gauge map.
  2. `sea-level-compare-desktop.jpg`: the same window's chart comparing six pinned coasts since 1900, with dashed "if the past trend continues" lines.
  3. `delhi-water-storage-desktop.jpg`: Water storage window, Delhi: High risk, −44 cm every 10 years, NASA GRACE satellites.
  4. `delhi-assistant-desktop.jpg`: the assistant answering "Are Delhi's hottest days getting hotter? Check more than one data source.": the records disagree.

## Use of AI (SI disclosure)
See `docs/SI.md`. Short version for the page: we used Claude (Anthropic) as a coding assistant to write and review most of the code, tests, docs and these slides, an LLM through OpenRouter runs the agent inside the app, and the assistant's chat and voice run on ElevenLabs. People chose the problem, the statistical method, the data sources and the expected answers in our evals, and reviewed every change. AI-made slides and video carry a visible "Built with AI assistance" label.
