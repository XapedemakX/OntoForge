import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent as RKeyboardEvent, type PointerEvent as RPointerEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useT } from '../i18n'
import { Icon } from './index'

/**
 * Feuille du bas (L44) : trois hauteurs (aperçu, moitié, plein écran), poignée glissable au doigt ou au clavier (flèches, Entrée), voile et
 * focus piégé quand elle est ouverte à moitié ou en plein écran, Échap pour fermer, `inert` sur le fond, rendu du focus à l'élément d'origine,
 * mouvement réduit sans animation, suivi du clavier virtuel par `visualViewport`. L'aperçu ne bloque pas l'écran (le graphe reste manipulable).
 */
export type Snap = 'peek' | 'half' | 'full'
const ORDER: Snap[] = ['peek', 'half', 'full']
export interface SheetApi { snap: Snap; setSnap: (s: Snap) => void }
interface Props {
  open: boolean; onClose: () => void; title: string; icon?: string
  children: ReactNode | ((a: SheetApi) => ReactNode)
  initial?: Snap; snaps?: Snap[]; testid?: string; className?: string; footer?: ReactNode
  /** Remplace le titre dans l'en-tête (ex. nom de la classe) sans changer l'étiquette d'accessibilité. */
  heading?: ReactNode
}
let modalCount = 0
const setInert = (on: boolean) => {
  const root = document.getElementById('root'); if (!root) return
  modalCount += on ? 1 : -1
  if (modalCount > 0) root.setAttribute('inert', ''); else { modalCount = 0; root.removeAttribute('inert') }
}

export function BottomSheet({ open, onClose, title, icon, children, initial = 'half', snaps = ORDER, testid, className = '', footer, heading }: Props) {
  const t = useT()
  const [snap, setSnapRaw] = useState<Snap>(initial)
  const [dragH, setDragH] = useState<number | null>(null)
  const [vv, setVv] = useState({ h: typeof innerHeight === 'number' ? innerHeight : 700, bottom: 0 })
  const box = useRef<HTMLDivElement>(null)
  const from = useRef<HTMLElement | null>(null)
  const drag = useRef<{ y: number; h: number; t: number; moved: boolean } | null>(null)
  const allowed = ORDER.filter(s => snaps.includes(s))
  const setSnap = useCallback((s: Snap) => setSnapRaw(allowed.includes(s) ? s : allowed[0]), [allowed.join()])  // eslint-disable-line react-hooks/exhaustive-deps
  const modal = snap !== 'peek'

  useLayoutEffect(() => { if (open) { setSnapRaw(initial); setDragH(null) } }, [open])  // eslint-disable-line react-hooks/exhaustive-deps
  // focus : on mémorise l'élément d'origine, on prend le focus, on le rend à la fermeture
  useEffect(() => {
    if (!open) return
    from.current = document.activeElement as HTMLElement | null
    const id = setTimeout(() => box.current?.focus({ preventScroll: true }), 30)
    return () => { clearTimeout(id); const f = from.current; if (f && f.isConnected) f.focus({ preventScroll: true }) }
  }, [open])
  useEffect(() => { if (!open || !modal) return; setInert(true); return () => setInert(false) }, [open, modal])
  useEffect(() => {
    if (!open) return
    const v = window.visualViewport
    const upd = () => setVv({ h: v ? v.height : innerHeight, bottom: v ? Math.max(0, innerHeight - v.height - v.offsetTop) : 0 })
    upd(); v?.addEventListener('resize', upd); v?.addEventListener('scroll', upd); addEventListener('resize', upd)
    return () => { v?.removeEventListener('resize', upd); v?.removeEventListener('scroll', upd); removeEventListener('resize', upd) }
  }, [open])
  useEffect(() => {
    if (!open) return
    const f = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }
    addEventListener('keydown', f, true); return () => removeEventListener('keydown', f, true)
  }, [open, onClose])

  const px = (s: Snap) => s === 'peek' ? Math.min(300, Math.round(vv.h * 0.42)) : s === 'half' ? Math.round(vv.h * 0.6) : Math.round(vv.h - 8)
  const onGripDown = (e: RPointerEvent) => {
    drag.current = { y: e.clientY, h: px(snap), t: e.timeStamp, moved: false }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  const onGripMove = (e: RPointerEvent) => {
    const d = drag.current; if (!d) return
    const dy = d.y - e.clientY
    if (!d.moved && Math.abs(dy) < 6) return
    d.moved = true
    setDragH(Math.max(60, Math.min(vv.h - 8, d.h + dy)))
  }
  const onGripUp = (e: RPointerEvent) => {
    const d = drag.current; drag.current = null
    if (!d) return
    try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId) } catch { /* ignoré */ }
    if (!d.moved) { setDragH(null); const i = allowed.indexOf(snap); setSnap(allowed[(i + 1) % allowed.length]); return }
    const h = dragH ?? d.h, v = (d.y - e.clientY) / Math.max(1, e.timeStamp - d.t)   // px/ms, positif = vers le haut
    setDragH(null)
    if (h < px(allowed[0]) * 0.7 || (v < -0.6 && snap === allowed[0])) { onClose(); return }
    const target = v > 0.6 ? allowed[Math.min(allowed.length - 1, allowed.indexOf(snap) + 1)] : v < -0.6 ? allowed[Math.max(0, allowed.indexOf(snap) - 1)] : allowed.reduce((a, b) => (Math.abs(px(b) - h) < Math.abs(px(a) - h) ? b : a))
    setSnap(target)
  }
  const onGripKey = (e: RKeyboardEvent) => {
    const i = allowed.indexOf(snap)
    if (e.key === 'ArrowUp' && i < allowed.length - 1) { e.preventDefault(); setSnap(allowed[i + 1]) }
    else if (e.key === 'ArrowDown') { e.preventDefault(); if (i > 0) setSnap(allowed[i - 1]); else onClose() }
  }
  const trap = (e: RKeyboardEvent) => {
    if (e.key !== 'Tab' || !modal || !box.current) return
    const f = [...box.current.querySelectorAll<HTMLElement>('a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')].filter(x => x.offsetParent !== null)
    if (!f.length) return
    const a = document.activeElement
    if (e.shiftKey && (a === f[0] || a === box.current)) { e.preventDefault(); f[f.length - 1].focus() }
    else if (!e.shiftKey && a === f[f.length - 1]) { e.preventDefault(); f[0].focus() }
  }
  if (!open) return null
  const style = { height: dragH ?? px(snap), bottom: vv.bottom, ['--sheet-vvh' as string]: vv.h + 'px' }
  const label = t(snap === 'full' ? 'sheet.shrink' : 'sheet.grow')
  return createPortal(
    <>
      {modal && <div className="sheet-scrim" data-testid="sheet-scrim" onClick={() => (snap === 'full' && allowed.includes('half') ? setSnap('half') : onClose())} />}
      <div ref={box} className={`sheet s-${snap}${dragH != null ? ' dragging' : ''} ${className}`} style={style} role="dialog" aria-modal={modal} aria-label={title}
        tabIndex={-1} data-testid={testid ?? 'sheet'} data-snap={snap} onKeyDown={trap}>
        <div className="sheet-head">
          <button type="button" className="sheet-grip" aria-label={`${label} — ${title}`} onPointerDown={onGripDown} onPointerMove={onGripMove} onPointerUp={onGripUp} onPointerCancel={() => { drag.current = null; setDragH(null) }} onKeyDown={onGripKey}>
            <span className="bar" aria-hidden="true" />
          </button>
          <div className="sheet-title">{icon && <Icon name={icon} />}<b>{heading ?? title}</b>
            <button type="button" className="sheet-x" aria-label={t('common.close')} onClick={onClose}><Icon name="xmark" /></button></div>
        </div>
        <div className="sheet-body">{typeof children === 'function' ? children({ snap, setSnap }) : children}</div>
        {footer && <div className="sheet-foot">{footer}</div>}
      </div>
    </>, document.body)
}
