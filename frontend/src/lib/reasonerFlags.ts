// Classes insatisfiables signalées par HermiT (L32) : partagées entre l'écran Conformité et l'éditeur, qui les met en rouge
// avec le même mécanisme d'erreur que les opérations refusées. Mémoire de session, par projet.
import { useSyncExternalStore } from 'react'

export interface ReasonerFlags { projectId: string; unsat: string[]; focus: string | null }
const EMPTY: ReasonerFlags = { projectId: '', unsat: [], focus: null }
let flags: ReasonerFlags = EMPTY
const subs = new Set<() => void>()
const emit = () => subs.forEach(f => f())

export const setReasonerFlags = (projectId: string, unsat: string[], focus: string | null = null) => { flags = { projectId, unsat, focus }; emit() }
export const clearReasonerFlags = () => { flags = EMPTY; emit() }
export const consumeFocus = () => { if (flags.focus) { flags = { ...flags, focus: null }; emit() } }
export const useReasonerFlags = (projectId: string): ReasonerFlags =>
  useSyncExternalStore(f => { subs.add(f); return () => { subs.delete(f) } }, () => (flags.projectId === projectId ? flags : EMPTY))
