import { curie, localName, labelOf, type OntoModel, type NodeShape, type PropertyShape, type ShPath, type ShapesModel, type ShaclResult } from '../../api'

export const XSD = 'http://www.w3.org/2001/XMLSchema#'
export const DATATYPES = ['string', 'integer', 'decimal', 'boolean', 'date', 'dateTime', 'float', 'double', 'anyURI', 'langString'].map(n => XSD + n)
export type T = (k: string, p?: Record<string, string | number>) => string

export function pathStr(p: ShPath, pf: Record<string, string>): string {
  if (p.kind === 'predicate') return curie(p.iri ?? '', pf)
  const a = p.args.map(x => pathStr(x, pf))
  switch (p.kind) {
    case 'inverse': return '^' + a[0]
    case 'zeroOrMore': return a[0] + '*'
    case 'oneOrMore': return a[0] + '+'
    case 'zeroOrOne': return a[0] + '?'
    case 'sequence': return a.join(' / ')
    default: return a.join(' | ')
  }
}
export const pathIri = (p: ShPath): string | null => (p.kind === 'predicate' ? p.iri ?? null : null)

export function pathLabel(p: ShPath, onto: OntoModel, lang: string): string {
  const iri = pathIri(p)
  if (!iri) return ''
  const e = onto.object_properties[iri] ?? onto.datatype_properties[iri]
  return e ? labelOf(e, iri, lang) : localName(iri)
}
export function classLabel(iri: string, onto: OntoModel, lang: string): string {
  return labelOf(onto.classes[iri], iri, lang)
}

/** Cardinalité en langage clair. */
export function cardText(min: number | null | undefined, max: number | null | undefined, t: T): string {
  const mn = min ?? 0
  if (max != null && mn === max) return mn === 1 ? t('sh.card.exact1') : t('sh.card.exact', { n: mn })
  if (mn >= 1 && max === 1) return t('sh.card.req1')
  if (mn >= 1 && max == null) return mn === 1 ? t('sh.card.min1') : t('sh.card.min', { n: mn })
  if (mn >= 1 && max != null) return t('sh.card.between', { a: mn, b: max })
  if (max === 1) return t('sh.card.opt1')
  if (max != null) return t('sh.card.max', { n: max })
  return t('sh.card.opt')
}
export type CardPreset = 'opt' | 'req1' | 'min1' | 'opt1' | 'custom'
export function cardPreset(min: number | null | undefined, max: number | null | undefined): CardPreset {
  const mn = min ?? 0
  if (mn === 0 && max == null) return 'opt'
  if (mn === 1 && max === 1) return 'req1'
  if (mn === 1 && max == null) return 'min1'
  if (mn === 0 && max === 1) return 'opt1'
  return 'custom'
}
export const PRESET_VALUES: Record<Exclude<CardPreset, 'custom'>, [number | null, number | null]> = { opt: [null, null], req1: [1, 1], min1: [1, null], opt1: [null, 1] }

/** Autres contraintes que cardinalité / type : puces lisibles. */
export function otherChips(s: PropertyShape, pf: Record<string, string>, onto: OntoModel, lang: string, t: T): { icon: string; text: string; title?: string }[] {
  const o: { icon: string; text: string; title?: string }[] = []
  const c = (x: string) => curie(x, pf)
  const val = (v: any) => (typeof v === 'string' ? c(v) : v.value)
  if (s.pattern) o.push({ icon: 'asterisk', text: t('sh.c.pattern', { v: s.pattern }), title: s.pattern })
  const lo = s.min_inclusive ?? s.min_exclusive, hi = s.max_inclusive ?? s.max_exclusive
  if (lo != null && hi != null) o.push({ icon: 'arrows-left-right', text: t('sh.c.range', { a: lo, b: hi }) })
  else if (lo != null) o.push({ icon: 'greater-than-equal', text: t(s.min_inclusive != null ? 'sh.c.gte' : 'sh.c.gt', { v: lo }) })
  else if (hi != null) o.push({ icon: 'less-than-equal', text: t(s.max_inclusive != null ? 'sh.c.lte' : 'sh.c.lt', { v: hi }) })
  if (s.min_length != null || s.max_length != null) {
    o.push({ icon: 'ruler-horizontal', text: s.min_length != null && s.max_length != null ? (s.min_length === s.max_length ? t('sh.c.len', { n: s.min_length }) : t('sh.c.lenrange', { a: s.min_length, b: s.max_length })) : s.min_length != null ? t('sh.c.lenmin', { n: s.min_length }) : t('sh.c.lenmax', { n: s.max_length! }) })
  }
  if (s.in?.length) { const l = s.in.map(val); o.push({ icon: 'list-check', text: t('sh.c.in', { v: l.length > 4 ? l.slice(0, 4).join(', ') + ' …' : l.join(', ') }), title: l.join(', ') }) }
  if ((s.has_value as unknown[] | undefined)?.length) o.push({ icon: "equals", text: t("sh.c.hasValue", { v: (s.has_value as unknown[]).map(val).join(', ') }) })
  if (s.node_kind) o.push({ icon: 'tag', text: t('sh.c.nodeKind', { v: s.node_kind }) })
  if (s.node?.length) o.push({ icon: 'diagram-project', text: t('sh.c.node', { v: s.node.map(c).join(', ') }) })
  for (const k of ['and', 'or', 'xone', 'not'] as const) {
    const l = (s as any)[k] as string[] | undefined
    if (l?.length) o.push({ icon: 'code-branch', text: `${k.toUpperCase()} ${l.map(c).join(', ')}` })
  }
  const li = (s as any).language_in as string[] | undefined
  if (li?.length) o.push({ icon: 'language', text: t('sh.c.langIn', { v: li.join(', ') }) })
  if (s.unique_lang) o.push({ icon: 'language', text: t('sh.c.uniqueLang') })
  if (s.qualified?.length) o.push({ icon: 'filter', text: t('sh.c.qualified', { n: s.qualified.length }) })
  if (s.sparql?.length) o.push({ icon: 'terminal', text: t('sh.c.sparql') })
  if (s.deactivated) o.push({ icon: 'ban', text: t('sh.c.off') })
  void onto; void lang
  return o
}

export function sev(s: string | undefined): 'Violation' | 'Warning' | 'Info' {
  const x = (s ?? '').replace(/.*[#:]/, '')
  return x === 'Warning' ? 'Warning' : x === 'Info' ? 'Info' : 'Violation'
}
export const SEV_ICON = { Violation: 'circle-xmark', Warning: 'triangle-exclamation', Info: 'circle-info' } as const

/** Classes + ancêtres. */
export function ancestors(onto: OntoModel, iri: string): Set<string> {
  const seen = new Set<string>(); const st = [iri]
  while (st.length) { const x = st.pop()!; if (seen.has(x)) continue; seen.add(x); for (const p of onto.classes[x]?.sub_class_of ?? []) st.push(p) }
  return seen
}

export function newPropertyShape(iri: string, onto: OntoModel): PropertyShape {
  const dp = onto.datatype_properties[iri]; const op = onto.object_properties[iri]
  const base: any = {
    id: `_:${localName(iri)}-${Math.random().toString(16).slice(2, 10)}`, path: { kind: 'predicate', iri, args: [] }, names: {},
    class: [], node: [], in: [], has_value: [], and: [], or: [], xone: [], not: [], sparql: [], language_in: [], qualified: [],
    datatype: null, severity: 'Violation', messages: {}, deactivated: false, min_count: null, max_count: null, unique_lang: false,
  }
  if (dp) base.datatype = dp.range[0] ?? XSD + 'string'
  if (op?.range.length) base.class = [op.range[0]]
  return base as PropertyShape
}

export function ownerOf(shapes: ShapesModel): Record<string, string> {
  const m: Record<string, string> = {}
  for (const s of Object.values(shapes.shapes)) for (const ps of s.properties) m[ps.id] = s.id
  return m
}

export function shapeTitle(s: NodeShape, onto: OntoModel, lang: string): { title: string; cls: string | null } {
  const tc = s.targets.target_class[0]
  const named = s.labels[lang] || s.labels.en || Object.values(s.labels)[0]
  if (tc) return { title: named || classLabel(tc, onto, lang), cls: tc }
  return { title: named || localName(s.id), cls: null }
}

export interface ShapeCheck { n: number; byShape: Record<string, ShaclResult[]> }
export const constraintKey = (c: string) => c.replace(/.*#/, '').replace(/ConstraintComponent$/, '')

/** Diff de génération : ajouts uniquement (shapes nouvelles, propriétés nouvelles sur shapes existantes). */
export interface GenDiff { newShapes: NodeShape[]; extra: { shape: NodeShape; props: PropertyShape[] }[]; merged: ShapesModel; skipped: number }
export function diffGenerated(cur: ShapesModel, gen: ShapesModel): GenDiff {
  const merged: ShapesModel = JSON.parse(JSON.stringify(cur))
  let skipped = 0; const newShapes: NodeShape[] = []; const extra: GenDiff['extra'] = []
  const key = (ps: PropertyShape) => pathStr(ps.path, {})
  const byClass = new Map<string, NodeShape>()
  for (const s of Object.values(cur.shapes)) for (const c of s.targets.target_class) byClass.set(c, s)
  for (const g of Object.values(gen.shapes)) {
    const ex = cur.shapes[g.id] ?? g.targets.target_class.map(c => byClass.get(c)).find(Boolean)
    if (!ex) { if (g.properties.length === 0) { skipped++; continue } newShapes.push(g); merged.shapes[g.id] = g; continue }
    const have = new Set(ex.properties.map(key))
    const props = g.properties.filter(ps => !have.has(key(ps)))
    if (props.length) { extra.push({ shape: ex, props }); merged.shapes[ex.id].properties.push(...props) }
  }
  for (const [k, v] of Object.entries(gen.prefixes)) merged.prefixes[k] ??= v
  return { newShapes, extra, merged, skipped }
}
