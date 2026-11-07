// État du constructeur : arbre de nœuds (une variable = une classe) -> GuidedQuery.
import type { DataSuggest, FilterKind, Guided, GFilter, GStep, ValueKind } from './qapi'

export const RDFS_LABEL = 'http://www.w3.org/2000/01/rdf-schema#label'

export interface QFilter { id: string; prop: string | null; propLabel: string; valueKind: ValueKind; kind: FilterKind; value: string; value2: string; lang: string; negate: boolean; caseInsensitive: boolean }
export interface QEdge { prop: string; propLabel: string; inverse: boolean; optional: boolean; negated: boolean }
export interface QNode { id: string; varName: string; classIri: string; label: string; edge?: QEdge; filters: QFilter[]; children: QNode[] }
export interface QCol { id: string; varName: string; prop: string | null; label: boolean; title: string }
export interface QState { root: QNode | null; cols: QCol[] | null; order: { colId: string; desc: boolean } | null; limit: number; subclasses: boolean }

export const EMPTY: QState = { root: null, cols: null, order: null, limit: 100, subclasses: false }
let seq = 0
export const uid = () => `n${Date.now().toString(36)}${(seq++).toString(36)}`
export const localName = (iri: string) => iri.replace(/^.*[#/]/, '')

export const colId = (varName: string, prop: string | null, label: boolean) => `${varName}|${label ? 'l' : prop ?? ''}`

export function varFor(label: string, taken: Set<string>): string {
  const base = label.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').replace(/^[0-9]/, 'x$&') || 'v'
  let v = base, i = 2
  while (taken.has(v)) v = `${base}_${i++}`
  return v
}
export function walk(n: QNode, f: (n: QNode, parent: QNode | null, hidden: boolean) => void, parent: QNode | null = null, hidden = false) {
  const h = hidden || !!n.edge?.negated
  f(n, parent, h)
  n.children.forEach(c => walk(c, f, n, h))
}
export const allNodes = (r: QNode | null) => { const out: QNode[] = []; if (r) walk(r, n => out.push(n)); return out }
export function mapNode(r: QNode, id: string, f: (n: QNode) => QNode | null): QNode | null {
  if (r.id === id) return f(r)
  return { ...r, children: r.children.map(c => mapNode(c, id, f)).filter((c): c is QNode => c !== null) }
}
export function defaultFilter(d: DataSuggest | null): QFilter {
  const kind: FilterKind = d?.filter_kinds[0] ?? 'text_contains'
  return { id: uid(), prop: d?.iri ?? null, propLabel: d?.label ?? '', valueKind: d?.value_kind ?? 'text', kind, value: '', value2: '', lang: '', negate: false, caseInsensitive: true }
}

/** Filtre « est l'un de » sur l'entité elle-même (liste à cocher d'individus connus). */
export function entityFilter(): QFilter {
  return { id: uid(), prop: null, propLabel: '', valueKind: 'other', kind: 'in_values', value: '', value2: '', lang: '', negate: false, caseInsensitive: true }
}
export const isEntityFilter = (f: QFilter) => f.prop === null && f.kind === 'in_values'

/** Colonnes par défaut : l'entité de chaque variable visible (pas sous une négation). */
export function defaultCols(r: QNode | null): QCol[] {
  const out: QCol[] = []
  if (r) walk(r, (n, _p, hidden) => { if (!hidden) out.push({ id: colId(n.varName, null, false), varName: n.varName, prop: null, label: false, title: n.label }) })
  return out
}
export function effectiveCols(s: QState): QCol[] {
  const vis = new Set<string>(); if (s.root) walk(s.root, (n, _p, h) => { if (!h) vis.add(n.varName) })
  const base = s.cols ?? defaultCols(s.root)
  return base.filter(c => vis.has(c.varName))
}

export function isActive(f: QFilter): boolean {
  if (f.kind === 'number_range' || f.kind === 'date_range') return f.value.trim() !== '' || f.value2.trim() !== ''
  return f.value.trim() !== ''
}

export function toGuided(s: QState): Guided | null {
  if (!s.root) return null
  const steps: GStep[] = []; const filters: GFilter[] = []
  walk(s.root, (n, parent) => {
    if (parent && n.edge) steps.push({ from_var: parent.varName, property_iri: n.edge.prop, inverse: n.edge.inverse, to_var: n.varName, to_class_iri: n.classIri, optional: n.edge.optional, negated: n.edge.negated })
    for (const f of n.filters) {
      if (!isActive(f)) continue
      const g: GFilter = { var: n.varName, kind: f.kind, property_iri: f.prop, negate: f.negate }
      if (f.kind === 'number_range') { g.value = f.value || null; g.value2 = f.value2 || null }
      else if (f.kind === 'date_range') { g.value = f.value || null; g.value2 = f.value2 || null }
      else if (f.kind === 'lang') g.lang = f.value.trim()
      else if (f.kind === 'in_values') { g.values = f.value.split('\n').map(x => x.trim()).filter(Boolean); if (isEntityFilter(f)) g.is_iri = true }
      else { g.value = f.value; if (f.kind !== 'equals' || f.valueKind === 'text') g.case_insensitive = f.caseInsensitive }
      if (f.kind === 'equals' && f.valueKind !== 'text') g.datatype = f.valueKind === 'number' ? 'http://www.w3.org/2001/XMLSchema#decimal' : f.valueKind === 'boolean' ? 'http://www.w3.org/2001/XMLSchema#boolean' : undefined
      filters.push(g)
    }
  })
  const cols = effectiveCols(s)
  const select = cols.map(c => ({ var: c.varName, property_iri: c.prop, label: c.label }))
  const col = s.order ? cols.find(c => c.id === s.order!.colId) : null
  return {
    root: { var: s.root.varName, class_iri: s.root.classIri }, steps, filters, select,
    order_by: col ? [{ var: col.varName, property_iri: col.prop, desc: s.order!.desc }] : [], limit: s.limit, distinct: true, subclasses: s.subclasses,
  }
}

/** Reconstruit un état d'édition depuis une GuidedQuery sauvegardée (libellés repris des suggestions déjà chargées). */
export function fromGuided(g: Guided, labelOf: (iri: string) => string): QState {
  const nodes = new Map<string, QNode>()
  const mk = (varName: string, cls: string, edge?: QEdge): QNode => ({ id: uid(), varName, classIri: cls, label: labelOf(cls), edge, filters: [], children: [] })
  const root = mk(g.root.var, g.root.class_iri ?? '')
  nodes.set(root.varName, root)
  for (const st of g.steps) {
    const parent = nodes.get(st.from_var); if (!parent) continue
    const n = mk(st.to_var, st.to_class_iri ?? '', { prop: st.property_iri, propLabel: labelOf(st.property_iri), inverse: st.inverse, optional: st.optional, negated: st.negated })
    parent.children.push(n); nodes.set(n.varName, n)
  }
  for (const f of g.filters) {
    const n = nodes.get(f.var); if (!n) continue
    const isRange = f.kind === 'number_range' || f.kind === 'date_range'
    n.filters.push({ id: uid(), prop: f.property_iri ?? null, propLabel: f.property_iri ? labelOf(f.property_iri) : '', valueKind: f.kind === 'number_range' ? 'number' : f.kind === 'date_range' ? 'date' : 'text',
      kind: f.kind, value: f.kind === 'lang' ? f.lang ?? '' : f.kind === 'in_values' ? (f.values ?? []).join('\n') : f.value ?? '', value2: isRange ? f.value2 ?? '' : '', lang: f.lang ?? '', negate: !!f.negate, caseInsensitive: f.case_insensitive ?? true })
  }
  const cols: QCol[] = g.select.map(s => ({ id: colId(s.var, s.property_iri ?? null, !!s.label), varName: s.var, prop: s.property_iri ?? null, label: !!s.label, title: nodes.get(s.var)?.label ?? s.var }))
  const o = g.order_by[0]
  const oc = o ? cols.find(c => c.varName === o.var && (c.prop ?? null) === (o.property_iri ?? null)) : null
  return { root, cols: cols.length ? cols : null, order: oc && o ? { colId: oc.id, desc: o.desc } : null, limit: g.limit, subclasses: !!g.subclasses }
}
