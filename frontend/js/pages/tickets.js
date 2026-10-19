import { createMap, priorityColor } from '../map.js';
import { pageCleanup } from '../app.js';
import { icon } from '../icons.js';
import { readAloudButton } from '../voice.js';
import { api, empty, errorBox, field, fmtDate, h, kv, loading, mount, navigate, priorityChip, select, slaChip, state,
  statusChip, t, table, toast } from '../core.js';

export async function render(app, { path }) {
  const params = new URLSearchParams(location.search);
  const ref = path.startsWith('/citizen/tickets/') ? decodeURIComponent(path.split('/').pop()) : null;
  if (ref && state.user) return detail(app, ref);
  const trackBox = h('div', { class: 'card' });
  const listBox = h('div');
  mount(app, h('h1', {}, state.user?.role === 'citizen' ? t('tickets.title_mine') : t('tickets.title_track')),
    h('div', { class: 'split' }, h('div', {}, listBox), trackBox));
  drawTrack(trackBox, params.get('track') || ref || '');
  if (state.user?.role === 'citizen') drawList(listBox);
  else mount(listBox, h('div', { class: 'card' }, h('h2', {}, t('tickets.sign_in_h')), h('p', {}, t('tickets.sign_in_text')),
    h('a', { class: 'btn primary', href: '/login?next=/citizen/tickets', 'data-link': true }, t('shell.login'))));
}

function drawTrack(box, initial) {
  const input = h('input', { placeholder: 'GRV-XXXX-XXXX', autocomplete: 'off' });
  input.value = initial;
  const out = h('div', { 'aria-live': 'polite' });
  const go = async () => {
    if (!input.value.trim()) return;
    mount(out, loading());
    try {
      const r = await api(`/api/track/${encodeURIComponent(input.value.trim())}`, { query: state.token ? {} : { tenant: state.tenant } });
      mount(out, h('div', { class: 'stack' }, h('div', { class: 'row' }, h('strong', { class: 'mono' }, r.public_id), statusChip(r.status, r.status_label), priorityChip(r.priority), slaChip(r.sla)),
        kv([[t('citizen.department'), r.department || t('citizen.routing_human')], [t('citizen.created'), fmtDate(r.created_at)],
          [t('citizen.sla_due'), fmtDate(r.sla_due_at)], [t('tickets.escalation'), String(r.escalation_level)]]),
        h('h3', {}, t('tickets.updates')),
        h('ul', { class: 'timeline' }, r.updates.map(u => h('li', {}, h('div', { class: 't' }, fmtDate(u.at)), h('div', {}, t(`event.${u.type}`), u.to ? ` → ${t('status.' + u.to)}` : ''), u.note ? h('div', { class: 'small' }, u.note) : null))),
        h('p', { class: 'hint' }, r.note)));
    } catch (e) { mount(out, errorBox(e)); }
  };
  mount(box, h('h2', {}, t('tickets.track_h')), h('p', { class: 'small muted' }, t('tickets.track_text')),
    h('form', { class: 'row', onsubmit: (e) => { e.preventDefault(); go(); } }, input, h('button', { class: 'primary', type: 'submit' }, t('home.track_btn'))), out);
  if (initial) go();
}

async function drawList(box) {
  const statusSel = select([{ value: '', label: t('tickets.all') }, ...['submitted', 'human_review', 'accepted', 'in_progress', 'info_requested', 'resolved', 'closed', 'rejected', 'reopened']
    .map(s => ({ value: s, label: t(`status.${s}`) }))], '');
  const out = h('div');
  const load = async () => {
    mount(out, loading());
    try {
      const r = await api('/api/grievances', { query: { status: statusSel.value, page_size: 100 } });
      mount(out, h('p', { class: 'small muted' }, t('tickets.count', { n: r.total })),
        table([
          { label: t('tickets.id'), render: g => h('span', { class: 'mono' }, g.public_id) },
          { label: t('citizen.category'), render: g => g.category?.name || t('citizen.routing_human') },
          { label: t('tickets.status'), render: g => statusChip(g.status) },
          { label: t('citizen.priority'), render: g => priorityChip(g.priority) },
          { label: 'SLA', render: g => slaChip(g.sla) },
          { label: t('citizen.created'), render: g => fmtDate(g.created_at, false) },
        ], r.items, { onRow: g => navigate(`/citizen/tickets/${g.public_id}`), empty: t('tickets.none') }));
    } catch (e) { mount(out, errorBox(e, load)); }
  };
  statusSel.addEventListener('change', load);
  mount(box, h('div', { class: 'card' }, h('div', { class: 'spread' }, h('h2', {}, t('tickets.history')),
    h('div', { class: 'row' }, h('label', { class: 'sr-only', for: 'st' }, t('tickets.status')), statusSel, h('button', { onclick: load }, t('common.refresh')))), out));
  statusSel.id = 'st';
  load();
}

export async function openAttachment(id, filename) {
  try {
    const res = await api(`/api/attachments/${id}`, { raw: true });
    const blob = await res.blob();
    const a = h('a', { href: URL.createObjectURL(blob), download: filename });
    document.body.append(a); a.click(); a.remove();
  } catch (e) { toast(e.message, true); }
}

async function detail(app, ref) {
  mount(app, loading());
  let g;
  try { g = await api(`/api/grievances/${encodeURIComponent(ref)}`); } catch (e) { mount(app, h('h1', {}, ref), errorBox(e)); return; }
  const actions = h('div', { class: 'card' });
  const trackCard = trackingCard(g);
  mount(app, h('div', { class: 'breadcrumb' }, h('a', { href: '/dashboard', 'data-link': true }, t('nav.dashboard')), ' / ', h('a', { href: '/citizen/tickets', 'data-link': true }, t('nav.mytickets')), ' / ', g.public_id),
    h('div', { class: 'spread' }, h('h1', { class: 'mono' }, g.public_id), h('div', { class: 'row' }, statusChip(g.status, g.status_label), priorityChip(g.priority), slaChip(g.sla))),
    g.emergency ? h('div', { class: 'notice bad' }, t('tickets.emergency_note')) : null,
    g.assignment_notice ? h('div', { class: 'assign-notice', role: 'status' }, icon('user'),
      h('div', {}, h('strong', {}, t('citizen.assigned_h')), h('p', { style: { margin: '2px 0 6px' } }, g.assignment_notice),
        readAloudButton(() => `${t('tickets.status')}: ${g.status_label}. ${g.assignment_notice}`))) : null,
    h('div', { class: 'split' },
      h('div', { class: 'stack' },
        h('div', { class: 'card' }, h('h2', {}, t('tickets.details')), h('div', { class: 'transcript' }, g.original_text),
          kv([[t('citizen.category'), g.category?.name || t('citizen.routing_human')], [t('citizen.department'), g.department?.name || '-'],
            [t('citizen.ward'), g.jurisdiction?.name || t('citizen.ward_unknown')], [t('citizen.location_text'), g.location_text || '-'],
            [t('citizen.created'), fmtDate(g.created_at)], [t('citizen.sla_due'), fmtDate(g.sla_due_at)],
            [t('tickets.first_response'), fmtDate(g.first_response_at)], [t('tickets.escalation'), String(g.escalation_level)],
            [t('tickets.assigned'), g.assigned_officer ? `${g.assigned_officer}${g.assigned_officer_designation ? ', ' + g.assigned_officer_designation : ''}` : '-'], g.master_incident ? [t('tickets.master'), g.master_incident.public_id] : null,
            g.joint_departments.length ? [t('tickets.joint'), g.joint_departments.join(', ')] : null,
            [t('tickets.photo_verification'), t(`photo.${g.photo_verification}`)], g.resolution_note ? [t('tickets.resolution'), g.resolution_note] : null])),
        h('div', { class: 'card' }, h('h2', {}, t('tickets.timeline')), h('ul', { class: 'timeline' }, g.events.map(e => h('li', {},
          h('div', { class: 't' }, `${fmtDate(e.at)} · ${t('role.' + e.actor_role)}`),
          h('div', {}, t(`event.${e.type}`), e.to ? ` → ${t('status.' + e.to)}` : ''), e.note ? h('div', { class: 'small' }, e.note) : null))))),
      h('div', { class: 'stack' }, trackCard, actions,
        h('div', { class: 'card' }, h('h2', {}, t('tickets.files')), g.attachments.length
          ? h('ul', {}, g.attachments.map(a => h('li', {}, h('button', { class: 'link', onclick: () => openAttachment(a.id, a.filename) }, a.filename), ` (${t('kind.' + a.kind)})`)))
          : empty(t('tickets.no_files')), uploader(g, app)))));
  drawActions(actions, g, app);
}

function uploader(g, app) {
  const fileIn = h('input', { type: 'file', accept: 'image/jpeg,image/png,application/pdf' });
  const kind = select([{ value: 'evidence', label: t('kind.evidence') }, { value: 'before', label: t('kind.before') }], 'evidence');
  return h('form', { class: 'stack', onsubmit: async (e) => {
    e.preventDefault();
    if (!fileIn.files[0]) return;
    const form = new FormData(); form.append('kind', kind.value); form.append('file', fileIn.files[0]);
    try { await api(`/api/grievances/${g.public_id}/attachments`, { method: 'POST', form }); toast(t('tickets.uploaded')); detail(app, g.public_id); }
    catch (err) { toast(err.message, true); }
  } }, h('hr'), field(t('tickets.add_file'), fileIn), kind, h('button', { type: 'submit' }, t('tickets.upload')));
}

function drawActions(box, g, app) {
  const acts = g.allowed_actions || [];
  const note = h('textarea', { maxlength: 2000, placeholder: t('tickets.note_ph') });
  const rating = select([5, 4, 3, 2, 1].map(n => ({ value: n, label: t(`rating.${n}`) })), 5);
  const err = h('div');
  const run = async (action) => {
    err.replaceChildren();
    try {
      await api(`/api/grievances/${g.public_id}/actions`, { method: 'POST', body: { action, note: note.value, rating: Number(rating.value) } });
      toast(t('tickets.updated')); detail(app, g.public_id);
    } catch (e) { err.append(errorBox(e)); }
  };
  const parts = [h('h2', {}, t('tickets.your_actions'))];
  if (!acts.length) parts.push(h('p', { class: 'muted' }, t('tickets.no_actions')));
  if (acts.includes('confirm_closure')) parts.push(h('p', {}, t('tickets.resolved_q')), field(t('tickets.rating'), rating));
  if (acts.length) parts.push(field(t('tickets.note'), note, t('tickets.note_hint')));
  parts.push(h('div', { class: 'row' }, acts.map(a => h('button', { class: a === 'confirm_closure' || a === 'provide_info' ? 'primary' : (a === 'reject_closure' ? 'danger' : ''), onclick: () => run(a) }, t(`action.${a}`)))));
  parts.push(err);
  if (['resolved', 'closed', 'rejected'].includes(g.status) && !acts.includes('confirm_closure')) {
    const fb = select([5, 4, 3, 2, 1].map(n => ({ value: n, label: t(`rating.${n}`) })), g.citizen_rating || 5);
    const fbText = h('input', { maxlength: 1000, placeholder: t('tickets.feedback_ph') });
    parts.push(h('hr'), h('h3', {}, t('tickets.feedback')), h('div', { class: 'row' }, fb, fbText,
      h('button', { onclick: async () => {
        try { await api(`/api/grievances/${g.public_id}/feedback`, { method: 'POST', body: { rating: Number(fb.value), comment: fbText.value } }); toast(t('tickets.thanks')); }
        catch (e) { toast(e.message, true); }
      } }, t('common.save'))));
  }
  mount(box, parts);
}


const STAGES = ['submitted', 'accepted', 'in_progress', 'resolved', 'closed'];

function trackingCard(g) {
  const stageIdx = Math.max(0, STAGES.indexOf(g.status === 'reopened' ? 'accepted' : g.status === 'info_requested' ? 'in_progress' : g.status));
  const live = h('div', { 'aria-live': 'polite' });
  const card = h('div', { class: 'card' }, h('h2', {}, t('track.h')),
    h('div', { class: 'progress', 'aria-label': t('track.progress') }, STAGES.map((s, i) => h('span', { class: i <= stageIdx && !['rejected', 'human_review'].includes(g.status) ? 'on' : '' }))),
    h('div', { class: 'small muted' }, STAGES.map(s => t(`status.${s}`)).join(' → ')), live);
  if (g.has_gps) {
    const mapEl = h('div', { class: 'map small', style: { marginTop: '10px' } });
    card.append(mapEl);
    api(`/api/grievances/${g.public_id}/tracking`).then(async (tr) => {
      const { L, map } = await createMap(mapEl, { center: { lat: tr.lat, lng: tr.lng }, zoom: 16 });
      L.circleMarker([tr.lat, tr.lng], { radius: 11, color: '#fff', weight: 3, fillColor: priorityColor(g.priority), fillOpacity: 0.95 })
        .addTo(map).bindTooltip(t('track.problem_here'), { permanent: false });
    }).catch(() => mapEl.replaceChildren(h('p', { class: 'muted small' }, t('map.unavailable'))));
  } else {
    card.append(h('p', { class: 'small muted' }, t('track.no_pin')));
  }
  const poll = async () => {
    try {
      const tr = await api(`/api/grievances/${g.public_id}/tracking`);
      mount(live, tr.officer_distance_km !== null
        ? h('div', { class: 'tracker', style: { marginTop: '10px' } }, h('span', { class: 'live-dot' }), t('track.officer_distance', { km: tr.officer_distance_km }))
        : h('p', { class: 'small muted', style: { marginTop: '8px' } }, ['accepted', 'in_progress'].includes(tr.status) ? t('track.officer_not_sharing') : t('track.updates_here')));
    } catch { /* ignore */ }
  };
  poll();
  const timer = setInterval(() => { if (!document.hidden) poll(); }, 15000);
  pageCleanup.fn = () => clearInterval(timer);
  return card;
}
