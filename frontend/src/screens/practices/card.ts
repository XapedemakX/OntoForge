// Fiche d'une entité (L49) : miroir client de backend/ontoforge/conformance/practices.py (entity_card).
// Les deux doivent rester alignés : mêmes critères, mêmes vocabulaires (CONTRACTS.md §19).
import type { Entity, OntoModel } from '../../api'

export const SKOS = 'http://www.w3.org/2004/02/skos/core#'
export const DCT = 'http://purl.org/dc/terms/'
export const DC = 'http://purl.org/dc/elements/1.1/'
export const VS = 'http://www.w3.org/2003/06/sw-vocab-status/ns#'
export const OWL = 'http://www.w3.org/2002/07/owl#'
export const P = {
  definition: SKOS + 'definition', prefLabel: SKOS + 'prefLabel', editorialNote: SKOS + 'editorialNote',
  creator: DCT + 'creator', source: DCT + 'source', status: VS + 'term_status', replacedBy: DCT + 'isReplacedBy',
  versionInfo: OWL + 'versionInfo', priorVersion: OWL + 'priorVersion',
}
export const NOTE_PROPS = [SKOS + 'note', SKOS + 'editorialNote', SKOS + 'scopeNote', SKOS + 'changeNote', SKOS + 'historyNote']
export const STATUS_VALUES = ['unstable', 'testing', 'stable', 'archaic'] as const
export type Criterion = 'label_fr' | 'label_en' | 'definition' | 'creator' | 'source' | 'status' | 'justification'
export type Kind = 'class' | 'objectProperty' | 'datatypeProperty'

const vals = (e: Entity, ...props: string[]) => e.annotations.filter(a => props.includes(a.property))
export const hasLabel = (e: Entity, l: string) => !!e.labels[l]?.trim() || vals(e, P.prefLabel).some(a => a.lang === l && a.value.trim())
export const hasDefinition = (e: Entity) => Object.values(e.comments).some(v => v.trim()) || vals(e, P.definition).some(a => a.value.trim())
export const statusOf = (e: Entity) => vals(e, P.status)[0]?.value.trim() ?? null
export const replacedBy = (e: Entity) => vals(e, P.replacedBy).map(a => a.value)
export const annValues = (e: Entity, prop: string, lang?: string) => vals(e, prop).filter(a => lang === undefined || (a.lang ?? '') === lang).map(a => a.value)

export function kindOf(onto: OntoModel, iri: string): Kind | null {
  return onto.classes[iri] ? 'class' : onto.object_properties[iri] ? 'objectProperty' : onto.datatype_properties[iri] ? 'datatypeProperty' : null
}
export function hasCharacteristics(onto: OntoModel, iri: string): boolean {
  const o = onto.object_properties[iri]; if (o) return o.characteristics.length > 0
  return !!onto.datatype_properties[iri]?.functional
}
export interface Card { criteria: Partial<Record<Criterion, boolean>>; missing: Criterion[]; score: number }
export function entityCard(onto: OntoModel, iri: string): Card | null {
  const e = onto.classes[iri] || onto.object_properties[iri] || onto.datatype_properties[iri]
  if (!e) return null
  const c: Partial<Record<Criterion, boolean>> = {
    label_fr: hasLabel(e, 'fr'), label_en: hasLabel(e, 'en'), definition: hasDefinition(e),
    creator: vals(e, DCT + 'creator', DC + 'creator').length > 0, source: vals(e, DCT + 'source', DC + 'source').length > 0,
    status: statusOf(e) !== null,
  }
  if (hasCharacteristics(onto, iri)) c.justification = vals(e, ...NOTE_PROPS).length > 0
  const keys = Object.keys(c) as Criterion[]
  const ok = keys.filter(k => c[k]).length
  return { criteria: c, missing: keys.filter(k => !c[k]), score: Math.round(100 * ok / keys.length) }
}
export const scoreTone = (s: number) => s >= 80 ? 'auto' : s >= 50 ? 'review' : 'lost'
