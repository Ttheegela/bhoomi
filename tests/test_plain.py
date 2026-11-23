"""The plain-language lines (earthtrends/stats/plain.py; web/design/16-plain-language.md §1). Offline: the rework
fixtures (synthetic records, real AR6 and CMIP6 packs) and small hand-made projections."""
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from earthtrends.stats import compute_trend
from earthtrends.stats.plain import AGREE, NO_PROJECTION, check_text, plain_lines, scenario_lines

RW = Path(__file__).parent / "fixtures" / "rework"
CASES = sorted(f.stem for f in RW.glob("*.json") if f.stem != "variables")
NB = " "
PATH = "the intermediate emissions path"
CAVEAT = "Faster ice-sheet loss could push this higher, outside this range."
SEA_YEARS = list(range(2020, 2151, 10))
WINDOWS = [{"start": 2021, "end": 2040, "mid": 2030}, {"start": 2041, "end": 2060, "mid": 2050},
           {"start": 2081, "end": 2100, "mid": 2090}]


def nb(s: str) -> str:
    """The design's worked strings, with the no-break space the lines put before a unit."""
    return re.sub(r" (cm|mm|°C)\b", NB + r"\1", s)


def trend(name):
    return json.loads((RW / f"{name}.json").read_text())["trend"]


def row(t, sid):
    return next(s for s in t["projection"]["scenarios"] if s["id"] == sid)


def sea(p50, p17, p83, rate, confidence="medium", at=2050):
    """A one-row sea-level projection with values only at `at`."""
    i = SEA_YEARS.index(at)
    col = lambda v: [v if k == i else None for k in range(len(SEA_YEARS))]  # noqa: E731
    r = {"id": "x", "name": "intermediate emissions", "confidence": confidence, "p17": col(p17), "p50": col(p50),
         "p83": col(p83), "rate": {"p50": col(rate)}}
    return {"years": SEA_YEARS, "caveat": CAVEAT, "scenarios": [r], "default_scenario": "x"}, r


def cm6(p50, p10, p90, disagree=None):
    r = {"id": "x", "name": "intermediate emissions", "p10": [p10] * 3, "p50": [p50] * 3, "p90": [p90] * 3,
         "disagree": None if disagree is None else [disagree] * 3}
    return {"windows": WINDOWS, "scenarios": [r], "default_scenario": "x"}, r


# ---- §1's worked lines, from the fixtures ----

def test_the_battery_sea_level_medium_confidence():
    assert plain_lines(trend("battery_sea_level")) == [nb(s) for s in (
        "By 2050, experts project the sea here about 36 cm higher than its 1995 to 2014 average, on the intermediate "
        "emissions path.",
        "Experts give about a 2 in 3 chance it lands between 27 and 46 cm higher on that path. Faster ice-sheet loss "
        "could push this higher, outside this range.",
        "So each high tide would come in about that much higher than in 1995 to 2014, and the sea would still be "
        "rising about 8.6 mm a year.")]


def test_sea_level_low_confidence_row():
    t = trend("battery_sea_level")
    assert scenario_lines("sea_level", t["projection"], row(t, "ssp245_low"))[1:] == [nb(s) for s in (
        "Experts have low confidence in this path: it adds ice-sheet loss that is hard to predict, so they give no "
        "odds for it. Its middle range is between 27 and 48 cm higher.",
        "So each high tide would come in about that much higher than in 1995 to 2014, and the sea would still be "
        "rising about 8.7 mm a year.")]


def test_princeton_air_temperature():
    assert plain_lines(trend("princeton_air_temp")) == [nb(s) for s in (
        "Around 2050, climate models put the average year here about 1.9 °C warmer than in 1995 to 2014, on the "
        "intermediate emissions path.",
        "8 in 10 climate models put it between 1.2 and 2.3 °C warmer. That shows how much the models agree, not how "
        "likely it is.",
        "An average day, summer and winter together, would be about that much warmer; this does not say how summers "
        "alone would change.")]


def test_delhi_hottest_day():
    assert plain_lines(trend("delhi_hottest_day")) == [nb(s) for s in (
        "Around 2050, climate models put each month's hottest day here about 1.3 °C hotter than in 1995 to 2014, on "
        "the intermediate emissions path.",
        "8 in 10 climate models put it between 0.5 and 1.8 °C hotter. That shows how much the models agree, not how "
        "likely it is.",
        "So in a typical month the hottest day would be about that much hotter; the year's single hottest day is not "
        "projected here.")]


def test_chennai_rain_models_disagree():
    assert plain_lines(trend("chennai_rain")) == [nb(s) for s in (
        "Around 2050, climate models put a year's rain here about 11% more than in 1995 to 2014, on the intermediate "
        "emissions path.",
        "The models disagree on wetter or drier: 8 in 10 of them put it between 3% less and 24% more rain.",
        "For every 100 mm of rain a usual year brought here in 1995 to 2014, a year around 2050 would bring about "
        "111 mm.")]


def test_water_storage_has_no_projection():
    assert plain_lines(trend("grace_water_storage")) == [
        "There is no standard expert projection for total water storage, so we don't show one.",
        "A change this steady would be very unlikely if nothing were really changing.",
        "About 1.6 cm less water each year, as a layer spread over the region."]  # meaning.comparison, as it is


def test_no_projection_uses_why_and_how_sure():
    assert plain_lines(trend("riverside_no_baseline")) == [
        "This record has no 1995–2014 average to start the projection from, so we don't show one.",
        "A change like this would be unlikely if nothing were really changing.",
        "About 0.4 °C warmer every 10 years."]
    # an empty comparison leaves two lines; no projection at all says so
    assert plain_lines({"projection": {"available": False, "why": "Why."},
                        "meaning": {"confidence": "Not clear", "comparison": ""}}) == [
        "Why.", "The data do not show a clear change: the ups and downs are too large to tell."]
    assert plain_lines({"meaning": {"confidence": "Clear", "comparison": ""}})[0] == NO_PROJECTION


# ---- the other rows and special cases of §1 ----

def test_sea_level_lower_both_ends_below_zero_and_falling_rate():
    p, r = sea(-123, -180, -60, -1.2)
    assert scenario_lines("sea_level", p, r) == [nb(s) for s in (
        f"By 2050, experts project the sea here about 12 cm lower than its 1995 to 2014 average, on {PATH}.",
        f"Experts give about a 2 in 3 chance it lands between 6 and 18 cm lower on that path. {CAVEAT}",
        "So each high tide would come in about that much lower than in 1995 to 2014.")]  # rate <= 0: no rising clause


def test_sea_level_range_across_zero_low_confidence_null_rate():
    p, r = sea(12, -30, 55, None, confidence="low")
    assert scenario_lines("sea_level", p, r) == [nb(s) for s in (
        f"By 2050, experts project the sea here about 1.2 cm higher than its 1995 to 2014 average, on {PATH}.",
        "Experts have low confidence in this path: it adds ice-sheet loss that is hard to predict, so they give no "
        "odds for it. Its middle range is between 3.0 cm lower and 5.5 cm higher.",
        "So each high tide would come in about that much higher than in 1995 to 2014.")]


def test_sea_level_range_end_at_zero_reads_no_change():
    p, r = sea(25, 0, 50, 2)
    assert scenario_lines("sea_level", p, r)[1:] == [nb(s) for s in (
        f"Experts give about a 2 in 3 chance it lands between no change and 5.0 cm higher on that path. {CAVEAT}",
        "So each high tide would come in about that much higher than in 1995 to 2014, and the sea would still be "
        "rising about 2.0 mm a year.")]


def test_sea_level_value_of_zero_drops_line_3():
    p, r = sea(0, -20, 20, 3.0)
    assert scenario_lines("sea_level", p, r) == [nb(s) for s in (
        f"By 2050, experts project the sea here at about its 1995 to 2014 average, on {PATH}.",
        f"Experts give about a 2 in 3 chance it lands between 2.0 cm lower and 2.0 cm higher on that path. {CAVEAT}")]


def test_sea_level_year_and_null_value():
    p, r = sea(612, 450, 800, 12.4, at=2100)
    assert scenario_lines("sea_level", p, r) == [f"By 2050, the experts give no value here on {PATH}."]
    assert scenario_lines("sea_level", p, r, 2100)[0] == nb(
        f"By 2100, experts project the sea here about 61 cm higher than its 1995 to 2014 average, on {PATH}.")
    with pytest.raises(ValueError):
        scenario_lines("sea_level", p, r, 2055)


def test_air_temperature_range_across_zero():
    p, r = cm6(0.3, -0.5, 1.2)
    assert scenario_lines("air_temp", p, r)[:2] == [nb(s) for s in (
        f"Around 2050, climate models put the average year here about 0.30 °C warmer than in 1995 to 2014, on {PATH}.",
        f"8 in 10 climate models put it between 0.5 °C cooler and 1.2 °C warmer. {AGREE}")]


def test_hottest_day_cooler():
    p, r = cm6(-0.42, -0.9, -0.1)
    assert scenario_lines("air_temp_max", p, r) == [nb(s) for s in (
        f"Around 2050, climate models put each month's hottest day here about 0.42 °C cooler than in 1995 to 2014, on "
        f"{PATH}.",
        f"8 in 10 climate models put it between 0.10 and 0.90 °C cooler. {AGREE}",
        "So in a typical month the hottest day would be about that much cooler; the year's single hottest day is not "
        "projected here.")]


def test_rain_models_agree_and_a_whole_number_per_100_mm():
    p, r = cm6(9.0, 2.0, 16.0, disagree=False)
    assert scenario_lines("precip", p, r) == [nb(s) for s in (
        f"Around 2050, climate models put a year's rain here about 9.0% more than in 1995 to 2014, on {PATH}.",
        f"8 in 10 climate models put it between 2% and 16% more rain. {AGREE}",
        "For every 100 mm of rain a usual year brought here in 1995 to 2014, a year around 2050 would bring about "
        "109 mm.")]


def test_rain_less():
    p, r = cm6(-5.2, -12.0, -1.0, disagree=False)
    lines = scenario_lines("precip", p, r)
    assert lines[0] == f"Around 2050, climate models put a year's rain here about 5.2% less than in 1995 to 2014, on {PATH}."
    assert lines[1] == f"8 in 10 climate models put it between 1% and 12% less rain. {AGREE}"
    assert lines[2].endswith(f"would bring about 95{NB}mm.")


def test_rain_disagree_with_an_end_at_zero():
    p, r = cm6(4.0, 0.0, 8.0, disagree=True)
    assert scenario_lines("precip", p, r)[1] == (
        "The models disagree on wetter or drier: 8 in 10 of them put it between no change and 8.0% more rain.")


def test_cmip6_value_of_zero_drops_line_3():
    p, r = cm6(0.0, -0.4, 0.4)
    assert scenario_lines("air_temp", p, r) == [nb(s) for s in (
        f"Around 2050, climate models put the average year here about the same as in 1995 to 2014, on {PATH}.",
        f"8 in 10 climate models put it between 0.40 °C cooler and 0.40 °C warmer. {AGREE}")]  # sig2: 2 figures


def test_cmip6_null_value_is_one_line():
    p, r = cm6(None, None, None)
    assert scenario_lines("air_temp", p, r) == [f"Around 2050, the climate models have no value here on {PATH}."]


def test_cmip6_windows_change_only_the_year_words():
    t = trend("princeton_air_temp")
    p, r = t["projection"], row(t, "ssp245")
    lines = {y: scenario_lines("air_temp", p, r, y) for y in (2030, 2050, 2090)}
    assert lines[2030][0].startswith("Around 2030, climate models put the average year here about ")
    assert lines[2090][0].startswith("Around 2090, ")
    for y in (2030, 2090):  # the same words with the year swapped, numbers aside
        assert re.sub(r"\d+(\.\d+)?", "N", " ".join(lines[y])) == re.sub(r"\d+(\.\d+)?", "N", " ".join(lines[2050]))
    t = trend("chennai_rain")
    assert "a year around 2030 would bring" in scenario_lines("precip", t["projection"], row(t, "ssp245"), 2030)[2]
    with pytest.raises(ValueError):
        scenario_lines("precip", t["projection"], row(t, "ssp245"), 2040)


# ---- check.text ----

def test_check_text():
    base = {"observed_2019_2021": 29, "ar6_2020_p05": 41, "ar6_2020_p95": 168, "kind": "2019-2021", "latest": None}
    assert check_text({**base, "inside": False}) == (
        "Measured levels here are already below the experts' range for recent years.")
    assert check_text({**base, "observed_2019_2021": 200, "inside": False}) == (
        "Measured levels here are already above the experts' range for recent years.")
    latest = {**base, "observed_2019_2021": None, "kind": "latest 12 months", "inside": False,
              "latest": {"value": 190, "year": 2024.5, "ar6_p05": 50, "ar6_p95": 180}}
    assert check_text(latest).startswith("Measured levels here are already above")
    assert check_text({**base, "inside": True}) is None and check_text({**base, "inside": None}) is None
    assert check_text(None) is None


# ---- wired into compute_trend ----

@pytest.mark.parametrize("name", ["battery_sea_level", "chennai_rain", "grace_water_storage"])
def test_compute_trend_writes_every_line(name):
    s = {k: v for k, v in json.loads((RW / f"{name}.json").read_text())["series"].items() if k != "anomaly"}
    r = compute_trend(s)
    keys = list(r)
    assert keys[keys.index("meaning") + 1] == "plain" and r["plain"] == plain_lines(r)
    p = r["projection"]
    if p["available"]:
        assert all(x["plain"] == scenario_lines(r["variable"], p, x) for x in p["scenarios"])
        assert r["plain"] == row(r, p["default_scenario"])["plain"]
    if name == "battery_sea_level":
        assert p["check"]["inside"] is False and p["check"]["text"] == check_text(p["check"]) is not None
    if name == "grace_water_storage":
        assert r["plain"][0] == p["why"] and len(r["plain"]) == 3


# ---- properties over every fixture, scenario and year ----

def every_line():
    for name in CASES:
        t = trend(name)
        p = t["projection"]
        if not p.get("available"):
            continue
        years = p["years"] if t["variable"] == "sea_level" else [w["mid"] for w in p["windows"]]
        for r in p["scenarios"]:
            for y in years:
                yield t, p, r, y, scenario_lines(t["variable"], p, r, y)


def test_spoken_form_no_dashes_brackets_or_signs():
    n = 0
    for t, p, r, y, lines in every_line():
        for line in lines:
            n += 1
            assert not re.search(r"[–—()\[\]+−]|\d-|-\d", line), line
            assert not re.search(r"\d (cm|mm|°C)", line), line  # a no-break space before every unit
    assert n > 300


def _rounds(n: str, x) -> bool:
    """n (as printed) is x rounded to n's last shown place (a whole number's trailing zeros may be rounding: 110)."""
    exp = -len(n.split(".")[1]) if "." in n else len(n) - len(n.rstrip("0"))
    return abs(Decimal(n) - abs(Decimal(repr(float(x))))) <= Decimal("0.5").scaleb(exp)


def test_every_number_is_from_the_projection():
    """Invented numbers: each number is the baseline's or the asked year's, a fixed "2 in 3" / "8 in 10" / "100", or
    a field of this row at this year rounded (sea level mm shown in cm); rain's "about 111 mm" is 100 plus its p50."""
    for t, p, r, y, lines in every_line():
        sea_level = t["variable"] == "sea_level"
        i = p["years"].index(y) if sea_level else [w["mid"] for w in p["windows"]].index(y)
        keys = ("p05", "p17", "p50", "p83", "p95") if sea_level else ("p10", "p50", "p90")
        fields = [r[k][i] / 10 if sea_level else r[k][i] for k in keys if r[k][i] is not None]
        fields += [r["rate"][k][i] for k in keys if sea_level and r["rate"][k][i] is not None]
        for line in lines:
            text = re.sub(r"\b(2 in 3|8 in 10)\b", "", line)
            for n in re.findall(r"\d+(?:\.\d+)?", text):
                if n in ("1995", "2014", str(y), "100"):
                    continue
                per_100 = f"would bring about {n}" in line
                assert any(_rounds(str(abs(Decimal(n) - 100)) if per_100 else n, x) for x in fields), (n, line)


def test_cmip6_lines_never_give_a_chance():
    for t, p, r, y, lines in every_line():
        text = " ".join(lines)
        if t["variable"] == "sea_level":
            assert ("2 in 3 chance" in text) == (r["confidence"] == "medium") or r["p50"][p["years"].index(y)] is None
            continue
        # "likely" only in the fixed sentence that says the range is not a likelihood
        assert not re.search(r"chance|odds|likely", text.replace(AGREE, "")), text
