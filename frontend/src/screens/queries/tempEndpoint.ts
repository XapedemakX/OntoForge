// Endpoint temporaire de l'écran Requêtes : mémoire du navigateur uniquement (module), jamais localStorage ni serveur.
import { useSyncExternalStore } from 'react'
import type { InlineEndpoint } from './qapi'

let current = null as InlineEndpoint | null
let using = false
const subs = new Set<() => void>()
let snap: { temp: InlineEndpoint | null; using: boolean } = { temp: current, using }
const emit = () => { snap = { temp: current, using }; subs.forEach(f => f()) }

export const tempStore = {
  set(e: InlineEndpoint | null, use = true) { current = e; using = !!e && use; emit() },
  use(v: boolean) { using = v && !!current; emit() },
  get: () => snap,
}
export function useTempEndpoint() {
  return useSyncExternalStore(f => { subs.add(f); return () => { subs.delete(f) } }, tempStore.get)
}
