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

/** Mise en page « téléphone » (L44) : moins de 700 px de large, ou paysage de moins de 500 px de haut. L'iPad en portrait (768 px) garde la mise en page large avec des cibles tactiles. */
export const MOBILE_Q = '(max-width: 700px), (max-height: 500px) and (orientation: landscape)'
export const isMobileNow = () => typeof matchMedia !== 'undefined' && matchMedia(MOBILE_Q).matches
export const useMobile = () => useMedia(MOBILE_Q)
/** Pointeur grossier (doigt) : indépendant de la largeur. */
export const useCoarse = () => useMedia('(pointer: coarse)')
/** Pose la classe `is-mobile` sur <html> (les feuilles de style s'y accrochent) et la tient à jour. */
export function initMobileClass() {
  const mq = matchMedia(MOBILE_Q)
  const f = () => document.documentElement.classList.toggle('is-mobile', mq.matches)
  f(); mq.addEventListener('change', f)
  // clavier virtuel ouvert : la barre d'onglets et le bouton Krakie s'effacent (classe `kb-open`)
  const v = window.visualViewport
  if (v) { const k = () => document.documentElement.classList.toggle('kb-open', mq.matches && v.height < innerHeight * 0.78); v.addEventListener('resize', k); k() }
}
