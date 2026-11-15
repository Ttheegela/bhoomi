'use strict';
/* Assistant: the ElevenLabs conversational widget (text and voice), bottom-right on every window.
   This file only mounts it and keeps its dynamic variables current. No question goes through our server. */

const CHAT_AGENT_ID = 'agent_0301m7fm167nfwkrmgrw26cgf7qb'; // public widget id
const CHAT_EMBED_SRC = 'https://unpkg.com/@elevenlabs/convai-widget-embed@0.18.3/dist/index.js';

(function () {
  if (typeof document === 'undefined') return;
  const slot = document.getElementById('chat-slot');
  if (!slot) return;

  const oneLine = (s) => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const cut = (s, n) => {
    if (s.length <= n) return s;
    const t = s.slice(0, n), i = t.lastIndexOf(' ');
    return (i > 0 ? t.slice(0, i) : t).replace(/[ ,;:.]+$/, '');
  };
  const TDx = () => window.TD || {};

  function windowName() {
    const w = TDx().window;
    if (!w || w === 'settings') return 'Settings';
    const f = (TDx().windows || []).find((x) => x.id === w);
    return f && f.name ? f.name : 'Settings';
  }
  function pins() { try { return TDx().pins ? TDx().pins() || [] : []; } catch (e) { return []; } }

  function onScreen(sel, all) {
    if (!sel) return 'Nothing is selected.';
    if (sel.status === 'loading') return 'Still loading.';
    const t = sel.trend, g = t && t.guidance, fmt = TDx().fmt || {};
    if (!t) return 'Nothing is selected.';
    const parts = [];
    try {
      const rate = fmt.rate ? fmt.rate(t) : '';
      if (g) {
        let a = windowName();
        if (rate) a += ` ${rate}${g.rate && g.rate.per ? ' ' + g.rate.per : ''}`;
        if (g.risk_label) a += `, ${g.risk_label}`;
        const look = window.TDPrefs ? window.TDPrefs.get().lookAhead : null;
        const o = fmt.outlook && look ? fmt.outlook(t, look) : '';
        if (o) a += `, ${o} by ${look}${g.outlook_label ? ' ' + g.outlook_label.charAt(0).toLowerCase() + g.outlook_label.slice(1) : ''}`;
        parts.push(a + '.');
      } else if (t.meaning && t.meaning.comparison) parts.push(oneLine(t.meaning.comparison));
    } catch (e) { /* show what we have */ }
    const others = all.filter((p) => p !== sel && p.status === 'ok' && p.trend && p.trend.guidance)
      .map((p) => `${p.label} (${p.trend.guidance.risk_label})`);
    if (others.length) parts.push(`Also pinned: ${others.join(', ')}.`);
    return parts.join(' ') || 'Nothing is selected.';
  }

  function vars() {
    const all = pins(), sel = all.find((p) => p.selected) || null;
    const on = TDx().window === 'settings' ? 'The Settings page is open.' : onScreen(sel, all);
    return JSON.stringify({
      current_window: oneLine(windowName()),
      current_place: sel && sel.label ? oneLine(sel.label) : 'none',
      on_screen: cut(oneLine(on), 300),
    });
  }

  let widget = null;
  function refresh() {
    if (!widget) return;
    const v = vars();
    if (widget.getAttribute('dynamic-variables') !== v) widget.setAttribute('dynamic-variables', v);
  }

  function mount() {
    if (widget) return;
    widget = document.createElement('elevenlabs-convai');
    widget.setAttribute('agent-id', CHAT_AGENT_ID);
    widget.setAttribute('dynamic-variables', vars());
    slot.append(widget);
    const s = document.createElement('script');
    s.src = CHAT_EMBED_SRC;
    s.async = true;
    document.body.append(s); // if it fails to load the element stays empty and the page works
  }

  ['td:route', 'td:pins', 'td:prefs'].forEach((ev) => document.addEventListener(ev, refresh));
  const ready = TDx().ready;
  if (ready && typeof ready.then === 'function') ready.then(mount, mount);
  else document.addEventListener('td:ready', mount, { once: true });
})();
