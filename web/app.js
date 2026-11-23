'use strict';
/* Bhoomi page shell (web/design/09-rework.md, 10-foundation.md). Same-origin /api/ calls only. Printed numbers come
   from the API; the place chart, "How we calculated this" and the CSV downloads are in explain.js (window.TDX). */

const PLACE_SOURCE = { name: 'Open-Meteo Geocoding API (GeoNames)', url: 'https://open-meteo.com/en/docs/geocoding-api' };

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

// Source name for a picker: short name, then the long label, then the raw id.
function sourceShort(id) { return SOURCE_SHORT[id] || SOURCE_LABELS[id] || id; }
function stripParens(name) { return String(name).replace(/\s*\([^)]*\)\s*$/, ''); }

/* ---------- DOM helpers ---------- */

const $ = (id) => document.getElementById(id);

function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const k in attrs || {}) n.setAttribute(k, attrs[k]);
  kids.forEach((c) => n.append(c));
  return n;
}
function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }

const isHttps = (src) => !!src && typeof src.url === 'string' && src.url.startsWith('https://');
// Display only: a trailing ", RLR monthly means" is jargon; the link is unchanged.
const shownName = (src) => (src && typeof src.name === 'string' ? src.name.replace(/, RLR monthly means$/, '') : 'unknown');
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
    question: 'Is the sea rising where you live? Some tide gauges have measured it for more than a century.', units: ['cm', 'inches'] },
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

const state = { variables: [] };
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
    const c = window.TDX.card(res.trend, imperial());
    TD.announce(`${p.label}: ${c.fact || c.word}`);
  }
}

/* ---------- pins as the modules see them ---------- */

function pinList(win) {
  const e = store[win];
  if (!e) return [];
  return e.pins.map((p) => {
    const key = pinKeyOf(p.lat, p.lon), r = results[resKey(win, p)] || { status: 'loading', trend: null, series: null, error: null };
    return { key, label: p.label, lat: p.lat, lon: p.lon, slot: p.slot, selected: key === e.selected, status: r.status, error: r.error, none: !!r.none, trend: r.trend, series: r.series, link: !!p.link, started: r.t0 || 0 };
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
  return `Checking ${SOURCES[sid] ? SOURCES[sid].name : 'the records'}. This usually takes about ${usualSecs()} seconds.${n >= 3 ? ` ${n} s so far.` : ''}`;
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
  renderDetail();
  renderFoot();
  syncTimer();
  const pins = pinList(curWin);
  const sel = pins.find((p) => p.selected);
  document.dispatchEvent(new CustomEvent('td:pins', { detail: { window: curWin, pins, selected: sel ? sel.key : null } }));
}

/* ---------- units and wording ---------- */

const imperial = () => window.TDPrefs.get().units === 'imperial';
const fmt = {
  // the rate every view prints: headline_rate ("+3.1 mm a year", "+0.31 °C per decade"), in the Units setting
  rate(t) { const r = t && window.TDX.rate(t, imperial()); return r ? r.text : ''; },
  // the pin line, the compare table's Rate and the Ask context (web/design/14-facts.md section 6): the rate when the
  // verdict is rising or falling, otherwise "No clear change" (an answer from before the rework has no rate: the verdict)
  line(t) { return t.verdict === 'rising' || t.verdict === 'falling' ? fmt.rate(t) || window.TDX.card(t, imperial()).word : 'No clear change'; },
};

// The line under a pinned place's name.
function pinLine(p) {
  if (p.status === 'loading') { const n = secsSince(p); return n < 2 ? 'Checking…' : `Checking… ${n} s`; }
  if (p.status === 'error') return 'No record here';
  return fmt.line(p.trend);
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
  const v = varById(curWin), many = !!v && Array.isArray(v.sources) && v.sources.length > 1;
  $('src-field').hidden = !many;
  if (many) {
    const cur = sourceFor(curWin) || v.sources[0];
    buildSeg($('seg-source'), v.sources.map((s) => ({ value: s, label: SOURCE_SEG[s] || sourceShort(s) })), cur, pickSource);
    $('src-help').textContent = SOURCE_HELP[cur] || '';
  }
}

// Measure the current window with another source (the sidebar's "Measured by", or a button on the card).
function pickSource(s) {
  const v = varById(curWin);
  if (!v || !Array.isArray(v.sources) || !v.sources.includes(s)) return;
  wsrc[curWin] = s === v.sources[0] ? null : s;
  ensureLoaded(curWin);
  renderControls(); changed(); renderFoot();
}

function renderSidebar() {
  const ul = $('pins');
  clear(ul);
  const all = pinList(curWin);
  if (all.length < MAX_PINS) lockRm = false;
  ul.className = lockRm ? 'pins show-rm' : 'pins';
  all.forEach((p) => {
    const btn = el('button', { type: 'button', class: 'pin' + (p.selected ? ' on' : ''), 'aria-pressed': String(p.selected) },
      el('i', { class: p.selected ? 'dot sel' : `dot s${p.slot}`, 'aria-hidden': 'true' }),
      el('span', { class: 'pn' }, el('b', {}, p.label), el('small', { class: 'pn-line', 'data-key': p.key }, pinLine(p))));
    btn.addEventListener('click', () => TD.select(p.key));
    const rm = el('button', { type: 'button', class: 'rm', 'aria-label': `Remove ${p.label}` }, '×');
    rm.addEventListener('click', () => TD.removePlace(p.key));
    ul.append(el('li', { class: 'pinrow' }, btn, rm));
  });
  $('pin-hint').hidden = false;
}

/* ---------- the answer card (web/design/10-foundation.md section 3, 14-facts.md section 1) ---------- */

// "Where to look next:" then each item, a link or plain text (14-facts.md section 4)
function nextLine(items) {
  const ul = el('ul', {});
  items.forEach((x) => ul.append(el('li', {}, x.href ? el('a', { href: x.href, target: '_blank', rel: 'noopener' }, x.text) : x.text)));
  return el('div', { class: 'next' }, el('span', { class: 'nl' }, 'Where to look next:'), ' ', ul);
}

// A re-render removes whatever had focus in the card (a button that switched the source, a link): focus then goes to the
// new card's heading, not to <body> (QA N5).
function renderRec() {
  const box = $('rec'), had = box.contains(document.activeElement);
  drawRec(box);
  if (had && !box.contains(document.activeElement)) { const h = box.querySelector('h2'); if (h) h.focus({ preventScroll: true }); }
}
function drawRec(box) {
  clear(box);
  const pin = selectedPin(curWin), w = winOf(curWin);
  box.setAttribute('aria-busy', String(!!pin && pin.status === 'loading'));
  if (!w) return;
  if (!pin) {
    box.append(el('h2', { tabindex: '-1' }, 'Pin a place to see what its records show'), el('p', { class: 'say' }, 'Search above, or click the map, to pin a place.'));
    return;
  }
  const h2 = (txt) => el('h2', { tabindex: '-1', id: 'rec-h' }, txt);
  if (pin.status === 'loading') {
    const max = usualSecs();
    box.append(h2(pin.label), el('progress', { id: 'rec-prog', max: String(max), value: String(Math.min(secsSince(pin), max - 0.5)), 'aria-label': `Loading ${pin.label}` }), el('p', { class: 'say', id: 'rec-load-text' }, loadingLine(pin)));
    return;
  }
  if (pin.status === 'error') {
    box.append(h2(pin.label), el('p', { class: 'say' }, pin.error || "We couldn't check this place."));
    // "no record here" from a source picked by hand: offer the measurement's default only when the page already holds a
    // working answer for this place from it (a US coast where CO-OPS worked, then PSMSL picked by hand); anything else
    // would be a dead end (QA B7, review)
    const v = varById(curWin), def = v && Array.isArray(v.sources) ? v.sources[0] : null, prev = results[`${curWin}||${pin.key}`];
    const offer = pin.none && sourceFor(curWin) && def && prev && prev.status === 'ok';
    if (offer) {
      const b = el('button', { type: 'button', class: 'btn' }, `Try ${SOURCE_SEG[def] || sourceShort(def)} instead`);
      b.addEventListener('click', () => pickSource(def));
      box.append(el('div', { class: 'acts' }, b));
    }
    if (pin.none && curWin === 'sea_level' && !offer) box.append(el('p', { class: 'say' }, "Without a usable tide gauge nearby, our records can't tell you about this coast."), nextLine([{ text: 'Your local planning office', href: '' }]));
    else box.append(el('p', { class: 'say' }, 'Try another place.'));
    return;
  }

  const t = pin.trend, g = t.guidance || {}, X = window.TDX, C = X.card(t, imperial()), url = X.recordUrl(t.source);
  const meta = el('p', { class: 'meta' }, url ? el('a', { href: url, target: '_blank', rel: 'noopener' }, `${X.srcText(t)} ↗`) : X.srcText(t));
  if (t.latest && t.latest.text) meta.append(' · ', el('span', { class: 'nw' }, t.latest.text)); // never split (QA N4)
  box.append(el('div', { class: 'where' }, h2(pin.label), meta));
  box.append(el('div', { class: 'verdict' }, el('b', {}, el('span', { class: 'shape', 'aria-hidden': 'true' }, C.shape), C.word), el('span', {}, C.conf)));
  if (C.fact) box.append(el('p', { class: 'say' }, C.fact));
  if (C.old) return; // a cached answer from before the rework: the verdict only, until it is asked again
  if (C.world) { // the two rates, then the world figure's source
    const wl = el('p', { class: 'world' }, C.world.text);
    if (C.world.src) wl.append(' World figure: ', C.world.href ? el('a', { href: C.world.href, target: '_blank', rel: 'noopener' }, `${C.world.src}\u00a0↗`) : C.world.src);
    box.append(wl);
  }
  // NASA POWER's grid against the nearest weather station (QA B10): the line, the switch, and after it whether they
  // disagree, from the POWER answer this page already has (the default source's result)
  const v = varById(curWin), prev = results[`${curWin}||${pin.key}`];
  const note = X.modelNote(t, prev && prev.status === 'ok' ? prev.trend : null);
  if (note) {
    const box2 = el('div', { class: note.strong ? 'model strong' : 'model' }, el('p', {}, note.line));
    if (note.offer && v && Array.isArray(v.sources) && v.sources.includes(note.offer)) {
      const b = el('button', { type: 'button', class: 'btn' }, 'Compare with the nearest weather station');
      b.addEventListener('click', () => pickSource(note.offer));
      box2.append(b);
    }
    box.append(box2);
    if (note.next) box.append(el('div', { class: 'model' }, el('p', {}, note.next))); // a plain next step under the strong line
  }
  // R3: the chosen scenario's 2050 projection (web/design/11-sea-level-future.md section 3); without one, why there is none
  const r3 = C.r3f ? el('div', {}, el('p', { class: 'rl' }, C.r3f.label), el('p', { class: 'rv' }, C.r3f.value), el('p', { class: 'rs' }, C.r3f.line))
    : el('div', {}, el('p', { class: 'rl' }, 'What experts project'), el('p', { class: 'rt' }, C.r3));
  const fl = !C.r3f && g.future_link; // with a projection the flood map moves under the chart and into step 7
  if (fl && typeof fl.url === 'string' && fl.url.startsWith('https://') && fl.label) r3.append(el('p', { class: 'rt' }, el('a', { href: fl.url, target: '_blank', rel: 'noopener' }, `${fl.label} ↗`)));
  box.append(el('div', { class: C.r3f ? 'reads sub' : 'reads' }, // sub: the three values share one row (subgrid)
    C.r1 ? el('div', {}, el('p', { class: 'rl' }, C.r1.label), el('p', { class: 'rv' }, C.r1.value), el('p', { class: 'rs' }, C.r1.line)) : '',
    el('div', {}, el('p', { class: 'rl' }, C.r2.label), el('p', { class: 'rv' }, C.r2.value, C.r2.per ? ' ' : '', C.r2.per ? el('small', {}, C.r2.per) : ''), el('p', { class: 'rs' }, C.r2.line)),
    r3));
  if (C.next.length) box.append(nextLine(C.next));
  const how = el('button', { type: 'button', class: 'btn', id: 'how-open' }, 'How we calculated this ↓');
  how.addEventListener('click', goHow);
  box.append(el('div', { class: 'acts' }, how));
  if (C.disc) box.append(el('p', { class: 'disc' }, C.disc));
}
// The button holds no route: it scrolls to the section and puts focus on its heading; it never opens a step.
function goHow() {
  const sec = $('how');
  if (sec.hidden) return;
  sec.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  $('how-h').focus({ preventScroll: true });
}

/* ---------- the place chart and "How we calculated this" (explain.js), for the selected pin ---------- */

let shown = { trend: null, units: null };
const loadStart = () => document.dispatchEvent(new CustomEvent('td:load-start', { detail: { id: 0, params: null, place: null, origin: 'window' } }));
function renderDetail() {
  const pin = curWin === 'settings' ? null : selectedPin(curWin), units = window.TDPrefs.get().units;
  const ctx = pin && { label: pin.label, name: nameOf(curWin), slug: winOf(curWin).slug, imperial: units === 'imperial' };
  if (pin && pin.status === 'ok') {
    if (pin.trend === shown.trend && units === shown.units) return; // another pin landed: nothing here changed
    const fresh = pin.trend !== shown.trend;
    if (fresh && shown.trend) loadStart();
    shown = { trend: pin.trend, units };
    window.TDX.show(pin, ctx, fresh);
    // Real or noise? (in step 5) waits for a finished answer
    if (fresh) document.dispatchEvent(new CustomEvent('td:load-end', { detail: compatDetail(pin) }));
    return;
  }
  if (shown.trend) loadStart();
  shown = { trend: null, units: null };
  window.TDX.show(pin, ctx, true);
}

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
  // with an expert projection on the page, the foot names it too
  const pin = selectedPin(curWin), pj = pin && pin.status === 'ok' ? window.TDX.projOf(pin.trend) : null, ps = pj && pj.source;
  if (ps && typeof ps.record_url === 'string' && ps.record_url.startsWith('https://')) {
    p.append('. Future: ', el('a', { href: ps.record_url, class: 'srclink' }, 'IPCC AR6 sea level projections ↗'), ` (${ps.licence})`);
  }
  p.append(`. Trends: our calculation (Mann-Kendall test with Sen's slope, seasons removed against ${curWin === 'water_storage' ? "the provider's own reference period" : 'the 1995–2014 average'}).`);
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

window.addEventListener('resize', () => window.TDX.redraw());
document.addEventListener('td:scen', renderRec); // a new emissions scenario: the card's "By 2050" follows it
document.addEventListener('td:prefs', () => { if (curWin !== 'settings') { renderControls(); changed(); } });
window.addEventListener('hashchange', route);
document.addEventListener('DOMContentLoaded', init);
