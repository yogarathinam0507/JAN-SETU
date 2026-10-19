import { api, empty, errorBox, fmtDate, h, kv, loading, mount, select, t, toast } from '../core.js';

export async function render(app) {
  mount(app, h('h1', {}, t('vendor.title')), loading());
  let wos, sc;
  try { [wos, sc] = await Promise.all([api('/api/vendor/work-orders'), api('/api/vendor/scorecard')]); }
  catch (e) { mount(app, h('h1', {}, t('vendor.title')), errorBox(e, () => render(app))); return; }
  mount(app, h('h1', {}, t('vendor.title')),
    h('div', { class: 'card' }, h('div', { class: 'spread' }, h('h2', {}, `${t('vendor.scorecard')}: ${sc.vendor}`), sc.label ? h('span', { class: 'chip sim' }, sc.label) : null),
      kv([[t('vendor.orders'), String(sc.work_orders)], [t('vendor.completed'), String(sc.completed)], [t('vendor.on_time'), sc.on_time_pct !== null ? `${sc.on_time_pct}%` : '-'],
        [t('vendor.rejected'), String(sc.rejected_after_verification)], [t('vendor.reopened'), String(sc.linked_tickets_reopened)]]),
      h('p', { class: 'hint' }, sc.definition)),
    h('h2', {}, t('vendor.orders_h')),
    wos.length ? wos.map(w => card(w, app)) : empty(t('vendor.none')));
}

function card(w, app) {
  const fileIn = h('input', { type: 'file', accept: 'image/jpeg,image/png' });
  const status = select([{ value: 'in_progress', label: t('status.in_progress') }, { value: 'completed', label: t('vendor.mark_completed') }], 'in_progress');
  const note = h('input', { maxlength: 1000, placeholder: t('vendor.note_ph') });
  return h('div', { class: 'card', style: { marginBottom: '10px' } },
    h('div', { class: 'spread' }, h('strong', { class: 'mono' }, w.public_id), h('span', { class: w.overdue ? 'chip bad' : 'chip' }, `${w.status}${w.overdue ? ' · ' + t('vendor.overdue') : ''}`)),
    kv([[t('vendor.task'), w.description], [t('citizen.category'), w.category], [t('citizen.location_text'), w.location], [t('officer.due'), fmtDate(w.due_at)],
      [t('vendor.boq'), w.boq.map(b => `${b.item}: ${b.qty} ${b.unit}`).join('; ') || '-'], [t('vendor.photos'), w.photos.map(p => p.filename).join(', ') || '-']]),
    ['verified', 'rejected'].includes(w.status) ? null : [
      h('form', { class: 'row', onsubmit: async (e) => {
        e.preventDefault(); if (!fileIn.files[0]) return;
        const form = new FormData(); form.append('file', fileIn.files[0]);
        try { await api(`/api/vendor/work-orders/${w.id}/photo`, { method: 'POST', form }); toast(t('tickets.uploaded')); render(app); } catch (err) { toast(err.message, true); }
      } }, h('label', {}, t('vendor.photo')), fileIn, h('button', { type: 'submit' }, t('tickets.upload'))),
      h('form', { class: 'row', onsubmit: async (e) => {
        e.preventDefault();
        try { await api(`/api/vendor/work-orders/${w.id}/progress`, { method: 'POST', body: { status: status.value, note: note.value } }); toast(t('tickets.updated')); render(app); } catch (err) { toast(err.message, true); }
      } }, status, note, h('button', { class: 'primary', type: 'submit' }, t('common.save')))]);
}
