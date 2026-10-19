import { api, errorBox, fmtDate, h, loading, mount, select, statusChip, t, table, tabs } from '../core.js';

let tab = 'log';
const f = { action: '', entity_type: '', actor_role: '', page: 1 };

export async function render(app) {
  const body = h('div');
  mount(app, h('h1', {}, t('audit.title')), h('p', { class: 'muted' }, t('audit.subtitle')),
    tabs([['log', t('audit.log')], ['chain', t('audit.chain')], ['sample', t('audit.sample')]], tab, (x) => { tab = x; render(app); }), body);
  if (tab === 'log') drawLog(body);
  else if (tab === 'chain') drawChain(body);
  else drawSample(body);
}

async function drawLog(box) {
  const action = select([{ value: '', label: t('audit.all_actions') }, ...['grievance', 'pii', 'auth', 'config', 'draft', 'efile', 'kb', 'interaction', 'incident', 'duplicate', 'workorder', 'privacy', 'user', 'scheme', 'integration', 'monitoring']
    .map(a => ({ value: a, label: a }))], f.action);
  const role = select([{ value: '', label: t('audit.all_roles') }, ...['system', 'citizen', 'agent', 'officer', 'nodal', 'hod', 'vendor', 'auditor', 'content', 'admin'].map(r => ({ value: r, label: r }))], f.actor_role);
  const out = h('div');
  const load = async () => {
    f.action = action.value; f.actor_role = role.value;
    mount(out, loading());
    try {
      const r = await api('/api/audit/logs', { query: { action: f.action, actor_role: f.actor_role, page: f.page, page_size: 50 } });
      mount(out, h('p', { class: 'small muted' }, t('audit.total', { n: r.total, p: r.page })),
        table([{ label: '#', key: 'id' }, { label: t('audit.at'), render: x => fmtDate(x.at) }, { label: t('audit.role'), key: 'actor_role' }, { label: t('audit.action'), key: 'action' },
          { label: t('audit.entity'), render: x => `${x.entity_type}:${x.entity_id}` }, { label: t('audit.change'), render: x => h('details', {}, h('summary', { class: 'small' }, t('audit.view')),
            h('pre', { class: 'small mono' }, JSON.stringify({ before: x.before, after: x.after }, null, 1))) },
          { label: t('audit.reason'), key: 'reason' }, { label: 'hash', render: x => h('span', { class: 'mono small' }, x.hash) }], r.items),
        h('div', { class: 'row' }, h('button', { disabled: f.page <= 1, onclick: () => { f.page--; load(); } }, t('common.prev')), h('span', {}, String(f.page)),
          h('button', { disabled: f.page * 50 >= r.total, onclick: () => { f.page++; load(); } }, t('common.next'))));
    } catch (e) { mount(out, errorBox(e, load)); }
  };
  [action, role].forEach(s => s.addEventListener('change', () => { f.page = 1; load(); }));
  mount(box, h('div', { class: 'card row' }, action, role, h('button', { onclick: load }, t('common.refresh'))), out);
  load();
}

async function drawChain(box) {
  mount(box, loading());
  try {
    const r = await api('/api/audit/verify-chain');
    mount(box, h('div', { class: `notice ${r.valid ? 'ok' : 'bad'}` }, h('strong', {}, r.valid ? t('audit.chain_ok') : t('audit.chain_bad', { id: r.broken_at_id })),
      h('p', {}, t('audit.checked', { n: r.checked })), h('p', { class: 'small' }, r.note)));
  } catch (e) { mount(box, errorBox(e)); }
}

async function drawSample(box) {
  mount(box, loading());
  try {
    const r = await api('/api/audit/closure-sample', { query: { size: 10 } });
    mount(box, h('p', { class: 'small muted' }, `${r.method} ${t('audit.population', { n: r.population, s: r.sample_size })}`),
      table([{ label: 'ID', render: g => h('span', { class: 'mono' }, g.public_id) }, { label: t('citizen.department'), render: g => g.department?.name || '-' },
        { label: t('tickets.status'), render: g => statusChip(g.status) }, { label: t('tickets.rating'), render: g => g.citizen_rating ?? '-' },
        { label: t('audit.flags'), render: g => g.qa_flags.length ? g.qa_flags.map(x => h('span', { class: 'chip warn' }, x)) : h('span', { class: 'chip ok' }, t('audit.no_flags')) }], r.items),
      h('button', { onclick: () => drawSample(box) }, t('audit.resample')));
  } catch (e) { mount(box, errorBox(e)); }
}
