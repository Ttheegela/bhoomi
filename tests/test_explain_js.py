"""Runs the pure text and CSV logic of web/explain.js (between the PURE markers) in node, against the rework fixtures
(tests/fixtures/rework: synthetic values, everything else built by the stats lane's own code)."""
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
function copy(d) { return JSON.parse(JSON.stringify(d)); }
var NAMES = { air_temp: 'Air temperature', air_temp_max: 'Hottest days', precip: 'Rain', sea_level: 'Sea level', water_storage: 'Water storage' };
var SLUGS = { air_temp: 'air-temperature', air_temp_max: 'hottest-days', precip: 'rain', sea_level: 'sea-level', water_storage: 'water-storage' };
function ctx(d, label, imp) { return { label: label, name: NAMES[d.trend.variable], slug: SLUGS[d.trend.variable], imperial: !!imp }; }
var NB = ' ', MN = '−';
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
function num(s) { return Number(String(s).replace(/−/g, '-').replace(/[^\d.+-]/g, '')); }
function decimals(s) { var m = String(s).match(/\.(\d+)/); return m ? m[1].length : 0; }
// step 4: "Over the record: {rate} × {span} = {change} (...)": the change is fit.change as printed, and the printed
// rate times the printed span gives it to the printed precision
function sumAddsUp(d, c, unitText, k) {
  var t = d.trend, w = steps(t, d.series, c)[3].work[0];
  var m = w.match(/^Over the record: (\S+) ?\S* .* × ([\d.]+) (decades|years) = (\S+?)( | |%)/);
  assert.ok(m, w);
  assert.ok(w.indexOf(' = ' + fmtNum(t.fit.change * (k || 1), true) + unitText + ' (') > 0, w);
  var z = num(m[4]);
  assert.ok(Math.abs(num(m[1]) * Number(m[2]) - z) <= 0.5 * Math.pow(10, -decimals(m[4])) + 1e-9, w);
}

// Princeton, air temperature: one zero everywhere, the chart's end label is the card's first number
var P = load('princeton_air_temp'), pc = ctx(P, 'Princeton, NJ'), pk = card(P.trend, false), pT = chartText(P.trend, P.series, pc), pS = steps(P.trend, P.series, pc);
var pw = P.trend.world, pf = P.trend.fit;
assert.strictEqual(pk.r1.label, 'Now, compared with the 1995–2014 average');
assert.strictEqual(pk.r1.value, fmtNum(pf.level_end, true) + NB + '°C');
assert.strictEqual(pk.r1.value, pT.endLabel);
assert.strictEqual(pk.r2.value + ' ' + pk.r2.per, P.trend.headline_rate.text);
assert.strictEqual(pk.r2.line, '95% range ' + P.trend.headline_rate.range_text);
assert.ok(pS[3].work[1].indexOf(pk.r1.value) > 0 && /first number on the card/.test(pS[3].work[1]));
assert.strictEqual(pS[3].short, P.trend.headline_rate.text + ', 95% range ' + P.trend.headline_rate.range_text);
sumAddsUp(P, pc, NB + '°C');
assert.strictEqual(pT.ytitle, '°C compared with the 1995–2014 average');
assert.strictEqual(pT.sub, 'Seasons removed: each month is compared with its own 1995–2014 average.');
assert.strictEqual(pk.world, 'Since 1981: here ' + fmtNum(pw.local_rate, true) + NB + '°C per decade, world ' + fmtNum(pw.world_rate, true) + NB + '°C per decade (' + fixed(pw.ratio, 1) + '×)');
assert.ok(pS[5].work[0].slice(-(pw.method.length + 1)) === pw.method + '.' || pS[5].work[0].slice(-pw.method.length) === pw.method, pS[5].work[0]);
assert.strictEqual(pS.length, 9);
assert.strictEqual(pS[0].link.href, P.trend.source.record_url);
assert.strictEqual(pS[6].link, null); // no future link here
// step 6 prints world.ratio as given, never one worked out from the rates
var P9 = copy(P); P9.trend.world.ratio = 9.9;
assert.ok(/ = 9\.9× · /.test(steps(P9.trend, P9.series, pc)[5].work[0]));
// step 5: "below" follows p < 0.05; the range words follow the range
assert.ok(/so below 0\.05 · .*all above zero → /.test(pS[4].work[0]), pS[4].work[0]);
var P5 = copy(P); P5.trend.explain.real.p_value = 0.2;
assert.ok(/^p-value 0\.200, so not below 0\.05/.test(steps(P5.trend, P5.series, pc)[4].work[0]));
P5.trend.explain.real.p_value = 0.049;
assert.ok(/^p-value 0\.049, so below 0\.05/.test(steps(P5.trend, P5.series, pc)[4].work[0]));
// the readout prints the month's anomaly next to its value
var i = 100, f = F(P.trend, false);
assert.strictEqual(readout(P.trend, P.series, pc, i), M(P.series.times[i]) + ': ' + f.lvl(P.series.values[i], 'degC') + ' measured, ' + f.val(P.series.anomaly.values[i], 'degC') +
  ' compared with the usual ' + MONTHS_LONG[mi(P.series.times[i]) % 12] + ' (1995–2014).');
// the chart's fitted line and its range come from fit as given
var md = chartModel(P.trend, P.series, false), mid = pf.level_end - pf.change / 2;
assert.ok(Math.abs(md.fit.y0 - (pf.level_end - pf.change)) < 1e-9 && md.fit.y1 === pf.level_end);
assert.ok(Math.abs(md.fit.lo0 - (mid - pf.change_low / 2)) < 1e-9 && Math.abs(md.fit.hi1 - (mid + pf.change_high / 2)) < 1e-9);
assert.ok(md.fit.lo1 < md.fit.hi1 && md.fit.lo0 > md.fit.hi0);
// a yearly dot needs 9 regular months
var P8 = copy(P), y0 = P8.series.times.indexOf('1990-01');
for (var k = 0; k < 4; k++) { P8.series.anomaly.values[y0 + k] = null; P8.series.values[y0 + k] = null; }
var dots = chartModel(P8.trend, P8.series, false).dots.map(function (q) { return q.x; });
assert.ok(dots.indexOf(1990 * 12 + 6) < 0 && dots.indexOf(1991 * 12 + 6) >= 0);
// the data table keeps the minus sign
var neg = P.series.values.findIndex(function (v) { return v != null && v < 0; });
assert.strictEqual(tableRows(P.series)[neg][1], String(P.series.values[neg]).replace('-', MN));
// links: https only
assert.strictEqual(recordUrl({ record_url: 'javascript:alert(1)' }), '');
assert.strictEqual(recordUrl({ record_url: 'http://example.org/', url: 'https://power.larc.nasa.gov/' }), 'https://power.larc.nasa.gov/');
clean(P, pc);

// the CSV header, as in the contract (a line with a comma is quoted, so it stays one cell)
var csv = csvPlace(P.trend, P.series, pc), lines = csv.text.split('\n'), src = P.trend.source;
assert.strictEqual(csv.name, 'bhoomi-air-temperature-princeton-nj.csv');
assert.deepStrictEqual(lines.slice(0, 9), [
  '"# Bhoomi: Air temperature at Princeton, NJ"', '# Source: ' + src.name, '"# Dataset: ' + src.dataset_id + '; version: ' + src.version + '"',
  '# Record: ' + src.record_url, '# Baseline: the 1995–2014 average (observed); anomaly = value minus the 1995–2014 mean of its calendar month',
  '# Method: ' + src.method, '# Retrieved: ' + src.retrieved, '# Built with AI assistance. bhoomi.earth', 'time,value_degC,anomaly_degC,flag']);
assert.strictEqual(lines.length, 9 + P.series.times.length + 1);
assert.strictEqual(lines[9], P.series.times[0] + ',' + P.series.values[0] + ',' + P.series.anomaly.values[0] + ',');
assert.ok(lines.slice(9).every(function (l) { return l.indexOf("'") < 0; })); // number cells, negative ones too, are left alone
// a hostile place name can't become a formula in either CSV
var EVIL = 'a,=HYPERLINK("https://evil.example")', hc = ctx(P, EVIL);
var hl = csvPlace(P.trend, P.series, hc).text.split('\n');
assert.strictEqual(hl[0], '"# Bhoomi: Air temperature at a,=HYPERLINK(""https://evil.example"")"');
var hcmp = csvCompare([{ label: EVIL, t: P.trend, s: P.series }, { label: '=1+1', t: P.trend, s: P.series }, { label: '@SUM(A1)', t: P.trend, s: P.series }], { name: 'Air temperature', slug: 'air-temperature' }).text.split('\n');
assert.ok(/^"# Place: a,=HYPERLINK\(""https:\/\/evil\.example""\); Source: /.test(hcmp[3]), hcmp[3]);
var body = hcmp.slice(7);
assert.ok(body.indexOf('"a,=HYPERLINK(""https://evil.example"")",' + P.series.times[0] + ',' + P.series.values[0] + ',' + P.series.anomaly.values[0] + ',') >= 0);
assert.ok(body.some(function (l) { return l.indexOf("'=1+1," + P.series.times[0] + ',') === 0; }));
assert.ok(body.some(function (l) { return l.indexOf("'@SUM(A1)," + P.series.times[0] + ',') === 0; }));
assert.ok(body.every(function (l) { return !/^[=+\-@]/.test(l); }));

// in °F: levels add 32, changes and rates do not; the API's world sentence is marked as metric
var pfc = ctx(P, 'Princeton, NJ', true), fk = card(P.trend, true);
assert.strictEqual(fk.r1.value, fmtNum(pf.level_end * 1.8, true) + NB + '°F');
assert.ok(/°F per decade$/.test(fk.r2.value + ' ' + fk.r2.per));
var pfS = steps(P.trend, P.series, pfc);
assert.ok(pfS[2].short.indexOf(fmtNum(P.trend.baseline.value * 1.8 + 32, false) + NB + '°F') > 0, pfS[2].short);
assert.ok(/ \(in metric\)\.$/.test(pfS[5].words[0]), pfS[5].words[0]);
sumAddsUp(P, pfc, NB + '°F', 1.8);
clean(P, pfc);

// The Battery, sea level: rates in mm a year everywhere, never cm per decade; one unit for the change in steps 2 and 4
var B = load('battery_sea_level'), bc = ctx(B, 'New York, NY'), bk = card(B.trend, false), bT = chartText(B.trend, B.series, bc), bS = steps(B.trend, B.series, bc);
var bd = B.trend.explain.data;
assert.strictEqual(bk.r2.per, 'a year');
assert.ok(/ cm$/.test(bk.r1.value));
all(B, bc).forEach(function (x) { assert.ok(!/cm per decade/.test(x), x); });
assert.ok(/September and October 2025 are preliminary\./.test(bT.summary), bT.summary);
assert.strictEqual(bT.title, 'Sea level at New York, NY (The Battery), 1920 to 2025');
assert.ok(/^Since 1993: here /.test(bk.world));
assert.strictEqual(bS[0].short, commas(bd.n_months) + ' months from the NOAA tide gauge at The Battery, ' + M(bd.start) + ' to ' + M(bd.end));
assert.ok(/^2 months are preliminary/.test(bS[0].words[1]));
var bch = fmtNum(B.trend.fit.change, true) + NB + 'mm';
assert.ok(bS[1].words[0].indexOf('The change we look for is ' + bch + ' over ') > 0 && bS[3].work[0].indexOf(' = ' + bch + ' (') > 0);
assert.ok(/^Over the record: \+3\.05059 mm a year × 105\.7 years = /.test(bS[3].work[0]), bS[3].work[0]);
sumAddsUp(B, bc, NB + 'mm');
assert.strictEqual(bS[5].work[2], 'The full record, 1920 to 2025: ' + B.trend.headline_rate.text + '. It gets no world ratio, because satellites only start in 1993.');
assert.strictEqual(readout(B.trend, B.series, bc, B.series.times.length - 1).slice(-13), ' Preliminary.');
clean(B, bc);
// a fitted baseline, and a long record whose rounded headline rate would not add up: the sum still does
var K = load('kolkata_sea_level_fitted'), kc = ctx(K, 'Kolkata');
assert.ok(/\. Baseline estimated from the fitted trend\.$/.test(card(K.trend, false).r1.line));
assert.ok(/so we fit the trend and the seasons together/.test(steps(K.trend, K.series, kc)[2].work[0]));
sumAddsUp(K, kc, NB + 'mm');
clean(K, kc);

// Chennai, rain: shares of the usual rain; monthly totals in mm; the annual total as given; rates a day
var C = load('chennai_rain'), cc = ctx(C, 'Chennai'), ck = card(C.trend, false), cT = chartText(C.trend, C.series, cc), cS = steps(C.trend, C.series, cc);
var cb = C.trend.explain.seasons;
assert.ok(/^Of the usual rain\. Trend line, December 2025$/.test(ck.r1.line) && /%$/.test(ck.r1.value));
assert.strictEqual(cT.ytitle, '% of the usual rain, compared with the 1995–2014 average');
assert.ok(cT.drawn && chartModel(C.trend, C.series, false).fit);
var cl = csvPlace(C.trend, C.series, cc).text.split('\n');
assert.strictEqual(cl[4], '"# Baseline: the 1995–2014 average (observed); anomaly = the difference from the 1995–2014 mean of its calendar month, as a % of the 1995–2014 average rate"');
assert.strictEqual(cl[8], 'time,value_mm/day,anomaly_%,flag');
assert.strictEqual(cS[1].short, 'Wettest in ' + MONTHS_LONG[cb.high_month - 1] + ' (' + fmtNum(cb.high, false) + NB + 'mm), driest in ' + MONTHS_LONG[cb.low_month - 1] + ' (' + fmtNum(cb.low, false) + NB + 'mm)');
assert.ok(/^Here the wettest month, /.test(cS[1].words[0]));
assert.ok(/ ÷ .*the usual rate = /.test(cS[1].work[0]) && /mm a day/.test(cS[1].work[0]) && !/a year/.test(cS[1].work[0]), cS[1].work[0]);
assert.strictEqual(cS[2].short, 'Every level is compared with the 1995–2014 average here, about ' + commas(Math.round(C.trend.baseline.annual_total_mm)) + NB + 'mm a year');
assert.ok(/ of the 1995–2014 average per decade × 4\.50 decades = /.test(cS[3].work[0]), cS[3].work[0]);
sumAddsUp(C, cc, '%');
all(C, cc).forEach(function (x) { if (/mm a year/.test(x)) assert.ok(/about [\d,]+ mm a year|mm (more|less) a year/.test(x), x); });
assert.ok(/mm a day measured/.test(readout(C.trend, C.series, cc, 5)));
clean(C, cc);
// headline_rate null (rain where the 1995-2014 average is zero): the verdict and the rate in mm a day
var C3 = copy(C); C3.trend.headline_rate = null;
var c3k = card(C3.trend, false);
assert.ok(/mm a day$/.test(c3k.r2.value) && c3k.r2.per === 'per decade', c3k.r2.value);
clean(C3, cc);
// a fit in other units than the chart's: no trend line drawn, no level on the chart
var C2 = copy(C); C2.trend.fit.units = 'mm/day';
assert.strictEqual(chartModel(C2.trend, C2.series, false).fit, null);
var c2T = chartText(C2.trend, C2.series, cc);
assert.ok(!c2T.drawn && c2T.endLabel === '' && !/stands at|trend line/.test(c2T.summary));

// Delhi, hottest day: no chip, no world figure
var H = load('delhi_hottest_day'), hdc = ctx(H, 'Delhi'), hk = card(H.trend, false), hS = steps(H.trend, H.series, hdc);
assert.strictEqual(hk.chip, '');
assert.strictEqual(hk.world, '');
assert.strictEqual(hS[5].short, 'There is no matching world figure for the hottest day of the month.');
assert.strictEqual(hS[5].work, undefined);
clean(H, hdc);

// a station with no 1995-2014 average: values as measured, no level, the rate still holds
var R = load('riverside_no_baseline'), rc = ctx(R, 'Riverside'), rk = card(R.trend, false), rT = chartText(R.trend, R.series, rc), rS = steps(R.trend, R.series, rc);
assert.strictEqual(rk.r1.value, '—');
assert.ok(rT.none && rT.ytitle === '°C, as measured' && rT.endLabel === '');
assert.strictEqual(rS[2].short, 'No 1995–2014 average for this record');
assert.ok(/runs from 1995 or earlier to 2014 or later\.$/.test(rS[2].work[0]));
var rl = csvPlace(R.trend, R.series, rc).text.split('\n');
assert.strictEqual(rl[4], '# Baseline: none (too few years from 1995 to 2014)');
assert.ok(/^\d{4}-\d{2},[-\d.]*,,$/.test(rl[10]), rl[10]);
assert.ok(/as measured\.$/.test(readout(R.trend, R.series, rc, 5)));
clean(R, rc);

// GRACE: the provider's own reference period; a negative normal is bracketed in the subtraction
var G = load('grace_water_storage'), gc = ctx(G, 'Punjab, India'), gT = chartText(G.trend, G.series, gc), gS = steps(G.trend, G.series, gc), gb = G.trend.baseline;
assert.strictEqual(gT.ytitle, 'cm of water compared with ' + gb.text);
assert.strictEqual(gS[2].short, 'Every level is compared with ' + gb.text);
assert.strictEqual(gS[6].short, G.trend.projection.why);
assert.strictEqual(card(G.trend, false).r1.label, 'Now, compared with ' + gb.text);
assert.ok(!/− −/.test(gS[1].work[0]) && / − \(−[\d.]+ cm\) \(the usual /.test(gS[1].work[0]), gS[1].work[0]);
sumAddsUp(G, gc, NB + 'cm');
clean(G, gc);

// no clear change: the chip says so, the range includes zero
var S = load('seattle_air_temp_no_change'), sc = ctx(S, 'Seattle'), sk = card(S.trend, false), sS = steps(S.trend, S.series, sc);
assert.strictEqual(sk.chip, 'No clear change');
assert.strictEqual(sk.conf, '45 years of records');
assert.ok(/, which includes no change$/.test(sk.r2.line));
assert.ok(/^That does not mean nothing changed/.test(sS[4].words[2]));
assert.ok(/not below 0\.05 · .*which includes zero → not clear\.$/.test(sS[4].work[0]), sS[4].work[0]);
assert.ok(/Verdict: no clear change\.$/.test(chartText(S.trend, S.series, sc).summary));
clean(S, sc);

// a short record
var L = load('lewes_sea_level_short'), lc = ctx(L, 'Lewes, DE'), lk = card(L.trend, false);
assert.ok(/ \(short record\)$/.test(lk.conf) && /\. Short record\.$/.test(lk.r2.line));
assert.ok(/This is a short record \(\d+ years\)/.test(steps(L.trend, L.series, lc)[3].words[2]));
clean(L, lc);

// an answer cached from before the rework: the verdict only
var O = { verdict: 'rising', slope_per_decade: 30.5, ci_low: 28, ci_high: 33, units: 'mm', meaning: { headline: 'The sea here has clearly been rising.', confidence: 'Very clear' } };
var ok_ = card(O, false);
assert.ok(ok_.old && ok_.word === 'Rising' && ok_.why === O.meaning.headline);
assert.strictEqual(rate(O, false), null);

// the compare CSV: one header block, then every plotted place's months
var cmp = csvCompare([{ label: 'New York, NY', t: B.trend, s: B.series }, { label: 'Lewes, DE', t: L.trend, s: L.series }], { name: 'Sea level', slug: 'sea-level' });
var cmpl = cmp.text.split('\n');
assert.strictEqual(cmp.name, 'bhoomi-sea-level-your-places.csv');
assert.strictEqual(cmpl[0], '# Bhoomi: Sea level at your places');
assert.ok(/^"# Place: New York, NY; Source: NOAA CO-OPS tide gauges; Dataset: .*; version: not named by the provider; Record: https:\/\//.test(cmpl[3]), cmpl[3]);
assert.strictEqual(cmpl[5], 'place,time,value_mm,anomaly_mm,flag');
assert.ok(/^"New York, NY",1920-01,/.test(cmpl[6]));
assert.strictEqual(cmpl.length, 6 + B.series.times.length + L.series.times.length + 1);

// formatting
assert.strictEqual(fmtNum(0.4, true), '+0.40'); assert.strictEqual(fmtNum(-12.34, true), '−12.3');
assert.strictEqual(given(false, 30.5059, 'mm', true), '+3.05059'); assert.strictEqual(given(false, -0.37, 'degC', false), '−0.37');
assert.strictEqual(given(false, 50, 'mm', true), '+5'); assert.strictEqual(given(true, 0.37, 'degC', false), '+0.666');
assert.strictEqual(D('2026-11-22'), '22 November 2026'); assert.strictEqual(M('2025-12'), 'December 2025'); assert.strictEqual(Mo('2025-08'), 'Aug 2025');
assert.strictEqual(commas(1266), '1,266'); assert.strictEqual(slug('São Paulo, SP'), 'sao-paulo-sp');
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_explain_pure_logic():
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-e", PURE + ASSERTS], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
