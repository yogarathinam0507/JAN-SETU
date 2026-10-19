// Live operations map for staff: complaint pins (auto-refresh), field team positions, ward boundaries,
// and opt-in live location sharing for field users.
import { api, errorBox, fmtDate, h, mount, navigate, select, state, t, toast } from '../core.js';
import { pageCleanup, tenantConfig, nameOf } from '../app.js';
import { complaintMarker, createMap, emergencyRing, popupContent, teamMarker } from '../map.js';
import { onShareChange, setManual, share, startGps, stop } from '../fieldshare.js';
import { icon } from '../icons.js';

const opts = { status: 'open', category: '', team: true, auto: true };
const REFRESH_MS = 10000;

export async function render(app) {
  const cfg = await tenantConfig();
  const mapEl = h('div', { class: 'map tall', id: 'live-map', role: 'region', 'aria-label': t('map.title') });
  const list = h('div', { class: 'map-list' });
  const kpis = h('div', { class: 'grid g4' });
  const liveTxt = h('span', { class: 'small muted' });
  const liveDot = h('span', { class: 'live-dot' });
  const statusSel = select([{ value: 'open', label: t('map.open') }, { value: 'all', label: t('map.all') }, { value: 'closed', label: t('map.closed') }], opts.status);
  const catSel = select([{ value: '', label: t('an.all_categories') }, ...cfg.categories.map(c => ({ value: c.code, label: nameOf(c.names) }))], opts.category);
  const teamChk = h('input', { type: 'checkbox', checked: opts.team });
  const autoChk = h('input', { type: 'checkbox', checked: opts.auto });
  const shareBox = h('div', { class: 'card' });
  const canShare = ['officer', 'nodal', 'vendor'].includes(state.user.role);
  mount(app,
    h('div', { class: 'spread' }, h('h1', {}, t('map.title')), h('div', { class: 'row' }, liveDot, liveTxt)),
    h('p', { class: 'muted' }, t('map.subtitle')),
    kpis,
    h('div', { class: 'card row', style: { margin: '12px 0' } },
      h('label', { class: 'sr-only' }, t('tickets.status')), statusSel, catSel,
      h('label', { class: 'check', style: { margin: 0 } }, teamChk, t('map.show_team')),
      h('label', { class: 'check', style: { margin: 0 } }, autoChk, t('map.auto')),
      h('button', { onclick: () => refresh(true) }, icon('refresh'), t('common.refresh')),
      h('button', { onclick: () => fitAll() }, icon('crosshair'), t('map.fit')),
      h('div', { class: 'legend', style: { marginLeft: 'auto' } },
        ['Emergency', 'High', 'Medium', 'Low'].map(p => h('span', {}, h('span', { class: `dot p-${p}` }), t(`priority.${p}`))),
        h('span', {}, h('span', { class: 'dot team' }), t('map.team')))),
    h('div', { class: 'map-layout' }, mapEl, h('div', { class: 'stack' }, canShare ? shareBox : null, h('div', { class: 'card' },
      h('h3', {}, t('map.list')), list))));

  let ctx;
  try { ctx = await createMap(mapEl, { wards: true }); } catch (e) { mount(mapEl, errorBox(e)); return; }
  const { L, map } = ctx;
  const complaintLayer = L.layerGroup().addTo(map);
  const teamLayer = L.layerGroup().addTo(map);
  const markersById = {};
  let data = null;
  let firstFit = true;
  let pickMode = false;

  function fitAll() {
    const pts = [...(data?.markers || []).map(m => [m.lat, m.lng]), ...(opts.team ? (data?.team || []).map(p => [p.lat, p.lng]) : [])];
    if (pts.length) map.fitBounds(pts, { padding: [40, 40], maxZoom: 15 });
  }

  function draw() {
    complaintLayer.clearLayers(); teamLayer.clearLayers();
    for (const m of data.markers) {
      if (m.priority === 'Emergency' && m.status !== 'closed') emergencyRing(L, m).addTo(complaintLayer);
      const mk = complaintMarker(L, m).addTo(complaintLayer);
      const acts = ['officer', 'nodal'].includes(state.user.role)
        ? [h('button', { class: 'primary', onclick: () => navigate(`/officer?ticket=${encodeURIComponent(m.id)}`) }, t('map.open_ticket'))] : [];
      mk.bindPopup(popupContent(m, acts));
      mk.bindTooltip(`${m.id} · ${m.category}`);
      markersById[m.id] = mk;
    }
    if (opts.team) {
      for (const p of data.team) {
        teamMarker(L, p).addTo(teamLayer).bindPopup(h('div', {}, h('strong', {}, p.name), h('div', { class: 'small' }, [p.role, p.department].filter(Boolean).join(' · ')),
          h('div', { class: 'small muted' }, `${t('map.updated')} ${Math.round(p.age_seconds / 60)} min · ${p.note || ''}${p.accuracy_m ? ` · ±${Math.round(p.accuracy_m)} m` : ''}`)));
      }
    }
    const tile = (v, l, cls) => h('div', { class: `card kpi ${cls || ''}` }, h('div', { class: 'v' }, String(v)), h('div', { class: 'l' }, l));
    mount(kpis, tile(data.markers.length, t('map.k_pins')), tile(data.markers.filter(m => m.priority === 'Emergency').length, t('map.k_emergency')),
      tile(data.markers.filter(m => m.sla === 'breached').length, t('map.k_overdue')), tile(data.team.length, t('map.k_team')));
    mount(list, data.markers.length ? data.markers.slice(0, 200).map(m => h('button', { class: 'map-item', onclick: () => {
      map.flyTo([m.lat, m.lng], 16); setTimeout(() => markersById[m.id]?.openPopup(), 400);
    } }, h('div', { class: 'spread' }, h('span', {}, h('span', { class: `dot p-${m.priority || 'none'}` }), h('strong', { class: 'mono' }, m.id)),
      h('span', { class: m.sla === 'breached' ? 'chip bad' : 'chip' }, t(`status.${m.status}`))),
    h('div', { class: 'small' }, m.category), h('div', { class: 'small muted' }, [m.location, fmtDate(m.created_at)].filter(Boolean).join(' · ')))) :
      h('p', { class: 'muted' }, t('map.none')),
    data.unlocated_open ? h('p', { class: 'small muted' }, t('map.unlocated', { n: data.unlocated_open })) : null,
    h('p', { class: 'hint' }, data.note));
    if (firstFit) { fitAll(); firstFit = false; }
  }

  async function refresh(manual = false) {
    try {
      data = await api('/api/map/live', { query: { status: opts.status, category: opts.category } });
      draw();
      liveDot.className = opts.auto ? 'live-dot' : 'live-dot off';
      liveTxt.textContent = `${opts.auto ? t('map.live') : t('map.paused')} · ${t('map.updated')} ${new Date(data.generated_at).toLocaleTimeString()}`;
      if (manual) toast(t('map.refreshed'));
    } catch (e) { liveDot.className = 'live-dot off'; liveTxt.textContent = e.message; }
  }

  statusSel.addEventListener('change', () => { opts.status = statusSel.value; firstFit = true; refresh(); });
  catSel.addEventListener('change', () => { opts.category = catSel.value; firstFit = true; refresh(); });
  teamChk.addEventListener('change', () => { opts.team = teamChk.checked; draw(); });
  autoChk.addEventListener('change', () => { opts.auto = autoChk.checked; refresh(); });

  // ---- live location sharing (field staff)
  function drawShare() {
    if (!canShare) return;
    const on = share.mode !== 'off';
    mount(shareBox, h('h3', {}, icon('broadcast'), ' ', t('map.share_h')),
      h('p', { class: 'small muted' }, t('map.share_text')),
      on ? h('div', { class: 'tracker' }, h('span', { class: 'live-dot' }),
        share.mode === 'gps' ? t('map.sharing_gps') : t('map.sharing_manual'),
        share.last ? h('span', { class: 'small' }, ` ${share.last.lat.toFixed(5)}, ${share.last.lng.toFixed(5)}`) : null) : null,
      share.error ? h('div', { class: 'notice bad small' }, share.error) : null,
      pickMode ? h('div', { class: 'notice small' }, t('map.click_to_set')) : null,
      h('div', { class: 'row' },
        h('button', { class: share.mode === 'gps' ? 'on' : 'primary', onclick: () => { pickMode = false; startGps(); } }, icon('crosshair'), t('map.share_gps')),
        h('button', { class: share.mode === 'manual' ? 'on' : '', onclick: () => { pickMode = true; drawShare(); } }, icon('pin'), t('map.share_manual')),
        on ? h('button', { class: 'danger', onclick: () => { pickMode = false; stop(); } }, t('map.stop')) : null),
      h('p', { class: 'hint' }, t('map.share_privacy')));
  }
  map.on('click', (e) => { if (pickMode) { pickMode = false; setManual(e.latlng.lat, e.latlng.lng); setTimeout(refresh, 600); } });
  const unsub = onShareChange(() => { drawShare(); });
  drawShare();

  await refresh();
  const timer = setInterval(() => { if (opts.auto && !document.hidden) refresh(); }, REFRESH_MS);
  const onTheme = () => map.invalidateSize();
  document.addEventListener('themechange', onTheme);
  pageCleanup.fn = () => { clearInterval(timer); unsub(); document.removeEventListener('themechange', onTheme); map.remove(); };
}
