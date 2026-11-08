// Entrées de la légende (L26) : un mini-dessin par encodage, fidèle au rendu réel (mêmes jetons de couleur, mêmes traits).
// `show` décide si l'entrée est présente dans la vue courante ; les états transitoires (sélection, erreur) sont toujours expliqués.
import type { Mode } from './prefs'
import type { MNode, ViewModel } from './view'
import { arrow, circ, line, path, rect, text, type Pal } from './glyphs'

export interface LegendFlags {
  cls: boolean; icon: boolean; abstract: boolean; deprecated: boolean; external: boolean; equivalent: boolean; thing: boolean
  union: boolean; inter: boolean; compl: boolean; datatype: boolean; sub: boolean; obj: boolean; inverse: boolean; disj: boolean
  equivEdge: boolean; anonEdge: boolean; selfLoop: boolean; chars: Set<string>; depProp: boolean; add: boolean; modify: boolean; hid: boolean
}
export function legendFlags(vm: ViewModel): LegendFlags {
  const k = (kind: string) => vm.edges.some(e => e.kind === kind)
  const cls = vm.nodes.filter((n: MNode) => n.vk === 'class')
  return {
    cls: cls.length > 0, icon: cls.some(n => !!n.icon), abstract: cls.some(n => n.abstract), deprecated: cls.some(n => n.deprecated), external: cls.some(n => n.external),
    equivalent: cls.some(n => n.merged.length > 0), thing: vm.nodes.some(n => n.vk === 'thing'),
    union: vm.nodes.some(n => n.op === 'or'), inter: vm.nodes.some(n => n.op === 'and'), compl: vm.nodes.some(n => n.op === 'not'),
    datatype: vm.nodes.some(n => n.vk === 'datatype'), sub: k('subClassOf'), obj: k('objectProperty'), inverse: vm.edges.some(e => !!e.inverse),
    disj: k('disjointWith'), equivEdge: k('equivalentClass'), anonEdge: k('anonymousOf'),
    selfLoop: vm.edges.some(e => e.kind === 'objectProperty' && e.source === e.target),
    chars: new Set(vm.edges.flatMap(e => e.chars)), depProp: vm.edges.some(e => e.kind === 'objectProperty' && e.deprecated),
    add: vm.nodes.some(n => n.status === 'add') || vm.edges.some(e => e.status === 'add'),
    modify: vm.nodes.some(n => n.status === 'modify') || vm.edges.some(e => e.status === 'modify'),
    hid: vm.nodes.some(n => n.hid > 0),
  }
}

export interface LegendEntry { id: string; group: 'nodes' | 'links' | 'states'; modes: Mode[]; show: (f: LegendFlags) => boolean; draw: (p: Pal, labels: Record<string, string>) => string }
export const LEGEND_W = 88, LEGEND_H = 38

// ---- briques classiques ----
const nodeBox = (p: Pal, o: { dash?: string; fill?: string; stroke?: string; halo?: string } = {}) =>
  (o.halo ? rect(0.5, 2.5, 87, 33, 10, { stroke: o.halo, sw: 4, op: 0.28 }) : '') + rect(2, 4, 84, 30, 8, { fill: o.fill ?? p.panel, stroke: o.stroke ?? p.lineStrong, sw: 1.5, dash: o.dash })
const iconSq = (p: Pal, col: string, bg: string) => rect(8, 10, 18, 18, 5, { fill: bg }) + circ(17, 19, 3, { fill: col }) + circ(13, 14, 1.6, { fill: col }) + circ(21.5, 24, 1.6, { fill: col }) + line(13, 14, 17, 19, { stroke: col, sw: 1 }) + line(17, 19, 21.5, 24, { stroke: col, sw: 1 })
const label = (p: Pal, s: string, o: { italic?: boolean; strike?: boolean; fill?: string } = {}) => text(31, 20, s, { size: 11, weight: 600, fill: o.fill ?? p.ink, italic: o.italic, strike: o.strike }) + text(31, 29.5, 'ex:' + s.toLowerCase().slice(0, 7), { size: 7, fill: p.muted, mono: true })
const flag = (cx: number, cy: number, fill: string, glyph: string) => circ(cx, cy, 7, { fill }) + text(cx, cy + 3.6, glyph, { size: 10, weight: 700, fill: '#fff', anchor: 'middle' })
const pill = (p: Pal, cx: number, cy: number, s: string, o: { fill?: string; stroke?: string; ink?: string; w?: number } = {}) => {
  const w = o.w ?? Math.max(18, s.length * 6 + 12)
  return rect(cx - w / 2, cy - 8, w, 16, 8, { fill: o.fill ?? p.panel, stroke: o.stroke ?? p.lineStrong, sw: 1 }) + text(cx, cy + 3.6, s, { size: 10, weight: 500, fill: o.ink ?? p.info, anchor: 'middle' })
}
const hline = (x1: number, x2: number, y: number, o: Parameters<typeof line>[4]) => line(x1, y, x2, y, o)

// ---- briques VOWL ----
const vc = (p: Pal, o: { fill?: string; dash?: string; r?: number; stroke?: string; halo?: string; cx?: number } = {}) =>
  (o.halo ? circ(o.cx ?? 44, 19, (o.r ?? 16) + 3, { stroke: o.halo, sw: 4, op: 0.3 }) : '') + circ(o.cx ?? 44, 19, o.r ?? 16, { fill: o.fill ?? p.vwClass, stroke: o.stroke ?? p.vwLine, sw: 1.5, dash: o.dash })
const vt = (p: Pal, s: string, o: { fill?: string; ink?: string; italic?: boolean; sub?: string; y?: number } = {}) =>
  text(44, o.sub ? 18 : (o.y ?? 22), s, { size: 8.5, weight: 600, fill: o.ink ?? p.vwInk, anchor: 'middle', italic: o.italic }) + (o.sub ? text(44, 27.5, o.sub, { size: 6, fill: o.ink ?? p.vwInk, anchor: 'middle' }) : '')

const E = (id: string, group: LegendEntry['group'], modes: Mode[], show: LegendEntry['show'], draw: LegendEntry['draw']): LegendEntry => ({ id, group, modes, show, draw })
const C: Mode[] = ['classic'], V: Mode[] = ['vowl']

export const LEGEND: LegendEntry[] = [
  // ======== classique : nœuds ========
  E('c-class', 'nodes', C, f => f.cls, (p, l) => nodeBox(p) + iconSq(p, p.accent, p.accentSoft) + label(p, l.cls)),
  E('c-icon', 'nodes', C, f => f.icon, (p, l) => nodeBox(p) + rect(8, 9, 20, 20, 6, { fill: p.accentSoft, stroke: p.accent, sw: 1.2 }) + circ(18, 19, 4, { fill: p.accent }) + text(34, 23, '← fa-…', { size: 10, fill: p.muted, mono: true })),
  E('c-abstract', 'nodes', C, f => f.abstract, (p, l) => nodeBox(p, { dash: '5 3' }) + iconSq(p, p.accent, p.accentSoft) + label(p, l.cls, { italic: true }) + rect(46, -0.5, 40, 12, 6, { fill: p.panel2, stroke: p.lineStrong, sw: 1 }) + text(66, 8.5, l.abs, { size: 8, fill: p.muted, anchor: 'middle' })),
  E('c-dep', 'nodes', C, f => f.deprecated, (p, l) => nodeBox(p) + iconSq(p, p.accent, p.accentSoft) + label(p, l.cls, { strike: true, fill: p.muted }) + rect(44, -0.5, 42, 12, 6, { fill: p.reviewSoft, stroke: p.review, sw: 1 }) + text(65, 8.5, l.dep, { size: 8, fill: p.review, anchor: 'middle' })),
  E('c-hid', 'nodes', C, f => f.hid, (p, l) => nodeBox(p) + iconSq(p, p.accent, p.accentSoft) + label(p, l.cls) + circ(80, 6, 8, { fill: p.accent }) + text(80, 9.4, '+2', { size: 8.5, weight: 700, fill: p.accentInk, anchor: 'middle' })),
  // ======== classique : liens ========
  E('c-sub', 'links', C, f => f.sub, (p, l) => hline(6, 70, 19, { stroke: p.accent, sw: 1.8 }) + arrow(82, 19, 0, 'hollow', p.panel, p.accent, 12)),
  E('c-obj', 'links', C, f => f.obj, (p, l) => hline(6, 70, 19, { stroke: p.info, sw: 1.5 }) + arrow(82, 19, 0, 'solid', p.info, p.info, 10) + pill(p, 40, 19, l.has)),
  E('c-inv', 'links', C, f => f.inverse, (p, l) => hline(6, 82, 19, { stroke: p.info, sw: 1.5 }) + arrow(82, 19, 0, 'solid', p.info, p.info, 10) + pill(p, 44, 19, l.inv, { w: 78 })),
  E('c-self', 'links', C, f => f.selfLoop, (p, l) => path('M 30 26 C 8 4, 66 4, 46 26', { stroke: p.info, sw: 1.5 }) + arrow(46, 26, Math.PI * 0.45, 'solid', p.info, p.info, 9)),
  E('c-disj', 'links', C, f => f.disj, (p, l) => hline(6, 82, 19, { stroke: p.lost, sw: 2, dash: '2 5', cap: 'round' }) + circ(44, 19, 9, { fill: p.lostSoft, stroke: p.lost, sw: 1 }) + text(44, 23, '⟂', { size: 12, weight: 700, fill: p.lost, anchor: 'middle' })),
  E('c-equiv', 'links', C, f => f.equivEdge, (p, l) => hline(6, 82, 19, { stroke: p.accent, sw: 1.5, dash: '9 3 2 3' }) + pill(p, 44, 19, '≡', { ink: p.accent, w: 24 })),
  // ======== VOWL : nœuds ========
  E('v-class', 'nodes', V, f => f.cls, (p, l) => vc(p) + vt(p, l.cls)),
  E('v-ext', 'nodes', V, f => f.external, (p, l) => vc(p, { fill: p.vwExt }) + vt(p, l.cls, { ink: p.vwExtInk, sub: '[' + l.extb + ']' })),
  E('v-dep', 'nodes', V, f => f.deprecated, (p, l) => vc(p, { fill: p.vwDep }) + vt(p, l.cls, { sub: '[' + l.depn + ']' })),
  E('v-abs', 'nodes', V, f => f.abstract, (p, l) => vc(p) + circ(44, 19, 11, { stroke: p.vwLine, sw: 1, dash: '3 2' }) + vt(p, l.cls, { italic: true })),
  E('v-eq', 'nodes', V, f => f.equivalent, (p, l) => circ(44, 19, 16.5, { fill: p.vwThing, stroke: p.vwLine, sw: 1.5 }) + circ(44, 19, 13, { fill: p.vwClass, stroke: p.vwLine, sw: 1.5 }) + vt(p, 'A', { sub: '[B]' })),
  E('v-thing', 'nodes', V, f => f.thing, (p, l) => vc(p, { fill: p.vwThing, dash: '3 2.5', r: 11 }) + vt(p, 'Thing', { y: 22 })),
  E('v-or', 'nodes', V, f => f.union, (p, l) => vc(p, { dash: '4 3' }) + vt(p, '∪', { y: 25 }).replace('font-size="8.5"', 'font-size="17"')),
  E('v-and', 'nodes', V, f => f.inter, (p, l) => vc(p, { dash: '4 3' }) + vt(p, '∩', { y: 25 }).replace('font-size="8.5"', 'font-size="17"')),
  E('v-not', 'nodes', V, f => f.compl, (p, l) => vc(p, { dash: '4 3' }) + vt(p, '¬', { y: 25 }).replace('font-size="8.5"', 'font-size="17"')),
  E('v-dt', 'nodes', V, f => f.datatype, (p, l) => rect(20, 8, 48, 22, 2, { fill: p.vwDt, stroke: p.vwLine, sw: 1.2 }) + text(44, 23, 'string', { size: 10.5, weight: 500, fill: p.vwInk, anchor: 'middle' })),
  E('v-hid', 'nodes', V, f => f.hid, (p, l) => vc(p) + vt(p, l.cls) + circ(60, 6, 8, { fill: p.accent }) + text(60, 9.4, '+2', { size: 8.5, weight: 700, fill: p.accentInk, anchor: 'middle' })),
  // ======== VOWL : liens ========
  E('v-sub', 'links', V, f => f.sub, (p, l) => hline(6, 70, 19, { stroke: p.vwLine, sw: 1.8, dash: '1 4', cap: 'round' }) + arrow(82, 19, 0, 'hollow', p.vwThing, p.vwLine, 12) + rect(16, 11, 50, 15, 2, { fill: p.vwThing, stroke: p.vwLine, sw: 0.6 }) + text(41, 22, l.subOf, { size: 8.5, fill: p.vwInk, anchor: 'middle' })),
  E('v-obj', 'links', V, f => f.obj, (p, l) => hline(6, 72, 19, { stroke: p.vwLine, sw: 1.5 }) + arrow(83, 19, 0, 'solid', p.vwLine, p.vwLine, 10) + rect(14, 9, 54, 21, 2, { fill: p.vwClass }) + text(41, 18, l.has, { size: 9.5, weight: 500, fill: p.vwInk, anchor: 'middle' }) + text(41, 26.5, '[' + l.fn + ']', { size: 7, fill: p.vwInk, anchor: 'middle' })),
  E('v-inv', 'links', V, f => f.inverse, (p, l) => hline(8, 80, 19, { stroke: p.vwLine, sw: 1.5 }) + arrow(83, 19, 0, 'solid', p.vwLine, p.vwLine, 10) + arrow(5, 19, Math.PI, 'solid', p.vwLine, p.vwLine, 10) + rect(14, 9, 60, 21, 2, { fill: p.vwClass }) + text(44, 18, l.inv, { size: 9, weight: 500, fill: p.vwInk, anchor: 'middle' }) + text(44, 26.5, '⇄', { size: 8, fill: p.vwInk, anchor: 'middle' })),
  E('v-chars', 'links', V, f => f.chars.size > 0 || f.depProp, (p, l) => rect(4, 6, 80, 26, 2, { fill: p.vwClass }) + text(44, 17, l.has, { size: 9.5, weight: 500, fill: p.vwInk, anchor: 'middle' }) + text(44, 27.5, '[' + l.fn + ', ' + l.tr + ']', { size: 7.5, fill: p.vwInk, anchor: 'middle' })),
  E('v-dp', 'links', V, f => f.datatype, (p, l) => hline(4, 52, 19, { stroke: p.vwLine, sw: 1.5 }) + arrow(54, 19, 0, 'solid', p.vwLine, p.vwLine, 8) + rect(8, 10, 38, 18, 2, { fill: p.vwDp }) + text(27, 22.5, l.name, { size: 9.5, weight: 500, fill: p.vwInk, anchor: 'middle' }) + rect(56, 9, 29, 20, 2, { fill: p.vwDt, stroke: p.vwLine, sw: 1 }) + text(70.5, 22.5, 'string', { size: 8, fill: p.vwInk, anchor: 'middle' })),
  E('v-disj', 'links', V, f => f.disj, (p, l) => hline(6, 82, 19, { stroke: p.vwLine, sw: 1.5, dash: '5 3' }) + rect(24, 8, 40, 22, 2, { fill: p.vwClass }) + circ(36, 17, 4.6, { fill: p.vwGfx }) + circ(46, 17, 4.6, { fill: p.vwGfx }) + text(44, 27.5, '[' + l.disj + ']', { size: 6.5, fill: p.vwInk, anchor: 'middle' })),
  E('v-anon', 'links', V, f => f.equivEdge || f.anonEdge, (p, l) => hline(6, 82, 19, { stroke: p.vwLine, sw: 1.5, dash: '5 3' })),
  // ======== états (classique et VOWL) ========
  E('c-add', 'states', C, f => f.add, (p, l) => nodeBox(p, { dash: '5 3', fill: p.addSoft, stroke: p.add }) + iconSq(p, p.add, p.panel) + label(p, l.cls) + flag(10, 4, p.add, '+') + circ(70, 36, 6, { fill: p.add }) + text(70, 39.5, '✓', { size: 8.5, weight: 700, fill: '#fff', anchor: 'middle' }) + circ(81, 36, 6, { fill: p.lost }) + text(81, 39.5, '✕', { size: 8, weight: 700, fill: '#fff', anchor: 'middle' })),
  E('v-add', 'states', V, f => f.add, (p, l) => vc(p, { fill: p.addSoft, stroke: p.add, dash: '4 3' }) + vt(p, l.cls) + flag(31, 7, p.add, '+')),
  E('c-mod', 'states', C, f => f.modify, (p, l) => nodeBox(p, { halo: p.mod, stroke: p.mod }) + iconSq(p, p.mod, p.accentSoft) + label(p, l.cls) + flag(10, 4, p.mod, '✎')),
  E('v-mod', 'states', V, f => f.modify, (p, l) => vc(p, { halo: p.mod, stroke: p.mod }) + vt(p, l.cls) + flag(31, 7, p.mod, '✎')),
  E('c-err', 'states', C, () => true, (p, l) => nodeBox(p, { halo: p.lost, stroke: p.lost }) + iconSq(p, p.accent, p.accentSoft) + label(p, l.cls)),
  E('v-err', 'states', V, () => true, (p, l) => vc(p, { halo: p.lost, stroke: p.lost }) + vt(p, l.cls)),
  E('c-sel', 'states', C, () => true, (p, l) => nodeBox(p, { halo: p.accent, stroke: p.accent }) + iconSq(p, p.accent, p.accentSoft) + label(p, l.cls)),
  E('v-sel', 'states', V, () => true, (p, l) => vc(p, { halo: p.accent, stroke: p.accent }) + vt(p, l.cls)),
]
