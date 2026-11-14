# Local judging pitch (Sun 14:00, Princeton Public Library)

**Slides:** the 7-slide deck is built in Claude (Slides artifact "Trend Detective pitch"); ask Sairam for the share link. It downloads as PDF or PowerPoint. Real numbers are already in: Atlantic City +42.5 mm/decade vs NOAA's published 42.4 ± 0.8 mm/decade (1.67 in/decade). The only blank is the golden-question score on slide 6. **Video:** see `video.md`.

Draft. Judging slot is 7 to 10 minutes including Q&A, and **both Tarun and Sairam present**. This script is about 4 minutes, which leaves room for the live demo and questions. Suggested split: Sairam slides 1, 2, 6, 7; Tarun the live demo (3, 4) and slide 5.
Every slide carries the visible label **"Built with AI assistance"**. No NASA logos or branding. Monochrome, matching the app.
Every number spoken or shown names its data source. Numbers marked `TBD` are filled from the live tool on Sunday morning, never typed by hand.

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
- the verdict and slope: `TBD` per decade, 95% range `TBD` to `TBD`
- the source line: NOAA CO-OPS tide gauge, station 8534720
**Say:** "It picked the right dataset, pulled the data, tested it, and named the source."

## Slide 4: Live demo, Delhi, when sources disagree (45 s)
Ask: **"Are Delhi's hottest days getting hotter?"** (`air_temp_max`, 28.58, 77.21)
**Say:** "Three datasets, three answers. NASA POWER says falling, ERA5 says no clear change, the Safdarjung weather station says rising. Grid cells about 50 km wide versus one station in a growing city. An honest tool shows that instead of picking one."
**Show:** the three slopes side by side, each labelled with its source. Live values on Sat 14 Nov, 1981 to 2025, °C per decade: POWER −0.25 (falling), ERA5 +0.12 (no clear change), Safdarjung +0.25 (rising). Quote what the tool returns on the day.

## Slide 5: How it works (30 s)
Question → AI agent → MCP tools (`list_variables`, `get_series`, `detect_trend`) → public data (NASA POWER/MERRA-2, ERA5, NOAA GHCN, NOAA CO-OPS, GRACE) → remove the seasons → Mann-Kendall test + Sen's slope, adjusted for autocorrelation → verdict: rising / falling / no clear change.
**Say:** "Any AI assistant can plug into the same tools through MCP, not just ours."

## Slide 6: How we know it's right (40 s)
- **Truth check:** our Atlantic City trend falls inside NOAA's own published range for that station. (`TBD` ours vs NOAA's `TBD`)
- **Stats tests:** on 200 pure-noise series we raise a false alarm about `TBD`% of the time (target ≤ 5%).
- **Golden questions:** 14 questions with answers from independent references (NOAA, published papers). Pass rate `TBD`%.
- Includes questions it must refuse: "Will it rain tomorrow?", "Is sea level rising in Mumbai?" (no US tide gauge there).
**Show:** the eval pass/fail table, plus the Langfuse trace screenshot.

## Slide 7: What's next (15 s)
More variables (floods, snow, air quality), more tide gauges outside the US, a classroom mode for teachers.
**Say:** "Trend Detective: is this really changing here? Now anyone can check." Then the live URL and QR code.

## Backup if the Wi-Fi or the live site fails
Keep a screen recording of slides 3 and 4 from Sunday morning, already on the laptop.

## Likely judge questions
- *Why not just fit a line?* A line always has a slope. Mann-Kendall asks if the change beats chance; Sen's slope isn't thrown off by outliers.
- *Why do sources disagree?* Grid cells about 50 km wide versus a single station, different methods, a city growing around the station.
- *Where's the AI risk?* The agent can't invent numbers: every number in an answer must appear in a tool result, and our evals check that.
- *What NASA data?* NASA POWER (built on MERRA-2, from the challenge's Resources list) and GRACE/GRACE-FO.
