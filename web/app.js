'use strict';
/* Trend Detective page. Same-origin /api/ calls only. Printed numbers come from the API;
   the browser's own arithmetic is for drawing (see the "pure helpers" block). */

// What the page does on a first visit with no link: null = no data request (only /api/variables), the empty start shows.
// A place set here loads with origin 'share-link' (no scroll, no focus, and the first-visit guide stays closed).
// For the old behaviour use { variable: 'sea_level', lat: 40.71, lon: -74.01, place: 'New York' }.
const FIRST_LOAD = null;
const GEO_LABEL = 'your location'; // the label of a "Use my location" pick; its link and search box stay empty
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
// The sideways-scroll hint wording: touch screens swipe, others scroll.
function scrollHintText(coarse) { return (coarse ? 'Swipe' : 'Scroll') + ' sideways to see the whole line.'; }
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

function rawLine(source, withTrend) { return `Raw values: ${source ? source.name : 'unknown'}.` + (withTrend ? " Trend and range: our calculation, the Mann-Kendall test with Sen's slope on monthly values with seasons removed." : ''); }
function chartHead(t, name, place) { return `${name} at ${place}: ${fmtVal(t.slope_per_decade, t.units)} per decade, ${t.period.start.slice(0, 4)} to ${t.period.end.slice(0, 4)}`; }

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

/* ---------- tabs and the URL hash (pure) ---------- */

const TABS = [
  { id: 'explore', label: 'Explore', title: 'Trend Detective' }, // the page title stays the short name; the question is the h2
  { id: 'ask', label: 'Ask', title: 'Trend Detective: Ask' },
  { id: 'connect', label: 'Use in your AI', title: 'Trend Detective: Use in your AI' },
];
const APPS = ['claude', 'claude-code', 'cursor', 'vscode', 'other'];

// A place name from a link or a search is only ever shown with textContent. Control characters and angle brackets
// are dropped, 60 characters at most.
function cleanPlace(s) { const t = String(s == null ? '' : s).replace(/[\u0000-\u001f\u007f-\u009f<>]/g, '').trim().slice(0, 60); return t || null; }
// "YYYY" or "YYYY-MM", years 1850 to 2100; anything else is null.
const yr = (v) => (/^(18[5-9]\d|19\d\d|20\d\d|2100)(-(0[1-9]|1[0-2]))?$/.test(v || '') ? v : null);
// Both given and start not before end: drop both.
function window2(a, b) { a = yr(a); b = yr(b); return a && b && monthIndex(a) >= monthIndex(b) ? [null, null] : [a, b]; }

// Names that older or hand-typed links may carry, mapped to the catalogue's ids. None of these was ever a catalogue id
// (the five ids have not changed since the catalogue was written); they are friendly aliases only. Any other unknown
// id is an out-of-date link.
const VARIABLE_ALIASES = { precipitation: 'precip', rain: 'precip', temperature: 'air_temp', air_temperature: 'air_temp',
  max_temperature: 'air_temp_max', hottest_day: 'air_temp_max', groundwater: 'water_storage', land_water: 'water_storage' };

// Hash -> { tab, app, explore }. Missing or unknown tab = explore; unknown app = claude.
// explore is set only for a complete, in-range variable/lat/lon (share links); else null.
function parseHash(raw) {
  const h = new URLSearchParams(String(raw).replace(/^#/, ''));
  const t = h.get('tab'), a = h.get('app');
  const num = (k) => { const r = (h.get(k) || '').trim(); return r === '' ? NaN : Number(r); };
  const lat = num('lat'), lon = num('lon');
  const ok = !!h.get('variable') && Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
  return {
    exploreBad: !ok && (h.has('variable') || h.has('lat') || h.has('lon')), // looks like a place link but is not usable
    tab: t === 'ask' || t === 'connect' ? t : 'explore',
    app: APPS.includes(a) ? a : 'claude',
    explore: ok ? (([start, end]) => ({ variable: VARIABLE_ALIASES[h.get('variable')] || h.get('variable'), lat, lon, source: h.get('source') || null, place: cleanPlace(h.get('place')), start, end }))(window2(h.get('start'), h.get('end'))) : null,
  };
}
// { tab, app, explore } -> hash text without '#'. Explore keeps its old key-less form.
function writeHash(st) {
  if (st.tab === 'ask') return 'tab=ask';
  if (st.tab === 'connect') return 'tab=connect' + (st.app && st.app !== 'claude' ? '&app=' + st.app : '');
  const e = st.explore;
  if (!e) return '';
  return `variable=${e.variable}&lat=${Number(e.lat).toFixed(2)}&lon=${Number(e.lon).toFixed(2)}` + (e.source ? '&source=' + encodeURIComponent(e.source) : '')
    + (e.start ? '&start=' + e.start : '') + (e.end ? '&end=' + e.end : '') + (cleanPlace(e.place) ? '&place=' + encodeURIComponent(cleanPlace(e.place)) : '');
}

// A place from a link or an answer, made safe for the catalog: null for an unknown measurement; the source
// is kept only when the measurement offers it and it is not the default one (the default is never written).
function fixExplore(e, vars) {
  const v = vars.find((x) => x.id === e.variable);
  if (!v) return null;
  const ok = !!e.source && Array.isArray(v.sources) && v.sources.includes(e.source) && e.source !== v.sources[0];
  const [start, end] = window2(e.start, e.end);
  return { variable: e.variable, lat: e.lat, lon: e.lon, source: ok ? e.source : null, place: cleanPlace(e.place), start, end };
}

// The source the page sends: only one the user chose by hand, offered by the measurement, and not its default.
function sourceToSend(v, userSource) {
  return v && Array.isArray(v.sources) && v.sources.length > 1 && userSource && v.sources.includes(userSource) && userSource !== v.sources[0] ? userSource : undefined;
}
// The source the control shows after a result: the one the result came from, when the measurement lists it.
function pickShown(v, resultSourceId) {
  return v && Array.isArray(v.sources) && v.sources.includes(resultSourceId) ? resultSourceId : null;
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

// Standard tabs pattern (automatic activation): arrows wrap, Home/End jump, one tab stop.
function wireTablist(tabs, activate) {
  tabs.forEach((t, i) => {
    t.addEventListener('click', () => activate(i, false));
    t.addEventListener('keydown', (e) => {
      const n = tabs.length;
      const j = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i + n - 1) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1;
      if (j < 0) return;
      e.preventDefault();
      tabs[j].focus();
      activate(j, true);
    });
  });
}
function selectTab(tabs, panels, i) {
  tabs.forEach((t, k) => { t.setAttribute('aria-selected', String(k === i)); t.tabIndex = k === i ? 0 : -1; });
  panels.forEach((p, k) => { p.hidden = k !== i; });
}

const isHttps = (src) => !!src && typeof src.url === 'string' && src.url.startsWith('https://');
// One block-level 48 px line: grey "<label>:" then "<name> ↗" as a link (https URLs only), plain text without the arrow otherwise.
// The text sits in one inner span so a long name wraps across the full line, not beside the label.
function srcBlock(node, label, source) {
  clear(node);
  const name = source ? source.name : 'unknown';
  const inner = (arrow) => el('span', {}, el('span', { class: 'src-label' }, label + ':'), ` ${name}` + (arrow ? '\u00a0↗' : ''));
  if (isHttps(source)) node.append(el('a', { href: source.url, class: 'srclink' }, inner(true)));
  else node.append(el('span', { class: 'srclink' }, inner(false)));
}
// Link with the name only (footer list).
function srcLink(node, source, arrow) {
  if (isHttps(source)) node.append(el('a', { href: source.url, class: 'srclink' }, source.name + (arrow ? '\u00a0↗' : '')));
  else node.append(source ? source.name : 'unknown');
}

/* ---------- state ---------- */

const tabState = { tab: 'explore', app: 'claude' };
const state = { userSource: null, variables: [], req: 0, series: null, trend: null, selIdx: null, fromGeo: false, params: null, slowTimer: 0, chart: null,
  place: null, origin: 'coords', win: null, status: 'idle', err: null }; // place = { label, source } | null; win = { start, end } | null

function placeOf(t) {
  const q = state.params || {};
  const lat = q.lat !== undefined ? q.lat : t.place.lat, lon = q.lon !== undefined ? q.lon : t.place.lon;
  const named = placeFor(lat, lon, t.place && t.place.name, t.source && t.source.id);
  // Only coordinates from the data (gridded sources) and a place the visitor named: say the visitor's word, not numbers.
  if (!state.place || state.place.fromLink || named !==`${fixed(Number(lat), 2)}, ${fixed(Number(lon), 2)}`) return named;
  if (state.place.label === GEO_LABEL) return GEO_LABEL;
  return cleanPlace(state.place.label.split(',')[0]) || named;
}
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
    return { ok: res.ok, status: res.status, body, retryAfter: res.headers.get('Retry-After') };
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
    b.addEventListener('focus', () => b.scrollIntoView({ inline: 'nearest', block: 'nearest' }));
    box.append(b);
  });
}
function markChips() {
  const lat = Number($('lat').value), lon = Number($('lon').value);
  document.querySelectorAll('#examples .chip').forEach((b) => {
    const p = PRESETS[+b.dataset.i];
    const on = p.lat === lat && p.lon === lon && p.variable === $('variable').value;
    b.setAttribute('aria-pressed', String(on));
    if (on) { // keep the pressed chip in view inside the sideways row (phones)
      const row = $('chips'), r = row.getBoundingClientRect(), c = b.getBoundingClientRect();
      if (c.left < r.left || c.right > r.right) row.scrollLeft += c.left - r.left - (r.width - c.width) / 2;
    }
  });
}
// Chip glyphs: the direction of an answer loaded in this visit, for the CURRENT measurement and source only.
// Any change of measurement or source clears them all (a glyph left behind would be a wrong statement).
const glyphs = { key: '', map: {} };
const GLYPH_WORD = { rising: 'rising', falling: 'falling', none: 'no clear change' };
function paintGlyphs() {
  document.querySelectorAll('#examples .chip').forEach((b) => {
    const g = glyphs.map[b.dataset.i], old = b.querySelector('.chip-g');
    if (old) old.remove();
    const label = PRESETS[+b.dataset.i].label;
    if (!g) { b.removeAttribute('aria-label'); return; }
    const w = el('span', { class: 'chip-g', 'aria-hidden': 'true' });
    w.append(shapeSvg(g === 'rising' ? 'up' : g === 'falling' ? 'down' : 'flat'));
    b.append(w);
    b.setAttribute('aria-label', `${label}, ${GLYPH_WORD[g]}`);
  });
}
// One key for a measurement and source, always taken from the request's own params (never from the selects).
const glyphKey = (params) => params.variable + '|' + (params.source || '');
function clearGlyphs() { glyphs.key = ''; glyphs.map = {}; paintGlyphs(); }
function noteGlyph(t, params) {
  if (!t || !params) return;
  if (glyphKey(params) !== glyphs.key) { glyphs.key = glyphKey(params); glyphs.map = {}; }
  const i = PRESETS.findIndex((p) => Math.abs(p.lat - params.lat) <= 0.005 && Math.abs(p.lon - params.lon) <= 0.005);
  if (i >= 0) glyphs.map[i] = t.verdict === 'rising' || t.verdict === 'falling' ? t.verdict : 'none';
  paintGlyphs();
}
function setCoords(on) { $('coords').hidden = !on; $('coords-toggle').setAttribute('aria-expanded', String(on)); }
function openCoords() { setCoords(true); }
function applyPreset(i) {
  const p = PRESETS[i];
  TD.loadPlace({ lat: p.lat, lon: p.lon, label: p.label, variable: p.variable, origin: 'example' });
}
// Both selects use short names at every width, open or closed (full names clip in the closed select).
const VAR_SHORT = { air_temp_max: 'Hottest day', water_storage: 'Water storage' };
function fillVariables() {
  const sel = $('variable');
  clear(sel);
  state.variables.forEach((v) => sel.append(el('option', { value: v.id }, VAR_SHORT[v.id] || stripParens(v.name))));
}
function syncVariableUI() {
  const v = varById($('variable').value);
  $('variable-help').textContent = v ? `Good for: ${v.good_for}.` : '';
  const src = $('source');
  clear(src);
  const many = !!v && Array.isArray(v.sources) && v.sources.length > 1;
  if (many) v.sources.forEach((s) => src.append(el('option', { value: s }, sourceShort(s))));
  // keep the source the user chose when this measurement has it; otherwise the default
  if (many) src.value = v.sources.includes(state.userSource) ? state.userSource : v.sources[0];
  $('source-field').hidden = !many;
  $('pick').classList.toggle('one', !many);
  sourceHelp();
}
// After a result the control shows the source the result came from (a fallback is not the user's choice).
function showResultSource(res) {
  const id = pickShown(varById($('variable').value), res && res.source && res.source.id);
  if (id) { $('source').value = id; sourceHelp(); }
}
// After a request that gave no result the control shows the source that was sent, or the default.
function showSentSource(params) {
  const v = varById(params.variable);
  if (!v || $('source-field').hidden) return;
  $('source').value = params.source && v.sources.includes(params.source) ? params.source : v.sources[0];
  sourceHelp();
}
function sourceHelp() {
  $('source-help').textContent = $('source-field').hidden ? '' : (SOURCE_HELP[$('source').value] || '');
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
  if (!ok) {
    openCoords();
    const first = document.querySelector('[aria-invalid="true"]');
    if (first) first.focus();
    return null;
  }
  const v = varById($('variable').value);
  const p = { variable: $('variable').value, lat, lon };
  const sent = sourceToSend(v, state.userSource);
  if (sent) p.source = sent;
  if (state.win) { if (state.win.start) p.start = state.win.start; if (state.win.end) p.end = state.win.end; }
  return p;
}

function placeNow() { return { lat: state.params.lat, lon: state.params.lon, label: state.place ? state.place.label : '' }; }
// The page's events (design/00-frame.md section 3). A load-end also answers every TD.loadPlace waiting for it.
const loadWaiters = [];
function fire(name, detail) {
  document.dispatchEvent(new CustomEvent(name, { detail, bubbles: false }));
  if (name === 'td:load-end') loadWaiters.splice(0).forEach((done) => done(detail));
}

function submit(user) {
  const p = readParams();
  if (!p) {
    // Modules saw a request start or an answer: tell them it is over. The id is the request being closed when one
    // was running, else the new id (the one this attempt took).
    const was = state.status === 'loading', shown = !!state.series;
    const endId = was ? state.req : state.req + 1;
    state.req++; // drop any answer still on its way
    setBusy(false);
    ['chart-wrap', 'how', 'answer-card', 'problem', 'answer-bar'].forEach((id) => { $(id).hidden = true; });
    state.series = null; state.trend = null;
    if (was || shown) {
      state.status = 'error'; state.err = { status: 422, heading: 'Check the latitude and longitude.' };
      fire('td:load-end', { id: endId, ok: false, params: state.params, place: state.params ? placeNow() : null, series: null, trend: null, error: state.err, origin: state.origin });
    }
    return;
  }
  state.params = p;
  if (!state.fromGeo && tabState.tab === 'explore') history.replaceState(null, '', '#' + writeHash({ tab: 'explore', explore: Object.assign({ place: state.place && state.place.label }, p) }));
  markChips();
  fire('td:place-pick', { lat: p.lat, lon: p.lon, label: state.place ? state.place.label : '', variable: p.variable, source: p.source || null, start: p.start || null, end: p.end || null, origin: state.origin });
  run(p, user);
}

function locate() {
  const fail = () => { const m = $('geo-msg'); m.hidden = false; m.textContent = "We couldn't get your location. Type coordinates or pick an example place."; };
  $('geo-msg').hidden = true;
  if (!navigator.geolocation) return fail();
  navigator.geolocation.getCurrentPosition((pos) => {
    TD.loadPlace({ lat: pos.coords.latitude, lon: pos.coords.longitude, label: GEO_LABEL, origin: 'geo' });
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

// keep = "Try again" on the same request: the old card stays, dimmed. Any new request clears the old answer.
async function run(params, user, keep) {
  const id = ++state.req;
  state.params = params;
  if (glyphKey(params) !== glyphs.key) { clearGlyphs(); glyphs.key = glyphKey(params); } // arrows belong to the latest request's measurement and source
  const first = !keep;
  if (first) { ['chart-wrap', 'how', 'answer-card', 'answer-bar', 'old-link'].forEach((i) => { $(i).hidden = true; }); state.series = null; state.trend = null; }
  $('problem').hidden = true;
  $('empty').hidden = true; // the start card is gone for good once a request has begun
  state.status = 'loading'; state.err = null;
  setBusy(true, first);
  fire('td:load-start', { id, params, place: placeNow(), origin: state.origin });
  state.scrollId = 0;
  if (user && first) { state.scrollId = id; visitorScrolled = false; scrollToAnswer(); }
  const [sr, tr] = await Promise.all([api('/api/series', params), api('/api/trend', params)]);
  if (id !== state.req) return; // stale
  setBusy(false);
  show(sr, tr, params, user, id);
}

// Phones: bring the answer to the top when a request starts, and again just after it ends (the page above it can
// change in between, for example a guide card closing). From 900 px only if its top is off screen. The jump is
// instant; the second one is skipped when the visitor scrolled in between.
let visitorScrolled = false;
['wheel', 'touchmove'].forEach((ev) => window.addEventListener(ev, () => { visitorScrolled = true; }, { passive: true }));
window.addEventListener('keydown', (e) => { if (/^(Page(Up|Down)|Home|End|Arrow(Up|Down)| )$/.test(e.key) && e.target === document.body) visitorScrolled = true; });
function scrollToAnswer() {
  const w = $('answer-wrap');
  if (window.innerWidth >= 900) { const t = w.getBoundingClientRect().top; if (t >= 0 && t < window.innerHeight) return; }
  w.scrollIntoView({ block: 'start', behavior: 'auto' });
}
// "40.71° N, 74.01° W"
function coordText(lat, lon) { return `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(2)}° ${lon >= 0 ? 'E' : 'W'}`; }

function show(sr, tr, params, user, id) {
  let heading, err = null;
  const problem = (p, status) => { err = { status, heading: p.heading }; return showProblem(p); };
  $('chart-wrap').hidden = true;
  $('year-stripes').hidden = true; // shown again only when renderVerdict draws them for this answer
  $('how').hidden = true;
  $('answer-card').hidden = true;
  $('problem').hidden = true;
  $('spark').hidden = true; // like the stripes: shown again only when renderVerdict draws it for this answer
  ['answer-card', 'chart-wrap', 'how'].forEach((i) => { delete $(i).dataset.verdict; });
  state.series = null; state.trend = null;

  if (!sr.ok) {
    showSentSource(params);
    heading = problem(problemFor(sr, params), sr.status);
  } else {
    const s = sr.body;
    const has = s && Array.isArray(s.values) && s.values.some((v) => v != null);
    if (!has) {
      showSentSource(params);
      heading = problem({ heading: 'No data for this place.', paras: [`${s && s.source ? s.source.name : 'The source'} has no readings here for this measurement. Try another place or measurement.`] }, 200);
    } else {
      state.series = s;
      state.trend = tr.ok ? tr.body : null;
      showResultSource(state.trend || s);
      $('chart-wrap').hidden = false;
      renderChart(s, state.trend);
      document.querySelectorAll('.t-only').forEach((li) => { li.hidden = !state.trend; });
      renderTable(s, !!state.trend);
      $('how').hidden = false; $('how').open = false; // closed on every new answer; without a trend only the chart help and the table show
      if (state.trend) {
        heading = renderVerdict(state.trend, s);
        if (!params.start && !params.end) noteGlyph(state.trend, params); // a chip opens the full record, so a windowed answer is not its arrow
        renderHow(state.trend);
      } else {
        heading = problem(problemFor(tr, params), tr.status);
      }
    }
  }
  const ok = !!(state.series && state.trend);
  state.status = ok ? 'loaded' : 'error'; state.err = err;
  $('answer-bar').hidden = !state.series;
  if (state.series) {
    const pl = (state.trend || state.series).place;
    const pn = state.place;
    $('answer-place').textContent = 'Showing: ' + (pn && pn.fromLink ? `${pn.label} (${coordText(params.lat, params.lon)})` // a name from a link is shown with its coordinates
      : pn && pn.label || pl && cleanPlace(pl.name) || coordText(params.lat, params.lon));
  }
  fire('td:load-end', { id, ok, params, place: placeNow(), series: state.series, trend: state.trend, error: err, origin: state.origin });
  if (state.scrollId === id) setTimeout(() => { if (id === state.req && !visitorScrolled) scrollToAnswer(); }, 60);
  if (user && heading) heading.focus({ preventScroll: true }); // the answer's headline (#meaning-heading), or the problem heading
}

function problemFor(r, params) {
  const again = [{ label: 'Try again', fn: () => run(state.params, true, true) }];
  if (r.status === 429) { // rate limit: show the API's own sentence
    const d = r.body && typeof r.body.detail === 'string' && r.body.detail ? r.body.detail : 'Too many requests right now. Please wait a little and try again.';
    return { heading: 'Too many requests.', paras: [d], buttons: again };
  }
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
    // The US-coast sentence is only true while CO-OPS is the only tide-gauge source.
    if (!(varById('sea_level') && varById('sea_level').sources.length > 1)) out.paras.push('Tide gauges sit along US coasts.');
    // Name the source that was asked for; with none sent and several offered, no source line (it would guess).
    const sv = varById('sea_level'), single = !sv || sv.sources.length < 2;
    const named = params.source ? SOURCES[params.source] : (single ? SOURCES[sv ? sv.sources[0] : 'coops'] : null);
    if (named) out.source = named;
    out.buttons = [{ label: 'Try New York', fn: () => applyPreset(0) }];
    if (varById('air_temp')) {
      out.buttons.push({ label: 'Show air temperature here', fn: () => { $('variable').value = 'air_temp'; syncVariableUI(); submit(true); } });
    }
  }
  const v = varById(params.variable), def = v && v.sources && v.sources[0];
  if (params.source && def && params.source !== def) {
    out.buttons = (out.buttons || []).concat([{ label: `Use ${SOURCE_LABELS[def] || def} for this place`, fn: () => { state.userSource = null; syncVariableUI(); submit(true); } }]);
  }
  out.paras.push('Try another place or measurement.');
  return out;
}

function showProblem(p) {
  $('problem-heading').textContent = p.heading;
  const body = $('problem-body');
  clear(body);
  p.paras.forEach((t) => body.append(el('p', {}, t)));
  if (p.source) { const sp = el('div', { class: 'srcline' }); srcBlock(sp, 'Source', p.source); body.append(sp); }
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

// 96 x 40 sparkline beside the big number: yearly averages (faint), the trend line and its band, from the same
// series and the same maths as the chart. No axes, no numbers. Decorative picture with a text alternative.
function renderSpark(t, series, word) {
  const box = $('spark');
  clear(box);
  if (![t.slope_per_decade, t.ci_low, t.ci_high].every(Number.isFinite)) { box.hidden = true; return; }
  const ms = series.times.map(monthIndex), des = deseasonalize(series.times, series.values);
  const yrs = yearlyAverages(ms, des);
  if (yrs.length < 3) { box.hidden = true; return; }
  const m0 = ms[0], m1 = ms[ms.length - 1], W = 96, H = 40, pad = 4;
  const ts = ms.map((m) => (m - m0) / 120), tEnd = (m1 - m0) / 120;
  const tm = median(ts.filter((_, i) => des[i] != null)), yp = trendIntercept(ts, des, t.slope_per_decade) + t.slope_per_decade * tm;
  const at = (slope, x) => yp + slope * (x - tm);
  const ends = [at(t.ci_low, 0), at(t.ci_low, tEnd), at(t.ci_high, 0), at(t.ci_high, tEnd)];
  const vals = yrs.map((y) => y.mean).concat(ends);
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi > lo ? hi - lo : 1;
  const X = (m) => (m1 === m0 ? 0 : (m - m0) / (m1 - m0) * W), Y = (v) => pad + (hi - v) / span * (H - 2 * pad);
  const f = (n) => n.toFixed(1);
  const s = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Small picture of the trend, ${word.toLowerCase()}: the line and its range from ${t.period.start.slice(0, 4)} to ${t.period.end.slice(0, 4)}. Shows direction only, no scale.` });
  s.append(svg('polygon', { points: `0,${f(Y(ends[0]))} ${W},${f(Y(ends[1]))} ${W},${f(Y(ends[3]))} 0,${f(Y(ends[2]))}`, class: 'sp-band' }));
  s.append(svg('polyline', { points: yrs.map((y) => `${f(X(y.x))},${f(Y(y.mean))}`).join(' '), class: 'sp-years' }));
  s.append(svg('line', { x1: 0, y1: f(Y(at(t.slope_per_decade, 0))), x2: W, y2: f(Y(at(t.slope_per_decade, tEnd))), class: 'sp-trend' }));
  box.append(s);
  box.hidden = false;
}

function fact(label, node) { return el('div', {}, el('dt', {}, label), el('dd', {}, node)); }

// The four plain-words strings the server sends (trend.meaning); null when they are missing or malformed.
const CONFIDENCE = ['Very clear', 'Clear', 'Not clear'];
function meaningOf(t) {
  const m = t && t.meaning;
  if (!m || typeof m !== 'object' || typeof m.headline !== 'string' || typeof m.confidence !== 'string' || typeof m.comparison !== 'string' || typeof m.limit !== 'string') return null;
  return m.headline && m.limit && CONFIDENCE.includes(m.confidence) ? m : null;
}

// The answer card: label, headline, verdict band, big line, how sure (and the sparkline), what past data can't tell, one source.
// Everything exact (rate, range, p-value, facts) goes in the "How we calculated this" section (#how), see renderHow.
function renderVerdict(t, series) {
  const c = verdictCopy(t, nameOf(t.variable), placeOf(t));
  const m = meaningOf(t);
  const y0 = t.period.start.slice(0, 4), y1 = t.period.end.slice(0, 4);
  const h = $('meaning-heading');
  h.textContent = m ? m.headline : c.p1;
  const band = $('verdict-heading');
  clear(band);
  band.append(shapeSvg(c.shape), c.head);
  const vk = t.verdict === 'rising' ? 'rising' : t.verdict === 'falling' ? 'falling' : 'none';
  ['answer-card', 'chart-wrap', 'how'].forEach((i) => { $(i).dataset.verdict = vk; }); // the band, chart lines and year stripes read it
  $('verdict-big').textContent = m ? (m.comparison || `No clear change from ${y0} to ${y1}.`) : `${fmtVal(t.slope_per_decade, t.units)} per decade, ${y0} to ${y1}.`;
  $('ac-conf').hidden = !m;
  $('ac-limit').hidden = !m;
  if (m) {
    $('ac-conf-word').textContent = m.confidence;
    $('ac-limit-text').textContent = m.limit;
  }
  // The stripes and the sparkline are extra: if one fails, hide it and keep the answer.
  try {
    const ms = series.times.map(monthIndex);
    window.renderStripes($('stripes-art'), yearlyAverages(ms, deseasonalize(series.times, series.values)), t.period);
    srcBlock($('stripes-source'), 'Raw data', t.source);
  } catch (e) {
    $('year-stripes').hidden = true;
  }
  if (m) { try { renderSpark(t, series, c.head); } catch (e) { $('spark').hidden = true; } }
  srcBlock($('verdict-source'), 'Raw data', t.source);
  $('answer-card').hidden = false;
  return h;
}

// "How we calculated this": closed on every new answer. Parts 1 to 9 in the order of the page (index.html).
function renderHow(t, series) {
  const c = verdictCopy(t, nameOf(t.variable), placeOf(t));
  $('how').open = false;
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
  (t.caveats || []).concat((state.series && state.series.notes) || []).forEach((n) => { if (!notes.includes(n)) notes.push(n); });
  if (!notes.length) notes.push('No extra caveats from the source.');
  notes.forEach((n) => list.append(el('li', {}, n)));

  $('howto-ac').textContent = t.autocorrelation_adjusted
    ? 'We adjusted for months that resemble their neighbours; without that the result would look surer than it is.'
    : 'We did not adjust for months that resemble their neighbours, so treat the result as less certain.';
  $('how').hidden = false;
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
  const cs = $('chart-source');
  srcBlock(cs, 'Raw data', t ? t.source : s.source);
  if (t) cs.append(el('span', { class: 'source' }, 'Trend and range: our calculation.'));
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

/* ---------- start ---------- */

// One entry per source the catalog lists (all known sources if there is no catalog yet), then the place-name credit.
// Items added by a module through TD.addCredit (data-credit) are kept.
function fillFooter(vars) {
  const ul = $('footer-sources');
  ul.querySelectorAll('li:not([data-credit])').forEach((li) => li.remove()); // init() can run again ("Try again")
  const used = vars ? new Set(vars.flatMap((v) => v.sources || [])) : null;
  const items = [];
  Object.entries(SOURCES).forEach(([id, src]) => {
    if (used && !used.has(id)) return;
    if (!used && id === 'grace') return; // known only through the catalog
    const li = el('li', {}), sp = el('span', {}); // one span, so the row's text flows as one line of text
    if (src.credit) {
      // link, ", dataset, ", link
      sp.append(el('a', { href: src.url, class: 'srclink' }, src.credit), `, ${src.dataset}, `, el('a', { href: src.licence.url, class: 'srclink' }, src.licence.name));
    } else srcLink(sp, src);
    li.append(sp);
    items.push(li);
  });
  const pl = el('li', {}), psp = el('span', {}, 'Place names: ');
  srcLink(psp, PLACE_SOURCE, true);
  pl.append(psp);
  items.push(pl);
  ul.prepend(...items);
}

/* ---------- the tab bar ---------- */

let tabEls = [], panelEls = [];
function hashFor(id) {
  if (id === 'explore') return state.params && !state.fromGeo ? writeHash({ tab: 'explore', explore: Object.assign({ place: state.place && state.place.label }, state.params) }) : '';
  return writeHash({ tab: id, app: tabState.app });
}
function showTab(id, push) {
  tabState.tab = id;
  const i = TABS.findIndex((t) => t.id === id);
  selectTab(tabEls, panelEls, i);
  document.title = TABS[i].title;
  $('skip').setAttribute('href', '#h-' + id);
  if (push) {
    const h = hashFor(id);
    if (h !== location.hash.slice(1)) history.pushState(null, '', h ? '#' + h : location.pathname + location.search);
  }
}
function buildTabbar() {
  const bar = $('tabbar');
  bar.setAttribute('role', 'tablist');
  bar.setAttribute('aria-label', 'Sections');
  TABS.forEach((t) => {
    const b = el('button', { type: 'button', role: 'tab', id: 'tab-' + t.id, 'aria-controls': 'panel-' + t.id, class: 'tab' }, t.label);
    bar.append(b);
    const p = $('panel-' + t.id);
    p.setAttribute('role', 'tabpanel');
    p.setAttribute('aria-labelledby', 'tab-' + t.id);
    tabEls.push(b); panelEls.push(p);
  });
  wireTablist(tabEls, (i) => showTab(TABS[i].id, true));
}

// The hash changed (Back, Forward, or an edited address): show what it says.
function sameExplore(a, b) {
  return !!a && !!b && a.variable === b.variable && Number(a.lat).toFixed(2) === Number(b.lat).toFixed(2)
    && Number(a.lon).toFixed(2) === Number(b.lon).toFixed(2) && (a.source || null) === (b.source || null)
    && (a.start || null) === (b.start || null) && (a.end || null) === (b.end || null);
}
// A link that cannot be run (unknown measurement, bad number): say so in the empty card and run nothing.
function outOfDate() {
  $('old-link').hidden = false;
  if (!state.params) $('empty').hidden = false;
}
function onLocation() {
  const h = parseHash(location.hash);
  if (typeof setApp === 'function' && h.app !== tabState.app) setApp(h.app);
  showTab(h.tab, false);
  if ((h.explore || h.exploreBad) && state.variables.length) {
    // An unusable link (unknown measurement, bad number) falls back to the empty start: the hash is cleared and
    // nothing runs. A repeat call (popstate, then hashchange) finds state.params already set, so it starts no second request.
    const fixed = h.explore && fixExplore(h.explore, state.variables);
    if (!fixed) { if (tabState.tab === 'explore') { history.replaceState(null, '', location.pathname + location.search); outOfDate(); } return; }
    if (!sameExplore(fixed, state.params)) applyExplore(fixed, false, 'share-link');
  }
}

// Put a place, measurement and source into the controls and run it. e = { lat, lon, variable?, source?, place?, start?, end? }.
// A source that is undefined keeps the one the user chose; a measurement that is missing keeps the current one.
function applyExplore(e, user, origin) {
  state.origin = origin || 'share-link';
  state.fromGeo = state.origin === 'geo' || e.place === GEO_LABEL; // that place never reaches the link, whatever the origin
  if (e.source !== undefined) state.userSource = e.source || null;
  state.win = e.start || e.end ? { start: e.start || null, end: e.end || null } : null;
  // fromLink: the name came from the address bar, so nothing has checked it against the coordinates
  state.place = e.place ? { label: e.place, fromLink: state.origin === 'share-link' } : null;
  $('place').value = e.place && !state.fromGeo ? e.place : '';  closeList(); setPlaceStatus(''); showCredit(null);
  const lat = Number(Number(e.lat).toFixed(2)), lon = Number(Number(e.lon).toFixed(2));
  $('lat').value = lat; $('lon').value = lon;
  if (e.variable) $('variable').value = e.variable;
  syncVariableUI();
  // a link with only coordinates shows them
  if (state.origin === 'share-link' && !e.place && !PRESETS.some((p) => Math.abs(p.lat - lat) <= 0.005 && Math.abs(p.lon - lon) <= 0.005)) openCoords();
  markChips();
  submit(user);
}
// "Show on chart" from an Ask answer: a normal Explore hash entry, then the normal Explore flow.
function showOnChart(e0) {
  const e = fixExplore(e0, state.variables);
  if (!e) return;
  history.pushState(null, '', '#' + writeHash({ tab: 'explore', explore: e }));
  showTab('explore', false);
  applyExplore(e, true, 'coords');
}

let readyDone = false, readyRes;
const readyPromise = new Promise((res) => { readyRes = res; });
function tdReady(vars) {
  if (readyDone) return;
  readyDone = true; readyRes(vars);
  fire('td:ready', { variables: vars });
}

async function init() {
  fillFooter();
  const r = await api('/api/variables');
  if (!r.ok || !Array.isArray(r.body) || !r.body.length) {
    const p = problemFor(r.ok ? { status: 500 } : r, {});
    if (p.buttons) p.buttons = [{ label: 'Try again', fn: init }];
    $('empty').hidden = true;
    showProblem(p);
    tdReady([]);
    return;
  }
  // Display name only: the id and everything sent to the server stay `precip`.
  state.variables = r.body.map((v) => (v && v.id === 'precip' ? { ...v, name: 'Rain' } : v));
  $('problem').hidden = true;
  if (!state.params) $('empty').hidden = false;
  fillFooter(state.variables);
  fillVariables();
  if (varById('air_temp')) $('variable').value = 'air_temp'; // works everywhere; sea level fails inland
  syncVariableUI();
  const h = parseHash(location.hash);
  const fixed = h.explore && fixExplore(h.explore, state.variables);
  if (!fixed && (h.explore || h.exploreBad) && h.tab === 'explore') { history.replaceState(null, '', location.pathname + location.search); outOfDate(); }
  tdReady(state.variables);
  const first = fixed || (FIRST_LOAD && fixExplore(FIRST_LOAD, state.variables));
  if (first) applyExplore(first, false, 'share-link');
}

/* ---------- place search (combobox; design/00-frame.md section 6) ---------- */

// Suggestions while typing: 350 ms after the last key, from 3 characters; Enter searches now from 2. Only the newest
// reply is used. Replies are kept for the visit (30 texts), so the same text is never asked for twice.
// Everything in a reply is untrusted text: it only ever goes in through textContent or an attribute value.
const search = { seq: 0, timer: 0, items: [], active: -1, cache: new Map(), last: null };
const placeLabel = (r) => [r.name, r.admin1, r.country].filter(Boolean).join(', ');
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
  else setPlaceStatus("Place search isn't working right now. You can use coordinates instead.");
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
  if (!state.variables.length) { setPlaceStatus("We can't reach the server. Check your connection and try again."); return; }
  setPlaceStatus('');
  TD.loadPlace({ lat: r.lat, lon: r.lon, label: placeLabel(r), origin: 'search' });
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

/* ---------- TD: the interface the module scripts use (design/00-frame.md section 3) ---------- */

const ORIGINS = Object.freeze(['search', 'map', 'saved', 'recent', 'guide', 'example', 'geo', 'coords', 'share-link', 'undo', 'window']);
let liveTimer = 0;
window.TD = {
  ready: readyPromise,
  get variables() { return state.variables; },
  // a copy of the current state; series and trend are the reply objects themselves (read them, do not change them)
  get state() {
    const p = state.params;
    return { place: p ? placeNow() : null, variable: p ? p.variable : ($('variable').value || null), source: p && p.source || null,
      start: p && p.start || null, end: p && p.end || null, status: state.status, series: state.series, trend: state.trend, error: state.err ? Object.assign({}, state.err) : null };
  },
  // Validates, fills the controls, writes the link, scrolls and fires place-pick, load-start, load-end. Never rejects.
  loadPlace(spec) {
    spec = spec || {};
    const num = (x) => (x === null || x === undefined || x === '' || typeof x === 'boolean' ? NaN : Number(x));
    const lat = num(spec.lat), lon = num(spec.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180 || !state.variables.length
      || (spec.variable && !varById(spec.variable))) return Promise.resolve({ ok: false });
    const [start, end] = window2(spec.start, spec.end);
    const done = new Promise((res) => loadWaiters.push(res));
    applyExplore({ lat, lon, variable: spec.variable, source: spec.source, place: cleanPlace(spec.label), start, end }, true, ORIGINS.includes(spec.origin) ? spec.origin : 'coords');
    return done;
  },
  fetchTrend(params) { return api('/api/trend', params).then((r) => ({ ok: r.ok, status: r.status, body: r.body, retryAfter: r.retryAfter === undefined ? null : r.retryAfter })); },
  linkFor(s) {
    s = s || TD.state;
    const pl = s.place;
    const h = pl && pl.label !== GEO_LABEL ? writeHash({ tab: 'explore', explore: { variable: s.variable, lat: pl.lat, lon: pl.lon, source: s.source, start: s.start, end: s.end, place: pl.label } }) : '';
    return location.origin + location.pathname + '#' + h;
  },
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
  originOf: ORIGINS,
};

/* ---------- wiring ---------- */

buildChips();
$('controls').addEventListener('submit', (e) => {
  e.preventDefault();
  if ($('go').getAttribute('aria-disabled') === 'true') return;
  // typed coordinates are a new pick with no name
  state.origin = 'coords'; state.fromGeo = false; state.place = null; state.win = null; $('place').value = '';
  submit(true);
});
// measurement and source act on the place already chosen; with no place yet they only change the selection
const hasPlace = () => $('lat').value.trim() !== '' && $('lon').value.trim() !== '';
$('variable').addEventListener('change', () => { clearGlyphs(); syncVariableUI(); if (hasPlace()) submit(true); });
$('source').addEventListener('change', () => {
  const v = varById($('variable').value);
  state.userSource = v && $('source').value !== v.sources[0] ? $('source').value : null;
  clearGlyphs();
  sourceHelp();
  if (hasPlace()) submit(true);
});
$('locate').addEventListener('click', locate);
['lat', 'lon'].forEach((id) => $(id).addEventListener('input', () => {
  state.fromGeo = false;
  if (state.place && state.place.label === GEO_LABEL) state.place = null; // edited coordinates are no longer "your location"
  markChips();
}));
// "How we calculated this" is printed open
let howWasOpen = false;
window.addEventListener('beforeprint', () => { howWasOpen = $('how').open; $('how').open = true; });
window.addEventListener('afterprint', () => { $('how').open = howWasOpen; });
$('coords-toggle').addEventListener('click', () => setCoords($('coords').hidden));
$('change-place').addEventListener('click', (e) => { e.preventDefault(); $('h-explore').scrollIntoView({ block: 'start' }); $('place').focus({ preventScroll: true }); });
// Re-draw when the chart's box width changes by 8 px or more. One observer for the page's life, so none pile up;
// a re-draw changes the box's height at most, never its width, so it cannot trigger itself.
if (window.ResizeObserver) new ResizeObserver(() => {
  const w = $('chart-box').clientWidth;
  if (w && Math.abs(w - chartW) >= 8 && state.series && !$('chart-wrap').hidden) renderChart(state.series, state.trend);
}).observe($('chart-box'));
let lastBand = layoutFor(window.innerWidth).vw;
window.addEventListener('resize', () => {
  const b = layoutFor(window.innerWidth).vw;
  if (b !== lastBand && state.series && !$('chart-wrap').hidden) { lastBand = b; renderChart(state.series, state.trend); }
});
$('skip').addEventListener('click', (e) => { e.preventDefault(); $('h-' + tabState.tab).focus(); });
buildTabbar();
showTab(parseHash(location.hash).tab, false);
window.addEventListener('popstate', onLocation);
window.addEventListener('hashchange', onLocation);
// every script is deferred, so each module has attached its listeners before this runs
document.addEventListener('DOMContentLoaded', init);
