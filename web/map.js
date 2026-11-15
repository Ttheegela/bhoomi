/* Module 01: the map. Fills #map-slot. Spec: web/design/01-map.md. Optional extra: the search box does everything. */
(function () {
  'use strict';
  var slot = document.getElementById('map-slot');
  if (!slot || !window.TD) return;
  var STYLE = 'https://tiles.openfreemap.org/styles/positron';
  var SEARCH = 'You can still search for a place above.';
  var map = null, pin = null, lib = null, prev = null, cur = null;
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
  var credit = h('p', 'map-credit');
  var a1 = h('a', '', 'OpenFreeMap © OpenMapTiles');
  a1.href = 'https://openfreemap.org/';
  var a2 = h('a', '', 'Data from OpenStreetMap');
  a2.href = 'https://www.openstreetmap.org/copyright';
  a1.rel = a2.rel = 'noopener';
  credit.append(a1, a2);
  slot.append(frame, row, credit);
  slot.hidden = false;
  if (TD.addCredit) TD.addCredit('map', 'Map: OpenFreeMap © OpenMapTiles, data from OpenStreetMap', 'https://www.openstreetmap.org/copyright');

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
  function noMap() {
    fail("Your browser can't show the map. Search for a place above.", false);
    status.textContent = SEARCH;
  }

  function start() {
    if (map) { map.remove(); map = null; pin = null; }
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
      map.addControl(new lib.NavigationControl({ showCompass: false, visualizePitch: false }), 'top-right');
      map.touchZoomRotate.disableRotation();
      map.on('load', function () {
        loaded = true;
        failed = false;
        clearTimeout(slowTimer);
        frame.classList.remove('map-failed');
        wait.hidden = true;
        if (cur) put(cur.lat, cur.lon, true);
      });
      // errors after load (a missed tile on a slow line) are ignored on purpose
      map.on('error', function () { if (!loaded) fail("The map couldn't load. " + SEARCH, true); });
      map.on('click', function (e) {
        var s = TD.state;
        prev = s.place ? { lat: s.place.lat, lon: s.place.lon, label: s.place.label, variable: s.variable, source: s.source, start: s.start, end: s.end, geo: curGeo } : null;
        var lat = Math.max(-85, Math.min(85, e.lngLat.lat));
        var lon = (((e.lngLat.lng + 180) % 360) + 360) % 360 - 180;
        cur = { lat: lat, lon: lon };
        put(lat, lon, false);
        TD.loadPlace({ lat: lat, lon: lon, label: 'Pinned spot (' + fmt(lat, lon) + ')', origin: 'map' });
      });
    }).catch(noMap);
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

  document.addEventListener('td:place-pick', function (e) {
    var d = e.detail, fromMap = d.origin === 'map';
    cur = { lat: d.lat, lon: d.lon };
    curGeo = d.origin === 'geo';
    if (!fromMap) put(d.lat, d.lon, true);
    status.textContent = (fromMap ? 'Pinned ' : 'Showing ') + fmt(d.lat, d.lon) + '. We use the nearest data we have.';
    undo.hidden = !(fromMap && prev);
  });

  undo.addEventListener('click', function () {
    var p = prev;
    prev = null;
    undo.hidden = true;
    if (p) TD.loadPlace({ lat: p.lat, lon: p.lon, label: p.label, variable: p.variable, source: p.source, start: p.start, end: p.end, origin: p.geo ? 'geo' : 'undo' });
  });
})();
