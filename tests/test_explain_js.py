"""Runs the pure text and CSV logic of web/explain.js (between the PURE markers) in node, against the rework fixtures
(tests/fixtures/rework: synthetic values, everything else built by the stats lane's own code)."""
import json
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
  var more = !fx ? [] : fx.cm ? [futRead(t, fx, c.imperial), cmTable(fx), fx.p.windows.map(function (w, i) { return winRead(fx, i); }), csvFuture(t, c).text]
    : [futCard(t, c), futRead(t, fx, c.imperial), fx.p.years.map(function (Y) { return decadeRead(fx, Y, c.imperial); }), futOnly(t, c), csvFuture(t, c).text];
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
    // facts, not advice (design 14): no risk level, recommendation or buy, build or invest advice anywhere
    assert.ok(!ADVICE.test(x), 'advice: ' + x);
  });
}
var ADVICE = /risk|recommend|advis|\bbuy|invest|high:|moderate:|low:|our rule/i;
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
// PR3: with a CMIP6 projection the card's "Now" is explained in step 7, as for sea level
assert.deepStrictEqual(pS[3].work.slice(1), ['The trend line ends at ' + pT.endLabel + ' compared with the 1995–2014 average, in December 2025. The card’s “Now” is the measured average of the last 12 months instead (step 7).']);
var P1 = copy(P); P1.trend.projection = { available: false, why: 'x' }; // without one, PR1's line
assert.strictEqual(steps(P1.trend, P1.series, pc)[3].work[2], 'The card’s “Now”, ' + P.trend.now.text + ', is the measured average of ' + P.trend.now.label + ', not a point on the line.');
// L5: step 4 says where the trend very likely is
assert.ok(pS[3].words[0].indexOf(' The trend is very likely between ' + P.trend.headline_rate.range_text.replace(' to ', ' and ') + ' (95% range).') > 0, pS[3].words[0]);
assert.ok(all(P, pc).every(function (x) { return !/support anything from/.test(x); }));
// now null: no "Now" readout, no "Now" line in step 4
var PN = copy(P); PN.trend.now = null;
assert.strictEqual(card(PN.trend, false).r1, null);
assert.ok(steps(PN.trend, PN.series, pc)[3].work.every(function (x) { return !/Now/.test(x); }));
clean(PN, pc);
// facts, not advice (design 14): the card prints guidance.fact as given; step 6 gives the ratio, its 95% range and how
// to read it, never a level or a threshold
assert.strictEqual(pk.fact, P.trend.guidance.fact);
assert.ok(!('chip' in pk));
assert.ok(pS[5].work[0].indexOf(' = ' + fixed(pw.ratio, 1) + '× · ' + fixed(pw.ratio_low, 1) + ' to ' + fixed(pw.ratio_high, 1) + ' times (95% range) · ') > 0, pS[5].work[0]);
assert.strictEqual(pS[5].work[1], '1× is the same pace as the world; 2× is twice as fast.');
var PR = copy(P); PR.trend.world.text += ' Here: ' + fixed(pw.ratio_low, 1) + ' to ' + fixed(pw.ratio_high, 1) + ' times.'; // the API's sentence already says it
assert.ok(!/times \(95% range\)/.test(steps(PR.trend, PR.series, pc)[5].work[0]));
// the card: the fact, where to look next (no url: plain text) and the disclaimer
assert.deepStrictEqual(pk.next, [{ text: 'Your national weather service', href: '' }]);
assert.strictEqual(pk.disc, 'This shows past measurements and IPCC projections, which depend on how much the world emits. It is not a prediction and not professional advice.'); // PR3: a CMIP6 projection, so the projection disclaimer
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
assert.strictEqual(pT.sub, "Each dot is one year's average, compared with the 1995–2014 average."); // PR3: a dot a year with a projection
assert.strictEqual(chartText(P1.trend, P1.series, pc).sub, 'Seasons removed: each month is compared with its own 1995–2014 average.');
// the card's world line: the two rates (the fact gives the ratio and the years), then the world figure's source
assert.deepStrictEqual(pk.world, { text: 'Over those years: here ' + fmtNum(pw.local_rate, true) + NB + '°C per decade, world ' + fmtNum(pw.world_rate, true) + NB + '°C per decade.',
  src: 'NOAA global land record', href: pw.source.record_url });
var PH = copy(P); PH.trend.world.source.record_url = 'http://example.org/'; // not https: the name, no link
assert.strictEqual(card(PH.trend, false).world.href, '');
assert.ok(pS[5].work[0].slice(-(pw.method.length + 1)) === pw.method + '.' || pS[5].work[0].slice(-pw.method.length) === pw.method, pS[5].work[0]);
assert.strictEqual(pS.length, 9);
assert.strictEqual(pS[0].link.href, P.trend.source.record_url);
assert.deepStrictEqual(pS[6].link, { text: 'IPCC AR6 Atlas, CMIP6 projections ↗', href: 'https://digital.csic.es/handle/10261/332744' }); // PR3
// step 6 prints world.ratio as given, never one worked out from the rates
var P9 = copy(P); P9.trend.world.ratio = 9.9;
assert.ok(/ = 9\.9× · /.test(steps(P9.trend, P9.series, pc)[5].work[0]));
// with the server's own digits, as the fact and the compare table print them: 0.75 stays 0.75, 1.0 stays 1.0
var P75 = copy(P); P75.trend.world.ratio = 0.75; P75.trend.world.ratio_low = 0.5; P75.trend.world.ratio_high = 1.0;
var p75 = steps(P75.trend, P75.series, pc)[5];
assert.ok(p75.work[0].indexOf(' = 0.75× · 0.5 to 1.0 times (95% range) · ') > 0 && / \(0\.75×\)$/.test(p75.short), p75.work[0] + ' | ' + p75.short);
assert.ok(worldParts(P75.trend, false).ratio === '0.75×' && worldParts(P75.trend, false).range === '0.5 to 1.0');
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
assert.strictEqual(fk.fact, P.trend.guidance.fact); // a ratio has no unit: the fact as given
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
// the card: the fact, the world line with its source, where to look next (FEMA's https url is a link) and the disclaimer
assert.strictEqual(bk.fact, B.trend.guidance.fact);
assert.deepStrictEqual(bk.world, { text: 'Over those years: here +2.7' + NB + 'mm a year, world +3.3' + NB + 'mm a year.', src: 'NASA satellite record', href: B.trend.world.source.record_url });
assert.deepStrictEqual(bk.next, [{ text: 'Official flood maps (FEMA Flood Map Service Center)' + NB + '↗', href: 'https://msc.fema.gov/portal/home' }, { text: 'Your local planning office', href: '' }]);
assert.strictEqual(bk.disc, 'This shows past measurements and IPCC projections, which depend on how much the world emits. It is not a prediction and not professional advice.');
var BL = copy(B); BL.trend.guidance.look_next = [{ label: 'X', url: 'http://msc.fema.gov/' }, { label: '', url: null }, null];
assert.deepStrictEqual(card(BL.trend, false).next, [{ text: 'X', href: '' }]); // not https: plain text; no label: left out
BL.trend.guidance.look_next = []; delete BL.trend.guidance.disclaimer;
assert.ok(card(BL.trend, false).next.length === 0 && card(BL.trend, false).disc === '');
// step 6 still starts "Since 1993"
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
assert.ok(/is corrected for the slow sinking of the ocean floor/.test(bw.source.method));
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
assert.ok(bfS.work.every(function (x) { return !/1× is/.test(x); })); // no ratio: no line on how to read it
assert.strictEqual(card(BF.trend, false).world.text, 'Since 1993: here +2.7' + NB + 'mm a year, world +3.3' + NB + 'mm a year.'); // the rates, no ratio
clean(BF, bc);
// Juneau: falling while the world rose (a ratio below 0). The fact gives the world's rate, so the world line doesn't
// repeat it; step 6 says what below 0 means; in inches the fact (mm) says it is in metric
var JU = copy(B); JU.trend.verdict = 'falling'; JU.trend.world.local_rate = -15; JU.trend.world.ratio = -4.5; JU.trend.world.ratio_low = -5.2; JU.trend.world.ratio_high = -3.8;
JU.trend.guidance.fact = 'Falling here, while the world average rose 3.3 mm a year over the same years (1993 to April 2025).';
assert.deepStrictEqual(card(JU.trend, false).world, { text: 'Over those years: here −15' + NB + 'mm a year.', src: 'NASA satellite record', href: B.trend.world.source.record_url });
assert.strictEqual(steps(JU.trend, JU.series, bc)[5].work[1], '1× is the same pace as the world. Below 0, the change here went the other way.');
assert.strictEqual(card(JU.trend, true).fact, 'Falling here, while the world average rose 3.3 mm a year over the same years (1993 to April 2025) (in metric).');
assert.strictEqual(card(JU.trend, false).fact, JU.trend.guidance.fact);
// step 6's division shows the world line's digits (review: it printed "−15.0 ÷ 3.3" beside "here −15")
assert.strictEqual(steps(JU.trend, JU.series, bc)[5].work[0].indexOf(MN + '15 ÷ 3.3 = ' + MN + '4.5×'), 0, steps(JU.trend, JU.series, bc)[5].work[0]);
var P6 = copy(P); P6.trend.world.local_rate = 0.064; P6.trend.world.world_rate = 0.2; P6.trend.world.ratio = 0.32;
assert.strictEqual(card(P6.trend, false).world.text, 'Over those years: here +0.064' + NB + '°C per decade, world +0.20' + NB + '°C per decade.');
assert.strictEqual(steps(P6.trend, P6.series, pc)[5].work[0].indexOf('0.064 ÷ 0.20 = 0.32×'), 0, steps(P6.trend, P6.series, pc)[5].work[0]);
// in inches without the 4-decimal fields: headline_rate's own numbers converted, never the metric text; without them, null
var B3 = copy(B); delete B3.trend.slope_per_decade;
assert.deepStrictEqual([rate(B3.trend, true).text, rate(B3.trend, true).range], ['+0.12' + NB + 'in a year', '+0.11 to +0.13' + NB + 'in a year']);
delete B3.trend.headline_rate.value;
assert.strictEqual(rate(B3.trend, true), null);
clean(JU, bc);
// review: "Over those years" only when the fact is the world comparison, i.e. the ratio's sign agrees with the verdict
// (guidance.py). Otherwise the fact gives the full record's rate and years, so the line says "Since 1993" and both rates.
var SINCE = { src: 'NASA satellite record', href: B.trend.world.source.record_url };
var FR = copy(B); FR.trend.verdict = 'falling'; FR.trend.world.ratio = 0.5; // falling over the record, rising since 1993
assert.deepStrictEqual(card(FR.trend, false).world, Object.assign({ text: 'Since 1993: here +2.7' + NB + 'mm a year, world +3.3' + NB + 'mm a year.' }, SINCE));
var RN = copy(B); RN.trend.world.ratio = -0.3; RN.trend.world.local_rate = -0.5; // rising over the record, falling since 1993
assert.deepStrictEqual(card(RN.trend, false).world, Object.assign({ text: 'Since 1993: here −0.50' + NB + 'mm a year, world +3.3' + NB + 'mm a year.' }, SINCE));
var R0 = copy(B); R0.trend.world.ratio = 0; R0.trend.world.local_rate = 0; // a zero ratio says nothing: the fact is the rate
assert.deepStrictEqual(card(R0.trend, false).world, Object.assign({ text: 'Since 1993: here 0' + NB + 'mm a year, world +3.3' + NB + 'mm a year.' }, SINCE));
[FR, RN, R0].forEach(function (d) { clean(d, bc); });
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
assert.strictEqual(steps(K.trend, K.series, kc)[5].work[1], '1× is the same pace as the world; 2× is twice as fast.');
assert.deepStrictEqual(card(K.trend, false).next, [{ text: 'Your local planning office', href: '' }]); // a PSMSL gauge: no FEMA link
clean(K, kc);

// Chennai, rain: shares of the usual rain; monthly totals in mm; the annual total as given; rates a day
var C = load('chennai_rain'), cc = ctx(C, 'Chennai'), ck = card(C.trend, false), cT = chartText(C.trend, C.series, cc), cS = steps(C.trend, C.series, cc);
var cb = C.trend.explain.seasons;
assert.strictEqual(ck.r1.value, C.trend.now.text);
assert.strictEqual(ck.r1.line, 'Rain in ' + C.trend.now.label + ', % above or below a usual year');
// F4: the chart plots trend.yearly (one point a year, mid-year) with the fit line through them
assert.strictEqual(C.trend.yearly.length, 45);
assert.strictEqual(cT.ytitle, "Each year's rain, % above or below the 1995–2014 average");
assert.ok(cT.yearly && cT.legend.monthly === "Each year's rain" && cT.hint === 'Hover, tap or use the arrow keys to read a year, then each 20-year period after the record ends.');
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
// step 6 without a world figure: why there is none, never world.text (an older answer's level rule is not printed)
assert.ok(!C.trend.world.available && C.trend.world.text === null && C.trend.world.why_none);
assert.deepStrictEqual(cS[5].words, [C.trend.world.why_none]);
assert.strictEqual(cS[5].short, C.trend.world.why_none);
var CR = copy(C); CR.trend.world.text = 'Our rule: a change of 10% or more is high.';
assert.deepStrictEqual(steps(CR.trend, CR.series, cc)[5].words, [C.trend.world.why_none]);
// the card: the fact as given (no rain note after it), no world line; in inches a % fact is unchanged
assert.strictEqual(ck.fact, C.trend.guidance.fact);
assert.ok(ck.world === null && card(C.trend, true).fact === C.trend.guidance.fact && !/mm/.test(ck.fact));
assert.deepStrictEqual(ck.next, [{ text: 'Your national weather service', href: '' }]);
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

// Delhi, hottest day: no world figure; the fact, where to look next and the disclaimer like any other card
var H = load('delhi_hottest_day'), hdc = ctx(H, 'Delhi'), hk = card(H.trend, false), hS = steps(H.trend, H.series, hdc);
assert.strictEqual(hk.world, null);
assert.strictEqual(hk.fact, H.trend.guidance.fact);
assert.deepStrictEqual(hk.next, [{ text: 'Your national weather service', href: '' }]);
assert.strictEqual(hk.disc, 'This shows past measurements and IPCC projections, which depend on how much the world emits. It is not a prediction and not professional advice.');
assert.strictEqual(card(H.trend, true).fact, H.trend.guidance.fact.replace(/\.$/, ' (in metric).')); // °C in a °F page
assert.strictEqual(hS[5].short, 'There is no matching world figure for the hottest day of the month.');
assert.strictEqual(hS[5].work, undefined);
assert.deepStrictEqual(hS[5].words, [H.trend.world.why_none]); // no rule (world.text null): why_none alone
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
assert.deepStrictEqual(gS[5].words, [G.trend.world.why_none]); // why there is no world figure, no level rule
assert.strictEqual(card(G.trend, false).world, null);
assert.strictEqual(card(G.trend, false).r1.label, 'Now, compared with ' + gb.text);
assert.ok(!/− −/.test(gS[1].work[0]) && / − \(−[\d.]+ cm\) \(the usual /.test(gS[1].work[0]), gS[1].work[0]);
sumAddsUp(G, gc, NB + 'cm');
clean(G, gc);

// no clear change: a card like any other, the fact as given; the range includes zero
var S = load('seattle_air_temp_no_change'), sc = ctx(S, 'Seattle'), sk = card(S.trend, false), sS = steps(S.trend, S.series, sc);
assert.ok(sk.word === 'No clear change' && sk.fact === S.trend.guidance.fact && /^No clear change \(/.test(sk.fact));
assert.ok(sk.next.length === 1 && /^This shows past measurements and IPCC projections/.test(sk.disc));
assert.strictEqual(sk.conf, '45 years of records');
assert.ok(/, which includes no change$/.test(sk.r2.line));
assert.ok(/^That does not mean nothing changed/.test(sS[4].words[2]));
assert.ok(/not below 0\.05 · .*which includes zero → not clear\.$/.test(sS[4].work[0]), sS[4].work[0]);
assert.ok(/Verdict: no clear change\.$/.test(chartText(S.trend, S.series, sc).summary));
// the world line keeps the API's digits (facts QA bug 1: fmtNum printed -0.014 as -0.01; Chennai's 0.064 as +0.06)
var SE = load('seattle_air_temp_no_change');
assert.strictEqual(worldParts(SE.trend, false).here, MN + '0.014' + NB + '°C per decade');
var SE2 = copy(SE); SE2.trend.world.local_rate = 0.064; SE2.trend.world.world_rate = 0.2;
assert.deepStrictEqual([worldParts(SE2.trend, false).here, worldParts(SE2.trend, false).world], ['+0.064' + NB + '°C per decade', '+0.20' + NB + '°C per decade']);
// rain's "Now" is a share: the same text in mm and inches (facts QA bug 2: +126.2% in inches beside +130% in mm)
var CR = load('chennai_rain'); CR.trend.now.value = 126.2169; CR.trend.now.text = '+130%';
assert.strictEqual(card(CR.trend, true).r1.value, '+130%');
assert.strictEqual(card(CR.trend, false).r1.value, '+130%');
// L1/B6: no ratio for no clear change, only the two rates (even if a ratio came through)
var S9 = copy(S); S9.trend.world.ratio = -0.4;
[S, S9].forEach(function (d) {
  var k9 = card(d.trend, false), s9 = steps(d.trend, d.series, sc);
  assert.ok(/^Since 1981: here −0\.014 °C per decade, world \+0\.35 °C per decade\.$/.test(k9.world.text) && k9.world.src === 'NOAA global land record', k9.world.text);
  assert.ok(!/×|÷/.test(s9[5].work[0]) && !/×/.test(s9[5].short) && s9[5].work.length === 1, s9[5].work[0]);
});
clean(S, sc);

// QA B3: a clear rise with no world figure (Mumbai): the fact as given, then why there is no world figure, no link
var MB = load('mumbai_sea_level_no_world'), mc = ctx(MB, 'Mumbai'), mk = card(MB.trend, false), mg = MB.trend.guidance;
assert.ok(!('risk' in mg) && !('risk_label' in mg) && !('recommendation' in mg) && !('why' in mg));
assert.strictEqual(mk.fact, mg.fact);
assert.deepStrictEqual(mk.world, { text: MB.trend.world.why_none, src: '', href: '' });
assert.deepStrictEqual(mk.next, [{ text: 'Your local planning office', href: '' }]);
assert.strictEqual(mk.disc, mg.disclaimer);
assert.strictEqual(card(MB.trend, true).fact, mg.fact.replace(/\.$/, ' (in metric).')); // mm in an inches page
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
assert.ok(ok_.old && ok_.word === 'Rising' && ok_.fact === O.meaning.headline);
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
var OUT = " Measured levels here are below the experts' range for recent years (step 7)."; // R3 when check.inside is false: this synthetic Battery's +2.9 cm is under +4.1 to +17 cm
function pc2(d, label, imp, sel) { return Object.assign(ctx(d, label, imp), { today: TODAY, sel: sel || null }); }
function sp(x) { return String(x).replace(/\u00a0/g, ' '); } // the server's texts use a plain space
// cm(): 2 significant figures, half away from zero, a true minus: the server's sig2 (9 mm is +0.90 cm, 1036 mm is +100 cm)
assert.deepStrictEqual([358, 80, 9, 1036, -68, 0, 355, -355, 4, 1, 999, 10360].map(function (x) { return cmv(x, false); }),
  ['+36 cm', '+8.0 cm', '+0.90 cm', '+100 cm', '−6.8 cm', '0 cm', '+36 cm', '−36 cm', '+0.40 cm', '+0.10 cm', '+100 cm', '+1000 cm'].map(function (x) { return x.replace(' ', NB); }));
assert.strictEqual(cmv(254, true), '+10' + NB + 'in'); assert.strictEqual(cmv(100, true), '+3.9' + NB + 'in'); assert.strictEqual(cmv(-292, false, true), '29' + NB + 'cm');
assert.strictEqual(rngc(266, 464, false), '+27 to +46' + NB + 'cm'); assert.strictEqual(rngc(null, 464, false), 'no value');

// The Battery, intermediate (the default): the card reads the server's readouts, word for word
var BP = B.trend.projection, b2 = pc2(B, 'New York, NY'), bk2 = card(B.trend, false, null, TODAY), bfx = futOf(B.trend, null, false, TODAY);
assert.strictEqual(modeOf(B.trend, B.series, bfx), 'both');
assert.deepStrictEqual(bk2.r3f, { label: 'By 2050, intermediate emissions', value: '+36' + NB + 'cm', line: 'SSP2-4.5, IPCC AR6. Likely +27 to +46' + NB + 'cm. About 29' + NB + 'cm more than today.' + OUT });
assert.strictEqual(bk2.r1.value, BP.readouts.now.text); // "Now" is PR1's now readout, unchanged (readouts.now is the same object)
assert.strictEqual(bk2.r1.label, 'Now, compared with the 1995–2014 average');
['battery_sea_level', 'lewes_sea_level_short', 'kolkata_sea_level_fitted', 'mumbai_sea_level_no_world'].map(load).forEach(function (d) {
  var p = d.trend.projection, fx = futOf(d.trend, null, false, TODAY), ro = p.readouts;
  assert.strictEqual(sp(fx.p50 === ro.by_2050.p50 && cmv(fx.p50) + ' (likely ' + rngc(fx.lo, fx.hi) + ')'), ro.by_2050.text); // QA: cm() equals by_2050.text
  assert.strictEqual(sp(fx.more), ro.more_than_today.text); // as given: the server says "than today" or "than in {year}"
  assert.deepStrictEqual(ro.now, d.trend.now);
  clean(d, pc2(d, 'X')); clean(d, pc2(d, 'X', true)); clean(d, pc2(d, 'X', false, { ssp: 'ssp585', low: true })); clean(d, pc2(d, 'X', false, { ssp: 'ssp370', low: true }));
});
// another scenario computes the same numbers from its arrays; whole mm before cm, like the server
var b585 = card(B.trend, false, { ssp: 'ssp585', low: false }, TODAY).r3f, s585 = BP.scenarios[3];
assert.strictEqual(b585.label, 'By 2050, very high emissions');
assert.strictEqual(b585.line, 'SSP5-8.5, IPCC AR6. Likely ' + rngc(s585.p17[3], s585.p83[3]) + '. About ' + cmv(wholeMm(s585.p50[3] - B.trend.now.value), false, true) + ' more than today.' + OUT);
// low confidence: percentiles, never "likely"; the chart's band and median dashed; High has no low version
var blo = futOf(B.trend, { ssp: 'ssp585', low: true }, false, TODAY), bloC = pc2(B, 'New York, NY', false, { ssp: 'ssp585', low: true });
assert.ok(blo.S.id === 'ssp585_low' && blo.low && blo.lc === ', low confidence' && blo.rk === '17th to 83rd percentile');
var blk = card(B.trend, false, { ssp: 'ssp585', low: true }, TODAY).r3f;
assert.ok(/^SSP5-8\.5, low confidence, IPCC AR6\. 17th to 83rd percentile \+\d+ to \+\d+\scm\. About /.test(blk.line), blk.line);
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
assert.strictEqual(bm.others.length, 3);
// low confidence on (QA): the other three medians only, never S's own medium twin ("Very high +100 cm" next to its +110 cm)
var blm = futModel(blo, id1);
assert.deepStrictEqual(blm.others.map(function (o) { return o.S.id; }), ['ssp126_medium', 'ssp245_medium', 'ssp370_medium']);
assert.ok(blo.p.years.every(function (Y) { var o = decadeRead(blo, Y, false).split(' Others: ')[1]; return o && !/Very high/.test(o); }));
assert.deepStrictEqual(futModel(b370, id1).others.map(function (o) { return o.S.id; }), ['ssp126_medium', 'ssp245_medium', 'ssp585_medium']); // High: no low version
// item 3: at 375 px the low-confidence end label fits the 96 px right margin (84 px of 12 px text, about 6.5 px a character)
assert.deepStrictEqual(lcLines(false), ['low confidence']);
assert.ok(lcLines(true).join(' ') === 'low confidence' && lcLines(true).every(function (x) { return x.length * 6.5 <= 83; }), lcLines(true));
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
assert.ok(bT2.summary.indexOf(' Now: ' + B.trend.now.text + ' (' + B.trend.now.label + '). Middle estimates for 2100: low emissions (SSP1-2.6) +67' + NB + 'cm, intermediate emissions (SSP2-4.5) +81' + NB + 'cm, high emissions (SSP3-7.0) +93' + NB + 'cm, very high emissions (SSP5-8.5) +100' + NB + 'cm. Shaded: the likely range (about 2 in 3 chance) for intermediate emissions, +62 to +110' + NB + 'cm in 2100.') > 0, bT2.summary);
assert.ok(/ Verdict: rising, very clear\.$/.test(bT2.summary));
var bloS = chartText(B.trend, B.series, bloC).summary, v110 = cmv(atY(BP, blo.S, 'p50', 2100));
assert.ok(v110 !== cmv(BP.scenarios[3].p50[8]) && bloS.indexOf(', very high emissions (SSP5-8.5), low confidence ' + v110 + '. Shaded: the 17th to 83rd percentile for very high emissions, low confidence, ') > 0, bloS);
assert.ok(bloS.indexOf('very high emissions (SSP5-8.5) ' + cmv(BP.scenarios[3].p50[8])) < 0, bloS); // never the medium value it no longer draws
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
assert.strictEqual(bad[0].text, 'Check: +2.9' + NB + "cm is outside the experts' 2020 range for SSP2-4.5 (5th to 95th percentile +4.1 to +17" + NB + "cm). Some tide gauges fall outside the experts' 2020 range, often because of earthquakes, land rising after the ice age, or a recent surge. Read the projection here with extra care.");
// review: no share of gauges ("1 in 7", "15%") that no field backs; the only numbers are this gauge's own
assert.ok(!/\d+ (in|of|out of) \d+|\d\s*%|\d+ (gauges|tide gauges)/.test(bad[0].text), bad[0].text);
assert.ok(b7.work.indexOf('One 12-month “Now” can swing by about 3 cm from year to year at a gauge, so a single year can sit above or below the line.') > b7.work.indexOf(bad[0]));
assert.strictEqual(b7.work[0], 'Now: the 12 months to August 2025 average ' + B.trend.now.text + ' compared with the 1995–2014 average.');
assert.strictEqual(b7.work[1], '2050, SSP2-4.5: +36' + NB + 'cm − ' + B.trend.now.text + ' = about 29' + NB + 'cm more than today. Approximate: it takes a 12-month average from a projection.');
assert.strictEqual(b7.work[2], "2020: the experts' middle estimate is +10" + NB + 'cm; the measured average for 2019 to 2021 is +2.9' + NB + 'cm. We plot the projection as published, so the gap of 7.3' + NB + 'cm shows on the chart.');
assert.strictEqual(b7.short.indexOf('+36' + NB + 'cm by 2050 under intermediate emissions (SSP2-4.5), from the IPCC'), 0);
assert.ok(/^For the future we use only published expert projections: the IPCC's sea level projections \(AR6, 2021\) at this tide gauge\. They use /.test(b7.words[0]), b7.words[0]);
assert.strictEqual(b7.words[2].indexOf("The experts' scenarios are low (SSP1-2.6), intermediate (SSP2-4.5), high (SSP3-7.0) and very high (SSP5-8.5) emissions. They are possible paths for the world's emissions, not predictions."), 0, b7.words[2]);
assert.strictEqual(b7.words[3], 'We never stretch the past trend into the future.');
assert.deepStrictEqual(b7.links.map(function (l) { return l.href; }), ['https://doi.org/10.5281/zenodo.6382554', B.trend.guidance.future_link.url]);
// inside (Lewes): step 7 starts closed, the plain check line; no flag
var L7 = steps(L.trend, L.series, pc2(L, 'Lewes, DE'))[6];
assert.ok(!L7.open && !/Check/.test(L7.short) && L7.work.some(function (x) { return /^Check: \+8\.4\scm is inside the experts' 2020 range for SSP2-4\.5 \(5th to 95th percentile \+4\.4 to \+18\scm\), so the record and the projection agree here\.$/.test(x); }), JSON.stringify(L7.work));
assert.strictEqual(futRead(L.trend, futOf(L.trend, null, false, TODAY), false).outside, '');
// QA (New Orleans): a check that rests on a fitted baseline (fewer than 15 of the 20 baseline years) says so next to it
var isChk = function (x) { return /^Check: /.test(x.text || x); };
var kf7 = steps(K.trend, K.series, pc2(K, 'Kolkata'))[6].work.filter(isChk)[0];
assert.strictEqual(K.trend.baseline.method, 'fitted');
assert.ok(/^Check: \S+\scm \(the baseline here is estimated from the trend\) is inside the experts' 2020 range for /.test(kf7), kf7);
assert.ok(!/estimated from the trend/.test(L7.work.filter(isChk)[0]) && !/estimated from the trend/.test(bad[0].text)); // observed baselines: no note
// the check's kinds (contract check.kind). null: the regenerated Mumbai has too few months in 2019-2021, and its latest
// 12 months end in 2010, before AR6 starts
var mbChk = steps(MB.trend, MB.series, pc2(MB, 'Mumbai'))[6].work.filter(isChk);
assert.ok(MB.trend.projection.check.kind === null && MB.trend.projection.check.latest === null);
assert.deepStrictEqual(mbChk, ["Check: not possible here. The record has fewer than 24 of the 36 months from 2019 to 2021, and its latest 12 months end before the experts' projections start in 2020."]);
assert.strictEqual(futRead(MB.trend, futOf(MB.trend, null, false, TODAY), false).outside, '');
// "latest 12 months" (QA B1: Mumbai with a record to December 2024): the server's check of `now` at its mid-year, as given
var M12 = copy(MB), n12 = { value: 135.4, units: 'mm', kind: '12-month mean', start: '2024-01', end: '2024-12', n: 12, text: '+14 cm', label: 'the 12 months to December 2024' };
M12.trend.now = n12; M12.trend.projection.readouts.now = n12;
M12.trend.projection.check = { observed_2019_2021: null, ar6_2020_p05: 9, ar6_2020_p95: 79, kind: 'latest 12 months', latest: { value: 135, year: 2024.5, ar6_p05: 22, ar6_p95: 106 }, inside: false };
var m7 = steps(M12.trend, M12.series, pc2(M12, 'Mumbai'))[6], mBad = m7.work.filter(function (x) { return x.bad; });
assert.strictEqual(futRead(M12.trend, futOf(M12.trend, null, false, TODAY), false).outside, "Here the measured level for the latest 12 months is outside the experts' range for that year. ");
assert.ok(m7.open && / · Check: outside the experts' range$/.test(m7.short), m7.short);
var MO = copy(MB); MO.trend.projection.check = { observed_2019_2021: null, ar6_2020_p05: 9, ar6_2020_p95: 79, kind: 'latest 12 months', latest: { value: 135, year: 2024.5, ar6_p05: 22, ar6_p95: 106 }, inside: false };
assert.ok(/ Measured levels here are already above the experts' range for recent years \(step 7\)\.$/.test(card(MO.trend, false, null, TODAY).r3f.line), card(MO.trend, false, null, TODAY).r3f.line); // 135 mm over 22 to 106
var MOB = copy(MO); MOB.trend.projection.check.latest.value = 10; // under the range: "below", from latest (not the 2019-2021 fields)
assert.ok(/ Measured levels here are below the experts' range for recent years \(step 7\)\.$/.test(card(MOB.trend, false, null, TODAY).r3f.line), card(MOB.trend, false, null, TODAY).r3f.line);
var BA = copy(B); BA.trend.projection.check.observed_2019_2021 = 200; // 2019-2021 over its 2020 range: "above"
assert.ok(/ already above the experts' range for recent years \(step 7\)\.$/.test(card(BA.trend, false, null, TODAY).r3f.line), card(BA.trend, false, null, TODAY).r3f.line);
MO.trend.projection.check.inside = true; // QA: the card says it only when the check is outside
assert.ok(!/experts' range/.test(card(MO.trend, false, null, TODAY).r3f.line), card(MO.trend, false, null, TODAY).r3f.line);
assert.ok(!/experts' range/.test(card(MB.trend, false, null, TODAY).r3f.line) && !/experts' range/.test(card(L.trend, false, null, TODAY).r3f.line)); // null; inside (Lewes)
assert.deepStrictEqual(mBad.map(function (x) { return x.text; }), ["Check: the latest 12 months (to December 2024) are +14" + NB + "cm, outside the experts' range for that year under SSP2-4.5 (5th to 95th percentile +2.2 to +11" + NB + "cm). Some tide gauges fall outside the experts' range, often because of earthquakes, land rising after the ice age, or a recent surge. Read the projection here with extra care."]);
assert.ok(m7.work.every(function (x) { return !/^2020: |2019 to 2021|not possible/.test(x.text || x); }), JSON.stringify(m7.work)); // no 2020 gap: these months are not 2020
assert.ok(m7.work.some(function (x) { return /^One 12-month “Now” can swing/.test(x); }));
M12.trend.projection.check.inside = true;
assert.deepStrictEqual(steps(M12.trend, M12.series, pc2(M12, 'Mumbai'))[6].work.filter(isChk), ["Check: the latest 12 months (to December 2024) are +14" + NB + "cm, inside the experts' range for that year under SSP2-4.5 (5th to 95th percentile +2.2 to +11" + NB + 'cm), so the record and the projection agree here.']);
assert.strictEqual(futRead(M12.trend, futOf(M12.trend, null, false, TODAY), false).outside, '');
clean(M12, pc2(M12, 'Mumbai'));
// step 4: the trend line's level stays; the card's "Now" is explained in step 7
var b4 = steps(B.trend, B.series, b2)[3].work;
assert.ok(/ The card’s “Now” is the measured average of the last 12 months instead \(step 7\)\.$/.test(b4[1]) && b4.length === 2, JSON.stringify(b4));
// step 9: the projection's source, its citations, and its own CSV
var b9 = steps(B.trend, B.series, b2)[8];
assert.ok(/; future from IPCC AR6$/.test(b9.short) && b9.csv && b9.csvFut);
assert.ok(b9.words[0].list.some(function (x) { return x.text === 'Future: IPCC AR6 sea level projections (Garner et al. 2021), doi:10.5281/zenodo.6382554, version 20210809, CC BY 4.0. ' && x.link.href === 'https://doi.org/10.5281/zenodo.6382554'; }));
assert.deepStrictEqual(b9.words[1].cite, BP.source.citation);
assert.strictEqual(b9.words[0].list[1].text, 'World figure: NASA Global Mean Sea Level Trend from Integrated Multi-Mission Ocean Altimeters, Version 5.2, doi:10.5067/GMSLM-TJ152. Retrieved 22 November 2026. ');
assert.strictEqual(b9.words[1].ack, 'Acknowledgement: ' + BP.source.acknowledgement);
// "What experts project": the drivers for SSP2-4.5 only, every decade for the chosen scenario
var bC = futCard(B.trend, b2);
assert.strictEqual(bC.title, 'What experts project for New York, NY');
assert.strictEqual(bC.sub, 'IPCC AR6 sea level projections at this tide gauge, compared with the 1995–2014 average. Source: ');
// review: "at this tide gauge" when the AR6 gauge is under 1 km away or, for a PSMSL record, has the record's own id;
// otherwise its name and distance (never "0 km from this one")
var BF = copy(B); BF.trend.projection.location.km = 2.5;
assert.strictEqual(futCard(BF.trend, b2).sub, 'IPCC AR6 sea level projections at the tide gauge New York (The Battery), 2.5 km from this one, compared with the 1995–2014 average. Source: ');
assert.ok(steps(BF.trend, BF.series, b2)[6].words[0].indexOf(' (AR6, 2021) at the tide gauge New York (The Battery), 2.5 km from this one. ') > 0);
var KP = copy(K), kp2 = pc2(KP, 'Kolkata');
assert.ok(futOf(KP.trend, null, false, TODAY).same && /^IPCC AR6 sea level projections at this tide gauge, /.test(futCard(KP.trend, kp2).sub)); // 0 km
KP.trend.projection.location.km = 1.2; // the same id (543, from the station page), over 1 km: still this gauge
assert.ok(futOf(KP.trend, null, false, TODAY).same && steps(KP.trend, KP.series, kp2)[6].words[0].indexOf(' at this tide gauge. ') > 0);
KP.trend.projection.location.id = 544; // a nearby AR6 gauge
assert.ok(!futOf(KP.trend, null, false, TODAY).same && futCard(KP.trend, kp2).sub.indexOf(' at the tide gauge DIAMOND HARBOUR, 1.2 km from this one, ') > 0);
assert.ok(all(K, pc2(K, 'Kolkata')).every(function (x) { return !/ 0(\.0)? km from this/.test(x); }));
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
  '# Projection location: tide gauge New York (The Battery), 0.4 km away', '# Baseline: the 1995–2014 average; levels in mm as published, not shifted to meet the observations',
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
var RE = copy(B), REG = 'IPCC AR6 has no projection at a tide gauge close enough, so this is its estimate for the surrounding 1° area: the land motion in it is AR6\'s regional estimate, and local sinking may differ and may be faster in places, so check the ground at the site.';
RE.trend.projection.location = { kind: 'regional estimate', id: 1000000123, name: '1° area around 30°N, 90°W', km: 12.3, note: REG };
var rec2 = pc2(RE, 'New Orleans, LA'), rfx = futOf(RE.trend, null, false, TODAY);
assert.ok(card(RE.trend, false, null, TODAY).r3f.line.endsWith('. Regional estimate: local sinking may differ.' + OUT));
assert.strictEqual(futRead(RE.trend, rfx, false).regional, REG);
assert.strictEqual(chartText(RE.trend, RE.series, rec2).fu.link.text, 'IPCC AR6 regional estimate ↗');
assert.strictEqual(chartText(RE.trend, RE.series, rec2).fu.tail, ' for the 1° area around 30°N, 90°W.');
assert.strictEqual(futCard(RE.trend, rec2).sub, 'IPCC AR6 regional estimate for the 1° area around 30°N, 90°W (12.3 km from this gauge), compared with the 1995–2014 average. Source: ');
assert.strictEqual(futCard(RE.trend, rec2).parts[5].name, 'Land rising or sinking here (regional estimate)');
assert.ok(steps(RE.trend, RE.series, rec2)[6].words[0].indexOf('(AR6, 2021) for the 1° area around 30°N, 90°W. ' + REG + ' They use the same 1995–2014 average') > 0); // the server's note, as given
assert.strictEqual(csvFuture(RE.trend, rec2).text.split('\n')[4], '# Projection location: regional estimate for the 1° area around 30°N, 90°W; ' + REG.replace(/"/g, "'"));
clean(RE, rec2);
// an old record (Mumbai ends in 2010): "Latest" and "in 2010" for "Now" and "today"
var MBk = card(MB.trend, false, null, TODAY), mfx = futOf(MB.trend, null, false, TODAY);
assert.ok(mfx.old && MBk.r1.label === 'Latest, compared with the 1995–2014 average', MBk.r1.label);
var MBY = copy(MB); MBY.trend.projection.readouts.more_than_today.text = 'about 18 cm more than in 2010'; // the server's text for an old record
assert.ok(/ About 18\scm more than in 2010\.$/.test(card(MBY.trend, false, null, TODAY).r3f.line), card(MBY.trend, false, null, TODAY).r3f.line);
assert.ok(/ more than in 2010\.$/.test(card(MB.trend, false, { ssp: 'ssp585' }, TODAY).r3f.line)); // another scenario: computed, "in 2010"
assert.ok(/^Latest: the 12 months to December 2010 average /.test(steps(MB.trend, MB.series, pc2(MB, 'Mumbai'))[6].work[0]));
assert.ok(!futOf(B.trend, null, false, 2025 * 12 + 7 + 24).old && futOf(B.trend, null, false, 2025 * 12 + 7 + 25).old);
// now null: no Now dot or "more" sentence anywhere; step 7 says why
var BNN = copy(B); BNN.trend.now = null; BNN.trend.projection.readouts.now = null; BNN.trend.projection.readouts.more_than_today = null;
var nnk = card(BNN.trend, false, null, TODAY), nn7 = steps(BNN.trend, BNN.series, pc2(BNN, 'X'))[6];
assert.ok(nnk.r1 === null && nnk.r3f.line === 'SSP2-4.5, IPCC AR6. Likely +27 to +46' + NB + 'cm.' + OUT, nnk.r3f.line);
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
// the default scenario, in metric, prints by_2050.text and more_than_today.text as given (only the space before cm is a
// no-break space); another scenario, or inches, computes them with cm()
var BG = copy(B); BG.trend.projection.readouts.by_2050.text = '+37 cm (likely +28 to +47 cm)'; BG.trend.projection.readouts.more_than_today.text = 'about 30 cm more than today';
var bgc = pc2(BG, 'X'), bgfx = futOf(BG.trend, null, false, TODAY), bgk = card(BG.trend, false, null, TODAY).r3f, bgR = futRead(BG.trend, bgfx, false), bg7 = steps(BG.trend, BG.series, bgc)[6];
assert.strictEqual(bgk.value, '+37' + NB + 'cm');
assert.strictEqual(bgk.line, 'SSP2-4.5, IPCC AR6. Likely +28 to +47' + NB + 'cm. About 30' + NB + 'cm more than today.' + OUT);
assert.strictEqual(bgR.b + bgR.rest, '+37' + NB + 'cm by 2050 under intermediate emissions (SSP2-4.5): likely range (about 2 in 3 chance) +28 to +47' + NB + 'cm. That is about 30' + NB + 'cm more than today.');
assert.ok(bg7.short.indexOf('+37' + NB + 'cm by 2050') === 0 && bg7.words[1].indexOf(' is +37' + NB + 'cm. Their likely range (about 2 in 3 chance) is +28 to +47' + NB + 'cm, ') > 0, bg7.words[1]);
assert.ok(bg7.work.indexOf('2050, SSP2-4.5: +37' + NB + 'cm − ' + B.trend.now.text + ' = about 30' + NB + 'cm more than today. Approximate: it takes a 12-month average from a projection.') >= 0);
assert.strictEqual(card(BG.trend, false, { ssp: 'ssp585' }, TODAY).r3f.value, cmv(s585.p50[3])); // not the default: computed
assert.strictEqual(card(BG.trend, true, null, TODAY).r3f.value, cmv(358, true)); // inches: computed
var MG = copy(MB); MG.trend.projection.readouts.more_than_today.text = 'about 99 cm more than today'; // as given: the page never rewrites "today"
assert.ok(/ About 99\scm more than today\.$/.test(card(MG.trend, false, null, TODAY).r3f.line), card(MG.trend, false, null, TODAY).r3f.line);
// QA (New Orleans): a fit trimmed of sparse early readings; the chart's title and summary start at the first year drawn,
// the trend line says where it starts (legend and summary)
var NO = copy(B); NO.trend.record.trimmed_from = '1920-01'; NO.trend.period.start = NO.trend.fit.start = '2005-01';
var noT = chartText(NO.trend, NO.series, pc2(NO, 'New Orleans, LA'));
assert.strictEqual(noT.title, 'Sea level at New Orleans, LA (The Battery), 1920 to 2100');
assert.ok(noT.summary.indexOf('Sea level at New Orleans, LA (The Battery), January 1920 to ') === 0 && noT.summary.indexOf(' The trend line, from January 2005, rises ') > 0, noT.summary);
assert.strictEqual(noT.legend.trend, 'Trend line, from 2005');
assert.strictEqual(bT2.legend.trend, 'Trend line'); // not trimmed: no note
var NX = copy(NO); NX.trend.baseline.projection_axis = false; // PR1's chart: the same title rule
var nxT = chartText(NX.trend, NX.series, pc2(NX, 'X'));
assert.ok(nxT.title === 'Sea level at X (The Battery), 1920 to 2025' && / The trend line, from January 2005, rises /.test(nxT.summary), nxT.title + ' | ' + nxT.summary);
clean(NO, pc2(NO, 'X'));
// inches: every projection number in inches
var bik = card(B.trend, true, null, TODAY).r3f;
assert.ok(/^\+14 in$/.test(sp(bik.value)) && sp(bik.line).endsWith(' About 11 in more than today.' + OUT), bik.value + ' | ' + bik.line);

// ---------- PR3: CMIP6 windows for air temperature, hottest day and rain (web/design/15-cmip6.md) ----------
var CMF = ['princeton_air_temp', 'delhi_hottest_day', 'chennai_rain', 'seattle_air_temp_no_change'];
var NOTE = "These are the climate models' raw results. The IPCC's assessed warming, which also uses past observations, is a little lower for the world as a whole.";
var CP = load('princeton_air_temp'), CD = load('delhi_hottest_day'), CC = load('chennai_rain'), CR3 = load('riverside_no_baseline');
// the contract (QA of PR3): no "more than today" for hottest day, as for rain; set here so the tests hold before and after
// the server's regenerated fixture lands
CD.trend.projection.readouts.more_than_today = null;
var cpc = pc2(CP, 'Princeton, NJ'), cdc = pc2(CD, 'Delhi'), ccc = pc2(CC, 'Chennai');
var cpx = futOf(CP.trend, null, false, TODAY), cdx = futOf(CD.trend, null, false, TODAY), ccx = futOf(CC.trend, null, false, TODAY);
assert.ok(cpx.cm && ccx.cm && cpx.rain === false && ccx.rain === true && modeOf(CP.trend, CP.series, cpx) === 'both');
// §2 the card's R3, intermediate emissions: the server's numbers, rounded as by_2050.text rounds them (not "−2.9 to +24%")
assert.deepStrictEqual(card(CP.trend, false, null, TODAY).r3f, { label: 'Around 2050, intermediate emissions', value: '+1.9' + NB + '°C', per: '',
  line: 'SSP2-4.5, IPCC AR6 Atlas. Range across models +1.2 to +2.3' + NB + '°C. About 1.7' + NB + '°C more than today.' });
assert.deepStrictEqual(card(CD.trend, false, null, TODAY).r3f, { label: 'Around 2050, intermediate emissions', value: '+1.3' + NB + '°C', per: '',
  line: 'SSP2-4.5, IPCC AR6 Atlas. Range across models +0.5 to +1.8' + NB + '°C.' });
// hottest day: no "more than today" anywhere, in any scenario or unit (the readout line, step 7; step 4 keeps PR1's "Now" line)
[[null, false], [null, true], [{ ssp: 'ssp585' }, false], [{ ssp: 'ssp126' }, true]].forEach(function (a) {
  var hx = futOf(CD.trend, a[0], a[1], TODAY), hR = futRead(CD.trend, hx, a[1]), hS = steps(CD.trend, CD.series, pc2(CD, 'Delhi', a[1], a[0]));
  assert.ok(hx.more === '' && !/than today|That is/.test(card(CD.trend, a[1], a[0], TODAY).r3f.line + hR.rest), hR.rest);
  assert.ok(hS[6].work.every(function (x) { return !/^(Now|Latest): | − /.test(x); }), JSON.stringify(hS[6].work));
  assert.strictEqual(hS[6].work[hS[6].work.length - 1], "No “more than today” for the hottest day of the month: one year's hottest days swing more than this change.");
  assert.ok(/, not a point on the line\.$/.test(hS[3].work.slice(-1)[0]) && !/\(step 7\)/.test(hS[3].work.join(' ')), JSON.stringify(hS[3].work));
  clean(CD, pc2(CD, 'Delhi', a[1], a[0]));
});
assert.ok(/ Now: \+0\.51 °C \(the 12 months to December 2025\)\. /.test(sp(chartText(CD.trend, CD.series, cdc).summary))); // the Now dot stays
var CDN = copy(CD); CDN.trend.now = null; // no "Now" either: no line about it
assert.ok(steps(CDN.trend, CDN.series, cdc)[6].work.every(function (x) { return !/more than today/.test(x); }));
assert.deepStrictEqual(card(CC.trend, false, null, TODAY).r3f, { label: 'Around 2050, intermediate emissions', value: '+11%', per: 'of the usual yearly rain',
  line: 'SSP2-4.5, IPCC AR6 Atlas. Range across models −3 to +24%. Models disagree on wetter or drier.' });
// QA: the default scenario in metric equals by_2050.text and more_than_today.text, for every CMIP6 fixture
CMF.map(load).forEach(function (d) {
  var p = d.trend.projection, ro = p.readouts, fx = futOf(d.trend, null, false, TODAY), S = fx.S;
  assert.strictEqual(sp(fx.v(S.p50[1]) + ' (range across climate models ' + fx.rng(S.p10[1], S.p90[1]) + ')'), ro.by_2050.text);
  assert.strictEqual(sp(fx.more), ro.more_than_today ? ro.more_than_today.text : '');
  assert.strictEqual(!!fx.dis(1), !!ro.by_2050.disagree);
  [[false, null], [true, null], [false, { ssp: 'ssp585' }], [false, { ssp: 'ssp126', low: true }]].forEach(function (a) { clean(d, pc2(d, 'X', a[0], a[1])); });
});
// Riverside: no 1995-2014 average, so no projection: PR1's card, chart and step 7, with the server's why
assert.ok(futOf(CR3.trend, null, false, TODAY) === null && card(CR3.trend, false, null, TODAY).r3f === null);
assert.strictEqual(card(CR3.trend, false, null, TODAY).r3, "This record has no 1995–2014 average to start the projection from, so we don't show one.");
assert.deepStrictEqual(steps(CR3.trend, CR3.series, pc2(CR3, 'Riverside'))[6].words, [CR3.trend.projection.why, NO_FUTURE]);
var CNV = copy(CP); CNV.trend.projection = { available: false, why: 'The climate models have no value for this place.' };
assert.strictEqual(card(CNV.trend, false, null, TODAY).r3, 'The climate models have no value for this place.');
assert.ok(chartText(CNV.trend, CNV.series, cpc).title === 'Air temperature at Princeton, NJ, 1981 to 2025' && /^Seasons removed/.test(chartText(CNV.trend, CNV.series, cpc).sub));
// another scenario: its own arrays, "more than today" worked out from them (2.56 − 0.239 = 2.3)
var c585 = card(CP.trend, false, { ssp: 'ssp585' }, TODAY).r3f;
assert.deepStrictEqual([c585.label, c585.value, c585.line], ['Around 2050, very high emissions', '+2.6' + NB + '°C', 'SSP5-8.5, IPCC AR6 Atlas. Range across models +1.7 to +3.1' + NB + '°C. About 2.3' + NB + '°C more than today.']);
// §1.1 °F: changes × 1.8 (never +32), rounded once from the API's numbers; rain stays %
assert.deepStrictEqual(card(CP.trend, true, null, TODAY).r3f, { label: 'Around 2050, intermediate emissions', value: '+3.4' + NB + '°F', per: '',
  line: 'SSP2-4.5, IPCC AR6 Atlas. Range across models +2.2 to +4.2' + NB + '°F. About 3.0' + NB + '°F more than today.' }); // 1.89, 1.2, 2.31, 1.89 − 0.239
assert.deepStrictEqual(card(CC.trend, true, null, TODAY).r3f, card(CC.trend, false, null, TODAY).r3f);
assert.strictEqual(futOf(CP.trend, null, true, TODAY).v(-0.04), MN + '0.072' + NB + '°F');
// §1.2 the readout line, the sub-line and the hot-model note (the server's text, under the readout; rain has none)
var cpR = futRead(CP.trend, cpx, false), ccR = futRead(CC.trend, ccx, false);
assert.strictEqual(cpR.b + cpR.rest, '+1.9' + NB + '°C around 2050 under intermediate emissions (SSP2-4.5): the 2041–2060 average, with a range across climate models (10th–90th percentile) of +1.2 to +2.3' + NB + '°C. That is about 1.7' + NB + '°C more than today.');
assert.strictEqual(cpR.sub, "From 34 climate models, for the 1° grid cell around this place (its centre is 21 km away). A 1° grid cell is about 100 km wide, so hills or a coast nearby can make the change here differ. It is the change in the year's average temperature, not in summer alone.");
assert.strictEqual(ccR.b + ccR.rest, '+11% around 2050 under intermediate emissions (SSP2-4.5): the 2041–2060 average yearly rain, with a range across climate models (10th–90th percentile) of −3 to +24%. Models disagree on wetter or drier: 75% agree on the direction, under the 80% the IPCC Atlas asks for.');
assert.ok(/It is the change in each month's hottest day, averaged over the year, not in the year's single hottest day\.$/.test(futRead(CD.trend, cdx, false).sub));
assert.ok(cpR.note === NOTE && CP.trend.projection.models_note === NOTE && ccR.note === '' && cpR.vs === '' && cpR.regional === '');
var CNT = copy(CP); CNT.trend.projection.models_note = 'A different note.'; // never written in: the server's words
var cnS = steps(CNT.trend, CNT.series, cpc)[7];
assert.ok(futRead(CNT.trend, futOf(CNT.trend, null, false, TODAY), false).note === 'A different note.' && cnS.words[0].list.indexOf('A different note.') >= 0);
CNT.trend.projection.models_note = null;
assert.ok(futRead(CNT.trend, futOf(CNT.trend, null, false, TODAY), false).note === '' && all(CNT, cpc).every(function (x) { return x.indexOf(NOTE) < 0; }));
// step 8: the note is a thing to keep in mind (temperature and hottest day), never for rain
var cp8 = steps(CP.trend, CP.series, cpc)[7];
assert.deepStrictEqual(cp8.words[0].list, CP.trend.caveats.concat([NOTE, 'This shows whether air temperature changed here. It doesn\'t say why.']));
assert.strictEqual(cp8.short, CP.trend.caveats[0] + ' And 2 more');
assert.ok(steps(CC.trend, CC.series, ccc)[7].words[0].list.indexOf(NOTE) < 0);
// §1.3 records against models: opposite signs, not disagreeing; both stated, no cause
var CDF = copy(CD); CDF.trend.verdict = 'falling';
assert.strictEqual(futRead(CDF.trend, futOf(CDF.trend, null, false, TODAY), false).vs, 'Here the records show the hottest day of the month falling, while the climate models project it rising by 2041–2060. The records describe this place since 1981; the models give a 20-year average for a grid cell about 100 km wide under one emissions path. We show both as they are.');
var CCF = copy(CC); CCF.trend.projection.scenarios[1].p50[1] = -5; CCF.trend.projection.scenarios[1].disagree[1] = false;
assert.ok(/^Here the records show more rain, while the climate models project less rain by 2041–2060\. /.test(futRead(CCF.trend, futOf(CCF.trend, null, false, TODAY), false).vs));
CCF.trend.projection.scenarios[1].disagree[1] = true; // models disagree: no flag
assert.strictEqual(futRead(CCF.trend, futOf(CCF.trend, null, false, TODAY), false).vs, '');
clean(CDF, pc2(CDF, 'Delhi'));
// §5 the nearest land cell and a mostly-ocean cell: the sub-line, the flag (the server's note), step 7, the CSV
var NL = 'The place\'s own grid cell is mostly ocean, so this uses the nearest land cell.', CN = copy(CC);
CN.trend.projection.location = { kind: 'nearest land cell', lat: 13.5, lon: 79.5, km: 88, land_pct: 81, note: NL };
var cnR = futRead(CN.trend, futOf(CN.trend, null, false, TODAY), false), cnc = pc2(CN, 'Chennai');
assert.ok(/^From 32 climate models, for the nearest land grid cell \(its centre is 88 km away\)\. /.test(cnR.sub) && cnR.regional === NL);
assert.strictEqual(chartText(CN.trend, CN.series, cnc).fu.tail, ' for the nearest land grid cell.');
assert.strictEqual(steps(CN.trend, CN.series, cnc)[6].words[2], 'Grid cell: the nearest land cell (13.5°N, 79.5°E, 81% land), 88 km away. ' + NL);
assert.strictEqual(csvFuture(CN.trend, cnc).text.split('\n')[5], '# Grid cell: nearest land cell lat 13.5, lon 79.5, 88 km from the place, 81% land; ' + NL.replace(/'/g, "'"));
CN.trend.projection.location = { kind: 'regional estimate (mostly ocean cell)', lat: 13.5, lon: 80.5, km: 40, land_pct: 30, note: "The models' grid cell here is mostly ocean, which warms less than land." };
assert.ok(/, for the 1° grid cell around this place, which is mostly ocean\. /.test(futRead(CN.trend, futOf(CN.trend, null, false, TODAY), false).sub));
assert.strictEqual(chartText(CN.trend, CN.series, cnc).fu.tail, ' for the 1° grid cell here.');
assert.strictEqual(steps(CN.trend, CN.series, cnc)[6].words[2], "Grid cell: the 1° cell around this place (30% land). The models' grid cell here is mostly ocean, which warms less than land.");
clean(CN, cnc);
// §5 a window with no value: no box, "no value" in the readout and the table, R3 "—"
var CX = copy(CP), cxs = CX.trend.projection.scenarios[1]; cxs.p10[1] = cxs.p50[1] = cxs.p90[1] = null;
var cxx = futOf(CX.trend, null, false, TODAY);
assert.deepStrictEqual(card(CX.trend, false, null, TODAY).r3f, { label: 'Around 2050, intermediate emissions', value: '—', per: '', line: 'SSP2-4.5, IPCC AR6 Atlas. No value for 2041–2060 here.' });
assert.strictEqual(winRead(cxx, 1), '2041–2060: the models have no value here.');
assert.deepStrictEqual(cmTable(cxx).rows[1].cells.slice(0, 3), ['2041–2060', 'no value', 'no value']);
assert.deepStrictEqual(cmModel(cxx, id1).sel[1], { m0: 2041 * 12, m1: 2061 * 12, lo: null, mid: null, hi: null, dis: false });
// §5 now null: no "more" sentence, no Now line in step 7
var CNN = copy(CP); CNN.trend.now = null; CNN.trend.projection.readouts.now = null; CNN.trend.projection.readouts.more_than_today = null;
assert.strictEqual(card(CNN.trend, false, null, TODAY).r3f.line, 'SSP2-4.5, IPCC AR6 Atlas. Range across models +1.2 to +2.3' + NB + '°C.');
assert.ok(steps(CNN.trend, CNN.series, pc2(CNN, 'X'))[6].work.every(function (x) { return !/^Now/.test(x); }));
clean(CNN, pc2(CNN, 'X'));
// §1.4, §1.5 chart geometry: each of S's boxes spans exactly its 20 years (1 January to 1 January), p10 to p90; nothing
// between 2061 and 2081; no box joins another; the y-axis span is every scenario's p10 to p90, the same whichever is chosen
var gm = cmModel(cpx, id1), cps = CP.trend.projection.scenarios[1];
assert.deepStrictEqual(gm.sel.map(function (b) { return [b.m0 / 12, b.m1 / 12, b.lo, b.mid, b.hi]; }),
  [[2021, 2041, cps.p10[0], cps.p50[0], cps.p90[0]], [2041, 2061, cps.p10[1], cps.p50[1], cps.p90[1]], [2081, 2101, cps.p10[2], cps.p50[2], cps.p90[2]]]);
assert.ok(gm.wins.every(function (w) { return w.m1 <= 2061 * 12 || w.m0 >= 2081 * 12; }) && gm.sel.every(function (b, i) { return !i || b.m0 >= gm.sel[i - 1].m1; }));
assert.ok(gm.others.length === 3 && gm.others.every(function (o) { return o.S !== cpx.S && o.mids.length === 3; }) && gm.k === 2);
var cspan = function (sel) { return cmModel(futOf(CP.trend, sel, false, TODAY), id1).span.slice().sort(function (a, b) { return a - b; }); };
assert.deepStrictEqual(cspan({ ssp: 'ssp126' }), cspan({ ssp: 'ssp585' }));
assert.strictEqual(Math.max.apply(null, cspan(null)), 6.79); // very high's 2081-2100 p90 sets the top, whatever is chosen
// rain's disagreeing windows are dashed (S's own flags)
assert.deepStrictEqual(cmModel(ccx, id1).sel.map(function (b) { return b.dis; }), [true, true, false]);
// §1.6 temperature: a point a year (9 regular months), from the first January; a year short of that breaks the line
var CY9 = copy(CP), y90 = CY9.series.times.indexOf('1990-01');
for (var k9 = 0; k9 < 4; k9++) CY9.series.anomaly.values[y90 + k9] = null;
var yln = yearLine(chartModel(CY9.trend, CY9.series, false));
assert.ok(yln.x0 === 1981 * 12 && yln.ms.length === 45 && yln.ms[9] === 1990 * 12 + 5.5 && yln.ys[9] === null && yln.ys[10] != null && yln.pre.every(function (x) { return !x; }));
// §1.10 the readouts: a year, then each window
assert.strictEqual(cmYear(CP.trend, cpx, 2025, 0.239), "2025: +0.24" + NB + "°C, the year's average, compared with the 1995–2014 average.");
assert.strictEqual(winRead(cpx, 1), '2041–2060, intermediate emissions (SSP2-4.5): +1.9' + NB + '°C, range across climate models +1.2 to +2.3' + NB + '°C, 34 models. Others: Low +1.6' + NB + '°C, High +2.0' + NB + '°C, Very high +2.6' + NB + '°C.');
assert.strictEqual(winRead(ccx, 0), '2021–2040, intermediate emissions (SSP2-4.5): +3.5%, range across climate models −8 to +20%, 32 models. Others: Low +7.2%, High +5.1%, Very high +4.7%. Models disagree on wetter or drier (66% agree).');
assert.ok(!/disagree/.test(winRead(ccx, 2)));
// §1.11 the text summary, which is also the chart's aria-label: the result with its numbers
var cpT = chartText(CP.trend, CP.series, cpc), ccT = chartText(CC.trend, CC.series, ccc);
assert.strictEqual(cpT.title, 'Air temperature at Princeton, NJ, 1981 to 2100');
assert.strictEqual(sp(cpT.summary), 'Air temperature at Princeton, NJ, January 1981 to December 2025, and climate-model projections for 2021–2040, 2041–2060 and 2081–2100, all compared with the 1995–2014 average. '
  + 'The trend line rises 0.37 °C per decade (95% range +0.24 to +0.50 °C per decade). Now: +0.24 °C (the 12 months to December 2025). '
  + 'Middle estimates for 2081–2100: low emissions (SSP1-2.6) +1.6 °C, intermediate emissions (SSP2-4.5) +2.9 °C, high emissions (SSP3-7.0) +4.3 °C, very high emissions (SSP5-8.5) +5.4 °C. '
  + 'Boxed: the range across climate models for intermediate emissions, +2.0 to +3.7 °C in 2081–2100. Verdict: rising, very clear.');
// rain (domain review): the yearly totals' own years, then the 12 months "Now" covers, so the last dot and "Now" can differ
assert.strictEqual(ccT.summary.indexOf('Rain at Chennai, yearly totals 1981 to 2025, and ' + CC.trend.now.label + ', with climate-model projections for 2021–2040, 2041–2060 and 2081–2100, all compared with the 1995–2014 average. The trend line rises '), 0, ccT.summary);
assert.ok(/ Boxed: the range across climate models for intermediate emissions, \+2 to \+35% in 2081–2100\. Models disagree on wetter or drier for 2021–2040 and 2041–2060\. Verdict: rising, clear\.$/.test(ccT.summary), ccT.summary);
var CCN = copy(CC); CCN.trend.now = null;
assert.strictEqual(chartText(CCN.trend, CCN.series, ccc).summary.indexOf('Rain at Chennai, yearly totals 1981 to 2025, and climate-model projections for '), 0);
assert.strictEqual(cpT.sub, "Each dot is one year's average, compared with the 1995–2014 average.");
assert.deepStrictEqual(cpT.fu, { link: { text: 'IPCC AR6 Atlas, CMIP6 ↗', href: 'https://digital.csic.es/handle/10261/332744' }, tail: ' for the 1° grid cell around it.' });
assert.ok(cpT.legend.monthly === "Each year's average" && cpT.ytitle === '°C compared with the 1995–2014 average' && ccT.ytitle === "Each year's rain, % above or below the 1995–2014 average");
assert.strictEqual(cpT.hint, 'Hover, tap or use the arrow keys to read a year, then each 20-year period after the record ends.');
assert.deepStrictEqual(cpT.cols, ['Month', 'Air temperature (°C)', 'Compared with the 1995–2014 average (°C)', 'Note']); // the table keeps every month
// §1.12 the projections table
assert.deepStrictEqual(cmTable(cpx), { caption: 'Intermediate emissions (SSP2-4.5), IPCC AR6 Atlas (CMIP6), compared with the 1995–2014 average.',
  cols: ['Years', 'Middle estimate', 'Range across climate models (10th–90th percentile)', 'Models'],
  rows: [{ hl: false, cells: ['2021–2040', '+1.1' + NB + '°C', '+0.6 to +1.5' + NB + '°C', '34'] }, { hl: true, cells: ['2041–2060', '+1.9' + NB + '°C', '+1.2 to +2.3' + NB + '°C', '34'] },
    { hl: false, cells: ['2081–2100', '+2.9' + NB + '°C', '+2.0 to +3.7' + NB + '°C', '34'] }] });
assert.deepStrictEqual(cmTable(ccx).rows.map(function (r) { return r.cells[4]; }), ['66%, disagree', '75%, disagree', '91%']);
assert.strictEqual(cmTable(ccx).cols[4], 'Models agreeing on wetter or drier');
// agreement at 80% or more everywhere: no "disagree" sentence anywhere (the caveat and step 7's rule are not about this place)
var CA = copy(CC); CA.trend.projection.scenarios.forEach(function (x) { x.agree = [0.9, 0.85, 0.95]; x.disagree = [false, false, false]; }); CA.trend.projection.readouts.by_2050.disagree = false;
all(CA, pc2(CA, 'Chennai')).forEach(function (x) { assert.ok(!/disagree/i.test(x) || /Climate models disagree more about rain/.test(x) || /Under 80%, we say they disagree\.$/.test(x) || /^# Bhoomi: /.test(x), x); }); // the CSV: its column name
assert.ok(!/disagree/.test(steps(CA.trend, CA.series, pc2(CA, 'Chennai'))[6].short) && cmTable(futOf(CA.trend, null, false, TODAY)).rows.every(function (r) { return !/disagree/.test(r.cells[4]); }));
// §4 step 7 "What comes next": the delta method, the cell, the models, the range's name, the caveat, the working
var cp7 = steps(CP.trend, CP.series, cpc)[6], cc7 = steps(CC.trend, CC.series, ccc)[6];
assert.ok(!cp7.open);
assert.strictEqual(cp7.short, '+1.9' + NB + '°C around 2050 under intermediate emissions (SSP2-4.5), from 34 climate models');
assert.strictEqual(cc7.short, '+11% around 2050 under intermediate emissions (SSP2-4.5), from 32 climate models; models disagree on wetter or drier');
assert.deepStrictEqual(cp7.words, ['Future values come only from the climate models (CMIP6) behind the IPCC AR6 Atlas.',
  "We add the models' change to this place's own 1995–2014 average (the delta method), so raw model values never sit next to the records.",
  'Grid cell: the 1° cell around this place (40.5°N, 74.5°W, 100% land), its centre 21 km away.',
  '34 models. The box is the range across climate models (10th–90th percentile): 8 in 10 models fall inside it.',
  'A 1° grid cell is about 100 km wide, so hills or a coast nearby can make the change here differ.',
  "Scenarios are possible paths for the world's emissions, not predictions. We never stretch the past trend into the future."]);
assert.deepStrictEqual(cp7.work.map(sp), ["This place's 1995–2014 average from NASA POWER: 11.9 °C (step 3). On the chart that is 0.", // now.text keeps the server's space
  "Models' change, 2041–2060, SSP2-4.5: +1.9 °C (range +1.2 to +2.3 °C).", 'So the 2041–2060 average sits at +1.9 °C on the chart, where 0 is that average.',
  'Now: +0.24 °C (the 12 months to December 2025). +1.9 °C − +0.2 °C = about 1.7 °C more than today. Approximate: a 12-month average against a 20-year one.']);
// review: the working's subtraction adds up at the printed digits. Both numbers are printed at the result's decimals
// (by_2050.p50 and now.value, as sea level does in whole mm); the card's R3 keeps its own rounding.
function subtracts(d, sel, imp) {
  var w = steps(d.trend, d.series, pc2(d, 'X', imp, sel))[6].work.filter(function (x) { return /^(Now|Latest): /.test(x); })[0];
  var m = sp(w).match(/\. ([+−]?[\d.]+) °[CF] − \(?([+−]?[\d.]+) °[CF]\)? = about ([\d.]+) °[CF] (more|less) than /);
  assert.ok(m, w);
  var a = num(m[1]), b = num(m[2]), c = num(m[3]), dc = decimals(m[3]);
  assert.strictEqual(Number((a - b).toFixed(dc)) * (m[4] === 'less' ? -1 : 1), c, w);
  return sp(w);
}
// Delhi's numbers (1.26 − 0.5071 = 0.75), as air temperature: the only measurement with "more than today" now
var CDA = copy(CD); CDA.trend.variable = 'air_temp'; CDA.trend.projection.readouts.more_than_today = { value: 0.75, text: 'about 0.75 °C more than today', approximate: true };
assert.strictEqual(subtracts(CDA, null, false), 'Now: +0.51 °C (the 12 months to December 2025). +1.26 °C − +0.51 °C = about 0.75 °C more than today. Approximate: a 12-month average against a 20-year one.');
assert.ok(subtracts(CP, null, false).indexOf(' +1.9 °C − +0.2 °C = about 1.7 °C more than today.') > 0);
assert.ok(subtracts(CP, null, true).indexOf(' +3.4 °F − +0.4 °F = about 3.0 °F more than today.') > 0); // °F: × 1.8 first, then rounded
assert.ok(subtracts(load('seattle_air_temp_no_change'), null, false).indexOf(' +1.6 °C − (−0.5 °C) = about 2.1 °C more than today.') > 0); // a negative "Now" in brackets
CMF.map(load).filter(function (d) { return d.trend.projection.readouts.more_than_today; }).forEach(function (d) { // where the server gives one
  [[null, false], [null, true], [{ ssp: 'ssp126' }, false], [{ ssp: 'ssp585' }, true]].forEach(function (a) { subtracts(d, a[0], a[1]); }); });
// rounding at the result's decimals can miss by one digit (1.25 → 1.3, 0.04 → 0.0, but 1.25 − 0.04 = 1.2): one decimal more
var CM1 = copy(CP); CM1.trend.projection.scenarios[1].p50[1] = 1.25; CM1.trend.now.value = 0.04; CM1.trend.now.text = '+0.040 °C';
CM1.trend.projection.readouts.more_than_today = { value: 1.2, text: 'about 1.2 °C more than today', approximate: true };
assert.ok(subtracts(CM1, null, false).indexOf(' +1.25 °C − +0.04 °C = about 1.2 °C more than today.') > 0);
assert.strictEqual(card(CDA.trend, false, null, TODAY).r3f.line, 'SSP2-4.5, IPCC AR6 Atlas. Range across models +0.5 to +1.8' + NB + '°C. About 0.75' + NB + '°C more than today.'); // the card: its own rounding
// QA B1: the label over S's 2041-2060 box moves up past another scenario's median that would run under it. Princeton,
// intermediate: very high's +2.56 sits just over the box's +2.31 top (32.6 px a degree, as at 1440 px)
var px = function (v) { return 200 - v * 32.6; }, pm = cmModel(cpx, id1), ptop = px(pm.sel[1].hi), pmeds = pm.others.map(function (o) { return px(o.mids[1]); });
var under = function (y, meds, extra) { return meds.filter(function (m) { return m >= y - 14 - (extra || 0) && m <= y + 4; }); };
assert.ok(under(ptop - 10, pmeds).length === 1, 'the old place had very high under it'); // the bug, at the old 10 px
var ply = cmLabelY(ptop, pmeds, 10, 0);
assert.ok(under(ply, pmeds).length === 0 && ply < ptop - 10, ply);
assert.strictEqual(cmLabelY(ptop, [], 10, 0), ptop - 10); // nothing in the way: 10 px over the box, as designed
assert.strictEqual(cmLabelY(100, [140, 95, 300], 10, 0), 100 - 10); // medians inside or below the box never move it
var two = cmLabelY(100, [88, 70], 8, 16); // two lines ("Models disagree" and the value 16 px over it): both clear
assert.ok(under(two, [88, 70], 16).length === 0, two);
assert.deepStrictEqual(cp7.link, { text: 'IPCC AR6 Atlas, CMIP6 projections ↗', href: 'https://digital.csic.es/handle/10261/332744' });
assert.strictEqual(cc7.words[1], "We change this place's own 1995–2014 average by the share the models give (the delta method), so raw model values never sit next to the records.");
assert.deepStrictEqual(cc7.work, ["This place's 1995–2014 average from NASA POWER: 3.7" + NB + 'mm a day, about 1,363' + NB + 'mm a year (step 3). On the chart that is 0.',
  "Models' change, 2041–2060, SSP2-4.5: +11% (range −3 to +24%).", 'So the 2041–2060 average sits at +11% on the chart, where 0 is that average.',
  'Models agreeing on wetter or drier: 66% for 2021–2040, 75% for 2041–2060, 91% for 2081–2100. Under 80%, we say they disagree.',
  "No “more than today” for rain: one year's rain swings more than this change."]);
// rain's step 4 keeps PR1's "Now" line (its step 7 has none); temperature points to step 7
assert.ok(/, not a point on the line\.$/.test(steps(CC.trend, CC.series, ccc)[3].work.slice(-1)[0]));
// the record the delta method starts from: baseline_record, in the page's short words; never one fixed dataset (PR4: ERA5)
assert.deepStrictEqual(CP.trend.projection.baseline_record, { id: 'power', name: 'NASA POWER (MERRA-2)' });
var CE = copy(CP); CE.trend.source = Object.assign({}, CE.trend.source, { id: 'era5', name: 'ERA5 reanalysis via Open-Meteo archive' }); CE.trend.caveats = [];
CE.trend.projection.baseline_record = { id: 'era5', name: 'ERA5 reanalysis via Open-Meteo archive' };
var cec = pc2(CE, 'Princeton, NJ'), ce7 = steps(CE.trend, CE.series, cec)[6];
assert.strictEqual(ce7.work[0], "This place's 1995–2014 average from ERA5: 11.9" + NB + '°C (step 3). On the chart that is 0.');
[card(CE.trend, false, null, TODAY), ce7, futRead(CE.trend, futOf(CE.trend, null, false, TODAY), false), cmTable(futOf(CE.trend, null, false, TODAY)), csvFuture(CE.trend, cec).text,
  chartText(CE.trend, CE.series, cec).summary].forEach(function (x) { assert.ok(!/POWER|MERRA/.test(JSON.stringify(x)), JSON.stringify(x).slice(0, 200)); });
CE.trend.projection.baseline_record = { id: 'ghcn', name: 'NOAA NCEI GHCN-Daily' };
assert.ok(/^This place's 1995–2014 average from the NOAA weather station: /.test(steps(CE.trend, CE.series, cec)[6].work[0]));
CE.trend.projection.baseline_record = { id: 'other', name: 'Some record' };
assert.ok(/^This place's 1995–2014 average from Some record: /.test(steps(CE.trend, CE.series, cec)[6].work[0]));
delete CE.trend.projection.baseline_record; // an answer from before the field: the answer's own source
assert.ok(/^This place's 1995–2014 average from ERA5 reanalysis via Open-Meteo archive: /.test(steps(CE.trend, CE.series, cec)[6].work[0]));
var CFB = copy(CP); CFB.trend.baseline.method = 'fitted';
assert.ok(/: 11\.9\s°C \(estimated from the fitted trend\) \(step 3\)\. /.test(steps(CFB.trend, CFB.series, cpc)[6].work[0]));
// step 9: the Atlas, where it was retrieved, the citations, the projections CSV
var cp9 = steps(CP.trend, CP.series, cpc)[8], ps9 = CP.trend.projection.source;
assert.ok(/; future from the IPCC AR6 Atlas \(CMIP6\)$/.test(cp9.short) && cp9.csvFut);
assert.ok(cp9.words[0].list.some(function (x) { return x.text === 'Future: IPCC AR6 Interactive Atlas, CMIP6 projections, doi:10.20350/digitalCSIC/15492, version v2.0-final, CC BY 4.0. Retrieved from '
  + ps9.retrieved_from.name + ' (doi:10.24381/cds.5292a2b0). ' && x.link.href === ps9.record_url && x.link.text === 'Open it ↗'; }));
assert.deepStrictEqual(cp9.words[1], { cite: ps9.citation, ack: 'Acknowledgement: ' + ps9.acknowledgement });
// §3 the projections CSV: every scenario and window, metric in °F too; header lines never quoted
var cc1 = csvFuture(CP.trend, pc2(CP, 'Princeton, NJ', true)), cl1 = cc1.text.split('\n'), hd1 = cl1.indexOf('scenario,name,window_start,window_end,p10_degC,p50_degC,p90_degC,models');
assert.strictEqual(cc1.name, 'bhoomi-air-temperature-princeton-nj-cmip6.csv');
assert.deepStrictEqual(cl1.slice(0, 8), ['# Bhoomi: Air temperature projections for Princeton, NJ', '# Source: IPCC AR6 Interactive Atlas, CMIP6 projections',
  '# Dataset: doi:10.20350/digitalCSIC/15492; version: v2.0-final; licence: CC BY 4.0', '# Retrieved from: ' + ps9.retrieved_from.name + ', doi:10.24381/cds.5292a2b0',
  '# Record: https://digital.csic.es/handle/10261/332744', '# Grid cell: land cell lat 40.5, lon -74.5, 21 km from the place, 100% land',
  "# Baseline: the 1995–2014 average; each model's 20-year mean minus its own 1995–2014 mean, added to this place's observed 1995–2014 average",
  '# Ranges: p10-p90 is the range across climate models (10th-90th percentile)']);
assert.strictEqual(cl1.filter(function (l) { return /^# Cite: /.test(l); }).length, ps9.citation.length);
assert.ok(cl1[hd1 - 2].indexOf('# Acknowledgement: ') === 0 && cl1[hd1 - 1] === '# Built with AI assistance. bhoomi.earth');
assert.ok(cl1.slice(0, hd1).every(function (l) { return /^# /.test(l) && l.indexOf('"') < 0; }));
assert.strictEqual(cl1.length, hd1 + 1 + 4 * 3 + 1);
assert.strictEqual(cl1[hd1 + 1 + 3 + 1], 'ssp245,intermediate emissions,2041,2060,1.2,1.89,2.31,34');
var cl2 = csvFuture(CC.trend, ccc).text.split('\n'), hd2 = cl2.indexOf('scenario,name,window_start,window_end,p10_pct,p50_pct,p90_pct,models,agree_share,models_disagree');
assert.ok(hd2 > 0 && cl2[hd2 + 1 + 3 + 1] === 'ssp245,intermediate emissions,2041,2060,-2.9,10.8,23.6,32,0.75,true' && cl2[hd2 + 1 + 3 + 2] === 'ssp245,intermediate emissions,2081,2100,2,10.2,35.4,32,0.91,false');
assert.ok(/, as % of it, added to /.test(cl2[6]));
var CEV = copy(CP); CEV.trend.projection.scenarios[0].name = '=HYPERLINK("x")';
assert.ok(csvFuture(CEV.trend, cpc).text.split('\n').some(function (l) { return l.indexOf('ssp126,"\'=HYPERLINK(""x"")",2021,2040,') === 0; }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_explain_pure_logic():
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=PURE + ASSERTS, capture_output=True, text=True, env=env)
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
    """QA B8: a long place name pushed the last column out of sight at 1440. Place names wrap in the compare table; the
    box still scrolls sideways from 600 px up. Design 14 §8: under 600 px each place is a block with its column names
    (data-label), so nothing scrolls sideways; the table keeps explicit roles for Safari."""
    css = (ROOT / "web" / "compare.css").read_text(encoding="utf-8")
    rules = re.findall(r"([^{}]+)\{([^}]*)\}", css)
    place = [sel for sel, body in rules if "nowrap" in body and re.search(r"td:first-child|td:nth-child\(1\)", sel)]
    assert not place, place
    assert re.search(r"\.cmp-scroll \{ overflow-x: auto; \}", css)
    narrow = re.search(r"@media \(max-width: 599px\) \{ /\* one block per place.*?\n\}", css, re.S)
    assert narrow, "no block layout under 600 px"
    for rule in (".cmp-scroll { overflow-x: visible; }", ".cmp-tbl, .cmp-tbl tbody, .cmp-tbl tr, .cmp-tbl td { display: block; }",
                 ".cmp-tbl td[data-label]::before { content: attr(data-label);"):
        assert rule in narrow[0], rule
    assert css.index(".cmp-tbl td.n {") < narrow.start()  # the block rules come last, so they win at equal specificity
    assert ".cmp-tbl" not in (ROOT / "web" / "style.css").read_text(encoding="utf-8")  # the table's rules live in compare.css
    assert re.search(r"\.cmp-tbl th \{ font-size: 14px;[^}]*font-weight: 400;", css) and "uppercase" not in css  # sentence case
    cmp = (ROOT / "web" / "compare.js").read_text(encoding="utf-8")
    for r in ("'table'", "'rowgroup'", "'row'", "'columnheader'", "'cell'"):
        assert r in cmp, r
    assert "c.setAttribute('data-label', cols[k])" in cmp


def test_narrow_readout_value_column_is_capped():
    """QA B9: at 375 px rain's long unit filled an `auto` value column and squeezed the label to one word a line."""
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    narrow = re.search(r"@container \(max-width: 519px\) \{(.*?)\n\}", css, re.S)
    assert narrow
    cols = re.search(r"\.reads > div, \.reads > div \+ div \{[^}]*grid-template-columns: ([^;]+);", narrow[1])
    assert cols and cols[1] == "minmax(0, 1fr) fit-content(45%)", cols and cols[1]


def test_no_risk_level_or_advice_in_the_page_code():
    """Facts, not advice (owner, 2026-11-22; design 14 §0): no risk chip, advice box or threshold is left in the page's
    code or words, outside comments: no "risk", "recommend", "advise", "buy" or "invest" in any string the page can
    print, and no .risk or .advice rule in style.css."""
    banned = re.compile(r"risk|recommend|advis|\bbuy|invest", re.I)
    for name in ("app.js", "compare.js", "chat.js", "map.js", "explain.js", "index.html"):
        text = (ROOT / "web" / name).read_text(encoding="utf-8")
        code = re.sub(r"/\*.*?\*/|<!--.*?-->", "", text, flags=re.S)
        code = re.sub(r"(^|\s)//[^\n]*", r"\1", code)  # line comments; "https://" keeps its ':' so it stays
        m = banned.search(code)
        assert not m, (name, code[max(0, m.start() - 60):m.end() + 20])
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    assert not re.search(r"\.(risk|advice)\b", css)
    assert not re.search(r"\.(risk|rk)\b", (ROOT / "web" / "compare.css").read_text(encoding="utf-8"))
    # every pinned-place marker looks the same (§6; the ink teardrop, 13-maps.md §2a): no risk classes, no --mk-low
    mcss = (ROOT / "web" / "map.css").read_text(encoding="utf-8")
    assert "--mk-low" not in mcss and not re.search(r"\.map-mk\.(high|moderate|low)\b", mcss)
    assert re.search(r"\n\.map-mk path \{[^}]*fill: var\(--ink\);", mcss)
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "Our recommendation" not in app
    # design 14 §6: the small words, exactly
    assert "Pin up to 6 places to compare. Click one to see what its records show." in (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "'Pin a place to see what its records show'" in app
    assert "question: 'Is the sea rising where you live? Some tide gauges have measured it for more than a century.'" in app
    assert ("\"Without a usable tide gauge nearby, our records can't tell you about this coast.\"), "
            "nextLine([{ text: 'Your local planning office', href: '' }])") in app
    assert "return el('div', { class: 'next' }, el('span', { class: 'nl' }, 'Where to look next:'), ' ', ul);" in app
    # the card: the fact, then the world line, the readouts, where to look next, the button, then the disclaimer, always
    rec = re.search(r"\nfunction drawRec\(box\) \{(.*?)\n\}", app, re.S)[1]
    at = rec.index
    assert at("if (C.fact) box.append(el('p', { class: 'say' }, C.fact));") < at("if (C.world)") < at("class: C.r3f ? 'reads sub' : 'reads'") \
        < at("if (C.next.length) box.append(nextLine(C.next));") < at("box.append(el('div', { class: 'acts' }, how));") \
        < at("if (C.disc) box.append(el('p', { class: 'disc' }, C.disc));")


def test_scenario_colours_never_colour_text():
    """Design 11 §9: --scen-1 is under 4.5:1 on white, so scenario colours only stroke and fill marks; every label on
    the chart and in the control is ink or --ink-2."""
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        if ("var(--k)" in body or "var(--scen-" in body) and ":root" not in sel:
            assert not re.search(r"(^|[;\s])color:", body), sel
    assert re.search(r"\.pc-r \{[^}]*fill: var\(--ink-2\);", css) and re.search(r"\.pc-lab \{[^}]*fill: var\(--ink\);", css)


def test_future_chart_cases_the_trend_line_and_the_medians():
    """QA6: over a band and the trend's own 95% range, the light orange fell to 2.48:1 and the dark falling blue to
    1.97:1. In the sea-level future chart a --surface casing, 1.5 px each side, lies under the trend line and the
    medians. Review: the medians meet at 2020, so the casings are one layer over the band and the range and under
    every observed mark; then the medians, then the record's trend line on top."""
    draw = re.search(r"\n  function draw\(c\) \{(.*?)\n  \}\n", SRC, re.S)[1]
    at = lambda x: draw.index(x)
    trend = "root.append(sv('line', Object.assign({ class: 's-trend' }, tl)));"
    case_t = at("if (cx != null && cx < tl.x2) root.append(sv('line', { class: 'c-case', x1: cx,")
    case_m = at("meds.forEach(function (m) { root.append(sv('path', { d: m.d, class: m.cs })); });")
    meds = at("meds.forEach(function (m) { root.append(sv('path', { d: m.d, class: m.cls })); });")
    fut_trend = at("if (tl) " + trend)
    assert at("class: 'f-edge'") < at("class: 's-edge'") < case_t < case_m  # over the band, the range and their edges
    assert case_m < at("class: 's-month'") < at("class: 'c-zero'") < at("class: 's-avg'") < meds < fut_trend  # nothing observed under a casing
    assert at("if (tl && !fut) { // PR1") < at(trend) < meds  # PR1's chart draws its own trend line, uncased
    assert draw.count(trend) == 2 and "class: 'c-case'" not in draw[fut_trend:]
    assert "cls: 'f-med k' + o.k, cs: 'c-case thin' }" in draw and "cls: 'f-sel' + sk + (fx.low ? ' low' : ''), cs: 'c-case' }" in draw
    assert "class: 'f-med" not in draw and "class: 'f-sel" not in draw  # every median goes through meds
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    width = lambda sel: float(re.search(r"(?:^|\n)%s \{[^}]*stroke-width: ([\d.]+);" % re.escape(sel), css)[1])
    assert re.search(r"\n\.c-case \{[^}]*stroke: var\(--surface\);", css)
    assert width(".c-case") == width(".pc-svg.fut .s-trend") + 3 == width(".f-sel") + 3
    assert width(".c-case.thin") == width(".f-med") + 3


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_trend_casing_starts_at_2020_and_spares_a_thin_range():
    """QA (The Battery, Grand Isle, Juneau): a 95% range under 3 px each side was hidden by the 3 px trend casing, and
    the casing striped the 1995-2014 box. The real draw() runs on a tiny fake DOM (no browser, no network): the
    trend's casing starts at or after x(2020), every casing does, and the range and its edges start before 2020."""
    grab = lambda pat: re.search(pat, SRC, re.S)[0]
    dom = "\n".join([grab(r"\n  var SVGNS = [^\n]*\n"), grab(r"\n  function sv\(tag, attrs, text\) \{.*?\n  \}\n"),
                     grab(r"\n  function clear\(n\) \{[^\n]*\n"), grab(r"\n  function pathOf\(xs, ys\) \{.*?\n  \}\n"),
                     grab(r"\n  function draw\(c\) \{.*?\n  \}\n")])
    js = PURE + dom + ASSERTS.split("var NB = ")[0] + r"""
function El(tag) { this.tag = tag; this.a = {}; this.kids = []; this.classList = { toggle: function () {} }; this.clientWidth = 1100; }
El.prototype.setAttribute = function (k, v) { this.a[k] = String(v); };
El.prototype.append = function () { for (var i = 0; i < arguments.length; i++) this.kids.push(arguments[i]); };
El.prototype.addEventListener = function () {};
El.prototype.removeChild = function (n) { this.kids.splice(this.kids.indexOf(n), 1); };
Object.defineProperty(El.prototype, 'firstChild', { get: function () { return this.kids[0] || null; } });
var document = { createElementNS: function (ns, tag) { return new El(tag); } };
var B = load('battery_sea_level'), f = B.trend.fit;
f.change_low = f.change - 8; f.change_high = f.change + 8; // a range 4 mm each side at its ends: about 1 px
var ctx = Object.assign(ctx(B, 'New York, NY'), { today: 2026 * 12 + 10, sel: null });
var c = { box: new El('div'), pin: { trend: B.trend, series: B.series }, T: chartText(B.trend, B.series, ctx), ctx: ctx,
  fx: futOf(B.trend, null, false, ctx.today), mode: 'both', ro: new El('p') };
draw(c);
var els = c.box.kids[0].kids, cls = function (e) { return e.a['class'] || ''; };
var xs = function (pts) { return pts.split(' ').map(function (p) { return +p.split(',')[0]; }); };
var ysOf = function (pts) { return pts.split(' ').map(function (p) { return +p.split(',')[1]; }); };
var x2020 = Math.min.apply(null, xs(els.filter(function (e) { return /^f-band/.test(cls(e)); })[0].a.points)) - 0.05; // points are rounded to 0.1 px
var fan = els.filter(function (e) { return cls(e) === 's-fan'; })[0], fy = ysOf(fan.a.points);
assert.ok(Math.abs(fy[1] - fy[2]) / 2 < 3, 'the range must be under 3 px here: ' + fy); // [x0 lo0, x1 lo1, x1 hi1, x0 hi0]
var trend = els.filter(function (e) { return cls(e) === 's-trend'; });
var tcase = els.filter(function (e) { return e.tag === 'line' && cls(e) === 'c-case'; });
assert.ok(trend.length === 1 && tcase.length === 1 && els.indexOf(tcase[0]) < els.indexOf(trend[0]));
assert.ok(+tcase[0].a.x1 >= x2020 && +tcase[0].a.x2 === +trend[0].a.x2, JSON.stringify(tcase[0].a) + ' ' + x2020);
var tl = trend[0].a, k = (+tcase[0].a.x1 - +tl.x1) / (+tl.x2 - +tl.x1); // the casing lies on the trend line
assert.ok(Math.abs(+tl.y1 + (+tl.y2 - +tl.y1) * k - +tcase[0].a.y1) < 1e-6);
els.filter(function (e) { return /c-case/.test(cls(e)) && e.tag === 'path'; }).forEach(function (e) {
  assert.ok(+/^M([\d.]+)/.exec(e.a.d)[1] >= x2020, e.a.d.slice(0, 20)); });
var edges = els.filter(function (e) { return cls(e) === 's-edge'; });
assert.ok(Math.min.apply(null, xs(fan.a.points)) < x2020 - 100 && edges.length === 2 && edges.every(function (e) { return +e.a.x1 < x2020 - 100; }));
assert.ok(els.indexOf(fan) < els.indexOf(tcase[0]) && edges.every(function (e) { return els.indexOf(e) < els.indexOf(tcase[0]); }));
"""
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_cmip6_chart_draws_boxes_across_their_years():
    """Design 15 §1: the real draw() on a tiny fake DOM (no browser, no network). Each of S's windows is a box from
    1 January of its first year to 1 January after its last, p10 to p90; medians are bars across their own window;
    nothing is drawn between 2061 and 2081 and no mark joins the record to a box or one box to the next; the y-axis is the
    same for every scenario; a dot a year for temperature; rain's disagreeing windows are dashed and labelled from 600 px;
    the keys read each year, then each window; the aria-label is the summary."""
    grab = lambda pat: re.search(pat, SRC, re.S)[0]
    dom = "\n".join([grab(r"\n  var SVGNS = [^\n]*\n"), grab(r"\n  function sv\(tag, attrs, text\) \{.*?\n  \}\n"),
                     grab(r"\n  function clear\(n\) \{[^\n]*\n"), grab(r"\n  function pathOf\(xs, ys\) \{.*?\n  \}\n"),
                     grab(r"\n  function draw\(c\) \{.*?\n  \}\n")])
    js = PURE + dom + ASSERTS.split("var NB = ")[0] + r"""
var W0 = 1100;
function El(tag) { this.tag = tag; this.a = {}; this.kids = []; this.on = {}; this.classList = { toggle: function () {} }; this.clientWidth = W0; }
El.prototype.setAttribute = function (k, v) { this.a[k] = String(v); };
El.prototype.append = function () { for (var i = 0; i < arguments.length; i++) this.kids.push(arguments[i]); };
El.prototype.addEventListener = function (k, f) { this.on[k] = f; };
El.prototype.removeChild = function (n) { this.kids.splice(this.kids.indexOf(n), 1); };
Object.defineProperty(El.prototype, 'firstChild', { get: function () { return this.kids[0] || null; } });
var document = { createElementNS: function (ns, tag) { return new El(tag); } };
var TODAY = 2026 * 12 + 10;
function run(name, sel, width) {
  W0 = width || 1100;
  var d = load(name), cx = Object.assign(ctx(d, 'X'), { today: TODAY, sel: sel || null }), fx = futOf(d.trend, sel || null, false, TODAY);
  var c = { box: new El('div'), pin: { trend: d.trend, series: d.series }, T: chartText(d.trend, d.series, cx), ctx: cx, fx: fx, mode: modeOf(d.trend, d.series, fx), ro: new El('p') };
  draw(c);
  return { c: c, d: d, fx: fx, root: c.box.kids[0], els: c.box.kids[0].kids };
}
var cls = function (e) { return e.a['class'] || ''; };
var key = function (r, k) { r.root.on.keydown({ key: k, shiftKey: false, preventDefault: function () {} }); return r.c.ro.textContent; };
var P = run('princeton_air_temp'), els = P.els;
assert.strictEqual(P.c.mode, 'both');
assert.strictEqual(P.root.a['aria-label'], P.c.T.summary);
// the x scale: left margin 52, right margin 170, from January 1981 to 1 January 2101
var pw = 1100 - 52 - 170, X = function (y) { return 52 + (y - 1981) / (2101 - 1981) * pw; }, near = function (a, b) { return Math.abs(a - b) < 0.05; };
var boxes = els.filter(function (e) { return e.tag === 'rect' && cls(e) === 'f-band k2'; }), S = P.d.trend.projection.scenarios[1];
assert.deepStrictEqual(boxes.map(function (b) { return [Math.round(+b.a.x * 10) / 10, Math.round((+b.a.x + +b.a.width) * 10) / 10]; }),
  [[2021, 2041], [2041, 2061], [2081, 2101]].map(function (w) { return [Math.round(X(w[0]) * 10) / 10, Math.round(X(w[1]) * 10) / 10]; }));
var edges = els.filter(function (e) { return e.tag === 'rect' && /^f-edge k2/.test(cls(e)); });
assert.ok(edges.length === 3 && edges.every(function (e, i) { return near(+e.a.x, +boxes[i].a.x + 0.5) && near(+e.a.width, +boxes[i].a.width - 1) && !/dis/.test(cls(e)); }));
// p10 below, p90 above: the boxes' heights keep the published ratios
var hts = boxes.map(function (b) { return +b.a.height; });
assert.ok(Math.abs(hts[0] / hts[2] - (S.p90[0] - S.p10[0]) / (S.p90[2] - S.p10[2])) < 1e-6);
// medians: S's three bars (3 px, butt) and three for each other scenario, each across its own window only
var segs = function (dd) { var out = [], re = /M([\d.]+) ([\d.]+)H([\d.]+)/g, m; while ((m = re.exec(dd))) out.push([+m[1], +m[3]]); return out; };
var wins = els.filter(function (e) { return /^f-win/.test(cls(e)); }), meds = els.filter(function (e) { return /^f-med/.test(cls(e)); });
assert.ok(wins.length === 3 && meds.length === 3 && meds.every(function (m) { return segs(m.a.d).length === 3; }));
var gapL = X(2061), gapR = X(2081);
wins.concat(meds).forEach(function (m) { segs(m.a.d).forEach(function (s) { assert.ok(s[1] <= gapL + 0.1 || s[0] >= gapR - 0.1, m.a.d); }); });
// nothing at all in 2061-2080 but the axis furniture (grid, zero, ticks, the hover rule)
els.forEach(function (e) {
  if (/^(c-grid|c-zero|pc-tick|c-rule|pc-t|pc-ytitle|pc-r|pc-r on)$/.test(cls(e)) || /^f-lead/.test(cls(e))) return;
  if (e.tag === 'rect') assert.ok(+e.a.x + +e.a.width <= gapL + 0.1 || +e.a.x >= gapR - 0.1, cls(e));
  if (e.tag === 'path' && e.a.d) segs(e.a.d).forEach(function (s) { assert.ok(s[1] <= gapL + 0.1 || s[0] >= gapR - 0.1, cls(e)); });
  if (e.tag === 'circle') assert.ok(+e.a.cx < gapL, cls(e));
});
// the record is never joined to a box: the yearly line ends at the last year, the trend line at fit.end
var line = els.filter(function (e) { return cls(e) === 's-month'; })[0], trend = els.filter(function (e) { return cls(e) === 's-trend'; })[0];
assert.ok(Math.max.apply(null, line.a.d.split(/[ML]/).filter(Boolean).map(function (p) { return +p.split(' ')[0]; })) < X(2026) && +trend.a.x2 < X(2026));
// a dot a year (45 years), drawn over the trend line; the trend's casing starts where the first box starts
var dots = els.filter(function (e) { return cls(e) === 's-year'; });
assert.ok(dots.length === 45 && els.indexOf(dots[0]) > els.indexOf(trend) && els.indexOf(trend) > els.indexOf(wins[2]));
var tcase = els.filter(function (e) { return e.tag === 'line' && cls(e) === 'c-case'; });
assert.ok(tcase.length === 1 && near(+tcase[0].a.x1, X(2021)), JSON.stringify(tcase[0] && tcase[0].a));
assert.ok(els.filter(function (e) { return e.tag === 'path' && /^c-case/.test(cls(e)); }).length === 6);
// labels: the card's number over its box, the 2081-2100 heading, the zero label; no 2100 break mark
var texts = P.els.filter(function (e) { return e.tag === 'text'; }).map(function (e) { return e.textContent; });
assert.ok(texts.indexOf('+1.9' + NB + '°C, 2041–2060') >= 0 && texts.indexOf('2081–2100:') >= 0 && texts.indexOf('Intermediate +2.9' + NB + '°C') >= 0 && texts.indexOf('0 = the 1995–2014') >= 0, JSON.stringify(texts));
assert.ok(texts.indexOf('Today') >= 0 && texts.some(function (x) { return /^Now \+0\.24/.test(x); }));
// QA B1: no other scenario's 2041-2060 median runs under that label (very high's sat just over the box's top)
var lab = els.filter(function (e) { return e.textContent === '+1.9' + NB + '°C, 2041–2060'; })[0], labY = +lab.a.y;
var w1 = function (r) { var out = []; r.els.filter(function (e) { return /^f-med/.test(cls(e)); }).forEach(function (e) {
  var re = /M([\d.]+) ([\d.]+)H([\d.]+)/g, m; while ((m = re.exec(e.a.d))) if (+m[1] >= X(2041) - 0.1 && +m[3] <= X(2061) + 0.1) out.push(+m[2]); }); return out; };
assert.ok(w1(P).length === 3 && w1(P).every(function (m) { return m < labY - 14 || m > labY + 4; }), labY + ' ' + w1(P));
assert.ok(labY < +boxes[1].a.y - 10); // moved up past it
assert.ok(!els.some(function (e) { return cls(e) === 'c-brk'; }) && !els.some(function (e) { return cls(e) === 's-avg'; }));
// keys: Right from the last year goes to 2021-2040, End to 2081-2100, Home to the first year
assert.ok(/^2025: \+0\.\d+\s°C, the year's average, compared with the 1995–2014 average\.$/.test(key(P, 'ArrowRight')), P.c.ro.textContent);
assert.ok(/^2021–2040, intermediate emissions \(SSP2-4\.5\): /.test(key(P, 'ArrowRight')), P.c.ro.textContent);
assert.ok(/^2041–2060, /.test(key(P, 'ArrowRight')) && /^2081–2100, /.test(key(P, 'End')) && /^1981: /.test(key(P, 'Home')));
// the y-axis does not move when the scenario changes
var ticks = function (r) { return r.els.filter(function (e) { return e.tag === 'text' && e.a['text-anchor'] === 'end' && cls(e) === 'pc-t'; }).map(function (e) { return e.textContent + '@' + e.a.y; }); };
assert.deepStrictEqual(ticks(run('princeton_air_temp', { ssp: 'ssp126' })), ticks(run('princeton_air_temp', { ssp: 'ssp585' })));
assert.deepStrictEqual(ticks(P), ticks(run('princeton_air_temp', { ssp: 'ssp585' })));
assert.ok(run('princeton_air_temp', { ssp: 'ssp585' }).els.filter(function (e) { return cls(e) === 'f-band k4'; }).length === 3);
// rain: dashed edges and bars where S's models disagree, "Models disagree" over the 2041-2060 box from 600 px
var C = run('chennai_rain'), ce = C.els.filter(function (e) { return e.tag === 'rect' && /^f-edge/.test(cls(e)); });
assert.deepStrictEqual(ce.map(function (e) { return / dis$/.test(cls(e)); }), [true, true, false]);
assert.deepStrictEqual(C.els.filter(function (e) { return /^f-win/.test(cls(e)); }).map(function (e) { return / dis$/.test(cls(e)); }), [true, true, false]);
var ct = C.els.filter(function (e) { return e.tag === 'text'; }).map(function (e) { return e.textContent; });
assert.ok(ct.indexOf('Models disagree') >= 0 && ct.indexOf('+11%, 2041–2060') >= 0, JSON.stringify(ct));
// rain reads its years as PR1 does (QA: a shadowed name gave rain the temperature wording)
assert.ok(C.els.filter(function (e) { return cls(e) === 's-year'; }).length === 45);
assert.strictEqual(key(C, 'ArrowRight'), readout(C.d.trend, C.d.series, C.c.ctx, 44));
assert.ok(/ compared with the usual year \(1995–2014\)\.$/.test(C.c.ro.textContent), C.c.ro.textContent);
// 375 px: no "Models disagree" label, the value alone over the box, names only at the right, no zero label
var N = run('chennai_rain', null, 375), nt = N.els.filter(function (e) { return e.tag === 'text'; }).map(function (e) { return e.textContent; });
assert.ok(nt.indexOf('Models disagree') < 0 && nt.indexOf('+11%') >= 0 && nt.indexOf('Intermediate') >= 0 && !nt.some(function (x) { return /^0 = the/.test(x); }), JSON.stringify(nt));
"""
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\.f-win \{[^}]*stroke-width: 3;[^}]*stroke-linecap: butt;", css)
    assert re.search(r"\.f-win\.dis \{ stroke-dasharray: 7 4; \}", css) and re.search(r"\.f-edge\.dis \{ stroke-dasharray: 4 3; \}", css)
    assert re.search(r"\.pc-dis \{[^}]*fill: var\(--ink-2\);", css)
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "C.r3f.per ? el('small', {}, C.r3f.per) : ''" in app  # rain's "of the usual yearly rain", small, as R2's unit
    assert "pj.windows ? 'IPCC AR6 Interactive Atlas, CMIP6 projections" in app


def test_scenario_lines_draw_at_full_colour():
    """Design 11 §9: lines need 3:1, so no scenario line is faded (the low median at 75% was about 2.5:1 on white); the
    other medians are lighter by a thinner stroke than the chosen one."""
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    lines = [(sel, body) for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", css) if re.search(r"\.f-(med|edge|sel|lead|sw)\b", sel)]
    assert len(lines) >= 5, lines
    for sel, body in lines:
        for v in re.findall(r"(?:^|[;\s])(?:stroke-)?opacity:\s*([\d.]+)", body):
            assert float(v) >= 1, sel
    width = lambda c: float(re.search(r"\.%s \{[^}]*stroke-width: ([\d.]+);" % c, css)[1])
    assert width("f-med") < width("f-sel")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_page_cm_equals_the_server_cm():
    """The page's cm() is the server's rule (2 significant figures, sig2): 9 mm is "+0.90 cm", 1036 mm "+100 cm"."""
    from earthtrends.stats.projection import _cm

    mm = list(range(-1200, 1201)) + [1036, 9999, 10360, 25000]
    js = PURE + "console.log(JSON.stringify(%s.map(function (x) { return cmv(x, false); })));" % mm
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    page = [x.replace(" ", " ") for x in json.loads(r.stdout)]
    assert page == [_cm(m) for m in mm]
    assert page[mm.index(9)] == "+0.90 cm" and page[mm.index(1036)] == "+100 cm"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_fahrenheit_readout_and_world_line_round_one_number():
    """In °F (and inches) the card's rate and its world line convert the same number, slope_per_decade, and round it once to 2
    significant figures: 0.365 °C a decade reads +0.66 °F in both (the world line converted local_rate's 0.36 to +0.65). A world
    window shorter than the trend's keeps local_rate, its only source."""
    js = PURE + r"""
var t = { variable: 'air_temp', units: 'degC', verdict: 'rising', slope_per_decade: 0.365, ci_low: 0.3, ci_high: 0.43,
  fit: { start: '1981-01', end: '2025-12' },
  headline_rate: { value: 0.365, low: 0.3, high: 0.43, unit: '°C', per: 'per decade', text: '+0.37 °C per decade', range_text: '+0.30 to +0.43 °C per decade' },
  world: { available: true, local_rate: 0.36, world_rate: 0.18, unit: '°C per decade', window: { start: '1981-01', end: '2025-12' },
    ratio: 2.0, ratio_low: 1.7, ratio_high: 2.4, source: {} } };
var t2 = JSON.parse(JSON.stringify(t)); t2.world.window.start = '1993-01';
console.log(JSON.stringify([rate(t, true).text, rate(t, true).range, cardWorld(t, true).text, worldParts(t2, true).here]));
"""
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert [x.replace(" ", " ") for x in json.loads(r.stdout)] == [
        "+0.66 °F per decade", "+0.54 to +0.77 °F per decade",
        "Over those years: here +0.66 °F per decade, world +0.32 °F per decade.", "+0.65 °F per decade"]


def test_after_2100_note_wraps_at_the_visible_width():
    """At 375 px the decade table scrolls sideways: its after-2100 note is one full-width row (colspan) whose text is as
    wide as the visible box and stays at its left edge, so it is never cut off."""
    assert "h('td', { colspan: String(C.cols.length) }, h('div', {}, C.brk))" in SRC
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\.dec-scroll \{[^}]*overflow-x: auto;[^}]*container-type: inline-size;", css)
    assert re.search(r"\.dec tr\.brk td \{ padding: 0;[^}]*white-space: normal;", css)
    note = re.search(r"\.dec tr\.brk td > div \{([^}]*)\}", css)
    assert note and all(x in note[1] for x in ("box-sizing: border-box", "width: 100cqw", "position: sticky", "left: 0"))


def test_fixtures_carry_the_current_guidance():
    """The fixtures' guidance is the server's current wording (facts, not advice: owner, 2026-11-22), never an older
    text: the stats lane's own code on the fixture's series gives the same object."""
    from earthtrends.stats import compute_trend
    from earthtrends.stats.baseline import baseline

    for f in sorted((ROOT / "tests" / "fixtures" / "rework").glob("*.json")):
        if f.stem == "variables":
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        s = {k: v for k, v in d["series"].items() if k != "anomaly"}
        assert d["trend"]["guidance"] == compute_trend(s, base=baseline(s))["guidance"], f.name
        assert {"fact", "look_next"} <= set(d["trend"]["guidance"]) and "thresholds" not in d["trend"]["world"]


def _contrast(a, b):
    def lum(c):
        r, g, b_ = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b_
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_driver_bars_and_scenario_marks_reach_3_to_1():
    """QA: the driver bars were drawn at 35% (1.64:1 on white, 2.24:1 in dark). Graphics need 3:1 against --surface
    after any opacity, in both themes, for every scenario colour: the bars, the band edges, the medians."""
    css = re.sub(r"/\*.*?\*/", "", (ROOT / "web" / "style.css").read_text(encoding="utf-8"), flags=re.S)
    tok = lambda body: dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", body))
    light = tok(re.search(r":root \{([^}]*)\}", css)[1])
    themes = [light, {**light, **tok(re.search(r':root\[data-theme="dark"\] \{([^}]*)\}', css)[1])}]
    rules = re.findall(r"([^{}]+)\{([^}]*)\}", css)
    body = lambda sel: " ".join(b for s, b in rules if s.strip() == sel)
    checked = 0
    for sels, paint in [((".d-bar",), "fill"), ((".d-bar", ".d-bar.tot"), "fill"), ((".f-edge",), "stroke"),
                        ((".f-edge", ".f-edge.low"), "stroke"), ((".f-med",), "stroke"), ((".f-sel",), "stroke")]:
        b = " ".join(body(s) for s in sels)  # the later rule wins, as in the cascade
        assert b.strip(), sels
        var = re.findall(r"(?:^|[;\s])%s:\s*var\(--([\w-]+)\)" % paint, b)[-1]
        op = 1.0
        for k in ("opacity", paint + "-opacity"):
            v = re.findall(r"(?:^|[;\s])%s:\s*([\d.]+)" % k, b)
            op *= float(v[-1]) if v else 1.0
        for th in themes:
            surf = th["surface"]
            for c in [th["scen-%d" % k] for k in (1, 2, 3, 4)] if var == "k" else [th[var]]:
                mix = "#" + "".join("%02x" % round(op * int(c[i:i + 2], 16) + (1 - op) * int(surf[i:i + 2], 16)) for i in (1, 3, 5))
                assert _contrast(mix, surf) >= 3.0, (sels, c, surf, round(_contrast(mix, surf), 2))
                checked += 1
    assert checked == 2 * (4 + 1 + 4 + 4 + 4 + 4)
    assert "var lc = lcLines(narrow);" in SRC and "lc.forEach(function (x, j) {" in SRC  # the chart draws the 375 px split


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_open_all_steps_button():
    """The owner: "add a open close button in the how we calculated section!" The real showHow() runs on a tiny fake
    DOM (no browser, no network). One button over the steps reads "Open all steps" while any step is closed and
    "Close all steps" when all nine are open; a step toggled by hand and a re-render update it; it is made once."""
    dom = SRC.split("/* ---------- DOM ---------- */")[1].split("\n  window.TDX")[0]
    js = PURE + dom + ASSERTS.split("var NB = ")[0] + r"""
var ids = {}, Q = []; // Q: toggle events waiting to fire, as a browser fires them after the change
function El(tag) { var a = this.a = {}; this.tagName = tag.toUpperCase(); this.kids = []; this.on = {}; this.parentNode = null;
  this.classList = { add: function (c) { a['class'] = ((a['class'] || '') + ' ' + c).trim(); } }; }
El.prototype.setAttribute = function (k, v) { this.a[k] = String(v); if (k === 'id') ids[v] = this; };
El.prototype.getAttribute = function (k) { return k in this.a ? this.a[k] : null; };
El.prototype.addEventListener = function (k, f) { (this.on[k] = this.on[k] || []).push(f); };
El.prototype.append = function () { for (var i = 0; i < arguments.length; i++) { var n = arguments[i];
  if (typeof n === 'object') { if (n.parentNode) n.parentNode.removeChild(n); n.parentNode = this; } this.kids.push(n); } };
El.prototype.removeChild = function (n) { this.kids.splice(this.kids.indexOf(n), 1); if (typeof n === 'object') n.parentNode = null; };
El.prototype.before = function (n) { var p = this.parentNode; p.kids.splice(p.kids.indexOf(this), 0, n); n.parentNode = p; };
El.prototype.querySelectorAll = function (sel) {
  assert.strictEqual(sel, ':scope > li > details');
  var out = []; this.kids.forEach(function (li) { if (li.tagName === 'LI') li.kids.forEach(function (d) { if (d.tagName === 'DETAILS') out.push(d); }); }); return out; };
Object.defineProperty(El.prototype, 'firstChild', { get: function () { return this.kids[0] || null; } });
Object.defineProperty(El.prototype, 'textContent', { get: function () { return this.kids.map(function (k) { return typeof k === 'object' ? k.textContent : k; }).join(''); },
  set: function (v) { this.kids = [String(v)]; } });
Object.defineProperty(El.prototype, 'open', { get: function () { return 'open' in this.a; },
  set: function (v) { if (!!v !== this.open) { if (v) this.a.open = ''; else delete this.a.open; Q.push(this); } } });
var document = { getElementById: function (id) { return ids[id] || null; }, createElement: function (t) { return new El(t); }, createElementNS: function (ns, t) { return new El(t); } };
function flush() { while (Q.length) (Q.shift().on.toggle || []).forEach(function (f) { f(); }); }
function click(b) { b.on.click.forEach(function (f) { f(); }); }
function mk(tag, id) { var n = new El(tag); n.setAttribute('id', id); return n; }

var sec = mk('section', 'how'), ol = mk('ol', 'how-steps');
sec.append(mk('h2', 'how-h'), mk('p', 'how-lead'), ol, mk('div', 'noise-slot'));
var P = load('princeton_air_temp'), B = load('battery_sea_level');
function cx(d, label) { return Object.assign(ctx(d, label), { today: 2026 * 12 + 10, sel: null }); }
function opened() { return ol.querySelectorAll(':scope > li > details').map(function (d, i) { return d.open ? i + 1 : 0; }).filter(Boolean); }
function says(label) { var b = ids['how-all']; assert.strictEqual(b.textContent, label); assert.strictEqual(b.a['aria-expanded'], String(label === 'Close all steps')); }
var ALL = [1, 2, 3, 4, 5, 6, 7, 8, 9];

// a new answer: steps 3 to 6 open, and one native button right above step 1
showHow(P, cx(P, 'Princeton, NJ'), true); flush();
var btn = ids['how-all'];
assert.ok(btn.tagName === 'BUTTON' && btn.a.type === 'button' && btn.a['class'] === 'btn' && btn.a['aria-controls'] === 'how-steps');
assert.strictEqual(sec.kids.indexOf(btn) + 1, sec.kids.indexOf(ol));
assert.deepStrictEqual(opened(), [3, 4, 5, 6]);
says('Open all steps');
// open all, then close all; the label is right at once and after the toggle events
click(btn); assert.deepStrictEqual(opened(), ALL); says('Close all steps'); flush(); says('Close all steps');
click(btn); assert.deepStrictEqual(opened(), []); says('Open all steps'); flush(); says('Open all steps');
// one step closed by hand after "Open all steps" flips the label back; opened again, it flips forward
click(btn); flush();
ol.querySelectorAll(':scope > li > details')[0].open = false; flush(); says('Open all steps');
ol.querySelectorAll(':scope > li > details')[0].open = true; flush(); says('Close all steps');
// a re-render (another place or window) keeps the open steps and the same button, and the label follows
showHow(B, cx(B, 'New York, NY'), false); flush();
assert.strictEqual(ids['how-all'], btn);
assert.strictEqual(btn.on.click.length, 1); // one click listener, not one more per render
assert.strictEqual(sec.kids.filter(function (k) { return k.tagName === 'BUTTON'; }).length, 1);
assert.deepStrictEqual(opened(), ALL); says('Close all steps');
ol.querySelectorAll(':scope > li > details')[8].open = false; flush();
showHow(P, cx(P, 'Princeton, NJ'), false); flush();
assert.deepStrictEqual(opened(), [1, 2, 3, 4, 5, 6, 7, 8]); says('Open all steps');
click(btn); flush(); says('Close all steps');
showHow(P, cx(P, 'Princeton, NJ'), true); flush(); // a new answer goes back to the default
assert.deepStrictEqual(opened(), [3, 4, 5, 6]); says('Open all steps');
"""
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
