// Core helpers: state, API client, safe DOM builder, formatting. No innerHTML with untrusted data anywhere.
export const state = {
  user: null, token: null, tenant: null, tenants: [], lang: 'en', config: null, strings: {}, fallback: {},
};

const store = {
  get(k) { try { return sessionStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { v === null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch { /* ignore */ } },
  getL(k) { try { return localStorage.getItem(k); } catch { return null; } },
  setL(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } },
};
export { store };

export class ApiError extends Error {
  constructor(status, body) {
    const e = (body && body.error) || {};
    super(e.message || `Request failed (${status})`);
    this.status = status; this.code = e.code; this.body = body; this.fields = e.fields || [];
  }
}

export async function api(path, { method = 'GET', body, form, query, raw, quiet } = {}) {
  const url = new URL(path, window.location.origin);
  const q = { ...(query || {}) };
  if (!state.token && state.tenant && !('tenant' in q)) q.tenant = state.tenant;
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  let res;
  try { res = await fetch(url, { method, headers, body: payload }); }
  catch { throw new ApiError(0, { error: { code: 'network', message: 'Network error - check your connection and retry.' } }); }
  if (raw) { if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null)); return res; }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (res.status === 401 && state.token && !['bad_credentials', 'otp_invalid', 'otp_expired'].includes(data?.error?.code)) {
    // The active account's session is no longer valid: drop it and return to the sign-in page (or the next saved account).
    setSession(null, null);
    if (!quiet) toast(t('shell.session_ended'), true);
    document.dispatchEvent(new CustomEvent('signedout'));
  }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

// ---------------------------------------------------------------- multi-account sessions
// Several accounts (e.g. a citizen and an officer, or two officers) can stay signed in on one device;
// the account menu switches between them instantly. Tokens are short-lived (TOKEN_TTL_MINUTES).
function loadAccounts() {
  try { return JSON.parse(store.getL('jansetu.accounts') || '[]'); } catch { return []; }
}
function saveAccounts(list) { store.setL('jansetu.accounts', JSON.stringify(list)); }

export function accounts() { return loadAccounts(); }

export function setSession(token, user) {
  let list = loadAccounts();
  if (token && user) {
    list = list.filter(a => a.user.id !== user.id);
    list.unshift({ token, user, added: Date.now() });
    saveAccounts(list.slice(0, 8));
    store.setL('jansetu.active', user.id);
  } else if (state.user) {
    // sign out the active account only
    list = list.filter(a => a.user.id !== state.user.id);
    saveAccounts(list);
    const next = list[0];
    store.setL('jansetu.active', next ? next.user.id : '');
    token = next?.token || null; user = next?.user || null;
  }
  state.token = token; state.user = user;
  document.dispatchEvent(new CustomEvent('session'));
}

export function switchAccount(userId) {
  const acc = loadAccounts().find(a => a.user.id === userId);
  if (!acc) return false;
  store.setL('jansetu.active', userId);
  state.token = acc.token; state.user = acc.user;
  document.dispatchEvent(new CustomEvent('session'));
  return true;
}

export function forgetAccount(userId) {
  saveAccounts(loadAccounts().filter(a => a.user.id !== userId));
}

export function clearAllAccounts() {
  saveAccounts([]); store.setL('jansetu.active', '');
  state.token = null; state.user = null;
  document.dispatchEvent(new CustomEvent('session'));
}

export function updateActiveUser(user) {
  const list = loadAccounts().map(a => (a.user.id === user.id ? { ...a, user } : a));
  saveAccounts(list);
  state.user = user;
}

export function restoreSession() {
  const list = loadAccounts();
  const active = store.getL('jansetu.active');
  const acc = list.find(a => a.user.id === active) || null;
  if (acc) { state.token = acc.token; state.user = acc.user; }
}

// ---------------------------------------------------------------- DOM builder
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, String(v));
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

export function svg(tag, attrs = {}, ...children) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) el.setAttribute(k, String(v));
  for (const c of children.flat(Infinity)) if (c) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}

export function mount(root, ...children) { root.replaceChildren(); append(root, children); }

// ---------------------------------------------------------------- i18n
export function t(key, vars) {
  let s = state.strings[key] ?? state.fallback[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

// ---------------------------------------------------------------- feedback
export function toast(msg, bad = false) {
  const box = document.getElementById('toast');
  const el = h('div', { class: 't' + (bad ? ' bad' : '') }, msg);
  box.append(el);
  setTimeout(() => el.remove(), 4500);
}

export function errorBox(err, onRetry) {
  const msg = err instanceof ApiError ? err.message : String(err?.message || err);
  return h('div', { class: 'notice bad', role: 'alert' },
    h('strong', {}, t('common.error') + ': '), msg,
    err?.fields?.length ? h('ul', {}, err.fields.map(f => h('li', {}, `${f.field}: ${f.message}`))) : null,
    err?.body?.error?.fallback ? h('div', { class: 'small' }, err.body.error.fallback) : null,
    onRetry ? h('div', {}, h('button', { onclick: onRetry }, t('common.retry'))) : null);
}

export function loading(label) { return h('div', { class: 'empty' }, h('span', { class: 'spinner' }), ' ', label || t('common.loading')); }
export function empty(label) { return h('div', { class: 'empty' }, label || t('common.empty')); }

// ---------------------------------------------------------------- formatting
export function fmtDate(iso, withTime = true) {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleString(state.lang === 'en' ? 'en-IN' : `${state.lang}-IN`,
    withTime ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' });
}
export function fmtDuration(sec) {
  if (sec === null || sec === undefined) return '-';
  const neg = sec < 0; const s = Math.abs(sec);
  const d = Math.floor(s / 86400), hh = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  const txt = d ? `${d}d ${hh}h` : hh ? `${hh}h ${m}m` : `${m}m`;
  return neg ? `-${txt}` : txt;
}
export function pct(v) { return v === null || v === undefined ? '-' : `${v}%`; }

const STATUS_CLASS = { submitted: 'info', human_review: 'warn', accepted: 'info', in_progress: 'info', info_requested: 'warn',
  resolved: 'ok', closed: 'ok', rejected: 'bad', reopened: 'warn' };
export function statusChip(status, label) { return h('span', { class: `chip ${STATUS_CLASS[status] || ''}` }, label || t(`status.${status}`)); }
const PRI_CLASS = { Emergency: 'bad', High: 'warn', Medium: 'info', Low: '' };
export function priorityChip(p) { return p ? h('span', { class: `chip ${PRI_CLASS[p] || ''}` }, t(`priority.${p}`)) : h('span', { class: 'chip' }, t('priority.none')); }
const SLA_CLASS = { on_track: 'ok', at_risk: 'warn', breached: 'bad', met: 'ok', missed: 'bad', stopped: '', not_started: '' };
export function slaChip(sla) {
  if (!sla) return null;
  const extra = sla.remaining_seconds !== null && sla.remaining_seconds !== undefined ? ` (${fmtDuration(sla.remaining_seconds)})` : '';
  return h('span', { class: `chip ${SLA_CLASS[sla.state] || ''}` }, t(`sla.${sla.state}`) + extra);
}
export function simChip(text) { return h('span', { class: 'chip sim' }, text || t('common.test_data')); }

export function kv(pairs) {
  return h('dl', { class: 'kv' }, pairs.filter(Boolean).map(([k, v]) => [h('dt', {}, k), h('dd', {}, v ?? '-')]));
}

export function field(labelText, input, hint) {
  const id = input.id || `f-${Math.random().toString(36).slice(2, 9)}`;
  input.id = id;
  return h('div', { class: 'field' }, h('label', { for: id }, labelText), input, hint ? h('div', { class: 'hint' }, hint) : null);
}

export function select(options, value, attrs = {}) {
  return h('select', attrs, options.map(o => h('option', { value: o.value, selected: String(o.value) === String(value) }, o.label)));
}

export function table(columns, rows, { onRow, empty: emptyText, rowClass } = {}) {
  if (!rows.length) return empty(emptyText);
  return h('div', { class: 'table-wrap' }, h('table', {},
    h('thead', {}, h('tr', {}, columns.map(c => h('th', { scope: 'col' }, c.label)))),
    h('tbody', {}, rows.map(r => h('tr', {
      class: [(onRow ? 'clickable' : ''), rowClass ? rowClass(r) : ''].join(' ').trim() || null,
      tabindex: onRow ? 0 : null,
      onclick: onRow ? () => onRow(r) : null,
      onkeydown: onRow ? (e) => { if (e.key === 'Enter') onRow(r); } : null,
    }, columns.map(c => h('td', {}, c.render ? c.render(r) : (r[c.key] ?? '-'))))))));
}

export function tabs(items, active, onChange) {
  return h('div', { class: 'tabs', role: 'tablist' }, items.map(([id, label]) => h('button', {
    role: 'tab', 'aria-selected': String(id === active), onclick: () => onChange(id),
  }, label)));
}

export function download(filename, text, type = 'application/json') {
  const blob = new Blob([text], { type });
  const a = h('a', { href: URL.createObjectURL(blob), download: filename });
  document.body.append(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}

export function hasPerm(p) { return !!state.user?.permissions?.includes(p); }
export function initials(name) {
  return (name || '?').replace(/\(.*?\)/g, '').trim().split(/\s+/).slice(0, 2).map(w => w[0] || '').join('').toUpperCase() || '?';
}

export function navigate(path) { history.pushState({}, '', path); window.dispatchEvent(new Event('popstate')); }
