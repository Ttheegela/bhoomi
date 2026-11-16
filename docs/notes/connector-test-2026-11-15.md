# Connector test, 2026-11-15

Built with AI assistance.

**The public connector was not tested.** The cloud session that ran this test may not reach `trend-detective-six.vercel.app` or `bhoomi.earth`: its network policy refused the connection before it left the session, and the request to allow the host was declined. No call reached production.

What was tested instead: the same server code (`main` at `85f9fe4`, fetched 19:46 US Eastern), started inside the session and used through a real MCP client over streamable HTTP. NASA and NOAA are blocked from the session too, so only land water storage (its data file ships with the app) gave a live result. To check the guidance arithmetic on more than one result, the provider responses saved in `tests/fixtures/` were run through the unmodified tool functions.

Three things to act on:

1. The old connector address is refused by the code now on `main` (421), so anyone who added it before the rename may be cut off. Not confirmed on production.
2. `detect_trend`'s description never mentions `guidance`, and nothing tells an outside model how to show it.
3. The outlook and the sea-level risk level compare a whole-record average with a recent world rate, which likely understates a fast-rising coast.

## How it was run

| | |
|---|---|
| Model | Not the one asked for. The session report names it; model names are kept out of the repository. |
| Connector tools native to the session | No. None were offered. |
| Production over HTTP | Blocked. 1 connection attempt, 0 tool calls, 0 of the 60-call budget used. |
| Local server over MCP | 20 tool calls with the MCP Python SDK client at `http://127.0.0.1:8765/mcp/`, plus raw HTTP checks of the Host rule and the rate limit. |
| Saved provider data | 5 results computed in-process from `tests/fixtures/` (real NOAA, NASA POWER and PSMSL responses saved 2026-11-14). Not MCP calls. |
| Tests | `uv run pytest -q`: 1398 passed. |

## Calls

### Production

| Tool | Arguments | Result | Note |
|---|---|---|---|
| connect | `https://trend-detective-six.vercel.app/mcp/` | Blocked | 403 from the session's own network proxy. Says nothing about the server. |

### Local server, over MCP

| # | Tool | Arguments | Result | Note |
|---|---|---|---|---|
| 1 | `ping` | none | Pass | `pong` |
| 2 | `list_variables` | none | Pass | 5 variables, each with id, name, units, sources, start year, resolution, good_for |
| 3 | `detect_trend` | water_storage, 30.9, 75.85 | Pass | Falling, −40 cm per 10 years (95% range −42.7 to −37.9), High risk. Source with URL, 6 caveats, `meaning`, all 12 `guidance` keys. Arithmetic matches `docs/RISK.md` |
| 4 | `get_series` | water_storage, 30.9, 75.85 | Pass | Shape matches `docs/CONTRACTS.md`. 291 months, 2002-04 to 2026-06, 33 nulls |
| 5 | `get_series` | same, start 2015, end 2020-06 | Pass | 66 months, cut correctly |
| 6 | `detect_trend` | variable `temperature` | Pass | "Unknown variable 'temperature'. Choose one of: air_temp, air_temp_max, precip, sea_level, water_storage." |
| 7 | `detect_trend` | air_temp, lat 95 | Pass | "Latitude must be between -90 and 90, got 95.0." |
| 8 | `detect_trend` | air_temp, lon 200 | Pass | "Longitude must be between -180 and 180, got 200.0." |
| 9 | `detect_trend` | water_storage, 0, -30 (open ocean) | Pass | Error, no value: "too little land within about 200 km (open ocean, an ice sheet or a small island)" |
| 10 | `detect_trend` | sea_level, source `power` | Pass | "sea_level is not available from 'power'. Available: coops, psmsl." |
| 11 | `detect_trend` | start `1990s` | Pass | "start must look like 2015 or 2015-06, got '1990s'." |
| 12 | `detect_trend` | start 2020, end 2010 | Pass | "start must not be after end." |
| 13 | `detect_trend` | end 1999 (before the record) | Pass | "No land water storage data for that place and period." |
| 14 | `detect_trend` | water_storage, start 2019 | Pass, mixed words | Risk "Not enough data" and no outlook, as the rules say. But `meaning` says "clearly been decreasing" and "Clear" in the same result |
| 15 | `detect_trend` | lat `"north"` | Pass, noisy | Three lines of validation text ending in a pydantic.dev link |
| 16 | `detect_trend` | no `lon` | Pass, noisy | Same style: "lon Field required" |
| 17 | `detect_trend` | `place: "Grand Isle, Louisiana"`, no lat or lon | Pass, noisy | "Field required" twice. Does not say that coordinates are needed |
| 18 | `geocode` | any | Pass | "Unknown tool: geocode" |
| 19 | `detect_trend` | air_temp, 0, -30 (open ocean) | Not testable | NASA POWER blocked from the session: "The data source did not answer. Please try again." See problem 4 |
| 20 | `detect_trend` | sea_level, 39.74, -104.99 (Denver) | Not testable | NOAA blocked: same message. With the saved station lists the wording is "There is no tide gauge within 100 km of this place, so sea level can't be measured here. The nearest gauge is …" |

Raw HTTP checks on the local server:

| Check | Result |
|---|---|
| `POST /mcp` (no slash) | 307 to `/mcp/` |
| Host `bhoomi.earth`, `www.bhoomi.earth` | 200 |
| Host `trend-detective-six.vercel.app` | **421 "Invalid Host header"** |
| 131 requests in a minute | 120 answered, the rest got 429 with `Retry-After` and "Too many requests right now. Please wait 54 seconds and try again." |
| `GET /mcp/` | 200, then an empty stream held open until the client gives up |

### Saved provider data through the tool functions (not MCP calls)

| Place and measurement | Result | Guidance | Arithmetic |
|---|---|---|---|
| Atlantic City sea level, NOAA gauge 8534720, 1911-09 to 2026-10 | Rising, 42.5 mm per decade (41.1 to 44.0) | Moderate, 1.3 times the world average, "+10 to +11 cm by 2050", NOAA flood map link | Matches |
| Atlantic City air temperature, NASA POWER, 1981 to 2025 | Rising, 0.33 °C per decade (0.23 to 0.44) | High, 1.7 times the world average | Matches |
| Atlantic City hottest day of the month, NASA POWER | Rising, 0.22 °C per decade (0.08 to 0.37) | Moderate, 1.1 | Matches |
| Atlantic City rain, NASA POWER | No clear change (p 0.12) | Low, no rate, no outlook | Matches |
| Mumbai sea level, PSMSL gauge 43, 1878 to 2024 | Rising, 9.4 mm per decade (8.3 to 10.4) | Low, 0.3 times the world average, NASA projection link | Matches |

"Matches" means every number was worked out again from `docs/RISK.md` by separate code: the rate, the ratio, the risk level, each outlook range and its rounding, and the map link coordinates. With the Punjab result that is 6 of 6.

### Asked for and not run

Sea level at Grand Isle and Lower Manhattan, rain at Chennai, hottest day at Delhi, air temperature at Princeton. All need NOAA or NASA POWER, which the session cannot reach, and no saved response exists for these places.

## Would a new model know what to call?

For "Is sea level rising in Grand Isle, Louisiana?": yes. The first line of `detect_trend` is the question itself, the variable ids are listed in the description with units, and lat and lon have ranges and an example. A model would call `detect_trend(variable="sea_level", lat=29.26, lon=-89.96)` without calling `list_variables` first.

What is unclear or missing:

- Nothing says that a place name must be turned into coordinates by the model, and there is no tool for it.
- `guidance` is not in the list of returned fields. The description says "not a forecast" while the result carries ranges out to 2075.
- `air_temp_max` is not explained in `detect_trend` or `get_series`. Only `list_variables` says it is the hottest day of the month.
- The input schema has names and types only: no parameter descriptions, no ranges.
- The tools have no title and no read-only marking, and the server sends no instructions when a client connects.

## The four visitor questions

None could be answered from the connector, because no result for these places could be fetched. What each would need, judged from the results that were seen:

- **(a) Chennai rain, or just this year?** Not answered. The result would settle "really changing or not" (verdict, p-value, share of usual rainfall per decade). It cannot speak about this year: the NASA POWER series stops at last December, and nothing in the result says so except `period.end`.
- **(b) House in Lower Manhattan.** Not answered. The result shape covers it well: rate, comparison with the world, risk level, a recommendation about flood level, a NOAA flood map link centred on the gauge, and the disclaimer. See problem 2 for the caution on the outlook.
- **(c) Delhi heat, summers when I'm older.** Not answered. Two gaps: the trend is over all months with no way to ask for summer only, and an outside model gets one source unless it thinks to ask for the others, where the README says the sources disagree for Delhi.
- **(d) Grand Isle or Atlantic City.** Half. Atlantic City, from the saved NOAA response: the sea is rising 4.3 cm every 10 years, 1.3 times the world average, Moderate risk. Grand Isle: no result, so no comparison.

## Problems, by how much they would hurt a real user

1. **The old address is refused.** Commit `6380e2f` (15:26 Eastern) took `trend-detective-six.vercel.app` out of the hosts `/mcp/` always accepts. On `main` it is accepted only if a Vercel variable still lists it. An AI app set up before the rename would show the connector as broken, with no reason given. Shown locally, not confirmed on production.
2. **The outlook and the sea-level risk likely understate.** The gauge's whole-record average (115 years at Atlantic City, 146 at Mumbai) is compared with the world rate since 1993, and the same average is carried forward. The range "+10 to +11 cm by 2050" is only the uncertainty of the past slope, so it reads as far more exact than it is. `docs/RISK.md` says the ranges ignore speed-ups; the result does not.
3. **`guidance` is undocumented for outside models.** No instruction to show the recommendation with its disclaimer, to keep the label "If the past trend continues", or to add no numbers. `docs/CONTRACTS.md` says all three; the tool description says none.
4. **Air temperature over open ocean probably returns a value.** The brief says it must be an error. The code has no such check for NASA POWER, which is a global grid. Only water storage and sea level refuse ocean points. Not confirmed.
5. **Place names.** The model supplies coordinates from memory. A wrong guess for a small place gives a confident answer about somewhere else.
6. **One source by default.** For temperature and rain an outside model sees NASA POWER only. The Ask tab checks every source; the connector does not suggest it.
7. **No read-only marking.** Some AI apps ask the user to approve every call of an unmarked tool.
8. **`get_series` is large.** A full tide-gauge record is 37,000 to 48,000 characters of indented JSON, which some apps cut off.
9. **Temperature risk runs high on land.** A land point is compared with the land-and-ocean world average, so most land places will read High (Atlantic City: 1.7 times).
10. **Small.** Validation errors are noisy. `meaning` and `guidance` round differently ("About 4 cm" and "+4.3 cm"; "About 9 mm" and "+0.94 cm"). `GET /mcp/` holds an empty stream open. The README tool table omits `meaning` and `guidance`.

## Suggested fixes

1. Put the old host back in `PUBLIC_HOSTS` for a few weeks, or confirm `MCP_ALLOWED_HOSTS` on Vercel lists it.
2. Work out the sea-level ratio from the gauge's record since 1993, and add one sentence to the outlook: "Official projections allow for speed-ups; open the link."
3. Add to the `detect_trend` description: "Also returns guidance: risk level, why, recommendation, outlook and disclaimer. Show these strings as they are, keep the label 'If the past trend continues', never call the outlook a forecast, and show the disclaimer with the recommendation."
4. Decide whether ocean points are allowed for temperature and rain. If not, refuse them before calling NASA POWER.
5. Add one sentence to the description: "Needs coordinates. There is no place search here; look them up or ask the user." Or expose `search_places` as a fifth tool, through a `docs/CONTRACTS.md` change.
6. Add to the description: "Temperature and rain have three sources. For a decision, call once per source and say so if they disagree."
7. Mark all four tools read-only: `@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))`.
8. Say in `get_series` that `start` and `end` keep the answer small, or return the JSON without indentation.
9. Use a land-only world figure for temperature, or say "including oceans" in `why`.
10. Catch argument errors and answer in one plain line; answer `GET /mcp/` with 405; add `meaning` and `guidance` to the README table.

## To finish the test

The production run is about 25 calls and three minutes. It needs a session whose network allows `bhoomi.earth` (and the old host, to settle problem 1). The client script is not in the repository; it is 40 lines around `mcp.client.streamable_http.streamable_http_client`.

SI used: an AI coding agent ran the local MCP calls, re-derived the guidance numbers, read the code and wrote this note.
