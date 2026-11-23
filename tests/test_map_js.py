"""The map's pure logic (web/map.js, between the PURE markers) run in node, no network: the colour steps, the GRACE file decode,
which gauges are drawn, the hover words, the view moves (web/design/13-maps.md sections 2, 4, 8) and the greyed base map."""
import base64
import json
import pathlib
import re
import shutil
import struct
import subprocess

import pytest

from earthtrends.agent import tools
from earthtrends.stats import trend
from earthtrends.stats.meaning import UNITS

ROOT = pathlib.Path(__file__).parent.parent
SRC = (ROOT / "web" / "map.js").read_text(encoding="utf-8")
PURE = SRC.split("/* PURE START")[1].split("*/", 1)[1].split("/* PURE END */")[0]


def i16(values) -> str:
    return base64.b64encode(struct.pack("<%dh" % len(values), *values)).decode()


def u8(values) -> str:
    return base64.b64encode(bytes(values)).decode()


def i32(values) -> str:
    return base64.b64encode(struct.pack("<%di" % len(values), *values)).decode()


# grace-trends.json v2: each field's encoding
ENC = {"lat": "i16le-b64", "lon": "i16le-b64", "area": "i16le-b64", "slope": "i32le-b64", "lo": "i32le-b64",
       "hi": "i32le-b64", "sig": "u8-b64"}
# a tiny grace-trends.json: Delhi falling, Princeton no clear change, one fill, one with a very wide range
GRACE = {"v": 2, "enc": ENC, "scale": 0.01, "fill": -2147483648, "n": 4, "lat_lon_scale": 0.01,
         "lat": i16([2900, 4000, 0, 3800]), "lon": i16([7739, -7527, 0, 14200]), "area": i16([12406, 12392, 100, 12000]),
         "slope": i32([-431, 6, -2147483648, 1234]), "lo": i32([-476, -15, -2147483648, -32767]),
         "hi": i32([-381, 26, -2147483648, 32767]),
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

// 2. the base64 decode: little-endian int16, int32 and bytes, lat and lon / 100, fill and "no data" dropped
eq(Array.from(ints('AQD//wCA/38=', 4)), [1, -1, -32768, 32767]);
eq(Array.from(ints(Buffer.from(new Int32Array([5707, -475, -2147483648, 2147483647]).buffer).toString('base64'), 4)), [5707, -475, -2147483648, 2147483647]);
eq(Array.from(ints(G.sig, 4)), [2, 0, 255, 0]);
eq(ints('AQD//wCA', 4), null); // 6 bytes for 4 values: no width fits
var bs = graceBlocks(G);
eq(bs.length, 3);
eq(bs[0], { lat: 29, lon: 77.39, area: 12406, slope: -4.31, lo: -4.76, hi: -3.81, v: 'falling' });
eq([bs[1].lat, bs[1].lon, bs[1].v], [40, -75.27, 'no_clear_change']);
eq([bs[2].lon, bs[2].slope, bs[2].lo, bs[2].hi], [142, 12.34, -327.67, 327.67]);
eq(graceBlocks(Object.assign({}, G, { n: 5 })), null); // lengths that disagree: the file does not read
eq(graceBlocks(Object.assign({}, G, { lat: '%%%' })), null);
// another format reads as nothing, never as garbage: a field's enc we don't decode, an enc that disagrees with the bytes
// (int16 bytes where enc says int32), the old single enc string, or another version
eq(graceBlocks(Object.assign({}, G, { enc: Object.assign({}, G.enc, { slope: 'f32le-b64' }) })), null);
eq(graceBlocks(Object.assign({}, G, { lo: G.lat })), null);
eq(graceBlocks(Object.assign({}, G, { enc: 'i32le-b64' })), null);
eq(graceBlocks(Object.assign({}, G, { v: 3 })), null);

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
eq(blockTip(bs[2], G, false)[1], 'No clear change: +12 cm of water a year, 95% range ' + M + '330 to +330, which includes no change.');
// 2 significant figures, half away from zero, as the card's headline_rate text
eq([0.94, 3.04, -13.62, 0, 99.6, -0.004].map(function (x) { return num(x, false, 'mm'); }), ['+0.94', '+3.0', M + '14', '0', '+100', M + '0.0040']);
eq(rng(-0.004, 11, false, 'mm'), M + '0.004 to +11.000');  // no non-zero end reads 0
eq(rng(0.941, 0.944, false, 'mm'), '+0.941 to +0.944');    // the ends differ
// the card's own words for the same numbers (the stats lane's _headline_rate, passed in): the hover equals the card
// the card joins number and unit with a no-break space in inches; the hover uses a plain one
function sp(r) { return { text: r.text.replace(/\u00a0/g, " "), range: r.range.replace(/\u00a0/g, " ") }; }
JSON.parse(process.env.CARD).forEach(function (c) {
  eq([num(c.v, false, 'mm') + ' mm a year', rng(c.lo, c.hi, false, 'mm') + ' mm a year'], [c.h.text, c.h.range_text], JSON.stringify(c));
  var r = sp(TDX.rate({ headline_rate: c.h, slope_per_decade: c.pd[0], ci_low: c.pd[1], ci_high: c.pd[2] }, true));
  eq([num(c.v, true, 'mm') + ' in a year', rng(c.lo, c.hi, true, 'mm') + ' in a year'], [r.text, r.range], JSON.stringify(c));
});
// inches: the unrounded rate converted, then rounded once (QA B2): 3.4285 mm is +0.13 in; its 3 significant figures (3.43)
// converted would read +0.14
eq(num(3.4285, true, 'mm'), '+0.13');
eq(TDX.sig2Text(3.43 / 25.4), '+0.14');
// Juneau (QA B2: the card converted headline_rate's rounded -14.1, the hover the unrounded -14.071): both convert ci_low now
var ju = TDX.rate({ headline_rate: { value: -13.6, low: -14.1, high: -13.2, unit: 'mm', per: 'a year', text: M + '14 mm a year', range_text: M + '14 to ' + M + '13 mm a year' },
  slope_per_decade: -136.2959, ci_low: -140.7101, ci_high: -131.8067 }, true);
eq(sp(ju).range, rng(-14.07101, -13.18067, true, 'mm') + ' in a year');
eq([sp(ju).text, sp(ju).range], [M + '0.54 in a year', M + '0.55 to ' + M + '0.52 in a year']);
// a range with an earthquake step (Ofunato II, 2011) prints its numbers, as the card does (review: no "very wide")
var of = { name: 'Ofunato II', network: 'psmsl', slope: 8.92411, lo: -1699.3872, hi: 3266.6668, verdict: 'no_clear_change', start: '1965-01', end: '2016-12', years: 52 };
eq(gaugeTip(of, false)[1], 'No clear change: +8.9 mm a year, 95% range ' + M + '1700 to +3300, which includes no change.');
eq(gaugeTip(of, true)[1], 'No clear change: +0.35 in a year, 95% range ' + M + '70 to +130, which includes no change.');
// "which includes no change" only for no clear change: a clear verdict's range end can round to 0
var edge = { lat: 0, lon: 0, area: 1, slope: -0.25, lo: -0.49, hi: 0, v: 'falling' };
eq(blockTip(edge, G, false)[1], 'Falling: ' + M + '0.25 cm of water a year, 95% range ' + M + '0.49 to 0.');
eq(blockTip(Object.assign({}, edge, { v: 'no_clear_change' }), G, false)[1], 'No clear change: ' + M + '0.25 cm of water a year, 95% range ' + M + '0.49 to 0, which includes no change.');
eq(gaugeTip(Object.assign({}, d[3], { hi: 0 }), false)[1], 'Falling: ' + M + '14 mm a year, 95% range ' + M + '14 to 0.');
// the water file as int32 with its own scale and no clamp: each block's hover equals its card (Delhi, Princeton, Chennai)
var W = JSON.parse(process.env.WATER), wb = graceBlocks(W.file);
eq(wb.length, W.cards.length);
W.cards.forEach(function (c, i) {
  var b = wb[i], nc = c.verdict === 'no_clear_change' && c.h.low <= 0 && c.h.high >= 0 ? ', which includes no change' : '';
  eq(b.v, c.verdict);
  eq(blockTip(b, W.file, false)[1], VERDICT[c.verdict] + ': ' + c.h.text + ', 95% range ' + c.h.range_text.replace(' cm of water a year', '') + nc + '.');
  var r = sp(TDX.rate({ headline_rate: c.h, slope_per_decade: c.pd[0], ci_low: c.pd[1], ci_high: c.pd[2] }, true));
  eq(blockTip(b, W.file, true)[1], VERDICT[c.verdict] + ': ' + r.text + ', 95% range ' + r.range.replace(' in of water a year', '') + nc + '.');
});
eq(W.cards.map(function (c) { return c.h.text; }), [M + '4.3 cm of water a year', '+0.057 cm of water a year', M + '0.026 cm of water a year']);

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
// QA B5: greyed, the detailed map's road shields (coloured sprite icons) and its relief are hidden; with the colours back,
// a shield returns only with labels on
var lib = { layers: [{ id: 'water', type: 'fill', paint: { 'fill-color': '#abc' } }, { id: 'relief', type: 'raster' },
  { id: 'highway-shield-non-us', type: 'symbol', layout: { 'icon-image': 'road_2' } }, { id: 'road_shield_us', type: 'symbol' },
  { id: 'label_city', type: 'symbol', paint: { 'text-color': '#333' } }] };
var rs = recordStyle(lib), vis = {}, paint = {};
var sm = { getLayer: function () { return true; }, setLayoutProperty: function (id, k, v) { vis[id] = v; }, setPaintProperty: function (id, k, v) { paint[id] = v; } };
eq(rs.hide.map(function (x) { return x.id; }), ['relief', 'highway-shield-non-us', 'road_shield_us']);
greyStyle(sm, rs, true, false, true);
eq(vis, { relief: 'none', 'highway-shield-non-us': 'none', road_shield_us: 'none' });
eq([paint.water, paint.label_city], [greyOf('#abc', 'fill', false), greyOf('#333', 'text', false)]);
greyStyle(sm, rs, false, false, true);
eq(vis, { relief: 'visible', 'highway-shield-non-us': 'visible', road_shield_us: 'visible' });
eq([paint.water, paint.label_city], ['#abc', '#333']);
greyStyle(sm, rs, false, false, false);
eq([vis.relief, vis.road_shield_us], ['visible', 'none']);
// QA B1: over a pin the hover reads at the pin's tip (its place), not the pointer; elsewhere at the pointer
var pinEl = {}, tipLL = { lng: -90.07, lat: 29.95 };
var over = { point: { x: 5, y: 9 }, lngLat: { lng: -90.1, lat: 30.0 }, originalEvent: { target: { closest: function (s) { return s === '.map-mk' ? pinEl : null; } } } };
var tipOfStub = function (el) { return el === pinEl ? tipLL : null; }, proj = function (ll) { return { x: ll.lng + 100, y: ll.lat }; };
eq(hoverAt(over, tipOfStub, proj), { point: { x: -90.07 + 100, y: 29.95 }, lngLat: tipLL });
var off = { point: { x: 5, y: 9 }, lngLat: { lng: -90.1, lat: 30.0 }, originalEvent: { target: { closest: function () { return null; } } } };
assert.strictEqual(hoverAt(off, tipOfStub, proj), off);
console.log('ok');
"""


EXPLAIN = (ROOT / "web" / "explain.js").read_text(encoding="utf-8").split("/* PURE START */")[1].split("/* PURE END */")[0]
# the card's formatter as the page has it (window.TDX): map.js rounds with the card's own sig2Text and spanText
CARD_JS = "var TDX = (function () {" + EXPLAIN + "; return { rate: rate, sig2Text: sig2Text, spanText: spanText }; })();\n"


def card_texts():
    """The answer card's headline_rate (built by the stats lane) for gauge rates a year, as the file gives them."""
    out = []
    for v, lo, hi in ((0.94, 0.9, 0.98), (3.04, 2.86, 3.21), (-13.62, -14.1, -13.1), (-0.4, -1.2, 0.5), (12.34, 11.95, 12.05),
                      (0.06, -0.15, 0.26), (2.0, 1.995, 2.004), (3.9, 3.4285, 4.5), (-0.0933, -0.21, 0.02), (7.1, 0.005, 14.0),
                      (-0.8, -1.3, -0.005)):  # the last two: an end that reads 0.000 in inches
        h = trend._headline_rate("sea_level", UNITS["sea_level"], tuple(round(x * 10, 6) for x in (v, lo, hi)), None)
        out.append({"v": v, "lo": lo, "hi": hi, "pd": [round(x * 10, 6) for x in (v, lo, hi)], "h": h})
    return out


def water_file():
    """grace-trends.json as int32 with its own scale and no clamp (the data lane's new format) for three real blocks, with
    the point answer's headline_rate at each block centre (local GRACE file, no network)."""
    spots = ((2900, 7739), (4000, -7527), (1300, 8051), (0, 0))  # Delhi, Princeton, Chennai, one with no data
    rs = [tools.detect_trend("water_storage", la / 100, lo / 100) for la, lo in spots[:3]]
    dig = lambda k: [round(r[k] * 10**4) for r in rs] + [-2147483648]  # 4-decimal digits a decade
    sig = {"no_clear_change": 0, "rising": 1, "falling": 2}
    f = {"v": 2, "enc": ENC, "scale": 0.00001, "fill": -2147483648, "n": 4, "lat_lon_scale": 0.01,
         "lat": i16([la for la, _ in spots]), "lon": i16([lo for _, lo in spots]), "area": i16([12406, 12392, 12000, 100]),
         "slope": i32(dig("slope_per_decade")), "lo": i32(dig("ci_low")), "hi": i32(dig("ci_high")),
         "sig": u8([sig[r["verdict"]] for r in rs] + [255]), "start": "2002-04", "end": "2026-06", "footprint_km": 444}
    return {"file": f, "cards": [{"verdict": r["verdict"], "h": r["headline_rate"],
                                  "pd": [r[k] for k in ("slope_per_decade", "ci_low", "ci_high")]} for r in rs]}


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_map_pure_logic():
    env = {"GRACE": json.dumps(GRACE), "GAUGES": json.dumps(GAUGES), "CARD": json.dumps(card_texts()),
           "WATER": json.dumps(water_file()), "PATH": ""}
    r = subprocess.run([shutil.which("node"), "-"], input=CARD_JS + PURE + CHECK, capture_output=True, text=True, env=env)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr or r.stdout


SWEEP = r"""
var E = JSON.parse(process.env.E), bad = { mm: 0, in: 0 };
E.forEach(function (c) {
  var t = { headline_rate: c.h, slope_per_decade: c.pd[0], ci_low: c.pd[1], ci_high: c.pd[2] };
  [false, true].forEach(function (im) {
    var r = TDX.rate(t, im), u = im ? ' in a year' : ' mm a year', cut = function (s) { return s.replace(/ /g, ' ').slice(0, -u.length); };
    if (cut(r.text) !== num(c.v, im, 'mm') || cut(r.range) !== rng(c.lo, c.hi, im, 'mm')) bad[im ? 'in' : 'mm']++;
  });
});
var f = JSON.parse(require('fs').readFileSync(process.env.W, 'utf8')), bs = graceBlocks(f);
console.log(JSON.stringify({ n: E.length, bad: bad, blocks: bs && bs.length }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_every_gauge_hover_equals_its_card_and_the_real_files_read():
    """QA B2: over every dot in web/data/gauge-trends.json (both "Measured by" lists), the hover's rate and 95% range equal
    the card's in mm (the server's headline_rate text) and in inches (the card's conversion of slope_per_decade, ci_low and
    ci_high), the earthquake-step gauges' wide ranges included. The real grace-trends.json reads (its enc is per field)."""
    f = json.loads((ROOT / "web" / "data" / "gauge-trends.json").read_text(encoding="utf-8"))
    ents = [g for g in f["gauges"] if g.get("slope") is not None]
    ents += [dict(s, **s["psmsl_mode"]) for s in f["skipped"] if s.get("psmsl_mode")]
    cases = []
    for g in ents:
        pd = [round(g[k] * 10, 4) for k in ("slope", "lo", "hi")]  # the API's 4-decimal values a decade
        cases.append({"name": g["name"], "v": g["slope"], "lo": g["lo"], "hi": g["hi"], "pd": pd,
                      "h": trend._headline_rate("sea_level", UNITS["sea_level"], tuple(pd), None)})
    env = {"E": json.dumps(cases), "W": str(ROOT / "web" / "data" / "grace-trends.json"), "PATH": ""}
    r = subprocess.run([shutil.which("node"), "-"], input=CARD_JS + PURE + SWEEP, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["n"] == len(ents) > 600 and out["bad"] == {"mm": 0, "in": 0}, out["bad"]
    assert out["blocks"] == json.loads((ROOT / "web/data/grace-trends.json").read_text())["stats"]["n"]  # every block decodes


def test_pins_are_ink_teardrops_with_a_key_line():
    """QA B1 (13-maps.md §2a): each pin holds the teardrop path, its tip on the place (anchor bottom), filled with --ink (not
    the no-change grey); both keys end item 3 with it and "Your places"; the old --mk-mod grey is gone from web/."""
    assert "var PIN_D = 'M7 22 L0.81 10.27 A7 7 0 1 1 13.19 10.27 Z';" in SRC
    assert "'<svg viewBox=\"0 0 14 22\" aria-hidden=\"true\"><path d=\"' + PIN_D + '\"/></svg>'" in SRC
    assert "el.innerHTML = PIN_SVG;" in SRC and "new lib.Marker({ element: el, anchor: 'bottom' })" in SRC
    css = (ROOT / "web" / "map.css").read_text(encoding="utf-8")
    path = re.search(r"\.map-mk path \{([^}]*)\}", css)[1]
    assert "fill: var(--ink)" in path and "stroke: var(--surface)" in path and "--dv-nc" not in path
    assert re.search(r"\.mk-pin \{ fill: var\(--ink\); \}", (ROOT / "web" / "style.css").read_text(encoding="utf-8"))
    sea, water = SRC.split("if (kind === 'gauges') {")[1].split("} else {")[0], SRC.split("var f = files.water.data")[1]
    assert "['pin', 'Your places']" in sea and "['pin', 'Your places']" in water.split("updateView();")[0]
    for f in (ROOT / "web").rglob("*"):
        if f.is_file() and f.suffix in (".js", ".css", ".html") and "vendor" not in f.parts:
            assert "--mk-mod" not in f.read_text(encoding="utf-8"), f


def test_the_hover_sits_above_the_selected_pin_and_its_tag():
    """QA B6: the selected pin's black tag covered the hover's last line ("Click for the full answer."): the popup's z-index
    must be above .map-mk.sel's."""
    css = (ROOT / "web" / "map.css").read_text(encoding="utf-8")
    z = lambda sel: int(re.search(r"(?:^|\n)%s \{[^}]*z-index: (\d+);" % re.escape(sel), css)[1])
    assert z(".map-tip") > z(".map-mk.sel") >= 1


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_a_redraw_after_a_map_tap_keeps_the_map_in_place():
    """QA B4 residual: at 375 the card and sidebar sit above the map. After a tap on the map, a redraw that makes them taller
    (or shorter) scrolls the page by the same amount, so the map stays put; a redraw that leaves the map alone scrolls none.
    Only a tap or key press inside #map-slot turns it on."""
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    fn = re.search(r"^function keepTop\(.*?^}$", app, re.M | re.S)[0]
    changed = app.split("function changed() {")[1].split("\n}\n")[0]
    assert "if (fromMap) keepTop($('map-slot'), draw," in changed and "behavior: 'instant'" in changed
    assert "e.target.closest('#map-slot')" in app
    js = fn + r"""
var box = { top: 157, getBoundingClientRect: function () { return { top: this.top }; } }, moved = [];
keepTop(box, function () { box.top += 98; }, function (d) { moved.push(d); });   // a taller answer above the map
keepTop(box, function () { box.top -= 60; }, function (d) { moved.push(d); });   // a shorter one
keepTop(box, function () {}, function (d) { moved.push(d); });                   // the map did not move: no scroll
console.log(JSON.stringify(moved));
"""
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [98, -60]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_map_key_and_card_height_lines():
    """QA B3: the water key says a block's rate is for its centre. QA B4: while a place loads the card keeps its last height
    (holdHeight, before the card is cleared) and lets it go once the answer is drawn."""
    water_key = SRC.split("var f = files.water.data")[1].split("updateView();")[0]
    assert "A block's rate is for its centre; a town's own answer can differ a little." in water_key
    for f in ("map.js", "app.js", "explain.js"):  # the whole file parses, not only its pure block
        r = subprocess.run(["node", "--check", str(ROOT / "web" / f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    fn = re.search(r"^function holdHeight\(.*$", app, re.M)[0]
    body = app.split("function drawRec(box) {")[1].split("\n}\n")[0]
    assert body.index("holdHeight(box,") < body.index("clear(box)")
    js = fn + r"""
var box = { style: { minHeight: '' }, offsetHeight: 1016 }, seen = [];
holdHeight(box, true); seen.push(box.style.minHeight);   // loading: the answer card's height is kept
box.offsetHeight = 185;
holdHeight(box, true); seen.push(box.style.minHeight);   // another pin landed while loading: still the old height
holdHeight(box, false); seen.push(box.style.minHeight);  // the answer drawn: released
console.log(JSON.stringify(seen));
"""
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == ["1016px", "1016px", ""]


def test_map_reads_the_static_files_and_no_css_filter_greys_it():
    """The dots come from web/data/gauge-trends.json (it replaces /api/gauges for the map). The base map is greyed in its
    style, so no CSS filter may grey the canvas (it would grey the data too); the old legend is gone."""
    assert "/data/gauge-trends.json" in SRC and "/data/grace-trends.json" in SRC
    assert "/api/gauges" not in SRC
    css = (ROOT / "web" / "map.css").read_text(encoding="utf-8")
    assert "grayscale" not in css and "maplibregl-canvas { filter" not in css
    assert "map-legend" not in css + SRC and "map-detailed" not in css + SRC
