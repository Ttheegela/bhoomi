# Local judging pitch (Sun 14:00, Princeton Public Library)

**Final draft, Sat 14 Nov night.** It follows the demo flow Tarun set on #18: New York sea level → Delhi "sources disagree" on the Ask tab → Delhi groundwater → Mumbai sea level since 1878 → the "Use in your AI" page.

**Slot:** 7 to 10 minutes including Q&A, and **both of us present**. This script runs about 6¾ minutes, which leaves 2 to 3 minutes for questions.
**Slides:** a 10-slide deck in Claude Slides ("Trend Detective pitch"); Sairam shares the link. It downloads as PDF or PowerPoint. The demo slides (3 to 6) hold the same numbers as screenshots. If the Wi-Fi or a live answer fails, stay on the slide and keep talking.
**Rules:** every slide shows **"Built with AI assistance"**. No NASA logos or branding. Every number we say or show names its source. Numbers below were checked on production on Sat 14 Nov at about 23:50 UTC and again on Sun 15 Nov at about 16:30 UTC (unchanged); quote what the tool returns on the day.

| # | Slide | Who | Time |
|---|---|---|---|
| 1 | The question | Sairam | 0:20 |
| 2 | Why it's hard | Sairam | 0:30 |
| 3 | Live: New York sea level (Explore) | Tarun | 0:45 |
| 4 | Live: Delhi, sources disagree (Ask) | Tarun | 1:00 |
| 5 | Live: Delhi groundwater (Ask) | Sairam | 0:50 |
| 6 | Live: Mumbai since 1878 (Ask) | Sairam | 0:30 |
| 7 | Live: Use in your AI + how it works | Tarun | 0:45 |
| 8 | How we know it's right | Sairam | 0:45 |
| 9 | Who it's for | Sairam | 0:30 |
| 10 | How we used AI, what's next | Tarun | 0:30 |

## Before we start (5 minutes before the slot)
- Laptop on power, notifications off, browser zoom 125%, light mode.
- Tab 1: the deck. Tab 2: https://trend-detective-six.vercel.app/#variable=sea_level&lat=40.71&lon=-74.01 (New York, already loaded). Tab 3: the Ask tab, empty. Tab 4: https://trend-detective-six.vercel.app/#tab=connect
- Ask each Ask question once in a private window before the slot, so the data is warm in the cache.
- Backup: a screen recording of slides 3 to 7 from Sunday morning, on the laptop.

## Slide 1: The question (Sairam, 20 s)
**Say:** "Every week someone says 'the floods are getting worse here' or 'summers are hotter than when I was a kid.' Is that really true for *your* place, or is it just a bad year? That's hard to answer, even with public NASA and NOAA data."
**Show:** title "Trend Detective", one line: *Is this really changing here?*

## Slide 2: Why it's hard (Sairam, 30 s)
- The data exists, but it's spread across many portals and formats.
- Seasons and noise hide the trend. A hot summer isn't a trend.
- Different datasets can disagree for the same place.
**Say:** "Most tools draw a line through the data. A line always goes up or down. We ask whether the change is real. Tarun will show you."

## Slide 3: Live, New York sea level (Tarun, 45 s)
Tab 2, Explore. Live: type "New York" in **Search for a place** (or tap it on the map, where the dots are tide gauges), then pick **Sea level**. Tab 2 is preloaded with the same result in case the search is slow.
Point at, top to bottom:
- **What this means for you:** "Sea level here has clearly been rising. About 3 cm higher every 10 years." How sure we are: **Very clear**. What past data can't tell you: "It cannot tell you how high the sea will get."
- the verdict: **rising, +31.8 mm per decade** (95% range +30.6 to +33.0), January 1900 to October 2026
- the chart with the seasons removed, the trend line and its shaded range
- the source line: NOAA CO-OPS tide gauge at The Battery
**Say:** "Search for your town or tap the map. It pulls the monthly record, takes out the seasons, and tests whether the change beats chance. Then it says it in plain words: about three centimetres higher every ten years, very clear, and what the past can't tell you. And it names the gauge."

## Slide 4: Live, Delhi, when sources disagree (Tarun, 60 s)
Tab 3, Ask: **"Are Delhi's hottest days getting hotter? Check more than one data source."** (about 20 s to answer; talk while it works)
**Say while it works:** "Now in plain words. The agent picks the measurement and the place, and calls our tools three times, once per dataset."
**Point at the answer:** "The sources disagree." NASA POWER: falling, −0.25 °C per decade. ERA5: no clear change, +0.13. The Safdarjung weather station (NOAA GHCN): rising, +0.25. (Live on Sat 14 Nov, hottest day of each month, 1981 to 2025.)
**Say:** "Grid cells 25 to 50 km wide, versus one station in a growing city. An honest tool shows the disagreement instead of picking a side."
**Fallback:** if the answer is slow or odd, show slide 4, or use Explore: Delhi, "Hottest day", switch the source.

## Slide 5: Live, Delhi groundwater (Sairam, 50 s)
Tab 3, Ask: **"Is groundwater running out in Delhi?"** (about 6 s)
**Point at:** water stored on land near Delhi is **clearly falling, −43.85 cm per decade** (range −47.27 to −40.08), April 2002 to June 2026, from NASA's GRACE and GRACE-FO satellites, which weigh water by its gravity.
**Then the honest part:** the answer says this adds up soil moisture, groundwater, snow, lakes and rivers, so it can't show groundwater alone or how much is left.
**Then the guidance line** at the end of the answer: **High risk**, falling about 4.4 cm a year; for farming or a new well, don't rely on groundwater here without a secure supply. It ends: "This guidance isn't perfect. It is based only on past records."
**Say:** "It tells you what the data can show, and what it can't. And then what that could mean for a decision, with the warning attached."

## Slide 6: Live, Mumbai since 1878 (Sairam, 30 s)
Tab 3, Ask: **"Is sea level rising in Mumbai?"** (about 8 s)
**Point at:** **rising, +9.36 mm per decade** (range 8.30 to 10.44), January 1878 to December 2024, Apollo Bandar tide gauge, PSMSL.
**Guidance line:** **Low risk**, rising more slowly than the world average (NASA, about 3.4 mm a year since 1993). If the past trend continues: +2.2 to +2.7 cm by 2050, with a link to NASA's sea-level projection tool for the real future.
**Say:** "Not just US coasts. Tide gauges worldwide, and this one has almost 150 years of records. The US network had no gauge here, so the agent switched to the worldwide archive and said so."

## Slide 7: Live, use it in your own AI, and how it works (Tarun, 45 s)
Tab 4: **Use in your AI**. Show the server address and the Claude steps.
**Say:** "Everything you just saw is open. Any AI app that speaks MCP, like Claude, ChatGPT or Copilot, can call the same three tools with no key." Then, on the slide: question → agent → MCP tools (`list_variables`, `get_series`, `detect_trend`) → public data (NASA POWER/MERRA-2, ERA5, NOAA GHCN, NOAA CO-OPS and PSMSL tide gauges, NASA GSFC GRACE/GRACE-FO) → remove the seasons → Mann-Kendall test with Sen's slope, adjusted for autocorrelation → rising, falling or no clear change.
**Say:** "The model never does the maths. It can only quote numbers that came back from a tool."

## Slide 8: How we know it's right (Sairam, 45 s)
- **Truth check:** Atlantic City sea level, ours +42.5 mm per decade (41.1 to 44.0) versus NOAA's own published 42.4 ± 0.8 for the same gauge (station 8534720). They match.
- **Satellites versus a published study:** north-west India, Aug 2002 to Oct 2008. Our GRACE land water fall is 5.3 cm a year (3.9 to 6.9); Rodell, Velicogna and Famiglietti (2009, *Nature*) report groundwater falling 4.0 ± 1.0. The ranges overlap.
- **Golden questions:** 15 questions with answers set from NOAA and published papers, never from our own tool. The agent on the live site (Claude Haiku 5.5) passes **all 15** in the runs of Sun 15 Nov at 06:00 and again at about 16:20 UTC, after the guidance feature, on the code that's live, including the ones it must decline: "Will it rain tomorrow?" (a forecast) and "Is sea level rising in Delhi?" (inland). It never invented a number.
- **Stats tests:** pure noise, seasons only and autocorrelated noise all come back "no clear change", so it doesn't cry wolf.

## Slide 9: Who it's for (Sairam, 30 s)
**Say:** "Students and teachers checking a claim about their own town. But also anyone who needs a local trend they can trust: insurers looking at coastal property, heat, rain and water on land; city planners asking whether flooding, heat or water shortage is really getting worse. Honesty is the feature: ask about sea level in Delhi and it says Delhi is inland, with no estimate and no made-up number."

## Slide 10: How we used AI, what's next (Tarun, 30 s)
**Say (AI use, judges asked for it):** "We built this with AI coding agents: Claude Code wrote and reviewed most of the code, tests and docs, and a language model runs the agent inside the app. We chose the problem, the statistics, the data sources and the expected answers, and reviewed every change. Details and citations are in `docs/SI.md`."
**Next:** floods, snow and air quality; groundwater from well records next to the satellites; a classroom mode for teachers.
**Close:** "Trend Detective: is this really changing here? Now anyone can check." Leave the URL on screen for questions.

## Likely judge questions
- *Why not just fit a line?* A line always has a slope. Mann-Kendall asks if the change beats chance; Sen's slope isn't thrown off by outliers.
- *Why do sources disagree?* Grid cells 25 to 50 km wide versus a single station, different methods, a city growing around the station.
- *Where's the AI risk?* The agent can't invent numbers: every number in an answer must appear in a tool result, and our evals check that. In Sunday's runs it passed all 15 golden questions every time. At noon it also passed 14 of 15 extra behaviour checks; the one miss was a connection error in our test runner, and the live site answers that question fine.
- *What NASA data?* NASA POWER (built on MERRA-2, from the challenge's Resources list) and the NASA GSFC GRACE/GRACE-FO mascons (RL06 v2.0; Loomis, Luthcke and Sabaka 2019).
- *Isn't a risk level dangerous advice?* It is computed in code from the measured rate against a published reference (NASA's world-average sea-level rise, for example), never by the model. Every guidance line says it is based only on past records and isn't professional advice, and "if the past trend continues" is labelled as exactly that, with a link to the official projection tool. Rules are in `docs/RISK.md`.
- *Is the GRACE number groundwater?* No. It is all water on land together (soil moisture, groundwater, snow and ice, lakes and rivers), averaged over about 400 km and compared with its 2004 to 2009 average. The answer says so. There is no data from mid-2017 to mid-2018, between the two satellite missions.
- *Why does Central Valley say "no clear change" for 2003 to 2010?* A short window. Our range (−48 to +5 mm a year) contains the published −31.0 ± 2.7 (Famiglietti et al. 2011). Over the full record it is clearly falling, 17.5 cm per decade.
- *Why did New York use two sources?* The agent checks NOAA's gauge, then the worldwide PSMSL archive; both agree for The Battery.
