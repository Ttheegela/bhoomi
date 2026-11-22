"""Runs the pure text and CSV logic of web/explain.js (between the PURE markers) in node, against the rework fixtures."""
import os
import pathlib
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).parent.parent
SRC = (ROOT / "web" / "explain.js").read_text(encoding="utf-8")
PURE = SRC.split("/* PURE START */")[1].split("/* PURE END */")[0]

ASSERTS = r"""
var assert = require('assert'), fs = require('fs'), path = require('path');
function load(n) { return JSON.parse(fs.readFileSync(path.join(process.env.FIX, n + '.json'), 'utf8')); }
var NAMES = { air_temp: 'Air temperature', air_temp_max: 'Hottest days', precip: 'Rain', sea_level: 'Sea level', water_storage: 'Water storage' };
var SLUGS = { air_temp: 'air-temperature', air_temp_max: 'hottest-days', precip: 'rain', sea_level: 'sea-level', water_storage: 'water-storage' };
function ctx(d, label, imp) { return { label: label, name: NAMES[d.trend.variable], slug: SLUGS[d.trend.variable], imperial: !!imp }; }
// every string the page would print for one answer
function all(d, c) {
  var t = d.trend, s = d.series, out = [], k = card(t, c.imperial), T = chartText(t, s, c);
  JSON.stringify([k, T, steps(t, s, c), readout(t, s, c, s.times.length - 1)], function (key, v) { if (typeof v === 'string') out.push(v); return v; });
  return out;
}
function clean(d, c) {
  all(d, c).forEach(function (x) {
    assert.ok(!/undefined|NaN|null|\[object/.test(x), 'leak: ' + x);
    assert.ok(!/If the past trend continues|by 2050|confidence interval|chance it.s real/i.test(x), 'banned: ' + x);
  });
}
var NB = ' ';

// Princeton, air temperature: one zero everywhere, the chart's end label is the card's first number
var P = load('princeton_air_temp'), pc = ctx(P, 'Princeton, NJ'), pk = card(P.trend, false), pT = chartText(P.trend, P.series, pc), pS = steps(P.trend, P.series, pc);
assert.strictEqual(pk.r1.label, 'Now, compared with the 1995–2014 average');
assert.strictEqual(pk.r1.value, pT.endLabel);
assert.strictEqual(pk.r2.value + ' ' + pk.r2.per, P.trend.headline_rate.text);
assert.strictEqual(pk.r2.line, '95% range ' + P.trend.headline_rate.range_text);
assert.ok(pS[3].work[1].indexOf(pk.r1.value) > 0 && /first number on the card/.test(pS[3].work[1]));
assert.strictEqual(pS[3].short, P.trend.headline_rate.text + ', 95% range ' + P.trend.headline_rate.range_text);
assert.strictEqual(pT.ytitle, '°C compared with the 1995–2014 average');
assert.ok(/^Seasons removed: each month is compared with its own 1995–2014 average\.$/.test(pT.sub));
assert.ok(/^Since 1981: here \+0\.38 °C per decade, world \+0\.29 °C per decade \(1\.3×\)$/.test(pk.world), pk.world);
assert.ok(/different datasets/.test(pS[5].work[0]));
assert.strictEqual(pS.length, 9);
assert.strictEqual(pS[0].link.href, P.trend.source.record_url);
assert.strictEqual(pS[6].link, null); // no future link: the expert projection comes later
clean(P, pc);

// the CSV header, exactly as in the contract
var csv = csvPlace(P.trend, P.series, pc), lines = csv.text.split('\n'), src = P.trend.source;
assert.strictEqual(csv.name, 'bhoomi-air-temperature-princeton-nj.csv');
assert.deepStrictEqual(lines.slice(0, 9), [
  '# Bhoomi: Air temperature at Princeton, NJ', '# Source: ' + src.name, '# Dataset: ' + src.dataset_id + '; version: ' + src.version,
  '# Record: ' + src.record_url, '# Baseline: the 1995–2014 average (observed); anomaly = value minus the 1995–2014 mean of its calendar month',
  '# Method: ' + src.method, '# Retrieved: ' + src.retrieved, '# Built with AI assistance. bhoomi.earth', 'time,value_degC,anomaly_degC,flag']);
assert.strictEqual(lines.length, 9 + P.series.times.length + 1);
assert.strictEqual(lines[9], P.series.times[0] + ',' + P.series.values[0] + ',' + P.series.anomaly.values[0] + ',');

// in °F: levels add 32, changes and rates do not
var pf = ctx(P, 'Princeton, NJ', true), fk = card(P.trend, true);
assert.ok(/°F$/.test(fk.r1.value) && /°F per decade$/.test(fk.r2.value + ' ' + fk.r2.per));
var s3 = steps(P.trend, P.series, pf)[2].short, base = P.trend.baseline.value * 1.8 + 32;
assert.ok(s3.indexOf(base.toFixed(1) + NB + '°F') > 0, s3);
clean(P, pf);

// The Battery, sea level: rates in mm a year everywhere, never cm per decade; preliminary months named
var B = load('battery_sea_level'), bc = ctx(B, 'New York, NY'), bk = card(B.trend, false), bT = chartText(B.trend, B.series, bc);
assert.strictEqual(bk.r2.per, 'a year');
assert.ok(/\u00a0cm$/.test(bk.r1.value));
all(B, bc).forEach(function (x) { assert.ok(!/cm per decade/.test(x), x); });
assert.ok(/September and October 2025 are preliminary\./.test(bT.summary), bT.summary);
assert.strictEqual(bT.title, 'Sea level at New York, NY (The Battery), 1920 to 2025');
assert.ok(/^Since 1993: here /.test(bk.world));
var bS = steps(B.trend, B.series, bc);
assert.ok(/^1,\d{3} months from the NOAA tide gauge at The Battery, January 1920 to October 2025$/.test(bS[0].short), bS[0].short);
assert.ok(/2 months are preliminary/.test(bS[0].words[1]));
assert.ok(/mm a year × 105\.7 years = \+\d+\.\d mm/.test(bS[3].work[0]), bS[3].work[0]);
assert.ok(/The full record, 1920 to 2025: \+3\.1 mm a year\./.test(bS[5].work[2]));
assert.strictEqual(readout(B.trend, B.series, bc, B.series.times.length - 1).slice(-13), ' Preliminary.');
clean(B, bc);

// Chennai, rain: shares of the usual rain
var C = load('chennai_rain'), cc = ctx(C, 'Chennai'), ck = card(C.trend, false), cT = chartText(C.trend, C.series, cc);
assert.ok(/^Of the usual rain\. Trend line, December 2025$/.test(ck.r1.line));
assert.ok(/%$/.test(ck.r1.value));
assert.ok(/\(about 90 mm more a year\)\.$/.test(ck.why), ck.why);
assert.strictEqual(cT.ytitle, '% of the usual rain, compared with the 1995–2014 average');
var cl = csvPlace(C.trend, C.series, cc).text.split('\n');
assert.strictEqual(cl[4], '# Baseline: the 1995–2014 average (observed); anomaly = the difference from the 1995–2014 mean of its calendar month, as a % of the 1995–2014 average rate');
assert.strictEqual(cl[8], 'time,value_mm/day,anomaly_%,flag');
assert.ok(/ ÷ .*the usual rate = /.test(steps(C.trend, C.series, cc)[1].work[0]));
clean(C, cc);
// a fit in other units than the chart's (rain's fit in mm/day on a % axis): no trend line drawn, no level on the chart
var C2 = JSON.parse(JSON.stringify(C)); C2.trend.fit.units = 'mm/day';
assert.strictEqual(chartModel(C2.trend, C2.series, false).fit, null);
var c2T = chartText(C2.trend, C2.series, cc);
assert.ok(!c2T.drawn && c2T.endLabel === '' && !/stands at|trend line/.test(c2T.summary));
assert.ok(/mm a year$/.test(card(C2.trend, false).r1.value));

// Delhi, hottest day: no chip, no world figure
var H = load('delhi_hottest_day'), hc = ctx(H, 'Delhi'), hk = card(H.trend, false), hS = steps(H.trend, H.series, hc);
assert.strictEqual(hk.chip, '');
assert.strictEqual(hk.world, '');
assert.strictEqual(hS[5].short, 'There is no matching world figure for the hottest day of the month.');
assert.strictEqual(hS[5].work, undefined);
clean(H, hc);

// a station with no 1995-2014 average: values as measured, no level, the rate still holds
var R = load('riverside_no_baseline'), rc = ctx(R, 'Riverside'), rk = card(R.trend, false), rT = chartText(R.trend, R.series, rc), rS = steps(R.trend, R.series, rc);
assert.strictEqual(rk.r1.value, '—');
assert.ok(rT.none && rT.ytitle === '°C, as measured' && rT.endLabel === '');
assert.strictEqual(rS[2].short, 'No 1995–2014 average for this record');
assert.strictEqual(rS[3].work.length, 1);
var rl = csvPlace(R.trend, R.series, rc).text.split('\n');
assert.strictEqual(rl[4], '# Baseline: none (too few years from 1995 to 2014)');
assert.ok(/^\d{4}-\d{2},[-\d.]*,,$/.test(rl[10]), rl[10]);
assert.ok(/as measured\.$/.test(readout(R.trend, R.series, rc, 5)));
clean(R, rc);

// GRACE: the provider's own reference period
var G = load('grace_water_storage'), gc = ctx(G, 'Punjab, India'), gT = chartText(G.trend, G.series, gc), gS = steps(G.trend, G.series, gc);
assert.strictEqual(gT.ytitle, 'cm of water compared with the 2004–2009 average');
assert.strictEqual(gS[2].short, 'Every level is compared with the 2004–2009 average');
assert.strictEqual(gS[6].short, G.trend.projection.why);
assert.strictEqual(card(G.trend, false).r1.label, 'Now, compared with the 2004–2009 average');
clean(G, gc);

// no clear change: the chip says so, the range includes zero
var S = load('seattle_air_temp_no_change'), sc = ctx(S, 'Seattle'), sk = card(S.trend, false), sS = steps(S.trend, S.series, sc);
assert.strictEqual(sk.chip, 'No clear change');
assert.strictEqual(sk.conf, '45 years of records');
assert.ok(/, which includes no change$/.test(sk.r2.line));
assert.ok(/^That does not mean nothing changed/.test(sS[4].words[2]));
assert.ok(/which includes zero → not clear\.$/.test(sS[4].work[0]), sS[4].work[0]);
assert.ok(/Verdict: no clear change\.$/.test(chartText(S.trend, S.series, sc).summary));
clean(S, sc);

// a baseline fitted from the trend; a short record
var K = load('kolkata_sea_level_fitted'), kc = ctx(K, 'Kolkata');
assert.ok(/\. Baseline estimated from the fitted trend\.$/.test(card(K.trend, false).r1.line));
assert.ok(/so we fit the trend and the seasons together/.test(steps(K.trend, K.series, kc)[2].work[0]));
clean(K, kc);
var L = load('lewes_sea_level_short'), lc = ctx(L, 'Lewes, DE'), lk = card(L.trend, false);
assert.ok(/ \(short record\)$/.test(lk.conf) && /\. Short record\.$/.test(lk.r2.line));
assert.ok(/This is a short record \(27 years\)/.test(steps(L.trend, L.series, lc)[3].words[2]));
clean(L, lc);

// the compare CSV: one header block, then every plotted place's months
var cmp = csvCompare([{ label: 'New York, NY', t: B.trend, s: B.series }, { label: 'Lewes, DE', t: L.trend, s: L.series }], { name: 'Sea level', slug: 'sea-level' });
var cmpl = cmp.text.split('\n');
assert.strictEqual(cmp.name, 'bhoomi-sea-level-your-places.csv');
assert.strictEqual(cmpl[0], '# Bhoomi: Sea level at your places');
assert.ok(/^# Place: New York, NY; Source: NOAA CO-OPS tide gauges; Dataset: .*; version: not named by the provider; Record: https:\/\//.test(cmpl[3]));
assert.strictEqual(cmpl[5], 'place,time,value_mm,anomaly_mm,flag');
assert.ok(/^"New York, NY",1920-01,/.test(cmpl[6]));
assert.strictEqual(cmpl.length, 6 + B.series.times.length + L.series.times.length + 1);

// formatting
assert.strictEqual(fmtNum(0.4, true), '+0.40'); assert.strictEqual(fmtNum(-12.34, true), '−12.3'); assert.strictEqual(sig3(3.0511), '+3.05');
assert.strictEqual(D('2026-11-22'), '22 November 2026'); assert.strictEqual(M('2025-12'), 'December 2025'); assert.strictEqual(Mo('2025-08'), 'Aug 2025');
assert.strictEqual(commas(1266), '1,266'); assert.strictEqual(slug('São Paulo, SP'), 'sao-paulo-sp');
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_explain_pure_logic():
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-e", PURE + ASSERTS], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
