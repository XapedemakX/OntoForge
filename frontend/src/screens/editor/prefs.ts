// Préférences d'affichage de l'éditeur (L26) : mémorisées dans le navigateur, sans jamais dépendre du stockage (try/catch partout).
import { useCallback, useState } from 'react'

export type Mode = 'classic' | 'vowl'
export type LegendState = 'closed' | 'open' | 'folded'
export interface ShowPrefs { dt: boolean; sub: boolean; rel: boolean; disj: boolean; dep: boolean; krakie: boolean; density: number }
export const DEFAULT_SHOW: ShowPrefs = { dt: true, sub: true, rel: true, disj: true, dep: true, krakie: true, density: 0 }

export const KEYS = { mode: 'ontoforge.ed.mode', legend: 'ontoforge.ed.legend', show: 'ontoforge.ed.show' }

export function lsGet(k: string): string | null { try { return localStorage.getItem(k) } catch { return null } }
export function lsSet(k: string, v: string) { try { localStorage.setItem(k, v) } catch { /* stockage indisponible : on continue sans mémoriser */ } }

export function readShow(): ShowPrefs {
  try {
    const j = JSON.parse(lsGet(KEYS.show) ?? 'null')
    if (!j || typeof j !== 'object') return DEFAULT_SHOW
    const b = (k: keyof ShowPrefs) => (typeof j[k] === 'boolean' ? j[k] : DEFAULT_SHOW[k as 'dt'])
    const d = Number(j.density)
    return { dt: b('dt'), sub: b('sub'), rel: b('rel'), disj: b('disj'), dep: b('dep'), krakie: b('krakie'), density: Number.isFinite(d) ? Math.max(0, Math.min(6, Math.round(d))) : 0 }
  } catch { return DEFAULT_SHOW }
}

/** État mémorisé : `parse` valide la valeur lue, `ser` la sérialise. */
export function useStored<T>(key: string, init: () => T, ser: (v: T) => string): [T, (v: T) => void] {
  const [v, setV] = useState<T>(init)
  const set = useCallback((n: T) => { setV(n); lsSet(key, ser(n)) }, [key, ser])
  return [v, set]
}
