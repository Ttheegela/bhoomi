import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _contrast(a, b):
    def lum(c):
        r, g, b_ = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _over(top, op, bg):
    return "#" + "".join("%02x" % round(op * int(top[i:i + 2], 16) + (1 - op) * int(bg[i:i + 2], 16)) for i in (1, 3, 5))


def _themes():
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "web" / "style.css").read_text(encoding="utf-8"), flags=re.S)
    tok = lambda body: dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6}|[\d.]+)", body))
    light = tok(re.search(r":root \{([^}]*)\}", css)[1])
    dark = {**light, **tok(re.search(r':root\[data-theme="dark"\] \{([^}]*)\}', css)[1])}
    return (("light", light), ("dark", dark))


def _band(th, k):
    return _over(th["scen-%d" % k], float(th["scen-band"]), th["surface"])


def test_every_median_reaches_3_to_1_inside_another_scenarios_band():
    """QA6: the shaded band is the selected scenario's; the other medians run inside it (The Battery: Low's median lies
    in Intermediate's likely band 2020-2100). Light: Low #2B9877 on Intermediate's 15% band is 2.93:1, 2.67:1 on Very
    high's. Dark: Very high #E5487C on Intermediate's 22% band is 2.83:1."""
    bad = []
    for name, th in _themes():
        for band in (1, 2, 3, 4):
            bg = _band(th, band)
            for med in (1, 2, 3, 4):
                r = _contrast(th["scen-%d" % med], bg)
                if med != band and r < 3.0:
                    bad.append((name, "median k%d on band k%d" % (med, band), round(r, 2)))
    assert not bad, bad


def test_every_line_reaches_3_to_1_on_its_casing():
    """QA6: in the future chart the trend line (rising, falling, no change) and the medians lie on a casing, so their
    neighbours are the casing colour, whatever is under it (light orange on its range and a band was 2.48:1, the dark
    falling blue on a dark band 2.29:1)."""
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "web" / "style.css").read_text(encoding="utf-8"), flags=re.S)
    case = re.search(r"\n\.c-case \{[^}]*stroke: var\(--([\w-]+)\);", css)[1]
    bad, checked = [], 0
    for name, th in _themes():
        for line in ("up-bg", "dn-bg", "nc-bg", "scen-1", "scen-2", "scen-3", "scen-4"):
            r = _contrast(th[line], th[case])
            checked += 1
            if r < 3.0:
                bad.append((name, line, round(r, 2)))
    assert not bad and checked == 14, bad


def test_rising_trend_line_reaches_3_to_1_on_every_band():
    """QA6: the trend line runs to the record's end, so it crosses the band from 2020 (The Battery, Very high low
    confidence, 2020-2026). The rising orange #D4620A was 2.83:1 on Very high's light band and 2.99:1 on High's."""
    bad = []
    for name, th in _themes():
        for band in (1, 2, 3, 4):
            r = _contrast(th["up-bg"], _band(th, band))
            if r < 3.0:
                bad.append((name, "trend on band k%d" % band, round(r, 2)))
    assert not bad, bad
