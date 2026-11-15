/* Module 02: "What this means for you" card. Spec: web/design/02-meaning.md */
(function () {
  'use strict';
  var slot = document.getElementById('meaning-slot');
  if (!slot || !window.TD) return;
  var BARS = { 'Very clear': 3, 'Clear': 2, 'Not clear': 1 };

  // The only place that knows where the four strings live in the reply.
  function getMeaning(trend) {
    var m = trend && trend.meaning;
    if (!m || typeof m !== 'object') return null;
    if (typeof m.headline !== 'string' || typeof m.confidence !== 'string' ||
        typeof m.comparison !== 'string' || typeof m.limit !== 'string') return null;
    if (!m.headline || !m.limit || !Object.prototype.hasOwnProperty.call(BARS, m.confidence)) return null;
    return m;
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function hide() { slot.hidden = true; slot.textContent = ''; }

  function build(trend) {
    var m = getMeaning(trend);
    if (!m) return hide();
    var card = el('div', 'card mean');
    card.append(el('p', 'card-label', 'What this means for you'));
    var head = el('h2', 'mean-head', m.headline);
    head.id = 'meaning-heading';
    head.tabIndex = -1;
    card.append(head);
    if (m.comparison) card.append(el('p', 'mean-compare', m.comparison));

    var conf = el('div', 'mean-conf');
    var word = el('p', 'mean-conf-word', m.confidence);
    var marks = el('span', 'mean-marks');
    marks.setAttribute('aria-hidden', 'true');
    for (var i = 0; i < 3; i++) marks.append(el('span', i < BARS[m.confidence] ? 'mean-mark on' : 'mean-mark'));
    word.append(marks);
    conf.append(el('p', 'mean-conf-label', 'How sure we are'), word);
    card.append(conf);

    var limit = el('div', 'mean-limit');
    limit.append(el('p', 'mean-limit-label', "What past data can't tell you"), el('p', 'mean-limit-text', m.limit));
    card.append(limit, el('p', 'source', 'Our calculation from public data.'));

    var src = trend.source;
    if (src && typeof src.name === 'string' && src.name) {
      var line = el('div', 'srcline', 'Raw data: ');
      var https = typeof src.url === 'string' && /^https:\/\//.test(src.url);
      var link = el(https ? 'a' : 'span', 'srclink', src.name + (https ? ' ↗' : ''));
      if (https) link.href = src.url;
      line.append(link);
      card.append(line);
    }
    slot.textContent = '';
    slot.append(card);
    slot.hidden = false;
  }

  document.addEventListener('td:load-end', function (e) {
    var d = e.detail;
    if (d && d.ok && d.trend) build(d.trend); else hide();
  });

  var s = window.TD.state; // read once, in case this script loaded after the last event
  if (s && s.status === 'loaded' && s.trend) build(s.trend);
})();
