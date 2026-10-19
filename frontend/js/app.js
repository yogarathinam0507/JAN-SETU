import { accounts, api, clearAllAccounts, fmtDate, forgetAccount, h, initials, mount, navigate, restoreSession, setSession,
  state, store, switchAccount, t, toast, updateActiveUser } from './core.js';
import { icon } from './icons.js';

const UI_LANGS = ['en', 'kn', 'hi', 'ta'];
const RTL = ['ur', 'sd', 'ks'];
const ALL = null; // any signed-in role

// path -> [module file, roles allowed (ALL = any signed-in user)]. Everything except PUBLIC requires sign-in.
const ROUTES = {
  '/dashboard': ['dashboard', ALL],
  '/citizen': ['citizen', ['citizen']], '/citizen/tickets': ['tickets', ['citizen']],
  '/benefits': ['benefits', ALL], '/assist': ['benefits', ALL],
  '/map': ['livemap', ['officer', 'nodal', 'hod', 'auditor', 'vendor', 'agent']],
  '/agent': ['agent', ['agent', 'hod', 'auditor']], '/officer': ['officer', ['officer', 'nodal']],
  '/nodal': ['nodal', ['nodal']], '/vendor': ['vendor', ['vendor']], '/admin': ['admin', ['admin']],
  '/analytics': ['analytics', ['officer', 'nodal', 'hod', 'auditor', 'admin']],
  '/monitoring': ['monitoring', ['nodal', 'hod', 'auditor', 'admin']],
  '/knowledge': ['knowledge', ['content', 'agent', 'officer', 'nodal', 'hod', 'auditor']],
  '/audit': ['audit', ['auditor']],
  '/evidence': ['evidence', ['admin', 'auditor']], '/integrations': ['integrations', ['admin', 'auditor']],
  '/health': ['health', ['admin', 'auditor']],
};
const PUBLIC = { '/login': 'login', '/privacy': 'privacy', '/accessibility': 'info', '/terms': 'info', '/help': 'info' };

// [href, i18n key, icon]
const NAV = {
  citizen: [['/dashboard', 'nav.dashboard', 'dashboard'], ['/citizen', 'nav.file', 'edit'], ['/citizen/tickets', 'nav.mytickets', 'list'],
    ['/benefits', 'nav.benefits', 'hand']],
  agent: [['/dashboard', 'nav.dashboard', 'dashboard'], ['/agent', 'nav.agent', 'headset'], ['/map', 'nav.map', 'map'],
    ['/benefits', 'nav.benefits', 'hand'], ['/knowledge', 'nav.knowledge', 'book']],
  officer: [['/dashboard', 'nav.dashboard', 'dashboard'], ['/officer', 'nav.officer', 'clipboard'], ['/map', 'nav.map', 'map'],
    ['/analytics', 'nav.analytics', 'chart'], ['/knowledge', 'nav.knowledge', 'book']],
  nodal: [['/dashboard', 'nav.dashboard', 'dashboard'], ['/nodal', 'nav.nodal', 'route'], ['/officer', 'nav.officer', 'clipboard'],
    ['/map', 'nav.map', 'map'], ['/analytics', 'nav.analytics', 'chart'], ['/monitoring', 'nav.monitoring', 'activity']],
  hod: [['/dashboard', 'nav.dashboard', 'dashboard'], ['/analytics', 'nav.analytics', 'chart'], ['/map', 'nav.map', 'map'],
    ['/monitoring', 'nav.monitoring', 'activity'], ['/agent', 'nav.callcentre', 'headset']],
  vendor: [['/dashboard', 'nav.dashboard', 'dashboard'], ['/vendor', 'nav.vendor', 'tool'], ['/map', 'nav.map', 'map']],
  auditor: [['/dashboard', 'nav.dashboard', 'dashboard'], ['/audit', 'nav.audit', 'shield'], ['/map', 'nav.map', 'map'],
    ['/analytics', 'nav.analytics', 'chart'], ['/monitoring', 'nav.monitoring', 'activity'], ['/agent', 'nav.callcentre', 'headset']],
  content: [['/dashboard', 'nav.dashboard', 'dashboard'], ['/knowledge', 'nav.knowledge', 'book'], ['/benefits', 'nav.benefits', 'hand']],
  admin: [['/dashboard', 'nav.dashboard', 'dashboard'], ['/admin', 'nav.admin', 'settings'], ['/monitoring', 'nav.monitoring', 'activity'],
    ['/analytics', 'nav.analytics', 'chart'], ['/integrations', 'nav.integrations', 'plug'], ['/health', 'nav.health', 'heart']],
};
export const HOME_FOR_ROLE = Object.fromEntries(Object.keys(NAV).map(r => [r, '/dashboard']));

async function loadStrings(lang) {
  const get = async (l) => (await fetch(`/static/i18n/${l}.json`)).json();
  if (!Object.keys(state.fallback).length) state.fallback = await get('en');
  state.strings = UI_LANGS.includes(lang) ? await get(lang) : {};
}

export async function setLanguage(lang, persist = true) {
  state.lang = lang;
  await loadStrings(lang);
  document.documentElement.lang = lang;
  document.documentElement.dir = RTL.includes(lang) ? 'rtl' : 'ltr';
  if (persist) store.setL('jansetu.lang', lang);
  if (state.token && persist) {
    api('/api/me/language', { method: 'PATCH', body: { language: lang } })
      .then(() => updateActiveUser({ ...state.user, language: lang })).catch(() => {});
  }
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  renderShell();
  route();
}

// ---------------------------------------------------------------- theme & text size
const THEMES = ['system', 'light', 'dark'];
const THEME_ICON = { system: 'monitor', light: 'sun', dark: 'moon' };

export function applyTheme(pref) {
  const dark = pref === 'dark' || (pref === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.documentElement.dataset.themePref = pref;
  store.setL('jansetu.theme', pref);
  const btn = document.getElementById('theme-toggle');
  if (btn) {
    mount(btn, icon(THEME_ICON[pref]), ' ', t('theme.' + pref));
    btn.title = `${t('theme.label')}: ${t('theme.' + pref)} - ${t('theme.click')}`;
    btn.setAttribute('aria-label', btn.title);
  }
}
function themePref() { return store.getL('jansetu.theme') || 'system'; }

function setFont(size) {
  if (size === 'md') delete document.documentElement.dataset.font; else document.documentElement.dataset.font = size;
  store.setL('jansetu.font', size === 'md' ? '' : size);
  ['sm', 'md', 'lg'].forEach(s => document.getElementById(`font-${s}`)?.setAttribute('aria-pressed', String(s === size)));
}

let languageRegistry = [];

function currentTenant() { return state.tenants.find(x => x.code === state.tenant) || {}; }

function renderShell() {
  const role = state.user?.role;
  const items = role ? (NAV[role] || []) : [];
  const nav = document.getElementById('nav');
  mount(nav, items.map(([href, key, ico]) => h('a', { href, 'data-link': true,
    class: isActive(href) ? 'active' : null, 'aria-current': isActive(href) ? 'page' : null }, icon(ico), t(key))));
  if (!role) nav.append(h('a', { href: '/login', 'data-link': true, class: location.pathname === '/login' ? 'active' : null }, icon('lock'), t('shell.login')));
  mount(document.getElementById('nav-toggle'), icon('menu'));
  const lsel = document.getElementById('lang-select');
  const tenantLangs = currentTenant().languages || UI_LANGS;
  const primary = languageRegistry.filter(l => tenantLangs.includes(l.code));
  const others = languageRegistry.filter(l => !tenantLangs.includes(l.code));
  mount(lsel,
    h('optgroup', { label: t('shell.full_ui') }, primary.map(l => h('option', { value: l.code, selected: l.code === state.lang }, l.native_name))),
    h('optgroup', { label: t('shell.registry_only') }, others.map(l => h('option', { value: l.code, selected: l.code === state.lang },
      `${l.native_name} - ${l.name}`))));
  renderAccountBox();
  renderNotifBox();
  applyTheme(themePref());
  const brand = currentTenant().branding || {};
  document.getElementById('brand-title').textContent = brand.title || 'JanSetu';
  document.getElementById('brand-sub').textContent = brand.subtitle || t('shell.tagline');
  document.getElementById('brand-region').textContent = currentTenant().name || '';
  document.getElementById('strip-region').textContent = currentTenant().name || '';
  mount(document.getElementById('helpline'), t('shell.helpline'), h('strong', {}, brand.helpline || '1800'));
  renderFooter(brand);
}

function isActive(href) {
  const p = location.pathname;
  return p === href || (href !== '/dashboard' && href !== '/citizen' && p.startsWith(href + '/')) ;
}

function renderFooter(brand) {
  const tn = currentTenant();
  const link = (href, key) => h('a', { href, 'data-link': true }, t(key));
  const signed = !!state.user;
  mount(document.getElementById('footer'),
    h('div', { class: 'container cols' },
      h('div', {}, h('h4', {}, t('footer.about')), h('p', {}, brand.title || 'JanSetu'),
        h('p', { class: 'small' }, t('footer.about_text', { region: tn.name || '' }))),
      h('div', {}, h('h4', {}, signed && state.user.role !== 'citizen' ? t('footer.quick') : t('footer.services')),
        signed && state.user.role === 'citizen' ? [link('/citizen', 'nav.file'), link('/citizen/tickets', 'nav.mytickets'), link('/benefits', 'nav.benefits')]
          : signed ? [link('/dashboard', 'nav.dashboard'), link('/benefits', 'nav.benefits')] : [link('/login', 'shell.login')]),
      h('div', {}, h('h4', {}, t('footer.help')),
        h('p', { class: 'small' }, `${t('shell.helpline')}: ${brand.helpline || '-'}`),
        (tn.emergency_contacts || []).map(c => h('p', { class: 'small', style: { margin: '2px 0' } }, `${c.label}: ${c.number}`))),
      h('div', {}, h('h4', {}, t('footer.policies')), link('/privacy', 'nav.privacy'), link('/accessibility', 'footer.accessibility'),
        link('/terms', 'footer.terms'), link('/help', 'footer.helpfaq'))),
    h('div', { class: 'container bottom' },
      h('span', {}, t('footer.copyright', { year: new Date().getFullYear() })),
      h('span', {}, t('footer.browsers'))));
}

// ---------------------------------------------------------------- notifications
let notifOpen = false, notifItems = [], notifTimer = null;
const seenKey = () => `jansetu.seen.${state.user?.id}`;

async function pollNotifications() {
  if (!state.user) { notifItems = []; renderNotifBox(); return; }
  try { notifItems = (await api('/api/notifications')).items || []; } catch { /* ignore */ }
  renderNotifBox();
}

function renderNotifBox() {
  const box = document.getElementById('notif-box');
  if (!state.user) { mount(box); return; }
  const seen = store.getL(seenKey()) || '';
  const unread = notifItems.filter(i => (i.at || '') > seen).length;
  mount(box, h('button', { class: 'icon-btn', 'aria-label': t('notif.title'), title: t('notif.title'), 'aria-haspopup': 'true',
    'aria-expanded': String(notifOpen), onclick: (e) => {
      e.stopPropagation(); notifOpen = !notifOpen; menuOpen = false;
      if (notifOpen && notifItems[0]) setTimeout(() => store.setL(seenKey(), notifItems[0].at || ''), 1500);
      renderAccountBox(); renderNotifBox();
    } }, icon('bell'), unread ? h('span', { class: 'badge' }, unread > 9 ? '9+' : String(unread)) : null),
  notifOpen ? h('div', { class: 'notif-menu', role: 'dialog', 'aria-label': t('notif.title'), onclick: (e) => e.stopPropagation() },
    h('div', { class: 'nh' }, t('notif.title'), h('button', { class: 'link', onclick: () => pollNotifications() }, t('common.refresh'))),
    notifItems.length ? notifItems.map(i => h('a', { class: `notif-item ${i.tone || ''}${(i.at || '') > seen ? ' unread' : ''}`, href: i.link || '#',
      'data-link': true, onclick: () => { notifOpen = false; } }, h('strong', {}, i.title), h('span', {}, i.body), h('time', {}, fmtDate(i.at))))
      : h('p', { class: 'muted small', style: { padding: '12px' } }, t('notif.none'))) : null);
}

function startNotifications() {
  clearInterval(notifTimer);
  notifItems = [];
  if (!state.user) return;
  pollNotifications();
  notifTimer = setInterval(() => { if (!document.hidden) pollNotifications(); }, 60000);
}

// ---------------------------------------------------------------- account menu (multi-login)
let menuOpen = false;

function renderAccountBox() {
  const ub = document.getElementById('user-box');
  const list = accounts();
  if (!state.user) { mount(ub); return; }
  const idx = list.findIndex(a => a.user.id === state.user.id);
  mount(ub, h('button', { class: 'account-btn', 'aria-haspopup': 'menu', 'aria-expanded': String(menuOpen), onclick: toggleMenu },
    h('span', { class: `avatar alt${idx % 4}` }, initials(state.user.full_name)),
    h('span', { class: 'who' }, h('span', { class: 'small' }, state.user.full_name), h('small', {}, state.user.designation || state.user.role_name)),
    list.length > 1 ? h('span', { class: 'chip' }, `+${list.length - 1}`) : null), menuOpen ? accountMenu(list) : null);
}

function toggleMenu(e) { e?.stopPropagation(); menuOpen = !menuOpen; notifOpen = false; renderNotifBox(); renderAccountBox(); }

function accountMenu(list) {
  return h('div', { class: 'account-menu', role: 'menu', onclick: (e) => e.stopPropagation() },
    h('div', { class: 'small muted', style: { padding: '4px 8px' } }, t('shell.signed_in_accounts')),
    list.map((a, i) => h('button', { class: `acct${a.user.id === state.user?.id ? ' current' : ''}`, role: 'menuitem',
      onclick: async () => {
        menuOpen = false;
        if (a.user.id === state.user?.id) { renderAccountBox(); return; }
        await activate(a.user.id);
      } },
    h('span', { class: `avatar alt${i % 4}` }, initials(a.user.full_name)),
    h('span', {}, a.user.full_name, h('small', {}, `${a.user.designation || a.user.role_name} - ${a.user.tenant.name}`)))),
    h('hr'),
    h('button', { class: 'menu-item', role: 'menuitem', onclick: () => { menuOpen = false; navigate('/login?add=1'); } }, icon('plus'), t('shell.add_account')),
    h('button', { class: 'menu-item', role: 'menuitem', onclick: logout }, icon('logout'), t('shell.logout')),
    list.length > 1 ? h('button', { class: 'menu-item', role: 'menuitem', onclick: logoutAll }, icon('x'), t('shell.logout_all')) : null);
}

export async function activate(userId) {
  switchAccount(userId);
  try { updateActiveUser(await api('/api/me', { quiet: true })); }
  catch { toast(t('shell.session_expired_for', { name: '' }), true); navigate('/login'); return; }
  state.tenant = state.user.tenant.code;
  toast(t('shell.switched', { name: state.user.full_name }));
  history.pushState({}, '', '/dashboard');
  startNotifications();
  await setLanguage(state.lang, false);
}

async function logout() {
  menuOpen = false;
  try { await api('/api/auth/logout', { method: 'POST', quiet: true }); } catch { /* ignore */ }
  setSession(null, null);
  startNotifications();
  if (state.user) { state.tenant = state.user.tenant.code; toast(t('shell.switched', { name: state.user.full_name })); }
  navigate(state.user ? '/dashboard' : '/login');
}

async function logoutAll() {
  menuOpen = false;
  for (const a of accounts()) {
    try { await fetch('/api/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${a.token}` } }); } catch { /* ignore */ }
  }
  clearAllAccounts();
  startNotifications();
  navigate('/login');
}

// ---------------------------------------------------------------- routing (sign-in first)
const modules = {};
let routeToken = 0;
export const pageCleanup = { fn: null };

export async function route() {
  const my = ++routeToken;
  if (pageCleanup.fn) { try { pageCleanup.fn(); } catch { /* */ } pageCleanup.fn = null; }
  let path = location.pathname.replace(/\/+$/, '') || '/';
  const app = document.getElementById('app');
  document.getElementById('nav').classList.remove('open');
  if (path === '/') {
    path = state.user ? '/dashboard' : '/login';
    history.replaceState({}, '', path);
  }
  highlightNav();
  let mod;
  if (PUBLIC[path]) {
    mod = PUBLIC[path];
    if (path === '/login' && state.user && new URLSearchParams(location.search).get('add') !== '1') {
      history.replaceState({}, '', '/dashboard'); return route();
    }
  } else {
    const def = ROUTES[path] || (path.startsWith('/citizen/tickets/') ? ['tickets', ['citizen']] : null);
    if (!state.user) {
      history.replaceState({}, '', `/login?next=${encodeURIComponent(location.pathname + location.search)}`);
      highlightNav();
      mod = 'login';
    } else if (!def) {
      mount(app, h('div', { class: 'card', style: { marginTop: '20px' } }, h('h1', {}, t('common.not_found')),
        h('a', { class: 'btn primary', href: '/dashboard', 'data-link': true }, t('nav.dashboard'))));
      return;
    } else {
      const [m, roles] = def;
      if (roles && !roles.includes(state.user.role)) {
        mount(app, h('div', { class: 'card', style: { marginTop: '20px' } }, h('h1', {}, t('common.restricted')),
          h('p', {}, t('common.no_access', { role: state.user.role_name })),
          h('div', { class: 'row' }, h('a', { class: 'btn primary', href: '/dashboard', 'data-link': true }, t('nav.dashboard')),
            h('a', { class: 'btn', href: `/login?add=1&next=${encodeURIComponent(path)}`, 'data-link': true }, t('shell.add_account')))));
        return;
      }
      mod = m;
    }
  }
  try {
    modules[mod] = modules[mod] || await import(`./pages/${mod}.js`);
    if (my !== routeToken) return;
    await modules[mod].render(app, { path: location.pathname.replace(/\/+$/, '') || '/' });
    const brand = currentTenant().branding?.title || 'JanSetu';
    document.title = `${document.querySelector('#app h1')?.textContent || brand} | ${brand}`;
  } catch (e) {
    console.warn(e);
    mount(app, h('div', { class: 'notice bad', style: { marginTop: '20px' } }, t('common.page_error'), ' ', String(e.message || e)));
  }
}

function highlightNav() {
  document.querySelectorAll('#nav a').forEach(a => {
    const on = isActive(a.getAttribute('href'));
    a.classList.toggle('active', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
}

export async function afterLogin(res) {
  setSession(res.token, res.user);
  state.tenant = res.user.tenant.code;
  store.setL('jansetu.tenant', state.tenant);
  const lang = store.getL('jansetu.lang') || 'en';
  const next = new URLSearchParams(location.search).get('next');
  const nextPath = next && next.startsWith('/') && !next.startsWith('/login') ? next : '';
  const def = nextPath ? (ROUTES[nextPath.split('?')[0]] || (nextPath.startsWith('/citizen/tickets/') ? ['tickets', ['citizen']] : null)) : null;
  const allowed = def && (!def[1] || def[1].includes(res.user.role));
  history.pushState({}, '', allowed ? nextPath : '/dashboard');
  toast(t('shell.welcome', { name: res.user.full_name }));
  startNotifications();
  await setLanguage(lang, false);
}

function showBootError(message) {
  mount(document.getElementById('app'), h('div', { class: 'card', style: { marginTop: '24px' } },
    h('h1', {}, t('boot.title')), h('p', {}, t('boot.text')), h('pre', { class: 'small mono transcript' }, message),
    h('ol', {}, h('li', {}, t('boot.step1')), h('li', {}, t('boot.step2')), h('li', {}, t('boot.step3'))),
    h('button', { class: 'primary', onclick: () => location.reload() }, t('common.retry'))));
}

// Drop saved accounts whose token no longer works (expired, server key changed, account disabled) - silently.
async function pruneAccounts() {
  for (const a of accounts()) {
    try {
      const r = await fetch('/api/me', { headers: { Authorization: `Bearer ${a.token}` } });
      if (r.status === 401) forgetAccount(a.user.id);
      else if (r.ok) { const u = await r.json(); if (a.user.id === state.user?.id) updateActiveUser(u); }
    } catch { /* offline: keep */ }
  }
  const active = store.getL('jansetu.active');
  const list = accounts();
  const acc = list.find(a => a.user.id === active) || list[0] || null;
  state.token = acc?.token || null; state.user = acc?.user || null;
  store.setL('jansetu.active', acc ? acc.user.id : '');
}

async function boot() {
  applyTheme(themePref());
  setFont(document.documentElement.dataset.font || 'md');
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', () => applyTheme(themePref()));
  document.getElementById('theme-toggle').addEventListener('click', () => {
    const next = THEMES[(THEMES.indexOf(themePref()) + 1) % THEMES.length];
    applyTheme(next);
    document.dispatchEvent(new CustomEvent('themechange'));
  });
  ['sm', 'md', 'lg'].forEach(s => document.getElementById(`font-${s}`).addEventListener('click', () => setFont(s)));
  restoreSession();
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[data-link]');
    if (a && !e.ctrlKey && !e.metaKey && a.origin === location.origin) { e.preventDefault(); navigate(a.pathname + a.search); }
    if ((menuOpen || notifOpen) && !e.target.closest('.user-box')) { menuOpen = false; notifOpen = false; renderAccountBox(); renderNotifBox(); }
  });
  window.addEventListener('popstate', () => { renderShell(); route(); });
  document.addEventListener('session', () => { menuOpen = false; renderShell(); });
  document.addEventListener('signedout', () => { startNotifications(); renderShell(); route(); });
  document.getElementById('nav-toggle').addEventListener('click', (e) => {
    const target = document.getElementById('nav');
    target.classList.toggle('open');
    e.currentTarget.setAttribute('aria-expanded', String(target.classList.contains('open')));
  });
  try {
    state.fallback = await (await fetch('/static/i18n/en.json')).json();
    [state.tenants, { languages: languageRegistry }] = await Promise.all([api('/api/public/tenants', { query: { tenant: '' } }),
      api('/api/public/languages')]);
  } catch (e) {
    showBootError(String(e.message || e));
    return;
  }
  if (!state.tenants.length) { showBootError('No tenants configured in the database.'); return; }
  await pruneAccounts();
  state.tenant = state.user?.tenant.code || store.getL('jansetu.tenant') || state.tenants[0]?.code;
  if (!state.tenants.some(x => x.code === state.tenant)) state.tenant = state.tenants[0]?.code;
  document.getElementById('lang-select').addEventListener('change', (e) => setLanguage(e.target.value));
  const lang = store.getL('jansetu.lang') || 'en';
  startNotifications();
  await setLanguage(lang, false);
}

export async function selectTenant(code) {
  state.tenant = code; store.setL('jansetu.tenant', code); state.config = null;
  await setLanguage(store.getL('jansetu.lang') || 'en', false);
}

export async function tenantConfig() {
  if (!state.config || state.config.tenant.code !== state.tenant) state.config = await api('/api/public/config');
  return state.config;
}

export function nameOf(names) { return (names && (names[state.lang] || names.en)) || ''; }
export { toast };

boot();
