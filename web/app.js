'use strict';
/* Trend Detective page. Same-origin /api/ calls only. Printed numbers come from the API;
   the browser's own arithmetic is for drawing (see the "pure helpers" block). */

const MINUS = '−';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const PRESETS = [
  { label: 'Atlantic City, NJ', lat: 39.36, lon: -74.42, variable: 'sea_level' },
  { label: 'Delhi', lat: 28.61, lon: 77.21, variable: 'air_temp' },
  { label: 'Visakhapatnam', lat: 17.69, lon: 83.22, variable: 'air_temp' },
  { label: 'Princeton, NJ', lat: 40.35, lon: -74.66, variable: 'air_temp' },
];
const SOURCE_LABELS = { power: 'NASA POWER', era5: 'ERA5', ghcn: 'NOAA GHCN-Daily', coops: 'NOAA CO-OPS tide gauges', grace: 'GRACE/GRACE-FO' };

/* ---------- pure helpers (no DOM; exported for a node check) ---------- */

function median(a) {
  const s = a.slice().sort((x, y) => x - y);
  if (!s.length) return NaN;
  const h = s.length >> 1;
  return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
}

// 'YYYY-MM' -> months since year 0 (a bare 'YYYY' counts as January).
function monthIndex(t) {
  const p = String(t).split('-');
  return +p[0] * 12 + (p.length > 1 ? +p[1] - 1 : 0);
}

// value minus its calendar month's mean over all non-null values.
function deseasonalize(times, values) {
  const sum = new Array(12).fill(0), cnt = new Array(12).fill(0);
  const mon = times.map((t) => monthIndex(t) % 12);
  values.forEach((v, i) => { if (v != null) { sum[mon[i]] += v; cnt[mon[i]]++; } });
  return values.map((v, i) => (v == null ? null : v - sum[mon[i]] / cnt[mon[i]]));
}

// intercept = median(value - slope * t), t in decades, nulls skipped.
function trendIntercept(ts, ds, slope) {
  const r = [];
  ds.forEach((d, i) => { if (d != null) r.push(d - slope * ts[i]); });
  return median(r);
}

function niceNum(x, round) {
  const e = Math.floor(Math.log10(x)), f = x / Math.pow(10, e);
  const n = round ? (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) : (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10);
  return n * Math.pow(10, e);
}

// 4 to 5 nice ticks covering [lo, hi].
function niceTicks(lo, hi, n) {
  n = n || 5;
  if (!(hi > lo)) { const pad = Math.abs(lo) * 0.1 || 1; lo -= pad; hi += pad; }
  const step = niceNum(niceNum(hi - lo, false) / (n - 1), true);
  const start = Math.floor(lo / step + 1e-9) * step, end = Math.ceil(hi / step - 1e-9) * step;
  const ticks = [];
  for (let v = start, i = 0; v <= end + step / 2; i++, v = start + i * step) ticks.push(+v.toFixed(10));
  return { ticks, step, lo: ticks[0], hi: ticks[ticks.length - 1] };
}

function yearStep(spanYears) { return spanYears > 40 ? 10 : spanYears > 5 ? 5 : 1; }
// ponytail: "every 5 if span <= 40, else yearly" is read as yearly only for spans of 5 years or less.

function fixed(x, d) {
  let s = x.toFixed(d);
  if (Number(s) === 0) s = (0).toFixed(d);
  return s.replace('-', MINUS);
}
function tickLabel(v, step) {
  const d = step >= 1 ? 0 : Math.min(2, Math.ceil(-Math.log10(step) - 1e-9));
  return fixed(v, d);
}
// Plain number: 2 decimals if |x| < 1, else 1. A value that would round to zero keeps 3 decimals.
function fmtNum(x, signed) {
  let d = Math.abs(x) < 1 ? 2 : 1;
  if (x !== 0 && Number(x.toFixed(d)) === 0) d = 3;
  const s = fixed(x, d);
  return signed && x > 0 ? '+' + s : s;
}
function fmtVal(x, units) { return fmtNum(x, true) + (units ? ' ' + units : ''); }
function fmtP(p) { return p < 0.001 ? '< 0.001' : String(p); }

function stripParens(name) { return String(name).replace(/\s*\([^)]*\)\s*$/, ''); }
function placeName(place) {
  return place && place.name ? place.name : place ? place.lat.toFixed(2) + ', ' + place.lon.toFixed(2) : '';
}
function monthLabel(t) { const m = monthIndex(t); return MONTHS[m % 12] + ' ' + Math.floor(m / 12); }

function verdictCopy(t, name, place) {
  const y0 = t.period.start.slice(0, 4), y1 = t.period.end.slice(0, 4);
  const s = fmtVal(t.slope_per_decade, t.units), lo = fmtVal(t.ci_low, t.units), hi = fmtVal(t.ci_high, t.units);
  if (t.verdict === 'rising') {
    return { head: 'Rising', shape: 'up',
      p1: `${name} at ${place} is going up: ${s} per decade, from ${y0} to ${y1}.`,
      p2: `The 95% range is ${lo} to ${hi} per decade. Even the low end is above zero, so this is a clear rise.` };
  }
  if (t.verdict === 'falling') {
    return { head: 'Falling', shape: 'down',
      p1: `${name} at ${place} is going down: ${s} per decade, from ${y0} to ${y1}.`,
      p2: `The 95% range is ${lo} to ${hi} per decade. Even the high end is below zero, so this is a clear fall.` };
  }
  const sl = t.slope_per_decade;
  const incl = t.ci_low <= 0 && t.ci_high >= 0 ? 'includes zero' : 'is too wide to rule out no change';
  return { head: 'No clear change', shape: 'flat',
    p1: `We can't tell ${name} at ${place} apart from no change, ${y0} to ${y1}.`,
    p2: `${sl === 0 ? `The data show no lean either way: ${s} per decade.` : `The data lean ${sl > 0 ? 'up' : 'down'}: ${s} per decade.`} But the 95% range (${lo} to ${hi}) ${incl}. That is an answer: over this period, any change is too small or too noisy to separate from normal ups and downs.` };
}

function captionText(t, name, place) {
  const y = t.verdict === 'rising' ? 'rises' : t.verdict === 'falling' ? 'falls' : 'stays flat at';
  const v = t.verdict === 'no_clear_change' ? 'no clear change' : t.verdict;
  return `${name} at ${place}, ${t.period.start} to ${t.period.end}. The trend line ${y}, ${fmtVal(t.slope_per_decade, t.units)} per decade (95% range ${fmtVal(t.ci_low, t.units)} to ${fmtVal(t.ci_high, t.units)}). Verdict: ${v}.`;
}

function layoutFor(w) {
  if (w <= 599) return { vw: 340, vh: 340, hA: 110, hB: 190 };
  if (w < 900) return { vw: 640, vh: 420, hA: 150, hB: 230 };
  return { vw: 720, vh: 460, hA: 140, hB: 260 };
}

function nearestIndex(ms, m) {
  let lo = 0, hi = ms.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (ms[mid] < m) lo = mid; else hi = mid; }
  return Math.abs(ms[lo] - m) <= Math.abs(ms[hi] - m) ? lo : hi;
}

/* ---------- DOM helpers ---------- */

const $ = (id) => document.getElementById(id);
const SVGNS = 'http://www.w3.org/2000/svg';

function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const k in attrs || {}) n.setAttribute(k, attrs[k]);
  kids.forEach((c) => n.append(c));
  return n;
}
function svg(tag, attrs, text) {
  const n = document.createElementNS(SVGNS, tag);
  for (const k in attrs || {}) n.setAttribute(k, attrs[k]);
  if (text != null) n.textContent = text;
  return n;
}
function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }

// "Source: <name>" with a link only when the API gave an https:// URL.
function fillSource(node, source) {
  clear(node);
  node.append('Source: ');
  if (source && typeof source.url === 'string' && source.url.startsWith('https://')) {
    node.append(el('a', { href: source.url }, source.name));
  } else {
    node.append(source ? source.name : 'unknown');
  }
}

/* ---------- state ---------- */

const state = { variables: [], req: 0, series: null, trend: null, selIdx: null, fromGeo: false, params: null, slowTimer: 0, chart: null };

function varById(id) { return state.variables.find((v) => v.id === id); }
function nameOf(id) { const v = varById(id); return stripParens(v ? v.name : String(id).replace(/_/g, ' ')); }

/* ---------- API ---------- */

async function api(path, params) {
  const q = new URLSearchParams();
  for (const k in params || {}) if (params[k] !== undefined && params[k] !== '') q.set(k, params[k]);
  try {
    const res = await fetch(path + (q.toString() ? '?' + q : ''), { headers: { Accept: 'application/json' } });
    let body = null;
    try { body = await res.json(); } catch (e) { /* not json */ }
    return { ok: res.ok, status: res.status, body };
  } catch (e) {
    return { ok: false, status: 0, net: true, body: null };
  }
}

/* ---------- controls ---------- */

function buildChips() {
  const box = $('chips');
  PRESETS.forEach((p, i) => {
    const b = el('button', { type: 'button', class: 'chip', 'aria-pressed': 'false', 'data-i': String(i) }, p.label);
    b.addEventListener('click', () => applyPreset(i));
    box.append(b);
  });
}
function markChips() {
  const lat = Number($('lat').value), lon = Number($('lon').value);
  document.querySelectorAll('.chip').forEach((b) => {
    const p = PRESETS[+b.dataset.i];
    b.setAttribute('aria-pressed', String(p.lat === lat && p.lon === lon));
  });
}
function applyPreset(i) {
  const p = PRESETS[i];
  state.fromGeo = false;
  $('lat').value = p.lat; $('lon').value = p.lon;
  if (varById(p.variable)) $('variable').value = p.variable;
  syncVariableUI();
  submit(true);
}
function fillVariables() {
  const sel = $('variable');
  clear(sel);
  state.variables.forEach((v) => sel.append(el('option', { value: v.id }, v.name)));
}
function syncVariableUI() {
  const v = varById($('variable').value);
  $('variable-help').textContent = v ? `Good for: ${v.good_for}. Resolution: ${v.resolution}.` : '';
  const src = $('source');
  clear(src);
  const many = v && Array.isArray(v.sources) && v.sources.length > 1;
  if (many) v.sources.forEach((s) => src.append(el('option', { value: s }, SOURCE_LABELS[s] || s)));
  $('source-field').hidden = !many;
}

function readParams() {
  let ok = true;
  const one = (id, lim, label) => {
    const raw = $(id).value.trim(), x = raw === '' ? NaN : Number(raw);
    const bad = !Number.isFinite(x) || Math.abs(x) > lim;
    const err = $(id + '-err');
    err.hidden = !bad;
    err.textContent = bad ? `${label} must be a number from -${lim} to ${lim}.` : '';
    $(id).setAttribute('aria-invalid', String(bad));
    if (bad) ok = false;
    return x;
  };
  const lat = one('lat', 90, 'Latitude'), lon = one('lon', 180, 'Longitude');
  if (!ok) { const first = document.querySelector('[aria-invalid="true"]'); if (first) first.focus(); return null; }
  const v = varById($('variable').value);
  const p = { variable: $('variable').value, lat, lon };
  if (v && !$('source-field').hidden && $('source').value !== v.sources[0]) p.source = $('source').value;
  return p;
}

function submit(user) {
  const p = readParams();
  if (!p) return;
  if (!state.fromGeo) history.replaceState(null, '', `#variable=${p.variable}&lat=${p.lat.toFixed(2)}&lon=${p.lon.toFixed(2)}`);
  markChips();
  run(p, user);
}

function locate() {
  const fail = () => { const m = $('geo-msg'); m.hidden = false; m.textContent = "We couldn't get your location. Type coordinates or pick an example place."; };
  $('geo-msg').hidden = true;
  if (!navigator.geolocation) return fail();
  navigator.geolocation.getCurrentPosition((pos) => {
    state.fromGeo = true;
    $('lat').value = pos.coords.latitude.toFixed(2);
    $('lon').value = pos.coords.longitude.toFixed(2);
    submit(true);
  }, fail);
}

/* ---------- running a request ---------- */

function setBusy(on, first) {
  $('answer').setAttribute('aria-busy', String(on));
  const go = $('go');
  go.setAttribute('aria-disabled', String(on));
  go.textContent = on ? 'Working…' : 'Show trend';
  $('loading-text').textContent = on ? 'Looking up the data…' : '';
  $('grey').hidden = !(on && first);
  $('loading-slow').textContent = '';
  clearTimeout(state.slowTimer);
  if (on) {
    const id = state.req;
    state.slowTimer = setTimeout(() => { if (id === state.req) $('loading-slow').textContent = 'Still working. This source can take a few seconds.'; }, 4000);
  }
}

async function run(params, user) {
  const id = ++state.req;
  state.params = params;
  const first = !state.series && $('problem').hidden && $('verdict-card').hidden;
  setBusy(true, first);
  const [sr, tr] = await Promise.all([api('/api/series', params), api('/api/trend', params)]);
  if (id !== state.req) return; // stale
  setBusy(false);
  show(sr, tr, params, user);
}

function show(sr, tr, params, user) {
  let heading;
  $('chart-wrap').hidden = true;
  $('more').hidden = true;
  $('verdict-card').hidden = true;
  $('problem').hidden = true;
  state.series = null; state.trend = null;

  if (!sr.ok) {
    heading = showProblem(problemFor(sr, params));
  } else {
    const s = sr.body;
    const has = s && Array.isArray(s.values) && s.values.some((v) => v != null);
    if (!has) {
      heading = showProblem({ heading: 'No data for this place.', paras: [`${s && s.source ? s.source.name : 'The source'} has no readings here for this measurement. Try another place or measurement.`] });
    } else {
      state.series = s;
      state.trend = tr.ok ? tr.body : null;
      $('chart-wrap').hidden = false;
      renderChart(s, state.trend);
      document.querySelectorAll('#legend .t-only').forEach((li) => { li.hidden = !state.trend; });
      renderTable(s);
      if (state.trend) {
        heading = renderVerdict(state.trend);
        renderMore(state.trend, s);
      } else {
        heading = showProblem(problemFor(tr, params));
      }
    }
  }
  if (user && heading) heading.focus();
}

function problemFor(r, params) {
  const again = [{ label: 'Try again', fn: () => run(state.params, true) }];
  if (r.net || r.status !== 400 && r.status !== 422 && r.status !== 502) {
    return { heading: "We can't reach the server.", paras: ['Check your connection and try again.'], buttons: again };
  }
  if (r.status === 502) {
    return { heading: "The data source isn't answering.", paras: ["That's on their end, not yours. Try again in a minute."], buttons: again };
  }
  if (r.status === 422) {
    return { heading: "Something in the form isn't right.", paras: ['Check the latitude and longitude and try again.'] };
  }
  const detail = r.body && typeof r.body.detail === 'string' ? r.body.detail : 'The request was not accepted.';
  const out = { heading: "We can't answer that for this place.", paras: [detail] };
  if (params.variable === 'sea_level') {
    out.paras.push('Tide gauges sit along US coasts.');
    out.buttons = [{ label: 'Try Atlantic City, NJ', fn: () => applyPreset(0) }];
    if (varById('air_temp')) {
      out.buttons.push({ label: 'Show air temperature here', fn: () => { $('variable').value = 'air_temp'; syncVariableUI(); submit(true); } });
    }
  }
  out.paras.push('Try another place or measurement.');
  return out;
}

function showProblem(p) {
  $('problem-heading').textContent = p.heading;
  const body = $('problem-body');
  clear(body);
  p.paras.forEach((t) => body.append(el('p', {}, t)));
  const act = $('problem-actions');
  clear(act);
  (p.buttons || []).forEach((b) => {
    const btn = el('button', { type: 'button', class: 'btn' }, b.label);
    btn.addEventListener('click', b.fn);
    act.append(btn);
  });
  act.hidden = !(p.buttons && p.buttons.length);
  $('problem').hidden = false;
  return $('problem-heading');
}

/* ---------- verdict, numbers, notes ---------- */

function shapeSvg(kind) {
  const s = svg('svg', { viewBox: '0 0 24 24', 'aria-hidden': 'true', focusable: 'false' });
  if (kind === 'up') s.append(svg('polygon', { points: '12,3 22,21 2,21' }));
  else if (kind === 'down') s.append(svg('polygon', { points: '12,21 22,3 2,3' }));
  else {
    s.append(svg('path', { d: 'M2 9 Q7 4 12 9 T22 9 V12 Q17 17 12 12 T2 12 Z' }));
    s.append(svg('path', { d: 'M2 16 Q7 11 12 16 T22 16 V19 Q17 24 12 19 T2 19 Z' }));
  }
  return s;
}

function renderVerdict(t) {
  const c = verdictCopy(t, nameOf(t.variable), placeName(t.place));
  const h = $('verdict-heading');
  clear(h);
  h.append(shapeSvg(c.shape), c.head);
  $('verdict-p1').textContent = c.p1;
  $('verdict-p2').textContent = c.p2;
  $('verdict-evidence').textContent = `p-value: ${fmtP(t.p_value)}. The p-value says how easily luck alone could produce a trend this strong. Below 0.05 counts as a clear change.`;
  fillSource($('verdict-source'), t.source);
  $('verdict-card').hidden = false;
  return h;
}

function renderMore(t, s) {
  const dl = $('numbers-list');
  clear(dl);
  const rows = [
    ["How fast it's changing", "Sen's slope", fmtVal(t.slope_per_decade, t.units) + ' per decade'],
    ["Range we're 95% sure it falls in", 'confidence interval', `${fmtVal(t.ci_low, t.units)} to ${fmtVal(t.ci_high, t.units)} per decade`],
    ['How easily luck explains it', 'p-value', fmtP(t.p_value)],
    ['Period', null, `${t.period.start} to ${t.period.end}`],
    ['Months used', 'n', String(t.n)],
    ['Seasons removed', 'deseasonalized', t.deseasonalized ? 'Yes' : 'No'],
    ['Adjusted for neighbouring months', 'autocorrelation', t.autocorrelation_adjusted ? 'Yes' : 'No'],
    ['Test', null, t.method === 'mann_kendall_sen' ? "Mann-Kendall test with Sen's slope" : String(t.method)],
  ];
  rows.forEach(([label, term, val]) => {
    const dt = el('dt', {}, label);
    if (term) dt.append(' ', el('span', { class: 'term' }, `(${term})`));
    dl.append(el('div', {}, dt, el('dd', {}, val)));
  });
  fillSource($('numbers-source'), t.source);

  const list = $('notes-list');
  clear(list);
  const notes = [];
  (t.caveats || []).concat(s.notes || []).forEach((n) => { if (!notes.includes(n)) notes.push(n); });
  if (!notes.length) notes.push('No extra caveats from the source.');
  notes.forEach((n) => list.append(el('li', {}, n)));

  $('howto-ac').textContent = t.autocorrelation_adjusted
    ? 'We adjusted for months that resemble their neighbours; without that the result would look surer than it is.'
    : 'We did not adjust for months that resemble their neighbours, so treat the result as less certain.';
  $('more').hidden = false;
}

function renderTable(s) {
  const name = nameOf(s.variable);
  $('table-col').textContent = `${name} (${s.units})`;
  fillSource($('table-source'), s.source);
  const body = $('table-body');
  clear(body);
  const frag = document.createDocumentFragment();
  s.times.forEach((t, i) => {
    const v = s.values[i];
    frag.append(el('tr', {}, el('td', {}, t), el('td', {}, v == null ? 'no data' : String(v))));
  });
  body.append(frag);
}

/* ---------- chart ---------- */

function renderChart(s, t) {
  const box = $('chart-box');
  clear(box);
  const times = s.times, vals = s.values;
  const ms = times.map(monthIndex);
  const des = deseasonalize(times, vals);
  const m0 = ms[0], m1 = ms[ms.length - 1];
  const name = nameOf(s.variable), place = placeName(t ? t.place : s.place);
  const LY = layoutFor(window.innerWidth);
  const cw = box.clientWidth || LY.vw;
  const fs = Math.max(12, Math.round(12 * LY.vw / cw));
  const ml = Math.round(fs * 3.4) + 4, mr = 8, vw = LY.vw;
  const axis = Math.max(40, 2 * fs + 8);
  const vh = Math.max(LY.vh, LY.hA + LY.hB + axis);
  const hh = 2 * (fs + 2);
  const pw = vw - ml - mr;
  const xS = (m) => ml + (m1 === m0 ? 0 : (m - m0) / (m1 - m0) * pw);

  const nn = (a) => a.filter((v) => v != null);
  const rawT = niceTicks(Math.min(...nn(vals)), Math.max(...nn(vals)));
  const desT = niceTicks(Math.min(0, ...nn(des)), Math.max(0, ...nn(des)));
  const A = { top: hh, bot: LY.hA - 4, t: rawT, y0: 0 };
  const yB = vh - axis - LY.hB;
  const B = { top: yB + hh, bot: yB + LY.hB, t: desT, y0: yB };
  [A, B].forEach((p) => { p.yS = (v) => p.top + (p.t.hi - v) / (p.t.hi - p.t.lo) * (p.bot - p.top); });

  const root = svg('svg', { viewBox: `0 0 ${vw} ${vh}`, role: 'img', tabindex: '0', 'aria-labelledby': 'c-title c-desc', 'font-size': fs });
  root.append(svg('title', { id: 'c-title' }, `${name} at ${place}`));
  root.append(svg('desc', { id: 'c-desc' }, t ? captionText(t, name, place) : `${name} at ${place}, ${times[0]} to ${times[times.length - 1]}.`));

  // x ticks
  const y0y = Math.floor(m0 / 12), y1y = Math.floor(m1 / 12), step = yearStep((m1 - m0) / 12);
  const xt = [];
  for (let y = Math.ceil(y0y / step) * step; y <= y1y; y += step) if (y * 12 >= m0 && y * 12 <= m1) xt.push(y);

  const panel = (P, title, ylabel) => {
    root.append(svg('text', { x: 0, y: P.y0 + fs, class: 'c-text c-title' }, title));
    root.append(svg('text', { x: 0, y: P.y0 + 2 * fs + 2, class: 'c-text' }, ylabel));
    xt.forEach((y) => root.append(svg('line', { x1: xS(y * 12), x2: xS(y * 12), y1: P.top, y2: P.bot, class: 'c-grid' })));
    P.t.ticks.forEach((v) => {
      const y = P.yS(v);
      root.append(svg('line', { x1: ml, x2: vw - mr, y1: y, y2: y, class: 'c-grid' }));
      root.append(svg('text', { x: ml - 6, y: y + fs * 0.35, 'text-anchor': 'end', class: 'c-text' }, tickLabel(v, P.t.step)));
    });
  };
  panel(A, 'Raw monthly values', `${name} (${s.units})`);
  panel(B, 'Seasons removed, with trend', `Change from the usual for that month (${s.units})`);
  xt.forEach((y) => root.append(svg('text', { x: xS(y * 12), y: B.bot + fs + 3, 'text-anchor': 'middle', class: 'c-text' }, String(y))));
  root.append(svg('text', { x: ml + pw / 2, y: B.bot + 2 * fs + 6, 'text-anchor': 'middle', class: 'c-text' }, 'Year'));
  root.append(svg('line', { x1: ml, x2: vw - mr, y1: B.yS(0), y2: B.yS(0), class: 'c-zero' }));

  const path = (P, arr) => {
    let d = '', pen = false;
    arr.forEach((v, i) => {
      if (v == null) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${xS(ms[i]).toFixed(1)} ${P.yS(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  root.append(svg('path', { d: path(A, vals), class: 's-raw' }));
  root.append(svg('path', { d: path(B, des), class: 's-des' }));

  if (t) {
    const ts = ms.map((m) => (m - m0) / 120); // decades since the first month
    const b0 = trendIntercept(ts, des, t.slope_per_decade);
    const tv = ts.filter((_, i) => des[i] != null);
    const tm = median(tv), yp = b0 + t.slope_per_decade * tm;
    const tEnd = (m1 - m0) / 120;
    const line = (slope, a, b) => [B.yS(yp + slope * (a - tm)), B.yS(yp + slope * (b - tm))];
    const [l0, l1] = line(t.ci_low, 0, tEnd), [h0, h1] = line(t.ci_high, 0, tEnd), [m0y, m1y] = line(t.slope_per_decade, 0, tEnd);
    const x0 = xS(m0), x1 = xS(m1);
    const clip = svg('clipPath', { id: 'c-clip' });
    clip.append(svg('rect', { x: ml, y: B.top, width: pw, height: B.bot - B.top }));
    const g = svg('g', { 'clip-path': 'url(#c-clip)' });
    g.append(svg('polygon', { points: `${x0},${l0} ${x1},${l1} ${x1},${h1} ${x0},${h0}`, class: 's-fan' }));
    g.append(svg('line', { x1: x0, y1: l0, x2: x1, y2: l1, class: 's-edge' }));
    g.append(svg('line', { x1: x0, y1: h0, x2: x1, y2: h1, class: 's-edge' }));
    g.append(svg('line', { x1: x0, y1: m0y, x2: x1, y2: m1y, class: 's-trend' }));
    root.append(clip, g);
  }

  const rule = svg('line', { y1: A.top, y2: B.bot, class: 'c-rule', visibility: 'hidden' });
  root.append(rule);
  box.append(root);

  $('chart-caption').textContent = t ? captionText(t, name, place) : `${name} at ${place}.`;
  fillSource($('chart-source'), t ? t.source : s.source);

  // readout
  const readout = $('readout');
  const EMPTY = 'Tap or hover the chart to read a month.';
  const select = (i) => {
    state.selIdx = i;
    if (i == null) { rule.setAttribute('visibility', 'hidden'); readout.textContent = EMPTY; return; }
    const x = xS(ms[i]);
    rule.setAttribute('x1', x); rule.setAttribute('x2', x); rule.setAttribute('visibility', 'visible');
    const mi = ms[i] % 12, v = vals[i];
    if (v == null) { readout.textContent = `${monthLabel(times[i])}: no data.`; return; }
    const d = des[i], rel = d === 0 ? 'at' : d > 0 ? 'above' : 'below';
    readout.textContent = `${monthLabel(times[i])}: ${v} ${s.units} raw, ${rel} the usual ${MONTHS_LONG[mi]}.`;
  };
  const at = (e) => {
    const r = root.getBoundingClientRect();
    const xv = (e.clientX - r.left) / r.width * vw;
    select(nearestIndex(ms, m0 + (xv - ml) / pw * (m1 - m0)));
  };
  root.addEventListener('pointermove', at);
  root.addEventListener('pointerdown', at);
  root.addEventListener('keydown', (e) => {
    const n = ms.length, cur = state.selIdx, big = e.shiftKey ? 12 : 1;
    let i = null;
    if (e.key === 'ArrowLeft') i = cur == null ? n - 1 : Math.max(0, cur - big);
    else if (e.key === 'ArrowRight') i = cur == null ? n - 1 : Math.min(n - 1, cur + big);
    else if (e.key === 'Home') i = 0;
    else if (e.key === 'End') i = n - 1;
    else if (e.key === 'Escape') { select(null); return; }
    else return;
    e.preventDefault();
    select(i);
  });
  select(null);
}

/* ---------- start ---------- */

function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  if (!h.get('variable') || !h.has('lat') || !h.has('lon')) return null;
  return { variable: h.get('variable'), lat: h.get('lat'), lon: h.get('lon') }; // raw text; submit() validates
}

async function init() {
  const r = await api('/api/variables');
  if (!r.ok || !Array.isArray(r.body) || !r.body.length) {
    const p = problemFor(r.ok ? { status: 500 } : r, {});
    if (p.buttons) p.buttons = [{ label: 'Try again', fn: init }];
    showProblem(p);
    return;
  }
  state.variables = r.body;
  fillVariables();
  const h = readHash();
  const start = h && varById(h.variable) ? h : PRESETS[0];
  $('lat').value = start.lat; $('lon').value = start.lon; $('variable').value = start.variable;
  syncVariableUI();
  markChips();
  submit(false);
}

buildChips();
$('controls').addEventListener('submit', (e) => { e.preventDefault(); if ($('go').getAttribute('aria-disabled') !== 'true') submit(true); });
$('variable').addEventListener('change', () => { syncVariableUI(); submit(true); });
$('source').addEventListener('change', () => submit(true));
$('locate').addEventListener('click', locate);
['lat', 'lon'].forEach((id) => $(id).addEventListener('input', () => { state.fromGeo = false; markChips(); }));
let lastBand = layoutFor(window.innerWidth).vw;
window.addEventListener('resize', () => {
  const b = layoutFor(window.innerWidth).vw;
  if (b !== lastBand && state.series && !$('chart-wrap').hidden) { lastBand = b; renderChart(state.series, state.trend); }
});
init();

