"""The tool's own guidance: the model writes MARKER, the code puts each result's guidance strings there word for word
(the fact, then where to look next, the experts' projection, the future links and the disclaimer once). The model
never composes them. A result without a guidance fact adds nothing."""
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


def projection_view(p):
    """A result's `projection` as the model reads it, and the only thing the projection line is built from, so every
    number the answer shows is one the model saw: the default scenario's 2050 (sea level) or 2041-2060 readout text
    with its range name, "more than today" where the tool gives it, and the notes. Not available: only its why."""
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
           "baseline_record": (p.get("baseline_record") or {}).get("name")}
    return {k: v for k, v in out.items() if v is not None}


def projection_line(r: dict, label: str) -> str:
    """The experts' projection for one result, from projection_view alone; "" when it has none."""
    v = projection_view(r.get("projection"))
    if not (isinstance(v, dict) and v.get("available") and _s(v.get("text")) and _s(v.get("range_kind"))):
        return ""
    under = f" under {v['scenario']}" if v.get("scenario") else ""
    src = f", from {v['source']}" if v.get("source") else ""
    vs = f" against {v['baseline']}" if v.get("baseline") else ""
    more = f", {v['more_than_today']}" if v.get("more_than_today") else ""
    line = (f"{label}, experts' projection for {v['when']}{under}{src}: {v['text']}{vs}{more}. "
            f"The range is the {v['range_kind']}.")
    return " ".join([line] + [_end(v[k]) for k in ("disagree", "models_note") if _s(v.get(k))])


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


def block(calls: list[dict]) -> str:
    """The guidance text for this turn's results; "" when none has a fact."""
    rs = picked(calls)
    if not rs:
        return ""
    names = {v["id"]: v["name"].split(" (")[0] for v in tools.list_variables()}
    places = len({k[:2] for k, _ in rs}) > 1
    per = {}  # place and measurement -> how many entries: the source is named only when two there differ
    for k, _ in rs:
        per[k] = per.get(k, 0) + 1
    parts, disclaimers, look, links, future = [], [], {}, {}, {}
    for k, r in rs:
        g = r["guidance"]
        what = names.get(r.get("variable"), str(r.get("variable") or ""))
        place = _s((r.get("place") or {}).get("name"))
        label = f"{place}, {what[:1].lower()}{what[1:]}" if places and place else what
        future[k] = future.get(k) or projection_line(r, label)  # once per place and measurement, first source first
        if per[k] > 1:
            label += f" ({_s((r.get('source') or {}).get('name')).split(',')[0]})"
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
    tail += [x for x in future.values() if x] + [f"{lab} ({url})." for url, lab in links.items()]
    return " ".join(parts + tail + ([_end(disclaimer)] if disclaimer else []))


def strip(text: str) -> str:
    """The text without any marker: what the word limit counts."""
    return _MARK.sub("", text)


def fill(text: str, calls: list[dict]) -> str:
    """The first marker becomes the guidance (a space before it unless it starts a line); other markers go. No marker:
    the guidance goes in front of the official-resources marker if there is one, else at the end as its own
    paragraph. No guidance: markers removed, text otherwise unchanged."""
    add = block(calls)
    if not _MARK.search(text):
        if not add:
            return text
        m = resources._MARK.search(text)
        if m:
            head = text[:m.start()].rstrip()
            return head + ("\n\n" if head else "") + add + " " + text[m.start():].lstrip()
        return text.rstrip() + "\n\n" + add
    out, last = [], 0
    for m in _MARK.finditer(text):
        out.append(text[last:m.start()])
        if add:
            out.append(add if m.start() == 0 or text[m.start() - 1] == "\n" else " " + add)
            add = ""
        last = m.end()
    return ("".join(out) + text[last:]).rstrip()
