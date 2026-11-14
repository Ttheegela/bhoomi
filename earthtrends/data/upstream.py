"""Text a provider sent, made safe to put in an error message or a note: one plain line, cut to a limit.
Models read these messages, so a provider must not be able to put a long block of text in front of them."""
import re

LIMIT = 200  # the most a caller sees in one error sentence, our own words included
NAME = 80  # the most of a provider's station or gauge name


def text(value, limit: int) -> str:
    """Any value -> one line of plain text, whitespace and control characters collapsed, cut to `limit` with a final "…"."""
    s = " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", value if isinstance(value, str) else str(value)).split())
    return s if len(s) <= limit else s[: max(limit - 1, 0)].rstrip() + "…"


def fit(prefix: str, value, suffix: str = "") -> str:
    """prefix + provider text + suffix, with the provider text cut so the whole is at most LIMIT characters."""
    return prefix + text(value, LIMIT - len(prefix) - len(suffix)) + suffix
