# Trend Detective demo video (30 s or less)

Final script, updated Sun 15 Nov for the reworked site (#113), matching the pitch's demo flow. Record it from the live site, https://trend-detective-six.vercel.app, so every frame shows the app's own **Built with AI assistance** label. Title cards add that label too. No NASA logos. Captions carry the story; narration is optional.

Numbers below are what production returned on Sun 15 Nov at about 17:15 UTC. Record what the app shows on the day; if a number differs, the caption follows the app, never this table.

| Time | On screen (live site) | Caption | Source shown in the shot |
|---|---|---|---|
| 0–3 s | Title card: **Trend Detective** | *Is this really changing here?* | none (no numbers) |
| 3–9 s | **Sea level** window, New York selected. The card: **Moderate risk, +3.2 cm every 10 years**, the recommendation, "+7.3 to +7.9 cm by 2050 if the past trend continues". | **New York: sea level up about 3 cm every 10 years. Moderate risk.** | "NOAA tide gauge at The Battery" line on the card |
| 9–16 s | **Hottest days** window, Delhi. Click **NASA POWER**, then **ERA5**, then **Weather station**; cut the loading. | **Delhi's hottest days: three records, three answers. It shows all three.** | The source line on the card changes with each click (NASA POWER, ERA5, NOAA weather station) |
| 16–22 s | **Water storage** window, Delhi: **High risk, −44 cm every 10 years**, then the recommendation. | **Satellites weigh the water: falling about 4 cm a year.** *Can't tell groundwater from lakes and soil, and it says so.* | "NASA GRACE satellites" line on the card |
| 22–26 s | Assistant (bottom right), typed: "Is sea level rising in Mumbai?" Cut the wait; show the reply. | **Mumbai, since 1878: rising. Just ask.** | Add the caption "Source: PSMSL tide gauge, Apollo Bandar". The reply doesn't name it yet (#120); if it's fixed by then, show the reply's own source instead. |
| 26–30 s | End card with the URL large. | *Is this really changing here? Now anyone can check.* **trend-detective-six.vercel.app** | none (no numbers) |

Don't use the assistant's voice in the video. If you do, its voice is AI-generated (ElevenLabs): say so in the video description.

## Rules checklist
- [ ] **Built with AI assistance** is visible in every shot. It's in the app header; on the two title cards, add it as text in a corner.
- [ ] No NASA logos or branding anywhere. Source names as plain text only.
- [ ] Every number on screen has its source in the same shot (the app's source line or the link in the answer). Don't crop it out.
- [ ] Only the app's real output. Never edit a number. If the live answer is different on the day, use what it says.
- [ ] 30 seconds or less. Check the exported file's length.
- [ ] If the narration is an AI voice, write "AI-generated voiceover" in the video description.

## How to record (Mac)
1. Browser window at 1280×720, light mode, zoom 125%, notifications off, no other tabs visible.
2. Pin New York (Sea level) and Delhi (Hottest days, Water storage) first, and ask the assistant the Mumbai question once, so everything comes back fast.
3. Cmd+Shift+5 → Record Selected Portion → the browser window. Record each shot separately, with a few seconds of extra footage at each end.
4. In iMovie or CapCut: trim to the times above, cut the waiting, add the captions large (at least 40 px at 720p), add the two title cards.
5. Export MP4, 1280×720. Watch the whole file once against the checklist, then upload it to the project page.

Built with AI assistance: this script was drafted with Claude Code (see `docs/SI.md`).
