# 17 Data sources and World figures pages (PR6 item 4)

Two static pages: **Data sources** (`/sources/`) lists each dataset with its maker, where we get it, licence, credit, update rhythm, link and ID. **World figures** (`/sources/world/`) lists the world figures the cards compare with, with their series, period and surface. They add no API route, no contract field and no new token. Everything visitors read comes from code, a manifest, a snapshot file or the contract; §12 lists the facts that live only in `README.md` or in the brief.

Pictures (desktop first, light): `rework-pr6-sources-design/` in the side-session notes. `01`–`03` are 1440, `04`–`05` are 1920, `06`–`07` are 375 (full page), `08`–`09` are dark, `10`–`11` are the two ERA5 variants, `12`–`13` show the broken-link state, and `14`–`15` show the three new links on the real page. The mock (`sources.html`, `world.html`, `sources.css`) uses the page's own `style.css`, `settings.css`, `prefs.js` and fonts. **The mock shows ERA5 from our Copernicus copy** (the `data/era5-pack` branch); `10` shows the Open-Meteo variant.

## 1. Where they live and how a visitor gets there
- Files: `web/sources/index.html` and `web/sources/world/index.html`, plus `web/sources.css`. The existing `Web` static mount serves them (`/sources` redirects to `/sources/`). Any other path under `/sources/` gets `web/404.html`. Assets use absolute paths: `/style.css`, `/settings.css`, `/sources.css`, `/prefs.js` and `/favicon.svg`. `prefs.js` is the only script, so the saved theme applies before first paint. Without JS the pages render light and complete. They need no CSP change.
- `<title>`: "Data sources · Bhoomi" and "World figures · Bhoomi". Descriptions: "The public datasets behind every number on Bhoomi: who makes them, where we get them, their licences and the credit to give." / "The two world figures Bhoomi compares places with, what they cover, and the months we compare."
- Top bar: the app's `.top` as static HTML. `a.brand` "Bhoomi" links to `/`. The nav links are Sea level, Air temperature, Hottest days, Rain and Water storage, pointing to `/#sea-level` … `/#water-storage`, and none is current. Then the Settings link (`/#settings`) and "Built with AI assistance". No link to these pages is added to the top bar (subtract).
- Foot (`footer.foot`): "Data: the providers named on this page. Trends, ranges and world comparisons: our calculation."
- **Ways in.** These are the only changes to the existing page:
  1. Footer data line (`#foot-data`): after the trends sentence, a space and then the link "All data sources and licences" to `/sources/`. This applies on every window (`15`).
  2. Step 9 "Sources": a last list item that is only a link, "All our data sources, with licences and credits", to `/sources/#{t.source.id}` (the main record's card: `era5`, `power`, `ghcn`, `coops`, `psmsl` or `grace`). See `14`.
  3. Step 6 "Compared with the world": one link line under its existing world link, "About the world figures we compare with", to `/sources/world/#air-temperature`, `#sea-level`, or `#none` when there is no world figure. See `14`.
  4. Ask (agent lane, §8).
- Internal links open in the same tab. Provider links also open in the same tab (as on the app) and end with "↗".

## 2. Layout (both pages)
- `main#main.src-wrap`: padding 28/32, max-width 1312 px, left-aligned like Settings. It holds:
  - the head: `h1` (30 px, −0.4 letter-spacing), `.lead` (17 px `--ink-2`, max 74ch), and the two-page switch `nav.src-tabs[aria-label="Sources pages"]` with "Data sources" and "World figures". The switch uses the app's tab look: 48 px tall, the current page `aria-current="page"`, weight 650 with a 3 px `--ink` underline, others `--ink-2`, and a 1 px `--line` rule under the row.
  - `.src-cols`: a grid of 240 px and 1fr, gap 28, 24 px below the head. Left is `nav.st-nav[aria-label="On this page"]` (the Settings nav look: `.lbl` "On this page" and `a.st-navlink` anchors, sticky at `--top-h` + 24). Right is `.st-sections` (max 1040).
- Section: `section.st-sec` with an `h2` (20 px) and an optional `.st-lead` (14 px `--ink-2`), then cards. `scroll-margin-top: calc(var(--top-h) + 16px)` on sections, cards and anchored `th`.
- **Dataset card** (`article.card.src-card`, `aria-labelledby` its h3, flex column, gap 14), top to bottom:
  1. `.sc-head`: the h3 (20 px, margin 0) and the `.sc-desc` sentence; on the right, the `.btn.ghost` "Open the dataset ↗" with a visually hidden ": {name}". It goes to the DOI at `https://doi.org/…` when there is one, else the dataset page.
  2. `dl.facts`: rows of label (150 px, 14 px `--ink-2`) and value (15 px, line 1.5, `overflow-wrap: anywhere`), with 1 px `--line` rules. The rows are always Made by, We get it from, Licence, Updated, in that order.
  3. `.credit`: `--bg` fill, radius 8, padding 12/16. The label "Credit to give" is 14 px 600 `--ink-2`, then the lines to copy.
  4. `ul.keep` (optional): "**Keep in mind:** …" and "**For rain:** …".
  5. `details.cite` (optional, closed): reuse the step 9 pattern, `summary` with `span.mark` and "How to cite".
  6. `.sc-id`: 13 px `--ink-2`, "ID: …" (quiet).
- ≤820 px: one column, padding 16; the "On this page" links wrap (no sideways scroll) under the tabs. ≤599 px: h1 26 px; the "On this page" links sit in a 2-column grid; facts become label-above-value; the dataset button goes full width. All targets are at least 44 px.
- Colours: only `--ink`, `--ink-2`, `--line`, `--bg`, `--surface` and `--control`. Contrast, light/dark: ink on surface 18.4/15.4, `--ink-2` on surface 6.9/8.7, on `--bg` 6.4/9.5.

## 3. Data sources page: words
- h1 "Data sources". Lead: "Every number on Bhoomi comes from one of these public datasets. For each one: who makes it, where we get it, its licence, the credit to give, and how often it changes."
- `.src-note` (15 px `--ink-2`), before the first section: "The readings are each provider's own. The trends, ranges and comparisons with the world are our own calculation, not an official product of any provider."
- "On this page": Weather records (`#weather`), Sea level (`#sea-level`), Water on land (`#water`), Expert projections (`#projections`), Maps and place names (`#maps`), plus "Using a Bhoomi chart" (`#reuse`) only if the owner says yes (open question 1).
- **Weather records.** Lead: "Used for air temperature, hottest days and rain. Each answer names the record it used and links to that exact record." Cards in catalog order: ERA5 (§4), NASA POWER, weather stations.
  - `#power` "NASA POWER". "A NASA record of past weather on a grid about 50 km wide." (`SOURCE_HELP`). Made by: "NASA Langley Research Center's POWER project, from the MERRA-2 weather model". We get it from: "NASA POWER's monthly data service, for the place's grid cell." Licence: "NASA POWER asks for the credit below." Updated: "Fetched when an answer needs it: whole months from January 1981 to the end of last year." (`power.request_url`). Credit: README's first POWER sentence, "The data was obtained from National Aeronautics … NASA Earth Science Division." Keep in mind: `POWER_T_CAVEAT`. For rain: the first sentence of `source.limit`. How to cite: "POWER also asks for its version and the date you got the data: "The data was obtained from the POWER Project's {version} version on {date}." Step 9 of each answer, "Sources", gives both." ID: "monthly point data, parameters T2M, T2M_MAX and PRECTOTCORR". Link: `https://power.larc.nasa.gov/`.
  - `#ghcn` "Weather stations (GHCN-Daily)". "Readings from the nearest weather station within {ghcn.MAX_KM} km that has at least {MIN_YEARS} years of readings since 1981." (25 and 30 after PR4.) Made by: "NOAA's National Centers for Environmental Information (NCEI), from weather stations worldwide". We get it from: "NCEI's data service, day by day. We turn the days into months, leaving out readings that failed NOAA's quality checks." Licence: "NCEI asks for the citation below." Updated: "Fetched when an answer needs it, through the end of last year." Credit: README's first GHCN-Daily citation, without ", accessed 2026-11-14". Keep in mind: `GHCN_CAVEAT`. How to cite: README's second citation. ID: "doi:10.7289/V5D21VHZ · Version 3". Link: the DOI.
- **Sea level.** Lead: "Tide gauges measure the sea against the land at one spot, so land sinking or rising is included. Each answer uses the nearest gauge within 100 km with at least 30 years of monthly readings, the last no more than 5 years before the end of last year." (numbers from `upstream.rule`, `MAX_KM`).
  - `#coops` "NOAA tide gauges (CO-OPS)". "Readings from the nearest NOAA tide gauge (US coasts)." Made by: "NOAA's National Ocean Service, Center for Operational Oceanographic Products and Services (CO-OPS)". We get it from: "NOAA's Tides and Currents data service: the gauge's verified monthly mean sea level." Licence: "Public domain, unless NOAA marks it otherwise." Updated: "Fetched when an answer needs it, up to the latest month NOAA has verified." Credit: "Data from the NOAA National Ocean Service, Center for Operational Oceanographic Products and Services (CO-OPS)." ID: "verified monthly mean water level (product monthly_mean)". Link: `https://tidesandcurrents.noaa.gov/`.
  - `#psmsl` "Tide gauges worldwide (PSMSL)". "Readings from the nearest tide gauge in a worldwide collection." Made by: "Each gauge's own authority; collected and checked by the Permanent Service for Mean Sea Level (PSMSL)". We get it from: "PSMSL's monthly files, on each gauge's fixed reference level. We leave out months PSMSL flags as doubtful or filled in." Licence: "PSMSL asks for the two citations below." Updated: "Fetched when an answer needs it." Credit: "Permanent Service for Mean Sea Level (PSMSL), 2026, "Tide Gauge Data", Retrieved {the "Extracted from Database" date on PSMSL's data page} from http://www.psmsl.org/data/obtaining/." How to cite: README's Holgate et al. (2013). ID: "Revised Local Reference (RLR) monthly mean sea level". Link: `https://psmsl.org/data/obtaining/`.
- **Water on land.** Lead: "Used for water storage."
  - `#grace` "GRACE and GRACE-FO satellites". "Satellite measurements of water stored on land, averaged over an area about 400 km wide." Made by: "NASA Goddard Space Flight Center (GSFC)". We get it from: "Our own copy of NASA GSFC's file {grace.ZIP}, land cells only." Licence: "None stated on NASA GSFC's page." Updated: "Our copy runs from April 2002 to June 2026 and was made on 14 November 2026. It changes only when we rebuild it by hand." (`ZIP`, `RETRIEVED`). Credit: the Loomis et al. (2019) citation (`scripts/build_grace.py`). ID: "mascons RL06 v2.0, correction ICE-6G_D". Link: `SOURCE.url`.
- **Expert projections.** Lead: "What experts project for the future. We show them exactly as published, never shifted to meet the records." These cards add `.sc-used` under the description.
  - `#ar6` "IPCC sea-level projections (AR6)". "The sea-level projections of the IPCC's Sixth Assessment Report, for each tide gauge, every 10 years from 2020 to 2150." "Used for sea level." Made by: "Garner and others (2021), for the IPCC's Sixth Assessment Report". We get it from: "Our own copy of the published files on Zenodo." Licence: "CC BY 4.0 ↗". Updated: "One fixed release, version 20210809. Our copy was made on 22 November 2026." (`ar6_gauges.json` `version`, `accessed`). Credit: "IPCC AR6 Sea Level Projections (Garner et al. 2021), version 20210809, CC BY 4.0." How to cite: `citations` in full, then "Acknowledgement: {acknowledgement}". ID: "doi:10.5281/zenodo.6382554 · version 20210809".
  - `#atlas` "Climate model projections (IPCC Interactive Atlas, CMIP6)". "How the climate models in the IPCC's Interactive Atlas project air temperature, hottest days and rain to change, on a grid about 100 km wide, for 2021–2040, 2041–2060 and 2081–2100." "Used for air temperature, hottest days and rain." Made by: "Instituto de Física de Cantabria (IFCA, CSIC-UC), for the IPCC, from the CMIP6 climate models". We get it from: "Our own copy, retrieved from the Copernicus Climate Data Store and checked value by value against the originals." Licence: CC BY 4.0. Updated: "One fixed release, Version 2 final. Our copy was made on 23 November 2026." Credit: "Contains modified Copernicus Climate Change Service information 2026." and "IPCC AR6 Interactive Atlas, CMIP6 projections, version v2.0-final, CC BY 4.0." How to cite: `cmip6_atlas.json` `citations`, then `land_mask.citation`, then "Acknowledgement: …". ID: "doi:10.20350/digitalCSIC/15492 · v2.0-final · retrieved from doi:10.24381/cds.5292a2b0".
- **Maps and place names.** One card with a `table.wf.three`, caption "Maps and place names: where they come from and the credit to give". Columns: What, From, Licence, Credit to give.
  - Row 1: "Place names in the search box" | "Open-Meteo Geocoding API (GeoNames) ↗" (`PLACE_SOURCE`) | "CC BY 4.0 (Open-Meteo's API data)" | "Place names: Open-Meteo Geocoding API (GeoNames)".
  - Row 2: "Map background" | "OpenFreeMap, with OpenMapTiles and OpenStreetMap data" | "ODbL (OpenStreetMap data)" | "© OpenMapTiles, data from OpenStreetMap contributors" (`NOTICE`).
  - Then: "The coloured dots on the maps are our own calculation from the records above."
- Last line (`.checked`): "Links checked on {d Month yyyy}. If a link doesn't open, search for the name or the ID under it."

## 4. ERA5 card, two variants (the build shows the one `era5.py` serves by default)
- Shared: h3 "ERA5"; "A European record of past weather on a grid about 25 km wide."; Made by "ECMWF, for the Copernicus Climate Change Service"; credit line 1 "Contains modified Copernicus Climate Change Service information 2026." (`upstream.COPERNICUS`).
- **Our Copernicus copy** (the mock; `era5.PACK_URL` set). We get it from: "Our own copy of the Copernicus dataset behind the Copernicus Interactive Climate Atlas (its ERA5 part, land only)." and "If our copy can't be read, or has no land cell for a place, we fetch ERA5 from Open-Meteo instead, and the answer names Open-Meteo." Licence "CC BY 4.0 ↗". Updated: "Our copy runs from January 1981 to December 2025. The dataset is updated about once a year; we rebuild our copy by hand." Credit line 2: "If the answer names Open-Meteo, also: Weather data by Open-Meteo.com ↗". How to cite: the pack manifest's `citation` (its "Accessed on" date filled). ID: "doi:10.24381/cds.h35hb680 · Copernicus dataset multi-origin-c3s-atlas, ERA5 part". Link: the DOI.
- **Open-Meteo** (`PACK_URL` None). We get it from: "Open-Meteo's archive service, day by day. We turn the days into months." Licence: "CC BY 4.0 ↗ (Open-Meteo)" and "Open-Meteo's free service is for non-commercial use only." Updated: when `request_url` ends at the latest complete month (PR4, the pack branch), "Fetched when an answer needs it, through the latest complete month. The last 3 months are an early release that ERA5's makers may still correct; we mark them and leave them out of the trend."; when it ends at the end of last year (rework/pr6 today), "Fetched when an answer needs it, through the end of last year." Credit line 2: "Weather data by Open-Meteo.com ↗". How to cite: README's Hersbach et al. (2023), then Zippenfenig (2023). ID: "doi:10.24381/cds.adbb2d47 · ERA5 hourly data on single levels from 1940 to present". Link: the DOI.

## 5. World figures page: words
- h1 "World figures we compare with". Lead: "Some answers set a place's rate of change beside the world's, over exactly the same months. These are the two world figures we use, and the measurements that have none." "On this page": The two world figures (`#figures`), Why the two sides differ (`#differ`), No world figure (`#none`), Reading a comparison (`#reading`), Credits (`#credits`).
- **The two world figures**: one card, `table.wf` (rows of facts, one column per figure, so the two read side by side at every width). Caption: "The world figures: what they cover, our copy, and the months we compare". The column headers are `th#air-temperature` "Air temperature" and `th#sea-level` "Sea level" (18 px head font, 2 px `--ink` rule). Each row is a `th scope=row` (14 px `--ink-2`), then the air temperature value, then the sea level value:
  - Compared with: "The average for all land areas" | "Global average sea level, measured by satellites" (`trend.WORLD[…].measure`)
  - What it covers: "Land only, no ocean" | "The ocean from 66° south to 66° north"
  - How it is measured: "Weather stations on land" | "Satellites measuring the height of the sea surface, corrected for the slow sinking of the ocean floor since the last ice age"
  - Dataset: "NOAA Global Surface Temperature (NOAAGlobalTemp) version 6.1, land part, from NOAA NCEI Climate at a Glance" | "NASA Global Mean Sea Level version 5.2, from the TOPEX/Poseidon, Jason and Sentinel-6 satellites"
  - Our copy runs: "January 1850 to October 2026" | "January 1993 to April 2025" (first and last month of `world/*.json`)
  - Updated: "We refresh our copy by hand; last fetched 22 November 2026." (`source.retrieved`), in both columns
  - Months compared: "The same months as the place's record (from 1981 at the earliest), with at least 20 years in common" | "The gauge's months from January 1993 to April 2025 (or to the gauge's last month, if earlier), with at least 20 years"
  - Rate shown in: "°C per decade" | "mm a year"
  - Licence: "NOAA data, free to use with the citation below" | "NASA data, openly shared without restriction"
  - Dataset ID: "doi:10.25921/vvaa-wq11 ↗" | "doi:10.5067/GMSLM-TJ152 ↗"
- **Why the two sides differ** (card, paragraphs with a bold lead-in):
  - "**Air temperature.** The world figure is built from weather stations on land. The number for a place comes from a weather model (ERA5 or NASA POWER) or from one weather station, so the two are measured in different ways."
  - "**Sea level.** Satellites measure the height of the sea surface itself. A tide gauge measures the sea against the land, so if the land at the gauge is sinking, that adds to the local number."
  - "**Recent months.** NOAA says its most recent months may still be revised, without saying which. NASA calls its sea-level values after 28 March 2022 preliminary while its checks go on. We mark neither." (snapshot `notes`)
- **No world figure**: `dl.nofig`, with Hottest days, Rain and Water on land, each followed by its `trend.NO_MATCH` sentence verbatim.
- **Reading a comparison**:
  - "A rate on its own is hard to judge. Beside the world's rate over the same months, it shows whether this place has changed faster or slower than the world as a whole. It describes the past; it is not a forecast."
  - "1× is the same pace as the world; 2× is twice as fast. Below 0, the change here went the other way."
  - "The two numbers in brackets show how uncertain the comparison is. They come from the range of rates this place's own record allows."
  - "There is no "times as fast" figure when the change here is not clear, when the world figure did not rise over those years, or when the two records share fewer than 20 years."
- **Credits**: two `.credit` boxes. "Credit to give: the air temperature figure" holds the land citation from the `land_temp` notes. "Credit to give: the sea level figure" holds the GSFC (2024) citation from the `gmsl` notes. Then the `.checked` line as in §3, ending "search for the ID instead."
- No fixed world rate is printed (open question 4). Rates depend on the months, and each answer computes its own.

## 6. States
- **Broken link** (`12`, `13`). Before each release the link check covers every https link on both pages (§10). A provider link that fails is not removed silently. The button is replaced by `p.dead` (14 px `--ink-2`, right-aligned, left on phones): "This link wasn't working when we checked on {d Month yyyy}. Search for the name or the ID below instead." The ID line stays. A DOI that fails is printed as plain text with the same sentence under the table or card. Nothing changes at run time, since the pages make no requests.
- **Dark** (`08`, `09`): the saved theme via `prefs.js` (`data-theme`). The same tokens give the same contrast as the app.
- **ERA5 fallback**: the card states it (§4); each answer still names the record it used.
- **Snapshots or copies rebuilt** (`update_world.py`, `build_grace.py`, the AR6, Atlas or ERA5 builds): the dates and periods on the page change in the same PR. The test in §10 fails until they do.
- No JS: identical content, light theme. Unknown sub-path: `404.html`. Print: `.top` is hidden (existing rule), and the content prints in one column.

## 7. Accessibility
- `lang="en"`. Skip link "Skip to the content" to `#main`. Landmarks: `header.top` and its nav "Measurements", `main`, nav "Sources pages", nav "On this page", `footer`.
- Headings: one h1, then an h2 per section and an h3 per dataset card. Cards are `article` elements labelled by their h3.
- Tables: `<caption>`, `th scope="col"` and `scope="row"`, an empty top-left `td`. At 375 the world table keeps its three columns (row labels at 30%) and wraps text, with no sideways scroll. Facts are `dl` (`div` groups with `display: contents`).
- Each "Open the dataset ↗" has a unique accessible name through its hidden ": {name}". "How to cite" is a native `details`.
- Focus: the app's 3 px ring. Tab order: skip, top bar, the two tabs, "On this page", then per card: the button, links in the facts and credit, How to cite.
- Contrast: at least 6.4:1 for all text (§2). The controls' border `--control` is 4.5/5.1. Colour carries nothing.
- 375 and 320 px measured: `scrollWidth` equals the width on both pages (only the top bar's nav scrolls inside itself, as on the app). Long file names, DOIs and URLs break (`overflow-wrap: anywhere`).

## 8. Ask and voice (agent lane; listed in the PR body)
- When a question asks where the numbers come from, who made the data, whether it is official, or about licences or credit, the answer keeps naming each record's dataset and maker as today. It then ends with the code-written line "All our data sources, with licences: bhoomi.earth/sources". The line holds no number, so it is outside the word count.
- Voice prompt: say it as "You can find all our data sources at bhoomi dot earth slash sources." No URL is read out otherwise.

## 9. Walk-throughs (desktop 1440, light, under a minute each)
- **Student, "where does Chennai's rain number come from?"** I open Rain with Chennai pinned. The card says NASA POWER. I scroll to "How we calculated this", open step 9 and click "All our data sources, with licences and credits". I land on the NASA POWER card: a NASA record of past weather on a 50 km grid, from the MERRA-2 weather model. "For rain" tells me it is corrected every day to rain-gauge maps and can drift where gauges are few. I click "Open the dataset" to see it myself, or step 9's "Open this exact record" for Chennai's own request.
- **Builder, "whose sea-level data is this, and is it official?"** On Sea level with The Battery, I click the footer's "All data sources and licences", then "Sea level". The NOAA card says NOAA's National Ocean Service makes it and that it is their verified monthly mean, public domain. The note at the top says the trends are Bhoomi's calculation, not an official product. The projections card says the future comes from the IPCC's own release. Next, I open NOAA's station page from step 9 and check FEMA's flood maps, which the card already points to.
- **Teacher, checking the licence before showing a chart in class.** From the footer link I scan the Licence rows: ERA5 is CC BY 4.0 and NASA POWER asks for a credit line. I copy the "Credit to give" lines for the records the chart names. For Bhoomi's own chart I need the owner's answer (open question 1). Without it the page says nothing, and I would ask.

## 10. QA checks
- [ ] Screenshots: both pages at 1440 and 1920 light first, then 375 full page and 1440 dark. Compare with `01`–`09`.
- [ ] `tests/test_sources_pages.py` (frontend lane) reads both HTML files and fails when a fact drifts from code:
  - the IDs and DOIs: `era5.DATASET_ID`, or `PACK_DATASET_ID` when the pack is the default; `ghcn.DATASET_ID`; `grace.ZIP`; the AR6 and Atlas manifests' `doi`, `version` and `licence`; and both world `dataset_id`s;
  - the world snapshots' first and last months as "January 1850", "October 2026", "January 1993" and "April 2025", and their `retrieved` dates;
  - `grace.RETRIEVED`, the AR6 `accessed` date and the Atlas `source.retrieved`;
  - `upstream.MIN_YEARS`, `MAX_STALE_YEARS` and the gauges' `MAX_KM`, and `ghcn.MAX_KM`;
  - every `trend.NO_MATCH` sentence, `POWER_T_CAVEAT`, `GHCN_CAVEAT`, and `COPERNICUS` once PR4 lands.
- [ ] `scripts/check_links.py` (data lane) also checks every https link on the two pages for a 200. Run it before release and set the `.checked` date.
- [ ] Ways in: the footer link on all five windows; step 9's link lands on the main record's card for ERA5, POWER, station, CO-OPS, PSMSL and GRACE answers; step 6 lands on the right column, or `#none` for hottest day, rain and water. Each lands below the sticky bar.
- [ ] Keyboard only: reach and open every link and "How to cite"; the focus ring is visible. A screen reader announces the table caption and its row and column headers.
- [ ] At 375 and 320 the `scrollWidth` equals the width. Targets are at least 44 px. The AI label shows in the top bar. No NASA logo or image anywhere.
- [ ] The words hold no advice (no "should", buy, build or avoid) and no statistics terms beyond "95%", which the cards already use.

## 11. Needs from other lanes
- Data lane: the `check_links.py` extension. If the owner agrees (open question 2), `licence` and `credit` go into each module's `SOURCE` (a contract field), and the page and test read them.
- Agent lane: §8.
- Contract: none unless open question 2 is accepted.

## 12. Open questions for the owner (recommendation first)
1. **Licence for Bhoomi's own charts and text** (the teacher). Recommend CC BY 4.0, crediting "Bhoomi (bhoomi.earth), built with AI assistance" plus the datasets' credit lines; the code stays Apache-2.0. If yes, `#reuse` shows: "You may reuse our charts and text under CC BY 4.0 ↗. Credit "Bhoomi (bhoomi.earth), built with AI assistance", plus the credit lines above for the datasets the chart names." (drawn dashed in the mock). If no, the section is left out.
2. **Licences the repo doesn't record** (NASA POWER, GHCN-Daily, PSMSL). Recommend that the data lane reads each provider's terms and records `licence` and `credit` in code. Until then the Licence row only says what the provider asks for, as above.
3. **Two pages or one.** Recommend two, as specced: one template, cross-linked by the tabs, with step 6 landing on a short page. The alternative is one page with a `#world` part (one file fewer).
4. **A fixed world rate on the page** (e.g. "warmed X °C per decade, 1981 to 2025"). Recommend no: each answer compares the same months, and a fixed number invites unlike comparisons.
5. **A top-bar link.** Recommend no: the footer, steps 6 and 9, and Ask reach the pages.
6. **"Links checked on …" line.** Recommend yes, set by whoever runs the link check before a release.

## 13. Facts not found in code or the contract (flagged, not invented)
- Licences: NASA POWER, GHCN-Daily and PSMSL have none recorded (README gives only the credit asked for). CO-OPS "public domain unless annotated" and GRACE "states no licence" exist only in `README.md`. Credit lines for POWER, GHCN-Daily, CO-OPS, PSMSL, Open-Meteo and the ERA5 citation exist only in `README.md`.
- Update rhythms of the live providers: code shows only what we request. The ERA5 pack's "about once a year" comes from the brief, and its "Accessed on" date is in the pack's `manifest.json`, which is not in the repo.
- On rework/pr6 today: "Copernicus attribution", `source.limit`, the 25 km station radius and ERA5's latest-complete-month end are PR4 / `data/era5-pack`, not merged yet. GHCN-Daily is "Version 3" in code and "3.35" in README. "ECMWF" as ERA5's maker and the map credit are in `README.md` and `NOTICE` only.
- Update 2026-11-26: the ERA5 pack (PR #134) is merged into rework/pr6 (643b96d). Its name, DOI, licence and citation are in code (`era5.PACK_SOURCE`), so "not merged yet" and "only in `README.md`" above no longer hold for it.
