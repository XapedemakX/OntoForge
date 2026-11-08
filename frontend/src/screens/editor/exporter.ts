// Export du graphe tel qu'affiché (L26) : SVG autonome (styles en ligne, polices de secours) et PNG dérivé du SVG.
// Le dessin est refait à partir des nœuds et arêtes affichés, avec la géométrie de l'écran (geom.ts) et les couleurs résolues du thème courant.
import type { Edge, Node } from '@xyflow/react'
import { arrow, circ, esc, FONT, line, MONO, path, rect, text, type Pal } from './glyphs'
import { edgeGeom, type Box, type Shape } from './geom'
import { GROUPS, legendEntries, legendWords } from './Legend'
import { LEGEND_H, LEGEND_W, type LegendFlags } from './legendDefs'
import type { Mode } from './prefs'
import type { ClassNodeData } from './parts'
import type { OfEdgeData } from './parts'
import type { VNodeData } from './vowl'

type T = (k: string, p?: Record<string, string | number>) => string
export interface ExportIn { nodes: Node[]; edges: Edge[]; mode: Mode; pal: Pal; t: T; flags: LegendFlags; withLegend: boolean; title: string }

const dims = (n: Node) => ({ w: n.measured?.width ?? n.width ?? 196, h: n.measured?.height ?? n.height ?? 52 })
const trunc = (s: string, max: number) => (s.length > max ? s.slice(0, Math.max(1, max - 1)) + '…' : s)
function wrap(s: string, max: number, lines: number): string[] {
  const words = s.split(/\s+/); const out: string[] = []; let cur = ''
  for (const w of words) {
    if ((cur + ' ' + w).trim().length <= max) cur = (cur + ' ' + w).trim()
    else { if (cur) out.push(cur); cur = w }
  }
  if (cur) out.push(cur)
  if (out.length > lines) { const kept = out.slice(0, lines); kept[lines - 1] = trunc(kept[lines - 1] + '…', max); return kept }
  return out.map(l => (l.length > max + 2 ? trunc(l, max) : l))
}

function classicNode(n: Node, p: Pal, t: T): string {
  const d = n.data as ClassNodeData; const { w, h } = dims(n); const { x, y } = n.position
  const add = d.status === 'add', mod = d.status === 'modify'
  let g = ''
  if (mod || d.error) g += rect(x - 1.5, y - 1.5, w + 3, h + 3, 11, { stroke: d.error ? p.lost : p.mod, sw: 4, op: 0.3 })
  g += rect(x, y, w, h, 10, { fill: add ? p.addSoft : p.panel, stroke: d.error ? p.lost : add ? p.add : mod ? p.mod : p.lineStrong, sw: 1.5, dash: add || d.abstract ? '5 3' : undefined })
  const col = add ? p.add : mod ? p.mod : p.accent
  g += rect(x + 10, y + (h - 30) / 2, 30, 30, 6, { fill: add ? p.panel : p.accentSoft })
  const cx = x + 25, cy = y + h / 2
  g += circ(cx, cy, 4.2, { fill: col }) + circ(cx - 6, cy - 6, 2.4, { fill: col }) + circ(cx + 7, cy + 7, 2.4, { fill: col }) + line(cx - 6, cy - 6, cx, cy, { stroke: col, sw: 1.2 }) + line(cx, cy, cx + 7, cy + 7, { stroke: col, sw: 1.2 })
  const max = Math.floor((w - 62) / 7.4)
  g += text(x + 50, cy - 1, trunc(d.label, max), { size: 14, weight: 600, fill: d.deprecated ? p.muted : p.ink, italic: d.abstract, strike: d.deprecated })
  g += text(x + 50, cy + 13, trunc(d.curie, Math.floor((w - 62) / 6.4)), { size: 10.5, fill: p.muted, mono: true })
  let bx = x + w - 8
  const badge = (s: string, fill: string, stroke: string, ink: string) => { const bw = s.length * 5.6 + 12; bx -= bw; g += rect(bx, y - 9, bw, 15, 7.5, { fill, stroke, sw: 1 }) + text(bx + bw / 2, y + 1.6, s, { size: 9.5, fill: ink, anchor: 'middle' }); bx -= 4 }
  if (d.deprecated) badge(t('ed.deprecated'), p.reviewSoft, p.review, p.review)
  if (d.abstract) badge(t('ed.abstract'), p.panel2, p.lineStrong, p.muted)
  if (d.status) g += circ(x + 17, y - 1, 9, { fill: add ? p.add : p.mod }) + text(x + 17, y + 2.8, add ? '+' : '✎', { size: 11, weight: 700, fill: '#fff', anchor: 'middle' })
  if (d.hid) g += circ(x + w - 4, y + h - 2, 9, { fill: p.accent }) + text(x + w - 4, y + h + 1.4, `+${d.hid}`, { size: 9.5, weight: 700, fill: p.accentInk, anchor: 'middle' })
  return g
}

function vowlNode(n: Node, p: Pal, t: T): string {
  const d = n.data as VNodeData; const { w, h } = dims(n); const { x, y } = n.position; const cx = x + w / 2, cy = y + h / 2
  const add = d.status === 'add', mod = d.status === 'modify'
  const stroke = d.error ? p.lost : add ? p.add : mod ? p.mod : p.vwLine
  let g = ''
  if (d.vk === 'datatype') {
    g += rect(x, y, w, h, 2, { fill: p.vwDt, stroke: p.vwLine, sw: 1.2, dash: d.label === 'Literal' ? '4 3' : undefined }) + text(cx, cy + 4.3, trunc(d.label, Math.floor(w / 6.6)), { size: 12, weight: 500, fill: p.vwInk, anchor: 'middle' })
    return g
  }
  const r = w / 2
  if (mod || d.error) g += circ(cx, cy, r + 3, { stroke: d.error ? p.lost : p.mod, sw: 4, op: 0.3 })
  const fill = add ? p.addSoft : d.vk === 'thing' ? p.vwThing : d.deprecated ? p.vwDep : d.external ? p.vwExt : p.vwClass
  const ink = d.external && !d.deprecated && !add ? p.vwExtInk : p.vwInk
  if (d.merged.length) g += circ(cx, cy, r, { fill: p.vwThing, stroke, sw: 1.5 }) + circ(cx, cy, r - 4, { fill, stroke, sw: 1.5 })
  else g += circ(cx, cy, r, { fill, stroke, sw: 1.5, dash: d.vk === 'thing' || d.vk === 'anon' || add ? '4 3' : undefined })
  if (d.abstract) g += circ(cx, cy, r - 7, { stroke: p.vwLine, sw: 1, dash: '3 2' })
  if (d.vk === 'anon') return g + text(cx, cy + 7, { and: '∩', or: '∪', not: '¬' }[d.op ?? 'or'], { size: 22, weight: 600, fill: ink, anchor: 'middle' })
  if (d.vk === 'thing') return g + text(cx, cy + 4, 'Thing', { size: 11, fill: ink, anchor: 'middle' })
  const sub = d.merged.length ? `[${d.merged.join(', ')}]` : [d.deprecated && t('ed.deprecated').toLowerCase(), d.external && t('lg.w.extb')].filter(Boolean).length ? `[${[d.deprecated && t('ed.deprecated').toLowerCase(), d.external && t('lg.w.extb')].filter(Boolean).join(', ')}]` : ''
  const lines = wrap(d.label, Math.max(6, Math.floor((w - 20) / 6.9)), 3)
  const total = lines.length + (sub ? 0.8 : 0)
  let ty = cy - ((total - 1) * 15) / 2 + 4
  for (const l of lines) { g += text(cx, ty, l, { size: 12, weight: 600, fill: ink, anchor: 'middle', italic: d.abstract }); ty += 15 }
  if (sub) g += text(cx, ty - 1, trunc(sub, Math.floor((w - 16) / 5.2)), { size: 9, fill: ink, anchor: 'middle' })
  if (d.status) g += circ(cx - r * 0.7, cy - r * 0.7, 9, { fill: add ? p.add : p.mod }) + text(cx - r * 0.7, cy - r * 0.7 + 4, add ? '+' : '✎', { size: 11, weight: 700, fill: '#fff', anchor: 'middle' })
  if (d.hid) g += circ(cx + r * 0.72, cy - r * 0.72, 9, { fill: p.accent }) + text(cx + r * 0.72, cy - r * 0.72 + 3.4, `+${d.hid}`, { size: 9.5, weight: 700, fill: p.accentInk, anchor: 'middle' })
  return g
}

function pill(cx: number, cy: number, s: string, o: { fill: string; stroke?: string; ink: string; r: number; sub?: string; size?: number }): string {
  const size = o.size ?? 11.5; const w = Math.max(s.length, (o.sub ?? '').length * 0.82) * size * 0.56 + 14; const h = o.sub ? 28 : 19
  return rect(cx - w / 2, cy - h / 2, w, h, o.r, { fill: o.fill, stroke: o.stroke, sw: 1 }) +
    text(cx, cy + (o.sub ? -2.2 : 4), s, { size, weight: 500, fill: o.ink, anchor: 'middle' }) + (o.sub ? text(cx, cy + 9.5, o.sub, { size: 9, fill: o.ink, anchor: 'middle' }) : '')
}

function edgeSvg(e: Edge, nodes: Map<string, Node>, mode: Mode, p: Pal, t: T): string {
  const d = e.data as OfEdgeData; const s = nodes.get(e.source), tg = nodes.get(e.target); if (!s || !tg) return ''
  const box = (n: Node): Box => { const { w, h } = dims(n); return { cx: n.position.x + w / 2, cy: n.position.y + h / 2, w, h, shape: ((n.data as { shape?: Shape }).shape) ?? 'rect' } }
  const g = edgeGeom(box(s), box(tg), d.offset, e.source === e.target)
  const vowl = mode === 'vowl'; const add = d.status === 'add', mod = d.status === 'modify'
  const k = d.kind
  let stroke = vowl ? p.vwLine : k === 'subClassOf' ? p.accent : k === 'objectProperty' ? p.info : k === 'disjointWith' ? p.lost : k === 'equivalentClass' ? p.accent : p.muted
  let sw = vowl ? (k === 'subClassOf' ? 1.8 : 1.5) : k === 'subClassOf' ? 1.8 : k === 'disjointWith' ? 2 : 1.5
  let dash: string | undefined = vowl ? (k === 'subClassOf' ? '1 5' : k === 'disjointWith' || k === 'equivalentClass' || k === 'anonymousOf' ? '5 3' : undefined)
    : k === 'disjointWith' ? '2 5' : k === 'equivalentClass' ? '9 3 2 3' : undefined
  if (add) { stroke = p.add; dash = '6 4' } else if (mod) { stroke = p.mod; sw = 2.6 } else if (d.err) { stroke = p.lost; sw = 3 }
  let o = `<path d="${g.path}" style="fill:none;stroke:${stroke};stroke-width:${sw};${dash ? `stroke-dasharray:${dash};` : ''}${k === 'disjointWith' || (vowl && k === 'subClassOf') ? 'stroke-linecap:round;' : ''}"/>`
  const head = (kind: 'hollow' | 'solid', at: 'end' | 'start') => {
    const pt = at === 'end' ? g.b : g.a; const ang = at === 'end' ? g.endAngle : g.startAngle
    return arrow(pt.x, pt.y, ang, kind, vowl ? p.vwThing : p.panel, add ? p.add : mod ? p.mod : stroke, kind === 'hollow' ? 12 : 10)
  }
  if (k === 'subClassOf') o += head('hollow', 'end')
  else if (k === 'objectProperty' || k === 'datatypeProperty') { o += head('solid', 'end'); if (d.inverse) o += head('solid', 'start') }
  const { lx, ly } = g
  if (vowl) {
    if (k === 'objectProperty' || k === 'datatypeProperty') {
      const chars = (d.chars ?? []).map(c => t('ed.char.' + c).toLowerCase()); if (d.deprecated) chars.push(t('ed.deprecated').toLowerCase())
      const fill = add ? p.addSoft : d.deprecated ? p.vwDep : k === 'datatypeProperty' ? p.vwDp : p.vwClass
      o += pill(lx, ly, d.label + (d.inverse ? ` ⇄ ${d.inverse}` : ''), { fill, ink: p.vwInk, r: 2, sub: chars.length ? `[${chars.join(', ')}]` : undefined })
    } else if (k === 'subClassOf') o += pill(lx, ly, t('lg.w.subOf'), { fill: p.vwThing, stroke: p.vwLine, ink: p.vwInk, r: 2, size: 10 })
    else if (k === 'disjointWith') o += rect(lx - 18, ly - 12, 36, 24, 2, { fill: p.vwClass }) + circ(lx - 6, ly - 3, 5, { fill: p.vwGfx }) + circ(lx + 5, ly - 3, 5, { fill: p.vwGfx }) + text(lx, ly + 9, `[${t('lg.w.disj')}]`, { size: 7.5, fill: p.vwInk, anchor: 'middle' })
  } else if (k === 'objectProperty') o += pill(lx, ly, d.label + (d.inverse ? ` ⇄ ${d.inverse}` : ''), { fill: add ? p.addSoft : p.panel, stroke: add ? p.add : p.lineStrong, ink: add ? p.add : p.info, r: 9.5 })
  else if (k === 'disjointWith') o += circ(lx, ly, 9, { fill: p.lostSoft, stroke: p.lost, sw: 1 }) + text(lx, ly + 4.4, '⟂', { size: 12, weight: 700, fill: p.lost, anchor: 'middle' })
  else if (k === 'equivalentClass') o += pill(lx, ly, '≡', { fill: p.panel, stroke: p.lineStrong, ink: p.accent, r: 9.5 })
  return o
}

function legendBlock(i: ExportIn, W: number): { svg: string; h: number } {
  const entries = legendEntries(i.mode, i.flags); const words = legendWords(i.t); const p = i.pal
  const colW = 330; const cols = Math.max(1, Math.floor((W - 40) / colW)); let y = 34
  let g = text(20, y, i.t('lg.title') + ' — ' + i.t(i.mode === 'vowl' ? 'lg.mode.vowl' : 'lg.mode.classic'), { size: 15, weight: 700, fill: p.ink })
  y += 14
  for (const grp of GROUPS) {
    const es = entries.filter(e => e.group === grp); if (!es.length) continue
    y += 22; g += text(20, y, i.t('lg.g.' + grp).toUpperCase(), { size: 10.5, weight: 700, fill: p.muted }); y += 8
    es.forEach((e, k) => {
      const cx = 20 + (k % cols) * colW, cy = y + Math.floor(k / cols) * 56
      g += `<g transform="translate(${cx} ${cy})">${e.draw(p, words)}</g>`
      g += text(cx + LEGEND_W + 12, cy + 12, i.t(`lg.${e.id}.t`), { size: 12, weight: 600, fill: p.ink })
      wrap(i.t(`lg.${e.id}.d`), 42, 3).forEach((l, j) => { g += text(cx + LEGEND_W + 12, cy + 26 + j * 12.5, l, { size: 10.5, fill: p.muted }) })
    })
    y += Math.ceil(es.length / cols) * 56
  }
  void LEGEND_H
  return { svg: g, h: y + 14 }
}

export function buildSvg(i: ExportIn): { svg: string; w: number; h: number } {
  const p = i.pal; const map = new Map(i.nodes.map(n => [n.id, n]))
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const n of i.nodes) { const { w, h } = dims(n); minX = Math.min(minX, n.position.x); minY = Math.min(minY, n.position.y); maxX = Math.max(maxX, n.position.x + w); maxY = Math.max(maxY, n.position.y + h) }
  if (!isFinite(minX)) { minX = minY = 0; maxX = maxY = 200 }
  const body = i.edges.map(e => edgeSvg(e, map, i.mode, p, i.t)).join('') + i.nodes.map(n => (i.mode === 'vowl' ? vowlNode(n, p, i.t) : classicNode(n, p, i.t))).join('')
  // les libellés d'arêtes peuvent déborder des nœuds : marge généreuse
  const PAD = 48; const gx = minX - PAD, gy = minY - PAD, gw = maxX - minX + PAD * 2, gh = maxY - minY + PAD * 2
  const W = Math.max(gw, i.withLegend ? 720 : 0)
  const lg = i.withLegend ? legendBlock(i, W) : null
  const H = gh + (lg ? lg.h : 0)
  const svg = `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${Math.round(W)}" height="${Math.round(H)}" viewBox="0 0 ${Math.round(W)} ${Math.round(H)}" font-family="${FONT}">\n` +
    `<title>${esc(i.title)}</title><desc>OntoForge — ${esc(i.t(i.mode === 'vowl' ? 'lg.mode.vowl' : 'lg.mode.classic'))}</desc>\n` +
    `<rect width="100%" height="100%" style="fill:${p.bg}"/>\n<g transform="translate(${-gx + (W - gw) / 2} ${-gy})">${body}</g>\n` +
    (lg ? `<g transform="translate(0 ${gh})"><line x1="20" y1="0" x2="${W - 20}" y2="0" style="stroke:${p.line};stroke-width:1"/>${lg.svg}</g>\n` : '') + `</svg>\n`
  void MONO; void path
  return { svg, w: W, h: H }
}

export async function svgToPng(svg: string, w: number, h: number): Promise<Blob> {
  const scale = Math.min(2, 8000 / Math.max(w, h))
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }))
  try {
    const img = new Image(); img.decoding = 'async'
    await new Promise<void>((ok, ko) => { img.onload = () => ok(); img.onerror = () => ko(new Error('PNG')); img.src = url })
    const c = document.createElement('canvas'); c.width = Math.round(w * scale); c.height = Math.round(h * scale)
    const ctx = c.getContext('2d')!; ctx.scale(scale, scale); ctx.drawImage(img, 0, 0, w, h)
    return await new Promise<Blob>((ok, ko) => c.toBlob(b => (b ? ok(b) : ko(new Error('PNG'))), 'image/png'))
  } finally { URL.revokeObjectURL(url) }
}
export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const a = document.createElement('a')
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
