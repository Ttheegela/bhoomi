"""Text a provider sent, made safe to put in an error message or a note: one plain line, cut to a limit.
Models read these messages, so a provider must not be able to put a long block of text in front of them."""
import re
import unicodedata

LIMIT = 200  # the most a caller sees in one error sentence, our own words included
NAME = 80  # the most of a provider's station or gauge name


def text(value, limit: int) -> str:
    """Any value -> one line of plain text, whitespace and control characters collapsed, cut to `limit` with a final "…"."""
    s = value if isinstance(value, str) else str(value)
    s = "".join(c for c in s if unicodedata.category(c) != "Cf")  # bidi controls, zero-width characters
    s = " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", s).split())
    return s if len(s) <= limit else s[: max(limit - 1, 0)].rstrip() + "…"


def fit(prefix: str, value, suffix: str = "") -> str:
    """prefix + provider text + suffix, with the provider text cut so the whole is at most LIMIT characters."""
    return prefix + text(value, LIMIT - len(prefix) - len(suffix)) + suffix


def readable(name: str) -> str:
    """An all-capitals provider name -> title case ("NEW YORK (THE BATTERY)" -> "New York (The Battery)"); a name with any lowercase letter is returned unchanged.
    A final ", IN" style two-letter code keeps its capitals. Call it after text(), so the length limit is unchanged."""
    if any(c.islower() for c in name):
        return name
    # ponytail: roman numerals are kept up to IX; initials come out as "Dc", "Usa"; a truncated provider name stays truncated; use a lookup table if that matters
    head, code = (m.group(1), m.group(2)) if (m := re.fullmatch(r"(.*), ([^\W\d_]{2})", name)) else (name, "")
    out, start = [], True
    for c in head:
        cased = c.upper() if start else c.lower()
        out.append(cased if len(cased) == 1 else c)  # "İ" lowercases to two characters: keep it, so the length never grows
        start = c in " (/-."
    head = re.sub(r"\b(?:Ii|Iii|Iv|Vi|Vii|Viii|Ix)\b", lambda m: m.group().upper(), "".join(out))
    return head + (f", {code}" if code else "")
