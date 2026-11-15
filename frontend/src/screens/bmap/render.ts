// Dessin SVG de la carte métier (chaîne de caractères, sans dépendance au DOM) : même code pour l'écran et pour l'export.
// Technique : zones teintées à bordure pointillée, nœuds en cercles, arêtes en courbes quadratiques rognées aux cercles,
// libellés posés le long de la courbe au premier endroit libre, cadres pointillés, légende et notes en colonne de droite.
import { esc, FONT } from '../editor/glyphs'
import { drawnStyle, type BEdge, type BMap, type BScenario, type DrawnStyle } from './types'
import { palette, roleInk, roleOrder, zoneTint, type Pal } from './palette'
import { circleHitsObb, dist, noteLines, obb, obbOverlap, quad, readable, shortCount, splitCaption, textWidth, type Pt } from './geometry'

type T = (k: string, p?: Record<string, string | number>) => string
export interface RenderOpts {
  map: BMap; scenario: BScenario | null; pal: Pal; t: T; lang: string
  withLegend: boolean
  /** Ajoute les attributs data-* et les zones de capture utilisés par l'écran (survol, clic, glisser). Absent à l'export. */
  interactive: boolean
}
export interface Parts { w: number; h: number; inner: string; origin: Pt; u: number }

const f1 = (n: number) => (Math.round(n * 10) / 10).toString()
const RANK: Record<DrawnStyle, number> = { mention: 0, disabled: 0, subclass: 0, plain: 1, context_off: 1, both: 2, symmetric: 2, oneway: 2, context: 3, grouped: 3, read: 4, gate: 5, bundle: 5, scored: 6 }
const BOLD: DrawnStyle[] = ['scored', 'gate', 'bundle']

interface Geo { e: BEdge; st: DrawnStyle; d: string; faded: boolean; cands: { p: Pt; ang: number }[]; pts: Pt[]; text: string }

/** Unité de dessin : toutes les tailles de police et d'épaisseur sont proportionnelles au rayon médian des nœuds. */
export function unitOf(map: BMap): number {
  const rs = map.nodes.map(n => n.r).sort((a, b) => a - b)
  const med = rs.length ? rs[Math.floor(rs.length / 2)] : 42
  return Math.max(0.4, Math.min(3, med / 42))
}

function rectEdgePoint(r: { x: number; y: number; w: number; h: number }, to: Pt): Pt {
  const c = { x: r.x + r.w / 2, y: r.y + r.h / 2 }, dx = to.x - c.x, dy = to.y - c.y
  const k = Math.min(dx ? r.w / 2 / Math.abs(dx) : 1e9, dy ? r.h / 2 / Math.abs(dy) : 1e9)
  return { x: c.x + dx * k, y: c.y + dy * k }
}

function edgeGeometry(map: BMap, sc: BScenario | null, u: number, t: T): Geo[] {
  const byId = new Map(map.nodes.map(n => [n.id, n]))
  const frames = new Map(map.frames.map(f => [f.id, f]))
  const groups = new Map<string, BEdge[]>()
  const key = (e: BEdge) => (e.frame ? `f:${e.frame}|${e.to}` : [e.from, e.to].sort().join('|'))
  const drawable = map.edges.filter(e => byId.has(e.to) && (e.frame ? frames.has(e.frame) : byId.has(e.from)))
  for (const e of drawable) if (e.from !== e.to) groups.set(key(e), [...(groups.get(key(e)) ?? []), e])
  const out: Geo[] = []
  for (const e of drawable) {
    const st = drawnStyle(e, sc)
    const nb = byId.get(e.to)!, na = byId.get(e.from)
    const fr = e.frame ? frames.get(e.frame)! : null
    const faded = !!(na?.faded || nb.faded) && !fr
    // une arête de hiérarchie porte un mot court traduit (jamais le terme technique brut)
    const text = e.kind === 'subclass' ? t('bm.edge.subclass') : e.label + (fr && fr.note ? ` · ${fr.note}` : '')
    if (e.from === e.to && na) {
      const ra = na.r, s = { x: na.x + ra * Math.cos(-1.15), y: na.y + ra * Math.sin(-1.15) }, en = { x: na.x + ra * Math.cos(-0.25), y: na.y + ra * Math.sin(-0.25) }
      const c1 = { x: na.x + 2.2 * ra * Math.cos(-1.25), y: na.y + 2.2 * ra * Math.sin(-1.25) }, c2 = { x: na.x + 2.2 * ra * Math.cos(-0.15), y: na.y + 2.2 * ra * Math.sin(-0.15) }
      const lab = { x: na.x + 1.95 * ra * Math.cos(-0.7), y: na.y + 1.95 * ra * Math.sin(-0.7) }
      out.push({ e, st, d: `M${f1(s.x)},${f1(s.y)} C${f1(c1.x)},${f1(c1.y)} ${f1(c2.x)},${f1(c2.y)} ${f1(en.x)},${f1(en.y)}`, faded, cands: [{ p: lab, ang: 0 }], pts: [lab], text })
      continue
    }
    const pb = { x: nb.x, y: nb.y }
    let pa: Pt, ra = 0
    if (fr) pa = rectEdgePoint(fr, pb)
    else { pa = { x: na!.x, y: na!.y }; ra = na!.r }
    const grp = groups.get(key(e))!, k = grp.indexOf(e)
    const dx = pb.x - pa.x, dy = pb.y - pa.y, L = Math.hypot(dx, dy) || 1
    let off = grp.length === 1 ? L * 0.045 : (k - (grp.length - 1) / 2) * 70 * u
    if (!fr && e.from > e.to) off = -off
    const ctrl = { x: (pa.x + pb.x) / 2 + (-dy / L) * off * 2, y: (pa.y + pb.y) / 2 + (dx / L) * off * 2 }
    const w = (ink2(st)) * u
    const rb = nb.r, gap = 4 * u + w * 0.6
    let lo = 0, hi = 0.5
    if (ra) { for (let i = 0; i < 28; i++) { const m = (lo + hi) / 2; if (dist(quad(pa, ctrl, pb, m).p, pa) < ra + 3 * u) lo = m; else hi = m } }
    const ts = ra ? hi : 0
    lo = 0.5; hi = 1
    for (let i = 0; i < 28; i++) { const m = (lo + hi) / 2; if (dist(quad(pa, ctrl, pb, m).p, pb) < rb + gap) hi = m; else lo = m }
    const te = lo
    const s = quad(pa, ctrl, pb, ts).p, en = quad(pa, ctrl, pb, te).p
    // courbe de contrôle de la portion [ts, te] (sous-courbe d'une quadratique)
    const lerp = (p: Pt, q: Pt, v: number): Pt => ({ x: p.x + (q.x - p.x) * v, y: p.y + (q.y - p.y) * v })
    const cs = lerp(lerp(pa, ctrl, ts), lerp(ctrl, pb, ts), te)
    const d = `M${f1(s.x)},${f1(s.y)} Q${f1(cs.x)},${f1(cs.y)} ${f1(en.x)},${f1(en.y)}`
    const cands = [0.5, 0.42, 0.58, 0.34, 0.66, 0.27, 0.73, 0.21, 0.79].map(v => { const q = quad(pa, ctrl, pb, ts + (te - ts) * v); return { p: q.p, ang: q.ang } })
    const pts = Array.from({ length: 41 }, (_, i) => quad(pa, ctrl, pb, ts + ((te - ts) * i) / 40).p)
    out.push({ e, st, d, faded, cands, pts, text })
  }
  return out
}
// épaisseur de trait d'un style, lue dans la palette claire (les épaisseurs sont les mêmes en sombre)
const ink2 = (st: DrawnStyle) => palette(false).edge[st].w

export function buildParts(o: RenderOpts): Parts {
  const { scenario, pal, t, lang } = o
  // le serveur réserve une toile carrée : on rogne le vide à droite et en bas pour que le dessin reste lisible une fois ajusté à l'écran
  const m0 = o.map, cw0 = Math.max(0, ...m0.zones.map(z => z.x + z.w), ...m0.frames.map(f => f.x + f.w), ...m0.nodes.map(n => n.x + n.r)), ch0 = Math.max(0, ...m0.zones.map(z => z.y + z.h), ...m0.frames.map(f => f.y + f.h), ...m0.nodes.map(n => n.y + n.r))
  const map: BMap = cw0 > 0 && ch0 > 0 ? { ...m0, canvas: { w: Math.min(m0.canvas.w, cw0 + 40), h: Math.min(m0.canvas.h, ch0 + 40) } } : m0
  const u = unitOf(map), dec = lang === 'fr' ? ',' : '.'
  const nodes = map.nodes
  const byId = new Map(nodes.map(n => [n.id, n]))
  const order = roleOrder(nodes), legendOf = new Map(map.legend.map(l => [l.role, l])), ringed = new Set(scenario?.nodes ?? [])
  const geo = edgeGeometry(map, scenario, u, t)
  const pad = 60 * u, ox = pad, oy = 190 * u
  const legW = 700 * u, legGap = 70 * u
  const out: string[] = []
  const add = (s: string) => out.push(s)

  // marqueurs de flèche, un par style réellement utilisé
  add('<defs>')
  for (const st of new Set(geo.map(g => g.st))) {
    const ink = pal.edge[st], sz = Math.max(16 * u, ink.w * u * 3.2)
    add(`<marker id="bm-arr-${st}" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="${f1(sz)}" markerHeight="${f1(sz)}" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${ink.color}"/></marker>`)
  }
  add('</defs>')

  // ---- en-tête
  const title = map.meta.title || t('bm.title')
  const sub = [t('bm.subtitle', { date: map.meta.date || '—', types: map.meta.types, relations: map.meta.relations }), scenario ? t('bm.sub.scenario', { name: scenario.name }) : ''].filter(Boolean).join(' · ')
  add(`<text x="${f1(ox)}" y="${f1(78 * u)}" font-size="${f1(44 * u)}" font-weight="700" fill="${pal.ink}" data-bm="title">${esc(title)}</text>`)
  add(`<text x="${f1(ox)}" y="${f1(128 * u)}" font-size="${f1(23 * u)}" fill="${pal.muted}" data-bm="subtitle">${esc(sub)}</text>`)

  add(`<g transform="translate(${f1(ox)} ${f1(oy)})">`)
  // ---- zones
  const zoneText = (z: (typeof map.zones)[number], halo: boolean) => {
    const fsT = Math.max(14 * u, Math.min(30 * u, (z.w - 56 * u) / Math.max(1, textWidth(z.title, 1, true))))
    const fsS = Math.max(11 * u, Math.min(20 * u, (z.w - 56 * u) / Math.max(1, textWidth(z.subtitle, 1))))
    const h = (w: number) => (halo ? ` stroke="${zoneTint(z.color, pal)}" stroke-width="${f1(w * u)}" stroke-linejoin="round" paint-order="stroke"` : '')
    return `<text x="${f1(z.x + 28 * u)}" y="${f1(z.y + 50 * u)}" font-size="${f1(fsT)}" font-weight="700" fill="${pal.zoneTitle}"${h(10)}>${esc(z.title)}</text>` +
      (z.subtitle ? `<text x="${f1(z.x + 28 * u)}" y="${f1(z.y + 50 * u + 34 * u)}" font-size="${f1(fsS)}" fill="${pal.zoneSub}"${h(8)}>${esc(z.subtitle)}</text>` : '')
  }
  for (const z of map.zones) {
    add(`<g data-zone="${esc(z.id)}"><rect x="${f1(z.x)}" y="${f1(z.y)}" width="${f1(z.w)}" height="${f1(z.h)}" rx="${f1(28 * u)}" fill="${zoneTint(z.color, pal)}" stroke="${pal.zoneLine}" stroke-width="${f1(2 * u)}" stroke-dasharray="${f1(12 * u)} ${f1(8 * u)}"/>${zoneText(z, false)}</g>`)
  }
  // ---- cadres
  for (const fr of map.frames) {
    add(`<g data-frame="${esc(fr.id)}"><rect x="${f1(fr.x)}" y="${f1(fr.y)}" width="${f1(fr.w)}" height="${f1(fr.h)}" rx="${f1(36 * u)}" fill="${pal.frameFill}" fill-opacity="0.55" stroke="${pal.frame}" stroke-width="${f1(3.5 * u)}" stroke-dasharray="${f1(4 * u)} ${f1(7 * u)}" stroke-linecap="round"/>` +
      `<text x="${f1(fr.x + 16 * u)}" y="${f1(fr.y - 12 * u)}" font-size="${f1(20 * u)}" font-weight="700" fill="${pal.frame}">${esc(fr.title)}</text></g>`)
  }
  // ---- arêtes (les plus discrètes d'abord, les mises en avant par-dessus)
  const attrs = (g: Geo) => (o.interactive ? ` data-e="${esc(g.e.id)}" data-a="${esc(g.e.frame ? g.e.frame : g.e.from)}" data-b="${esc(g.e.to)}"` : '')
  for (const g of [...geo].sort((a, b) => RANK[a.st] - RANK[b.st])) {
    const ink = pal.edge[g.st], dash = ink.dash ? ` stroke-dasharray="${ink.dash.split(' ').map(x => f1(+x * u)).join(' ')}"` : ''
    const op = g.faded ? ' opacity="0.35"' : ''
    add(`<g${attrs(g)}${op}><path d="${g.d}" fill="none" stroke="${ink.color}" stroke-width="${f1(ink.w * u)}"${dash}${ink.round ? ' stroke-linecap="round"' : ''} marker-end="url(#bm-arr-${g.st})"/>` +
      (o.interactive ? `<path class="bm-hit" d="${g.d}" fill="none" stroke="transparent" stroke-width="${f1(Math.max(14 * u, ink.w * u + 10))}" pointer-events="stroke"/>` : '') + '</g>')
  }
  // ---- nœuds
  for (const n of nodes) {
    const ink = roleInk(n.role ? order.indexOf(n.role) : -1, pal, legendOf.get(n.role)?.color)
    const baseFs = Math.min(0.476 * n.r, 26 * u)
    let fs = baseFs, lines = splitCaption(n.label, fs, 2 * n.r - 22 * u)
    while (fs > baseFs * 0.62 && lines.some(l => textWidth(l, fs, true) > 2 * n.r - 14 * u)) { fs *= 0.92; lines = splitCaption(n.label, fs, 2 * n.r - 22 * u) }
    const cnt = shortCount(n.count, dec)
    const y0 = n.y - (lines.length - 1) * fs * 0.55 - (cnt ? 9 * u : 0)
    let g = `<g${o.interactive ? ` data-n="${esc(n.id)}" class="bm-n"` : ''}${n.faded ? ' opacity="0.45"' : ''}>`
    if (ringed.has(n.id)) g += `<circle cx="${f1(n.x)}" cy="${f1(n.y)}" r="${f1(n.r + 11 * u)}" fill="none" stroke="${pal.ring}" stroke-width="${f1(5 * u)}"/>`
    g += `<circle class="bm-c" cx="${f1(n.x)}" cy="${f1(n.y)}" r="${f1(n.r)}" fill="${ink.fill}" stroke="${ink.stroke}" stroke-width="${f1(4 * u)}"/>`
    lines.forEach((l, k) => { g += `<text x="${f1(n.x)}" y="${f1(y0 + k * fs * 1.1)}" text-anchor="middle" dominant-baseline="central" font-size="${f1(fs)}" font-weight="700" fill="${pal.ink}">${esc(l)}</text>` })
    if (cnt) g += `<text x="${f1(n.x)}" y="${f1(y0 + (lines.length - 1) * fs * 1.1 + fs + 6 * u)}" text-anchor="middle" dominant-baseline="central" font-size="${f1(fs * 0.9)}" fill="${pal.muted}">${esc(cnt)}</text>`
    if (o.interactive && n.pinned) g += `<circle class="bm-pin" cx="${f1(n.x + n.r * 0.72)}" cy="${f1(n.y - n.r * 0.72)}" r="${f1(6 * u)}" fill="${pal.ring}" stroke="${pal.bg}" stroke-width="${f1(2 * u)}"/>`
    add(g + '</g>')
  }
  // ---- libellés d'arêtes : premier emplacement libre le long de la courbe (hors nœuds et autres libellés)
  const placed: Pt[][] = []
  for (const g of [...geo].sort((a, b) => Number(BOLD.includes(b.st)) - Number(BOLD.includes(a.st)) || Number(a.faded) - Number(b.faded))) {
    if (!g.text) continue
    const bold = BOLD.includes(g.st), fs = (17 + (bold ? 3 : 0)) * u, w = textWidth(g.text, fs, bold) + 14 * u, h = fs + 9 * u
    let best: { hit: number; p: Pt; ang: number; box: Pt[] } | null = null
    for (const c of g.cands) {
      const ang = readable(c.ang), box = obb(c.p, ang, w, h)
      let hit = nodes.filter(n => circleHitsObb(n, n.r + 6 * u, ang, c.p, w, h)).length
      hit += placed.filter(pb => obbOverlap(box, pb)).length
      if (!best || hit < best.hit) best = { hit, p: c.p, ang, box }
      if (!hit) break
    }
    const b = best!
    placed.push(b.box)
    const ink = pal.edge[g.st], op = g.faded ? ' opacity="0.45"' : ''
    add(`<g${attrs(g)} transform="translate(${f1(b.p.x)} ${f1(b.p.y)}) rotate(${f1((b.ang * 180) / Math.PI)})"${op}${o.interactive ? ' class="bm-lab"' : ''}>` +
      `<rect x="${f1(-w / 2)}" y="${f1(-h / 2)}" width="${f1(w)}" height="${f1(h)}" rx="${f1(6 * u)}" fill="${pal.labelBg}" fill-opacity="0.9"/>` +
      `<text text-anchor="middle" dominant-baseline="central" font-size="${f1(fs)}"${bold ? ' font-weight="700"' : ''} fill="${ink.text}">${esc(g.text)}</text></g>`)
  }
  // ---- titres de zone une seconde fois, au-dessus des arêtes, avec un liseré de la couleur du fond
  for (const z of map.zones) add(zoneText(z, true))
  add('</g>')

  // ---- légende et notes
  let bottom = oy + map.canvas.h
  if (o.withLegend) {
    const lx = ox + map.canvas.w + legGap, S = 21 * u
    let y = oy + 30 * u
    const head = (s: string) => { add(`<text x="${f1(lx)}" y="${f1(y)}" font-size="${f1(30 * u)}" font-weight="700" fill="${pal.zoneTitle}">${esc(s)}</text>`) }
    head(t('bm.legend'))
    y += 50 * u
    const roles = order.filter(r => nodes.some(n => n.role === r))
    for (const r of roles) {
      const ink = roleInk(order.indexOf(r), pal, legendOf.get(r)?.color)
      add(`<circle cx="${f1(lx + 22 * u)}" cy="${f1(y)}" r="${f1(19 * u)}" fill="${ink.fill}" stroke="${ink.stroke}" stroke-width="${f1(3 * u)}"/>`)
      add(`<text x="${f1(lx + 58 * u)}" y="${f1(y)}" dominant-baseline="central" font-size="${f1(S)}" fill="${pal.zoneTitle}">${esc(legendOf.get(r)?.label || roleLabel(t, r))}</text>`)
      y += 54 * u
    }
    if (nodes.some(n => !n.role)) { const ink = roleInk(-1, pal); add(`<circle cx="${f1(lx + 22 * u)}" cy="${f1(y)}" r="${f1(19 * u)}" fill="${ink.fill}" stroke="${ink.stroke}" stroke-width="${f1(3 * u)}"/><text x="${f1(lx + 58 * u)}" y="${f1(y)}" dominant-baseline="central" font-size="${f1(S)}" fill="${pal.zoneTitle}">${esc(t('bm.role.none'))}</text>`); y += 54 * u }
    y += 14 * u
    const used = [...new Set(geo.map(g => g.st))].sort((a, b) => RANK[b] - RANK[a])
    for (const st of used) {
      const ink = pal.edge[st], dash = ink.dash ? ` stroke-dasharray="${ink.dash.split(' ').map(x => f1(+x * u)).join(' ')}"` : ''
      add(`<line x1="${f1(lx)}" y1="${f1(y)}" x2="${f1(lx + 80 * u)}" y2="${f1(y)}" stroke="${ink.color}" stroke-width="${f1(ink.w * u)}"${dash}${ink.round ? ' stroke-linecap="round"' : ''} marker-end="url(#bm-arr-${st})"/>`)
      add(`<text x="${f1(lx + 100 * u)}" y="${f1(y)}" dominant-baseline="central" font-size="${f1(S)}" fill="${pal.zoneTitle}">${esc(t('bm.style.' + st))}</text>`)
      y += 50 * u
    }
    const extra: string[] = []
    if (map.frames.length) extra.push(`<rect x="${f1(lx)}" y="${f1(y - 14 * u)}" width="${f1(80 * u)}" height="${f1(28 * u)}" rx="${f1(10 * u)}" fill="none" stroke="${pal.frame}" stroke-width="${f1(3 * u)}" stroke-dasharray="${f1(4 * u)} ${f1(6 * u)}" stroke-linecap="round"/>`, t('bm.lg.frame'))
    if (extra.length) { add(extra[0]); add(`<text x="${f1(lx + 100 * u)}" y="${f1(y)}" dominant-baseline="central" font-size="${f1(S)}" fill="${pal.zoneTitle}">${esc(extra[1])}</text>`); y += 50 * u }
    if (nodes.some(n => n.faded)) { add(`<circle cx="${f1(lx + 40 * u)}" cy="${f1(y)}" r="${f1(16 * u)}" fill="${pal.dark ? '#26324a' : '#e2e8f0'}" stroke="${pal.soft}" stroke-width="${f1(3 * u)}" opacity="0.45"/><text x="${f1(lx + 100 * u)}" y="${f1(y)}" dominant-baseline="central" font-size="${f1(S)}" fill="${pal.zoneTitle}">${esc(t('bm.lg.faded'))}</text>`); y += 50 * u }
    if (ringed.size) { add(`<circle cx="${f1(lx + 40 * u)}" cy="${f1(y)}" r="${f1(16 * u)}" fill="none" stroke="${pal.ring}" stroke-width="${f1(5 * u)}"/><text x="${f1(lx + 100 * u)}" y="${f1(y)}" dominant-baseline="central" font-size="${f1(S)}" fill="${pal.zoneTitle}">${esc(t('bm.lg.ring'))}</text>`); y += 50 * u }
    if (scenario && scenario.description.trim()) {
      y += 40 * u
      head(scenario.name)
      y += 12 * u
      for (const l of noteLines(scenario.description, legW - 10 * u, S)) {
        y += l.gap ? 16 * u : 33 * u
        if (l.text) add(`<text x="${f1(lx + l.indent)}" y="${f1(y)}" font-size="${f1(S)}"${l.bold ? ' font-weight="700"' : ''} fill="${pal.zoneTitle}" xml:space="preserve">${esc(l.text)}</text>`)
      }
    }
    bottom = Math.max(bottom, y + 20 * u)
  }
  const w = ox + map.canvas.w + (o.withLegend ? legGap + legW : 0) + pad
  return { w, h: bottom + pad, inner: out.join('\n'), origin: { x: ox, y: oy }, u }
}

export const roleLabel = (t: T, role: string) => { const k = 'bm.role.' + role; const v = t(k); return v === k ? role : v }

/** Document SVG autonome (export). */
export function buildMapSvg(o: RenderOpts, title: string): { svg: string; w: number; h: number } {
  const p = buildParts({ ...o, interactive: false })
  const w = Math.round(p.w), h = Math.round(p.h)
  const svg = `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" font-family="${FONT}">\n<title>${esc(title)}</title>\n` +
    `<rect width="100%" height="100%" fill="${o.pal.bg}"/>\n${p.inner}\n</svg>\n`
  return { svg, w, h }
}
export { FONT }
