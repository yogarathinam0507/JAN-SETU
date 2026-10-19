// Role dashboard: KPIs, charts and work lists from /api/dashboard (live, scoped server-side to the signed-in role).
import { api, errorBox, fmtDate, h, loading, mount, navigate, t } from '../core.js';
import { barChart, donutChart, multiLineChart } from '../charts.js';
import { pageCleanup } from '../app.js';
import { icon } from '../icons.js';

const ROLE_ICON = { citizen: 'user', officer: 'clipboard', nodal: 'route', agent: 'headset', hod: 'chart', vendor: 'tool',
  auditor: 'shield', content: 'book', admin: 'settings' };

export async function render(app) {
  mount(app, loading());
  const load = async (first) => {
    let d;
    try { d = await api('/api/dashboard'); } catch (e) { if (first) mount(app, errorBox(e, () => load(true))); return; }
    draw(app, d);
  };
  await load(true);
  const timer = setInterval(() => { if (!document.hidden && location.pathname === '/dashboard') load(false); }, 60000);
  pageCleanup.fn = () => clearInterval(timer);
}

function kpiTile(k) {
  const inner = [h('div', { class: 'l' }, k.label), h('div', { class: 'v' }, String(k.value), k.unit ? h('small', {}, k.unit) : null),
    k.hint ? h('div', { class: 'hnt' }, k.hint) : null];
  return k.link ? h('a', { class: `kpi ${k.tone || ''}`, href: k.link, 'data-link': true }, inner) : h('div', { class: `kpi ${k.tone || ''}` }, inner);
}

function chart(c) {
  let body;
  if (c.type === 'line') body = multiLineChart(c.labels, c.series, { title: c.title });
  else if (c.type === 'donut') body = donutChart(c.data.map(x => [x.label, x.value]), { title: c.title });
  else body = barChart(c.data.map(x => [x.label, x.value]), { title: c.title });
  return h('div', { class: 'card' }, h('h2', {}, c.title), body);
}

function list(l) {
  return h('div', { class: 'card', style: { marginTop: '14px' } }, h('h2', {}, l.title),
    l.rows.length ? h('div', { class: 'table-wrap' }, h('table', {},
      h('thead', {}, h('tr', {}, l.columns.map(c => h('th', { scope: 'col' }, c)))),
      h('tbody', {}, l.rows.map(r => h('tr', { class: [r.link ? 'clickable' : '', r.tone || ''].join(' ').trim() || null, tabindex: r.link ? 0 : null,
        onclick: r.link ? () => navigate(r.link) : null, onkeydown: r.link ? (e) => { if (e.key === 'Enter') navigate(r.link); } : null },
      r.cells.map((c, i) => h('td', { class: i === 0 && /^[A-Z]{2,4}-[A-Z0-9]{3,}/.test(String(c)) ? 'mono' : null }, c === null || c === undefined ? '-' : String(c))))))))
      : h('p', { class: 'muted' }, t('dash.nothing')));
}

function draw(app, d) {
  const hour = new Date().getHours();
  const greet = hour < 12 ? t('dash.morning') : hour < 17 ? t('dash.afternoon') : t('dash.evening');
  mount(app,
    h('div', { class: 'breadcrumb' }, t('nav.home'), ' / ', t('nav.dashboard')),
    h('div', { class: 'page-title' }, h('h1', {}, t('dash.title', { role: d.role_name })),
      h('span', { class: 'small muted' }, t('dash.updated', { at: fmtDate(d.generated_at) }))),
    h('div', { class: 'welcome' },
      h('div', { class: 'row' }, h('span', { class: 'avatar' }, icon(ROLE_ICON[d.role] || 'user')),
        h('div', {}, h('strong', {}, `${greet}, ${d.user}`), h('div', { class: 'small muted' }, [d.designation, d.scope].filter(Boolean).join(' - ')))),
      h('div', { class: 'row' }, (d.actions || []).map((a, i) => h('a', { class: `btn${i === 0 ? ' primary' : ''}`, href: a.link, 'data-link': true }, a.label)))),
    h('div', { class: 'kpi-grid' }, d.kpis.map(kpiTile)),
    d.charts.length ? h('div', { class: 'dash-charts' }, d.charts.map(chart)) : null,
    d.lists.map(list),
    h('p', { class: 'hint', style: { marginTop: '12px' } }, t('dash.source', { tenant: d.tenant })));
}
