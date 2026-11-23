"""The "In plain words" box (web/design/16-plain-language.md §3, §7, §9; rework PR6). The real explain.js and app.js run
in node on the rework fixtures: the box prints the chosen scenario's `plain` lines as the server wrote them, takes R3's
place on the card, swaps its lines in place for a new scenario, and reads the same whichever record is main."""
import os
import re
import shutil
import subprocess

import pytest

from test_explain_js import PURE, ROOT, SRC
from test_records_js import APP, APP_DOM

FIX = str(ROOT / "tests" / "fixtures" / "rework")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

# the tests choose the scenario as the chart's radios and low-confidence box would (SEL is private to explain.js)
HOOK = "card: function (t, imp) { return card(t, imp, SEL); },"
assert SRC.count(HOOK) == 1
SRC_SEL = SRC.replace(HOOK, HOOK + " _sel: function (s) { SEL = s; },")


def run(js):
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=dict(os.environ, FIX=FIX), timeout=60)
    assert r.returncode == 0, r.stderr + r.stdout


PURE_TEST = r"""
var assert = require('assert'), fs = require('fs'), path = require('path');
function load(n) { return JSON.parse(fs.readFileSync(path.join(process.env.FIX, n + '.json'), 'utf8')); }
function copy(d) { return JSON.parse(JSON.stringify(d)); }
var NB = ' ', TODAY = 2026 * 12 + 10;
function byId(t, id) { return t.projection.scenarios.filter(function (x) { return x.id === id; })[0]; }
function selOf(S) { return { ssp: S.id.replace(/_(medium|low)$/, ''), low: S.confidence === 'low' }; }
var B = load('battery_sea_level').trend, P = load('princeton_air_temp').trend, C = load('chennai_rain').trend, H = load('delhi_hottest_day').trend;

// the four personas' places: the lines are S.plain, as given, for every scenario and the low-confidence rows
[B, P, C, H].forEach(function (t) {
  assert.deepStrictEqual(card(t, false, null, TODAY).plain.lines, t.plain); // the default scenario's lines are the top-level plain
  assert.deepStrictEqual(t.plain, byId(t, t.projection.default_scenario).plain);
  t.projection.scenarios.forEach(function (S) { assert.deepStrictEqual(card(t, false, selOf(S), TODAY).plain.lines, S.plain, S.id); });
});
assert.strictEqual(card(B, false, null, TODAY).plain.lines[0], 'By 2050, experts project the sea here about 36' + NB + 'cm higher than its 1995 to 2014 average, on the intermediate emissions path.');
assert.deepStrictEqual(card(B, false, { ssp: 'ssp370', low: true }, TODAY).plain.lines, byId(B, 'ssp370_medium').plain); // High has no low version

// the foot: the projection's own link, S's code, the tail
var CHK = B.projection.check.text, kb = card(B, false, null, TODAY).plain;
assert.ok(/^Measured levels here are already (above|below) the experts' range for recent years\.$/.test(CHK), CHK);
assert.deepStrictEqual([kb.label, kb.href, kb.src, kb.code, kb.tail],
  ['In plain words', B.projection.source.record_url, 'IPCC AR6 sea level projections', 'SSP2-4.5', ', medium confidence · ' + CHK]);
var kl = card(B, false, { ssp: 'ssp585', low: true }, TODAY).plain;
assert.deepStrictEqual([kl.code, kl.tail], ['SSP5-8.5', ', low confidence · ' + CHK]);
var RE = copy(B); RE.projection.location.kind = 'regional estimate';
assert.strictEqual(card(RE, false, null, TODAY).plain.tail, ', medium confidence · Regional estimate: local sinking may differ. · ' + CHK);
RE.projection.check.text = null;
assert.strictEqual(card(RE, false, null, TODAY).plain.tail, ', medium confidence · Regional estimate: local sinking may differ.');
var L = load('lewes_sea_level_short').trend;
assert.ok(L.projection.check.text === null && card(L, false, null, TODAY).plain.tail === ', medium confidence');
var kp = card(P, false, null, TODAY).plain;
assert.deepStrictEqual([kp.href, kp.src, kp.code, kp.tail], [P.projection.source.record_url, 'IPCC AR6 Atlas, CMIP6', 'SSP2-4.5', ', ' + byId(P, 'ssp245').models[1] + ' climate models']);
assert.strictEqual(card(P, false, { ssp: 'ssp370' }, TODAY).plain.tail, ', ' + byId(P, 'ssp370').models[1] + ' climate models');
assert.ok(card(C, false, null, TODAY).plain.tail === ', 32 climate models' && card(H, false, null, TODAY).plain.tail === ', 27 climate models');
var NH = copy(B); NH.projection.source.record_url = 'http://example.org/';
assert.strictEqual(card(NH, false, null, TODAY).plain.href, ''); // not https: plain text, no link

// Units imperial: the label says the lines stay metric; the lines don't change
[B, P].forEach(function (t) { var k = card(t, true, null, TODAY).plain; assert.strictEqual(k.label, 'In plain words (in metric)'); assert.deepStrictEqual(k.lines, t.plain); });

// no projection: no box, R3 keeps `why` (water storage, a record with no 1995-2014 average)
['grace_water_storage', 'riverside_no_baseline'].forEach(function (n) {
  var t = load(n).trend, k = card(t, false, null, TODAY);
  assert.ok(k.plain === null && k.r3f === null && k.r3 === t.projection.why && k.r3.length > 0, n);
});
// an answer cached before PR6 (no plain anywhere), or an empty list: no box, R3 exactly as before
[B, P].forEach(function (t) {
  var o = copy(t); delete o.plain; o.projection.scenarios.forEach(function (S) { delete S.plain; });
  assert.ok(card(o, false, null, TODAY).plain === null);
  assert.deepStrictEqual(card(o, false, null, TODAY).r3f, card(t, false, null, TODAY).r3f);
  var e = copy(t); e.projection.scenarios.forEach(function (S) { S.plain = []; });
  assert.ok(card(e, false, null, TODAY).plain === null);
});

// "more than today" left the card but stays in the chart's readout line (#future-read)
[[B, null], [B, { ssp: 'ssp585', low: false }], [P, null], [P, { ssp: 'ssp585' }]].forEach(function (x) {
  var fx = futOf(x[0], x[1], false, TODAY), r = futRead(x[0], fx, false);
  assert.ok(/ That is about [\d.]+\s(cm|°C) more than today\.$/.test(r.rest), r.rest);
});

// record-free: another main record (its own source, level, verdict, baseline and trend) leaves the box exactly as it was
function other(t, src) {
  var o = copy(t);
  o.source = Object.assign({}, o.source, { id: src, name: src, record_url: 'https://example.org/' + src });
  o.verdict = o.verdict === 'rising' ? 'falling' : 'rising';
  if (o.now) { o.now.value += 0.7; o.now.text = 'changed'; }
  o.baseline = Object.assign({}, o.baseline, { value: 1 });
  o.fit = Object.assign({}, o.fit, { start: 1990, change: 0.1 });
  return o;
}
[[B, ['psmsl']], [P, ['era5', 'ghcn']], [C, ['era5', 'ghcn']], [H, ['era5', 'ghcn']]].forEach(function (x) {
  x[1].forEach(function (src) {
    [null, { ssp: 'ssp585', low: false }, { ssp: 'ssp126', low: true }].forEach(function (sel) {
      assert.deepStrictEqual(card(other(x[0], src), false, sel, TODAY).plain, card(x[0], false, sel, TODAY).plain, src);
    });
  });
});
"""


@needs_node
def test_plain_box_model():
    run(PURE + PURE_TEST)


APP_HEAD = r"""
window.TDX.show = function () {}; window.TDX.others = function () {}; window.TDX.redraw = function () {}; // the chart and the steps: not under test
var NB = ' ';
function settle() { return new Promise(function (r) { (function w() { setTimeout(function () { if (!flight && !queue.length) r(); else w(); }, 10); })(); }); }
function txt(n) { return typeof n === 'string' ? n : n.kids.length ? n.kids.map(txt).join('') : n.textContent || ''; }
function scen(sel) { window.TDX._sel(sel); docOn['td:scen'].forEach(function (f) { f(); }); } // a radio or the low-confidence box
function lines(box) { return box.querySelector('ul').children.map(function (li) { assert.strictEqual(li.tagName, 'LI'); return txt(li); }); }
function byId(t, id) { return t.projection.scenarios.filter(function (x) { return x.id === id; })[0]; }
function r3() { var c = ids['rec'].querySelector('.reads').children, l = txt(c[c.length - 1]); return /^Rate, /.test(l) ? null : l; } // R3, the last readout
"""

BOX_TEST = APP_HEAD + r"""
location.hash = '#sea-level';
FX = load('battery_sea_level');
var T = FX.trend, CHK = T.projection.check.text, SRCU = T.projection.source.record_url;
function series(src) { var s = copy(FX.series); if (src) s.source = Object.assign({}, s.source, { id: src }); return s; }
answer = function (u) {
  var src = u.searchParams.get('source');
  if (u.pathname === '/api/variables') return { status: 200, body: VARS };
  if (u.pathname === '/api/series') return { status: 200, body: series(src) };
  var t = copy(T);
  if (src === 'psmsl') Object.assign(t, { verdict: 'falling', source: { id: 'psmsl', name: 'Permanent Service for Mean Sea Level (PSMSL)', url: 'https://psmsl.org/', record_url: 'https://psmsl.org/data/obtaining/stations/12.php' },
    now: Object.assign({}, t.now, { value: 12, text: '+1.2 cm' }), baseline: Object.assign({}, t.baseline, { value: 7100 }) });
  return { status: 200, body: t };
};
(async function () {
  docOn.DOMContentLoaded[0]();
  await settle();
  var rec = ids['rec'], box = rec.querySelector('.plain'), k = rec.children, at = function (n) { return k.indexOf(n); };
  // after p.world, before the readouts; not a live region
  assert.ok(box && box.tagName === 'SECTION' && box.attrs['aria-labelledby'] === 'pl-h' && !('aria-live' in box.attrs));
  assert.ok(at(box) === at(rec.querySelector('.world')) + 1 && at(rec.querySelector('.reads')) === at(box) + 1);
  var h3 = box.children[0], ul = box.children[1], foot = box.children[2];
  assert.ok(h3.tagName === 'H3' && h3.attrs.id === 'pl-h' && h3.attrs['class'] === 'pl-h' && txt(h3) === 'In plain words');
  assert.ok(ul.tagName === 'UL' && ul.attrs.role === 'list' && foot.tagName === 'P' && foot.attrs['class'] === 'pl-src');
  assert.deepStrictEqual(lines(box), T.plain);
  assert.strictEqual(txt(foot), 'Future: IPCC AR6 sea level projections' + NB + '↗ · SSP2-4.5, medium confidence · ' + CHK);
  var a = foot.children[0], code = foot.children[1];
  assert.ok(a.tagName === 'A' && a.attrs.href === SRCU && a.attrs.target === '_blank' && a.attrs.rel === 'noopener');
  assert.ok(code.attrs['class'] === 'nw' && txt(code) === 'SSP2-4.5');
  // R3 is gone: R1 and R2 only, and nothing of R3's words is left on the card
  var reads = rec.querySelector('.reads');
  assert.ok(reads.children.length === 2 && r3() === null);
  assert.ok(!/By 2050, intermediate|more than today|Likely \+/.test(txt(rec)), txt(rec));

  // a radio or the low-confidence box: the lines and the foot swap in place; the card is not drawn again, focus stays
  var where = rec.querySelector('.where'), radio = new El('button'); document.activeElement = radio;
  [['ssp585', false, 'ssp585_medium'], ['ssp585', true, 'ssp585_low'], ['ssp126', true, 'ssp126_low'], ['ssp370', true, 'ssp370_medium'], ['ssp245', false, 'ssp245_medium']].forEach(function (x) {
    scen({ ssp: x[0], low: x[1] });
    var S = byId(T, x[2]);
    assert.ok(rec.querySelector('.plain') === box && box.querySelector('ul') === ul && rec.querySelector('.reads') === reads && rec.querySelector('.where') === where && box.children[0] === h3, x[2]);
    assert.strictEqual(document.activeElement, radio);
    assert.deepStrictEqual(lines(box), S.plain, x[2]);
    assert.strictEqual(txt(box.querySelector('.pl-src')), 'Future: IPCC AR6 sea level projections' + NB + '↗ · ' + S.code + ', ' + S.confidence + ' confidence · ' + CHK);
  });

  // Units imperial: "(in metric)", the same lines
  var get = window.TDPrefs.get;
  window.TDPrefs.get = function () { return { units: 'imperial', theme: 'light' }; };
  renderRec();
  assert.ok(txt(rec.querySelector('.pl-h')) === 'In plain words (in metric)' && lines(rec.querySelector('.plain')).join('|') === T.plain.join('|'));
  window.TDPrefs.get = get; renderRec();

  // the main record switched (CO-OPS to PSMSL): another answer, the same box text
  var before = txt(rec.querySelector('.plain'));
  pickSource('psmsl'); await settle();
  assert.ok(selectedPin(curWin).trend.source.id === 'psmsl' && selectedPin(curWin).trend.verdict === 'falling');
  assert.strictEqual(txt(rec.querySelector('.plain')), before);
  pickSource('coops'); await settle();
  assert.strictEqual(txt(rec.querySelector('.plain')), before);
  process.exit(0);
})().catch(function (e) { console.error(e); process.exit(1); });
"""


@needs_node
def test_plain_box_on_the_card():
    run(APP_DOM + SRC_SEL + "\n" + APP + BOX_TEST)


CACHED_TEST = APP_HEAD + r"""
location.hash = '#sea-level';
FX = load('battery_sea_level'); delete FX.trend.plain; FX.trend.projection.scenarios.forEach(function (S) { delete S.plain; }); // cached before PR6
answer = function (u) { return { status: 200, body: u.pathname === '/api/variables' ? VARS : u.pathname === '/api/series' ? copy(FX.series) : copy(FX.trend) }; };
(async function () {
  docOn.DOMContentLoaded[0]();
  await settle();
  var rec = ids['rec'], reads = rec.querySelector('.reads');
  assert.ok(rec.querySelector('.plain') === null && /^By 2050, intermediate emissions\+36\scm/.test(r3()), r3());
  scen({ ssp: 'ssp585', low: false }); // no box: the card is drawn again and R3 follows the scenario, as before PR6
  assert.ok(rec.querySelector('.reads') !== reads && /^By 2050, very high emissions/.test(r3()), r3());
  process.exit(0);
})().catch(function (e) { console.error(e); process.exit(1); });
"""


@needs_node
def test_cached_answer_without_plain_keeps_r3():
    run(APP_DOM + SRC_SEL + "\n" + APP + CACHED_TEST)


WHY_TEST = APP_HEAD + r"""
location.hash = '#air-temperature';
FX = load('riverside_no_baseline');
answer = function (u) { return { status: 200, body: u.pathname === '/api/variables' ? VARS : u.pathname === '/api/series' ? copy(FX.series) : copy(FX.trend) }; };
(async function () {
  docOn.DOMContentLoaded[0]();
  await settle();
  assert.ok(ids['rec'].querySelector('.plain') === null && r3() === 'What experts project' + FX.trend.projection.why, r3());
  process.exit(0);
})().catch(function (e) { console.error(e); process.exit(1); });
"""


@needs_node
def test_no_projection_no_box():
    run(APP_DOM + SRC_SEL + "\n" + APP + WHY_TEST)


def test_plain_box_style():
    """Design 16 §3.6, §8: the page fill, radius 8, no border, the given paddings (smaller in a card under 520 px), a 14 px
    --ink-2 label, 16 px ink lines 8 px apart with no bullets, a 14 px --ink-2 foot 10 px below; no new colours."""
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    for rule in (".plain { background: var(--bg); border-radius: 8px; padding: 14px 18px 12px; margin: 0 0 16px; }",
                 ".plain .pl-h { font-family: inherit; font-size: 14px; font-weight: 600; line-height: 1.35; color: var(--ink-2); margin: 0 0 8px; }",
                 ".plain ul { list-style: none; margin: 0; padding: 0; }", ".plain li { font-size: 16px; line-height: 1.45; color: var(--ink); }",
                 ".plain li + li { margin-top: 8px; }", ".plain .pl-src { font-size: 14px; line-height: 1.35; color: var(--ink-2); margin: 10px 0 0; max-width: none; }",
                 ".plain .nw { white-space: nowrap; }", "@container (max-width: 519px) { .plain { padding: 12px 14px 10px; } }"):
        assert rule in css, rule
    assert not re.search(r"\bborder(-(top|bottom|left|right))?:", css.split(".plain {")[1].split("}")[0])
