/* Module 01: the map. One map for the page, re-used across the five measurement windows. Fills #map-slot.
   A marker per pinned place, a click on empty map pins that point. Sea level: tide gauges coloured by their own rate; Water
   storage: the GRACE trend blocks (web/design/13-maps.md). The base map is greyed through its style, never a CSS filter. */
(function () {
  'use strict';
  /* PURE START: no DOM; tests/test_map_js.py runs this block in node */
  var MINUS = '−';
  // six steps split at 0 (13-maps.md sections 2, 4, 5): each array drives both the paint and the key under the map
  var SEA = [{ to: -3, tok: '--dv-dn2' }, { to: 0, tok: '--dv-dn1' }, { to: 2, tok: '--dv-up1' }, { to: 4, tok: '--dv-up2' }, { to: 7, tok: '--dv-up3' }, { to: Infinity, tok: '--dv-up4' }];
  var WATER = [{ to: -2, tok: '--dv-dn3' }, { to: -1, tok: '--dv-dn2' }, { to: 0, tok: '--dv-dn1' }, { to: 1, tok: '--dv-up1' }, { to: 2, tok: '--dv-up2' }, { to: Infinity, tok: '--dv-up3' }];
  var VERDICT = { rising: 'Rising', falling: 'Falling', no_clear_change: 'No clear change' };
  var SIG = { 0: 'no_clear_change', 1: 'rising', 2: 'falling' };
  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var INCH = { mm: 1 / 25.4, cm: 1 / 2.54 };
  var ANOTHER = 'the answer at this spot uses another gauge';
  // your places: an ink teardrop, head of radius 7 at (7, 7), tip at (7, 22): the tip is the place (13-maps.md §2a)
  var PIN_D = 'M7 22 L0.81 10.27 A7 7 0 1 1 13.19 10.27 Z';
  var PIN_SVG = '<svg viewBox="0 0 14 22" aria-hidden="true"><path d="' + PIN_D + '"/></svg>';

  function fin(x) { return typeof x === 'number' && isFinite(x); }
  // MapLibre 'step': below the first break the first colour; a value equal to a break takes the class above it
  function stepExpr(stops, input, col) {
    var e = ['step', input, col(stops[0].tok)];
    for (var i = 1; i < stops.length; i++) e.push(stops[i - 1].to, col(stops[i].tok));
    return e;
  }
  // a break as the key prints it: "−3", "0", "+2"; in inches to 2 decimals
  function absText(x, imp, u) { return x === 0 ? '0' : imp ? (Math.abs(x) * INCH[u]).toFixed(2) : String(Math.abs(x)); }
  function breakText(x, imp, u) { return x === 0 ? '0' : (x > 0 ? '+' : MINUS) + absText(x, imp, u); }
  // the key's swatches (tokens, left to right) and its labels at the breaks (position 0 to 1)
  function keyModel(stops, imp, u) {
    var n = stops.length;
    return { swatches: stops.map(function (s) { return s.tok; }),
      breaks: stops.slice(0, -1).map(function (s, i) { return { text: breakText(s.to, imp, u), at: (i + 1) / n, zero: s.to === 0 }; }) };
  }
  function ranges(bs, n) { return bs.map(function (b, i) { return i < bs.length - 1 ? n(b) + ' to ' + n(bs[i + 1]) : n(b) + ' or more'; }).join(', '); }
  // the scale in words (a visually hidden line: the swatches are aria-hidden)
  function seaWords(imp) {
    var n = function (x) { return absText(x, imp, 'mm'); }, u = (imp ? 'in' : 'mm') + ' a year';
    var up = SEA.filter(function (s) { return s.to >= 0 && s.to < Infinity; }).map(function (s) { return s.to; });
    return 'Colours: blue for falling (darker: ' + n(SEA[0].to) + ' ' + u + ' or more), orange to wine for rising, darker for faster: ' + ranges(up, n) + ' ' + u + '. A grey ring means no clear change.';
  }
  function waterWords(imp) {
    var n = function (x) { return absText(x, imp, 'cm'); }, u = (imp ? 'in' : 'cm') + ' of water a year';
    var dn = WATER.filter(function (s) { return s.to <= 0; }).map(function (s) { return -s.to; }).reverse();
    var up = WATER.filter(function (s) { return s.to >= 0 && s.to < Infinity; }).map(function (s) { return s.to; });
    return 'Colours: blue for less water, darker for faster: ' + ranges(dn, n) + ' ' + u + '; orange for more water, darker for faster: ' + ranges(up, n) + ' ' + u + '. A pale grey block means no clear change.';
  }
  // Rates as the answer card prints them, with the card's own rounding (explain.js sig2Text and spanText, the server's
  // headline_rate rule) on the files' unrounded rates a year; in inches converted first, then rounded once, as the card does
  function num(x, imp, u) { return TDX.sig2Text(imp ? x * INCH[u] : x); }
  function rng(lo, hi, imp, u) { var k = imp ? INCH[u] : 1; return TDX.spanText(lo * k, hi * k); }
  // a 95% range with an end at ±327.67 or beyond (a year, in the layer's own unit: the old int16 water file's clamp) says "very
  // wide": only records with an earthquake step reach it (Japan 2011, Chile 2010), gauges and water blocks alike
  function wide(lo, hi) { return lo <= -327.67 || hi >= 327.67; }
  // "which includes no change" only for no clear change, as the card (a clear verdict's end can round to 0)
  function rateLine(v, x, lo, hi, imp, u, per) {
    return VERDICT[v] + ': ' + num(x, imp, u) + ' ' + (imp ? 'in' : u) + ' ' + per + ', 95% range ' + (wide(lo, hi) ? 'very wide' : rng(lo, hi, imp, u)) +
      (v === 'no_clear_change' && lo <= 0 && hi >= 0 ? ', which includes no change' : '') + '.';
  }
  function month(t) { var p = String(t).split('-'); return MONTHS[+p[1] - 1] + ' ' + p[0]; }
  function about(km) { return 'about ' + Math.round(km / 100) * 100 + ' km'; }
  function deg(x, p, n) { return Math.abs(x).toFixed(1) + '° ' + (x >= 0 ? p : n); }
  // the hover label, one string per line (13-maps.md sections 2 and 4)
  function gaugeTip(g, imp) {
    return [g.name, rateLine(g.verdict, g.slope, g.lo, g.hi, imp, 'mm', 'a year'),
      g.start.slice(0, 4) + '–' + g.end.slice(0, 4) + ' · ' + g.years + ' years of records' + (g.years < 30 ? ' (short record)' : '') + ' · ' + (g.network === 'coops' ? 'NOAA CO-OPS' : 'PSMSL'),
      'Click for the full answer.'];
  }
  function blockTip(b, f, imp) {
    return ['Near ' + deg(b.lat, 'N', 'S') + ', ' + deg(b.lon, 'E', 'W'), rateLine(b.v, b.slope, b.lo, b.hi, imp, 'cm', 'of water a year'),
      month(f.start) + ' to ' + month(f.end) + ' · averaged over ' + about(f.footprint_km) + ' · GRACE', 'Click for the full answer.'];
  }
  function title(n) { // an all-capitals station name in Title Case
    n = n.trim();
    return /\p{Ll}/u.test(n) ? n : n.toLowerCase().replace(/(^|[\s\-\/(])(\p{L})/gu, function (m, a, b) { return a + b.toUpperCase(); });
  }
  // The dots: only gauges with a rate (20 years or more). "psmsl" (Measured by: Global gauges): the PSMSL gauges only, plus each
  // skipped "another gauge" PSMSL entry drawn with its psmsl_mode values, the answer a click opens with source=psmsl. With the NOAA
  // gauges those entries stay hidden (their spot is a drawn CO-OPS dot); other skipped entries no click can open, so never drawn.
  function gaugeDots(f, only) {
    var out = [], list = f && Array.isArray(f.gauges) ? f.gauges : [];
    if (only === 'psmsl' && f && Array.isArray(f.skipped)) {
      list = list.concat(f.skipped.filter(function (s) {
        return s && s.network === 'psmsl' && typeof s.why === 'string' && s.why.indexOf(ANOTHER) === 0 && s.psmsl_mode && typeof s.psmsl_mode === 'object';
      }).map(function (s) { return Object.assign({}, s, s.psmsl_mode); }));
    }
    list.forEach(function (g) {
      if (!g || typeof g.name !== 'string' || !g.name.trim() || !fin(g.lat) || !fin(g.lon) || Math.abs(g.lat) > 90 || Math.abs(g.lon) > 180) return;
      if (!fin(g.slope) || !fin(g.lo) || !fin(g.hi) || !(g.years >= 20) || !VERDICT[g.verdict] || !/^\d{4}-\d\d$/.test(g.start) || !/^\d{4}-\d\d$/.test(g.end)) return;
      if ((g.network !== 'coops' && g.network !== 'psmsl') || (only && g.network !== only) || out.length >= 5000) return;
      out.push({ name: title(g.name), network: g.network, lat: g.lat, lon: g.lon, slope: g.slope, lo: g.lo, hi: g.hi, verdict: g.verdict, start: g.start, end: g.end, years: g.years });
    });
    return out;
  }
  // n little-endian integers from base64: bytes (sig), int16 (enc i16le-b64) or int32 (i32le-b64), by the bytes per value; null
  // if the length fits none (the typed array wraps each unsigned value to its signed one)
  function ints(s, n) {
    var bin = atob(s), w = bin.length / n, out = w === 1 ? new Uint8Array(n) : w === 2 ? new Int16Array(n) : w === 4 ? new Int32Array(n) : null;
    for (var i = 0; out && i < n; i++) {
      var v = 0;
      for (var j = w - 1; j >= 0; j--) v = v * 256 + bin.charCodeAt(i * w + j);
      out[i] = v;
    }
    return out;
  }
  // a stored integer to its value with the file's scale: a divide when the scale is 1/an integer (0.01, 0.00001), so 431
  // reads -4.31, not -4.3100000000000005
  function scaler(s) { var q = Math.round(1 / s); return Math.abs(q * s - 1) < 1e-9 ? function (x) { return x / q; } : function (x) { return x * s; }; }
  // grace-trends.json to blocks with a value; null if the file does not read (each field's width comes from its length)
  function graceBlocks(f) {
    if (!f || !(f.n > 0) || !fin(f.scale) || !fin(f.lat_lon_scale) || !/^\d{4}-\d\d$/.test(f.start) || !/^\d{4}-\d\d$/.test(f.end)) return null;
    var a;
    try { a = ['lat', 'lon', 'area', 'slope', 'lo', 'hi', 'sig'].map(function (k) { return ints(f[k], f.n); }); } catch (e) { return null; }
    if (a.some(function (x) { return !x; }) || !(a[6] instanceof Uint8Array)) return null;
    var sv = scaler(f.scale), sl = scaler(f.lat_lon_scale), out = [];
    for (var i = 0; i < f.n; i++) {
      var v = SIG[a[6][i]];
      if (!v || a[3][i] === f.fill || !(a[2][i] > 0)) continue;
      out.push({ lat: sl(a[0][i]), lon: sl(a[1][i]), area: a[2][i], slope: sv(a[3][i]), lo: sv(a[4][i]), hi: sv(a[5][i]), v: v });
    }
    return out.length ? out : null;
  }
  // a block: 1 degree tall, area / (111.32^2 cos lat) degrees wide, both x 1.04 so no hairline seams show
  function blockRing(b) {
    var h = 0.52, w = 0.52 * b.area / (111.32 * 111.32 * Math.cos(b.lat * Math.PI / 180));
    return [[b.lon - w, b.lat - h], [b.lon + w, b.lat - h], [b.lon + w, b.lat + h], [b.lon - w, b.lat + h], [b.lon - w, b.lat - h]];
  }
  // what a click pins: a gauge at its own place, a block at its centre (the spot the file's rate is for), else the clicked point
  function pickSpec(hit, ll) {
    if (hit && hit.g) return { label: hit.g.name, lat: hit.g.lat, lon: hit.g.lon };
    if (hit && hit.b) return { label: 'Pinned spot', lat: hit.b.lat, lon: hit.b.lon };
    return { label: 'Pinned spot', lat: Math.max(-85, Math.min(85, ll.lat)), lon: (((ll.lng + 180) % 360) + 360) % 360 - 180 };
  }
  // where a hover reads (13-maps.md §2a): over a pin at its tip, the place, so a pin never hides the gauge or block under it;
  // else at the pointer. tipOf(el): a pin element's place, or null; project: a place to its point on the map
  function hoverAt(e, tipOf, project) {
    var t = e.originalEvent && e.originalEvent.target, mk = t && t.closest ? t.closest('.map-mk') : null, ll = mk && tipOf(mk);
    return ll ? { point: project(ll), lngLat: ll } : e;
  }
  // box: [west, south, east, north] from the map (west and east may pass 180 with world copies)
  function inBox(b, lat, lon) { var span = b[2] - b[0]; return lat >= b[1] && lat <= b[3] && (span >= 360 || ((lon - b[0]) % 360 + 360) % 360 <= span); }
  function gaugeView(ds, box, imp) {
    var n = 0, c = { rising: 0, falling: 0, no_clear_change: 0 }, top = null;
    ds.forEach(function (g) {
      if (!inBox(box, g.lat, g.lon)) return;
      n++; c[g.verdict]++;
      if (g.verdict === 'rising' && (!top || g.slope > top.slope)) top = g;
    });
    if (!n) return 'No gauges with 20 or more years of records in view. Zoom out or move the map.';
    return 'In view: ' + n + (n === 1 ? ' gauge. ' : ' gauges. ') + c.rising + ' rising, ' + c.falling + ' falling, ' + c.no_clear_change + ' no clear change.' +
      (top ? ' Fastest rise: ' + top.name + ', ' + num(top.slope, imp, 'mm') + ' ' + (imp ? 'in' : 'mm') + ' a year.' : '');
  }
  function blockView(bs, box) {
    var t = 0, w = { rising: 0, falling: 0, no_clear_change: 0 };
    bs.forEach(function (b) { if (inBox(box, b.lat, b.lon)) { t += b.area; w[b.v] += b.area; } });
    if (!t) return 'No blocks with a value in view. Zoom out or move the map.';
    var p = function (k) { return Math.round(100 * w[k] / t) + '%'; };
    return 'In view, by area: ' + p('falling') + ' losing water, ' + p('rising') + ' gaining, ' + p('no_clear_change') + ' no clear change.';
  }

  // ---- the base map in greys (13-maps.md section 1): every paint colour to its luminance grey, alpha kept ----
  function rgba(s) {
    var m = /^#([0-9a-f]{3,8})$/i.exec(s), h, v;
    if (m) {
      h = m[1].length < 5 ? m[1].replace(/./g, '$&$&') : m[1];
      if (h.length !== 6 && h.length !== 8) return null;
      return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), h.length === 8 ? parseInt(h.slice(6), 16) / 255 : 1];
    }
    m = /^(rgb|hsl)a?\(([^)]*)\)$/i.exec(s.trim());
    if (!m) return null;
    v = m[2].split(/[\s,\/]+/).filter(Boolean).map(parseFloat);
    if (v.length < 3 || v.some(isNaN)) return null;
    var a = v.length > 3 ? v[3] : 1;
    if (m[1].toLowerCase() === 'rgb') return [v[0], v[1], v[2], a];
    var hh = (((v[0] % 360) + 360) % 360) / 30, sl = v[1] / 100, l = v[2] / 100, k = sl * Math.min(l, 1 - l);
    var f = function (n) { var q = (n + hh) % 12; return 255 * (l - k * Math.max(-1, Math.min(q - 3, 9 - q, 1))); };
    return [f(0), f(8), f(4), a];
  }
  function lin(c) { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
  // role: fill (fills, lines, background), text, halo
  function greyOf(s, role, dark) {
    var c = typeof s === 'string' && rgba(s);
    if (!c) return s;
    var y = 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
    var g = 255 * (y <= 0.0031308 ? 12.92 * y : 1.055 * Math.pow(y, 1 / 2.4) - 0.055);
    var x = role === 'text' ? (dark ? 40 + (255 - g) * 0.75 : g) : role === 'halo' ? (dark ? 255 - g : g) : (dark ? 16 + (255 - g) * 0.45 : 255 - (255 - g) * 0.6);
    x = Math.round(Math.max(0, Math.min(255, x)));
    return 'rgba(' + x + ',' + x + ',' + x + ',' + c[3] + ')';
  }
  // strings, legacy stops and expressions alike: any string that reads as a colour is greyed, everything else is kept
  function greyAll(v, role, dark) {
    if (Array.isArray(v)) return v.map(function (x) { return greyAll(x, role, dark); });
    if (v && typeof v === 'object') { var o = {}; Object.keys(v).forEach(function (k) { o[k] = greyAll(v[k], role, dark); }); return o; }
    return greyOf(v, role, dark);
  }
  function roleOf(prop) { return /^(text|icon)-halo-color$/.test(prop) ? 'halo' : /^(text|icon)-color$/.test(prop) ? 'text' : 'fill'; }
  // the detailed map's road shields: coloured sprite icons that no paint grey reaches (QA B5), so hidden while greyed
  function isShield(l) { return /shield/.test(l.id); }
  // a fresh style's paint colours as the style gives them, and the layers hidden while greyed: rasters (the relief) and shields
  function recordStyle(st) {
    var r = { orig: [], hide: [] };
    ((st || {}).layers || []).forEach(function (l) {
      if (l.type === 'raster' || isShield(l)) r.hide.push({ id: l.id, sym: l.type === 'symbol' });
      Object.keys(l.paint || {}).forEach(function (p) { if (/-color$/.test(p)) r.orig.push([l.id, p, l.paint[p]]); });
    });
    return r;
  }
  // greys the style (on) or gives its colours back; a shield comes back only with labels on
  function greyStyle(map, r, on, d, labels) {
    r.orig.forEach(function (o) { if (map.getLayer(o[0])) map.setPaintProperty(o[0], o[1], on ? greyAll(o[2], roleOf(o[1]), d) : o[2]); });
    r.hide.forEach(function (x) { if (map.getLayer(x.id)) map.setLayoutProperty(x.id, 'visibility', on || (x.sym && !labels) ? 'none' : 'visible'); });
  }

  // ---- the view (13-maps.md section 8) ----
  function km(a, b) { // great-circle distance in km
    var r = Math.PI / 180, dLat = (b.lat - a.lat) * r, dLon = (b.lon - a.lon) * r;
    var x = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 12742 * Math.asin(Math.min(1, Math.sqrt(x)));
  }
  // room for the selected tag scales with the frame
  function padFor(w, h) {
    if (w < 420) return { top: 30, bottom: 30, left: 30, right: 30 };
    var x = Math.min(40, 0.1 * w), y = Math.min(40, 0.1 * h);
    return { top: y, bottom: y, left: x, right: Math.min(190, 0.3 * w) };
  }
  // The selected pin and every pin within 1,000 km of it (zoom 6 at most); with no neighbour, zoom 5 on it; with no selection, all
  // pins. No move leaves padding behind: fitBounds keeps none, and the lone-pin flyTo shifts by an offset instead (MapLibre keeps
  // a flyTo padding and subtracts it from the next fit). A fit that cannot be made centres on the selected place at zoom 5.
  function moveTo(map, LB, pins, sel, w, h, dur) {
    var pad = padFor(w, h), b = null, max = 9, c = sel;
    if (!sel) {
      b = new LB([pins[0].lon, pins[0].lat], [pins[0].lon, pins[0].lat]);
      pins.forEach(function (p) { b.extend([p.lon, p.lat]); });
    } else {
      var near = pins.filter(function (p) { return p !== sel && km(sel, p) <= 1000; });
      if (near.length) {
        b = new LB([sel.lon, sel.lat], [sel.lon, sel.lat]);
        // shift a neighbour across the antimeridian (by 360) so the box stays tight around the selected pin
        near.forEach(function (p) { b.extend([p.lon - 360 * Math.round((p.lon - sel.lon) / 360), p.lat]); });
        max = 6;
      }
    }
    if (b && map.cameraForBounds(b, { padding: pad, maxZoom: max })) { map.fitBounds(b, { padding: pad, maxZoom: max, duration: dur }); return; }
    if (!c) { var m = b.getCenter(); c = { lon: m.lng, lat: m.lat }; }
    map.flyTo({ center: [c.lon, c.lat], zoom: 5, offset: [(pad.left - pad.right) / 2, (pad.top - pad.bottom) / 2], duration: dur, essential: true });
  }
  /* PURE END */

  var slot = document.getElementById('map-slot');
  if (!slot || !window.TD) return;
  var STYLES = { light: 'https://tiles.openfreemap.org/styles/positron', detailed: 'https://tiles.openfreemap.org/styles/liberty' };
  var map = null, lib = null, loaded = false, styleReady = false, failed = false, retried = false, slowTimer = 0;
  var markers = Object.create(null), fitKey = null, fitSel = null, baseKey = 'light', userMoved = false, rzFrame = 0;
  var files = { gauges: { url: '/data/gauge-trends.json', data: null, tries: 0, loading: false }, water: { url: '/data/grace-trends.json', data: null, tries: 0, loading: false } };
  var dots = [], blocks = [], gMode = null, dotsOn = false, waterOn = false, hideTimer = 0;
  var key = null, keyFor = '', keyKind = null, viewEl = null, tip = null, tipFor = null;
  var rs = { orig: [], hide: [] }, greyKey = 'off';
  var hoverOK = matchMedia('(hover: hover)').matches, HIT = matchMedia('(pointer: coarse)').matches ? 24 : 14;

  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }
  function reduced() { return matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function dark() { return document.documentElement.dataset.theme === 'dark'; }
  function imp() { try { return TDPrefs.get().units === 'imperial'; } catch (e) { return false; } }
  function tok(t) { return getComputedStyle(document.documentElement).getPropertyValue(t).trim(); }
  function win() { return TD.window; }
  function inSettings() { return win() === 'settings'; }
  // the map preferences for the window on screen (defaults: light base map, labels on, stations on)
  function prefs() {
    var m = null;
    try { m = window.TDPrefs && TDPrefs.get().maps && TDPrefs.get().maps[win()]; } catch (e) {}
    m = m || {};
    return { base: m.base === 'detailed' ? 'detailed' : 'light', labels: m.labels !== false, stations: m.stations !== false };
  }
  // the colour layer this window wants: gauge dots (Sea level, "Measuring stations" on) or the water blocks (Water storage)
  function wantKind() {
    if (failed || inSettings()) return null;
    return win() === 'sea_level' ? (prefs().stations ? 'gauges' : null) : win() === 'water_storage' ? 'water' : null;
  }

  var frame = h('div', 'map-frame');
  frame.setAttribute('role', 'group');
  frame.setAttribute('aria-label', 'Map of your pinned places and the trend at each tide gauge (or water-storage block). The lines under the map sum up what is in view.');
  var canvas = h('div', 'map-canvas');
  canvas.id = 'map-canvas';
  var wait = h('p', 'map-wait', 'Loading the map…');
  frame.append(canvas, wait);
  slot.append(frame);
  slot.hidden = false;

  function fail(msg, canRetry) {
    if (failed) return;
    failed = true;
    clearTimeout(slowTimer);
    frame.classList.add('map-failed');
    wait.hidden = false;
    wait.textContent = msg;
    if (key) key.hidden = true;
    if (canRetry && !retried) {
      var b = h('button', 'btn map-retry', 'Try again');
      b.type = 'button';
      b.addEventListener('click', function () { retried = true; start(); });
      wait.append(b);
    }
  }

  // the control opens itself when it is added; start collapsed (just the info button) until the visitor taps it
  function collapseAttrib() {
    var a = canvas.querySelector('.maplibregl-ctrl-attrib');
    if (a) { a.removeAttribute('open'); a.classList.remove('maplibregl-compact-show'); }
  }

  // no WebGL or the library did not import: no retry (a failed module import is cached by the browser)
  function noMap() { fail("Your browser can't show the map. Your places are still listed on the left.", false); }

  // one marker per pin, all alike: a button holding the ink teardrop, its tip on the place (click or Enter selects it); the
  // selected pin is bigger and carries a tag with its name (facts, not advice: no risk level on the map)
  function syncMarkers() {
    if (!map) return;
    var pins = (TD.pins && TD.pins()) || [], seen = Object.create(null);
    pins.forEach(function (p) {
      if (!p || typeof p.lat !== 'number' || typeof p.lon !== 'number') return;
      seen[p.key] = true;
      var label = String(p.label || 'Place'), m = markers[p.key];
      if (!m) {
        var el = h('button', 'map-mk');
        el.type = 'button';
        el.innerHTML = PIN_SVG;
        el.addEventListener('click', function (e) { e.stopPropagation(); if (TD.select) TD.select(p.key); });
        m = markers[p.key] = { el: el, tag: null, mk: new lib.Marker({ element: el, anchor: 'bottom' }).setLngLat([p.lon, p.lat]).addTo(map) };
      } else {
        m.mk.setLngLat([p.lon, p.lat]);
      }
      // classList only: MapLibre put its own classes (maplibregl-marker, the anchor) on this element
      m.el.classList.add('map-mk');
      m.el.classList.toggle('sel', !!p.selected);
      m.el.setAttribute('aria-label', label);
      if (p.selected) {
        if (!m.tag) { m.tag = h('span', 'map-tag'); m.tag.setAttribute('aria-hidden', 'true'); m.el.append(m.tag); }
        m.tag.textContent = label;
      } else if (m.tag) {
        m.tag.remove();
        m.tag = null;
      }
    });
    Object.keys(markers).forEach(function (k) { if (!seen[k]) { markers[k].mk.remove(); delete markers[k]; } });
    placeTags();
  }

  // a tag opens to the right of its marker; in the right 45% of the map it opens to the left so the map's edge never cuts it
  function placeTags() {
    if (!map) return;
    var w = frame.offsetWidth;
    Object.keys(markers).forEach(function (k) {
      var m = markers[k];
      if (!m.tag) return;
      // measure the tag at its widest (220 px, wrapping beyond that), then take the side of the marker with room; if neither side has
      // enough, take the roomier side and narrow the tag to fit. 22 = half the marker + the gap + a 4 px margin at the map's edge.
      m.tag.style.maxWidth = '220px'; // CSSOM: a computed width, not a design value
      var x = map.project(m.mk.getLngLat()).x, tw = m.tag.offsetWidth, rr = w - x - 22, lr = x - 22;
      var left = tw <= rr ? false : tw <= lr ? true : lr > rr;
      m.tag.classList.toggle('left', left);
      m.tag.style.maxWidth = Math.max(80, Math.min(220, left ? lr : rr)) + 'px';
    });
  }

  // Runs on window entry, when the set of pins changes, and when the selection changes (then only if the visitor has not moved the
  // map themselves, or the newly selected pin is outside the view).
  function fit(force) {
    if (!map || inSettings() || !canvas.clientWidth) return;
    var pins = ((TD.pins && TD.pins()) || []).filter(function (p) { return p && typeof p.lat === 'number' && typeof p.lon === 'number'; });
    var k = win() + ':' + pins.map(function (p) { return p.key; }).sort().join('|');
    var sel = pins.filter(function (p) { return p.selected; })[0] || null, selKey = sel ? sel.key : '';
    var setChanged = k !== fitKey, selChanged = selKey !== fitSel;
    if (!force && !setChanged && !selChanged) return;
    fitKey = k;
    fitSel = selKey;
    if (!pins.length) return;
    if (!force && !setChanged && sel && userMoved && map.getBounds().contains([sel.lon, sel.lat])) return;
    userMoved = false;
    moveTo(map, lib.LngLatBounds, pins, sel, canvas.clientWidth, canvas.clientHeight, reduced() ? 0 : 600);
  }

  // base map, labels, the colour layer and the key from the preferences of the window on screen
  function applyPrefs() {
    if (!map || inSettings()) return;
    var p = prefs();
    if (p.base !== baseKey) {
      baseKey = p.base;
      styleReady = false;
      map.setStyle(STYLES[baseKey], { diff: false }); // the style.load handler greys it and re-adds labels and the layers
      return;
    }
    if (loaded) { applyLabels(); sync(); }
  }

  // the road shields stay hidden while the base map is greyed (greyBase shows them again)
  function applyLabels() {
    var on = prefs().labels, st = map.getStyle(), grey = greyKey !== 'off';
    ((st && st.layers) || []).forEach(function (l) {
      if (l.type === 'symbol') map.setLayoutProperty(l.id, 'visibility', on && !(grey && isShield(l)) ? 'visible' : 'none');
    });
  }

  function start() {
    if (map) { map.remove(); map = null; tip = null; tipFor = null; markers = Object.create(null); }
    failed = false; loaded = false; styleReady = false; fitKey = null; fitSel = null;
    frame.classList.remove('map-failed');
    wait.hidden = false;
    wait.textContent = 'Loading the map…';
    clearTimeout(slowTimer);
    slowTimer = setTimeout(function () {
      if (!loaded && !failed) wait.textContent = 'Loading the map… Still loading. The map is optional.';
    }, 8000);
    baseKey = prefs().base;
    import('./vendor/maplibre-gl/maplibre-gl.mjs').then(function (m) {
      lib = m;
      try {
        map = new lib.Map({
          container: canvas, style: STYLES[baseKey], center: [15, 28], zoom: 1.1,
          minZoom: 0.3, maxZoom: 11, renderWorldCopies: true, attributionControl: false,
          cooperativeGestures: true, doubleClickZoom: false, dragRotate: false, touchPitch: false, pitchWithRotate: false,
          fadeDuration: reduced() ? 0 : 300,
          locale: {
            'CooperativeGesturesHandler.MobileHelpText': 'Use two fingers to move the map',
            'CooperativeGesturesHandler.WindowsHelpText': 'Hold Ctrl and scroll to move the map',
            'CooperativeGesturesHandler.MacHelpText': 'Hold ⌘ and scroll to move the map'
          }
        });
      } catch (e) {
        map = null;
        noMap();
        return;
      }
      var cv = map.getCanvas();
      cv.tabIndex = -1;
      cv.setAttribute('aria-hidden', 'true');
      // the style carries the base-map credit itself; the compact control also shows the gauge credits
      map.addControl(new lib.AttributionControl({ compact: true }), 'bottom-right');
      collapseAttrib();
      map.on('resize', collapseAttrib);
      map.addControl(new lib.NavigationControl({ showCompass: false, visualizePitch: false }), 'top-right');
      map.touchZoomRotate.disableRotation();
      function afterStyle() { styleReady = true; collapseAttrib(); record(); applyLabels(); sync(); }
      map.on('style.load', function () { if (loaded) afterStyle(); });
      map.on('load', function () {
        loaded = true;
        failed = false;
        clearTimeout(slowTimer);
        frame.classList.remove('map-failed');
        wait.hidden = true;
        map.resize();
        applyPrefs();
        afterStyle();
        fit(true);
      });
      // errors after load (a missed tile on a slow line) are ignored on purpose
      map.on('error', function () { if (!loaded) fail("The map couldn't load. Your places are still listed on the left.", true); });
      map.on('mousemove', function (e) {
        if (!hoverOK) return;
        var hit = hitAt(hoverAt(e, tipOf, function (ll) { return map.project(ll); }), false), d = hit && (hit.g || hit.b);
        if (d && d === tipFor) return;
        if (!d) { tipOff(); return; }
        tipFor = d;
        map.getCanvas().style.cursor = 'pointer';
        var box = h('div');
        (hit.g ? gaugeTip(hit.g, imp()) : blockTip(hit.b, files.water.data, imp())).forEach(function (t, i) { box.append(h(i ? 'span' : 'b', i > 1 ? 'g' : '', t)); });
        if (!tip) tip = new lib.Popup({ className: 'map-tip', closeButton: false, closeOnClick: false, offset: 10, focusAfterOpen: false });
        tip.setDOMContent(box).setLngLat([hit.lng, d.lat]).addTo(map);
        tip.getElement().setAttribute('aria-hidden', 'true');
      });
      map.on('moveend', function () { placeTags(); updateView(); });
      map.on('mouseout', tipOff);
      // the visitor moved or zoomed the map (events with an original event): do not refit over it on a resize
      ['dragstart', 'zoomstart'].forEach(function (n) { map.on(n, function (e) { if (e && e.originalEvent) userMoved = true; }); });
      map.on('zoom', function () { if (map.getZoom() < 2) tipOff(); });
      // a click on empty map pins that point, the gauge or the block under it; markers stop their own clicks
      map.on('click', function (e) {
        if (!TD.addPlace) return;
        var s = pickSpec(hitAt(e, true), e.lngLat);
        if (s.label !== 'Pinned spot') s.label = (TD.cleanPlace && TD.cleanPlace(s.label)) || 'Tide gauge';
        Promise.resolve(TD.addPlace(s)).then(function (r) {
          if (r && r.ok === false && r.reason === 'full' && TD.announce) TD.announce('You can pin up to 6 places. Remove one first.');
        }).catch(function () {});
      });
      syncMarkers();
    }).catch(noMap);
  }

  // ---- the greyed base map ----
  function record() { rs = recordStyle(map.getStyle()); greyKey = 'off'; }
  function greyBase(on) {
    var d = dark(), k = on ? (d ? 'dark' : 'light') : 'off';
    if (k === greyKey) return;
    greyKey = k;
    greyStyle(map, rs, on, d, prefs().labels);
  }

  // ---- the two data files: read once, the first time their window is wanted; one more try at the next switch ----
  function fetchWanted() { var k = wantKind(); if (k) fetchFile(k); }
  function fetchFile(k) {
    var f = files[k];
    if (f.data || f.loading || f.tries >= 2) return;
    f.tries++;
    f.loading = true;
    var ctl = new AbortController();
    var timer = setTimeout(function () { ctl.abort(); }, 30000);
    fetch(f.url, { signal: ctl.signal })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (body) {
        if (k === 'gauges') { if (gaugeDots(body, '').length) f.data = body; return; }
        var bs = graceBlocks(body);
        if (bs) { blocks = bs; f.data = body; }
      })
      .catch(function () {})
      .then(function () { clearTimeout(timer); f.loading = false; sync(); });
  }

  // draws, shows or hides the window's colour layer, greys the base map under it and builds the key; runs when the map, a style or
  // a file arrives, on a window switch, and when the preferences, the theme or the "Measured by" source change
  function sync() {
    if (!map || !loaded || !styleReady) { if (!wantKind() && key) key.hidden = true; return; }
    var kind = wantKind(), g = kind === 'gauges' && !!files.gauges.data, w = kind === 'water' && !!files.water.data;
    if (g) drawGauges();
    fadeDots(g);
    if (w) drawWater();
    if (map.getLayer('grace-blocks') && w !== waterOn) {
      waterOn = w;
      ['grace-blocks', 'grace-water'].forEach(function (id) { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', w ? 'visible' : 'none'); });
      if (!w) tipOff();
    }
    greyBase(baseKey === 'light' || g || w);
    showKey(g ? 'gauges' : w ? 'water' : null);
  }

  function paintLayers() {
    if (map.getLayer('gauges-dots')) {
      map.setPaintProperty('gauges-dots', 'circle-color', ['case', ['get', 'nc'], 'rgba(0,0,0,0)', stepExpr(SEA, ['get', 's'], tok)]);
      map.setPaintProperty('gauges-dots', 'circle-stroke-color', ['case', ['get', 'nc'], tok('--dv-nc'), tok('--dv-ring')]);
    }
    if (map.getLayer('grace-blocks')) map.setPaintProperty('grace-blocks', 'fill-color', ['case', ['get', 'nc'], tok('--dv-ncfill'), stepExpr(WATER, ['get', 's'], tok)]);
  }

  // display only: the jargon ", RLR monthly means" is dropped from the credit name (the link is unchanged)
  function srcName(x) { return x.name.replace(/,\s*RLR monthly means\s*$/, ''); }
  function isHttps(u) { return typeof u === 'string' && u.indexOf('https://') === 0; }
  function esc(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
  // the file's source for a network ({name, url}), or null
  function gSource(net) {
    var re = net === 'coops' ? /CO-OPS/ : /PSMSL/;
    return (Array.isArray(files.gauges.data.source) ? files.gauges.data.source : []).filter(function (x) { return x && typeof x.name === 'string' && re.test(x.name); })[0] || null;
  }

  // one circle layer above the base map's labels: fill by rate in six steps, a grey hollow ring for no clear change, short
  // records smaller, rings first and then the larger rates on top. Rebuilt when "Measured by" switches between the gauge lists.
  function drawGauges() {
    var mode = TD.state && TD.state.source === 'psmsl' ? 'psmsl' : '';
    if (map.getSource('gauges') && mode === gMode) return;
    tipOff();
    if (map.getLayer('gauges-dots')) map.removeLayer('gauges-dots');
    if (map.getSource('gauges')) map.removeSource('gauges');
    gMode = mode;
    dots = gaugeDots(files.gauges.data, mode);
    var nets = {}, feats = dots.map(function (g, i) {
      var nc = g.verdict === 'no_clear_change';
      nets[g.network] = true;
      return { type: 'Feature', properties: { i: i, s: g.slope, nc: nc, sh: g.years < 30, k: nc ? -1 : Math.abs(g.slope) }, geometry: { type: 'Point', coordinates: [g.lon, g.lat] } };
    });
    // the credits: "Gauge records: {source}" for each list with a dot, in the control and the footer
    var srcs = ['coops', 'psmsl'].filter(function (n) { return nets[n] && gSource(n); }).map(function (n) { return { id: n, s: gSource(n) }; });
    var attrib = srcs.map(function (x) {
      var t = esc('Gauge records: ' + srcName(x.s));
      return '<div>' + (isHttps(x.s.url) ? '<a href="' + esc(x.s.url) + '" target="_blank" rel="noopener">' + t + '</a>' : t) + '</div>';
    }).join(' ');
    srcs.forEach(function (x) { if (TD.addCredit) TD.addCredit('gauges-' + x.id, 'Gauge records: ' + srcName(x.s), isHttps(x.s.url) ? x.s.url : undefined); });
    map.addSource('gauges', { type: 'geojson', attribution: attrib, data: { type: 'FeatureCollection', features: feats } });
    // radius by zoom; a short record x 0.6; a ring 1 px smaller, so with its 2 px line its outer edge matches a dot's
    var r = function (x) { return ['-', ['*', x, ['case', ['get', 'sh'], 0.6, 1]], ['case', ['get', 'nc'], 1, 0]]; };
    map.addLayer({ id: 'gauges-dots', type: 'circle', source: 'gauges', layout: { visibility: 'none', 'circle-sort-key': ['get', 'k'] },
      paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 1, r(2.5), 3, r(3.5), 5, r(5), 8, r(6.5), 11, r(7)],
        'circle-stroke-width': ['case', ['get', 'nc'], 2, 1], 'circle-opacity': 0, 'circle-stroke-opacity': 0 } });
    paintLayers();
    dotsOn = false;
    keyFor = '';
    collapseAttrib();
  }

  // fade in and out 200 ms (0 under reduced motion)
  function fadeDots(show) {
    if (!map.getLayer('gauges-dots') || show === dotsOn) return;
    dotsOn = show;
    clearTimeout(hideTimer);
    var d = { duration: reduced() ? 0 : 200 };
    map.setPaintProperty('gauges-dots', 'circle-opacity-transition', d);
    map.setPaintProperty('gauges-dots', 'circle-stroke-opacity-transition', d);
    if (show) map.setLayoutProperty('gauges-dots', 'visibility', 'visible');
    else hideTimer = setTimeout(function () { if (map && map.getLayer('gauges-dots') && !dotsOn) map.setLayoutProperty('gauges-dots', 'visibility', 'none'); }, d.duration);
    map.setPaintProperty('gauges-dots', 'circle-opacity', show ? 1 : 0);
    map.setPaintProperty('gauges-dots', 'circle-stroke-opacity', show ? 1 : 0);
    if (!show) tipOff();
  }

  // one fill layer of blocks below the base map's boundaries and labels, with a copy of its water layer above, so coasts cut them
  function drawWater() {
    if (map.getSource('grace')) return;
    var layers = map.getStyle().layers, before, wl = null;
    layers.forEach(function (l) {
      if (!before && (l.type === 'symbol' || l['source-layer'] === 'boundary')) before = l.id;
      if (!wl && l.type === 'fill' && l['source-layer'] === 'water') wl = l;
    });
    var feats = blocks.map(function (b, i) { return { type: 'Feature', properties: { i: i, s: b.slope, nc: b.v === 'no_clear_change' }, geometry: { type: 'Polygon', coordinates: [blockRing(b)] } }; });
    map.addSource('grace', { type: 'geojson', data: { type: 'FeatureCollection', features: feats } });
    map.addLayer({ id: 'grace-blocks', type: 'fill', source: 'grace', layout: { visibility: 'none' }, paint: {} }, before);
    if (wl) {
      var cp = { id: 'grace-water', type: 'fill', source: wl.source, 'source-layer': wl['source-layer'], layout: { visibility: 'none' }, paint: { 'fill-color': wl.paint['fill-color'] } };
      ['filter', 'minzoom', 'maxzoom'].forEach(function (k) { if (wl[k] !== undefined) cp[k] = wl[k]; });
      map.addLayer(cp, before);
      var o = rs.orig.filter(function (x) { return x[0] === wl.id && x[1] === 'fill-color'; })[0];
      if (o) { rs.orig.push(['grace-water', 'fill-color', o[2]]); greyKey = ''; } // grey the copy as its original
    }
    paintLayers();
    waterOn = false;
  }

  // a pin element's place (its marker's position), or null
  function tipOf(el) { for (var k in markers) if (markers[k].el === el) return markers[k].mk.getLngLat(); return null; }
  function tipOff() {
    tipFor = null;
    if (tip) tip.remove();
    if (map) map.getCanvas().style.cursor = '';
  }

  // what is under the pointer: { g: dot } within 14 px (24 on touch) from zoom 2, or { b: block } (hover from zoom 2, a click at
  // any zoom; never where the water copy covers it); lng is the longitude in the world copy shown
  function hitAt(e, click) {
    var z = map.getZoom(), pt = e.point;
    if (dotsOn && map.getLayer('gauges-dots') && z >= 2) {
      var best = null, bd = Infinity;
      map.queryRenderedFeatures([[pt.x - HIT, pt.y - HIT], [pt.x + HIT, pt.y + HIT]], { layers: ['gauges-dots'] }).forEach(function (f) {
        var g = dots[f.properties.i];
        if (!g) return;
        var lng = g.lon + 360 * Math.round((e.lngLat.lng - g.lon) / 360), p = map.project([lng, g.lat]), d = Math.hypot(p.x - pt.x, p.y - pt.y);
        if (d <= HIT && d < bd) { bd = d; best = { g: g, lng: lng }; }
      });
      return best;
    }
    if (waterOn && map.getLayer('grace-blocks') && (click || z >= 2)) {
      var ids = map.getLayer('grace-water') ? ['grace-water', 'grace-blocks'] : ['grace-blocks'];
      var top = map.queryRenderedFeatures(pt, { layers: ids })[0], b = top && top.layer.id === 'grace-blocks' && blocks[top.properties.i];
      return b ? { b: b, lng: b.lon + 360 * Math.round((e.lngLat.lng - b.lon) / 360) } : null;
    }
    return null;
  }

  // ---- the key under the map (13-maps.md sections 3 and 4): real text; the swatches are aria-hidden ----
  function svg(kind) {
    var ns = 'http://www.w3.org/2000/svg', s = document.createElementNS(ns, 'svg'), c, pin = kind === 'pin';
    s.setAttribute('width', pin ? '11' : '14'); s.setAttribute('height', pin ? '17' : '14'); s.setAttribute('viewBox', pin ? '0 0 14 22' : '0 0 14 14'); s.setAttribute('aria-hidden', 'true');
    if (kind === 'pale') { c = document.createElementNS(ns, 'rect'); c.setAttribute('width', '14'); c.setAttribute('height', '14'); }
    else if (pin) { c = document.createElementNS(ns, 'path'); c.setAttribute('d', PIN_D); }
    else { c = document.createElementNS(ns, 'circle'); c.setAttribute('cx', '7'); c.setAttribute('cy', '7'); c.setAttribute('r', kind === 'ring' ? '5' : '3'); }
    c.setAttribute('class', 'mk-' + kind);
    s.append(c);
    return s;
  }
  function scaleEl(stops, im, u, lo, hi) {
    var m = keyModel(stops, im, u), box = h('div', 'mk-scale'), sw = h('div', 'mk-sw'), br = h('div', 'mk-br'), ends = h('div', 'mk-ends');
    box.setAttribute('aria-hidden', 'true');
    m.swatches.forEach(function (t) { var i = h('i'); i.style.background = 'var(' + t + ')'; sw.append(i); });
    m.breaks.forEach(function (b) { var s = h('span', b.zero ? 'z' : '', b.text); s.style.left = 100 * b.at + '%'; br.append(s); });
    ends.append(h('span', '', lo), h('span', '', (im ? 'in' : u) + ' a year'), h('span', '', hi));
    box.append(sw, br, ends);
    return box;
  }
  function link(src, text) {
    if (!src || !isHttps(src.url)) return document.createTextNode(text);
    var a = h('a', '', text);
    a.href = src.url; a.target = '_blank'; a.rel = 'noopener';
    return a;
  }
  function showKey(kind) {
    if (!key) { key = h('div', 'map-key'); slot.append(key); }
    key.hidden = !kind;
    var im = imp(), id = kind ? [kind, im, gMode, dots.length].join('|') : '';
    if (id === keyFor) return;
    keyFor = id;
    keyKind = kind;
    key.textContent = '';
    if (!kind) return;
    var p = function (cls, text) { var e = h('p', cls, text); key.append(e); return e; };
    var sym = function (kinds) { var e = p('mk-sym'); kinds.forEach(function (x) { var s = h('span'); s.append(svg(x[0]), x[1]); e.append(s); }); };
    if (kind === 'gauges') {
      p('mk-t', 'How fast the sea is rising or falling at each tide gauge, relative to the land');
      key.append(scaleEl(SEA, im, 'mm', 'Falling', 'Rising'));
      p('sr-only', seaWords(im));
      sym([['ring', 'No clear change'], ['dot', 'Smaller dot: short record, 20 to 29 years'], ['pin', 'Your places']]);
      p('', hoverOK ? 'Point at a dot to read its rate. Click it to open that gauge’s answer.' : 'Tap a dot to open that gauge’s answer.');
      viewEl = p('mk-view');
      var last = dots.reduce(function (a, g) { return g.end > a ? g.end : a; }, '0000-01'), s = p('');
      s.append('Rates: our calculation from ');
      if (!gMode) s.append(link(gSource('coops'), 'NOAA CO-OPS'), ' and ');
      s.append(link(gSource('psmsl'), 'PSMSL'), " records, each gauge's whole record, so the years differ. Relative to the land: where the land sinks, the sea rises faster. Gauges with under 20 years are not shown." + (dots.length ? ' Records to ' + month(last) + '.' : ''));
    } else {
      var f = files.water.data, ref = f.reference && Array.isArray(f.reference.years) ? f.reference.years : null;
      p('mk-t', 'Change in water stored on land, in ' + (im ? 'inches' : 'cm') + ' of water a year');
      key.append(scaleEl(WATER, im, 'cm', 'Less water', 'More water'));
      p('sr-only', waterWords(im));
      sym([['pale', 'No clear change'], ['pin', 'Your places']]);
      p('', hoverOK ? 'Point at a block to read it. Click it to open the answer for that spot.' : 'Tap a block to open the answer for that spot.');
      viewEl = p('mk-view');
      p('', "Each block is the satellites' average over " + about(f.footprint_km) + ": read regions, not towns. A block's rate is for its centre; a town's own answer can differ a little. A pale block is not proof of no change, and even with no real change anywhere, about 1 block in 20 would look clear by chance.");
      var r = p('');
      r.append('Rates: our calculation from ', link({ url: f.source_url }, 'NASA GSFC GRACE and GRACE-FO mascons'), ', ' + month(f.start) + ' to ' + month(f.end) + '.' +
        (ref ? " Levels on this tab are compared with the provider's " + ref[0] + '–' + ref[1] + ' average.' : '') + ' Greenland, Antarctica and the Gulf of Alaska glaciers are left out.');
    }
    updateView();
  }
  // the text summary of what is in view, on moveend (not announced)
  function updateView() {
    if (!map || !keyKind || !viewEl || !key || key.hidden) return;
    var b = map.getBounds(), box = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
    viewEl.textContent = keyKind === 'gauges' ? gaugeView(dots, box, imp()) : blockView(blocks, box);
  }

  // a measurement window came on screen (the map was laid out at zero size while it was hidden)
  function route() {
    if (inSettings()) return;
    syncMarkers();
    fetchWanted();
    applyPrefs();
    if (map) requestAnimationFrame(function () { if (map) { map.resize(); fit(true); } });
  }

  document.addEventListener('td:route', route);
  document.addEventListener('td:prefs', function () { tipOff(); fetchWanted(); applyPrefs(); });
  // the pins changed, or "Measured by" switched between the gauge lists (sync redraws the dots for the list a click would open)
  document.addEventListener('td:pins', function () { if (inSettings()) return; syncMarkers(); fit(false); if (map && loaded) sync(); });
  if (TD.ready) TD.ready.then(function () { if (!inSettings()) fetchWanted(); });
  // a theme change: the base map greys again and the layers read their tokens again (the key's swatches follow by themselves)
  new MutationObserver(function () { if (map && loaded && styleReady) { tipOff(); sync(); paintLayers(); } })
    .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  // the slot can change size after the map is made (the row grows when the card fills in): keep the canvas, and so the DOM markers, in step
  if (window.ResizeObserver) {
    new ResizeObserver(function () {
      if (rzFrame) return;
      rzFrame = requestAnimationFrame(function () {
        rzFrame = 0;
        if (!map || !loaded || inSettings() || !frame.offsetWidth) return;
        map.resize();
        if (!userMoved) fit(true);
      });
    }).observe(frame);
  }

  var io = null;
  if ('IntersectionObserver' in window) {
    io = new IntersectionObserver(function (es) {
      if (es[0].isIntersecting) { io.disconnect(); start(); }
    }, { rootMargin: '300px' });
    io.observe(slot);
  } else {
    start();
  }
})();
