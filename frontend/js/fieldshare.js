// Opt-in live location sharing for field staff. Keeps running while the user moves between pages
// and stops on sign-out / account switch. Positions are sent at most every 10 s.
import { api, state, toast } from './core.js';

const listeners = new Set();
export const share = { mode: 'off', watchId: null, last: null, lastSent: 0, error: null, userId: null };

function emit() { listeners.forEach(fn => { try { fn(share); } catch { /* */ } }); }
export function onShareChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }

async function send(lat, lng, accuracy, note, force = false) {
  const now = Date.now();
  share.last = { lat, lng, accuracy };
  if (!force && now - share.lastSent < 10000) { emit(); return; }
  share.lastSent = now;
  try {
    await api('/api/field/location', { method: 'PUT', body: { lat, lng, accuracy_m: accuracy ?? null, status_note: note } });
    share.error = null;
  } catch (e) { share.error = e.message; }
  emit();
}

export function startGps() {
  stop(false);
  if (!navigator.geolocation) { share.error = 'Location is not available in this browser.'; emit(); return; }
  share.mode = 'gps'; share.userId = state.user?.id; share.error = null;
  share.watchId = navigator.geolocation.watchPosition(
    (p) => send(p.coords.latitude, p.coords.longitude, p.coords.accuracy, 'live GPS'),
    (err) => { share.error = err.code === 1 ? 'Location permission denied.' : 'Could not get your location.'; emit(); },
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
  emit();
}

export function setManual(lat, lng) {
  if (share.watchId !== null) { navigator.geolocation.clearWatch(share.watchId); share.watchId = null; }
  share.mode = 'manual'; share.userId = state.user?.id;
  send(lat, lng, null, 'position set on map', true);
}

export async function stop(notifyServer = true) {
  if (share.watchId !== null) { navigator.geolocation.clearWatch(share.watchId); share.watchId = null; }
  const was = share.mode;
  share.mode = 'off'; share.last = null;
  if (notifyServer && was !== 'off') {
    try { await api('/api/field/location', { method: 'DELETE' }); } catch { /* */ }
    toast('Live location sharing stopped');
  }
  emit();
}

// Stop when the signed-in account changes.
document.addEventListener('session', () => { if (share.mode !== 'off' && share.userId !== state.user?.id) stop(false); });
