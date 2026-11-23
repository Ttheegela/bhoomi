"""Check that every record_url type opens our exact record: HTTP 200 and the page names our station, coordinates or file.
Live, by hand, never in tests or on Vercel (about 40 small requests):  uv run python scripts/check_links.py

The series come from the real data code (earthtrends.data.get_series), so the URLs checked are the ones users get.
ERA5: record_url is the Open-Meteo archive request the fetcher makes, and this project never calls that API from a
developer machine, so only the ERA5 DOI page is fetched here (tests/test_data.py checks the URL is the request made).
CO-OPS station pages are filled in by JavaScript, so their HTML never holds the station's name: the page must answer 200,
and the station metadata it loads (the CO-OPS metadata API, same id) must name the station.
It also opens every outbound link on the two sources pages (web/sources/index.html and web/sources/world/index.html,
design 17): each must answer 200. With --stamp, and only when every check passes, it sets the pages' "Links checked on
{date}" line to today:  uv run python scripts/check_links.py --stamp
Exit status 1 if any check fails. Hosts it reaches: power.larc.nasa.gov, www.ncei.noaa.gov, tidesandcurrents.noaa.gov,
api.tidesandcurrents.noaa.gov, psmsl.org, earth.gsfc.nasa.gov, assets.science.nasa.gov, doi.org and the DOI landing hosts
(cds.climate.copernicus.eu, earthdata.nasa.gov, www.earthdata.nasa.gov, zenodo.org, digital.csic.es), and from the
sources pages open-meteo.com and creativecommons.org.
"""
import html
import re
import sys
from datetime import date
from pathlib import Path

import httpx

from earthtrends import data
from earthtrends.data import era5, grace, world

PLACES = {"New York (The Battery)": (40.70, -74.01), "Princeton NJ": (40.35, -74.66), "Delhi": (28.61, 77.21)}
TYPES = (("air_temp_max", "power"), ("air_temp_max", "ghcn"), ("sea_level", "coops"), ("sea_level", "psmsl"), ("water_storage", "grace"))
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; link-check)"}
PAGES = [Path(__file__).resolve().parent.parent / "web" / "sources" / p / "index.html" for p in ("", "world")]
CHECKED = re.compile(r"Links checked on \d{1,2} [A-Z][a-z]+ \d{4}\.")
rows, failed = [], []


def page_links() -> list[str]:
    """Every outbound link (href) on the two sources pages, each once, in page order."""
    found = (html.unescape(u) for p in PAGES for u in re.findall(r'href="(https?://[^"]+)"', p.read_text(encoding="utf-8")))
    return list(dict.fromkeys(found))


def stamp(day: date) -> None:
    """Set both pages' "Links checked on {d Month yyyy}." line to `day`."""
    for p in PAGES:
        text = p.read_text(encoding="utf-8")
        if not CHECKED.search(text):
            sys.exit(f"no 'Links checked on' line in {p}")
        p.write_text(CHECKED.sub(f"Links checked on {day.day} {day:%B %Y}.", text), encoding="utf-8")


def check(label: str, url: str, want: list[str], body_url: str | None = None) -> None:
    """GET `url` (following redirects); pass if 200 and the body of `body_url` (default: the same) names any of `want`."""
    try:
        r = httpx.get(url, headers=HEADERS, timeout=60, follow_redirects=True)
        body = r.text if body_url is None else httpx.get(body_url, headers=HEADERS, timeout=60).text
        named = [w for w in want if w.lower() in body.lower()]
        status = r.status_code
    except httpx.HTTPError as e:
        status, named = type(e).__name__, []
    ok = status == 200 and (named or not want)
    rows.append((label, url, status, ", ".join(named) + (" (in the metadata the page loads)" if body_url and named else "") or "-"))
    if not ok:
        failed.append(label)


def main() -> None:
    for place, (lat, lon) in PLACES.items():
        for variable, source in TYPES:
            label = f"{place}: {source}"
            try:
                s = data.get_series(variable, lat, lon, source=source)
            except ValueError as e:  # no station or gauge near this place: nothing to link
                rows.append((label, "-", "-", f"no record here ({e})"[:120]))
                continue
            src, url = s["source"], s["source"]["record_url"]
            if source == "power":
                check(label, url, [str(s["place"]["lat"]), str(s["place"]["lon"])])
            elif source == "ghcn":
                check(label, url, [url.split("GHCND:")[1].split("/")[0], s["place"]["name"].split(",")[0]])
            elif source == "coops":
                sid = re.search(r"id=([^&]+)", url).group(1)
                check(label, url, [s["place"]["name"], sid], f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{sid}.json")
            elif source == "psmsl":
                check(label, url, [s["place"]["name"], f"Station ID: {url.rsplit('/', 1)[1].split('.')[0]}"])
            else:
                check(label, url, [grace.ZIP])
        rows.append((f"{place}: era5 (not fetched)", era5.request_url(era5.PARAMS["air_temp_max"], lat, lon), "-", "the fetcher's own request"))
    check("ERA5 dataset DOI", "https://doi.org/" + era5.DATASET_ID[4:], ["ERA5 hourly data on single levels"])
    check("GHCN-Daily DOI", "https://doi.org/10.7289/V5D21VHZ", ["GHCN", "Global Historical Climatology Network"])
    for name, want in (("land_temp", ["Global Land Average Temperature"]), ("gmsl", ["MERGED_TP_J1_OSTM_OST_GMSL_ASCII_V52"])):
        src = world.reference(name)["source"]
        check(f"world {name}", src["record_url"], want)
        check(f"world {name} DOI", "https://doi.org/" + src["dataset_id"][4:], [])
    for url in page_links():
        check("sources pages", url, [])
    print("| check | URL | status | what the body names |\n|---|---|---|---|")
    for row in rows:
        print("| " + " | ".join(str(x) for x in row) + " |")
    if failed:
        sys.exit(f"failed: {', '.join(failed)}")
    if "--stamp" in sys.argv[1:]:
        stamp(date.today())
        print(f"Set 'Links checked on' to today in {', '.join(str(p) for p in PAGES)}.")


if __name__ == "__main__":
    main()
