// Small dependency-free SVG charts. Every chart gets a text alternative.
import { h, svg } from './core.js';

export function barChart(entries, { title = '', max = 10, height = 22, alt = false, unit = '' } = {}) {
  const items = entries.slice(0, max);
  if (!items.length) return h('div', { class: 'empty small' }, 'No data');
  const top = Math.max(...items.map(([, v]) => v), 1);
  const labelW = 170, w = 520, rowH = height + 8;
  const svgEl = svg('svg', { viewBox: `0 0 ${w} ${items.length * rowH + 4}`, role: 'img', 'aria-label': title },
    items.map(([label, v], i) => {
      const bw = Math.max(2, ((w - labelW - 50) * v) / top);
      const y = i * rowH + 2;
      return svg('g', {},
        svg('text', { x: 0, y: y + height * 0.7 }, String(label).length > 26 ? String(label).slice(0, 25) + '…' : String(label)),
        svg('rect', { x: labelW, y, width: bw, height, rx: 3, class: alt ? 'bar alt' : 'bar' }),
        svg('text', { x: labelW + bw + 6, y: y + height * 0.7 }, `${v}${unit}`));
    }));
  return h('figure', { class: 'chart', style: { margin: 0 } }, svgEl,
    h('figcaption', { class: 'sr-only' }, `${title}: ${items.map(([l, v]) => `${l} ${v}${unit}`).join(', ')}`));
}

export function lineChart(points, { title = '', yLabel = '', badKey = null, height = 160 } = {}) {
  // points: [{x: label, y: number|null, bad?: bool}]
  if (!points.length) return h('div', { class: 'empty small' }, 'No data');
  const w = 560, pad = 30;
  const ys = points.map(p => p.y).filter(v => v !== null && v !== undefined);
  const maxY = Math.max(...ys, 1);
  const step = (w - pad * 2) / Math.max(points.length - 1, 1);
  const xy = (i, y) => [pad + i * step, height - pad - ((height - pad * 2) * y) / maxY];
  let d = '';
  points.forEach((p, i) => {
    if (p.y === null || p.y === undefined) return;
    const [x, y] = xy(i, p.y);
    d += `${d && points[i - 1]?.y !== null && points[i - 1]?.y !== undefined ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)} `;
  });
  const bad = points.map((p, i) => (p.bad ? svg('circle', { cx: xy(i, 0)[0], cy: height - pad, r: 3, class: 'dot-bad' }) : null));
  const labels = [0, Math.floor(points.length / 2), points.length - 1].map(i => svg('text', { x: xy(i, 0)[0] - 20, y: height - 8 }, points[i].x));
  return h('figure', { class: 'chart', style: { margin: 0 } },
    svg('svg', { viewBox: `0 0 ${w} ${height}`, role: 'img', 'aria-label': title },
      svg('line', { x1: pad, y1: height - pad, x2: w - pad, y2: height - pad, class: 'axis' }),
      svg('text', { x: 2, y: 12 }, `${yLabel} max ${Math.round(maxY)}`),
      svg('path', { d, class: 'line' }), bad, labels),
    h('figcaption', { class: 'sr-only' }, `${title}. ${points.length} points, maximum ${Math.round(maxY)}${badKey ? ', red dots mark failures' : ''}.`));
}

const PALETTE = ['#0b3d91', '#e8851a', '#138808', '#c62828', '#6a4c93', '#00838f', '#8d6e63', '#546e7a', '#f9a825', '#ad1457'];

export function donutChart(entries, { title = '' } = {}) {
  const items = entries.filter(([, v]) => v > 0);
  if (!items.length) return h('div', { class: 'empty small' }, 'No data');
  const total = items.reduce((s, [, v]) => s + v, 0);
  const r = 60, c = 2 * Math.PI * r;
  let off = 0;
  const arcs = items.map(([, v], i) => {
    const len = (v / total) * c;
    const el = svg('circle', { cx: 85, cy: 85, r, fill: 'none', stroke: PALETTE[i % PALETTE.length], 'stroke-width': 26,
      'stroke-dasharray': `${len} ${c - len}`, 'stroke-dashoffset': -off, transform: 'rotate(-90 85 85)' });
    off += len;
    return el;
  });
  return h('figure', { class: 'chart donut-wrap', style: { margin: 0 } },
    svg('svg', { viewBox: '0 0 170 170', role: 'img', 'aria-label': title }, arcs,
      svg('text', { x: 85, y: 82, 'text-anchor': 'middle', class: 'donut-total' }, String(total)),
      svg('text', { x: 85, y: 102, 'text-anchor': 'middle' }, 'total')),
    h('ul', { class: 'legend-list' }, items.map(([l, v], i) => {
      const sw = h('i'); sw.style.background = PALETTE[i % PALETTE.length];
      return h('li', {}, sw, h('span', {}, l), h('b', {}, `${v} (${Math.round(100 * v / total)}%)`));
    })),
    h('figcaption', { class: 'sr-only' }, `${title}: ${items.map(([l, v]) => `${l} ${v}`).join(', ')}`));
}

export function multiLineChart(labels, series, { title = '', height = 200 } = {}) {
  if (!labels.length) return h('div', { class: 'empty small' }, 'No data');
  const w = 560, padL = 30, padB = 26, padT = 10;
  const maxY = Math.max(1, ...series.flatMap(s => s.values));
  const step = (w - padL - 10) / Math.max(labels.length - 1, 1);
  const x = (i) => padL + i * step;
  const y = (v) => height - padB - ((height - padB - padT) * v) / maxY;
  const grid = [0, 0.5, 1].map(f => [svg('line', { x1: padL, x2: w - 10, y1: y(maxY * f), y2: y(maxY * f), class: 'grid-line' }),
    svg('text', { x: 2, y: y(maxY * f) + 4 }, String(Math.round(maxY * f)))]);
  const paths = series.map((s, si) => svg('path', { class: `line2 s${si}`,
    d: s.values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ') }));
  const every = Math.ceil(labels.length / 7);
  const xl = labels.map((l, i) => (i % every === 0 || i === labels.length - 1) ? svg('text', { x: x(i) - 16, y: height - 6 }, l) : null);
  const legend = h('div', { class: 'legend' }, series.map((s, si) => {
    const sw = h('span', { class: 'dot' }); sw.style.background = si ? 'var(--green)' : 'var(--brand)';
    return h('span', {}, sw, s.name);
  }));
  return h('figure', { class: 'chart', style: { margin: 0 } }, legend,
    svg('svg', { viewBox: `0 0 ${w} ${height}`, role: 'img', 'aria-label': title }, grid, paths, xl),
    h('figcaption', { class: 'sr-only' }, `${title}. ${series.map(s => `${s.name}: ${s.values.reduce((a, b) => a + b, 0)} in total`).join('; ')}.`));
}
