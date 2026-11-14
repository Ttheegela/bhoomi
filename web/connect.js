'use strict';
/* "Use in your AI" tab: per-app tabs, config tabs and Copy buttons. Loaded after app.js (uses el, $, wireTablist,
   selectTab, tabState, APPS, writeHash). The steps themselves are static HTML in index.html. */

const APP_LABELS = { claude: 'Claude', 'claude-code': 'Claude Code', cursor: 'Cursor', vscode: 'VS Code', other: 'Any other AI agent' };
const CFG_IDS = ['claude-code', 'cursor', 'vscode'];
const COPIED_SAYS = { 'server address': 'Copied the server address.', command: 'Copied the command.', config: 'Copied the config.' };

// A tablist built from ids, over panels "<panelPrefix><id>". Returns the select function.
function buildSubTabs(boxId, ids, label, tabPrefix, panelPrefix, onPick) {
  const box = $(boxId);
  box.setAttribute('role', 'tablist');
  box.setAttribute('aria-label', label);
  const tabs = ids.map((id) => {
    const b = el('button', { type: 'button', role: 'tab', id: tabPrefix + id, 'aria-controls': panelPrefix + id, class: 'tab' }, APP_LABELS[id]);
    box.append(b);
    return b;
  });
  const panels = ids.map((id) => {
    const p = $(panelPrefix + id);
    p.setAttribute('role', 'tabpanel');
    p.setAttribute('aria-labelledby', tabPrefix + id);
    return p;
  });
  const select = (i) => selectTab(tabs, panels, i);
  wireTablist(tabs, (i) => { select(i); onPick(ids[i]); });
  select(0);
  return (id) => select(Math.max(0, ids.indexOf(id)));
}

let selectApp = () => {};
function setApp(app) { tabState.app = app; selectApp(app); }

/* ---------- Copy ---------- */

function selectNode(node) {
  if (node.select) { node.focus(); node.select(); return; }
  const r = document.createRange();
  r.selectNodeContents(node);
  const s = window.getSelection();
  s.removeAllRanges();
  s.addRange(r);
}
// Resolves true when the text reached the clipboard; otherwise the text is left selected.
async function copyText(text, node) {
  try {
    if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
  } catch (e) { /* fall through */ }
  selectNode(node);
  try { return document.execCommand('copy'); } catch (e) { return false; }
}

function addCopyButtons() {
  const status = $('copy-status');
  document.querySelectorAll('#panel-connect [data-copy]').forEach((node) => {
    const kind = node.getAttribute('data-copy');
    const row = node.parentNode;
    const btn = el('button', { type: 'button', class: 'btn copy-btn', 'aria-label': 'Copy ' + kind }, 'Copy');
    const fail = el('p', { class: 'small copy-fail', hidden: '' });
    row.append(btn);
    row.after(fail);
    if (node.tagName === 'PRE' && window.ResizeObserver) { // a hint only while the text is actually cut off (the panel is hidden until its tab is chosen; the observer fires when it shows or resizes)
      const hint = el('p', { class: 'small scroll-hint', hidden: '' }, scrollHintText(matchMedia('(pointer: coarse)').matches));
      fail.after(hint);
      new ResizeObserver(() => { hint.hidden = !(node.scrollWidth > node.clientWidth + 1); }).observe(node);
    }
    let timer = 0;
    btn.addEventListener('click', async () => {
      const text = node.value !== undefined ? node.value : node.textContent;
      const ok = await copyText(text, node);
      clearTimeout(timer);
      btn.textContent = ok ? 'Copied' : 'Copy failed';
      fail.hidden = ok; // after "Copy failed" the line stays until the next click
      fail.textContent = ok ? '' : 'Select the text and copy it yourself.';
      status.textContent = '';
      setTimeout(() => { status.textContent = ok ? COPIED_SAYS[kind] : 'Copy failed. Select the text and copy it yourself.'; }, 50);
      timer = setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
  });
  document.querySelectorAll('.addr').forEach((i) => i.addEventListener('focus', () => i.select()));
}

/* ---------- start ---------- */

selectApp = buildSubTabs('apptabs', APPS, 'AI apps', 'tab-app-', 'app-', (id) => {
  tabState.app = id;
  if (tabState.tab === 'connect') history.replaceState(null, '', '#' + writeHash({ tab: 'connect', app: id }));
});
buildSubTabs('cfgtabs', CFG_IDS, 'Config files', 'tab-cfg-', 'cfg-', () => {});
addCopyButtons();
setApp(parseHash(location.hash).app);
