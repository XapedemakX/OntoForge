import { drawText, norm, textCanvas, textWidth } from './font'
import { ALL, options, type Kind } from './content'
import type { Sfx } from './audio'
import type { GamePose, KrakieSprites } from './sprites'

export type Phase = 'ready' | 'playing' | 'paused' | 'over'
export interface HudState { score: number; lives: number; level: number; triples: number; chain: string[]; shield: boolean }
export const EXPRESSIONS: Record<GamePose, string> = { nage: 'neutral', nage_clin: 'wink', nage_ravie: 'delight', nage_surprise: 'surprise', nage_grimace: 'grimace', nage_inquiete: 'worried' }
export interface Result { score: number; triples: number; level: number }
export interface EngineOpts {
  canvas: HTMLCanvasElement; reduced: boolean; sfx: Sfx; sprites: () => KrakieSprites; labels: { score: string; level: string }
  on: { phase(p: Phase): void; hud(h: HudState): void; say(key: string, params?: Record<string, string | number>): void; over(r: Result): void }
}

// Palette lagon d'OntoForge (identique aux sprites de Krakie)
const C = {
  ink: '#0B2B33', amber: '#E0A23B', amberHi: '#F3C468', mint: '#7FDCD4', mintHi: '#BFF3EE', lav: '#A9B8F5', lavHi: '#D3DBFB',
  red: '#D6453D', redD: '#8F2420', paper: '#F5E6C8', sand: '#C9B994', sandD: '#A89874', grey: '#8A99A3', greyHi: '#B8C4CB',
  glass: '#CDEFF5', purple: '#C79BF2', purpleHi: '#E2C8FA', lag: '#147A77', lagL: '#1FA39E', blue: '#3E5C9A', white: '#FFFFFF',
}
const KCOL: Record<Kind, [string, string]> = { S: [C.amber, C.amberHi], P: [C.mint, C.mintHi], O: [C.lav, C.lavHi] }

type ItemType = 'tok' | 'bad' | 'iri' | 'inf' | 'shacl'
interface Item { type: ItemType; kind?: Kind; label: string; x: number; y: number; w: number; h: number; vy: number; ph: number; spr: HTMLCanvasElement }
interface Part { x: number; y: number; vx: number; vy: number; life: number; max: number; c: string; s: number }
interface Pop { x: number; y: number; text: string; color: string; life: number }
interface Tri { s: string; p: string; o: string; t: number }

const mk = (w: number, h: number) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c }
const rnd = (a: number, b: number) => a + Math.random() * (b - a)
const pick = <T,>(a: T[]) => a[Math.floor(Math.random() * a.length)]
function hash(s: string) { let h = 2166136261; for (const ch of s) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619) } return (h >>> 0) / 4294967295 }

// ------------------------------------------------------------------ sprites pixel art des éléments
type Shape = 'round' | 'square' | 'arrow'
function fillShape(x: CanvasRenderingContext2D, color: string, ox: number, oy: number, w: number, h: number, shape: Shape, c: number) {
  x.fillStyle = color
  const mid = (h - 1) / 2
  for (let r = 0; r < h; r++) {
    const d = Math.min(r, h - 1 - r)
    const l = Math.max(0, c - d)
    const rt = shape === 'arrow' ? Math.round(Math.abs(r - mid)) : l
    x.fillRect(ox + l, oy + r, w - l - rt, 1)
  }
}
const spriteCache = new Map<string, HTMLCanvasElement>()
function pill(kind: Kind | 'inf' | 'shacl' | 'iri', label: string): HTMLCanvasElement {
  const key = kind + '|' + label
  const hit = spriteCache.get(key); if (hit) return hit
  const text = norm(label), tw = textWidth(text), h = 9
  const shape: Shape = kind === 'P' ? 'arrow' : kind === 'O' ? 'square' : 'round'
  const w = tw + (kind === 'P' ? 8 : 7)
  const c = mk(w, h), x = c.getContext('2d')!
  const [fill, hi] = kind === 'S' || kind === 'P' || kind === 'O' ? KCOL[kind] : kind === 'inf' ? [C.purple, C.purpleHi] : kind === 'shacl' ? [C.glass, C.white] : [C.grey, C.greyHi]
  const out = kind === 'inf' || kind === 'shacl' ? C.white : C.ink
  fillShape(x, out, 0, 0, w, h, shape, shape === 'round' ? 2 : 1)
  fillShape(x, fill, 1, 1, w - 2, h - 2, shape, shape === 'round' ? 1 : 0)
  x.fillStyle = hi; x.fillRect(3, 1, Math.max(1, w - (kind === 'P' ? 9 : 6)), 1)
  x.drawImage(textCanvas(text, kind === 'shacl' ? C.blue : C.ink), 3, 2)
  if (kind === 'iri') { // fissure rouge en zigzag
    x.fillStyle = C.red
    const cx = Math.floor(w / 2) - 1
    ;[0, 0, 1, 1, 0, 0, -1, -1, 0].forEach((o, r) => x.fillRect(cx + o, r, 1, 1))
  }
  spriteCache.set(key, c); return c
}

function bubbleSprite(): HTMLCanvasElement {
  const hit = spriteCache.get('bad'); if (hit) return hit
  const c = mk(13, 13), x = c.getContext('2d')!
  for (let j = 0; j < 13; j++) for (let i = 0; i < 13; i++) {
    const d = Math.hypot(i - 6, j - 6)
    if (d <= 6.4) { x.fillStyle = d > 5.3 ? C.ink : j > 8 ? C.redD : C.red; x.fillRect(i, j, 1, 1) }
  }
  x.fillStyle = '#FF9A8F'; x.fillRect(3, 3, 2, 1); x.fillRect(3, 4, 1, 1)
  x.drawImage(textCanvas('!', C.white), 5, 4)
  spriteCache.set('bad', c); return c
}
const HEART = ['.XX.XX.', 'XXXXXXX', 'XXXXXXX', '.XXXXX.', '..XXX..', '...X...']
function heartSprite(on: boolean): HTMLCanvasElement {
  const key = 'heart' + on; const hit = spriteCache.get(key); if (hit) return hit
  const c = mk(7, 6), x = c.getContext('2d')!
  HEART.forEach((row, j) => [...row].forEach((ch, i) => { if (ch === 'X') { x.fillStyle = on ? (j < 2 && i < 3 ? '#FF8A80' : C.red) : '#1F4A50'; x.fillRect(i, j, 1, 1) } }))
  spriteCache.set(key, c); return c
}

function line(x: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number) {
  x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1)
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1
  let err = dx + dy
  for (let n = 0; n < 600; n++) {
    x.fillRect(x0, y0, 1, 1)
    if (x0 === x1 && y0 === y1) break
    const e2 = 2 * err
    if (e2 >= dy) { err += dy; x0 += sx }
    if (e2 <= dx) { err += dx; y0 += sy }
  }
}

export class Engine {
  W = 220; H = 260; scale = 3
  phase: Phase = 'ready'
  private ctx: CanvasRenderingContext2D
  private bg: HTMLCanvasElement | null = null
  private raf = 0; private last = 0; private clock = 0
  // état de partie
  private score = 0; private lives = 3; private triples = 0; private level = 1
  private chain: string[] = []
  private graph: Tri[] = []
  private items: Item[] = []; private parts: Part[] = []; private pops: Pop[] = []
  private bubbles: { x: number; y: number; r: number; v: number }[] = []
  private kx = 110; private face = 1
  private keyL = false; private keyR = false; private ptr: number | null = null
  private spawnT = 0.6; private bonusT = 6
  private invuln = 0; private shield = false; private shake = 0; private flash = 0
  private poseT = 0; private pose: GamePose = 'nage'; private animT = 0
  private lean = 0; private trail = 0; private infT = 0; private vx = 0
  private overT = 0

  constructor(private o: EngineOpts) {
    this.ctx = o.canvas.getContext('2d')!
    for (let i = 0; i < 16; i++) this.bubbles.push({ x: Math.random() * 260, y: Math.random() * 340, r: Math.random() < 0.3 ? 2 : 1, v: rnd(6, 16) })
  }

  // ---------------------------------------------------------------- cycle de vie
  start() { this.loop(performance.now()) }
  destroy() { cancelAnimationFrame(this.raf) }
  private setPhase(p: Phase) { this.phase = p; this.o.on.phase(p) }
  newGame() {
    this.score = 0; this.lives = 3; this.triples = 0; this.level = 1; this.chain = []; this.graph = []
    this.items = []; this.parts = []; this.pops = []; this.spawnT = 0.5; this.bonusT = 7; this.invuln = 0; this.shield = false
    this.shake = 0; this.flash = 0; this.pose = 'nage'; this.poseT = 0; this.infT = 0; this.lean = 0; this.trail = 0; this.vx = 0; this.kx = this.W / 2
    this.setPhase('playing'); this.emit()
  }
  pause() { if (this.phase === 'playing') this.setPhase('paused') }
  resume() { if (this.phase === 'paused') { this.last = performance.now(); this.setPhase('playing') } }
  setKeys(l: boolean, r: boolean) { this.keyL = l; this.keyR = r }
  setPointer(clientX: number | null) {
    if (clientX === null) { this.ptr = null; return }
    const b = this.o.canvas.getBoundingClientRect()
    this.ptr = ((clientX - b.left) / b.width) * this.W
  }
  /** Taille disponible (px CSS) → échelle entière, résolution logique du canvas. */
  resize(availW: number, availH: number) {
    let s = 1
    for (let c = 6; c >= 1; c--) if (Math.floor(availW / c) >= 150 && Math.floor(availH / c) >= 200) { s = c; break }
    this.scale = s
    this.W = Math.max(120, Math.min(220, Math.floor(availW / s))); this.H = Math.max(160, Math.min(340, Math.floor(availH / s)))
    const cv = this.o.canvas
    cv.width = this.W; cv.height = this.H
    cv.style.width = this.W * s + 'px'; cv.style.height = this.H * s + 'px'
    this.ctx = cv.getContext('2d')!; this.ctx.imageSmoothingEnabled = false
    this.bg = this.makeBg()
    this.kx = Math.min(Math.max(this.kx, 16), this.W - 16)
    this.items.forEach(i => { i.x = Math.min(i.x, this.W - i.w - 2) })
    this.bubbles.forEach(b => { b.x = Math.min(b.x, this.W); b.y = Math.min(b.y, this.H) })
  }
  /** Instantané pour la recette automatisée (lecture seule). */
  snapshot() {
    const opt = options(this.chain)
    return { phase: this.phase, W: this.W, H: this.H, kx: this.kx, score: this.score, lives: this.lives, level: this.level, triples: this.triples, chain: this.chain, want: opt.labels, kind: opt.kind,
      items: this.items.map(i => ({ type: i.type, kind: i.kind, label: i.label, cx: i.x + i.w / 2, y: i.y })) }
  }
  /** Expression courante de Krakie pour la recette (fixe sous mouvement réduit). */
  state() {
    const pose = this.curPose
    return { expression: EXPRESSIONS[pose], pose, phase: this.phase, shield: this.shield, inference: this.infT > 0, lean: this.o.reduced ? 0 : Math.round(this.lean * 10) / 10, lives: this.lives, score: this.score, reduced: this.o.reduced }
  }
  /** Pose affichée : expression brève en cours, sinon inquiète à une seule vie (ou fin de partie), sinon nage. */
  private get curPose(): GamePose {
    if (this.phase === 'over') return 'nage_inquiete'
    if (this.poseT > 0) return this.pose
    return this.phase === 'playing' && this.lives === 1 ? 'nage_inquiete' : 'nage'
  }
  private emit() { this.o.on.hud({ score: this.score, lives: this.lives, level: this.level, triples: this.triples, chain: [...this.chain], shield: this.shield }) }
  private say(k: string, p?: Record<string, string | number>) { this.o.on.say(k, p) }

  // ---------------------------------------------------------------- boucle
  private loop = (now: number) => {
    this.raf = requestAnimationFrame(this.loop)
    const dt = Math.min(0.05, Math.max(0, (now - (this.last || now)) / 1000)); this.last = now
    if (this.phase !== 'paused') this.clock += dt
    if (this.phase === 'over') { this.flash = Math.max(0, this.flash - dt); this.shake = Math.max(0, this.shake - dt) }
    if (this.phase === 'playing') this.update(dt)
    else if (this.phase === 'over') { this.overT += dt; this.updateParts(dt) }
    else if (this.phase === 'ready') this.updateAmbient(dt)
    this.draw()
  }

  private get fallSpeed() { return Math.min(125, 42 + 7 * this.level) * (this.o.reduced ? 0.6 : 1) }
  private updateAmbient(dt: number) {
    if (this.o.reduced) return
    for (const b of this.bubbles) { b.y -= b.v * dt; if (b.y < -3) { b.y = this.H + 3; b.x = Math.random() * this.W } }
  }
  private updateParts(dt: number) {
    for (const p of this.parts) { p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 40 * dt; p.life -= dt }
    this.parts = this.parts.filter(p => p.life > 0)
    for (const p of this.pops) { p.y -= 14 * dt; p.life -= dt }
    this.pops = this.pops.filter(p => p.life > 0)
  }

  private update(dt: number) {
    this.updateAmbient(dt); this.updateParts(dt)
    if (this.poseT > 0) { this.poseT -= dt; if (this.poseT <= 0) this.pose = 'nage' }
    this.infT = Math.max(0, this.infT - dt)
    this.invuln = Math.max(0, this.invuln - dt); this.shake = Math.max(0, this.shake - dt); this.flash = Math.max(0, this.flash - dt)
    // déplacement de Krakie
    const maxV = 120
    let v = 0
    if (this.ptr !== null) { const d = this.ptr - this.kx; v = Math.max(-260, Math.min(260, d * 9)); if (Math.abs(d) < 0.6) v = 0 }
    else v = ((this.keyR ? 1 : 0) - (this.keyL ? 1 : 0)) * maxV
    this.kx = Math.min(this.W - 14, Math.max(14, this.kx + v * dt))
    if (v > 1) this.face = 1; else if (v < -1) this.face = -1
    this.vx = v
    this.lean += (Math.max(-1, Math.min(1, v / 110)) * 3 - this.lean) * Math.min(1, dt * 12)
    this.animT += dt * 1000 * (Math.abs(v) > 5 ? 1.7 : 0.8)
    // apparitions
    this.spawnT -= dt
    this.bonusT -= dt
    if (this.spawnT <= 0) { this.spawn(); this.spawnT = Math.max(0.5, 1.05 - 0.045 * this.level) * (this.o.reduced ? 1.35 : 1) * rnd(0.85, 1.15) }
    // chute + collisions
    const hz = { x0: this.kx - 10, x1: this.kx + 10, y0: this.ky + 5, y1: this.ky + 27 }
    for (const it of this.items) {
      it.y += it.vy * dt
      if (it.type === 'bad' && !this.o.reduced) it.x += Math.sin(this.clock * 3 + it.ph) * 8 * dt
      if (it.x + it.w > hz.x0 && it.x < hz.x1 && it.y + it.h > hz.y0 && it.y < hz.y1) { it.y = 9999; this.collide(it) }
      else if (it.y + it.h > this.H - 8) { this.burst(it.x + it.w / 2, this.H - 9, C.mint, 3); it.y = 9999 }
    }
    this.items = this.items.filter(i => i.y < 9000)
    if (this.lives <= 0 && this.phase === 'playing') {
      this.overT = 0; this.poseT = 0; this.animT = 0
      this.setPhase('over'); this.o.sfx.play('over'); this.say('game.say.over', { score: this.score })
      this.o.on.over({ score: this.score, triples: this.triples, level: this.level })
    }
  }
  private get ky() { return this.H - 10 - 32 - 1 + (this.o.reduced ? 0 : Math.round(Math.sin(this.clock * 2.2) * 1.2)) }

  private spawn() {
    const level = this.level
    const pHaz = Math.min(0.12 + 0.025 * level, 0.36)
    const r = Math.random()
    let it: Item | null = null
    const vy = this.fallSpeed * rnd(0.92, 1.1)
    const mkItem = (type: ItemType, kind: Kind | undefined, label: string, spr: HTMLCanvasElement): Item =>
      ({ type, kind, label, spr, w: spr.width, h: spr.height, x: 0, y: -spr.height, vy, ph: Math.random() * 6 })
    if (r < pHaz) it = Math.random() < 0.65 || level < 2 ? mkItem('bad', undefined, '!', bubbleSprite()) : mkItem('iri', undefined, '<IRI>', pill('iri', '<IRI>'))
    else if (r < pHaz + 0.07 && this.bonusT <= 0) {
      this.bonusT = 9
      it = !this.shield && Math.random() < 0.5 ? mkItem('shacl', undefined, 'SHACL', pill('shacl', 'SHACL')) : mkItem('inf', undefined, 'INF', pill('inf', 'INF'))
    } else {
      const opt = options(this.chain)
      const haveCont = this.items.some(i => i.type === 'tok' && i.kind === opt.kind && opt.labels.includes(i.label))
      if (!haveCont || Math.random() < 0.4) { const free = opt.labels.filter(l => !this.items.some(o => o.type === 'tok' && o.label === l && o.kind !== opt.kind)); const l = pick(free.length ? free : opt.labels); it = mkItem('tok', opt.kind, l, pill(opt.kind, l)) }
      else {
        // distracteur : jamais le même mot qu'une cible d'une autre catégorie, ni qu'un élément déjà à l'écran sous une autre catégorie
        for (let n = 0; n < 12 && !it; n++) {
          const k = pick<Kind>(['S', 'P', 'O']); const l = pick(ALL[k])
          if (k !== opt.kind && opt.labels.includes(l)) continue
          if (this.items.some(o => o.type === 'tok' && o.label === l && o.kind !== k)) continue
          it = mkItem('tok', k, l, pill(k, l))
        }
        if (!it) { const l = pick(opt.labels); it = mkItem('tok', opt.kind, l, pill(opt.kind, l)) }
      }
    }
    // abscisse : éviter de superposer les derniers éléments encore hauts
    for (let n = 0; n < 8; n++) {
      it.x = Math.round(rnd(3, this.W - it.w - 3))
      if (!this.items.some(o => o.y < 26 && Math.abs(o.x - it.x) < Math.max(o.w, it.w) + 4)) break
    }
    this.items.push(it)
  }

  private collide(it: Item) {
    const cx = it.x + it.w / 2, cy = it.y + it.h / 2
    if (it.type === 'tok') return this.catchTok(it.kind!, it.label, cx, cy)
    if (it.type === 'inf') { this.o.sfx.play('bonus'); this.setPose('nage_surprise', 0.7); this.infT = 1.5; this.burst(cx, cy, C.purple, 14); this.say('game.say.inf'); this.autoCatch(); return }
    if (it.type === 'shacl') { this.shield = true; this.o.sfx.play('bonus'); this.setPose('nage_surprise', 0.7); this.burst(cx, cy, C.glass, 10); this.say('game.say.shacl'); this.emit(); return }
    // dangers
    if (this.shield) { this.shield = false; this.setPose('nage_surprise', 0.4); this.o.sfx.play('shield'); this.burst(cx, cy, C.glass, 12); this.say('game.say.shield'); this.emit(); return }
    if (this.invuln > 0) return
    this.lives--; this.invuln = 1.5; this.shake = this.o.reduced ? 0 : 0.28; this.flash = this.o.reduced ? 0 : 0.18
    this.setPose('nage_grimace', 0.6); this.burst(cx, cy, C.red, 12); this.o.sfx.play('hit')
    if (it.type === 'iri') { this.chain = []; this.pop(this.kx, this.ky, 'IRI?', C.grey) }
    this.say('game.say.life', { lives: this.lives }); this.emit()
  }
  private catchTok(kind: Kind, label: string, cx: number, cy: number) {
    const ok = options(this.chain)
    if (kind === ok.kind && ok.labels.includes(label)) { this.chain.push(label); this.score += 10; this.setPose('nage_clin', 0.45); this.o.sfx.play('catch'); this.burst(cx, cy, KCOL[kind][0], 6); this.pop(cx, cy, '+10', KCOL[kind][0]); this.afterPush(); return }
    // maillon incohérent : un sujet relance une chaîne, tout autre élément se dissout sans effet
    if (kind === 'S') {
      const had = this.chain.length > 0
      this.chain = [label]; this.o.sfx.play('reset'); this.burst(cx, cy, C.grey, 5)
      if (had) { this.pop(cx, cy, 'X', C.grey); this.say('game.say.reset') }
      this.emit(); return
    }
    this.o.sfx.play('reset'); this.burst(cx, cy, C.grey, 5); this.pop(cx, cy, '?', C.grey)
  }
  private autoCatch() {
    const ok = options(this.chain)
    const l = pick(ok.labels)
    this.chain.push(l); this.score += 10; this.pop(this.kx, this.ky - 4, l, KCOL[ok.kind][0])
    this.afterPush()
  }
  private afterPush() {
    if (this.chain.length === 3) {
      const [s, p, o] = this.chain
      this.triples++
      const gain = 100 + 25 * (this.level - 1); this.score += gain
      this.graph.push({ s, p, o, t: this.clock }); if (this.graph.length > 7) this.graph.shift()
      this.chain = []
      this.setPose('nage_ravie', 0.8); this.burst(this.kx, this.ky + 8, C.amberHi, 14); this.o.sfx.play('triple'); this.pop(this.kx, this.ky - 6, '+' + gain, C.white)
      this.say('game.say.triple', { s, p, o, score: this.score })
      const lv = 1 + Math.floor(this.triples / 2)
      if (lv > this.level) { this.level = lv; this.o.sfx.play('level'); this.say('game.say.level', { level: lv }); this.pop(this.W / 2 - 10, 40, norm(this.o.labels.level) + ' ' + lv, C.amberHi) }
    }
    this.emit()
  }
  private setPose(p: GamePose, t: number) { this.pose = p; this.poseT = t; this.animT = 0 }
  private pop(x: number, y: number, text: string, color: string) { this.pops.push({ x, y, text, color, life: 0.9 }) }
  private burst(x: number, y: number, color: string, n: number) {
    const k = this.o.reduced ? Math.ceil(n / 3) : n
    for (let i = 0; i < k; i++) { const a = Math.random() * 6.28, s = rnd(10, 40); this.parts.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 14, life: rnd(0.3, 0.6), max: 0.6, c: color, s: Math.random() < 0.3 ? 2 : 1 }) }
  }

  // ---------------------------------------------------------------- rendu
  private makeBg(): HTMLCanvasElement {
    const { W, H } = this, c = mk(W, H), x = c.getContext('2d')!
    const bands = ['#0B2B33', '#0C363C', '#0D4245', '#0E4E4F', '#0F5A59', '#116663', '#137470']
    const floor = H - 10, n = bands.length, bh = floor / n
    const ys = bands.map((_, i) => Math.floor(i * bh)); ys.push(floor)
    bands.forEach((col, i) => { x.fillStyle = col; x.fillRect(0, ys[i], W, ys[i + 1] - ys[i]) })
    // tramage entre bandes (4 rangées : A rare, damier, damier inversé, B rare)
    for (let i = 1; i < n; i++) {
      const y = ys[i]
      const row = (r: number, col: string, mod: number, off: number) => { x.fillStyle = col; for (let px = 0; px < W; px++) if (px % mod === off) x.fillRect(px, y + r, 1, 1) }
      row(-2, bands[i], 4, 0); row(-1, bands[i], 2, 0); row(0, bands[i - 1], 2, 1); row(1, bands[i - 1], 4, 2)
    }
    // sol de sable
    x.fillStyle = C.sand; x.fillRect(0, floor, W, 10)
    x.fillStyle = C.paper; x.fillRect(0, floor, W, 1)
    x.fillStyle = C.sandD
    for (let i = 0; i < W * 0.5; i++) x.fillRect(Math.floor(hash('s' + i) * W), floor + 2 + Math.floor(hash('t' + i) * 7), 1, 1)
    // coquillages
    for (let i = 0; i < Math.floor(W / 60); i++) { const sx = Math.floor(hash('c' + i) * (W - 8)) + 2; x.fillStyle = '#F29A8E'; x.fillRect(sx, floor + 3, 3, 2); x.fillStyle = C.paper; x.fillRect(sx + 1, floor + 3, 1, 1) }
    return c
  }

  private drawGrass() {
    const x = this.ctx, floor = this.H - 10
    for (let i = 0; i < Math.floor(this.W / 28); i++) {
      const gx = 6 + i * 28 + Math.floor(hash('g' + i) * 10)
      for (let b = 0; b < 3; b++) {
        const hgt = 6 + Math.floor(hash('h' + i + b) * 5)
        for (let j = 0; j < hgt; j++) {
          const sway = this.o.reduced ? 0 : Math.round(Math.sin(this.clock * 1.6 + i + b * 0.7) * (j / hgt) * 1.6)
          x.fillStyle = j > hgt - 3 ? C.mint : b === 1 ? C.lagL : C.lag
          x.fillRect(gx + b * 2 + sway, floor - j, 1, 1)
        }
      }
    }
  }

  private drawGraph() {
    const x = this.ctx, top = 46, bot = Math.max(top + 20, Math.floor(this.H * 0.55))
    const pos = (n: string) => ({ x: 14 + Math.floor(hash('x' + n) * (this.W - 28)), y: top + Math.floor(hash('y' + n) * (bot - top)) })
    for (const t of this.graph) {
      const age = this.clock - t.t, fresh = Math.max(0, 1 - age / 2.5)
      const a = pos(t.s), b = pos(t.o)
      x.globalAlpha = 0.28 + 0.72 * fresh
      x.fillStyle = fresh > 0.2 ? C.mintHi : '#3FB5AE'
      line(x, a.x, a.y, b.x, b.y)
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
      x.fillRect(Math.round(a.x + (b.x - a.x) * 0.78) - 1, Math.round(a.y + (b.y - a.y) * 0.78) - 1, 3, 3) // pointe de flèche
      drawText(x, t.p, mx - textWidth(norm(t.p)) / 2, Math.max(37, my - 7), fresh > 0.2 ? C.white : '#7FDCD4')
      for (const [n, p] of [[t.s, a], [t.o, b]] as const) {
        x.fillStyle = C.ink; x.fillRect(p.x - 3, p.y - 3, 7, 7)
        x.fillStyle = n === t.s ? C.amber : C.lav; x.fillRect(p.x - 2, p.y - 2, 5, 5)
        x.fillStyle = C.white; x.fillRect(p.x - 2, p.y - 2, 1, 1)
        drawText(x, n, p.x - textWidth(norm(n)) / 2, p.y + 5, '#BFF3EE')
      }
    }
    x.globalAlpha = 1
  }

  private drawKrakie() {
    const x = this.ctx, sp = this.o.sprites(), pose = this.curPose, fr = sp[pose] ?? sp.nage
    const kx = Math.round(this.kx), ky = this.ky, cy = ky + 17, red = this.o.reduced
    this.drawAuras(kx, cy)
    if (this.invuln > 0 && Math.floor(this.clock * 14) % 2 === 0 && this.phase === 'playing') return
    if (!fr) { x.fillStyle = C.lagL; x.fillRect(kx - 10, ky + 6, 20, 20); return }
    // image : cycle de nage (fixe sous mouvement réduit)
    let f = 0
    if (!red && fr.frames.length > 1) {
      const tot = fr.durations.reduce((a, b) => a + b, 0); let t = this.animT % tot
      while (f < fr.frames.length - 1 && t >= fr.durations[f]) { t -= fr.durations[f]; f++ }
    }
    // tremblement de la grimace. Pas de rotation ni de cisaillement : le sprite 32 px reste intact, positions entières.
    // « Inclinaison » = les tentacules (rangées 20 et +) traînent d'un pixel, état discret avec hystérésis (pas de scintillement).
    const jit = !red && pose === 'nage_grimace' ? (Math.floor(this.clock * 40) % 2 ? 1 : -1) : 0
    const lean = red ? 0 : this.lean, img = fr.frames[f]
    if (lean > 1.4) this.trail = 1; else if (lean < -1.4) this.trail = -1; else if (Math.abs(lean) < 0.6) this.trail = 0
    const ox = kx - 16 + jit, tr = red ? 0 : this.trail
    if (tr === 0) x.drawImage(img, ox, ky)
    else { x.drawImage(img, 0, 0, 32, 20, ox, ky, 32, 20); x.drawImage(img, 0, 20, 32, 12, ox - tr, ky + 20, 32, 12) }
    if (this.shield) this.drawShieldFront(kx, cy)
  }

  /** Halo de bouclier SHACL (disque de verre translucide, anneau, reflets qui tournent) et effet d'inférence. */
  private drawAuras(kx: number, cy: number) {
    const x = this.ctx, red = this.o.reduced
    if (this.shield) {
      const R = 21 + (red ? 0 : Math.round(Math.sin(this.clock * 4)))
      x.fillStyle = 'rgba(205,239,245,0.16)'
      for (let j = -R; j <= R; j++) { const w = Math.floor(Math.sqrt(R * R - j * j)); x.fillRect(kx - w, cy + j, w * 2 + 1, 1) }
    }
    if (this.infT > 0) {
      const k = 1 - this.infT / 1.5, ph = red ? 0 : this.clock * 5
      x.fillStyle = 'rgba(199,155,242,0.20)'
      const R = red ? 18 : 12 + Math.round(k * 12)
      for (let j = -R; j <= R; j++) { const w = Math.floor(Math.sqrt(R * R - j * j)); x.fillRect(kx - w, cy + j, w * 2 + 1, 1) }
      for (let i = 0; i < 8; i++) { // étincelles violettes en orbite
        const a = ph + (i * Math.PI) / 4, r = 19 + (i % 2) * 3
        const px = Math.round(kx + Math.cos(a) * r), py = Math.round(cy + Math.sin(a) * r * 0.9)
        x.fillStyle = i % 2 ? C.white : C.purple
        x.fillRect(px, py, 1, 1); if (i % 2 === 0) { x.fillRect(px - 1, py, 3, 1); x.fillRect(px, py - 1, 1, 3) }
      }
    }
  }
  private drawShieldFront(kx: number, cy: number) {
    const x = this.ctx, red = this.o.reduced, R = 21 + (red ? 0 : Math.round(Math.sin(this.clock * 4)))
    for (let a = 0; a < 360; a += 4) {
      const rad = (a * Math.PI) / 180, px = Math.round(kx + Math.cos(rad) * R), py = Math.round(cy + Math.sin(rad) * R)
      x.fillStyle = (a / 4) % 3 === 0 ? C.white : C.glass; x.fillRect(px, py, 1, 1)
    }
    const g = red ? 225 : (this.clock * 120) % 360 // reflet qui glisse sur l'anneau
    x.fillStyle = C.white
    for (let d = 0; d < 28; d += 4) { const rad = ((g + d) * Math.PI) / 180; x.fillRect(Math.round(kx + Math.cos(rad) * (R - 1)), Math.round(cy + Math.sin(rad) * (R - 1)), 1, 1) }
  }

  private drawHud() {
    const x = this.ctx, W = this.W
    x.fillStyle = 'rgba(11,43,51,0.82)'; x.fillRect(0, 0, W, 33)
    drawText(x, `${this.o.labels.score} ${this.score}`, 4, 4, C.paper)
    drawText(x, `${this.o.labels.level} ${this.level}`, 4, 11, C.mint)
    for (let i = 0; i < 3; i++) x.drawImage(heartSprite(i < this.lives), W - 4 - (3 - i) * 9 + 2, 4)
    if (this.shield) { x.fillStyle = C.glass; x.fillRect(W - 31, 12, 4, 1); x.fillRect(W - 30, 13, 2, 1) }
    // chaîne en cours : trois emplacements S P O
    const sw = Math.min(46, Math.floor((W - 16) / 3) - 3), sx0 = Math.floor((W - (sw * 3 + 6)) / 2), sy = 20
    const want = this.chain.length
    for (let i = 0; i < 3; i++) {
      const k: Kind = (['S', 'P', 'O'] as const)[i], [col, hi] = KCOL[k], px = sx0 + i * (sw + 3)
      const filled = i < this.chain.length
      x.fillStyle = C.ink; x.fillRect(px, sy, sw, 11)
      if (filled) {
        x.fillStyle = col; x.fillRect(px + 1, sy + 1, sw - 2, 9); x.fillStyle = hi; x.fillRect(px + 1, sy + 1, sw - 2, 1)
        let lab = this.chain[i]; while (lab.length > 1 && textWidth(lab) > sw - 4) lab = lab.slice(0, -1)
        drawText(x, lab, px + Math.floor((sw - textWidth(lab)) / 2), sy + 3, C.ink)
      } else {
        const blink = i === want && this.phase === 'playing' && Math.floor(this.clock * 3) % 2 === 0
        x.fillStyle = '#0F3E43'; x.fillRect(px + 1, sy + 1, sw - 2, 9)
        if (i === want) { x.fillStyle = blink ? C.white : col; for (let d = 0; d < sw; d += 2) { x.fillRect(px + d, sy, 1, 1); x.fillRect(px + d, sy + 10, 1, 1) } }
        drawText(x, k, px + Math.floor((sw - 3) / 2), sy + 3, col)
      }
    }
  }

  private draw() {
    const x = this.ctx, { W, H } = this
    if (!this.bg) return
    x.save()
    if (this.shake > 0) x.translate(Math.round(rnd(-1.5, 1.5)), Math.round(rnd(-1.5, 1.5)))
    x.drawImage(this.bg, 0, 0)
    // rayons de lumière (marches d'escalier, sans anticrénelage)
    x.fillStyle = 'rgba(190,243,238,0.05)'
    const drift = this.o.reduced ? 0 : this.clock * 4
    for (let i = 0; i < 3; i++) {
      const x0 = ((i * W) / 2.2 + drift) % (W + 60) - 30, w = 14 + i * 6
      for (let y = 0; y < H * 0.78; y++) x.fillRect(Math.round(x0 + y * 0.45), y, w, 1)
    }
    x.fillStyle = 'rgba(190,243,238,0.5)'
    for (const b of this.bubbles) { const bx = Math.round(b.x), by = Math.round(b.y); if (b.r === 1) x.fillRect(bx, by, 1, 1); else { x.fillRect(bx + 1, by, 1, 1); x.fillRect(bx, by + 1, 1, 1); x.fillRect(bx + 2, by + 1, 1, 1); x.fillRect(bx + 1, by + 2, 1, 1) } }
    this.drawGraph()
    this.drawGrass()
    for (const it of this.items) {
      const ix = Math.round(it.x), iy = Math.round(it.y)
      x.drawImage(it.spr, ix, iy)
      if (it.type === 'inf' || it.type === 'shacl') { // scintillement des bonus
        if (Math.floor(this.clock * 6) % 2 === 0) { x.fillStyle = C.white; x.fillRect(ix - 2, iy - 1, 1, 3); x.fillRect(ix - 3, iy, 3, 1); x.fillRect(ix + it.w + 1, iy + it.h - 2, 1, 3); x.fillRect(ix + it.w, iy + it.h - 1, 3, 1) }
      }
    }
    this.drawKrakie()
    for (const p of this.parts) { x.globalAlpha = Math.max(0, p.life / p.max); x.fillStyle = p.c; x.fillRect(Math.round(p.x), Math.round(p.y), p.s, p.s) }
    x.globalAlpha = 1
    for (const p of this.pops) drawText(x, p.text, p.x - textWidth(norm(p.text)) / 2, p.y, p.color)
    this.drawHud()
    if (this.flash > 0) { x.fillStyle = 'rgba(214,69,61,0.28)'; x.fillRect(0, 0, W, H) }
    x.restore()
  }
}

