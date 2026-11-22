'use strict';
/* Bhoomi preferences (window.TDPrefs). Loaded in <head>, blocking, so the theme is set before first paint.
   Stored in localStorage "td.prefs.v1" (a failure to read or write is ignored). Light is the default. */
(function () {
  var KEY = 'td.prefs.v1';
  var WINDOWS = ['sea_level', 'air_temp', 'air_temp_max', 'precip', 'water_storage'];
  var THEMES = ['light', 'dark', 'device'];
  var BASES = ['light', 'detailed'];

  function defaults() {
    var maps = {};
    WINDOWS.forEach(function (w) { maps[w] = { base: 'light', labels: true, stations: true }; });
    return { theme: 'light', units: 'metric', maps: maps };
  }

  // Merge stored text into the defaults, keeping only values of the right kind.
  function clean(raw) {
    var d = defaults();
    if (!raw || typeof raw !== 'object') return d;
    if (THEMES.indexOf(raw.theme) >= 0) d.theme = raw.theme;
    if (raw.units === 'metric' || raw.units === 'imperial') d.units = raw.units;
    if (raw.maps && typeof raw.maps === 'object') {
      WINDOWS.forEach(function (w) {
        var m = raw.maps[w];
        if (!m || typeof m !== 'object') return;
        if (BASES.indexOf(m.base) >= 0) d.maps[w].base = m.base;
        if (typeof m.labels === 'boolean') d.maps[w].labels = m.labels;
        if (typeof m.stations === 'boolean') d.maps[w].stations = m.stations;
      });
    }
    return d;
  }

  var prefs = defaults();
  try { prefs = clean(JSON.parse(localStorage.getItem(KEY))); } catch (e) { /* keep the defaults */ }

  var dark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function applyTheme() {
    var t = prefs.theme === 'device' ? (dark && dark.matches ? 'dark' : 'light') : prefs.theme;
    document.documentElement.dataset.theme = t;
  }
  applyTheme();
  if (dark && dark.addEventListener) dark.addEventListener('change', function () { if (prefs.theme === 'device') applyTheme(); });

  function copy() { return JSON.parse(JSON.stringify(prefs)); }

  window.TDPrefs = {
    get: copy,
    // patch: { theme?, units?, maps?: { <window id>: { base?, labels?, stations? } } }
    set: function (patch) {
      patch = patch || {};
      var next = copy();
      if (patch.theme !== undefined) next.theme = patch.theme;
      if (patch.units !== undefined) next.units = patch.units;
      if (patch.maps && typeof patch.maps === 'object') {
        Object.keys(patch.maps).forEach(function (w) {
          if (next.maps[w] && patch.maps[w] && typeof patch.maps[w] === 'object') Object.assign(next.maps[w], patch.maps[w]);
        });
      }
      prefs = clean(next);
      try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (e) { /* storage may be off */ }
      applyTheme();
      document.dispatchEvent(new CustomEvent('td:prefs', { detail: copy() }));
    },
  };
})();
