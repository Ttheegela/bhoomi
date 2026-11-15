'use strict';
/* Trend scene: a picture of the verdict, drawn under the evidence lines on the Explore tab.
   One small illustration per measurement (tide gauge on a pier, thermometer, rain gauge,
   ground cross-section), and year stripes under the chart.
   Rules: the picture shows direction only, never size (one fixed travel up or down).
   It never formats a data value: app.js passes the strings the answer card prints, and years
   come from the period. Motion plays once; nothing loops. Ink tokens only, no new colours.
   prefers-reduced-motion: the global CSS rule turns every transition and animation off. */

(function () {
  const NS = 'http://www.w3.org/2000/svg';
  // 268 units wide = the width the picture is shown at (see .sc-art), so 14 units of text is 14 px.
  const W = 268, H = 128;

  function s(tag, attrs, text) {
    const n = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([k, v]) => { if (v != null) n.setAttribute(k, String(v)); });
    if (text != null) n.textContent = text;
    return n;
  }
  function h(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => { if (v != null) n.setAttribute(k, String(v)); });
    kids.forEach((k) => n.append(k));
    return n;
  }

  // Which picture: by variable id.
  function kindOf(v) {
    if (v === 'sea_level') return 'sea';
    if (v === 'air_temp' || v === 'air_temp_max') return 'heat';
    if (v === 'precip') return 'rain';
    if (v === 'water_storage') return 'ground';
    return 'gauge';
  }

  // Illustrative levels (SVG y, smaller is higher): one small fixed travel either way, so the picture
  // shows direction and never size, and no column nears empty or full.
  const MID = 64, TRAVEL = 24;
  function levels(t) {
    if (t.verdict === 'rising') return { y0: MID, y1: MID - TRAVEL, clear: true };
    if (t.verdict === 'falling') return { y0: MID, y1: MID + TRAVEL, clear: true };
    return { y0: MID, y1: MID, clear: false };
  }

  // A still wave path, wavelength 40.
  function wavePath(y, amp, x0, x1, bottom) {
    let d = `M${x0} ${y}`;
    for (let x = x0; x < x1; x += 40) d += ` q10 ${-amp} 20 0 t20 0`;
    return bottom != null ? d + ` V${bottom} H${x0} Z` : d;
  }

  function ghostLine(g, x0, x1, y, label) {
    g.append(s('line', { x1: x0, y1: y, x2: x1, y2: y, class: 'sc-ghost' }));
    g.append(s('text', { x: x0, y: y - 5, class: 'sc-yr' }, label));
  }

  function arrow(g, x, ya, yb) {
    if (Math.abs(yb - ya) < 8) return;
    const dir = yb < ya ? -1 : 1;
    g.append(s('line', { x1: x, y1: ya, x2: x, y2: yb - dir * 6, class: 'sc-arrow' }));
    g.append(s('polygon', { points: `${x - 5},${yb - dir * 7} ${x + 5},${yb - dir * 7} ${x},${yb}`, class: 'sc-ink' }));
  }

  // The level label and the arrow, both beside the new level.
  function nowMark(g, xLabel, xArrow, L, y1txt) {
    g.append(s('text', { x: xLabel, y: L.y1 + 5, class: 'sc-yr sc-now' }, y1txt));
    if (xArrow != null) arrow(g, xArrow, L.y0, L.y1 + (L.y1 < L.y0 ? 4 : -4));
  }

  // Group that moves from the first year's level to the last: drawn at the last level,
  // started shifted, then released so the CSS transition carries it home.
  function mover(y0, y1) {
    const g = s('g', { class: 'sc-move' });
    g.dataset.from = String(y0 - y1);
    return g;
  }

  /* ---------- the four pictures ---------- */

  function sea(root, L, y0txt, y1txt) {
    // Pier deck and pilings, with a tide staff on the front piling.
    root.append(s('rect', { x: 110, y: 8, width: 158, height: 8, class: 'sc-ink' }));
    [120, 256].forEach((x) => root.append(s('rect', { x, y: 16, width: 8, height: H - 16, class: 'sc-soft' })));
    root.append(s('rect', { x: 170, y: 16, width: 18, height: H - 16, class: 'sc-staff' }));
    for (let y = 24, i = 0; y < H; y += 8, i++) {
      root.append(s('line', { x1: 170, y1: y, x2: i % 2 ? 178 : 184, y2: y, class: 'sc-tick' }));
    }
    const m = mover(L.y0, L.y1);
    m.append(s('path', { d: wavePath(L.y1, 5, 0, W, H), class: 'sc-water' }));
    m.append(s('path', { d: wavePath(L.y1, 5, 0, W), class: 'sc-surf' }));
    root.append(m);
    root.append(s('line', { x1: 0, y1: H - 1, x2: W, y2: H - 1, class: 'sc-hair' }));
    ghostLine(root, 4, 166, L.y0, y0txt);
    nowMark(root, 222, 212, L, y1txt);
  }

  function heat(root, L, y0txt, y1txt, hottest) {
    // A small sun for the hottest-day measure, and a thermometer whose column moves.
    if (hottest) {
      const sun = s('g', {});
      sun.append(s('circle', { cx: 20, cy: 24, r: 8, class: 'sc-ink' }));
      for (let i = 0; i < 12; i++) {
        const a = (i * Math.PI) / 6, c = Math.cos(a), sn = Math.sin(a);
        sun.append(s('line', { x1: 20 + 11 * c, y1: 24 + 11 * sn, x2: 20 + 15 * c, y2: 24 + 15 * sn, class: 'sc-ray' }));
      }
      root.append(sun);
    }
    const x = 150;
    root.append(s('rect', { x: x - 11, y: 8, width: 22, height: 92, rx: 11, class: 'sc-glass' }));
    root.append(s('circle', { cx: x, cy: 110, r: 16, class: 'sc-glass' }));
    for (let y = 24, i = 0; y <= 92; y += 10, i++) {
      root.append(s('line', { x1: x + 14, y1: y, x2: x + (i % 2 ? 20 : 26), y2: y, class: 'sc-tick' }));
    }
    root.append(s('circle', { cx: x, cy: 110, r: 11, class: 'sc-ink' }));
    const clip = s('clipPath', { id: 'sc-tube' });
    clip.append(s('rect', { x: x - 6, y: 12, width: 12, height: 100, rx: 6 }));
    root.append(clip);
    const col = s('g', { 'clip-path': 'url(#sc-tube)' });
    const m = mover(L.y0, L.y1);
    m.append(s('rect', { x: x - 6, y: L.y1, width: 12, height: 200, class: 'sc-ink' }));
    col.append(m);
    root.append(col);
    ghostLine(root, 4, x - 14, L.y0, y0txt);
    nowMark(root, x + 32, x + 86, L, y1txt);
  }

  function rain(root, L, y0txt, y1txt) {
    // A cloud, still drops, and a rain gauge that fills to the level.
    const cloud = s('g', { class: 'sc-cloud' });
    [[50, 24, 14], [72, 18, 17], [94, 24, 14], [72, 30, 15]].forEach(([cx, cy, r]) => cloud.append(s('circle', { cx, cy, r, class: 'sc-ink' })));
    root.append(cloud);
    for (let i = 0; i < 12; i++) {
      const dx = 44 + (i * 37) % 70, dy = 50 + (i * 23) % 60;
      root.append(s('line', { x1: dx, y1: dy, x2: dx - 3, y2: dy + 10, class: 'sc-drop' }));
    }
    const x0 = 140, x1 = 190;
    root.append(s('path', { d: `M${x0 - 14} 10 L${x0} 28 L${x1} 28 L${x1 + 14} 10`, class: 'sc-glass-line' }));
    const clip = s('clipPath', { id: 'sc-cyl' });
    clip.append(s('rect', { x: x0, y: 28, width: x1 - x0, height: H - 32 }));
    root.append(clip);
    const g = s('g', { 'clip-path': 'url(#sc-cyl)' });
    const m = mover(L.y0, L.y1);
    m.append(s('path', { d: wavePath(L.y1, 3, x0, x1 + 30, H), class: 'sc-water' }));
    m.append(s('path', { d: wavePath(L.y1, 3, x0, x1 + 30), class: 'sc-surf' }));
    g.append(m);
    root.append(g);
    root.append(s('rect', { x: x0, y: 28, width: x1 - x0, height: H - 32, class: 'sc-glass-line' }));
    for (let y = 40, i = 0; y < H - 6; y += 10, i++) {
      root.append(s('line', { x1: x1, y1: y, x2: x1 - (i % 2 ? 6 : 12), y2: y, class: 'sc-tick' }));
    }
    ghostLine(root, 4, x0 - 4, L.y0, y0txt);
    nowMark(root, x1 + 10, x1 + 60, L, y1txt);
  }

  function ground(root, L, y0txt, y1txt) {
    // Cross-section: sky, a field and a tree on the surface, soil, and the water held in the land below.
    const top = 36;
    root.append(s('path', { d: `M180 ${top} V${top - 14}`, class: 'sc-trunk' }));
    root.append(s('circle', { cx: 180, cy: top - 22, r: 10, class: 'sc-soft' }));
    for (let x = 4; x < 160; x += 12) root.append(s('path', { d: `M${x} ${top} l3 -7 l3 7`, class: 'sc-grass' }));
    const defs = s('defs', {});
    const p = s('pattern', { id: 'sc-soil', width: 10, height: 10, patternUnits: 'userSpaceOnUse' });
    p.append(s('circle', { cx: 2, cy: 3, r: 1, class: 'sc-ink' }));
    p.append(s('circle', { cx: 7, cy: 8, r: 1, class: 'sc-ink' }));
    defs.append(p);
    root.append(defs);
    root.append(s('rect', { x: 0, y: top, width: W, height: H - top, fill: 'url(#sc-soil)', class: 'sc-soilfill' }));
    const clip = s('clipPath', { id: 'sc-earth' });
    clip.append(s('rect', { x: 0, y: top + 2, width: W, height: H - top }));
    root.append(clip);
    const g = s('g', { 'clip-path': 'url(#sc-earth)' });
    const m = mover(L.y0, L.y1);
    m.append(s('path', { d: wavePath(L.y1, 2, 0, W, H + 60), class: 'sc-water sc-deep' }));
    m.append(s('path', { d: wavePath(L.y1, 2, 0, W), class: 'sc-surf' }));
    g.append(m);
    root.append(g);
    root.append(s('line', { x1: 0, y1: top, x2: W, y2: top, class: 'sc-surface' }));
    ghostLine(root, 4, 200, L.y0, y0txt);
    nowMark(root, 218, 254, L, y1txt);
  }

  function gauge(root, L, y0txt, y1txt) {
    root.append(s('rect', { x: 114, y: 16, width: 40, height: H - 20, class: 'sc-glass-line' }));
    const m = mover(L.y0, L.y1);
    m.append(s('rect', { x: 114, y: L.y1, width: 40, height: 200, class: 'sc-water' }));
    root.append(m);
    ghostLine(root, 4, 110, L.y0, y0txt);
    nowMark(root, 164, null, L, y1txt);
  }

  /* ---------- year stripes (under the chart) ---------- */

  // The one place the stripe shading is decided: k runs from 0 (lowest year) to 1 (highest).
  // Ink at a fill opacity, so the palette can replace this with one small change.
  function shade(k) { return (0.06 + 0.88 * k).toFixed(3); }

  // mount: #stripes-art. years: [{year, mean}] (drawing only). period: t.period (the printed years).
  window.renderStripes = function renderStripes(mount, years, period) {
    while (mount.firstChild) mount.removeChild(mount.firstChild);
    const box = mount.parentNode;
    if (!years || years.length < 3 || !period) { box.hidden = true; return; }
    const lo = Math.min(...years.map((y) => y.mean)), hi = Math.max(...years.map((y) => y.mean));
    const n = years.length, sw = 300 / n;
    const sv = s('svg', { viewBox: '0 0 300 28', class: 'sc-stripes', 'aria-hidden': 'true', focusable: 'false', preserveAspectRatio: 'none' });
    years.forEach((y, i) => {
      const k = hi > lo ? (y.mean - lo) / (hi - lo) : 0.5;
      const r = s('rect', { x: (i * sw).toFixed(2), y: 0, width: (sw + 0.6).toFixed(2), height: 28, class: 'sc-stripe', 'fill-opacity': shade(k) });
      r.style.animationDelay = `${Math.round((i / n) * 900)}ms`;
      sv.append(r);
    });
    const swatch = (k) => {
      const q = s('svg', { width: 20, height: 14, class: 'sc-sw', 'aria-hidden': 'true', focusable: 'false' });
      q.append(s('rect', { width: 20, height: 14, rx: 2, class: 'sc-stripe-key', 'fill-opacity': shade(k) }));
      return q;
    };
    mount.append(
      sv,
      h('div', { class: 'sc-ends' }, h('span', {}, period.start.slice(0, 4)), h('span', {}, period.end.slice(0, 4))),
      h('ul', { class: 'sc-key' }, h('li', {}, swatch(0), 'lower year'), h('li', {}, swatch(1), 'higher year')),
    );
    box.hidden = false;
  };

  /* ---------- the picture ---------- */

  const ALT = {
    sea: (up, down) => up ? 'the water stands higher on the pier' : down ? 'the water stands lower on the pier' : 'the water sits at about the same mark',
    heat: (up, down) => up ? 'the thermometer reads higher' : down ? 'the thermometer reads lower' : 'the thermometer reads about the same',
    rain: (up, down) => up ? 'the rain gauge fills higher' : down ? 'the rain gauge fills lower' : 'the rain gauge fills to about the same mark',
    ground: (up, down) => up ? 'the land holds more water' : down ? 'the land holds less water' : 'the land holds about the same water',
    gauge: (up, down) => up ? 'the level is higher' : down ? 'the level is lower' : 'the level is about the same',
  };

  function play(fig) {
    fig.querySelectorAll('.sc-move').forEach((g) => {
      g.classList.remove('go');
      g.style.transform = `translateY(${g.dataset.from}px)`;
    });
    void fig.getBoundingClientRect();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      fig.querySelectorAll('.sc-move').forEach((g) => { g.classList.add('go'); g.style.transform = ''; });
    }));
  }

  // t: TrendResult from the API. text: strings app.js already prints on the card:
  // { place, name, slope, range } (slope and range are the card's own text, used unchanged).
  window.renderScene = function renderScene(mount, t, text) {
    while (mount.firstChild) mount.removeChild(mount.firstChild);
    if (!t || !t.period) { mount.hidden = true; return; }
    const kind = kindOf(t.variable);
    const L = levels(t);
    const y0 = t.period.start.slice(0, 4), y1 = t.period.end.slice(0, 4);
    const up = t.verdict === 'rising', down = t.verdict === 'falling';

    const fig = h('figure', { class: `scene sc-${kind}${L.clear ? '' : ' sc-flat'}` });
    const sv = s('svg', { viewBox: `0 0 ${W} ${H}`, class: 'sc-art', role: 'img', focusable: 'false' });
    const label = `Illustration, direction only, not size: ${ALT[kind](up, down)} in ${y1} ${up || down ? 'than' : 'as'} in ${y0}. ` +
      `${text.name} at ${text.place}: ${text.slope} per decade, range ${text.range} per decade.`;
    sv.append(s('title', {}, label));
    const root = s('g', {});
    sv.append(root);

    if (!L.clear) {
      // The band the data support, drawn around the level, which rests inside it.
      root.append(s('rect', { x: 0, y: MID - 16, width: W, height: 32, class: 'sc-band' }));
    }
    ({ sea, heat: (r, l, a, b) => heat(r, l, a, b, t.variable === 'air_temp_max'), rain, ground, gauge })[kind](root, L, y0, y1);

    const tag = h('p', { class: 'sc-tag' },
      h('span', { class: 'sc-tag-n' }, text.name), ` · ${y0} → ${y1}`,
      L.clear ? '' : h('span', { class: 'sc-tag-q' }, ' · no clear change'));
    const replay = h('button', { type: 'button', class: 'btn sc-replay' }, 'Play again');
    replay.addEventListener('click', () => play(fig));
    const head = h('div', { class: 'sc-head' }, tag, replay);

    fig.append(head, sv);
    fig.append(h('figcaption', { class: 'source' },
      L.clear ? 'Picture shows direction only, not size. The number is the trend we calculated from the source above.'
        : 'Picture shows direction only, not size. The level rests inside the shaded band: any change here is too small or too noisy to call.'));
    mount.append(fig);
    mount.hidden = false;
    play(fig);
  };
})();
