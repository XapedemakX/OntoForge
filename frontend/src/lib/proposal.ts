// Proposition de l'assistant, partagée entre l'écran Assistant (L10) et l'éditeur graphique (L9).
// Contrat : setProposal({projectId, onto, source, items}), useProposal(), acceptItem(id), rejectItem(id), acceptAll(), rejectAll(), clear().
// L'acceptation applique les opérations via POST /api/projects/{id}/ops (tout ou rien) puis rafraîchit le projet
// (callback `onProject` fourni à setProposal ou via bindProjectSetter, et évènement window « ontoforge:project »).
import { tr } from '../i18n'
import { useSyncExternalStore } from 'react'
import { labelOf, localName, type LangText, type OntoModel, type Project } from '../api'

export type PropOp = { op: string; [k: string]: unknown }
export interface ProposalItem {
  id: string
  kind: 'add' | 'modify'
  entity_iri: string
  label: string
  ops: PropOp[]
  /** Sorte d'élément (affichage, mini-graphe). */
  type: 'class' | 'objectProperty' | 'datatypeProperty' | 'subClassOf'
  detail?: string
  source?: string
  target?: string
  /** Éléments dont celui-ci dépend (classes ajoutées dans la même proposition) : acceptés avec lui. */
  needs?: string[]
  /** Document d'origine (amorçage L25) : extrait cité ; l'élément reste « à confirmer » tant qu'il n'est pas accepté. */
  provenance?: { document: string; page: number; excerpt: string }
  /** Avertissements du lint W3C pour cet élément (autres que les libellés manquants). */
  lint?: { code: string; message: string; level: string }[]
}
/** Résumé du document d'origine, pour l'en-tête de la proposition. */
export interface ProposalDoc { id: string; name: string; lint: { code: string; message: string; level: string }[]; approximate: boolean; skipped: number; lang?: string }
export interface ProposalState {
  projectId: string
  onto: OntoModel
  source: string
  items: ProposalItem[]
  accepted: number
  rejected: number
  busy: boolean
  error: string | null
  doc?: ProposalDoc
}
type SetInput = { projectId: string; onto: OntoModel; source: string; items: ProposalItem[]; doc?: ProposalDoc; onProject?: (p: Project) => void }

const KEY = 'ontoforge.proposal'
let state: ProposalState | null = null
let onProject: ((p: Project) => void) | null = null
const subs = new Set<() => void>()
const emit = () => { persist(); subs.forEach(f => f()) }
function persist() {
  try { if (state) localStorage.setItem(KEY, JSON.stringify(state)); else localStorage.removeItem(KEY) } catch { /* stockage indisponible */ }
}
try { const raw = localStorage.getItem(KEY); if (raw) state = { ...JSON.parse(raw), busy: false } } catch { /* ignoré */ }

export function bindProjectSetter(fn: ((p: Project) => void) | null) { onProject = fn }
export function setProposal(inp: SetInput) {
  if (inp.onProject) onProject = inp.onProject
  state = { projectId: inp.projectId, onto: inp.onto, source: inp.source, items: inp.items, doc: inp.doc, accepted: 0, rejected: 0, busy: false, error: null }
  emit()
}
export function clear() { state = null; emit() }
export function getProposal() { return state }
export function useProposal(): ProposalState | null {
  return useSyncExternalStore(f => { subs.add(f); return () => { subs.delete(f) } }, () => state)
}

async function apply(ids: string[]): Promise<boolean> {
  const s = state; if (!s || s.busy) return false
  const chosen = new Set<string>(); const seen = new Set<string>(); const order: ProposalItem[] = []
  // les éléments dont dépend un autre (classe parente, domaine, portée) passent d'abord : sinon « classe parente inconnue » à l'application
  const add = (id: string) => { const it = s.items.find(i => i.id === id); if (!it || seen.has(id)) return; seen.add(id); (it.needs ?? []).forEach(add); chosen.add(id); order.push(it) }
  ids.forEach(add)
  const list = order
  const ops = list.flatMap(i => i.ops)
  if (!list.length) return false
  state = { ...s, busy: true, error: null }; emit()
  try {
    const r = await fetch(`/api/projects/${encodeURIComponent(s.projectId)}/ops`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ops, label: list.length === 1 ? tr('ui.assistant.one', { label: list[0].label }) : tr('ui.assistant.many', { n: list.length }) }),
    })
    if (!r.ok) { let d = tr('ui.http', { s: r.status }); try { const j = await r.json(); if (typeof j.detail === 'string') d = j.detail } catch { /* non JSON */ } throw new Error(d) }
    const res = await r.json() as { ok: boolean; project: Project; errors: { message: string }[] }
    if (!res.ok) throw new Error(res.errors.map(e => e.message).join(' ; ') || tr('ui.refused'))
    state = { ...state!, items: state!.items.filter(i => !chosen.has(i.id)), accepted: state!.accepted + list.length, busy: false, error: null, onto: res.project.onto }
    emit()
    onProject?.(res.project)
    window.dispatchEvent(new CustomEvent('ontoforge:project', { detail: res.project }))
    return true
  } catch (e) {
    state = { ...state!, busy: false, error: e instanceof Error ? e.message : String(e) }; emit(); return false
  }
}
export const acceptItem = (id: string) => apply([id])
/** Accepte un sous-ensemble (un groupe de la liste) ; les éléments dont ils dépendent suivent. */
export const acceptIds = (ids: string[]) => apply(ids)
export const acceptAll = () => apply((state?.items ?? []).map(i => i.id))
export function rejectItem(id: string) {
  if (!state) return
  const gone = new Set([id]); // un rejet entraîne celui des éléments qui en dépendent
  for (const i of state.items) if (i.needs?.includes(id)) gone.add(i.id)
  state = { ...state, items: state.items.filter(i => !gone.has(i.id)), rejected: state.rejected + gone.size, error: null }; emit()
}
export function rejectAll() { if (state) { state = { ...state, rejected: state.rejected + state.items.length, items: [], error: null }; emit() } }

// ---------- calcul de la proposition (modèle partiel → éléments avec opérations) ----------
const first = (l: LangText): string | undefined => Object.values(l).find(Boolean)
const same = (a: string[], b: string[]) => a.length === b.length && a.every(x => b.includes(x))

export function buildItems(cur: OntoModel, prop: OntoModel, lang = 'fr'): ProposalItem[] {
  const out: ProposalItem[] = []
  const newClass = (iri: string) => !cur.classes[iri] && !!prop.classes[iri]
  const needsOf = (...iris: (string | undefined)[]) => iris.filter((i): i is string => !!i && newClass(i)).map(i => 'c:' + i)
  const labelOps = (iri: string, labels: LangText, comments: LangText, old?: { labels: LangText; comments: LangText }): PropOp[] => {
    const ops: PropOp[] = []
    for (const [l, t] of Object.entries(labels)) if (t && old?.labels[l] !== t) ops.push({ op: 'set_label', iri, text: t, lang: l })
    for (const [l, t] of Object.entries(comments)) if (t && old?.comments[l] !== t) ops.push({ op: 'set_comment', iri, text: t, lang: l })
    return ops
  }
  for (const [iri, c] of Object.entries(prop.classes)) {
    const old = cur.classes[iri]; const label = labelOf(c, iri, lang)
    if (!old) {
      out.push({ id: 'c:' + iri, kind: 'add', type: 'class', entity_iri: iri, label, detail: c.comments[lang] || first(c.comments),
        ops: [{ op: 'add_class', iri }, ...labelOps(iri, c.labels, c.comments), ...c.sub_class_of.map(p => ({ op: 'add_subclass', iri, parent: p }))],
        needs: needsOf(...c.sub_class_of) })
    } else {
      const ops = labelOps(iri, c.labels, c.comments, old)
      if (ops.length) out.push({ id: 'c:' + iri, kind: 'modify', type: 'class', entity_iri: iri, label, ops, detail: ops.map(o => o.op === 'set_label' ? tr('prop.d.label', { lang: String(o.lang) }) : tr('prop.d.comment', { lang: String(o.lang) })).join(', ') })
      for (const p of c.sub_class_of) if (!old.sub_class_of.includes(p))
        out.push({ id: `s:${iri}>${p}`, kind: 'add', type: 'subClassOf', entity_iri: iri, label, source: iri, target: p, ops: [{ op: 'add_subclass', iri, parent: p }], needs: needsOf(p) })
    }
  }
  for (const [iri, o] of Object.entries(prop.object_properties)) {
    const old = cur.object_properties[iri]; const label = labelOf(o, iri, lang)
    if (!old) out.push({ id: 'o:' + iri, kind: 'add', type: 'objectProperty', entity_iri: iri, label, source: o.domain[0], target: o.range[0], needs: needsOf(...o.domain, ...o.range),
      ops: [{ op: 'add_object_property', iri, domain: o.domain, range: o.range, characteristics: o.characteristics, inverse_of: o.inverse_of ?? undefined }, ...labelOps(iri, o.labels, o.comments)] })
    else if (!same(o.domain, old.domain) || !same(o.range, old.range))
      out.push({ id: 'o:' + iri, kind: 'modify', type: 'objectProperty', entity_iri: iri, label, source: o.domain[0], target: o.range[0], detail: tr('prop.d.domrange'), needs: needsOf(...o.domain, ...o.range), ops: [{ op: 'set_domain_range', iri, domain: o.domain, range: o.range }] })
  }
  for (const [iri, d] of Object.entries(prop.datatype_properties)) {
    const old = cur.datatype_properties[iri]; const label = labelOf(d, iri, lang)
    if (!old) out.push({ id: 'd:' + iri, kind: 'add', type: 'datatypeProperty', entity_iri: iri, label, source: d.domain[0], detail: d.range[0] ? localName(d.range[0]) : undefined, needs: needsOf(...d.domain),
      ops: [{ op: 'add_datatype_property', iri, domain: d.domain, range: d.range[0], functional: d.functional }, ...labelOps(iri, d.labels, d.comments)] })
    else if (!same(d.domain, old.domain) || !same(d.range, old.range))
      out.push({ id: 'd:' + iri, kind: 'modify', type: 'datatypeProperty', entity_iri: iri, label, source: d.domain[0], detail: 'domaine / type', needs: needsOf(...d.domain), ops: [{ op: 'set_domain_range', iri, domain: d.domain, range: d.range }] })
  }
  const rank = (i: ProposalItem) => (i.type === 'class' ? 0 : i.type === 'subClassOf' ? 1 : 2)
  return out.sort((a, b) => rank(a) - rank(b))
}
