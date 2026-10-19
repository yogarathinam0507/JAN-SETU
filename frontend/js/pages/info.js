// Static information pages: accessibility statement, terms of use, help / FAQ.
import { h, mount, state, t } from '../core.js';

const PAGES = {
  '/accessibility': ['info.acc_h', ['info.acc1', 'info.acc2', 'info.acc3', 'info.acc4', 'info.acc5']],
  '/terms': ['info.terms_h', ['info.terms1', 'info.terms2', 'info.terms3', 'info.terms4']],
  '/help': ['info.help_h', ['info.help1', 'info.help2', 'info.help3', 'info.help4', 'info.help5', 'info.help6']],
};

export async function render(app, { path }) {
  const [title, items] = PAGES[path] || PAGES['/help'];
  const brand = state.tenants.find(x => x.code === state.tenant)?.branding || {};
  mount(app, h('div', { class: 'breadcrumb' }, h('a', { href: '/', 'data-link': true }, t('nav.home')), ' / ', t(title)),
    h('div', { class: 'page-title' }, h('h1', {}, t(title))),
    h('div', { class: 'card' }, items.map(k => h('p', {}, t(k, { helpline: brand.helpline || '-' })))));
}
