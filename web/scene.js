'use strict';
/* Trend scene: a picture of the verdict, drawn under the big number on the Explore tab.
   One small illustration per measurement (tide gauge on a pier, thermometer, rain gauge,
   ground cross-section), plus year stripes from the yearly averages.
   Rules kept from app.js: printed numbers come from the API only (slope, range, years);
   heights in the picture are illustrative, never measured. Ink tokens only, no new colours.
   prefers-reduced-motion: the global CSS rule turns every transition and animation off. */

(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const W = 320, H = 176;
  const MINUS = '−';

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
  function num(x) {
    const a = Math.abs(x), d = a >= 100 ? 0 : a >= 10 ? 1 : 2;
    const t = a.toFixed(d);
    return (x < 0 ? MINUS : x > 0 ? '+' : '') + t;
  }
  function unit(u) { return u === 'degC' ? '°C' : u; }

  // Which picture: by variable id.
  function kindOf(v) {
    if (v === 'sea_level') return 'sea';
    if (v === 'air_temp' || v === 'air_temp_max') return 'heat';
    if (v === 'precip') return 'rain';
    if (v === 'water_storage') return 'ground';
    return 'gauge';
  }

  // Illustrative levels (SVG y, smaller is higher). Same for every picture so they read alike.
  const MID = 104, RISE = 50, FALL = 146;
  function levels(t) {
    if (t.verdict === 'rising') return { y0: MID, y1: RISE, clear: true };
    if (t.verdict === 'falling') return { y0: MID, y1: FALL, clear: true };
    return { y0: MID, y1: MID, clear: false };
  }

  // A periodic wave path, wavelength 40, wide enough to slide left by one wavelength forever.
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
    root.append(s('rect', { x: 150, y: 10, width: 170, height: 8, class: 'sc-ink' }));
    [176, 300].forEach((x) => root.append(s('rect', { x, y: 18, width: 8, height: H - 18, class: 'sc-soft' })));
    root.append(s('rect', { x: 226, y: 18, width: 18, height: H - 18, class: 'sc-staff' }));
    for (let y = 26, i = 0; y < H; y += 8, i++) {
      root.append(s('line', { x1: 226, y1: y, x2: i % 2 ? 234 : 240, y2: y, class: 'sc-tick' }));
    }
    const m = mover(L.y0, L.y1);
    const waves = s('g', { class: 'sc-wave' });
    waves.append(s('path', { d: wavePath(L.y1, 5, -40, W + 40, H), class: 'sc-water' }));
    waves.append(s('path', { d: wavePath(L.y1, 5, -40, W + 40), class: 'sc-surf' }));
    m.append(waves);
    root.append(m);
    root.append(s('line', { x1: 0, y1: H - 1, x2: W, y2: H - 1, class: 'sc-hair' }));
    ghostLine(root, 12, 220, L.y0, y0txt);
    root.append(s('text', { x: 252, y: L.y1 - 9, class: 'sc-yr sc-now' }, y1txt));
    arrow(root, 268, L.y0, L.y1 + (L.y1 < L.y0 ? 4 : -4));
  }

  function heat(root, L, y0txt, y1txt, hottest) {
    // Skyline, a sun for the hottest-day measure, and a thermometer whose column moves.
    const sky = [[8, 120, 26], [36, 96, 22], [60, 132, 30], [92, 108, 18], [112, 140, 26], [140, 116, 20]];
    sky.forEach(([x, y, w]) => root.append(s('rect', { x, y, width: w, height: H - y, class: 'sc-soft' })));
    if (hottest) {
      const sun = s('g', { class: 'sc-sun' });
      sun.append(s('circle', { cx: 268, cy: 40, r: 14, class: 'sc-ink' }));
      for (let i = 0; i < 12; i++) {
        const a = (i * Math.PI) / 6, c = Math.cos(a), sn = Math.sin(a);
        sun.append(s('line', { x1: 268 + 20 * c, y1: 40 + 20 * sn, x2: 268 + 28 * c, y2: 40 + 28 * sn, class: 'sc-ray' }));
      }
      root.append(sun);
    }
    const x = 196;
    root.append(s('rect', { x: x - 11, y: 14, width: 22, height: 140, rx: 11, class: 'sc-glass' }));
    root.append(s('circle', { cx: x, cy: 158, r: 16, class: 'sc-glass' }));
    for (let y = 30, i = 0; y <= 140; y += 10, i++) {
      root.append(s('line', { x1: x + 14, y1: y, x2: x + (i % 2 ? 20 : 26), y2: y, class: 'sc-tick' }));
    }
    root.append(s('circle', { cx: x, cy: 158, r: 11, class: 'sc-ink' }));
    const clip = s('clipPath', { id: 'sc-tube' });
    clip.append(s('rect', { x: x - 6, y: 18, width: 12, height: 142, rx: 6 }));
    root.append(clip);
    const col = s('g', { 'clip-path': 'url(#sc-tube)' });
    const m = mover(L.y0, L.y1);
    m.append(s('rect', { x: x - 6, y: L.y1, width: 12, height: 200, class: 'sc-ink' }));
    col.append(m);
    root.append(col);
    ghostLine(root, 12, x - 14, L.y0, y0txt);
    root.append(s('text', { x: x + 32, y: L.y1 + 4, class: 'sc-yr sc-now' }, y1txt));
    arrow(root, x + 92, L.y0, L.y1 + (L.y1 < L.y0 ? 4 : -4));
  }

  function rain(root, L, y0txt, y1txt) {
    // A cloud, falling drops, and a rain gauge that fills to the level.
    const cloud = s('g', { class: 'sc-cloud' });
    [[70, 34, 18], [94, 26, 22], [120, 34, 18], [94, 40, 20]].forEach(([cx, cy, r]) => cloud.append(s('circle', { cx, cy, r, class: 'sc-ink' })));
    root.append(cloud);
    const drops = s('g', { class: 'sc-drops' });
    for (let i = 0; i < 14; i++) {
      const dx = 56 + (i * 37) % 80, dy = 62 + (i * 23) % 90;
      drops.append(s('line', { x1: dx, y1: dy, x2: dx - 3, y2: dy + 10, class: 'sc-drop' }));
    }
    root.append(drops);
    const x0 = 180, x1 = 236;
    root.append(s('path', { d: `M${x0 - 14} 22 L${x0} 40 L${x1} 40 L${x1 + 14} 22`, class: 'sc-glass-line' }));
    const clip = s('clipPath', { id: 'sc-cyl' });
    clip.append(s('rect', { x: x0, y: 40, width: x1 - x0, height: H - 44 }));
    root.append(clip);
    const g = s('g', { 'clip-path': 'url(#sc-cyl)' });
    const m = mover(L.y0, L.y1);
    const waves = s('g', { class: 'sc-wave' });
    waves.append(s('path', { d: wavePath(L.y1, 3, x0 - 40, x1 + 40, H), class: 'sc-water' }));
    waves.append(s('path', { d: wavePath(L.y1, 3, x0 - 40, x1 + 40), class: 'sc-surf' }));
    m.append(waves);
    g.append(m);
    root.append(g);
    root.append(s('rect', { x: x0, y: 40, width: x1 - x0, height: H - 44, class: 'sc-glass-line' }));
    for (let y = 52, i = 0; y < H - 6; y += 10, i++) {
      root.append(s('line', { x1: x1, y1: y, x2: x1 - (i % 2 ? 6 : 12), y2: y, class: 'sc-tick' }));
    }
    ghostLine(root, 12, x0 - 4, L.y0, y0txt);
    root.append(s('text', { x: x1 + 10, y: L.y1 + 4, class: 'sc-yr sc-now' }, y1txt));
    arrow(root, x1 + 66, L.y0, L.y1 + (L.y1 < L.y0 ? 4 : -4));
  }

  function ground(root, L, y0txt, y1txt) {
    // Cross-section: sky, a field and a tree on the surface, soil, and the land water below.
    const top = 40;
    root.append(s('path', { d: `M224 ${top} V${top - 18}`, class: 'sc-trunk' }));
    root.append(s('circle', { cx: 224, cy: top - 26, r: 12, class: 'sc-soft' }));
    for (let x = 8; x < 200; x += 12) root.append(s('path', { d: `M${x} ${top} l3 -7 l3 7`, class: 'sc-grass' }));
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
    const waves = s('g', { class: 'sc-wave sc-slow' });
    waves.append(s('path', { d: wavePath(L.y1, 2, -40, W + 40, H + 60), class: 'sc-water sc-deep' }));
    waves.append(s('path', { d: wavePath(L.y1, 2, -40, W + 40), class: 'sc-surf' }));
    m.append(waves);
    g.append(m);
    root.append(g);
    root.append(s('line', { x1: 0, y1: top, x2: W, y2: top, class: 'sc-surface' }));
    // A well down to the water.
    root.append(s('rect', { x: 262, y: top - 14, width: 16, height: 14, class: 'sc-glass-line' }));
    root.append(s('line', { x1: 264, y1: top, x2: 264, y2: H, class: 'sc-wellwall' }));
    root.append(s('line', { x1: 276, y1: top, x2: 276, y2: H, class: 'sc-wellwall' }));
    ghostLine(root, 12, 250, L.y0, y0txt);
    root.append(s('text', { x: 12, y: L.y1 + 16, class: 'sc-yr sc-now sc-onwater' }, y1txt));
    arrow(root, 300, L.y0, L.y1 + (L.y1 < L.y0 ? 4 : -4));
  }

  function gauge(root, L, y0txt, y1txt) {
    root.append(s('rect', { x: 140, y: 20, width: 40, height: H - 24, class: 'sc-glass-line' }));
    const m = mover(L.y0, L.y1);
    m.append(s('rect', { x: 140, y: L.y1, width: 40, height: 200, class: 'sc-water' }));
    root.append(m);
    ghostLine(root, 12, 136, L.y0, y0txt);
    root.append(s('text', { x: 190, y: L.y1 + 4, class: 'sc-yr sc-now' }, y1txt));
  }

  /* ---------- year stripes ---------- */

  function stripes(years) {
    const wrap = h('div', { class: 'sc-stripes-wrap' });
    if (!years || years.length < 3) return null;
    const lo = Math.min(...years.map((y) => y.mean)), hi = Math.max(...years.map((y) => y.mean));
    const n = years.length, sw = W / n;
    const sv = s('svg', { viewBox: `0 0 ${W} 28`, class: 'sc-stripes', 'aria-hidden': 'true', focusable: 'false', preserveAspectRatio: 'none' });
    years.forEach((y, i) => {
      const k = hi > lo ? (y.mean - lo) / (hi - lo) : 0.5;
      const r = s('rect', { x: (i * sw).toFixed(2), y: 0, width: (sw + 0.6).toFixed(2), height: 28, class: 'sc-stripe', 'fill-opacity': (0.06 + 0.88 * k).toFixed(3) });
      r.style.animationDelay = `${Math.round((i / n) * 900)}ms`;
      sv.append(r);
    });
    const ends = h('div', { class: 'sc-ends' }, h('span', {}, String(years[0].year)), h('span', {}, String(years[n - 1].year)));
    wrap.append(h('p', { class: 'sc-label' }, 'Year by year'), sv, ends,
      h('p', { class: 'source' }, 'One stripe per year, seasons removed. The stronger the shade, the higher that year.'));
    return wrap;
  }

  /* ---------- entry point ---------- */

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
    fig.classList.remove('run');
    void fig.getBoundingClientRect();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      fig.classList.add('run');
      fig.querySelectorAll('.sc-move').forEach((g) => { g.classList.add('go'); g.style.transform = ''; });
    }));
  }

  // t: TrendResult from the API. years: [{year, mean}] from app.js yearlyAverages (drawing only).
  window.renderScene = function renderScene(mount, t, years, placeName, varName) {
    while (mount.firstChild) mount.removeChild(mount.firstChild);
    if (!t || !t.period) { mount.hidden = true; return; }
    const kind = kindOf(t.variable);
    const L = levels(t);
    const y0 = t.period.start.slice(0, 4), y1 = t.period.end.slice(0, 4);
    const up = t.verdict === 'rising', down = t.verdict === 'falling';

    const fig = h('figure', { class: `scene sc-${kind}${L.clear ? '' : ' sc-flat'}` });
    const sv = s('svg', { viewBox: `0 0 ${W} ${H}`, class: 'sc-art', role: 'img', focusable: 'false' });
    const label = `Illustration, not to scale: ${ALT[kind](up, down)} in ${y1} ${up || down ? 'than' : 'as'} in ${y0}. ` +
      `${varName} at ${placeName}: ${num(t.slope_per_decade)} ${unit(t.units)} per decade, range ${num(t.ci_low)} to ${num(t.ci_high)}.`;
    sv.append(s('title', {}, label));
    const root = s('g', {});
    sv.append(root);

    if (!L.clear) {
      // The band the data support, drawn around the level, with a gentle bob inside it.
      root.append(s('rect', { x: 0, y: MID - 16, width: W, height: 32, class: 'sc-band' }));
    }
    ({ sea, heat: (r, l, a, b) => heat(r, l, a, b, t.variable === 'air_temp_max'), rain, ground, gauge })[kind](root, L, y0, y1);

    const tag = h('p', { class: 'sc-tag' },
      h('span', { class: 'sc-tag-n' }, varName), ` · ${y0} → ${y1}`,
      L.clear ? '' : h('span', { class: 'sc-tag-q' }, ' · no clear change'));
    const replay = h('button', { type: 'button', class: 'btn sc-replay' }, 'Play again');
    replay.addEventListener('click', () => play(fig));
    const head = h('div', { class: 'sc-head' }, tag, replay);

    fig.append(head, sv);
    const st = stripes(years);
    if (st) fig.append(st);
    fig.append(h('figcaption', { class: 'source' },
      L.clear ? 'Picture not to scale: it shows the direction. The number is the trend we calculated from the source above.'
        : 'Picture not to scale. The level drifts inside the shaded band: any change here is too small or too noisy to call.'));
    mount.append(fig);
    mount.hidden = false;
    play(fig);
  };
})();
