# Local judging pitch (Sun 14:00, Princeton Public Library)

**Final draft, Sat 14 Nov night.** It follows the demo flow Tarun set on #18, moved onto the reworked site (#113, Sun 15 Nov): New York sea level (Sea level window) → Delhi "sources disagree" (Hottest days window, switching the source) → Delhi land water (Water storage window) → Mumbai sea level since 1878 (the assistant) → Settings → "Use in your AI".

**Slot:** 7 to 10 minutes including Q&A, and **both of us present**. This script runs about 6¾ minutes, which leaves 2 to 3 minutes for questions.
**Slides:** a 10-slide deck in Claude Slides ("Trend Detective pitch"); Sairam shares the link. It downloads as PDF or PowerPoint. The demo slides (3 to 6) hold the same numbers as screenshots. If the Wi-Fi or a live answer fails, stay on the slide and keep talking.
**Rules:** every slide shows **"Built with AI assistance"**. No NASA logos or branding. Every number we say or show names its source. Numbers below were checked on production on Sun 15 Nov at about 17:15 UTC, on the reworked site; quote what the tool returns on the day.

| # | Slide | Who | Time |
|---|---|---|---|
| 1 | The question | Sairam | 0:20 |
| 2 | Why it's hard | Sairam | 0:30 |
| 3 | Live: New York sea level (Sea level window) | Tarun | 0:45 |
| 4 | Live: Delhi, sources disagree (Hottest days) | Tarun | 1:00 |
| 5 | Live: Delhi water on land (Water storage) | Sairam | 0:50 |
| 6 | Live: Mumbai since 1878 (assistant) | Sairam | 0:30 |
| 7 | Live: Use in your AI + how it works | Tarun | 0:45 |
| 8 | How we know it's right | Sairam | 0:45 |
| 9 | Who it's for | Sairam | 0:30 |
| 10 | How we used AI, what's next | Tarun | 0:30 |

## Before we start (5 minutes before the slot)
- Laptop on power, notifications off, browser at 125% zoom. The app opens in light mode by default.
- The site now has one window per measurement (Sea level, Air temperature, Hottest days, Rain, Water storage) plus Settings. There are no Explore or Ask tabs any more (#113). Questions in words go to the **assistant** at the bottom right of every window.
- Pin the demo places beforehand in the same browser (pins are kept in that browser):
  - **Sea level:** New York, NY among the pinned places, selected.
  - **Hottest days:** Delhi, selected, source set to **NASA POWER**.
  - **Water storage:** Delhi, selected.
- Tab 1: the deck. Tab 2: https://trend-detective-six.vercel.app/#sea-level. Tab 3: https://trend-detective-six.vercel.app/#hottest-days. Tab 4: https://trend-detective-six.vercel.app/#water-storage. Settings → **Use in your AI** is one click away from any of them.
- **Type** to the assistant, don't talk to it: the room will be noisy. Ask the Mumbai question once before the slot so the data is warm in the cache.
- Backup: a screen recording of slides 3 to 7 from Sunday, on the laptop.

## Slide 1: The question (Sairam, 20 s)
**Say:** "Every week someone says 'the floods are getting worse here' or 'summers are hotter than when I was a kid.' Is that really true for *your* place, or is it just a bad year? That's hard to answer, even with public NASA and NOAA data."
**Show:** title "Trend Detective", one line: *Is this really changing here?*

## Slide 2: Why it's hard (Sairam, 30 s)
- The data exists, but it's spread across many portals and formats.
- Seasons and noise hide the trend. A hot summer isn't a trend.
- Different datasets can disagree for the same place.
**Say:** "Most tools draw a line through the data. A line always goes up or down. We ask whether the change is real, and what it means for you. Tarun will show you."

## Slide 3: Live, New York sea level (Tarun, 45 s)
Tab 2, **Sea level** window, New York selected. Live: type a town in **Search a coastal town or city**, or tap a tide-gauge dot on the map, to show how a place gets pinned.
Point at, top to bottom on the card:
- the source line: **NOAA tide gauge at The Battery, 1900–2026**
- **Moderate risk, +3.2 cm every 10 years.** "The sea here is rising about as fast as the world average."
- **Our recommendation:** "For a long-term home or investment near the shore here, check how high the site sits above flood level before you commit."
- **If the past trend continues: +7.3 to +7.9 cm by 2050.** How sure we are: **Very clear, 126 years of data.**
- the disclaimer under it: based only on past records, not professional advice
Then scroll to **Compare your places**: Grand Isle, Louisiana is rising **2.4×** the world average (NASA, about 3.4 mm a year since 1993), **High risk**.
**Say:** "Pick your town. It pulls the tide-gauge record, takes out the seasons, and tests whether the change beats chance. Then it tells you what it means: moderate risk here, what to check before you buy, and how much higher by 2050 if the past simply continues. Every number names its gauge."

## Slide 4: Live, Delhi, when sources disagree (Tarun, 60 s)
Tab 3, **Hottest days** window, Delhi selected. Switch **Measured by** live, one at a time (each loads in under 10 s):
- **NASA POWER:** −0.25 °C every 10 years, Low risk, "getting less hot".
- **ERA5:** no clear change.
- **Weather station** (NOAA, New Delhi Safdarjung): +0.25 °C every 10 years, Moderate risk.
(Live on Sun 15 Nov, hottest day of each month, 1981 to 2025.)
**Say:** "Same city, three records, three answers. Grid cells 25 to 50 km wide, versus one station in a growing city. An honest tool shows you the disagreement instead of picking a side."
**Optional:** the assistant says the same in words for "Are Delhi's hottest days getting hotter? Check more than one data source." It takes up to a minute, so only type it at the start of slide 3 if you want it.

## Slide 5: Live, Delhi water on land (Sairam, 50 s)
Tab 4, **Water storage** window, Delhi selected.
**Point at:** **NASA GRACE satellites, 2002–2026. High risk, −44 cm every 10 years.** "Water stored in this region is falling by about 4.4 cm a year." Our recommendation: "For farming or a new well, we'd advise against relying on groundwater here without a secure supply."
**Then the honest part:** open **How we calculated this**. Exact rate −43.8 cm per decade (range −47.3 to −40.1). Under "Caveats and notes": soil moisture, groundwater, snow and ice, lakes and rivers together, and "it cannot tell groundwater from surface water".
**Say:** "Satellites weigh the water by its gravity. It tells you what the data can show, what it can't, and what that could mean for a decision, with the warning attached."

## Slide 6: Live, Mumbai since 1878, in words (Sairam, 30 s)
Click the assistant's chat button (bottom right) and type: **"Is sea level rising in Mumbai?"** (about 20 s).
**Point at:** "Yes, the sea at Mumbai has been rising… about 9 mm (under 1 cm) higher every 10 years since 1878. The risk is rated low… about 2 to 3 cm higher by 2050."
**Say the source out loud:** "That's the Apollo Bandar tide gauge, from the worldwide PSMSL archive. Almost 150 years of records." Right now the assistant's reply doesn't name its source (#120), so the slide shows it: +9.36 mm per decade, January 1878 to December 2024, PSMSL.
**Say:** "Not just US coasts, and you can just ask. The assistant's one tool is our checked agent, so the numbers are the same ones you just saw."

## Slide 7: Live, use it in your own AI, and how it works (Tarun, 45 s)
**Settings → Use in your AI.** Show the server address and the Claude steps.
**Say:** "Everything you just saw is open. Any AI app that speaks MCP, like Claude, ChatGPT or Copilot, can call the same three tools with no key." Then, on the slide: question → agent → MCP tools (`list_variables`, `get_series`, `detect_trend`) → public data (NASA POWER/MERRA-2, ERA5, NOAA GHCN, NOAA CO-OPS and PSMSL tide gauges, NASA GSFC GRACE/GRACE-FO) → remove the seasons → Mann-Kendall test with Sen's slope, adjusted for autocorrelation → rising, falling or no clear change → risk level and recommendation, computed in code.
**Say:** "The model never does the maths. It can only quote numbers that came back from a tool."

## Slide 8: How we know it's right (Sairam, 45 s)
- **Truth check:** Atlantic City sea level, ours +42.5 mm per decade (41.1 to 44.0) versus NOAA's own published 42.4 ± 0.8 for the same gauge (station 8534720). They match.
- **Satellites versus a published study:** north-west India, Aug 2002 to Oct 2008. Our GRACE land water fall is 5.3 cm a year (3.9 to 6.9); Rodell, Velicogna and Famiglietti (2009, *Nature*) report groundwater falling 4.0 ± 1.0. The ranges overlap.
- **Golden questions:** 15 questions with answers set from NOAA and published papers, never from our own tool. The agent on the live site (Claude Haiku 5.5) passes **all 15** in the runs of Sun 15 Nov at 06:00 and again at about 16:20 UTC, after the guidance feature, on the code that's live, including the ones it must decline: "Will it rain tomorrow?" (a forecast) and "Is sea level rising in Delhi?" (inland). It never invented a number.
- **Stats tests:** pure noise, seasons only and autocorrelated noise all come back "no clear change", so it doesn't cry wolf.

## Slide 9: Who it's for (Sairam, 30 s)
**Say:** "Students and teachers checking a claim about their own town. But also anyone who needs a local trend they can trust: insurers looking at coastal property, heat, rain and water on land; city planners asking whether flooding, heat or water shortage is really getting worse. Honesty is the feature: ask about sea level in Delhi and it says Delhi is inland, with no estimate and no made-up number."

## Slide 10: How we used AI, what's next (Tarun, 30 s)
**Say (AI use, judges asked for it):** "We built this with AI coding agents: Claude Code wrote and reviewed most of the code, tests and docs, a language model runs the agent inside the app, and the assistant's chat and voice run on ElevenLabs. We chose the problem, the statistics, the data sources and the expected answers, and reviewed every change. Details and citations are in `docs/SI.md`."
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
