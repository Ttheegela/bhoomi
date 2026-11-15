// Compare: comparison chart card + comparison table card (rework contract, section 5).
// Pure helpers (yearly, smooth, baseline, convert, niceTicks, stack, buildModel) take plain data;
// everything under "DOM" talks to TD / TDPrefs and draws with textContent only.
(function () {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';
  var X0 = 56, X1 = 890, Y0 = 20, Y1 = 304;           // plot area, as the mock
  var HEADS = {
    sea_level: 'the sea', air_temp: 'air temperature', air_temp_max: 'the hottest days',
    precip: 'rain', water_storage: 'water storage'
  };

  // ---------- pure helpers ----------

  // Yearly mean of a TimeSeries; a year needs enough periods (9 of 12 months). -> {year: mean}
  function yearly(series) {
    var out = {}, sum = {}, cnt = {};
    if (!series || !series.times || !series.values) return out;
    var need = series.freq === 'monthly' ? 9 : series.freq === 'daily' ? 270 : 1;
    series.times.forEach(function (t, i) {
      var v = series.values[i], y = parseInt(String(t).slice(0, 4), 10);
      if (typeof v !== 'number' || !isFinite(v) || !isFinite(y)) return;
      sum[y] = (sum[y] || 0) + v; cnt[y] = (cnt[y] || 0) + 1;
    });
    Object.keys(cnt).forEach(function (y) { if (cnt[y] >= need) out[y] = sum[y] / cnt[y]; });
    return out;
  }

  // Centred 5-year average, needs 3 of the 5 years. -> [{year, v}] ascending (gaps = missing years)
  function smooth(ym) {
    var pts = [];
    Object.keys(ym).map(Number).sort(function (a, b) { return a - b; }).forEach(function (y) {
      var s = 0, n = 0;
      for (var k = y - 2; k <= y + 2; k++) if (ym[k] !== undefined) { s += ym[k]; n++; }
      if (n >= 3) pts.push({ year: y, v: s / n });
    });
    return pts;
  }

  // The place's own 2000-2009 mean; fewer than 5 such years -> its first 10 years. -> {value, fallback}
  function baseline(ym) {
    var ys = Object.keys(ym).map(Number).sort(function (a, b) { return a - b; });
    if (!ys.length) return null;
    var pick = ys.filter(function (y) { return y >= 2000 && y <= 2009; }), fb = false;
    if (pick.length < 5) { pick = ys.filter(function (y) { return y < ys[0] + 10; }); fb = true; }
    var s = 0;
    pick.forEach(function (y) { s += ym[y]; });
    return { value: s / pick.length, fallback: fb };
  }

  // Unit setting applied to a change value: cm/mm -> in, degC -> degF (a change, so x1.8 only).
  function convert(v, unit, units) {
    if (units !== 'imperial') return v;
    var u = String(unit || '');
    if (u === 'cm') return v / 2.54;
    if (u === 'mm') return v / 25.4;
    if (/°?C$/.test(u)) return v * 1.8;
    return v;
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

  function signed(v, step) {
    var d = step >= 1 ? 0 : Math.min(3, Math.ceil(-Math.log10(step) - 1e-9));
    var s = Math.abs(v).toFixed(d);
    return (v < 0 && Number(s) !== 0 ? '-' : '+') + s;
  }

  // Direct labels: sort by y, push apart to >= gap, keep inside [min, max]. items: [{y}] -> adds .ly
  function stack(items, gap, min, max) {
    var a = items.slice().sort(function (p, q) { return p.y - q.y; }), i;
    a.forEach(function (it) { it.ly = Math.min(Math.max(it.y, min), max); });
    for (i = 1; i < a.length; i++) a[i].ly = Math.max(a[i].ly, a[i - 1].ly + gap);
    if (a.length && a[a.length - 1].ly > max) {
      a[a.length - 1].ly = max;
      for (i = a.length - 2; i >= 0; i--) a[i].ly = Math.min(a[i].ly, a[i + 1].ly - gap);
    }
    return a;
  }

  function shortName(label) {
    var s = String(label || '').split(',')[0].trim();
    return s.length > 18 ? s.slice(0, 17) + '…' : s;
  }

  function todayYear(now) {
    var d = now || new Date(), y = d.getFullYear();
    return y + (d - new Date(y, 0, 1)) / (365.25 * 864e5);
  }

  // Everything the chart needs, from plain data. pins: [{label, slot, selected, status, trend, series}]
  function buildModel(pins, o) {
    var units = o.units, la = o.lookAhead, lines = [], out = { left: [], fallback: [], lines: lines };
    (pins || []).forEach(function (p) {
      if (p.status === 'loading' || (!p.status && !p.series)) { out.left.push({ label: p.label, why: 'still loading' }); return; }
      if (p.status === 'error') { out.left.push({ label: p.label, why: 'could not be loaded' }); return; }
      var ym = yearly(p.series), pts = smooth(ym), base = baseline(ym);
      if (!pts.length || !base) { out.left.push({ label: p.label, why: 'has too little data' }); return; }
      var g = p.trend && p.trend.guidance, d = (g && g.display) || {};
      var f = typeof d.factor === 'number' ? d.factor : 1, du = d.unit || (p.series && p.series.units) || '';
      var line = {
        pin: p, slot: p.slot || 0, selected: !!p.selected, unit: du,
        pts: pts.map(function (q) { return { year: q.year, v: convert((q.v - base.value) * f, du, units) }; })
      };
      if (base.fallback) out.fallback.push(p.label);
      var last = line.pts[line.pts.length - 1], oe = null;
      ((g && g.outlook) || []).forEach(function (e) { if (e && e.year === la) oe = e; });
      if (line.selected && oe && typeof oe.low === 'number' && typeof oe.high === 'number' && la > last.year) {
        line.wedge = {
          year: la, label: g.outlook_label || '',
          lo: last.v + convert(oe.low, oe.unit || du, units), hi: last.v + convert(oe.high, oe.unit || du, units)
        };
      }
      lines.push(line);
    });
    if (!lines.length) return out;
    var minY = Infinity, minV = Infinity, maxV = -Infinity;
    lines.forEach(function (l) {
      minY = Math.min(minY, l.pts[0].year);
      l.pts.forEach(function (q) { minV = Math.min(minV, q.v); maxV = Math.max(maxV, q.v); });
      if (l.wedge) { minV = Math.min(minV, l.wedge.lo); maxV = Math.max(maxV, l.wedge.hi); }
    });
    var lastYear = Math.max.apply(null, lines.map(function (l) { return l.pts[l.pts.length - 1].year; }));
    out.xMin = minY; out.xMax = Math.max(la, lastYear + 1);
    out.y = niceTicks(minV, maxV);
    out.xTicks = [];
    for (var t = Math.ceil(out.xMin / 25) * 25; t <= out.xMax; t += 25) out.xTicks.push(t);
    out.unit = lines[0].unit;
    var span = out.xMax - out.xMin || 1, ys = out.y.hi - out.y.lo || 1;
    out.px = function (yr) { return X0 + (yr - out.xMin) / span * (X1 - X0); };
    out.py = function (v) { return Y1 - (v - out.y.lo) / ys * (Y1 - Y0); };
    out.today = todayYear(o.now);
    var hi = lines[0];
    lines.forEach(function (l) { if (l.pts[l.pts.length - 1].v > hi.pts[hi.pts.length - 1].v) hi = l; });
    out.highest = hi.pin.label;
    return out;
  }

  function describe(model, unitLabel) {
    var names = model.lines.map(function (l) { return l.pin.label; }).join(', ');
    return 'Line chart: five-year average change in ' + unitLabel + ' for ' + names +
      '. Highest at the latest year: ' + model.highest + '.';
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

  function leftOut(g, left) {
    if (!left.length) return;
    g.appendChild(h('p', 'cmp-left', 'Left out of the chart: ' +
      left.map(function (x) { return x.label + ' (' + x.why + ')'; }).join('; ') + '.'));
  }

  function drawChart(slot, pins, o) {
    var P = window.TD, g = h('div', 'cmp-chart');
    g.appendChild(h('h3', 'cmp-h', 'How ' + (HEADS[o.window] || 'things') + ' has changed at your places'));
    var m = buildModel(pins, o);
    if (!m.lines.length) {
      g.appendChild(h('p', 'cmp-cap', m.left.length ? 'Waiting for the records to arrive.' : 'Add a place to see how it compares.'));
      leftOut(g, m.left);
      slot.replaceChildren(g);
      return;
    }
    var selLine = m.lines.filter(function (l) { return l.selected; })[0] || null, wedge = selLine && selLine.wedge;
    var unitLabel = (P && P.fmt && P.fmt.unit && selLine && P.fmt.unit(selLine.pin.trend)) || m.unit || 'the unit shown';
    var cap = 'Five-year average, in ' + unitLabel + ', compared with each place’s 2000–2009 level.';
    m.fallback.forEach(function (n) { cap += ' ' + n + ': compared with its first 10 years instead (no records for 2000–2009).'; });
    if (wedge) cap += ' The shaded wedge shows where ' + selLine.pin.label + ' would be if its past trend simply continued.';
    g.appendChild(h('p', 'cmp-cap', cap));

    var s = svg('svg', { viewBox: '0 0 1040 340', width: '100%', role: 'img', 'aria-label': describe(m, unitLabel), class: 'cmp-svg' });
    var defs = svg('defs'), cp = svg('clipPath', { id: 'cmp-clip' });
    cp.appendChild(svg('rect', { x: X0, y: Y0, width: X1 - X0, height: Y1 - Y0 }));
    defs.appendChild(cp); s.appendChild(defs);

    m.y.ticks.forEach(function (v) {
      var y = m.py(v);
      s.appendChild(svg('line', { x1: X0, x2: X1, y1: y.toFixed(1), y2: y.toFixed(1), class: v === 0 ? 'cmp-grid zero' : 'cmp-grid' }));
      s.appendChild(svg('text', { x: X0 - 10, y: (y + 4).toFixed(1), class: 'cmp-ax', 'text-anchor': 'end' }, signed(v, m.y.step)));
    });
    m.xTicks.forEach(function (t) {
      s.appendChild(svg('text', { x: m.px(t).toFixed(1), y: 324, class: 'cmp-ax', 'text-anchor': 'middle' }, String(t)));
    });
    if (m.today >= m.xMin && m.today <= m.xMax) {
      var tx = m.px(m.today);
      s.appendChild(svg('line', { x1: tx.toFixed(1), x2: tx.toFixed(1), y1: Y0, y2: Y1, class: 'cmp-today' }));
      s.appendChild(svg('text', { x: (tx - 6).toFixed(1), y: 296, class: 'cmp-ax', 'text-anchor': 'end' }, 'today'));
    }

    var clip = svg('g', { 'clip-path': 'url(#cmp-clip)' }), lp = null;
    if (wedge) {
      lp = selLine.pts[selLine.pts.length - 1];
      var sx = m.px(lp.year).toFixed(1), sy = m.py(lp.v).toFixed(1), ex = m.px(wedge.year).toFixed(1);
      clip.appendChild(svg('path', {
        d: 'M' + sx + ',' + sy + ' L' + ex + ',' + m.py(wedge.hi).toFixed(1) + ' L' + ex + ',' + m.py(wedge.lo).toFixed(1) + ' Z',
        class: 'cmp-wedge'
      }));
    }
    // others first, selected last so it sits on top
    m.lines.slice().sort(function (a, b) { return (a.selected ? 1 : 0) - (b.selected ? 1 : 0); }).forEach(function (l) {
      var d = segments(l.pts, m.px, m.py);
      if (d) clip.appendChild(svg('path', { d: d, class: 'cmp-line s' + slotCls(l) }));
    });
    if (wedge) {
      clip.appendChild(svg('path', {
        d: 'M' + m.px(lp.year).toFixed(1) + ',' + m.py(lp.v).toFixed(1) + ' L' + m.px(wedge.year).toFixed(1) + ',' +
          m.py((wedge.lo + wedge.hi) / 2).toFixed(1), class: 'cmp-centre'
      }));
    }
    s.appendChild(clip);

    // direct labels: line ends plus the wedge label, stacked so none overlap
    var items = [];
    m.lines.forEach(function (l) {
      var e = l.pts[l.pts.length - 1], x, y;
      if (l === selLine && wedge) { x = X1 + 6; y = m.py((wedge.lo + wedge.hi) / 2) + 4; }
      else { x = m.px(e.year) + 6; y = m.py(e.v) + 4; }
      items.push({
        x: x, y: y, text: shortName(l.pin.label), full: l.pin.label, ax: m.px(e.year), ay: m.py(e.v),
        cls: 'cmp-dl t' + slotCls(l) + (l.selected ? ' b' : '')
      });
    });
    var placed = stack(items, 15, Y0 + 8, Y1 - 4);
    if (wedge && wedge.label) {
      // 60 % of the way to the look-ahead year, 6 px above the wedge's upper edge; up past any line-end label, else below the lower edge
      var wx = m.px(lp.year) + 0.6 * (m.px(wedge.year) - m.px(lp.year)), w = wedge.label.length * 6.6;
      var edge = function (v) { return m.py(lp.v) + 0.6 * (m.py(v) - m.py(lp.v)); };
      var hit = function (y) {
        return placed.some(function (it) {
          var iw = it.text.length * 7;
          return wx - w / 2 < it.x + iw && it.x < wx + w / 2 && y - 12 < it.ly + 4 && it.ly - 12 < y + 3;
        });
      };
      var wy = edge(wedge.hi) - 6;
      while (hit(wy) && wy - 4 - 12 >= Y0) wy -= 4;
      if (hit(wy) || wy - 12 < Y0) wy = edge(wedge.lo) + 18;
      s.appendChild(svg('text', { x: wx.toFixed(1), y: wy.toFixed(1), class: 'cmp-pl', 'text-anchor': 'middle' }, wedge.label));
    }
    placed.forEach(function (it) {
      if (it.ax != null && Math.abs(it.ly - it.y) > 6) {
        s.appendChild(svg('line', { x1: it.ax.toFixed(1), y1: it.ay.toFixed(1), x2: (it.x - 2).toFixed(1), y2: (it.ly - 4).toFixed(1), class: 'cmp-lead' }));
      }
      var t = svg('text', { x: it.x.toFixed(1), y: it.ly.toFixed(1), class: it.cls }, it.text);
      if (it.full) t.appendChild(svg('title', {}, it.full));
      s.appendChild(t);
    });
    g.appendChild(s);
    leftOut(g, m.left);
    slot.replaceChildren(g);
  }

  function dash(td, text) { td.textContent = text || '—'; return td; }

  function drawTable(slot, pins, o) {
    var P = window.TD, f = P.fmt || {}, box = h('div', 'cmp-table');
    box.appendChild(h('h3', 'cmp-h', 'Compare your places'));
    var selPin = (pins || []).filter(function (p) { return p.selected; })[0];
    var ref = selPin && selPin.trend && selPin.trend.guidance && selPin.trend.guidance.reference;
    if (ref && ref.text) {
      var rp = h('p', 'cmp-cap', ref.text), u = ref.source && httpsOnly(ref.source.url);
      if (u) {
        var a = h('a', 'cmp-src', ref.source.name || u);
        a.href = u; a.target = '_blank'; a.rel = 'noopener';
        rp.appendChild(document.createTextNode(' Source: ')); rp.appendChild(a);
      }
      box.appendChild(rp);
    }
    var wrap = h('div', 'cmp-scroll'), tbl = h('table', 'cmp-tbl'), thead = h('thead'), hr = h('tr');
    var hasRatio = (pins || []).some(function (p) { return p.trend && p.trend.guidance && typeof p.trend.guidance.ratio === 'number'; });
    ['Place', 'Measured at', 'Record', 'Change per 10 years', hasRatio && 'vs world average', 'Risk', 'By ' + o.lookAhead + ' if the trend continues']
      .filter(Boolean).forEach(function (c) { var th = h('th', null, c); th.scope = 'col'; hr.appendChild(th); });
    thead.appendChild(hr); tbl.appendChild(thead);
    var tb = h('tbody');
    (pins || []).forEach(function (p) {
      var tr = h('tr', p.selected ? 'on' : ''), t = p.trend, g = t && t.guidance;
      tr.tabIndex = 0; tr.setAttribute('aria-selected', p.selected ? 'true' : 'false');
      tr.addEventListener('click', function () { P.select(p.key); });
      tr.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); P.select(p.key); }
      });
      var c0 = h('td'), dot = h('i', 'cmp-dot ' + (p.selected ? 'dsel' : 'd' + ((p.slot || 0) % 6)));
      dot.setAttribute('aria-hidden', 'true');
      c0.appendChild(dot); c0.appendChild(document.createTextNode(p.label)); tr.appendChild(c0);
      if (p.status !== 'ok' || !t) {
        var cs = h('td', 'cmp-msg', p.status === 'error' ? (p.error || 'Could not load this place.') : 'Checking…');
        cs.colSpan = hasRatio ? 6 : 5; tr.appendChild(cs); tb.appendChild(tr); return;
      }
      var name = t.place && t.place.name ? String(t.place.name).trim() : '', lab = String(p.label).trim().toLowerCase();
      tr.appendChild(dash(h('td'), /[^\d\s.,;°+\-−NSEWnsew]/.test(name) ? name : (t.source && t.source.name)));
      tr.appendChild(dash(h('td', 'n'), f.years && f.years(t)));
      tr.appendChild(h('td', 'n', (f.rate && f.rate(t)) || 'No clear change'));
      if (hasRatio) tr.appendChild(dash(h('td', 'n'), g && typeof g.ratio === 'number' ? g.ratio.toFixed(1) + '×' : ''));
      var cr = h('td');
      if (g && g.risk_label) cr.appendChild(h('span', 'risk ' + (/^(high|moderate|low|unknown)$/.test(g.risk) ? g.risk : 'unknown'), g.risk_label));
      else cr.textContent = '—';
      tr.appendChild(cr);
      tr.appendChild(dash(h('td', 'n'), f.outlook && f.outlook(t, o.lookAhead)));
      tb.appendChild(tr);
    });
    if (!(pins || []).length) {
      var er = h('tr'), ec = h('td', 'cmp-msg', 'No places yet. Search for a place or click the map.');
      ec.colSpan = hasRatio ? 7 : 6; er.appendChild(ec); tb.appendChild(er);
    }
    tbl.appendChild(tb); wrap.appendChild(tbl); box.appendChild(wrap);
    slot.replaceChildren(box);
  }

  function render() {
    var P = window.TD;
    if (!P || P.window === 'settings') return;
    var prefs = (window.TDPrefs && window.TDPrefs.get()) || {};
    var o = { window: P.window, units: prefs.units || 'metric', lookAhead: prefs.lookAhead || 2050 };
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

  window.TDCompare = { yearly: yearly, smooth: smooth, baseline: baseline, convert: convert, niceTicks: niceTicks, stack: stack, buildModel: buildModel };
})();
