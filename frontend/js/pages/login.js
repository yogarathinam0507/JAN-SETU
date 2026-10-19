// Sign-in page (the portal opens here). Citizen: mobile OTP or user ID. Department staff: user ID + password.
import { accounts, api, errorBox, field, h, initials, mount, state, t, tabs } from '../core.js';
import { activate, afterLogin, selectTenant } from '../app.js';
import { icon } from '../icons.js';

let mode = 'citizen';
let citizenMode = 'otp';

const ROLE_ORDER = ['citizen', 'officer', 'nodal', 'agent', 'hod', 'vendor', 'auditor', 'content', 'admin'];

export async function render(app) {
  const adding = new URLSearchParams(location.search).get('add') === '1' && !!state.user;
  let test = null;
  try { test = await api('/api/auth/demo-accounts'); } catch { /* not available in production */ }
  const saved = accounts().filter(a => a.user.id !== state.user?.id);
  const body = h('div', { class: 'lc-body' });
  const tenantSel = h('select', { id: 'portal-select', disabled: adding ? null : null, onchange: async (e) => { await selectTenant(e.target.value); } },
    state.tenants.map(x => h('option', { value: x.code, selected: x.code === state.tenant }, x.name)));
  const card = h('section', { class: 'card login-card', 'aria-labelledby': 'login-h' },
    h('div', { class: 'lc-head' }, h('h1', { id: 'login-h' }, adding ? t('login.add_title') : t('login.title')),
      h('p', {}, adding ? t('login.add_text') : t('login.subtitle'))),
    h('div', { class: 'lc-body', style: { paddingBottom: '0' } }, field(t('login.portal'), tenantSel, t('login.portal_hint')),
      tabs([['citizen', t('login.citizen_tab')], ['staff', t('login.staff_tab')]], mode, (m) => { mode = m; render(app); })),
    body);
  mount(app,
    h('div', { class: 'login-wrap' },
      h('div', { class: 'login-info' },
        h('div', { class: 'marquee', role: 'note' }, icon('info'), ' ', t('login.notice')),
        h('h2', {}, t('login.services_h')),
        h('div', { class: 'svc' },
          svc('edit', 'login.svc1', 'login.svc1d'), svc('pin', 'login.svc2', 'login.svc2d'),
          svc('hand', 'login.svc3', 'login.svc3d'), svc('headset', 'login.svc4', 'login.svc4d'),
          svc('clipboard', 'login.svc5', 'login.svc5d'), svc('chart', 'login.svc6', 'login.svc6d')),
        saved.length ? h('div', { class: 'card', style: { marginTop: '14px' } }, h('h2', {}, t('login.saved')),
          h('div', { class: 'stack' }, saved.map((a, i) => h('button', { class: 'w100', style: { justifyContent: 'flex-start' }, onclick: () => activate(a.user.id) },
            h('span', { class: `avatar alt${i % 4}` }, initials(a.user.full_name)),
            h('span', {}, h('strong', {}, a.user.full_name), ' - ', a.user.designation || a.user.role_name))))) : null,
        test ? testAccounts(test) : null),
      card));
  if (mode === 'citizen') drawCitizen(body, app); else mount(body, passwordForm('staff'));
}

function svc(ico, title, desc) {
  return h('div', {}, icon(ico), h('div', {}, h('strong', {}, t(title)), h('span', {}, t(desc))));
}

function drawCitizen(body, app) {
  mount(body, h('div', { class: 'row', style: { marginBottom: '10px' }, role: 'radiogroup', 'aria-label': t('login.citizen_method') },
    radio('otp', t('login.with_otp'), app), radio('password', t('login.with_password'), app)),
  citizenMode === 'otp' ? otpForm() : passwordForm('citizen'));
}

function radio(value, label, app) {
  const r = h('input', { type: 'radio', name: 'cmethod', value, checked: citizenMode === value });
  r.addEventListener('change', () => { citizenMode = value; render(app); });
  return h('label', { class: 'check', style: { fontWeight: '600' } }, r, label);
}

function passwordForm(kind) {
  const u = h('input', { autocomplete: 'username', required: true, id: `${kind}-user`, placeholder: kind === 'staff' ? 'ka.officer.water' : 'ka.citizen1' });
  const p = h('input', { type: 'password', autocomplete: 'current-password', required: true, id: `${kind}-pass` });
  const show = h('button', { type: 'button', class: 'icon-btn', 'aria-label': t('login.show_password'), title: t('login.show_password'),
    onclick: () => { p.type = p.type === 'password' ? 'text' : 'password'; } }, icon('eye'));
  const out = h('div', { 'aria-live': 'polite' });
  const btn = h('button', { class: 'primary big w100', type: 'submit' }, icon('login'), t('login.signin'));
  return h('form', { id: `${kind}-form`, onsubmit: async (e) => {
    e.preventDefault(); out.replaceChildren(); btn.disabled = true;
    try { await afterLogin(await api('/api/auth/login', { method: 'POST', body: { username: u.value.trim().toLowerCase(), password: p.value } })); }
    catch (err) { out.append(errorBox(err)); btn.disabled = false; }
  } }, field(t('login.username'), u), h('div', { class: 'field' }, h('label', { for: p.id }, t('login.password')), h('div', { class: 'pw-wrap' }, p, show)),
  kind === 'staff' ? h('p', { class: 'hint' }, t('login.staff_hint')) : null, out, btn);
}

function otpForm() {
  const phone = h('input', { inputmode: 'numeric', maxlength: 10, pattern: '[6-9][0-9]{9}', placeholder: '9XXXXXXXXX', autocomplete: 'tel' });
  const name = h('input', { autocomplete: 'name' });
  const code = h('input', { inputmode: 'numeric', maxlength: 6, autocomplete: 'one-time-code' });
  const out = h('div', { 'aria-live': 'polite' });
  const step2 = h('div', { hidden: true }, field(t('login.otp'), code),
    h('button', { class: 'primary big w100', type: 'button', onclick: verify }, icon('login'), t('login.verify')));
  async function request() {
    out.replaceChildren();
    if (!/^[6-9]\d{9}$/.test(phone.value.trim())) { out.append(h('p', { class: 'err' }, t('login.mobile_invalid'))); return; }
    try {
      const r = await api('/api/auth/otp/request', { method: 'POST', body: { tenant: state.tenant, phone: phone.value.trim() } });
      step2.hidden = false;
      if (r.simulated) { out.append(h('div', { class: 'notice' }, r.message, ' ', h('strong', {}, `${t('login.otp')}: ${r.demo_otp}`))); code.value = r.demo_otp; }
      code.focus();
    } catch (err) { out.append(errorBox(err)); }
  }
  async function verify() {
    try { await afterLogin(await api('/api/auth/otp/verify', { method: 'POST', body: { tenant: state.tenant, phone: phone.value.trim(), code: code.value.trim(), full_name: name.value } })); }
    catch (err) { out.append(errorBox(err)); }
  }
  return h('div', {}, field(t('login.mobile'), phone, t('login.mobile_hint')), field(t('login.name_optional'), name),
    h('button', { type: 'button', class: 'big w100', onclick: request }, icon('phone'), t('login.send_otp')), out, step2,
    h('p', { class: 'hint' }, t('login.guest_note')));
}

function testAccounts(test) {
  const rows = test.accounts.filter(a => a.tenant === state.tenant)
    .sort((a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role) || a.username.localeCompare(b.username));
  const fill = (a) => {
    mode = a.role === 'citizen' ? 'citizen' : 'staff';
    if (a.role === 'citizen') citizenMode = 'password';
    render(document.getElementById('app')).then(() => {
      const kind = a.role === 'citizen' ? 'citizen' : 'staff';
      document.getElementById(`${kind}-user`).value = a.username;
      document.getElementById(`${kind}-pass`).value = test.password;
      document.getElementById(`${kind}-form`).requestSubmit();
    });
  };
  return h('details', { class: 'card test-accounts', style: { marginTop: '14px' } },
    h('summary', {}, t('login.test_accounts')),
    h('p', { class: 'small muted' }, t('login.test_note', { pw: test.password })),
    h('div', { class: 'table-wrap' }, h('table', {},
      h('thead', {}, h('tr', {}, h('th', {}, t('login.col_name')), h('th', {}, t('login.col_role')), h('th', {}, t('login.username')), h('th', {}, ''))),
      h('tbody', {}, rows.map(a => h('tr', { class: 'clickable', tabindex: 0, onclick: () => fill(a), onkeydown: (e) => { if (e.key === 'Enter') fill(a); } },
        h('td', {}, a.full_name, a.designation ? h('div', { class: 'small muted' }, a.designation) : null),
        h('td', {}, a.role_name, a.department ? h('div', { class: 'small muted' }, a.department) : null),
        h('td', { class: 'mono' }, a.username),
        h('td', {}, h('button', { class: 'speak-btn', tabindex: -1 }, t('login.use')))))))));
}
