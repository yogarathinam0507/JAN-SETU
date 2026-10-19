import { api, download, errorBox, h, loading, mount, state, t, toast } from '../core.js';

export async function render(app) {
  mount(app, h('h1', {}, t('privacy.title')), loading());
  let p;
  try { p = await api('/api/public/privacy'); } catch (e) { mount(app, h('h1', {}, t('privacy.title')), errorBox(e)); return; }
  const list = (items) => h('ul', {}, items.map(x => h('li', {}, x)));
  mount(app, h('h1', {}, t('privacy.title')), h('div', { class: 'notice warn' }, p.status),
    h('div', { class: 'card stack' },
      h('p', {}, h('strong', {}, t('privacy.controller') + ': '), p.controller),
      h('h2', {}, t('privacy.collect')), list(p.what_we_collect), h('h2', {}, t('privacy.why')), list(p.why),
      h('h2', {}, t('privacy.ai')), h('p', {}, p.ai_processing), h('h2', {}, t('privacy.voice')), h('p', {}, p.voice),
      h('h2', {}, t('privacy.sharing')), h('p', {}, p.sharing),
      h('h2', {}, t('privacy.retention')), h('p', {}, `${t('privacy.transcripts')}: ${p.retention.transcripts_days} ${t('privacy.days')}. ${p.retention.grievances}`),
      h('h2', {}, t('privacy.rights')), list(p.your_rights), h('p', { class: 'small muted' }, p.training)),
    state.user?.role === 'citizen' ? h('div', { class: 'card', style: { marginTop: '12px' } }, h('h2', {}, t('privacy.my_data')),
      h('div', { class: 'row' }, h('button', { onclick: async () => {
        try { const d = await api('/api/me/export'); download('my-jansetu-data.json', JSON.stringify(d, null, 2)); } catch (e) { toast(e.message, true); }
      } }, t('privacy.export')), h('button', { class: 'danger', onclick: async () => {
        const reason = prompt(t('privacy.delete_reason')); if (reason === null) return;
        try { const r = await api('/api/me/deletion-request', { method: 'POST', body: { reason } }); toast(r.message); } catch (e) { toast(e.message, true); }
      } }, t('privacy.delete')))) : null);
}
