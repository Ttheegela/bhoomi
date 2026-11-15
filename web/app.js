'use strict';
/* Bhoomi page shell (web/design/09-rework.md). Same-origin /api/ calls only. Printed numbers come from the API;
   the browser's own arithmetic is for drawing and for converting units (see the "pure helpers" block). */

const PLACE_SOURCE = { name: 'Open-Meteo Geocoding API (GeoNames)', url: 'https://open-meteo.com/en/docs/geocoding-api' };

const MINUS = '−';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const PRESETS = [
  { label: 'New York', lat: 40.71, lon: -74.01, variable: 'sea_level' },
  { label: 'Princeton, NJ', lat: 40.35, lon: -74.66, variable: 'air_temp' },
  { label: 'Delhi', lat: 28.58, lon: 77.21, variable: 'air_temp_max' },
  { label: 'Visakhapatnam', lat: 17.69, lon: 83.22, variable: 'air_temp' },
  { label: 'Mumbai', lat: 19.08, lon: 72.88, variable: 'air_temp_max' },
  { label: 'Chennai', lat: 13.08, lon: 80.27, variable: 'air_temp' },
  { label: 'London', lat: 51.51, lon: -0.13, variable: 'air_temp' },
  { label: 'Seattle', lat: 47.61, lon: -122.33, variable: 'sea_level' },
];
const SOURCES = {
  power: { name: 'NASA POWER (MERRA-2)', url: 'https://power.larc.nasa.gov/' },
  era5: { name: 'ERA5 reanalysis via Open-Meteo archive', url: 'https://open-meteo.com/',
    // the footer carries the attribution Open-Meteo asks for: its credit line, the dataset, and the licence
    credit: 'Weather data by Open-Meteo.com', dataset: 'ERA5 reanalysis', licence: { name: 'CC BY 4.0', url: 'https://creativecommons.org/licenses/by/4.0/' } },
  ghcn: { name: 'NOAA NCEI GHCN-Daily', url: 'https://www.ncei.noaa.gov/' },
  coops: { name: 'NOAA CO-OPS tide gauges', url: 'https://tidesandcurrents.noaa.gov/' },
  psmsl: { name: 'Permanent Service for Mean Sea Level (PSMSL)', url: 'https://psmsl.org/' },
  // Used only when /api/variables lists it (the footer and the pickers follow the catalog).
  grace: { name: 'NASA GSFC GRACE and GRACE-FO mascons', url: 'https://earth.gsfc.nasa.gov/geo/data/grace-mascons' },
};
// One plain-words line under the source control (grid sizes as in the catalog's resolution text).
const SOURCE_HELP = {
  power: 'A NASA record of past weather on a grid about 50 km wide.',
  era5: 'A European record of past weather on a grid about 25 km wide.',
  ghcn: 'Readings from the nearest weather station.',
  coops: 'Readings from the nearest NOAA tide gauge (US coasts).',
  psmsl: 'Readings from the nearest tide gauge in a worldwide collection.',
  grace: 'Satellite measurements of water stored on land, averaged over an area about 400 km wide.',
};
// Names in the source select (every width); SOURCE_LABELS are the full names used in text elsewhere.
const SOURCE_SHORT = { power: 'NASA POWER', era5: 'ERA5', ghcn: 'GHCN-Daily', coops: 'CO-OPS', psmsl: 'PSMSL', grace: 'GRACE' };
// Short names for the first screen; the full dataset name stays in "How we calculated this".
const SOURCE_PLAIN = { coops: 'NOAA tide gauge', psmsl: 'tide gauge (PSMSL)', ghcn: 'NOAA weather station', power: 'NASA POWER', era5: 'ERA5', grace: 'NASA GRACE satellites' };
const SOURCE_LABELS = { power: 'NASA POWER', era5: 'ERA5', ghcn: 'NOAA GHCN-Daily', coops: 'NOAA CO-OPS tide gauges', grace: 'NASA GSFC GRACE mascons', psmsl: 'PSMSL tide gauges' };

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

// Year ticks by screen spacing: smallest step in STEPS whose ticks are >= 56 screen px apart
// (pw = plot width in viewBox units, cw = container px, vw = viewBox width). Needs >= 2 labels when span >= 2 years.
const TICK_STEPS = [1, 2, 5, 10, 20, 25, 50];
function yearTicks(m0, m1, pw, cw, vw) {
  const span = (m1 - m0) / 12, y0 = Math.floor(m0 / 12), y1 = Math.floor(m1 / 12);
  const at = (step) => { const r = []; for (let y = Math.ceil(m0 / 12 / step) * step; y * 12 <= m1; y += step) r.push(y); return r; };
  const px = (step) => span > 0 ? step * pw / span * (cw / vw) : Infinity;
  const need = span >= 2 ? 2 : 1;
  let step = TICK_STEPS.find((st) => px(st) >= 56 && at(st).length >= need);
  if (step === undefined) step = TICK_STEPS.slice().reverse().find((st) => at(st).length >= need) || 1;
  return at(step).filter((y) => y >= y0 && y <= y1);
}

// Yearly averages of seasons-removed values, drawing only. A year needs >= 6 valid months;
// x is the mean month index of its valid months.
function yearlyAverages(ms, des) {
  const years = new Map();
  des.forEach((v, i) => {
    if (v == null) return;
    const y = Math.floor(ms[i] / 12), e = years.get(y) || { sum: 0, n: 0, m: 0 };
    e.sum += v; e.n += 1; e.m += ms[i];
    years.set(y, e);
  });
  const out = [];
  years.forEach((e, y) => { if (e.n >= 6) out.push({ year: y, x: e.m / e.n, mean: e.sum / e.n }); });
  return out.sort((p, q) => p.x - q.x);
}

// Dot radius: at most rmax and at most 0.35 of the typical gap between neighbouring dots.
function dotRadius(xs, rmax) {
  const g = [];
  for (let i = 1; i < xs.length; i++) if (xs[i] - xs[i - 1] > 0) g.push(xs[i] - xs[i - 1]);
  return g.length ? Math.min(rmax, 0.35 * median(g)) : rmax;
}

function unitLabel(u) { return u === 'degC' ? '°C' : u; }
// Source name for a picker: short name, then the long label, then the raw id.
function sourceShort(id) { return SOURCE_SHORT[id] || SOURCE_LABELS[id] || id; }
function lcName(n) { return /^[A-Z]{2,}/.test(n) ? n : n.charAt(0).toLowerCase() + n.slice(1); }

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
function fmtVal(x, units) { return fmtNum(x, true) + (units ? '\u00a0' + unitLabel(units) : ''); }
function fmtAbs(x, units) { return fmtNum(Math.abs(x), false) + (units ? '\u00a0' + unitLabel(units) : ''); }
function fmtP(p) { return p < 0.001 ? '< 0.001' : String(p); }

function stripParens(name) { return String(name).replace(/\s*\([^)]*\)\s*$/, ''); }
// Station sources (coops, ghcn) give a real station name: use it as given. Otherwise a preset
// within 0.005 degrees gives its chip label; any other point is written as "lat, lon".
function placeFor(lat, lon, apiName, sourceId) {
  if (apiName && (sourceId === 'coops' || sourceId === 'ghcn')) return apiName;
  const p = PRESETS.find((q) => Math.abs(q.lat - lat) <= 0.005 && Math.abs(q.lon - lon) <= 0.005);
  return p ? p.label : `${fixed(Number(lat), 2)}, ${fixed(Number(lon), 2)}`;
}
function monthLabel(t) { const m = monthIndex(t); return MONTHS[m % 12] + ' ' + Math.floor(m / 12); }

function verdictCopy(t, name, place) {
  const y0 = t.period.start.slice(0, 4), y1 = t.period.end.slice(0, 4), n = lcName(name);
  const lo = fmtVal(t.ci_low, t.units), hi = fmtVal(t.ci_high, t.units);
  const sl = t.slope_per_decade;
  if (t.verdict === 'rising' || t.verdict === 'falling') {
    const up = t.verdict === 'rising';
    return { head: up ? 'Rising' : 'Falling', shape: up ? 'up' : 'down', lean: null,
      p1: `From ${y0} to ${y1}, ${n} at ${place} ${up ? 'rose' : 'fell'} by about ${fmtAbs(sl, t.units)} per decade, and the data support a range of ${lo} to ${hi}.`,
      p2: up ? 'Even the low end of the range is above zero, so this is a clear rise.' : 'Even the high end of the range is below zero, so this is a clear fall.' };
  }
  const zeroIn = t.ci_low <= 0 && t.ci_high >= 0;
  const dir = sl > 0 ? 'up' : 'down';
  const p1 = sl === 0
    ? `From ${y0} to ${y1}, we can't tell ${n} at ${place} apart from no change: the data show no lean either way, and the range runs from ${lo} to ${hi}.`
    : `From ${y0} to ${y1}, we can't tell ${n} at ${place} apart from no change: the data lean ${dir} about ${fmtAbs(sl, t.units)} per decade, but the range runs from ${lo} to ${hi}.`;
  const lean = sl === 0 ? `The data show no lean either way, and the range includes zero.`
    : `The data lean ${dir}, but ${zeroIn ? 'the range includes zero' : 'the p-value is not below 0.05'}.`;
  const p2 = zeroIn
    ? 'That is an answer: over this period, any change is too small or too noisy to separate from normal ups and downs.'
    : `The 95% range (${lo} to ${hi}) stays ${t.ci_low > 0 ? 'above' : 'below'} zero, but the p-value is ${fmtP(t.p_value)}, which is not below 0.05. We go by the stricter test, so we don't call this a clear change. Treat it as a hint, not a finding.`;
  return { head: 'No clear change', shape: 'flat', lean, p1, p2 };
}

function captionText(t, name, place) {
  const s = fmtVal(t.slope_per_decade, t.units);
  const amt = fmtAbs(t.slope_per_decade, t.units);
  const range = `(range of trends the data support: ${fmtVal(t.ci_low, t.units)} to ${fmtVal(t.ci_high, t.units)} per decade)`;
  const y = t.verdict === 'rising' ? `rises by ${amt} per decade` : t.verdict === 'falling' ? `falls by ${amt} per decade` : `moves by ${s} per decade, which we can't tell from zero`;
  const v = t.verdict === 'no_clear_change' ? 'no clear change' : t.verdict;
  return `${name} at ${place}, ${t.period.start} to ${t.period.end}. The trend line ${y} ${range}. Verdict: ${v}.`;
}

function rawLine(source, withTrend) { return `Raw values: ${shownName(source)}.` + (withTrend ? " Trend and range: our calculation, the Mann-Kendall test with Sen's slope on monthly values with seasons removed." : ''); }
function chartHead(t, name, place) { return `${name} at ${place}, ${t.period.start.slice(0, 4)} to ${t.period.end.slice(0, 4)}`; }

function layoutFor(w) {
  if (w <= 599) return { vw: 340, hA: 126, hB: 206 };
  if (w < 900) return { vw: 640, hA: 166, hB: 246 };
  return { vw: 720, hA: 156, hB: 276 };
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

const isHttps = (src) => !!src && typeof src.url === 'string' && src.url.startsWith('https://');
// One block-level 48 px line: grey "<label>:" then "<name> ↗" as a link (https URLs only), plain text without the arrow otherwise.
// The text sits in one inner span so a long name wraps across the full line, not beside the label.
// Display only: a trailing ", RLR monthly means" is jargon; the link is unchanged.
const shownName = (src) => (src && typeof src.name === 'string' ? src.name.replace(/, RLR monthly means$/, '') : 'unknown');
function srcBlock(node, label, source) {
  clear(node);
  const name = shownName(source);
  const inner = (arrow) => el('span', {}, el('span', { class: 'src-label' }, label + ':'), ` ${name}` + (arrow ? '\u00a0↗' : ''));
  if (isHttps(source)) node.append(el('a', { href: source.url, class: 'srclink' }, inner(true)));
  else node.append(el('span', { class: 'srclink' }, inner(false)));
}
// Link with the name only (footer list).
function srcLink(node, source, arrow) {
  if (isHttps(source)) node.append(el('a', { href: source.url, class: 'srclink' }, shownName(source) + (arrow ? '\u00a0↗' : '')));
  else node.append(shownName(source));
}

/* ---------- API ---------- */

async function api(path, params) {
  const q = new URLSearchParams();
  for (const k in params || {}) if (params[k] !== undefined && params[k] !== '') q.set(k, params[k]);
  try {
    const res = await fetch(path + (q.toString() ? '?' + q : ''), { headers: { Accept: 'application/json' } });
    let body = null;
    try { body = await res.json(); } catch (e) { /* not json */ }
    return { ok: res.ok, status: res.status, body, retryAfter: res.headers.get('Retry-After') };
  } catch (e) {
    return { ok: false, status: 0, net: true, body: null };
  }
}

function renderTable(s, withTrend) {
  const name = nameOf(s.variable);
  $('table-col').textContent = `${name} (${unitLabel(s.units)})`;
  srcBlock($('table-source'), 'Raw data', s.source);
  $('table-caption').textContent = rawLine(s.source, withTrend);
  const body = $('table-body');
  clear(body);
  const frag = document.createDocumentFragment();
  s.times.forEach((t, i) => {
    const v = s.values[i];
    frag.append(el('tr', {}, el('td', {}, t), el('td', {}, v == null ? 'no data' : String(v).replace('-', MINUS))));
  });
  body.append(frag);
}

/* ---------- chart ---------- */

let chartW = 0; // box width (px) the chart was last drawn at
function renderChart(s, t) {
  const box = $('chart-box');
  clear(box);
  const times = s.times, vals = s.values;
  const ms = times.map(monthIndex);
  const des = deseasonalize(times, vals);
  const m0 = ms[0], m1 = ms[ms.length - 1];
  const name = nameOf(s.variable), place = placeOf(t || s);
  const units = unitLabel(s.units);
  const LY = layoutFor(window.innerWidth);
  // The drawing is as wide as its box (1 unit = 1 px), so the font is 12 px on screen at every width.
  // A box that is not laid out yet (hidden) falls back to the band's width.
  const fs = 12;
  const vw = Math.max(280, Math.round(box.clientWidth || LY.vw)), cw = vw;
  chartW = box.clientWidth;
  const ml = Math.round(fs * 3.4) + 4, mr = 8;
  const axis = Math.max(40, Math.round(3.2 * fs) + 6);
  const gap = fs + 8; // between the upper panel's bottom and the lower panel's title
  const vh = LY.hA + gap + LY.hB + axis;
  const hh = Math.round(fs * 3.5); // panel header: title, y label, then room above the top tick label
  const pw = vw - ml - mr;
  const xS = (m) => ml + (m1 === m0 ? 0 : (m - m0) / (m1 - m0) * pw);

  const nn = (a) => a.filter((v) => v != null);
  const nTicks = (h) => Math.min(5, Math.max(3, Math.floor(h / (1.6 * fs)))); // ticks at least 19 px apart
  const A = { top: hh, bot: LY.hA - 4, t: niceTicks(Math.min(...nn(vals)), Math.max(...nn(vals)), nTicks(LY.hA - 4 - hh)), y0: 0 };
  const yB = LY.hA + gap;
  const B = { top: yB + hh, bot: yB + LY.hB, t: niceTicks(Math.min(0, ...nn(des)), Math.max(0, ...nn(des)), nTicks(LY.hB - hh)), y0: yB };
  [A, B].forEach((p) => { p.yS = (v) => p.top + (p.t.hi - v) / (p.t.hi - p.t.lo) * (p.bot - p.top); });

  const root = svg('svg', { viewBox: `0 0 ${vw} ${vh}`, role: 'img', tabindex: '0', 'aria-labelledby': 'c-title c-desc', 'font-size': fs });
  root.append(svg('title', { id: 'c-title' }, `${name} at ${place}`));
  root.append(svg('desc', { id: 'c-desc' }, t ? captionText(t, name, place) : `${name} at ${place}, ${times[0]} to ${times[times.length - 1]}.`));

  const xt = yearTicks(m0, m1, pw, cw, vw);

  const panel = (P, title, ylabel) => {
    root.append(svg('text', { x: 0, y: P.y0 + fs, class: 'c-text c-title' }, title));
    root.append(svg('text', { x: 0, y: P.y0 + Math.round(fs * 2.3), class: 'c-text' }, ylabel));
    xt.forEach((y) => root.append(svg('line', { x1: xS(y * 12), x2: xS(y * 12), y1: P.top, y2: P.bot, class: 'c-grid' })));
    P.t.ticks.forEach((v) => {
      const y = P.yS(v);
      root.append(svg('line', { x1: ml, x2: vw - mr, y1: y, y2: y, class: 'c-grid' }));
      root.append(svg('text', { x: ml - 6, y: y + fs * 0.35, 'text-anchor': 'end', class: 'c-text' }, tickLabel(v, P.t.step)));
    });
  };
  panel(A, 'Raw monthly values', `${name} (${units})`);
  panel(B, 'Seasons removed, with trend', `Change from the usual for that month (${units})`);
  xt.forEach((y) => {
    const x = xS(y * 12), hw = 0.3 * fs * String(y).length; // half the label width, roughly
    const edge = x + hw > vw ? ['end', vw] : x - hw < 0 ? ['start', 0] : ['middle', x];
    root.append(svg('text', { x: edge[1], y: B.bot + Math.round(fs * 1.5) + 2, 'text-anchor': edge[0], class: 'c-text' }, String(y)));
  });
  root.append(svg('text', { x: ml + pw / 2, y: B.bot + Math.round(fs * 2.9) + 4, 'text-anchor': 'middle', class: 'c-text' }, 'Year'));
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

  let trendLine = null;
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
    trendLine = { x1: x0, y1: m0y, x2: x1, y2: m1y };
    root.append(clip, g);
  }

  // Yearly averages (dots) sit over the faint monthly line; the solid trend line goes on top. Drawing only: never printed.
  const dots = yearlyAverages(ms, des);
  const r = dotRadius(dots.map((d) => xS(d.x)), Math.max(2.5, fs * 0.22));
  dots.forEach((d) => root.append(svg('circle', { cx: xS(d.x).toFixed(1), cy: B.yS(d.mean).toFixed(1), r: r.toFixed(2), class: 's-year', 'aria-hidden': 'true' })));
  if (trendLine) root.append(svg('line', Object.assign({ class: 's-trend', 'clip-path': 'url(#c-clip)' }, trendLine)));

  const rule = svg('line', { y1: A.top, y2: B.bot, class: 'c-rule', visibility: 'hidden' });
  root.append(rule);
  box.append(root);

  $('chart-head').textContent = t ? chartHead(t, name, place) : `${name} at ${place}`;
  $('chart-caption').textContent = t ? captionText(t, name, place) : `${name} at ${place}.`;
  // With a trend the answer card names the source once; here only what we calculated. Without one there is no card, so the link stays.
  const cs = $('chart-source');
  clear(cs);
  if (t) cs.append(el('span', { class: 'source' }, 'Trend and range: our calculation.')); else srcBlock(cs, 'Raw data', s.source);
  $('chart-key').textContent = t ? 'Thick line: the trend. Shaded band: the range of trends the data support. Dashed line: no change.' : 'Dashed line: no change.';
  $('chart-raw').textContent = rawLine(t ? t.source : s.source, !!t);

  // readout
  const readout = $('readout');
  const EMPTY = 'Tap or hover the chart to read a month.';
  const dRange = Math.max(...nn(des)) - Math.min(...nn(des));
  const select = (i) => {
    state.selIdx = i;
    readout.classList.toggle('sel', i != null);
    if (i == null) { rule.setAttribute('visibility', 'hidden'); readout.textContent = EMPTY; return; }
    const x = xS(ms[i]);
    rule.setAttribute('x1', x); rule.setAttribute('x2', x); rule.setAttribute('visibility', 'visible');
    const mi = ms[i] % 12, v = vals[i];
    if (v == null) { readout.textContent = `${monthLabel(times[i])}: no data.`; return; }
    const d = des[i], rel = d === 0 || Math.abs(d) < 1e-9 * dRange ? 'at' : d > 0 ? 'above' : 'below';
    readout.textContent = `${monthLabel(times[i])}: ${String(v).replace('-', MINUS)}\u00a0${units} raw, ${rel} the usual ${MONTHS_LONG[mi]}.`;
  };
  const at = (e) => {
    const rc = root.getBoundingClientRect();
    const xv = (e.clientX - rc.left) / rc.width * vw;
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


/* ---------- text and link helpers ---------- */

// A place name from a link or a search is only ever shown with textContent. Control characters and angle brackets
// are dropped, 60 characters at most.
function cleanPlace(s) { const t = String(s == null ? '' : s).replace(/[\u0000-\u001f\u007f-\u009f<>]/g, '').trim().slice(0, 60); return t || null; }
// "YYYY" or "YYYY-MM", years 1850 to 2100; anything else is null.
const yr = (v) => (/^(18[5-9]\d|19\d\d|20\d\d|2100)(-(0[1-9]|1[0-2]))?$/.test(v || '') ? v : null);
// "40.71° N, 74.01° W"
function coordText(lat, lon) { return `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(2)}° ${lon >= 0 ? 'E' : 'W'}`; }

// Names that older or hand-typed links may carry, mapped to the catalogue's ids. None of these was ever a catalogue id
// (the five ids have not changed since the catalogue was written); they are friendly aliases only. Any other unknown
// id is an out-of-date link.
const VARIABLE_ALIASES = { precipitation: 'precip', rain: 'precip', temperature: 'air_temp', air_temperature: 'air_temp',
  max_temperature: 'air_temp_max', hottest_day: 'air_temp_max', groundwater: 'water_storage', land_water: 'water_storage' };

/* ---------- the five windows ---------- */

const WINDOWS = [
  { id: 'sea_level', slug: 'sea-level', name: 'Sea level', search: 'Search a coastal town or city',
    question: 'Is the sea rising where you live, build or invest? Tide gauges have measured it for up to 125 years.', units: ['cm', 'inches'] },
  { id: 'air_temp', slug: 'air-temperature', name: 'Air temperature', search: 'Search a town or city',
    question: 'Is the air getting warmer where you live? Our records start in 1981 and come from weather models and weather stations.', units: ['°C', '°F'] },
  { id: 'air_temp_max', slug: 'hottest-days', name: 'Hottest days', search: 'Search a town or city',
    question: 'Are the hottest days getting hotter where you live? We follow the hottest day of every month since 1981.', units: ['°C', '°F'] },
  { id: 'precip', slug: 'rain', name: 'Rain', search: 'Search a town or city',
    question: 'Is it getting wetter or drier where you live? Our rainfall records start in 1981.', units: ['mm', 'inches'] },
  { id: 'water_storage', slug: 'water-storage', name: 'Water storage', search: 'Search a town or city',
    question: 'Is the land holding more or less water where you live? Satellites have measured it since 2002, as an average over about 400 km.', units: ['cm', 'inches'] },
];
const WIN_BY_ID = {}; const WIN_BY_SLUG = {};
WINDOWS.forEach((w) => { WIN_BY_ID[w.id] = w; WIN_BY_SLUG[w.slug] = w; });
const DEFAULT_WINDOW = 'sea_level';
const MAX_PINS = 6, MAX_FLIGHT = 3;
const PIN_KEY = 'td.pins.v2';

const D = (label, lat, lon) => ({ label, lat, lon });
const DEFAULT_PINS = {
  sea_level: [D('Grand Isle, LA', 29.2633, -89.9567), D('New Orleans, LA', 30.0272, -90.1133), D('Galveston, TX', 29.31, -94.7933),
    D('Miami, FL', 25.7314, -80.1618), D('New York, NY', 40.7006, -74.0142), D('Seattle, WA', 47.6026, -122.3393)],
  air_temp: [D('New York', 40.71, -74.01), D('Princeton, NJ', 40.35, -74.66), D('Delhi', 28.58, 77.21), D('Chennai', 13.08, 80.27), D('London', 51.51, -0.13), D('Seattle', 47.61, -122.33)],
  air_temp_max: [D('Delhi', 28.58, 77.21), D('Mumbai', 19.08, 72.88), D('Chennai', 13.08, 80.27), D('New York', 40.71, -74.01), D('Princeton, NJ', 40.35, -74.66), D('London', 51.51, -0.13)],
  precip: [D('Chennai', 13.08, 80.27), D('Mumbai', 19.08, 72.88), D('Delhi', 28.58, 77.21), D('London', 51.51, -0.13), D('Seattle', 47.61, -122.33), D('New York', 40.71, -74.01)],
  water_storage: [D('Punjab, India', 30.90, 75.85), D('Delhi', 28.58, 77.21), D('Central Valley, California', 36.75, -119.77), D('Chennai', 13.08, 80.27), D('London', 51.51, -0.13), D('New York', 40.71, -74.01)],
};

/* ---------- state ---------- */

// Old chart code reads state.params (the place being drawn), state.place (its name) and state.selIdx (the readout).
const state = { variables: [], params: null, place: null, selIdx: null };
const pinKeyOf = (lat, lon) => `${Number(lat).toFixed(2)},${Number(lon).toFixed(2)}`;
const store = {};          // variable id -> { pins: [{label, lat, lon, slot, link?}], selected: key }
const wsrc = {};           // variable id -> the data source chosen by hand (null = the measurement's default)
const results = {};        // "variable|source|key" -> { status, trend, series, error }
const queue = [];
let flight = 0;
let curWin = DEFAULT_WINDOW; // a variable id, or 'settings'

function varById(id) { return state.variables.find((v) => v.id === id); }
// The visitor's name for a measurement ("Rain", not "Precipitation"), in every string the page builds.
function nameOf(id) { const w = WIN_BY_ID[id]; if (w) return w.name; const v = varById(id); return stripParens(v ? v.name : String(id).replace(/_/g, ' ')); }
function winOf(id) { return WIN_BY_ID[id] || null; }

// The name used in a sentence: a station or gauge name from the data; else the visitor's word for the place
// (first part of its label); a name that came from a link is not trusted, so coordinates stay.
function placeOf(t) {
  const q = state.params || {};
  const lat = q.lat !== undefined ? q.lat : t.place.lat, lon = q.lon !== undefined ? q.lon : t.place.lon;
  const named = placeFor(lat, lon, t.place && t.place.name, t.source && t.source.id);
  if (!state.place || state.place.link || named !== `${fixed(Number(lat), 2)}, ${fixed(Number(lon), 2)}`) return named;
  return cleanPlace(state.place.label.split(',')[0]) || named;
}

function loadStore() {
  let raw = null;
  try { raw = JSON.parse(localStorage.getItem(PIN_KEY)); } catch (e) { /* storage may be off */ }
  WINDOWS.forEach((w) => {
    const r = raw && typeof raw === 'object' ? raw[w.id] : null;
    let pins = [];
    if (r && Array.isArray(r.pins)) {
      r.pins.forEach((p) => {
        const label = p && cleanPlace(p.label), lat = p && Number(p.lat), lon = p && Number(p.lon);
        if (!label || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return;
        if (pins.length < MAX_PINS && !pins.some((q) => pinKeyOf(q.lat, q.lon) === pinKeyOf(lat, lon))) pins.push({ label, lat, lon, link: p.link === true, slot: p.slot, preset: typeof p.preset === 'boolean' ? p.preset : DEFAULT_PINS[w.id].some((d) => pinKeyOf(d.lat, d.lon) === pinKeyOf(lat, lon)) });
      });
    }
    let selected = r && typeof r.selected === 'string' ? r.selected : null;
    if (!pins.length && !(r && Array.isArray(r.pins))) { pins = DEFAULT_PINS[w.id].map((p) => Object.assign({ preset: true }, p)); selected = null; } // the defaults are examples
    assignSlots(pins);
    if (!pins.some((p) => pinKeyOf(p.lat, p.lon) === selected)) selected = pins.length ? pinKeyOf(pins[0].lat, pins[0].lon) : null;
    store[w.id] = { pins, selected };
  });
}
// slot 0 to 5 picks the colour; a pin keeps its slot while it stays pinned
function assignSlots(pins) {
  const used = new Set(pins.map((p) => p.slot).filter((s) => Number.isInteger(s) && s >= 0 && s < MAX_PINS));
  const seen = new Set();
  pins.forEach((p) => {
    if (Number.isInteger(p.slot) && p.slot >= 0 && p.slot < MAX_PINS && !seen.has(p.slot)) { seen.add(p.slot); return; }
    let s = 0; while (used.has(s) || seen.has(s)) s++;
    p.slot = s; seen.add(s); used.add(s);
  });
}
function saveStore() {
  const out = {};
  WINDOWS.forEach((w) => { const e = store[w.id]; out[w.id] = { pins: e.pins.map((p) => ({ label: p.label, lat: p.lat, lon: p.lon, slot: p.slot, link: p.link || undefined, preset: !!p.preset })), selected: e.selected }; });
  try { localStorage.setItem(PIN_KEY, JSON.stringify(out)); } catch (e) { /* storage may be off */ }
}

/* ---------- requests: at most three pins in flight ---------- */

// The source the page sends: only one chosen by hand, offered by the measurement, and not its default.
function sourceFor(win) {
  const v = varById(win), s = wsrc[win];
  return v && Array.isArray(v.sources) && v.sources.length > 1 && s && v.sources.includes(s) && s !== v.sources[0] ? s : undefined;
}
const resKey = (win, p) => `${win}|${sourceFor(win) || ''}|${pinKeyOf(p.lat, p.lon)}`;

function plainError(r) {
  if (r.status === 429) return (r.body && typeof r.body.detail === 'string' && r.body.detail) || 'Too many requests right now. Please wait a little and try again.';
  if (r.net || (r.status !== 400 && r.status !== 422 && r.status !== 502)) return "We can't reach the server. Check your connection and try again.";
  if (r.status === 502) return "The data source isn't answering. That's on their end, not yours. Try again in a minute.";
  if (r.status === 422) return "We couldn't read that place.";
  return r.body && typeof r.body.detail === 'string' && r.body.detail ? r.body.detail : "We can't answer that for this place.";
}

// A failed answer is not kept: it is asked again when its window is shown and when the visitor selects the pin.
function dropErrors(win, key) {
  const e = store[win];
  if (!e) return;
  e.pins.forEach((p) => { const k = resKey(win, p); if (results[k] && results[k].status === 'error' && !(key && results[k].none) && (!key || pinKeyOf(p.lat, p.lon) === key)) delete results[k]; });
}
function enqueue(win, p) {
  const k = resKey(win, p);
  if (results[k]) return;
  results[k] = { status: 'loading', trend: null, series: null, error: null, t0: Date.now() };
  queue.push({ win, p, k, params: Object.assign({ variable: win, lat: p.lat, lon: p.lon }, sourceFor(win) ? { source: sourceFor(win) } : {}) });
  pump();
}
function pump() {
  while (flight < MAX_FLIGHT && queue.length) {
    const job = queue.shift();
    flight++;
    Promise.all([api('/api/series', job.params), api('/api/trend', job.params)]).then(([sr, tr]) => {
      const res = results[job.k];
      if (!res) { flight--; pump(); return; }
      // too many requests: try once more by itself after Retry-After seconds (5 if missing, 30 at most); "Checking…" meanwhile
      const slow = sr.status === 429 ? sr : tr.status === 429 ? tr : null;
      if (slow && !job.retried) {
        const wait = Math.min(30, Math.max(1, parseInt(slow.retryAfter, 10) || 5));
        job.retried = true; flight--;
        setTimeout(() => { if (results[job.k] === res) { queue.push(job); pump(); } }, wait * 1000);
        pump();
        return;
      }
      const s = sr.ok ? sr.body : null;
      const has = s && Array.isArray(s.values) && s.values.some((v) => v != null);
      if (!sr.ok) { res.status = 'error'; res.error = plainError(sr); res.none = sr.status === 400; } // none: a real "no record here", not asked again on every click
      else if (!has) { res.status = 'error'; res.error = `${s && s.source ? s.source.name : 'The source'} has no readings here for this measurement.`; res.none = true; }
      else if (!tr.ok) { res.status = 'error'; res.error = plainError(tr); res.series = s; res.none = tr.status === 400; }
      else { res.status = 'ok'; res.series = s; res.trend = tr.body; }
      flight--;
      landed(job.win, job.p, res);
      pump();
    });
  }
}
function ensureLoaded(win) {
  const e = store[win];
  if (!e) return;
  const first = e.pins.filter((p) => pinKeyOf(p.lat, p.lon) === e.selected).concat(e.pins.filter((p) => pinKeyOf(p.lat, p.lon) !== e.selected));
  first.forEach((p) => enqueue(win, p));
}
// a result arrived
function landed(win, p, res) {
  if (win !== curWin) return;
  changed();
  const e = store[win];
  if (pinKeyOf(p.lat, p.lon) === e.selected && res.status === 'ok') {
    const g = res.trend.guidance;
    TD.announce(`${p.label}: ${g && g.risk_label ? g.risk_label + '. ' + whyOf(g) : (res.trend.meaning && res.trend.meaning.headline) || 'Loaded.'}`);
  }
}

/* ---------- pins as the modules see them ---------- */

function pinList(win) {
  const e = store[win];
  if (!e) return [];
  return e.pins.map((p) => {
    const key = pinKeyOf(p.lat, p.lon), r = results[resKey(win, p)] || { status: 'loading', trend: null, series: null, error: null };
    return { key, label: p.label, lat: p.lat, lon: p.lon, slot: p.slot, selected: key === e.selected, status: r.status, error: r.error, trend: r.trend, series: r.series, link: !!p.link, started: r.t0 || 0 };
  });
}
function selectedPin(win) { return pinList(win).find((p) => p.selected) || null; }

// When the selected place was answered by another source than the one highlighted, say so.
function renderSrcNote() {
  const n = $('src-note'), pin = curWin === 'settings' ? null : selectedPin(curWin), v = varById(curWin);
  const sid = pin && pin.status === 'ok' && pin.trend.source && pin.trend.source.id;
  const cur = v && Array.isArray(v.sources) ? (sourceFor(curWin) || v.sources[0]) : null;
  const show = !!sid && !!cur && v.sources.length > 1 && sid !== cur;
  n.hidden = !show;
  n.textContent = show ? `This place is measured by ${shownName(pin.trend.source)}.` : '';
}

// While a place in the shown window is loading, a one-second timer updates only the loading texts.
let loadTimer = 0;
const secsSince = (p) => Math.max(0, Math.floor((Date.now() - p.started) / 1000));
// the usual time for the window's source: weather stations send a long daily record
function usualSecs() { const v = varById(curWin), sid = sourceFor(curWin) || (v && v.sources && v.sources[0]); return sid === 'ghcn' ? 20 : 5; }
function loadingLine(p) {
  const n = secsSince(p), v = varById(curWin), sid = sourceFor(curWin) || (v && v.sources && v.sources[0]);
  if (sid === 'ghcn') return `Reading daily weather-station records from NOAA since 1981. ${n > 20 ? 'This is taking longer than usual; still reading.' : 'This usually takes 5 to 20 seconds for each place.'} ${n} s so far.`;
  if (n > 15) return `This is taking longer than usual; still checking. ${n} s so far.`;
  return `Checking the records for ${p.label}…${n >= 3 ? ` ${n} s so far.` : ''}`;
}
function tickLoading() {
  const pins = curWin === 'settings' ? [] : pinList(curWin);
  document.querySelectorAll('#pins .pn-line').forEach((s) => {
    const p = pins.find((x) => x.key === s.getAttribute('data-key'));
    if (p && p.status === 'loading') s.textContent = pinLine(p);
  });
  const sel = pins.find((p) => p.selected), prog = $('rec-prog');
  if (sel && sel.status === 'loading' && prog) { prog.value = Math.min(secsSince(sel), usualSecs() - 0.5); $('rec-load-text').textContent = loadingLine(sel); }
  syncTimer();
}
function syncTimer() {
  const any = curWin !== 'settings' && pinList(curWin).some((p) => p.status === 'loading');
  if (any && !loadTimer) loadTimer = setInterval(tickLoading, 1000);
  else if (!any && loadTimer) { clearInterval(loadTimer); loadTimer = 0; }
}

function changed() {
  renderSrcNote();
  renderSidebar();
  renderRec();
  syncTimer();
  const pins = pinList(curWin);
  const sel = pins.find((p) => p.selected);
  document.dispatchEvent(new CustomEvent('td:pins', { detail: { window: curWin, pins, selected: sel ? sel.key : null } }));
}

/* ---------- units and wording ---------- */

const UNIT_NAME = { degC: '°C', '°C': '°C', C: '°C' };
const normUnit = (u) => UNIT_NAME[u] || u;
function convert(v, unit) {
  const u = normUnit(unit);
  if (window.TDPrefs.get().units === 'imperial') {
    if (u === 'cm') return { v: v / 2.54, unit: 'in' };
    if (u === 'mm') return { v: v / 25.4, unit: 'in' };
    if (u === '°C') return { v: v * 1.8, unit: '°F' };
  }
  return { v, unit: u };
}
const signed = (x) => fmtNum(x, true);
const imperial = () => window.TDPrefs.get().units === 'imperial';
const fmt = {
  rate(t) {
    const g = t && t.guidance, r = g && g.rate;
    if (!r || typeof r.value !== 'number') return '';
    if (!imperial() || r.unit === '%') return String(r.text || ''); // a percentage reads the same in both unit settings
    const c = convert(r.value, r.unit);
    return `${signed(c.v)} ${c.unit}`;
  },
  outlook(t, year) {
    const g = t && t.guidance, o = g && Array.isArray(g.outlook) && g.outlook.find((x) => x && x.year === year);
    if (!o) return '';
    if (!imperial()) return String(o.text || '').replace(/ by \d{4}$/, '');
    const lo = convert(o.low, o.unit), hi = convert(o.high, o.unit);
    const a = signed(lo.v), b = signed(hi.v);
    return a === b ? `about ${a} ${lo.unit}` : `${a} to ${b} ${lo.unit}`;
  },
  years(t) { return t && t.period ? `${t.period.start.slice(0, 4)}–${t.period.end.slice(0, 4)}` : ''; },
  unit(t) { const g = t && t.guidance; return convert(0, (g && g.display && g.display.unit) || (t && t.units) || '').unit; },
};
// The "why" sentence; a rate note (Rain: "about 60 mm more a year") goes in brackets before its final full stop.
function noteText(n) {
  if (!n || typeof n.text !== 'string') return '';
  if (!imperial() || typeof n.value !== 'number') return n.text;
  const c = convert(Math.abs(n.value), n.unit);
  return `about ${fmtNum(c.v, false)} ${c.unit} ${n.value < 0 || /\bless\b/.test(n.text) ? 'less' : 'more'} a year`;
}
function whyOf(g) {
  if (!g || !g.why) return '';
  const note = noteText(g.rate && g.rate.note);
  return note ? `${g.why.replace(/\.\s*$/, '')} (${note}).` : g.why;
}
const perOf = (t) => (t && t.guidance && t.guidance.rate && t.guidance.rate.per) || '';
const riskShort = (g) => (g && g.risk_label ? g.risk_label.replace(/ risk$/, '') : '');
const riskClass = (g) => (g && ['high', 'moderate', 'low', 'unknown'].includes(g.risk) ? g.risk : 'unknown');

// The line under a pinned place's name.
function pinLine(p) {
  if (p.status === 'loading') { const n = secsSince(p); return n < 2 ? 'Checking…' : `Checking… ${n} s`; }
  if (p.status === 'error') return 'No record here';
  const t = p.trend, rate = fmt.rate(t);
  if (rate) return t.guidance.rate.unit === '%' ? `${rate} every 10 years` : `${rate} ${perOf(t)}`.trim(); // the sign already gives the direction
  if (t.guidance) return 'No clear change';
  return (t.meaning && t.meaning.comparison) || 'No clear change';
}

/* ---------- the sidebar ---------- */

function buildSeg(box, opts, cur, onPick) {
  clear(box);
  opts.forEach((o) => {
    const on = o.value === cur;
    const b = el('button', { type: 'button', role: 'radio', 'aria-checked': String(on), class: on ? 'on' : '' }, o.label);
    b.addEventListener('click', () => onPick(o.value));
    box.append(b);
  });
}
const SOURCE_SEG = { coops: 'NOAA tide gauges', psmsl: 'Global gauges (PSMSL)', power: 'NASA POWER', era5: 'ERA5', ghcn: 'Weather station', grace: 'GRACE satellites' };

function renderControls() {
  const w = winOf(curWin);
  if (!w) return;
  const prefs = window.TDPrefs.get();
  buildSeg($('seg-units'), [{ value: 'metric', label: w.units[0] }, { value: 'imperial', label: w.units[1] }], prefs.units, (u) => window.TDPrefs.set({ units: u }));
  buildSeg($('seg-look'), [2035, 2050, 2075].map((y) => ({ value: y, label: String(y) })), prefs.lookAhead, (y) => window.TDPrefs.set({ lookAhead: y }));
  const v = varById(curWin), many = !!v && Array.isArray(v.sources) && v.sources.length > 1;
  $('src-field').hidden = !many;
  if (many) {
    const cur = sourceFor(curWin) || v.sources[0];
    buildSeg($('seg-source'), v.sources.map((s) => ({ value: s, label: SOURCE_SEG[s] || sourceShort(s) })), cur, (s) => {
      wsrc[curWin] = s === v.sources[0] ? null : s;
      ensureLoaded(curWin);
      renderControls(); changed(); renderFoot();
    });
    $('src-help').textContent = SOURCE_HELP[cur] || '';
  }
}

function renderSidebar() {
  const ul = $('pins');
  clear(ul);
  const all = pinList(curWin);
  if (all.length < MAX_PINS) lockRm = false;
  ul.className = lockRm ? 'pins show-rm' : 'pins';
  all.forEach((p) => {
    const g = p.trend && p.trend.guidance;
    const btn = el('button', { type: 'button', class: 'pin' + (p.selected ? ' on' : ''), 'aria-pressed': String(p.selected) },
      el('i', { class: p.selected ? 'dot sel' : `dot s${p.slot}`, 'aria-hidden': 'true' }),
      el('span', { class: 'pn' }, el('b', {}, p.label), el('small', { class: 'pn-line', 'data-key': p.key }, pinLine(p))),
      g && g.risk_label ? el('span', { class: `risk ${riskClass(g)}` }, riskShort(g)) : '');
    btn.addEventListener('click', () => TD.select(p.key));
    const rm = el('button', { type: 'button', class: 'rm', 'aria-label': `Remove ${p.label}` }, '×');
    rm.addEventListener('click', () => TD.removePlace(p.key));
    ul.append(el('li', { class: 'pinrow' }, btn, rm));
  });
  $('pin-hint').hidden = false;
}

/* ---------- the recommendation card ---------- */

function renderRec() {
  const box = $('rec');
  clear(box);
  const pin = selectedPin(curWin), w = winOf(curWin);
  box.setAttribute('aria-busy', String(!!pin && pin.status === 'loading'));
  if (!w) return;
  if (!pin) {
    box.append(el('h2', { tabindex: '-1' }, 'Pin a place to see its recommendation'), el('p', { class: 'say' }, 'Search above, or click the map, to pin a place.'));
    return;
  }
  const h2 = (txt) => el('h2', { tabindex: '-1', id: 'rec-h' }, txt);
  if (pin.status === 'loading') {
    const max = usualSecs();
    box.append(h2(pin.label), el('progress', { id: 'rec-prog', max: String(max), value: String(Math.min(secsSince(pin), max - 0.5)), 'aria-label': `Loading ${pin.label}` }), el('p', { class: 'say', id: 'rec-load-text' }, loadingLine(pin)));
    return;
  }
  if (pin.status === 'error') {
    box.append(h2(pin.label), el('p', { class: 'say' }, pin.error || "We couldn't check this place."), el('p', { class: 'say' }, 'Try another place.'));
    if (curWin === 'sea_level') box.append(el('p', { class: 'say' }, el('a', { href: 'https://sealevel.nasa.gov/ipcc-ar6-sea-level-projection-tool', target: '_blank', rel: 'noopener' }, 'Future sea level (NASA projection tool)\u00a0↗')));
    return;
  }

  state.params = { lat: pin.lat, lon: pin.lon, variable: curWin }; // the sentence helpers read the place being shown
  state.place = { label: pin.label, link: pin.link };
  const t = pin.trend, g = t.guidance, m = meaningOf(t), look = window.TDPrefs.get().lookAhead;
  const risk = riskClass(g), years = fmt.years(t), pl = t.place && t.place.name;
  const station = pl && t.source && ['coops', 'ghcn', 'psmsl'].includes(t.source.id) ? pl : '';
  const srcLine = el('div', { class: 'src' });
  const short = t.source && SOURCE_PLAIN[t.source.id];
  const srcText = (short ? short.charAt(0).toUpperCase() + short.slice(1) : shownName(t.source)) + (short && station ? ` at ${station}` : '');
  if (isHttps(t.source)) srcLine.append(el('a', { href: t.source.url, class: 'srclink', target: '_blank', rel: 'noopener' }, `${srcText}\u00a0↗`)); else srcLine.append(srcText);
  srcLine.append(` · ${years}`);
  box.append(el('div', { class: 'where' }, el('div', {}, h2(pin.label), srcLine), g && g.risk_label ? el('span', { class: `risk ${risk}` }, g.risk_label) : ''));

  // big number
  const rate = fmt.rate(t);
  const big = el('div', { class: 'big' });
  if (g && rate) big.append(rate, ' ', el('small', {}, perOf(t)));
  else if (g) big.append('No clear change', ' ', el('small', {}, years));
  else big.append(verdictWord(t));
  box.append(big);
  box.append(el('p', { class: 'say' }, g && g.why ? whyOf(g) : [m && m.headline, m && m.comparison].filter(Boolean).join(' ') || verdictCopy(t, nameOf(t.variable), placeOf(t)).p1));
  if (g && g.recommendation) box.append(el('div', { class: `advice ${risk}` }, el('b', {}, 'Our recommendation'), g.recommendation));

  // two facts
  const facts = el('div', { class: 'facts2' });
  const outlook = fmt.outlook(t, look);
  if (g && outlook) facts.append(el('div', {}, g.outlook_label || 'If the past trend continues', el('b', {}, `${outlook} by ${look}`)));
  const yrs = Number(t.period.end.slice(0, 4)) - Number(t.period.start.slice(0, 4));
  facts.append(el('div', {}, 'How sure we are', el('b', {}, [m && m.confidence, `${yrs} years of data`].filter(Boolean).join(' · '))));
  box.append(facts);

  const acts = el('div', { class: 'acts' });
  if (g && g.future_link && typeof g.future_link.url === 'string' && g.future_link.url.startsWith('https://')) {
    acts.append(el('a', { class: 'btn dark', href: g.future_link.url, target: '_blank', rel: 'noopener' }, `${g.future_link.label} ↗`));
  }
  const how = el('button', { type: 'button', class: 'btn ghost', id: 'how-open' }, 'How we calculated this');
  how.addEventListener('click', openHow);
  acts.append(how);
  box.append(acts);
  if (g && g.disclaimer) box.append(el('p', { class: 'disc' }, g.disclaimer));
}
function verdictWord(t) { return t.verdict === 'rising' ? 'Rising' : t.verdict === 'falling' ? 'Falling' : 'No clear change'; }

// The four plain-words strings the server sends (trend.meaning); null when they are missing or malformed.
const CONFIDENCE = ['Very clear', 'Clear', 'Not clear'];
function meaningOf(t) {
  const m = t && t.meaning;
  if (!m || typeof m !== 'object' || typeof m.headline !== 'string' || typeof m.confidence !== 'string' || typeof m.comparison !== 'string' || typeof m.limit !== 'string') return null;
  return m.headline && m.limit && CONFIDENCE.includes(m.confidence) ? m : null;
}

/* ---------- "How we calculated this" (a native dialog with today's detail) ---------- */

function openHow() {
  const pin = selectedPin(curWin);
  if (!pin || pin.status !== 'ok') return;
  const dlg = $('how-dialog');
  if (!dlg.open) dlg.showModal();
  renderDetail(pin);
  // Real or noise? listens for a finished answer: tell it this one is on screen now
  document.dispatchEvent(new CustomEvent('td:load-end', { detail: compatDetail(pin) }));
}
function renderDetail(pin) {
  const t = pin.trend, series = pin.series;
  state.params = { lat: pin.lat, lon: pin.lon, variable: curWin };
  state.place = { label: pin.label, link: pin.link };
  $('how-place').textContent = `${pin.label}`;
  const vk = t.verdict === 'rising' ? 'rising' : t.verdict === 'falling' ? 'falling' : 'none';
  $('how-detail').dataset.verdict = vk;
  renderChart(series, t);
  renderTable(series, true);
  const c = verdictCopy(t, nameOf(t.variable), placeOf(t));
  $('verdict-p1').textContent = c.p1;
  $('verdict-lean').textContent = c.lean || '';
  $('verdict-lean').hidden = !c.lean;
  $('verdict-p2').textContent = c.p2;
  $('verdict-evidence').textContent = `p-value: ${fmtP(t.p_value)}. The p-value says how easily luck alone could produce a trend this strong. Below 0.05 counts as a clear change.`;
  const facts = $('facts');
  clear(facts);
  [
    ['Period', `${t.period.start} to ${t.period.end}`],
    ['Months of data', String(t.n)],
    ['Exact rate', `${fmtVal(t.slope_per_decade, t.units)} per decade`],
    ['Range of trends the data support', `${fmtVal(t.ci_low, t.units)} to ${fmtVal(t.ci_high, t.units)} per decade`],
    ['p-value', fmtP(t.p_value)],
    ['Seasons removed', t.deseasonalized ? 'Yes' : 'No'],
    ['Adjusted for neighbouring months', t.autocorrelation_adjusted ? 'Yes' : 'No'],
    ['Source', 'src'],
    ['Method', t.method === 'mann_kendall_sen' ? "Mann-Kendall test with Sen's slope" : String(t.method)],
  ].forEach(([l, v]) => {
    if (v !== 'src') { facts.append(fact(l, v)); return; }
    const dd = el('dd', {});
    srcLink(dd, t.source, true);
    facts.append(el('div', {}, el('dt', {}, l), dd));
  });
  const list = $('notes-list');
  clear(list);
  const notes = [];
  (t.caveats || []).concat(series.notes || []).forEach((n) => { if (!notes.includes(n)) notes.push(n); });
  if (!notes.length) notes.push('No extra caveats from the source.');
  notes.forEach((n) => list.append(el('li', {}, n)));
  $('howto-ac').textContent = t.autocorrelation_adjusted
    ? 'We adjusted for months that resemble their neighbours; without that the result would look surer than it is.'
    : 'We did not adjust for months that resemble their neighbours, so treat the result as less certain.';
  try {
    const ms = series.times.map(monthIndex);
    window.renderStripes($('stripes-art'), yearlyAverages(ms, deseasonalize(series.times, series.values)), t.period);
    srcBlock($('stripes-source'), 'Raw data', t.source);
  } catch (e) { $('year-stripes').hidden = true; }
}
function fact(label, node) { return el('div', {}, el('dt', {}, label), el('dd', {}, node)); }

/* ---------- compatibility for "Real or noise?" (it reads TD.state and td:load-end) ---------- */

function compatDetail(pin) {
  const params = { variable: curWin, lat: pin.lat, lon: pin.lon };
  if (sourceFor(curWin)) params.source = sourceFor(curWin);
  return { id: 0, ok: pin.status === 'ok', params, place: { lat: pin.lat, lon: pin.lon, label: pin.label }, series: pin.series, trend: pin.trend, error: null, origin: 'window' };
}
function compatState() {
  const pin = selectedPin(curWin);
  if (!pin) return { place: null, variable: curWin, source: null, start: null, end: null, status: 'idle', series: null, trend: null, error: null };
  return { place: { lat: pin.lat, lon: pin.lon, label: pin.label }, variable: curWin, source: sourceFor(curWin) || null, start: null, end: null,
    status: pin.status === 'ok' ? 'loaded' : pin.status === 'error' ? 'error' : 'loading', series: pin.series, trend: pin.trend, error: pin.error ? { status: 0, heading: pin.error } : null };
}

/* ---------- the window: head, title, footer, route ---------- */

function renderFoot() {
  const p = $('foot-data');
  clear(p);
  const w = winOf(curWin);
  if (!w) return;
  const v = varById(curWin), sid = sourceFor(curWin) || (v && v.sources && v.sources[0]);
  const src = SOURCES[sid];
  p.append('Data: ');
  if (src) srcLink(p, src, true); else p.append('public records');
  p.append(". Trends: our calculation (Mann-Kendall test with Sen's slope, seasons removed).");
  // the Open-Meteo attribution travels with its data
  const ul = $('footer-sources');
  let li = Array.prototype.find.call(ul.children, (x) => x.dataset.credit === 'era5');
  if (sid === 'era5' && SOURCES.era5) {
    if (!li) { li = el('li', {}); li.dataset.credit = 'era5'; ul.append(li); }
    clear(li);
    li.append(el('a', { href: SOURCES.era5.url, class: 'srclink' }, SOURCES.era5.credit), `, ${SOURCES.era5.dataset}, `, el('a', { href: SOURCES.era5.licence.url, class: 'srclink' }, SOURCES.era5.licence.name));
  } else if (li) li.remove();
}
function placeCredit() {
  const ul = $('footer-sources');
  const li = el('li', {});
  li.dataset.credit = 'places';
  li.append('Place names: ');
  srcLink(li, PLACE_SOURCE, true);
  ul.prepend(li);
}

function setStatusLine(text) { const s = $('status-line'); s.textContent = text || ''; s.hidden = !text; }

function showWindow(id) {
  curWin = id;
  const settings = id === 'settings';
  $('win-measure').hidden = settings;
  $('win-settings').hidden = !settings;
  $('settings-link').setAttribute('aria-current', settings ? 'page' : 'false');
  document.querySelectorAll('#nav a').forEach((a) => {
    const on = a.dataset.id === id;
    a.classList.toggle('act', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  if (settings) {
    document.title = 'Settings · Bhoomi';
  } else {
    const w = winOf(id);
    document.title = `${w.name} · Bhoomi`;
    $('win-h1').textContent = w.name;
    $('win-q').textContent = w.question;
    $('place').setAttribute('placeholder', w.search);
    closeList(); setPlaceStatus(''); showCredit(null);
    $('place').value = '';
    renderControls();
    renderFoot();
    dropErrors(id);
    ensureLoaded(id);
    changed();
  }
  syncTimer();
  document.dispatchEvent(new CustomEvent('td:route', { detail: { window: id } }));
  if (settings) document.dispatchEvent(new CustomEvent('td:pins', { detail: { window: id, pins: [], selected: null } }));
}

// Read the address: a window slug, "#settings", or an older link with a place.
function route() {
  const raw = location.hash.replace(/^#/, '');
  setStatusLine('');
  if (raw === 'settings') return showWindow('settings');
  if (WIN_BY_SLUG[raw]) return showWindow(WIN_BY_SLUG[raw].id);
  if (!raw) { const w0 = curWin === 'settings' ? DEFAULT_WINDOW : curWin; history.replaceState(null, '', '#' + WIN_BY_ID[w0].slug); return showWindow(w0); }
  const h = new URLSearchParams(raw);
  if (h.get('tab') === 'connect') { history.replaceState(null, '', '#settings'); return showWindow('settings'); }
  if (h.get('tab') === 'ask') { history.replaceState(null, '', '#' + WIN_BY_ID[DEFAULT_WINDOW].slug); return showWindow(DEFAULT_WINDOW); }
  // an older place link: #variable=…&lat=…&lon=…&place=…
  const vid = VARIABLE_ALIASES[h.get('variable')] || h.get('variable');
  const num = (k) => { const r = (h.get(k) || '').trim(); return r === '' ? NaN : Number(r); };
  const lat = num('lat'), lon = num('lon');
  const w = winOf(vid);
  if (!w || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
    history.replaceState(null, '', '#' + WIN_BY_ID[DEFAULT_WINDOW].slug);
    showWindow(DEFAULT_WINDOW);
    setStatusLine('That link is out of date.');
    return undefined;
  }
  const src = h.get('source');
  const v = varById(w.id);
  if (src && v && Array.isArray(v.sources) && v.sources.includes(src)) wsrc[w.id] = src === v.sources[0] ? null : src;
  history.replaceState(null, '', '#' + w.slug);
  showWindow(w.id);
  const named = cleanPlace(h.get('place'));
  const label = named || coordText(lat, lon);
  addPin(w.id, { label, lat, lon, link: true });
  return undefined;
}

/* ---------- adding, selecting, removing ---------- */

let lockRm = false; // the list is full of the visitor's own places: show every Remove control until there is room
function addPin(win, spec) {
  const e = store[win];
  const lat = Number(Number(spec.lat).toFixed(4)), lon = Number(Number(spec.lon).toFixed(4));
  const key = pinKeyOf(lat, lon);
  // a place within 0.25 degrees of a pinned one is that pin: select it, keep its label, say nothing
  const near = e.pins.find((p) => Math.abs(p.lat - lat) <= 0.25 && Math.abs(((p.lon - lon + 540) % 360) - 180) <= 0.25);
  if (near && near.preset && !spec.link && cleanPlace(spec.label) && spec.label !== 'Pinned spot') { near.label = cleanPlace(spec.label); near.preset = false; } // a typed place keeps its name
  if (near) { e.selected = pinKeyOf(near.lat, near.lon); saveStore(); if (win === curWin) { ensureLoaded(win); changed(); } return { ok: true }; }
  const label = cleanPlace(spec.label) || coordText(lat, lon);
  let replaced = null;
  if (e.pins.length >= MAX_PINS) {
    // the list is full: an example place makes room (the last one that is not selected); only then is the visitor asked to
    for (let i = e.pins.length - 1; i >= 0; i--) if (e.pins[i].preset && pinKeyOf(e.pins[i].lat, e.pins[i].lon) !== e.selected) { replaced = e.pins.splice(i, 1)[0]; break; }
    if (!replaced) {
      lockRm = true;
      if (win === curWin) { changed(); TD.announce(`Your list is full. Remove a place with × to add ${label}.`); }
      return { ok: false, reason: 'full' };
    }
  }
  const pin = { label, lat, lon, link: spec.link === true };
  e.pins.push(pin);
  assignSlots(e.pins);
  e.selected = key;
  saveStore();
  if (win === curWin) { ensureLoaded(win); changed(); TD.announce(replaced ? `Replaced ${replaced.label} with ${pin.label} to keep six places.` : `Pinned ${pin.label}.`); }
  return { ok: true };
}

/* ---------- the place search (combobox) ---------- */

// Suggestions while typing: 350 ms after the last key, from 3 characters; Enter searches now from 2. Only the newest
// reply is used. Replies are kept for the visit (30 texts), so the same text is never asked for twice.
// Everything in a reply is untrusted text: it only ever goes in through textContent or an attribute value.
const search = { seq: 0, timer: 0, items: [], active: -1, cache: new Map(), last: null };
const placeLabel = (r) => [r.name, r.admin1, r.country].filter(Boolean).join(', ');
const pinLabel = (r) => [r.name, r.admin1].filter(Boolean).join(', ');
const goodPlace = (r) => !!r && typeof r.name === 'string' && r.name !== '' && Number.isFinite(r.lat) && Number.isFinite(r.lon) && Math.abs(r.lat) <= 90 && Math.abs(r.lon) <= 180;
// Written only when the text changes, so a screen reader does not repeat it on every key.
function setPlaceStatus(text) { const s = $('place-status'); if (s.textContent !== text) s.textContent = text; }
function closeList() {
  const l = $('place-list');
  l.hidden = true; clear(l);
  search.items = []; search.active = -1;
  $('place').setAttribute('aria-expanded', 'false');
  $('place').removeAttribute('aria-activedescendant');
}
function setActive(i) {
  const opts = $('place-list').children;
  Array.prototype.forEach.call(opts, (o, k) => o.setAttribute('aria-selected', String(k === i)));
  search.active = i;
  if (i >= 0) { $('place').setAttribute('aria-activedescendant', opts[i].id); opts[i].scrollIntoView({ block: 'nearest' }); }
  else $('place').removeAttribute('aria-activedescendant');
}
// "Place search: <name> ↗"; the address is used only when it starts with https://
function showCredit(src) {
  const c = $('place-credit');
  clear(c);
  if (src === null) { c.hidden = true; return; }
  const s = src && typeof src.name === 'string' && src.name ? src : PLACE_SOURCE;
  c.append('Place search: ');
  if (isHttps(s)) c.append(el('a', { href: s.url, class: 'srclink' }, s.name + ' ↗')); else c.append(s.name);
  c.hidden = false;
}
function showResults(res, q) {
  search.items = res.results;
  search.last = { q, res };
  const l = $('place-list');
  clear(l);
  res.results.forEach((r, i) => {
    const o = el('li', { role: 'option', id: 'place-opt-' + i, 'aria-selected': 'false', class: 'opt' },
      el('span', { class: 'opt-name' }, r.name), el('span', { class: 'opt-sub' }, [r.admin1, r.country].filter(Boolean).join(', ')));
    o.setAttribute('aria-label', placeLabel(r));
    // pressing an option must not take focus from the box (mouse and touch)
    o.addEventListener('pointerdown', (e) => e.preventDefault());
    o.addEventListener('mousedown', (e) => e.preventDefault());
    o.addEventListener('click', () => pickPlace(r));
    l.append(o);
  });
  l.hidden = false;
  $('place').setAttribute('aria-expanded', 'true');
  setActive(-1);
  const n = res.results.length;
  setPlaceStatus(n === 1 ? '1 place found.' : `${n} places found. Use the up and down arrow keys, then Enter.`);
  showCredit(res.source);
}
async function runSearch(q, enter) {
  const id = ++search.seq;
  closeList(); showCredit(null);
  let r = search.cache.get(q);
  if (!r) {
    setPlaceStatus('Looking for places…'); // only when a request really starts
    r = await api('/api/places', { q });
    if (id !== search.seq) return; // an older reply: drop it
    if (r.ok && r.body && Array.isArray(r.body.results)) { search.cache.set(q, r); if (search.cache.size > 30) search.cache.delete(search.cache.keys().next().value); }
  }
  if (r.ok && r.body && Array.isArray(r.body.results)) {
    const results = r.body.results.filter(goodPlace);
    if (!results.length) { showCredit(r.body.source); setPlaceStatus(`No place found for “${q}”. Check the spelling, or try a bigger town nearby.`); return; }
    if (enter && results.length === 1) { pickPlace(results[0]); return; }
    showResults({ results, source: r.body.source }, q);
    return;
  }
  if (r.net) setPlaceStatus("We can't reach the server. Check your connection and try again.");
  else if (r.status === 429) { const n = parseInt(r.retryAfter, 10); setPlaceStatus(n > 0 ? `Too many searches. Please wait ${n} ${n === 1 ? 'second' : 'seconds'} and try again.` : 'Too many searches. Please wait a minute and try again.'); }
  else if (r.status === 400 || r.status === 422) setPlaceStatus('Please type between 2 and 80 characters.');
  else setPlaceStatus("Place search isn't working right now. Try again in a minute.");
}
function queued() {
  clearTimeout(search.timer);
  const q = $('place').value.trim();
  search.seq++; // anything still on its way is now out of date
  closeList(); showCredit(null);
  if (!q) { setPlaceStatus(''); return; }
  if (q.length < 3) { setPlaceStatus('Type at least 3 letters to see suggestions.'); return; }
  setPlaceStatus('');
  search.timer = setTimeout(() => runSearch(q), 350);
}
function pickPlace(r) {
  clearTimeout(search.timer); search.seq++;
  closeList(); showCredit(null);
  TD.addPlace({ lat: r.lat, lon: r.lon, label: pinLabel(r) }).then((res) => {
    if (!res.ok && res.reason === 'full') setPlaceStatus(`Your list is full. Remove a place with × to add ${pinLabel(r)}.`);
    else if (res.ok) { $('place').value = ''; setPlaceStatus(''); const h = $('rec').querySelector('h2'); if (h) h.focus({ preventScroll: true }); } else setPlaceStatus('You can pin up to 6 places. Remove one first.');
  });
}
$('place').addEventListener('input', queued);
$('place').addEventListener('keydown', (e) => {
  const n = search.items.length, open = !$('place-list').hidden;
  // a held key sends no more requests (moving through an open list is not a request)
  if (e.repeat && (e.key === 'Enter' || (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')))) { e.preventDefault(); return; }
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    if (!open) { // open the last list for this text, or search now
      const q = $('place').value.trim();
      if (search.last && search.last.q === q) showResults(search.last.res, q);
      else if (q.length >= 2) { clearTimeout(search.timer); runSearch(q); }
      return;
    }
    const d = e.key === 'ArrowDown' ? 1 : -1;
    setActive(search.active < 0 ? (d > 0 ? 0 : n - 1) : (search.active + d + n) % n);
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (open && search.active >= 0) pickPlace(search.items[search.active]);
    else {
      const q = $('place').value.trim();
      clearTimeout(search.timer);
      if (q.length < 2) setPlaceStatus('Type at least 2 letters, then press Enter.'); else runSearch(q, true);
    }
  } else if (e.key === 'Escape') {
    if (open) { e.preventDefault(); closeList(); showCredit(null); setPlaceStatus(''); }
    else if ($('place').value) { e.preventDefault(); $('place').value = ''; queued(); }
  } else if (e.key === 'Tab') closeList();
});
$('place').addEventListener('blur', () => setTimeout(() => {
  if ($('place-list').hidden) return;
  closeList(); showCredit(null);
  if (/ found\./.test($('place-status').textContent)) setPlaceStatus('');
}, 120));

/* ---------- TD: the interface the modules use (web/design/09-rework.md) ---------- */

let readyRes;
const readyPromise = new Promise((res) => { readyRes = res; });
let liveTimer = 0;
window.TD = {
  ready: readyPromise,
  get variables() { return state.variables; },
  windows: WINDOWS.map((w) => ({ id: w.id, slug: w.slug, name: w.name })),
  get window() { return curWin; },
  pins() { return curWin === 'settings' ? [] : pinList(curWin); },
  select(key, opts) {
    const e = store[curWin];
    if (!e || !e.pins.some((p) => pinKeyOf(p.lat, p.lon) === key)) return;
    e.selected = key;
    saveStore();
    dropErrors(curWin, key);
    ensureLoaded(curWin);
    changed();
    if (!opts || opts.focus !== false) { const h = $('rec').querySelector('h2'); if (h) h.focus({ preventScroll: true }); }
  },
  // Pin a place in the current window (select it when it is already pinned). Resolves { ok, reason } ('full' = six pinned).
  addPlace(spec) {
    spec = spec || {};
    const lat = Number(spec.lat), lon = Number(spec.lon);
    if (spec.lat === null || spec.lon === null || spec.lat === '' || spec.lon === '' || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180 || curWin === 'settings') return Promise.resolve({ ok: false, reason: 'invalid' });
    return Promise.resolve(addPin(curWin, { label: spec.label, lat, lon }));
  },
  removePlace(key) {
    const e = store[curWin];
    if (!e) return;
    const i = e.pins.findIndex((p) => pinKeyOf(p.lat, p.lon) === key);
    if (i < 0) return;
    const [gone] = e.pins.splice(i, 1);
    delete results[resKey(curWin, gone)]; // a retry timer or a late reply for it is then dropped
    if (e.selected === key) e.selected = e.pins.length ? pinKeyOf(e.pins[0].lat, e.pins[0].lon) : null;
    saveStore();
    changed();
    TD.announce(`Removed ${gone.label}.`);
  },
  fmt,
  announce(text) {
    const l = $('td-live');
    l.textContent = '';
    clearTimeout(liveTimer);
    liveTimer = setTimeout(() => { l.textContent = String(text); }, 30);
  },
  cleanPlace,
  addCredit(id, text, url) {
    const ul = $('footer-sources');
    let li = Array.prototype.find.call(ul.children, (x) => x.dataset.credit === id);
    if (!li) { li = el('li', {}); li.dataset.credit = id; ul.append(li); }
    clear(li);
    if (typeof url === 'string' && url.startsWith('https://')) li.append(el('a', { href: url, class: 'srclink' }, text + ' ↗')); else li.append(String(text));
  },
  // for "Real or noise?" (it was written for the old page)
  get state() { return compatState(); },
  fetchTrend(params) { return api('/api/trend', params).then((r) => ({ ok: r.ok, status: r.status, body: r.body, retryAfter: r.retryAfter === undefined ? null : r.retryAfter })); },
  loadPlace(spec) {
    spec = spec || {};
    if ($('how-dialog').open) $('how-dialog').close();
    return TD.addPlace({ lat: spec.lat, lon: spec.lon, label: spec.label }).then((r) => Object.assign({ ok: r.ok }, r));
  },
};

/* ---------- start ---------- */

function buildNav() {
  const nav = $('nav');
  WINDOWS.forEach((w) => {
    const a = el('a', { href: '#' + w.slug }, w.name);
    a.dataset.id = w.id;
    nav.append(a);
  });
}
async function init() {
  buildNav();
  placeCredit();
  loadStore();
  const r = await api('/api/variables');
  if (r.ok && Array.isArray(r.body)) state.variables = r.body;
  readyRes(state.variables);
  document.dispatchEvent(new CustomEvent('td:ready', { detail: { variables: state.variables } }));
  route();
}

$('how-close').addEventListener('click', () => $('how-dialog').close());
$('how-dialog').addEventListener('click', (e) => { if (e.target === $('how-dialog')) $('how-dialog').close(); }); // a click on the backdrop
$('how-dialog').addEventListener('close', () => { const b = $('how-open'); if (b) b.focus(); document.dispatchEvent(new CustomEvent('td:load-start', { detail: { id: 0, params: null, place: null, origin: 'window' } })); });
let lastBand = layoutFor(window.innerWidth).vw;
window.addEventListener('resize', () => {
  const b = layoutFor(window.innerWidth).vw;
  if (b !== lastBand && $('how-dialog').open) { lastBand = b; const p = selectedPin(curWin); if (p && p.status === 'ok') renderChart(p.series, p.trend); }
});
document.addEventListener('td:prefs', () => { if (curWin !== 'settings') { renderControls(); changed(); } });
window.addEventListener('hashchange', route);
// the dialog's detail is printed whole
document.addEventListener('DOMContentLoaded', init);
