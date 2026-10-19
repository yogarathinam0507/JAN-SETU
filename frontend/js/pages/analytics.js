// Executive / department analytics. Everything is computed by the API from persisted records; every block
// states its source, window and whether data is demo.
import { api, download, errorBox, fmtDate, fmtDuration, h, hasPerm, kv, loading, mount, pct, select, simChip, t, table, toast } from '../core.js';
import { nameOf, tenantConfig } from '../app.js';
import { barChart, lineChart } from '../charts.js';

const f = { period: '30d', date_from: '', date_to: '', department_id: '', category_id: '', language: '', channel: '', priority: '' };
let last = null;

export async function render(app) {
  const cfg = await tenantConfig();
  const body = h('div');
  const periodBtns = h('div', { class: 'pill-toggle', role: 'group', 'aria-label': t('an.period') }, ['7d', '30d', '90d', '365d'].map(p =>
    h('button', { 'aria-pressed': String(f.period === p && !f.date_from), onclick: () => { f.period = p; f.date_from = f.date_to = ''; render(app); } }, t(`an.p_${p}`))));
  const from = h('input', { type: 'date', value: f.date_from, 'aria-label': t('an.from') });
  const to = h('input', { type: 'date', value: f.date_to, 'aria-label': t('an.to') });
  const sel = (key, opts, all) => { const s = select([{ value: '', label: all }, ...opts], f[key], { 'aria-label': all }); s.addEventListener('change', () => { f[key] = s.value; load(body); }); return s; };
  mount(app, h('div', { class: 'spread' }, h('h1', {}, t('an.title')),
    h('div', { class: 'row' }, h('button', { onclick: () => load(body) }, t('common.refresh')),
      h('button', { onclick: exportJson }, t('an.export')), h('button', { onclick: () => { if (last) navigator.clipboard?.writeText(JSON.stringify(last, null, 2)).then(() => toast(t('an.copied')), () => toast(t('an.copy_failed'), true)); } }, t('an.copy')))),
  h('div', { class: 'card row' }, periodBtns,
    h('form', { class: 'row', onsubmit: (e) => { e.preventDefault(); f.date_from = from.value; f.date_to = to.value; load(body); } }, from, to, h('button', { type: 'submit' }, t('an.apply_range'))),
    sel('department_id', cfg.departments.map(d => ({ value: d.id, label: nameOf(d.names) })), t('officer.all_departments')),
    sel('category_id', cfg.categories.map(c => ({ value: c.id, label: nameOf(c.names) })), t('an.all_categories')),
    sel('language', cfg.tenant.languages.map(l => ({ value: l, label: l })), t('an.all_languages')),
    sel('channel', ['web', 'assistant', 'voice', 'web_chat', 'whatsapp', 'email'].map(c => ({ value: c, label: c })), t('an.all_channels')),
    sel('priority', ['Emergency', 'High', 'Medium', 'Low'].map(p => ({ value: p, label: p })), t('officer.all_priorities'))),
  body);
  load(body);
}

function query() {
  const q = { ...f };
  if (f.date_from) q.date_from = `${f.date_from}T00:00:00`; else delete q.date_from;
  if (f.date_to) q.date_to = `${f.date_to}T23:59:59`; else delete q.date_to;
  return q;
}

async function exportJson() {
  try {
    const res = await api('/api/analytics/export', { query: query(), raw: true });
    download('jansetu-analytics.json', await res.text());
  } catch (e) { toast(e.message, true); }
}

async function load(box) {
  mount(box, loading());
  let d;
  try { d = await api('/api/analytics/overview', { query: query() }); last = d; } catch (e) { mount(box, errorBox(e, () => load(box))); return; }
  const tile = (v, l, sub) => h('div', { class: 'card kpi' }, h('div', { class: 'v' }, String(v ?? '-')), h('div', { class: 'l' }, l), sub ? h('div', { class: 'small muted' }, sub) : null);
  const m = d.meta;
  const dist = (obj) => Object.entries(obj).sort((a, b) => b[1] - a[1]);
  const ai = d.ai_evaluation;
  mount(box,
    h('div', { class: `notice ${m.data_mode === 'real records' ? '' : 'sim'} small` }, `${t('an.source')}: ${m.source}. ${t('an.window')}: ${m.window}. ${t('an.scope')}: ${m.scope}. `,
      h('strong', {}, `${t('an.data')}: ${m.data_mode}`), ` (${m.demo_records} ${t('an.demo_records')}). ${t('an.generated')} ${fmtDate(m.generated_at)}.`),
    h('div', { class: 'grid g4' }, tile(d.totals.total, t('an.total')), tile(d.totals.open, t('an.open'), `${d.totals.human_review} ${t('an.in_triage')}`),
      tile(d.totals.overdue, t('an.overdue')), tile(pct(d.sla.compliance_pct), t('an.sla_compliance'), `${d.sla.resolved_within_sla}/${d.sla.resolved_with_sla}`)),
    h('div', { class: 'grid g4', style: { marginTop: '12px' } }, tile(d.timings.avg_first_response_hours !== null ? `${d.timings.avg_first_response_hours} h` : '-', t('an.first_response')),
      tile(d.timings.avg_resolution_hours !== null ? `${d.timings.avg_resolution_hours} h` : '-', t('an.resolution')),
      tile(pct(d.rates.escalation_rate_pct), t('an.escalation_rate')), tile(pct(d.rates.reopen_rate_pct), t('an.reopen_rate'))),
    h('p', { class: 'hint' }, `${d.sla.definition} ${d.timings.definition}`),
    h('div', { class: 'grid g2', style: { marginTop: '12px' } },
      h('div', { class: 'card' }, h('h2', {}, t('an.daily')), lineChart(d.daily.map(x => ({ x: x.date.slice(5), y: x.count })), { title: t('an.daily'), yLabel: t('an.complaints') })),
      h('div', { class: 'card' }, h('h2', {}, t('an.by_status')), barChart(dist(d.distribution.status).map(([k, v]) => [t('status.' + k), v]), { title: t('an.by_status') })),
      h('div', { class: 'card' }, h('h2', {}, t('an.by_department')), barChart(dist(d.distribution.department), { title: t('an.by_department') })),
      h('div', { class: 'card' }, h('h2', {}, t('an.by_category')), barChart(dist(d.distribution.category), { title: t('an.by_category'), alt: true })),
      h('div', { class: 'card' }, h('h2', {}, t('an.by_priority')), barChart(dist(d.distribution.priority), { title: t('an.by_priority') }),
        h('h3', {}, t('an.by_language')), barChart(dist(d.distribution.language), { title: t('an.by_language'), alt: true }),
        h('h3', {}, t('an.by_channel')), barChart(dist(d.distribution.channel), { title: t('an.by_channel') })),
      h('div', { class: 'card' }, h('h2', {}, t('an.duplicates')), kv([[t('nodal.masters'), String(d.duplicates.master_incidents)], [t('nodal.linked'), String(d.duplicates.linked_reports)], [t('nodal.duplicates'), String(d.duplicates.duplicates)]]),
        h('p', { class: 'hint' }, d.duplicates.definition),
        h('h2', {}, t('an.callcentre')), d.call_centre.simulated ? simChip(t('an.includes_sim', { n: d.call_centre.simulated })) : null,
        kv([[t('agent.interactions'), String(d.call_centre.interactions)], [t('agent.avg_wait'), fmtDuration(d.call_centre.avg_wait_seconds)],
          [t('agent.tickets_created'), String(d.call_centre.tickets_created)], [t('an.callbacks'), String(d.call_centre.callbacks)], [t('an.qa'), d.call_centre.qa_avg_pct !== null ? `${d.call_centre.qa_avg_pct}% (n=${d.call_centre.qa_reviewed})` : '-']]),
        h('h2', {}, t('an.benefits')), kv([[t('an.events'), String(d.benefits.events)], [t('an.assisted'), String(d.benefits.assisted_referrals)],
          [t('an.outcomes'), Object.entries(d.benefits.by_outcome).map(([k, v]) => `${k}: ${v}`).join(', ') || '-']]))),
    h('div', { class: 'card', style: { marginTop: '12px' } }, h('h2', {}, t('an.uptime')),
      table([{ label: t('mon.service'), key: 'name' }, { label: t('mon.data'), render: s => s.check_mode === 'simulated' ? simChip(s.data_label) : h('span', { class: 'chip info' }, s.data_label) },
        { label: t('mon.availability'), render: s => pct(s.availability_pct) }, { label: 'p95', render: s => s.p95_ms !== null ? `${s.p95_ms} ms` : '-' },
        { label: 'SLO', render: s => `${s.slo_target}% ${s.slo_met === null ? '' : s.slo_met ? '(met)' : '(missed)'}` }], d.uptime)),
    h('div', { class: 'card', style: { marginTop: '12px' } }, h('div', { class: 'spread' }, h('h2', {}, t('an.ai')),
      hasPerm('ai_eval:run') ? h('button', { onclick: async () => { try { await api('/api/analytics/ai-eval/run', { method: 'POST' }); load(box); } catch (e) { toast(e.message, true); } } }, t('an.run_eval')) : null),
    ai ? h('div', {}, h('p', { class: 'small' }, `${ai.dataset} · ${t('an.provider')}: ${ai.provider} · ${fmtDate(ai.run_at)}`),
      h('p', { class: 'notice warn small' }, ai.caveat),
      table([{ label: t('an.language'), key: 'lang' }, { label: 'n', key: 'n' }, { label: t('an.cat_acc'), render: r => `${r.category_correct}/${r.n} (${r.category_accuracy_pct}%)` },
        { label: t('an.pri_acc'), render: r => `${r.priority_correct}/${r.n} (${r.priority_accuracy_pct}%)` }],
      [...Object.entries(ai.by_language).map(([lang, v]) => ({ lang, ...v })), { lang: t('an.overall'), ...ai.overall }]),
      ai.errors.length ? h('details', {}, h('summary', {}, t('an.errors', { n: ai.errors.length })), h('ul', { class: 'small' }, ai.errors.map(e => h('li', {}, `[${e.language}] ${e.text} → ${e.predicted} (${t('an.expected')} ${e.expected})`)))) : null)
      : h('p', { class: 'muted' }, t('an.no_eval'))));
}
