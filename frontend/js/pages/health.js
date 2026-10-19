import { api, errorBox, h, kv, loading, mount, t } from '../core.js';

export async function render(app) {
  mount(app, h('h1', {}, t('health.title')), loading());
  try {
    const [hl, ready, diag] = await Promise.all([api('/api/health'), api('/api/health/ready'), api('/api/diagnostics')]);
    mount(app, h('h1', {}, t('health.title')),
      h('div', { class: 'grid g3' },
        h('div', { class: 'card kpi' }, h('div', { class: 'v' }, hl.status.toUpperCase()), h('div', { class: 'l' }, `API v${hl.version}`)),
        h('div', { class: 'card kpi' }, h('div', { class: 'v' }, ready.status.toUpperCase()), h('div', { class: 'l' }, `DB ${ready.db_latency_ms} ms`)),
        h('div', { class: 'card kpi' }, h('div', { class: 'v' }, `${Math.round(diag.uptime_seconds / 60)} min`), h('div', { class: 'l' }, t('health.uptime')))),
      h('div', { class: 'card', style: { marginTop: '12px' } }, h('h2', {}, t('health.diagnostics')),
        kv([[t('health.env'), diag.environment], [t('health.db'), `${diag.database.engine} (${diag.database.latency_ms} ms)`], [t('health.ai'), diag.ai_mode],
          [t('health.jobs'), diag.background_jobs_enabled ? Object.entries(diag.jobs).map(([k, v]) => `${k}: ${v.ok ? 'ok' : 'failed'} (${v.seconds_since_last_run}s ago)`).join('; ') || t('health.jobs_pending') : t('health.jobs_off')],
          ...Object.entries(diag.providers).map(([k, v]) => [k, v])])),
      h('p', { class: 'small muted' }, t('health.note')));
  } catch (e) { mount(app, h('h1', {}, t('health.title')), errorBox(e, () => render(app))); }
}
