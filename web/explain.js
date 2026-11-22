'use strict';
/* The place chart (#place-chart), "How we calculated this" (#how) and the CSV downloads (web/design/10-foundation.md).
   Every printed number is an API field (docs/CONTRACTS.md "Rework v2"). This file only formats, converts units
   (guidance.display, °F, inches) and draws. The block between the PURE markers has no DOM: tests/test_explain_js.py runs it. */
(function () {
  /* PURE START */
  var MINUS = '−', NB = ' ';
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  // Short source names for the card; station sources add " at {station}".
  var PLAIN = { coops: 'NOAA tide gauge', psmsl: 'tide gauge (PSMSL)', ghcn: 'NOAA weather station', power: 'NASA POWER', era5: 'ERA5', grace: 'NASA GRACE satellites' };
  var STATION = { coops: 1, ghcn: 1, psmsl: 1 };
  var MEASURE = { sea_level: 'sea level', air_temp: 'air temperature', air_temp_max: 'the hottest day of the month', precip: 'rain', water_storage: 'water storage' };
  var LEVELS = { air_temp: 1, air_temp_max: 1, precip: 1 }; // measurements whose own levels mean something to a visitor
  var OPEN_STEPS = [3, 4, 5, 6]; // steps that start open on a new answer, at every width
  var NO_FUTURE = 'We never stretch the past trend into the future. Future values on this page come only from published expert projections.';

  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function str(x) { return typeof x === 'string' ? x : ''; }
  function fixed(x, d) {
    var s = x.toFixed(d);
    if (Number(s) === 0) s = (0).toFixed(d);
    return s.replace('-', MINUS);
  }
  // 2 decimals if |x| < 1, else 1; a value that would round to zero keeps 3 (same rule as app.js).
  function fmtNum(x, signed) {
    var d = Math.abs(x) < 1 ? 2 : 1;
    if (x !== 0 && Number(x.toFixed(d)) === 0) d = 3;
    var s = fixed(x, d);
    return signed && x > 0 ? '+' + s : s;
  }
  // A rate as the API gives it, signed, with no digit added or lost: ÷10 when `tenth` (a decade's rate a year) shifts the
  // point; in °F or inches the converted value to 6 significant figures.
  function given(imp, x, u, tenth) {
    var k = imp && RATE_K[normU(u)], a = Math.abs(x), txt;
    if (k) txt = String(Number((a * k[0] / (tenth ? 10 : 1)).toPrecision(6)));
    else if (/e/.test(String(a))) txt = String(tenth ? a / 10 : a);
    else txt = (a / (tenth ? 10 : 1)).toFixed((String(a).split('.')[1] || '').length + (tenth ? 1 : 0)).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
    return (x > 0 ? '+' : x < 0 ? MINUS : '') + txt;
  }
  function mi(t) { var p = String(t).split('-'); return +p[0] * 12 + (p.length > 1 ? +p[1] - 1 : 0); }
  function M(t) { var m = mi(t); return MONTHS_LONG[m % 12] + ' ' + Math.floor(m / 12); }
  function Mo(t) { var m = mi(t); return MONTHS[m % 12] + ' ' + Math.floor(m / 12); }
  function Y(t) { return String(t).slice(0, 4); }
  function D(d) { var p = String(d).split('-'); return p.length === 3 ? +p[2] + ' ' + MONTHS_LONG[+p[1] - 1] + ' ' + p[0] : String(d); }
  function commas(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
  function months(n) { return n === 1 ? '1 month is' : commas(n) + ' months are'; }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function lc1(s) { return /^[A-Z][a-z]/.test(s) ? s.charAt(0).toLowerCase() + s.slice(1) : s; }
  function stop(s) { return /[.!?]$/.test(s) ? s : s + '.'; }
  function https(u) { return typeof u === 'string' && u.indexOf('https://') === 0 ? u : ''; }
  function andList(a) { return a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' and ' + a[a.length - 1]; }
  function normU(u) { return u === 'degC' || u === 'C' ? '°C' : u; }
  function own(text) { return str(text).replace(/^the /, ''); } // "its own 1995–2014 average"
  function yrsOf(b) { return b && b.years ? b.years[0] + '–' + b.years[1] : '1995–2014'; }
  function recordUrl(src) { return src ? https(src.record_url) || https(src.url) : ''; }
  function clearV(t) { return t.verdict === 'rising' || t.verdict === 'falling'; }
  // The fitted line goes on the chart only in the chart's own units (never a second unit on one axis).
  function fitOnAxis(t, s, imp) {
    var f = F(t, imp), fit = t.fit || {}, a = s.anomaly || {};
    return (t.baseline || {}).method !== 'none' && !!a.values && isNum(fit.level_end) && f.unit(fit.units) === f.unit(a.units);
  }

  // A value in units u, as shown: the series' own units go through guidance.display, then the Units setting.
  // Rain's mm/day stays a rate a day: a monthly value is never annualised. level: an absolute level (°F adds 32).
  function conv(t, imp, x, u, level) {
    if (u === '%') return { v: x, unit: '%' };
    var g = t.guidance && t.guidance.display, v = x, unit = normU(u);
    if (u === 'mm/day') unit = 'mm a day';
    else if (u === t.units && g && isNum(g.factor) && str(g.unit)) { v = x * g.factor; unit = normU(g.unit); }
    if (imp) {
      if (unit === 'cm') { v /= 2.54; unit = 'in'; }
      else if (/^mm( |$)/.test(unit)) { v /= 25.4; unit = unit.replace(/^mm/, 'in'); }
      else if (unit === '°C') { v = v * 1.8 + (level ? 32 : 0); unit = '°F'; }
    }
    return { v: v, unit: unit };
  }
  function withUnit(s, unit) { return unit === '%' ? s + '%' : unit ? s + NB + unit : s; }
  // val: signed change; lvl: a level; amt: an unsigned size; rng: "+0.22 to +0.40 °C"
  function F(t, imp) {
    return {
      val: function (x, u) { var c = conv(t, imp, x, u); return withUnit(fmtNum(c.v, true), c.unit); },
      lvl: function (x, u) { var c = conv(t, imp, x, u, true); return withUnit(fmtNum(c.v, false), c.unit); },
      amt: function (x, u) { var c = conv(t, imp, x, u); return withUnit(fmtNum(Math.abs(c.v), false), c.unit); },
      rng: function (a, b, u) { var p = conv(t, imp, a, u), q = conv(t, imp, b, u); return withUnit(fmtNum(p.v, true) + ' to ' + fmtNum(q.v, true), q.unit); },
      unit: function (u) { return conv(t, imp, 0, u).unit; },
      num: function (x, u, level) { return conv(t, imp, x, u, level).v; },
    };
  }
  // A rate or a change in a rate's own unit (°C, mm, cm, %), with the Units setting.
  var RATE_K = { '°C': [1.8, '°F'], mm: [1 / 25.4, 'in'], cm: [1 / 2.54, 'in'] };
  function rconv(imp, x, u) { u = normU(u); var k = imp && RATE_K[u]; return k ? { v: x * k[0], unit: k[1] } : { v: x, unit: u }; }

  // The rate every view prints (headline_rate): its own text, or converted for the Units setting.
  function rate(t, imp) {
    var h = t.headline_rate;
    if (!h || typeof h.text !== 'string') { // null only for rain where the 1995-2014 average is zero: the rate in mm a day
      if (oldAnswer(t) || !isNum(t.slope_per_decade) || !isNum(t.ci_low) || !isNum(t.ci_high)) return null;
      var c = function (x) { return conv(t, imp, x, t.units).v; }, cu = conv(t, imp, 0, t.units).unit;
      return { text: withUnit(fmtNum(c(t.slope_per_decade), true), cu) + ' per decade', range: fmtNum(c(t.ci_low), true) + ' to ' + withUnit(fmtNum(c(t.ci_high), true), cu) + ' per decade',
        value: c(t.slope_per_decade), low: c(t.ci_low), high: c(t.ci_high), unit: cu, per: 'per decade' };
    }
    var u = normU(h.unit), per = str(h.per), k = imp && RATE_K[u];
    if (k && isNum(h.value) && isNum(h.low) && isNum(h.high)) {
      var f = function (x) { return fmtNum(x * k[0], true); };
      return { text: withUnit(f(h.value), k[1]) + ' ' + per, range: f(h.low) + ' to ' + withUnit(f(h.high), k[1]) + ' ' + per,
        value: h.value * k[0], low: h.low * k[0], high: h.high * k[0], unit: k[1], per: per };
    }
    return { text: h.text, range: str(h.range_text), value: h.value, low: h.low, high: h.high, unit: u, per: per };
  }
  // "+3.1 mm a year" -> "+3.1 mm" (the card prints "a year" smaller); "+3.1 mm" -> "3.1 mm"
  function bare(r) { var e = ' ' + r.per; return r.per && r.text.slice(-e.length) === e ? r.text.slice(0, -e.length) : r.text; }
  function unsign(s) { return s.replace(/^[+−-]/, ''); }

  // World figures carry their unit in words ("°C per decade", "mm a year").
  function wconv(imp, x, unit) {
    if (imp && /^°C\b/.test(unit)) return { v: x * 1.8, unit: unit.replace('°C', '°F') };
    if (imp && /^mm\b/.test(unit)) return { v: x / 25.4, unit: unit.replace(/^mm/, 'in') };
    return { v: x, unit: unit };
  }
  // the API's world sentence carries metric numbers: say so when the page shows °F or inches
  function metric(text) { return str(text).replace(/\.?\s*$/, ' (in metric).'); }
  function hasWorld(w) { return !!w && w.available === true && isNum(w.local_rate) && isNum(w.world_rate) && !!w.window; }
  // the local and world rates over the same window, next to their ratio; no ratio without a clear trend (only the two rates)
  function worldParts(t, imp) {
    var w = t.world;
    if (!hasWorld(w)) return null;
    var a = wconv(imp, w.local_rate, str(w.unit)), b = wconv(imp, w.world_rate, str(w.unit)), has = isNum(w.ratio) && clearV(t);
    return { since: 'Since ' + Y(w.window.start), here: withUnit(fmtNum(a.v, true), a.unit), world: withUnit(fmtNum(b.v, true), b.unit),
      ratio: has ? fixed(w.ratio, 1) + '×' : '', a: a.v, b: b.v };
  }
  // noSince: the sentence above already starts "Since 1993, …", so the line doesn't say it again
  function worldLine(t, imp, noSince) {
    var p = worldParts(t, imp);
    return p ? (noSince ? 'Here ' : p.since + ': here ') + p.here + ', world ' + p.world + (p.ratio ? ' (' + p.ratio + ')' : '') : '';
  }

  function srcText(t) {
    var s = t.source || {}, p = PLAIN[s.id], pl = t.place && t.place.name;
    return (p ? cap(p) : str(s.name).replace(/, RLR monthly means$/, '') || 'The source') + (p && STATION[s.id] && pl ? ' at ' + pl : '');
  }
  // in a sentence: "the NOAA tide gauge at The Battery", "NASA POWER"
  function srcIn(t) { var s = t.source || {}; return STATION[s.id] && PLAIN[s.id] ? 'the ' + PLAIN[s.id] + (t.place && t.place.name ? ' at ' + t.place.name : '') : srcText(t); }
  function placeName(t, label) { var pl = t.place && t.place.name; return label + (pl && STATION[(t.source || {}).id] ? ' (' + pl + ')' : ''); }
  function verdictWord(t) { return t.verdict === 'rising' ? 'Rising' : t.verdict === 'falling' ? 'Falling' : 'No clear change'; }

  // The "why" sentence; a rain note ("about 60 mm more a year") goes in brackets before its full stop.
  function why(t, imp) {
    var g = t.guidance || {}, n = g.rate && g.rate.note, note = '';
    if (!str(g.why)) return str(t.meaning && t.meaning.headline);
    if (n && typeof n.text === 'string') note = imp && isNum(n.value) ? 'about ' + fmtNum(Math.abs(n.value) / 25.4, false) + ' in ' + (n.value < 0 ? 'less' : 'more') + ' a year' : n.text;
    return note ? g.why.replace(/\.\s*$/, '') + ' (' + note + ').' : g.why;
  }

  // The answer card's words and readouts (section 3).
  function oldAnswer(t) { return !t.fit || !t.baseline; }
  // The measured level today (trend.now), never the end of the trend line: its own text, converted only for the Units setting.
  function nowOf(t, imp) {
    var nw = t.now;
    if (!nw || typeof nw.text !== 'string' || !str(nw.label)) return null;
    return { value: imp && isNum(nw.value) ? F(t, imp).val(nw.value, nw.units) : nw.text, label: nw.label, rain: nw.kind === '12-month total' };
  }
  function card(t, imp) {
    if (oldAnswer(t)) return { old: true, word: verdictWord(t), shape: t.verdict === 'rising' ? '▲' : t.verdict === 'falling' ? '▼' : '≈',
      conf: str(t.meaning && t.meaning.confidence), why: str(t.meaning && t.meaning.headline), chip: '' };
    var b = t.baseline || {}, fit = t.fit || {}, rec = t.record || {}, m = t.meaning || {}, r = rate(t, imp);
    var clear = clearV(t), short = rec.status === 'short', rk = t.range_kind || '95% range';
    var conf = (clear && m.confidence ? m.confidence + ' · ' : '') + (isNum(rec.years) ? Math.round(rec.years) + ' years of records' : '') + (short ? ' (short record)' : '');
    var nw = nowOf(t, imp), r1 = null; // no "Now" readout without trend.now
    if (nw) r1 = { label: 'Now, compared with ' + str(b.text), value: nw.value,
      line: (nw.rain ? 'Rain in ' + nw.label + ", % above or below a usual year" : 'Average of ' + nw.label) + (b.method === 'fitted' ? '. Baseline estimated from the fitted trend.' : '') };
    var r2 = { label: 'Rate, ' + Y(fit.start) + '–' + Y(fit.end), value: r ? bare(r) : '—', per: r ? r.per : '', line: r ? rk + ' ' + r.range : '' };
    if (r && !clear && isNum(r.low) && isNum(r.high) && r.low <= 0 && r.high >= 0) r2.line += ', which includes no change';
    if (short) r2.line += '. Short record.';
    var g = t.guidance || {}, word = verdictWord(t);
    return { word: word, shape: t.verdict === 'rising' ? '▲' : t.verdict === 'falling' ? '▼' : '≈', conf: conf, why: why(t, imp),
      world: worldLine(t, imp, /^Since \d{4}\b/.test(str(g.why))), r1: r1, r2: r2, r3: str(t.projection && t.projection.why),
      chip: str(g.risk_label) === word ? '' : str(g.risk_label) }; // the headline already says "No clear change"
  }
  // The NASA POWER grid against the nearest weather station (QA B10). other: this place's POWER answer the page
  // already has (or null); nothing is fetched for it.
  var MODEL_LINE = 'This comes from a weather model grid about 50 km wide. A weather station nearby can tell a different story.';
  function modelNote(t, other) {
    var id = (t.source || {}).id;
    if (id === 'power' && (t.variable === 'air_temp' || t.variable === 'air_temp_max')) return { line: MODEL_LINE, offer: 'ghcn' };
    if (id === 'ghcn' && other && (other.source || {}).id === 'power' && other.verdict && other.verdict !== t.verdict) return { line: 'The weather station and the model disagree here.', strong: true };
    return null;
  }

  // Rain's trend runs on yearly values (trend.yearly, in fit.units): the chart plots those. An answer without them, or
  // without a baseline, keeps the monthly plot.
  function yearlyOf(t, s) {
    var a = s.anomaly || {};
    return Array.isArray(t.yearly) && t.yearly.length && (t.baseline || {}).method !== 'none' && a.values ? t.yearly : null;
  }
  // The place chart's words (section 5).
  function chartText(t, s, ctx) {
    var imp = ctx.imperial, f = F(t, imp), b = t.baseline || {}, a = s.anomaly || {}, src = t.source || {}, fit = t.fit || {};
    var none = b.method === 'none' || !a.values, yrs = yrsOf(b), place = placeName(t, ctx.label), r = rate(t, imp), rk = t.range_kind || '95% range';
    var drawn = fitOnAxis(t, s, imp), yearly = !!yearlyOf(t, s);
    var seasons = !none && src.cadence !== 'annual' && !src.deseasoned_upstream;
    var sub = yearly ? "Each dot is one year's rain, compared with " + b.text + '.'
      : seasons ? 'Seasons removed: each month is compared with its own ' + own(b.text) + (a.kind === 'percent' ? ', as a share of the usual rain.' : '.') : '';
    if (t.variable === 'sea_level') sub += (sub ? ' ' : '') + 'Measured against the land, so land sinking adds to the rise.';
    var u = none ? f.unit(s.units) : f.unit(a.units);
    var uw = u + (t.variable === 'water_storage' ? ' of water' : '');
    var ytitle = none ? u + ', as measured'
      : yearly ? "Each year's rain, % above or below " + b.text
      : a.kind === 'percent' ? '% of the usual rain, compared with ' + b.text
      : uw + ' compared with ' + b.text;
    // a chart under 600 px: at most about 40 characters, so the title is never cut (QA B9)
    var ytitleNarrow = none ? ytitle : a.kind === 'percent' ? '% above or below the ' + yrs + ' average' : uw + ' compared with ' + yrs;
    var summary = ctx.name + ' at ' + place + ', ' + M(t.period.start) + ' to ' + M(t.period.end) + (none ? ', as measured.' : ', compared with ' + b.text + '.');
    if (r) {
      var line = drawn ? 'The trend line' : 'The trend';
      summary += ' ' + (clearV(t) ? line + (t.verdict === 'rising' ? ' rises ' : ' falls ') + unsign(r.text) + ' (' + rk + ' ' + r.range + ')'
        : line + ' moves ' + r.text + ", which we can't tell apart from no change (" + rk + ' ' + r.range + '),')
        + (drawn ? ' and stands at ' + f.val(fit.level_end, fit.units) + ' in ' + M(fit.end) : '') + '.';
      summary = summary.replace(/,\.$/, '.');
    }
    var pre = [];
    (s.flags || []).forEach(function (x, i) { if (x === 'preliminary' && s.values[i] != null) pre.push(s.times[i]); });
    if (pre.length) {
      var oneYear = pre.every(function (x) { return Y(x) === Y(pre[0]); });
      summary += ' ' + (oneYear ? andList(pre.map(function (x) { return MONTHS_LONG[mi(x) % 12]; })) + ' ' + Y(pre[0]) : andList(pre.map(M))) + (pre.length === 1 ? ' is' : ' are') + ' preliminary.';
    }
    var conf = str(t.meaning && t.meaning.confidence).toLowerCase();
    summary += ' Verdict: ' + verdictWord(t).toLowerCase() + (clearV(t) && conf ? ', ' + conf : '') + '.';
    var cols = ['Month', ctx.name + ' (' + normU(s.units) + ')'];
    if (!none) cols.push('Compared with ' + b.text + ' (' + normU(a.units) + ')');
    cols.push('Note');
    if (yearly) cols = ['Year', "Each year's rain, compared with " + b.text]; // the rows the chart plots (yearRows)
    return {
      title: ctx.name + ' at ' + place + ', ' + Y(t.period.start) + ' to ' + Y(t.period.end), sub: sub, src: srcText(t), url: recordUrl(src),
      latest: str(t.latest && t.latest.text), ytitle: ytitle, ytitleNarrow: ytitleNarrow, summary: summary, none: none, hasPre: pre.length > 0, yearly: yearly,
      hint: 'Hover, tap or use the arrow keys to read ' + (yearly ? 'a year.' : 'a month.'),
      noneNote: none ? 'This record has too few years from 1995 to 2014 for an average, so the chart shows the values as measured, with no trend line. The rate on the card still holds.' : '',
      legend: { monthly: yearly ? "Each year's rain" : none ? 'Monthly value, as measured' : 'Monthly value, seasons removed', range: rk + ' of the trend', zero: yrs + ' average (zero)', yrs: yrs },
      drawn: drawn, endLabel: drawn ? f.val(fit.level_end, fit.units) : '', endSub: fit.end ? 'trend line, ' + Mo(fit.end) : '',
      cols: cols, caption: 'Records: ' + srcText(t) + '. ' + str(t.latest && t.latest.text) + '.' + (yearly ? ' One row a year, as the chart shows; the CSV has every month.' : ''),
    };
  }
  // rain on yearly values: the table's rows, printed as the chart's readout prints them
  function yearRows(t, imp) {
    var f = F(t, imp);
    return t.yearly.map(function (q) { return [String(q.year), isNum(q.value) ? f.val(q.value, t.fit.units) : 'no data']; });
  }
  // the readout for point i: a month, or a year for rain on yearly values
  function readout(t, s, ctx, i) {
    var f = F(t, ctx.imperial), a = s.anomaly || {}, b = t.baseline || {}, yr = yearlyOf(t, s);
    if (yr) return yr[i].year + ': ' + (isNum(yr[i].value) ? f.val(yr[i].value, t.fit.units) + ' compared with the usual year (' + yrsOf(b) + ').' : 'no data.');
    var tm = s.times[i], v = s.values[i], an = a.values ? a.values[i] : null;
    var pre = s.flags && s.flags[i] === 'preliminary' ? ' Preliminary.' : '';
    if (v == null) return M(tm) + ': no data.';
    if (b.method === 'none' || an == null) return M(tm) + ': ' + f.lvl(v, s.units) + ', as measured.' + pre;
    return M(tm) + ': ' + (LEVELS[t.variable] ? f.lvl(v, s.units) + ' measured, ' : '') + f.val(an, a.units) + ' compared with the usual ' + MONTHS_LONG[mi(tm) % 12] + ' (' + yrsOf(b) + ').' + pre;
  }
  function tableRows(s) {
    var a = s.anomaly || {}, none = !a.values || (a.baseline && a.baseline.method === 'none');
    var txt = function (v) { return v == null ? 'no data' : String(v).replace('-', MINUS); };
    return s.times.map(function (tm, i) {
      var row = [tm, txt(s.values[i])];
      if (!none) row.push(s.values[i] == null ? 'no data' : txt(a.values[i]));
      row.push(s.flags && s.flags[i] === 'preliminary' ? 'Preliminary' : '');
      return row;
    });
  }

  // Numbers for the drawing, in the units shown. Yearly averages are drawing only (a year needs 9 regular months).
  function chartModel(t, s, imp) {
    var f = F(t, imp), b = t.baseline || {}, a = s.anomaly || {}, fit = t.fit || {}, none = b.method === 'none' || !a.values;
    var ms = s.times.map(mi), raw = none ? s.values : a.values, u = none ? s.units : a.units;
    var ys = raw.map(function (v) { return isNum(v) ? f.num(v, u, none) : null; });
    var pre = ms.map(function (_, i) { return !!s.flags && s.flags[i] === 'preliminary'; });
    var by = {};
    ys.forEach(function (v, i) { if (v != null && !pre[i]) { var y = Math.floor(ms[i] / 12); (by[y] = by[y] || []).push(v); } });
    var dots = Object.keys(by).filter(function (y) { return by[y].length >= 9; })
      .map(function (y) { return { x: +y * 12 + 6, v: by[y].reduce(function (p, q) { return p + q; }, 0) / by[y].length }; });
    var out = { none: none, ms: ms, ys: ys, pre: pre, dots: dots, x0: ms[0], x1: ms[ms.length - 1] + 1, fit: null, band: null };
    var yr = yearlyOf(t, s);
    if (yr) { // one point a year at mid-year (drawn at ms + 0.5), the axis from the first January to the last December
      out.ms = yr.map(function (q) { return q.year * 12 + 5.5; });
      out.ys = yr.map(function (q) { return isNum(q.value) ? f.num(q.value, fit.units) : null; });
      out.pre = yr.map(function () { return false; });
      out.dots = yr.filter(function (q) { return isNum(q.value); }).map(function (q) { return { x: q.year * 12 + 6, v: f.num(q.value, fit.units) }; });
      out.x0 = yr[0].year * 12; out.x1 = (yr[yr.length - 1].year + 1) * 12;
    }
    if (fitOnAxis(t, s, imp) && isNum(fit.change) && isNum(fit.change_low) && isNum(fit.change_high)) {
      var mid = fit.level_end - fit.change / 2, c = function (x) { return f.num(x, fit.units); };
      out.fit = { x0: mi(fit.start) + 0.5, x1: mi(fit.end) + 0.5, y0: c(fit.level_end - fit.change), y1: c(fit.level_end),
        lo0: c(mid - fit.change_low / 2), lo1: c(mid + fit.change_low / 2), hi0: c(mid - fit.change_high / 2), hi1: c(mid + fit.change_high / 2) };
      if (b.years) out.band = [b.years[0] * 12, (b.years[1] + 1) * 12];
    }
    return out;
  }

  // "How we calculated this": nine steps, each { title, short, words: [string | {list} | {text, csv}], work, link, fig, csv, noise }.
  function steps(t, s, ctx) {
    var imp = ctx.imperial, f = F(t, imp), b = t.baseline || {}, fit = t.fit || {}, w = t.world || {}, src = t.source || {}, g = t.guidance || {};
    var ex = t.explain || {}, dat = ex.data || {}, sea = ex.seasons, real = ex.real || {}, rec = t.record || {}, m = t.meaning || {}, a = s.anomaly || {};
    var r = rate(t, imp) || { text: '—', range: '—', per: '', value: NaN }, rk = t.range_kind || '95% range', measure = MEASURE[t.variable] || ctx.name.toLowerCase();
    var clear = clearV(t), pct = a.kind === 'percent', yrs = yrsOf(b), url = recordUrl(src), isSea = t.variable === 'sea_level';
    var byYear = isNum(dat.n_years); // rain: the trend runs on calendar years
    // a change is shown like a level (cm for sea level), a rate in its own unit (mm a year): cu is the rate's unit
    var cu = rconv(imp, 0, fit.units).unit, ch = function (x) { return withUnit(fmtNum(rconv(imp, x, fit.units).v, true), cu); };
    var nPre = (s.flags || []).filter(function (x, i) { return x === 'preliminary' && s.values[i] != null; }).length;
    var out = [];

    var nMiss = dat.n_missing_years, s1 = byYear
      ? ['We used ' + commas(dat.n_years) + ' yearly values of rain from ' + str(src.name) + ', for ' + str(dat.where) + ', built from ' + commas(dat.n_months) + ' monthly values. They run from '
        + Y(dat.start) + ' to ' + Y(dat.end) + '. A year counts when at least 11 of its months have data. ' + (nMiss ? (nMiss === 1 ? '1 year is' : commas(nMiss) + ' years are') + ' left out.' : 'No year is left out.')]
      : ['We used ' + commas(dat.n_months) + ' monthly values of ' + measure + ' from ' + str(src.name) + ', for ' + str(dat.where) + '. They run from ' + M(dat.start) + ' to ' + M(dat.end) + '. '
        + (dat.n_missing ? months(dat.n_missing) + ' missing.' : 'No months are missing.')];
    out.push({ title: 'The data',
      short: byYear ? commas(dat.n_years) + ' years from ' + srcIn(t) + ', ' + Y(dat.start) + ' to ' + Y(dat.end) : commas(dat.n_months) + ' months from ' + srcIn(t) + ', ' + M(dat.start) + ' to ' + M(dat.end),
      words: s1.concat(nPre ? [months(nPre) + ' preliminary: the provider may still change ' + (nPre === 1 ? 'it, so the trend leaves it out.' : 'them, so the trend leaves them out.')] : []),
      work: ['How the provider made them: ' + lc1(str(src.method)), 'Dataset: ' + str(src.dataset_id) + '.' + (src.version ? ' Version: ' + src.version + '.' : '') + ' Retrieved ' + D(src.retrieved) + '.'],
      link: url ? { text: 'Open this exact record ↗', href: url } : null });

    var s2 = { title: 'Seasons removed' };
    if (src.deseasoned_upstream) { s2.short = 'Already removed by the provider'; s2.words = ['The provider has already removed the seasons, so we use its values as they come.']; }
    else if (src.cadence === 'annual') { s2.short = 'Yearly values: no seasons to remove'; s2.words = ['These are yearly values, so there are no seasons to remove.']; }
    else if (!sea || !b.months || !a.values) {
      s2.short = 'No ' + yrs + ' average for each month';
      s2.words = ["This record has too few years from 1995 to 2014 to make each month's average, so this page shows its values as measured."];
    } else {
      var hi = MONTHS_LONG[sea.high_month - 1], lo = MONTHS_LONG[sea.low_month - 1], swing = f.amt(sea.swing, sea.units), p2;
      if (/ a month$/.test(str(sea.units))) { // rain: monthly totals, "263.4 mm"
        var mo = function (x) { var c = conv(t, imp, x, sea.units); return withUnit(fmtNum(c.v, false), c.unit.replace(/ a month$/, '')); };
        s2.short = 'Wettest in ' + hi + ' (' + mo(sea.high) + '), driest in ' + lo + ' (' + mo(sea.low) + ')';
        p2 = 'Here the wettest month, ' + hi + ', usually gets ' + mo(sea.high) + ' of rain, and the driest, ' + lo + ', ' + mo(sea.low) + '.';
      } else {
        s2.short = 'Highest in ' + hi + ', lowest in ' + lo + ': a swing of ' + swing;
        p2 = 'Here ' + measure + ' is usually ' + (LEVELS[t.variable] ? f.lvl(sea.high, sea.units) + ' in ' + hi + ' and ' + f.lvl(sea.low, sea.units) + ' in ' + lo
          : 'highest in ' + hi + ' and lowest in ' + lo) + ': a seasonal swing of ' + swing + '.';
      }
      p2 += ' The change we look for is ' + f.val(fit.change, fit.units) + ' over ' + Math.round(fit.years) + ' years. So we compare each month with its own ' + own(b.text) + ' first'
        + (pct ? ', and write the difference as a share of the usual rain' : '') + '.';
      s2.words = [p2, { text: "Check it yourself: the CSV's anomaly column is " + (pct ? "each value's difference from its month's " + yrs + ' average, as a % of the ' + yrs + ' average rate.'
        : "each value minus its month's " + yrs + ' average.'), csv: true }];
      var k = -1;
      for (var i = s.times.length - 1; i >= 0 && k < 0; i--) if (s.values[i] != null && a.values[i] != null && !(s.flags && s.flags[i] === 'preliminary')) k = i;
      if (k >= 0) {
        var mon = mi(s.times[k]) % 12, v = s.values[k], nrm = b.months[mon], an = a.values[k];
        var sub = function (x) { var q = f.lvl(x, s.units); return q.charAt(0) === MINUS ? '(' + q + ')' : q; }; // "− (−10.6 cm)"
        s2.work = [pct ? M(s.times[k]) + ': (' + f.lvl(v, s.units) + ' − ' + sub(nrm) + ', the usual ' + MONTHS_LONG[mon] + ') ÷ ' + f.lvl(b.value, s.units) + ', the usual rate = ' + f.val(an, a.units)
          : M(s.times[k]) + ': ' + f.lvl(v, s.units) + ' − ' + sub(nrm) + ' (the usual ' + MONTHS_LONG[mon] + ') = ' + f.val(an, a.units)];
        if (isSea) s2.work.push("Heights are against the gauge's own zero.");
        s2.fig = true;
      }
    }
    out.push(s2);

    // the level at this place: rain says its annual total as the API gives it ("about 1,239 mm a year"), never converted from a rate
    var lvl3 = isNum(b.annual_total_mm) ? 'about ' + (imp ? fmtNum(b.annual_total_mm / 25.4, false) + NB + 'in' : commas(Math.round(b.annual_total_mm)) + NB + 'mm') + ' a year'
      : LEVELS[t.variable] && t.variable !== 'precip' && isNum(b.value) ? f.lvl(b.value, s.units) : '';
    var s3 = { title: 'One baseline' };
    if (b.method === 'provider') {
      s3.short = 'Every level is compared with ' + b.text;
      s3.words = ['Every level on this page is compared with ' + b.text + ': ' + stop(str(b.label)) + " Water storage has no expert projection, so it keeps the provider's own reference."];
    } else if (b.method === 'none') {
      s3.short = 'No 1995–2014 average for this record';
      s3.words = ['This record has too few years from 1995 to 2014 to make that average, so this page shows no levels for it, only the rate.'];
      s3.work = [b.years_covered + ' of the 20 years have at least 9 months of data. We need at least 15, or a record of 30 years or more with at least 5 of the 20 years counted and data both before 1995 and after 2014.'];
    } else {
      s3.short = 'Every level is compared with ' + b.text + (lvl3 ? ' here, ' + lvl3 : '');
      s3.words = ['Every level on this page is compared with ' + b.text + ' at this place' + (lvl3 ? ', ' + lvl3 : '') + ', so 0 means that average. '
        + 'The card, the chart, the table and the CSV all use it. Expert projections from the IPCC use the same years, so past and future can share one axis.'];
      s3.work = [b.method === 'fitted'
        ? b.years_covered + ' of the 20 years have at least 9 months of data; we need 15. The record spans ' + Math.round(rec.years) + " years, at least 5 of the 20 years are counted, and it has data both before 1995 and after 2014, so we fit the trend and the seasons together and take the line's 1995–2014 average (" + b.label + ').'
        : b.years_covered + ' of the 20 years from 1995 to 2014 have at least 9 months of data. We need at least 15.'];
    }
    out.push(s3);

    var dec = /per decade$/.test(r.per); // rain: "of the 1995–2014 average per decade"
    var s4 = { title: 'The trend and its range', short: r.text + ', ' + rk + ' ' + r.range };
    s4.words = [(clear
      ? 'From ' + Y(fit.start) + ' to ' + Y(fit.end) + ', ' + measure + ' here ' + (t.verdict === 'rising' ? 'rose' : 'fell') + ' by about ' + unsign(r.text) + (dec ? ' (every 10 years).' : '.')
      : 'From ' + Y(fit.start) + ' to ' + Y(fit.end) + ', ' + measure + ' here changed by ' + r.text + (dec ? ' (every 10 years)' : '') + ", which we can't tell apart from no change.")
      + ' The trend is very likely between ' + r.range.replace(' to ', ' and ') + ' (' + rk + ').',
      "We use Sen's slope: the middle of the slopes between every pair of " + (byYear ? "years. One odd year can't pull it far." : "months. One odd month can't pull it far.")];
    if (rec.status === 'short') s4.words.push('This is a short record (' + Math.round(rec.years) + ' years). Its trend can move when new years arrive.');
    // fit.change is slope_per_decade × fit.years / 10, so the sum multiplies those numbers as the API gives them (a rate a
    // year is the decade's rate ÷ 10: unit display). Rain's % rate exists only in headline_rate.
    var mul = normU(t.units) === normU(fit.units) && isNum(t.slope_per_decade) ? given(imp, t.slope_per_decade, fit.units, !dec)
      : r.unit === cu && isNum(r.value) && r.unit === '%' ? (r.value > 0 ? '+' : '') + fixed(r.value, (String(r.value).split('.')[1] || '').length) : '';
    s4.work = [];
    // the span fit.change uses: its months, first to last (fit.years is rounded to 0.1, so 105.7 × the rate can miss by a digit)
    var span = /-/.test(str(fit.start)) && /-/.test(str(fit.end)) ? (mi(fit.end) - mi(fit.start) + 1) / 12 : fit.years;
    if (mul && isNum(fit.change)) { // the sum in the rate's unit; a change in another unit (sea level: cm) then says it in that unit too
      s4.work.push('Over the record: ' + withUnit(mul, cu) + ' ' + r.per + ' × ' + (dec ? fixed(span / 10, 2) + ' decades' : Number(span.toFixed(3)) + ' years') + ' = ' + ch(fit.change)
        + (f.unit(fit.units) !== cu ? ', which is ' + f.val(fit.change, fit.units) : '') + ' (' + rk + ' ' + f.rng(fit.change_low, fit.change_high, fit.units) + ').');
    }
    if (isNum(fit.level_end)) s4.work.push('The trend line ends at ' + f.val(fit.level_end, fit.units) + ' compared with ' + b.text + ', in ' + M(fit.end) + '.');
    var nw = nowOf(t, imp);
    if (nw) s4.work.push('The card’s “Now”, ' + nw.value + ', is ' + (nw.rain ? 'the rain measured in ' : 'the measured average of ') + nw.label + ', not a point on the line.');
    out.push(s4);

    var pv = isNum(real.p_value) ? real.p_value : t.p_value, conf = str(m.confidence);
    var s5 = { title: 'Is it real?', short: conf + ': by chance, ' + real.in_100 + ' in 100', noise: true,
      words: ['If there were no real trend here, a trend at least this strong, up or down, would turn up by chance in ' + real.in_100 + ' of 100 records like this one.', str(real.rule)] };
    if (!clear) s5.words.push("That does not mean nothing changed. The data can't rule out anything from " + r.range + '.');
    s5.work = ['p-value ' + (pv < 0.001 ? 'under 0.001' : fixed(pv, 3)) + ', so ' + (pv < 0.05 ? 'below' : 'not below') + ' 0.05 · ' + rk + ' ' + r.range + ', '
      + (r.low > 0 ? 'all above zero' : r.high < 0 ? 'all below zero' : 'which includes zero') + ' → ' + conf.toLowerCase() + '.'];
    // what we did, not what the data are (white noise can come out widened too)
    if (real.widened) s5.work.push(byYear ? 'Years next to each other can be alike. We allow for that, so this range is wider than ' + commas(dat.n_years) + ' separate years would give.'
      : 'Months next to each other can be alike, and so can whole years in a row. We allow for that, so this range is wider than ' + commas(dat.n_months) + ' separate months would give.');
    if (isSea) s5.work.push('Slow swings in the ocean that last a decade or more can still make this range a little too narrow.');
    if (t.variable === 'water_storage') s5.work.push('Slow swings in rain and groundwater that last several years can still make this range a little too narrow.');
    out.push(s5);

    var wp = worldParts(t, imp), s6 = { title: 'Compared with the world' };
    if (wp) {
      var th = w.thresholds || {}, lbl = str(g.risk_label), two = / to /.test(lbl), unclear = /^Risk level unclear\b/.test(lbl);
      // the ratio's 95% range, unless the API's sentence already gives it
      var rr = wp.ratio && isNum(w.ratio_low) && isNum(w.ratio_high) ? fixed(w.ratio_low, 1) + ' to ' + fixed(w.ratio_high, 1) : '';
      if (rr && str(w.text).indexOf(rr) >= 0) rr = '';
      // the division in metric, like the API's sentence above it ("(in metric)" in °F or inches): one unit in the step (B5)
      var wm = worldParts(t, false);
      s6.short = worldLine(t, imp);
      s6.words = [imp ? metric(w.text) : str(w.text)];
      // the owner's domain review: say how the two figures are measured, in plain words
      if (isSea) s6.words.push('Satellites measure the height of the sea surface itself. The tide gauge measures the sea against the land, so if the land here is sinking, that adds to the local number.');
      if (t.variable === 'air_temp') s6.words.push('The world figure is built from weather stations on land.'
        + (src.id === 'power' || src.id === 'era5' ? ' The number here comes from a weather model, so the two are measured in different ways.' : ''));
      s6.work = [(wp.ratio ? fmtNum(wm.a, false) + ' ÷ ' + fmtNum(wm.b, false) + ' = ' + wp.ratio + ' · ' + (rr ? rr + ' times (' + rk + ') · ' : '') : '')
        + M(w.window.start) + ' to ' + M(w.window.end) + ' · ' + stop(str(w.method)),
        '1× is the same as the world. ' + th.high + '× or more: high risk. ' + th.moderate + '× to ' + th.high + '×: moderate risk. Under ' + th.moderate + '×: low risk. '
        + (unclear ? 'Here the ' + rk + ' spans every level, so the risk level is unclear.'
          : 'Here: ' + (lbl ? lbl.toLowerCase() : 'no risk level') + (two && rr ? ', because the ' + rk + ' spans more than one level.' : '.'))];
      if (isSea) s6.work.push('The full record, ' + Y(fit.start) + ' to ' + Y(fit.end) + ': ' + r.text + '. It gets no world ratio, because satellites only start in 1993.');
      if (isSea && w.source && str(w.source.method)) s6.work.push('The world figure: ' + lc1(stop(w.source.method))); // it names what the satellites don't correct for
      s6.link = w.source && https(w.source.record_url) ? { text: w.source.name + ' ↗', href: w.source.record_url } : null;
    } else {
      s6.short = str(w.why_none) || str(w.text);
      s6.words = [s6.short];
    }
    out.push(s6);

    var pj = str(t.projection && t.projection.why), fl = g.future_link;
    out.push({ title: 'What comes next', short: pj, words: [pj, NO_FUTURE],
      link: fl && https(fl.url) && str(fl.label) ? { text: fl.label + ' ↗', href: fl.url } : null });

    var notes = [];
    (t.caveats || []).concat(s.notes || []).forEach(function (n) { if (str(n) && notes.indexOf(n) < 0) notes.push(n); });
    var last = 'This shows whether ' + measure + " changed here. It doesn't say why.";
    out.push({ title: 'Things to keep in mind', short: notes.length ? notes[0] + (notes.length > 1 ? ' And ' + (notes.length - 1) + ' more' : '') : last,
      words: [{ list: notes.concat([last]) }] });

    var list = [{ text: 'Records: ' + str(src.name) + ', ' + str(src.dataset_id) + (src.version ? ', version ' + src.version : '') + '. Retrieved ' + D(src.retrieved) + '. ',
      link: url ? { text: 'Open this exact record ↗', href: url } : null }];
    if (wp && w.source) list.push({ text: 'World figure: ' + w.source.name + '. Retrieved ' + D(w.source.retrieved) + '. ', link: https(w.source.record_url) ? { text: 'Open it ↗', href: w.source.record_url } : null });
    list.push({ text: "Our calculation: the Mann-Kendall test and Sen's slope on " + (byYear ? 'yearly rain' : 'monthly values with seasons removed') + (b.method === 'none' ? '.' : ', against ' + b.text + '.') });
    out.push({ title: 'Sources', short: str(src.name) + (wp && w.source ? '; world figure from ' + lc1(str(w.source.name)) : ''), words: [{ list: list }], csv: true });
    return out;
  }

  /* CSV (section 8): built from the fields, values in the record's own units. */
  function slug(x) { return String(x).toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'place'; }
  // A text cell: one that starts with = + - @ tab or CR would run as a formula in a spreadsheet, so it gets a ' first;
  // then quotes when it holds a comma, a quote or a line break. Number cells never come through here.
  function csvField(x) {
    var s = String(x);
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }
  // A header line starts with "#" and is never quoted, so tools that skip "#" lines skip it. A spreadsheet still splits
  // it at commas (some imports at tabs too): a piece that would start a formula there gets a ' first; quotes, tabs and
  // line breaks can't open a cell.
  function headLine(x) { return String(x).replace(/[\r\n\t]+/g, ' ').replace(/"/g, "'").replace(/,(\s*)(?=[=+\-@])/g, ",$1'"); }
  // "Station: The Battery, lat 40.7006, lon -74.0142" from trend.place; a grid source names only its point
  function placeLine(t) {
    var p = t.place || {}, nm = str(p.name), at = 'lat ' + p.lat + ', lon ' + p.lon;
    if (!isNum(p.lat) || !isNum(p.lon)) return '';
    if (STATION[(t.source || {}).id]) return 'Station: ' + (nm ? nm + ', ' : '') + at;
    return 'Grid point: ' + (nm && !/^-?[\d.]+, ?-?[\d.]+$/.test(nm) ? nm + ', ' : '') + at;
  }
  function cell(v) { return v == null ? '' : String(v); }
  function baseLine(b, pct, withMethod) {
    if (!b || b.method === 'none') return 'none (too few years from 1995 to 2014)';
    var y = yrsOf(b);
    return b.text + (withMethod ? ' (' + b.method + ')' : '') + '; anomaly = '
      + (pct ? 'the difference from the ' + y + ' mean of its calendar month, as a % of the ' + y + ' average rate' : 'value minus the ' + y + ' mean of its calendar month');
  }
  function rows(s, place) {
    var a = s.anomaly || {}, none = !a.values || (a.baseline && a.baseline.method === 'none');
    return s.times.map(function (tm, i) {
      return (place ? [csvField(place)] : []).concat([tm, cell(s.values[i]), none ? '' : cell(a.values[i]), s.flags && s.flags[i] === 'preliminary' ? 'preliminary' : '']).join(',');
    });
  }
  function csvPlace(t, s, ctx) {
    var src = t.source || {}, a = s.anomaly || {}, pl = placeLine(t), thru = str(t.latest && t.latest.text).replace(/^Data through /, '');
    // no "# Datum:" line: the API has no datum field (source.method names it in words)
    var head = ['# Bhoomi: ' + ctx.name + ' at ' + ctx.label, '# Source: ' + str(src.name),
      '# Dataset: ' + str(src.dataset_id) + '; version: ' + (src.version || 'not named by the provider'), '# Record: ' + recordUrl(src)]
      .concat(pl ? ['# ' + pl] : [], ['# Baseline: ' + baseLine(t.baseline, a.kind === 'percent', true), '# Method: ' + str(src.method), '# Retrieved: ' + str(src.retrieved)],
        thru ? ['# Data through: ' + thru] : [], ['# Built with AI assistance. bhoomi.earth']).map(headLine);
    head.push('time,value_' + s.units + ',anomaly_' + (a.units || s.units) + ',flag');
    return { name: 'bhoomi-' + ctx.slug + '-' + slug(ctx.label) + '.csv', text: head.concat(rows(s)).join('\n') + '\n' };
  }
  // list: [{label, t, s}], the plotted places in pin order
  function csvCompare(list, ctx) {
    var s0 = list[0].s, a0 = s0.anomaly || {};
    var head = ['# Bhoomi: ' + ctx.name + ' at your places', '# Baseline: ' + baseLine(list[0].t.baseline, a0.kind === 'percent', false), '# Built with AI assistance. bhoomi.earth'];
    list.forEach(function (p) {
      var src = p.t.source || {};
      head.push('# Place: ' + p.label + '; Source: ' + str(src.name) + '; Dataset: ' + str(src.dataset_id) + '; version: ' + (src.version || 'not named by the provider')
        + '; Record: ' + recordUrl(src) + '; Method: ' + str(src.method) + '; Retrieved: ' + str(src.retrieved));
    });
    head = head.map(headLine);
    head.push('place,time,value_' + s0.units + ',anomaly_' + (a0.units || s0.units) + ',flag');
    var body = [];
    list.forEach(function (p) { body = body.concat(rows(p.s, p.label)); });
    return { name: 'bhoomi-' + ctx.slug + '-your-places.csv', text: head.concat(body).join('\n') + '\n' };
  }

  /* chart ticks */
  function niceNum(x, round) {
    var e = Math.floor(Math.log10(x)), f = x / Math.pow(10, e);
    var n = round ? (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) : (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10);
    return n * Math.pow(10, e);
  }
  function niceTicks(lo, hi, n) {
    if (!(hi > lo)) { var pad = Math.abs(lo) * 0.1 || 1; lo -= pad; hi += pad; }
    var step = niceNum(niceNum(hi - lo, false) / (n - 1), true);
    var start = Math.floor(lo / step + 1e-9) * step, end = Math.ceil(hi / step - 1e-9) * step, ticks = [];
    for (var v = start, i = 0; v <= end + step / 2; i++, v = start + i * step) ticks.push(+v.toFixed(10));
    return { ticks: ticks, step: step, lo: ticks[0], hi: ticks[ticks.length - 1] };
  }
  function tickLabel(v, step, signed) {
    var d = step >= 1 ? 0 : Math.min(2, Math.ceil(-Math.log10(step) - 1e-9)), s = fixed(v, d);
    return signed && v > 0 ? '+' + s : s;
  }
  // year ticks at least 56 px apart (pw: plot width in px)
  function yearTicks(m0, m1, pw) {
    var span = (m1 - m0) / 12, need = span >= 2 ? 2 : 1, STEPS = [1, 2, 5, 10, 20, 25, 50];
    var at = function (st) { var r = []; for (var y = Math.ceil(m0 / 12 / st) * st; y * 12 <= m1; y += st) r.push(y); return r; };
    var step = STEPS.filter(function (st) { return span > 0 && st * pw / span >= 56 && at(st).length >= need; })[0];
    if (step === undefined) step = STEPS.slice().reverse().filter(function (st) { return at(st).length >= need; })[0] || 1;
    return at(step);
  }
  /* PURE END */

  /* ---------- DOM ---------- */
  var SVGNS = 'http://www.w3.org/2000/svg';
  var $ = function (id) { return document.getElementById(id); };
  function h(tag, attrs) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) n.setAttribute(k, attrs[k]);
    for (var i = 2; i < arguments.length; i++) if (arguments[i] != null && arguments[i] !== '') n.append(arguments[i]);
    return n;
  }
  function sv(tag, attrs, text) {
    var n = document.createElementNS(SVGNS, tag);
    for (var k in attrs || {}) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function ext(text, href) { return href ? h('a', { href: href, target: '_blank', rel: 'noopener', class: 'srclink' }, text) : text.replace(/\s*↗$/, ''); }
  function download(c) {
    var url = URL.createObjectURL(new Blob(['﻿' + c.text], { type: 'text/csv;charset=utf-8' })); // the mark tells spreadsheets it is UTF-8
    var a = h('a', { href: url, download: c.name });
    document.body.append(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }
  function csvButton(get) { var b = h('button', { type: 'button', class: 'btn' }, 'Download CSV'); b.addEventListener('click', function () { download(get()); }); return b; }
  function vkey(t) { return t.verdict === 'rising' ? 'rising' : t.verdict === 'falling' ? 'falling' : 'none'; }
  function key(art, text) { return h('span', { class: 'lg' }, art, text); }
  function swatch(draw) { var s = sv('svg', { width: 28, height: 12, 'aria-hidden': 'true' }); draw.forEach(function (d) { s.append(sv(d[0], d[1])); }); return s; }

  var cur = null; // the place chart on screen: { pin, ctx, T, box, ro }

  function showPlace(pin, ctx) {
    var sec = $('place-chart'), t = pin.trend, s = pin.series, T = chartText(t, s, ctx);
    clear(sec);
    sec.dataset.verdict = vkey(t);
    var sub = h('p', { class: 'csub' });
    sub.append((T.sub ? T.sub + ' ' : '') + 'Records: ', T.url ? h('a', { href: T.url, target: '_blank', rel: 'noopener' }, T.src + NB + '↗') : T.src, '. ' + T.latest + '.');
    sec.append(h('div', { class: 'chead' }, h('div', {}, h('h2', { id: 'pc-h' }, T.title), sub), csvButton(function () { return csvPlace(t, s, ctx); })));
    var box = h('div', { class: 'pc-box' });
    sec.append(box);
    if (T.noneNote) sec.append(h('p', { class: 'note' }, T.noneNote));
    var lg = h('div', { class: 'legend' }, h('span', { class: 'grp' }, 'From the records:'),
      key(swatch(T.yearly ? [['line', { x1: 1, y1: 6, x2: 27, y2: 6, class: 's-month' }], ['circle', { cx: 14, cy: 6, r: 3.4, class: 's-year' }]]
        : [['line', { x1: 1, y1: 6, x2: 27, y2: 6, class: 's-month' }]]), T.legend.monthly));
    if (T.hasPre && !T.yearly) lg.append(key(swatch([['line', { x1: 1, y1: 6, x2: 27, y2: 6, class: 's-pre' }]]), 'Preliminary month (may still change)'));
    lg.append(h('span', { class: 'grp' }, 'Our calculation:'));
    if (!T.yearly) lg.append(key(swatch([['circle', { cx: 14, cy: 6, r: 3.4, class: 's-year' }]]), 'Yearly average'));
    if (T.drawn) {
      lg.append(key(swatch([['line', { x1: 2, y1: 6, x2: 26, y2: 6, class: 's-trend' }]]), 'Trend line'),
        key(swatch([['rect', { x: 1, y: 1, width: 26, height: 10, class: 's-fan' }], ['line', { x1: 1, y1: 1, x2: 27, y2: 1, class: 's-edge' }], ['line', { x1: 1, y1: 11, x2: 27, y2: 11, class: 's-edge' }]]), T.legend.range));
    }
    if (!T.none) lg.append(key(swatch([['line', { x1: 1, y1: 6, x2: 27, y2: 6, class: 'c-zero' }]]), T.legend.zero));
    var ro = h('p', { class: 'readout', 'aria-live': 'polite' }, T.hint);
    sec.append(lg, ro, h('p', { class: 'summary' }, T.summary), dataTable(T, function () { return T.yearly ? yearRows(t, ctx.imperial) : tableRows(s); }));
    sec.hidden = false;
    cur = { pin: pin, ctx: ctx, T: T, box: box, ro: ro };
    draw();
  }

  function dataTable(T, rows) { // rows: a function, called when the table is first opened
    var body = h('tbody'), det = h('details', { class: 'pc-table' }, h('summary', {}, h('span', { class: 'mark', 'aria-hidden': 'true' }), 'Show the data as a table'));
    var head = h('tr');
    T.cols.forEach(function (c) { head.append(h('th', { scope: 'col' }, c)); });
    det.append(h('div', { class: 'table-scroll', tabindex: '0', role: 'region', 'aria-label': T.yearly ? 'Yearly data table' : 'Monthly data table' },
      h('table', {}, h('caption', {}, T.caption), h('thead', {}, head), body)));
    det.addEventListener('toggle', function () { // built when first opened: a century of months is a long table
      if (!det.open || body.firstChild) return;
      var frag = document.createDocumentFragment();
      rows().forEach(function (r) { var tr = h('tr'); r.forEach(function (c) { tr.append(h('td', {}, c)); }); frag.append(tr); });
      body.append(frag);
    });
    return det;
  }

  // Drawn at the box's width (1 unit = 1 px, text 12 px or more), 330 tall.
  function draw() {
    if (!cur) return;
    var box = cur.box, t = cur.pin.trend, s = cur.pin.series, T = cur.T, md = chartModel(t, s, cur.ctx.imperial);
    clear(box);
    var W = Math.max(280, Math.round(box.clientWidth || 700)), H = 330, narrow = W < 600, ml = 52, mr = narrow ? 96 : 150, mt = 34, mb = 34;
    var pw = W - ml - mr, ph = H - mt - mb;
    var vals = md.ys.filter(function (v) { return v != null; });
    if (!md.none) vals.push(0);
    if (md.fit) vals.push(md.fit.y0, md.fit.y1, md.fit.lo0, md.fit.lo1, md.fit.hi0, md.fit.hi1);
    var tk = niceTicks(Math.min.apply(null, vals), Math.max.apply(null, vals), 5);
    var X = function (m) { return ml + (m - md.x0) / (md.x1 - md.x0) * pw; };
    var Yp = function (v) { return mt + (tk.hi - v) / (tk.hi - tk.lo) * ph; };
    var root = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img', tabindex: '0', 'aria-label': T.summary, class: 'pc-svg' });
    root.append(sv('text', { x: 0, y: 14, class: 'pc-ytitle' }, narrow ? T.ytitleNarrow : T.ytitle));
    if (md.band) {
      var bx0 = Math.max(ml, X(md.band[0])), bx1 = Math.min(ml + pw, X(md.band[1]));
      if (bx1 > bx0) {
        root.append(sv('rect', { x: bx0, y: mt, width: bx1 - bx0, height: ph, class: 'pc-band' }));
        if (bx1 - bx0 > 64) root.append(sv('text', { x: (bx0 + bx1) / 2, y: mt + 14, 'text-anchor': 'middle', class: 'pc-t' }, T.legend.yrs));
      }
    }
    tk.ticks.forEach(function (v) {
      root.append(sv('line', { x1: ml, x2: ml + pw, y1: Yp(v), y2: Yp(v), class: 'c-grid' }));
      root.append(sv('text', { x: ml - 8, y: Yp(v) + 4, 'text-anchor': 'end', class: 'pc-t' }, tickLabel(v, tk.step, !md.none)));
    });
    yearTicks(md.x0, md.x1 - 1, pw).forEach(function (y) { // up to the last month, not past it
      var x = X(y * 12);
      if (x < ml - 0.5 || x > ml + pw + 0.5) return;
      root.append(sv('line', { x1: x, x2: x, y1: mt + ph, y2: mt + ph + 4, class: 'pc-tick' }));
      root.append(sv('text', { x: x, y: H - 10, 'text-anchor': 'middle', class: 'pc-t' }, String(y)));
    });
    var F0 = md.fit;
    if (F0) {
      var pts = [[F0.x0, F0.lo0], [F0.x1, F0.lo1], [F0.x1, F0.hi1], [F0.x0, F0.hi0]].map(function (p) { return X(p[0]).toFixed(1) + ',' + Yp(p[1]).toFixed(1); });
      root.append(sv('polygon', { points: pts.join(' '), class: 's-fan' }));
      root.append(sv('line', { x1: X(F0.x0), y1: Yp(F0.lo0), x2: X(F0.x1), y2: Yp(F0.lo1), class: 's-edge' }));
      root.append(sv('line', { x1: X(F0.x0), y1: Yp(F0.hi0), x2: X(F0.x1), y2: Yp(F0.hi1), class: 's-edge' }));
    }
    // monthly values (regular months; a gap or a preliminary month breaks the line), then preliminary months joined to the last regular one
    var d = '', dp = '', pen = false, lastReg = null;
    md.ys.forEach(function (v, i) {
      if (v == null || md.pre[i]) { pen = false; return; }
      d += (pen ? 'L' : 'M') + X(md.ms[i] + 0.5).toFixed(1) + ' ' + Yp(v).toFixed(1);
      pen = true; lastReg = i;
    });
    md.ys.forEach(function (v, i) {
      if (v == null || !md.pre[i]) return;
      if (!dp) dp = lastReg != null ? 'M' + X(md.ms[lastReg] + 0.5).toFixed(1) + ' ' + Yp(md.ys[lastReg]).toFixed(1) : '';
      dp += (dp ? 'L' : 'M') + X(md.ms[i] + 0.5).toFixed(1) + ' ' + Yp(v).toFixed(1);
    });
    root.append(sv('path', { d: d, class: 's-month' }));
    if (dp) root.append(sv('path', { d: dp, class: 's-pre' }));
    if (!md.none) root.append(sv('line', { x1: ml, x2: ml + pw, y1: Yp(0), y2: Yp(0), class: 'c-zero' }));
    md.dots.forEach(function (q) { root.append(sv('circle', { cx: X(q.x).toFixed(1), cy: Yp(q.v).toFixed(1), r: 3.4, class: 's-year' })); });
    var xr = ml + pw + 12;
    if (F0) {
      root.append(sv('line', { x1: X(F0.x0), y1: Yp(F0.y0), x2: X(F0.x1), y2: Yp(F0.y1), class: 's-trend' }));
      root.append(sv('circle', { cx: X(F0.x1), cy: Yp(F0.y1), r: 5, class: 's-end' }));
      // the end label moves away from the zero label when they would touch; the zero label never moves
      var ez = Yp(0), ey = Yp(F0.y1) + 5;
      if (Math.abs(ey - ez) < 40) ey = ey <= ez ? ez - 40 : ez + 44;
      ey = Math.min(H - mb - (narrow ? 0 : 15), Math.max(mt + 10, ey));
      root.append(sv('text', { x: xr, y: ey, class: 'pc-end' }, T.endLabel));
      if (!narrow) root.append(sv('text', { x: xr, y: ey + 15, class: 'pc-t' }, T.endSub));
      // narrow: "0 = the" over the years (the 96 px margin can't hold "0 = the 1995–2014" on one line)
      root.append(sv('text', { x: xr, y: ez + 4, class: 'pc-t' }, narrow ? '0 = the' : '0 = the ' + T.legend.yrs));
      root.append(sv('text', { x: xr, y: ez + 18, class: 'pc-t' }, narrow ? T.legend.yrs : 'average'));
    }
    var rule = sv('line', { y1: mt, y2: mt + ph, class: 'c-rule', visibility: 'hidden' });
    root.append(rule);
    box.append(root);
    cur.W = W;

    var sel = null, ms = md.ms;
    var select = function (i) {
      sel = i;
      cur.ro.classList.toggle('sel', i != null);
      if (i == null) { rule.setAttribute('visibility', 'hidden'); cur.ro.textContent = T.hint; return; }
      var x = X(ms[i] + 0.5);
      rule.setAttribute('x1', x); rule.setAttribute('x2', x); rule.setAttribute('visibility', 'visible');
      cur.ro.textContent = readout(t, s, cur.ctx, i);
    };
    var at = function (e) {
      var rc = root.getBoundingClientRect(), m = md.x0 + ((e.clientX - rc.left) / rc.width * W - ml) / pw * (md.x1 - md.x0) - 0.5;
      var lo = 0, hi = ms.length - 1;
      while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (ms[mid] < m) lo = mid; else hi = mid; }
      select(Math.abs(ms[lo] - m) <= Math.abs(ms[hi] - m) ? lo : hi);
    };
    root.addEventListener('pointermove', at);
    root.addEventListener('pointerdown', at);
    root.addEventListener('keydown', function (e) {
      var n = ms.length, big = e.shiftKey ? 12 : 1, i;
      if (e.key === 'ArrowLeft') i = sel == null ? n - 1 : Math.max(0, sel - big);
      else if (e.key === 'ArrowRight') i = sel == null ? n - 1 : Math.min(n - 1, sel + big);
      else if (e.key === 'Home') i = 0;
      else if (e.key === 'End') i = n - 1;
      else if (e.key === 'Escape') { select(null); return; }
      else return;
      e.preventDefault();
      select(i);
    });
  }

  // step 2: the last 10 years as measured, then with seasons removed (shape only, aria-hidden)
  function figure(t, s, ctx) {
    var f = F(t, ctx.imperial), a = s.anomaly || {}, from = Math.max(0, s.times.length - 120);
    var strip = function (vals) {
      var ok = vals.filter(function (v) { return v != null; }), lo = Math.min.apply(null, ok), hi = Math.max.apply(null, ok), n = vals.length - 1 || 1, d = '', pen = false;
      vals.forEach(function (v, i) {
        if (v == null) { pen = false; return; }
        d += (pen ? 'L' : 'M') + (i / n * 120).toFixed(2) + ' ' + (54 - (hi > lo ? (v - lo) / (hi - lo) : 0.5) * 52).toFixed(2);
        pen = true;
      });
      var g = sv('svg', { viewBox: '0 0 120 56', preserveAspectRatio: 'none', class: 'fig-strip', 'aria-hidden': 'true', focusable: 'false' });
      g.append(sv('path', { d: d, 'vector-effect': 'non-scaling-stroke' }));
      return g;
    };
    var au = a.kind === 'percent' ? '% of the yearly average rate' : f.unit(a.units);
    return h('div', { class: 'fig', 'aria-hidden': 'true' },
      h('p', { class: 'fig-l' }, 'As measured (' + f.unit(s.units) + '), last 10 years'), strip(s.values.slice(from)),
      h('p', { class: 'fig-l' }, 'Seasons removed (' + au + ' compared with ' + yrsOf(t.baseline) + ')'), strip(a.values.slice(from)));
  }

  function wordsNode(item, t, s, ctx) {
    if (typeof item === 'string') return item ? h('p', {}, item) : null;
    if (item.list) {
      var ul = h('ul', { class: 'caveats' });
      item.list.forEach(function (x) { ul.append(typeof x === 'string' ? h('li', {}, x) : h('li', {}, x.text, x.link ? ext(x.link.text, x.link.href) : '')); });
      return ul;
    }
    return h('div', { class: 'check' }, h('p', {}, item.text), csvButton(function () { return csvPlace(t, s, ctx); }));
  }

  function showHow(pin, ctx, fresh) {
    var sec = $('how'), ol = $('how-steps'), slot = $('noise-slot'), t = pin.trend, s = pin.series, keep = [];
    if (!fresh) Array.prototype.forEach.call(ol.querySelectorAll(':scope > li > details'), function (d, i) { keep[i] = d.open; });
    sec.append(slot); // park "Real or noise?" while the steps are rebuilt
    clear(ol);
    $('how-lead').textContent = 'For ' + ctx.label + '. Every number below is the one the card and the chart use.';
    steps(t, s, ctx).forEach(function (st, i) {
      var open = fresh ? OPEN_STEPS.indexOf(i + 1) >= 0 : !!keep[i];
      var det = h('details', open ? { open: '' } : {}, h('summary', {},
        h('span', { class: 'step-n' }, String(i + 1)), h('span', { class: 'step-t' }, st.title), h('span', { class: 'step-s' }, st.short), h('span', { class: 'step-c', 'aria-hidden': 'true' })));
      var words = h('div', { class: 'words' }), side = h('div', { class: 'step-w' });
      st.words.forEach(function (x) { var n = wordsNode(x, t, s, ctx); if (n) words.append(n); });
      if (st.link) words.append(h('p', { class: 'link' }, ext(st.link.text, st.link.href)));
      if (st.csv) words.append(h('p', { class: 'link' }, csvButton(function () { return csvPlace(t, s, ctx); })));
      if (st.work && st.work.length) {
        var wk = h('div', { class: 'work' }, h('p', { class: 'wl' }, 'The working'));
        st.work.forEach(function (x) { wk.append(h('p', {}, x)); });
        side.append(wk);
      }
      if (st.fig) side.append(figure(t, s, ctx));
      var body = h('div', { class: 'step-b' }, words);
      if (side.firstChild) body.append(side); else body.classList.add('one');
      if (st.noise) body.append(slot);
      det.append(body);
      ol.append(h('li', {}, det));
    });
    sec.hidden = false;
  }

  // pin: the selected pin (or null); fresh: a new answer, so the steps go back to their default state
  function show(pin, ctx, fresh) {
    var pc = $('place-chart'), how = $('how');
    if (!pin || pin.status === 'error') { pc.hidden = true; how.hidden = true; cur = null; return; }
    if (pin.status !== 'ok') {
      cur = null; how.hidden = true;
      clear(pc); pc.removeAttribute('data-verdict');
      pc.append(h('div', { class: 'chead' }, h('div', {}, h('h2', { id: 'pc-h' }, ctx.name + ' at ' + ctx.label))), h('div', { class: 'pc-wait' }, 'Loading the records…'));
      pc.hidden = false;
      return;
    }
    if (oldAnswer(pin.trend)) { pc.hidden = true; how.hidden = true; cur = null; return; }
    try { showPlace(pin, ctx); showHow(pin, ctx, fresh); }
    catch (e) { pc.hidden = true; how.hidden = true; cur = null; console.error(e); } // an answer without the v2 fields: the card still shows
  }
  // redraw the chart when its box changes width
  function redraw() { if (cur && Math.round(cur.box.clientWidth) !== cur.W) draw(); }

  window.TDX = { show: show, redraw: redraw, card: card, rate: rate, worldParts: worldParts, srcText: srcText, recordUrl: recordUrl,
    csvCompare: csvCompare, download: download, Mo: Mo, Y: Y, conv: conv, metric: metric, modelNote: modelNote };
})();
