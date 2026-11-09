import { useEffect, useRef, useState, type RefObject } from 'react'
import draft from './krakie-draft-20px.json'

export type Pose = 'accueil' | 'reflechit' | 'lit' | 'loupe' | 'graphe' | 'contente' | 'inquiete' | 'forge' | 'trophee'
const PAL = draft.palette as Record<string, string>
const BASE = draft.base as string[]

/*
 * Sprites : /krakie/<pose>.svg (statique) et /krakie/anim/<pose>-<n>.svg (n = 1..N),
 * générés par design/krakie/build.py ; durées par frame dans /krakie/anim/manifest.json.
 * Animation : boucle requestAnimationFrame, en pause hors écran (IntersectionObserver)
 * ou onglet caché (visibilitychange) ; image statique si prefers-reduced-motion.
 */

// ---------------------------------------------------------------- manifest + préchargement
type Manifest = Partial<Record<Pose, number[]>>
let manifestPromise: Promise<Manifest> | null = null
function loadManifest(): Promise<Manifest> {
  if (!manifestPromise) {
    manifestPromise = fetch('/krakie/anim/manifest.json')
      .then((r) => (r.ok ? (r.json() as Promise<Manifest>) : {}))
      .catch(() => ({}))
  }
  return manifestPromise
}
const frameUrl = (pose: Pose, n: number) => `/krakie/anim/${pose}-${n}.svg`
const preloaded = new Set<string>()
function preload(pose: Pose, count: number) {
  for (let n = 1; n <= count; n++) {
    const u = frameUrl(pose, n)
    if (!preloaded.has(u)) { preloaded.add(u); const img = new Image(); img.src = u }
  }
}

function usePrefersReducedMotion(): boolean {
  const q = '(prefers-reduced-motion: reduce)'
  const [reduced, setReduced] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.(q).matches)
  useEffect(() => {
    const mq = window.matchMedia?.(q)
    if (!mq) return
    const on = () => setReduced(mq.matches)
    mq.addEventListener?.('change', on)
    return () => mq.removeEventListener?.('change', on)
  }, [])
  return reduced
}

/** Index de frame courant (0-based) ou -1 si pas d'animation. */
function useFrames(pose: Pose, enabled: boolean, el: RefObject<Element>): number {
  const [durations, setDurations] = useState<number[] | null>(null)
  const [frame, setFrame] = useState(0)
  const cur = useRef(0)
  const [visible, setVisible] = useState(true)
  const [tabVisible, setTabVisible] = useState(() => typeof document === 'undefined' || !document.hidden)

  useEffect(() => {
    if (!enabled) return
    let alive = true
    loadManifest().then((m) => {
      const d = m[pose]
      if (!alive) return
      if (d && d.length > 1) { preload(pose, d.length); setDurations(d) } else setDurations(null)
    })
    cur.current = 0
    setFrame(0)
    return () => { alive = false }
  }, [pose, enabled])

  useEffect(() => {
    const onVis = () => setTabVisible(!document.hidden)
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

  useEffect(() => {
    const node = el.current
    if (!enabled || !node || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver((entries) => setVisible(entries.some((e) => e.isIntersecting)))
    io.observe(node)
    return () => io.disconnect()
  }, [enabled, el, durations])

  const running = enabled && !!durations && visible && tabVisible
  useEffect(() => {
    if (!running || !durations) return
    let raf = 0
    let last = performance.now()
    let i = cur.current % durations.length
    const tick = (now: number) => {
      if (now - last >= durations[i]) {
        // rattrape au plus une frame (pas de saut après une longue pause)
        last = now - Math.min(now - last - durations[i], durations[i])
        i = (i + 1) % durations.length
        cur.current = i
        setFrame(i)
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [running, durations])

  return durations ? frame : -1
}

// ---------------------------------------------------------------- repli : ébauche 20 px
type Px = [number, number, string]
const rect = (x: number, y: number, w: number, h: number, c: string): Px[] => {
  const o: Px[] = []; for (let i = 0; i < w; i++) for (let j = 0; j < h; j++) o.push([x + i, y + j, c]); return o
}
const ACC: Partial<Record<Pose, Px[]>> = {
  lit: [...rect(6, 14, 8, 4, 'K'), ...rect(7, 15, 3, 2, 'p'), ...rect(10, 15, 3, 2, 'p')],
  loupe: [...rect(15, 11, 3, 1, 'K'), ...rect(14, 12, 1, 3, 'K'), ...rect(18, 12, 1, 3, 'K'), ...rect(15, 15, 3, 1, 'K'), ...rect(15, 12, 3, 3, 'H'), ...rect(18, 16, 1, 2, 'a')],
  graphe: [...rect(0, 2, 2, 2, 'A'), ...rect(18, 1, 2, 2, 'A'), ...rect(17, 15, 2, 2, 'A'), [2, 3, 'a'], [3, 3, 'a'], [16, 2, 'a'], [17, 2, 'a'], [18, 12, 'a'], [18, 13, 'a'], [18, 14, 'a']],
  forge: [...rect(0, 14, 4, 2, 'K'), ...rect(16, 14, 4, 2, 'K'), ...rect(5, 16, 10, 1, 'A'), ...rect(3, 17, 14, 2, 'K')],
  trophee: [...rect(0, 4, 4, 1, 'A'), ...rect(1, 5, 2, 3, 'A'), ...rect(0, 8, 4, 1, 'a')],
  reflechit: [...rect(16, 1, 1, 1, 'K'), ...rect(17, 3, 1, 1, 'K'), ...rect(18, 0, 2, 2, 'W'), ...rect(17, 0, 1, 2, 'K')],
  contente: [...rect(1, 1, 1, 3, 'A'), ...rect(0, 2, 3, 1, 'A'), ...rect(18, 3, 1, 3, 'A'), ...rect(17, 4, 3, 1, 'A')],
  inquiete: [...rect(17, 5, 1, 2, 'H'), ...rect(16, 7, 3, 2, 'H'), ...rect(4, 6, 4, 1, 'K'), ...rect(12, 6, 4, 1, 'K')],
}

function sprite(pose: Pose): Px[] {
  const px: Px[] = []
  BASE.forEach((row, y) => [...row].forEach((ch, x) => { if (ch !== ' ') px.push([x, y, ch]) }))
  const acc = ACC[pose] ?? []
  const over = new Set(acc.map(([x, y]) => x + ',' + y))
  const kept = px.filter(([x, y]) => !over.has(x + ',' + y) || pose === 'inquiete')
  if (pose === 'contente') {
    const calm = kept.map(([x, y, c]) => (c === 'W' || c === 'D') && y >= 7 && y <= 8 ? [x, y, 'L'] as Px : [x, y, c] as Px)
    return [...calm, ...rect(3, 7, 3, 1, 'K'), [3, 8, 'K'], [5, 8, 'K'], ...rect(13, 7, 3, 1, 'K'), [13, 8, 'K'], [15, 8, 'K'], ...acc] as Px[]
  }
  return [...kept, ...acc]
}

// ---------------------------------------------------------------- composant
export function Krakie({ pose = 'accueil', size = 64, title, float = true, animated = true, className = '' }: {
  pose?: Pose; size?: number; title?: string; float?: boolean
  /** Boucle de frames (défaut true). Ignoré si l'utilisateur préfère réduire les animations. */
  animated?: boolean; className?: string
}) {
  const [svgOk, setSvgOk] = useState(true)
  const [animOk, setAnimOk] = useState(true)
  const reduced = usePrefersReducedMotion()
  const ref = useRef<HTMLImageElement>(null)
  const frame = useFrames(pose, animated && !reduced && svgOk && animOk, ref)
  useEffect(() => { setAnimOk(true); setSvgOk(true) }, [pose])

  // flottement CSS désactivé quand les frames animent déjà, ou en mouvement réduit
  const cls = `krakie ${float && frame < 0 && !reduced ? 'float' : ''} ${className}`
  const common = { width: size, height: size, className: cls, role: title ? 'img' : undefined, 'aria-label': title, 'aria-hidden': title ? undefined : true } as const
  if (svgOk) {
    const src = frame >= 0 ? frameUrl(pose, frame + 1) : `/krakie/${pose}.svg`
    return <img {...common} data-pose={pose} ref={ref} src={src} alt={title ?? ''} draggable={false}
      onError={() => (frame >= 0 ? setAnimOk(false) : setSvgOk(false))} style={{ imageRendering: 'pixelated' }} />
  }
  return (
    <svg {...common} viewBox="0 0 20 19" shapeRendering="crispEdges" preserveAspectRatio="xMidYMid meet">
      {sprite(pose).map(([x, y, c], i) => <rect key={i} x={x} y={y} width={1} height={1} fill={PAL[c] ?? c} />)}
    </svg>
  )
}

// ---------------------------------------------------------------- forge + trophée (traitement en cours / fin réussie)
/** Vrai pendant `ms` après la fin réussie d'un traitement (busy passe de true à false avec ok). */
export function useResultFlash(busy: boolean, ok: boolean, ms = 2000): boolean {
  const [on, setOn] = useState(false)
  const prev = useRef(busy)
  useEffect(() => {
    const was = prev.current
    prev.current = busy
    if (was && !busy && ok) {
      setOn(true)
      const id = setTimeout(() => setOn(false), ms)
      return () => clearTimeout(id)
    }
    if (busy) setOn(false)
  }, [busy, ok, ms])
  return on
}

/** Krakie forgeronne pendant le traitement, puis brièvement avec le trophée à la fin. Image fixe si mouvement réduit (géré par <Krakie>). */
export function KrakieStatus({ busy, done, label, doneLabel, size = 64, donePose = 'trophee' }: { busy: boolean; done: boolean; label: string; doneLabel: string; size?: number; donePose?: 'trophee' | 'inquiete' }) {
  if (!busy && !done) return null
  return (
    <div className={'kstatus ' + (busy ? 'busy' : 'done')} role="status" aria-live="polite" data-kstatus={busy ? 'forge' : donePose}>
      <Krakie pose={busy ? 'forge' : donePose} size={size} float={false} />
      <span>{busy ? label : doneLabel}</span>
    </div>
  )
}
