// Triplestore local (L19) : choix « Triplestore local (test) » dans le sélecteur d'endpoint. Mémoire du navigateur uniquement (module).
import { useSyncExternalStore } from 'react'
import type { LocalEndpoint } from './qapi'

export const LOCAL: LocalEndpoint = { kind: 'local' }
let on = false
const subs = new Set<() => void>()
let snap = { local: on }
const emit = () => { snap = { local: on }; subs.forEach(f => f()) }

export const localMode = {
  set(v: boolean) { if (v !== on) { on = v; emit() } },
  get: () => snap,
}
export function useLocalMode() {
  return useSyncExternalStore(f => { subs.add(f); return () => { subs.delete(f) } }, localMode.get)
}
