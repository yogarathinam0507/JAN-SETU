// Officer e-Office workspace - queue, case actions, drafts, e-files, documents, work orders.
import { api, empty, errorBox, field, fmtDate, h, hasPerm, kv, loading, mount, priorityChip, select, slaChip, state, statusChip,
  t, table, tabs, toast } from '../core.js';
import { nameOf, tenantConfig } from '../app.js';
import { openAttachment } from './tickets.js';
import { createMap, priorityColor } from '../map.js';

let tab = 'queue';
const filters = { status: 'submitted,accepted,in_progress,info_requested,reopened', department_id: '', priority: '', sla: '', q: '', sort: '-created_at' };
let selected = null;

export async function render(app) {
  const qp = new URLSearchParams(location.search).get('ticket');
  if (qp) { selected = qp; tab = 'queue'; filters.status = ''; }
  const kpis = h('div', { class: 'grid g4' });
  const body = h('div');
  mount(app, h('div', { class: 'spread' }, h('h1', {}, t('officer.title')),
    h('span', { class: 'small muted' }, [state.user.department?.name, state.user.jurisdiction?.name].filter(Boolean).join(' · ') || t('officer.all_scope'))),
  kpis, tabs([['queue', t('officer.tab_queue')], ['efiles', t('officer.tab_files')], ['documents', t('officer.tab_docs')]], tab,
    (x) => { tab = x; render(app); }), body);
  loadKpis(kpis);
  if (tab === 'queue') drawQueue(body);
  else if (tab === 'efiles') drawFiles(body);
  else drawDocs(body);
}

async function loadKpis(box) {
  try {
    const s = await api('/api/officer/summary');
    const tile = (v, l, cls) => h('div', { class: `card kpi ${cls || ''}` }, h('div', { class: 'v' }, String(v)), h('div', { class: 'l' }, l));
    mount(box, tile(s.open, t('officer.kpi_open')), tile(s.overdue, t('officer.kpi_overdue')), tile(s.at_risk, t('officer.kpi_at_risk')),
      tile(s.emergency_open, t('officer.kpi_emergency')));
  } catch (e) { mount(box, errorBox(e)); }
}

// ---------------------------------------------------------------- queue
async function drawQueue(box) {
  const cfg = await tenantConfig();
  const statusSel = select([
    { value: 'submitted,accepted,in_progress,info_requested,reopened', label: t('officer.f_open') },
    { value: 'submitted,reopened', label: t('officer.f_new') }, { value: 'human_review', label: t('status.human_review') },
    { value: 'resolved', label: t('status.resolved') }, { value: 'closed', label: t('status.closed') },
    { value: 'rejected', label: t('status.rejected') }, { value: '', label: t('tickets.all') }], filters.status);
  const deptSel = select([{ value: '', label: t('officer.all_departments') }, ...cfg.departments.map(d => ({ value: d.id, label: nameOf(d.names) }))], filters.department_id);
  const priSel = select([{ value: '', label: t('officer.all_priorities') }, ...['Emergency', 'High', 'Medium', 'Low'].map(p => ({ value: p, label: t('priority.' + p) }))], filters.priority);
  const slaSel = select([{ value: '', label: t('officer.all_sla') }, { value: 'breached', label: t('sla.breached') }, { value: 'at_risk', label: t('sla.at_risk') }, { value: 'on_track', label: t('sla.on_track') }], filters.sla);
  const sortSel = select([{ value: '-created_at', label: t('officer.sort_new') }, { value: 'sla_due_at', label: t('officer.sort_due') }, { value: '-priority', label: t('officer.sort_pri') }], filters.sort);
  const q = h('input', { placeholder: t('officer.search_ph'), value: filters.q });
  const list = h('div');
  const side = h('div', { class: 'card' }, empty(t('officer.pick_ticket')));
  const load = async () => {
    Object.assign(filters, { status: statusSel.value, department_id: deptSel.value, priority: priSel.value, sla: slaSel.value, q: q.value, sort: sortSel.value });
    mount(list, loading());
    try {
      const r = await api('/api/grievances', { query: { ...filters, page_size: 200 } });
      mount(list, h('p', { class: 'small muted' }, t('officer.showing', { n: r.items.length, total: r.total })),
        table([
          { label: t('tickets.id'), render: g => h('span', { class: 'mono' }, g.public_id) },
          { label: t('citizen.category'), render: g => g.category?.name || t('status.human_review') },
          { label: t('citizen.ward'), render: g => g.jurisdiction?.name || '-' },
          { label: t('tickets.status'), render: g => statusChip(g.status) },
          { label: t('citizen.priority'), render: g => priorityChip(g.priority) },
          { label: 'SLA', render: g => slaChip(g.sla) },
          { label: t('officer.esc'), render: g => g.escalation_level ? h('span', { class: 'chip bad' }, `L${g.escalation_level}`) : '-' },
          { label: t('officer.contact'), render: g => h('span', { class: 'mono small' }, g.contact_phone || '-') },
          { label: t('citizen.created'), render: g => fmtDate(g.created_at) },
        ], r.items, { onRow: g => { selected = g.public_id; showTicket(side, load); }, rowClass: g => (g.public_id === selected ? 'selected' : ''), empty: t('officer.empty_queue') }));
    } catch (e) { mount(list, errorBox(e, load)); }
  };
  [statusSel, deptSel, priSel, slaSel, sortSel].forEach(s => s.addEventListener('change', load));
  mount(box, h('div', { class: 'card' }, h('form', { class: 'row', onsubmit: (e) => { e.preventDefault(); load(); } },
    statusSel, state.user.role === 'nodal' ? deptSel : null, priSel, slaSel, sortSel, q, h('button', { type: 'submit' }, t('common.search')),
    h('button', { type: 'button', onclick: load }, t('common.refresh')))),
  h('div', { class: 'split', style: { marginTop: '12px' } }, list, side));
  await load();
  if (selected) showTicket(side, load);
}

async function showTicket(box, reload) {
  mount(box, loading());
  let g;
  try { g = await api(`/api/grievances/${selected}`); } catch (e) { mount(box, errorBox(e)); return; }
  const cfg = await tenantConfig();
  const note = h('textarea', { maxlength: 2000, placeholder: t('officer.note_ph'), style: { minHeight: '70px' } });
  const out = h('div');
  const act = async (url, body) => {
    out.replaceChildren();
    try { await api(url, { method: 'POST', body }); toast(t('tickets.updated')); await reload(); showTicket(box, reload); }
    catch (e) { out.append(errorBox(e)); }
  };
  const tr = g.triage;
  const deptOpts = cfg.departments.filter(d => d.id !== g.department?.id).map(d => ({ value: d.id, label: nameOf(d.names) }));
  const transferSel = select(deptOpts, '');
  const colleagues = await api('/api/officer/colleagues').catch(() => []);
  const assignSel = select(colleagues.filter(c => c.role === 'officer' && c.department_id === g.department?.id).map(c => ({ value: c.id, label: c.name })), '');
  const contactOut = h('span', { class: 'mono' }, `${g.contact_name || '-'} · ${g.contact_phone || '-'}`);
  mount(box,
    h('div', { class: 'spread' }, h('h2', { class: 'mono' }, g.public_id), h('div', { class: 'row' }, statusChip(g.status), priorityChip(g.priority), slaChip(g.sla))),
    g.emergency ? h('div', { class: 'notice bad small' }, t('officer.emergency')) : null,
    h('div', { class: 'transcript' }, g.original_text || ''),
    miniMap(g),
    kv([[t('citizen.category'), g.category?.name], [t('citizen.department'), g.department?.name], [t('citizen.ward'), g.jurisdiction?.name || t('citizen.ward_unknown')],
      [t('citizen.location_text'), g.location_text || '-'], [t('officer.language'), g.language], [t('officer.channel'), g.channel],
      [t('citizen.sla_due'), fmtDate(g.sla_due_at)], [t('tickets.assigned'), g.assigned_officer ? `${g.assigned_officer}${g.assigned_officer_designation ? ', ' + g.assigned_officer_designation : ''}` : '-'],
      g.master_incident ? [t('tickets.master'), g.master_incident.public_id] : null,
      [t('officer.contact'), h('span', {}, contactOut, ' ', g.contact_masked ? h('button', { class: 'link', onclick: async () => {
        const reason = prompt(t('officer.reveal_reason'));
        if (!reason) return;
        try { const r = await api(`/api/grievances/${g.public_id}/reveal-contact`, { method: 'POST', body: { reason } }); contactOut.textContent = `${r.contact_name} · ${r.contact_phone} (${t('officer.audited')})`; }
        catch (e) { toast(e.message, true); }
      } }, t('officer.reveal')) : null)],
      [t('tickets.photo_verification'), t(`photo.${g.photo_verification}`)]]),
    tr ? h('details', {}, h('summary', {}, `${t('ts.title')}: ${Math.round(tr.confidence * 100)}%`),
      h('ul', { class: 'small' }, tr.reasoning_summary.map(x => h('li', {}, x)), tr.rules_applied.map(r => h('li', {}, `${r.rule} ${r.label} → ${r.outcome}`))),
      g.triage_override ? h('p', { class: 'small' }, t('officer.override', { by: g.triage_override.role, cat: g.triage_override.category })) : null) : null,
    h('h3', {}, t('officer.actions')), note,
    h('div', { class: 'row' }, (g.allowed_actions || []).map(a => h('button', { class: a === 'resolve' ? 'primary' : a === 'reject' ? 'danger' : '',
      onclick: () => act(`/api/grievances/${g.public_id}/actions`, { action: a, note: note.value }) }, t(`action.${a}`))),
    g.status !== 'closed' && g.status !== 'rejected' ? [
      h('button', { onclick: () => act(`/api/grievances/${g.public_id}/escalate`, { note: note.value }) }, t('officer.escalate')),
      h('button', { onclick: () => act(`/api/grievances/${g.public_id}/public-update`, { note: note.value }) }, t('officer.public_update'))] : null),
    h('div', { class: 'row' }, h('label', { class: 'sr-only' }, t('officer.assign')), assignSel,
      h('button', { disabled: !assignSel.options.length, onclick: () => act(`/api/grievances/${g.public_id}/assign`, { officer_id: assignSel.value, note: note.value }) }, t('officer.assign'))),
    h('div', { class: 'row' }, transferSel,
      h('button', { onclick: () => act(`/api/grievances/${g.public_id}/transfer`, { department_id: transferSel.value, reason: note.value }) }, t('officer.transfer')),
      h('button', { onclick: () => act(`/api/grievances/${g.public_id}/joint`, { department_id: transferSel.value, note: note.value }) }, t('officer.joint'))),
    h('p', { class: 'hint' }, t('officer.note_needed')), out,
    h('h3', {}, t('tickets.files')),
    g.attachments.length ? h('ul', { class: 'small' }, g.attachments.map(a => h('li', {}, h('button', { class: 'link', onclick: () => openAttachment(a.id, a.filename) }, a.filename), ` (${t('kind.' + a.kind)})`))) : h('p', { class: 'small muted' }, t('tickets.no_files')),
    photoUpload(g, () => showTicket(box, reload)),
    hasPerm('workorder:manage') ? workOrders(g) : null,
    draftsPanel(g),
    h('h3', {}, t('tickets.timeline')), h('ul', { class: 'timeline small' }, g.events.slice(-12).map(e => h('li', {},
      h('div', { class: 't' }, `${fmtDate(e.at)} · ${e.actor_role}${e.public ? '' : ' · ' + t('officer.internal')}`), h('div', {}, t(`event.${e.type}`), e.to ? ` → ${t('status.' + e.to)}` : ''), e.note ? h('div', {}, e.note) : null))));
}

function photoUpload(g, done) {
  const fileIn = h('input', { type: 'file', accept: 'image/jpeg,image/png' });
  const kind = select([{ value: 'after', label: t('kind.after') }, { value: 'before', label: t('kind.before') }], 'after');
  return h('form', { class: 'row', onsubmit: async (e) => {
    e.preventDefault(); if (!fileIn.files[0]) return;
    const form = new FormData(); form.append('kind', kind.value); form.append('file', fileIn.files[0]);
    try { await api(`/api/grievances/${g.public_id}/attachments`, { method: 'POST', form }); toast(t('tickets.uploaded')); done(); }
    catch (err) { toast(err.message, true); }
  } }, fileIn, kind, h('button', { type: 'submit' }, t('tickets.upload')));
}

function workOrders(g) {
  const box = h('div', {}, h('h3', {}, t('officer.work_orders')));
  (async () => {
    try {
      const [wos, vendors] = await Promise.all([api(`/api/grievances/${g.public_id}/work-orders`), api('/api/vendors')]);
      const vSel = select(vendors.map(v => ({ value: v.id, label: `${v.name} ${v.label ? '(' + v.label + ')' : ''}` })), '');
      const desc = h('input', { placeholder: t('officer.wo_desc'), maxlength: 1000 });
      box.append(wos.length ? h('ul', { class: 'small' }, wos.map(w => h('li', {}, `${w.public_id} · ${w.vendor} · ${w.status} · ${t('officer.due')} ${fmtDate(w.due_at, false)}`,
        w.status === 'completed' ? h('span', {}, ' ', h('button', { class: 'link', onclick: () => verifyWo(w, true) }, t('officer.wo_accept')), ' / ',
          h('button', { class: 'link', onclick: () => verifyWo(w, false) }, t('officer.wo_reject'))) : null))) : h('p', { class: 'small muted' }, t('officer.no_wo')),
      h('form', { class: 'row', onsubmit: async (e) => {
        e.preventDefault();
        try { await api(`/api/grievances/${g.public_id}/work-orders`, { method: 'POST', body: { vendor_id: vSel.value, description: desc.value, due_days: 3 } }); toast(t('officer.wo_issued')); }
        catch (err) { toast(err.message, true); }
      } }, vSel, desc, h('button', { type: 'submit' }, t('officer.wo_issue'))));
    } catch (e) { box.append(errorBox(e)); }
  })();
  async function verifyWo(w, accept) {
    const noteText = prompt(t('officer.wo_note'));
    if (!noteText) return;
    try { await api(`/api/work-orders/${w.id}/verify`, { method: 'POST', body: { accept, note: noteText } }); toast(t('tickets.updated')); }
    catch (e) { toast(e.message, true); }
  }
  return box;
}

function draftsPanel(g) {
  const box = h('div', {}, h('h3', {}, t('officer.drafts')), h('p', { class: 'small notice warn' }, t('officer.draft_notice')));
  (async () => {
    try {
      const [tpls, drafts] = await Promise.all([api('/api/templates'), api('/api/drafts', { query: { grievance_ref: g.public_id } })]);
      const pref = tpls.find(x => x.language === state.lang) || tpls[0];
      const tSel = select(tpls.map(x => ({ value: x.id, label: `${x.title} [${x.language}] - ${x.label}` })), pref?.id);
      const editor = h('textarea', { style: { minHeight: '220px' }, 'aria-label': t('officer.draft_editor') });
      let current = drafts[0] || null;
      if (current) editor.value = current.content;
      const meta = h('div', { class: 'small muted' }, current ? t('officer.draft_meta', { v: current.version, s: current.status, g: current.generator }) : '');
      const save = async (status) => {
        if (!current) return;
        try { current = await api(`/api/drafts/${current.id}`, { method: 'PUT', body: { content: editor.value, status } }); meta.textContent = t('officer.draft_meta', { v: current.version, s: current.status, g: current.generator }); toast(t('officer.draft_saved')); }
        catch (e) { toast(e.message, true); }
      };
      box.append(h('div', { class: 'row' }, tSel, h('button', { onclick: async () => {
        try { current = await api('/api/drafts/generate', { method: 'POST', body: { template_id: tSel.value, grievance_ref: g.public_id } }); editor.value = current.content; meta.textContent = t('officer.draft_meta', { v: current.version, s: current.status, g: current.generator }); }
        catch (e) { toast(e.message, true); }
      } }, t('officer.generate'))), editor, meta,
      h('div', { class: 'row' }, h('button', { onclick: () => save('draft') }, t('officer.save_draft')), h('button', { onclick: () => save('ready_for_manual_dispatch') }, t('officer.mark_ready'))));
    } catch (e) { box.append(errorBox(e)); }
  })();
  return box;
}

// ---------------------------------------------------------------- e-files
async function drawFiles(box) {
  mount(box, loading());
  const cfg = await tenantConfig();
  let files;
  try { files = await api('/api/efiles'); } catch (e) { mount(box, errorBox(e, () => drawFiles(box))); return; }
  const side = h('div', { class: 'card' }, empty(t('officer.pick_file')));
  const subj = h('input', { maxlength: 300, placeholder: t('officer.file_subject') });
  const link = h('input', { maxlength: 30, placeholder: 'GRV-XXXX-XXXX (optional)' });
  mount(box, h('div', { class: 'split' }, h('div', {},
    h('form', { class: 'card row', onsubmit: async (e) => {
      e.preventDefault();
      try { await api('/api/efiles', { method: 'POST', body: { subject: subj.value, grievance_ref: link.value || null } }); toast(t('officer.file_created')); drawFiles(box); }
      catch (err) { toast(err.message, true); }
    } }, subj, link, h('button', { class: 'primary', type: 'submit' }, t('officer.new_file'))),
    table([{ label: 'File', render: f => h('span', { class: 'mono' }, f.public_id) }, { label: t('officer.subject'), key: 'subject' },
      { label: t('tickets.status'), key: 'status' }, { label: t('officer.holder'), key: 'current_holder' }, { label: t('citizen.department'), key: 'department' },
      { label: t('officer.updated'), render: f => fmtDate(f.updated_at) }], files, { onRow: f => showFile(side, f.id, cfg, box), empty: t('officer.no_files') })), side));
}

async function showFile(box, id, cfg, listBox) {
  let f, colleagues;
  try { [f, colleagues] = await Promise.all([api(`/api/efiles/${id}`), api('/api/officer/colleagues')]); } catch (e) { mount(box, errorBox(e)); return; }
  const action = select([{ value: 'forward', label: t('officer.mv_forward') }, { value: 'return', label: t('officer.mv_return') },
    { value: 'send_to_department', label: t('officer.mv_dept') }, { value: 'close', label: t('officer.mv_close') }], 'forward');
  const userSel = select(colleagues.map(c => ({ value: c.id, label: c.name })), '');
  const deptSel = select(cfg.departments.map(d => ({ value: d.id, label: nameOf(d.names) })), '');
  const note = h('input', { maxlength: 1000, placeholder: t('officer.note_ph') });
  const docIn = h('input', { type: 'file', accept: 'application/pdf,text/plain,image/jpeg,image/png' });
  mount(box, h('h2', { class: 'mono' }, f.public_id), h('p', {}, f.subject),
    kv([[t('tickets.status'), f.status], [t('officer.holder'), f.current_holder], [t('citizen.department'), f.department], [t('officer.linked_ticket'), f.grievance || '-']]),
    h('h3', {}, t('officer.route_file')),
    h('form', { class: 'stack', onsubmit: async (e) => {
      e.preventDefault();
      try { await api(`/api/efiles/${f.id}/move`, { method: 'POST', body: { action: action.value, to_user_id: userSel.value, to_department_id: deptSel.value, note: note.value } }); toast(t('tickets.updated')); drawFiles(listBox); }
      catch (err) { toast(err.message, true); }
    } }, h('div', { class: 'row' }, action, userSel, deptSel), note, h('button', { type: 'submit', disabled: f.status === 'closed' }, t('officer.move'))),
    h('h3', {}, t('officer.movements')), h('ul', { class: 'timeline small' }, f.movements.map(m => h('li', {}, h('div', { class: 't' }, fmtDate(m.at)),
      `${m.action}: ${m.from || '-'} → ${m.to || m.to_department || '-'}`, m.note ? h('div', {}, m.note) : null))),
    h('h3', {}, t('officer.file_docs')), f.documents.length ? h('ul', { class: 'small' }, f.documents.map(d => h('li', {}, `${d.filename} (${d.extraction_status})`, d.summary ? h('div', { class: 'muted' }, d.summary) : null))) : h('p', { class: 'small muted' }, t('tickets.no_files')),
    h('form', { class: 'row', onsubmit: async (e) => {
      e.preventDefault(); if (!docIn.files[0]) return;
      const form = new FormData(); form.append('file', docIn.files[0]); form.append('efile_id', f.id);
      try { await api('/api/documents', { method: 'POST', form }); toast(t('tickets.uploaded')); showFile(box, id, cfg, listBox); } catch (err) { toast(err.message, true); }
    } }, docIn, h('button', { type: 'submit' }, t('tickets.upload'))));
}

// ---------------------------------------------------------------- documents
function drawDocs(box) {
  const fileIn = h('input', { type: 'file', accept: 'application/pdf,text/plain,image/jpeg,image/png' });
  const result = h('div', { 'aria-live': 'polite' });
  const q = h('input', { placeholder: t('officer.doc_search_ph') });
  const list = h('div');
  const search = async () => {
    mount(list, loading());
    try {
      const rows = await api('/api/documents', { query: { q: q.value } });
      mount(list, rows.length ? rows.map(d => h('div', { class: 'card', style: { marginBottom: '8px' } }, h('div', { class: 'spread' }, h('strong', {}, d.filename), h('span', { class: 'chip' }, d.extraction_status)),
        d.summary ? h('p', { class: 'small' }, d.summary) : null,
        h('p', { class: 'small muted' }, `${t('officer.dates')}: ${d.metadata.dates?.join(', ') || '-'} · ${t('officer.refs')}: ${d.metadata.references?.join(', ') || '-'} · ${t('officer.amounts')}: ${d.metadata.amounts?.join(', ') || '-'}`))) : empty(t('officer.no_docs')));
    } catch (e) { mount(list, errorBox(e)); }
  };
  mount(box, h('div', { class: 'grid g2' },
    h('form', { class: 'card', onsubmit: async (e) => {
      e.preventDefault(); if (!fileIn.files[0]) return;
      const form = new FormData(); form.append('file', fileIn.files[0]);
      mount(result, loading());
      try {
        const r = await api('/api/documents', { method: 'POST', form });
        mount(result, h('div', { class: 'notice' }, h('strong', {}, r.filename), ` · ${r.extraction_status}`, r.ocr_note ? h('p', {}, r.ocr_note) : null,
          r.summary ? h('p', {}, h('strong', {}, t('officer.summary') + ': '), r.summary) : null,
          h('pre', { class: 'small mono' }, JSON.stringify(r.metadata, null, 2))));
        search();
      } catch (err) { mount(result, errorBox(err)); }
    } }, h('h2', {}, t('officer.upload_doc')), h('p', { class: 'small muted' }, t('officer.upload_doc_text')), fileIn, h('button', { class: 'primary', type: 'submit' }, t('tickets.upload')), result),
    h('div', { class: 'card' }, h('h2', {}, t('officer.search_docs')), h('form', { class: 'row', onsubmit: (e) => { e.preventDefault(); search(); } }, q, h('button', { type: 'submit' }, t('common.search'))), list)));
  search();
}


function miniMap(g) {
  if (!g.has_gps) return h('p', { class: 'small muted' }, t('track.no_pin'));
  const el = h('div', { class: 'map small', style: { margin: '10px 0' } });
  api(`/api/grievances/${g.public_id}/tracking`).then(async (tr) => {
    const { L, map } = await createMap(el, { center: { lat: tr.lat, lng: tr.lng }, zoom: 16 });
    L.circleMarker([tr.lat, tr.lng], { radius: 11, color: '#fff', weight: 3, fillColor: priorityColor(g.priority), fillOpacity: 0.95 }).addTo(map);
    el.append(h('a', { class: 'btn', href: `https://www.openstreetmap.org/?mlat=${tr.lat}&mlon=${tr.lng}#map=18/${tr.lat}/${tr.lng}`,
      target: '_blank', rel: 'noopener noreferrer', style: { position: 'absolute', right: '10px', top: '10px', zIndex: '500' } }, t('track.directions')));
  }).catch(() => el.replaceChildren(h('p', { class: 'muted small' }, t('map.unavailable'))));
  el.style.position = 'relative';
  return el;
}
