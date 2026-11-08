import { lazy, Suspense, useEffect, useState } from 'react'

// Le jeu vit dans son propre chunk : rien n'est chargé tant qu'un déclencheur n'a pas été activé.
const Overlay = lazy(() => import('./GameOverlay'))

const KONAMI = 'ArrowUp,ArrowUp,ArrowDown,ArrowDown,ArrowLeft,ArrowRight,ArrowLeft,ArrowRight,b,a'
export const OPEN_EVENT = 'ontoforge:game'
const editable = (t: EventTarget | null) => t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))

/**
 * Écoute passive (jamais de preventDefault, aucun focus pris) des trois déclencheurs de l'easter egg :
 * code Konami, mot « krakie » tapé hors champ de saisie, ou événement « ontoforge:game » (5 clics sur le logo).
 */
export function GameLauncher() {
  const [open, setOpen] = useState(false)
  useEffect(() => { const f = () => setOpen(true); addEventListener(OPEN_EVENT, f); return () => removeEventListener(OPEN_EVENT, f) }, [])
  useEffect(() => {
    if (open) return
    let seq: string[] = [], typed = ''
    const on = (e: KeyboardEvent) => {
      if (e.repeat || e.isComposing || e.ctrlKey || e.metaKey || e.altKey) return
      if (editable(e.target)) { seq = []; typed = ''; return }
      if (e.key === 'Shift' || e.key === 'CapsLock') return
      const k = e.key.length === 1 ? e.key.toLowerCase() : e.key
      seq = [...seq, k].slice(-10)
      typed = k.length === 1 ? (typed + k).slice(-6) : ''
      if (seq.join() === KONAMI || typed === 'krakie') { seq = []; typed = ''; setOpen(true) }
    }
    addEventListener('keydown', on)
    return () => removeEventListener('keydown', on)
  }, [open])
  return open ? <Suspense fallback={null}><Overlay onClose={() => setOpen(false)} /></Suspense> : null
}
