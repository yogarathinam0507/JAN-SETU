// Helpline: agent workbench + supervisor/QA view. Simulated channels are labelled on every record.
import { api, empty, errorBox, field, fmtDate, fmtDuration, h, kv, loading, mount, priorityChip, select, simChip, state, t, table,
  toast } from '../core.js';

let activeId = null;

export async function render(app) {
  if (state.user.role !== 'agent') return supervisor(app);
  const queueBox = h('div', { class: 'card' });
  const work = h('div', { class: 'card' }, empty(t('agent.pick')));
  mount(app, h('h1', {}, t('agent.title')), h('div', { id: 'tel-status' }),
    h('div', { class: 'split' }, work, queueBox));
  await drawQueue(queueBox, work);
  if (activeId) drawWork(work, queueBox);
}

async function drawQueue(box, work) {
  let q;
  try { q = await api('/api/agent/queue'); } catch (e) { mount(box, errorBox(e, () => drawQueue(box, work))); return; }
  mount(document.getElementById('tel-status'), h('div', { class: 'notice sim small' }, q.telephony.message));
  const script = select([{ value: '', label: t('agent.random_script') }, { value: 0, label: 'Kannada streetlight' }, { value: 1, label: 'English dirty water' },
    { value: 2, label: 'Hindi scheme query' }, { value: 3, label: 'English transformer sparking' }], '');
  const item = (i, btn) => h('li', { class: 'row', style: { justifyContent: 'space-between', borderBottom: '1px solid var(--line)', padding: '6px 0' } },
    h('span', {}, i.practice ? simChip(t('agent.sim_call')) : h('span', { class: 'chip info' }, t('agent.real')), ' ', h('strong', {}, i.channel.replace('_', ' ')), ' · ', i.language, ' · ', priorityChip(i.priority),
      h('div', { class: 'small muted' }, `${i.caller_name} ${i.caller_phone} · ${t('agent.wait')} ${fmtDuration(i.wait_seconds)}`)), btn);
  mount(box, h('div', { class: 'spread' }, h('h2', {}, t('agent.queue')), h('button', { onclick: () => render(document.getElementById('app')) }, t('common.refresh'))),
    kv([[t('agent.queued'), String(q.stats.queued)], [t('agent.longest'), fmtDuration(q.stats.longest_wait_seconds)], [t('agent.avg_wait'), fmtDuration(q.stats.avg_wait_seconds)]]),
    h('ul', { style: { listStyle: 'none', padding: 0 } }, q.queued.map(i => item(i, h('button', { class: 'primary', onclick: async () => {
      try { await api(`/api/agent/interactions/${i.id}/accept`, { method: 'POST' }); activeId = i.id; render(document.getElementById('app')); } catch (e) { toast(e.message, true); }
    } }, t('agent.accept'))))),
    q.queued.length ? null : empty(t('agent.queue_empty')),
    h('h3', {}, t('agent.mine')), h('ul', { style: { listStyle: 'none', padding: 0 } }, q.mine.map(i => item(i, h('button', { onclick: () => { activeId = i.id; drawWork(work, box); } }, t('agent.open'))))),
    q.callbacks.length ? [h('h3', {}, t('agent.callbacks')), h('ul', {}, q.callbacks.map(i => h('li', { class: 'small' }, `${fmtDate(i.callback_at)} · ${i.caller_name} ${i.caller_phone}`)))] : null,
    h('hr'), h('h3', {}, t('agent.simulate_h')), h('p', { class: 'small muted' }, t('agent.simulate_text')),
    h('div', { class: 'row' }, script, h('button', { onclick: async () => {
      try { await api('/api/agent/simulate-call', { method: 'POST', body: { script: script.value === '' ? null : Number(script.value) } }); render(document.getElementById('app')); }
      catch (e) { toast(e.message, true); }
    } }, t('agent.simulate'))),
    manualForm(work, box));
}

function manualForm(work, queueBox) {
  const ch = select(['voice', 'web_chat', 'email', 'whatsapp'].map(c => ({ value: c, label: c })), 'voice');
  const name = h('input', { placeholder: t('agent.caller_name'), maxlength: 120 });
  const phone = h('input', { placeholder: '9XXXXXXXXX', maxlength: 10, inputmode: 'numeric' });
  const msg = h('input', { placeholder: t('agent.first_message'), maxlength: 2000 });
  return h('details', {}, h('summary', {}, t('agent.log_manual')),
    h('form', { class: 'stack', onsubmit: async (e) => {
      e.preventDefault();
      try { const i = await api('/api/agent/interactions', { method: 'POST', body: { channel: ch.value, caller_name: name.value, caller_phone: phone.value, language: state.lang, first_message: msg.value } }); activeId = i.id; drawWork(work, queueBox); }
      catch (err) { toast(err.message, true); }
    } }, ch, name, phone, msg, h('p', { class: 'hint' }, t('agent.manual_note')), h('button', { type: 'submit' }, t('agent.create'))));
}

async function drawWork(box, queueBox) {
  mount(box, loading());
  let i;
  try { i = await api(`/api/agent/interactions/${activeId}`); } catch (e) { mount(box, errorBox(e)); return; }
  const assistBox = h('div', {}, loading(t('agent.assisting')));
  const speaker = select([{ value: 'caller', label: t('agent.caller') }, { value: 'agent', label: t('agent.me') }], 'caller');
  const line = h('input', { maxlength: 2000, placeholder: t('agent.add_line_ph') });
  const phoneOut = h('span', { class: 'mono' }, `${i.caller_name} · ${i.caller_phone}`);
  mount(box,
    h('div', { class: 'spread' }, h('h2', {}, `${i.public_id}`), h('div', { class: 'row' }, i.practice ? simChip(t('agent.sim_call')) : h('span', { class: 'chip info' }, i.channel_label), priorityChip(i.priority), h('span', { class: 'chip' }, i.status))),
    kv([[t('agent.caller'), h('span', {}, phoneOut, ' ', h('button', { class: 'link', onclick: async () => {
      const reason = prompt(t('officer.reveal_reason')); if (!reason) return;
      try { const r = await api(`/api/agent/interactions/${i.id}/reveal`, { method: 'POST', body: { reason } }); phoneOut.textContent = `${r.caller_name} · ${r.caller_phone} (${t('officer.audited')})`; } catch (e) { toast(e.message, true); }
    } }, t('officer.reveal')))], [t('officer.language'), i.language], [t('agent.queued_at'), fmtDate(i.queued_at)], [t('agent.ticket'), i.grievance || '-'],
      [t('agent.retention'), fmtDate(i.transcript_expires_at, false)]]),
    h('h3', {}, t('agent.transcript')), h('div', { class: 'transcript' }, i.transcript.map(l => h('div', {}, h('strong', {}, `${l.speaker}: `), l.text, l.source === 'simulated-script' ? h('span', { class: 'small muted' }, ` [${t('agent.sim_call')}]`) : null))),
    i.status !== 'closed' ? h('form', { class: 'row', onsubmit: async (e) => {
      e.preventDefault(); if (!line.value.trim()) return;
      try { await api(`/api/agent/interactions/${i.id}/transcript`, { method: 'POST', body: { speaker: speaker.value, text: line.value } }); drawWork(box, queueBox); } catch (err) { toast(err.message, true); }
    } }, speaker, line, h('button', { type: 'submit' }, t('agent.add_line'))) : null,
    h('h3', {}, t('agent.assist')), assistBox, h('div', { id: 'agent-forms' }));
  let a;
  try { a = await api(`/api/agent/interactions/${i.id}/assist`); } catch (e) { mount(assistBox, errorBox(e)); return; }
  const tr = a.triage;
  mount(assistBox, h('p', { class: 'small notice warn' }, a.ai_label),
    a.triage_error ? h('div', { class: 'notice bad' }, a.triage_error) : null,
    tr ? h('div', {}, tr.emergency ? h('div', { class: 'notice bad' }, tr.safety_message) : null,
      kv([[t('ts.category'), tr.category_name || t('ts.none')], [t('ts.department'), tr.department_name || '-'], [t('ts.priority'), priorityChip(tr.priority)],
        [t('ts.confidence'), `${Math.round(tr.confidence * 100)}%`], [t('ts.human_review'), tr.human_review_required ? tr.human_review_reason : t('common.no')],
        [t('agent.sentiment'), a.sentiment]])) : h('p', { class: 'muted' }, t('agent.no_text')),
    a.duplicate_candidate ? h('div', { class: 'notice warn' }, t('agent.dup', { id: a.duplicate_candidate.public_id, s: a.duplicate_candidate.status })) : null,
    a.knowledge.length ? h('div', {}, h('h3', {}, t('agent.kb')), a.knowledge.map(k => h('div', { class: 'cite' }, h('strong', {}, `${k.title} v${k.version} `), h('span', { class: k.verified ? 'chip ok' : 'chip warn' }, k.label), h('p', { class: 'small' }, k.text)))) : null,
    h('h3', {}, t('agent.summary')), h('p', {}, a.summary), h('ul', { class: 'small' }, a.action_items.map(x => h('li', {}, x))));
  if (i.status === 'closed') return;
  const forms = document.getElementById('agent-forms');
  const loc = h('input', { maxlength: 300, placeholder: t('citizen.location_ph') });
  const consent = h('input', { type: 'checkbox' });
  const disp = select(Object.entries(a.dispositions).map(([v, l]) => ({ value: v, label: l })), i.grievance ? 'grievance_registered' : 'information_provided');
  const summary = h('textarea', { style: { minHeight: '80px' } }); summary.value = a.summary;
  const cb = h('input', { type: 'datetime-local' });
  const agents = await api('/api/agent/agents').catch(() => []);
  const toAgent = select([{ value: '', label: t('agent.supervisor_queue') }, ...agents.map(x => ({ value: x.id, label: x.name }))], '');
  const hoNote = h('input', { maxlength: 500, placeholder: t('agent.handoff_note') });
  mount(forms,
    !i.grievance ? h('form', { class: 'card stack', onsubmit: async (e) => {
      e.preventDefault();
      try { const r = await api(`/api/agent/interactions/${i.id}/create-ticket`, { method: 'POST', body: { location_text: loc.value, consent_confirmed_verbally: consent.checked } }); toast(t('agent.ticket_created', { id: r.grievance.public_id })); drawWork(box, queueBox); }
      catch (err) { toast(err.message, true); }
    } }, h('h3', {}, t('agent.create_ticket')), loc, h('label', { class: 'check' }, consent, t('agent.verbal_consent')),
    h('div', { class: 'row' }, h('button', { class: 'primary', type: 'submit' }, t('agent.create_ticket')),
      a.duplicate_candidate ? h('button', { type: 'button', onclick: async () => {
        try { await api(`/api/agent/interactions/${i.id}/create-ticket`, { method: 'POST', body: { link_to_existing: a.duplicate_candidate.public_id } }); toast(t('agent.linked')); drawWork(box, queueBox); } catch (err) { toast(err.message, true); }
      } }, t('agent.link_existing', { id: a.duplicate_candidate.public_id })) : null)) : null,
    h('form', { class: 'card stack', onsubmit: async (e) => {
      e.preventDefault();
      try {
        await api(`/api/agent/interactions/${i.id}/wrap`, { method: 'POST', body: { disposition: disp.value, summary: summary.value, action_items: a.action_items, callback_at: cb.value ? new Date(cb.value).toISOString() : null } });
        toast(t('agent.wrapped')); activeId = null; render(document.getElementById('app'));
      } catch (err) { toast(err.message, true); }
    } }, h('h3', {}, t('agent.wrap')), field(t('agent.disposition'), disp), field(t('agent.summary_edit'), summary), field(t('agent.callback'), cb), h('button', { class: 'primary', type: 'submit' }, t('agent.close'))),
    h('form', { class: 'card row', onsubmit: async (e) => {
      e.preventDefault();
      try { await api(`/api/agent/interactions/${i.id}/handoff`, { method: 'POST', body: { to_agent_id: toAgent.value || null, note: hoNote.value } }); toast(t('agent.handed_off')); activeId = null; render(document.getElementById('app')); }
      catch (err) { toast(err.message, true); }
    } }, h('strong', {}, t('agent.handoff')), toAgent, hoNote, h('button', { type: 'submit' }, t('agent.handoff_btn'))));
}

// ---------------------------------------------------------------- supervisor / QA
async function supervisor(app) {
  mount(app, h('h1', {}, t('agent.sup_title')), loading());
  let s;
  try { s = await api('/api/agent/supervisor'); } catch (e) { mount(app, h('h1', {}, t('agent.sup_title')), errorBox(e)); return; }
  const qaBox = h('div', { class: 'card' }, empty(t('agent.qa_pick')));
  const tile = (v, l) => h('div', { class: 'card kpi' }, h('div', { class: 'v' }, String(v ?? '-')), h('div', { class: 'l' }, l));
  mount(app, h('h1', {}, t('agent.sup_title')), s.data_label ? h('div', { class: 'notice sim small' }, s.data_label) : null,
    h('p', { class: 'small muted' }, s.window),
    h('div', { class: 'grid g4' }, tile(s.total, t('agent.interactions')), tile(fmtDuration(s.avg_wait_seconds), t('agent.avg_wait')),
      tile(s.tickets_created, t('agent.tickets_created')), tile(s.qa.avg_percent !== null ? `${s.qa.avg_percent}%` : '-', t('agent.qa_avg', { n: s.qa.reviewed }))),
    h('div', { class: 'split', style: { marginTop: '12px' } },
      table([{ label: 'ID', render: i => h('span', { class: 'mono' }, i.public_id) }, { label: t('agent.channel'), render: i => i.practice ? simChip(i.channel_label) : i.channel_label },
        { label: t('tickets.status'), key: 'status' }, { label: t('agent.agent'), render: i => i.agent || '-' }, { label: t('agent.disposition'), render: i => i.disposition || '-' },
        { label: t('agent.wait'), render: i => fmtDuration(i.wait_seconds) }], s.recent, { onRow: i => qaForm(qaBox, i.id, s.qa.rubric) }), qaBox),
    h('div', { class: 'card', style: { marginTop: '12px' } }, h('h2', {}, t('agent.per_agent')), h('ul', {}, s.per_agent.map(p => h('li', {}, `${p.agent}: ${p.interactions}`)))));
}

async function qaForm(box, id, rubric) {
  let i;
  try { i = await api(`/api/agent/interactions/${id}`); } catch (e) { mount(box, errorBox(e)); return; }
  const inputs = {};
  mount(box, h('h2', {}, `${t('agent.qa_review')} ${i.public_id}`), i.practice ? simChip(t('agent.sim_call')) : null,
    h('div', { class: 'transcript' }, i.transcript.map(l => h('div', {}, `${l.speaker}: ${l.text}`))), h('p', {}, i.summary || ''),
    i.qa_review ? h('div', { class: 'notice ok' }, t('agent.qa_existing', { p: i.qa_review.percent, by: i.qa_review.reviewer })) : null,
    i.status === 'closed' ? h('form', { class: 'stack', onsubmit: async (e) => {
      e.preventDefault();
      const scores = Object.fromEntries(Object.entries(inputs).map(([k, el]) => [k, Number(el.value)]));
      try { const r = await api(`/api/agent/interactions/${id}/qa`, { method: 'POST', body: { scores, comments: '' } }); toast(`QA ${r.qa_review.percent}%`); qaForm(box, id, rubric); }
      catch (err) { toast(err.message, true); }
    } }, rubric.map(r => { inputs[r.id] = select([0, 1, 2].slice(0, r.max + 1).map(n => ({ value: n, label: String(n) })), 2); return field(`${r.label} (0-${r.max})`, inputs[r.id]); }),
    h('button', { class: 'primary', type: 'submit' }, t('agent.qa_save'))) : h('p', { class: 'muted' }, t('agent.qa_closed_only')));
}
