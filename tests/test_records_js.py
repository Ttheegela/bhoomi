"""Records for this place (web/design/12-two-sources.md, rework PR4a). The pure logic of web/explain.js runs in node on
hand-made `comparisons`, `comparisons_window`, `disagree` and `drift` in the contract's shape (docs/CONTRACTS.md "Records
for this place"), on top of the rework fixtures; the page code's two calls, roles and narrow layout are read from
web/app.js and web/style.css. Every agreement, reason and drift sentence is the server's: the page prints it as given."""
import os
import re
import shutil
import subprocess

import pytest

from test_explain_js import FAKE_DOM, PURE, ROOT, SRC

DATA = r"""
var assert = require('assert'), fs = require('fs'), path = require('path');
function load(n) { return JSON.parse(fs.readFileSync(path.join(process.env.FIX, n + '.json'), 'utf8')); }
function copy(d) { return JSON.parse(JSON.stringify(d)); }
var NB = ' ', MN = '−';
var COP = 'Contains modified Copernicus Climate Change Service information 2026.';
var LIMIT = "NASA POWER's rain is corrected every day to rain-gauge maps. Where gauges are few (much of Africa, inland Australia, South America and the far north), it can drift.";
var SRC = {
  era5: { id: 'era5', name: 'ERA5 reanalysis via Open-Meteo archive', dataset_id: 'ERA5 reanalysis, daily maximum 2 m temperature', retrieved: '2026-11-22', attribution: COP,
    record_url: 'https://archive-api.open-meteo.com/v1/archive?latitude=28.58&longitude=77.21&start_date=1981-01-01&end_date=2026-10-31&daily=temperature_2m_max' },
  power: { id: 'power', name: 'NASA POWER (MERRA-2)', dataset_id: 'NASA POWER monthly point data, parameter T2M_MAX (MERRA-2)', retrieved: '2026-11-22', attribution: null,
    record_url: 'https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=T2M_MAX&community=AG&latitude=28.58&longitude=77.21&start=1981&end=2025&format=JSON' },
  ghcn: { id: 'ghcn', name: 'NOAA NCEI GHCN-Daily', dataset_id: 'GHCN-Daily station IN022021900', retrieved: '2026-11-22', attribution: null,
    record_url: 'https://www.ncei.noaa.gov/access/services/data/v1?dataset=daily-summaries&stations=IN022021900' } };
var LBL = { era5: 'ERA5', power: 'NASA POWER', ghcn: 'Weather station' };
var GRID = { era5: 'Weather model, grid cell about 25 km wide', power: 'Weather model, grid cell about 50 km wide' };
// a rate as the contract's example writes a row's: the text without "per decade", the range with it
function hr(v, lo, hi) { var s = function (x) { return (x > 0 ? '+' : x < 0 ? MN : '') + Math.abs(x).toFixed(2); };
  return { value: v, low: lo, high: hi, unit: '°C', per: 'per decade', text: s(v) + ' °C', range_text: s(lo) + ' to ' + s(hi) + ' °C per decade' }; }
// rain: as the top-level rain rate, its text with its "per"
function hp(v, lo, hi) { var s = function (x) { return (x > 0 ? '+' : x < 0 ? MN : '') + Math.abs(x).toFixed(1); }, per = 'of the 1995–2014 average per decade';
  return { value: v, low: lo, high: hi, unit: '%', per: per, text: s(v) + '% ' + per, range_text: s(lo) + ' to ' + s(hi) + '% ' + per }; }
function row(id, o) { return Object.assign({ main: false, source: copy(SRC[id]), label: LBL[id], kind: id === 'ghcn' ? 'station' : 'grid', where: GRID[id] || null, km: null, station: null,
  status: 'ok', available: true, why: null, years: '1981–2025', n_months: 540, n_missing: 0, n_preliminary: 0, baseline_value: 33.6, verdict: 'rising', confidence: 'Clear',
  p_value: 0.01, in_100: '1', headline_rate: hr(0.25, 0.11, 0.38) }, o); }
function station(o) { return row('ghcn', Object.assign({ km: 3.4, station: { id: 'IN022021900', name: 'New Delhi Safdarjung' }, where: 'New Delhi Safdarjung, 3 km away' }, o)); }
var CANT = "The records can't tell us which of these reasons applies here, so we show every record as it is.";
var DRIFT = 'Weather models can drift over decades at some places; at this spot NASA POWER has been cooling relative to the other records.';
var REASONS = [DRIFT, "The station's record has gaps: 77 of its 540 months are missing. Stations also move and change instruments, and NOAA doesn't adjust these daily records for that.",
  'Some of these trends sit close to the line we use for a clear change, so one unusual year can move a record across it.',
  'The weather station is one thermometer at one spot, 3 km away, and roads and buildings around it can warm it. The weather models give the average over a grid cell 25 to 50 km wide.'];
var BANNED = /risk|recommend|advis|\bbuy|invest|trust|undefined|NaN|null|\[object/i;
function strings(x) { var out = []; JSON.stringify(x, function (k, v) { if (typeof v === 'string') out.push(v); return v; }); return out; }
function nothingBanned(x) { strings(x).forEach(function (s) { assert.ok(!BANNED.test(s), 'banned: ' + s); }); }

// Delhi, hottest day: ERA5 main says no clear change; NASA POWER falling, the station 3 km away rising
var H = load('delhi_hottest_day'), DT = H.trend;
DT.source = Object.assign({}, DT.source, SRC.era5);
var DEL = {
  comparisons: [
    row('era5', { main: true, verdict: 'no_clear_change', confidence: 'Not clear', p_value: 0.09, in_100: '9', years: '1981–2026', n_months: 549, n_preliminary: 3, headline_rate: hr(0.13, -0.02, 0.27) }),
    row('power', { verdict: 'falling', p_value: 0.02, in_100: '2', baseline_value: 34.9, headline_rate: hr(-0.25, -0.48, -0.02) }),
    station({ n_months: 463, n_missing: 77, verdict: 'rising', confidence: 'Very clear', p_value: 0.0004, in_100: 'less than 1', baseline_value: 35.4, headline_rate: hr(0.25, 0.11, 0.38) })],
  comparisons_window: { start: 1981, end: 2025, label: 'Same years for all: 1981 to 2025' },
  disagree: { any: true, line: 'The records disagree here.', say: 'ERA5 shows no clear change. NASA POWER shows the hottest days getting less hot. The weather station shows them getting hotter.',
    reasons: REASONS.map(function (x, i) { return { id: ['model_drift', 'station_gaps', 'near_line', 'point_vs_grid'][i], text: x }; }) },
  drift: { source: 'power', label: 'NASA POWER', direction: 'cooling', unit: '°C', per: 'per decade', text: DRIFT,
    pairs: [{ against: 'era5', rate: -0.39, low: -0.52, high: -0.25 }, { against: 'ghcn', rate: -0.41, low: -0.6, high: -0.22 }] } };
var dc = { label: 'Delhi, India', name: 'Hottest days', slug: 'hottest-days', imperial: false, cmp: 'ok' };
"""

PURE_TESTS = r"""
// §2 the merge: only the four fields, into the same answer (so the page's identity check skips the chart)
var t0 = copy(DT), served = Object.assign(copy(DT), copy(DEL), { fit: 'from the second call', verdict: 'rising' });
assert.strictEqual(mergeOthers(t0, served), t0);
assert.deepStrictEqual(t0.comparisons, DEL.comparisons);
assert.deepStrictEqual([t0.comparisons_window, t0.disagree, t0.drift], [DEL.comparisons_window, DEL.disagree, DEL.drift]);
assert.ok(t0.fit !== 'from the second call' && t0.verdict === DT.verdict);
var tn = mergeOthers(copy(t0), null); // asked again: back to nothing
assert.ok(tn.comparisons === null && tn.disagree === null && tn.drift === null && tn.comparisons_window === null);
assert.deepStrictEqual(mergeOthers(copy(DT), {}).comparisons, null); // an older server: no records, no block
assert.strictEqual(recBlock(mergeOthers(copy(DT), {}), dc), null);

// §3, §4 Delhi: the rows in order, the main row first; "The records disagree here." with the reasons as given
var b = recBlock(t0, dc);
assert.strictEqual(b.caption, 'Records for Delhi, India: the main record first, then the others, each with its own trend.');
assert.strictEqual(b.window, 'Same years for all: 1981 to 2025');
assert.deepStrictEqual(b.rows.map(function (r) { return [r.main, r.label, r.href, r.sub, r.shape, r.word, r.rate, r.years, r.miss, r.note]; }), [
  [true, 'ERA5', SRC.era5.record_url, 'Main record · Weather model, grid cell about 25 km wide', '≈', 'No clear change', '+0.13 °C', '1981–2026', '', ''],
  [false, 'NASA POWER', SRC.power.record_url, 'Weather model, grid cell about 50 km wide', '▼', 'Falling', MN + '0.25 °C', '1981–2025', '', ''],
  [false, 'Weather station', SRC.ghcn.record_url, 'New Delhi Safdarjung, 3 km away', '▲', 'Rising', '+0.25 °C', '1981–2025', '77 months missing', '']]);
assert.strictEqual(b.link, true); // "Other records disagree ↓" on the verdict line
assert.deepStrictEqual(b.dis, { line: 'The records disagree here.', lead: 'Why records can differ:', note: CANT, reasons: REASONS });
assert.ok(b.agree === undefined && !b.retry && !b.wait && !b.fail && b.limits.length === 0);
nothingBanned(b);
// °F: each row's rate in the Units setting, as the card's (2 significant figures, one rounding)
assert.deepStrictEqual(recBlock(t0, Object.assign({}, dc, { imperial: true })).rows.map(function (r) { return r.rate; }), ['+0.23' + NB + '°F', MN + '0.45' + NB + '°F', '+0.45' + NB + '°F']);
// a station that covers only part of the shared years says so under its years; a record url that isn't https is plain text
var tq = copy(t0); tq.comparisons[2].note = 'Covers only 1995–2025 of these years'; tq.comparisons[1].source.record_url = 'http://power.larc.nasa.gov/';
var bq = recBlock(tq, dc);
assert.ok(bq.rows[2].note === 'Covers only 1995–2025 of these years' && bq.rows[1].href === '');

// §9 step 8: after step 7, open (they disagree), one column, the working with the records as columns
var S = steps(t0, H.series, dc);
assert.strictEqual(S.length, 10);
assert.deepStrictEqual(S.map(function (x) { return x.title; }).slice(6), ['What comes next', 'Other records', 'Things to keep in mind', 'Sources']);
var s8 = S[7];
assert.strictEqual(s8.short, 'They disagree: ERA5 no clear change, NASA POWER falling, weather station rising');
assert.deepStrictEqual(s8.words, ['We ran steps 1 to 6 on two more records for this place, each against its own 1995–2014 average. ERA5, the main record, leads the card and the chart; the others are here so you can see whether they agree.',
  'The records disagree here. ERA5 shows no clear change. NASA POWER shows the hottest days getting less hot. The weather station shows them getting hotter.',
  'The reasons are listed on the card.']);
assert.ok(s8.open === true && s8.one === true);
assert.strictEqual(s8.work[0], 'Same years for all: 1981 to 2025');
assert.deepStrictEqual(s8.work[1].table.cols, ['', 'ERA5 (main)', 'NASA POWER', 'Weather station']);
assert.deepStrictEqual(s8.work[1].table.rows, [
  ['Months used', '549, 1981–2026', '540, 1981–2025', '463, 1981–2025'],
  ['Months missing', '0 (3 preliminary)', '0', '77'],
  ['1995–2014 average', '33.6' + NB + '°C', '34.9' + NB + '°C', '35.4' + NB + '°C'],
  ['Rate per decade', '+0.13 °C', MN + '0.25 °C', '+0.25 °C'],
  ['95% range', MN + '0.02 to +0.27 °C', MN + '0.48 to ' + MN + '0.02 °C', '+0.11 to +0.38 °C'],
  ['By chance, in 100', '9', '2', 'less than 1'],
  ['Trend', 'no clear change', 'falling, clear', 'rising, very clear']]);
assert.strictEqual(s8.work[2], 'Drift, month by month, each record against its own 1995–2014 average: NASA POWER minus ERA5 ' + MN + '0.39' + NB + '°C per decade (95% range ' + MN + '0.52 to ' + MN
  + '0.25); NASA POWER minus the weather station ' + MN + '0.41' + NB + '°C per decade (' + MN + '0.60 to ' + MN + '0.22). We flag a model when it drifts the same way against every other record.');
var f8 = steps(t0, H.series, Object.assign({}, dc, { imperial: true }))[7].work[2]; // °F: × 1.8, the metric digits (0.39 → 0.70)
assert.ok(f8.indexOf(' minus ERA5 ' + MN + '0.70' + NB + '°F per decade (95% range ' + MN + '0.94 to ' + MN + '0.45)') > 0, f8);
nothingBanned(S);
// §8 naming the main record: the lead, step 3, step 10 with each other record and the Copernicus line
assert.strictEqual(howLead(t0, dc), 'For Delhi, India. Steps 1 to 7 use the main record, ERA5; step 8 sets the other records beside it. Every number below is the one the card and the chart use.');
assert.strictEqual(S[2].short.indexOf("Every level is compared with ERA5's 1995–2014 average here, "), 0, S[2].short);
assert.ok(S[2].words[0].indexOf('compared with the 1995–2014 average at this place in ERA5, the main record, ') > 0, S[2].words[0]);
assert.ok(/ The other records in step 8 each use their own 1995–2014 average\.$/.test(S[2].words[0]), S[2].words[0]);
assert.strictEqual(S[9].short.indexOf('ERA5 reanalysis via Open-Meteo archive; NASA POWER (MERRA-2); NOAA NCEI GHCN-Daily'), 0, S[9].short);
var src10 = S[9].words[0].list;
assert.deepStrictEqual(src10.filter(function (x) { return /^Other record: /.test(x.text); }).map(function (x) { return [x.text, x.link.href]; }), [
  ['Other record: NASA POWER (MERRA-2), NASA POWER monthly point data, parameter T2M_MAX (MERRA-2). Retrieved 22 November 2026. ', SRC.power.record_url],
  ['Other record: NOAA NCEI GHCN-Daily, GHCN-Daily station IN022021900. Retrieved 22 November 2026. ', SRC.ghcn.record_url]]);
assert.strictEqual(src10.filter(function (x) { return x.text === COP; }).length, 1); // once
assert.strictEqual(attribution(t0), COP);
// without the records step 8 is not there and nothing is renamed (sea level, water storage, an older server)
var tz = mergeOthers(copy(DT), null); tz.source = load("delhi_hottest_day").trend.source; // NASA POWER: no attribution
assert.strictEqual(steps(tz, H.series, Object.assign({}, dc, { cmp: undefined })).length, 9);
assert.strictEqual(howLead(tz, { label: 'Delhi' }), 'For Delhi. Every number below is the one the card and the chart use.');
assert.strictEqual(attribution(Object.assign(tz, { projection: { available: false, why: 'x' } })), ''); // no ERA5, no CMIP6: no line

// §10 CSV: after "# Retrieved:", the main record, each other record, agreement, drift, then Copernicus; ASCII minus
var cl = csvPlace(t0, H.series, dc).text.split('\n'), ri = cl.indexOf('# Retrieved: 2026-11-22');
assert.deepStrictEqual(cl.slice(ri + 1, ri + 7), [
  '# Main record: ERA5 reanalysis via Open-Meteo archive (chart, trend and projection baseline)',
  '# Other record: NASA POWER (MERRA-2); 1981–2025; -0.25 °C per decade (95% range -0.48 to -0.02 °C per decade); falling; ' + SRC.power.record_url,
  '# Other record: NOAA NCEI GHCN-Daily, station New Delhi Safdarjung (IN022021900), 3.4 km away; 1981–2025, 77 months missing; +0.25 °C per decade (95% range +0.11 to +0.38 °C per decade); rising; ' + SRC.ghcn.record_url,
  '# Records agree: no', '# Drift: ' + DRIFT, '# ' + COP]);
assert.ok(/^# Data through: /.test(cl[ri + 7]), cl[ri + 7]);
cl.filter(function (l) { return /^#/.test(l); }).forEach(function (l) { assert.ok(!/−/.test(l), l); });

// §7 ERA5T: card meta, chart sub-line, CSV line; one year, across two years, one month
var HP = copy(H); HP.trend = t0; var n = HP.series.times.length;
HP.series.flags = HP.series.times.map(function (x, i) { return i >= n - 3 ? 'preliminary' : null; });
assert.deepStrictEqual(preMonths(HP.series), { n: 3, meta: 'October to December preliminary', full: 'October to December 2025' });
assert.strictEqual(chartText(HP.trend, HP.series, dc).pre, "October to December 2025 are an early release that ERA5's makers may still correct, so the trend and the dots leave them out.");
assert.ok(csvPlace(HP.trend, HP.series, dc).text.split('\n').indexOf('# Preliminary: October to December 2025; ERA5T, an early release that may still change; left out of the trend') > 0);
var two = { times: ['2026-10', '2026-11', '2026-12', '2027-01'], values: [1, 2, 3, 4], flags: [null, 'preliminary', 'preliminary', 'preliminary'] };
assert.deepStrictEqual(preMonths(two), { n: 3, meta: 'November 2026 to January 2027 preliminary', full: 'November 2026 to January 2027' });
two.flags = [null, null, null, 'preliminary'];
assert.deepStrictEqual(preMonths(two), { n: 1, meta: 'January preliminary', full: 'January 2027' });
assert.strictEqual(preLine(t0, two), "January 2027 is an early release that ERA5's makers may still correct, so the trend and the dots leave it out.");
two.values[3] = null; // a month with no value is not named
assert.strictEqual(preMonths(two), null);
assert.strictEqual(chartText(t0, H.series, dc).pre, '');

// Princeton, air temperature: all three agree, no reasons, no drift
var P = load('princeton_air_temp'), PT = P.trend;
PT.source = Object.assign({}, PT.source, SRC.era5);
mergeOthers(PT, { comparisons: [row('era5', { main: true, verdict: 'rising', confidence: 'Very clear', headline_rate: hr(0.31, 0.24, 0.38) }),
  row('power', { verdict: 'rising', confidence: 'Very clear', headline_rate: hr(0.34, 0.27, 0.41) }),
  station({ where: 'Hightstown 2 W, 12 km away', km: 12.2, station: { id: 'USC00283951', name: 'Hightstown 2 W' }, verdict: 'rising', confidence: 'Clear', headline_rate: hr(0.29, 0.15, 0.42) })],
  comparisons_window: { start: 1981, end: 2025, label: 'Same years for all: 1981 to 2025' },
  disagree: { any: false, line: 'All three records agree: rising.', say: 'ERA5 shows it getting warmer. NASA POWER shows it getting warmer. The weather station shows it getting warmer.', reasons: [] },
  drift: null });
var pc = { label: 'Princeton, NJ', name: 'Air temperature', slug: 'air-temperature', imperial: false, cmp: 'ok' }, pb = recBlock(PT, pc);
assert.deepStrictEqual(pb.agree, ['All three records agree: rising.']);
assert.ok(pb.dis === undefined && pb.link === false && pb.limits.length === 0);
assert.deepStrictEqual(pb.rows.map(function (r) { return r.word + ' ' + r.rate; }), ['Rising +0.31 °C', 'Rising +0.34 °C', 'Rising +0.29 °C']);
var p8 = steps(PT, P.series, pc)[7];
assert.ok(p8.short === 'All three agree: rising' && p8.open === false && p8.words.length === 2, p8.short);
assert.strictEqual(p8.work[p8.work.length - 1], 'No drift flagged at this spot.');
var pl = csvPlace(PT, P.series, pc).text.split('\n');
assert.ok(pl.indexOf('# Records agree: yes') > 0 && !pl.some(function (l) { return /^# Drift/.test(l); }));
nothingBanned([pb, p8]);

// Sydney, rain: NASA POWER main; all three no clear change; the drift line, then the gauge note
var C = load('chennai_rain'), CT = C.trend;
CT.source = Object.assign({}, CT.source, SRC.power, { limit: LIMIT });
var SYD = 'Weather models can drift over decades at some places; at this spot NASA POWER has been getting drier relative to the other records.';
mergeOthers(CT, { comparisons: [row('power', { main: true, source: Object.assign(copy(SRC.power), { limit: LIMIT }), verdict: 'no_clear_change', confidence: 'Not clear', headline_rate: hp(-5.4, -11.8, 1.3) }),
  row('era5', { verdict: 'no_clear_change', confidence: 'Not clear', headline_rate: hp(0.4, -6.2, 7.1) }),
  station({ where: 'Sydney Botanic Gardens, 1 km away', km: 1.2, station: { id: 'ASN00066006', name: 'Sydney Botanic Gardens' }, n_missing: 72, verdict: 'no_clear_change', confidence: 'Not clear', headline_rate: hp(2.9, -3.0, 9.0) })],
  comparisons_window: { start: 1981, end: 2025, label: 'Same years for all: 1981 to 2025' },
  disagree: { any: false, line: 'All three records agree: no clear change.', say: 'NASA POWER shows no clear change. ERA5 shows no clear change. The weather station shows no clear change.', reasons: [] },
  drift: { source: 'power', label: 'NASA POWER', direction: 'getting drier', unit: '%', per: 'per decade', text: SYD, pairs: [{ against: 'era5', rate: -5.8, low: -9.1, high: -2.4 }, { against: 'ghcn', rate: -8.2, low: -13, high: -3.1 }] } });
var sc = { label: 'Sydney, Australia', name: 'Rain', slug: 'rain', imperial: false, cmp: 'ok' }, sb = recBlock(CT, sc);
assert.strictEqual(sb.caption, "Records for Sydney, Australia: the main record first, then the others, each with its own trend. Rates are % of each record's own usual yearly rain.");
assert.deepStrictEqual(sb.rows.map(function (r) { return r.rate; }), [MN + '5.4%', '+0.4%', '+2.9%']);
assert.deepStrictEqual(recBlock(CT, Object.assign({}, sc, { imperial: true })).rows.map(function (r) { return r.rate; }), [MN + '5.4%', '+0.4%', '+2.9%']); // rain stays %
assert.deepStrictEqual(sb.agree, ['All three records agree: no clear change.', SYD]);
assert.deepStrictEqual(sb.limits, [LIMIT]);
var cS = steps(CT, C.series, sc), c8 = cS[7];
assert.ok(c8.short === 'All three agree: no clear change; NASA POWER has been drifting drier' && c8.open === true, c8.short);
assert.ok(/^Drift, year by year, each record against its own 1995–2014 average: NASA POWER minus ERA5 −5\.8% per decade \(95% range −9\.1 to −2\.4\); NASA POWER minus the weather station −8\.2% per decade \(−13 to −3\)\. /.test(c8.work[c8.work.length - 1]), c8.work[c8.work.length - 1]);
assert.strictEqual(cS[8].words[0].list[0], LIMIT); // step 9: the main record's source.limit first
assert.ok(csvPlace(CT, C.series, sc).text.split('\n').indexOf('# Drift: ' + SYD) > 0);
assert.ok(/; -5\.4% of the 1995–2014 average per decade \(95% range -11\.8 to \+1\.3% of the 1995–2014 average per decade\); no clear change; /.test(csvOther(CT.comparisons[0])));
nothingBanned([sb, cS]);

// §5 a missing station, a short station and a record that couldn't be read
var NONE = 'No weather station within 25 km has 30 years of daily mean temperature data since 1981.';
var tm = copy(PT); tm.comparisons[2] = row('ghcn', { status: 'none', available: false, why: NONE, where: null, verdict: null, headline_rate: null });
tm.disagree = { any: false, line: 'Both records agree: rising.', say: 'ERA5 shows it getting warmer. NASA POWER shows it getting warmer.', reasons: [] };
var mb = recBlock(tm, pc);
assert.deepStrictEqual(mb.rows[2], { main: false, label: 'Weather station', href: '', sub: '', note: '', why: NONE }); // no link, no where line
assert.deepStrictEqual(mb.agree, ['Both records agree: rising.']);
var m8 = steps(tm, P.series, pc)[7];
assert.ok(m8.short === 'Both agree: rising' && /^We ran steps 1 to 6 on one more record for this place/.test(m8.words[0]), m8.short);
assert.deepStrictEqual(m8.work[1].table.rows.map(function (r) { return r[3]; }), ['—', '—', '—', '—', '—', '—', '—']);
assert.strictEqual(m8.work[2], 'Weather station: ' + NONE);
assert.ok(csvPlace(tm, P.series, pc).text.split('\n').indexOf('# Other record: Weather station: ' + NONE) > 0);
var SHORT = 'This station has fewer than 30 years of daily rain data since 1981, and no other station within 25 km does either.';
var ts = copy(tm); ts.comparisons[2] = station({ status: 'short', available: false, why: SHORT, where: 'Madras Minambakkam, 13 km away', verdict: null });
assert.deepStrictEqual(recBlock(ts, pc).rows[2], { main: false, label: 'Weather station', href: SRC.ghcn.record_url, sub: 'Madras Minambakkam, 13 km away', note: '', why: SHORT });
var te = copy(PT); te.comparisons[1] = row('power', { status: 'error', available: false, why: "We couldn't read this record just now.", verdict: null });
var eb = recBlock(te, pc);
assert.ok(eb.retry === true && eb.rows[1].why === "We couldn't read this record just now.");
// "pending" (Ask and MCP only) is shown like "error"
var tg = copy(PT); tg.comparisons[1] = row('power', { status: 'pending', available: false, counted: false, why: 'Not loaded yet.', verdict: null });
assert.ok(recBlock(tg, pc).retry === true && recBlock(tg, pc).rows[1].why === 'Not loaded yet.');
// a thin station: kept with its own verdict, muted, its note under the row; the server compared the other two only
var THIN = "Few readings after 2015 (3 to 8 months a year), so this row covers less and isn't counted when we compare.";
var tt = copy(t0); tt.comparisons.forEach(function (x) { x.counted = true; });
Object.assign(tt.comparisons[2], { counted: false, note: THIN });
tt.disagree = { any: true, line: 'The records disagree here.', say: 'ERA5 shows no clear change. NASA POWER shows the hottest days getting less hot.', reasons: [{ id: 'two_models', text: 'x' }] };
var tb2 = recBlock(tt, dc);
assert.ok(tb2.rows[2].thin === true && tb2.rows[2].note === THIN && tb2.rows[2].word === 'Rising' && tb2.rows[0].thin === false && tb2.rows[0].note === '');
var t8 = steps(tt, H.series, dc)[7];
assert.strictEqual(t8.short, 'They disagree: ERA5 no clear change, NASA POWER falling'); // the counted rows only
assert.ok(t8.work.indexOf('Weather station: ' + THIN) > 0);
assert.ok(/; rising; Few readings after 2015 \(3 to 8 months a year\), so this row covers less and isn't counted when we compare\.; https:/.test(csvOther(tt.comparisons[2])));
// fewer than two rows with a trend: disagree null, rows only
var t1 = copy(tm); t1.comparisons[1] = te.comparisons[1]; t1.disagree = null;
var b1 = recBlock(t1, pc);
assert.ok(b1.agree === undefined && b1.dis === undefined && b1.link === false);
assert.strictEqual(steps(t1, P.series, pc)[7].short, 'Only ERA5 has a trend here');

// §5 the compare call pending, then failed: the main row from the card's own numbers, then the line or the retry
var tp = mergeOthers(copy(PT), null), WAIT = recWait(['era5', 'power', 'ghcn'], 'era5');
assert.strictEqual(WAIT, 'Reading the other records for this place: NASA POWER and the nearest weather station within 25 km. A weather station can take a minute or more the first time.'); // the seconds: the page's aria-hidden span
assert.strictEqual(recWait(['power', 'era5', 'ghcn'], 'power'), 'Reading the other records for this place: ERA5 and the nearest weather station within 25 km. A weather station can take a minute or more the first time.');
assert.strictEqual(recWait(['era5', 'power', 'ghcn'], 'ghcn'), 'Reading the other records for this place: ERA5 and NASA POWER.');
var wb = recBlock(tp, Object.assign({}, pc, { cmp: 'loading', wait: WAIT }));
assert.deepStrictEqual(wb.rows, [{ main: true, label: 'ERA5', href: SRC.era5.record_url, sub: 'Main record', shape: '▲', word: 'Rising', rate: card(tp, false).r2.value, years: '1981–2025', miss: '', note: '', thin: false }]);
assert.ok(wb.wait === WAIT && !wb.link && !wb.fail);
var fb = recBlock(tp, Object.assign({}, pc, { cmp: 'error' }));
assert.ok(fb.rows.length === 1 && fb.fail === "We couldn't read the other records just now." && !fb.wait);
assert.strictEqual(recBlock(tp, Object.assign({}, pc, { cmp: 'error', err: 'Too many requests right now. Please wait 30 seconds and try again.' })).fail, 'Too many requests right now. Please wait 30 seconds and try again.'); // a 429: the API's sentence
var w8 = steps(tp, P.series, Object.assign({}, pc, { cmp: 'loading' })), f8 = steps(tp, P.series, Object.assign({}, pc, { cmp: 'error' }));
assert.ok(w8.length === 10 && w8[7].short === 'Reading the other records for this place…' && !w8[7].work);
assert.strictEqual(f8[7].short, "We couldn't read the other records just now.");
assert.strictEqual(howLead(tp, { label: 'Princeton, NJ', cmp: 'loading' }).indexOf('For Princeton, NJ. Steps 1 to 7 use the main record, ERA5;'), 0);

// §6 the sidebar: "Main record" help lines, each with "The other records are listed on the card."
assert.ok(COMPARED.air_temp && COMPARED.air_temp_max && COMPARED.precip && !COMPARED.sea_level && !COMPARED.water_storage);
assert.strictEqual(recHelp('air_temp', 'era5'), 'ERA5: a European weather model of past weather, on a grid about 25 km wide. The other records are listed on the card.');
assert.strictEqual(recHelp('air_temp_max', 'power'), 'NASA POWER: a NASA weather model on a grid about 50 km wide. The other records are listed on the card.');
assert.strictEqual(recHelp('precip', 'power'), 'NASA POWER: a NASA weather model on a grid about 50 km wide, its rain corrected every day to rain-gauge maps. The other records are listed on the card.');
assert.strictEqual(recHelp('precip', 'ghcn'), 'The nearest weather station within 25 km with 30 years of records. The other records are listed on the card.');
assert.strictEqual(recHelp('sea_level', 'coops'), ''); // sea level keeps "Measured by" and its own help

// Copernicus: the CMIP6 projection CSV carries it when its source does; the compare CSV once for ERA5 places
var PC = load('princeton_air_temp'), pcc = { label: 'Princeton, NJ', name: 'Air temperature', slug: 'air-temperature', imperial: false };
assert.strictEqual(PC.trend.projection.source.attribution, COP); // as the server sends it
assert.ok(csvFuture(PC.trend, pcc).text.split('\n').indexOf('# ' + COP) > 0);
PC.trend.projection.source.attribution = null;
assert.ok(csvFuture(PC.trend, pcc).text.split('\n').indexOf('# ' + COP) < 0);
var pj = load('princeton_air_temp').trend;
assert.strictEqual(attribution(Object.assign(pj, { source: { id: 'power' }, comparisons: null })), COP); // the projection's alone
var cc = csvCompare([{ label: 'Delhi', t: t0, s: H.series }, { label: 'Princeton', t: PT, s: P.series }], { name: 'Hottest days', slug: 'hottest-days' }).text.split('\n');
assert.strictEqual(cc.filter(function (l) { return l === '# ' + COP; }).length, 1);
"""

# The server's own output (tests/fixtures/rework, made by the stats lane's code): NASA POWER is still first in the
# catalog there, so it is the main record; the page takes it from the rows' `main`, never from a name.
REAL = r"""
var NAME = { air_temp: 'Air temperature', air_temp_max: 'Hottest days', precip: 'Rain' }, SLUG = { air_temp: 'air-temperature', air_temp_max: 'hottest-days', precip: 'rain' };
function real(n, label) { var d = load(n), t = d.trend; return { t: t, s: d.series, c: { label: label, name: NAME[t.variable], slug: SLUG[t.variable], imperial: false, cmp: 'ok' } }; }
function rowsText(b) { return b.rows.map(function (r) { return r.why !== undefined ? [r.label, r.sub, r.why] : [r.label + (r.href ? ' ↗' : ''), r.sub, r.shape + ' ' + r.word, r.rate, r.years, r.miss, r.note]; }); }

// Delhi, hottest day: the records disagree. Numbers come from the fixture as the server made them; the words around them are fixed.
var RD = real('delhi_hottest_day', 'Delhi, India'), rb = recBlock(RD.t, RD.c), rs = steps(RD.t, RD.s, RD.c), RC3 = RD.t.comparisons;
var asGiven = function (x) { return x.headline_rate.text.replace(/ per decade$/, ''); }; // a row's rate: the server's text without "per decade"
var missing = function (x) { return x.n_missing > 0 ? x.n_missing + ' months missing' : ''; };
assert.strictEqual(rb.window, RD.t.comparisons_window.label);
assert.ok(/^Same years for all: 1981 to 20\d\d$/.test(rb.window), rb.window);
assert.deepStrictEqual(rowsText(rb), [
  ['NASA POWER ↗', 'Main record · Weather model, grid cell about 50 km wide', '▲ Rising', asGiven(RC3[0]), RC3[0].years, '', ''],
  ['ERA5 ↗', 'Weather model, grid cell about 25 km wide', '≈ No clear change', asGiven(RC3[1]), RC3[1].years, '', ''],
  ['Weather station ↗', RC3[2].where, '▲ Rising', asGiven(RC3[2]), RC3[2].years, missing(RC3[2]), '']]);
assert.ok(/^New Delhi Safdarjun, IN, 1 km away$/.test(RC3[2].where));
var rq = rate(RD.t, false); assert.strictEqual(card(RD.t, false).r2.value, bare(rq)); // the card's headline: its own full window, as given
assert.ok(rb.link && rb.dis.line === 'The records disagree here.' && rb.dis.reasons.length >= 2 && rb.dis.note === CANT);
assert.deepStrictEqual(rb.dis.reasons, RD.t.disagree.reasons.map(function (x) { return x.text; }));
assert.strictEqual(rs[7].short, 'They disagree: NASA POWER rising, ERA5 no clear change, weather station rising');
assert.ok(rs[7].open === true);
var dr = RD.t.drift; // each pair with the shared rounding: the rate to 2 significant figures, the range's ends to the same decimals
assert.strictEqual(rs[7].work[rs[7].work.length - 1], 'Drift, month by month, each record against its own 1995–2014 average: ERA5 minus NASA POWER ' + sig2Text(dr.pairs[0].rate) + NB + '°C per decade (95% range '
  + spanText(dr.pairs[0].low, dr.pairs[0].high) + '); ERA5 minus the weather station ' + sig2Text(dr.pairs[1].rate) + NB + '°C per decade (' + spanText(dr.pairs[1].low, dr.pairs[1].high)
  + '). We flag a model when it drifts the same way against every other record.');
var rl = csvPlace(RD.t, RD.s, RD.c).text.split('\n'), ascii = function (s) { return s.replace(/−/g, '-'); };
assert.ok(rl.indexOf('# Main record: NASA POWER (MERRA-2) (chart, trend and projection baseline)') > 0);
assert.ok(rl.indexOf('# Other record: ERA5 reanalysis via Open-Meteo archive; ' + RC3[1].years + '; ' + ascii(RC3[1].headline_rate.text) + ' (95% range ' + ascii(RC3[1].headline_rate.range_text) + '); no clear change; '
  + RC3[1].source.record_url) > 0, rl.join('\n'));
assert.ok(rl.indexOf('# Other record: NOAA NCEI GHCN-Daily, station New Delhi Safdarjun, IN (IN022021900), 1 km away; ' + RC3[2].years + (RC3[2].n_missing ? ', ' + missing(RC3[2]) : '') + '; '
  + ascii(RC3[2].headline_rate.text) + ' (95% range ' + ascii(RC3[2].headline_rate.range_text) + '); rising; ' + RC3[2].source.record_url) > 0, rl.join('\n'));
assert.ok(rl.indexOf('# Records agree: no') > 0 && rl.indexOf('# Drift: ' + RD.t.drift.text) > 0 && rl.indexOf('# ' + COP) > 0); // an ERA5 row: Copernicus
nothingBanned([rb, rs, rl]);

// Princeton, air temperature: all three agree
var RP = real('princeton_air_temp', 'Princeton, NJ'), pb2 = recBlock(RP.t, RP.c), ps2 = steps(RP.t, RP.s, RP.c);
assert.deepStrictEqual(pb2.agree, ['All three records agree: rising.']);
assert.deepStrictEqual(rowsText(pb2).map(function (r) { return r[2] + ' ' + r[3]; }), ['▲ Rising +0.37 °C', '▲ Rising +0.35 °C', '▲ Rising +0.39 °C']);
assert.ok(ps2[7].short === 'All three agree: rising' && ps2[7].open === false);
nothingBanned([pb2, ps2]);

// Chennai, rain: the station is too short (named and placed from ghcn.NoStation, plus its why), both models agree
var RC = real('chennai_rain', 'Chennai, India'), cb2 = recBlock(RC.t, RC.c), cs2 = steps(RC.t, RC.s, RC.c);
assert.ok(/km away$/.test(RC.t.comparisons[2].where));
assert.deepStrictEqual(rowsText(cb2)[2], ['Weather station', RC.t.comparisons[2].where, RC.t.comparisons[2].why]);
assert.deepStrictEqual(rowsText(cb2).slice(0, 2).map(function (r) { return r[3]; }), ['+6.1%', '+7.0%']);
assert.deepStrictEqual(cb2.agree, ['Both records agree: rising.']);
assert.ok(cs2[7].short === 'Both agree: rising' && /^We ran steps 1 to 6 on one more record /.test(cs2[7].words[0]));
var avg8 = cs2[7].work[1].table.rows[2], yr8 = function (x) { return F(RC.t, false).lvl(x.baseline_value, RC.t.units) + ', about ' + commas(Math.round(x.baseline_value * 365.25)) + NB + 'mm a year'; };
assert.deepStrictEqual(avg8, ['1995–2014 average', yr8(RC.t.comparisons[0]), yr8(RC.t.comparisons[1]), '—']);
assert.ok(/ mm a day, about 1,363 mm a year$/.test(avg8[1]) && / here, about 1,363 mm a year$/.test(cs2[2].short), avg8[1] + ' | ' + cs2[2].short); // the same total as step 3
assert.ok(/ in a day, about [\d.]+ in a year$/.test(steps(RC.t, RC.s, Object.assign({}, RC.c, { imperial: true }))[7].work[1].table.rows[2][1])); // inches
nothingBanned([cb2, cs2]);

// Sydney, rain: all three show no clear change; the drift line follows the agree line
var RS = real('sydney_rain_drift', 'Sydney, Australia'), sb2 = recBlock(RS.t, RS.c), ss2 = steps(RS.t, RS.s, RS.c);
assert.deepStrictEqual(sb2.agree, ['All three records agree: no clear change.', 'Weather models can drift over decades at some places; at this spot NASA POWER has been getting drier relative to the other records.']);
assert.deepStrictEqual(rowsText(sb2).map(function (r) { return r[3]; }), [MN + '6.6%', MN + '0.78%', '+1.3%']);
assert.ok(ss2[7].short === 'All three agree: no clear change; NASA POWER has been drifting drier' && ss2[7].open === true, ss2[7].short);
nothingBanned([sb2, ss2]);
var syd = copy(RS.t); syd.drift.pairs = [{ against: 'era5', rate: -5.66, low: -9.4, high: -1.05 }, { against: 'ghcn', rate: -8.09, low: -14.18, high: -4 }];
var sydW = steps(syd, RS.s, RS.c)[7].work, sydL = sydW[sydW.length - 1];
assert.ok(sydL.indexOf('NASA POWER minus ERA5 −5.7% per decade (95% range −9.4 to −1.1); NASA POWER minus the weather station −8.1% per decade (−14 to −4).') > 0, sydL);
// both models flagged: drift.source null, the server's "drifted apart" text, no pair line and no "drifting" in the short
var R2 = copy(RS.t); R2.drift = Object.assign({}, R2.drift, { source: null, label: null, text: 'Weather models can drift over decades at some places; at this spot ERA5 and NASA POWER have drifted apart.' });
var r2s = steps(R2, RS.s, RS.c)[7];
assert.ok(r2s.short === 'All three agree: no clear change' && r2s.work[r2s.work.length - 1] === R2.drift.text, r2s.short);
assert.strictEqual(recBlock(R2, RS.c).agree[1], R2.drift.text);
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_records_pure_logic():
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=PURE + DATA + PURE_TESTS + REAL, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_other_records_arrive_without_a_chart_redraw():
    """§2: the records land in the same answer; TDX.others() rebuilds "How we calculated this" only (never the chart),
    keeps the steps the visitor opened, and opens step 8 by its own default because the records disagree."""
    dom = SRC.split("/* ---------- DOM ---------- */")[1].split("\n  window.TDX")[0]
    js = PURE + dom + DATA + FAKE_DOM + r"""
var sec = mk('section', 'how'), ol = mk('ol', 'how-steps');
sec.append(mk('h2', 'how-h'), mk('p', 'how-lead'), ol, mk('div', 'noise-slot'));
var drawn = 0; showPlace = function () { drawn++; }; showFuture = function () { drawn++; }; // the chart: counted, not drawn
var t = mergeOthers(copy(DT), null), pin = { status: 'ok', trend: t, series: H.series, label: 'Delhi, India' };
function titles() { return ol.querySelectorAll(':scope > li > details').map(function (d) { return (d.open ? '+' : '-') + d.getAttribute('data-t'); }); }
show(pin, Object.assign({}, dc, { cmp: 'loading' }), true); flush();
assert.strictEqual(drawn, 1);
assert.deepStrictEqual(titles(), ['-The data', '-Seasons removed', '+One baseline', '+The trend and its range', '+Is it real?', '+Compared with the world',
  '-What comes next', '-Other records', '-Things to keep in mind', '-Sources']);
ol.querySelectorAll(':scope > li > details')[0].open = true; flush(); // the visitor opens step 1
mergeOthers(t, DEL); // the second call lands in the same answer
others(pin, Object.assign({}, dc, { cmp: 'ok' })); flush();
assert.strictEqual(drawn, 1); // no chart redraw
assert.deepStrictEqual(titles(), ['+The data', '-Seasons removed', '+One baseline', '+The trend and its range', '+Is it real?', '+Compared with the world',
  '-What comes next', '+Other records', '-Things to keep in mind', '-Sources']);
assert.ok(/^For Delhi, India\. Steps 1 to 7 use the main record, ERA5; step 8 /.test(ids['how-lead'].textContent));
// step 8's body is one column, the working's table has its own scrolling box with a name
var d8 = ol.querySelectorAll(':scope > li > details')[7], body = d8.kids[1];
assert.ok(/\bone\b/.test(body.a['class']), body.a['class']);
var work = body.kids[1].kids[0], box = work.kids.filter(function (k) { return k.a && k.a['class'] === 'work-x'; })[0];
assert.ok(box && box.a.tabindex === '0' && box.a.role === 'region' && box.a['aria-label'] === 'Other records, scrolls sideways');
// another answer's records: nothing happens to this one
others({ status: 'ok', trend: copy(t), series: H.series, label: 'X' }, dc);
assert.ok(/^For Delhi, India\./.test(ids['how-lead'].textContent));
"""
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


APP = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "style.css").read_text(encoding="utf-8")


def test_two_calls_and_the_merge():
    """§2: the card's call sends compare=false; once it succeeds the same /api/trend runs without it, and its answer goes
    into the stored one in place; renderDetail skips the chart when the answer is the same object and only rebuilds the
    steps (TDX.others). A failed second call keeps the card and offers "Try again"; a 429 shows the API's sentence."""
    assert "Promise.all([api('/api/series', job.params), api('/api/trend', noCompare(job.params))])" in APP
    assert "Object.assign({}, params, { compare: 'false' })" in APP
    assert "api('/api/trend', job.res.params).then((r) => { flight--; othersLanded(job, r); pump(); });" in APP  # counted in MAX_FLIGHT
    comp = re.search(r"\nfunction othersLanded\(job, r\) \{(.*?)\n\}", APP, re.S)[1]
    assert "window.TDX.mergeOthers(res.trend, r.body)" in comp
    assert "r.status === 429 ? plainError(r) : \"We couldn't read the other records just now.\"" in comp
    det = re.search(r"\nfunction renderDetail\(\) \{(.*?)\n\}", APP, re.S)[1]
    assert "if (pin.cmp !== shown.cmp) { shown.cmp = pin.cmp; window.TDX.others(pin, ctx); }\n      return;" in det
    assert "fetchTrend(params) { return api('/api/trend', noCompare(params))" in APP  # "Real or noise?" needs no records


# The real explain.js and app.js on a small fake DOM, with a fetch that records every call (no network, no browser).
APP_DOM = r"""
var assert = require('assert'), fs = require('fs'), path = require('path');
function load(n) { return JSON.parse(fs.readFileSync(path.join(process.env.FIX, n + '.json'), 'utf8')); }
function copy(d) { return JSON.parse(JSON.stringify(d)); }
var ids = {};
function El(tag) { this.tagName = String(tag).toUpperCase(); this.kids = []; this.attrs = {}; this.style = {}; this.dataset = {}; this.parentNode = null;
  this.hidden = false; this.value = ''; this.textContent = ''; this.offsetHeight = 0;
  this.classList = { toggle: function () {}, add: function () {}, remove: function () {}, contains: function () { return false; } }; }
El.prototype.setAttribute = function (k, v) { this.attrs[k] = String(v); if (k === 'id') ids[v] = this; };
El.prototype.getAttribute = function (k) { return k in this.attrs ? this.attrs[k] : null; };
El.prototype.removeAttribute = function (k) { delete this.attrs[k]; };
El.prototype.addEventListener = function () {};
El.prototype.append = function () { for (var i = 0; i < arguments.length; i++) { var n = arguments[i]; if (n && typeof n === 'object') { if (n.parentNode) n.parentNode.removeChild(n); n.parentNode = this; } this.kids.push(n); } };
El.prototype.prepend = function (n) { this.append(n); this.kids.unshift(this.kids.pop()); };
El.prototype.removeChild = function (n) { var i = this.kids.indexOf(n); if (i >= 0) this.kids.splice(i, 1); if (n && typeof n === 'object') n.parentNode = null; };
El.prototype.remove = function () { if (this.parentNode) this.parentNode.removeChild(this); };
El.prototype.after = function () { var p = this.parentNode, ns = Array.prototype.slice.call(arguments);
  ns.forEach(function (n) { if (n.parentNode) n.parentNode.removeChild(n); n.parentNode = p; }); p.kids.splice.apply(p.kids, [p.kids.indexOf(this) + 1, 0].concat(ns)); };
El.prototype.replaceWith = function (n) { var p = this.parentNode; if (!p) return; if (n.parentNode) n.parentNode.removeChild(n); p.kids[p.kids.indexOf(this)] = n; n.parentNode = p; this.parentNode = null; };
El.prototype.contains = function (n) { for (; n; n = n.parentNode) if (n === this) return true; return false; };
El.prototype.all = function () { var out = []; this.kids.forEach(function (k) { if (k && typeof k === 'object') out = out.concat([k], k.all()); }); return out; };
function is(n, s) { return s.charAt(0) === '.' ? (' ' + (n.attrs['class'] || '') + ' ').indexOf(' ' + s.slice(1) + ' ') >= 0 : n.tagName === s.toUpperCase(); }
El.prototype.querySelectorAll = function (sel) { var p = sel.split(' > '); return this.all().filter(function (n) { return is(n, p[p.length - 1]) && (p.length < 2 || (n.parentNode && is(n.parentNode, p[0]))); }); };
El.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
El.prototype.focus = function () { document.activeElement = this; };
El.prototype.scrollIntoView = function () {};
El.prototype.getBoundingClientRect = function () { return { top: 0, left: 0, width: 0, height: 0 }; };
Object.defineProperty(El.prototype, 'firstChild', { get: function () { return this.kids[0] || null; } });
Object.defineProperty(El.prototype, 'children', { get: function () { return this.kids.filter(function (k) { return k && typeof k === 'object'; }); } });
var docOn = {};
var document = { activeElement: null, createElement: function (t) { return new El(t); }, createElementNS: function (ns, t) { return new El(t); },
  getElementById: function (id) { return ids[id] || null; }, querySelectorAll: function () { return []; },
  addEventListener: function (t, f) { (docOn[t] = docOn[t] || []).push(f); }, dispatchEvent: function () {} };
('td-live skip nav settings-link win-measure place place-list place-status place-credit pins pin-hint src-field src-lbl seg-source src-help src-note seg-units '
  + 'main win-h1 win-q status-line rec map-slot place-chart how how-h how-lead how-steps noise-slot compare-chart-slot compare-table-slot foot-data footer-sources '
  + 'win-settings settings-slot chat-slot').split(' ').forEach(function (id) { new El('div').setAttribute('id', id); });
var window = globalThis;
window.addEventListener = function () {}; window.matchMedia = function () { return { matches: true }; }; window.scrollBy = function () {};
window.TDPrefs = { get: function () { return { units: 'metric', theme: 'light' }; }, set: function () {} };
globalThis.CustomEvent = function (t, o) { this.type = t; this.detail = o && o.detail; };
var localStorage = { getItem: function () { return null; }, setItem: function () {} };
var location = { hash: '#air-temperature' }, history = { replaceState: function (a, b, h) { location.hash = h; } };
// the catalog as the data lane ships it, and every answer from the Princeton fixture (its records agree)
var VARS = [{ id: 'sea_level', sources: ['coops', 'psmsl'] }, { id: 'air_temp', sources: ['era5', 'power', 'ghcn'] }, { id: 'air_temp_max', sources: ['era5', 'power', 'ghcn'] },
  { id: 'precip', sources: ['power', 'era5', 'ghcn'] }, { id: 'water_storage', sources: ['grace'] }];
var FX = load('princeton_air_temp'), calls = [], live = 0, most = 0;
var answer = function (u, others) { // a test may swap this: { status, body } for a request
  return { status: 200, body: u.pathname === '/api/variables' ? VARS : u.pathname === '/api/series' ? copy(FX.series) : others ? copy(FX.trend)
    : Object.assign(copy(FX.trend), { comparisons: null, comparisons_window: null, disagree: null, drift: null }) };
};
globalThis.fetch = function (url) {
  var u = new URL(url, 'http://page'), trend = u.pathname === '/api/trend', others = trend && u.searchParams.get('compare') !== 'false', a = answer(u, others);
  calls.push(url);
  if (trend) { live++; most = Math.max(most, live); } // one /api/trend per job: a pin's card, or a pin's other records
  return new Promise(function (r) { setTimeout(function () { if (trend) live--;
    r({ ok: a.status < 400, status: a.status, json: function () { return Promise.resolve(a.body); }, headers: { get: function () { return null; } } }); }, others ? 60 : 5); });
};
"""

APP_TEST = r"""
window.TDX.show = function () {}; window.TDX.others = function () {}; window.TDX.redraw = function () {}; // the chart and the steps: not under test here
function settle() { return new Promise(function (r) { (function w() { setTimeout(function () { if (!flight && !queue.length) r(); else w(); }, 10); })(); }); }
function othersCalls() { return calls.filter(function (u) { return /^\/api\/trend\?/.test(u) && !/compare=false/.test(u); }); }
(async function () {
  docOn.DOMContentLoaded[0]();
  await settle();
  // six pinned places: six cards, one call for the other records, for the pin on screen (New York, the first)
  assert.strictEqual(calls.filter(function (u) { return /^\/api\/series\?/.test(u); }).length, 6);
  assert.strictEqual(calls.filter(function (u) { return /compare=false/.test(u); }).length, 6);
  assert.deepStrictEqual(othersCalls(), ['/api/trend?variable=air_temp&lat=40.71&lon=-74.01&source=' + FX.trend.source.id]); // pinned to the card's record
  assert.ok(most <= MAX_FLIGHT, 'in flight: ' + most);
  await new Promise(function (r) { setTimeout(r, 40); });
  assert.strictEqual(ids['td-live'].textContent, FX.trend.disagree.line); // announced once more when they land
  // another pin opened: its other records now, and the pending line hides its ticking seconds from screen readers
  TD.select('40.35,-74.66');
  var st = ids['rec-oth-st'];
  assert.ok(st && st.attrs.role === undefined && typeof st.kids[0] === 'string' && !/ s so far/.test(st.kids[0]), JSON.stringify(st && st.kids[0]));
  assert.ok(st.kids[1].attrs['aria-hidden'] === 'true' && /^ \d+ s so far\.$/.test(st.kids[1].kids[0]), JSON.stringify(st.kids[1].kids));
  await new Promise(function (r) { setTimeout(r, 40); });
  assert.strictEqual(ids['td-live'].textContent, 'Loading the other records…'); // announced once while they load
  await settle();
  assert.deepStrictEqual(othersCalls().slice(1), ['/api/trend?variable=air_temp&lat=40.35&lon=-74.66&source=' + FX.trend.source.id]);
  // back to New York, and to Princeton again: kept on the stored answer, never asked twice
  TD.select('40.71,-74.01'); await settle(); TD.select('40.35,-74.66'); await settle();
  assert.strictEqual(othersCalls().length, 2);
  assert.ok(most <= MAX_FLIGHT, 'in flight: ' + most);
  process.exit(0);
})().catch(function (e) { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_other_records_only_for_the_pin_on_screen():
    """The coordinator's fix: every records call reads ERA5 (Open-Meteo's free allowance is the bottleneck), so only the
    pin on screen asks for them, once, counted in MAX_FLIGHT. Six pins give one call; opening a second pin gives one more;
    coming back asks nothing. The pending line is announced once, then again when the records land; its seconds are
    aria-hidden."""
    js = APP_DOM + SRC + "\n" + APP + APP_TEST
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr + r.stdout


def test_the_block_markup_and_focus():
    """§3, §5, §12: a real table with a hidden caption, row headers and explicit roles (Safari drops them under
    display: grid); the verdict link moves focus to h3#rec-oth without touching the address; the block is redrawn in
    place when the records land, so focus never moves, and a removed retry button sends it to the heading."""
    for s in ("el('table', { role: 'table' }", "el('caption', { class: 'sr-only' }, B.caption)", "el('thead', { role: 'rowgroup' }, hr)",
              "el('tbody', { role: 'rowgroup' })", "el('th', { scope: 'col', role: 'columnheader' }, c)", "el('th', { scope: 'row', role: 'rowheader' }",
              "r.main ? 'is-main' : ''", "r.thin ? 'thin' : ''", "el('tr', { role: 'row', class: 'nt' }, el('td', { role: 'cell', colspan: '4' }, r.note))", "tb.append(...othRow(r))", "el('td', { role: 'cell', class: 'na', colspan: '3' }, r.why)",
              "el('h3', { id: 'rec-oth', tabindex: '-1' }, 'Records for this place')", "el('p', { class: 'st', id: 'rec-oth-st' }, B.wait, el('span', { 'aria-hidden': 'true', id: 'rec-oth-n' }, othSecs(pin)))",
              "othRetry('Try again', pin)", "othRetry('Try the other records again', pin)", "'Other records disagree\u00a0↓'",
              "el('span', { class: 'pd' }, ' per decade')"):
        assert s in APP, s
    assert "class: 'main'" not in APP  # .main is the page column's class
    # the main record fell back (ERA5 couldn't be read): the server's main_note under the source line, as given
    assert "h2(pin.label), meta, typeof t.main_note === 'string' && t.main_note ? el('p', { class: 'mnote' }, t.main_note) : ''" in APP
    link = re.search(r"\nfunction confLine\(conf, B\) \{(.*?)\n\}", APP, re.S)[1]
    assert "e.preventDefault();" in link and "h.focus({ preventScroll: true });" in link
    ref = re.search(r"\nfunction refreshOth\(\) \{(.*?)\n\}", APP, re.S)[1]
    assert "old.replaceWith(othBlock(B, pin))" in ref and "const h = $('rec-oth'); if (h) h.focus({ preventScroll: true });" in ref
    # the card: the readouts, then the block, then where to look next
    rec = re.search(r"\nfunction drawRec\(box\) \{(.*?)\n\}", APP, re.S)[1]
    assert rec.index("class: C.r3f ? 'reads sub' : 'reads'") < rec.index("if (B) box.append(othBlock(B, pin));") < rec.index("if (C.next.length)")
    # the model note and its station button are gone
    for gone in ("modelNote", "Compare with the nearest weather station", "'model strong'"):
        assert gone not in APP and gone not in SRC, gone
    assert ".rec .model" not in CSS


def test_sidebar_main_record_and_the_catalog_default():
    """§6: "Main record" on air temperature, hottest days and rain, "Measured by" on sea level; the default is the
    catalog's first source (sourceFor sends a source only when it is not the first)."""
    assert "$('src-lbl').textContent = window.TDX.compared(curWin) ? 'Main record' : 'Measured by';" in APP
    assert "const cur = used && v.sources.includes(used) ? used : sourceFor(curWin) || v.sources[0];" in APP  # the answer's record, else the choice, else the catalog's first
    assert "s !== v.sources[0] ? s : undefined;" in APP
    assert "$('src-help').textContent = window.TDX.recHelp(curWin, cur) || SOURCE_HELP[cur] || '';" in APP


def test_narrow_card_turns_rows_into_blocks():
    """§12: under 520 px (container query) the header row is visually hidden and each row is a grid block: name left,
    verdict right, then the rate with " per decade" and the years; the main row keeps its ink rule; the global sticky
    header never applies to this table."""
    blocks = re.findall(r"@container \(max-width: 479px\) \{(.*?)\n\}", CSS, re.S)
    oth = [b for b in blocks if ".oth tr {" in b]
    assert len(oth) == 1, "no block layout for the records under 520 px"
    for rule in (".oth thead { position: absolute;", ".oth table, .oth tbody { display: block; }",
                 ".oth tr { display: grid; grid-template-columns: minmax(0, 1fr) fit-content(45%);", ".oth tr.is-main { border-bottom: 1.5px solid var(--ink); }",
                 ".oth td.v { grid-column: 2; grid-row: 1;", ".oth td.r { grid-column: 1; grid-row: 3; }", ".oth td.y { grid-column: 2; grid-row: 3;",
                 ".oth td.na { grid-column: 1 / -1;", ".oth .pd { display: inline;"):
        assert rule in oth[0], rule
    assert ".oth thead th { position: static; background: none;" in CSS
    assert ".oth tr.is-main > * { font-weight: 650; border-bottom: 1.5px solid var(--ink); }" in CSS
    assert re.search(r"\.oth col\.c1 \{ width: 34%; \} \.oth col\.c2 \{ width: 30%; \} \.oth col\.c3 \{ width: 18%; \} \.oth col\.c4 \{ width: 18%; \}", CSS)
    assert ".oth .pd { display: none; }" in CSS
    # a thin station is muted, and its note sits under the row (full width at every size)
    assert ".oth tr.thin > td, .oth tr.thin a { color: var(--ink-2); }" in CSS and ".oth tr.nt td { font-size: 14px; color: var(--ink-2);" in CSS
    assert ".oth tr.nt { display: block; padding: 0 0 10px; }" in oth[0] and ".oth tr.with-note { border-bottom: 0;" in oth[0]
    assert "#rec-oth { scroll-margin-top: calc(var(--top-h) + 16px); }" in CSS
    # the first 479 px block is still the readouts' (test_narrow_readout_value_column_is_capped reads the first one)
    assert ".reads > div, .reads > div + div {" in blocks[0]


FALLBACK_TEST = r"""
window.TDX.others = function () {}; window.TDX.redraw = function () {};
var drawn = []; window.TDX.show = function (pin) { if (pin && pin.status === 'ok') drawn.push(pin); }; // what the chart and the CSV get
function settle() { return new Promise(function (r) { (function w() { setTimeout(function () { if (!flight && !queue.length) r(); else w(); }, 10); })(); }); }
var NOTE = "ERA5 couldn't be read just now; showing NASA POWER.";
assert.strictEqual(FX.trend.source.id, 'power'); // the fixture's answer is NASA POWER's, its records' main row too
assert.ok(FX.trend.comparisons[0].main && FX.trend.comparisons[0].source.id === 'power');
answer = function (u, others) {
  var src = u.searchParams.get('source'), princeton = u.searchParams.get('lat') === '40.35';
  if (u.pathname === '/api/variables') return { status: 200, body: VARS };
  // ERA5, the default, can't be read: New York's series fails with the 502 that app.py gives any httpx.HTTPError (ConnectError
  // included); Princeton's comes from an old ERA5 cache
  if (u.pathname === '/api/series') {
    if (src === 'power') return { status: 200, body: copy(FX.series) };
    return princeton ? { status: 200, body: Object.assign(copy(FX.series), { source: Object.assign(copy(FX.series.source), { id: 'era5', name: 'ERA5 reanalysis via Open-Meteo archive' }) }) }
      : { status: 502, body: { detail: 'upstream' } };
  }
  var t = copy(FX.trend); // the trend falls back to NASA POWER and says so
  return { status: 200, body: others ? t : Object.assign(t, { main_note: src ? null : NOTE, comparisons: null, comparisons_window: null, disagree: null, drift: null }) };
};
(async function () {
  docOn.DOMContentLoaded[0]();
  await settle();
  var ny = TD.pins().filter(function (p) { return p.selected; })[0];
  assert.ok(ny.status === 'ok' && ny.trend.main_note === NOTE, ny.status + ' ' + ny.error); // the failed ERA5 series never errors the card
  assert.deepStrictEqual(calls.filter(function (u) { return /^\/api\/series\?.*lat=40\.71/.test(u); }),
    ['/api/series?variable=air_temp&lat=40.71&lon=-74.01', '/api/series?variable=air_temp&lat=40.71&lon=-74.01&source=power']);
  // the card: NASA POWER and the note under its source line; the chart and the CSV: NASA POWER's series
  var meta = ids['rec'].querySelector('.meta');
  assert.ok(/^NASA POWER\s↗$/.test(meta.kids[0].kids[0]), JSON.stringify(meta.kids[0].kids));
  assert.strictEqual(ids['rec'].querySelector('.mnote').kids[0], NOTE);
  // the sidebar's "Main record" highlights the record the card uses; the visitor's choice (the default, ERA5) is unchanged
  assert.ok(ids['seg-source'].children.filter(function (b) { return b.attrs['aria-checked'] === 'true'; }).map(function (b) { return b.kids[0]; }).join() === 'NASA POWER' && sourceFor('air_temp') === undefined);
  var last = drawn[drawn.length - 1];
  assert.ok(last.series.source.id === 'power' && last.trend.source.id === 'power');
  // the other records are asked for NASA POWER, so their main row is the card's record
  assert.ok(calls.indexOf('/api/trend?variable=air_temp&lat=40.71&lon=-74.01&source=power') >= 0, JSON.stringify(calls.filter(function (u) { return !/compare=false/.test(u); })));
  assert.ok(ny.trend.comparisons[0].main && ny.trend.comparisons[0].source.id === 'power');
  assert.ok(/^NASA POWER\s↗$/.test(ids['rec'].querySelector('.is-main').kids[0].kids[0].kids[0]));
  // Princeton: its series came from ERA5 while its answer is NASA POWER's: asked again, so the chart can't show ERA5
  var pr = TD.pins().filter(function (p) { return p.key === '40.35,-74.66'; })[0];
  assert.ok(pr.status === 'ok' && pr.series.source.id === 'power' && pr.trend.source.id === 'power', pr.series && pr.series.source.id);
  process.exit(0);
})().catch(function (e) { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_main_record_fallback_on_the_page():
    """Review fix (high): when ERA5 can't be read, /api/trend falls back to NASA POWER with main_note while /api/series
    fails (or comes from an old ERA5 cache). The page takes the record from the trend answer, asks the series again for it
    before any error, pins it on the stored answer, and asks the other records for it: the card, the chart and the
    records all show NASA POWER, with main_note under the source line."""
    js = APP_DOM + SRC + "\n" + APP + FALLBACK_TEST
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr + r.stdout


def test_retry_never_reuses_a_cached_error():
    """Review fix 2: the server sends no-store for an answer with main_note or with error or pending rows; the page's
    fetch sets no cache mode of its own, so "Try the other records again" always reaches the server."""
    api = re.search(r"\nasync function api\(path, params\) \{(.*?)\n\}", APP, re.S)[1]
    assert "fetch(path + (q.toString() ? '?' + q : ''), { headers: { Accept: 'application/json' } })" in api
    assert APP.count("fetch(") == 1 and "force-cache" not in APP and "no-cache" not in APP  # api() is the page's only fetch


ONE_JS = r"""
window.TDX.show = function () {}; window.TDX.others = function () {}; window.TDX.redraw = function () {};
function settle() { return new Promise(function (r) { (function w() { setTimeout(function () { if (!flight && !queue.length) r(); else w(); }, 10); })(); }); }
var MODEL = 'Only one record could be compared here, so this answer rests on a single weather model.';
var THIN = "This record has few readings in recent years, so it isn't counted when we compare.";
var AGREE = 'Both records agree: rising.';
function ones() { return ids['rec'].querySelectorAll('.one'); }
// the notes, in this order, right after .verdict, each with the server's text as given
function notesAre(texts) {
  var k = ids['rec'].children, n = ones(), v = k.indexOf(ids['rec'].querySelector('.verdict'));
  assert.strictEqual(n.length, texts.length, 'notes: ' + n.length);
  texts.forEach(function (x, i) { assert.ok(n[i].tagName === 'P' && k[v + 1 + i] === n[i]); assert.deepStrictEqual(n[i].kids, [x]); });
}
function sel() { return TD.pins().filter(function (p) { return p.selected; })[0]; }
function heard() { return new Promise(function (r) { setTimeout(function () { r(ids['td-live'].textContent); }, 40); }); } // after announce's 30 ms
"""

SINGLE_TEST = ONE_JS + r"""
// New York's compare answer (changed between tries); Princeton's has neither note and no agree line
var ny = { thin_note: null, single_note: MODEL, disagree: null };
answer = function (u, others) {
  if (u.pathname === '/api/variables') return { status: 200, body: VARS };
  if (u.pathname === '/api/series') return { status: 200, body: copy(FX.series) };
  var t = copy(FX.trend);
  return { status: 200, body: others ? Object.assign(t, u.searchParams.get('lat') === '40.71' ? copy(ny) : { thin_note: null, single_note: null, disagree: null })
    : Object.assign(t, { comparisons: null, comparisons_window: null, disagree: null, drift: null, thin_note: null, single_note: null }) };
};
// "Try the other records again" with a changed answer: the notes go while they load, then come back replaced, never twice
async function again(next) {
  ny = next;
  var p = sel(), k = resKey(curWin, p);
  compare(curWin, p, k); othLanded(curWin, p, k);
  assert.strictEqual(ones().length, 0);
  await settle();
}
(async function () {
  docOn.DOMContentLoaded[0]();
  // the card is drawn first (compare=false: both notes null): no note until the records land
  await new Promise(function (r) { (function w() { setTimeout(function () { var p = sel(); if (p && p.status === 'ok') r(); else w(); }, 2); })(); });
  assert.ok(sel().cmp === 'loading' && ones().length === 0);
  await settle();
  notesAre([MODEL]); // single only
  assert.strictEqual(await heard(), MODEL); // announced in place of "The other records have loaded."
  renderRec(); notesAre([MODEL]); // a re-render never stacks it
  await again({ thin_note: THIN, single_note: null, disagree: null }); // thin: the server leaves single_note null
  notesAre([THIN]);
  assert.strictEqual(await heard(), THIN);
  renderRec(); notesAre([THIN]);
  await again({ thin_note: THIN, single_note: null, disagree: { any: false, line: AGREE, say: '', reasons: [] } }); // thin only, two others agree
  notesAre([THIN]);
  assert.strictEqual(await heard(), THIN + ' ' + AGREE);
  // a new place with neither: no note; back again: the stored one, once
  TD.select('40.35,-74.66'); assert.strictEqual(ones().length, 0);
  await settle();
  assert.ok(sel().cmp === 'ok' && sel().trend.thin_note === null && sel().trend.single_note === null && ones().length === 0);
  assert.strictEqual(await heard(), 'The other records have loaded.');
  TD.select('40.71,-74.01'); notesAre([THIN]);
  process.exit(0);
})().catch(function (e) { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_single_note_under_the_verdict():
    """Domain review (design 12 §3, §5): the compare answer's thin_note, then single_note, each printed verbatim in a p.one
    right after .verdict, when the records land; null gives none; a re-render or "Try again" replaces them, never a
    second copy. The status message reads thin_note, then disagree.line or single_note."""
    assert ".rec .one { color: var(--ink-2); font-size: 15px; margin: 4px 0 10px;" in CSS  # a note on the verdict, not the start of p.say
    js = APP_DOM + SRC + "\n" + APP + SINGLE_TEST
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr + r.stdout


SINGLE_FALLBACK_TEST = ONE_JS + r"""
var NOTE = "ERA5 couldn't be read just now; showing NASA POWER.";
answer = function (u, others) {
  if (u.pathname === '/api/variables') return { status: 200, body: VARS };
  if (u.pathname === '/api/series') return u.searchParams.get('source') === 'power' ? { status: 200, body: copy(FX.series) } : { status: 502, body: { detail: 'upstream' } };
  var t = Object.assign(copy(FX.trend), { main_note: u.searchParams.get('source') ? null : NOTE });
  if (!others) return { status: 200, body: Object.assign(t, { comparisons: null, comparisons_window: null, disagree: null, drift: null, single_note: null }) };
  // ERA5 can't be read and there is no station: one record counted
  Object.assign(t.comparisons[1], { status: 'error', available: false, counted: false, why: "We couldn't read this record just now." });
  Object.assign(t.comparisons[2], { status: 'none', available: false, counted: false, why: 'No weather station with enough readings within 25 km.' });
  return { status: 200, body: Object.assign(t, { disagree: null, drift: null, single_note: MODEL }) };
};
(async function () {
  docOn.DOMContentLoaded[0]();
  await settle();
  assert.ok(sel().trend.main_note === NOTE && sel().trend.comparisons[1].status === 'error');
  // main_note under the source line as before, single_note under the verdict
  var where = ids['rec'].querySelector('.where');
  assert.strictEqual(where.querySelector('.mnote').kids[0], NOTE);
  assert.ok(where.children.indexOf(where.querySelector('.meta')) < where.children.indexOf(where.querySelector('.mnote')));
  notesAre([MODEL]);
  assert.strictEqual(await heard(), MODEL);
  process.exit(0);
})().catch(function (e) { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_single_note_with_the_main_record_fallback():
    """ERA5 can't be read (main_note, ERA5 row "error") and the station is missing: both sentences show, main_note under
    the source line and single_note under the verdict."""
    js = APP_DOM + SRC + "\n" + APP + SINGLE_FALLBACK_TEST
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr + r.stdout



# ERA5 comes from our Copernicus pack, or from Open-Meteo's archive when the pack can't be read (docs/CONTRACTS.md "ERA5
# pack"). The answers are the Princeton fixture (NASA POWER main, its ERA5 row from Open-Meteo) with `source` replaced.
ERA5_CREDIT = r"""
var P = load('princeton_air_temp');
var OM = copy(P.trend.comparisons[1].source); // Open-Meteo's ERA5 block, as the fixture has it
var PACK = { id: 'era5', name: 'ERA5 reanalysis (Copernicus Interactive Climate Atlas dataset)', url: 'https://cds.climate.copernicus.eu/datasets/multi-origin-c3s-atlas',
  dataset_id: 'doi:10.24381/cds.h35hb680', version: 'pack-2026-11', record_url: 'https://doi.org/10.24381/cds.h35hb680', retrieved: '2026-11-23',
  method: "The Atlas dataset's monthly mean of ERA5 2 m air temperature for the grid cell, about 25 km across.", cadence: 'monthly', deseasoned_upstream: false, limit: null,
  attribution: 'Contains modified Copernicus Climate Change Service information 2026.' };
// ERA5 main from `src`: its row first, NASA POWER beside it
function era5Main(src) {
  var d = copy(P), c = d.trend.comparisons, e = c[1];
  c[1] = c[0]; c[0] = e; c[0].main = true; c[1].main = false; c[0].source = copy(src);
  d.trend.source = copy(src); d.series.source = copy(src); d.trend.projection.baseline_record = { id: 'era5', name: src.name };
  return d;
}
function powerWith(src) { var d = copy(P); d.trend.comparisons[1].source = copy(src); return d; } // NASA POWER main, its ERA5 row from `src`
var CASES = { pack: era5Main(PACK), om: era5Main(OM), power: copy(P), powerPack: powerWith(PACK) };
"""

ERA5_CREDIT_PURE = ERA5_CREDIT + r"""
var pc = { label: 'Princeton, NJ', name: 'Air temperature', slug: 'air-temperature', imperial: false, cmp: 'ok' };
function sources(d) { var S = steps(d.trend, d.series, pc), s = S[S.length - 1]; assert.strictEqual(s.title, 'Sources');
  return { short: s.short, list: s.words[0].list.map(function (x) { return x.text + (x.link ? x.link.href : ''); }) }; }
function head(d) { return csvPlace(d.trend, d.series, pc).text.split('\n').filter(function (l) { return l.charAt(0) === '#'; }); }
function om(x) { return /open-meteo/i.test(JSON.stringify(x)); }
function once(a, s) { return a.filter(function (x) { return x === s; }).length === 1; }
var REC = 'Other record: NASA POWER (MERRA-2), NASA POWER monthly point data, parameter T2M (MERRA-2). Retrieved 22 November 2026. ' + P.trend.source.record_url;
// the pack: named by its own block, no Open-Meteo anywhere, the Copernicus line once
var s = sources(CASES.pack), h = head(CASES.pack);
assert.strictEqual(s.list[0], 'Records: ERA5 reanalysis (Copernicus Interactive Climate Atlas dataset), doi:10.24381/cds.h35hb680, version pack-2026-11. Retrieved 23 November 2026. ' + PACK.record_url);
assert.ok(s.list[1] === REC && once(s.list, COP) && s.short.indexOf(PACK.name + '; NASA POWER (MERRA-2)') === 0, JSON.stringify(s));
assert.deepStrictEqual(h.slice(1, 4), ['# Source: ' + PACK.name, '# Dataset: doi:10.24381/cds.h35hb680; version: pack-2026-11', '# Record: ' + PACK.record_url]);
assert.ok(once(h, '# ' + COP) && !om(s) && !om(h), JSON.stringify(h));
// the fallback: Open-Meteo's own block, as today, with the Copernicus line
s = sources(CASES.om); h = head(CASES.om);
assert.strictEqual(s.list[0], 'Records: ERA5 reanalysis via Open-Meteo archive, doi:10.24381/cds.adbb2d47. Retrieved 22 November 2026. ' + OM.record_url);
assert.ok(s.list[1] === REC && once(s.list, COP) && s.short.indexOf(OM.name + '; NASA POWER (MERRA-2)') === 0, JSON.stringify(s));
assert.deepStrictEqual(h.slice(1, 4), ['# Source: ' + OM.name, '# Dataset: doi:10.24381/cds.adbb2d47; version: not named by the provider', '# Record: ' + OM.record_url]);
assert.ok(once(h, '# ' + COP));
// NASA POWER: unchanged, its ERA5 row named by that row's own block
s = sources(CASES.power); h = head(CASES.power);
assert.ok(/^Records: NASA POWER \(MERRA-2\), /.test(s.list[0]) && s.list[1].indexOf('Other record: ' + OM.name + ', doi:10.24381/cds.adbb2d47.') === 0 && once(s.list, COP), JSON.stringify(s));
assert.ok(h[1] === '# Source: NASA POWER (MERRA-2)' && h.some(function (l) { return l.indexOf('# Other record: ' + OM.name + ';') === 0; }) && once(h, '# ' + COP), JSON.stringify(h));
s = sources(CASES.powerPack); h = head(CASES.powerPack);
assert.ok(s.list[1].indexOf('Other record: ' + PACK.name + ', doi:10.24381/cds.h35hb680.') === 0 && once(s.list, COP) && !om(s), JSON.stringify(s));
assert.ok(h.some(function (l) { return l.indexOf('# Other record: ' + PACK.name + ';') === 0; }) && once(h, '# ' + COP) && !om(h), JSON.stringify(h));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_era5_credit_in_sources_step_and_csv():
    """The Sources step and the CSV name each record by its own source block: a pack answer never mentions Open-Meteo, a
    fallback answer names it as today, and both carry the Copernicus line once."""
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=PURE + DATA + ERA5_CREDIT_PURE, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


ERA5_CREDIT_FOOT = ERA5_CREDIT + r"""
window.TDX.show = function () {}; window.TDX.others = function () {}; window.TDX.redraw = function () {};
function settle() { return new Promise(function (r) { (function w() { setTimeout(function () { if (!flight && !queue.length) r(); else w(); }, 10); })(); }); }
function txt(n) { return typeof n === 'string' ? n : n.kids.map(txt).join(''); }
function hrefs(n) { return n.all().filter(function (k) { return k.tagName === 'A'; }).map(function (k) { return k.attrs.href; }); }
function credit() { return ids['footer-sources'].children.filter(function (li) { return li.dataset.credit === 'era5'; }); }
var COP = PACK.attribution, A = '\u00a0↗';
// d's answer on screen, then the footer as drawn
function foot(d) { results[resKey(curWin, selectedPin(curWin))].trend = d.trend; renderFoot(); var p = ids['foot-data'], c = credit();
  assert.ok(c.length <= 1 && txt(p).split(COP).length === 2, txt(p)); // the Copernicus line once, at most one Open-Meteo credit
  return { line: txt(p), href: hrefs(p)[0], credit: c.length ? [txt(c[0]), hrefs(c[0])] : null }; }
var OMC = ['Weather data by Open-Meteo.com, ERA5 reanalysis, CC BY 4.0', ['https://open-meteo.com/', 'https://creativecommons.org/licenses/by/4.0/']];
(async function () {
  docOn.DOMContentLoaded[0]();
  await settle();
  var f = foot(CASES.om); // the fallback: Open-Meteo named and credited, as today
  assert.ok(f.line.indexOf('Data: ' + OM.name + A + ' · NASA POWER (MERRA-2)' + A + ' · NOAA NCEI GHCN-Daily' + A + '. ') === 0 && f.href === 'https://open-meteo.com/', f.line);
  assert.deepStrictEqual(f.credit, OMC);
  f = foot(CASES.pack); // the pack: its own name and page, no Open-Meteo credit
  assert.ok(f.line.indexOf('Data: ' + PACK.name + A + ' · NASA POWER (MERRA-2)' + A + ' · NOAA NCEI GHCN-Daily' + A + '. ') === 0 && f.href === PACK.url, f.line);
  assert.ok(f.credit === null && !/open-meteo/i.test(f.line), f.line);
  f = foot(CASES.power); // NASA POWER with an ERA5 row from Open-Meteo: unchanged
  assert.ok(f.line.indexOf('Data: NASA POWER (MERRA-2)' + A + ' · ' + OM.name + A + ' · NOAA NCEI GHCN-Daily' + A + '. ') === 0 && f.href === 'https://power.larc.nasa.gov/', f.line);
  assert.deepStrictEqual(f.credit, OMC);
  f = foot(CASES.powerPack); // its ERA5 row from the pack: the row's own name, no Open-Meteo credit
  assert.ok(f.line.indexOf('Data: NASA POWER (MERRA-2)' + A + ' · ' + PACK.name + A + ' · ') === 0 && f.credit === null, f.line);
  process.exit(0);
})().catch(function (e) { console.error(e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_era5_credit_in_the_footer():
    """The footer names each record by its own source block and credits Open-Meteo only while an ERA5 record on screen came
    from its archive; the Copernicus line stays for both."""
    js = APP_DOM + SRC + "\n" + APP + ERA5_CREDIT_FOOT
    env = dict(os.environ, FIX=str(ROOT / "tests" / "fixtures" / "rework"))
    r = subprocess.run(["node", "-"], input=js, capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr + r.stdout
