import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import { Button, Icon, Krakie } from '../kit'
import { useT } from '../i18n'
import { getState, subscribe, tour, isMobile, targetBox, type Box, type Placement } from './controller'

const PAD = 6, GAP = 16, M = 12

function place(box: Box | null, bw: number, bh: number, pref?: Placement) {
  const vw = innerWidth, vh = innerHeight
  if (!box) return { left: (vw - bw) / 2, top: (vh - bh) / 2, side: null as Placement | null, arrow: 0 }
  const clampX = (x: number) => Math.min(Math.max(x, M), vw - bw - M)
  const clampY = (y: number) => Math.min(Math.max(y, M), vh - bh - M)
  const cx = box.left + box.width / 2, cy = box.top + box.height / 2
  const order = [...new Set([pref, 'bottom', 'top', 'right', 'left'].filter(Boolean))] as Placement[]
  const at = (s: Placement) => s === 'bottom' ? { left: clampX(cx - bw / 2), top: box.top + box.height + PAD + GAP }
    : s === 'top' ? { left: clampX(cx - bw / 2), top: box.top - PAD - GAP - bh }
      : s === 'right' ? { left: box.left + box.width + PAD + GAP, top: clampY(cy - bh / 2) }
        : { left: box.left - PAD - GAP - bw, top: clampY(cy - bh / 2) }
  for (const s of order) {
    const p = at(s)
    if (p.left >= M && p.top >= M && p.left + bw <= vw - M && p.top + bh <= vh - M) {
      return { ...p, side: s, arrow: s === 'top' || s === 'bottom' ? Math.min(Math.max(cx - p.left, 20), bw - 20) : Math.min(Math.max(cy - p.top, 20), bh - 20) }
    }
  }
  // cible trop grande pour laisser la place à côté : la bulle se pose dans son angle bas-droit
  return { left: clampX(box.left + box.width - bw - GAP), top: clampY(box.top + box.height - bh - GAP), side: null as Placement | null, arrow: 0 }
}

export function Overlay() {
  const t = useT()
  const st = useSyncExternalStore(subscribe, getState)
  const step = st.steps[st.index]
  const bub = useRef<HTMLDivElement>(null)
  const [box, setBox] = useState<Box | null>(null)
  const [size, setSize] = useState({ w: 380, h: 220 })
  const [, tick] = useState(0)
  const running = st.active && st.phase === 'running' && !!step
  const ready = running && st.status === 'ready'
  const mobile = isMobile()
  const last = st.index === st.steps.length - 1

  // suit la cible à chaque image : défilement, redimensionnement, animations
  useEffect(() => {
    if (!ready || !step?.target || !st.found) { setBox(null); return }
    let raf = 0; let prev = ''
    const loop = () => {
      const b = targetBox(step.target!)
      const k = b ? [b.left, b.top, b.width, b.height].map(Math.round).join() : ''
      if (k !== prev) { prev = k; setBox(b) }
      raf = requestAnimationFrame(loop)
    }
    loop()
    return () => cancelAnimationFrame(raf)
  }, [ready, step, st.found])
  useEffect(() => { if (!st.active) return; const f = () => tick(x => x + 1); addEventListener('resize', f); return () => removeEventListener('resize', f) }, [st.active])
  useLayoutEffect(() => { const e = bub.current; if (e && (e.offsetWidth !== size.w || e.offsetHeight !== size.h)) setSize({ w: e.offsetWidth, h: e.offsetHeight }) })

  // focus sur la bulle à chaque étape ; retour au déclencheur à la fin
  const opener = useRef<Element | null>(null)
  useEffect(() => { if (st.active && !opener.current) opener.current = document.activeElement; if (!st.active && opener.current) { (opener.current as HTMLElement).focus?.(); opener.current = null } }, [st.active])
  useEffect(() => { if (ready || st.phase === 'ask-demo') bub.current?.focus({ preventScroll: true }) }, [ready, st.index, st.phase])

  useEffect(() => {
    if (!st.active) return
    const key = (e: KeyboardEvent) => {
      const tg = e.target as HTMLElement
      const typing = tg && (tg.tagName === 'INPUT' || tg.tagName === 'TEXTAREA' || tg.tagName === 'SELECT' || tg.isContentEditable) && !bub.current?.contains(tg)
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); tour.stop() }
      else if (typing) return
      else if (e.key === 'ArrowRight' && st.phase === 'running') { e.preventDefault(); e.stopPropagation(); void tour.next() }
      else if (e.key === 'ArrowLeft' && st.phase === 'running') { e.preventDefault(); e.stopPropagation(); void tour.prev() }
      else if (e.key === 'Tab' && bub.current) {
        const f = [...bub.current.querySelectorAll<HTMLElement>('button:not([disabled])')]; if (!f.length) return
        const i = f.indexOf(document.activeElement as HTMLElement)
        if (e.shiftKey && (i <= 0)) { e.preventDefault(); f[f.length - 1].focus() }
        else if (!e.shiftKey && (i === f.length - 1 || i < 0 && document.activeElement !== bub.current)) { e.preventDefault(); f[0].focus() }
      }
    }
    addEventListener('keydown', key, true); return () => removeEventListener('keydown', key, true)
  }, [st.active, st.phase])

  if (!st.active) return null
  const hole = box && ready ? { left: box.left - PAD, top: box.top - PAD, width: box.width + PAD * 2, height: box.height + PAD * 2 } : null
  const pos = mobile ? null : place(box && ready ? box : null, size.w, size.h, step?.placement)
  const style: React.CSSProperties = mobile ? {} : { left: pos!.left, top: pos!.top }
  const demo = st.phase === 'ask-demo' || st.phase === 'creating'

  return (
    <div className={'tour-root' + (hole ? ' has-hole' : '')} data-tour-root data-step={step?.id} data-found={st.found ? '1' : '0'} data-ready={ready ? '1' : '0'}>
      {!hole && <div className="tour-dim" />}
      {hole && <><div className="tour-hole" style={hole} /><div className="tour-halo" style={hole} /></>}
      <div ref={bub} className={'tour-bubble' + (mobile ? ' mobile' : '') + (pos?.side ? ' side-' + pos.side : '')} style={{ ...style, ['--arrow' as string]: pos ? pos.arrow + 'px' : '0' }}
        role="dialog" aria-modal="true" aria-label={t('tour.dialog')} aria-labelledby="tour-title" aria-describedby="tour-body" tabIndex={-1} data-tour-bubble>
        {demo ? (
          <div className="tour-in">
            <Krakie pose="accueil" size={mobile ? 44 : 60} />
            <div className="tour-txt">
              <h2 id="tour-title">{t('tour.demo.t')}</h2>
              <p id="tour-body">{t('tour.demo.d')}</p>
              {st.error && <p className="tour-err" role="alert">{t('tour.demo.err')}</p>}
              <div className="tour-btns">
                <Button variant="ghost" onClick={() => tour.stop()}>{t('tour.demo.cancel')}</Button><span className="grow" />
                <Button variant="primary" icon="seedling" disabled={st.phase === 'creating'} onClick={() => void tour.createDemo()}>{st.phase === 'creating' ? t('tour.demo.busy') : t('tour.demo.go')}</Button>
              </div>
            </div>
          </div>
        ) : step && (
          <div className="tour-in">
            <Krakie pose={st.status === 'loading' ? 'reflechit' : step.pose ?? 'accueil'} size={mobile ? 44 : 60} />
            <div className="tour-txt">
              <div className="tour-meta"><span className="tour-count">{t('tour.step', { n: st.index + 1, total: st.steps.length })}</span>
                <span className="tour-dots" aria-hidden="true">{st.steps.map((s, i) => <i key={s.id} className={i === st.index ? 'on' : i < st.index ? 'done' : ''} />)}</span>
                <span className="grow" /><button type="button" className="tour-skip" onClick={() => tour.stop()}>{t('tour.skip')}</button></div>
              <h2 id="tour-title">{step.title}</h2>
              <p id="tour-body">{step.body}{ready && step.target && !st.found && <em className="tour-miss"> {t('tour.noTarget')}</em>}</p>
              <div className="tour-btns">
                <span className="grow" />
                <Button size="sm" icon="arrow-left" disabled={st.index === 0} onClick={() => void tour.prev()}>{t('tour.prev')}</Button>
                <Button size="sm" variant="primary" onClick={() => void tour.next()}>{last ? t('tour.finish') : t('tour.next')}{!last && <Icon name="arrow-right" />}</Button>
              </div>
            </div>
          </div>
        )}
      </div>
      <div className="sr" aria-live="polite" role="status">{ready && step ? t('tour.live', { n: st.index + 1, total: st.steps.length, title: step.title }) : ''}</div>
    </div>
  )
}
