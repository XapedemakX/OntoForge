import { useEffect, useRef } from 'react'

/*
 * Krakie et son récif (bouton flottant en bas à droite). L37b : plus de « boîte » d'eau — le récif pousse depuis le bord bas de la fenêtre,
 * ses couleurs viennent des jetons de l'app (--accent, --panel, --ink, --lost, --review-edge) et suivent donc les thèmes clair et sombre.
 * Deux canvas à résolution « pixel » (échelle 1,5 sur desktop, 1 sur mobile) : récif + micro-bulles derrière, Krakie devant.
 * Règle L30 : jamais de rotation ni de cisaillement du bitmap — la tête et le corps (rangées 0-19) sont posés à une position entière,
 * l'inclinaison est un décalage d'un pixel des tentacules (rangées 20-31), avec hystérésis.
 * Une seule boucle requestAnimationFrame (≈ 20 images/s), en pause quand l'onglet est caché ; image fixe si prefers-reduced-motion.
 * Zone cliquable = Krakie + récif : le bouton est transparent aux clics ailleurs (voir hitTest et dock.css).
 */

export type AquariumState = 'idle' | 'busy' | 'happy' | 'worried'
type Rows = string[]

const CORAL: Rows = [
  'H     H   ',
  'L  H  L  H',
  'L  L  L  L',
  'LL L LL LL',
  ' LLLLLLLL ',
  '  LBLLBL  ',
  '   BBBB   ',
  '   BDDB   ',
]
const FAN: Rows = [
  '  C  C  C  ',
  ' C C CC C C',
  ' CCCCCCCCC ',
  '  CcCCCcC  ',
  '   cCCCc   ',
  '    ccc    ',
  '     c     ',
]
const STAR: Rows = [
  '   a   ',
  '  aAa  ',
  'aaAAAaa',
  ' aAaAa ',
  ' aa aa ',
  'a     a',
]
const TUBE: Rows = [
  'H  H',
  'LHHL',
  'L  L',
  'L  B',
  'LBBB',
]

// pose -> durées (ms) par image, copiées de /krakie/anim/manifest.json (les poses du jeu et l'accueil existent déjà)
const FRAMES: Record<string, number[]> = {
  nage: [95, 95, 95, 95, 95, 95],
  accueil: [260, 220, 140, 220],
  reflechit: [320, 240, 320, 160],
  contente: [160, 120, 160, 120],
  inquiete: [240, 200, 200, 200],
}
const imgs = new Map<string, HTMLImageElement>()
function frameImg(pose: string, n: number): HTMLImageElement | null {
  const u = `/krakie/anim/${pose}-${n + 1}.svg`
  let im = imgs.get(u)
  if (!im) { im = new Image(); im.src = u; imgs.set(u, im) }
  return im.complete && im.naturalWidth > 0 ? im : null
}

type RGB = [number, number, number]
const parse = (c: string, fb: RGB): RGB => {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(c.trim()); if (!m) return fb
  let h = m[1]; if (h.length === 3) h = [...h].map(x => x + x).join('')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}
const mix = (a: RGB, b: RGB, p: number): string => `rgb(${a.map((v, i) => Math.round(v * (1 - p) + b[i] * p)).join(',')})`

/** Palette du récif dérivée des jetons de l'app (relue quand le thème change). */
function readPalette(): { pal: Record<string, string>; bubble: string; alpha: number; sig: string } {
  const cs = getComputedStyle(document.documentElement), v = (n: string) => cs.getPropertyValue(n).trim()
  const accent = parse(v('--accent'), [11, 110, 110]), panel = parse(v('--panel'), [255, 255, 255]), ink = parse(v("--ink"), [20, 33, 61])
  const lost = parse(v('--lost'), [180, 35, 24]), amber = parse(v('--review-edge'), [242, 169, 0]), line = parse(v('--line-strong'), [185, 196, 209])
  const dark = panel[0] < 90
  const pal: Record<string, string> = {
    B: mix(accent, panel, 0.15), D: dark ? mix(accent, panel, 0.55) : mix(accent, ink, 0.3), L: mix(accent, panel, dark ? 0.1 : 0.32), H: mix(accent, panel, dark ? 0.35 : 0.6),
    C: mix(lost, panel, dark ? 0.35 : 0.55), c: mix(lost, panel, dark ? 0.62 : 0.3),
    A: mix(amber, panel, dark ? 0.3 : 0.42), a: mix(amber, panel, dark ? 0.55 : 0.18),
    s: mix(line, panel, dark ? 0.45 : 0.35),
  }
  return { pal, bubble: mix(accent, panel, dark ? 0.7 : 0.1), alpha: dark ? 0.8 : 0.88, sig: [v('--accent'), v('--panel'), v('--lost')].join('|') }
}

type Bubble = { x: number; y: number; v: number; a: number; s: number; ph: number; wait: number }

/** Test de zone cliquable (coordonnées logiques) : Krakie (avec une marge) ou le récif. */
export function Aquarium({ state, hovered, onCursor, width, height, scale, reefW, reefH }: {
  state: AquariumState; hovered: boolean; scale: number; width: number; height: number; reefW: number; reefH: number
  onCursor: React.MutableRefObject<{ x: number; y: number } | null>
}) {
  const back = useRef<HTMLCanvasElement>(null)
  const front = useRef<HTMLCanvasElement>(null)
  const ring = useRef<HTMLSpanElement>(null)
  const live = useRef({ state, hovered }); live.current = { state, hovered }

  useEffect(() => {
    const cb = back.current, cf = front.current; if (!cb || !cf) return
    const gb = cb.getContext('2d'), gf = cf.getContext('2d'); if (!gb || !gf) return
    gb.imageSmoothingEnabled = false; gf.imageSmoothingEnabled = false
    const btn = cb.parentElement as HTMLElement | null
    const W = width, H = height, S = 32, RW = reefW, RX = W - RW, RH = reefH
    const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    let reduced = !!mq?.matches
    let P = readPalette()

    const rnd = (a: number, b: number) => a + Math.random() * (b - a)
    // micro-bulles : 3 au plus, rares ; elles montent d'environ 80 px logiques (≈ 120 px à l'écran) en s'estompant
    const RISE = 80
    const bubbles: Bubble[] = Array.from({ length: 3 }, (_, i) => ({ x: 0, y: -1, v: 9, a: 0.8, s: i === 0 ? 2 : 1, ph: rnd(0, 6), wait: 1 + i * 2.2 }))
    const swimTop = 14, swimBottom = H - RH - S + 12
    const kr = { x: W * 0.4 - S / 2, y: swimTop + 10, vx: 0, vy: 0, tx: W * 0.4 - S / 2, ty: swimTop + 10, wait: 1.2, lean: 0 }
    const lim = { x0: 0, x1: W - S - 4, y0: swimTop, y1: swimBottom }

    const blit = (g: CanvasRenderingContext2D, rows: Rows, x: number, y: number) => {
      rows.forEach((row, j) => [...row].forEach((ch, i) => { if (ch !== ' ') { g.fillStyle = P.pal[ch]; g.fillRect(x + i, y + j, 1, 1) } }))
    }
    /** Algue ondulante : décalage entier d'un pixel par ruban de 3 rangées, qui se propage avec le temps. */
    const weed = (g: CanvasRenderingContext2D, x: number, h: number, tick: number, col = 'L') => {
      const wave = [0, 0, 1, 1, 1, 0, 0, -1, -1, -1]
      g.fillStyle = P.pal[col]
      for (let r = 0; r < h; r++) {
        const k = Math.min(1, r / (h * 0.6))
        const off = k > 0.2 ? wave[(tick + Math.floor(r / 3)) % 10] : 0
        g.fillRect(x + off, H - 3 - r, 2, 1)
      }
    }
    // récif : sort du bord bas (rangée H-1 = bord de la fenêtre). Petit monticule de sable collé au bord, aucune ligne de sol.
    const reefLayer = () => {
      const g = document.createElement('canvas'); g.width = W; g.height = H
      const c = g.getContext('2d')!
      // roches : un lit continu de 3 à 6 rangées, irrégulier, qui sort du bord bas (pas de ligne de sol)
      for (let x = 0; x < RW; x++) {
        const h = 4 + Math.round(1.6 * Math.sin(x * 0.31) + 1.2 * Math.sin(x * 0.83 + 1))
        for (let r = 0; r < h; r++) { c.fillStyle = r === h - 1 ? P.pal.L : r === h - 2 ? P.pal.B : P.pal.D; c.fillRect(RX + x, H - 1 - r, 1, 1) }
      }
      const base = H - 5, mir = (rows: Rows) => rows.map(r => [...r].reverse().join(''))
      blit(c, CORAL, RX + Math.round(RW * 0.06), base - CORAL.length + 2)
      blit(c, mir(CORAL), RX + Math.round(RW * 0.66), base - CORAL.length + 3)
      blit(c, STAR, RX + Math.round(RW * 0.38), base - STAR.length + 3)
      blit(c, FAN, RX + Math.round(RW * 0.5), base - FAN.length + 3)
      blit(c, TUBE, RX + Math.round(RW * 0.84), base - TUBE.length + 3)
      return g
    }
    let reef = reefLayer()

    let raf = 0, last = performance.now(), acc = 0, t = 0, themeT = 0, frameClock = 0

    const poseNow = (): string => {
      const { state: st, hovered: hv } = live.current
      if (st === 'busy') return 'reflechit'
      if (hv) return 'accueil'
      if (st === 'happy') return 'contente'
      if (st === 'worried') return 'inquiete'
      return 'nage'
    }

    const drawBack = () => {
      gb.clearRect(0, 0, W, H)
      gb.globalAlpha = P.alpha
      gb.drawImage(reef, 0, 0)
      const tick = Math.floor(t * 1.4)
      weed(gb, RX + Math.round(RW * 0.2), 15, tick)
      weed(gb, RX + Math.round(RW * 0.3), 11, tick + 3, 'B')
      weed(gb, RX + Math.round(RW * 0.62), 16, tick + 2)
      weed(gb, RX + Math.round(RW * 0.77), 10, tick + 5, 'B')
      weed(gb, RX + Math.round(RW * 0.95), 14, tick + 4)
      gb.fillStyle = P.bubble
      for (const b of bubbles) {
        if (b.wait > 0) continue
        const k = (H - 12 - b.y) / RISE // 0 → 1 pendant la montée
        gb.globalAlpha = b.a * Math.max(0, 1 - k) * Math.min(1, k * 8 + 0.2)
        const x = Math.round(b.x) + (Math.sin(b.ph + b.y * 0.15) > 0.4 ? 1 : 0)
        gb.fillRect(x, Math.round(b.y), b.s, b.s)
      }
      gb.globalAlpha = 1
    }

    const drawKrakie = () => {
      gf.clearRect(0, 0, W, H)
      const pose = poseNow(), d = FRAMES[pose] ?? FRAMES.nage
      let n = 0
      if (!reduced) { const total = d.reduce((a, b) => a + b, 0); let m = (frameClock * 1000) % total; while (m >= d[n]) { m -= d[n]; n++ } }
      const im = frameImg(pose, n) ?? frameImg('nage', 0)
      const bob = reduced || pose === 'reflechit' ? 0 : Math.round(Math.sin(t * 1.6) * 1)
      const x = Math.round(kr.x), y = Math.round(kr.y) + bob, off = reduced ? 0 : kr.lean
      if (ring.current) ring.current.style.transform = `translate(${(x + 4) * scale}px, ${(y + 2) * scale}px)`
      if (!im) return
      gf.drawImage(im, 0, 0, S, 20, x, y, S, 20)
      gf.drawImage(im, 0, 20, S, S - 20, x + off, y + 20, S, S - 20)
    }

    const step = (dt: number) => {
      t += dt; frameClock += dt
      const { state: st, hovered: hv } = live.current
      const boost = st === 'busy' ? 1.6 : 1
      for (const b of bubbles) {
        if (b.wait > 0) { b.wait -= dt * boost; if (b.wait <= 0) { b.x = RX + rnd(RW * 0.15, RW * 0.9); b.y = H - 12; b.v = rnd(8, 12); b.a = rnd(0.6, 0.9) } continue }
        b.y -= b.v * dt * boost
        if (H - 12 - b.y > RISE) b.wait = rnd(2.5, 7)
      }
      const stop = hv || st === 'busy'
      const cur = onCursor.current
      if (stop) { kr.vx *= Math.pow(0.02, dt); kr.vy *= Math.pow(0.02, dt) }
      else {
        const dx = kr.tx - kr.x, dy = kr.ty - kr.y, dist = Math.hypot(dx, dy)
        if (kr.wait > 0) { kr.wait -= dt; kr.vx *= Math.pow(0.05, dt); kr.vy *= Math.pow(0.05, dt) }
        else if (dist < 2) { kr.wait = rnd(1.4, 3.6); kr.tx = rnd(lim.x0, lim.x1); kr.ty = rnd(lim.y0, lim.y1) }
        else { const sp = Math.min(11, 3 + dist * 0.5); kr.vx += (dx / dist * sp - kr.vx) * Math.min(1, dt * 1.6); kr.vy += (dy / dist * sp - kr.vy) * Math.min(1, dt * 1.6) }
      }
      kr.x = Math.min(lim.x1, Math.max(lim.x0, kr.x + kr.vx * dt)); kr.y = Math.min(lim.y1, Math.max(lim.y0, kr.y + kr.vy * dt))
      let intent = kr.vx
      if (hv && cur) { const dx = cur.x - (kr.x + S / 2); intent = Math.abs(dx) > 5 ? Math.sign(dx) * 6 : 0 }
      const a = Math.abs(intent)
      if (kr.lean === 0 ? a > 3 : a < 1.4) kr.lean = kr.lean === 0 ? -Math.sign(intent) : 0
    }

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      const dt = Math.min(0.1, (now - last) / 1000); last = now; acc += dt
      if (acc < 0.045) return
      const d = acc; acc = 0
      themeT += d; if (themeT > 1.5) { themeT = 0; const np = readPalette(); if (np.sig !== P.sig) { P = np; reef = reefLayer() } }
      step(d); drawBack(); drawKrakie()
    }
    const staticDraw = () => { drawBack(); drawKrakie() }
    const start = () => { if (raf || reduced || document.hidden) return; last = performance.now(); acc = 0; raf = requestAnimationFrame(frame) }
    const halt = () => { if (raf) cancelAnimationFrame(raf); raf = 0 }
    const onVis = () => { if (document.hidden) halt(); else start() }
    const onMq = () => { reduced = !!mq?.matches; halt(); if (reduced) { kr.lean = 0; staticDraw() } else start() }
    document.addEventListener('visibilitychange', onVis)
    mq?.addEventListener?.('change', onMq)

    // zone cliquable : le bouton laisse passer les clics (pointer-events:none) sauf sur Krakie et le récif
    const hit = (cx: number, cy: number) => {
      const r = cb.getBoundingClientRect(), x = (cx - r.left) / scale, y = (cy - r.top) / scale
      if (x < 0 || y < 0 || x > W || y > H) return false
      if (x >= kr.x - 3 && x <= kr.x + S + 3 && y >= kr.y - 2 && y <= kr.y + S + 3) return true
      return x >= RX && y >= H - RH
    }
    const onMove = (e: PointerEvent) => { if (!btn) return; const h = hit(e.clientX, e.clientY); btn.classList.toggle('aq-hit', h) }
    // toucher / clic sans mouvement préalable : on relaie vers le bouton si la cible est dans la zone
    const onClick = (e: MouseEvent) => { if (btn && !btn.contains(e.target as Node) && hit(e.clientX, e.clientY)) { e.stopPropagation(); btn.click() } }
    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('click', onClick, true)

    // images : on redessine dès qu'elles arrivent (utile en mouvement réduit)
    const warm = window.setInterval(() => { if (reduced) staticDraw() }, 400)
    // mouvement réduit : Krakie immobile, bulles figées à mi-montée
    if (reduced) { kr.x = (W - S) / 2; kr.y = swimTop + 18; bubbles.forEach((b, i) => { b.wait = 0; b.x = RX + RW * (0.3 + i * 0.25); b.y = H - 12 - RISE * (0.25 + i * 0.2); b.a = 0.7 }); staticDraw() } else start()
    return () => { halt(); document.removeEventListener('visibilitychange', onVis); mq?.removeEventListener?.('change', onMq); window.removeEventListener('pointermove', onMove); window.removeEventListener('click', onClick, true); clearInterval(warm) }
  }, [width, height, reefW, reefH, scale, onCursor])

  const css = { width: width * scale, height: height * scale, imageRendering: 'pixelated' as const }
  return (
    <>
      <canvas ref={back} className="aq-reef" width={width} height={height} style={css} aria-hidden="true" />
      <canvas ref={front} className="aq-krakie" width={width} height={height} style={css} aria-hidden="true" />
      <span ref={ring} className="aq-ring" aria-hidden="true" style={{ width: 24 * scale, height: 28 * scale }} />
    </>
  )
}
