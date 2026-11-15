'use strict';
/* Floating chat on every window: a thread over POST /api/ask. Self-contained: reads window.TD only for the window
   name, the context and the route event. The answer text is shown exactly as the API returned it; the page adds no
   numbers of its own. All DOM is built here inside #chat-slot. */

/* PURE START (no DOM; a node check can read this block) */

const HISTORY_MAX_MSGS = 6;
const HISTORY_MAX_CHARS = 4000;
const ASK_STAGES = [
  [0, 'Reading your question and choosing what to look up.'],
  [3, 'Fetching public data and running the trend test. This usually takes 10 to 20 seconds.'],
  [20, 'Still working. Some data sources answer slowly.'],
  [40, 'Still working. Some questions take up to a minute.'],
];
const ASK_STOP_MS = 150000;
const GAVE_UP_PREFIX = 'Sorry, I could not finish';
const STARTERS = {
  sea_level: ['Is it safe to buy a home near the shore here?', 'Which of my places is riskiest?'],
  air_temp: ['Is it getting hotter here?', "Will summers be worse when I'm older?"],
  air_temp_max: ['Are the hottest days getting hotter here?', 'What should I plan for?'],
  precip: ['Is it really getting wetter here, or is it just this year?', 'What does this mean for farming?'],
  water_storage: ['Is the water here running low?', 'Should I drill a well here?'],
  settings: ['What can you help me with?'],
};
const SUMMARIZE = "Summarize what I'm looking at";

// turns: [{ q, a, kind }]; only kind 'answer' turns go in. Oldest pairs drop first so user/assistant keep alternating.
function buildHistory(turns, maxMsgs, maxChars) {
  const pairs = turns.filter((t) => t.kind === 'answer').map((t) => [{ role: 'user', content: t.q }, { role: 'assistant', content: t.a }]);
  const size = () => pairs.reduce((n, p) => n + p[0].content.length + p[1].content.length, 0);
  while (pairs.length && (pairs.length * 2 > maxMsgs || size() > maxChars)) pairs.shift();
  return [].concat(...pairs);
}

function waitSeconds(retryAfter, detail) {
  const n = Number(retryAfter);
  if (retryAfter != null && retryAfter !== '' && Number.isFinite(n) && n > 0) return Math.ceil(n);
  const m = /(\d+)\s*seconds?/.exec(String(detail || ''));
  return m ? Number(m[1]) : null;
}
function waitShort(n) { return n <= 90 ? `${n}s` : `${Math.ceil(n / 60)} min`; }
function asNum(x) { return typeof x === 'number' ? (Number.isFinite(x) ? x : NaN) : typeof x === 'string' && x.trim() !== '' ? Number(x) : NaN; }

function httpsUrl(u) { try { const x = new URL(String(u)); return x.protocol === 'https:' ? x.href : ''; } catch (e) { return ''; } }

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
    const a = good[0].arguments || {};
    const lat = asNum(a.lat != null ? a.lat : p.lat), lon = asNum(a.lon != null ? a.lon : p.lon);
    const spot = Number.isFinite(lat) && Number.isFinite(lon) ? `the spot at ${lat.toFixed(2)}, ${lon.toFixed(2)}` : 'this place';
    return Object.assign(out, {
      variant: 'data', count: new Set(good.map((c) => (c.result.place || {}).name)).size, sources,
      variable: typeof r.variable === 'string' ? r.variable : '', where: `at ${p.name ? p.name : spot}`,
      y0: String(per.start || '').slice(0, 4), y1: String(per.end || '').slice(0, 4),
    });
  }
  if (trends.length) return Object.assign(out, { variant: 'dataerror', tide: /tide gauge/i.test(String(trends[0].error)) });
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

(function () {
  if (typeof document === 'undefined') return;
  const slot = document.getElementById('chat-slot');
  if (!slot) return;

  const S = { open: false, off: false, busy: false, turns: [], ctrl: null, reason: '', tick: 0, timer: 0, cd: 0, cdTimer: 0, said: 0, listening: false, speakBtn: null };
  const TDx = () => window.TD || {};
  const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const synth = window.speechSynthesis && window.SpeechSynthesisUtterance ? window.speechSynthesis : null;

  function h(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => { if (v === true) n.setAttribute(k, ''); else if (v !== false && v != null) n.setAttribute(k, v); });
    kids.forEach((k) => n.append(k));
    return n;
  }

  /* ---------- DOM ---------- */
  const launcher = h('button', { type: 'button', class: 'btn dark chat-launcher', 'aria-expanded': 'false', 'aria-controls': 'chat-panel' }, 'Ask AI');
  const title = h('h2', { class: 'chat-title' }, 'Trend Detective assistant');
  const closeBtn = h('button', { type: 'button', class: 'btn ghost chat-close', 'aria-label': 'Close assistant' }, 'Close');
  const intro = h('div', { class: 'chat-intro' },
    h('p', { class: 'chat-small' }, "Ask about a place in your own words. We look up public data and tell you whether it changed over time. We can't forecast the future."),
    h('p', { class: 'chat-small' }, "Your question and the earlier messages in this chat are sent to an AI model provider so it can be answered. Don't include personal details."),
    h('p', { class: 'chat-small' }, 'Your conversation stays in this browser tab. Reloading clears it. Questions and answers are recorded by a quality-checking service (Langfuse); nothing else about you is kept.'));
  const starters = h('div', { class: 'chat-starters' });
  const thread = h('div', { class: 'chat-thread', role: 'log', 'aria-live': 'polite', 'aria-label': 'Conversation' });
  const status = h('p', { class: 'chat-sr', role: 'status' });
  const scroller = h('div', { class: 'chat-scroll' }, intro, starters, thread, status);
  const offBox = h('div', { class: 'chat-off', hidden: true },
    h('p', {}, h('strong', {}, "Asking questions isn't available right now.")),
    h('p', { class: 'chat-small' }, 'You can still pick a place and a measurement on the page.'));
  const q = h('textarea', { id: 'chat-q', rows: '2', maxlength: '500', 'aria-label': 'Your question', placeholder: 'Ask a question', 'aria-describedby': 'chat-help chat-err' });
  const mic = SR ? h('button', { type: 'button', class: 'btn ghost chat-mic', 'aria-pressed': 'false', 'aria-label': 'Voice typing' }, 'Mic') : null;
  const go = h('button', { type: 'submit', class: 'btn dark chat-go' }, 'Ask');
  const cancel = h('button', { type: 'button', class: 'btn ghost', hidden: true }, 'Cancel');
  const err = h('p', { class: 'chat-err', id: 'chat-err', hidden: true });
  const count = h('p', { class: 'chat-small', hidden: true });
  const form = h('form', { class: 'chat-form', novalidate: true },
    h('div', { class: 'chat-row' }, q, h('div', { class: 'chat-btns' }, go, ...(mic ? [mic] : []), cancel)),
    err, count,
    h('p', { class: 'chat-small', id: 'chat-help' }, 'Press Enter to ask. Shift+Enter starts a new line.'),
    ...(SR ? [h('p', { class: 'chat-small' }, "Voice typing uses your browser's speech service.")] : []));
  const panel = h('div', { class: 'card chat-panel', id: 'chat-panel', role: 'dialog', 'aria-label': 'Trend Detective assistant', hidden: true },
    h('div', { class: 'chat-head' }, title, closeBtn), scroller, offBox, form);
  slot.append(panel, launcher);

  /* ---------- window name, starters ---------- */
  function winName() {
    const t = TDx(), w = t.window;
    if (!w || w === 'settings') return 'Trend Detective';
    const f = (t.windows || []).find((x) => x.id === w);
    return f && f.name ? f.name : 'Trend Detective';
  }
  function renderStarters() {
    starters.replaceChildren();
    starters.hidden = S.turns.length > 0 || S.off;
    [SUMMARIZE, ...(STARTERS[TDx().window] || STARTERS.settings)].forEach((t) => {
      const b = h('button', { type: 'button', class: 'btn ghost chat-starter' }, t);
      b.addEventListener('click', () => send(t));
      starters.append(b);
    });
  }
  function onRoute() {
    const n = winName();
    panel.setAttribute('aria-label', `${n} assistant`);
    title.textContent = `${n} assistant`;
    stopSpeaking();
    renderStarters();
  }

  /* ---------- open / close ---------- */
  function setOpen(on) {
    S.open = on;
    panel.hidden = !on;
    launcher.setAttribute('aria-expanded', String(on));
    if (on) { onRoute(); if (S.off) closeBtn.focus(); else q.focus(); }
    else { stopSpeaking(); stopListening(); launcher.focus(); }
  }
  launcher.addEventListener('click', () => setOpen(!S.open));
  closeBtn.addEventListener('click', () => setOpen(false));
  panel.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); } });
  document.addEventListener('td:route', onRoute);

  function say(t) { status.textContent = t; }

  /* ---------- answer blocks ---------- */
  function paras(text) { return text.split(/\n\s*\n/).map((t) => t.trim()).filter(Boolean).map((t) => { const p = h('p', { class: 'msg-text' }); p.textContent = t; return p; }); }
  function srcLine(s) {
    const p = h('p', { class: 'chat-small' });
    p.append('Raw data: ');
    if (!s || !s.name) { p.append('source not named'); return p; }
    const url = httpsUrl(s.url);
    if (url) { const a = h('a', { href: url, target: '_blank', rel: 'noopener' }); a.textContent = `${s.name} ↗`; p.append(a); } else p.append(String(s.name));
    return p;
  }
  function stopSpeaking() {
    if (synth) synth.cancel();
    if (S.speakBtn) { S.speakBtn.textContent = 'Read aloud'; S.speakBtn.setAttribute('aria-pressed', 'false'); S.speakBtn = null; }
  }
  function speakButton(text) {
    const b = h('button', { type: 'button', class: 'btn ghost chat-speak', 'aria-pressed': 'false' }, 'Read aloud');
    b.addEventListener('click', () => {
      if (S.speakBtn === b) { stopSpeaking(); return; }
      stopSpeaking();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = navigator.language || 'en';
      u.onend = u.onerror = () => { if (S.speakBtn === b) stopSpeaking(); };
      S.speakBtn = b; b.textContent = 'Stop'; b.setAttribute('aria-pressed', 'true');
      synth.speak(u);
    });
    return b;
  }

  function answerBlock(d) {
    const label = h('p', { class: 'msg-label', tabindex: '-1' }, h('span', { class: 'chat-badge', 'aria-hidden': 'true' }, 'AI'), ' Written by an AI model');
    const block = h('div', { class: 'msg ai' }, label, ...paras(d.text));
    if (synth && d.text) block.append(speakButton(d.text));
    const small = (t) => { const p = h('p', { class: 'chat-small' }); p.textContent = t; block.append(p); };
    const unchecked = 'No data was looked up for this answer, so treat any numbers in it as unchecked.';
    let focus = label;
    if (d.variant === 'data') {
      let line = `Looked up: ${d.variable || 'the trend'} ${d.where}, ${d.y0} to ${d.y1}.`;
      if (d.count > 1) line += ` The assistant checked ${d.count} places. The first is shown here.`;
      small(line);
      if (d.sources.length) d.sources.forEach((s) => block.append(srcLine(s))); else block.append(srcLine(null));
      small('The AI wrote the text above. The trend, range and verdict are our calculation from public data.');
    } else if (d.variant === 'dataerror') {
      small(d.tide ? 'No tide gauge near this place.' : "We couldn't get the data for that.");
      small('Try another place or measurement.');
    } else if (d.variant === 'gaveup') {
      small('Try a shorter question, or pick a place on the page.');
    } else if (d.variant === 'clarify') {
      small(unchecked); small('Answer in the box below to continue.');
      focus = q;
    } else {
      small(unchecked); small('We can tell you whether something changed over time at a place. Try one of these:');
      const box = h('div', { class: 'chat-starters' });
      (STARTERS[TDx().window] || STARTERS.settings).forEach((t) => { const b = h('button', { type: 'button', class: 'btn ghost chat-starter' }, t); b.addEventListener('click', () => send(t)); box.append(b); });
      block.append(box);
    }
    return { block, focus };
  }
  function errorBlock(text, retryQ) {
    const t = h('p', { class: 'msg-text', tabindex: '-1' });
    t.textContent = text;
    const b = h('div', { class: 'msg err' }, t);
    if (retryQ) { const btn = h('button', { type: 'button', class: 'btn ghost' }, 'Try again'); btn.addEventListener('click', () => send(retryQ)); b.append(btn); }
    return b;
  }

  /* ---------- sending ---------- */
  function busy(on) {
    S.busy = on;
    go.textContent = on ? 'Asking…' : 'Ask';
    go.setAttribute('aria-disabled', String(on));
    cancel.hidden = !on;
    q.readOnly = on;
  }
  function context() { try { const c = TDx().context && TDx().context(); return c && typeof c === 'object' ? c : null; } catch (e) { return null; } }

  async function post(question, signal, ctx) {
    const body = { question, history: buildHistory(S.turns, HISTORY_MAX_MSGS, HISTORY_MAX_CHARS) };
    if (ctx) body.context = ctx;
    try {
      const res = await fetch('/api/ask', { method: 'POST', signal, headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body) });
      let b = null;
      try { b = await res.json(); } catch (e) { if (signal.aborted) return { cancelled: S.reason === 'cancel', timedOut: S.reason === 'timeout' }; }
      return { status: res.status, body: b, retryAfter: res.headers.get('Retry-After') };
    } catch (e) {
      if (e && e.name === 'AbortError') return { cancelled: S.reason === 'cancel', timedOut: S.reason === 'timeout' };
      return { net: true };
    }
  }

  function scrollTo(n) { n.scrollIntoView({ block: 'start', behavior: reduced() ? 'auto' : 'smooth' }); }

  async function send(raw) {
    if (S.busy || S.cd) return;
    const text = String(raw).trim();
    err.hidden = true; say('');
    if (!text) { err.hidden = false; err.textContent = 'Type a question first.'; q.focus(); return; }
    stopSpeaking(); stopListening();
    starters.hidden = true;
    q.value = text; updateCount();
    const youText = h('p', { class: 'msg-text' });
    youText.textContent = text;
    const you = h('div', { class: 'msg you' }, h('p', { class: 'msg-label' }, 'You'), youText);
    const secs = h('span', { class: 'chat-small', 'aria-hidden': 'true' }, '0 s');
    const words = h('p', { class: 'msg-text' }, ASK_STAGES[0][1]);
    const wait = h('div', { class: 'msg ai', role: 'status' }, words, secs);
    thread.append(you, wait);
    scrollTo(you);
    busy(true);
    S.reason = '';
    S.ctrl = new AbortController();
    const t0 = Date.now();
    S.tick = setInterval(() => {
      const s = Math.floor((Date.now() - t0) / 1000);
      secs.textContent = `${s} s`;
      const w = ASK_STAGES.filter(([from]) => s >= from).pop()[1];
      if (words.textContent !== w) words.textContent = w;
    }, 1000);
    S.timer = setTimeout(() => { S.reason = 'timeout'; S.ctrl.abort(); }, ASK_STOP_MS);

    const ctx = context();
    let r = await post(text, S.ctrl.signal, ctx);
    if (r.status === 422 && ctx) r = await post(text, S.ctrl.signal, null); // server does not know "context" yet
    clearTimeout(S.timer); clearInterval(S.tick);
    busy(false);
    wait.remove();
    const o = classifyAsk(r);
    let focus = q;
    if (o.kind === 'answer') {
      const a = answerBlock(o);
      thread.append(a.block);
      focus = a.focus;
      S.turns.push({ q: text, a: o.text, kind: o.variant === 'gaveup' ? 'gaveup' : 'answer', variant: o.variant });
      q.value = ''; updateCount();
      say('Answer ready.');
    } else if (o.kind === 'cancelled') {
      S.turns.push({ q: text, a: '', kind: 'cancelled' });
      thread.append(h('div', { class: 'msg ai' }, h('p', { class: 'msg-text' }, 'Cancelled.')));
    } else if (o.kind === 'off') {
      S.turns.push({ q: text, a: '', kind: 'error' });
      setOff();
      say("Asking questions isn't available right now.");
      focus = closeBtn;
    } else {
      S.turns.push({ q: text, a: '', kind: 'error' });
      const b = errorBlock(o.text, o.retry ? text : null);
      thread.append(b);
      if (o.kind === 'limit' && o.seconds) countdown(o.seconds);
      if (o.retry) focus = b.querySelector('.msg-text');
    }
    if (S.open) focus.focus({ preventScroll: true });
    if (o.kind === 'answer') scrollTo(thread.lastElementChild);
  }

  function countdown(n) {
    S.cd = n;
    const tick = () => {
      if (S.cd <= 0) { clearInterval(S.cdTimer); go.textContent = 'Ask'; go.setAttribute('aria-disabled', 'false'); return; }
      go.textContent = `Ask again in ${waitShort(S.cd)}`;
      go.setAttribute('aria-disabled', 'true');
      S.cd--;
    };
    clearInterval(S.cdTimer);
    tick();
    S.cdTimer = setInterval(tick, 1000);
  }

  function setOff() {
    S.off = true;
    form.hidden = true; starters.hidden = true; offBox.hidden = false;
  }

  /* ---------- composer ---------- */
  function updateCount() {
    const n = q.value.length;
    count.hidden = n < 400;
    count.textContent = `${n} of 500`;
    if (n >= 500 && S.said < 500) { S.said = 500; say('Limit reached: 500 characters.'); }
    else if (n >= 450 && n < 500 && S.said < 450) { S.said = 450; say('50 characters left.'); }
    else if (n < 450) S.said = 0;
  }
  const submit = () => { if (go.getAttribute('aria-disabled') !== 'true') send(q.value); };
  form.addEventListener('submit', (e) => { e.preventDefault(); submit(); });
  q.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); } });
  q.addEventListener('input', () => { updateCount(); err.hidden = true; });
  cancel.addEventListener('click', () => { S.reason = 'cancel'; S.ctrl.abort(); });

  /* ---------- voice in ---------- */
  let rec = null;
  function stopListening() { if (rec) { try { rec.stop(); } catch (e) { /* already stopped */ } } }
  if (mic) {
    mic.addEventListener('click', () => {
      if (S.listening) { stopListening(); return; }
      rec = new SR();
      rec.lang = navigator.language || 'en-US';
      rec.interimResults = true;
      rec.continuous = false;
      const base = q.value ? q.value.replace(/\s*$/, ' ') : '';
      rec.onresult = (e) => {
        let t = '';
        for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
        q.value = (base + t).slice(0, 500); updateCount();
      };
      rec.onerror = (e) => {
        const blocked = 'Microphone access was blocked. Allow it in your browser, or type your question.';
        const m = { 'not-allowed': blocked, 'service-not-allowed': blocked, 'no-speech': "We didn't hear anything. Try again, or type your question." };
        err.hidden = false; err.textContent = m[e.error] || "Voice typing didn't work. Type your question instead.";
      };
      rec.onend = () => { S.listening = false; mic.setAttribute('aria-pressed', 'false'); mic.textContent = 'Mic'; rec = null; };
      err.hidden = true;
      try { rec.start(); S.listening = true; mic.setAttribute('aria-pressed', 'true'); mic.textContent = 'Stop'; stopSpeaking(); }
      catch (e) { rec = null; err.hidden = false; err.textContent = "Voice typing didn't work. Type your question instead."; }
    });
  }

  /* ---------- start ---------- */
  onRoute();
  fetch('/api/health', { headers: { Accept: 'application/json' } })
    .then((r) => r.json())
    .then((x) => { if (x && x.ask === false) setOff(); })
    .catch(() => { /* treat as on; the send decides */ });
})();
