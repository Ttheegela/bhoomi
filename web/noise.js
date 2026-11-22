/* Module 05: "Real or noise?" (web/design/05-noise.md). Fills #noise-slot. */
(function () {
  'use strict';
  /* PURE START */
  var MINUS = '−';
  var WORDS = { rising: 'rising', falling: 'falling', no_clear_change: 'no clear change' };
  // Same behaviour as fmtNum/fmtVal in app.js: sign, 2 decimals under 1 else 1, 3 when it would round to zero.
  function fmtNum(x) {
    var d = Math.abs(x) < 1 ? 2 : 1;
    if (x !== 0 && Number(x.toFixed(d)) === 0) d = 3;
    var s = x.toFixed(d);
    if (Number(s) === 0) s = (0).toFixed(d);
    s = s.replace('-', MINUS);
    return x > 0 ? '+' + s : s;
  }
  function fmtVal(x, units) { return fmtNum(x) + (units ? ' ' + (units === 'degC' ? '°C' : units) : ''); }
  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function valid(t) {
    return !!t && typeof t === 'object' && !!WORDS[t.verdict] && isNum(t.slope_per_decade) && isNum(t.ci_low) && isNum(t.ci_high) &&
      !!t.period && typeof t.period.start === 'string' && typeof t.period.end === 'string';
  }
  function startFor(endYear, n) { return String(endYear - n + 1); }
  function windowsFor(L) { return [10, 20, 30].filter(function (n) { return L >= n + 5; }); }
  function labelFor(n, t) {
    var base = n ? 'Last ' + n + ' years' : 'Full record';
    return t ? base + ', ' + t.period.start.slice(0, 4) + ' to ' + t.period.end.slice(0, 4) : base;
  }
  // rows: [{n, t}] shortest first, the full record last with n = 0.
  // "Every stretch" claims need every row valid; the mixed claim needs the shortest and the full record valid.
  function buildSentence(rows) {
    var ok = rows.filter(function (r) { return valid(r.t); });
    if (rows.length < 2 || !valid(rows[0].t) || !valid(rows[rows.length - 1].t) || rows[rows.length - 1].n !== 0) return '';
    var v0 = ok[0].t.verdict;
    var all = ok.length === rows.length;
    var same = all && ok.every(function (r) { return r.t.verdict === v0; });
    if (same && v0 === 'no_clear_change') {
      return 'No stretch shows a clear change. Over this record, any change is too small or too noisy to separate from normal ups and downs.';
    }
    if (same) {
      var sorted = ok.slice().sort(function (a, b) { return Math.abs(a.t.slope_per_decade) - Math.abs(b.t.slope_per_decade); });
      var lo = sorted[0].t, hi = sorted[sorted.length - 1].t;
      if (Math.abs(hi.slope_per_decade) <= 1.5 * Math.abs(lo.slope_per_decade)) {
        return 'Every stretch gives the same answer: ' + WORDS[v0] + '. That is what a real change looks like.';
      }
      return 'Every stretch points the same way: ' + WORDS[v0] + '. Short stretches give a shakier rate, from ' +
        fmtVal(lo.slope_per_decade, lo.units) + ' to ' + fmtVal(hi.slope_per_decade, hi.units) +
        ' per decade; the full record is steadier.';
    }
    var s = ok[0], f = ok[ok.length - 1];
    if (f.n !== 0 || s.t.verdict === f.t.verdict) return '';
    return 'The answer changes with the length of the record: last ' + s.n + ' years says ' + WORDS[s.t.verdict] +
      ', the full record says ' + WORDS[f.t.verdict] +
      '. Short stretches wobble because normal ups and downs weigh more; longer ones hold steady, so trust the longer record more.';
  }
  /* PURE END */

  var slot = document.getElementById('noise-slot');
  if (!slot || !window.TD) return;
  var TD = window.TD, NS = 'http://www.w3.org/2000/svg';
  var store = {};      // per place: { start: valid reply }, kept for the visit
  var gen = 0, busy = false, view = null, slowTimer = 0, lastOrigin = '';

  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function placeKey(p) { return [p.lat, p.lon, p.variable, p.source || ''].join('|'); }
  function hide() { clearTimeout(slowTimer); view = null; busy = false; slot.hidden = true; slot.textContent = ''; }

  function failText(res) {
    if (res && res.status === 429) return 'Too many requests. Wait a moment and try again.';
    if (res && res.status === 400 && res.body && typeof res.body.detail === 'string' && res.body.detail) return res.body.detail.slice(0, 300);
    return "We couldn't check this stretch.";
  }

  function svgEl(parent, name, attrs) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    parent.appendChild(e);
    return e;
  }

  function draw(svg, t, mn, mx) {
    var w = Math.max(160, svg.clientWidth || 280), span = mx - mn || 1;
    function X(v) { return (v - mn) / span * w; }
    svg.setAttribute('viewBox', '0 0 ' + w + ' 36');
    svg.textContent = '';
    svgEl(svg, 'line', { x1: X(0), x2: X(0), y1: 0, y2: 36, 'class': 'noise-zero' });
    svgEl(svg, 'rect', { x: X(t.ci_low), y: 13, width: Math.max(2, X(t.ci_high) - X(t.ci_low)), height: 10, 'class': 'noise-range' });
    svgEl(svg, 'circle', { cx: X(t.slope_per_decade), cy: 18, r: 5, 'class': 'noise-dot' });
  }

  function showOnChart(r) {
    var spec = { lat: view.params.lat, lon: view.params.lon, variable: view.params.variable, origin: lastOrigin === 'geo' || view.label === 'your location' ? 'geo' : 'window' };
    if (view.label) spec.label = view.label;
    if (view.params.source) spec.source = view.params.source;
    if (r.start) spec.start = r.start;
    TD.loadPlace(spec);
  }

  // withBars: the shared scale needs every reply, so bars are drawn only once all are in.
  function renderRows(withBars) {
    var list = view.list, bars = [];
    list.textContent = '';
    view.rows.forEach(function (r) {
      var li = h('li', 'noise-row');
      var top = h('div', 'noise-top');
      top.appendChild(h('span', 'noise-label', labelFor(r.n, r.t)));
      li.appendChild(top);
      if (r.t) {
        var v = r.t.verdict;
        li.setAttribute('data-v', v === 'rising' ? 'rising' : v === 'falling' ? 'falling' : 'none');
        top.appendChild(h('span', 'noise-verdict', v === 'rising' ? '▲ Rising' : v === 'falling' ? '▼ Falling' : '≈ No clear change'));
        var svg = document.createElementNS(NS, 'svg');
        svg.setAttribute('class', 'noise-bar');
        svg.setAttribute('aria-hidden', 'true');
        svg.setAttribute('height', '36');
        li.appendChild(svg);
        bars.push([svg, r.t]);
        li.appendChild(h('p', 'noise-num', fmtVal(r.t.slope_per_decade, r.t.units) + ' per decade. 95% range ' +
          fmtNum(r.t.ci_low) + ' to ' + fmtNum(r.t.ci_high) + '.'));
        var b = h('button', 'linkbtn noise-show', 'Show this on the chart');
        b.type = 'button';
        b.addEventListener('click', function () { showOnChart(r); });
        li.appendChild(b);
      } else if (r.err) {
        li.setAttribute('data-v', 'err');
        li.appendChild(h('p', 'noise-num', r.err));
      } else {
        li.className += ' noise-wait';
      }
      list.appendChild(li);
    });
    if (view) view.drawn = !!withBars;
    if (withBars) {
      var mn = 0, mx = 0;
      bars.forEach(function (b) { mn = Math.min(mn, b[1].ci_low); mx = Math.max(mx, b[1].ci_high); });
      var pad = (mx - mn) * 0.06;
      bars.forEach(function (b) { draw(b[0], b[1], mn - pad, mx + pad); });
    }
  }

  async function run() {
    if (busy) return;
    busy = true;
    var g = gen, v = view, p = v.params, kept = store[v.key] || (store[v.key] = {});
    function get(start) {
      var q = { variable: p.variable, lat: p.lat, lon: p.lon };
      if (p.source) q.source = p.source;
      if (start) q.start = start;
      return Promise.resolve().then(function () { return TD.fetchTrend(q); }).catch(function () { return null; });
    }
    v.go.textContent = 'Checking…';
    v.go.setAttribute('aria-disabled', 'true');
    v.status.textContent = 'Checking shorter stretches…';
    clearTimeout(slowTimer);
    slowTimer = setTimeout(function () {
      if (g === gen && busy) v.status.textContent = 'Checking shorter stretches… Still working. This can take a few seconds.';
    }, 8000);
    if (!v.wins) { // the loaded answer is a window: fetch the full record first, then work out the stretches from it
      var fr = kept[''] ? { ok: true, body: kept[''] } : await get('');
      if (g !== gen) return;
      if (!(fr && fr.ok && valid(fr.body))) {
        clearTimeout(slowTimer);
        busy = false;
        v.go.removeAttribute('aria-disabled');
        v.go.textContent = 'Try again';
        v.status.textContent = "We couldn't compare stretches right now. Try again in a minute.";
        return;
      }
      kept[''] = fr.body;
      v.endY = Number(fr.body.period.end.slice(0, 4));
      v.wins = windowsFor(v.endY - Number(fr.body.period.start.slice(0, 4)));
      if (!v.wins.length) { hide(); return; }
    }
    v.rows = v.wins.map(function (n) { return { n: n, start: startFor(v.endY, n), t: null, err: '' }; });
    v.rows.push({ n: 0, start: '', t: null, err: '' });
    v.rows.forEach(function (r) { if (kept[r.start]) r.t = kept[r.start]; });
    var todo = v.rows.filter(function (r) { return !r.t; });
    renderRows(false);
    async function worker() {
      while (todo.length) {
        var r = todo.shift(), res = await get(r.start);
        if (g !== gen) return;
        if (res && res.ok && valid(res.body)) { r.t = res.body; kept[r.start] = res.body; } else { r.err = failText(res); }
        renderRows(false);
      }
    }
    await Promise.all([worker(), worker(), worker()]);
    if (g !== gen) return;
    clearTimeout(slowTimer);
    busy = false;
    var okN = v.rows.filter(function (r) { return r.t; }).length;
    renderRows(true);
    var s = buildSentence(v.rows);
    v.sentence.textContent = s;
    v.sentence.hidden = !s;
    v.legend.hidden = !okN;
    v.go.removeAttribute('aria-disabled');
    v.go.textContent = okN < v.rows.length ? 'Try again' : 'Try shorter stretches';
    v.status.textContent = okN ? 'Compared ' + okN + (okN === 1 ? ' stretch.' : ' stretches.') : "We couldn't compare stretches right now. Try again in a minute.";
  }

  function setup(params, trend, label) {
    hide();
    if (!trend) return;
    var key = placeKey(params), kept = store[key] || (store[key] = {});
    if (!params.start && !params.end && valid(trend)) kept[''] = trend;
    var endY = 0, wins = null; // unknown until the full record is known; run() fetches it first
    if (kept['']) {
      endY = Number(kept[''].period.end.slice(0, 4));
      wins = windowsFor(endY - Number(kept[''].period.start.slice(0, 4)));
      if (!wins.length) return;
    }
    var card = h('div', 'noise-card');
    var sentence = h('p', 'noise-sentence');
    sentence.id = 'noise-sentence';
    sentence.hidden = true;
    var go = h('button', 'btn noise-go', 'Try shorter stretches');
    go.type = 'button';
    var status = h('p', 'help');
    status.id = 'noise-status';
    status.setAttribute('role', 'status');
    var list = h('ul', 'noise-list');
    var legend = h('div', 'noise-legend');
    legend.hidden = true;
    legend.appendChild(h('p', 'help', 'Each bar is the range of trends the data support (95% range). The dot is our best estimate. The dashed line is no change. All bars share one scale.'));
    legend.appendChild(h('p', 'help noise-tag', 'Our calculation.'));
    var src = trend.source;
    var href = src && [src.record_url, src.url].filter(function (u) { return typeof u === 'string' && /^https:\/\//.test(u); })[0]; // this exact record first
    if (src && typeof src.name === 'string' && href) {
      var line = h('p', 'srcline');
      var a = h('a', 'srclink', 'Raw data: ' + src.name + ' ↗');
      a.href = href;
      a.target = '_blank';
      a.rel = 'noopener';
      line.appendChild(a);
      legend.appendChild(line);
    }
    card.appendChild(h('h3', 'noise-h', 'Real or noise?'));
    card.appendChild(sentence);
    card.appendChild(h('p', 'noise-lead', 'A short stretch of data can mislead: normal ups and downs weigh more. Try shorter stretches of this record and see whether the answer holds.'));
    card.appendChild(go);
    card.appendChild(status);
    card.appendChild(list);
    card.appendChild(legend);
    view = { params: params, key: key, label: label || '', endY: endY, wins: wins, rows: [], go: go, status: status, sentence: sentence, list: list, legend: legend };
    go.addEventListener('click', run);
    slot.appendChild(card);
    slot.hidden = false;
  }

  function paramsFrom(s) {
    var p = { variable: s.variable, lat: s.place.lat, lon: s.place.lon };
    if (s.source) p.source = s.source;
    if (s.start) p.start = s.start;
    if (s.end) p.end = s.end;
    return p;
  }

  // inside a closed <details> every width is 0: draw the bars again when the section opens
  var det = slot.closest('details');
  if (det) det.addEventListener('toggle', function () { if (det.open && view && view.drawn) renderRows(true); });

  document.addEventListener('td:load-start', function () { gen++; hide(); });
  document.addEventListener('td:load-end', function (e) {
    var d = e.detail || {};
    gen++;
    lastOrigin = d.origin || '';
    if (d.ok && d.params && d.trend) setup(d.params, d.trend, d.place && d.place.label);
    else hide();
  });
  var s0 = TD.state; // loaded late: act as if the last event was just seen
  if (s0 && s0.status === 'loaded' && s0.place && s0.trend) setup(paramsFrom(s0), s0.trend, s0.place.label);
})();
