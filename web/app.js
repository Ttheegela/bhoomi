'use strict';
/* Trend Detective page. Same-origin /api/ calls only. Printed numbers come from the API;
   the browser's own arithmetic is for drawing (see the "pure helpers" block). */

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
// Where the "No change" label goes: the end of the dashed line the trend line is clear of.
// yl, yr = trend line's screen y at the left and right ends; zy = the dashed line's screen y (larger y = lower).
function noChangeLabel(yl, yr, zy) {
  if (yl > zy) return { end: 'left', below: false };   // trend is under the line on the left: clear above it
  if (yr > zy) return { end: 'right', below: false };  // under it on the right
  return { end: 'left', below: true };                 // above it at both ends: clear below it
}
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
  const s = fmtVal(t.slope_per_decade, t.units), lo = fmtVal(t.ci_low, t.units), hi = fmtVal(t.ci_high, t.units);
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
  { id: 'explore', label: 'Explore', title: 'Trend Detective' },
  { id: 'ask', label: 'Ask', title: 'Trend Detective: Ask' },
  { id: 'connect', label: 'Use in your AI', title: 'Trend Detective: Use in your AI' },
];
const APPS = ['claude', 'claude-code', 'cursor', 'vscode', 'other'];

// Hash -> { tab, app, explore }. Missing or unknown tab = explore; unknown app = claude.
// explore is set only for a complete, in-range variable/lat/lon (old share links); else null.
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
    explore: ok ? { variable: h.get('variable'), lat, lon, source: h.get('source') || null } : null,
  };
}
// { tab, app, explore } -> hash text without '#'. Explore keeps its old key-less form.
function writeHash(st) {
  if (st.tab === 'ask') return 'tab=ask';
  if (st.tab === 'connect') return 'tab=connect' + (st.app && st.app !== 'claude' ? '&app=' + st.app : '');
  const e = st.explore;
  if (!e) return '';
  return `variable=${e.variable}&lat=${Number(e.lat).toFixed(2)}&lon=${Number(e.lon).toFixed(2)}` + (e.source ? '&source=' + encodeURIComponent(e.source) : '');
}

// A place from a link or an answer, made safe for the catalog: null for an unknown measurement; the source
// is kept only when the measurement offers it and it is not the default one (the default is never written).
function fixExplore(e, vars) {
  const v = vars.find((x) => x.id === e.variable);
  if (!v) return null;
  const ok = !!e.source && Array.isArray(v.sources) && v.sources.includes(e.source) && e.source !== v.sources[0];
  return { variable: e.variable, lat: e.lat, lon: e.lon, source: ok ? e.source : null };
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
const state = { userSource: null, variables: [], req: 0, series: null, trend: null, selIdx: null, fromGeo: false, params: null, slowTimer: 0, chart: null };

function placeOf(t) {
  const q = state.params || {};
  const lat = q.lat !== undefined ? q.lat : t.place.lat, lon = q.lon !== undefined ? q.lon : t.place.lon;
  return placeFor(lat, lon, t.place && t.place.name, t.source && t.source.id);
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
    b.addEventListener('focus', () => b.scrollIntoView({ inline: 'nearest', block: 'nearest' }));
    box.append(b);
  });
}
function markChips() {
  const lat = Number($('lat').value), lon = Number($('lon').value);
  document.querySelectorAll('.chip').forEach((b) => {
    const p = PRESETS[+b.dataset.i];
    const on = p.lat === lat && p.lon === lon && p.variable === $('variable').value;
    b.setAttribute('aria-pressed', String(on));
    if (on) { // keep the pressed chip in view inside the sideways row (phones)
      const row = $('chips'), r = row.getBoundingClientRect(), c = b.getBoundingClientRect();
      if (c.left < r.left || c.right > r.right) row.scrollLeft += c.left - r.left - (r.width - c.width) / 2;
    }
  });
}
function openCoords() { $('coords').open = true; }
function applyPreset(i) {
  const p = PRESETS[i];
  state.fromGeo = false;
  $('lat').value = p.lat; $('lon').value = p.lon;
  if (varById(p.variable)) $('variable').value = p.variable;
  syncVariableUI();
  submit(true);
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
  return p;
}

function submit(user) {
  const p = readParams();
  if (!p) {
    state.req++; // drop any answer still on its way
    setBusy(false);
    ['chart-wrap', 'more', 'verdict-card', 'problem'].forEach((id) => { $(id).hidden = true; });
    state.series = null; state.trend = null;
    return;
  }
  if (!state.fromGeo && tabState.tab === 'explore') history.replaceState(null, '', '#' + writeHash({ tab: 'explore', explore: p }));
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

// keep = "Try again" on the same request: the old card stays, dimmed. Any new request clears the old answer.
async function run(params, user, keep) {
  const id = ++state.req;
  state.params = params;
  const first = !keep;
  if (first) { ['chart-wrap', 'more', 'verdict-card'].forEach((i) => { $(i).hidden = true; }); state.series = null; state.trend = null; }
  $('problem').hidden = true;
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
    showSentSource(params);
    heading = showProblem(problemFor(sr, params));
  } else {
    const s = sr.body;
    const has = s && Array.isArray(s.values) && s.values.some((v) => v != null);
    if (!has) {
      showSentSource(params);
      heading = showProblem({ heading: 'No data for this place.', paras: [`${s && s.source ? s.source.name : 'The source'} has no readings here for this measurement. Try another place or measurement.`] });
    } else {
      state.series = s;
      state.trend = tr.ok ? tr.body : null;
      showResultSource(state.trend || s);
      $('chart-wrap').hidden = false;
      renderChart(s, state.trend);
      document.querySelectorAll('#chart-fig .t-only').forEach((li) => { li.hidden = !state.trend; });
      renderTable(s, !!state.trend);
      if (state.trend) {
        heading = renderVerdict(state.trend, s);
        renderMore(state.trend);
      } else {
        heading = showProblem(problemFor(tr, params));
      }
    }
  }
  if (user && heading) heading.focus();
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

function fact(label, node) { return el('div', {}, el('dt', {}, label), el('dd', {}, node)); }

function renderVerdict(t, series) {
  const c = verdictCopy(t, nameOf(t.variable), placeOf(t));
  const h = $('verdict-heading');
  clear(h);
  h.append(shapeSvg(c.shape), c.head);
  const big = $('verdict-big');
  clear(big);
  big.append(el('span', { class: 'big-n' }, fmtVal(t.slope_per_decade, t.units)), ' ', el('span', { class: 'big-u' }, 'per decade'));
  $('verdict-lean').textContent = c.lean || '';
  $('verdict-lean').hidden = !c.lean;
  $('verdict-p1').textContent = c.p1;
  $('verdict-p2').textContent = c.p2;
  $('verdict-evidence').textContent = `p-value: ${fmtP(t.p_value)}. The p-value says how easily luck alone could produce a trend this strong. Below 0.05 counts as a clear change.`;
  srcBlock($('verdict-source'), 'Raw data', t.source);
  $('verdict-calc').textContent = 'Trend, range and verdict: our calculation.';

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
  (t.caveats || []).concat(series.notes || []).forEach((n) => { if (!notes.includes(n)) notes.push(n); });
  if (!notes.length) notes.push('No extra caveats from the source.');
  notes.forEach((n) => list.append(el('li', {}, n)));

  $('verdict-card').hidden = false;
  return h;
}

function renderMore(t) {
  $('howto-ac').textContent = t.autocorrelation_adjusted
    ? 'We adjusted for months that resemble their neighbours; without that the result would look surer than it is.'
    : 'We did not adjust for months that resemble their neighbours, so treat the result as less certain.';
  $('more').hidden = false;
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

function renderChart(s, t) {
  const box = $('chart-box');
  clear(box);
  const times = s.times, vals = s.values;
  const ms = times.map(monthIndex);
  const des = deseasonalize(times, vals);
  const m0 = ms[0], m1 = ms[ms.length - 1];
  const name = nameOf(s.variable), place = t ? placeOf(t) : placeFor(state.params.lat, state.params.lon, s.place && s.place.name, s.source && s.source.id);
  const units = unitLabel(s.units);
  const LY = layoutFor(window.innerWidth);
  const cw = box.clientWidth || LY.vw;
  const fs = Math.max(12, Math.round(12 * LY.vw / cw));
  const ml = Math.round(fs * 3.4) + 4, mr = 8, vw = LY.vw;
  const axis = Math.max(40, 2 * fs + 12);
  const gap = fs + 8; // between the upper panel's bottom and the lower panel's title
  const vh = LY.hA + gap + LY.hB + axis;
  const hh = Math.round(fs * 3.25); // panel header: title, y label, then room above the top tick label
  const pw = vw - ml - mr;
  const xS = (m) => ml + (m1 === m0 ? 0 : (m - m0) / (m1 - m0) * pw);

  const nn = (a) => a.filter((v) => v != null);
  const rawT = niceTicks(Math.min(...nn(vals)), Math.max(...nn(vals)));
  const desT = niceTicks(Math.min(0, ...nn(des)), Math.max(0, ...nn(des)));
  const A = { top: hh, bot: LY.hA - 4, t: rawT, y0: 0 };
  const yB = LY.hA + gap;
  const B = { top: yB + hh, bot: yB + LY.hB, t: desT, y0: yB };
  [A, B].forEach((p) => { p.yS = (v) => p.top + (p.t.hi - v) / (p.t.hi - p.t.lo) * (p.bot - p.top); });

  const root = svg('svg', { viewBox: `0 0 ${vw} ${vh}`, role: 'img', tabindex: '0', 'aria-labelledby': 'c-title c-desc', 'font-size': fs });
  root.append(svg('title', { id: 'c-title' }, `${name} at ${place}`));
  root.append(svg('desc', { id: 'c-desc' }, t ? captionText(t, name, place) : `${name} at ${place}, ${times[0]} to ${times[times.length - 1]}.`));

  const xt = yearTicks(m0, m1, pw, cw, vw);

  const panel = (P, title, ylabel) => {
    root.append(svg('text', { x: 0, y: P.y0 + fs, class: 'c-text c-title' }, title));
    root.append(svg('text', { x: 0, y: P.y0 + Math.round(fs * 2.15), class: 'c-text' }, ylabel));
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
    root.append(svg('text', { x: edge[1], y: B.bot + fs + 3, 'text-anchor': edge[0], class: 'c-text' }, String(y)));
  });
  root.append(svg('text', { x: ml + pw / 2, y: B.bot + 2 * fs + 6, 'text-anchor': 'middle', class: 'c-text' }, 'Year'));
  root.append(svg('line', { x1: ml, x2: vw - mr, y1: B.yS(0), y2: B.yS(0), class: 'c-zero' }));
  const noText = svg('text', { class: 'c-text c-halo' }, 'No change'); // placed once the trend line is known
  root.append(noText);

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

  const nc = trendLine ? noChangeLabel(trendLine.y1, trendLine.y2, B.yS(0)) : { end: 'right', below: false };
  noText.setAttribute('x', nc.end === 'left' ? ml + 4 : vw - mr - 2);
  noText.setAttribute('text-anchor', nc.end === 'left' ? 'start' : 'end');
  noText.setAttribute('y', nc.below ? B.yS(0) + fs + 3 : B.yS(0) - 5);

  // Yearly averages (dots) sit over the faint monthly line; the solid trend line goes on top. Drawing only: never printed.
  const dots = yearlyAverages(ms, des);
  const r = dotRadius(dots.map((d) => xS(d.x)), Math.max(2.5, fs * 0.22));
  dots.forEach((d) => root.append(svg('circle', { cx: xS(d.x).toFixed(1), cy: B.yS(d.mean).toFixed(1), r: r.toFixed(2), class: 's-year', 'aria-hidden': 'true' })));
  if (trendLine) root.append(svg('line', Object.assign({ class: 's-trend', 'clip-path': 'url(#c-clip)' }, trendLine)));
  root.append(noText); // drawn after the lines, band, dots and trend so nothing paints over it (its halo hides what is under it); only the hover rule follows

  const rule = svg('line', { y1: A.top, y2: B.bot, class: 'c-rule', visibility: 'hidden' });
  root.append(rule);
  box.append(root);

  $('chart-head').textContent = t ? chartHead(t, name, place) : `${name} at ${place}`;
  $('chart-caption').textContent = t ? captionText(t, name, place) : `${name} at ${place}.`;
  srcBlock($('chart-source'), 'Raw data', t ? t.source : s.source);
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

// One entry per source the catalog lists (all known sources if there is no catalog yet).
function fillFooter(vars) {
  const ul = $('footer-sources');
  clear(ul); // init() can run again ("Try again")
  const used = vars ? new Set(vars.flatMap((v) => v.sources || [])) : null;
  Object.entries(SOURCES).forEach(([id, src]) => {
    if (used && !used.has(id)) return;
    if (!used && id === 'grace') return; // known only through the catalog
    const li = el('li', {});
    if (src.credit) {
      // one list item, one flowing line of text: link, ", dataset, ", link
      li.append(el('a', { href: src.url, class: 'srclink' }, src.credit), `, ${src.dataset}, `, el('a', { href: src.licence.url, class: 'srclink' }, src.licence.name));
    } else srcLink(li, src);
    ul.append(li);
  });
}

/* ---------- the tab bar ---------- */

let tabEls = [], panelEls = [];
function hashFor(id) {
  if (id === 'explore') return state.params && !state.fromGeo ? writeHash({ tab: 'explore', explore: state.params }) : '';
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
    && Number(a.lon).toFixed(2) === Number(b.lon).toFixed(2) && (a.source || null) === (b.source || null);
}
function onLocation() {
  const h = parseHash(location.hash);
  if (typeof setApp === 'function' && h.app !== tabState.app) setApp(h.app);
  showTab(h.tab, false);
  if ((h.explore || h.exploreBad) && state.variables.length) {
    // An unusable link (unknown measurement, bad number) falls back to the default place and the hash is
    // rewritten, as on a fresh load. A repeat call (popstate, then hashchange) finds a good hash and
    // state.params already set, so it starts no second request.
    const fixed = h.explore && fixExplore(h.explore, state.variables);
    const e = fixed || fixExplore(PRESETS[0], state.variables);
    if (!fixed || !sameExplore(e, state.params)) applyExplore(e, false);
    if (!fixed && tabState.tab !== 'explore') history.replaceState(null, '', '#' + writeHash({ tab: h.tab, app: h.app }));
  }
}

// Put a place, measurement and source into the controls and run it.
function applyExplore(e, user) {
  state.fromGeo = false;
  state.userSource = e.source || null;
  $('lat').value = e.lat; $('lon').value = e.lon;
  $('variable').value = e.variable;
  syncVariableUI();
  if (!PRESETS.some((p) => Math.abs(p.lat - e.lat) <= 0.005 && Math.abs(p.lon - e.lon) <= 0.005)) openCoords();
  markChips();
  submit(user);
}
// "Show on chart" from an Ask answer: a normal Explore hash entry, then the normal Explore flow.
function showOnChart(e0) {
  const e = fixExplore(e0, state.variables);
  if (!e) return;
  history.pushState(null, '', '#' + writeHash({ tab: 'explore', explore: e }));
  showTab('explore', false);
  applyExplore(e, true);
}

async function init() {
  fillFooter();
  const r = await api('/api/variables');
  if (!r.ok || !Array.isArray(r.body) || !r.body.length) {
    const p = problemFor(r.ok ? { status: 500 } : r, {});
    if (p.buttons) p.buttons = [{ label: 'Try again', fn: init }];
    showProblem(p);
    return;
  }
  state.variables = r.body;
  fillFooter(state.variables);
  fillVariables();
  const h = parseHash(location.hash).explore;
  applyExplore((h && fixExplore(h, state.variables)) || fixExplore(PRESETS[0], state.variables), false);
}

buildChips();
$('controls').addEventListener('submit', (e) => { e.preventDefault(); if ($('go').getAttribute('aria-disabled') !== 'true') submit(true); });
$('variable').addEventListener('change', () => { syncVariableUI(); submit(true); });
$('source').addEventListener('change', () => {
  const v = varById($('variable').value);
  state.userSource = v && $('source').value !== v.sources[0] ? $('source').value : null;
  sourceHelp();
  submit(true);
});
$('locate').addEventListener('click', locate);
['lat', 'lon'].forEach((id) => $(id).addEventListener('input', () => { state.fromGeo = false; markChips(); }));
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
init();

