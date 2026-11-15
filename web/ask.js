'use strict';
/* Ask tab: a chat thread over POST /api/ask. Loaded after app.js (uses el, $, clear, srcBlock, nameOf, showTab,
   showOnChart, tabState, writeHash). The answer text is shown exactly as the API returned it; the page adds no
   numbers of its own. */

/* PURE START (no DOM; the throwaway node check reads this block) */

const ASK_HISTORY = false;      // switch on when the backend accepts "history"
const HISTORY_MAX_MSGS = 6;
const HISTORY_MAX_CHARS = 4000;
// Waiting words by elapsed seconds (the server streams nothing, so no source is named).
const ASK_STAGES = [
  [0, 'Reading your question and choosing what to look up.'],
  [3, 'Fetching public data and running the trend test. This usually takes 10 to 20 seconds.'],
  [20, 'Still working. Some data sources answer slowly.'],
  [40, 'Still working. Some questions take up to a minute.'],
];
const ASK_STOP_MS = 150000;
const GAVE_UP_PREFIX = 'Sorry, I could not finish';
const EXAMPLES = [
  'Is sea level rising in New York?',
  'Are the hottest days getting hotter in Delhi?',
  'Is it getting warmer in Princeton, New Jersey?',
  'Has anything changed in Visakhapatnam (17.69, 83.22) since 1981?',
];

// turns: [{ q, a, kind }], kind 'answer' | 'gaveup' | 'error' | 'cancelled'. Only 'answer' turns go in.
// Oldest pairs are dropped first until both limits hold, so user/assistant keep alternating.
function buildHistory(turns, maxMsgs, maxChars) {
  const pairs = turns.filter((t) => t.kind === 'answer').map((t) => [{ role: 'user', content: t.q }, { role: 'assistant', content: t.a }]);
  const size = () => pairs.reduce((n, p) => n + p[0].content.length + p[1].content.length, 0);
  while (pairs.length && (pairs.length * 2 > maxMsgs || size() > maxChars)) pairs.shift();
  return [].concat(...pairs);
}

// Today the body is exactly { question }: the server rejects other fields.
function askBody(q, turns) {
  const b = { question: q };
  if (ASK_HISTORY) { const h = buildHistory(turns, HISTORY_MAX_MSGS, HISTORY_MAX_CHARS); if (h.length) b.history = h; }
  return b;
}

function waitSeconds(retryAfter, detail) {
  const n = Number(retryAfter);
  if (retryAfter != null && retryAfter !== '' && Number.isFinite(n) && n > 0) return Math.ceil(n);
  const m = /(\d+)\s*seconds?/.exec(String(detail || ''));
  return m ? Number(m[1]) : null;
}
function waitShort(n) { return n <= 90 ? `${n}s` : `${Math.ceil(n / 60)} min`; }

// Only a real number or a non-blank numeric string; never true, [5] or " ".
function asNum(x) { return typeof x === 'number' ? (Number.isFinite(x) ? x : NaN) : typeof x === 'string' && x.trim() !== '' ? Number(x) : NaN; }
function firstNum(...xs) { for (const x of xs) { const n = asNum(x); if (Number.isFinite(n)) return n; } return NaN; }

// What "Show on chart" opens: the detect_trend call's own variable, latitude, longitude and source.
function chartTarget(call) {
  const a = call.arguments || {}, r = call.result || {}, p = r.place || {};
  const variable = typeof a.variable === 'string' && a.variable ? a.variable : r.variable;
  const lat = firstNum(a.lat, p.lat), lon = firstNum(a.lon, p.lon);
  if (typeof variable !== 'string' || !variable || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
  // Only a source the tool was asked for (a fallback source in the result is not a choice anyone made).
  const src = typeof a.source === 'string' && a.source ? a.source : null;
  return { variable, lat, lon, source: src };
}

// A 200 response -> what to show.
function describeAnswer(body) {
  const text = String((body && body.answer) || '').trim();
  const calls = body && Array.isArray(body.tool_calls) ? body.tool_calls.filter(Boolean) : [];
  const trends = calls.filter((c) => c.name === 'detect_trend');
  const good = trends.filter((c) => !c.error && c.result && typeof c.result === 'object');
  const out = { kind: 'answer', text, model: (body && body.model) || '' };
  if (text.startsWith(GAVE_UP_PREFIX)) return Object.assign(out, { variant: 'gaveup' });
  if (good.length) {
    const r = good[0].result, p = r.place || {}, per = r.period || {};
    const seen = new Set(), sources = [];
    good.forEach((c) => { const s = c.result.source; if (s && !seen.has(s.id || s.name)) { seen.add(s.id || s.name); sources.push(s); } });
    const spots = new Set(good.map((c) => { const t = chartTarget(c), q = c.result.place || {}; return t ? `${t.lat.toFixed(2)},${t.lon.toFixed(2)}` : String(q.name); }));
    const place = p.name ? p.name : `the spot at ${Number(p.lat).toFixed(2)}, ${Number(p.lon).toFixed(2)}`;
    return Object.assign(out, {
      variant: 'data', count: spots.size, sources, chart: chartTarget(good[0]),
      variable: r.variable, place, y0: String(per.start || '').slice(0, 4), y1: String(per.end || '').slice(0, 4),
    });
  }
  if (trends.length) {
    const e = trends[0].error;
    return Object.assign(out, { variant: 'dataerror', tide: /tide gauge/i.test(String(e)) });
  }
  return Object.assign(out, { variant: text.includes('?') ? 'clarify' : 'declined' });
}

// r: { status, body, retryAfter, net, timedOut, cancelled } -> { kind, ... }
function classifyAsk(r) {
  if (r.cancelled) return { kind: 'cancelled' };
  if (r.timedOut) return { kind: 'timeout', text: 'That took too long, so we stopped waiting. Try a shorter or simpler question.' };
  if (r.net) return { kind: 'network', text: "We can't reach the server. Check your connection and try again.", retry: true };
  const detail = r.body && typeof r.body.detail === 'string' ? r.body.detail : '';
  if (r.status === 200 && r.body) return describeAnswer(r.body);
  if (r.status === 400) return { kind: 'bad', text: detail || 'The request was not accepted.' };
  if (r.status === 422) return { kind: 'invalid', text: 'Something went wrong with that question. Please try again.' };
  if (r.status === 429) {
    const n = waitSeconds(r.retryAfter, detail);
    if (n == null) return { kind: 'limit', seconds: null, text: detail || 'Too many questions right now. Please wait a moment and try again.' };
    const phrase = n > 90 ? `about ${Math.ceil(n / 60)} minutes` : `${n} seconds`;
    return { kind: 'limit', seconds: n, text: `Too many questions right now. Please wait ${phrase} and try again.` };
  }
  if (r.status === 502) return { kind: 'upstream', text: 'The assistant could not be reached. Please try again.', retry: true };
  if (r.status === 503) return { kind: 'off' };
  return { kind: 'network', text: "We can't reach the server. Check your connection and try again.", retry: true };
}

/* PURE END */

/* ---------- the thread ---------- */

const askS = { off: false, busy: false, turns: [], ctrl: null, reason: '', timers: [], said: 0, cd: 0 };

function paras(text) { return text.split(/\n\s*\n/).map((t) => t.trim()).filter(Boolean).map((t) => el('p', { class: 'msg-text' }, t)); }
function reducedMotion() { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
// The status line is for screen readers only (the element is sr-only); anything shown on screen is its own block.
function say(t) { $('ask-status').textContent = t; }

function exampleButtons() {
  const box = el('div', { class: 'examples' });
  EXAMPLES.forEach((t) => {
    const b = el('button', { type: 'button', class: 'btn example' }, t);
    b.addEventListener('click', () => send(t));
    box.append(b);
  });
  return box;
}

function youBlock(q) {
  return el('div', { class: 'msg you' }, el('p', { class: 'msg-label' }, 'You'), el('p', { class: 'msg-text' }, q));
}
function aiLabel(model) {
  return el('p', { class: 'msg-label', tabindex: '-1' }, el('span', { class: 'badge', 'aria-hidden': 'true' }, 'AI'), ' Written by an AI model');
}
function goExplore() { showTab('explore', true); $('h-explore').focus(); }
function goExploreButton() {
  const b = el('button', { type: 'button', class: 'btn' }, 'Go to Explore');
  b.addEventListener('click', goExplore);
  return b;
}

// Returns { block, focus } for a described answer.
function answerBlock(d) {
  const label = aiLabel(d.model);
  const block = el('div', { class: 'msg ai' }, label, ...(d.model ? [el('p', { class: 'msg-model small' }, d.model)] : []), ...paras(d.text));
  let focus = label;
  if (d.variant === 'data') {
    let line = `Looked up: ${nameOf(d.variable)} at ${d.place}, ${d.y0} to ${d.y1}.`;
    if (d.count > 1) line += ` The assistant checked ${d.count} places. The first is shown here.`;
    block.append(el('p', { class: 'small' }, line));
    d.sources.forEach((s) => { const src = el('div', { class: 'srcline' }); srcBlock(src, 'Raw data', s); block.append(src); });
    if (!d.sources.length) { const src = el('div', { class: 'srcline' }); srcBlock(src, 'Raw data', null); block.append(src); }
    block.append(el('p', { class: 'small' }, 'The AI wrote the text above. The trend, range and verdict are our calculation from public data. To see them, open the chart.'));
    const target = d.chart && fixExplore(d.chart, state.variables);
    if (target) {
      const a = el('a', { class: 'srclink', href: '#' + writeHash({ tab: 'explore', explore: target }) }, 'Show on chart');
      a.addEventListener('click', (e) => { e.preventDefault(); showOnChart(target); });
      block.append(a);
    }
  } else if (d.variant === 'dataerror') {
    block.append(el('p', {}, d.tide ? 'No tide gauge near this place.' : "We couldn't get the data for that."));
    block.append(el('p', {}, 'Try another place or measurement.'));
    if (d.tide && !(varById('sea_level') && varById('sea_level').sources.length > 1)) block.append(el('p', {}, 'Tide gauges sit along US coasts.'));
  } else if (d.variant === 'gaveup') {
    block.append(el('p', {}, 'Try a shorter question, or pick a place on the Explore tab.'), goExploreButton());
  } else if (d.variant === 'clarify') {
    block.append(el('p', { class: 'small' }, 'No data was looked up for this answer, so treat any numbers in it as unchecked.'));
    block.append(el('p', { class: 'small' }, ASK_HISTORY ? 'Answer in the box below to continue.' : 'Answer in the box below. Name the place and what to measure again.'));
    focus = $('ask-q');
  } else {
    block.append(el('p', { class: 'small' }, 'No data was looked up for this answer, so treat any numbers in it as unchecked.'));
    block.append(el('p', { class: 'small' }, 'We can tell you whether something changed over time at a place. Try one of these:'), exampleButtons());
  }
  return { block, focus };
}

function errorBlock(text, retryQ) {
  const b = el('div', { class: 'msg err' }, el('p', { class: 'msg-text', tabindex: '-1' }, text));
  if (retryQ) {
    const btn = el('button', { type: 'button', class: 'btn' }, 'Try again');
    btn.addEventListener('click', () => send(retryQ));
    b.append(btn);
  }
  return b;
}

/* ---------- sending ---------- */

function askBusy(on) {
  askS.busy = on;
  const go = $('ask-go');
  go.textContent = on ? 'Asking…' : 'Ask';
  go.setAttribute('aria-disabled', String(on));
  $('ask-cancel').hidden = !on;
  $('ask-q').readOnly = on;
}

async function postAsk(q, signal) {
  try {
    const res = await fetch('/api/ask', {
      method: 'POST', signal,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(askBody(q, askS.turns)),
    });
    let body = null;
    try { body = await res.json(); } catch (e) { if (signal.aborted) return { cancelled: askS.reason === 'cancel', timedOut: askS.reason === 'timeout' }; }
    return { status: res.status, body, retryAfter: res.headers.get('Retry-After') };
  } catch (e) {
    if (e && e.name === 'AbortError') return { cancelled: askS.reason === 'cancel', timedOut: askS.reason === 'timeout' };
    return { net: true };
  }
}

async function send(raw) {
  if (askS.busy || askS.cd) return;
  const q = String(raw).trim();
  const err = $('ask-err');
  err.hidden = true;
  say('');
  if (!q) { err.hidden = false; err.textContent = 'Type a question first.'; $('ask-q').focus(); return; }

  $('ask-q').value = q;
  updateCount();
  $('ask-empty').hidden = true;
  const thread = $('ask-thread');
  const you = youBlock(q);
  const wait = el('div', { class: 'msg ai ask-wait', role: 'status' }, el('p', { class: 'msg-text' }, ASK_STAGES[0][1]), el('span', { class: 'small ask-secs', 'aria-hidden': 'true' }, '0 s'));
  thread.append(you, wait);
  you.scrollIntoView({ block: 'start', behavior: reducedMotion() ? 'auto' : 'smooth' });
  askBusy(true);
  askS.reason = '';
  askS.ctrl = new AbortController();
  const t0 = Date.now();
  askS.tick = setInterval(() => {
    const sec = Math.floor((Date.now() - t0) / 1000);
    wait.lastChild.textContent = `${sec} s`;
    wait.firstChild.textContent = ASK_STAGES.filter(([from]) => sec >= from).pop()[1];
  }, 1000);
  askS.timers = [
    setTimeout(() => { askS.reason = 'timeout'; askS.ctrl.abort(); }, ASK_STOP_MS),
  ];

  const r = await postAsk(q, askS.ctrl.signal);
  askS.timers.forEach(clearTimeout);
  clearInterval(askS.tick);
  askBusy(false);
  wait.remove();
  const o = classifyAsk(r);
  let focus = null;
  if (o.kind === 'answer') {
    const { block, focus: f } = answerBlock(o);
    thread.append(block);
    focus = f;
    askS.turns.push({ q, a: o.text, kind: o.variant === 'gaveup' ? 'gaveup' : 'answer', variant: o.variant });
    $('ask-q').value = '';
    updateCount();
    say('Answer ready.');
  } else if (o.kind === 'cancelled') {
    askS.turns.push({ q, a: '', kind: 'cancelled' });
    thread.append(el('div', { class: 'msg ai' }, el('p', { class: 'msg-text' }, 'Cancelled.')));
    focus = $('ask-q');
  } else if (o.kind === 'off') {
    askS.turns.push({ q, a: '', kind: 'error' });
    setOff();
    focus = $('ask-off-go');
    say("Asking questions isn't available right now.");
  } else {
    askS.turns.push({ q, a: '', kind: 'error' });
    const b = errorBlock(o.text, o.retry ? q : null);
    thread.append(b);
    if (o.kind === 'limit' && o.seconds) countdown(o.seconds);
    focus = o.retry ? b.querySelector('.msg-text') : $('ask-q');
  }
  refreshThreadUI();
  if (focus === $('ask-q')) { $('ask-q').focus(); }
  else if (focus) { focus.focus(); }
}

function countdown(n) {
  const go = $('ask-go');
  askS.cd = n;
  const tick = () => {
    if (askS.cd <= 0) { clearInterval(askS.cdTimer); go.textContent = 'Ask'; go.setAttribute('aria-disabled', 'false'); return; }
    go.textContent = `Ask again in ${waitShort(askS.cd)}`;
    go.setAttribute('aria-disabled', 'true');
    askS.cd--;
  };
  clearInterval(askS.cdTimer);
  tick();
  askS.cdTimer = setInterval(tick, 1000);
}

// The "answered on its own" line: shown once an answer exists, unless the latest answer or clarifying question is a clarifying one.
function nohistHidden(turns, history) {
  const last = turns.filter((t) => t.kind === 'answer').pop();
  return history || !last || last.variant === 'clarify';
}

function refreshThreadUI() {
  if (askS.off) { ['ask-jump', 'ask-nohist', 'ask-hint'].forEach((id) => { $(id).hidden = true; }); return; }
  const answers = $('ask-thread').querySelectorAll('.msg.ai:not([role="status"])').length;
  $('ask-jump').hidden = answers < 3;
  // the clarifying-question line already says to name the place again, so the "on its own" line waits
  $('ask-nohist').hidden = nohistHidden(askS.turns, ASK_HISTORY);
  $('ask-hint').hidden = !ASK_HISTORY || !askS.turns.some((t) => t.kind === 'answer');
}

function setOff() {
  askS.off = true;
  ['ask-lead', 'ask-privacy', 'ask-form', 'ask-empty', 'ask-jump', 'ask-hint'].forEach((id) => { $(id).hidden = true; });
  $('ask-off').hidden = false;
}

/* ---------- composer ---------- */

function updateCount() {
  const n = $('ask-q').value.length, c = $('ask-count');
  c.hidden = n < 400;
  c.textContent = `${n} of 500`;
  if (n >= 500 && askS.said < 500) { askS.said = 500; say('Limit reached: 500 characters.'); }
  else if (n >= 450 && n < 500 && askS.said < 450) { askS.said = 450; say('50 characters left.'); }
  else if (n < 450) askS.said = 0;
}

function startAsk() {
  $('ask-ui').hidden = false;
  [...exampleButtons().children].forEach((b) => $('ask-examples').append(b));
  $('ask-form').addEventListener('submit', (e) => { e.preventDefault(); if ($('ask-go').getAttribute('aria-disabled') !== 'true') send($('ask-q').value); });
  $('ask-q').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if ($('ask-go').getAttribute('aria-disabled') !== 'true') send($('ask-q').value); }
  });
  $('ask-q').addEventListener('input', () => { updateCount(); $('ask-err').hidden = true; });
  $('ask-cancel').addEventListener('click', () => { askS.reason = 'cancel'; askS.ctrl.abort(); });
  $('ask-jump').addEventListener('click', (e) => { e.preventDefault(); $('ask-q').focus(); });
  $('ask-off-go').addEventListener('click', goExplore);
  fetch('/api/health', { headers: { Accept: 'application/json' } })
    .then((r) => r.json())
    .then((h) => { if (h && h.ask === false) setOff(); })
    .catch(() => { /* health failing means: treat as on and let the send decide */ });
}

if (typeof document !== 'undefined') startAsk();
