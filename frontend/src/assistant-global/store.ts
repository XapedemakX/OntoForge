// Conversation du projet partagée entre le panneau global et l'écran Assistant plein écran (même clé localStorage que L10).
import { useCallback, useSyncExternalStore } from 'react'

export type ActionKind = 'ops' | 'proposal' | 'shapes' | 'guided_query' | 'navigate' | 'versions' | 'help'
export interface AgentAction {
  kind: ActionKind
  payload: Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any
  summary: string
  status?: 'idle' | 'busy' | 'applied' | 'undone' | 'error' | 'dismissed'
  error?: string
}
export interface DocMsg {
  id: string; name: string; pages: number; provider: string; approximate: boolean; calls: number; items: number; skipped: number
  questions: { id: string; text: string; covered: boolean; terms: string[] }[]
  lint: { code: string; message: string; level: string }[]
}
export interface Msg { id: string; role: 'user' | 'assistant'; content: string; warnings?: string[]; files?: string[]; count?: number; error?: boolean; actions?: AgentAction[]; doc?: DocMsg }

const storeKey = (id: string) => `ontoforge.assistant.${id}`
const mem = new Map<string, Msg[]>()
const subs = new Set<() => void>()
const EMPTY: Msg[] = []
export const uid = () => Math.random().toString(36).slice(2, 9)

function load(id: string): Msg[] {
  const hit = mem.get(id); if (hit) return hit
  let v: Msg[] = []
  try { v = JSON.parse(localStorage.getItem(storeKey(id)) || '[]') } catch { /* stockage indisponible */ }
  mem.set(id, v); return v
}
export const getMsgs = (id: string): Msg[] => (id ? load(id) : EMPTY)
export function setMsgs(id: string, next: Msg[] | ((m: Msg[]) => Msg[])) {
  if (!id) return
  const v = typeof next === 'function' ? next(load(id)) : next
  mem.set(id, v)
  try { localStorage.setItem(storeKey(id), JSON.stringify(v.slice(-80))) } catch { /* stockage indisponible */ }
  subs.forEach(f => f())
}
export function patchAction(id: string, msgId: string, idx: number, patch: Partial<AgentAction>) {
  setMsgs(id, ms => ms.map(m => m.id !== msgId ? m : { ...m, actions: m.actions?.map((a, i) => i === idx ? { ...a, ...patch } : a) }))
}
export function useConversation(id: string): [Msg[], (n: Msg[] | ((m: Msg[]) => Msg[])) => void] {
  const msgs = useSyncExternalStore(f => { subs.add(f); return () => { subs.delete(f) } }, () => getMsgs(id))
  const set = useCallback((n: Msg[] | ((m: Msg[]) => Msg[])) => setMsgs(id, n), [id])
  return [msgs, set]
}

// ---- état d'interface du panneau (ouvert, largeur, fournisseur) ----
const UI = 'ontoforge.assistant.ui'
export interface DockUi { open: boolean; width: number; provider: string }
let ui: DockUi = { open: false, width: 460, provider: '' }
try { ui = { ...ui, ...JSON.parse(localStorage.getItem(UI) || '{}'), open: false } } catch { /* ignoré */ }
export const getUi = () => ui
export function setUi(p: Partial<DockUi>) {
  ui = { ...ui, ...p }
  try { localStorage.setItem(UI, JSON.stringify({ width: ui.width, provider: ui.provider })) } catch { /* ignoré */ }
  subs.forEach(f => f())
}
export const useDockUi = () => useSyncExternalStore(f => { subs.add(f); return () => { subs.delete(f) } }, getUi)

/** Dernière action appliquée par projet : seule celle-ci peut être annulée (l'historique est linéaire). */
const last = new Map<string, string>()
export const setLastApplied = (pid: string, key: string | null) => { if (key) last.set(pid, key); else last.delete(pid); subs.forEach(f => f()) }
export const getLastApplied = (pid: string) => last.get(pid) ?? null
