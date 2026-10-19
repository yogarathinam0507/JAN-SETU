import { api, errorBox, fmtDate, h, loading, mount, t, table } from '../core.js';

const CLS = { connected_tested: 'chip ok', configured_unverified: 'chip info', simulated: 'chip sim', planned: 'chip' };

export async function render(app) {
  mount(app, h('h1', {}, t('int.title')), loading());
  let r;
  try { r = await api('/api/public/integrations'); } catch (e) { mount(app, h('h1', {}, t('int.title')), errorBox(e)); return; }
  mount(app, h('h1', {}, t('int.title')), h('p', { class: 'muted' }, t('int.subtitle')),
    h('div', { class: 'row' }, Object.entries(r.states).map(([k, v]) => h('span', { class: CLS[k] }, v))),
    h('div', { class: 'card', style: { marginTop: '12px' } }, h('h2', {}, t('int.api')),
      h('ul', {}, h('li', {}, h('a', { href: '/api/docs', target: '_blank', rel: 'noopener' }, 'OpenAPI / Swagger UI'), ' - /api/docs'),
        h('li', {}, h('a', { href: '/api/openapi.json', target: '_blank', rel: 'noopener' }, 'OpenAPI JSON'), ' - /api/openapi.json'),
        h('li', {}, h('a', { href: '/api/public/benchmark/dataset', target: '_blank', rel: 'noopener' }, t('int.benchmark')), ' - /api/public/benchmark/dataset'),
        h('li', {}, h('a', { href: '/metrics', target: '_blank', rel: 'noopener' }, 'Prometheus metrics'), ' - /metrics'),
        h('li', {}, h('a', { href: '/api/health', target: '_blank', rel: 'noopener' }, 'Health'), ' - /api/health, /api/health/ready, /api/diagnostics')),
      h('p', { class: 'small muted' }, t('int.links_note'))),
    h('div', { class: 'notice sim', style: { marginTop: '12px' } }, h('strong', {}, 'Telephony: '), r.telephony.message),
    h('div', { style: { marginTop: '12px' } }, table([{ label: t('int.name'), key: 'name' }, { label: t('int.kind'), key: 'kind' },
      { label: t('int.state'), render: x => h('span', { class: CLS[x.state] }, r.states[x.state]) }, { label: t('int.adapter'), render: x => h('span', { class: 'mono small' }, x.adapter || '-') },
      { label: t('int.verified'), render: x => fmtDate(x.last_verified_at, false) }, { label: t('int.notes'), key: 'notes' }], r.integrations)));
}
