// Compare: comparison chart card + comparison table card (web/design/10-foundation.md section 7).
// Each place is drawn from its own anomalies against its 1995–2014 average (series.anomaly); no future is drawn.
// Pure helpers (yearly, smooth, niceTicks, buildModel) take plain data; everything under "DOM" talks to TD / TDX / TDPrefs.
(function () {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';
  var X0 = 56, X1 = 1024, Y0 = 34, Y1 = 304;           // plot area in the 1040 x 340 drawing
  var HEADS = {
    sea_level: 'the sea', air_temp: 'air temperature', air_temp_max: 'the hottest days',
    precip: 'rain', water_storage: 'water storage'
  };

  // ---------- pure helpers ----------

  // Yearly mean of a list of monthly values; a year needs 9 of its 12 months. -> {year: mean}
  function yearly(times, values) {
    var out = {}, sum = {}, cnt = {};
    (times || []).forEach(function (t, i) {
      var v = values[i], y = parseInt(String(t).slice(0, 4), 10);
      if (typeof v !== 'number' || !isFinite(v) || !isFinite(y)) return;
      sum[y] = (sum[y] || 0) + v; cnt[y] = (cnt[y] || 0) + 1;
    });
    Object.keys(cnt).forEach(function (y) { if (cnt[y] >= 9) out[y] = sum[y] / cnt[y]; });
    return out;
  }

  // Centred 5-year average, shown only where 4 of its 5 years exist (D6). -> [{year, v}] ascending; a missing year breaks the line
  function smooth(ym) {
    var ys = Object.keys(ym).map(Number), pts = [];
    if (!ys.length) return pts;
    var a = Math.min.apply(null, ys), b = Math.max.apply(null, ys);
    for (var y = a; y <= b; y++) {
      var s = 0, n = 0;
      for (var k = y - 2; k <= y + 2; k++) if (ym[k] !== undefined) { s += ym[k]; n++; }
      if (n >= 4) pts.push({ year: y, v: s / n });
    }
    return pts;
  }

  function niceTicks(lo, hi) {
    lo = Math.min(lo, 0); hi = Math.max(hi, 0);
    if (hi - lo < 1e-9) hi = lo + 1;
    // smallest step from 5, 10, 20, 25, 50, 100 (x10^k) that gives at most 7 ticks; limits = first tick at or beyond the data
    var step, a, b, t = [], p = Math.pow(10, Math.floor(Math.log10((hi - lo) / 7)) - 1), i = 0, M = [1, 2, 2.5, 5];
    do {
      step = M[i % 4] * p * (i >= 4 ? Math.pow(10, Math.floor(i / 4)) : 1);
      a = Math.floor(lo / step + 1e-9) * step; b = Math.ceil(hi / step - 1e-9) * step; i++;
    } while ((b - a) / step + 1 > 7 && i < 40);
    for (var v = a; v <= b + step / 2; v += step) t.push(Math.round(v / step) * step);
    return { ticks: t, step: step, lo: a, hi: b };
  }

  // tick label with the step's decimals: "+0.5", "0", "−10"
  function signed(v, step) {
    var d = step >= 1 ? 0 : Math.min(3, Math.ceil(-Math.log10(step) - 1e-9));
    var s = Math.abs(v).toFixed(d);
    return Number(s) === 0 ? '0' : (v < 0 ? '−' : '+') + s;
  }

  // Everything the chart needs, from plain data. pins: [{label, slot, selected, status, trend, series}];
  // conv(trend, value, units) -> the value in the unit shown.
  function buildModel(pins, conv) {
    var lines = [], out = { left: [], lines: lines };
    (pins || []).forEach(function (p) {
      if (p.status === 'loading' || (!p.status && !p.series)) { out.left.push({ label: p.label, why: 'still loading' }); return; }
      if (p.status === 'error') { out.left.push({ label: p.label, why: 'could not be loaded' }); return; }
      var a = p.series && p.series.anomaly, b = p.trend && p.trend.baseline;
      if (!a || !Array.isArray(a.values) || !b || b.method === 'none') { out.left.push({ label: p.label, why: 'no 1995–2014 average for its record' }); return; }
      var pts = smooth(yearly(p.series.times, a.values));
      if (!pts.length) { out.left.push({ label: p.label, why: 'has too little data' }); return; }
      lines.push({ pin: p, slot: p.slot || 0, selected: !!p.selected,
        pts: pts.map(function (q) { return { year: q.year, v: conv(p.trend, q.v, a.units) }; }) });
    });
    if (!lines.length) return out;
    var minV = Infinity, maxV = -Infinity;
    lines.forEach(function (l) { l.pts.forEach(function (q) { minV = Math.min(minV, q.v); maxV = Math.max(maxV, q.v); }); });
    out.xMin = Math.min.apply(null, lines.map(function (l) { return l.pts[0].year; }));
    out.xMax = Math.max.apply(null, lines.map(function (l) { return l.pts[l.pts.length - 1].year; })); // the last plotted year
    if (out.xMax === out.xMin) out.xMax = out.xMin + 1;
    out.y = niceTicks(minV, maxV);
    out.xTicks = [];
    var step = out.xMax - out.xMin <= 30 ? 5 : out.xMax - out.xMin <= 80 ? 10 : 25;
    for (var t = Math.ceil(out.xMin / step) * step; t <= out.xMax; t += step) out.xTicks.push(t);
    var span = out.xMax - out.xMin, ys = out.y.hi - out.y.lo || 1;
    out.px = function (yr) { return X0 + (yr - out.xMin) / span * (X1 - X0); };
    out.py = function (v) { return Y1 - (v - out.y.lo) / ys * (Y1 - Y0); };
    var hi = lines[0];
    lines.forEach(function (l) { if (l.pts[l.pts.length - 1].v > hi.pts[hi.pts.length - 1].v) hi = l; });
    out.highest = hi.pin.label;
    return out;
  }

  // Path "M..L.." per run of consecutive years; runs of one point are dropped (a gap breaks the line).
  function segments(pts, px, py) {
    var runs = [], cur = [];
    pts.forEach(function (q, i) {
      if (i && q.year !== pts[i - 1].year + 1) { runs.push(cur); cur = []; }
      cur.push(q);
    });
    runs.push(cur);
    return runs.filter(function (r) { return r.length > 1; }).map(function (r) {
      return r.map(function (q, i) { return (i ? 'L' : 'M') + px(q.year).toFixed(1) + ',' + py(q.v).toFixed(1); }).join(' ');
    }).join(' ');
  }

  // ---------- DOM ----------

  function svg(name, attrs, text) {
    var e = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (text != null) e.textContent = text;
    return e;
  }
  function h(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function httpsOnly(u) { return typeof u === 'string' && /^https:\/\//i.test(u) ? u : ''; }
  function slotCls(l) { return l.selected ? 'sel' : String(l.slot % 6); }
  function own(text) { return String(text || '').replace(/^the /, ''); } // "its own 1995–2014 average"

  function leftOut(g, left) {
    if (!left.length) return;
    g.appendChild(h('p', 'cmp-left', 'Left out of the chart: ' +
      left.map(function (x) { return x.label + ' (' + x.why + ')'; }).join('; ') + '.'));
  }

  function drawChart(slot, pins, o) {
    var P = window.TD, X = window.TDX, g = h('div', 'cmp-chart'), head = h('div', 'chead'), hd = h('div');
    hd.appendChild(h('h3', 'cmp-h', 'How ' + (HEADS[o.window] || 'things') + (o.window === 'air_temp_max' ? ' have' : ' has') + ' changed at your places'));
    head.appendChild(hd);
    g.appendChild(head);
    var m = buildModel(pins, function (t, v, u) { return X.conv(t, o.imperial, v, u).v; });
    if (!m.lines.length) {
      hd.appendChild(h('p', 'cmp-cap', m.left.length ? 'Waiting for the records to arrive.' : 'Add a place to see how it compares.'));
      leftOut(g, m.left);
      slot.replaceChildren(g);
      return;
    }
    var first = m.lines.filter(function (l) { return l.selected; })[0] || m.lines[0], ft = first.pin.trend, fa = first.pin.series.anomaly;
    var unit = fa.kind === 'percent' ? '% of the usual rain' : X.conv(ft, o.imperial, 0, fa.units).unit;
    var base = ft.baseline.text;
    var months = m.lines.map(function (l) { return l.pin.trend.latest && l.pin.trend.latest.month; });
    var same = months.every(function (x) { return x && x === months[0]; });
    var cap = 'Five-year averages, in ' + unit + ', each compared with its own ' + own(base) + '.' +
      (same ? ' ' + first.pin.trend.latest.text + '.' : ' Records end at different months; the table has each one.');
    hd.appendChild(h('p', 'cmp-cap', cap));
    var dl = h('button', 'btn', 'Download CSV');
    dl.type = 'button';
    dl.addEventListener('click', function () {
      X.download(X.csvCompare(m.lines.map(function (l) { return { label: l.pin.label, t: l.pin.trend, s: l.pin.series }; }), { name: o.name, slug: o.slug }));
    });
    head.appendChild(dl);

    var names = m.lines.map(function (l) { return l.pin.label; }).join(', ');
    var s = svg('svg', { viewBox: '0 0 1040 340', width: '100%', role: 'img', class: 'cmp-svg',
      'aria-label': 'Line chart: five-year averages in ' + unit + ', each compared with its own ' + own(base) + ', for ' + names + '. Highest at the latest year: ' + m.highest + '.' });
    var ytitle = fa.kind === 'percent' ? '% of the usual rain, compared with ' + base : unit + (o.window === 'water_storage' ? ' of water' : '') + ' compared with ' + base;
    s.appendChild(svg('text', { x: 0, y: 14, class: 'cmp-ytitle' }, ytitle));
    m.y.ticks.forEach(function (v) {
      var y = m.py(v);
      s.appendChild(svg('line', { x1: X0, x2: X1, y1: y.toFixed(1), y2: y.toFixed(1), class: v === 0 ? 'cmp-grid zero' : 'cmp-grid' }));
      s.appendChild(svg('text', { x: X0 - 10, y: (y + 4).toFixed(1), class: 'cmp-ax', 'text-anchor': 'end' }, signed(v, m.y.step)));
    });
    m.xTicks.forEach(function (t) {
      s.appendChild(svg('text', { x: m.px(t).toFixed(1), y: 330, class: 'cmp-ax', 'text-anchor': 'middle' }, String(t)));
    });
    // others first, selected last so it sits on top
    m.lines.slice().sort(function (a, b) { return (a.selected ? 1 : 0) - (b.selected ? 1 : 0); }).forEach(function (l) {
      var d = segments(l.pts, m.px, m.py);
      if (d) { var pth = svg('path', { d: d, class: 'cmp-line s' + slotCls(l) }); pth.appendChild(svg('title', {}, l.pin.label)); s.appendChild(pth); }
    });

    // legend (HTML, place keys only) in pin order, then the chart in a box that scrolls sideways on narrow screens
    var leg = h('div', 'cmp-legend');
    m.lines.forEach(function (l) {
      var b = h('button', 'cmp-key' + (l.selected ? ' on' : ''));
      b.type = 'button'; b.setAttribute('aria-pressed', l.selected ? 'true' : 'false');
      b.appendChild(h('i', 'cmp-sw s' + slotCls(l)));
      b.appendChild(document.createTextNode(l.pin.label));
      b.addEventListener('click', function () { P.select(l.pin.key); });
      leg.appendChild(b);
    });
    g.appendChild(leg);
    var sc = h('div', 'cmp-plot');
    sc.appendChild(s);
    g.appendChild(sc);
    leftOut(g, m.left);
    slot.replaceChildren(g);
  }

  function drawTable(slot, pins, o) {
    var P = window.TD, X = window.TDX, f = P.fmt || {}, box = h('div', 'cmp-table');
    box.appendChild(h('h3', 'cmp-h', 'Compare your places'));
    var selPin = (pins || []).filter(function (p) { return p.selected; })[0];
    var sw = selPin && selPin.status === 'ok' && selPin.trend && selPin.trend.world;
    if (sw) {
      var rp, u = sw.available && sw.source && httpsOnly(sw.source.record_url);
      if (sw.available) {
        rp = h('p', 'cmp-cap', 'World figure for ' + selPin.label + ': ' + (sw.text || ''));
        if (u) {
          var a = h('a', 'cmp-src', (sw.source.name || u) + ' ↗');
          a.href = u; a.target = '_blank'; a.rel = 'noopener';
          rp.appendChild(document.createTextNode(' Source: ')); rp.appendChild(a);
        }
      } else if (sw.why_none || sw.text) rp = h('p', 'cmp-cap', selPin.label + ': ' + (sw.why_none || sw.text));
      if (rp) box.appendChild(rp);
    }
    // each row's own window and world rate (windows differ from gauge to gauge)
    var cells = (pins || []).map(function (p) {
      var t = p.status === 'ok' && p.trend, g = t && t.guidance, wp = t && X.worldParts(t, o.imperial), clear = t && (t.verdict === 'rising' || t.verdict === 'falling');
      if (!t) return null;
      var name = t.place && t.place.name ? String(t.place.name).trim() : '';
      return {
        at: /[^\d\s.,;°+\-−NSEWnsew]/.test(name) ? name : (t.source && t.source.name) || '—',
        record: t.period && t.latest ? X.Y(t.period.start) + '–' + X.Mo(t.latest.month) : '—',
        rate: (f.rate && f.rate(t) && (clear || (g && g.risk_label))) ? f.rate(t) : 'No clear change',
        here: wp ? wp.here + ' ' + wp.since.toLowerCase() : '—',
        ratio: wp ? wp.ratio + ' (world ' + wp.world + ')' : '—',
        risk: g && g.risk_label ? g : null
      };
    });
    var hasW = cells.some(function (c) { return c && c.ratio !== '—'; }), hasRisk = cells.some(function (c) { return c && c.risk; });
    var cols = ['Place', 'Measured at', 'Record', 'Rate'].concat(hasW ? ['Here, same years', '× world, same years'] : [], hasRisk ? ['Risk'] : []);
    var wrap = h('div', 'cmp-scroll'), tbl = h('table', 'cmp-tbl'), thead = h('thead'), hr = h('tr');
    cols.forEach(function (c) { var th = h('th', null, c); th.scope = 'col'; hr.appendChild(th); });
    thead.appendChild(hr); tbl.appendChild(thead);
    var tb = h('tbody');
    (pins || []).forEach(function (p, i) {
      var tr = h('tr', p.selected ? 'on' : ''), c = cells[i];
      tr.tabIndex = 0; if (p.selected) tr.setAttribute('aria-current', 'true');
      tr.addEventListener('click', function () { P.select(p.key); });
      tr.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); P.select(p.key); }
      });
      var c0 = h('td'), dot = h('i', 'cmp-dot ' + (p.selected ? 'dsel' : 'd' + ((p.slot || 0) % 6)));
      dot.setAttribute('aria-hidden', 'true');
      c0.appendChild(dot); c0.appendChild(document.createTextNode(p.label)); tr.appendChild(c0);
      if (!c) {
        var cs = h('td', 'cmp-msg', p.status === 'error' ? (p.error || 'Could not load this place.') : 'Checking…');
        cs.colSpan = cols.length - 1; tr.appendChild(cs); tb.appendChild(tr); return;
      }
      tr.appendChild(h('td', null, c.at));
      tr.appendChild(h('td', 'n', c.record));
      tr.appendChild(h('td', 'n', c.rate));
      if (hasW) { tr.appendChild(h('td', 'w', c.here)); tr.appendChild(h('td', 'w', c.ratio)); }
      if (hasRisk) {
        var cr = h('td');
        if (c.risk) cr.appendChild(h('span', 'risk ' + (/^(high|moderate|low)$/.test(c.risk.risk) ? c.risk.risk : 'unknown'), c.risk.risk_label));
        else cr.textContent = '—';
        tr.appendChild(cr);
      }
      tb.appendChild(tr);
    });
    if (!(pins || []).length) {
      var er = h('tr'), ec = h('td', 'cmp-msg', 'No places yet. Search for a place or click the map.');
      ec.colSpan = cols.length; er.appendChild(ec); tb.appendChild(er);
    }
    tbl.appendChild(tb); wrap.appendChild(tbl); box.appendChild(wrap);
    slot.replaceChildren(box);
  }

  function render() {
    var P = window.TD;
    if (!P || P.window === 'settings' || !window.TDX) return;
    var prefs = (window.TDPrefs && window.TDPrefs.get()) || {}, w = (P.windows || []).filter(function (x) { return x.id === P.window; })[0] || {};
    var o = { window: P.window, imperial: prefs.units === 'imperial', name: w.name || '', slug: w.slug || P.window };
    var pins = P.pins() || [], a = document.getElementById('compare-chart-slot'), b = document.getElementById('compare-table-slot');
    try { if (a) drawChart(a, pins, o); } catch (e) { if (a) a.textContent = 'The chart could not be drawn.'; console.error(e); }
    try { if (b) drawTable(b, pins, o); } catch (e) { if (b) b.textContent = 'The table could not be drawn.'; console.error(e); }
  }

  function start() {
    ['td:pins', 'td:route', 'td:prefs'].forEach(function (n) { document.addEventListener(n, render); });
    render();
  }
  if (window.TD && window.TD.ready) window.TD.ready.then(start);
  else document.addEventListener('td:ready', start, { once: true });

  window.TDCompare = { yearly: yearly, smooth: smooth, niceTicks: niceTicks, buildModel: buildModel };
})();
