/* Module 03: memory without accounts. Saved places, recent results, Save and Share, privacy note. Nothing leaves this browser. */
(function () {
  'use strict';
  var TD = window.TD;
  var savedSlot = document.getElementById('saved-slot'), shareSlot = document.getElementById('share-slot'), privSlot = document.getElementById('privacy-slot');
  if (!TD || !(savedSlot || shareSlot || privSlot)) return;

  var SK = 'td.saved.v1', RK = 'td.recent.v1', MAX_SAVED = 6, MAX_RECENT = 4;
  var SHORT = { air_temp_max: 'Hottest day', water_storage: 'Water storage' };
  var WORD = { rising: 'rising', falling: 'falling', none: 'no clear change' };
  var SHAPE = { rising: '▲', falling: '▼', none: '≈' };
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var saved = [], recents = [], cur = null, ok = true, copyTimer = 0;
  var NOSAVE = "Saving isn't available in this browser. Sharing still works.", OLDEST = 'Saved. The oldest saved place was removed (up to 6 are kept).', KEPT = 'Saved. It is kept in this browser only.';
  var els = {};
  function isGeo(label) { return typeof label === 'string' && label.trim().toLowerCase() === 'your location'; }
  function savedMsg(dropped) { return !ok ? NOSAVE : dropped ? OLDEST : KEPT; }

  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function btn(cls, text) { var b = h('button', cls, text); b.type = 'button'; return b; }
  function keyOf(p) { return [p.lat.toFixed(2), p.lon.toFixed(2), p.variable, p.source || ''].join('|'); }
  function coordText(lat, lon) {
    return Math.abs(lat).toFixed(2) + '° ' + (lat < 0 ? 'S' : 'N') + ', ' + Math.abs(lon).toFixed(2) + '° ' + (lon < 0 ? 'W' : 'E');
  }
  function labelOf(p) { return p.label || coordText(p.lat, p.lon); }
  function measureOf(id) {
    var v = TD.variables.filter(function (x) { return x.id === id; })[0];
    return SHORT[id] || (v ? String(v.name).replace(/\s*\([^)]*\)/g, '').trim() : id);
  }
  function dateText(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
    return m && +m[2] >= 1 && +m[2] <= 12 && +m[3] >= 1 && +m[3] <= 31 ? (+m[3]) + ' ' + MON[+m[2] - 1] + ' ' + m[1] : '';
  }
  function say(t) { if (!els.status) return; els.status.textContent = t || ''; els.status.hidden = !t; }

  // ---- storage: every item read back is untrusted ----
  function clean(x) {
    if (!x || typeof x !== 'object') return null;
    var lat = x.lat, lon = x.lon;
    if (typeof lat !== 'number' || typeof lon !== 'number' || !(Math.abs(lat) <= 90) || !(Math.abs(lon) <= 180)) return null;
    if (typeof x.variable !== 'string' || !TD.variables.some(function (v) { return v.id === x.variable; })) return null;
    if (isGeo(x.label)) return null;
    var win = function (s) { return typeof s === 'string' && /^\d{4}(-\d{2})?$/.test(s) ? s : null; };
    return {
      lat: lat, lon: lon,
      label: (typeof x.label === 'string' && TD.cleanPlace(x.label)) || '',
      variable: x.variable,
      source: (typeof x.source === 'string' && TD.cleanPlace(x.source)) || null,
      start: win(x.start), end: win(x.end),
      verdict: Object.prototype.hasOwnProperty.call(WORD, x.verdict) ? x.verdict : null,
      checked: typeof x.checked === 'string' && dateText(x.checked) ? x.checked : null
    };
  }
  function read(key, cap, skip) {
    var out = [], seen = {};
    try {
      var a = JSON.parse(localStorage.getItem(key) || '[]');
      if (!Array.isArray(a)) return out;
      a.forEach(function (x) {
        var p = clean(x), k = p && keyOf(p);
        if (!p || seen[k] || (skip && skip[k]) || out.length >= cap) return;
        seen[k] = 1; out.push(p);
      });
    } catch (e) { /* bad file: ignored, replaced on the next write */ }
    return out;
  }
  function persist() {
    try {
      localStorage.setItem(SK, JSON.stringify(saved));
      localStorage.setItem(RK, JSON.stringify(recents));
    } catch (e) { ok = false; }
  }
  function isSaved(p) { var k = keyOf(p); return saved.some(function (s) { return keyOf(s) === k; }); }

  // ---- changes ----
  function save(p) {
    var k = keyOf(p), dropped = false;
    saved = saved.filter(function (s) { return keyOf(s) !== k; });
    recents = recents.filter(function (s) { return keyOf(s) !== k; });
    saved.unshift(p);
    if (saved.length > MAX_SAVED) { saved.length = MAX_SAVED; dropped = true; }
    persist(); refresh();
    return dropped;
  }
  function unsave(p) {
    var k = keyOf(p);
    saved = saved.filter(function (s) { return keyOf(s) !== k; });
    persist(); refresh();
  }

  // ---- Save and Share (in #share-slot) ----
  function buildShare() {
    els.actions = h('div', 'mem-actions'); els.actions.hidden = true;
    els.save = btn('btn mem-btn'); els.share = btn('btn mem-btn', 'Share this result');
    els.actions.append(els.save, els.share);
    els.noSave = h('p', 'help mem-note', NOSAVE); els.noSave.hidden = true;
    els.linkBox = h('label', 'mem-linkbox'); els.linkBox.hidden = true;
    els.link = h('input', 'mem-link'); els.link.type = 'text'; els.link.readOnly = true;
    els.linkBox.append(h('span', 'help', 'Link to copy'), els.link);
    els.status = h('p', 'help mem-status'); els.status.id = 'mem-status'; els.status.setAttribute('role', 'status'); els.status.hidden = true;
    shareSlot.append(els.actions, els.noSave, els.linkBox, els.status);

    els.save.addEventListener('click', function () {
      if (!cur) return;
      if (isSaved(cur)) { unsave(cur); say('Removed from saved places.'); return; }
      say(savedMsg(save(cur)));
    });
    els.share.addEventListener('click', function () {
      var url = TD.linkFor();
      var fallback = function () {
        els.link.value = url; els.linkBox.hidden = false; els.link.focus(); els.link.select();
        say('Copy this link.');
      };
      var done = function () {
        els.linkBox.hidden = true;
        els.share.textContent = 'Link copied';
        clearTimeout(copyTimer);
        copyTimer = setTimeout(function () { els.share.textContent = 'Share this result'; }, 3000);
        say('Link copied. It reopens this place, measurement and years. It holds nothing about you.');
      };
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, fallback);
        else fallback();
      } catch (e) { fallback(); }
    });
  }
  function refreshShare() {
    els.actions.hidden = !cur;
    els.save.hidden = !ok;
    els.noSave.hidden = ok || !cur;
    if (cur) els.save.textContent = isSaved(cur) ? 'Remove from saved' : 'Save this place';
  }

  // ---- saved places and recents (in #saved-slot) ----
  function card(p, isSavedList) {
    var li = h('li', 'mem-card'), label = labelOf(p), measure = measureOf(p.variable);
    var open = btn('mem-open'), sub = h('span', 'mem-sub'), parts = [label, measure];
    sub.append(measure);
    if (p.verdict) {
      var shape = h('span', 'mem-shape', SHAPE[p.verdict]);
      shape.setAttribute('aria-hidden', 'true');
      sub.append(' · ', shape, ' ' + WORD[p.verdict]);
      parts.push(WORD[p.verdict]);
    }
    if (p.checked) { sub.append(' · checked ' + dateText(p.checked)); parts.push('checked ' + dateText(p.checked)); }
    open.append(h('span', 'mem-name', label), sub);
    open.setAttribute('aria-label', parts.join(', ') + '. Open.');
    open.addEventListener('click', function () {
      TD.loadPlace({ lat: p.lat, lon: p.lon, label: p.label || undefined, variable: p.variable, source: p.source || undefined, start: p.start || undefined, end: p.end || undefined, origin: isSavedList ? 'saved' : 'recent' });
    });
    var x = btn('mem-x', isSavedList ? '×' : '+');
    x.setAttribute('aria-label', isSavedList ? 'Remove ' + label + ' from saved places' : 'Save ' + label);
    x.addEventListener('click', function () {
      if (isSavedList) {
        var i = saved.indexOf(p);
        unsave(p); say(label + ' removed.');
        var t = (els.savedList && els.savedList.querySelectorAll('.mem-open')[i]) || els.savedH || els.recentH || (els.save && !els.save.hidden && !els.actions.hidden ? els.save : null);
        if (t) t.focus();
      } else {
        var dropped = save(p);
        say(!ok ? NOSAVE : dropped ? OLDEST : label + ' saved.');
        if (els.savedH) els.savedH.focus();
      }
    });
    li.append(open, x);
    return li;
  }
  function renderLists() {
    savedSlot.textContent = '';
    els.savedH = els.recentH = els.savedList = null;
    var show = ok && (saved.length || recents.length);
    savedSlot.hidden = !show;
    if (!show) return;
    [[saved, 'Saved places', true], [recents, 'Recent results', false]].forEach(function (g) {
      if (!g[0].length) return;
      var hd = h('h2', 'mem-h', g[1]), ul = h('ul', 'mem-list');
      hd.tabIndex = -1;
      g[0].forEach(function (p) { ul.append(card(p, g[2])); });
      savedSlot.append(hd, ul);
      if (g[2]) { els.savedH = hd; els.savedList = ul; } else els.recentH = hd;
    });
  }

  // ---- "Your data and privacy" (in #privacy-slot) ----
  var PRIVACY = [
    'No account. We never ask you to sign in.',
    'Saved places and recent results stay in this browser, on this device. Nothing is sent to us.',
    "Place names you type in the search box go to our server, and from there to Open-Meteo's place search.",
    'The map loads its tiles from OpenFreeMap, which sees your network address, like any website you visit.',
    'A question you type in Ask, and the earlier messages of that chat, are sent to an AI model provider so it can be answered. Questions and answers are also recorded by a quality-checking service (Langfuse). Nothing else about you is kept.',
    'Our server counts requests from each network address for a short time, to stop overuse.'
  ];
  function buildPrivacy() {
    var d = h('details', 'mem-privacy'), s = h('summary'), ul = h('ul', 'mem-facts'), mark = h('span', 'mark');
    mark.setAttribute('aria-hidden', 'true');
    s.append(mark, 'Your data and privacy');
    PRIVACY.forEach(function (t) { ul.append(h('li', null, t)); });
    els.clear = h('div', 'mem-clear');
    d.append(s, ul, els.clear);
    privSlot.append(d);
    privSlot.hidden = false;
    clearRow(false);
  }
  function clearRow(confirming, note) {
    els.clear.textContent = '';
    if (!confirming) {
      var go = btn('btn mem-btn', 'Clear saved places and recent results');
      go.addEventListener('click', function () { clearRow(true); });
      els.clear.append(go);
      if (note) els.clear.append(h('p', 'help mem-note', note));
      return go;
    }
    var yes = btn('btn mem-btn', 'Yes, clear'), no = btn('btn mem-btn', 'Cancel');
    els.clear.append(h('p', 'mem-ask', 'Clear everything saved in this browser?'), yes, no);
    no.focus();
    no.addEventListener('click', function () { clearRow(false).focus(); });
    yes.addEventListener('click', function () {
      saved = []; recents = [];
      try { localStorage.removeItem(SK); localStorage.removeItem(RK); } catch (e) { ok = false; }
      refresh();
      say('Cleared.');
      if (els.actions && els.actions.hidden) TD.announce('Cleared.');
      clearRow(false, 'Cleared.').focus();
    });
  }

  function refresh() {
    if (savedSlot) renderLists();
    if (shareSlot) refreshShare();
    if (els.clear) els.clear.hidden = !ok;
  }

  // ---- events ----
  function onEnd(d) {
    cur = null; say('');
    if (els.linkBox) els.linkBox.hidden = true;
    var p = d && d.ok && d.params;
    var lat = p && Number(p.lat), lon = p && Number(p.lon);
    if (!p || !(Math.abs(lat) <= 90) || !(Math.abs(lon) <= 180) || typeof p.variable !== 'string') { refresh(); return; }
    var place = d.place || {}, tp = d.trend && d.trend.place;
    if (d.origin === 'geo' || isGeo(place.label)) {
      say("We don't make a link for your own location, to keep it private. Search for the place by name to share it.");
      refresh(); return;
    }
    var v = d.trend && d.trend.verdict, now = new Date();
    cur = clean({
      lat: lat, lon: lon, variable: p.variable, source: p.source || null, start: p.start || null, end: p.end || null,
      label: TD.cleanPlace(place.label) || (tp && /^Average of/.test(tp.name) ? '' : TD.cleanPlace(tp && tp.name)) || '',
      verdict: v === 'no_clear_change' ? 'none' : v || null,
      checked: now.getFullYear() + '-' + ('0' + (now.getMonth() + 1)).slice(-2) + '-' + ('0' + now.getDate()).slice(-2)
    });
    if (!cur) { refresh(); return; }
    var k = keyOf(cur), found = saved.filter(function (s) { return keyOf(s) === k; })[0];
    if (found) {
      if (cur.verdict && found.start === cur.start && found.end === cur.end) { found.verdict = cur.verdict; found.checked = cur.checked; }
    } else if (d.origin !== 'undo') {
      recents = recents.filter(function (s) { return keyOf(s) !== k; });
      recents.unshift(cur);
      recents.length = Math.min(recents.length, MAX_RECENT);
    }
    persist(); refresh();
  }

  TD.ready.then(function () {
    try { localStorage.setItem('td.probe', '1'); localStorage.removeItem('td.probe'); } catch (e) { ok = false; }
    if (ok) {
      saved = read(SK, MAX_SAVED);
      recents = read(RK, MAX_RECENT, saved.reduce(function (m, p) { m[keyOf(p)] = 1; return m; }, {}));
    }
    if (shareSlot) buildShare();
    if (privSlot) buildPrivacy();
    refresh();
    document.addEventListener('td:load-end', function (e) { onEnd(e.detail); });
    var s = TD.state;
    if (s && s.status === 'loaded' && s.place) {
      onEnd({ ok: true, origin: null, place: s.place, trend: s.trend, params: { variable: s.variable, lat: s.place.lat, lon: s.place.lon, source: s.source, start: s.start, end: s.end } });
    }
  });
})();
