/* Module 01: the map. One map for the page, re-used across the five measurement windows. Fills #map-slot.
   A marker per pinned place (risk in words and colour), a click on empty map pins that point, tide gauge dots on Sea level. */
(function () {
  'use strict';
  var slot = document.getElementById('map-slot');
  if (!slot || !window.TD) return;
  var STYLES = { light: 'https://tiles.openfreemap.org/styles/positron', detailed: 'https://tiles.openfreemap.org/styles/liberty' };
  var map = null, lib = null, loaded = false, failed = false, retried = false, slowTimer = 0;
  var markers = Object.create(null), fitKey = null, baseKey = 'light', userMoved = false, rzFrame = 0;
  var gauges = null, gaugeSrcs = [], gTries = 0, gLoading = false, wantDots = false, hideTimer = 0;
  var legend = null, tip = null, tipFor = null;
  var hoverOK = matchMedia('(hover: hover)').matches;
  var OP = ['step', ['zoom'], 0.65, 4, 0.9];

  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }
  function reduced() { return matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function win() { return TD.window; }
  function inSettings() { return win() === 'settings'; }
  // the map preferences for the window on screen (defaults: light base map, labels on, stations on)
  function prefs() {
    var m = null;
    try { m = window.TDPrefs && TDPrefs.get().maps && TDPrefs.get().maps[win()]; } catch (e) {}
    m = m || {};
    return { base: m.base === 'detailed' ? 'detailed' : 'light', labels: m.labels !== false, stations: m.stations !== false };
  }

  var frame = h('div', 'map-frame');
  frame.setAttribute('role', 'group');
  frame.setAttribute('aria-label', 'Map of your pinned places');
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

  function riskOf(p) {
    var g = p.trend && p.trend.guidance;
    if (!g || typeof g !== 'object') return { cls: 'low', label: '' };
    return { cls: g.risk === 'high' ? 'high' : g.risk === 'moderate' ? 'moderate' : 'low', label: typeof g.risk_label === 'string' ? g.risk_label : '' };
  }

  // one marker per pin: a button (click or Enter selects it); the selected pin is bigger and carries a tag. Risk is in words, never colour alone.
  function syncMarkers() {
    if (!map) return;
    var pins = (TD.pins && TD.pins()) || [], seen = Object.create(null);
    pins.forEach(function (p) {
      if (!p || typeof p.lat !== 'number' || typeof p.lon !== 'number') return;
      seen[p.key] = true;
      var r = riskOf(p), label = String(p.label || 'Place'), m = markers[p.key];
      if (!m) {
        var el = h('button', 'map-mk');
        el.type = 'button';
        el.addEventListener('click', function (e) { e.stopPropagation(); if (TD.select) TD.select(p.key); });
        m = markers[p.key] = { el: el, tag: null, mk: new lib.Marker({ element: el }).setLngLat([p.lon, p.lat]).addTo(map) };
      } else {
        m.mk.setLngLat([p.lon, p.lat]);
      }
      m.el.className = 'map-mk ' + r.cls + (p.selected ? ' sel' : '');
      m.el.setAttribute('aria-label', r.label ? label + ', ' + r.label : label);
      if (p.selected) {
        if (!m.tag) { m.tag = h('span', 'map-tag'); m.tag.setAttribute('aria-hidden', 'true'); m.el.append(m.tag); }
        m.tag.textContent = r.label ? label + ' · ' + r.label : label;
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
      if (m.tag) m.tag.classList.toggle('left', map.project(m.mk.getLngLat()).x > w * 0.55);
    });
  }

  // fit to all pins; not on a mere selection change (the key is the set of pins)
  function fit(force) {
    if (!map || inSettings() || !frame.offsetWidth) return;
    var pins = ((TD.pins && TD.pins()) || []).filter(function (p) { return p && typeof p.lat === 'number' && typeof p.lon === 'number'; });
    var key = win() + ':' + pins.map(function (p) { return p.key; }).sort().join('|');
    if (!force && key === fitKey) return;
    fitKey = key;
    userMoved = false;
    if (!pins.length) return;
    var b = new lib.LngLatBounds([pins[0].lon, pins[0].lat], [pins[0].lon, pins[0].lat]);
    pins.forEach(function (p) { b.extend([p.lon, p.lat]); });
    var pad = frame.offsetWidth < 420 ? 30 : { top: 40, bottom: 40, left: 40, right: 190 }; // room on the right for the selected tag
    map.fitBounds(b, { padding: pad, maxZoom: 9, duration: reduced() ? 0 : 600 });
  }

  // base map, labels and stations from the preferences of the window on screen
  function applyPrefs() {
    if (!map || inSettings()) return;
    var p = prefs();
    frame.classList.toggle('map-detailed', p.base === 'detailed');
    if (p.base !== baseKey) {
      baseKey = p.base;
      map.setStyle(STYLES[baseKey], { diff: false }); // the style.load handler re-adds labels and the gauge layer
      return;
    }
    if (loaded) { applyLabels(); setWant(win() === 'sea_level' && p.stations); }
  }

  function applyLabels() {
    var on = prefs().labels, st = map.getStyle();
    ((st && st.layers) || []).forEach(function (l) {
      if (l.type === 'symbol') map.setLayoutProperty(l.id, 'visibility', on ? 'visible' : 'none');
    });
  }

  function start() {
    if (map) { map.remove(); map = null; tip = null; tipFor = null; markers = Object.create(null); }
    failed = false; loaded = false; fitKey = null;
    frame.classList.remove('map-failed');
    wait.hidden = false;
    wait.textContent = 'Loading the map…';
    clearTimeout(slowTimer);
    slowTimer = setTimeout(function () {
      if (!loaded && !failed) wait.textContent = 'Loading the map… Still loading. The map is optional.';
    }, 8000);
    baseKey = prefs().base;
    frame.classList.toggle('map-detailed', baseKey === 'detailed');
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
      function afterStyle() { collapseAttrib(); applyLabels(); setWant(!inSettings() && win() === 'sea_level' && prefs().stations); applyDots(); }
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
        var hit = nearest(e);
        if (hit && hit.g === tipFor) return;
        if (!hit) { tipOff(); return; }
        tipFor = hit.g;
        map.getCanvas().style.cursor = 'pointer';
        var t = h('span', '', hit.g.name);
        if (!tip) tip = new lib.Popup({ className: 'map-tip', closeButton: false, closeOnClick: false, offset: 10, focusAfterOpen: false });
        tip.setDOMContent(t).setLngLat([hit.lng, hit.g.lat]).addTo(map);
        tip.getElement().setAttribute('aria-hidden', 'true');
      });
      map.on('moveend', placeTags);
      map.on('mouseout', tipOff);
      // the visitor moved or zoomed the map (events with an original event): do not refit over it on a resize
      ['dragstart', 'zoomstart'].forEach(function (n) { map.on(n, function (e) { if (e && e.originalEvent) userMoved = true; }); });
      map.on('zoom', function () { if (map.getZoom() < 4) tipOff(); });
      // a click on empty map pins that point (or the gauge under it); markers stop their own clicks
      map.on('click', function (e) {
        if (!TD.addPlace) return;
        var hit = nearest(e), lat, lon, label;
        if (hit) {
          lat = hit.g.lat; lon = hit.g.lon;
          label = (TD.cleanPlace && TD.cleanPlace(hit.g.name)) || 'Tide gauge';
        } else {
          lat = Math.max(-85, Math.min(85, e.lngLat.lat));
          lon = (((e.lngLat.lng + 180) % 360) + 360) % 360 - 180;
          label = 'Pinned spot';
        }
        Promise.resolve(TD.addPlace({ label: label, lat: lat, lon: lon })).then(function (r) {
          if (r && r.ok === false && r.reason === 'full' && TD.announce) TD.announce('You can pin up to 6 places. Remove one first.');
        }).catch(function () {});
      });
      syncMarkers();
    }).catch(noMap);
  }

  // ---- tide gauge dots (web/design/07-gauges.md); Sea level only, and only with "Measuring stations" on ----
  function setWant(on) {
    if (on === wantDots) return;
    wantDots = on;
    maybeFetch();
    applyDots();
  }

  // not when the map failed (rows that can never be drawn); a map that has not started or loaded yet is fine
  function maybeFetch() {
    if (wantDots && !gauges && !gLoading && gTries < 2 && !failed) fetchGauges();
  }

  function tipOff() {
    tipFor = null;
    if (tip) tip.remove();
    if (map) map.getCanvas().style.cursor = '';
  }

  function fetchGauges() {
    gTries++;
    gLoading = true;
    var ctl = new AbortController();
    var timer = setTimeout(function () { ctl.abort(); }, 30000);
    fetch('/api/gauges', { signal: ctl.signal })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (body) {
        var seen = Object.create(null), list = [], ids = Object.create(null);
        (Array.isArray(body.gauges) ? body.gauges : []).forEach(function (g) {
          if (!g || typeof g.name !== 'string' || !g.name.trim() || typeof g.lat !== 'number' || typeof g.lon !== 'number') return;
          if (!isFinite(g.lat) || !isFinite(g.lon) || Math.abs(g.lat) > 90 || Math.abs(g.lon) > 180) return;
          var k = g.lat.toFixed(3) + ',' + g.lon.toFixed(3);
          if (seen[k]) { ids[g.source] = true; return; }
          if (list.length >= 5000) return;
          seen[k] = true;
          ids[g.source] = true;
          var n = g.name.trim();
          if (!/\p{Ll}/u.test(n)) n = n.toLowerCase().replace(/(^|[\s\-\/(])(\p{L})/gu, function (m, a, b) { return a + b.toUpperCase(); });
          list.push({ name: n, lat: g.lat, lon: g.lon });
        });
        if (!list.length) return;
        gaugeSrcs = (Array.isArray(body.sources) ? body.sources : []).filter(function (x) {
          return x && ids[x.id] && typeof x.name === 'string' && x.name.trim() && typeof x.id === 'string';
        });
        gauges = list;
      })
      .catch(function () {})
      .then(function () { clearTimeout(timer); gLoading = false; applyDots(); });
  }

  // display only: the jargon ", RLR monthly means" is dropped from the credit name (the link and the route are unchanged)
  function creditName(x) { return 'Gauge locations: ' + x.name.replace(/,\s*RLR monthly means\s*$/, ''); }
  function isHttps(u) { return typeof u === 'string' && u.indexOf('https://') === 0; }
  function esc(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }

  // the gauges source's own attribution (HTML, built only from escaped text and https addresses): the control shows it while the layer is shown
  function gaugeAttribution() {
    return gaugeSrcs.map(function (x) {
      var text = esc(creditName(x));
      // each credit in its own block (div is allowed by the control's sanitizer)
      return '<div>' + (isHttps(x.url) ? '<a href="' + esc(x.url) + '" target="_blank" rel="noopener">' + text + '</a>' : text) + '</div>';
    }).join(' ');
  }

  function buildLegend() {
    legend = h('p', 'map-legend');
    legend.setAttribute('aria-hidden', 'true');
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('width', '10');
    svg.setAttribute('height', '10');
    svg.setAttribute('viewBox', '0 0 10 10');
    svg.setAttribute('aria-hidden', 'true');
    var c = document.createElementNS(ns, 'circle');
    c.setAttribute('cx', '5'); c.setAttribute('cy', '5'); c.setAttribute('r', '4');
    svg.append(c);
    legend.append(svg, document.createTextNode('Dots are tide gauges. Zoom in and click one to pin it.'));
    slot.append(legend);
    gaugeSrcs.forEach(function (x) {
      if (TD.addCredit) TD.addCredit('gauges-' + x.id, creditName(x), isHttps(x.url) ? x.url : undefined);
    });
  }

  // draws, shows or fades out the dots; runs when the map or the list arrives, after a style change, and when the preferences change
  function applyDots() {
    if (!map || !loaded || !gauges) return;
    var show = wantDots;
    if (!map.getSource('gauges')) {
      var feats = gauges.map(function (g, i) { return { type: 'Feature', properties: { i: i }, geometry: { type: 'Point', coordinates: [g.lon, g.lat] } }; });
      map.addSource('gauges', { type: 'geojson', attribution: gaugeAttribution(), data: { type: 'FeatureCollection', features: feats } });
      map.addLayer({
        id: 'gauges-dots', type: 'circle', source: 'gauges',
        layout: { visibility: show ? 'visible' : 'none' },
        paint: {
          'circle-color': '#111111', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1,
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 0.3, 1.5, 3, 2.5, 4, 4, 6, 5, 11, 6],
          'circle-opacity': show ? OP : 0, 'circle-stroke-opacity': show ? OP : 0,
          'circle-opacity-transition': { duration: reduced() ? 0 : 200 }, 'circle-stroke-opacity-transition': { duration: reduced() ? 0 : 200 }
        }
      });
      if (!legend) buildLegend();
      collapseAttrib();
    }
    clearTimeout(hideTimer);
    map.setPaintProperty('gauges-dots', 'circle-opacity-transition', { duration: reduced() ? 0 : 200 });
    map.setPaintProperty('gauges-dots', 'circle-stroke-opacity-transition', { duration: reduced() ? 0 : 200 });
    if (show) {
      map.setLayoutProperty('gauges-dots', 'visibility', 'visible');
      map.setPaintProperty('gauges-dots', 'circle-opacity', OP);
      map.setPaintProperty('gauges-dots', 'circle-stroke-opacity', OP);
    } else {
      map.setPaintProperty('gauges-dots', 'circle-opacity', 0);
      map.setPaintProperty('gauges-dots', 'circle-stroke-opacity', 0);
      hideTimer = setTimeout(function () { if (map && map.getLayer('gauges-dots') && !wantDots) map.setLayoutProperty('gauges-dots', 'visibility', 'none'); }, reduced() ? 0 : 200);
      tipOff();
    }
    legend.hidden = !show;
  }

  // the nearest dot within 14 px of the pointer (dots on, zoom 4 or more); { g: gauge, lng: its longitude in the world copy shown }
  function nearest(e) {
    if (!gauges || !wantDots || !map.getLayer('gauges-dots') || map.getZoom() < 4) return null;
    var pt = e.point, best = null, bd = Infinity;
    var fs = map.queryRenderedFeatures([[pt.x - 14, pt.y - 14], [pt.x + 14, pt.y + 14]], { layers: ['gauges-dots'] });
    fs.forEach(function (f) {
      var g = gauges[f.properties.i];
      if (!g) return;
      var lng = g.lon + 360 * Math.round((e.lngLat.lng - g.lon) / 360);
      var p = map.project([lng, g.lat]);
      var d = Math.hypot(p.x - pt.x, p.y - pt.y);
      if (d <= 14 && d < bd) { bd = d; best = { g: g, lng: lng }; }
    });
    return best;
  }

  // a measurement window came on screen (the map was laid out at zero size while it was hidden)
  function route() {
    if (inSettings()) return;
    syncMarkers();
    applyPrefs();
    if (map) requestAnimationFrame(function () { if (map) { map.resize(); fit(true); } });
  }

  document.addEventListener('td:route', route);
  document.addEventListener('td:prefs', function () { applyPrefs(); });
  document.addEventListener('td:pins', function () { if (inSettings()) return; syncMarkers(); fit(false); });
  if (TD.ready) TD.ready.then(function () { if (!inSettings()) { applyPrefs(); setWant(win() === 'sea_level' && prefs().stations); } });

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
