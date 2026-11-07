// Endpoint SPARQL actif : source de vérité = GET /api/settings (active_endpoint_id + sparql_endpoints).
// ÉVÉNEMENT : l'écran Paramètres émet `window` « ontoforge:endpoint-changed » (detail: ActiveEndpoint | null)
// après tout changement (choix, ajout, modification, suppression). Le shell l'écoute via useActiveEndpoint().
import { useEffect, useState } from 'react'

export const ENDPOINT_EVENT = 'ontoforge:endpoint-changed'
export interface ActiveEndpoint { id: string; name: string; url: string }

export function announceActiveEndpoint(e: ActiveEndpoint | null) {
  window.dispatchEvent(new CustomEvent<ActiveEndpoint | null>(ENDPOINT_EVENT, { detail: e }))
}

async function load(): Promise<ActiveEndpoint | null> {
  try {
    const r = await fetch('/api/settings'); if (!r.ok) return null
    const s = await r.json()
    const id = s.active_endpoint_id ?? s.active_sparql_endpoint
    const e = (s.sparql_endpoints ?? []).find((x: { id: string }) => x.id === id)
    if (e) return { id: e.id, name: e.name, url: e.url }
    return s.sparql_endpoint?.url ? { id: 'default', name: '', url: s.sparql_endpoint.url } : null
  } catch { return null }
}

/** Endpoint actif (rechargé à la connexion, à chaque changement de `deps` et à chaque événement). */
export function useActiveEndpoint(...deps: unknown[]): ActiveEndpoint | null {
  const [ep, setEp] = useState<ActiveEndpoint | null>(null)
  useEffect(() => { let ok = true; load().then(x => { if (ok) setEp(x) }); return () => { ok = false } }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const f = (ev: Event) => setEp((ev as CustomEvent<ActiveEndpoint | null>).detail ?? null)
    window.addEventListener(ENDPOINT_EVENT, f); return () => window.removeEventListener(ENDPOINT_EVENT, f)
  }, [])
  return ep
}
