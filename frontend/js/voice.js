// Speech input (Web Speech API) and read-aloud (speechSynthesis). The transcript is ALWAYS shown to the user for
// editing/confirmation; nothing is submitted automatically.
import { h, state, t } from './core.js';
import { icon } from './icons.js';

export const SPEECH_CODES = { en: 'en-IN', kn: 'kn-IN', hi: 'hi-IN', ta: 'ta-IN', te: 'te-IN', ml: 'ml-IN', mr: 'mr-IN',
  bn: 'bn-IN', gu: 'gu-IN', pa: 'pa-IN', or: 'or-IN', ur: 'ur-IN' };
export const SPEECH_LANGS = [['en', 'English (India)'], ['kn', 'ಕನ್ನಡ'], ['hi', 'हिन्दी'], ['ta', 'தமிழ்'], ['te', 'తెలుగు'],
  ['ml', 'മലയാളം'], ['mr', 'मराठी'], ['bn', 'বাংলা'], ['gu', 'ગુજરાતી'], ['pa', 'ਪੰਜਾਬੀ'], ['ur', 'اردو']];

export function speechSupported() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

const ERRORS = {
  'not-allowed': 'voice.err_permission', 'service-not-allowed': 'voice.err_permission', 'no-speech': 'voice.err_nospeech',
  'audio-capture': 'voice.err_mic', network: 'voice.err_network', 'language-not-supported': 'voice.err_lang',
  not_supported: 'voice.err_browser', language_not_supported: 'voice.err_lang',
};
export function voiceErrorText(code) { return t(ERRORS[code] || 'voice.err_generic', { err: code }); }

/**
 * Continuous dictation. Keeps listening across the browser's short pauses (auto-restart) until stop() is called.
 * onText(fullText) receives `base + final + interim` so typed text is never lost.
 */
export function startRecognition(lang, { base = '', onText, onEnd, onError, onState }) {
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) { onError?.('not_supported'); return null; }
  const code = SPEECH_CODES[lang];
  if (!code) { onError?.('language_not_supported'); return null; }
  let finalText = '';
  let stopped = false;
  let rec = null;
  let restarts = 0;
  const joined = (extra) => [base.trim(), (finalText + extra).trim()].filter(Boolean).join(base.trim() ? ' ' : '');
  const begin = () => {
    rec = new Rec();
    rec.lang = code;
    rec.interimResults = true;
    rec.continuous = true;
    rec.maxAlternatives = 1;
    rec.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalText += (finalText && !finalText.endsWith(' ') ? ' ' : '') + r[0].transcript.trim();
        else interim += r[0].transcript;
      }
      restarts = 0;
      onText?.(joined(interim ? ' ' + interim : ''));
    };
    rec.onerror = (e) => {
      if (e.error === 'no-speech' || e.error === 'aborted') return; // pauses are normal; onend restarts
      stopped = true;
      onError?.(e.error || 'error');
    };
    rec.onend = () => {
      if (!stopped && restarts < 20) { restarts += 1; try { begin(); return; } catch { /* fall through */ } }
      onEnd?.(joined(''));
    };
    try { rec.start(); onState?.('listening'); } catch (err) { stopped = true; onError?.(String(err)); }
  };
  begin();
  return { stop() { stopped = true; try { rec?.stop(); } catch { /* */ } } };
}

/** Mic button + "speak in" language selector bound to a textarea. */
export function dictationBar(textarea, { lang = state.lang, onChange } = {}) {
  const status = h('span', { class: 'small', 'aria-live': 'polite' });
  const langSel = h('select', { 'aria-label': t('voice.speak_in'), title: t('voice.speak_in') },
    SPEECH_LANGS.map(([c, n]) => h('option', { value: c, selected: c === (SPEECH_CODES[lang] ? lang : 'en') }, n)));
  const bar = h('div', { class: 'voice-bar' });
  let rec = null;
  const btn = h('button', { type: 'button', class: 'primary' });
  const idle = () => { btn.replaceChildren(icon('mic'), ' ', t('citizen.speak')); bar.classList.remove('listening'); };
  idle();
  btn.addEventListener('click', () => {
    if (rec) { rec.stop(); return; }
    status.textContent = t('citizen.listening');
    btn.replaceChildren(icon('stop'), ' ', t('citizen.stop'));
    bar.classList.add('listening');
    rec = startRecognition(langSel.value, {
      base: textarea.value,
      onText: (txt) => { textarea.value = txt; onChange?.(txt, langSel.value); },
      onEnd: () => { rec = null; idle(); status.textContent = textarea.value ? t('citizen.voice_done') : ''; },
      onError: (e) => { rec = null; idle(); status.textContent = voiceErrorText(e); },
    });
    if (!rec) idle();
  });
  if (!speechSupported()) return h('p', { class: 'notice warn small' }, t('citizen.no_speech'));
  bar.append(btn, h('label', { class: 'small', style: { margin: 0, fontWeight: 600 } }, t('voice.speak_in')), langSel,
    h('span', { class: 'rec-dot', hidden: true }), status);
  return bar;
}

// ---------------------------------------------------------------- text to speech
export function ttsSupported() { return 'speechSynthesis' in window; }

let voicesReady = null;
function voices() {
  if (!ttsSupported()) return Promise.resolve([]);
  if (!voicesReady) {
    voicesReady = new Promise((resolve) => {
      const v = speechSynthesis.getVoices();
      if (v.length) { resolve(v); return; }
      speechSynthesis.addEventListener('voiceschanged', () => resolve(speechSynthesis.getVoices()), { once: true });
      setTimeout(() => resolve(speechSynthesis.getVoices()), 1200);
    });
  }
  return voicesReady;
}

function pickVoice(list, code) {
  const base = code.split('-')[0];
  return list.find(v => v.lang === code && /google|natural|neural/i.test(v.name))
    || list.find(v => v.lang === code)
    || list.find(v => v.lang?.toLowerCase().startsWith(base))
    || null;
}

// Long text is split into sentences so the engine does not cut off (a known Chrome issue with long utterances).
function chunks(text) {
  const parts = String(text).replace(/\s+/g, ' ').match(/[^.!?।\n]+[.!?।]?/g) || [text];
  const out = [];
  for (const p of parts) {
    let s = p.trim();
    while (s.length > 180) { const cut = s.lastIndexOf(' ', 180) > 60 ? s.lastIndexOf(' ', 180) : 180; out.push(s.slice(0, cut)); s = s.slice(cut).trim(); }
    if (s) out.push(s);
  }
  return out;
}

export async function speak(text, lang = state.lang, { onEnd } = {}) {
  if (!ttsSupported() || !text) return false;
  speechSynthesis.cancel();
  const code = SPEECH_CODES[lang] || 'en-IN';
  const list = await voices();
  let voice = pickVoice(list, code);
  let useCode = code;
  if (!voice && lang !== 'en') { voice = pickVoice(list, 'en-IN') || pickVoice(list, 'en-GB'); useCode = voice?.lang || 'en-IN'; }
  const parts = chunks(text);
  parts.forEach((p, i) => {
    const u = new SpeechSynthesisUtterance(p);
    u.lang = useCode;
    if (voice) u.voice = voice;
    u.rate = 0.95; u.pitch = 1;
    if (i === parts.length - 1) u.onend = () => onEnd?.();
    speechSynthesis.speak(u);
  });
  return !!voice || lang === 'en';
}

export function stopSpeaking() { if (ttsSupported()) speechSynthesis.cancel(); }

/** "Read aloud" toggle button for any text (or a function returning text). */
export function readAloudButton(getText, lang) {
  if (!ttsSupported()) return null;
  let on = false;
  const btn = h('button', { type: 'button', class: 'speak-btn', title: t('voice.read_aloud') });
  const idle = () => { on = false; btn.replaceChildren(icon('speaker'), ' ', t('voice.read_aloud')); btn.setAttribute('aria-pressed', 'false'); };
  idle();
  btn.addEventListener('click', async () => {
    if (on) { stopSpeaking(); idle(); return; }
    on = true; btn.replaceChildren(icon('stop'), ' ', t('voice.stop_reading')); btn.setAttribute('aria-pressed', 'true');
    const text = typeof getText === 'function' ? getText() : getText;
    await speak(text, typeof lang === 'function' ? lang() : (lang || state.lang), { onEnd: idle });
  });
  return btn;
}
