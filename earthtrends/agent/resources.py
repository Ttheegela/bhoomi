"""Official links for decision questions: the model writes MARKER, the code puts one fixed sentence there.
Links only, no numbers. Addresses checked to respond on 2026-11-14."""
import re

MARKER = "[OFFICIAL RESOURCES]"
_MARK = re.compile(r"[ \t]*\[\s*official\s+resources\s*\]", re.I)
US_COAST = ("For future flood risk at a US address, see NOAA's Sea Level Rise Viewer (https://coast.noaa.gov/slr/) "
            "and FEMA's flood maps (https://msc.fema.gov/portal/home).")
SEA = "For how sea level may change in future, see NASA's sea level portal (https://sealevel.nasa.gov/)."
OTHER = ("For what the climate may do next in the United States, see the U.S. Climate Resilience Toolkit "
         "(https://toolkit.climate.gov/).")
URLS = ("https://coast.noaa.gov/slr/", "https://msc.fema.gov/portal/home", "https://sealevel.nasa.gov/",
        "https://toolkit.climate.gov/")  # every address above; the eval scorer imports it


def sentence(results: list[dict]) -> str:
    """The row of the table for this turn's successful results; "" when there are none."""
    if any(r.get("variable") == "sea_level" and (r.get("source") or {}).get("id") == "coops" for r in results):
        return US_COAST
    if any(r.get("variable") == "sea_level" for r in results):
        return SEA
    return OTHER if results else ""


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
