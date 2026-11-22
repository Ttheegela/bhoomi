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
  var t = d.trend, s = d.series, out = [], k = card(t, c.imperial, c.sel, c.today), T = chartText(t, s, c), fx = futOf(t, c.sel, c.imperial, c.today);
  var more = fx ? [futCard(t, c), futRead(t, fx, c.imperial), fx.p.years.map(function (Y) { return decadeRead(fx, Y, c.imperial); }), futOnly(t, c), csvFuture(t, c).text] : [];
  JSON.stringify([k, T, steps(t, s, c), readout(t, s, c, chartModel(t, s, c.imperial).ms.length - 1, avg12(s))].concat(more), function (key, v) {
    if (typeof v === 'string' && !(v === 'no value' && key !== '')) out.push(v); return v; });
  return out;
}
function clean(d, c) {
  // "by 2050" is fine only from an expert projection (PR2), never from the past trend
  var banned = projOf(d.trend) ? /If the past trend continues|confidence interval|chance it.s real/i : /If the past trend continues|by 2050|confidence interval|chance it.s real/i;
  all(d, c).forEach(function (x) {
    assert.ok(!/undefined|NaN|null|\[object|no value/.test(x), 'leak: ' + x);
    assert.ok(!banned.test(x), 'banned: ' + x);
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
assert.strictEqual(bT.title, 'Sea level at New York, NY (The Battery), 1920 to 2100'); // PR2: past and future on one axis
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
// QA N6: the inches working rounds the rate like the metric one, and still adds up
var bic = ctx(B, 'New York, NY', true), biW = steps(B.trend, B.series, bic)[3].work[0];
assert.ok(biW.indexOf(given(true, B.trend.slope_per_decade, B.trend.fit.units, true) + NB + 'in a year × ') > 0, biW);
assert.ok(!/\d\.\d{5}/.test(biW), biW);
sumAddsUp(B, bic, NB + 'in', 1 / 25.4);
// QA N6: a version that already says "Version" is printed once
var RV = load('riverside_no_baseline'), rvc = ctx(RV, 'Riverside'); RV.trend.source.version = 'Version 3';
var rvS = steps(RV.trend, RV.series, rvc);
assert.ok(rvS[8].words[0].list[0].text.indexOf(', Version 3. Retrieved ') > 0 && !/version Version/i.test(JSON.stringify(rvS)), rvS[8].words[0].list[0].text);
assert.ok(/ Version 3\. Retrieved /.test(rvS[0].work[1]), rvS[0].work[1]);
RV.trend.source.version = '2.1';
assert.ok(steps(RV.trend, RV.series, rvc)[8].words[0].list[0].text.indexOf(', version 2.1. ') > 0);
// step 6, sea level: satellites vs a gauge against the land, in plain words (the owner's domain review)
var SEA6 = 'Satellites measure the height of the sea surface itself. The tide gauge measures the sea against the land, so if the land here is sinking, that adds to the local number.';
assert.deepStrictEqual(bS[5].words, [B.trend.world.text, SEA6]);
var KS = load('kolkata_sea_level_fitted'); assert.strictEqual(KS.trend.source.id, 'psmsl');
assert.strictEqual(steps(KS.trend, KS.series, ctx(KS, 'Kolkata'))[5].words[1], SEA6);
// no "land rebound" anywhere; "isostatic" only inside the API's world-method line, which stays as given
all(B, bc).forEach(function (x) { assert.ok(!/land rebound/i.test(x), x); assert.ok(!/isostatic/i.test(x) || x === bS[5].work[3], x); });
// contract: a world figure that did not rise (available, why_none set) prints why_none in step 6, with no ratio
var BF = copy(B); BF.trend.world.why_none = 'The world figure did not rise over these years, so there is no ratio.';
BF.trend.world.ratio = BF.trend.world.ratio_low = BF.trend.world.ratio_high = null;
var bfS = steps(BF.trend, BF.series, bc)[5];
assert.deepStrictEqual(bfS.words, [BF.trend.world.text, BF.trend.world.why_none, SEA6]);
assert.ok(!/×/.test(bfS.short) && !/ ÷ /.test(bfS.work[0]), bfS.short + ' | ' + bfS.work[0]);
clean(BF, bc);
// step 6, air temperature: the world figure is station-based; a model source says the two are measured differently
var AIR6 = 'The world figure is built from weather stations on land.', MOD6 = ' The number here comes from a weather model, so the two are measured in different ways.';
assert.strictEqual(P.trend.source.id, 'power');
assert.deepStrictEqual(pS[5].words, [P.trend.world.text, AIR6 + MOD6]);
var PE = copy(P); PE.trend.source.id = 'era5';
assert.strictEqual(steps(PE.trend, PE.series, pc)[5].words[1], AIR6 + MOD6);
var RG = load('riverside_no_baseline'); assert.strictEqual(RG.trend.source.id, 'ghcn');
assert.deepStrictEqual(steps(RG.trend, RG.series, ctx(RG, 'Riverside'))[5].words, [RG.trend.world.text, AIR6]);
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
assert.deepStrictEqual(modelNote(HS.trend, H.trend), { line: 'The weather station and the model disagree here.', strong: true,
  next: 'For the heat you feel day to day, the station is closer to the ground; the model covers a wider area.' });
HS.trend.verdict = H.trend.verdict;
assert.deepStrictEqual(modelNote(HS.trend, H.trend), { line: 'The weather station and the model agree here.' }); // they agree
// the grid size is read from explain.data.where, never written in
var HW = copy(H); HW.trend.explain.data.where = 'a grid cell about 55 km wide';
assert.strictEqual(modelNote(HW.trend, null).line, 'This comes from a weather model grid about 55 km wide. A weather station nearby can tell a different story.');
HW.trend.explain.data.where = null;
assert.strictEqual(modelNote(HW.trend, null).line, 'This comes from a weather model grid. A weather station nearby can tell a different story.');
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

// steps 3 to 6 start open: one baseline, the trend, is it real, compared with the world
assert.deepStrictEqual(OPEN_STEPS.map(function (n) { return pS[n - 1].title; }), ['One baseline', 'The trend and its range', 'Is it real?', 'Compared with the world']);

// formatting
assert.strictEqual(fmtNum(0.4, true), '+0.40'); assert.strictEqual(fmtNum(-12.34, true), '−12.3');
assert.strictEqual(given(false, 30.5059, 'mm', true), '+3.05059'); assert.strictEqual(given(false, -0.37, 'degC', false), '−0.37');
assert.strictEqual(given(false, 50, 'mm', true), '+5'); assert.strictEqual(given(true, 0.37, 'degC', false), '+0.67');
// QA N6: °F and inches keep the metric decimals (+3.1812 mm a year is +0.1252 in, not +0.125244)
assert.strictEqual(given(true, 31.812, 'mm', true), '+0.1252'); assert.strictEqual(given(true, 0.004, 'mm', false), '+0.000157');
assert.strictEqual(D('2026-11-22'), '22 November 2026'); assert.strictEqual(M('2025-12'), 'December 2025'); assert.strictEqual(Mo('2025-08'), 'Aug 2025');
assert.strictEqual(commas(1266), '1,266'); assert.strictEqual(slug('São Paulo, SP'), 'sao-paulo-sp');

// ---------- PR2: sea-level expert projections (web/design/11-sea-level-future.md) ----------
var TODAY = 2026 * 12 + 10; // November 2026
function pc2(d, label, imp, sel) { return Object.assign(ctx(d, label, imp), { today: TODAY, sel: sel || null }); }
function sp(x) { return String(x).replace(/\u00a0/g, ' '); } // the server's texts use a plain space
// cm(): 2 significant figures, at most 1 decimal, half away from zero, a true minus
assert.deepStrictEqual([358, 80, 9, 1036, -68, 0, 355, -355, 4, 1].map(function (x) { return cmv(x, false); }),
  ['+36 cm', '+8.0 cm', '+0.9 cm', '+104 cm', '−6.8 cm', '0 cm', '+36 cm', '−36 cm', '+0.4 cm', '+0.1 cm'].map(function (x) { return x.replace(' ', NB); }));
assert.strictEqual(cmv(254, true), '+10' + NB + 'in'); assert.strictEqual(cmv(100, true), '+3.9' + NB + 'in'); assert.strictEqual(cmv(-292, false, true), '29' + NB + 'cm');
assert.strictEqual(rngc(266, 464, false), '+27 to +46' + NB + 'cm'); assert.strictEqual(rngc(null, 464, false), 'no value');

// The Battery, intermediate (the default): the card reads the server's readouts, word for word
var BP = B.trend.projection, b2 = pc2(B, 'New York, NY'), bk2 = card(B.trend, false, null, TODAY), bfx = futOf(B.trend, null, false, TODAY);
assert.strictEqual(modeOf(B.trend, B.series, bfx), 'both');
assert.deepStrictEqual(bk2.r3f, { label: 'By 2050, intermediate emissions', value: '+36' + NB + 'cm', line: 'SSP2-4.5. Likely +27 to +46' + NB + 'cm. About 29' + NB + 'cm more than today.' });
assert.strictEqual(bk2.r1.value, BP.readouts.now.text); // "Now" is PR1's now readout, unchanged (readouts.now is the same object)
assert.strictEqual(bk2.r1.label, 'Now, compared with the 1995–2014 average');
['battery_sea_level', 'lewes_sea_level_short', 'kolkata_sea_level_fitted', 'mumbai_sea_level_no_world'].map(load).forEach(function (d) {
  var p = d.trend.projection, fx = futOf(d.trend, null, false, TODAY), ro = p.readouts;
  assert.strictEqual(sp(fx.p50 === ro.by_2050.p50 && cmv(fx.p50) + ' (likely ' + rngc(fx.lo, fx.hi) + ')'), ro.by_2050.text); // QA: cm() equals by_2050.text
  assert.strictEqual(sp(fx.more.replace(/ in \d{4}$/, ' today')), ro.more_than_today.text);
  assert.deepStrictEqual(ro.now, d.trend.now);
  clean(d, pc2(d, 'X')); clean(d, pc2(d, 'X', true)); clean(d, pc2(d, 'X', false, { ssp: 'ssp585', low: true })); clean(d, pc2(d, 'X', false, { ssp: 'ssp370', low: true }));
});
// another scenario computes the same numbers from its arrays; whole mm before cm, like the server
var b585 = card(B.trend, false, { ssp: 'ssp585', low: false }, TODAY).r3f, s585 = BP.scenarios[3];
assert.strictEqual(b585.label, 'By 2050, very high emissions');
assert.strictEqual(b585.line, 'SSP5-8.5. Likely ' + rngc(s585.p17[3], s585.p83[3]) + '. About ' + cmv(wholeMm(s585.p50[3] - B.trend.now.value), false, true) + ' more than today.');
// low confidence: percentiles, never "likely"; the chart's band and median dashed; High has no low version
var blo = futOf(B.trend, { ssp: 'ssp585', low: true }, false, TODAY), bloC = pc2(B, 'New York, NY', false, { ssp: 'ssp585', low: true });
assert.ok(blo.S.id === 'ssp585_low' && blo.low && blo.lc === ', low confidence' && blo.rk === '17th to 83rd percentile');
var blk = card(B.trend, false, { ssp: 'ssp585', low: true }, TODAY).r3f;
assert.ok(/^SSP5-8\.5, low confidence\. 17th to 83rd percentile \+\d+ to \+\d+\scm\. About /.test(blk.line), blk.line);
var bloT = futCard(B.trend, bloC), bloR = futRead(B.trend, blo, false);
[blk.line, bloR.rest, bloT.tsub, bloT.cols.join(' '), decadeRead(blo, 2050, false), chartText(B.trend, B.series, bloC).fu.band, steps(B.trend, B.series, bloC)[6].words[1]]
  .forEach(function (x) { assert.ok(!/likely|2 in 3/i.test(x), x); });
assert.deepStrictEqual(bloT.cols, ['Year', 'Middle estimate', '17th to 83rd percentile', '5th to 95th percentile', 'Rate, mm a year']);
assert.ok(/ This version adds ice-sheet changes that are hard to predict, so the experts give no chance for its range\.$/.test(steps(B.trend, B.series, bloC)[6].words[1]));
var b370 = futOf(B.trend, { ssp: 'ssp370', low: true }, false, TODAY);
assert.ok(b370.S.id === 'ssp370_medium' && b370.noLow && !b370.low);
assert.strictEqual(futRead(B.trend, b370, false).noLow, 'High (SSP3-7.0) has no low-confidence version, so this shows its medium-confidence projection.');
assert.strictEqual(futRead(B.trend, bfx, false).noLow, '');
// the y-axis: switching among medium scenarios never moves it; the low-confidence version can widen it
var id1 = function (v) { return v; }, spanOf = function (sel) { return futModel(futOf(B.trend, sel, false, TODAY), id1).span.slice().sort(function (a, b) { return a - b; }); };
assert.deepStrictEqual(spanOf({ ssp: 'ssp126' }), spanOf({ ssp: 'ssp585' }));
assert.ok(Math.max.apply(null, spanOf({ ssp: 'ssp585', low: true })) > Math.max.apply(null, spanOf({ ssp: 'ssp585' })));
var bm = futModel(bfx, id1);
assert.deepStrictEqual(bm.years, [2020, 2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100]); // the chart stops at 2100
assert.strictEqual(bm.others.length, 3); assert.strictEqual(futModel(blo, id1).others.length, 4); // low: every medium median stays
assert.deepStrictEqual(bm.sel.p50, BP.scenarios[1].p50.slice(0, 9)); // as published, from 2020: nothing shifted or joined
assert.ok(bm.others.every(function (o) { return o.S.confidence === 'medium' && o.S !== bfx.S; }));
// the 12-month average: months i-6 to i+5 inside the record, 10 valid and not preliminary; it stops 6 months before the data
var av = avg12(B.series), lastAv = av.length - 1;
while (av[lastAv] == null) lastAv--;
assert.strictEqual(lastAv, B.series.times.length - 6);
var BQ = copy(B); BQ.series.flags = BQ.series.flags.map(function () { return null; }); // no preliminary months: the window alone stops it
var avq = avg12(BQ.series);
assert.ok(avq[avq.length - 6] != null && avq.slice(-5).every(function (v) { return v == null; }));
var j = 600, win = B.series.anomaly.values.slice(j - 6, j + 6).filter(function (v) { return v != null; });
assert.ok(win.length >= 10 && Math.abs(av[j] - win.reduce(function (a, b) { return a + b; }, 0) / win.length) < 1e-9);
assert.strictEqual(av[5], null);
assert.ok(/ 12-month average: [+−][\d.]+\scm\.$/.test(readout(B.trend, B.series, b2, j, av)), readout(B.trend, B.series, b2, j, av));
// the chart's words: past and future to 2100, the future link, the summary
var bT2 = chartText(B.trend, B.series, b2);
assert.strictEqual(bT2.ytitle, 'cm above the 1995–2014 average'); assert.strictEqual(chartText(B.trend, B.series, pc2(B, 'X', true)).ytitle, 'inches above the 1995–2014 average');
assert.deepStrictEqual(bT2.fu.link, { text: 'IPCC AR6 sea level projections ↗', href: 'https://doi.org/10.5281/zenodo.6382554' });
assert.strictEqual(bT2.fu.tail, ' for New York (The Battery).');
assert.strictEqual(bT2.fu.band, 'Likely range (about 2 in 3 chance), intermediate');
assert.strictEqual(bT2.hint, 'Hover, tap or use the arrow keys to read a month, then each decade after the record ends.');
assert.ok(bT2.summary.indexOf('Sea level at New York, NY (The Battery), January 1920 to ' + M(B.trend.period.end) + ', and IPCC projections to 2100, all compared with the 1995–2014 average. The trend line rises ') === 0, bT2.summary);
assert.ok(bT2.summary.indexOf(' Now: ' + B.trend.now.text + ' (' + B.trend.now.label + '). Middle estimates for 2100: low emissions (SSP1-2.6) +67' + NB + 'cm, intermediate emissions (SSP2-4.5) +81' + NB + 'cm, high emissions (SSP3-7.0) +93' + NB + 'cm, very high emissions (SSP5-8.5) +104' + NB + 'cm. Shaded: the likely range (about 2 in 3 chance) for intermediate emissions, +62 to +108' + NB + 'cm in 2100.') > 0, bT2.summary);
assert.ok(/ Verdict: rising, very clear\.$/.test(bT2.summary));
assert.strictEqual(decadeRead(bfx, 2050, false), '2050: intermediate emissions (SSP2-4.5) +36' + NB + 'cm, likely range (about 2 in 3 chance) +27 to +46' + NB + 'cm. Others: Low +35' + NB + 'cm, High +35' + NB + 'cm, Very high +39' + NB + 'cm.');
// the readout line and the line under it
var bR = futRead(B.trend, bfx, false);
assert.strictEqual(bR.b + bR.rest, '+36' + NB + 'cm by 2050 under intermediate emissions (SSP2-4.5): likely range (about 2 in 3 chance) +27 to +46' + NB + 'cm. That is about 29' + NB + 'cm more than today.');
assert.strictEqual(bR.sub, BP.caveat + ' For flood planning here: ');
assert.deepStrictEqual(bR.link, { text: B.trend.guidance.future_link.label + ' ↗', href: B.trend.guidance.future_link.url });
// the check falls outside at this (synthetic) record: the flag, step 7 open, its short answer flagged, the ruled line
assert.strictEqual(BP.check.inside, false);
assert.strictEqual(bR.outside, "Here the measured level for 2019 to 2021 is outside the experts' 2020 range. ");
var b7 = steps(B.trend, B.series, b2)[6], bad = b7.work.filter(function (x) { return x.bad; });
assert.ok(b7.open && / · Check: outside the experts' 2020 range$/.test(b7.short), b7.short);
assert.strictEqual(bad.length, 1);
assert.strictEqual(bad[0].text, 'Check: +2.9' + NB + "cm is outside the experts' 2020 range for SSP2-4.5 (5th to 95th percentile +4.1 to +17" + NB + 'cm). About 1 in 7 tide gauges fall outside, mostly for real reasons such as an earthquake, fast land uplift or a recent regional surge. Read the projection here with extra care.');
assert.ok(b7.work.indexOf('One 12-month “Now” can swing by about 3 cm from year to year at a gauge, so a single year can sit above or below the line.') > b7.work.indexOf(bad[0]));
assert.strictEqual(b7.work[0], 'Now: the 12 months to August 2025 average ' + B.trend.now.text + ' compared with the 1995–2014 average.');
assert.strictEqual(b7.work[1], '2050, SSP2-4.5: +36' + NB + 'cm − ' + B.trend.now.text + ' = about 29' + NB + 'cm more than today. Approximate: it takes a 12-month average from a projection.');
assert.strictEqual(b7.work[2], "2020: the experts' middle estimate is +10" + NB + 'cm; the measured average for 2019 to 2021 is +2.9' + NB + 'cm. We plot the projection as published, so the gap of 7.3' + NB + 'cm shows on the chart.');
assert.strictEqual(b7.short.indexOf('+36' + NB + 'cm by 2050 under intermediate emissions (SSP2-4.5), from the IPCC'), 0);
assert.ok(/^For the future we use only published expert projections: the IPCC's sea level projections \(AR6, 2021\) at the tide gauge New York \(The Battery\), 0\.4 km from this one\./.test(b7.words[0]), b7.words[0]);
assert.strictEqual(b7.words[2].indexOf("The experts' scenarios are low (SSP1-2.6), intermediate (SSP2-4.5), high (SSP3-7.0) and very high (SSP5-8.5) emissions. They are possible paths for the world's emissions, not predictions."), 0, b7.words[2]);
assert.strictEqual(b7.words[3], 'We never stretch the past trend into the future.');
assert.deepStrictEqual(b7.links.map(function (l) { return l.href; }), ['https://doi.org/10.5281/zenodo.6382554', B.trend.guidance.future_link.url]);
// inside (Lewes): step 7 starts closed, the plain check line; no flag
var L7 = steps(L.trend, L.series, pc2(L, 'Lewes, DE'))[6];
assert.ok(!L7.open && !/Check/.test(L7.short) && L7.work.some(function (x) { return /^Check: \+8\.4\scm is inside the experts' 2020 range for SSP2-4\.5 \(5th to 95th percentile \+4\.4 to \+18\scm\), so the record and the projection agree here\.$/.test(x); }), JSON.stringify(L7.work));
assert.strictEqual(futRead(L.trend, futOf(L.trend, null, false, TODAY), false).outside, '');
// step 4: the trend line's level stays; the card's "Now" is explained in step 7
var b4 = steps(B.trend, B.series, b2)[3].work;
assert.ok(/ The card’s “Now” is the measured average of the last 12 months instead \(step 7\)\.$/.test(b4[1]) && b4.length === 2, JSON.stringify(b4));
// step 9: the projection's source, its citations, and its own CSV
var b9 = steps(B.trend, B.series, b2)[8];
assert.ok(/; future from IPCC AR6$/.test(b9.short) && b9.csv && b9.csvFut);
assert.ok(b9.words[0].list.some(function (x) { return x.text === 'Future: IPCC AR6 sea level projections (Garner et al. 2021), doi:10.5281/zenodo.6382554, version 20210809, CC BY 4.0. ' && x.link.href === 'https://doi.org/10.5281/zenodo.6382554'; }));
assert.deepStrictEqual(b9.words[1].cite, BP.source.citation);
assert.strictEqual(b9.words[1].ack, 'Acknowledgement: ' + BP.source.acknowledgement);
// "What experts project": the drivers for SSP2-4.5 only, every decade for the chosen scenario
var bC = futCard(B.trend, b2);
assert.strictEqual(bC.title, 'What experts project for New York, NY');
assert.strictEqual(bC.sub, 'IPCC AR6 sea level projections at the tide gauge New York (The Battery), 0.4 km from this one, compared with the 1995–2014 average. Source: ');
assert.strictEqual(bC.srcTail, ', version 20210809, CC BY 4.0.');
assert.strictEqual(bC.dh, 'What drives the rise by 2050');
assert.ok(/^Intermediate emissions \(SSP2-4\.5\), the one scenario this breakdown comes in\./.test(bC.dsub));
assert.deepStrictEqual(bC.parts.map(function (q) { return q.name; }), ['Ocean warming and currents', 'Greenland ice', 'Antarctic ice', 'Mountain glaciers', 'Water stored on land', 'Land rising or sinking here', 'Total']);
assert.deepStrictEqual(bC.parts[6], { name: 'Total', p17: 266, p50: 358, p83: 464, total: true, mid: '+36' + NB + 'cm', rng: '+27 to +46' + NB + 'cm' });
assert.deepStrictEqual(futCard(B.trend, bloC).parts, bC.parts); // the breakdown stays SSP2-4.5 whatever is chosen
assert.ok(bC.lo === 0 && bC.hi === 464);
assert.strictEqual(bC.rows.length, 14);
assert.deepStrictEqual(bC.rows[3], { cells: ['2050', '+36' + NB + 'cm', '+27 to +46' + NB + 'cm', '+21 to +55' + NB + 'cm', '8.6'], hl: true, brk: false });
assert.ok(bC.rows[8].brk && bC.rows.filter(function (r) { return r.brk; }).length === 1);
assert.strictEqual(bC.brk, 'After 2100 the experts used a different set of model runs, so values can jump between 2100 and 2110.');
assert.strictEqual(futCard(B.trend, pc2(B, 'X', true)).rows[3].cells[4], '0.34'); // inches a year, 2 decimals
// the projection CSV: every scenario and decade, in mm; header lines never quoted; text cells guarded
var fcsv = csvFuture(B.trend, b2), fl = fcsv.text.split('\n'), nh = fl.indexOf('scenario,name,confidence,year,p05_mm,p17_mm,p50_mm,p83_mm,p95_mm,rate_p50_mm_a_year');
assert.strictEqual(fcsv.name, 'bhoomi-sea-level-new-york-ny-ipcc-ar6.csv');
assert.deepStrictEqual(fl.slice(0, 8), ['# Bhoomi: Sea level projections for New York, NY', '# Source: IPCC AR6 sea level projections (Garner et al. 2021)',
  '# Dataset: doi:10.5281/zenodo.6382554; version: 20210809; licence: CC BY 4.0', '# Record: https://doi.org/10.5281/zenodo.6382554',
  '# Location: New York (The Battery) (gauge, 0.4 km from the gauge)', '# Baseline: the 1995–2014 average; levels in mm as published, not shifted to meet the observations',
  '# Ranges: p17-p83 is the likely range (about 2 in 3 chance) for medium confidence and the 17th to 83rd percentile for low confidence; p05-p95 is the 5th to 95th percentile',
  "# Rates: the experts' own rate of rise for each decade, mm a year"]);
assert.ok(fl.slice(0, nh).every(function (l) { return /^# /.test(l) && l.indexOf('"') < 0; }));
assert.strictEqual(fl.filter(function (l) { return /^# Cite: /.test(l); }).length, 3);
assert.strictEqual(fl[nh - 1], '# Built with AI assistance. bhoomi.earth');
assert.strictEqual(fl.length, nh + 1 + 7 * 14 + 1);
var s245 = BP.scenarios[1];
assert.strictEqual(fl[nh + 1 + 14 + 3], 'ssp245_medium,intermediate emissions,medium,2050,' + [s245.p05[3], s245.p17[3], s245.p50[3], s245.p83[3], s245.p95[3], s245.rate.p50[3]].join(','));
var BE = copy(B); BE.trend.projection.scenarios[0].name = '=HYPERLINK("x")';
assert.ok(csvFuture(BE.trend, b2).text.split('\n').some(function (l) { return l.indexOf('ssp126_medium,"\'=HYPERLINK(""x"")",medium,2020,') === 0; }));
var BN = copy(B); BN.trend.projection.scenarios[1].p95[13] = null;
assert.ok(/^ssp245_medium,intermediate emissions,medium,2150,\d+,\d+,\d+,\d+,,[\d.]+$/.test(csvFuture(BN.trend, b2).text.split('\n')[nh + 1 + 14 + 13]));
assert.strictEqual(futCard(BN.trend, b2).rows[13].cells[3], 'no value');
// the regional estimate (New Orleans): labelled as such everywhere, with the note that local sinking may differ
var RE = copy(B), REG = 'IPCC AR6 has no projection at a tide gauge close enough, so this is its estimate for the surrounding 1° area: the land motion in it is AR6\'s regional estimate, and local sinking here may differ.';
RE.trend.projection.location = { kind: 'regional estimate', id: 1000000123, name: '1° area around 30°N, 90°W', km: 12.3, note: REG };
var rec2 = pc2(RE, 'New Orleans, LA'), rfx = futOf(RE.trend, null, false, TODAY);
assert.ok(/\. Regional estimate: local sinking may differ\.$/.test(card(RE.trend, false, null, TODAY).r3f.line));
assert.strictEqual(futRead(RE.trend, rfx, false).regional, REG);
assert.strictEqual(chartText(RE.trend, RE.series, rec2).fu.link.text, 'IPCC AR6 regional estimate ↗');
assert.strictEqual(chartText(RE.trend, RE.series, rec2).fu.tail, ' for the 1° area around 30°N, 90°W.');
assert.strictEqual(futCard(RE.trend, rec2).sub, 'IPCC AR6 regional estimate for the 1° area around 30°N, 90°W (12.3 km from this gauge), compared with the 1995–2014 average. Source: ');
assert.strictEqual(futCard(RE.trend, rec2).parts[5].name, 'Land rising or sinking here (regional estimate)');
assert.ok(steps(RE.trend, RE.series, rec2)[6].words[0].indexOf("for the 1° area around 30°N, 90°W, because there is no AR6 tide gauge close enough. The land motion in it is AR6's regional estimate, and local sinking here may differ.") > 0);
assert.strictEqual(csvFuture(RE.trend, rec2).text.split('\n')[4], '# Location: 1° area around 30°N, 90°W (regional estimate, 12.3 km from the gauge); ' + REG.replace(/"/g, "'"));
clean(RE, rec2);
// an old record (Mumbai ends in 2010): "Latest" and "in 2010" for "Now" and "today"
var MBk = card(MB.trend, false, null, TODAY), mfx = futOf(MB.trend, null, false, TODAY);
assert.ok(mfx.old && MBk.r1.label === 'Latest, compared with the 1995–2014 average', MBk.r1.label);
assert.ok(/ About 18\scm more than in 2010\.$/.test(MBk.r3f.line), MBk.r3f.line);
assert.ok(/^Latest: the 12 months to December 2010 average /.test(steps(MB.trend, MB.series, pc2(MB, 'Mumbai'))[6].work[0]));
assert.strictEqual(steps(MB.trend, MB.series, pc2(MB, 'Mumbai'))[6].work.filter(function (x) { return /^Check: /.test(x); })[0], 'Check: not possible here. The record has fewer than 24 of the 36 months from 2019 to 2021.');
assert.ok(!futOf(B.trend, null, false, 2025 * 12 + 7 + 24).old && futOf(B.trend, null, false, 2025 * 12 + 7 + 25).old);
// now null: no Now dot or "more" sentence anywhere; step 7 says why
var BNN = copy(B); BNN.trend.now = null; BNN.trend.projection.readouts.now = null; BNN.trend.projection.readouts.more_than_today = null;
var nnk = card(BNN.trend, false, null, TODAY), nn7 = steps(BNN.trend, BNN.series, pc2(BNN, 'X'))[6];
assert.ok(nnk.r1 === null && nnk.r3f.line === 'SSP2-4.5. Likely +27 to +46' + NB + 'cm.', nnk.r3f.line);
assert.strictEqual(nn7.work[0], 'Now: fewer than 10 of the last 12 months have data, so there is no 12-month average to compare.');
clean(BNN, pc2(BNN, 'X'));
// a record off the 1995-2014 axis: PR1's place chart, the projection on its own chart, no "more" sentence
var BX = copy(B); BX.trend.baseline.projection_axis = false;
var xfx = futOf(BX.trend, null, false, TODAY);
assert.strictEqual(modeOf(BX.trend, BX.series, xfx), 'future');
assert.strictEqual(chartText(BX.trend, BX.series, pc2(BX, 'X')).title, 'Sea level at X (The Battery), 1920 to 2025');
assert.ok(/ This record has no 1995–2014 average, so we can't say how far that is above today\.$/.test(futRead(BX.trend, xfx, false).rest));
assert.ok(!/more than/.test(card(BX.trend, false, null, TODAY).r3f.line));
assert.ok(/^IPCC projections for X, 2020 to 2100, compared with the 1995–2014 average\. Middle estimates for 2100: /.test(futOnly(BX.trend, pc2(BX, 'X')).summary));
// no projection (water storage): PR1 exactly
assert.strictEqual(card(G.trend, false, null, TODAY).r3f, null);
assert.strictEqual(steps(G.trend, G.series, pc2(G, 'Punjab'))[6].short, G.trend.projection.why);
assert.strictEqual(modeOf(G.trend, G.series, futOf(G.trend, null, false, TODAY)), 'past');
// inches: every projection number in inches
var bik = card(B.trend, true, null, TODAY).r3f;
assert.ok(/^\+14 in$/.test(sp(bik.value)) && / About 11 in more than today\.$/.test(sp(bik.line)), bik.value + ' | ' + bik.line);
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_explain_pure_logic():
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-e", PURE + ASSERTS], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


def test_steps_3_to_6_start_open():
    """The owner's choice: steps 3, 4, 5 and 6 start open on a new answer, 1, 2 and 7 to 9 closed, at every width."""
    m = re.search(r"var OPEN_STEPS = \[([\d, ]+)\];", PURE)
    assert m and m[1] == "3, 4, 5, 6", m and m[1]
    assert "var open = fresh ? OPEN_STEPS.indexOf(i + 1) >= 0 || !!st.open : !!keep[i];" in SRC


def test_review_fixes_outside_the_pure_block():
    """Review: the step 2 strip says what the chart says; the compare caption prints why_none with a world figure; a
    failed hand-picked sea-level source offers the default only when this place already has a working answer from it."""
    assert "'% above or below the usual rain'" in SRC and "yearly average rate" not in SRC
    cmp = (ROOT / "web" / "compare.js").read_text(encoding="utf-8")
    assert "(sw.why_none ? ' ' + sw.why_none : '')" in cmp
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "def !== 'coops'" not in app
    assert "const offer = pin.none && sourceFor(curWin) && def && prev && prev.status === 'ok';" in app
    assert "b.addEventListener('click', () => pickSource(def));" in app
    assert "pin.none && curWin === 'sea_level' && !offer" in app


def test_card_meta_and_focus():
    """QA N4: "Data through {month}" never splits across lines. QA N5: a re-render that removes the focused control
    (the station button) puts focus on the new card's heading, not on <body>."""
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    assert "meta.append(' · ', el('span', { class: 'nw' }, t.latest.text));" in app
    assert re.search(r"\.rec \.meta \.nw \{ white-space: nowrap; \}", css)
    rec = re.search(r"function renderRec\(\) \{(.*?)\n\}", app, re.S)
    assert rec and "had = box.contains(document.activeElement)" in rec[1] and "drawRec(box);" in rec[1]
    assert "if (had && !box.contains(document.activeElement)) { const h = box.querySelector('h2'); if (h) h.focus({ preventScroll: true }); }" in rec[1]


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


def test_scenario_colours_never_colour_text():
    """Design 11 §9: --scen-1 is under 4.5:1 on white, so scenario colours only stroke and fill marks; every label on
    the chart and in the control is ink or --ink-2."""
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        if ("var(--k)" in body or "var(--scen-" in body) and ":root" not in sel:
            assert not re.search(r"(^|[;\s])color:", body), sel
    assert re.search(r"\.pc-r \{[^}]*fill: var\(--ink-2\);", css) and re.search(r"\.pc-lab \{[^}]*fill: var\(--ink\);", css)
