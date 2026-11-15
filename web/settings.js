'use strict';
/* Settings window, built into #settings-slot once TD is ready. Reads TDPrefs, writes TDPrefs.set, redraws values on td:prefs.
   The "Use in your AI" content moved here from connect.js. */
(function () {
  const slot = document.getElementById('settings-slot');
  if (!slot) return;

  function h(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const k in attrs || {}) n.setAttribute(k, attrs[k]);
    kids.forEach((c) => n.append(c));
    return n;
  }
  const code = (t) => h('code', null, t);

  const sync = []; // functions that refresh controls from TDPrefs.get()
  const prefs = () => window.TDPrefs.get();

  /* ---------- option cards (radio) ---------- */
  function radioCards(name, label, options, current, write) {
    const box = h('div', { class: 'st-opts', role: 'radiogroup', 'aria-label': label });
    const inputs = options.map((o) => {
      const input = h('input', { type: 'radio', name: 'st-' + name, value: o.value });
      input.addEventListener('change', () => write(o.value));
      const text = h('span', { class: 'st-opt-text' }, h('b', null, o.label));
      if (o.sub) text.append(h('small', null, o.sub));
      box.append(h('label', { class: 'st-opt' }, input, o.swatch ? h('span', { class: 'st-sw st-sw-' + o.value, 'aria-hidden': 'true' }) : '', text));
      return input;
    });
    sync.push(() => { const v = current(); inputs.forEach((i) => { i.checked = i.value === v; }); });
    return box;
  }

  /* ---------- maps table ---------- */
  const mapOf = (id) => Object.assign({ base: 'light', labels: true, stations: true }, (prefs().maps || {})[id]);
  function setMap(id, patch) { window.TDPrefs.set({ maps: { [id]: Object.assign(mapOf(id), patch) } }); }

  function switchCell(id, key, label) {
    const input = h('input', { type: 'checkbox', role: 'switch', class: 'st-switch', 'aria-label': label });
    input.addEventListener('change', () => setMap(id, { [key]: input.checked }));
    sync.push(() => { input.checked = !!mapOf(id)[key]; });
    return h('label', { class: 'st-tg' }, input, h('span', { class: 'st-tg-track', 'aria-hidden': 'true' }));
  }

  function mapsTable(windows) {
    const tbody = h('tbody');
    windows.forEach((w) => {
      const seg = h('div', { class: 'seg st-seg', role: 'radiogroup', 'aria-label': w.name + ' base map' });
      const radios = [['light', 'Light'], ['detailed', 'Detailed']].map(([v, t]) => {
        const input = h('input', { type: 'radio', name: 'st-base-' + w.id, value: v });
        input.addEventListener('change', () => setMap(w.id, { base: v }));
        seg.append(h('label', null, input, h('span', null, t)));
        return input;
      });
      sync.push(() => { const b = mapOf(w.id).base; radios.forEach((r) => { r.checked = r.value === b; }); });
      const stations = w.id === 'sea_level' ? switchCell(w.id, 'stations', w.name + ' measuring stations') : h('span', null, '—');
      tbody.append(h('tr', null,
        h('th', { scope: 'row' }, w.name),
        h('td', null, seg),
        h('td', null, switchCell(w.id, 'labels', w.name + ' place labels')),
        h('td', null, stations)));
    });
    const head = h('tr', null, ...['Window', 'Base map', 'Place labels', 'Measuring stations'].map((t) => h('th', { scope: 'col' }, t)));
    return h('div', { class: 'st-scroll' }, h('table', { class: 'st-table' }, h('thead', null, head), tbody));
  }

  /* ---------- copy ---------- */
  const status = h('p', { class: 'st-sr', role: 'status' });
  const COPIED = { 'server address': 'Copied the server address.', command: 'Copied the command.', config: 'Copied the config.' };

  async function copyText(text, node) {
    try {
      if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
    } catch (e) { /* fall through */ }
    if (node.select) { node.focus(); node.select(); } else {
      const r = document.createRange(); r.selectNodeContents(node);
      const s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
    }
    try { return document.execCommand('copy'); } catch (e) { return false; }
  }

  // A copy row around a text node (input or pre). kind is "server address" | "command" | "config".
  function copyRow(node, kind) {
    const btn = h('button', { type: 'button', class: 'btn st-copy', 'aria-label': 'Copy ' + kind }, 'Copy');
    const fail = h('p', { class: 'small st-fail', hidden: '' });
    const wrap = h('div', { class: 'st-copywrap' }, h('div', { class: 'st-copyrow' }, node, btn), fail);
    if (node.tagName === 'PRE' && window.ResizeObserver) { // hint only while the text is cut off
      const hint = h('p', { class: 'small st-fail', hidden: '' }, (matchMedia('(pointer: coarse)').matches ? 'Swipe' : 'Scroll') + ' sideways to see the whole line.');
      wrap.append(hint);
      new ResizeObserver(() => { hint.hidden = !(node.scrollWidth > node.clientWidth + 1); }).observe(node);
    }
    let timer = 0;
    btn.addEventListener('click', async () => {
      const ok = await copyText(node.value !== undefined ? node.value : node.textContent, node);
      clearTimeout(timer);
      btn.textContent = ok ? 'Copied' : 'Copy failed';
      fail.hidden = ok;
      fail.textContent = ok ? '' : 'Select the text and copy it yourself.';
      status.textContent = '';
      setTimeout(() => { status.textContent = ok ? COPIED[kind] : 'Copy failed. Select the text and copy it yourself.'; }, 50);
      timer = setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
    return wrap;
  }

  /* ---------- Use in your AI ---------- */
  const ADDR = location.origin + '/mcp';
  const addrInput = (id) => {
    const i = h('input', { id, class: 'st-addr', type: 'text', readonly: '', value: ADDR });
    i.addEventListener('focus', () => i.select());
    return i;
  };
  const server = { type: 'http', url: ADDR };

  // Text between backticks becomes <code>.
  function rich(text) {
    const p = document.createDocumentFragment();
    text.split('`').forEach((t, i) => { if (t) p.append(i % 2 ? code(t) : t); });
    return p;
  }
  function steps(list) {
    const ol = h('ol');
    list.forEach((t) => ol.append(h('li', null, rich(t))));
    return ol;
  }
  const docLink = (text, url) => h('a', { class: 'st-link', href: url, target: '_blank', rel: 'noopener' }, text + ' ↗');

  const APPS = [
    { id: 'claude', name: 'Claude', sub: 'claude.ai and Claude desktop',
      steps: ['Open Customize, then Connectors.', 'Click "+ Add", then "Add custom connector".', 'Enter the name "Trend Detective" and paste the server address, then click "Continue".', 'Under Authentication choose "No sign in", then click "Add".', 'In a chat, click "+" at the lower left, then "Connectors", and switch Trend Detective on.'],
      note: 'Free plans can add one custom connector. On Team and Enterprise plans an owner has to add it.',
      links: [['Claude setup docs', 'https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp']], checked: true },
    { id: 'claude-code', name: 'Claude Code', sub: 'In your terminal',
      steps: ['In your terminal run the command in the box.'],
      cmd: 'claude mcp add --transport http trend-detective ' + ADDR,
      steps2: ['Start Claude Code and type `/mcp`. Trend Detective should show as connected.', 'Optional: add `--scope user` to the command to use it in every project.'],
      note: 'The command `claude mcp list` also shows it.',
      links: [['Claude Code setup docs', 'https://code.claude.com/docs/en/mcp']], checked: true },
    { id: 'cursor', name: 'Cursor', sub: 'Config file',
      steps: ['Create or open `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project).', 'Paste the entry from "Prefer a settings file?" below, using `url` and no `type`.', 'Open Customize and check that Trend Detective is listed and on.'],
      note: 'We could not confirm the menu names for adding a server in the Cursor app, so we show the config file instead.',
      links: [['Cursor setup docs', 'https://cursor.com/docs/context/mcp']], checked: true },
    { id: 'vscode', name: 'VS Code', sub: 'With GitHub Copilot',
      steps: ['Open the Command Palette and run "MCP: Add Server".', 'Choose "HTTP (HTTP or Server-Sent Events)" and paste the server address.', 'Name it "trend-detective", then choose Global (or the workspace if you prefer).', 'Accept the trust prompt after reading it, then ask GitHub Copilot a question and look for Trend Detective\'s tools.'],
      note: 'Or put the VS Code block from "Prefer a settings file?" in `.vscode/mcp.json`. VS Code uses `servers`, not `mcpServers`.',
      links: [['VS Code MCP servers docs', 'https://code.visualstudio.com/docs/copilot/customization/mcp-servers'], ['VS Code MCP configuration reference', 'https://code.visualstudio.com/docs/agents/reference/mcp-configuration']], checked: true },
    { id: 'other', name: 'Any other AI agent', sub: 'Any MCP client',
      steps: ['Open your AI agent\'s settings for MCP servers or connectors.', 'Add a new server.', 'Paste this address. No key and no sign-in are needed.'],
      note: 'If it asks for a type, choose "HTTP" or "streamable HTTP".',
      links: [['About MCP', 'https://modelcontextprotocol.io']] },
  ];

  function appCard(a) {
    const box = h('details', { class: 'st-app' }, h('summary', null, h('b', null, a.name), a.sub ? h('small', null, a.sub) : ''));
    box.append(steps(a.steps));
    if (a.cmd) {
      box.append(copyRow(h('pre', { role: 'group', tabindex: '0', 'aria-label': a.name + ' command' }, code(a.cmd)), 'command'));
      const ol = steps(a.steps2);
      ol.start = 2;
      box.append(ol);
    }
    box.append(h('label', { for: 'st-addr-' + a.id }, 'Trend Detective server address'), copyRow(addrInput('st-addr-' + a.id), 'server address'));
    if (a.note) box.append(h('p', { class: 'small' }, rich(a.note)));
    a.links.forEach(([t, u]) => box.append(docLink(t, u)));
    if (a.checked) box.append(h('p', { class: 'small' }, 'Checked 14 November 2026'));
    return box;
  }

  const CONFIGS = [
    ['Claude Code', 'project file `.mcp.json`. Claude Code needs `"type": "http"`.', { mcpServers: { 'trend-detective': server } }],
    ['Cursor', 'file `mcp.json`. No `type`.', { mcpServers: { 'trend-detective': { url: ADDR } } }],
    ['VS Code', 'file `.vscode/mcp.json`.', { servers: { 'trend-detective': server } }],
  ];

  function connectSection() {
    const frag = document.createDocumentFragment();
    frag.append(
      h('p', { class: 'st-lead' }, 'Connect an AI app to Trend Detective and ask it whether something is really changing at a place. The AI calls our tools. The trend, range and verdict are our calculation from public data, with the source named.'),
      h('p', { class: 'small' }, 'Works with AI agents such as Claude and GitHub Copilot.'),
      h('p', null, 'MCP is a standard way for an AI app to use outside tools. Adding this server lets your AI look up these trends itself.'),
      h('label', { for: 'st-addr-top' }, 'Trend Detective server address'),
      copyRow(addrInput('st-addr-top'), 'server address'),
      h('p', { class: 'small' }, 'This address is for AI apps. It is not a web page. It needs no key and no sign-in.'),
      status,
      h('h3', null, 'Pick your AI app'),
      h('div', { class: 'st-apps' }, ...APPS.map(appCard)),
      h('h3', null, 'Prefer a settings file?'),
      h('p', null, 'Paste this into your app\'s settings file instead of following the steps above. Field names differ between apps, so match yours.'));
    CONFIGS.forEach(([name, note, obj]) => {
      frag.append(h('p', { class: 'small' }, name + ', ', rich(note)),
        copyRow(h('pre', { role: 'group', tabindex: '0', 'aria-label': name + ' config' }, code(JSON.stringify(obj, null, 2))), 'config'));
    });
    const dl = h('dl', { class: 'st-tools' });
    [['list_variables', 'Lists what we can measure, such as air temperature and sea level, and where the data come from.'],
      ['get_series', 'Gets the month-by-month values for a place.'],
      ['detect_trend', 'Says whether it is changing at a place, how fast, and how sure we are, using the Mann-Kendall test and Sen\'s slope.']]
      .forEach(([t, d]) => dl.append(h('div', null, h('dt', null, code(t)), h('dd', null, d))));
    frag.append(h('h3', null, 'What you can ask once connected'), dl,
      h('p', null, 'Try asking:'),
      h('ul', null, ...['Is sea level rising in New York?', 'Are the hottest days getting hotter in Delhi?', 'Has anything changed in Visakhapatnam (17.69, 83.22) since 1981?'].map((q) => h('li', null, q))),
      h('p', { class: 'small' }, 'Your AI app may ask your permission before it calls a tool.'),
      h('h3', null, 'What it can and can\'t do'),
      h('p', null, 'It can read public climate data from the sources named next to each result. It can\'t see your files, your chats or anything else on your device, and it can\'t change anything. It only reads.'));
    return frag;
  }

  /* ---------- Privacy ---------- */
  function forgetAll() {
    if (!confirm('Forget your pinned places and settings in this browser? This cannot be undone.')) return;
    try {
      Object.keys(localStorage).filter((k) => k.indexOf('td.') === 0).forEach((k) => localStorage.removeItem(k));
    } catch (e) { /* storage unavailable: nothing to forget */ }
    location.reload();
  }
  function privacySection() {
    const frag = document.createDocumentFragment();
    frag.append(h('ul', { class: 'st-facts' },
      ...['No account.',
        'Your pinned places and these settings are kept in this browser; we don\'t store them on our server.',
        'Place names you type in the search box go to our server, and from there to Open-Meteo\'s place search.',
        'The map loads its tiles from OpenFreeMap, and the assistant\'s code loads from unpkg.com; each sees your network address, like any website you visit.',
        'The assistant runs on ElevenLabs; if you talk or type to it, your voice and the conversation are processed by ElevenLabs.',
        'When you use the assistant, the page tells it which window is open and which places you have pinned, so it can answer about what you see.',
        'To answer, the assistant sends your question to our server, which passes it to our AI model provider. Questions and answers are recorded by a quality-checking service (Langfuse). Don\'t include personal details.',
        'Our server counts requests from each network address for a short time, to stop overuse.'].map((t) => h('li', null, t))));
    const btn = h('button', { type: 'button', class: 'btn' }, 'Forget my places and settings');
    btn.addEventListener('click', forgetAll);
    frag.append(btn);
    return frag;
  }

  /* ---------- build ---------- */
  function build() {
    const secs = [
      ['appearance', 'Appearance', 'Choose how Trend Detective looks. Light is the default.', () => radioCards('theme', 'Theme', [
        { value: 'light', label: 'Light', swatch: 1 }, { value: 'dark', label: 'Dark', swatch: 1 }, { value: 'device', label: 'Match my device', swatch: 1 }],
        () => prefs().theme, (v) => window.TDPrefs.set({ theme: v }))],
      ['units', 'Units', 'Used in every window.', () => radioCards('units', 'Units', [
        { value: 'metric', label: 'Metric', sub: 'cm, °C' }, { value: 'imperial', label: 'Imperial', sub: 'in, °F' }],
        () => prefs().units, (v) => window.TDPrefs.set({ units: v }))],
      ['maps', 'Maps', 'Map options for each window.', () => mapsTable(window.TD.windows)],
      ['connect', 'Use in your AI', null, connectSection],
      ['privacy', 'Privacy & data', null, privacySection],
    ];
    const nav = h('nav', { class: 'st-nav', 'aria-label': 'Settings sections' });
    const main = h('div', { class: 'st-sections' });
    const links = {};
    const mark = (cur) => { for (const id in links) { if (id === cur) links[id].setAttribute('aria-current', 'true'); else links[id].removeAttribute('aria-current'); } };
    secs.forEach(([id, title, lead, body]) => {
      const sec = h('section', { class: 'card st-sec', id: 'st-' + id, 'aria-labelledby': 'st-h-' + id }, h('h2', { id: 'st-h-' + id }, title));
      if (lead) sec.append(h('p', { class: 'st-lead' }, lead));
      sec.append(body());
      main.append(sec);
      const a = h('button', { type: 'button', class: 'st-navlink' }, title);
      a.addEventListener('click', () => {
        sec.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
        mark(id);
      });
      links[id] = a;
      nav.append(a);
    });
    // Current = the last section whose top is at or above 120 px from the viewport top; the last one at the page bottom.
    const secEls = Array.from(main.children);
    const track = () => {
      if (!secEls[0].offsetParent) return; // Settings window hidden
      let cur = secEls[0];
      secEls.forEach((s) => { if (s.getBoundingClientRect().top <= 120) cur = s; });
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) cur = secEls[secEls.length - 1];
      mark(cur.id.slice(3));
    };
    window.addEventListener('scroll', track, { passive: true });
    window.addEventListener('resize', track);
    document.addEventListener('td:route', track);
    mark('appearance');
    slot.replaceChildren(h('div', { class: 'st-layout' }, nav, main));
    const refresh = () => sync.forEach((f) => f());
    refresh();
    track();
    document.addEventListener('td:prefs', refresh);
  }

  (window.TD && window.TD.ready ? window.TD.ready : new Promise((r) => document.addEventListener('td:ready', r, { once: true }))).then(build);
})();
