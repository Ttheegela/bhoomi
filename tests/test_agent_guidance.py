"""The tool's guidance put in by code and the gave-up fix. Offline: no LLM, no network."""
import json

import pytest

from evals import run
from earthtrends.agent import guidance, loop, providers, resources, tools

FACT = "Rising about 2.4 times as fast as the world average (1993 to April 2025; 95% range 2.1 to 2.7 times)."
FEMA = {"label": "Official flood maps (FEMA Flood Map Service Center)", "url": "https://msc.fema.gov/portal/home"}
PLANNING = {"label": "Your local planning office", "url": None}
DISCLAIMER = "This shows past measurements only. It is not a prediction and not professional advice."
GUIDE = {"fact": FACT, "ratio": 2.4,
         "reference": {"text": "World average", "source": {"name": "Ref", "url": "https://example.org/ref"}},
         "rate": {"value": 8.3, "unit": "mm", "text": "+8.3 mm", "per": "a year", "note": None},
         "display": {"unit": "cm", "factor": 0.1}, "look_next": [FEMA, PLANNING],
         "future_link": {"label": "Future flood map (NOAA)", "url": "https://coast.noaa.gov/slr/"},
         "disclaimer": DISCLAIMER}
SRC = {"id": "coops", "name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/"}
GI = {"variable": "sea_level", "units": "mm", "place": {"name": "Grand Isle", "lat": 29.26, "lon": -89.96},
      "period": {"start": "1947-01", "end": "2026-09"}, "verdict": "rising", "slope_per_decade": 83.0,
      "ci_low": 80.0, "ci_high": 86.0, "p_value": 0.0001, "source": SRC, "caveats": [],
      "meaning": {"headline": "The sea here has clearly been rising.", "confidence": "Very clear",
                  "comparison": "About 8 cm higher every 10 years.", "limit": "It cannot tell the future."},
      "guidance": GUIDE}
GI_ARGS = {"variable": "sea_level", "lat": 29.26, "lon": -89.96}
SOURCES = "All our data sources, with licences: bhoomi.earth/sources"  # design 17 §8: first answer or when asked
EXPECT = (f"Sea level: {FACT} Where to look next: Official flood maps (FEMA Flood Map Service Center) "
          "(https://msc.fema.gov/portal/home); Your local planning office. Future flood map (NOAA) "
          f"(https://coast.noaa.gov/slr/). {DISCLAIMER}")


def ok(result, args):
    return {"name": "detect_trend", "arguments": args, "result": result, "error": None}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "AGENT_MODEL"):
        monkeypatch.delenv(k, raising=False)


# ---- guidance strings, word for word ----

def test_block_is_the_tools_strings_word_for_word():
    assert guidance.block([ok(GI, GI_ARGS)]) == EXPECT
    for s in (GUIDE["fact"], GUIDE["disclaimer"], FEMA["label"], FEMA["url"], PLANNING["label"]):
        assert s in EXPECT
    assert guidance.SOURCES_LINE == SOURCES and loop.stated_numbers(SOURCES) == []  # no number: outside every check
    # simple words: the same block without the fact
    assert guidance.block([ok(GI, GI_ARGS)], simple=True) == EXPECT.replace(f"Sea level: {FACT} ", "")
    # an old result that still carries a past-trend outlook adds nothing about the future (spec D1)
    old = {**GUIDE, "outlook_label": "If the past trend continues",
           "outlook": [{"year": 2050, "low": 18.2, "high": 21.4, "unit": "cm", "text": "+18 to +21 cm by 2050"}]}
    assert guidance.block([ok({**GI, "guidance": old}, GI_ARGS)]) == EXPECT


def test_hottest_day_adds_its_fact():
    fact = "No clear change (1981 to 2025; 95% range −0.02 to +0.27 °C per decade)."
    flat = {**GUIDE, "fact": fact, "ratio": None, "reference": None, "future_link": None,
            "look_next": [{"label": "Your national weather service", "url": None}]}
    hot = {**GI, "variable": "air_temp_max", "units": "degC", "guidance": flat}
    assert guidance.block([ok(hot, {**GI_ARGS, "variable": "air_temp_max"})]) == (
        f"Hottest day of the month: {fact} Where to look next: Your national weather service. {DISCLAIMER}")
    assert guidance.block([ok({**hot, "guidance": {**flat, "fact": ""}}, GI_ARGS)]) == ""  # no fact: nothing


@pytest.mark.parametrize("text,want", [
    ("Rising. [GUIDANCE] [OFFICIAL RESOURCES]", f"Rising. {EXPECT} [OFFICIAL RESOURCES]"),
    ("Rising.\n[GUIDANCE]", f"Rising.\n{EXPECT}"),
    ("Rising. [OFFICIAL RESOURCES]", f"Rising.\n\n{EXPECT} [OFFICIAL RESOURCES]"),  # no marker: before the links
    ("Rising.", f"Rising.\n\n{EXPECT}"),  # no marker at all: at the end
    ("A. [GUIDANCE] B. [guidance]", f"A. {EXPECT} B."),  # once
])
def test_fill(text, want):
    assert guidance.fill(text, [ok(GI, GI_ARGS)]) == want




def test_result_without_guidance_is_unchanged():
    plain = {k: v for k, v in GI.items() if k != "guidance"}
    assert guidance.fill("Rising.", [ok(plain, GI_ARGS)]) == "Rising."
    assert guidance.fill("Rising. [GUIDANCE]", [ok(plain, GI_ARGS)]) == "Rising."


def test_two_places_are_named_and_the_disclaimer_and_look_next_come_once():
    other = "Rising about 1.3 times as fast as the world average (1993 to April 2025; 95% range 1.1 to 1.5 times)."
    ac = {**GI, "place": {"name": "Atlantic City", "lat": 39.36, "lon": -74.42}, "guidance": {**GUIDE, "fact": other}}
    out = guidance.block([ok(GI, GI_ARGS), ok(ac, {**GI_ARGS, "lat": 39.36, "lon": -74.42})])
    assert out.startswith(f"Grand Isle, sea level: {FACT} Atlantic City, sea level: {other} Where to look next: ")
    assert out.count(GUIDE["disclaimer"]) == 1 and out.count("coast.noaa.gov/slr") == 1
    assert out.count(FEMA["url"]) == 1 and out.count(PLANNING["label"]) == 1 and out.endswith(DISCLAIMER)


def test_sources_at_one_place_that_disagree_are_both_shown():
    flat = "No clear change (1947 to 2026)."
    psmsl = {**GI, "source": {"id": "psmsl", "name": "PSMSL, RLR", "url": "https://psmsl.org/"},
             "verdict": "no_clear_change", "guidance": {**GUIDE, "fact": flat, "look_next": [PLANNING]}}
    out = guidance.block([ok(psmsl, {**GI_ARGS, "source": "psmsl"}), ok(GI, {**GI_ARGS, "source": "coops"})])
    assert out.index(f"(NOAA CO-OPS tide gauges): {FACT}") < out.index(f"(PSMSL): {flat}")
    same = guidance.block([ok(GI, GI_ARGS), ok({**GI, "source": psmsl["source"]}, GI_ARGS)])
    assert same == EXPECT  # agreeing sources: one entry, the catalog default's


# ---- the scorer accepts guidance numbers ----

def test_scorer_accepts_inserted_guidance_numbers_and_link():
    case = {"id": "gi", "question": "q", "expect_tool": "detect_trend",
            "must_say": ["times as fast as the world average", "msc.fema.gov", "not professional advice"],
            "must_not_say": ["High risk", "advise against", "recommend"]}
    answer = guidance.fill("Yes. Sea level at Grand Isle has clearly been rising. Source: NOAA CO-OPS tide gauges, "
                           "https://tidesandcurrents.noaa.gov/.", [ok(GI, GI_ARGS)])
    out = run.check(case, {"answer": answer, "tool_calls": [ok(GI, GI_ARGS)]})
    # the fact's world window (1993 to April 2025) is the tool's own words, not a wrong period
    assert out["numbers"] and out["links"] and out["must_say"] and out["wording"], out


def test_the_number_check_pools_the_facts_numbers():
    """The fact's ratio range is in no other field the model reads (world is cut to its text), so the pool takes it
    from the fact: an answer may quote it, and a range of its own still fails."""
    res = loop.model_results([ok({**GI, "world": {"text": "x", "ratio_low": 2.1}}, GI_ARGS)])
    assert "ratio_low" not in json.dumps(res)
    said = "It rose about 2.4 times as fast as the world average (95% range 2.1 to 2.7 times)."
    assert loop.invented_numbers(said, res) == []
    assert loop.invented_numbers(said.replace("2.7", "3.9"), res) == ["3.9"]


# ---- through the loop ----

@pytest.fixture
def fake(monkeypatch):
    class Fake:
        script, results, starts = [], [], []

        def __init__(self, model):
            pass

        def start(self, system, question, tools, history=()):
            Fake.starts.append((question, tools))

        def step(self):
            return Fake.script.pop(0)

        def add_tool_results(self, results):
            Fake.results.append(results)

    monkeypatch.setitem(providers.PROVIDERS, "fake", Fake)
    return Fake


def step(text=None, calls=()):
    return {"text": text, "tool_calls": list(calls), "usage": {"prompt_tokens": 1, "completion_tokens": 1,
                                                               "cost_usd": 0.0}}


def call(id, **args):
    return {"id": id, "name": "detect_trend", "arguments": args, "arguments_error": None}


def test_loop_inserts_guidance_outside_the_word_limit(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: GI)
    body = " ".join(["word"] * 100) + "."
    fake.script = [step(calls=[call("a", **GI_ARGS)]), step(body + " [GUIDANCE] [OFFICIAL RESOURCES]")]
    r = loop.ask("Should I invest in a house in Grand Isle?", model="fake:m")
    # the missing source link goes in front of the markers; the guidance and the official resources follow, and
    # the sources pages line (a first answer) is the very last line
    assert r["answer"] == f"{body} Source: NOAA CO-OPS tide gauges, {SRC['url']}. {EXPECT} {resources.US_COAST}\n{SOURCES}"
    assert fake.script == []  # 100 words + code's text: no length retry
    # FEMA's flood maps once, in "Where to look next"; the official-resources sentence doesn't repeat them
    assert r["answer"].count("msc.fema.gov") == 1 and r["answer"].index("msc.fema.gov") < r["answer"].index(resources.US_COAST)


def test_results_but_no_answer_is_never_the_give_up(fake, monkeypatch):
    """The Atlantic City bug: one call per source for five measurements is more than a step runs, the model keeps
    asking for tools until the call cap, and the loop used to return GAVE_UP over good results."""
    def detect(variable, lat, lon, source=None, **kw):
        if variable == "water_storage":
            raise ValueError("No GRACE data at 1234 km.")
        return {**GI, "variable": variable, "units": "degC" if variable != "sea_level" else "mm", "guidance": None,
                "place": {"name": "Atlantic City"}, "source": loop.SOURCES[source or "coops"],
                "meaning": {"headline": "It has clearly been rising."}}
    monkeypatch.setattr(tools, "detect_trend", detect)
    fan = [call(f"{v}{s}", variable=v, lat=39.36, lon=-74.42, source=s) for v, srcs in
           (("sea_level", ("coops", "psmsl")), ("air_temp", ("power", "era5", "ghcn")),
            ("air_temp_max", ("power", "era5", "ghcn")), ("precip", ("power", "era5", "ghcn")),
            ("water_storage", ("grace",))) for s in srcs]
    fake.script = [step(calls=fan[i:i + 6]) for i in range(0, 12, 6)] + [step(calls=fan[-1:])] * 4
    r = loop.ask("Atlantic City: sea level, heat, rain, water storage?", model="fake:m")
    a = r["answer"]
    assert a != loop.GAVE_UP and a.startswith(loop.FOUND_HEAD)
    assert "Sea level at Atlantic City: It has clearly been rising. Rate 83.00 mm per decade (95% range 80.00 to 86.00)" in a
    assert "Air temperature at Atlantic City" in a and "83.00 °C" in a
    assert a.splitlines()[-1] == "I could not look up: land water storage at Atlantic City."
    case = {"id": "x", "question": "q", "expect_tool": "detect_trend", "must_say": ["sea level", "temperature"]}
    checks = run.check(case, r)
    assert checks["answered"] and checks["numbers"] and checks["must_say"] and checks["wording"], checks


AC_ARGS = {"variable": "sea_level", "lat": 39.36, "lon": -74.42}
AC_TEMP = {**GI, "variable": "air_temp", "units": "degC", "place": {"name": "Atlantic City"}, "guidance": None,
           "source": loop.SOURCES["power"]}


def failed(args):
    return {"name": "detect_trend", "arguments": args, "result": None, "error": "No tide gauge near here."}


def test_found_answer_names_each_missing_place_and_measurement():
    calls = [ok(GI, GI_ARGS), failed(AC_ARGS), ok(AC_TEMP, {**AC_ARGS, "variable": "air_temp"}),
             failed({**AC_ARGS, "lat": 10.0, "lon": 10.0}),  # no result anywhere at this point: no name
             failed({**AC_ARGS, "variable": "sea level 2"})]  # not a catalog id: never echoed
    a = loop.found_answer(calls)
    assert a.splitlines()[-1] == "I could not look up: sea level at Atlantic City, sea level at another place."
    assert "sea level 2" not in a and "Sea level at Grand Isle" in a


def test_found_answer_without_headline_says_the_verdict():
    flat = {**GI, "verdict": "no_clear_change", "meaning": {}, "slope_per_decade": 1.0, "ci_low": -2.0}
    a = loop.found_answer([ok(flat, GI_ARGS)])
    assert "Sea level at Grand Isle: No clear change. Rate 1.00 mm per decade (95% range -2.00 to 86.00)" in a
    up = loop.found_answer([ok({**GI, "meaning": None}, GI_ARGS)])
    assert "Sea level at Grand Isle: Clearly rising. Rate" in up
    assert "I could not look up" not in up


def test_no_results_still_gives_up(fake, monkeypatch):
    def none(**kw):
        raise ValueError("No tide gauge near here.")
    monkeypatch.setattr(tools, "detect_trend", none)
    fake.script = [step(calls=[call(str(i), variable="sea_level", lat=1, lon=2)]) for i in range(10)]
    assert loop.ask("q", model="fake:m")["answer"] == loop.GAVE_UP


# ---- "These are examples, not a ranking." put in by code ----

TOKYO = {"name": "detect_trend", "arguments": {"variable": "sea_level", "lat": 35.65, "lon": 139.77}}
MANILA = {"name": "detect_trend", "arguments": {"variable": "sea_level", "lat": 14.58, "lon": 120.97}}


@pytest.mark.parametrize("opener", ["I cannot rank a whole region from past data at single places.",
                                    "I can't rank a whole region from past data at single places.",
                                    "I can’t rank a whole region from past data at single places."])
def test_cannot_rank_answer_gets_the_sentence_once(opener):
    text = f"{opener}\n\nTokyo: rising.\n\nManila: rising."
    out = loop.add_examples(text, [TOKYO, MANILA])
    assert out == f"{opener} {loop.EXAMPLES}\n\nTokyo: rising.\n\nManila: rising."


@pytest.mark.parametrize("text", ["New York and Seattle: both rising. Source: NOAA.",
                                  "I can't rank which home is safer from this data. Both coasts are rising."])
def test_two_places_without_the_broad_opener_unchanged(text):
    assert loop.add_examples(text, [TOKYO, MANILA]) == text


def test_sentence_goes_right_after_the_opener_and_the_marker_stays_last():
    text = ("I cannot rank a whole region from past data at single places. Tokyo: rising. Manila: rising. "
            "[OFFICIAL RESOURCES]")
    out = loop.add_examples(text, [TOKYO, MANILA])
    assert out == ("I cannot rank a whole region from past data at single places. These are examples, not a "
                   "ranking. Tokyo: rising. Manila: rising. [OFFICIAL RESOURCES]")
    assert out.endswith("[OFFICIAL RESOURCES]")


def test_opener_in_the_second_paragraph():
    text = ("Sea level is rising in many places.\n\nI can't rank a whole region from 9.36 years of data alone. "
            "Tokyo: rising.")
    out = loop.add_examples(text, [TOKYO, MANILA])
    assert out == ("Sea level is rising in many places.\n\nI can't rank a whole region from 9.36 years of data alone. "
                   "These are examples, not a ranking. Tokyo: rising.")


def test_opener_with_no_sentence_end_goes_at_the_end():
    assert loop.add_examples("I can't rank a whole region", [TOKYO, MANILA]) == (
        "I can't rank a whole region These are examples, not a ranking.")


def test_not_a_ranking_already_there_is_not_doubled():
    text = "I can't rank a whole region. These are examples I chose, not a ranking. Tokyo: rising."
    assert loop.add_examples(text, [TOKYO, MANILA]) == text


def test_one_place_unchanged():
    one = [TOKYO, {**TOKYO, "arguments": {**TOKYO["arguments"], "lat": 35.66, "source": "psmsl"}}]  # same city
    text = "I can't rank a whole region. Tokyo: rising."
    assert loop.add_examples(text, one) == text


def test_loop_adds_examples_sentence(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: {**GI, "guidance": None})
    fake.script = [step(calls=[call("a", **TOKYO["arguments"]), call("b", **MANILA["arguments"])]),
                   step("I can't rank a whole region from past data at single places.\n\nTokyo and Manila: rising.")]
    assert loop.ask("Which Asian cities?", model="fake:m")["answer"].count(loop.EXAMPLES) == 1


# ---- a tool call written out as text is never the answer ----

LEAK = ("I'll run the three checks again instead of reusing the earlier results, since only fresh tool results can "
        "support this answer.\n\ndetect_trend\n"
        '{"variable": "air_temp_max", "lat": 28.61, "lon": 77.21, "source": "power"}')


def _clean(answer):
    return "detect_trend" not in answer and '{"variable"' not in answer


def test_leak_on_the_retry_returns_the_earlier_complete_answer(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: {**GI, "guidance": None})
    long = " ".join(["word"] * 130) + "."
    fake.script = [step(calls=[call("a", **GI_ARGS)]), step(long), step(LEAK)]
    r = loop.ask("Is sea level rising at Grand Isle?", model="fake:m")
    assert r["answer"] == loop.best([loop.compose(long, r["tool_calls"])], r["tool_calls"]) and _clean(r["answer"])
    assert fake.script == []  # the leak was the retry's reply


def test_leak_as_first_text_returns_the_found_answer(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: {**GI, "guidance": None})
    fake.script = [step(calls=[call("a", **GI_ARGS)]), step(LEAK)]
    r = loop.ask("Is sea level rising at Grand Isle?", model="fake:m")
    assert r["answer"] == loop.found_answer(r["tool_calls"]) and _clean(r["answer"])


def test_leak_with_no_results_gives_up(fake):
    fake.script = [step(LEAK), step(LEAK)]  # the one restart leaks again
    assert loop.ask("Is sea level rising at Grand Isle?", model="fake:m")["answer"] == loop.GAVE_UP
    assert fake.script == []  # two model calls: the first answer and the one restart, no third


@pytest.mark.parametrize("text", [LEAK, 'detect_trend({"variable": "air_temp_max", "lat": 28.61, "lon": 77.21})',
                                  'detect_trend(variable="air_temp_max", lat=28.61, lon=77.21)',
                                  "Calling `detect_trend`: {'variable': 'precip'}", "list_variables()"])
def test_written_out_tool_calls_match(text):
    assert loop.TOOL_NAME.search(text)


@pytest.mark.parametrize("text", ["I use a tool called detect_trend to check the records.",
                                  "detect_trend (the trend check) looks at all months together.",
                                  "The list_variables tool lists what we measure."])
def test_mentions_do_not_match(text):
    assert not loop.TOOL_NAME.search(text)


def test_answer_that_mentions_a_tool_is_returned(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: {**GI, "guidance": None})
    text = (f"I use a tool called detect_trend to check this. Sea level at Grand Isle has clearly been rising. "
            f"Source: NOAA CO-OPS tide gauges, {SRC['url']}.")
    fake.script = [step(calls=[call("a", **GI_ARGS)]), step(text)]
    assert loop.ask("Is sea level rising at Grand Isle?", model="fake:m")["answer"] == text


def test_leak_before_any_call_restarts_once_with_tools(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: {**GI, "guidance": None})
    text = f"Yes. Sea level at Grand Isle has clearly been rising. Source: NOAA CO-OPS tide gauges, {SRC['url']}."
    fake.script = [step(LEAK), step(calls=[call("a", **GI_ARGS)]), step(text)]
    r = loop.ask("Is sea level rising at Grand Isle?", model="fake:m")
    assert r["answer"] == text and len(r["tool_calls"]) == 1 and fake.script == []


def test_normal_answer_is_untouched(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: {**GI, "guidance": None})
    text = f"Yes. Sea level at Grand Isle has clearly been rising. Source: NOAA CO-OPS tide gauges, {SRC['url']}."
    fake.script = [step(calls=[call("a", **GI_ARGS)]), step(text)]
    assert loop.ask("Is sea level rising at Grand Isle?", model="fake:m")["answer"] == text


# ---- with results, every number must be one of theirs ----

POWER = {"id": "power", "name": "NASA POWER", "url": "https://power.larc.nasa.gov/"}
FLAT = {"variable": "air_temp_max", "units": "degC", "place": {"name": "Delhi"}, "verdict": "no_clear_change",
        "slope_per_decade": 0.125, "ci_low": -0.0151, "ci_high": 0.266, "p_value": 0.08,
        "period": {"start": "1981-01", "end": "2025-12"}, "source": POWER, "caveats": [],
        "meaning": {"headline": "The hottest days here show no clear change.", "confidence": "Not clear",
                    "comparison": "", "limit": "It cannot tell the future."}}
DELHI = {"variable": "air_temp_max", "lat": 28.61, "lon": 77.21}
WRONG_SIGN = ("No clear change: -0.13 °C per decade (95% range -0.02 to 0.27). "
              "Source: NASA POWER, https://power.larc.nasa.gov/.")
RIGHT_SIGN = WRONG_SIGN.replace("-0.13", "0.13")


def test_wrong_sign_gets_one_retry_naming_the_number(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: FLAT)
    fake.script = [step(calls=[call("a", **DELHI)]), step(WRONG_SIGN), step(RIGHT_SIGN)]
    r = loop.ask("Are Delhi's hottest days getting hotter?", model="fake:m")
    assert r["answer"] == RIGHT_SIGN and fake.script == []
    retry, offered = fake.starts[-1]
    assert loop.INVENTED_ASK.format(numbers="-0.13") in retry and offered == []  # no tools on the retry


def test_wrong_twice_gives_the_found_answer(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: FLAT)
    fake.script = [step(calls=[call("a", **DELHI)]), step(WRONG_SIGN), step(WRONG_SIGN)]
    r = loop.ask("Are Delhi's hottest days getting hotter?", model="fake:m")
    assert r["answer"] == loop.found_answer(r["tool_calls"]) and "-0.13" not in r["answer"]
    assert loop.invented_numbers(r["answer"], loop.model_results(r["tool_calls"])) == []


def test_right_numbers_pass_with_no_retry(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: FLAT)
    fake.script = [step(calls=[call("a", **DELHI)]), step(RIGHT_SIGN), step("never")]
    r = loop.ask("Are Delhi's hottest days getting hotter?", model="fake:m")
    assert r["answer"] == RIGHT_SIGN and len(fake.script) == 1


def test_direction_word_drops_the_slope_sign_but_not_a_range_end():
    falling = {**FLAT, "verdict": "falling", "slope_per_decade": -0.2512, "ci_low": -0.41, "ci_high": -0.09}
    res = loop.model_results([{"name": "detect_trend", "arguments": DELHI, "result": falling, "error": None}])
    assert loop.invented_numbers("Clearly falling by 0.25 °C per decade (95% range -0.41 to -0.09).", res) == []
    assert loop.invented_numbers("Clearly falling by 0.25 °C per decade (95% range 0.41 to -0.09).", res) == ["0.41"]


def test_a_number_in_the_question_does_not_make_it_pass(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: FLAT)
    fake.script = [step(calls=[call("a", **DELHI)]), step(WRONG_SIGN), step(RIGHT_SIGN)]
    r = loop.ask("Is it true Delhi's hottest days changed by -0.13 °C per decade?", model="fake:m")
    assert r["answer"] == RIGHT_SIGN and fake.script == []  # the retry was taken


def test_a_year_repeated_from_the_question_is_retried(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: FLAT)
    text = RIGHT_SIGN + " Past records cannot say what happens by 2050."
    fake.script = [step(calls=[call("a", **DELHI)]), step(text), step(RIGHT_SIGN)]
    r = loop.ask("Will Delhi's hottest days be worse by 2050?", model="fake:m")
    assert r["answer"] == RIGHT_SIGN and loop.INVENTED_ASK.format(numbers="2050") in fake.starts[-1][0]


def test_only_real_periods_are_left_to_the_period_check():
    res = loop.model_results([{"name": "detect_trend", "arguments": DELHI, "result": FLAT, "error": None}])
    made_up = "No clear change (95% range 1650 to 2010)."
    assert loop.invented_numbers(loop.without_periods(made_up), res) == ["1650", "2010"]
    real = "No clear change, January 1981 to December 2025."
    assert loop.without_periods(real) != real and loop.invented_numbers(loop.without_periods(real), res) == []


def test_wrong_number_long_answer_is_not_kept(fake, monkeypatch):
    monkeypatch.setattr(tools, "detect_trend", lambda **kw: FLAT)
    long = WRONG_SIGN + " " + " ".join(["word"] * 130) + "."
    fake.script = [step(calls=[call("a", **DELHI)]), step(long), step(LEAK)]
    r = loop.ask("Are Delhi's hottest days getting hotter?", model="fake:m")
    assert r["answer"] == loop.found_answer(r["tool_calls"]) and "-0.13" not in r["answer"]


def test_scorer_uses_the_loops_number_check():
    assert run.invented_numbers is loop.invented_numbers and run._pool is loop._pool


# ---- the model reads, and the number check pools, only the fields the prompt uses ----

def test_rework_fields_stay_out_of_the_model_view_and_the_number_check(monkeypatch):
    """ERA5 is air temperature's main record (PR4a): Princeton's recorded ERA5 series, with NASA POWER beside it (the
    station can't be read offline). Numbers only the page uses (fit.change, the July normal) stay out of the view."""
    import json
    from pathlib import Path

    from earthtrends.data import era5, power
    fixtures = Path(__file__).parent / "fixtures"
    monkeypatch.setenv(era5.REPLAY, str(fixtures / "era5_replay"))
    fx = json.loads((fixtures / "power_monthly.json").read_text())
    monkeypatch.setattr(power, "fetch", lambda p, la, lo: fx)
    args = {"variable": "air_temp", "lat": 40.35, "lon": -74.66}
    full = tools.detect_trend(**args)
    assert full["source"]["id"] == "era5" and full["main_note"] is None
    assert [c["label"] for c in full["comparisons"]] == ["ERA5", "NASA POWER", "Weather station"]
    leaks = (f"It could warm another {full['fit']['change']:.2f} °C by mid-century.",  # fit.change
             f"July is about {full['baseline']['months'][6]:.1f} °C.")  # baseline.months
    calls = [ok(full, args)]
    view = loop.for_model(calls)[0]["result"]
    assert loop.model_results(calls) == [view]  # one view for the model and for the check (the scorer's too)
    assert set(view) <= set(loop.MODEL_FIELDS) and not {"fit", "explain", "record", "latest"} & set(view)
    assert view["baseline"] == {"text": full["baseline"]["text"]} and view["world"] == {"text": full["world"]["text"]}
    assert set(view["source"]) == {"id", "name", "url"} and view["headline_rate"] == full["headline_rate"]
    assert all(set(row) == {"label", "where", "years", "verdict", "note", "rate"} for row in view["comparisons"])
    assert all(not loop.invented_numbers(t, [full]) for t in leaks)  # the whole result would let them through
    res = loop.model_results(calls)
    for text in leaks:
        assert loop.invented_numbers(loop.without_periods(text), res), text
    h = full["headline_rate"]
    good = (f"It has clearly been getting warmer here: {h['text']} (95% range {h['range_text']}), January 1981 to "
            f"December 2025. {full['world']['text']} {' '.join(full['plain'])}")
    assert loop.invented_numbers(loop.without_periods(good), res) == []
