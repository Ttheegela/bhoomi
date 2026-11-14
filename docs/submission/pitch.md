# Local judging pitch (Sun 14:00, Princeton Public Library)

**Slides:** the 8-slide deck is built in Claude (Slides artifact "Trend Detective pitch"); ask Sairam for the share link. It downloads as PDF or PowerPoint. Real numbers are already in: Atlantic City +42.5 mm/decade vs NOAA's published 42.4 ± 0.8 mm/decade (1.67 in/decade), and the golden-question score on slide 6. **Video:** see `video.md`.

Draft. Judging slot is 7 to 10 minutes including Q&A, and **both Tarun and Sairam present**. This script is about 4 minutes, which leaves room for the live demo and questions. Suggested split: Sairam slides 1, 2, 6, 7, 8; Tarun the live demo (3, 4) and slide 5. Also say in a sentence or two how we used AI (judges asked for it): see the SI paragraph in `project-page.md`.
Every slide carries the visible label **"Built with AI assistance"**. No NASA logos or branding. Monochrome, matching the app.
Every number spoken or shown names its data source. Numbers here come from the live tool and the eval run on Sat 14 Nov (late evening, after GRACE and PSMSL went live); re-check them on Sunday morning.

## Slide 1: The question (20 s)
**Say:** "Every week someone says 'the floods are getting worse here' or 'summers are hotter than when I was a kid.' Is that really true for *your* place, or is it just a bad year? That's hard to answer, even with public NASA and NOAA data."
**Show:** title "Trend Detective", one line: *Is this really changing here?*

## Slide 2: Why it's hard (30 s)
- The data exists, but it's spread across many portals and formats.
- Seasons and noise hide the trend. A hot summer isn't a trend.
- Different datasets can disagree for the same place.
**Say:** "Most tools draw a line through the data. A line always goes up or down. We ask whether the change is real."

## Slide 3: Live demo, sea level in Atlantic City (60 s)
Ask the app: **"Is sea level rising in Atlantic City?"**
Point at:
- the chart with the season taken out
- the verdict and slope: rising, +42.5 mm per decade, 95% range +41.1 to +44.0 mm
- the source line: NOAA CO-OPS tide gauge, station 8534720
**Say:** "It picked the right dataset, pulled the data, tested it, and named the source."

## Slide 4: Live demo, Delhi, when sources disagree (45 s)
**Fallback:** the "gives up after three sources" bug (#50) is fixed, so the Ask box works. If the answer is slow or odd on the day, switch to the **Explore** page (pick Delhi, switch the source) or show the slide.
Ask: **"Are Delhi's hottest days getting hotter?"** (`air_temp_max`, 28.58, 77.21)
**Say:** "Three datasets, three answers. NASA POWER says falling, ERA5 says no clear change, the Safdarjung weather station says rising. Grid cells about 50 km wide versus one station in a growing city. An honest tool shows that instead of picking one."
**Show:** the three slopes side by side, each labelled with its source. Live values on Sat 14 Nov, 1981 to 2025, °C per decade: POWER −0.25 (falling), ERA5 +0.12 (no clear change), Safdarjung +0.25 (rising). Quote what the tool returns on the day.

## Slide 5: How it works (30 s)
Question → AI agent → MCP tools (`list_variables`, `get_series`, `detect_trend`) → public data (NASA POWER/MERRA-2, ERA5, NOAA GHCN, NOAA CO-OPS and PSMSL tide gauges, NASA GSFC GRACE/GRACE-FO) → remove the seasons → Mann-Kendall test + Sen's slope, adjusted for autocorrelation → verdict: rising / falling / no clear change.
**Say:** "Any AI assistant can plug into the same tools through MCP, not just ours."

## Slide 6: How we know it's right (40 s)
- **Truth check:** our Atlantic City trend matches NOAA's own published one for that station: ours +42.5 mm per decade (41.1 to 44.0) vs NOAA's 42.4 ± 0.8 (1.67 ± 0.03 inches per decade).
- **Stats tests:** pure noise, seasonal-only data and autocorrelated noise all come back "no clear change", so the tool doesn't cry wolf.
- **Golden questions:** expected answers come from independent references (NOAA, published papers). Our agent (Claude Haiku 5.5) passes 13 of 15 (87%) in the run of Sat 14 Nov, 23:30 UTC, with GRACE and worldwide tide gauges live; 9 models were compared on an earlier 12-question set (`evals/results/`). The two misses are being fixed in the agent: it looked up tide gauges for Delhi before saying it's inland (the answer itself had no numbers), and it named the wrong source in one "agrees" sentence. Re-run Sunday morning and quote that score.
- **Satellites vs a published study:** for north-west India, August 2002 to October 2008, our GRACE land water trend is a fall of 5.3 cm of water a year (range 3.9 to 6.9). Rodell, Velicogna and Famiglietti (2009, *Nature*) report groundwater there falling 4.0 ± 1.0 cm a year over the same months. Ours is all land water, theirs is groundwater, and the ranges overlap.
- Includes questions it must decline: "Will it rain tomorrow?" (a forecast, not a trend) and "Is sea level rising in Delhi?" (inland, no sea-level record).
**Show:** the eval pass/fail table, plus the Langfuse trace screenshot.

## Slide 7: Who it's for (Impact, 40 s)
**Say:** "Students and teachers can check a claim about their own town. But anyone who needs a local trend they can trust can use it: insurers looking at coastal property risk, heat, rain and water on land; city planners asking whether flooding, heat or water shortage is really getting worse."
**Honesty is the feature:** ask "Is sea level rising in Delhi?" and the agent replies that Delhi is inland, so there's no sea-level record, with no estimate and no made-up number. (A real reply from the eval run on Sat 14 Nov; this case is in `evals/cases.toml`.)
**Worldwide coasts:** sea level is no longer US only. Mumbai's Apollo Bandar tide gauge (PSMSL, records since 1878) gives rising, +9.4 mm per decade (range 8.3 to 10.4).
**Optional live moment (about 20 s):** ask "Is groundwater running out in Punjab and Haryana?" It answers that water on land is clearly falling (about 39 cm per decade, NASA GSFC GRACE/GRACE-FO, April 2002 to June 2026), then adds that this alone doesn't prove groundwater is running out, because the satellites weigh all land water together. **Say:** "It tells you what the data can and can't show."

## Slide 8: What's next (15 s)
More variables (floods, snow, air quality), groundwater from well records alongside the satellites, a classroom mode for teachers.
**Say:** "Trend Detective: is this really changing here? Now anyone can check." Then the live URL and QR code.

## Backup if the Wi-Fi or the live site fails
Keep a screen recording of slides 3 and 4 from Sunday morning, already on the laptop.

## Likely judge questions
- *Why not just fit a line?* A line always has a slope. Mann-Kendall asks if the change beats chance; Sen's slope isn't thrown off by outliers.
- *Why do sources disagree?* Grid cells about 50 km wide versus a single station, different methods, a city growing around the station.
- *Where's the AI risk?* The agent can't invent numbers: every number in an answer must appear in a tool result, and our evals check that.
- *What NASA data?* NASA POWER (built on MERRA-2, from the challenge's Resources list) and the NASA GSFC GRACE/GRACE-FO mascons (RL06 v2.0, Loomis, Luthcke and Sabaka 2019).
- *Is the GRACE number groundwater?* No. It is all water on land together (soil moisture, groundwater, snow and ice, lakes and rivers), averaged over about 400 km, compared with its 2004 to 2009 average. The answer says so. There is no data from mid-2017 to mid-2018, between the two satellite missions.
- *Why does Central Valley say "no clear change" for 2003 to 2010?* A short window. Our range (−48 to +5 mm a year) contains the published −31.0 ± 2.7 (Famiglietti et al. 2011; figures from Tarun's check in #18). Over the full record it is clearly falling, 17.5 cm per decade.
