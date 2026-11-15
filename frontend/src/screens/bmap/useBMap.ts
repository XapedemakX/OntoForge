import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../../api'
import { normalizeMap, toPut, type BMap, type Source } from './types'

/** Charge la carte, garde l'historique (annuler) et enregistre chaque modification. */
export function useBMap(projectId: string, source: Source, updatedAt: string | undefined) {
  const [map, setMap] = useState<BMap | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [depth, setDepth] = useState(0)
  const stack = useRef<BMap[]>([])
  const cur = useRef<BMap | null>(null)
  const seq = useRef(0)
  const key = useRef('')

  useEffect(() => {
    let live = true
    setLoading(true); setError(null)
    api.businessMap(projectId, source).then(raw => {
      if (!live) return
      const m = normalizeMap(raw)
      // un autre projet ou une autre source remet l'historique à zéro ; un simple rechargement le garde
      const k = projectId + source
      if (key.current !== k) { stack.current = []; setDepth(0); key.current = k }
      cur.current = m; setMap(m)
    }).catch(e => { if (live) { setError(e instanceof ApiError ? e : new ApiError(0, String(e))); setMap(null); cur.current = null } })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [projectId, source, updatedAt])

  const persist = useCallback((m: BMap) => {
    const n = ++seq.current
    setSaving(true)
    api.putBusinessMap(projectId, source, toPut(m)).then(res => {
      // le serveur renvoie la carte recalculée (rectangles de zone, rôles déduits) : on l'adopte s'il n'y a pas eu de modification entre-temps
      if (n === seq.current && res) {
        const fresh = normalizeMap(res)
        cur.current = fresh; setMap(fresh)
      }
    }).catch(e => setError(e instanceof ApiError ? e : new ApiError(0, String(e)))).finally(() => { if (n === seq.current) setSaving(false) })
  }, [projectId, source])

  /** Applique une modification : l'état courant va sur la pile d'annulation. */
  const commit = useCallback((next: BMap | ((m: BMap) => BMap), save = true) => {
    const before = cur.current; if (!before) return
    const m = typeof next === 'function' ? next(before) : next
    if (m === before) return
    stack.current = [...stack.current.slice(-49), before]; setDepth(stack.current.length)
    cur.current = m; setMap(m); if (save) persist(m)
  }, [persist])
  const undo = useCallback(() => {
    const prev = stack.current.pop(); if (!prev) return
    setDepth(stack.current.length); cur.current = prev; setMap(prev); persist(prev)
  }, [persist])
  return { map, error, loading, saving, commit, undo, canUndo: depth > 0, setError }
}
