"""The two sources pages (web/design/17-sources-pages.md) say what the code says. Every provider's name, licence, credit,
dataset ID and URL, the projection manifests' citations and licence, the world figures' names, periods and dates, the
rules and caveats, and the three "no world figure" sentences are read from code here; a fact that changes in code fails
this test until the page changes with it."""
import calendar
import importlib.util
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from earthtrends.app import app
from earthtrends.data import ar6, cmip6, coops, era5, ghcn, grace, places, power, psmsl, upstream, world
from earthtrends.stats import projection, trend

ROOT = Path(__file__).parent.parent
SOURCES = (ROOT / "web" / "sources" / "index.html").read_text(encoding="utf-8")
WORLD = (ROOT / "web" / "sources" / "world" / "index.html").read_text(encoding="utf-8")
_spec = importlib.util.spec_from_file_location("check_links", ROOT / "scripts" / "check_links.py")
check_links = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_links)


class _Text(HTMLParser):
    """Text as read aloud (the sr-only parts included), and every href."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hrefs = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.append(dict(attrs)["href"])
        if tag in ("br", "p", "li", "td", "th", "dt", "dd"):
            self.parts.append(" ")

    def handle_data(self, data):
        self.parts.append(data)


def read(fragment: str) -> tuple[str, list[str]]:
    p = _Text()
    p.feed(fragment)
    return " ".join("".join(p.parts).replace("\xa0", " ").split()), p.hrefs


def part(page: str, open_tag: str, close_tag: str) -> tuple[str, list[str]]:
    m = re.search(re.escape(open_tag) + ".*?" + re.escape(close_tag), page, re.S)
    assert m, open_tag
    return read(m.group())


def card(cid: str) -> tuple[str, list[str]]:
    return part(SOURCES, f'<article class="card src-card" id="{cid}"', "</article>")


def month(t: str) -> str:
    """"2025-04" -> "April 2025"."""
    return f"{calendar.month_name[int(t[5:7])]} {t[:4]}"


def day(d: str) -> str:
    """"2026-11-22" -> "22 November 2026"."""
    x = date.fromisoformat(d)
    return f"{x.day} {calendar.month_name[x.month]} {x.year}"


@pytest.mark.parametrize("cid, mod", [("power", power), ("ghcn", ghcn), ("coops", coops), ("psmsl", psmsl), ("grace", grace)])
def test_each_provider_card_prints_its_source(cid, mod):
    text, hrefs = card(cid)
    src = mod.SOURCE
    assert f"Named in answers: {src['name']} · ID: " in text
    assert f"Licence {src['licence']} Updated" in text  # the licence row is the code's words, nothing added
    assert f"Credit to give {src['credit']}" in text
    assert src["url"] in hrefs


def test_each_card_prints_its_dataset_id():
    assert all(p in card("power")[0] for p in power.PARAMS.values())
    assert f"ID: {ghcn.DATASET_ID} · {ghcn.VERSION}" in card("ghcn")[0] and f"https://doi.org/{ghcn.DATASET_ID[4:]}" in card("ghcn")[1]
    assert f"ID: {coops.DATASET_ID}" in card("coops")[0]
    assert f"ID: {psmsl.DATASET_ID}" in card("psmsl")[0]
    g = grace.source()
    assert grace.ZIP in card("grace")[0] and g["version"] in card("grace")[0] and g["record_url"] in card("grace")[1]


def test_the_rules_dates_and_caveats_on_the_cards():
    assert f"within {ghcn.MAX_KM} km that has at least {ghcn.MIN_YEARS} years of readings since {ghcn.FIRST_DAY[:4]}" in card("ghcn")[0]
    assert psmsl.MAX_KM == coops.MAX_KM
    sea = part(SOURCES, '<section class="st-sec" id="sea-level"', '<article')[0]
    assert (f"the nearest gauge within {coops.MAX_KM} km with at least {upstream.MIN_YEARS} years of monthly readings, "
            f"the last no more than {upstream.MAX_STALE_YEARS} years before the end of last year") in sea
    assert f"Keep in mind: {trend.POWER_T_CAVEAT}" in card("power")[0] and f"For rain: {power.RAIN_LIMIT}" in card("power")[0]
    assert f"Keep in mind: {trend.GHCN_CAVEAT}" in card("ghcn")[0]
    first, last = re.search(r"\.(\d{6})_(\d{6})_", grace.ZIP).groups()
    assert (f"Our copy runs from {month(first[:4] + '-' + first[4:])} to {month(last[:4] + '-' + last[4:])} and was made on "
            f"{day(grace.RETRIEVED)}.") in card("grace")[0]


def test_era5_card_open_meteo_part():
    """The card shows our Copernicus copy and names Open-Meteo, the fallback, with its own licence, credit and ID."""
    text, hrefs = card("era5")
    src = era5.SOURCE
    assert f"From Open-Meteo, named in answers: {src['name']} · ID: {era5.DATASET_ID} ·" in text
    assert f"If the answer names Open-Meteo: {src['licence']}." in text  # the code's words only
    assert "Open-Meteo's free service is for non-commercial use only." in text  # Open-Meteo's terms, its own line
    assert f"If the answer names Open-Meteo, also: {src['credit']}" in text and src["url"] in hrefs
    assert f"Credit to give {upstream.COPERNICUS}" in text


def test_era5_card_pack_part(monkeypatch):
    pack = era5.PACK_SOURCE
    # the shipped default is our public Blob store (conftest clears it for every test, so read the module's own line)
    assert re.search(r'^PACK_URL = "https://[\w-]+\.public\.blob\.vercel-storage\.com/era5/v2025-12"$',
                     Path(era5.__file__).read_text(), re.M), "production must serve the pack (design 17 §4)"
    monkeypatch.setattr(era5, "PACK_URL", "https://example.test/era5/v2025-12")
    monkeypatch.delenv(era5.PACK, raising=False)
    monkeypatch.delenv(era5.REPLAY, raising=False)
    assert era5.default_source() is pack, "the page shows the pack: era5 must serve it by default (design 17 §4)"
    text, hrefs = card("era5")
    assert f"Named in answers: {pack['name']} · ID: {era5.PACK_DATASET_ID} ·" in text
    assert f"Licence {pack['licence']}, the licence of ERA5" in text
    assert pack["url"] in hrefs and era5.PACK_DOI_URL in hrefs
    assert f"Our copy runs from {month(era5.PACK_START)} to December 2025." in text


@pytest.mark.parametrize("cid, mod, name, version", [
    ("ar6", ar6, projection.SOURCE_NAME, None), ("atlas", cmip6, projection.CMIP6_SOURCE["name"], projection.CMIP6_SOURCE["version"])])
def test_projection_cards_print_their_manifests(cid, mod, name, version):
    m = json.loads(mod.MANIFEST.read_text(encoding="utf-8"))
    text, hrefs = card(cid)
    version = version or m["version"]
    shown = version if cid == "atlas" else f"version {version}"
    assert f"Named in answers: {name} · ID: doi:{m['doi']} · {shown}" in text and f"https://doi.org/{m['doi']}" in hrefs
    licence = m["licence"].replace("-", " ")  # "CC-BY-4.0", as the page writes it
    assert f"Licence {licence}, the licence of" in text and m["licence_url"] in hrefs
    assert f"version {version}, {licence}." in text  # the credit line
    cites = m["citations"] + ([m["land_mask"]["citation"]] if "land_mask" in m else [])
    assert f"How to cite {' '.join(cites)} Acknowledgement: {m['acknowledgement']}" in text
    made = m["accessed"] if cid == "ar6" else m["source"]["retrieved"]
    assert f"Our copy was made on {day(made)}." in text
    if cid == "atlas":
        assert f"retrieved from doi:{m['source']['doi']}" in text and f"Credit to give {upstream.COPERNICUS}" in text


def test_place_names_row():
    text, hrefs = part(SOURCES, '<table class="wf three">', "</table>")
    assert f"{places.SOURCE['name']}" in text and places.SOURCE["url"] in hrefs
    # the licence cell: Open-Meteo's API data licence, which code records on era5.SOURCE (places.SOURCE is /api/places'
    # source block, whose shape the contract fixes at name and url)
    row = re.search(r'<th scope="row">Place names in the search box</th>(.*?)</tr>', SOURCES, re.S).group(1)
    assert [read(c)[0] for c in re.findall(r"<td>(.*?)</td>", row, re.S)][1] == era5.SOURCE["licence"]


@pytest.mark.parametrize("col, var, name", [("air-temperature", "air_temp", "land_temp"), ("sea-level", "sea_level", "gmsl")])
def test_world_table_prints_the_snapshots(col, var, name):
    s = world.reference(name)
    src, w = s["source"], trend.WORLD[var]
    i = ("air-temperature", "sea-level").index(col)
    rows = {}
    for tr in re.findall(r"<tr>(.*?)</tr>", WORLD, re.S)[1:]:
        cells = [read(c)[0] for c in re.findall(r"<td>(.*?)</td>", tr, re.S)]
        rows[read(re.search(r'<th scope="row">(.*?)</th>', tr, re.S).group(1))[0]] = cells[i]
    assert f'<th scope="col" id="{col}">' in WORLD
    assert rows["Compared with"].lower() in (w["measure"], "the " + w["measure"])
    assert rows["Our copy runs"] == f"{month(s['times'][0])} to {month(s['times'][-1])}"
    assert rows["Updated"] == f"We refresh our copy by hand; last fetched {day(src['retrieved'])}."
    assert rows["Dataset"].endswith(f"Named in answers: {src['name']}")
    assert rows["Rate shown in"] == w["unit"]
    assert rows["Dataset ID"] == f"{src['dataset_id']} ↗" and f"https://doi.org/{src['dataset_id'][4:]}" in read(WORLD)[1]
    assert f"with at least {trend.WORLD_YEARS} years" in rows["Months compared"]
    if w["since"]:
        assert rows["Months compared"].startswith(f"The gauge's months from {month(w['since'])} to {month(s['times'][-1])}")
    licence, cite = re.split(r"(?: with this citation|; cite): ", s["notes"][-1])
    assert rows["Licence"].startswith(licence)
    credits = read(WORLD.split('id="credits"')[1])[0]
    assert cite in credits


def test_world_page_notes_and_no_world_figure():
    text = read(WORLD)[0]
    assert "28 March 2022" in " ".join(world.reference("gmsl")["notes"]) and "after 28 March 2022 preliminary" in text
    none = read(WORLD.split('id="none"')[1].split("</section>")[0])[0]
    assert len(trend.NO_MATCH) == 3
    for label, var in (("Hottest days", "air_temp_max"), ("Rain", "precip"), ("Water on land", "water_storage")):
        assert f"{label} {trend.NO_MATCH[var]}" in none


def test_links_checked_line_and_stamp(tmp_path, monkeypatch):
    for page in (SOURCES, WORLD):
        assert len(check_links.CHECKED.findall(page)) == 1
    pages = []
    for k, page in enumerate((SOURCES, WORLD)):
        p = tmp_path / f"{k}.html"
        p.write_text(page, encoding="utf-8")
        pages.append(p)
    monkeypatch.setattr(check_links, "PAGES", pages)
    check_links.stamp(date(2027, 1, 5))
    for p, page in zip(pages, (SOURCES, WORLD)):
        out = p.read_text(encoding="utf-8")
        assert "Links checked on 5 January 2027." in out
        assert check_links.CHECKED.sub("", out) == check_links.CHECKED.sub("", page)  # nothing else changed


def test_link_check_covers_every_outbound_link():
    out = [h for page in (SOURCES, WORLD) for h in read(page)[1] if not h.startswith(("/", "#"))]
    assert out and all(h.startswith("https://") for h in out)  # providers' links are https, so a check can open each
    assert set(check_links.page_links()) == set(out)


@pytest.mark.parametrize("page", [SOURCES, WORLD])
def test_page_structure(page):
    """Design 17 §7, and what the Space Apps rules and the CSP ask of every page."""
    assert page.count("<h1>") == 1 and "Built with AI assistance" in page
    assert re.findall(r"<script[^>]*>", page) == ['<script src="/prefs.js">'] and 'style="' not in page and "<img" not in page
    ids = re.findall(r'\sid="([^"]+)"', page)
    assert len(ids) == len(set(ids))
    arts, h3s = re.findall(r'<article [^>]*aria-labelledby="([^"]+)"', page), re.findall(r'<h3 id="([^"]+)"', page)
    assert arts == h3s  # every card is an article named by its own h3, and every h3 is a card's
    for m in re.finditer(r"<table.*?</table>", page, re.S):
        t = m.group()
        assert "<caption>" in t and t.count('scope="col"') >= 2 and 'scope="row"' in t
    # outbound links: each name says where it goes
    names = [read(a)[0] for a in re.findall(r'<a [^>]*href="https://[^"]+"[^>]*>.*?</a>', page, re.S)]
    assert len(names) == len(set(names)), names


def test_both_pages_are_served():
    c = TestClient(app, follow_redirects=False)
    for path, h1 in (("/sources/", "<h1>Data sources</h1>"), ("/sources/world/", "<h1>World figures we compare with</h1>")):
        r = c.get(path)
        assert r.status_code == 200 and h1 in r.text
        r = c.get(path.rstrip("/"))
        assert r.status_code in (307, 308) and r.headers["location"].endswith(path)
    assert c.get("/sources.css").status_code == 200
    r = c.get("/sources/no-such-page")
    assert r.status_code == 404 and r.headers["content-type"].startswith("text/html")


def test_deep_links_clear_the_taller_bar():
    """QA: --top-h is this bar's real height, measured from 320 to 414 px. The 44 px brand link shares a row with Settings
    down to 384 px (117 px, where style.css's 399 px rule gives the app 149) and wraps below that (169 px); 390 and 393
    are common phone widths. scroll-margin-top follows --top-h."""
    css = (ROOT / "web" / "sources.css").read_text(encoding="utf-8")
    assert "min-height: 44px; }" in css.split(".top .brand {")[1].split("\n")[0]
    tall = re.findall(r"@media \(max-width: (\d+)px\) \{ :root \{ --top-h: 169px; \} \}", css)
    assert len(tall) == 1 and int(tall[0]) <= 383, tall
    assert "@media (max-width: 399px) { :root { --top-h: 117px; } }" in css  # undoes the app's 149 px from 384 to 399 px
    assert css.index("--top-h: 117px") < css.index("--top-h: 169px")  # the narrower query comes last, so it wins
    assert ".st-sec, .src-card, .wf th[id] { scroll-margin-top: calc(var(--top-h) + 16px); }" in css
