import { useEffect, useState, useSyncExternalStore } from 'react'

/** Préférence du bandeau latéral : « auto » (replié sur les écrans de plein canevas), « open » (toujours ouvert), « closed » (toujours replié). */
export type SidePref = 'auto' | 'open' | 'closed'
const K = 'ontoforge.side'
const EVT = 'ontoforge:side-pref'
let mem: SidePref = 'auto'

export function readSidePref(): SidePref {
  try { const v = localStorage.getItem(K); if (v === 'open' || v === 'closed' || v === 'auto') return v } catch { /* stockage indisponible : mémoire */ }
  return mem
}
export function writeSidePref(v: SidePref) {
  mem = v
  try { localStorage.setItem(K, v) } catch { /* ignoré */ }
  dispatchEvent(new Event(EVT))
}
const subscribe = (cb: () => void) => { addEventListener(EVT, cb); addEventListener('storage', cb); return () => { removeEventListener(EVT, cb); removeEventListener('storage', cb) } }
export const useSidePref = (): [SidePref, (v: SidePref) => void] => [useSyncExternalStore(subscribe, readSidePref, () => 'auto' as SidePref), writeSidePref]

/** true quand la fenêtre correspond à la requête (ex. bureau : « (min-width: 901px) »). */
export function useMedia(q: string): boolean {
  const [m, setM] = useState(() => matchMedia(q).matches)
  useEffect(() => { const mq = matchMedia(q); const f = () => setM(mq.matches); f(); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f) }, [q])
  return m
}
