import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import './strings'
import './game.css'
import { useI18n } from '../i18n'
import { Icon } from '../kit'
import { Krakie } from '../krakie/Krakie'
import { Engine, type EngineOpts, type HudState, type Phase, type Result } from './engine'
import { Sfx } from './audio'
import { loadKrakieSprites, type KrakieSprites } from './sprites'

const BEST_KEY = 'ontoforge.game.best', SND_KEY = 'ontoforge.game.sound'
const store = {
  get(k: string) { try { return localStorage.getItem(k) } catch { return null } },
  set(k: string, v: string) { try { localStorage.setItem(k, v) } catch { /* stockage indisponible : le jeu marche sans */ } },
}
const readBest = () => { const n = Number(store.get(BEST_KEY)); return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0 }
const HAPPY = 400  // seuil de score à partir duquel Krakie est content

interface End extends Result { best: number; record: boolean; same: boolean; phrase: string }

export default function GameOverlay({ onClose }: { onClose: () => void }) {
  const { t } = useI18n()
  const tRef = useRef(t); tRef.current = t
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const engine = useRef<Engine | null>(null)
  const sprites = useRef<KrakieSprites>({})
  const sfx = useRef<Sfx>(new Sfx())
  const keys = useRef({ l: false, r: false, bl: false, br: false })
  const best = useRef(readBest())
  const [phase, setPhase] = useState<Phase>('ready')
  const [hud, setHud] = useState<HudState>({ score: 0, lives: 3, level: 1, triples: 0, chain: [], shield: false })
  const [end, setEnd] = useState<End | null>(null)
  const [sound, setSound] = useState(() => store.get(SND_KEY) === '1')
  const [say, setSay] = useState('')
  const phaseRef = useRef<Phase>('ready'); phaseRef.current = phase

  const sync = useCallback(() => { const k = keys.current; engine.current?.setKeys(k.l || k.bl, k.r || k.br) }, [])
  const start = useCallback(() => { setEnd(null); engine.current?.newGame() }, [])
  const togglePause = useCallback(() => { const e = engine.current; if (!e) return; if (e.phase === 'playing') e.pause(); else if (e.phase === 'paused') e.resume() }, [])
  const toggleSound = useCallback(() => {
    setSound(s => { const n = !s; sfx.current.setEnabled(n); store.set(SND_KEY, n ? '1' : '0'); return n })
  }, [])

  // moteur : création, taille, boucle ; nettoyage complet à la fermeture
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    const root = document.getElementById('root') as (HTMLElement & { inert?: boolean }) | null
    if (root) root.inert = true
    const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const s = sfx.current; s.setEnabled(store.get(SND_KEY) === '1')
    const opts: EngineOpts = {
      canvas: canvasRef.current!, reduced: !!mq?.matches, sfx: s, sprites: () => sprites.current,
      labels: { score: tRef.current('game.hud.score'), level: tRef.current('game.hud.level') },
      on: {
        phase: setPhase, hud: setHud,
        say: (k, p) => setSay(prevS => tRef.current(k, p) + (prevS.endsWith('​') ? '' : '​')),
        over: r => {
          const prevBest = best.current
          const record = r.score > prevBest, same = r.score > 0 && r.score === prevBest
          if (record) { best.current = r.score; store.set(BEST_KEY, String(r.score)) }
          const key = record && prevBest > 0 ? 'game.end.record' : same ? 'game.end.same' : `game.end.${r.score >= HAPPY ? 'hi' : 'low'}.${1 + Math.floor(Math.random() * 4)}`
          setEnd({ ...r, best: best.current, record, same, phrase: tRef.current(key) })
        },
      },
    }
    const eng = new Engine(opts); engine.current = eng
    const onMq = () => { opts.reduced = !!mq?.matches }
    mq?.addEventListener?.('change', onMq)
    let alive = true
    void loadKrakieSprites(['accueil', 'graphe', 'inquiete', 'contente']).then(sp => { if (alive) sprites.current = sp })
    const fit = () => { const st = stageRef.current; if (st) eng.resize(st.clientWidth - 8, st.clientHeight - 8) }
    fit()
    const ro = new ResizeObserver(fit); if (stageRef.current) ro.observe(stageRef.current)
    eng.start()
    if (store.get('ontoforge.game.debug') === '1') (window as unknown as { __ontoforgeGame?: unknown }).__ontoforgeGame = eng
    const onVis = () => { if (document.hidden) eng.pause() }
    document.addEventListener('visibilitychange', onVis)
    dialogRef.current?.focus()
    return () => {
      alive = false; eng.destroy(); ro.disconnect(); mq?.removeEventListener?.('change', onMq)
      document.removeEventListener('visibilitychange', onVis); s.close(); engine.current = null
      delete (window as unknown as { __ontoforgeGame?: unknown }).__ontoforgeGame
      if (root) root.inert = false
      prev?.focus?.()
    }
  }, [])

  // clavier : actif seulement tant que le jeu est ouvert (monté)
  useEffect(() => {
    const isBtn = (t: EventTarget | null) => t instanceof HTMLElement && !!t.closest('button, a')
    const dir = (k: string): 'l' | 'r' | null => (k === 'ArrowLeft' || k === 'a' || k === 'A' || k === 'q' || k === 'Q' ? 'l' : k === 'ArrowRight' || k === 'd' || k === 'D' ? 'r' : null)
    const down = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose(); return }
      if (e.ctrlKey || e.metaKey || e.altKey) return
      if (/^Arrow/.test(e.key) || (e.key === ' ' && !isBtn(e.target))) e.preventDefault()
      const d = dir(e.key)
      if (d) { keys.current[d] = true; sync(); return }
      if (e.repeat) return
      if (e.key === 'p' || e.key === 'P') togglePause()
      else if (e.key === 'm' || e.key === 'M') toggleSound()
      else if ((e.key === 'Enter' || e.key === ' ') && !isBtn(e.target)) {
        if (phaseRef.current === 'ready' || phaseRef.current === 'over') start(); else if (phaseRef.current === 'paused') togglePause()
      }
    }
    const up = (e: KeyboardEvent) => { const d = dir(e.key); if (d) { keys.current[d] = false; sync() } }
    const blur = () => { keys.current.l = keys.current.r = false; sync() }
    addEventListener('keydown', down, true); addEventListener('keyup', up, true); addEventListener('blur', blur)
    return () => { removeEventListener('keydown', down, true); removeEventListener('keyup', up, true); removeEventListener('blur', blur) }
  }, [onClose, sync, start, togglePause, toggleSound])

  // focus : le bouton principal de la carte affichée (autoFocus) ou le dialogue pendant la partie
  useEffect(() => { if (phase === 'playing') dialogRef.current?.focus() }, [phase])

  const pointer = (e: React.PointerEvent) => { if (e.buttons || e.pointerType === 'touch') engine.current?.setPointer(e.clientX) }
  const hold = (side: 'bl' | 'br', on: boolean) => ({
    onPointerDown: (e: React.PointerEvent) => { e.preventDefault(); (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId); keys.current[side] = on; sync() },
    onPointerUp: () => { keys.current[side] = false; sync() }, onPointerCancel: () => { keys.current[side] = false; sync() },
  })

  const pose = end ? (end.score >= HAPPY || end.record ? 'contente' : 'inquiete') : 'accueil'
  const legend = (cls: string, label: string, text: string) => <li><span className={`g-chip ${cls}`} aria-hidden="true">{label}</span><span>{text}</span></li>

  return createPortal(
    <div className="game" role="dialog" aria-modal="true" aria-label={t('game.dialog')} ref={dialogRef} tabIndex={-1}
      data-phase={phase} data-score={hud.score} data-lives={hud.lives} data-level={hud.level} data-triples={hud.triples}>
      <header className="g-bar">
        <h2 className="g-title"><Krakie pose="accueil" size={28} float={false} animated={false} /> <span>{t('game.title')}</span></h2>
        <span className="g-grow" />
        <button type="button" className="g-btn" onClick={togglePause} disabled={phase !== 'playing' && phase !== 'paused'} aria-label={phase === 'paused' ? t('game.resume') : t('game.pause')} title={t('game.pause') + ' (P)'}><Icon name={phase === 'paused' ? 'play' : 'pause'} /></button>
        <button type="button" className="g-btn" onClick={toggleSound} aria-pressed={sound} aria-label={sound ? t('game.sound.off') : t('game.sound.on')} title={(sound ? t('game.sound.off') : t('game.sound.on')) + ' (M)'}><Icon name={sound ? 'volume-high' : 'volume-xmark'} /></button>
        <button type="button" className="g-btn" onClick={onClose} aria-label={t('game.close')} title={t('game.close') + ' (Esc)'}><Icon name="xmark" /></button>
      </header>
      <div className="g-stage" ref={stageRef}>
        <canvas ref={canvasRef} className="g-canvas" role="img" aria-label={t('game.canvas')}
          onPointerDown={e => { e.currentTarget.setPointerCapture?.(e.pointerId); pointer(e) }} onPointerMove={pointer}
          onPointerUp={() => engine.current?.setPointer(null)} onPointerCancel={() => engine.current?.setPointer(null)} />
        {phase === 'ready' && (
          <div className="g-card">
            <Krakie pose="graphe" size={72} float={false} />
            <h3>{t('game.title')}</h3>
            <p>{t('game.intro')}</p>
            <ul className="g-legend">
              {legend('s', 'S', t('game.legend.s'))}{legend('p', 'P', t('game.legend.p'))}{legend('o', 'O', t('game.legend.o'))}
              {legend('bad', '!', t('game.legend.bad'))}{legend('iri', '<IRI>', t('game.legend.iri'))}
              {legend('inf', 'INF', t('game.legend.inf'))}{legend('shacl', 'SHACL', t('game.legend.shacl'))}
            </ul>
            <button type="button" className="g-btn primary" onClick={start} autoFocus>{t('game.play')}</button>
          </div>)}
        {phase === 'paused' && (
          <div className="g-card small"><h3>{t('game.paused')}</h3>
            <button type="button" className="g-btn primary" onClick={togglePause} autoFocus>{t('game.resume')}</button>
            <button type="button" className="g-btn" onClick={onClose}>{t('game.close')}</button></div>)}
        {phase === 'over' && end && (
          <div className="g-card">
            <Krakie pose={pose} size={88} float={false} />
            <h3>{t('game.over')}</h3>
            <p className="g-score">{t('game.result', { score: end.score, triples: end.triples, level: end.level })}</p>
            <p className="g-best">{end.record ? <b>{t('game.newbest')}</b> : null} {t('game.best', { best: end.best })}</p>
            <p className="g-quote">« {end.phrase} »</p>
            <div className="g-row">
              <button type="button" className="g-btn primary" onClick={start} autoFocus>{t('game.again')}</button>
              <button type="button" className="g-btn" onClick={onClose}>{t('game.close')}</button>
            </div>
          </div>)}
      </div>
      <div className="g-pad">
        <button type="button" className="g-btn pad" aria-label={t('game.left')} {...hold('bl', true)}><Icon name="arrow-left" /></button>
        <button type="button" className="g-btn pad" aria-label={t('game.right')} {...hold('br', true)}><Icon name="arrow-right" /></button>
      </div>
      <footer className="g-keys">{t('game.keys')}</footer>
      <div className="g-sr" role="status" aria-live="polite">{say}</div>
    </div>, document.body)
}
