// Calculs dérivés de l'ontologie pour la vue liste (aucun appel réseau).
import { labelOf, localName, type ClassExpr, type OntClass, type OntoModel, type Restriction } from '../../api'

export type Kind = 'class' | 'objectProperty' | 'datatypeProperty' | 'individual'
export type Tr = (k: string, p?: Record<string, string | number>) => string
export const XSD = 'http://www.w3.org/2001/XMLSchema#'
export const DATATYPES = ['string', 'integer', 'decimal', 'boolean', 'dateTime', 'date', 'float', 'double', 'anyURI'].map(x => XSD + x)

export function kindOf(o: OntoModel, iri: string): Kind | null {
  if (o.classes[iri]) return 'class'
  if (o.object_properties[iri]) return 'objectProperty'
  if (o.datatype_properties[iri]) return 'datatypeProperty'
  if (o.individuals[iri]) return 'individual'
  return null
}
export function lblOf(o: OntoModel, iri: string, lang: string): string {
  const e = o.classes[iri] || o.object_properties[iri] || o.datatype_properties[iri] || o.individuals[iri]
  return labelOf(e, iri, lang)
}
export const lowerFirst = (s: string) => (s.length > 1 && s[1] === s[1].toLowerCase() ? s[0].toLowerCase() + s.slice(1) : s)

/** Ancêtres d'une classe (les plus proches d'abord), sans boucle. */
export function ancestors(o: OntoModel, iri: string): string[] {
  const out: string[] = []; const seen = new Set([iri]); let front = [iri]
  while (front.length) {
    const next: string[] = []
    for (const f of front) for (const p of o.classes[f]?.sub_class_of ?? []) if (o.classes[p] && !seen.has(p)) { seen.add(p); out.push(p); next.push(p) }
    front = next
  }
  return out
}
export function childrenMap(o: OntoModel, lang: string): Map<string, string[]> {
  const m = new Map<string, string[]>()
  for (const c of Object.values(o.classes)) for (const p of c.sub_class_of) if (o.classes[p]) (m.get(p) ?? m.set(p, []).get(p)!).push(c.iri)
  m.forEach(v => v.sort((a, b) => lblOf(o, a, lang).localeCompare(lblOf(o, b, lang))))
  return m
}

export interface Card { min: number; max: number | null }
const CARD_KINDS = ['min', 'max', 'exactly']
/** Cardinalité effective d'une propriété pour une classe : restrictions de la classe puis de ses ancêtres. */
export function cardinality(o: OntoModel, cls: string, prop: string, functional: boolean): { card: Card; from: string | null } {
  for (const c of [cls, ...ancestors(o, cls)]) {
    const rs = (o.classes[c]?.restrictions ?? []).filter(r => r.property === prop && !r.inverse && CARD_KINDS.includes(r.kind))
    if (!rs.length) continue
    let min = 0; let max: number | null = null
    for (const r of rs) {
      const n = r.n ?? 0
      if (r.kind === 'exactly') { min = Math.max(min, n); max = n } else if (r.kind === 'min') min = Math.max(min, n); else max = max === null ? n : Math.min(max, n)
    }
    return { card: { min, max }, from: c }
  }
  return { card: { min: 0, max: functional ? 1 : null }, from: null }
}
export function cardText(c: Card, t: Tr): string {
  if (c.max !== null && c.min === c.max) return t('ol.card.exactly', { n: c.min })
  if (c.min > 0 && c.max === null) return t('ol.card.min', { n: c.min })
  if (c.min > 0 && c.max !== null) return t('ol.card.between', { a: c.min, b: c.max })
  if (c.max !== null) return t('ol.card.max', { n: c.max })
  return t('ol.card.free')
}
export const CARD_PRESETS: [string, Card][] = [['free', { min: 0, max: null }], ['one', { min: 1, max: 1 }], ['atmost1', { min: 0, max: 1 }], ['atleast1', { min: 1, max: null }]]
export const presetOf = (c: Card): string => CARD_PRESETS.find(([, p]) => p.min === c.min && p.max === c.max)?.[0] ?? 'custom'
/** Opérations qui fixent la cardinalité d'une propriété pour une classe (efface les restrictions min/max/exactly propres). */
export function cardOps(o: OntoModel, cls: string, prop: string, c: Card): Record<string, unknown>[] {
  const rm = (o.classes[cls]?.restrictions ?? []).filter(r => r.property === prop && !r.inverse && CARD_KINDS.includes(r.kind)).map(r => ({ op: 'remove_restriction', iri: cls, property: prop, kind: r.kind }))
  const add: Record<string, unknown>[] = []
  if (c.max !== null && c.min === c.max) add.push({ op: 'set_restriction', iri: cls, property: prop, kind: 'exactly', n: c.min })
  else {
    if (c.min > 0) add.push({ op: 'set_restriction', iri: cls, property: prop, kind: 'min', n: c.min })
    if (c.max !== null) add.push({ op: 'set_restriction', iri: cls, property: prop, kind: 'max', n: c.max })
  }
  return [...rm, ...add]
}

export interface PropRow {
  iri: string; kind: 'data' | 'object'; label: string; target: string; targetIri: string | null
  card: Card; origin: string | null; required: boolean; key: boolean
}
/** Propriétés dont le domaine contient la classe ou l'un de ses ancêtres. */
export function classProps(o: OntoModel, cls: string, lang: string): PropRow[] {
  const chain = [cls, ...ancestors(o, cls)]
  const keys = chain.flatMap(c => o.classes[c]?.has_keys ?? [])
  const originOf = (domain: string[]) => chain.find(c => domain.includes(c)) ?? null
  const rows: PropRow[] = []
  for (const d of Object.values(o.datatype_properties)) {
    const og = originOf(d.domain); if (!og) continue
    const { card } = cardinality(o, cls, d.iri, d.functional)
    rows.push({ iri: d.iri, kind: 'data', label: labelOf(d, d.iri, lang), target: d.range[0] ? localName(d.range[0]) : '—', targetIri: null, card, origin: og === cls ? null : og, required: card.min > 0, key: keys.some(k => k.includes(d.iri)) })
  }
  for (const p of Object.values(o.object_properties)) {
    const og = originOf(p.domain); if (!og) continue
    const { card } = cardinality(o, cls, p.iri, p.characteristics.includes('functional'))
    const tg = p.range[0]
    rows.push({ iri: p.iri, kind: 'object', label: labelOf(p, p.iri, lang), target: tg ? lblOf(o, tg, lang) : '—', targetIri: tg ?? null, card, origin: og === cls ? null : og, required: card.min > 0, key: keys.some(k => k.includes(p.iri)) })
  }
  return rows.sort((a, b) => Number(!!a.origin) - Number(!!b.origin) || a.label.localeCompare(b.label))
}

export function exprText(e: ClassExpr, lbl: (i: string) => string, t: Tr): string {
  const a = (x: ClassExpr) => exprText(x, lbl, t)
  switch (e.op) {
    case 'named': return e.iri ? lbl(e.iri) : '?'
    case 'and': return e.args.map(a).join(` ${t('ol.expr.and')} `)
    case 'or': return e.args.map(a).join(` ${t('ol.expr.or')} `)
    case 'not': return `${t('ol.expr.not')} ${e.args[0] ? a(e.args[0]) : '?'}`
    case 'oneOf': return '{ ' + e.individuals.map(lbl).join(', ') + ' }'
    default: return `${e.property ? lbl(e.property) : '?'} ${e.op}${e.n != null ? ' ' + e.n : ''} ${e.filler ? a(e.filler) : e.data_range ? localName(e.data_range) : typeof e.value === 'string' ? lbl(e.value) : e.value?.value ?? ''}`.trim()
  }
}

/** Restriction en langage naturel : « a exactement 1 code opération ». */
export function restrText(r: Restriction, lbl: (i: string) => string, t: Tr): string {
  const prop = lowerFirst(lbl(r.property))
  const filler = r.filler ? lowerFirst(lbl(r.filler)) : r.filler_expr ? '…' : ''
  const what = filler ? `${filler} ${t('ol.r.via', { p: prop })}` : prop
  const inv = r.inverse ? ` ${t('ol.r.inverse')}` : ''
  const v = typeof r.value === 'string' ? lbl(r.value) : r.value?.value ?? ''
  switch (r.kind) {
    case 'exactly': return t('ol.r.exactly', { n: r.n ?? 0, what }) + inv
    case 'min': return t('ol.r.min', { n: r.n ?? 0, what }) + inv
    case 'max': return t('ol.r.max', { n: r.n ?? 0, what }) + inv
    case 'some': return t('ol.r.some', { what }) + inv
    case 'only': return t('ol.r.only', { what }) + inv
    case 'value': return t('ol.r.value', { p: prop, v }) + inv
    default: return t('ol.r.self', { p: prop })
  }
}

export interface Usage {
  asDomain: string[]; asRange: string[]; inRestrictions: string[]
  shapes: { id: string; label: string; constraints: number }[]
}
export function classUsage(o: OntoModel, shapes: { shapes: Record<string, { id: string; targets: { target_class: string[] }; properties: unknown[]; labels: Record<string, string> }> }, iri: string, lang: string): Usage {
  return {
    asDomain: Object.values(o.object_properties).filter(p => p.domain.includes(iri)).map(p => p.iri).concat(Object.values(o.datatype_properties).filter(p => p.domain.includes(iri)).map(p => p.iri)),
    asRange: Object.values(o.object_properties).filter(p => p.range.includes(iri)).map(p => p.iri),
    inRestrictions: Object.values(o.classes).filter(c => c.iri !== iri && c.restrictions.some(r => r.filler === iri)).map(c => c.iri),
    shapes: Object.values(shapes.shapes).filter(s => s.targets.target_class.includes(iri)).map(s => ({ id: s.id, label: s.labels?.[lang] || s.labels?.fr || localName(s.id), constraints: s.properties.length })),
  }
}
export type { OntClass }
