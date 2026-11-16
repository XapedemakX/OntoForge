import { useEffect, useRef, type RefObject } from 'react'

/**
 * Appui long (L44) : 500 ms sans que le doigt bouge de plus de 8 px. Safari iOS n'émet pas `contextmenu` à l'appui long : on le calcule
 * donc nous-mêmes avec des pointer events posés sur le conteneur (phase de capture : le canevas garde ses propres gestes).
 * Le toucher qui suit l'appui long est avalé (pas de sélection par erreur) et le menu contextuel natif est bloqué.
 */
export function useLongPress(ref: RefObject<HTMLElement>, cb: (target: Element, x: number, y: number) => void, opts: { ms?: number; tol?: number; enabled?: boolean } = {}) {
  const { ms = 500, tol = 8, enabled = true } = opts
  const cbRef = useRef(cb); cbRef.current = cb
  useEffect(() => {
    const el = ref.current
    if (!el || !enabled) return
    let timer = 0, sx = 0, sy = 0, id = -1, fired = false
    const clear = () => { clearTimeout(timer); timer = 0 }
    const down = (e: PointerEvent) => {
      if (e.pointerType === 'mouse' && e.button !== 0) return
      if (id !== -1 && e.pointerId !== id) { clear(); return }   // deuxième doigt : c'est un pincement
      id = e.pointerId; sx = e.clientX; sy = e.clientY; fired = false
      const tgt = e.target as Element
      clear(); timer = window.setTimeout(() => { fired = true; timer = 0; cbRef.current(tgt, sx, sy) }, ms)
    }
    const move = (e: PointerEvent) => { if (timer && e.pointerId === id && Math.hypot(e.clientX - sx, e.clientY - sy) > tol) clear() }
    const up = (e: PointerEvent) => { if (e.pointerId === id) { clear(); id = -1 } }
    const click = (e: MouseEvent) => { if (fired) { fired = false; e.stopPropagation(); e.preventDefault() } }
    const ctx = (e: Event) => { if (fired || timer) e.preventDefault() }
    el.addEventListener('pointerdown', down, true); el.addEventListener('pointermove', move, true)
    el.addEventListener('pointerup', up, true); el.addEventListener('pointercancel', up, true)
    el.addEventListener('click', click, true); el.addEventListener('contextmenu', ctx)
    return () => {
      clear()
      el.removeEventListener('pointerdown', down, true); el.removeEventListener('pointermove', move, true)
      el.removeEventListener('pointerup', up, true); el.removeEventListener('pointercancel', up, true)
      el.removeEventListener('click', click, true); el.removeEventListener('contextmenu', ctx)
    }
  }, [ref, ms, tol, enabled])
}
