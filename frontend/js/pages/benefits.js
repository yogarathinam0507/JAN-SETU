// Multilingual assistant, scheme navigator (information only) and assisted-service mode.
import { api, errorBox, field, fmtDate, h, kv, loading, mount, navigate, select, state, store, t, tabs, toast } from '../core.js';
import { readAloudButton, speechSupported, startRecognition, voiceErrorText } from '../voice.js';
import { icon } from '../icons.js';

let tab = 'assistant';
const chatLog = [];
let currentScheme = null;

export async function render(app, { path }) {
  if (path === '/assist') tab = 'assisted';
  const body = h('div');
  mount(app, h('h1', {}, t('benefits.title')), h('p', { class: 'muted' }, t('benefits.subtitle')),
    h('div', { class: 'notice warn small' }, t('benefits.disclaimer')),
    tabs([['assistant', t('benefits.tab_assistant')], ['navigator', t('benefits.tab_navigator')], ['assisted', t('benefits.tab_assisted')]], tab,
      (x) => { tab = x; render(app, { path: '/benefits' }); }), body);
  if (tab === 'assistant') drawChat(body, app);
  else if (tab === 'navigator') drawNavigator(body, app);
  else drawAssisted(body, app);
}

// ---------------------------------------------------------------- assistant chat
function drawChat(box, app) {
  const log = h('div', { class: 'chat', 'aria-live': 'polite' });
  const input = h('textarea', { rows: 2, maxlength: 2000, placeholder: t('benefits.ask_ph'), style: { minHeight: '60px' } });
  const send = h('button', { class: 'primary', type: 'submit' }, t('benefits.send'));
  const paint = () => {
    mount(log, chatLog.length ? chatLog.map(m => renderMsg(m, app)) : h('p', { class: 'muted' }, t('benefits.chat_empty')));
    log.scrollTop = log.scrollHeight;
  };
  const submit = async (text) => {
    if (!text.trim()) return;
    chatLog.push({ me: true, text });
    input.value = ''; send.disabled = true; paint();
    try { chatLog.push({ me: false, reply: await api('/api/assistant/chat', { method: 'POST', body: { message: text, language: state.lang } }) }); }
    catch (e) { chatLog.push({ me: false, error: e }); }
    send.disabled = false; paint();
  };
  let rec = null;
  const mic = speechSupported() ? h('button', { type: 'button', onclick: () => {
    if (rec) { rec.stop(); return; }
    mic.replaceChildren(icon('stop'), ' ', t('citizen.stop'));
    rec = startRecognition(state.lang, { base: input.value, onText: (x) => { input.value = x; },
      onEnd: () => { rec = null; mic.replaceChildren(icon('mic'), ' ', t('citizen.speak')); },
      onError: (e) => { rec = null; mic.replaceChildren(icon('mic'), ' ', t('citizen.speak')); toast(voiceErrorText(e), true); } });
  } }, icon('mic'), ' ', t('citizen.speak')) : null;
  const examples = [t('benefits.ex1'), t('benefits.ex2'), t('benefits.ex3')];
  mount(box, h('div', { class: 'split' },
    h('div', { class: 'card' }, log,
      h('form', { class: 'stack', onsubmit: (e) => { e.preventDefault(); submit(input.value); } },
        h('label', { class: 'sr-only', for: 'ask' }, t('benefits.ask_ph')), input,
        h('div', { class: 'row' }, send, mic, h('span', { class: 'hint' }, t('benefits.voice_note'))))),
    h('div', { class: 'card' }, h('h2', {}, t('benefits.try')), h('div', { class: 'stack' }, examples.map(x => h('button', { class: 'w100', onclick: () => submit(x) }, x))),
      h('hr'), h('p', { class: 'small muted' }, t('benefits.how_answers')))));
  input.id = 'ask';
  paint();
}

function renderMsg(m, app) {
  if (m.me) return h('div', { class: 'msg me' }, m.text);
  if (m.error) return h('div', { class: 'msg' }, errorBox(m.error));
  const r = m.reply;
  const parts = [h('div', {}, r.text), h('div', { style: { marginTop: '6px' } }, readAloudButton(r.text))];
  if (r.translation_missing) parts.push(h('div', { class: 'small notice warn' }, t('benefits.translation_missing')));
  if (r.type === 'scheme') {
    const s = r.scheme;
    parts.push(h('div', { class: 'cite' }, h('strong', {}, s.name), ' ', h('span', { class: 'chip warn' }, s.label), h('p', {}, s.summary),
      h('div', { class: 'small' }, t('benefits.version', { v: s.version, d: fmtDate(s.updated_at, false) }))));
  }
  if (r.type === 'grievance') {
    parts.push(h('div', { class: 'cite' }, `${r.triage.category_name} - ${r.triage.department_name} (${t('priority.' + r.triage.priority)})`));
    if (r.triage.emergency) parts.push(h('div', { class: 'notice bad small' }, r.triage.safety_message));
  }
  if (r.answer_passages) parts.push(...r.answer_passages.map(p => h('blockquote', { class: 'small' }, p)));
  if (r.citations?.length) parts.push(h('div', { class: 'cite' }, h('strong', {}, t('benefits.sources')), h('ul', {}, r.citations.map(c =>
    h('li', {}, `${c.title} (v${c.version}, ${c.published_date || '-'}) `, h('span', { class: c.verified ? 'chip ok' : 'chip warn' }, c.label),
      c.source_url ? [' ', h('a', { href: c.source_url, target: '_blank', rel: 'noopener noreferrer' }, t('benefits.open_source'))] : null)))));
  if (r.limitations) parts.push(h('div', { class: 'meta' }, r.limitations));
  if (r.confidence !== null && r.confidence !== undefined) parts.push(h('div', { class: 'meta' }, `${t('ts.confidence')}: ${typeof r.confidence === 'number' ? Math.round(r.confidence * 100) + '%' : r.confidence}`));
  const acts = r.actions.map(a => {
    if (a.type === 'file_grievance') return h('button', { onclick: () => { store.set('jansetu.prefill', JSON.stringify(a.prefill)); navigate('/citizen'); } }, t('benefits.file_this'));
    if (a.type === 'start_eligibility') return h('button', { onclick: async () => { currentScheme = a.scheme; tab = 'navigator'; render(app, { path: '/benefits' }); } }, t('benefits.check_eligibility'));
    if (a.type === 'human_help') return h('button', { onclick: () => { tab = 'assisted'; render(app, { path: '/benefits' }); } }, t('benefits.human_help'));
    return null;
  });
  parts.push(h('div', { class: 'row' }, acts));
  return h('div', { class: 'msg' }, parts);
}

// ---------------------------------------------------------------- navigator
async function drawNavigator(box, app) {
  mount(box, loading());
  let cats, schemes;
  try { [cats, schemes] = await Promise.all([api('/api/benefits/categories'), api('/api/benefits/schemes', { query: { lang: state.lang } })]); }
  catch (e) { mount(box, errorBox(e, () => drawNavigator(box, app))); return; }
  const catSel = select([{ value: '', label: t('benefits.all_categories') }, ...cats.map(c => ({ value: c.code, label: c.name }))], '');
  const list = h('div', { class: 'stack' });
  const detailBox = h('div', { class: 'card' });
  const paintList = () => {
    const rows = schemes.filter(s => !catSel.value || s.service_category === catSel.value);
    mount(list, rows.map(s => h('button', { class: 'w100', style: { justifyContent: 'space-between' }, onclick: () => { currentScheme = s.code; showScheme(detailBox); } },
      h('span', {}, s.name), h('span', { class: s.verified ? 'chip ok' : 'chip warn' }, s.verified ? t('benefits.verified') : t('benefits.unverified')))));
  };
  catSel.addEventListener('change', paintList);
  mount(box, h('div', { class: 'split' }, h('div', { class: 'card' }, field(t('benefits.category'), catSel), list), detailBox));
  paintList();
  if (currentScheme) showScheme(detailBox); else mount(detailBox, h('p', { class: 'muted' }, t('benefits.pick_scheme')));
}

async function showScheme(box) {
  mount(box, loading());
  let s;
  try { s = await api(`/api/benefits/schemes/${currentScheme}`, { query: { lang: state.lang } }); } catch (e) { mount(box, errorBox(e)); return; }
  const answers = {};
  const result = h('div', { 'aria-live': 'polite' });
  const qs = s.questions.map(q => {
    let input;
    if (q.type === 'number') { input = h('input', { type: 'number', min: 0 }); input.addEventListener('input', () => { answers[q.id] = input.value === '' ? null : Number(input.value); }); }
    else { input = select([{ value: '', label: t('benefits.choose') }, ...q.options], ''); input.addEventListener('change', () => { answers[q.id] = input.value || null; }); }
    return field(q.text, input);
  });
  mount(box, h('div', { class: 'spread' }, h('h2', {}, s.name), h('span', { class: s.verified ? 'chip ok' : 'chip warn' }, s.label)),
    h('p', {}, s.summary),
    kv([[t('benefits.department'), s.department], [t('benefits.benefit'), s.benefits || '-'], [t('benefits.version_l'), `v${s.version} · ${fmtDate(s.updated_at, false)}`],
      [t('benefits.official_link'), s.official_url ? h('a', { href: s.official_url, target: '_blank', rel: 'noopener noreferrer' }, s.official_url) : t('benefits.no_link')]]),
    s.documents.length ? [h('h3', {}, t('benefits.documents')), h('ul', {}, s.documents.map(d => h('li', {}, d)))] : null,
    s.steps.length ? [h('h3', {}, t('benefits.steps')), h('ol', {}, s.steps.map(d => h('li', {}, d)))] : null,
    h('p', { class: 'small muted' }, s.source_note),
    s.questions.length ? h('form', { class: 'card', onsubmit: async (e) => {
      e.preventDefault();
      try {
        const r = await api(`/api/benefits/schemes/${s.code}/check`, { method: 'POST', body: { answers, language: state.lang } });
        const cls = { potentially_eligible: 'ok', more_information_required: 'warn', likely_not_eligible: 'bad', not_enough_verified_information: 'sim' }[r.outcome];
        mount(result, h('div', { class: `notice ${cls}` }, h('strong', {}, r.outcome_label),
          h('ul', { class: 'small' }, r.reasons.map(x => h('li', {}, x))),
          r.missing_questions.length ? h('p', { class: 'small' }, t('benefits.missing', { q: r.missing_questions.map(q => q.text).join('; ') })) : null,
          r.preliminary_rule_check !== r.outcome ? h('p', { class: 'small' }, t('benefits.preliminary', { r: r.preliminary_rule_check.replaceAll('_', ' ') })) : null,
          h('p', { class: 'small' }, r.disclaimer)));
      } catch (err) { mount(result, errorBox(err)); }
    } }, h('h3', {}, t('benefits.check_h')), qs, h('button', { class: 'primary', type: 'submit' }, t('benefits.check_btn')), result)
      : h('div', { class: 'notice' }, t('benefits.no_rules')));
}

// ---------------------------------------------------------------- assisted service
function drawAssisted(box, app) {
  const name = h('input', { maxlength: 120, autocomplete: 'name' });
  const phone = h('input', { inputmode: 'numeric', maxlength: 10, autocomplete: 'tel' });
  const topic = h('textarea', { maxlength: 500, style: { minHeight: '70px' } });
  const consent = h('input', { type: 'checkbox' });
  const out = h('div', { 'aria-live': 'polite' });
  mount(box, h('div', { class: 'grid g2 assist-mode' },
    h('div', { class: 'card stack' }, h('h2', {}, t('assist.h')), h('p', {}, t('assist.text')),
      h('button', { class: 'big primary', onclick: () => navigate('/citizen') }, icon('mic'), ' ', t('assist.speak_complaint')),
      h('button', { class: 'big', onclick: () => { tab = 'navigator'; render(app, { path: '/benefits' }); } }, icon('clipboard'), ' ', t('assist.find_schemes')),
      h('button', { class: 'big', onclick: () => navigate('/citizen/tickets') }, icon('search'), ' ', t('assist.track'))),
    h('form', { class: 'card', onsubmit: async (e) => {
      e.preventDefault(); out.replaceChildren();
      try {
        const r = await api('/api/assistant/callback-request', { method: 'POST', body: { name: name.value, phone: phone.value.trim(), language: state.lang, topic: topic.value, consent: consent.checked } });
        mount(out, h('div', { class: 'notice ok' }, h('strong', {}, r.message), h('p', { class: 'mono' }, r.reference), h('p', { class: 'small' }, r.note)));
      } catch (err) { mount(out, errorBox(err)); }
    } }, h('h2', {}, t('assist.callback_h')), h('p', { class: 'small muted' }, t('assist.callback_text')),
    field(t('citizen.name'), name), field(t('login.mobile'), phone), field(t('assist.topic'), topic),
    h('label', { class: 'check' }, consent, t('assist.consent')), out, h('button', { class: 'primary big', type: 'submit' }, t('assist.request')))));
}
