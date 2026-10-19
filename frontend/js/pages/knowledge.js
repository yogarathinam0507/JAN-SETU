// Knowledge base (versioned, cited) + scheme content verification + translations. Writes need content role.
import { api, empty, errorBox, field, fmtDate, h, hasPerm, loading, mount, select, state, t, table, tabs, toast } from '../core.js';
import { tenantConfig } from '../app.js';

let tab = 'search';

export async function render(app) {
  const body = h('div');
  const items = [['search', t('kb.search')], ['docs', t('kb.documents')]];
  if (hasPerm('kb:write')) items.push(['add', t('kb.add')]);
  if (hasPerm('schemes:write')) items.push(['schemes', t('kb.schemes')]);
  if (hasPerm('translations:write')) items.push(['translations', t('kb.translations')]);
  mount(app, h('h1', {}, t('kb.title')), h('p', { class: 'muted' }, t('kb.subtitle')), tabs(items, tab, (x) => { tab = x; render(app); }), body);
  ({ search: drawSearch, docs: drawDocs, add: drawAdd, schemes: drawSchemes, translations: drawTranslations })[tab](body);
}

function drawSearch(box) {
  const q = h('input', { placeholder: t('kb.search_ph') });
  const out = h('div');
  mount(box, h('form', { class: 'card row', onsubmit: async (e) => {
    e.preventDefault(); mount(out, loading());
    try {
      const r = await api('/api/knowledge/search', { query: { q: q.value } });
      mount(out, h('p', { class: 'small muted' }, r.retrieval_mode), r.results.length ? r.results.map(x => h('div', { class: 'card', style: { marginBottom: '8px' } },
        h('div', { class: 'spread' }, h('strong', {}, `${x.title} · v${x.version}`), h('span', { class: x.verified ? 'chip ok' : 'chip warn' }, x.label)),
        h('p', { class: 'small' }, x.text), h('p', { class: 'small muted' }, `score ${x.score} · ${x.language} · ${x.published_date || '-'} · ${x.source_url || x.source_filename || 'no source URL'}`))) : empty(t('kb.no_results')));
    } catch (err) { mount(out, errorBox(err)); }
  } }, q, h('button', { class: 'primary', type: 'submit' }, t('common.search'))), out);
}

async function drawDocs(box) {
  mount(box, loading());
  let docs;
  try { docs = await api('/api/knowledge/documents', { query: { include_history: true } }); } catch (e) { mount(box, errorBox(e, () => drawDocs(box))); return; }
  mount(box, h('div', { class: 'row' }, hasPerm('kb:write') ? h('button', { onclick: async () => { try { const r = await api('/api/knowledge/reindex', { method: 'POST' }); toast(t('kb.reindexed', { d: r.documents, c: r.chunks })); } catch (e) { toast(e.message, true); } } }, t('kb.reindex')) : null),
    table([{ label: t('kb.doc_title'), key: 'title' }, { label: 'v', key: 'version' }, { label: t('tickets.status'), key: 'status' }, { label: t('officer.language'), key: 'language' },
      { label: t('kb.chunks'), key: 'chunks' }, { label: t('kb.label'), render: d => h('span', { class: d.verified ? 'chip ok' : 'chip warn' }, d.label) },
      { label: t('kb.indexed'), render: d => fmtDate(d.indexed_at) },
      { label: '', render: d => hasPerm('kb:write') && d.status !== 'superseded' ? h('button', { onclick: async () => {
        const reason = prompt(t('kb.status_reason')); if (!reason) return;
        try { await api(`/api/knowledge/documents/${d.id}/status`, { method: 'POST', body: { status: d.status === 'active' ? 'inactive' : 'active', reason } }); drawDocs(box); } catch (e) { toast(e.message, true); }
      } }, d.status === 'active' ? t('kb.deactivate') : t('kb.activate')) : '' }], docs));
}

function drawAdd(box) {
  const title = h('input', { maxlength: 300 });
  const key = h('input', { maxlength: 120, placeholder: t('kb.key_ph') });
  const lang = select(['en', 'kn', 'hi', 'ta'].map(l => ({ value: l, label: l })), state.lang);
  const dept = h('input', { maxlength: 40, placeholder: 'e.g. WATER' });
  const url = h('input', { maxlength: 500, placeholder: 'https://' });
  const date = h('input', { type: 'date' });
  const verified = h('input', { type: 'checkbox' });
  const bodyTa = h('textarea', { style: { minHeight: '180px' } });
  const file = h('input', { type: 'file', accept: 'application/pdf,text/plain' });
  mount(box, h('form', { class: 'card', onsubmit: async (e) => {
    e.preventDefault();
    try {
      let r;
      if (file.files[0]) {
        const form = new FormData();
        Object.entries({ title: title.value, doc_key: key.value, department_code: dept.value, language: lang.value, source_url: url.value, published_date: date.value, verified: verified.checked })
          .forEach(([k, v]) => form.append(k, String(v)));
        form.append('file', file.files[0]);
        r = await api('/api/knowledge/documents/upload', { method: 'POST', form });
      } else {
        r = await api('/api/knowledge/documents', { method: 'POST', body: { title: title.value, doc_key: key.value || null, department_code: dept.value, language: lang.value, source_url: url.value, published_date: date.value, verified: verified.checked, body: bodyTa.value } });
      }
      toast(t('kb.added', { v: r.version, c: r.chunks }));
    } catch (err) { toast(err.message, true); }
  } }, h('h2', {}, t('kb.add')), h('p', { class: 'small muted' }, t('kb.add_text')),
  h('div', { class: 'grid g2' }, field(t('kb.doc_title'), title), field(t('kb.key'), key, t('kb.key_hint')), field(t('officer.language'), lang), field(t('kb.dept'), dept),
    field(t('kb.source_url'), url), field(t('kb.pub_date'), date)),
  h('label', { class: 'check' }, verified, t('kb.verified_check')), field(t('kb.body'), bodyTa, t('kb.or_upload')), field(t('kb.file'), file),
  h('button', { class: 'primary', type: 'submit' }, t('common.save'))));
}

async function drawSchemes(box) {
  mount(box, loading());
  let list;
  try { list = await api('/api/benefits/schemes'); } catch (e) { mount(box, errorBox(e)); return; }
  mount(box, h('p', { class: 'notice warn small' }, t('kb.scheme_note')), list.filter(s => !s.code.startsWith('dir_')).map(s => {
    const url = h('input', { maxlength: 500, placeholder: 'https://', value: s.official_url || '' });
    const summary = h('textarea', { style: { minHeight: '60px' } }); summary.value = s.summary;
    const verified = h('input', { type: 'checkbox', checked: s.verified });
    return h('form', { class: 'card', style: { marginBottom: '10px' }, onsubmit: async (e) => {
      e.preventDefault();
      try { const r = await api(`/api/knowledge/schemes/${s.code}`, { method: 'PUT', body: { official_url: url.value, summary: summary.value, verified: verified.checked } }); toast(t('kb.scheme_saved', { v: r.version })); }
      catch (err) { toast(err.message, true); }
    } }, h('div', { class: 'spread' }, h('strong', {}, `${s.name} (v${s.version})`), h('span', { class: s.verified ? 'chip ok' : 'chip warn' }, s.label)),
    field(t('kb.summary'), summary), field(t('benefits.official_link'), url), h('label', { class: 'check' }, verified, t('kb.mark_verified')), h('button', { type: 'submit' }, t('common.save')));
  }));
}

async function drawTranslations(box) {
  const cfg = await tenantConfig();
  const rows = [...cfg.departments.map(d => ({ entity: 'department', id: d.id, code: d.code, names: d.names })),
    ...cfg.categories.map(c => ({ entity: 'category', id: c.id, code: c.code, names: c.names }))];
  const langs = cfg.tenant.languages;
  mount(box, h('p', { class: 'small muted' }, t('kb.translations_text')), table([{ label: t('kb.entity'), render: r => `${r.entity}: ${r.code}` },
    ...langs.map(l => ({ label: l, render: r => {
      const i = h('input', { value: r.names[l] || '', 'aria-label': `${r.code} ${l}` });
      i.addEventListener('change', async () => { try { await api('/api/knowledge/translations', { method: 'PUT', body: { entity: r.entity, entity_id: r.id, language: l, name: i.value } }); toast(t('common.saved')); } catch (e) { toast(e.message, true); } });
      return i;
    } }))], rows));
}
