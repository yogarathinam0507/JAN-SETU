// Tenant administration (no access to citizen grievance content).
import { api, errorBox, field, fmtDate, h, loading, mount, select, t, table, tabs, toast } from '../core.js';

let tab = 'departments';

export async function render(app) {
  mount(app, h('h1', {}, t('admin.title')), loading());
  let d;
  try { d = await api('/api/admin/overview'); } catch (e) { mount(app, h('h1', {}, t('admin.title')), errorBox(e, () => render(app))); return; }
  const body = h('div');
  mount(app, h('h1', {}, t('admin.title')), h('p', { class: 'muted' }, `${d.tenant.name} · ${d.tenant.code} · ${t('admin.default_lang')}: ${d.tenant.default_language}`),
    h('p', { class: 'notice small' }, t('admin.no_content')),
    tabs([['departments', t('admin.departments')], ['categories', t('admin.categories')], ['sla', t('admin.sla')], ['users', t('admin.users')],
      ['jurisdictions', t('admin.jurisdictions')], ['privacy', t('admin.data_requests')]], tab, (x) => { tab = x; render(app); }), body);
  const deptName = Object.fromEntries(d.departments.map(x => [x.id, x.names.en]));
  if (tab === 'departments') {
    mount(body, table([{ label: 'Code', key: 'code' }, { label: 'English', render: x => x.names.en }, { label: t('admin.local'), render: x => Object.entries(x.names).filter(([k]) => k !== 'en').map(([k, v]) => `${k}: ${v}`).join(' | ') },
      { label: t('admin.verified'), render: x => x.name_verified ? h('span', { class: 'chip ok' }, t('common.yes')) : h('span', { class: 'chip warn' }, t('admin.needs_verification')) },
      { label: t('admin.contact'), render: x => Object.values(x.contact).join(', ') || '-' }], d.departments));
  } else if (tab === 'categories') {
    mount(body, table([{ label: 'Code', key: 'code' }, { label: 'Name', render: x => x.names.en },
      { label: t('citizen.department'), render: x => {
        const s = select(d.departments.map(dd => ({ value: dd.id, label: dd.names.en })), x.department_id);
        s.addEventListener('change', () => patch(x.id, { department_id: s.value }));
        return s;
      } },
      { label: t('admin.default_priority'), render: x => {
        const s = select(['Emergency', 'High', 'Medium', 'Low'].map(p => ({ value: p, label: p })), x.default_priority);
        s.addEventListener('change', () => patch(x.id, { default_priority: s.value }));
        return s;
      } },
      { label: t('admin.photo_required'), render: x => {
        const c = h('input', { type: 'checkbox', checked: x.requires_photo_verification, 'aria-label': t('admin.photo_required') });
        c.addEventListener('change', () => patch(x.id, { requires_photo_verification: c.checked }));
        return c;
      } },
      { label: t('admin.active'), render: x => {
        const c = h('input', { type: 'checkbox', checked: x.active, 'aria-label': t('admin.active') });
        c.addEventListener('change', () => patch(x.id, { active: c.checked }));
        return c;
      } }], d.categories));
  } else if (tab === 'sla') {
    mount(body, h('h2', {}, t('admin.sla')), table([{ label: t('citizen.priority'), key: 'priority' },
      { label: t('admin.first_response_h'), render: x => numInput(x.first_response_hours, v => saveSla(x, { first_response_hours: v, resolve_hours: x.resolve_hours })) },
      { label: t('admin.resolve_h'), render: x => numInput(x.resolve_hours, v => saveSla(x, { first_response_hours: x.first_response_hours, resolve_hours: v })) }], d.sla_policies),
    h('p', { class: 'hint' }, t('admin.sla_note')),
    h('h2', {}, t('admin.escalation')), table([{ label: t('admin.level'), key: 'level' },
      { label: t('admin.role'), render: x => { const s = select([{ value: 'nodal', label: 'nodal' }, { value: 'hod', label: 'hod' }], x.role); s.addEventListener('change', () => saveEsc(x, { role: s.value, sla_fraction: x.sla_fraction })); return s; } },
      { label: t('admin.fraction'), render: x => numInput(x.sla_fraction, v => saveEsc(x, { role: x.role, sla_fraction: v }), 0.1) },
      { label: '', key: 'description' }], d.escalation_rules));
  } else if (tab === 'users') {
    const uname = h('input', { pattern: '[a-z0-9._-]{3,60}' });
    const fname = h('input');
    const role = select(d.roles.filter(r => r.code !== 'citizen').map(r => ({ value: r.code, label: r.name })), 'officer');
    const dept = select([{ value: '', label: '-' }, ...d.departments.map(x => ({ value: x.id, label: x.names.en }))], '');
    const pw = h('input', { type: 'password', minlength: 10, autocomplete: 'new-password' });
    mount(body, h('p', { class: 'small muted' }, t('admin.citizens', { n: d.citizen_accounts })),
      table([{ label: 'Username', render: u => h('span', { class: 'mono' }, u.username) }, { label: 'Name', key: 'full_name' }, { label: t('admin.role'), key: 'role' },
        { label: t('citizen.department'), render: u => deptName[u.department_id] || '-' }, { label: t('admin.last_login'), render: u => fmtDate(u.last_login_at) },
        { label: t('admin.active'), render: u => {
          const c = h('input', { type: 'checkbox', checked: u.active, 'aria-label': t('admin.active') });
          c.addEventListener('change', async () => { try { await api(`/api/admin/users/${u.id}`, { method: 'PATCH', body: { active: c.checked, reason: 'Changed from admin console' } }); toast(t('common.saved')); } catch (e) { toast(e.message, true); c.checked = !c.checked; } });
          return c;
        } }], d.users),
      h('form', { class: 'card', style: { marginTop: '12px' }, onsubmit: async (e) => {
        e.preventDefault();
        try { await api('/api/admin/users', { method: 'POST', body: { username: uname.value, full_name: fname.value, role: role.value, password: pw.value, department_id: dept.value || null } }); toast(t('common.saved')); render(document.getElementById('app')); }
        catch (err) { toast(err.message, true); }
      } }, h('h2', {}, t('admin.add_user')), h('div', { class: 'grid g2' }, field('Username', uname), field('Full name', fname), field(t('admin.role'), role), field(t('citizen.department'), dept), field(t('login.password'), pw, t('admin.pw_hint'))),
      h('button', { class: 'primary', type: 'submit' }, t('admin.create'))));
  } else if (tab === 'jurisdictions') {
    mount(body, h('p', { class: 'notice warn small' }, t('admin.boundaries_note')), table([{ label: 'Code', key: 'code' }, { label: 'Name', key: 'name' }, { label: t('admin.kind'), key: 'kind' },
      { label: t('admin.boundary'), render: j => j.demo_boundary ? h('span', { class: 'chip sim' }, t('admin.demo_boundary')) : t('admin.official') }], d.jurisdictions));
  } else {
    mount(body, table([{ label: 'ID', render: r => h('span', { class: 'mono' }, r.id.slice(0, 8)) }, { label: t('admin.kind'), key: 'kind' }, { label: t('tickets.status'), key: 'status' },
      { label: t('citizen.created'), render: r => fmtDate(r.created_at) }], d.data_requests, { empty: t('admin.no_requests') }));
  }
}

function numInput(value, onSave, step = 1) {
  const i = h('input', { type: 'number', value, step, min: step, style: { width: '110px' } });
  i.addEventListener('change', () => onSave(Number(i.value)));
  return i;
}
async function patch(id, body) { try { await api(`/api/admin/categories/${id}`, { method: 'PATCH', body }); toast(t('common.saved')); } catch (e) { toast(e.message, true); } }
async function saveSla(x, body) { try { await api(`/api/admin/sla/${x.id}`, { method: 'PUT', body }); Object.assign(x, body); toast(t('common.saved')); } catch (e) { toast(e.message, true); } }
async function saveEsc(x, body) { try { await api(`/api/admin/escalation/${x.id}`, { method: 'PUT', body }); Object.assign(x, body); toast(t('common.saved')); } catch (e) { toast(e.message, true); } }
