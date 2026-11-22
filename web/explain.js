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
    var dp = (String(a).split('.')[1] || '').length + (tenth ? 1 : 0); // the decimals the metric value prints with
    if (k) { // °F and inches keep the metric decimals (QA N6); a value that would read 0 keeps 3 significant digits
      var v = a * k[0] / (tenth ? 10 : 1);
      txt = Number(v.toFixed(dp)) === 0 && v !== 0 ? String(Number(v.toPrecision(3))) : String(Number(v.toFixed(dp)));
    } else if (/e/.test(String(a))) txt = String(tenth ? a / 10 : a);
    else txt = (a / (tenth ? 10 : 1)).toFixed(dp).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
    return (x > 0 ? '+' : x < 0 ? MINUS : '') + txt;
  }
  // "Version 3" as given, never "version Version 3" (QA N6)
  function ver(v, label) { return /^version\b/i.test(String(v)) ? String(v) : label + v; }
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
  // sel: the emissions scenario on screen ({ssp, low}; ssp null is the default); today: the current month (tests set it)
  function card(t, imp, sel, today) {
    if (oldAnswer(t)) return { old: true, word: verdictWord(t), shape: t.verdict === 'rising' ? '▲' : t.verdict === 'falling' ? '▼' : '≈',
      conf: str(t.meaning && t.meaning.confidence), why: str(t.meaning && t.meaning.headline), chip: '' };
    var b = t.baseline || {}, fit = t.fit || {}, rec = t.record || {}, m = t.meaning || {}, r = rate(t, imp);
    var clear = clearV(t), short = rec.status === 'short', rk = t.range_kind || '95% range', fx = futOf(t, sel, imp, today);
    var conf = (clear && m.confidence ? m.confidence + ' · ' : '') + (isNum(rec.years) ? Math.round(rec.years) + ' years of records' : '') + (short ? ' (short record)' : '');
    var nw = nowOf(t, imp), r1 = null; // no "Now" readout without trend.now
    if (nw) r1 = { label: (fx ? fx.nowWord : 'Now') + ', compared with ' + str(b.text), value: nw.value,
      line: (nw.rain ? 'Rain in ' + nw.label + ", % above or below a usual year" : 'Average of ' + nw.label) + (b.method === 'fitted' ? '. Baseline estimated from the fitted trend.' : '') };
    var r2 = { label: 'Rate, ' + Y(fit.start) + '–' + Y(fit.end), value: r ? bare(r) : '—', per: r ? r.per : '', line: r ? rk + ' ' + r.range : '' };
    if (r && !clear && isNum(r.low) && isNum(r.high) && r.low <= 0 && r.high >= 0) r2.line += ', which includes no change';
    if (short) r2.line += '. Short record.';
    var g = t.guidance || {}, word = verdictWord(t);
    // R3 with an expert projection (design 11 §3): the chosen scenario's 2050 value, its range and how far that is above today
    var r3f = fx ? { label: 'By 2050, ' + fx.name, value: fx.t50, line: fx.code + fx.lc + ', IPCC AR6. ' + fx.rkShort + ' ' + fx.trng + '.'
      + (fx.more ? ' ' + cap(fx.more) + '.' : '') + (fx.regional ? ' Regional estimate: local sinking may differ.' : '')
      + (fx.outside ? ' Measured levels here are ' + (fx.side === 'above' ? 'already above' : fx.side) + " the experts' range for recent years (step 7)." : '') } : null;
    return { word: word, shape: t.verdict === 'rising' ? '▲' : t.verdict === 'falling' ? '▼' : '≈', conf: conf, why: why(t, imp),
      world: worldLine(t, imp, /^Since \d{4}\b/.test(str(g.why))), r1: r1, r2: r2, r3: str(t.projection && t.projection.why), r3f: r3f,
      chip: str(g.risk_label) === word ? '' : str(g.risk_label) }; // the headline already says "No clear change"
  }
  // The NASA POWER grid against the nearest weather station (QA B10). other: this place's POWER answer the page
  // already has (or null); nothing is fetched for it.
  // The grid size comes from explain.data.where ("a grid cell about 50 km wide").
  function modelNote(t, other) {
    var id = (t.source || {}).id, size = /\babout \d[\d,.]* km\b/.exec(str(((t.explain || {}).data || {}).where));
    if (id === 'power' && (t.variable === 'air_temp' || t.variable === 'air_temp_max')) {
      return { line: 'This comes from a weather model grid' + (size ? ' ' + size[0] + ' wide' : '') + '. A weather station nearby can tell a different story.', offer: 'ghcn' };
    }
    if (id !== 'ghcn' || !other || (other.source || {}).id !== 'power' || !other.verdict) return null;
    if (other.verdict === t.verdict) return { line: 'The weather station and the model agree here.' };
    return { line: 'The weather station and the model disagree here.', strong: true,
      next: 'For the heat you feel day to day, the station is closer to the ground; the model covers a wider area.' };
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
    // the chart starts at its first month drawn; a fit trimmed of sparse early readings says where it starts (record.trimmed_from)
    var first = yearly ? t.yearly[0].year + '-01' : s.times[0], from = (t.record || {}).trimmed_from && fit.start ? ', from ' + M(fit.start) + ',' : '';
    var summary = ctx.name + ' at ' + place + ', ' + M(first) + ' to ' + M(t.period.end) + (none ? ', as measured.' : ', compared with ' + b.text + '.');
    if (r) {
      var line = (drawn ? 'The trend line' : 'The trend') + from;
      summary += ' ' + (clearV(t) ? line + (t.verdict === 'rising' ? ' rises ' : ' falls ') + unsign(r.text) + ' (' + rk + ' ' + r.range + ')'
        : line + ' moves ' + r.text + ", which we can't tell apart from no change (" + rk + ' ' + r.range + '),')
        + (drawn ? ' and stands at ' + f.val(fit.level_end, fit.units) + ' in ' + M(fit.end) : '') + '.';
      summary = summary.replace(/,\.$/, '.');
    }
    var pre = [], preTxt = '';
    (s.flags || []).forEach(function (x, i) { if (x === 'preliminary' && s.values[i] != null) pre.push(s.times[i]); });
    if (pre.length) {
      var oneYear = pre.every(function (x) { return Y(x) === Y(pre[0]); });
      preTxt = ' ' + (oneYear ? andList(pre.map(function (x) { return MONTHS_LONG[mi(x) % 12]; })) + ' ' + Y(pre[0]) : andList(pre.map(M))) + (pre.length === 1 ? ' is' : ' are') + ' preliminary.';
    }
    var conf = str(t.meaning && t.meaning.confidence).toLowerCase(), verdict = ' Verdict: ' + verdictWord(t).toLowerCase() + (clearV(t) && conf ? ', ' + conf : '') + '.';
    summary += preTxt + verdict;
    var cols = ['Month', ctx.name + ' (' + normU(s.units) + ')'];
    if (!none) cols.push('Compared with ' + b.text + ' (' + normU(a.units) + ')');
    cols.push('Note');
    if (yearly) cols = ['Year', "Each year's rain, compared with " + b.text]; // the rows the chart plots (yearRows)
    var fx = futOf(t, ctx.sel, imp, ctx.today), both = modeOf(t, s, fx) === 'both', fu = null;
    if (both) { // past and future on one axis (design 11 §4)
      var lo = fx.loc, p = fx.p;
      fu = { link: { text: (fx.regional ? 'IPCC AR6 regional estimate' : 'IPCC AR6 sea level projections') + ' ↗', href: https((p.source || {}).record_url) },
        tail: ' for ' + (fx.regional ? 'the ' : '') + str(lo.name) + '.', nowWord: fx.nowWord,
        band: cap(fx.rk) + ', ' + fx.short.toLowerCase() + fx.lc };
      var trend = r ? (clearV(t) ? ' The trend line' + from + ' ' + (t.verdict === 'rising' ? 'rises ' : 'falls ') + unsign(r.text) + ' (' + rk + ' ' + r.range + ').'
        : ' The trend line' + from + ' moves ' + r.text + ", which we can't tell apart from no change (" + rk + ' ' + r.range + ').') : '';
      var nw = fx.now;
      summary = ctx.name + ' at ' + place + ', ' + M(first) + ' to ' + M(t.period.end) + ', and IPCC projections to 2100, all compared with ' + b.text + '.' + trend
        + (nw ? ' ' + fx.nowWord + ': ' + nw.value + ' (' + nw.label + ').' : '')
        + mids(fx, imp) + preTxt + verdict;
      ytitle = ytitleNarrow = (imp ? 'inches' : 'cm') + ' above ' + b.text;
    }
    return {
      title: ctx.name + ' at ' + place + ', ' + Y(first) + ' to ' + (both ? '2100' : Y(t.period.end)), sub: sub, src: srcText(t), url: recordUrl(src),
      latest: str(t.latest && t.latest.text), ytitle: ytitle, ytitleNarrow: ytitleNarrow, summary: summary, none: none, hasPre: pre.length > 0, yearly: yearly, fu: fu,
      hint: both ? 'Hover, tap or use the arrow keys to read a month, then each decade after the record ends.' : 'Hover, tap or use the arrow keys to read ' + (yearly ? 'a year.' : 'a month.'),
      noneNote: none ? 'This record has too few years from 1995 to 2014 for an average, so the chart shows the values as measured, with no trend line. The rate on the card still holds.' : '',
      legend: { monthly: yearly ? "Each year's rain" : none ? 'Monthly value, as measured' : 'Monthly value, seasons removed', range: rk + ' of the trend', zero: yrs + ' average (zero)', yrs: yrs,
        trend: 'Trend line' + (from ? ', from ' + Y(fit.start) : '') },
      drawn: drawn, endLabel: drawn ? f.val(fit.level_end, fit.units) : '', endSub: fit.end ? 'trend line, ' + Mo(fit.end) : '',
      cols: cols, caption: 'Records: ' + srcText(t) + '. ' + str(t.latest && t.latest.text) + '.' + (yearly ? ' One row a year, as the chart shows; the CSV has every month.' : ''),
    };
  }
  // rain on yearly values: the table's rows, printed as the chart's readout prints them
  function yearRows(t, imp) {
    var f = F(t, imp);
    return t.yearly.map(function (q) { return [String(q.year), isNum(q.value) ? f.val(q.value, t.fit.units) : 'no data']; });
  }
  // the readout for point i: a month, or a year for rain on yearly values; avg: the 12-month averages (avg12), when drawn
  function readout(t, s, ctx, i, avg) {
    var f = F(t, ctx.imperial), a = s.anomaly || {}, b = t.baseline || {}, yr = yearlyOf(t, s);
    if (yr) return yr[i].year + ': ' + (isNum(yr[i].value) ? f.val(yr[i].value, t.fit.units) + ' compared with the usual year (' + yrsOf(b) + ').' : 'no data.');
    var tm = s.times[i], v = s.values[i], an = a.values ? a.values[i] : null;
    var pre = s.flags && s.flags[i] === 'preliminary' ? ' Preliminary.' : '';
    var av = avg && isNum(avg[i]) ? ' 12-month average: ' + cmv(avg[i], ctx.imperial) + '.' : '';
    if (v == null) return M(tm) + ': no data.' + av;
    if (b.method === 'none' || an == null) return M(tm) + ': ' + f.lvl(v, s.units) + ', as measured.' + pre;
    return M(tm) + ': ' + (LEVELS[t.variable] ? f.lvl(v, s.units) + ' measured, ' : '') + f.val(an, a.units) + ' compared with the usual ' + MONTHS_LONG[mi(tm) % 12] + ' (' + yrsOf(b) + ').' + pre + av;
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
      work: ['How the provider made them: ' + lc1(str(src.method)), 'Dataset: ' + str(src.dataset_id) + '.' + (src.version ? ' ' + ver(src.version, 'Version: ') + '.' : '') + ' Retrieved ' + D(src.retrieved) + '.'],
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
    var nw = nowOf(t, imp), fx = futOf(t, ctx.sel, imp, ctx.today);
    // with a projection the card's "Now" is explained in step 7 (design 11 §6)
    if (isNum(fit.level_end)) s4.work.push('The trend line ends at ' + f.val(fit.level_end, fit.units) + ' compared with ' + b.text + ', in ' + M(fit.end) + '.'
      + (fx && nw ? ' The card’s “' + fx.nowWord + '” is the measured average of the last 12 months instead (step 7).' : ''));
    if (nw && !fx) s4.work.push('The card’s “Now”, ' + nw.value + ', is ' + (nw.rain ? 'the rain measured in ' : 'the measured average of ') + nw.label + ', not a point on the line.');
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
      var th = w.thresholds || {}, lbl = str(g.risk_label), two = / to /.test(lbl), unclear = /^Risk between low and high\b/.test(lbl);
      // the ratio's 95% range, unless the API's sentence already gives it
      var rr = wp.ratio && isNum(w.ratio_low) && isNum(w.ratio_high) ? fixed(w.ratio_low, 1) + ' to ' + fixed(w.ratio_high, 1) : '';
      if (rr && str(w.text).indexOf(rr) >= 0) rr = '';
      // the division in metric, like the API's sentence above it ("(in metric)" in °F or inches): one unit in the step (B5)
      var wm = worldParts(t, false);
      s6.short = worldLine(t, imp);
      s6.words = [imp ? metric(w.text) : str(w.text)];
      if (str(w.why_none)) s6.words.push(w.why_none); // a world figure that did not rise: no ratio, and why
      // the owner's domain review: say how the two figures are measured, in plain words
      if (isSea) s6.words.push('Satellites measure the height of the sea surface itself. The tide gauge measures the sea against the land, so if the land here is sinking, that adds to the local number.');
      if (t.variable === 'air_temp') s6.words.push('The world figure is built from weather stations on land.'
        + (src.id === 'power' || src.id === 'era5' ? ' The number here comes from a weather model, so the two are measured in different ways.' : ''));
      s6.work = [(wp.ratio ? fmtNum(wm.a, false) + ' ÷ ' + fmtNum(wm.b, false) + ' = ' + wp.ratio + ' · ' + (rr ? rr + ' times (' + rk + ') · ' : '') : '')
        + M(w.window.start) + ' to ' + M(w.window.end) + ' · ' + stop(str(w.method)),
        '1× is the same as the world. ' + th.high + '× or more: high risk. ' + th.moderate + '× to ' + th.high + '×: moderate risk. Under ' + th.moderate + '×: low risk. '
        + (unclear ? 'Here the ' + rk + ' spans every level, so the risk could be anywhere from low to high.'
          : 'Here: ' + (lbl ? lbl.toLowerCase() : 'no risk level') + (two && rr ? ', because the ' + rk + ' spans more than one level.' : '.'))];
      if (isSea) s6.work.push('The full record, ' + Y(fit.start) + ' to ' + Y(fit.end) + ': ' + r.text + '. It gets no world ratio, because satellites only start in 1993.');
      if (isSea && w.source && str(w.source.method)) s6.work.push('The world figure: ' + lc1(stop(w.source.method))); // it names what the satellites don't correct for
      s6.link = w.source && https(w.source.record_url) ? { text: w.source.name + ' ↗', href: w.source.record_url } : null;
    } else { // why there is no world figure, then the place's own rule (rain, water storage) in world.text
      s6.short = str(w.why_none) || str(w.text);
      s6.words = [str(w.why_none), str(w.text)].filter(Boolean);
    }
    out.push(s6);

    var pj = str(t.projection && t.projection.why), fl = g.future_link, flink = fl && https(fl.url) && str(fl.label) ? { text: fl.label + ' ↗', href: fl.url } : null;
    out.push(fx ? step7(t, fx, imp, flink) : { title: 'What comes next', short: pj, words: [pj, NO_FUTURE], link: flink });

    var notes = [];
    (t.caveats || []).concat(s.notes || []).forEach(function (n) { if (str(n) && notes.indexOf(n) < 0) notes.push(n); });
    var last = 'This shows whether ' + measure + " changed here. It doesn't say why.";
    out.push({ title: 'Things to keep in mind', short: notes.length ? notes[0] + (notes.length > 1 ? ' And ' + (notes.length - 1) + ' more' : '') : last,
      words: [{ list: notes.concat([last]) }] });

    var list = [{ text: 'Records: ' + str(src.name) + ', ' + str(src.dataset_id) + (src.version ? ', ' + ver(src.version, 'version ') : '') + '. Retrieved ' + D(src.retrieved) + '. ',
      link: url ? { text: 'Open this exact record ↗', href: url } : null }];
    if (wp && w.source) list.push({ text: 'World figure: ' + w.source.name + (str(w.source.dataset_id) ? ', ' + w.source.dataset_id : '') + '. Retrieved ' + D(w.source.retrieved) + '. ', link: https(w.source.record_url) ? { text: 'Open it ↗', href: w.source.record_url } : null });
    var ps = fx && (fx.p.source || {}), s9 = [{ list: list }];
    if (ps) {
      list.push({ text: 'Future: ' + str(ps.name) + ', ' + str(ps.dataset_id) + ', ' + ver(ps.version, 'version ') + ', ' + str(ps.licence) + '. ',
        link: https(ps.record_url) ? { text: 'Open it ↗', href: ps.record_url } : null });
      s9.push({ cite: (ps.citation || []).filter(str), ack: str(ps.acknowledgement) ? 'Acknowledgement: ' + ps.acknowledgement : '' });
    }
    list.push({ text: "Our calculation: the Mann-Kendall test and Sen's slope on " + (byYear ? 'yearly rain' : 'monthly values with seasons removed') + (b.method === 'none' ? '.' : ', against ' + b.text + '.') });
    out.push({ title: 'Sources', short: str(src.name) + (wp && w.source ? '; world figure from ' + lc1(str(w.source.name)) : '') + (ps ? '; future from IPCC AR6' : ''),
      words: s9, csv: true, csvFut: !!ps });
    return out;
  }

  /* Sea-level expert projections (web/design/11-sea-level-future.md). Every number is a field of trend.projection, as
     published: nothing is shifted to meet the record, joined to it, or stretched from the trend. */
  var SCOL = { ssp126: 1, ssp245: 2, ssp370: 3, ssp585: 4 }; // --scen-k, low to very high emissions
  var GAP_NOTE = "The expert lines start at their own 2020 values, as published. We don't move them to meet the measured line, so a gap in 2020 is real; step 7 checks it.";
  var AFTER_2100 = 'After 2100 the experts used a different set of model runs, so values can jump between 2100 and 2110.';
  // the current month in New York, as a month index ("today" on the chart; an old record's "Latest")
  function estMonth(d) {
    var p = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: 'numeric' }).formatToParts(d || new Date());
    var g = function (k) { return +p.filter(function (x) { return x.type === k; })[0].value; };
    return g('year') * 12 + g('month') - 1;
  }
  function projOf(t) { var p = t && t.projection; return p && p.available === true && Array.isArray(p.scenarios) && p.scenarios.length && Array.isArray(p.years) ? p : null; }
  function sspOf(id) { return String(id).replace(/_(medium|low)$/, ''); }
  function scenShort(S) { return cap(str(S.name).replace(/ emissions$/, '')); } // "Intermediate", "Very high"
  // cm(): mm as cm (inches), 2 significant figures, half away from zero, as the server's sig2: 36, 8.0, 0.90, 100
  function cmv(mm, imp, unsigned) {
    if (!isNum(mm)) return 'no value';
    var v = imp ? mm / 25.4 : mm / 10, a = Math.abs(v), e = a ? Math.floor(Math.log10(a)) : 0, k = Math.pow(10, e - 1);
    var r = Math.round(a / k + 1e-9) * k;
    return (r === 0 ? '0' : (unsigned ? '' : v < 0 ? MINUS : '+') + r.toFixed(Math.max(0, 1 - e))) + NB + (imp ? 'in' : 'cm');
  }
  function rngc(a, b, imp) { return isNum(a) && isNum(b) ? cmv(a, imp).slice(0, -3) + ' to ' + cmv(b, imp) : 'no value'; } // "+27 to +46 cm"
  function wholeMm(x) { return (x < 0 ? -1 : 1) * Math.round(Math.abs(x)); }
  function atY(p, S, k, Y) { var i = p.years.indexOf(Y), a = S && S[k]; return i >= 0 && Array.isArray(a) && isNum(a[i]) ? a[i] : null; }

  // Everything the card, the chart, the table and step 7 say about the chosen scenario S (design 11 §2).
  function futOf(t, sel, imp, today) {
    var p = projOf(t);
    if (!p) return null;
    var by = function (id) { return p.scenarios.filter(function (x) { return x.id === id; })[0] || null; };
    var S0 = by(p.default_scenario) || p.scenarios[0], ssp = (sel && sel.ssp) || sspOf(S0.id);
    var lowS = sel && sel.low ? by(ssp + '_low') : null, S = lowS || by(ssp + '_medium') || S0, low = S.confidence === 'low';
    var ro = p.readouts || {}, b50 = ro.by_2050 || {}, mt = ro.more_than_today, n = t.now, nw = nowOf(t, imp);
    var p50 = atY(p, S, 'p50', 2050), lo = atY(p, S, 'p17', 2050), hi = atY(p, S, 'p83', 2050);
    if (S === S0 && isNum(b50.p50)) { p50 = b50.p50; lo = b50.low; hi = b50.high; } // the default scenario reads the server's readouts
    var axis = (t.baseline || {}).projection_axis !== false;
    var old = !!nw && /-/.test(str(n.end)) && (isNum(today) ? today : estMonth()) - mi(n.end) > 24, tw = old ? 'in ' + Y(n.end) : 'today', more = null;
    if (nw && axis && isNum(n.value) && isNum(p50)) more = S === S0 && mt && isNum(mt.value) ? mt.value : wholeMm(p50 - n.value);
    // the default scenario in metric prints the server's texts as given ("+36 cm (likely +27 to +46 cm)"); only the
    // space before "cm" becomes a no-break space (the server's more_than_today.text already says "than in {year}" for an old record)
    var srv = S === S0 && !imp, gv = srv ? /^(\S+ cm) \(likely (\S+ to \S+ cm)\)$/.exec(str(b50.text)) : null;
    var nb = function (x) { return x.replace(/ cm\b/g, NB + 'cm'); };
    var loc = p.location || {}, chk = p.check || {}, ts = t.source || {};
    var gid = ts.id === 'psmsl' && /\/stations\/(\d+)\.php$/.exec(str(ts.record_url)); // a PSMSL record's id, from its station page
    var med = p.scenarios.filter(function (x) { return x.confidence === 'medium'; });
    // the server's fallback when 2019-2021 is too sparse (Mumbai): the latest 12 months against AR6's range at their mid-year
    var l12 = chk.kind === 'latest 12 months' && !!chk.latest && isNum(chk.latest.value);
    // which side of the experts' range the server's check fell on (the card says "above" or "below")
    var cv = l12 ? [chk.latest.value, chk.latest.ar6_p05, chk.latest.ar6_p95] : [chk.observed_2019_2021, chk.ar6_2020_p05, chk.ar6_2020_p95];
    var side = cv[0] > cv[2] ? 'above' : cv[0] < cv[1] ? 'below' : 'outside';
    return { side: side, p: p, S: S, S0: S0, ssp: ssp, noLow: !!(sel && sel.low) && !lowS, low: low, lc: low ? ', low confidence' : '', rk: str(S.range_kind),
      rkShort: low ? str(S.range_kind) : 'Likely', med: med,
      oth: med.filter(function (x) { return sspOf(x.id) !== sspOf(S.id); }), // the other three: never S's own medium twin
      l12: l12,
      name: str(S.name), Name: cap(str(S.name)), short: scenShort(S), code: str(S.code), p50: p50, lo: lo, hi: hi,
      t50: gv ? nb(gv[1]) : cmv(p50, imp), trng: gv ? nb(gv[2]) : rngc(lo, hi, imp),
      now: nw, old: old, nowWord: old ? 'Latest' : 'Now', more: more == null ? '' : srv && mt && str(mt.text) ? nb(mt.text)
        : more === 0 ? 'about the same as ' + tw : 'about ' + cmv(Math.abs(more), imp, true) + ' ' + (more > 0 ? 'more' : 'less') + ' than ' + tw,
      regional: loc.kind === 'regional estimate', loc: loc, axis: axis, check: chk, outside: chk.inside === false,
      same: loc.kind === 'gauge' && ((isNum(loc.km) && loc.km < 1) || (!!gid && +gid[1] === loc.id)) }; // the AR6 gauge is this gauge
  }
  // 'past': PR1's chart; 'both': past and future on the 1995-2014 axis; 'future': the record is off that axis, so the
  // place chart stays PR1's and "What experts project" draws the projection alone
  function modeOf(t, s, fx) { return !fx ? 'past' : fx.axis && (t.baseline || {}).method !== 'none' && (s.anomaly || {}).values ? 'both' : 'future'; }
  // The 12-month average at month i (mm): months i-6 to i+5, inside the record, 10 of them valid and not preliminary.
  // Drawn at the window's centre (the start of month i), so it stops 6 months before the data.
  function avg12(s) {
    var a = (s.anomaly || {}).values, ms = s.times.map(mi), by = {};
    if (!a) return [];
    ms.forEach(function (m, i) { if (isNum(a[i]) && !(s.flags && s.flags[i] === 'preliminary')) by[m] = a[i]; });
    return ms.map(function (m) {
      if (m - 6 < ms[0] || m + 5 > ms[ms.length - 1]) return null;
      var n = 0, sum = 0;
      for (var k = m - 6; k <= m + 5; k++) if (k in by) { n++; sum += by[k]; }
      return n >= 10 ? sum / n : null;
    });
  }
  // the lines to draw (num: mm -> the chart's unit): the other medians, S with its band, and the y-axis span (p17 to p83
  // of every medium scenario 2020-2100, plus S when low confidence, so switching among medium scenarios never moves it)
  function futModel(fx, num) {
    var p = fx.p, ys = p.years.filter(function (Y) { return Y <= 2100; });
    var line = function (S, k) { return ys.map(function (Y) { var v = atY(p, S, k, Y); return v == null ? null : num(v); }); };
    var span = [];
    fx.med.concat(fx.low ? [fx.S] : []).forEach(function (x) { line(x, 'p17').concat(line(x, 'p83')).forEach(function (v) { if (v != null) span.push(v); }); });
    return { years: ys, span: span,
      others: fx.oth.map(function (x) { return { S: x, k: SCOL[sspOf(x.id)] || 1, p50: line(x, 'p50') }; }),
      sel: { S: fx.S, k: SCOL[fx.ssp] || 2, p17: line(fx.S, 'p17'), p50: line(fx.S, 'p50'), p83: line(fx.S, 'p83') } };
  }
  // the second line of a low-confidence end label: under 600 px the right margin holds 84 px of 12 px text, and
  // "low confidence" is about 87 (QA at 375), so it takes two lines there
  function lcLines(narrow) { return narrow ? ['low', 'confidence'] : ['low confidence']; }
  // a decade on the chart's readout
  function decadeRead(fx, Y, imp) {
    var p = fx.p, o = fx.oth;
    return Y + ': ' + fx.name + ' (' + fx.code + ')' + fx.lc + ' ' + cmv(atY(p, fx.S, 'p50', Y), imp) + ', ' + fx.rk + ' ' + rngc(atY(p, fx.S, 'p17', Y), atY(p, fx.S, 'p83', Y), imp) + '.'
      + (o.length ? ' Others: ' + o.map(function (x) { return scenShort(x) + ' ' + cmv(atY(p, x, 'p50', Y), imp); }).join(', ') + '.' : '');
  }
  // The readout line over the chart, the line under it and the flags (design 11 §4)
  function futRead(t, fx, imp) {
    var fl = (t.guidance || {}).future_link, regional = fx.regional && str(fx.loc.note);
    return { b: fx.t50 + ' by 2050', rest: ' under ' + fx.name + ' (' + fx.code + ')' + fx.lc + ': ' + fx.rk + ' ' + fx.trng + '.'
        + (!fx.axis ? " This record has no 1995–2014 average, so we can't say how far that is above today." : fx.more ? ' That is ' + fx.more + '.' : ''),
      sub: str(fx.p.caveat) + (fl && https(fl.url) && str(fl.label) ? ' For flood planning here: ' : ''), link: fl && https(fl.url) && str(fl.label) ? { text: fl.label + ' ↗', href: fl.url } : null,
      regional: regional || '', outside: !fx.outside ? '' : fx.l12 ? "Here the measured level for the latest 12 months is outside the experts' range for that year. "
        : "Here the measured level for 2019 to 2021 is outside the experts' 2020 range. ",
      noLow: fx.noLow ? fx.short + ' (' + fx.code + ') has no low-confidence version, so this shows its medium-confidence projection.' : '' };
  }
  // the chart's summary: the four middle estimates drawn for 2100 (a low-confidence S in place of its medium twin) and the shaded range
  function mids(fx, imp) {
    var drawn = fx.med.map(function (x) { return sspOf(x.id) === sspOf(fx.S.id) ? fx.S : x; });
    return ' Middle estimates for 2100: ' + drawn.map(function (x) { return x.name + ' (' + x.code + ')' + (x === fx.S ? fx.lc : '') + ' ' + cmv(atY(fx.p, x, 'p50', 2100), imp); }).join(', ') + '.'
      + ' Shaded: the ' + fx.rk + ' for ' + fx.name + fx.lc + ', ' + rngc(atY(fx.p, fx.S, 'p17', 2100), atY(fx.p, fx.S, 'p83', 2100), imp) + ' in 2100.';
  }
  // the projection on its own chart (a record off the 1995-2014 axis, design 11 §8)
  function futOnly(t, ctx) {
    var fx = futOf(t, ctx.sel, ctx.imperial, ctx.today), pb = str((fx.p.baseline || {}).text), yt = (ctx.imperial ? 'inches' : 'cm') + ' above ' + pb;
    return { ytitle: yt, ytitleNarrow: yt, hint: 'Hover, tap or use the arrow keys to read a decade.',
      summary: 'IPCC projections for ' + ctx.label + ', 2020 to 2100, compared with ' + pb + '.' + mids(fx, ctx.imperial) };
  }
  // step 7 "What comes next" with a projection (design 11 §6)
  function step7(t, fx, imp, flink) {
    var p = fx.p, c = fx.check, S0 = fx.S0, o = c.observed_2019_2021, b20 = atY(p, S0, 'p50', 2020), bt = str((t.baseline || {}).text), loc = fx.loc;
    var where = fx.regional ? 'for the ' + str(loc.name) + (str(loc.note) ? '. ' + loc.note.replace(/\.$/, '') : '') // the server's note, as given
      : fx.same ? 'at this tide gauge' : 'at the tide gauge ' + str(loc.name) + ', ' + loc.km + ' km from this one';
    var sub = function (x) { return x.charAt(0) === MINUS ? '(' + x + ')' : x; }, work = [];
    if (fx.now) {
      work.push(fx.nowWord + ': the 12 months to ' + M(t.now.end) + ' average ' + fx.now.value + ' compared with ' + bt + '.');
      if (fx.more) work.push('2050, ' + fx.code + ': ' + fx.t50 + ' − ' + sub(fx.now.value) + ' = ' + fx.more + '. Approximate: it takes a 12-month average from a projection.');
    } else work.push('Now: fewer than 10 of the last 12 months have data, so there is no 12-month average to compare.');
    var rng = function (a, b) { return S0.code + ' (' + str(S0.outer_kind) + ' ' + rngc(a, b, imp) + ')'; };
    var cause = ', often because of earthquakes, land rising after the ice age, or a recent surge. Read the projection here with extra care.';
    // the measured level rests on a fitted baseline when fewer than 15 of the 20 baseline years count (QA: New Orleans)
    var fb = (t.baseline || {}).method === 'fitted' ? ' (the baseline here is estimated from the trend)' : '';
    if (isNum(o)) { // check.kind "2019-2021"
      if (isNum(b20)) work.push("2020: the experts' middle estimate is " + cmv(b20, imp) + '; the measured average for 2019 to 2021 is ' + cmv(o, imp)
        + '. We plot the projection as published, so the gap of ' + cmv(Math.abs(b20 - o), imp, true) + ' shows on the chart.');
      var r20 = rng(c.ar6_2020_p05, c.ar6_2020_p95);
      work.push(c.inside ? 'Check: ' + cmv(o, imp) + fb + " is inside the experts' 2020 range for " + r20 + ', so the record and the projection agree here.'
        : { bad: true, text: 'Check: ' + cmv(o, imp) + fb + " is outside the experts' 2020 range for " + r20 + ". Some tide gauges fall outside the experts' 2020 range" + cause });
    } else if (fx.l12) { // check.kind "latest 12 months": 2019-2021 is too sparse, so the server checks `now` at its mid-year
      var L = c.latest, lead = 'Check: the latest 12 months' + (t.now && t.now.end ? ' (to ' + M(t.now.end) + ')' : '') + ' are ' + cmv(L.value, imp) + fb;
      work.push(c.inside ? lead + ", inside the experts' range for that year under " + rng(L.ar6_p05, L.ar6_p95) + ', so the record and the projection agree here.'
        : { bad: true, text: lead + ", outside the experts' range for that year under " + rng(L.ar6_p05, L.ar6_p95) + ". Some tide gauges fall outside the experts' range" + cause });
    } else work.push(!fx.axis ? 'Check: not possible here. This record has no 1995–2014 average.'
      : 'Check: not possible here. The record has fewer than 24 of the 36 months from 2019 to 2021' + (fx.now
        ? ", and its latest 12 months end before the experts' projections start in 2020." : ', and fewer than 10 of its last 12 months have data.'));
    // the owner's domain review: one year's mean is noisy at a gauge
    if (isNum(o) || fx.l12) work.push('One 12-month “Now” can swing by about ' + (imp ? '1 inch' : '3 cm') + ' from year to year at a gauge, so a single year can sit above or below the line.');
    work.push('After 2100 the experts used a different set of model runs, so the table can jump between 2100 and 2110.');
    var names = andList(fx.med.map(function (x) { return scenShort(x).toLowerCase() + ' (' + x.code + ')'; })) + ' emissions';
    return { title: 'What comes next', open: fx.outside,
      short: fx.t50 + ' by 2050 under ' + fx.name + ' (' + fx.code + ')' + fx.lc + ', from the IPCC' + (fx.outside ? " · Check: outside the experts' " + (fx.l12 ? 'range' : '2020 range') : ''),
      words: ["For the future we use only published expert projections: the IPCC's sea level projections (AR6, 2021) " + where + '. They use the same 1995–2014 average as the rest of this page, so past and future share one axis.',
        'Under ' + fx.name + ' (' + fx.code + ')' + fx.lc + ", the experts' middle estimate for 2050 is " + fx.t50 + '. Their ' + fx.rk + ' is ' + fx.trng + ', and their '
          + str(fx.S.outer_kind) + ' is ' + rngc(atY(p, fx.S, 'p05', 2050), atY(p, fx.S, 'p95', 2050), imp) + '.'
          + (fx.low ? ' This version adds ice-sheet changes that are hard to predict, so the experts give no chance for its range.' : ''),
        "The experts' scenarios are " + names + ". They are possible paths for the world's emissions, not predictions. The experts give no odds for which one will happen. " + str(p.caveat),
        'We never stretch the past trend into the future.'],
      work: work, links: [https((p.source || {}).record_url) ? { text: 'IPCC AR6 sea level projections ↗', href: p.source.record_url } : null, flink].filter(Boolean) };
  }
  // "What experts project" (design 11 §5): what drives it (the default scenario only) and every decade for S
  function futCard(t, ctx) {
    var imp = ctx.imperial, fx = futOf(t, ctx.sel, imp, ctx.today), p = fx.p, S = fx.S, S0 = fx.S0, loc = fx.loc, src = p.source || {};
    var dv = p.drivers || {}, dy = dv.year || 2050, pb = str((p.baseline || {}).text) || str((t.baseline || {}).text), last = p.years[p.years.length - 1];
    var parts = (dv.parts || []).map(function (q) { return { name: str(q.name) + (q.id === 'land_motion' && fx.regional ? ' (regional estimate)' : ''), p17: q.p17, p50: q.p50, p83: q.p83 }; });
    parts.push({ name: 'Total', p17: atY(p, S0, 'p17', dy), p50: atY(p, S0, 'p50', dy), p83: atY(p, S0, 'p83', dy), total: true });
    parts.forEach(function (q) { q.mid = cmv(q.p50, imp); q.rng = rngc(q.p17, q.p83, imp); });
    var ends = parts.filter(function (q) { return isNum(q.p17) && isNum(q.p83); });
    var rows = p.years.map(function (Y) {
      var r = atY(p, S.rate || {}, 'p50', Y);
      return { cells: [String(Y), cmv(atY(p, S, 'p50', Y), imp), rngc(atY(p, S, 'p17', Y), atY(p, S, 'p83', Y), imp), rngc(atY(p, S, 'p05', Y), atY(p, S, 'p95', Y), imp),
        isNum(r) ? (imp ? fixed(r / 25.4, 2) : fixed(r, 1)) : 'no value'], hl: Y === 2050, brk: Y === 2100 && last > 2100 };
    });
    return { title: 'What experts project for ' + ctx.label,
      sub: (fx.regional ? 'IPCC AR6 regional estimate for the ' + str(loc.name) + ' (' + loc.km + ' km from this gauge), compared with ' + pb + '.'
        : 'IPCC AR6 sea level projections ' + (fx.same ? 'at this tide gauge' : 'at the tide gauge ' + str(loc.name) + ', ' + loc.km + ' km from this one') + ', compared with ' + pb + '.') + ' Source: ',
      src: { text: str(src.name) + ' ↗', href: https(src.record_url) }, srcTail: ', ' + ver(src.version, 'version ') + ', ' + str(src.licence) + '.',
      dh: 'What drives the rise by ' + dy, dk: SCOL[sspOf(S0.id)] || 2,
      dsub: cap(str(S0.name)) + ' (' + S0.code + "), the one scenario this breakdown comes in. The bar is each part's likely range (about 2 in 3 chance); the dot is its middle estimate. The thin line is zero.",
      parts: parts, lo: Math.min.apply(null, [0].concat(ends.map(function (q) { return q.p17; }))), hi: Math.max.apply(null, [0].concat(ends.map(function (q) { return q.p83; }))),
      dnote: stop(str(dv.note)) + ' The middle estimates add up to about the total, not exactly.',
      th: 'Every decade to ' + last, tsub: fx.Name + ' (' + fx.code + ')' + fx.lc + ', compared with ' + pb + '.', scroll: 'Every decade to ' + last + ', scrolls sideways',
      cols: ['Year', 'Middle estimate', cap(fx.rk), cap(str(S.outer_kind)), imp ? 'Rate, in a year' : 'Rate, mm a year'], rows: rows, brk: AFTER_2100, caveat: str(p.caveat) };
  }
  // The projection CSV (design 11 §7): every scenario, in mm whatever the Units setting
  function csvFuture(t, ctx) {
    var p = projOf(t), src = p.source || {}, loc = p.location || {};
    var head = ['# Bhoomi: Sea level projections for ' + ctx.label, '# Source: ' + str(src.name),
      '# Dataset: ' + str(src.dataset_id) + '; version: ' + str(src.version) + '; licence: ' + str(src.licence), '# Record: ' + https(src.record_url),
      '# Projection location: ' + (loc.kind === 'regional estimate' ? 'regional estimate for the ' + str(loc.name) : 'tide gauge ' + str(loc.name) + ', ' + loc.km + ' km away')
        + (str(loc.note) ? '; ' + loc.note : ''),
      '# Baseline: ' + str((p.baseline || {}).text) + '; levels in mm as published, not shifted to meet the observations',
      '# Ranges: p17-p83 is the likely range (about 2 in 3 chance) for medium confidence and the 17th to 83rd percentile for low confidence; p05-p95 is the 5th to 95th percentile',
      "# Rates: the experts' own rate of rise for each decade, mm a year"]
      .concat((src.citation || []).map(function (c) { return '# Cite: ' + c; }), str(src.acknowledgement) ? ['# Acknowledgement: ' + src.acknowledgement] : [],
        ['# Built with AI assistance. bhoomi.earth']).map(headLine);
    head.push('scenario,name,confidence,year,p05_mm,p17_mm,p50_mm,p83_mm,p95_mm,rate_p50_mm_a_year');
    var body = [];
    p.scenarios.forEach(function (S) {
      p.years.forEach(function (Y) {
        body.push([csvField(S.id), csvField(S.name), csvField(S.confidence), Y].concat(['p05', 'p17', 'p50', 'p83', 'p95'].map(function (k) { return cell(atY(p, S, k, Y)); }),
          [cell(atY(p, S.rate || {}, 'p50', Y))]).join(','));
      });
    });
    return { name: 'bhoomi-' + ctx.slug + '-' + slug(ctx.label) + '-ipcc-ar6.csv', text: head.concat(body).join('\n') + '\n' };
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

  var charts = []; // the charts on screen: { pin, ctx, T, fx, mode, box, ro, W }
  var SEL = { ssp: null, low: false }; // the emissions scenario: one per tab, shared by every view, never stored (design 11 §2)
  var last = null; // the answer on screen, redrawn when the scenario changes

  // A new scenario redraws the chart, "What experts project" and the steps (keeping open steps open), then the card
  // (app.js listens for td:scen); focus goes back to the control that changed it.
  function setSel(next, focus) {
    SEL = next;
    if (!last) return;
    show(last.pin, last.ctx, false);
    var el = focus === 'low' ? $('scen-low') : document.querySelector('[data-scen="' + focus + '"]');
    if (el) el.focus();
    document.dispatchEvent(new CustomEvent('td:scen'));
    var r = $('future-read');
    if (r && window.TD) window.TD.announce(r.textContent);
  }
  function scenSwatch(k, dash) {
    var s = sv('svg', { width: 14, height: 4, 'aria-hidden': 'true', focusable: 'false' });
    s.append(sv('line', { x1: 0, y1: 2, x2: 14, y2: 2, class: 'f-sw k' + k + (dash ? ' low' : '') }));
    return h('span', { class: 'sw' }, s);
  }
  // four radios in one segmented group (one tab stop; arrows move and select) and the low-confidence box
  function scenControl(fx, R) {
    var grp = h('div', { class: 'seg4', role: 'radiogroup', 'aria-labelledby': 'scen-l' }), btns = [];
    fx.med.forEach(function (x) {
      var ssp = sspOf(x.id), on = ssp === fx.ssp;
      var b = h('button', { type: 'button', role: 'radio', 'aria-checked': String(on), tabindex: on ? '0' : '-1', 'data-scen': ssp },
        scenSwatch(SCOL[ssp] || 1, on && fx.low), h('span', {}, h('b', {}, scenShort(x)), h('small', {}, x.code)));
      b.addEventListener('click', function () { if (!on) setSel({ ssp: ssp, low: SEL.low }, ssp); });
      btns.push(b); grp.append(b);
    });
    grp.addEventListener('keydown', function (e) {
      var d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      var i = btns.indexOf(document.activeElement), n = btns[(Math.max(0, i) + d + btns.length) % btns.length].getAttribute('data-scen');
      setSel({ ssp: n, low: SEL.low }, n);
    });
    var cb = h('input', { type: 'checkbox', id: 'scen-low' });
    cb.checked = !!SEL.low;
    cb.addEventListener('change', function () { setSel({ ssp: SEL.ssp, low: cb.checked }, 'low'); });
    var txt = h('span', {}, h('b', {}, 'Show the low-confidence version'), h('small', {}, 'Adds ice-sheet changes that are hard to predict. The experts give no chance for its range.'));
    if (R.noLow) txt.append(h('small', {}, R.noLow));
    return h('div', { class: 'scen' }, h('fieldset', {}, h('legend', { id: 'scen-l' }, 'Emissions scenario'), grp), h('label', { class: 'lc' }, cb, txt));
  }
  // the control, the readout line, the line under it and the flags (design 11 §4)
  function futureTop(t, fx, ctx) {
    var R = futRead(t, fx, ctx.imperial);
    var out = [scenControl(fx, R), h('p', { class: 'scen-help' }, "Scenarios are possible paths for the world's emissions. Experts give no odds for which one will happen."),
      h('p', { class: 'fread', id: 'future-read', 'aria-live': 'polite' }, h('b', {}, R.b), R.rest), h('p', { class: 'fsub' }, R.sub, R.link ? ext(R.link.text, R.link.href) : '')];
    if (R.regional) out.push(h('p', { class: 'flag' }, R.regional));
    if (R.outside) {
      var jb = h('button', { type: 'button', class: 'linkbtn' }, 'Step 7 explains ↓');
      jb.addEventListener('click', goStep7);
      out.push(h('p', { class: 'flag' }, R.outside, jb));
    }
    return out;
  }
  function goStep7() {
    var li = $('how-steps').children[6], d = li && li.querySelector('details');
    if (!d) return;
    d.open = true;
    d.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    d.querySelector('summary').focus({ preventScroll: true });
  }
  function line28(cls) { return swatch([['line', { x1: 1, y1: 6, x2: 27, y2: 6, class: cls }]]); }
  // the legend with projections, three rows (design 11 §4); obs false: the experts' row alone
  function legendFut(T, fx, obs) {
    var lg = h('div', { class: 'legend fut' }), k = ' k' + (SCOL[fx.ssp] || 2);
    if (obs) {
      lg.append(h('span', { class: 'grp' }, 'From the records:'), key(line28('s-month'), T.legend.monthly), key(line28('s-avg'), '12-month average'));
      if (fx.now) lg.append(key(swatch([['circle', { cx: 14, cy: 6, r: 4.5, class: 's-now' }]]), fx.nowWord));
      if (T.hasPre) lg.append(key(line28('s-pre'), 'Preliminary month (may still change)'));
      lg.append(h('span', { class: 'br' }), h('span', { class: 'grp' }, 'Our calculation:'));
      if (T.drawn) lg.append(key(line28('s-trend'), T.legend.trend), key(swatch([['rect', { x: 1, y: 1, width: 26, height: 10, class: 's-fan' }]]), T.legend.range));
      lg.append(key(line28('c-zero'), T.legend.zero), h('span', { class: 'br' }));
    }
    var four = sv('svg', { width: 34, height: 14, 'aria-hidden': 'true' });
    fx.med.forEach(function (x, i) { four.append(sv('line', { x1: 1, y1: 2 + i * 3.3, x2: 33, y2: 2 + i * 3.3, class: 'f-med k' + (SCOL[sspOf(x.id)] || 1) })); });
    lg.append(h('span', { class: 'grp' }, 'Experts (IPCC):'), key(four, 'Middle estimate for each scenario, named at the right'),
      key(swatch([['rect', { x: 1, y: 1, width: 26, height: 10, class: 'f-band' + k }], ['rect', { x: 1, y: 1, width: 26, height: 10, class: 'f-edge' + k + (fx.low ? ' low' : '') }]]), cap(fx.rk) + ', ' + fx.short.toLowerCase() + fx.lc));
    if (obs) lg.append(key(line28('c-today'), 'Today'));
    return lg;
  }

  function showPlace(pin, ctx, fx, mode) {
    var sec = $('place-chart'), t = pin.trend, s = pin.series, T = chartText(t, s, ctx), both = mode === 'both';
    clear(sec);
    sec.dataset.verdict = vkey(t);
    var sub = h('p', { class: 'csub' });
    sub.append((T.sub ? T.sub + ' ' : '') + 'Records: ', T.url ? h('a', { href: T.url, target: '_blank', rel: 'noopener' }, T.src + NB + '↗') : T.src, '. ' + T.latest + '.');
    if (T.fu) sub.append(' Future: ', T.fu.link.href ? h('a', { href: T.fu.link.href, target: '_blank', rel: 'noopener' }, T.fu.link.text.replace(' ↗', NB + '↗')) : T.fu.link.text.replace(' ↗', ''), T.fu.tail);
    sec.append(h('div', { class: 'chead' }, h('div', {}, h('h2', { id: 'pc-h' }, T.title), sub), csvButton(function () { return csvPlace(t, s, ctx); })));
    if (both) futureTop(t, fx, ctx).forEach(function (n) { sec.append(n); });
    var box = h('div', { class: 'pc-box' });
    sec.append(box);
    if (T.noneNote) sec.append(h('p', { class: 'note' }, T.noneNote));
    var lg;
    if (both) lg = legendFut(T, fx, true);
    else {
      lg = h('div', { class: 'legend' }, h('span', { class: 'grp' }, 'From the records:'),
        key(swatch(T.yearly ? [['line', { x1: 1, y1: 6, x2: 27, y2: 6, class: 's-month' }], ['circle', { cx: 14, cy: 6, r: 3.4, class: 's-year' }]]
          : [['line', { x1: 1, y1: 6, x2: 27, y2: 6, class: 's-month' }]]), T.legend.monthly));
      if (T.hasPre && !T.yearly) lg.append(key(swatch([['line', { x1: 1, y1: 6, x2: 27, y2: 6, class: 's-pre' }]]), 'Preliminary month (may still change)'));
      lg.append(h('span', { class: 'grp' }, 'Our calculation:'));
      if (!T.yearly) lg.append(key(swatch([['circle', { cx: 14, cy: 6, r: 3.4, class: 's-year' }]]), 'Yearly average'));
      if (T.drawn) {
        lg.append(key(swatch([['line', { x1: 2, y1: 6, x2: 26, y2: 6, class: 's-trend' }]]), T.legend.trend),
          key(swatch([['rect', { x: 1, y: 1, width: 26, height: 10, class: 's-fan' }], ['line', { x1: 1, y1: 1, x2: 27, y2: 1, class: 's-edge' }], ['line', { x1: 1, y1: 11, x2: 27, y2: 11, class: 's-edge' }]]), T.legend.range));
      }
      if (!T.none) lg.append(key(swatch([['line', { x1: 1, y1: 6, x2: 27, y2: 6, class: 'c-zero' }]]), T.legend.zero));
    }
    var ro = h('p', { class: 'readout', 'aria-live': 'polite' }, T.hint);
    sec.append(lg);
    if (both) sec.append(h('p', { class: 'note' }, GAP_NOTE));
    sec.append(ro, h('p', { class: 'summary' }, T.summary), dataTable(T, function () { return T.yearly ? yearRows(t, ctx.imperial) : tableRows(s); }));
    sec.hidden = false;
    var c = { pin: pin, ctx: ctx, T: T, fx: fx, mode: both ? 'both' : 'past', box: box, ro: ro };
    charts.push(c);
    draw(c);
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

  // "M…L…" through the points, broken where a value is missing
  function pathOf(xs, ys) {
    var d = '', pen = false;
    ys.forEach(function (v, i) { if (v == null) { pen = false; return; } d += (pen ? 'L' : 'M') + xs[i].toFixed(1) + ' ' + v.toFixed(1); pen = true; });
    return d;
  }
  // Drawn at the box's width (1 unit = 1 px, text 12 px or more). 'past': PR1's chart, 330 tall. 'both': past and future
  // on the 1995-2014 axis, 400 tall, to 2100 (design 11 §4). 'future': the projection alone, 2020 to 2100, 320 tall.
  function draw(c) {
    var box = c.box, t = c.pin.trend, s = c.pin.series, T = c.T, imp = c.ctx.imperial, fx = c.fx, fut = c.mode !== 'past', obs = c.mode !== 'future';
    var f = F(t, imp), md = obs ? chartModel(t, s, imp) : { none: false, ms: [], ys: [], pre: [], dots: [], x0: 2020 * 12, x1: 2100 * 12, fit: null, band: null };
    clear(box);
    var W = Math.max(280, Math.round(box.clientWidth || 700)), H = fut ? (obs ? 400 : 320) : 330, narrow = W < 600;
    var ml = 52, mr = narrow ? 96 : fut ? 170 : 150, mt = fut ? 40 : 34, mb = 34, pw = W - ml - mr, ph = H - mt - mb;
    var fm = fut ? futModel(fx, function (v) { return f.num(v, 'mm'); }) : null, avg = fut && obs ? avg12(s) : null;
    if (fut) md.x1 = 2100 * 12;
    var vals = md.ys.filter(function (v) { return v != null; });
    if (!md.none) vals.push(0);
    if (md.fit) vals.push(md.fit.y0, md.fit.y1, md.fit.lo0, md.fit.lo1, md.fit.hi0, md.fit.hi1);
    if (fm) vals = vals.concat(fm.span);
    var tk = niceTicks(Math.min.apply(null, vals), Math.max.apply(null, vals), fut ? 6 : 5);
    var X = function (m) { return ml + (m - md.x0) / (md.x1 - md.x0) * pw; };
    var Yp = function (v) { return mt + (tk.hi - v) / (tk.hi - tk.lo) * ph; };
    var root = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img', tabindex: '0', 'aria-label': T.summary, class: 'pc-svg' + (fut ? ' fut' : '') });
    root.append(sv('text', { x: 0, y: 14, class: 'pc-ytitle' }, narrow ? T.ytitleNarrow : T.ytitle));
    if (md.band) {
      var bx0 = Math.max(ml, X(md.band[0])), bx1 = Math.min(ml + pw, X(md.band[1]));
      if (bx1 > bx0) {
        root.append(sv('rect', { x: bx0, y: mt, width: bx1 - bx0, height: ph, class: 'pc-band' }));
        if (bx1 - bx0 > 64) root.append(sv('text', { x: (bx0 + bx1) / 2, y: fut ? mt + ph - 8 : mt + 14, 'text-anchor': 'middle', class: 'pc-t' }, T.legend.yrs));
      }
    }
    tk.ticks.forEach(function (v) {
      root.append(sv('line', { x1: ml, x2: ml + pw, y1: Yp(v), y2: Yp(v), class: 'c-grid' }));
      root.append(sv('text', { x: ml - 8, y: Yp(v) + 4, 'text-anchor': 'end', class: 'pc-t' }, tickLabel(v, tk.step, !md.none)));
    });
    yearTicks(md.x0, fut ? md.x1 : md.x1 - 1, pw).forEach(function (y) { // up to the last month (or 2100), not past it
      var x = X(y * 12);
      if (x < ml - 0.5 || x > ml + pw + 0.5) return;
      root.append(sv('line', { x1: x, x2: x, y1: mt + ph, y2: mt + ph + 4, class: 'pc-tick' }));
      root.append(sv('text', { x: x, y: H - 10, 'text-anchor': 'middle', class: 'pc-t' }, String(y)));
    });
    var fxs = fm ? fm.years.map(function (Y) { return X(Y * 12); }) : null, sk = fm ? ' k' + fm.sel.k : '';
    var yy = function (a) { return a.map(function (v) { return v == null ? null : Yp(v); }); };
    if (fm) { // the chosen scenario's range, as published: p17 below, p83 above, broken where AR6 has no value
      var run = [], runs = [];
      fm.years.forEach(function (Y, i) { if (fm.sel.p17[i] != null && fm.sel.p83[i] != null) run.push(i); else { runs.push(run); run = []; } });
      runs.push(run);
      runs.filter(function (r) { return r.length > 1; }).forEach(function (r) {
        var top = r.map(function (i) { return fxs[i].toFixed(1) + ',' + Yp(fm.sel.p83[i]).toFixed(1); });
        var bot = r.slice().reverse().map(function (i) { return fxs[i].toFixed(1) + ',' + Yp(fm.sel.p17[i]).toFixed(1); });
        root.append(sv('polygon', { points: top.concat(bot).join(' '), class: 'f-band' + sk }));
      });
      root.append(sv('path', { d: pathOf(fxs, yy(fm.sel.p17)), class: 'f-edge' + sk + (fx.low ? ' low' : '') }));
      root.append(sv('path', { d: pathOf(fxs, yy(fm.sel.p83)), class: 'f-edge' + sk + (fx.low ? ' low' : '') }));
    }
    var F0 = md.fit;
    if (F0) {
      var pts = [[F0.x0, F0.lo0], [F0.x1, F0.lo1], [F0.x1, F0.hi1], [F0.x0, F0.hi0]].map(function (p) { return X(p[0]).toFixed(1) + ',' + Yp(p[1]).toFixed(1); });
      root.append(sv('polygon', { points: pts.join(' '), class: 's-fan' }));
      root.append(sv('line', { x1: X(F0.x0), y1: Yp(F0.lo0), x2: X(F0.x1), y2: Yp(F0.lo1), class: 's-edge' }));
      root.append(sv('line', { x1: X(F0.x0), y1: Yp(F0.hi0), x2: X(F0.x1), y2: Yp(F0.hi1), class: 's-edge' }));
    }
    // casings (design 11 §9), one layer over the band and the trend's range and under every observed mark: the medians
    // meet at 2020, so casing each line in turn would hide the trend line's tail and the months under them
    var tl = F0 ? { x1: X(F0.x0), y1: Yp(F0.y0), x2: X(F0.x1), y2: Yp(F0.y1) } : null;
    var meds = !fm ? [] : fm.others.map(function (o) { return { d: pathOf(fxs, yy(o.p50)), cls: 'f-med k' + o.k, cs: 'c-case thin' }; })
      .concat([{ d: pathOf(fxs, yy(fm.sel.p50)), cls: 'f-sel' + sk + (fx.low ? ' low' : ''), cs: 'c-case' }]);
    // the trend line is cased only over the projections (2020 on): before them there is no band, and the casing would
    // hide a 95% range thinner than itself (QA: The Battery, Grand Isle, Juneau) and stripe the 1995-2014 box
    var cx = fm && tl ? Math.max(tl.x1, fxs[0]) : null;
    if (cx != null && cx < tl.x2) root.append(sv('line', { class: 'c-case', x1: cx, y1: tl.y1 + (tl.y2 - tl.y1) * (cx - tl.x1) / (tl.x2 - tl.x1), x2: tl.x2, y2: tl.y2 }));
    meds.forEach(function (m) { root.append(sv('path', { d: m.d, class: m.cs })); });
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
    if (d) root.append(sv('path', { d: d, class: 's-month' }));
    if (dp) root.append(sv('path', { d: dp, class: 's-pre' }));
    if (!md.none) root.append(sv('line', { x1: ml, x2: ml + pw, y1: Yp(0), y2: Yp(0), class: 'c-zero' }));
    // with projections the 12-month average replaces the yearly dots
    if (avg) root.append(sv('path', { d: pathOf(md.ms.map(X), avg.map(function (v) { return v == null ? null : Yp(f.num(v, (s.anomaly || {}).units)); })), class: 's-avg' }));
    else md.dots.forEach(function (q) { root.append(sv('circle', { cx: X(q.x).toFixed(1), cy: Yp(q.v).toFixed(1), r: 3.4, class: 's-year' })); });
    var xr = ml + pw + 12;
    if (tl && !fut) { // PR1's chart: the trend line and its end label (with projections it is drawn after the medians)
      root.append(sv('line', Object.assign({ class: 's-trend' }, tl)));
      root.append(sv('circle', { cx: X(F0.x1), cy: Yp(F0.y1), r: 5, class: 's-end' }));
      // the end label moves away from the zero label when they would touch; the zero label never moves
      var ey = Yp(F0.y1) + 5;
      if (Math.abs(ey - Yp(0)) < 40) ey = ey <= Yp(0) ? Yp(0) - 40 : Yp(0) + 44;
      ey = Math.min(H - mb - (narrow ? 0 : 15), Math.max(mt + 10, ey));
      root.append(sv('text', { x: xr, y: ey, class: 'pc-end' }, T.endLabel));
      if (!narrow) root.append(sv('text', { x: xr, y: ey + 15, class: 'pc-t' }, T.endSub));
    }
    if (F0 || (fut && !md.none)) {
      // narrow: "0 = the" over the years (the 96 px margin can't hold "0 = the 1995–2014" on one line)
      var ez = Yp(0), yl = T.legend ? T.legend.yrs : '1995–2014';
      root.append(sv('text', { x: xr, y: ez + 4, class: 'pc-t' }, narrow ? '0 = the' : '0 = the ' + yl));
      root.append(sv('text', { x: xr, y: ez + 18, class: 'pc-t' }, narrow ? yl : 'average'));
    }
    if (fm) {
      var tx = X(c.ctx.today);
      if (tx >= ml && tx <= ml + pw) {
        root.append(sv('line', { x1: tx, x2: tx, y1: mt - 4, y2: mt + ph, class: 'c-today' }));
        root.append(sv('text', { x: tx, y: mt - 10, 'text-anchor': 'middle', class: 'pc-t' }, 'Today'));
      }
      meds.forEach(function (m) { root.append(sv('path', { d: m.d, class: m.cls })); });
      if (tl) root.append(sv('line', Object.assign({ class: 's-trend' }, tl))); // the record's trend line on top of the lines
      var i50 = fm.years.indexOf(2050), v50 = i50 < 0 ? null : fm.sel.p50[i50];
      if (v50 != null) { // the card's 2050 number, on its line
        root.append(sv('circle', { cx: fxs[i50], cy: Yp(v50), r: 4.5, class: 'f-dot' + sk }));
        root.append(sv('text', { x: fxs[i50], y: (fm.sel.p83[i50] != null ? Yp(fm.sel.p83[i50]) : Yp(v50) - 4) - 10, 'text-anchor': 'middle', class: 'pc-lab' }, fx.t50 + ' in 2050'));
      }
      var nw = t.now;
      if (obs && fx.now && isNum(nw.value)) { // the card's "Now", at the middle of its 12 months
        var nx = X((mi(nw.start) + mi(nw.end) + 1) / 2), ny = Yp(f.num(nw.value, nw.units));
        root.append(sv('line', { x1: nx - 8, y1: ny - 26, x2: nx - 2, y2: ny - 7, class: 's-lead' }));
        root.append(sv('circle', { cx: nx, cy: ny, r: 5, class: 's-now' }));
        root.append(sv('text', { x: nx - 10, y: ny - 30, 'text-anchor': 'end', class: 'pc-lab' }, fx.nowWord + ' ' + fx.now.value));
      }
      // right margin: each drawn median named at its 2100 height, pushed apart, with a leader to its line end
      var i21 = fm.years.indexOf(2100), labs = [];
      if (i21 >= 0) {
        fm.others.forEach(function (o) { if (o.p50[i21] != null) labs.push({ k: o.k, v: o.p50[i21], txt: scenShort(o.S) + (narrow ? '' : ' ' + cmv(atY(fx.p, o.S, 'p50', 2100), imp)) }); });
        if (fm.sel.p50[i21] != null) labs.push({ k: fm.sel.k, v: fm.sel.p50[i21], on: true, two: fx.low, txt: fx.short + (narrow ? '' : ' ' + cmv(atY(fx.p, fx.S, 'p50', 2100), imp)) });
      }
      labs.forEach(function (l) { l.y = Yp(l.v) + 4; });
      labs.sort(function (a, b) { return a.y - b.y; });
      var lc = lcLines(narrow);
      labs.forEach(function (l, i) { var g = i && labs[i - 1].two ? 16 + 13 * lc.length : 16; if (i && l.y - labs[i - 1].y < g) l.y = labs[i - 1].y + g; });
      if (labs.length) root.append(sv('text', { x: xr, y: labs[0].y - 18, class: 'pc-t' }, 'In 2100:'));
      labs.forEach(function (l) {
        root.append(sv('line', { x1: ml + pw + 1, y1: Yp(l.v), x2: xr - 3, y2: l.y - 4, class: 'f-lead k' + l.k }));
        root.append(sv('text', { x: xr, y: l.y, class: 'pc-r' + (l.on ? ' on' : '') }, l.txt));
        if (l.two) lc.forEach(function (x, j) { root.append(sv('text', { x: xr, y: l.y + 13 * (j + 1), class: 'pc-t' }, x)); });
      });
      // the axis stops at 2100: AR6 values after it come from other model runs (the table has them)
      var bx = ml + pw, by = mt + ph;
      root.append(sv('path', { d: 'M' + (bx - 7) + ' ' + (by + 5) + 'L' + (bx - 3) + ' ' + (by - 5) + 'M' + (bx - 2) + ' ' + (by + 5) + 'L' + (bx + 2) + ' ' + (by - 5), class: 'c-brk' }));
    }
    var rule = sv('line', { y1: mt, y2: mt + ph, class: 'c-rule', visibility: 'hidden' });
    root.append(rule);
    box.append(root);
    c.W = W;

    // points to read: every month, then (with projections) each decade after the record ends
    var nM = md.ms.length, lastM = nM ? md.ms[nM - 1] : -Infinity;
    var decs = fm ? fm.years.filter(function (Y) { return Y * 12 > lastM; }) : [];
    var pos = md.ms.map(function (m) { return m + 0.5; }).concat(decs.map(function (Y) { return Y * 12; }));
    var sel = null;
    var select = function (i) {
      sel = i;
      c.ro.classList.toggle('sel', i != null);
      if (i == null) { rule.setAttribute('visibility', 'hidden'); c.ro.textContent = T.hint; return; }
      var x = X(pos[i]);
      rule.setAttribute('x1', x); rule.setAttribute('x2', x); rule.setAttribute('visibility', 'visible');
      c.ro.textContent = i < nM ? readout(t, s, c.ctx, i, avg) : decadeRead(fx, decs[i - nM], imp);
    };
    var at = function (e) {
      var rc = root.getBoundingClientRect(), m = md.x0 + ((e.clientX - rc.left) / rc.width * W - ml) / pw * (md.x1 - md.x0);
      var lo = 0, hi = pos.length - 1;
      while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (pos[mid] < m) lo = mid; else hi = mid; }
      select(Math.abs(pos[lo] - m) <= Math.abs(pos[hi] - m) ? lo : hi);
    };
    root.addEventListener('pointermove', at);
    root.addEventListener('pointerdown', at);
    root.addEventListener('keydown', function (e) {
      var n = pos.length, big = e.shiftKey ? 12 : 1, i, start = nM ? nM - 1 : 0;
      if (e.key === 'ArrowLeft') i = sel == null ? start : Math.max(0, sel - big);
      else if (e.key === 'ArrowRight') i = sel == null ? start : Math.min(n - 1, sel + big);
      else if (e.key === 'Home') i = 0;
      else if (e.key === 'End') i = n - 1;
      else if (e.key === 'Escape') { select(null); return; }
      else return;
      e.preventDefault();
      select(i);
    });
  }

  // "What experts project" (design 11 §5), after the place chart. A record off the 1995-2014 axis keeps PR1's place
  // chart, so this card then starts with the control and the projection on its own chart.
  function showFuture(pin, ctx, fx, mode) {
    var sec = $('future');
    if (!sec) { sec = h('section', { id: 'future', class: 'card fut', 'aria-labelledby': 'fut-h' }); $('place-chart').after(sec); }
    var t = pin.trend, C = futCard(t, ctx);
    clear(sec);
    var sub = h('p', { class: 'csub' }, C.sub, C.src.href ? h('a', { href: C.src.href, target: '_blank', rel: 'noopener' }, C.src.text.replace(' ↗', NB + '↗')) : C.src.text.replace(' ↗', ''), C.srcTail);
    sec.append(h('div', { class: 'chead' }, h('div', {}, h('h2', { id: 'fut-h' }, C.title), sub), csvButton(function () { return csvFuture(t, ctx); })));
    if (mode === 'future') {
      futureTop(t, fx, ctx).forEach(function (n) { sec.append(n); });
      var T = futOnly(t, ctx), box = h('div', { class: 'pc-box' }), ro = h('p', { class: 'readout', 'aria-live': 'polite' }, T.hint);
      sec.append(box, legendFut(T, fx, false), ro, h('p', { class: 'summary' }, T.summary));
      var c = { pin: pin, ctx: ctx, T: T, fx: fx, mode: 'future', box: box, ro: ro };
      charts.push(c);
      draw(c);
    }
    sec.append(h('div', { class: 'fut-cols' }, drivers(C), decades(C)));
    sec.hidden = false;
  }
  // what drives it: one table, a bar per part on one shared axis (aria-hidden; the numbers are in the cells)
  function drivers(C) {
    var BW = 260, span = C.hi - C.lo || 1, bx = function (v) { return +(4 + (v - C.lo) / span * (BW - 8)).toFixed(1); }, tb = h('tbody'), k = ' k' + C.dk;
    C.parts.forEach(function (q) {
      var bar = sv('svg', { class: 'dbar', viewBox: '0 0 ' + BW + ' 16', width: BW, height: 16, 'aria-hidden': 'true', focusable: 'false' });
      bar.append(sv('line', { x1: bx(0), x2: bx(0), y1: 0, y2: 16, class: 'd-zero' }));
      if (isNum(q.p17) && isNum(q.p83)) bar.append(sv('rect', { x: bx(q.p17), y: 4, width: Math.max(2, bx(q.p83) - bx(q.p17)), height: 8, rx: 2, class: q.total ? 'd-bar tot' : 'd-bar' + k }));
      if (isNum(q.p50)) bar.append(sv('circle', { cx: bx(q.p50), cy: 8, r: 4.5, class: q.total ? 'd-dot tot' : 'd-dot' + k }));
      tb.append(h('tr', q.total ? { class: 'tot' } : {}, h('td', {}, h('span', {}, q.name), bar), h('td', { class: 'num' }, q.mid), h('td', { class: 'rg' }, q.rng)));
    });
    var hr = h('tr', {}, h('th', { scope: 'col' }, 'Part'), h('th', { scope: 'col', class: 'num' }, 'Middle'), h('th', { scope: 'col', class: 'num' }, 'Likely range'));
    return h('div', {}, h('h3', {}, C.dh), h('p', { class: 'csub' }, C.dsub), h('table', { class: 'drv' }, h('thead', {}, hr), tb), h('p', { class: 'note' }, C.dnote));
  }
  // every decade for the chosen scenario, to 2150; the table scrolls sideways in its own box on a phone
  function decades(C) {
    var tb = h('tbody'), hr = h('tr');
    C.cols.forEach(function (x) { hr.append(h('th', { scope: 'col' }, x)); });
    C.rows.forEach(function (r) {
      var tr = h('tr', r.hl ? { class: 'hl' } : {});
      r.cells.forEach(function (x, i) { tr.append(i ? h('td', {}, x) : h('th', { scope: 'row' }, x)); });
      tb.append(tr);
      // the note spans the row and wraps at the box's visible width, even when the table is wider and scrolls (375 px)
      if (r.brk) tb.append(h('tr', { class: 'brk' }, h('td', { colspan: String(C.cols.length) }, h('div', {}, C.brk))));
    });
    return h('div', {}, h('h3', {}, C.th), h('p', { class: 'csub' }, C.tsub),
      h('div', { class: 'dec-scroll', tabindex: '0', role: 'region', 'aria-label': C.scroll }, h('table', { class: 'dec' }, h('thead', {}, hr), tb)), h('p', { class: 'caveat' }, C.caveat));
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
    var au = a.kind === 'percent' ? '% above or below the usual rain' : f.unit(a.units) + ' compared with ' + yrsOf(t.baseline); // the chart's words
    return h('div', { class: 'fig', 'aria-hidden': 'true' },
      h('p', { class: 'fig-l' }, 'As measured (' + f.unit(s.units) + '), last 10 years'), strip(s.values.slice(from)),
      h('p', { class: 'fig-l' }, 'Seasons removed (' + au + ')'), strip(a.values.slice(from)));
  }

  function wordsNode(item, t, s, ctx) {
    if (typeof item === 'string') return item ? h('p', {}, item) : null;
    if (item.list) {
      var ul = h('ul', { class: 'caveats' });
      item.list.forEach(function (x) { ul.append(typeof x === 'string' ? h('li', {}, x) : h('li', {}, x.text, x.link ? ext(x.link.text, x.link.href) : '')); });
      return ul;
    }
    if (item.cite) { // step 9: how to cite the projections, closed
      var cd = h('details', { class: 'cite' }, h('summary', {}, h('span', { class: 'mark', 'aria-hidden': 'true' }), 'How to cite the projections'));
      item.cite.forEach(function (x) { cd.append(h('p', {}, x)); });
      if (item.ack) cd.append(h('p', {}, item.ack));
      return cd;
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
      var open = fresh ? OPEN_STEPS.indexOf(i + 1) >= 0 || !!st.open : !!keep[i]; // st.open: step 7 when the check falls outside
      var det = h('details', open ? { open: '' } : {}, h('summary', {},
        h('span', { class: 'step-n' }, String(i + 1)), h('span', { class: 'step-t' }, st.title), h('span', { class: 'step-s' }, st.short), h('span', { class: 'step-c', 'aria-hidden': 'true' })));
      var words = h('div', { class: 'words' }), side = h('div', { class: 'step-w' });
      st.words.forEach(function (x) { var n = wordsNode(x, t, s, ctx); if (n) words.append(n); });
      if (st.link) words.append(h('p', { class: 'link' }, ext(st.link.text, st.link.href)));
      if (st.links && st.links.length) {
        var lp = h('p', { class: 'link' });
        st.links.forEach(function (l, k) { lp.append(k ? ' · ' : '', ext(l.text, l.href)); });
        words.append(lp);
      }
      if (st.csv) words.append(h('p', { class: 'link' }, csvButton(function () { return csvPlace(t, s, ctx); })));
      if (st.csvFut) {
        var fb = csvButton(function () { return csvFuture(t, ctx); });
        fb.textContent = 'Download the projections (CSV)';
        words.append(h('p', { class: 'link' }, fb));
      }
      if (st.work && st.work.length) {
        var wk = h('div', { class: 'work' }, h('p', { class: 'wl' }, 'The working'));
        st.work.forEach(function (x) { wk.append(typeof x === 'string' ? h('p', {}, x) : h('p', { class: x.bad ? 'bad' : '' }, x.text)); });
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
    var pc = $('place-chart'), how = $('how'), fu = $('future');
    charts = []; last = null;
    if (fu) fu.hidden = true;
    if (!pin || pin.status === 'error') { pc.hidden = true; how.hidden = true; return; }
    if (pin.status !== 'ok') {
      how.hidden = true;
      clear(pc); pc.removeAttribute('data-verdict');
      pc.append(h('div', { class: 'chead' }, h('div', {}, h('h2', { id: 'pc-h' }, ctx.name + ' at ' + ctx.label))), h('div', { class: 'pc-wait' }, 'Loading the records…'));
      pc.hidden = false;
      return;
    }
    if (oldAnswer(pin.trend)) { pc.hidden = true; how.hidden = true; return; }
    last = { pin: pin, ctx: ctx };
    var c2 = Object.assign({}, ctx, { sel: SEL, today: estMonth() });
    try {
      var fx = futOf(pin.trend, SEL, c2.imperial, c2.today), mode = modeOf(pin.trend, pin.series, fx);
      showPlace(pin, c2, fx, mode);
      if (fx) showFuture(pin, c2, fx, mode);
      showHow(pin, c2, fresh);
    } catch (e) { pc.hidden = true; how.hidden = true; if (fu || $('future')) $('future').hidden = true; charts = []; console.error(e); } // an answer without the v2 fields: the card still shows
  }
  // redraw a chart when its box changes width
  function redraw() { charts.forEach(function (c) { if (Math.round(c.box.clientWidth) !== c.W) draw(c); }); }

  window.TDX = { show: show, redraw: redraw, card: function (t, imp) { return card(t, imp, SEL); }, rate: rate, worldParts: worldParts, srcText: srcText, recordUrl: recordUrl,
    csvCompare: csvCompare, download: download, Mo: Mo, Y: Y, conv: conv, metric: metric, modelNote: modelNote, projOf: projOf };
})();
