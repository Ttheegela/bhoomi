(function () {
  var TD = window.TD;
  var slot = document.getElementById('guide-slot');
  var reopen = document.getElementById('guide-reopen');
  if (!TD || !slot || !reopen) return;

  var KEY = 'td.guide.v1';
  var NOTE = 'This changes only the examples and the wording, not the data.';
  var ROLES = [
    { chip: "I'm a homeowner", label: 'Lower Manhattan, New York', lat: 40.71, lon: -74.01, variable: 'sea_level',
      words: 'sea level', q: 'Is the sea rising where I live?', note: 'Tide gauges measure the sea against the land.' },
    { chip: "I'm a farmer", label: 'Punjab, India (near Ludhiana)', lat: 30.90, lon: 75.85, variable: 'water_storage',
      words: 'land water storage', q: 'Is the water stored in the land under my fields going down?',
      note: 'Satellites measure all water stored in the land, not the level in one well.',
      alt: { text: 'Look at the hottest days instead', variable: 'air_temp_max' } },
    { chip: "I'm a student", label: 'Chennai, Tamil Nadu, India', lat: 13.08, lon: 80.27, variable: 'precip',
      words: 'rainfall', q: 'Is it raining more or less than it used to?', note: '' },
    { chip: "I'm a local planner", label: 'Mumbai, Maharashtra, India', lat: 19.08, lon: 72.88, variable: 'sea_level',
      words: 'sea level', q: 'How fast is the sea rising along our coast?', note: '' }
  ];
  var roles = [];

  function remember() { try { localStorage.setItem(KEY, 'done'); } catch (e) {} }
  function remembered() { try { return localStorage.getItem(KEY) === 'done'; } catch (e) { return false; } }

  function el(tag, cls, text, parent) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }

  function hasVar(id) {
    return (TD.variables || []).some(function (v) { return v && v.id === id; });
  }

  function close(save, focusId) {
    if (save) remember();
    slot.hidden = true;
    while (slot.firstChild) slot.removeChild(slot.firstChild);
    document.documentElement.removeAttribute('data-guide');
    var t = focusId && document.getElementById(focusId);
    if (t) t.focus();
  }

  function card(step) {
    while (slot.firstChild) slot.removeChild(slot.firstChild);
    var c = el('div', 'card quiet guide-card', '', slot);
    el('p', 'guide-step', step, c);
    slot.hidden = false;
    document.documentElement.setAttribute('data-guide', 'open');
    return c;
  }

  function heading(c, text) {
    var h = el('h2', 'guide-h', text, c);
    h.id = 'guide-h';
    h.tabIndex = -1;
    return h;
  }

  function step1(focus) {
    var c = card('Step 1 of 2');
    var h = heading(c, 'New here? Pick what describes you.');
    var g = el('div', 'guide-chips', '', c);
    g.setAttribute('role', 'group');
    g.setAttribute('aria-labelledby', 'guide-h');
    roles.forEach(function (r) {
      var b = el('button', 'chip guide-chip', r.chip, g);
      b.type = 'button';
      b.addEventListener('click', function () { step2(r); });
    });
    el('p', 'guide-note', NOTE, c);
    var s = el('button', 'btn guide-skip', 'Skip, just search', c);
    s.type = 'button';
    s.addEventListener('click', function () { close(true, 'place'); TD.announce('Quick start closed.'); });
    if (focus) h.focus();
  }

  function step2(r) {
    var c = card('Step 2 of 2');
    var h = heading(c, r.q);
    el('p', 'guide-plan', "We'll look at " + r.words + ' for ' + r.label + '.', c);
    if (r.note) el('p', 'guide-note', r.note, c);
    var a = el('div', 'guide-actions', '', c);
    function btn(cls, text, fn) {
      var b = el('button', cls, text, a);
      b.type = 'button';
      b.addEventListener('click', fn);
    }
    function go(variable) {
      remember();
      close(false);
      TD.loadPlace({ lat: r.lat, lon: r.lon, label: r.label, variable: variable, origin: 'guide' });
    }
    btn('btn primary', 'Show me', function () { go(r.variable); });
    btn('btn', 'Choose a different place', function () { close(true, 'place'); });
    if (r.alt && hasVar(r.alt.variable)) btn('btn guide-alt', r.alt.text, function () { go(r.alt.variable); });
    btn('linkbtn', 'Back', function () { step1(true); });
    el('p', 'guide-note', NOTE, c);
    h.focus();
  }

  TD.ready.then(function () {
    roles = ROLES.filter(function (r) { return hasVar(r.variable); });
    if (roles.length < 2) return;
    reopen.hidden = false;
    reopen.addEventListener('click', function () { step1(true); });
    // a share link that opens a place hides the guide for this visit, without remembering
    document.addEventListener('td:place-pick', function (e) {
      if (e.detail && e.detail.origin === 'share-link') close(false);
    });
    var p;
    try { p = new URLSearchParams(location.hash.replace(/^#/, '')); } catch (e) { p = new URLSearchParams(''); }
    var explore = !p.get('tab') || p.get('tab') === 'explore';
    if (!remembered() && !p.has('variable') && explore) step1(false);
  });
})();
