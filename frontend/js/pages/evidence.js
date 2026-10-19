import { api, errorBox, h, loading, mount, select, t, table } from '../core.js';

const CLS = { Working: 'chip ok', 'Demo/Simulated': 'chip sim', 'Planned/Requires External Credentials': 'chip' };
let filter = '';

export async function render(app) {
  mount(app, h('h1', {}, t('ev.title')), loading());
  let r;
  try { r = await api('/api/public/evidence'); } catch (e) { mount(app, h('h1', {}, t('ev.title')), errorBox(e)); return; }
  const counts = r.features.reduce((acc, f) => { acc[f.status] = (acc[f.status] || 0) + 1; return acc; }, {});
  const sel = select([{ value: '', label: t('ev.all') }, ...Object.keys(CLS).map(k => ({ value: k, label: `${k} (${counts[k] || 0})` }))], filter);
  sel.addEventListener('change', () => { filter = sel.value; render(app); });
  const rows = r.features.filter(f => !filter || f.status === filter);
  mount(app, h('h1', {}, t('ev.title')), h('p', { class: 'muted' }, r.description),
    h('div', { class: 'row' }, Object.entries(counts).map(([k, v]) => h('span', { class: CLS[k] }, `${k}: ${v}`)), sel),
    h('p', { class: 'small muted' }, `${t('ev.updated')}: ${r.updated} · ${t('ev.tests')}: ${r.test_summary}`),
    table([{ label: 'PS', key: 'ps' }, { label: t('ev.feature'), key: 'feature' }, { label: t('ev.status'), render: f => h('span', { class: CLS[f.status] }, f.status) },
      { label: t('ev.evidence'), key: 'evidence' }, { label: t('ev.where'), render: f => h('span', { class: 'mono small' }, f.where) }], rows));
}
