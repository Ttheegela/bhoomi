# Space Apps project page text (final, ready to paste)

Tarun pastes this into the Space Apps project page (he owns the team). Numbers below were checked on production on Sat 14 Nov at about 23:50 UTC, and the eval score is from the run that night; re-check on Sunday morning. Aim to submit by Sun 18:00; the deadline is 23:59. Each section below matches one field of the page; paste the text without the headings.

## Title
Trend Detective: is this really changing here?

## Short summary
Trend Detective is an AI agent and MCP server that answers one question for any place: *is this really changing here?* Ask in plain words, for example "Is sea level rising in New York?" (rising, about 32 mm per decade at The Battery tide gauge since 1900, from NOAA). It picks the right public NASA or NOAA dataset, pulls the time series, removes the seasonal cycle, and runs a proper significance test. Then it answers rising, falling, or no clear change, with the size of the change, an uncertainty range, and the data source. It covers air temperature, the hottest day of the month, rainfall, sea level at tide gauges worldwide, and water stored on land, weighed from space by NASA's GRACE satellites. When datasets disagree, it says so; when there is no data for a place, it says that too, with no made-up number. On the Explore page you search for your town or tap a map (the dots are tide gauges), and a "What this means for you" card says it in plain words: for New York, "about 3 cm higher every 10 years", how sure we are, and what past data can't tell you. On the Ask page you can ask follow-up questions, and the chat remembers. It's built for students and the public, and for anyone who needs a local trend they can trust.

## How it works
1. **Ask or pick.** Type a question on the Ask page, or search for a place or tap the map on Explore. The AI agent works out the place and what to measure.
2. **Fetch.** Through MCP tools (`list_variables`, `get_series`, `detect_trend`), it pulls a monthly time series from a public dataset.
3. **Test.** It removes the seasons, then runs the Mann-Kendall trend test with Sen's slope, adjusted for autocorrelation, to give a slope per decade with a 95% range.
4. **Answer.** Rising, falling, or no clear change. Every number names its source. The agent can't state a number that isn't in a tool result.
5. **Open.** Any MCP-capable AI assistant can use the same tools at `https://trend-detective-six.vercel.app/mcp/`.

## How we checked it
- Our Atlantic City sea-level trend is +42.5 mm per decade (95% range +41.1 to +44.0). NOAA publishes 1.67 ± 0.03 inches per decade for the same tide gauge (station 8534720), which is 42.4 ± 0.8 mm per decade. They match.
- Our statistics tests check that pure noise, seasonal-only data and autocorrelated noise all come back as "no clear change", so the tool doesn't cry wolf.
- The AI agent on the live site (Claude Haiku 5.5) passes all 15 golden questions (Sun 15 Nov, 06:00 UTC, on the live code), with expected answers from independent references (NOAA, published papers), and never invented a number. Results: `evals/results/2026-11-15-sunday-morning/`. Other models were compared on the same questions in `evals/results/`.
- For north-west India, August 2002 to October 2008, our GRACE land water trend is a fall of 5.3 cm of water a year (range 3.9 to 6.9); Rodell, Velicogna and Famiglietti (2009, *Nature*, doi:10.1038/nature08238) report groundwater there falling 4.0 ± 1.0 cm a year over the same months. The ranges overlap.

## Data sources
- NASA POWER (MERRA-2): https://power.larc.nasa.gov/
- ERA5 reanalysis via the Open-Meteo archive: https://open-meteo.com/
- NOAA NCEI GHCN-Daily: https://www.ncei.noaa.gov/
- NOAA CO-OPS tide gauges: https://tidesandcurrents.noaa.gov/
- PSMSL tide gauges, worldwide (Permanent Service for Mean Sea Level): https://psmsl.org/
- NASA GSFC GRACE and GRACE-FO mascons, RL06 v2.0 (Loomis, Luthcke and Sabaka 2019, *J. Geodesy* 93, doi:10.1007/s00190-019-01252-y): https://earth.gsfc.nasa.gov/geo/data/grace-mascons

All six are used by the live build (checked Sat 14 Nov).

## Links
- Live app: https://trend-detective-six.vercel.app
- Code: https://github.com/Ttheegela/trend-detective
- Demo video (30 s or less, recorded from the live site; script in `docs/submission/video.md`): New York sea level, Delhi sources disagree, Delhi land water, Mumbai since 1878. Upload the MP4 to the page.
- Slides: the 10-slide pitch deck as PDF (exported from Claude Slides). At local judging we demo live and keep the deck as backup.
- Screenshots (`docs/submission/screenshots/`), in this order:
  1. `new-york-sea-level-desktop.jpg`: Explore, New York sea level: the map with tide gauges, "What this means for you", rising, NOAA CO-OPS.
  2. `delhi-sources-disagree-ask.jpg`: Ask, Delhi's hottest days, three sources that disagree.
  3. `delhi-water-storage-phone.jpg`: Explore on a phone, Delhi land water: "clearly been decreasing, about 40 cm less water every 10 years", NASA GRACE.
  4. `delhi-groundwater-phone.jpg`: Ask on a phone, the same question in words, with the caveat that it isn't groundwater alone.
  5. `atlantic-city-desktop.jpg`: Atlantic City, the trend we checked against NOAA's published one.

## Use of AI (SI disclosure)
See `docs/SI.md`. Short version for the page: we used Claude (Anthropic) as a coding assistant to write and review most of the code, tests, docs and these slides, and an LLM through OpenRouter runs the agent inside the app. People chose the problem, the statistical method, the data sources and the expected answers in our evals, and reviewed every change. AI-made slides and video carry a visible "Built with AI assistance" label.
