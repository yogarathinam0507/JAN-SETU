import { api, empty, errorBox, field, fmtDate, h, kv, loading, mount, priorityChip, select, slaChip, statusChip, t, table, tabs, toast } from '../core.js';
import { nameOf, tenantConfig } from '../app.js';

let tab = 'triage';

export async function render(app) {
  const body = h('div');
  mount(app, h('div', { class: 'spread' }, h('h1', {}, t('nodal.title')),
    h('button', { onclick: async () => { try { const r = await api('/api/nodal/run-escalations', { method: 'POST' }); toast(t('nodal.escalated', { n: r.escalated })); render(app); } catch (e) { toast(e.message, true); } } }, t('nodal.run_escalations'))),
  tabs([['triage', t('nodal.tab_triage')], ['masters', t('nodal.tab_masters')], ['escalations', t('nodal.tab_escalations')], ['cross', t('nodal.tab_cross')]], tab, (x) => { tab = x; render(app); }), body);
  ({ triage: drawTriage, masters: drawMasters, escalations: drawEsc, cross: drawCross })[tab](body);
}

async function drawTriage(box) {
  mount(box, loading());
  const cfg = await tenantConfig();
  let rows;
  try { rows = await api('/api/nodal/triage-queue'); } catch (e) { mount(box, errorBox(e, () => drawTriage(box))); return; }
  if (!rows.length) { mount(box, empty(t('nodal.triage_empty'))); return; }
  mount(box, h('p', { class: 'muted' }, t('nodal.triage_text')), rows.map(g => {
    const catSel = select(cfg.categories.map(c => ({ value: c.id, label: `${nameOf(c.names)} (${c.default_priority})` })), '');
    const pri = select([{ value: '', label: t('nodal.default_priority') }, ...['Emergency', 'High', 'Medium', 'Low'].map(p => ({ value: p, label: p }))], '');
    const note = h('input', { maxlength: 500, placeholder: t('nodal.route_note') });
    return h('div', { class: 'card', style: { marginBottom: '10px' } },
      h('div', { class: 'spread' }, h('strong', { class: 'mono' }, g.public_id), h('div', { class: 'row' }, g.emergency ? h('span', { class: 'chip bad' }, t('priority.Emergency')) : null, statusChip(g.status), h('span', { class: 'small muted' }, fmtDate(g.created_at)))),
      h('div', { class: 'transcript' }, g.original_text),
      g.triage ? h('p', { class: 'small muted' }, `${t('nodal.why')}: ${g.triage.human_review_reason || '-'} · ${t('officer.language')}: ${g.triage.language}`) : null,
      h('form', { class: 'row', onsubmit: async (e) => {
        e.preventDefault();
        try { await api(`/api/nodal/triage-queue/${g.public_id}/route`, { method: 'POST', body: { category_id: catSel.value, priority: pri.value || null, note: note.value } }); toast(t('nodal.routed')); drawTriage(box); }
        catch (err) { toast(err.message, true); }
      } }, catSel, pri, note, h('button', { class: 'primary', type: 'submit' }, t('nodal.route'))),
      h('form', { class: 'row', onsubmit: async (e) => {
        e.preventDefault();
        const reason = prompt(t('nodal.reject_reason')); if (!reason) return;
        try { await api(`/api/grievances/${g.public_id}/actions`, { method: 'POST', body: { action: 'reject', note: reason } }); drawTriage(box); }
        catch (err) { toast(err.message, true); }
      } }, h('button', { class: 'danger', type: 'submit' }, t('nodal.reject_invalid'))));
  }));
}

async function drawMasters(box) {
  mount(box, loading());
  let r;
  try { r = await api('/api/nodal/master-incidents'); } catch (e) { mount(box, errorBox(e, () => drawMasters(box))); return; }
  const s = r.stats;
  mount(box, h('div', { class: 'grid g3' },
    h('div', { class: 'card kpi' }, h('div', { class: 'v' }, String(s.master_incidents)), h('div', { class: 'l' }, t('nodal.masters'))),
    h('div', { class: 'card kpi' }, h('div', { class: 'v' }, String(s.linked_reports)), h('div', { class: 'l' }, t('nodal.linked'))),
    h('div', { class: 'card kpi' }, h('div', { class: 'v' }, String(s.duplicates)), h('div', { class: 'l' }, t('nodal.duplicates')))),
  h('p', { class: 'small notice' }, s.definition, h('br'), s.rule),
  r.items.length ? r.items.map(m => h('div', { class: 'card', style: { marginTop: '10px' } },
    h('div', { class: 'spread' }, h('strong', {}, `${m.public_id} · ${m.title}`), h('span', { class: 'chip' }, `${m.linked_reports} ${t('nodal.reports')} · ${m.channels.join(', ')}`)),
    h('ul', {}, m.tickets.map(x => h('li', { class: 'row' }, h('span', { class: 'mono' }, x.public_id), statusChip(x.status),
      h('button', { class: 'link', onclick: async () => {
        const reason = prompt(t('nodal.unlink_reason')); if (!reason) return;
        try { await api(`/api/nodal/grievances/${x.public_id}/unlink`, { method: 'POST', body: { reason } }); toast(t('nodal.unlinked')); drawMasters(box); }
        catch (e) { toast(e.message, true); }
      } }, t('nodal.unlink'))))))) : empty(t('nodal.no_masters')));
}

async function drawEsc(box) {
  mount(box, loading());
  try {
    const rows = await api('/api/nodal/escalations');
    mount(box, table([{ label: t('tickets.id'), render: g => h('span', { class: 'mono' }, g.public_id) },
      { label: t('citizen.department'), render: g => g.department?.name || '-' }, { label: t('tickets.status'), render: g => statusChip(g.status) },
      { label: t('citizen.priority'), render: g => priorityChip(g.priority) }, { label: 'SLA', render: g => slaChip(g.sla) },
      { label: t('officer.esc'), render: g => h('span', { class: 'chip bad' }, `L${g.escalation_level}`) }], rows, { empty: t('nodal.no_escalations') }));
  } catch (e) { mount(box, errorBox(e, () => drawEsc(box))); }
}

async function drawCross(box) {
  mount(box, loading());
  try {
    const rows = await api('/api/nodal/cross-department');
    mount(box, table([{ label: t('tickets.id'), render: g => h('span', { class: 'mono' }, g.public_id) },
      { label: t('citizen.department'), render: g => g.department?.name || '-' }, { label: t('tickets.joint'), render: g => g.joint_departments.join(', ') },
      { label: t('tickets.status'), render: g => statusChip(g.status) }], rows, { empty: t('nodal.no_cross') }));
  } catch (e) { mount(box, errorBox(e, () => drawCross(box))); }
}

export { kv, field };
