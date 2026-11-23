"""The tool's own guidance: the model writes MARKER, the code puts each result's guidance strings there word for word
(the fact, then where to look next, the future links, the disclaimer once and the sources pages line). The model
never composes them. A result without a guidance fact adds nothing. The experts' projection reaches the answer in the
plain lines that lead it (lead), not here."""
import re

from earthtrends.agent import resources, tools
from earthtrends.stats.guidance import DISCLAIMER_PROJECTION

MARKER = "[GUIDANCE]"
_MARK = re.compile(r"[ \t]*\**\[\s*guidance\s*\]\**", re.I)  # tolerant, like the official-resources marker


def _s(x) -> str:
    return x.strip() if isinstance(x, str) else ""


def _end(s: str) -> str:
    return s if s[-1:] in ".!?" else s + "."


DISAGREE = "Models disagree on wetter or drier."  # the page's words for by_2050.disagree (rain)
SOURCES_LINE = "All our data sources, with licences: bhoomi.earth/sources"  # design 17 §8: last, no number
_AFTER_SOURCES = re.compile(rf"(?<={re.escape(SOURCES_LINE)})[ \t]+(?=\S)")  # text after it starts a new line


def projection_view(p):
    """A result's `projection` as the model reads it (the number check pools it): the default scenario's 2050 (sea
    level) or 2041-2060 readout text with its range name, "more than today" where the tool gives it, and the notes the
    model passes on with the caveats (models_note, location_note, check). Not available: only its why."""
    if not isinstance(p, dict):
        return p
    if not p.get("available"):
        return {"available": False, "why": p.get("why")}
    ro = p.get("readouts") or {}
    b = ro.get("by_2050") or {}
    sc = next((s for s in p.get("scenarios") or [] if s.get("id") == b.get("scenario")), {})
    w = b.get("window")
    out = {"available": True, "kind": p.get("kind"), "source": (p.get("source") or {}).get("name"),
           "scenario": f"{sc['name']} ({sc['code']})" if sc.get("name") and sc.get("code") else None,
           "when": f"{w[0]}–{w[1]}" if isinstance(w, list) and len(w) == 2 else "2050",  # sea level's by_2050 is 2050
           "baseline": (p.get("baseline") or {}).get("text"), "text": b.get("text"), "range_kind": b.get("range_kind"),
           "more_than_today": (ro.get("more_than_today") or {}).get("text"),
           "disagree": DISAGREE if b.get("disagree") else None, "models_note": p.get("models_note"),
           "location_note": (p.get("location") or {}).get("note"), "check": (p.get("check") or {}).get("text"),
           "baseline_record": (p.get("baseline_record") or {}).get("name")}
    return {k: v for k, v in out.items() if v is not None}


def _key(c: dict):
    a = c.get("arguments") or {}
    try:
        return round(float(a["lat"]), 2) + 0.0, round(float(a["lon"]), 2) + 0.0, a.get("variable")
    except (KeyError, TypeError, ValueError):
        return None, None, a.get("variable")


def picked(calls: list[dict]) -> list[tuple[tuple, dict]]:
    """The results whose fact is shown: per place (the call's point) and measurement, the first source in catalog
    order that has one, plus any other source there whose verdict differs (never pick one of two that disagree)."""
    cat = {v["id"]: v for v in tools.list_variables()}
    groups: dict = {}
    for c in calls:
        r = c.get("result")
        if isinstance(r, dict) and isinstance(r.get("guidance"), dict) and _s(r["guidance"].get("fact")):
            groups.setdefault(_key(c), []).append(r)
    out = []
    for key, rs in groups.items():
        var = key[2]
        order = (cat.get(var) or {}).get("sources", [])
        rs.sort(key=lambda r: order.index(r["source"]["id"]) if (r.get("source") or {}).get("id") in order else 99)
        seen = set()
        for r in rs:
            if (verdict := r.get("verdict")) not in seen:
                seen.add(verdict)
                out.append((key, r))
    return out


def block(calls: list[dict], simple: bool = False, sources: bool = False) -> str:
    """The guidance text for this turn's results; "" when none has a fact. `simple` (a request for simple words,
    design 16 §4): without the facts (they carry the 95% range and the world ratio). No projection line: the plain
    lines, first in the answer, carry the projection (design 16 §4.3). `sources`: SOURCES_LINE closes it, on its own
    line (the loop decides when: the first answer or a question about sources, never in voice)."""
    rs = picked(calls)
    if not rs:
        return ""
    names = {v["id"]: v["name"].split(" (")[0] for v in tools.list_variables()}
    places = len({k[:2] for k, _ in rs}) > 1
    per = {}  # place and measurement -> how many entries: the source is named only when two there differ
    for k, _ in rs:
        per[k] = per.get(k, 0) + 1
    parts, disclaimers, look, links = [], [], {}, {}
    for k, r in rs:
        g = r["guidance"]
        what = names.get(r.get("variable"), str(r.get("variable") or ""))
        place = _s((r.get("place") or {}).get("name"))
        label = f"{place}, {what[:1].lower()}{what[1:]}" if places and place else what
        if per[k] > 1:
            label += f" ({_s((r.get('source') or {}).get('name')).split(',')[0]})"
        if not simple:
            parts.append(f"{label}: {_end(_s(g['fact']))}")
        for x in g.get("look_next") or []:
            if isinstance(x, dict) and _s(x.get("label")):
                url = _s(x.get("url"))
                look.setdefault(_s(x["label"]), f" ({url})" if url.startswith("https://") else "")
        disclaimers.append(_s(g.get("disclaimer")))
        f = g.get("future_link") or {}
        if isinstance(f, dict) and _s(f.get("url")).startswith("https://"):
            links.setdefault(f["url"].strip(), _s(f.get("label")) or "Future map")
    # once: the projection wording if any result carries it, so a mixed answer never hides the IPCC part
    disclaimer = DISCLAIMER_PROJECTION if DISCLAIMER_PROJECTION in disclaimers else next(filter(None, disclaimers), "")
    tail = ([f"Where to look next: {'; '.join(lab + url for lab, url in look.items())}."] if look else [])
    tail += [f"{lab} ({url})." for url, lab in links.items()]
    return "\n".join(filter(None, (" ".join(parts + tail + ([_end(disclaimer)] if disclaimer else [])),
                                    SOURCES_LINE if sources else "")))


RECORDS_DISAGREE = "Our records here disagree about the past."  # design 16 §4: the past clause when verdicts differ
MAX_LEAD = 3  # places and measurements that get a line, with two or more


def lead(calls: list[dict]) -> str:
    """The lines an answer that looked something up starts with (design 16 §4), written by code and outside the word
    count. Per place and measurement in picked() order: line 1 is the past clause (the shared meaning.headline, or
    RECORDS_DISAGREE when the picked verdicts differ or the records there disagree, so it never depends on which
    record is main), then plain[0]; then plain's other lines; then what each record shows with the first reason when
    the records disagree, and thin_note or single_note. Two or more places or measurements: line 1 of each (and its
    records lines), at most MAX_LEAD, each after "{Place}, {measurement}: ". "" when no result has plain lines."""
    groups: dict = {}
    for k, r in picked(calls):
        groups.setdefault(k, []).append(r)
    groups = {k: rs for k, rs in groups.items() if [x for x in rs[0].get("plain") or [] if _s(x)]}
    names = {v["id"]: v["name"].split(" (")[0] for v in tools.list_variables()}
    out = []
    for rs in list(groups.values())[:MAX_LEAD]:
        r = rs[0]
        apart = len(rs) > 1 or any((x.get("disagree") or {}).get("any") for x in rs)
        past = RECORDS_DISAGREE if apart else _s((r.get("meaning") or {}).get("headline"))
        plain = [_s(x) for x in r["plain"] if _s(x)]
        what = names.get(r.get("variable"), _s(r.get("variable")))
        place = _s((r.get("place") or {}).get("name"))
        head = (f"{place}, {what[:1].lower()}{what[1:]}: " if place else f"{what}: ") if len(groups) > 1 else ""
        d = r.get("disagree") or {}
        why = next((_s(x.get("text")) for x in d.get("reasons") or [] if isinstance(x, dict) and _s(x.get("text"))), "")
        said = [" ".join(filter(None, (_s(d.get("say")), why)))] if d.get("any") else []
        out += [head + " ".join(filter(None, (past and _end(past), plain[0]))),
                *(plain[1:] if len(groups) == 1 else []),
                *filter(None, said + [_s(r.get("thin_note")), _s(r.get("single_note"))])]
    return "\n".join(out)


def strip(text: str) -> str:
    """The text without any marker: what the word limit counts."""
    return _MARK.sub("", text)


def fill(text: str, calls: list[dict], simple: bool = False, sources: bool = False, alone: bool = False) -> str:
    """The first marker becomes the guidance (a space before it unless it starts a line); other markers go. No marker:
    the guidance goes in front of the official-resources marker if there is one, else at the end as its own
    paragraph. No guidance: markers removed, text otherwise unchanged, or with `alone` the sources pages line by itself
    in the guidance's place (a question about sources that looked nothing up). Text that follows the guidance on its
    last line (the official resources) starts a new line, so the sources pages line stands alone."""
    add = block(calls, simple, sources) or (SOURCES_LINE if alone else "")
    if not _MARK.search(text):
        if not add:
            return text
        m = resources._MARK.search(text)
        if m:
            head = text[:m.start()].rstrip()
            return _AFTER_SOURCES.sub("\n", head + ("\n\n" if head else "") + add + " " + text[m.start():].lstrip())
        return text.rstrip() + "\n\n" + add
    out, last = [], 0
    for m in _MARK.finditer(text):
        out.append(text[last:m.start()])
        if add:
            out.append(add if m.start() == 0 or text[m.start() - 1] == "\n" else " " + add)
            add = ""
        last = m.end()
    return _AFTER_SOURCES.sub("\n", ("".join(out) + text[last:]).rstrip())
