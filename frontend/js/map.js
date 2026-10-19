// Leaflet map helpers (Leaflet 1.9.4 is bundled locally under /static/vendor/leaflet - no CDN).
import { api, h, state, t } from './core.js';

let leafletPromise = null;
const configCache = {};

export function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (!leafletPromise) {
    leafletPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = '/static/vendor/leaflet/leaflet.js';
      s.onload = () => resolve(window.L);
      s.onerror = () => reject(new Error('Map library failed to load'));
      document.head.append(s);
    });
  }
  return leafletPromise;
}

export async function mapConfig() {
  const key = state.tenant || 'default';
  if (!configCache[key]) configCache[key] = await api('/api/map/config');
  return configCache[key];
}

export const PRIORITY_COLORS = { Emergency: '#c62828', High: '#ef6c00', Medium: '#1565c0', Low: '#607d8b' };
export const priorityColor = (p) => PRIORITY_COLORS[p] || '#94a3b8';

// Basemap with automatic fallback: primary provider (light or dark variant) -> secondary provider -> notice.
function addBasemap(L, map, el, cfg) {
  const dark = document.documentElement.dataset.theme === 'dark';
  const providers = [dark && cfg.tile_url_dark ? cfg.tile_url_dark : cfg.tile_url, cfg.fallback_tile_url].filter(Boolean);
  let idx = 0, layer = null, failed = 0, loaded = 0;
  const use = (i) => {
    if (layer) map.removeLayer(layer);
    failed = 0; loaded = 0;
    const url = providers[i];
    const needsInvert = dark && url !== cfg.tile_url_dark;
    el.classList.toggle('tiles-invert', needsInvert);
    layer = L.tileLayer(url, { maxZoom: 19, subdomains: 'abcd', attribution: cfg.attribution, crossOrigin: false });
    layer.on('tileload', () => { loaded += 1; });
    layer.on('tileerror', () => {
      failed += 1;
      if (failed >= 4 && loaded === 0) {
        if (idx + 1 < providers.length) { idx += 1; use(idx); }
        else if (!el.querySelector('.map-offline')) el.append(h('div', { class: 'map-offline chip warn' }, t('map.tiles_offline')));
      }
    });
    layer.addTo(map);
  };
  use(0);
  const onTheme = () => { if (!document.body.contains(el)) { document.removeEventListener('themechange', onTheme); return; } addBasemapSwap(); };
  const addBasemapSwap = () => {
    const nowDark = document.documentElement.dataset.theme === 'dark';
    providers[0] = nowDark && cfg.tile_url_dark ? cfg.tile_url_dark : cfg.tile_url;
    idx = 0; use(0);
  };
  document.addEventListener('themechange', onTheme);
}

export async function createMap(el, { center, zoom, wards = false } = {}) {
  const [L, cfg] = await Promise.all([loadLeaflet(), mapConfig()]);
  const c = center || cfg.center;
  const map = L.map(el, { zoomControl: true, attributionControl: true }).setView([c.lat, c.lng], zoom || c.zoom || 12);
  addBasemap(L, map, el, cfg);
  if (wards) {
    for (const w of cfg.wards) {
      L.polygon(w.polygon, { color: '#0b3d91', weight: 1.2, fillOpacity: 0.04, dashArray: '4 4' })
        .bindTooltip(w.name, { sticky: true }).addTo(map);
    }
  }
  // Leaflet needs a size recalculation when its container becomes visible after layout.
  map.attributionControl.setPrefix('Leaflet');
  setTimeout(() => map.invalidateSize(), 150);
  return { L, map, cfg };
}

export function complaintMarker(L, m) {
  const marker = L.circleMarker([m.lat, m.lng], {
    radius: m.priority === 'Emergency' ? 11 : m.priority === 'High' ? 9 : 8,
    color: '#ffffff', weight: 2, fillColor: priorityColor(m.priority), fillOpacity: m.status === 'closed' || m.status === 'resolved' ? 0.45 : 0.95,
  });
  return marker;
}

export function emergencyRing(L, m) {
  return L.marker([m.lat, m.lng], { interactive: false, keyboard: false,
    icon: L.divIcon({ className: '', html: h('div', { class: 'emg-ring' }), iconSize: [26, 26], iconAnchor: [13, 13] }) });
}

export function teamMarker(L, p) {
  const label = (p.name || '?').replace(/\(.*?\)/g, '').trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  return L.marker([p.lat, p.lng], {
    zIndexOffset: 1000, title: p.name,
    icon: L.divIcon({ className: '', html: h('div', { class: `team-pin${p.me ? ' me' : ''}` }, label), iconSize: [34, 34], iconAnchor: [17, 17] }),
  });
}

export function pickPin(L, lat, lng) {
  return L.marker([lat, lng], { draggable: true, autoPan: true,
    icon: L.divIcon({ className: '', html: h('div', { class: 'pick-pin' }), iconSize: [22, 22], iconAnchor: [11, 22] }) });
}

export function popupContent(m, actions = []) {
  return h('div', {},
    h('div', { class: 'mono', style: { fontWeight: '700' } }, m.id),
    h('div', {}, m.category || ''),
    h('div', { class: 'small muted' }, [m.department, m.location].filter(Boolean).join(' · ')),
    h('div', { class: 'row', style: { marginTop: '6px' } },
      h('span', { class: 'chip' }, t(`status.${m.status}`)), m.priority ? h('span', { class: 'chip' }, t(`priority.${m.priority}`)) : null,
      m.sla === 'breached' ? h('span', { class: 'chip bad' }, t('sla.breached')) : null),
    actions.length ? h('div', { class: 'row', style: { marginTop: '8px' } }, actions) : null);
}
