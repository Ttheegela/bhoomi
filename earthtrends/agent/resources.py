"""Official links for decision questions: the model writes MARKER, the code puts one fixed sentence there.
Links only, no numbers outside an address. Addresses checked to respond on 2026-11-14 and 2026-11-15."""
import re

MARKER = "[OFFICIAL RESOURCES]"
# Tolerant: any case, singular or plural, space, underscore or hyphen, and markdown asterisks around it.
_MARK = re.compile(r"[ \t]*\**\[\s*official[\s_-]+resources?\s*\]\**", re.I)
# ponytail: rough boxes (contiguous states, Alaska, Hawaii), not borders; parts of Canada and Mexico near the edges
# count as US. Use real borders if a near-border place ever gets the wrong link.
US_BOXES = ((24.4, 49.5, -125.0, -66.9), (51.0, 71.5, -170.0, -129.9), (18.9, 22.3, -160.3, -154.8))
US_COAST = ("For future flood risk at a US address, see NOAA's Sea Level Rise Viewer (https://coast.noaa.gov/slr/) "
            "and FEMA's flood maps (https://msc.fema.gov/portal/home).")
SEA = ("For how sea level may change in future near you, see NASA's Sea Level Projection Tool, which shows the IPCC's "
       "projections (https://sealevel.nasa.gov/data_tools/17).")
OTHER = ("For what the climate may do next in the United States, see the U.S. Climate Resilience Toolkit "
         "(https://toolkit.climate.gov/).")
WATER = "For water risk where you are, see the World Resources Institute's Aqueduct tools (https://www.wri.org/aqueduct)."
WORLD = ("For what the climate may do next in your region, see the IPCC's Interactive Atlas "
         "(https://interactive-atlas.ipcc.ch/).")
URLS = ("https://coast.noaa.gov/slr/", "https://msc.fema.gov/portal/home", "https://sealevel.nasa.gov/data_tools/17",
        "https://toolkit.climate.gov/", "https://www.wri.org/aqueduct",
        "https://interactive-atlas.ipcc.ch/")  # every address above; the eval scorer imports it


def sentence(results: list[dict]) -> str:
    """The row of the table for this turn's successful results; "" when there are none."""
    if any(r.get("variable") == "sea_level" and (r.get("source") or {}).get("id") == "coops" for r in results):
        return US_COAST
    if any(r.get("variable") == "sea_level" for r in results):
        return SEA
    if not results:
        return ""
    p = results[0].get("place") or {}
    lat, lon = p.get("lat"), p.get("lon")
    us = (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
          and any(a <= lat <= b and c <= lon <= d for a, b, c, d in US_BOXES))
    if us:
        return OTHER  # the Toolkit is for the United States only
    return WATER if results[0].get("variable") == "water_storage" else WORLD


def strip(text: str) -> str:
    """The text without any marker: what the word limit counts."""
    return _MARK.sub("", text)


def fill(text: str, results: list[dict]) -> str:
    """The first marker becomes the sentence (a space before it unless it starts a line); every other marker, or all
    of them when there is no result, is removed. Text with no marker is unchanged."""
    if not _MARK.search(text):
        return text
    add, out, last = sentence(results), [], 0
    for m in _MARK.finditer(text):
        out.append(text[last:m.start()])
        if add:
            out.append(add if m.start() == 0 or text[m.start() - 1] == "\n" else " " + add)
            add = ""
        last = m.end()
    return ("".join(out) + text[last:]).rstrip()
