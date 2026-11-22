"""Runs the pure text and CSV logic of web/explain.js (between the PURE markers) in node, against the rework fixtures
(tests/fixtures/rework: synthetic values, everything else built by the stats lane's own code)."""
import os
import pathlib
import re
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
  JSON.stringify([k, T, steps(t, s, c), readout(t, s, c, chartModel(t, s, c.imperial).ms.length - 1)], function (key, v) { if (typeof v === 'string') out.push(v); return v; });
  return out;
}
function clean(d, c) {
  all(d, c).forEach(function (x) {
    assert.ok(!/undefined|NaN|null|\[object/.test(x), 'leak: ' + x);
    assert.ok(!/If the past trend continues|by 2050|confidence interval|chance it.s real/i.test(x), 'banned: ' + x);
    // the old fitted-baseline rule (the record only had to run from 1995 or earlier to 2014 or later)
    assert.ok(!/1995 or earlier|2014 or later/.test(x), 'old baseline rule: ' + x);
    // step 5 says what we did, not that the record "holds less independent information"
    assert.ok(!/independent information|we widened the range/.test(x), 'old widened sentence: ' + x);
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
  var z0 = ' = ' + fmtNum(t.fit.change * (k || 1), true) + unitText;
  assert.ok(w.indexOf(z0 + ' (') > 0 || w.indexOf(z0 + ', which is ') > 0, w);
  var z = num(m[4]);
  assert.ok(Math.abs(num(m[1]) * Number(m[2]) - z) <= 0.5 * Math.pow(10, -decimals(m[4])) + 1e-9, w);
}

// Princeton, air temperature: one zero everywhere, the chart's end label is the card's first number
var P = load('princeton_air_temp'), pc = ctx(P, 'Princeton, NJ'), pk = card(P.trend, false), pT = chartText(P.trend, P.series, pc), pS = steps(P.trend, P.series, pc);
var pw = P.trend.world, pf = P.trend.fit;
assert.strictEqual(pk.r1.label, 'Now, compared with the 1995–2014 average');
// F1: "Now" is trend.now as given (the 12 latest months), never the end of the trend line
assert.strictEqual(pk.r1.value, P.trend.now.text);
assert.strictEqual(pk.r1.line, 'Average of ' + P.trend.now.label);
assert.notStrictEqual(pk.r1.value, pT.endLabel);
assert.strictEqual(pT.endLabel, fmtNum(pf.level_end, true) + NB + '°C'); // the chart's line still ends at fit.level_end
assert.strictEqual(pk.r2.value + ' ' + pk.r2.per, P.trend.headline_rate.text);
assert.strictEqual(pk.r2.line, '95% range ' + P.trend.headline_rate.range_text);
assert.strictEqual(pS[3].work[1], 'The trend line ends at ' + pT.endLabel + ' compared with the 1995–2014 average, in December 2025.');
assert.strictEqual(pS[3].work[2], 'The card’s “Now”, ' + P.trend.now.text + ', is the measured average of ' + P.trend.now.label + ', not a point on the line.');
// L5: step 4 says where the trend very likely is
assert.ok(pS[3].words[0].indexOf(' The trend is very likely between ' + P.trend.headline_rate.range_text.replace(' to ', ' and ') + ' (95% range).') > 0, pS[3].words[0]);
assert.ok(all(P, pc).every(function (x) { return !/support anything from/.test(x); }));
// now null: no "Now" readout, no "Now" line in step 4
var PN = copy(P); PN.trend.now = null;
assert.strictEqual(card(PN.trend, false).r1, null);
assert.ok(steps(PN.trend, PN.series, pc)[3].work.every(function (x) { return !/Now/.test(x); }));
clean(PN, pc);
// two-level risk label: the chip is the label as given; step 6 gives the ratio's 95% range and why there are two levels
assert.strictEqual(P.trend.guidance.risk_label, 'Low to moderate risk');
assert.strictEqual(pk.chip, 'Low to moderate risk');
assert.ok(pS[5].work[0].indexOf(' = ' + fixed(pw.ratio, 1) + '× · ' + fixed(pw.ratio_low, 1) + ' to ' + fixed(pw.ratio_high, 1) + ' times (95% range) · ') > 0, pS[5].work[0]);
assert.ok(/ Here: low to moderate risk, because the 95% range spans more than one level\.$/.test(pS[5].work[1]), pS[5].work[1]);
var PR = copy(P); PR.trend.world.text += ' Here: ' + fixed(pw.ratio_low, 1) + ' to ' + fixed(pw.ratio_high, 1) + ' times.'; // the API's sentence already says it
assert.ok(!/times \(95% range\)/.test(steps(PR.trend, PR.series, pc)[5].work[0]));
var P1 = copy(P); P1.trend.guidance.risk_label = 'Moderate risk'; // one level: no "because"
assert.ok(/ Here: moderate risk\.$/.test(steps(P1.trend, P1.series, pc)[5].work[1]));
// item 6: every caveat is in "Things to keep in mind", the POWER model-data one too
assert.ok(P.trend.caveats.some(function (x) { return /weather model, MERRA-2/.test(x); }));
P.trend.caveats.forEach(function (x) { assert.ok(pS[7].words[0].list.indexOf(x) >= 0, x); });
// widened on: the exact sentence with the month count; no sea-level or water-storage line here
assert.ok(P.trend.explain.real.widened);
assert.strictEqual(pS[4].work[1], 'Months next to each other can be alike, and so can whole years in a row. We allow for that, so this range is wider than 540 separate months would give.');
assert.strictEqual(pS[4].work.length, 2);
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
// header lines start with # and are never quoted (pandas comment='#' skips them); a grid source names its point
assert.deepStrictEqual(lines.slice(0, 11), [
  '# Bhoomi: Air temperature at Princeton, NJ', '# Source: ' + src.name, '# Dataset: ' + src.dataset_id + '; version: ' + src.version,
  '# Record: ' + src.record_url, '# Grid point: Princeton, lat 40.35, lon -74.66',
  '# Baseline: the 1995–2014 average (observed); anomaly = value minus the 1995–2014 mean of its calendar month',
  '# Method: ' + src.method, '# Retrieved: ' + src.retrieved, '# Data through: December 2025', '# Built with AI assistance. bhoomi.earth', 'time,value_degC,anomaly_degC,flag']);
assert.ok(lines.slice(0, 10).every(function (l) { return /^# /.test(l) && l.indexOf('"') < 0; }));
assert.strictEqual(lines.length, 11 + P.series.times.length + 1);
assert.strictEqual(lines[11], P.series.times[0] + ',' + P.series.values[0] + ',' + P.series.anomaly.values[0] + ',');
assert.ok(lines.slice(11).every(function (l) { return l.indexOf("'") < 0; })); // number cells, negative ones too, are left alone
var PG = copy(P); PG.trend.place.name = '40.35, -74.66'; // the API names a grid point by its coordinates: said once
assert.strictEqual(csvPlace(PG.trend, PG.series, pc).text.split('\n')[4], '# Grid point: lat 40.35, lon -74.66');
// only fields the API gives: no latest, no "Data through" line; no coordinates, no place line
var PL = copy(P); PL.trend.latest = null; PL.trend.place = { name: 'x' };
assert.ok(csvPlace(PL.trend, PL.series, pc).text.split('\n').every(function (l) { return !/^# (Data through|Grid point|Station)/.test(l); }));
// a hostile place name can't become a formula in either CSV
var EVIL = 'a,=HYPERLINK("https://evil.example")', hc = ctx(P, EVIL);
var hl = csvPlace(P.trend, P.series, hc).text.split('\n');
assert.strictEqual(hl[0], "# Bhoomi: Air temperature at a,'=HYPERLINK('https://evil.example')"); // a spreadsheet splits at the comma: that piece stays text
// a tab in a header line becomes a space, as a line break does (some imports split at tabs); a formula after it still gets a '
var PT = copy(P); PT.trend.place.name = 'Princeton\tBorough';
var tl = csvPlace(PT.trend, PT.series, ctx(P, 'Princeton\tNJ,\t=1+1')).text.split('\n');
assert.strictEqual(tl[0], "# Bhoomi: Air temperature at Princeton NJ, '=1+1");
assert.strictEqual(tl[4], '# Grid point: Princeton Borough, lat 40.35, lon -74.66');
assert.ok(tl.slice(0, 10).every(function (l) { return l.indexOf('\t') < 0; }));
assert.ok(/^# Place: Princeton NJ; /.test(csvCompare([{ label: 'Princeton\tNJ', t: P.trend, s: P.series }], { name: 'Air temperature', slug: 'air-temperature' }).text.split('\n')[3]));
var hcmp = csvCompare([{ label: EVIL, t: P.trend, s: P.series }, { label: '=1+1', t: P.trend, s: P.series }, { label: '@SUM(A1)', t: P.trend, s: P.series }], { name: 'Air temperature', slug: 'air-temperature' }).text.split('\n');
assert.ok(/^# Place: a,'=HYPERLINK\('https:\/\/evil\.example'\); Source: /.test(hcmp[3]), hcmp[3]);
assert.ok(hcmp.slice(0, 6).every(function (l) { return /^# /.test(l); }));
var body = hcmp.slice(7);
assert.ok(body.indexOf('"a,=HYPERLINK(""https://evil.example"")",' + P.series.times[0] + ',' + P.series.values[0] + ',' + P.series.anomaly.values[0] + ',') >= 0);
assert.ok(body.some(function (l) { return l.indexOf("'=1+1," + P.series.times[0] + ',') === 0; }));
assert.ok(body.some(function (l) { return l.indexOf("'@SUM(A1)," + P.series.times[0] + ',') === 0; }));
assert.ok(body.every(function (l) { return !/^[=+\-@]/.test(l); }));

// in °F: levels add 32, changes and rates do not; the API's world sentence is marked as metric
var pfc = ctx(P, 'Princeton, NJ', true), fk = card(P.trend, true);
assert.strictEqual(fk.r1.value, fmtNum(P.trend.now.value * 1.8, true) + NB + '°F'); // "Now" in °F: a change, so no +32
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
assert.ok(/\scm$/.test(bk.r1.value)); // now.text, as the API writes it
all(B, bc).forEach(function (x) { assert.ok(!/cm per decade/.test(x), x); });
assert.ok(/September and October 2025 are preliminary\./.test(bT.summary), bT.summary);
assert.strictEqual(bT.title, 'Sea level at New York, NY (The Battery), 1920 to 2025');
assert.strictEqual(bS[0].short, commas(bd.n_months) + ' months from the NOAA tide gauge at The Battery, ' + M(bd.start) + ' to ' + M(bd.end));
assert.ok(/^2 months are preliminary/.test(bS[0].words[1]));
// B5: a change is in cm, like the levels; the rate stays mm a year; step 4's sum ends in the cm of step 2
var bcm = fmtNum(B.trend.fit.change / 10, true) + NB + 'cm', bmm = fmtNum(B.trend.fit.change, true) + NB + 'mm';
assert.ok(bS[1].words[0].indexOf('The change we look for is ' + bcm + ' over ') > 0, bS[1].words[0]);
assert.ok(bS[3].work[0].indexOf(' = ' + bmm + ', which is ' + bcm + ' (95% range ' + fmtNum(B.trend.fit.change_low / 10, true) + ' to ' + fmtNum(B.trend.fit.change_high / 10, true) + NB + 'cm).') > 0, bS[3].work[0]);
assert.ok(/^Over the record: \+3\.0\d* mm a year × 105\.667 years = /.test(bS[3].work[0]), bS[3].work[0]);
assert.strictEqual(bk.r1.value, B.trend.now.text);
assert.ok(!/which is/.test(steps(B.trend, B.series, ctx(B, 'New York, NY', true))[3].work[0])); // in inches one unit does
// the why already starts "Since 1993, …": the world line under it doesn't say it again; step 6 still does
assert.ok(/^Since 1993, /.test(B.trend.guidance.why) && /^Here \+/.test(bk.world), bk.world);
assert.ok(/^Since 1993: here /.test(bS[5].short), bS[5].short);
// widened, then the sea-level line
assert.ok(B.trend.explain.real.widened);
assert.deepStrictEqual(bS[4].work.slice(1), ['Months next to each other can be alike, and so can whole years in a row. We allow for that, so this range is wider than ' + commas(bd.n_months) + ' separate months would give.',
  'Slow swings in the ocean that last a decade or more can still make this range a little too narrow.']);
// widened off: no widened sentence and no substitute; the sea-level line stays
var B0 = copy(B); B0.trend.explain.real.widened = false;
assert.deepStrictEqual(steps(B0.trend, B0.series, bc)[4].work.slice(1), ['Slow swings in the ocean that last a decade or more can still make this range a little too narrow.']);
// CSV: the station and its coordinates, the data-through month; never quoted
var bl = csvPlace(B.trend, B.series, bc).text.split('\n');
assert.strictEqual(bl[4], '# Station: The Battery, lat 40.7006, lon -74.0142');
assert.strictEqual(bl[8], '# Data through: ' + B.trend.latest.text.replace('Data through ', ''));
sumAddsUp(B, bc, NB + 'mm');
assert.strictEqual(bS[5].work[2], 'The full record, 1920 to 2025: ' + B.trend.headline_rate.text + '. It gets no world ratio, because satellites only start in 1993.');
var bw = B.trend.world, biS = steps(B.trend, B.series, ctx(B, 'New York, NY', true));
assert.ok(/ \(in metric\)\.$/.test(biS[5].words[0]), biS[5].words[0]);
assert.strictEqual(biS[5].work[0].indexOf(fmtNum(bw.local_rate, false) + ' ÷ ' + fmtNum(bw.world_rate, false) + ' = ' + fixed(bw.ratio, 1) + '×'), 0, biS[5].work[0]);
assert.strictEqual(bS[5].work[0].indexOf(fmtNum(bw.local_rate, false) + ' ÷ '), 0);
assert.ok(/not corrected for the slow sinking of the ocean floor/.test(bw.source.method));
assert.strictEqual(bS[5].work[3], 'The world figure: ' + lc1(stop(bw.source.method)));
assert.strictEqual(pS[5].work.length, 2); // air temperature: no world-method line
assert.strictEqual(readout(B.trend, B.series, bc, B.series.times.length - 1).slice(-13), ' Preliminary.');
clean(B, bc);
// a fitted baseline, and a long record whose rounded headline rate would not add up: the sum still does
var K = load('kolkata_sea_level_fitted'), kc = ctx(K, 'Kolkata');
assert.ok(/\. Baseline estimated from the fitted trend\.$/.test(card(K.trend, false).r1.line));
var kw = steps(K.trend, K.series, kc)[2].work[0];
assert.ok(kw.indexOf('The record spans ' + Math.round(K.trend.record.years) + ' years, at least 5 of the 20 years are counted, and it has data both before 1995 and after 2014, so we fit the trend and the seasons together') > 0, kw);
sumAddsUp(K, kc, NB + 'mm');
assert.strictEqual(K.trend.guidance.risk_label, 'Risk level unclear (low to high)');
assert.strictEqual(card(K.trend, false).chip, 'Risk level unclear (low to high)');
var kS6 = steps(K.trend, K.series, kc)[5].work[1];
assert.ok(/ Here the 95% range spans every level, so the risk level is unclear\.$/.test(kS6) && !/\(low to high\)/.test(kS6), kS6);
clean(K, kc);

// Chennai, rain: shares of the usual rain; monthly totals in mm; the annual total as given; rates a day
var C = load('chennai_rain'), cc = ctx(C, 'Chennai'), ck = card(C.trend, false), cT = chartText(C.trend, C.series, cc), cS = steps(C.trend, C.series, cc);
var cb = C.trend.explain.seasons;
assert.strictEqual(ck.r1.value, C.trend.now.text);
assert.strictEqual(ck.r1.line, 'Rain in ' + C.trend.now.label + ', % above or below a usual year');
// F4: the chart plots trend.yearly (one point a year, mid-year) with the fit line through them
assert.strictEqual(C.trend.yearly.length, 45);
assert.strictEqual(cT.ytitle, "Each year's rain, % above or below the 1995–2014 average");
assert.ok(cT.yearly && cT.legend.monthly === "Each year's rain" && cT.hint === 'Hover, tap or use the arrow keys to read a year.');
var cm = chartModel(C.trend, C.series, false);
assert.strictEqual(cm.ms.length, 45);
assert.deepStrictEqual(cm.ys, C.trend.yearly.map(function (q) { return q.value; }));
assert.strictEqual(cm.dots[0].x, 1981 * 12 + 6);
assert.ok(cm.x0 === 1981 * 12 && cm.x1 === 2026 * 12 && cm.fit && cT.drawn);
assert.strictEqual(readout(C.trend, C.series, cc, 44), '2025: ' + fmtNum(C.trend.yearly[44].value, true) + '% compared with the usual year (1995–2014).');
// step 1 counts years; Sen's slope is on pairs of years; widened off here, so no widened sentence
var cd = C.trend.explain.data;
assert.strictEqual(cS[0].short, cd.n_years + ' years from NASA POWER, 1981 to 2025');
assert.ok(/^We used 45 yearly values of rain from .*, built from 540 monthly values\. They run from 1981 to 2025\. A year counts when at least 11 of its months have data\. No year is left out\.$/.test(cS[0].words[0]), cS[0].words[0]);
assert.ok(/every pair of years\. One odd year/.test(cS[3].words[1]));
assert.ok(!C.trend.explain.real.widened && cS[4].work.length === 1, cS[4].work);
var CW = copy(C); CW.trend.explain.real.widened = true; CW.trend.explain.data.n_missing_years = 2;
var cwS = steps(CW.trend, CW.series, cc);
assert.strictEqual(cwS[4].work[1], 'Years next to each other can be alike. We allow for that, so this range is wider than 45 separate years would give.'); // no months clause
clean(CW, cc);
assert.ok(/ 2 years are left out\.$/.test(cwS[0].words[0]));
var yrows = yearRows(C.trend, false), y17 = C.trend.yearly.findIndex(function (q) { return q.year === 2017; });
assert.strictEqual(yrows.length, C.trend.yearly.length);
assert.deepStrictEqual(cT.cols, ['Year', "Each year's rain, compared with the 1995–2014 average"]);
assert.strictEqual(readout(C.trend, C.series, cc, y17).indexOf(yrows[y17][0] + ': ' + yrows[y17][1] + ' compared with'), 0);
assert.ok(/One row a year/.test(cT.caption));
// no yearly (an older answer): the monthly plot
var CY = copy(C); delete CY.trend.yearly;
var cyT = chartText(CY.trend, CY.series, cc);
assert.ok(!cyT.yearly && cyT.ytitle === '% of the usual rain, compared with the 1995–2014 average' && chartModel(CY.trend, CY.series, false).ms.length === 540);
clean(CY, cc);
var cl = csvPlace(C.trend, C.series, cc).text.split('\n');
assert.strictEqual(cl[5], '# Baseline: the 1995–2014 average (observed); anomaly = the difference from the 1995–2014 mean of its calendar month, as a % of the 1995–2014 average rate');
assert.strictEqual(cl[10], 'time,value_mm/day,anomaly_%,flag');
assert.strictEqual(cS[1].short, 'Wettest in ' + MONTHS_LONG[cb.high_month - 1] + ' (' + fmtNum(cb.high, false) + NB + 'mm), driest in ' + MONTHS_LONG[cb.low_month - 1] + ' (' + fmtNum(cb.low, false) + NB + 'mm)');
assert.ok(/^Here the wettest month, /.test(cS[1].words[0]));
assert.ok(/ ÷ .*the usual rate = /.test(cS[1].work[0]) && /mm a day/.test(cS[1].work[0]) && !/a year/.test(cS[1].work[0]), cS[1].work[0]);
assert.strictEqual(cS[2].short, 'Every level is compared with the 1995–2014 average here, about ' + commas(Math.round(C.trend.baseline.annual_total_mm)) + NB + 'mm a year');
assert.ok(/ of the 1995–2014 average per decade × 4\.50 decades = /.test(cS[3].work[0]), cS[3].work[0]);
sumAddsUp(C, cc, '%');
all(C, cc).forEach(function (x) { if (/mm a year/.test(x)) assert.ok(/about [\d,]+ mm a year|mm (more|less) a year/.test(x), x); });
assert.ok(/mm a day measured/.test(readout(CY.trend, CY.series, cc, 5))); // the monthly plot's readout
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

// QA B10: NASA POWER air temperature and hottest day say what a grid is and offer the station; the station's answer says
// when it disagrees with the POWER answer the page already has
var ML = 'This comes from a weather model grid about 50 km wide. A weather station nearby can tell a different story.';
assert.deepStrictEqual(modelNote(H.trend, null), { line: ML, offer: 'ghcn' });
assert.deepStrictEqual(modelNote(P.trend, null), { line: ML, offer: 'ghcn' });
assert.strictEqual(modelNote(C.trend, null), null); // rain: not asked for
var HS = copy(H); HS.trend.source = { id: 'ghcn', name: 'NOAA NCEI GHCN-Daily' };
HS.trend.verdict = 'falling';
assert.deepStrictEqual(modelNote(HS.trend, H.trend), { line: 'The weather station and the model disagree here.', strong: true });
HS.trend.verdict = H.trend.verdict;
assert.strictEqual(modelNote(HS.trend, H.trend), null); // they agree
assert.strictEqual(modelNote(HS.trend, null), null); // no POWER answer on the page: nothing to compare
var HE = copy(H); HE.trend.source = { id: 'era5' };
assert.strictEqual(modelNote(HE.trend, null), null);

// a station with no 1995-2014 average: values as measured, no level, the rate still holds
var R = load('riverside_no_baseline'), rc = ctx(R, 'Riverside'), rk = card(R.trend, false), rT = chartText(R.trend, R.series, rc), rS = steps(R.trend, R.series, rc);
assert.strictEqual(rk.r1, null); // no trend.now: no "Now" readout
assert.ok(rT.none && rT.ytitle === '°C, as measured' && rT.endLabel === '');
assert.strictEqual(rS[2].short, 'No 1995–2014 average for this record');
assert.strictEqual(rS[2].work[0], R.trend.baseline.years_covered + ' of the 20 years have at least 9 months of data. We need at least 15, or a record of 30 years or more with at least 5 of the 20 years counted and data both before 1995 and after 2014.');
var rl = csvPlace(R.trend, R.series, rc).text.split('\n');
assert.strictEqual(rl[4], '# Station: RIVERSIDE FIRE STATION 3, lat 33.95, lon -117.39');
assert.strictEqual(rl[5], '# Baseline: none (too few years from 1995 to 2014)');
assert.ok(/^\d{4}-\d{2},[-\d.]*,,$/.test(rl[12]), rl[12]);
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

// no clear change: the headline says so, so the chip doesn't say it again (item 8); the range includes zero
var S = load('seattle_air_temp_no_change'), sc = ctx(S, 'Seattle'), sk = card(S.trend, false), sS = steps(S.trend, S.series, sc);
assert.ok(S.trend.guidance.risk_label === 'No clear change' && sk.word === 'No clear change');
assert.strictEqual(sk.chip, '');
assert.strictEqual(card(B.trend, false).chip, B.trend.guidance.risk_label); // any other label is the chip, as given
assert.strictEqual(sk.conf, '45 years of records');
assert.ok(/, which includes no change$/.test(sk.r2.line));
assert.ok(/^That does not mean nothing changed/.test(sS[4].words[2]));
assert.ok(/not below 0\.05 · .*which includes zero → not clear\.$/.test(sS[4].work[0]), sS[4].work[0]);
assert.ok(/Verdict: no clear change\.$/.test(chartText(S.trend, S.series, sc).summary));
// L1/B6: no ratio for no clear change, only the two rates (even if a ratio came through)
var S9 = copy(S); S9.trend.world.ratio = -0.4;
[S, S9].forEach(function (d) {
  var k9 = card(d.trend, false), s9 = steps(d.trend, d.series, sc);
  assert.ok(/^Since 1981: here −0\.01 °C per decade, world \+0\.35 °C per decade$/.test(k9.world), k9.world);
  assert.ok(!/×|÷/.test(s9[5].work[0]) && !/×/.test(s9[5].short), s9[5].work[0]);
});
clean(S, sc);

// QA B3: a clear rise with no world figure: the label and the why as given, no world line, a recommendation
var MB = load('mumbai_sea_level_no_world'), mc = ctx(MB, 'Mumbai'), mk = card(MB.trend, false), mg = MB.trend.guidance;
assert.ok(mg.risk === null && mg.risk_label === 'No world comparison' && typeof mg.recommendation === 'string' && mg.recommendation);
assert.strictEqual(mk.chip, 'No world comparison');
assert.strictEqual(mk.why, mg.why);
assert.strictEqual(mk.world, '');
assert.strictEqual(steps(MB.trend, MB.series, mc)[5].short, MB.trend.world.why_none);
clean(MB, mc);

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
assert.ok(/^# Place: New York, NY; Source: NOAA CO-OPS tide gauges; Dataset: .*; version: not named by the provider; Record: https:\/\//.test(cmpl[3]), cmpl[3]);
assert.strictEqual(cmpl[5], 'place,time,value_mm,anomaly_mm,flag');
assert.ok(/^"New York, NY",1920-01,/.test(cmpl[6]));
assert.strictEqual(cmpl.length, 6 + B.series.times.length + L.series.times.length + 1);

// QA B9: under 600 px the y-axis title is at most 40 characters (13 px semibold is about 7 px a character, so 280 px,
// the narrowest chart), for every fixture, in metric and imperial, rain's monthly plot too
['princeton_air_temp', 'battery_sea_level', 'chennai_rain', 'delhi_hottest_day', 'lewes_sea_level_short', 'riverside_no_baseline',
  'grace_water_storage', 'seattle_air_temp_no_change', 'kolkata_sea_level_fitted', 'mumbai_sea_level_no_world'].map(load).concat([CY]).forEach(function (d) {
  [false, true].forEach(function (imp) {
    var T = chartText(d.trend, d.series, ctx(d, 'X', imp));
    assert.ok(T.ytitleNarrow && T.ytitleNarrow.length <= 40, T.ytitleNarrow + ' (' + T.ytitle + ')');
  });
});
assert.strictEqual(cT.ytitleNarrow, '% above or below the 1995–2014 average');
assert.strictEqual(chartText(G.trend, G.series, gc).ytitleNarrow, 'cm of water compared with 2004–2009');

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


def test_how_clears_the_sticky_top_bar():
    """QA B2: the top bar's height is one variable, redefined where the bar grows (117 px below 900 px, 149 px below
    400 px, as measured at 375 and 414), and "How we calculated this" scrolls to just below it."""
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\.top \{ height: var\(--top-h\);", css)
    assert re.search(r"#how \{ scroll-margin-top: calc\(var\(--top-h\) \+ \d+px\); \}", css)
    root = re.search(r":root \{[^}]*--top-h: (\d+)px;", css)
    narrow = re.search(r"@media \(max-width: 899px\) \{\s*:root \{ --top-h: (\d+)px; \}", css)
    tiny = re.search(r"@media \(max-width: 399px\) \{ :root \{ --top-h: (\d+)px; \} \}", css)
    assert root and narrow and tiny
    assert (int(root[1]), int(narrow[1]), int(tiny[1])) == (64, 117, 149)


def test_compare_table_fits_wide_screens():
    """QA B8: a long place name pushed the Risk column out of sight at 1440. Place names and risk chips wrap in the
    compare table; the box still scrolls sideways, which only a narrow screen needs."""
    css = (ROOT / "web" / "compare.css").read_text(encoding="utf-8")
    rules = re.findall(r"([^{}]+)\{([^}]*)\}", css)
    place = [sel for sel, body in rules if "nowrap" in body and re.search(r"td:first-child|td:nth-child\(1\)", sel)]
    assert not place, place
    assert re.search(r"\.cmp-tbl \.risk \{[^}]*white-space: normal;", css)
    assert re.search(r"\.cmp-scroll \{ overflow-x: auto; \}", css)


def test_narrow_readout_value_column_is_capped():
    """QA B9: at 375 px rain's long unit filled an `auto` value column and squeezed the label to one word a line."""
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    narrow = re.search(r"@container \(max-width: 519px\) \{(.*?)\n\}", css, re.S)
    assert narrow
    cols = re.search(r"\.reads > div, \.reads > div \+ div \{[^}]*grid-template-columns: ([^;]+);", narrow[1])
    assert cols and cols[1] == "minmax(0, 1fr) fit-content(45%)", cols and cols[1]


def test_long_risk_chip_moves_under_the_heading():
    """Item 7: "Risk level unclear (low to high)" is shown as given. On a phone it moves under the place name instead of
    pushing past the card and squeezing the source line to one word a line."""
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\.rec \.where \{[^}]*flex-wrap: wrap;", css)
    assert re.search(r"\.rec \.where \.risk \{[^}]*white-space: normal;", css)
