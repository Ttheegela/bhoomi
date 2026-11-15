"""The tool's own guidance: the model writes MARKER, the code puts each result's guidance strings there word for word
(risk level, why, recommendation, the outlook for OUTLOOK_YEAR, then the disclaimer once and the future links). The
model never composes them. A result without "guidance" adds nothing."""
import re

from earthtrends.agent import resources, tools

MARKER = "[GUIDANCE]"
_MARK = re.compile(r"[ \t]*\**\[\s*guidance\s*\]\**", re.I)  # tolerant, like the official-resources marker
OUTLOOK_YEAR = 2050
OUTLOOK_LABEL = "If the past trend continues"


def _s(x) -> str:
    return x.strip() if isinstance(x, str) else ""


def _end(s: str) -> str:
    return s if s[-1:] in ".!?" else s + "."


def _key(c: dict):
    a = c.get("arguments") or {}
    try:
        return round(float(a["lat"]), 2) + 0.0, round(float(a["lon"]), 2) + 0.0, a.get("variable")
    except (KeyError, TypeError, ValueError):
        return None, None, a.get("variable")


def picked(calls: list[dict]) -> list[tuple[tuple, dict]]:
    """The results whose guidance is shown: per place (the call's point) and measurement, the first source in catalog
    order that has one, plus any other source there whose risk level differs (never pick one of two that disagree)."""
    cat = {v["id"]: v for v in tools.list_variables()}
    groups: dict = {}
    for c in calls:
        r = c.get("result")
        if isinstance(r, dict) and isinstance(r.get("guidance"), dict) and _s(r["guidance"].get("risk_label")):
            groups.setdefault(_key(c), []).append(r)
    out = []
    for key, rs in groups.items():
        var = key[2]
        order = (cat.get(var) or {}).get("sources", [])
        rs.sort(key=lambda r: order.index(r["source"]["id"]) if (r.get("source") or {}).get("id") in order else 99)
        seen = set()
        for r in rs:
            if (label := r["guidance"]["risk_label"]) not in seen:
                seen.add(label)
                out.append((key, r))
    return out


def block(calls: list[dict]) -> str:
    """The guidance text for this turn's results; "" when none has guidance."""
    rs = picked(calls)
    if not rs:
        return ""
    names = {v["id"]: v["name"].split(" (")[0] for v in tools.list_variables()}
    places = len({k[:2] for k, _ in rs}) > 1
    per = {}  # place and measurement -> how many entries: the source is named only when two there differ
    for k, _ in rs:
        per[k] = per.get(k, 0) + 1
    parts, disclaimer, links = [], "", {}
    for k, r in rs:
        g = r["guidance"]
        what = names.get(r.get("variable"), str(r.get("variable") or ""))
        place = _s((r.get("place") or {}).get("name"))
        label = f"{place}, {what[:1].lower()}{what[1:]}" if places and place else what
        if per[k] > 1:
            label += f" ({_s((r.get('source') or {}).get('name')).split(',')[0]})"
        bits = [f"{label}: {_end(g['risk_label'].strip())}"]
        bits += [_end(s) for s in (_s(g.get("why")), _s(g.get("recommendation"))) if s]
        o = next((x for x in g.get("outlook") or [] if isinstance(x, dict) and x.get("year") == OUTLOOK_YEAR
                  and _s(x.get("text"))), None)
        if o:
            bits.append(f"{_s(g.get('outlook_label')) or OUTLOOK_LABEL}: {_end(o['text'].strip())}")
        parts.append(" ".join(bits))
        disclaimer = disclaimer or _s(g.get("disclaimer"))
        f = g.get("future_link") or {}
        if isinstance(f, dict) and _s(f.get("url")).startswith("https://"):
            links.setdefault(f["url"].strip(), _s(f.get("label")) or "Future map")
    tail = ([_end(disclaimer)] if disclaimer else []) + [f"{lab} ({url})." for url, lab in links.items()]
    return " ".join(parts + tail)


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
