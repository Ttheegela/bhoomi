"""The map's pure logic (web/map.js, between the PURE markers) run in node, no network: the colour steps, the GRACE file decode,
which gauges are drawn, the hover words, the view moves (web/design/13-maps.md sections 2, 4, 8) and the greyed base map."""
import base64
import json
import pathlib
import shutil
import struct
import subprocess

import pytest

from earthtrends.stats import trend
from earthtrends.stats.meaning import UNITS

ROOT = pathlib.Path(__file__).parent.parent
SRC = (ROOT / "web" / "map.js").read_text(encoding="utf-8")
PURE = SRC.split("/* PURE START")[1].split("*/", 1)[1].split("/* PURE END */")[0]


def i16(values) -> str:
    return base64.b64encode(struct.pack("<%dh" % len(values), *values)).decode()


def u8(values) -> str:
    return base64.b64encode(bytes(values)).decode()


# a tiny grace-trends.json: Delhi falling, Princeton no clear change, one fill, one with a clamped range end
GRACE = {"v": 1, "enc": "i16le-b64", "scale": 0.01, "fill": -32768, "clamp": 32767, "n": 4, "lat_lon_scale": 0.01,
         "lat": i16([2900, 4000, 0, 3800]), "lon": i16([7739, -7527, 0, 14200]), "area": i16([12406, 12392, 100, 12000]),
         "slope": i16([-431, 6, -32768, 1234]), "lo": i16([-476, -15, -32768, -32767]), "hi": i16([-381, 26, -32768, 32767]),
         "sig": u8([2, 0, 255, 0]), "start": "2002-04", "end": "2026-06", "footprint_km": 444,
         "reference": {"years": [2004, 2009]}}

GAUGES = {"source": [{"name": "NOAA CO-OPS tide gauges", "url": "https://tidesandcurrents.noaa.gov/"},
                     {"name": "Permanent Service for Mean Sea Level (PSMSL), RLR monthly means", "url": "https://psmsl.org/"}],
          "gauges": [
              {"id": "8518750", "network": "coops", "name": "The Battery", "lat": 40.7006, "lon": -74.0142, "slope": 2.9, "lo": 2.7,
               "hi": 3.1, "verdict": "rising", "start": "1856-01", "end": "2026-10", "years": 171},
              {"id": "43", "network": "psmsl", "name": "MUMBAI / BOMBAY", "lat": 18.9167, "lon": 72.8333, "slope": 0.8, "lo": 0.6,
               "hi": 1.0, "verdict": "rising", "start": "1878-01", "end": "2025-12", "years": 26},
              {"id": "1", "network": "psmsl", "name": "Okha", "lat": 22.47, "lon": 69.08, "slope": -0.4, "lo": -1.2, "hi": 0.5,
               "verdict": "no_clear_change", "start": "1975-01", "end": "2005-12", "years": 31},
              {"id": "2", "network": "psmsl", "name": "Juneau", "lat": 58.3, "lon": -134.4, "slope": -13.6, "lo": -14.1, "hi": -13.1,
               "verdict": "falling", "start": "1936-01", "end": "2025-12", "years": 90},
              {"id": "3", "network": "coops", "name": "No Rate", "lat": 10.0, "lon": -150.0, "slope": None, "lo": None, "hi": None,
               "verdict": None, "start": "2010-01", "end": "2026-10", "years": 16}],
          "skipped": [
              {"id": "12", "network": "psmsl", "name": "New York (The Battery)", "lat": 40.7, "lon": -74.0133,
               "why": "the answer at this spot uses another gauge: The Battery (NOAA CO-OPS tide gauges)",
               "psmsl_mode": {"slope": 3.04, "lo": 2.86, "hi": 3.21, "verdict": "rising", "start": "1856-01", "end": "2025-12", "years": 170}},
              {"id": "13", "network": "psmsl", "name": "Sandy Hook", "lat": 40.4667, "lon": -74.0, "why":
               "the answer at this spot uses another gauge: Sandy Hook (NOAA CO-OPS tide gauges)"},
              {"id": "99", "network": "psmsl", "name": "Short One", "lat": 1.0, "lon": 1.0, "why": "it has only 13 years of valid data"}]}

CHECK = r"""
var assert = require('assert'), eq = assert.deepStrictEqual, M = '−';
var G = JSON.parse(process.env.GRACE), F = JSON.parse(process.env.GAUGES);

// 1. one stops array drives the MapLibre step expression and the key's swatches and labels
var col = function (t) { return 'C' + t; };
eq(stepExpr(SEA, ['get', 's'], col), ['step', ['get', 's'], 'C--dv-dn2', -3, 'C--dv-dn1', 0, 'C--dv-up1', 2, 'C--dv-up2', 4, 'C--dv-up3', 7, 'C--dv-up4']);
var k = keyModel(SEA, false, 'mm');
eq(k.swatches, SEA.map(function (s) { return s.tok; }));
eq(k.breaks.map(function (b) { return b.text; }), [M + '3', '0', '+2', '+4', '+7']);
eq(k.breaks.map(function (b) { return b.zero; }), [false, true, false, false, false]);
eq(k.breaks[1].at, 2 / 6);
eq(keyModel(SEA, true, 'mm').breaks.map(function (b) { return b.text; }), [M + '0.12', '0', '+0.08', '+0.16', '+0.28']);
eq(keyModel(WATER, false, 'cm').breaks.map(function (b) { return b.text; }), [M + '2', M + '1', '0', '+1', '+2']);
eq(stepExpr(WATER, 'x', col).filter(function (v, i) { return i > 1 && i % 2 === 0; }), WATER.map(function (s) { return 'C' + s.tok; }));
// change the array and both follow
var alt = [{ to: 5, tok: 'a' }, { to: Infinity, tok: 'b' }];
eq(stepExpr(alt, 'x', col), ['step', 'x', 'Ca', 5, 'Cb']);
eq(keyModel(alt, false, 'mm'), { swatches: ['a', 'b'], breaks: [{ text: '+5', at: 0.5, zero: false }] });
// a value equal to a break takes the class above it (MapLibre's step rule, evaluated here)
function step(e, x) { var out = e[2]; for (var i = 3; i < e.length; i += 2) if (x >= e[i]) out = e[i + 1]; return out; }
var se = stepExpr(SEA, 'x', col);
eq([-3.1, -3, -0.1, 0, 1.9, 2, 7, 14.6].map(function (x) { return step(se, x); }),
  ['C--dv-dn2', 'C--dv-dn1', 'C--dv-dn1', 'C--dv-up1', 'C--dv-up1', 'C--dv-up2', 'C--dv-up4', 'C--dv-up4']);
eq(seaWords(false), 'Colours: blue for falling (darker: 3 mm a year or more), orange to wine for rising, darker for faster: 0 to 2, 2 to 4, 4 to 7, 7 or more mm a year. A grey ring means no clear change.');

// 2. the base64 decode: little-endian int16 and bytes, lat and lon / 100, fill and "no data" dropped, a clamped end kept as wide
eq(Array.from(b64('AQD//wCA/38=', true)), [1, -1, -32768, 32767]);
eq(Array.from(b64(G.sig, false)), [2, 0, 255, 0]);
var bs = graceBlocks(G);
eq(bs.length, 3);
eq(bs[0], { lat: 29, lon: 77.39, area: 12406, slope: -4.31, lo: -4.76, hi: -3.81, wide: false, v: 'falling' });
eq([bs[1].lat, bs[1].lon, bs[1].v, bs[1].wide], [40, -75.27, 'no_clear_change', false]);
eq([bs[2].lon, bs[2].slope, bs[2].wide], [142, 12.34, true]);
eq(graceBlocks(Object.assign({}, G, { n: 5 })), null); // lengths that disagree: the file does not read
eq(graceBlocks(Object.assign({}, G, { lat: '%%%' })), null);

// 3. only gauges with a rate are drawn: "another gauge" entries are hidden and their partner drawn; other skipped ones never
var d = gaugeDots(F, '');
eq(d.map(function (g) { return g.name; }), ['The Battery', 'Mumbai / Bombay', 'Okha', 'Juneau']);
assert.ok(!d.some(function (g) { return g.name === 'New York (The Battery)' || g.name === 'Short One' || g.name === 'No Rate'; }));
// "Global gauges (PSMSL)": the PSMSL gauges plus the "another gauge" PSMSL entries with their psmsl_mode values
var dp = gaugeDots(F, 'psmsl');
eq(dp.map(function (g) { return g.name; }), ['Mumbai / Bombay', 'Okha', 'Juneau', 'New York (The Battery)']);
eq([dp[3].slope, dp[3].lo, dp[3].hi, dp[3].verdict, dp[3].years, dp[3].network], [3.04, 2.86, 3.21, 'rising', 170, 'psmsl']);
eq(gaugeTip(dp[3], false), ['New York (The Battery)', 'Rising: +3.0 mm a year, 95% range +2.9 to +3.2.', '1856–2025 · 170 years of records · PSMSL', 'Click for the full answer.']);
// the in-view line around New York in each mode (in PSMSL mode it said "No gauges ..." before)
var ny = [-75, 40, -73, 41.5];
eq(gaugeView(d, ny, false), 'In view: 1 gauge. 1 rising, 0 falling, 0 no clear change. Fastest rise: The Battery, +2.9 mm a year.');
eq(gaugeView(dp, ny, false), 'In view: 1 gauge. 1 rising, 0 falling, 0 no clear change. Fastest rise: New York (The Battery), +3.0 mm a year.');
eq(gaugeDots({ gauges: 'x' }, ''), []);

// 4. the hover words: rising, falling, no clear change, a clamped range, inches
eq(gaugeTip(d[0], false), ['The Battery', 'Rising: +2.9 mm a year, 95% range +2.7 to +3.1.', '1856–2026 · 171 years of records · NOAA CO-OPS', 'Click for the full answer.']);
eq(gaugeTip(d[3], false)[1], 'Falling: ' + M + '14 mm a year, 95% range ' + M + '14 to ' + M + '13.');
eq(gaugeTip(d[2], false)[1], 'No clear change: ' + M + '0.40 mm a year, 95% range ' + M + '1.2 to +0.5, which includes no change.');
eq(gaugeTip(d[1], false)[2], '1878–2025 · 26 years of records (short record) · PSMSL');
eq(gaugeTip(d[0], true)[1], 'Rising: +0.11 in a year, 95% range +0.11 to +0.12.');
eq(blockTip(bs[0], G, false), ['Near 29.0° N, 77.4° E', 'Falling: ' + M + '4.3 cm of water a year, 95% range ' + M + '4.8 to ' + M + '3.8.',
  'April 2002 to June 2026 · averaged over about 400 km · GRACE', 'Click for the full answer.']);
eq(blockTip(bs[1], G, false)[1], 'No clear change: +0.060 cm of water a year, 95% range ' + M + '0.15 to +0.26, which includes no change.');
eq(blockTip(bs[1], G, false)[0], 'Near 40.0° N, 75.3° W');
eq(blockTip(bs[2], G, false)[1], 'No clear change: +12 cm of water a year, 95% range very wide, which includes no change.');
// 2 significant figures, half away from zero, as the card's headline_rate text
eq([0.94, 3.04, -13.62, 0, 99.6, -0.004].map(function (x) { return num(x, false, 'mm'); }), ['+0.94', '+3.0', M + '14', '0', '+100', M + '0.0040']);
eq(rng(-0.004, 11, false, 'mm'), M + '0.004 to +11.000');  // no non-zero end reads 0
eq(rng(0.941, 0.944, false, 'mm'), '+0.941 to +0.944');    // the ends differ
// the card's own words for the same numbers (the stats lane's _headline_rate, passed in): the hover equals the card
JSON.parse(process.env.CARD).forEach(function (c) {
  eq([num(c.v, false, 'mm') + ' mm a year', rng(c.lo, c.hi, false, 'mm') + ' mm a year'], [c.text, c.range_text], JSON.stringify(c));
});

// the in-view lines
var world = [-540, -85, 540, 85];
eq(gaugeView(d, world, false), 'In view: 4 gauges. 2 rising, 1 falling, 1 no clear change. Fastest rise: The Battery, +2.9 mm a year.');
eq(gaugeView([d[3]], world, false), 'In view: 1 gauge. 0 rising, 1 falling, 0 no clear change.');
eq(gaugeView(d, [0, -10, 10, 10], false), 'No gauges with 20 or more years of records in view. Zoom out or move the map.');
eq(inBox([170, -10, 190, 10], 0, -175), true);  // a box across the antimeridian
eq(blockView(bs, world), 'In view, by area: 34% losing water, 0% gaining, 66% no clear change.');
eq(blockView(bs, [0, -10, 10, 10]), 'No blocks with a value in view. Zoom out or move the map.');

// 5. the moves: a stubbed map that keeps a flyTo padding (as MapLibre does) and subtracts it in the next fit
function LB(a, b) { this.w = a[0]; this.s = a[1]; this.e = b[0]; this.n = b[1]; }
LB.prototype.extend = function (p) { this.w = Math.min(this.w, p[0]); this.e = Math.max(this.e, p[0]); this.s = Math.min(this.s, p[1]); this.n = Math.max(this.n, p[1]); return this; };
LB.prototype.getCenter = function () { return { lng: (this.w + this.e) / 2, lat: (this.s + this.n) / 2 }; };
function stub(W, H) {
  var m = { calls: [], kept: { top: 0, bottom: 0, left: 0, right: 0 } };
  var fits = function (o) { var p = o.padding; return W - (m.kept.left + m.kept.right + p.left + p.right) > 0 && H - (m.kept.top + m.kept.bottom + p.top + p.bottom) > 0; };
  m.cameraForBounds = function (b, o) { return fits(o) ? { center: b.getCenter(), zoom: 5 } : undefined; };
  m.fitBounds = function (b, o) { m.calls.push(['fit', o, W - (m.kept.left + m.kept.right + o.padding.left + o.padding.right)]); };
  m.flyTo = function (o) { m.calls.push(['fly', o]); if (o.padding) m.kept = o.padding; };
  return m;
}
var NY = { key: 'ny', lat: 40.70, lon: -74.01 }, PR = { key: 'pr', lat: 40.35, lon: -74.66 }, MU = { key: 'mu', lat: 19.08, lon: 72.88 };
[[458, 440], [618, 440], [343, 320]].forEach(function (sz) {
  var m = stub(sz[0], sz[1]), pins = [NY, PR, MU];
  moveTo(m, LB, pins, MU, sz[0], sz[1], 0);   // Mumbai: no pin within 1,000 km
  moveTo(m, LB, pins, NY, sz[0], sz[1], 0);   // New York, with Princeton nearby
  eq(m.calls.map(function (c) { return c[0]; }), ['fly', 'fit'], sz);
  assert.strictEqual(m.calls[0][1].padding, undefined, 'flyTo keeps no padding');
  eq(m.calls[0][1].center, [72.88, 19.08]);
  eq(m.calls[0][1].zoom, 5);
  assert.ok(m.calls[1][2] > 0, 'the fit has room: ' + m.calls[1][2]);
  var p = m.calls[1][1].padding;
  assert.ok(p.left + p.right < sz[0] / 2, JSON.stringify(p));
});
eq(padFor(458, 440), { top: 40, bottom: 40, left: 40, right: 137.4 });
eq(padFor(1000, 800), { top: 40, bottom: 40, left: 40, right: 190 });
eq(padFor(343, 320), { top: 30, bottom: 30, left: 30, right: 30 });
// a fit that cannot be made centres on the selected place at zoom 5 (never keeps the old view)
var tiny = stub(50, 50);
moveTo(tiny, LB, [NY, PR], NY, 50, 50, 0);
eq(tiny.calls.map(function (c) { return [c[0], c[1].center, c[1].zoom]; }), [['fly', [-74.01, 40.70], 5]]);

// 6. a GRACE click sends the block centre (lat and lon / 100 from the file), not the clicked point
eq(pickSpec({ b: bs[0] }, { lat: 28.61, lng: 77.95 }), { label: 'Pinned spot', lat: 29, lon: 77.39 });
eq(pickSpec({ g: d[0] }, { lat: 40.72, lng: -74.0 }), { label: 'The Battery', lat: 40.7006, lon: -74.0142 });
eq(pickSpec(null, { lat: 89, lng: 190 }), { label: 'Pinned spot', lat: 85, lon: -170 });
eq(blockRing(bs[0])[0], [77.39 - 0.52 * 12406 / (111.32 * 111.32 * Math.cos(29 * Math.PI / 180)), 28.48]);

// the base map greys (13-maps.md section 1: positron land #F8F8F8 and water #DDDDDD light, #292929 water dark)
eq(greyOf('rgb(242,243,240)', 'fill', false), 'rgba(248,248,248,1)');
eq(greyOf('rgb(194, 200, 202)', 'fill', false), 'rgba(221,221,221,1)');
eq(greyOf('rgb(194, 200, 202)', 'fill', true), 'rgba(41,41,41,1)');
eq(greyOf('#000', 'text', true), 'rgba(231,231,231,1)');
eq(greyOf('#fff', 'halo', true), 'rgba(0,0,0,1)');
eq(greyAll(['interpolate', ['linear'], ['zoom'], 5.8, 'hsla(0,0%,85%,0.53)', 6, '#fff'], 'fill', false),
  ['interpolate', ['linear'], ['zoom'], 5.8, 'rgba(232,232,232,0.53)', 6, 'rgba(255,255,255,1)']);
eq(greyAll({ stops: [[5, '#fea'], [9, 'hsl(26,87%,62%)']] }, 'fill', false).stops.map(function (s) { return s[1].slice(0, 5); }), ['rgba(', 'rgba(']);
eq(roleOf('text-halo-color') + roleOf('text-color') + roleOf('fill-outline-color'), 'halotextfill');
console.log('ok');
"""


def card_texts():
    """The answer card's rate and range words (headline_rate, built by the stats lane) for rates given to 2 decimals."""
    out = []
    for v, lo, hi in ((0.94, 0.9, 0.98), (3.04, 2.86, 3.21), (-13.62, -14.1, -13.1), (-0.4, -1.2, 0.5), (12.34, 11.95, 12.05),
                      (0.06, -0.15, 0.26), (2.0, 1.995, 2.004)):
        h = trend._headline_rate("sea_level", UNITS["sea_level"], tuple(round(x * 10, 6) for x in (v, lo, hi)), None)
        out.append({"v": v, "lo": lo, "hi": hi, "text": h["text"], "range_text": h["range_text"]})
    return out


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_map_pure_logic():
    env = {"GRACE": json.dumps(GRACE), "GAUGES": json.dumps(GAUGES), "CARD": json.dumps(card_texts()), "PATH": ""}
    r = subprocess.run([shutil.which("node"), "-"], input=PURE + CHECK, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr or r.stdout


def test_map_reads_the_static_files_and_no_css_filter_greys_it():
    """The dots come from web/data/gauge-trends.json (it replaces /api/gauges for the map). The base map is greyed in its
    style, so no CSS filter may grey the canvas (it would grey the data too); the old legend is gone."""
    assert "/data/gauge-trends.json" in SRC and "/data/grace-trends.json" in SRC
    assert "/api/gauges" not in SRC
    css = (ROOT / "web" / "map.css").read_text(encoding="utf-8")
    assert "grayscale" not in css and "maplibregl-canvas { filter" not in css
    assert "map-legend" not in css + SRC and "map-detailed" not in css + SRC
