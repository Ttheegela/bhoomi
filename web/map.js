/* Module 01: the map. Fills #map-slot. Spec: web/design/01-map.md. Optional extra: the search box does everything. */
(function () {
  'use strict';
  var slot = document.getElementById('map-slot');
  if (!slot || !window.TD) return;
  var STYLE = 'https://tiles.openfreemap.org/styles/positron';
  var SEARCH = 'You can still search for a place above.';
  var map = null, pin = null, lib = null, prev = null, cur = null;
  var gauges = null, gaugeSrcs = [], gTries = 0, gLoading = false, wantDots = false, hideTimer = 0, snap = null;
  var legend = null, tip = null, tipFor = null;
  var curGeo = false, loaded = false, failed = false, retried = false, slowTimer = 0;

  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }
  function reduced() { return matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function fmt(lat, lon) {
    return Math.abs(lat).toFixed(2) + '° ' + (lat >= 0 ? 'N' : 'S') + ', ' + Math.abs(lon).toFixed(2) + '° ' + (lon >= 0 ? 'E' : 'W');
  }

  var frame = h('div', 'map-frame');
  frame.setAttribute('role', 'group');
  frame.setAttribute('aria-label', 'Map. Optional: you can also search for a place above.');
  var canvas = h('div', 'map-canvas');
  canvas.id = 'map-canvas';
  var wait = h('p', 'map-wait', 'Loading the map…');
  frame.append(canvas, wait);
  var status = h('p', 'help map-status', 'Tap the map to pick a place, or search above.');
  status.id = 'map-status';
  status.setAttribute('role', 'status');
  var undo = h('button', 'linkbtn map-undo', 'Undo');
  undo.type = 'button';
  undo.hidden = true;
  var row = h('div', 'map-row');
  row.append(status, undo);
  slot.append(frame, row);
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

  function put(lat, lon, fly) {
    if (!map || !loaded) return;
    if (!pin) {
      var el = h('div', 'map-pin');
      el.setAttribute('aria-hidden', 'true');
      pin = new lib.Marker({ element: el }).setLngLat([lon, lat]).addTo(map);
    } else {
      pin.setLngLat([lon, lat]);
    }
    if (fly) map.flyTo({ center: [lon, lat], zoom: Math.max(map.getZoom(), 4.5), duration: reduced() ? 0 : 900, essential: false });
  }

  // no WebGL or the library did not import: no retry (a failed module import is cached by the browser)
  // the control opens itself when it is added; start collapsed (just the info button) until the visitor taps it
  function collapseAttrib() {
    var a = canvas.querySelector('.maplibregl-ctrl-attrib');
    if (a) { a.removeAttribute('open'); a.classList.remove('maplibregl-compact-show'); }
  }

  function noMap() {
    fail("Your browser can't show the map. Search for a place above.", false);
    status.textContent = SEARCH;
  }

  function start() {
    if (map) { map.remove(); map = null; pin = null; tip = null; tipFor = null; }
    failed = false; loaded = false;
    frame.classList.remove('map-failed');
    wait.hidden = false;
    wait.textContent = 'Loading the map…';
    clearTimeout(slowTimer);
    slowTimer = setTimeout(function () {
      if (!loaded && !failed) wait.textContent = 'Loading the map… Still loading. The map is optional.';
    }, 8000);
    import('./vendor/maplibre-gl/maplibre-gl.mjs').then(function (m) {
      lib = m;
      try {
        map = new lib.Map({
          container: canvas, style: STYLE, center: [15, 28], zoom: window.innerWidth < 600 ? 0.4 : 1.1,
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
      // the required credit lives inside the map, bottom right (compact: an info button that opens the words)
      // the style carries the base-map credit itself, so no custom copy (it would show twice)
      map.addControl(new lib.AttributionControl({ compact: true }), 'bottom-right');
      collapseAttrib();
      map.on('resize', collapseAttrib);
      map.addControl(new lib.NavigationControl({ showCompass: false, visualizePitch: false }), 'top-right');
      map.touchZoomRotate.disableRotation();
      map.on('load', function () {
        loaded = true;
        failed = false;
        clearTimeout(slowTimer);
        frame.classList.remove('map-failed');
        wait.hidden = true;
        if (cur) put(cur.lat, cur.lon, true);
        maybeFetch();
        collapseAttrib();
        applyDots();
      });
      // errors after load (a missed tile on a slow line) are ignored on purpose
      map.on('error', function () { if (!loaded) fail("The map couldn't load. " + SEARCH, true); });
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
      map.on('mouseout', tipOff);
      map.on('zoom', function () { if (map.getZoom() < 4) tipOff(); });
      map.on('click', function (e) {
        var s = TD.state;
        prev = s.place ? { lat: s.place.lat, lon: s.place.lon, label: s.place.label, variable: s.variable, source: s.source, start: s.start, end: s.end, geo: curGeo } : null;
        var hit = nearest(e), lat, lon, label;
        snap = null;
        if (hit) {
          lat = hit.g.lat; lon = hit.g.lon;
          label = (TD.cleanPlace && TD.cleanPlace(hit.g.name)) || 'Tide gauge';
          snap = { lat: lat, lon: lon, label: label };
        } else {
          lat = Math.max(-85, Math.min(85, e.lngLat.lat));
          lon = (((e.lngLat.lng + 180) % 360) + 360) % 360 - 180;
          label = 'Pinned spot (' + fmt(lat, lon) + ')';
        }
        cur = { lat: lat, lon: lon };
        put(lat, lon, false);
        TD.loadPlace({ lat: lat, lon: lon, label: label, origin: 'map' });
      });
    }).catch(noMap);
  }

  // ---- tide gauge dots (spec: web/design/07-gauges.md); only while the measurement is sea level ----
  var hoverOK = matchMedia('(hover: hover)').matches;
  var OP = ['step', ['zoom'], 0.65, 4, 0.9];

  function setWant(v) {
    var on = v === 'sea_level';
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
    legend.append(svg, document.createTextNode('Tide gauge. Zoom in and tap one. A gauge with only a few years of readings cannot give a clear answer.'));
    slot.append(legend);
    gaugeSrcs.forEach(function (x) {
      if (TD.addCredit) TD.addCredit('gauges-' + x.id, creditName(x), isHttps(x.url) ? x.url : undefined);
    });
  }

  // draws, shows or fades out the dots; runs when the map or the list arrives, and when the measurement changes
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

  var sel = document.getElementById('variable');
  if (sel) sel.addEventListener('change', function () { setWant(sel.value); });
  if (TD.ready) TD.ready.then(function () { if (sel) setWant(sel.value); });

  var io = null;
  if ('IntersectionObserver' in window) {
    io = new IntersectionObserver(function (es) {
      if (es[0].isIntersecting) { io.disconnect(); start(); }
    }, { rootMargin: '300px' });
    io.observe(slot);
  } else {
    start();
  }

  document.addEventListener('td:place-pick', function (e) {
    var d = e.detail, fromMap = d.origin === 'map';
    cur = { lat: d.lat, lon: d.lon };
    curGeo = d.origin === 'geo';
    if (!fromMap) put(d.lat, d.lon, true);
    if (fromMap && snap && Math.abs(snap.lat - d.lat) <= 0.005 && Math.abs(snap.lon - d.lon) <= 0.005) {
      status.textContent = 'Pinned the tide gauge at ' + snap.label + '.';
    } else {
      status.textContent = (fromMap ? 'Pinned ' : 'Showing ') + fmt(d.lat, d.lon) + '. We use the nearest data we have.';
    }
    snap = null;
    if (d.variable) setWant(d.variable);
    undo.hidden = !(fromMap && prev);
  });

  undo.addEventListener('click', function () {
    var p = prev;
    prev = null;
    undo.hidden = true;
    if (p) TD.loadPlace({ lat: p.lat, lon: p.lon, label: p.label, variable: p.variable, source: p.source, start: p.start, end: p.end, origin: p.geo ? 'geo' : 'undo' });
  });
})();
