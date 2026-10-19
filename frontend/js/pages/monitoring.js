// Service uptime & incidents. Real vs simulated data is labelled on every row.
import { api, empty, errorBox, field, fmtDate, h, hasPerm, kv, loading, mount, pct, select, simChip, t, table, toast } from '../core.js';
import { barChart, lineChart } from '../charts.js';

let hours = 24;
let selectedSvc = null;

export async function render(app) {
  const detail = h('div', { class: 'card' }, empty(t('mon.pick')));
  const body = h('div');
  mount(app, h('div', { class: 'spread' }, h('h1', {}, t('mon.title')),
    h('div', { class: 'row' }, h('div', { class: 'pill-toggle' }, [24, 168, 720].map(x => h('button', { 'aria-pressed': String(hours === x), onclick: () => { hours = x; render(app); } }, x === 24 ? '24 h' : x === 168 ? '7 d' : '30 d'))),
      h('button', { onclick: () => render(app) }, t('common.refresh')))), body);
  mount(body, loading());
  let svcs, incidents, alerts, traffic;
  try {
    [svcs, incidents, alerts, traffic] = await Promise.all([api('/api/monitoring/services', { query: { hours } }), api('/api/monitoring/incidents'),
      api('/api/monitoring/alerts'), api('/api/monitoring/traffic', { query: { days: 14 } })]);
  } catch (e) { mount(body, errorBox(e, () => render(app))); return; }
  const modeChip = (s) => s.check_mode === 'simulated' ? simChip(s.data_label) : s.check_mode === 'planned' ? h('span', { class: 'chip' }, s.data_label) : h('span', { class: 'chip info' }, s.data_label);
  const statusChipM = (s) => s.last_status === 'up' ? h('span', { class: 'chip ok' }, t('mon.up')) : s.last_status === 'down' ? h('span', { class: 'chip bad' }, t('mon.down')) : h('span', { class: 'chip' }, t('mon.no_data'));
  mount(body,
    h('div', { class: 'notice small' }, Object.entries(svcs.legend).map(([k, v]) => h('div', {}, h('strong', {}, `${k}: `), v))),
    h('div', { class: 'split' }, h('div', {},
      table([{ label: t('mon.service'), key: 'name' }, { label: t('mon.data'), render: modeChip }, { label: t('mon.status'), render: statusChipM },
        { label: t('mon.availability'), render: s => pct(s.availability_pct) }, { label: 'p50 / p95', render: s => s.p50_ms !== null ? `${s.p50_ms} / ${s.p95_ms} ms` : '-' },
        { label: 'SLO', render: s => s.slo_met === null ? `${s.slo_target}%` : h('span', { class: s.slo_met ? 'chip ok' : 'chip bad' }, `${s.slo_target}%`) },
        { label: t('mon.last'), render: s => fmtDate(s.last_checked_at) }], svcs.services, { onRow: s => { selectedSvc = s.id; showSvc(detail); } }),
      hasPerm('monitoring:manage') ? addForm(app) : null), detail),
    h('div', { class: 'grid g2', style: { marginTop: '12px' } },
      h('div', { class: 'card' }, h('h2', {}, t('mon.incidents')), incidents.length ? incidents.map(i => incidentCard(i, app)) : empty(t('mon.no_incidents'))),
      h('div', { class: 'card' }, h('h2', {}, t('mon.traffic')), barChart(traffic.series.map(p => [p.date.slice(5), p.events]), { title: t('mon.traffic'), max: 14 }),
        h('p', { class: traffic.capacity_risk.triggered ? 'notice bad' : 'small muted' }, `${t('mon.capacity')}: ${traffic.capacity_risk.triggered ? t('mon.triggered') : t('mon.ok')} (${traffic.capacity_risk.rule})`),
        h('p', { class: 'small muted' }, traffic.autoscaling), h('p', { class: 'small muted' }, traffic.source),
        h('h2', {}, t('mon.alerts')), alerts.length ? h('ul', { class: 'small' }, alerts.slice(0, 15).map(a => h('li', {}, `${fmtDate(a.at)} · ${a.rule} · ${a.message} `, a.simulated ? simChip() : null))) : empty(t('mon.no_alerts')))));
  if (selectedSvc) showSvc(detail);
}

function incidentCard(i, app) {
  const note = h('input', { maxlength: 1000, placeholder: t('mon.note_ph') });
  const act = async (action) => {
    try { await api(`/api/monitoring/incidents/${i.id}`, { method: 'POST', body: { action, note: note.value } }); toast(t('tickets.updated')); render(app); }
    catch (e) { toast(e.message, true); }
  };
  return h('details', { class: 'card', style: { marginBottom: '8px' } },
    h('summary', {}, `${i.public_id} · ${i.service} · ${i.status} · ${i.duration_minutes} min `, i.simulated ? simChip(i.label) : h('span', { class: 'chip info' }, i.label)),
    kv([[t('mon.opened'), fmtDate(i.opened_at)], [t('mon.resolved'), fmtDate(i.resolved_at)], [t('mon.trigger'), i.trigger], [t('mon.summary'), i.summary],
      [t('mon.root_cause'), i.confirmed_root_cause || t('mon.unconfirmed')]]),
    h('h3', {}, t('mon.hypotheses')), h('ul', { class: 'small' }, i.hypotheses.map(x => h('li', {}, `${x.hypothesis} - ${x.evidence} `, h('span', { class: 'chip warn' }, x.status)))),
    hasPerm('monitoring:manage') ? h('div', { class: 'row' }, note, h('button', { onclick: () => act('acknowledge') }, t('mon.ack')),
      h('button', { onclick: () => act('confirm_root_cause') }, t('mon.confirm_rc')), h('button', { onclick: () => act('resolve') }, t('mon.resolve'))) : null);
}

async function showSvc(box) {
  mount(box, loading());
  let d;
  try { d = await api(`/api/monitoring/services/${selectedSvc}`, { query: { hours } }); } catch (e) { mount(box, errorBox(e)); return; }
  const s = d.summary;
  mount(box, h('div', { class: 'spread' }, h('h2', {}, s.name), s.check_mode === 'simulated' ? simChip(s.data_label) : h('span', { class: 'chip info' }, s.data_label)),
    kv([[t('mon.owner'), s.owner_team], [t('mon.env'), s.environment], [t('mon.criticality'), s.criticality], [t('mon.endpoint'), s.endpoint || '-'],
      [t('mon.checks'), String(s.checks)], [t('mon.availability'), pct(s.availability_pct)]]),
    s.notes ? h('p', { class: 'notice' }, s.notes) : null,
    d.series.length ? lineChart(d.series.map(p => ({ x: p.at.slice(11, 16), y: p.latency_ms, bad: !p.ok })), { title: t('mon.latency'), yLabel: 'ms', badKey: true }) : empty(t('mon.no_data')),
    h('h3', {}, t('mon.anomaly')), h('p', { class: d.anomaly.status === 'anomalous' ? 'notice bad' : 'small' }, d.anomaly.status === 'insufficient_data' ? d.anomaly.message : `${d.anomaly.status} · z=${d.anomaly.z_score} · ${d.anomaly.method}`),
    h('h3', {}, t('mon.risk')), h('p', { class: 'small' }, d.risk.status === 'insufficient_data' ? d.risk.message : `${d.risk.level} (${d.risk.score}/100) · ${d.risk.method}`),
    hasPerm('monitoring:manage') ? h('div', { class: 'row' },
      s.check_mode !== 'planned' ? h('button', { onclick: async () => { try { const r = await api(`/api/monitoring/services/${s.id}/check-now`, { method: 'POST' }); toast(`${r.ok ? 'OK' : 'FAIL'} ${r.latency_ms ?? ''} ms ${r.simulated ? '(synthetic probe)' : ''}`); showSvc(box); } catch (e) { toast(e.message, true); } } }, t('mon.check_now')) : null,
      s.check_mode !== 'planned' ? h('button', { onclick: async () => { try { await api(`/api/monitoring/services/${s.id}`, { method: 'PATCH', body: { enabled: !s.enabled } }); showSvc(box); } catch (e) { toast(e.message, true); } } }, s.enabled ? t('mon.disable') : t('mon.enable')) : null) : null);
}

function addForm(app) {
  const name = h('input', { maxlength: 200 });
  const endpoint = h('input', { maxlength: 500, placeholder: 'https://...' });
  const mode = select([{ value: 'http', label: t('mon.mode_http') }, { value: 'simulated', label: t('mon.mode_sim') }, { value: 'planned', label: t('mon.mode_planned') }], 'http');
  const auth = h('input', { maxlength: 300, placeholder: t('mon.auth_ph') });
  return h('details', { class: 'card', style: { marginTop: '12px' } }, h('summary', {}, t('mon.add')),
    h('form', { onsubmit: async (e) => {
      e.preventDefault();
      try { await api('/api/monitoring/services', { method: 'POST', body: { name: name.value, endpoint: endpoint.value, check_mode: mode.value, authorization_confirmation: auth.value } }); toast(t('mon.added')); render(app); }
      catch (err) { toast(err.message, true); }
    } }, field(t('mon.service'), name), field(t('mon.endpoint'), endpoint), field(t('mon.mode'), mode), field(t('mon.authorization'), auth, t('mon.auth_hint')),
    h('button', { class: 'primary', type: 'submit' }, t('mon.add'))));
}
