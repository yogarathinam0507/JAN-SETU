// Citizen grievance filing: describe -> confirm language/transcript -> confirm category/location -> review -> submit.
import { ApiError, api, errorBox, field, h, kv, mount, priorityChip, state, store, t, toast } from '../core.js';
import { dictationBar, readAloudButton } from '../voice.js';
import { icon } from '../icons.js';
import { createMap, pickPin } from '../map.js';

let f = null;
const STEPS = ['describe', 'language', 'category', 'review', 'done'];

function reset() {
  f = { step: 'describe', text: '', inputMode: 'text', language: state.lang, lat: null, lng: null, locationText: '',
    triage: null, triageError: null, transcriptConfirmed: false, disputed: false, disputeNote: '', name: '', phone: '',
    consent: false, files: [], result: null, busy: false };
  const pre = store.get('jansetu.prefill');
  if (pre) { try { const p = JSON.parse(pre); f.text = p.text || ''; f.language = p.language || f.language; f.fromAssistant = true; } catch { /* */ } store.set('jansetu.prefill', null); }
}

export async function render(app) {
  if (!f || f.step === 'done' && !f.result) reset();
  if (state.user && state.user.role !== 'citizen') {
    mount(app, h('h1', {}, t('citizen.title')), h('div', { class: 'notice' }, t('citizen.staff_note')));
    return;
  }
  draw(app);
}

function stepper() {
  return h('ol', { class: 'steps', 'aria-label': t('citizen.progress') }, STEPS.map((s, i) => {
    const cur = STEPS.indexOf(f.step);
    return h('li', { class: i === cur ? 'on' : i < cur ? 'done' : null, 'aria-current': i === cur ? 'step' : null }, t(`citizen.step_${s}`));
  }));
}

function draw(app) {
  const left = h('div', { class: 'card' });
  const right = h('aside', { class: 'card', 'aria-live': 'polite' });
  mount(app, h('h1', {}, t('citizen.title')), h('p', { class: 'muted' }, t('citizen.subtitle')), stepper(),
    f.fromAssistant ? h('div', { class: 'notice' }, t('citizen.from_assistant')) : null,
    h('div', { class: 'split' }, left, right));
  ({ describe: drawDescribe, language: drawLanguage, category: drawCategory, review: drawReview, done: drawDone })[f.step](left, app);
  drawTrustShield(right);
}

// ---------------------------------------------------------------- step 1
function drawDescribe(box, app) {
  const ta = h('textarea', { maxlength: 4000, placeholder: t('citizen.describe_ph'), 'aria-describedby': 'describe-hint' });
  ta.value = f.text;
  ta.addEventListener('input', () => { f.text = ta.value; if (f.inputMode === 'voice') f.transcriptConfirmed = false; });
  const mic = dictationBar(ta, { lang: f.language, onChange: (txt, lang) => {
    f.text = txt; f.inputMode = 'voice'; f.transcriptConfirmed = false; f.language = lang;
  } });
  const loc = h('input', { maxlength: 300, placeholder: t('citizen.location_ph') });
  loc.value = f.locationText;
  loc.addEventListener('input', () => { f.locationText = loc.value; });
  const gpsOut = h('span', { class: 'small muted', 'aria-live': 'polite' }, f.lat !== null ? t('citizen.gps_set', { lat: f.lat.toFixed(5), lng: f.lng.toFixed(5) }) : t('citizen.map_hint'));
  const mapEl = h('div', { class: 'map', style: { height: '300px' }, role: 'application', 'aria-label': t('citizen.map_label') });
  let pin = null, mapCtx = null;
  const setPin = (lat, lng, fly) => {
    f.lat = lat; f.lng = lng;
    gpsOut.textContent = t('citizen.gps_set', { lat: lat.toFixed(5), lng: lng.toFixed(5) });
    if (!mapCtx) return;
    if (!pin) {
      pin = pickPin(mapCtx.L, lat, lng).addTo(mapCtx.map);
      pin.on('dragend', () => { const p = pin.getLatLng(); setPin(p.lat, p.lng, false); });
    } else pin.setLatLng([lat, lng]);
    if (fly) mapCtx.map.flyTo([lat, lng], 17);
  };
  createMap(mapEl, f.lat !== null ? { center: { lat: f.lat, lng: f.lng }, zoom: 16 } : {}).then((ctx) => {
    mapCtx = ctx;
    ctx.map.on('click', (e) => setPin(e.latlng.lat, e.latlng.lng, false));
    if (f.lat !== null) setPin(f.lat, f.lng, false);
  }).catch(() => { mapEl.replaceChildren(h('p', { class: 'muted small', style: { padding: '12px' } }, t('map.unavailable'))); });
  const gpsBtn = h('button', { type: 'button', onclick: () => {
    if (!navigator.geolocation) { gpsOut.textContent = t('citizen.gps_unavailable'); return; }
    gpsOut.textContent = t('common.loading');
    navigator.geolocation.getCurrentPosition(
      (p) => setPin(p.coords.latitude, p.coords.longitude, true),
      () => { gpsOut.textContent = t('citizen.gps_denied'); }, { timeout: 10000, enableHighAccuracy: true });
  } }, icon('crosshair'), t('citizen.gps'));
  const clearGps = h('button', { type: 'button', class: 'link', onclick: () => { f.lat = f.lng = null; if (pin) { pin.remove(); pin = null; } gpsOut.textContent = t('citizen.map_hint'); } }, t('citizen.gps_clear'));
  const fileIn = h('input', { type: 'file', accept: 'image/jpeg,image/png,application/pdf', multiple: true });
  fileIn.addEventListener('change', () => { f.files = [...fileIn.files].slice(0, 3); });
  const err = h('div');
  const next = h('button', { class: 'primary big', type: 'submit' }, t('citizen.analyse'));
  mount(box, h('form', { onsubmit: async (e) => {
    e.preventDefault();
    err.replaceChildren();
    if (f.text.trim().length < 3) { err.append(h('p', { class: 'err' }, t('citizen.too_short'))); ta.focus(); return; }
    next.disabled = true; next.textContent = t('citizen.analysing');
    await runTriage();
    next.disabled = false;
    f.step = 'language'; draw(app);
  } },
  h('h2', {}, t('citizen.describe_h')),
  field(t('citizen.describe_label'), ta, t('citizen.describe_hint')),
  mic,
  h('p', { class: 'hint', id: 'describe-hint' }, t('citizen.voice_privacy')),
  field(t('citizen.location_label'), loc), mapEl, h('div', { class: 'row', style: { margin: '8px 0 14px' } }, gpsBtn, clearGps, gpsOut),
  field(t('citizen.evidence_label'), fileIn, t('citizen.evidence_hint')),
  err, next));
}

async function runTriage() {
  f.triage = null; f.triageError = null;
  try {
    f.triage = await api('/api/triage/preview', { method: 'POST', body: { text: f.text.trim(), language: f.language,
      input_mode: f.inputMode, lat: f.lat, lng: f.lng, location_text: f.locationText } });
  } catch (e) { f.triageError = e; }
}

// ---------------------------------------------------------------- step 2
function drawLanguage(box, app) {
  const back = h('button', { type: 'button', onclick: () => { f.step = 'describe'; draw(app); } }, t('common.back'));
  if (f.triageError) {
    mount(box, h('h2', {}, t('citizen.language_h')), errorBox(f.triageError, async () => { await runTriage(); draw(app); }),
      h('p', {}, t('citizen.human_fallback_text')),
      h('div', { class: 'row' }, back, h('button', { class: 'primary', onclick: () => { f.disputed = true; f.disputeNote = 'AI unavailable'; f.step = 'review'; draw(app); } }, t('citizen.send_human'))));
    return;
  }
  const det = f.triage.language_detection;
  const mismatch = det.code !== 'und' && det.code !== f.language && !(det.code === 'en' && det.transliterated_from === f.language);
  const confirm = h('input', { type: 'checkbox', checked: f.transcriptConfirmed });
  confirm.addEventListener('change', () => { f.transcriptConfirmed = confirm.checked; });
  const ta = h('textarea', {}); ta.value = f.text;
  const err = h('div');
  mount(box, h('h2', {}, t('citizen.language_h')),
    kv([[t('citizen.selected_language'), f.language], [t('citizen.detected_language'), `${det.code} (${Math.round(det.confidence * 100)}% ${det.method})`],
      det.transliterated_from ? [t('citizen.transliterated'), det.transliterated_from] : null]),
    mismatch ? h('div', { class: 'notice warn' }, t('citizen.lang_mismatch', { a: f.language, b: det.code })) : null,
    f.inputMode === 'voice'
      ? h('div', {}, h('h3', {}, t('citizen.transcript_h')), h('p', { class: 'small muted' }, t('citizen.transcript_help')),
        field(t('citizen.transcript_label'), ta), h('label', { class: 'check' }, confirm, t('citizen.transcript_confirm')))
      : h('div', {}, h('h3', {}, t('citizen.your_text')), h('div', { class: 'transcript' }, f.text)),
    err,
    h('div', { class: 'row' }, back, h('button', { class: 'primary', onclick: async () => {
      err.replaceChildren();
      if (f.inputMode === 'voice') {
        if (ta.value.trim() !== f.text.trim()) { f.text = ta.value; f.transcriptConfirmed = confirm.checked; await runTriage(); }
        if (!f.transcriptConfirmed) { err.append(h('p', { class: 'err' }, t('citizen.confirm_transcript_first'))); return; }
      }
      f.step = 'category'; draw(app);
    } }, t('common.continue'))));
}

// ---------------------------------------------------------------- step 3
function drawCategory(box, app) {
  const tr = f.triage;
  const disputeNote = h('input', { maxlength: 300, placeholder: t('citizen.dispute_ph') });
  disputeNote.value = f.disputeNote;
  const yes = h('input', { type: 'radio', name: 'agree', checked: !f.disputed });
  const no = h('input', { type: 'radio', name: 'agree', checked: f.disputed });
  yes.addEventListener('change', () => { f.disputed = false; });
  no.addEventListener('change', () => { f.disputed = true; });
  mount(box, h('h2', {}, t('citizen.category_h')),
    tr.emergency ? h('div', { class: 'notice bad', role: 'alert' }, icon('alert'), ' ', h('strong', {}, tr.safety_message)) : null,
    tr.human_review_required
      ? h('div', { class: 'notice warn' }, h('strong', {}, t('citizen.human_review_h')), h('p', {}, tr.human_review_reason), h('p', { class: 'small' }, t('citizen.human_review_text')))
      : h('div', {}, kv([[t('citizen.category'), tr.category_name], [t('citizen.department'), tr.department_name],
        [t('citizen.priority'), priorityChip(tr.priority)], [t('citizen.sla'), tr.sla_hours ? t('citizen.sla_hours', { h: tr.sla_hours }) : '-']]),
      h('fieldset', { style: { border: '0', padding: '0', marginTop: '12px' } }, h('legend', { class: 'small' }, t('citizen.is_this_right')),
        h('label', { class: 'check' }, yes, t('citizen.yes_right')), h('label', { class: 'check' }, no, t('citizen.no_wrong')),
        field(t('citizen.dispute_label'), disputeNote))),
    h('h3', {}, t('citizen.location_h')),
    kv([[t('citizen.location_text'), tr.location_text || f.locationText || t('citizen.not_given')],
      [t('citizen.ward'), tr.jurisdiction_name ? `${tr.jurisdiction_name} (${tr.jurisdiction_method})` : t('citizen.ward_unknown')],
      [t('citizen.gps_pin'), f.lat !== null ? `${f.lat.toFixed(5)}, ${f.lng.toFixed(5)}` : t('citizen.not_given')]]),
    h('div', { class: 'row', style: { marginTop: '12px' } },
      h('button', { onclick: () => { f.step = 'language'; draw(app); } }, t('common.back')),
      h('button', { class: 'primary', onclick: () => { f.disputeNote = disputeNote.value; f.step = 'review'; draw(app); } }, t('common.continue'))));
}

// ---------------------------------------------------------------- step 4
function drawReview(box, app) {
  const name = h('input', { maxlength: 120, autocomplete: 'name' });
  const phone = h('input', { inputmode: 'numeric', maxlength: 10, pattern: '[6-9][0-9]{9}', autocomplete: 'tel' });
  name.value = f.name || state.user?.full_name || '';
  phone.value = f.phone;
  const consent = h('input', { type: 'checkbox', checked: f.consent });
  const err = h('div');
  const submit = h('button', { class: 'primary big', type: 'submit' }, t('citizen.submit'));
  const needPhone = !state.user;
  mount(box, h('form', { onsubmit: async (e) => {
    e.preventDefault(); err.replaceChildren();
    f.name = name.value; f.phone = phone.value.trim(); f.consent = consent.checked;
    if (needPhone && !/^[6-9]\d{9}$/.test(f.phone)) { err.append(h('p', { class: 'err' }, t('citizen.phone_required'))); phone.focus(); return; }
    if (!f.consent) { err.append(h('p', { class: 'err' }, t('citizen.consent_required'))); return; }
    submit.disabled = true; submit.textContent = t('citizen.submitting');
    try {
      const res = await api('/api/grievances', { method: 'POST', body: {
        text: f.text.trim(), triage_id: f.triage?.triage_id || null, language: f.language, input_mode: f.inputMode,
        transcript_confirmed: f.inputMode === 'voice' ? f.transcriptConfirmed : false,
        channel: f.fromAssistant ? 'assistant' : 'web', lat: f.lat, lng: f.lng, location_text: f.locationText,
        contact_name: f.name, contact_phone: f.phone, consent: f.consent,
        request_human_review: f.disputed, human_review_note: f.disputeNote } });
      for (const file of f.files) {
        const form = new FormData(); form.append('kind', 'evidence'); form.append('file', file);
        if (state.token) { try { await api(`/api/grievances/${res.public_id}/attachments`, { method: 'POST', form }); } catch (e2) { toast(`${file.name}: ${e2.message}`, true); } }
      }
      if (f.files.length && !state.token) toast(t('citizen.files_need_login'), true);
      f.result = res; f.step = 'done'; draw(app);
    } catch (e2) {
      submit.disabled = false; submit.textContent = t('citizen.submit');
      err.append(errorBox(e2, e2 instanceof ApiError && e2.code === 'triage_failed' ? () => { f.disputed = true; } : null));
    }
  } },
  h('h2', {}, t('citizen.review_h')),
  h('div', { class: 'transcript' }, f.text),
  kv([[t('citizen.routing'), f.disputed || f.triage?.human_review_required ? t('citizen.routing_human') : `${f.triage?.department_name} · ${t('priority.' + f.triage?.priority)}`],
    [t('citizen.input_mode'), f.inputMode === 'voice' ? t('citizen.voice_confirmed') : t('citizen.typed')],
    [t('citizen.attachments'), f.files.length ? f.files.map(x => x.name).join(', ') : '-']]),
  h('hr'),
  field(t('citizen.name'), name), field(needPhone ? t('citizen.phone_req') : t('citizen.phone_opt'), phone, t('citizen.phone_hint')),
  h('label', { class: 'check' }, consent, h('span', {}, t('citizen.consent_text'), ' ', h('a', { href: '/privacy', 'data-link': true }, t('nav.privacy')))),
  err,
  h('div', { class: 'row' }, h('button', { type: 'button', onclick: () => { f.step = 'category'; draw(app); } }, t('common.back')), submit)));
}

// ---------------------------------------------------------------- step 5
function drawDone(box) {
  const r = f.result;
  mount(box, h('div', { class: 'notice ok' }, h('h2', {}, t('citizen.done_h')),
    h('p', {}, t('citizen.your_ticket')), h('p', { class: 'mono', style: { fontSize: '1.5rem', fontWeight: '700' } }, r.public_id),
    h('p', {}, r.status_label)),
  r.assignment_notice ? h('div', { class: 'assign-notice', role: 'status' }, icon('user'),
    h('div', {}, h('strong', {}, t('citizen.assigned_h')), h('p', { style: { margin: '2px 0 6px' } }, r.assignment_notice),
      readAloudButton(() => `${t('citizen.your_ticket')} ${r.public_id.split('').join(' ')}. ${r.assignment_notice}`))) : null,
  kv([[t('citizen.department'), r.department?.name || t('citizen.routing_human')], [t('citizen.priority'), priorityChip(r.priority)],
    [t('citizen.sla_due'), r.sla_due_at ? new Date(r.sla_due_at).toLocaleString() : t('citizen.sla_after_routing')],
    [t('citizen.created'), new Date(r.created_at).toLocaleString()]]),
  r.master_incident ? h('p', { class: 'notice' }, t('citizen.linked_master', { id: r.master_incident.public_id })) : null,
  h('p', { class: 'small muted' }, state.user ? t('citizen.track_logged_in') : t('citizen.track_guest')),
  h('div', { class: 'row' },
    h('a', { class: 'btn primary', href: state.user ? `/citizen/tickets/${r.public_id}` : `/citizen/tickets?track=${r.public_id}`, 'data-link': true }, t('citizen.view_ticket')),
    h('button', { onclick: () => { reset(); render(document.getElementById('app')); } }, t('citizen.file_another'))));
}

// ---------------------------------------------------------------- routing details panel
function drawTrustShield(box) {
  const tr = f.triage;
  if (!tr) {
    mount(box, h('h2', {}, t('ts.title')), h('p', { class: 'muted' }, t('ts.empty')),
      h('ul', { class: 'small muted' }, h('li', {}, t('ts.how1')), h('li', {}, t('ts.how2')), h('li', {}, t('ts.how3'))));
    return;
  }
  mount(box, h('h2', {}, t('ts.title')),
    kv([[t('ts.category'), tr.category_name || t('ts.none')], [t('ts.department'), tr.department_name || t('ts.none')],
      [t('ts.priority'), priorityChip(tr.priority)],
      [t('ts.human_review'), tr.human_review_required ? h('span', { class: 'chip warn' }, t('common.yes')) : h('span', { class: 'chip ok' }, t('common.no'))],
      [t('ts.ward'), tr.jurisdiction_name || t('citizen.ward_unknown')]]),
    h('h3', {}, t('ts.reasons')), h('ul', { class: 'small' }, (tr.reasoning_summary.length ? tr.reasoning_summary : [t('ts.no_reasons')]).map(r => h('li', {}, r))),
    h('p', { class: 'hint' }, t('ts.footer')));
}
