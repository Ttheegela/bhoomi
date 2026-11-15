'use strict';
/* Year stripes under "How we calculated this" on the Explore tab (one stripe per year, seasons removed).
   The trend picture that used to live here was removed (web/design/08-layout.md section C).
   It never formats a data value. Colours come from the verdict's ramp (data-verdict, --v-1 .. --v-5). */

(function () {
  const NS = 'http://www.w3.org/2000/svg';

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

  // Option A: k (0 lowest year .. 1 highest) picks a colour on the verdict's five-stop ramp (--v-1 .. --v-5,
  // set by data-verdict on an ancestor). color-mix keeps it live when the theme changes. Ink if no verdict.
  function shade(k) {
    const j = Math.min(3, Math.floor(k * 4)), u = Math.round((k * 4 - j) * 100);
    return `color-mix(in srgb, var(--v-${j + 2}, var(--ink)) ${u}%, var(--v-${j + 1}, var(--ink)))`;
  }
  // A browser without color-mix() would drop the fill and draw every stripe alike: use ink at a fill opacity instead.
  const MIX = !!(window.CSS && CSS.supports && CSS.supports('color', 'color-mix(in srgb, red, blue)'));
  function paint(rect, k) {
    if (MIX) { rect.style.fill = shade(k); return; }
    rect.style.fill = 'var(--ink)';
    rect.setAttribute('fill-opacity', (0.06 + 0.88 * k).toFixed(3));
  }

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
      const r = s('rect', { x: (i * sw).toFixed(2), y: 0, width: (sw + 0.6).toFixed(2), height: 28, class: 'sc-stripe' });
      paint(r, k);
      r.style.animationDelay = `${Math.round((i / n) * 900)}ms`;
      sv.append(r);
    });
    const swatch = (k) => {
      const q = s('svg', { width: 20, height: 14, class: 'sc-sw', 'aria-hidden': 'true', focusable: 'false' });
      const kr = s('rect', { width: 20, height: 14, rx: 2, class: 'sc-stripe-key' });
      paint(kr, k);
      q.append(kr);
      return q;
    };
    mount.append(
      sv,
      h('div', { class: 'sc-ends' }, h('span', {}, period.start.slice(0, 4)), h('span', {}, period.end.slice(0, 4))),
      h('ul', { class: 'sc-key' }, h('li', {}, swatch(0), 'lower year'), h('li', {}, swatch(1), 'higher year')),
    );
    box.hidden = false;
  };
})();
