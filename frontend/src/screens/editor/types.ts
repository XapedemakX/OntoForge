// Types et appels API propres à l'éditeur graphique (contrat : docs/CONTRACTS.md §5).
import { tr } from '../../i18n'
import type { Project, Perimeter, OntoModel } from '../../api'

export interface GNode { id: string; label: string; kind: 'class' | 'datatype' | 'individual' | 'thing' | 'anonymous'; icon: string | null; position: { x: number; y: number } | null; abstract: boolean; deprecated: boolean; collapsed: boolean; external?: boolean; equivalent?: boolean; op?: 'and' | 'or' | 'not' }
export interface GEdge { id: string; source: string; target: string; kind: string; label: string; iri: string | null; inverse_of?: string | null; inverse_label?: string; on?: string; characteristics?: string[]; deprecated?: boolean; functional?: boolean }
export interface GraphData { nodes: GNode[]; edges: GEdge[]; skipped: unknown[] }
export interface OpResult { ok: boolean; project: Project; applied: number; errors: { index: number; message: string }[]; warnings: string[]; can_undo: boolean; can_redo: boolean; label?: string }
export interface IconDef { id: string; label: { fr: string; en: string }; keywords: string[] }
export type Op = { op: string; [k: string]: unknown }
export type EdgeFilter = 'isa' | 'rel' | 'all'
export type Sel = { kind: 'class' | 'prop'; iri: string } | null

/** PROPOSITION de l'assistant (L10) : modèle partiel affiché en surbrillance dans l'éditeur. */
export interface ProposalItem {
  key: string
  status: 'add' | 'modify'
  kind: 'class' | 'objectProperty' | 'datatypeProperty' | 'subClassOf'
  iri: string
  label: string
  detail?: string
  /** Opérations /ops qui appliquent l'élément (calculées par diffProposal). */
  ops: Op[]
  /** Pour les arêtes (sous-classe / propriété objet) : extrémités. */
  source?: string
  target?: string
}

const BASE = '/api'
async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  let r: Response
  try { r = await fetch(BASE + path, { method, headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined, body: body !== undefined ? JSON.stringify(body) : undefined }) }
  catch { throw new Error('Serveur injoignable') }
  if (!r.ok) {
    let d = tr('ui.http', { s: r.status })
    try { const j = await r.json(); if (typeof j.detail === 'string') d = j.detail } catch { /* non JSON */ }
    throw Object.assign(new Error(d), { status: r.status })
  }
  return r.json() as Promise<T>
}
const pp = (id: string) => `/projects/${encodeURIComponent(id)}`
export const eapi = {
  graph: (id: string, perimeter: string, lang: string, include = '') => call<GraphData>('GET', `${pp(id)}/graph?lang=${lang}${perimeter ? '&perimeter=' + encodeURIComponent(perimeter) : ''}${include ? '&include=' + include : ''}`),
  ops: (id: string, ops: Op[], label?: string) => call<OpResult>('POST', `${pp(id)}/ops`, { ops, label }),
  undo: (id: string) => call<OpResult>('POST', `${pp(id)}/ops/undo`),
  redo: (id: string) => call<OpResult>('POST', `${pp(id)}/ops/redo`),
  history: (id: string) => call<{ can_undo: boolean; can_redo: boolean }>('GET', `${pp(id)}/ops/history`),
  icons: (q: string) => call<{ icons: IconDef[]; total: number }>('GET', `/icons?q=${encodeURIComponent(q)}`),
  createPerimeter: (id: string, b: { name: string; classes: string[]; properties: string[]; include_descendants: boolean }) => call<Perimeter>('POST', `${pp(id)}/perimeters`, b),
  setActive: (id: string, pid: string | null) => call<{ active_perimeter: string | null }>('PUT', `${pp(id)}/perimeters/active`, { id: pid }),
}
