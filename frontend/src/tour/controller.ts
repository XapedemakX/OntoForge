/*
 * Moteur de la visite guidée : état partagé (store externe), navigation d'écran en écran,
 * attente des cibles, API `window.ontoforgeTour`. Aucune dépendance externe.
 * L'affichage (voile, découpe, bulle) est dans Overlay.tsx.
 */
import type { Pose } from '../krakie/Krakie'

export type Placement = 'top' | 'bottom' | 'left' | 'right'

export interface TourStep {
  id: string
  /** Écran du registre (clé de SCREENS) à ouvrir pour cette étape. */
  route?: string
  /** Sélecteur CSS de la cible, de préférence [data-tour="..."]. Une liste (a, b) met en évidence l'union des éléments visibles. */
  target?: string
  title: string
  body: string
  placement?: Placement
  /** Préparer l'écran : sélectionner une classe, ouvrir un onglet… Exécutée une fois `waitFor` apparu, avant la recherche de la cible. */
  action?: () => void | Promise<void>
  /** Sélecteur à attendre avant `action` (écran chargé paresseusement, données reçues). */
  waitFor?: string
  pose?: Pose
  /** Étape qui vise le menu : sur mobile, le tiroir de navigation est ouvert pour elle. */
  drawer?: boolean
  /** Remise en état en quittant l'étape (fermer un panneau ouvert par `action`). */
  leave?: () => void
}

export type TourStatus = 'loading' | 'ready'
export interface TourState {
  active: boolean
  phase: 'idle' | 'ask-demo' | 'creating' | 'running'
  index: number
  steps: TourStep[]
  status: TourStatus
  /** La cible de l'étape a été trouvée et est visible. */
  found: boolean
  error: string | null
}
export interface TourHost {
  buildSteps(): TourStep[]
  createDemo(): Promise<string>
}
export interface StartOptions { demo?: boolean; from?: number }

export const DONE_KEY = 'ontoforge.tour.done'
export const POLL_MS = 4000

const IDLE: TourState = { active: false, phase: 'idle', index: 0, steps: [], status: 'loading', found: false, error: null }
let state: TourState = IDLE
let host: TourHost | null = null
let pendingStart: StartOptions | null = null
let seq = 0
const subs = new Set<() => void>()
const set = (p: Partial<TourState>) => { state = { ...state, ...p }; subs.forEach(f => f()) }
export const getState = () => state
export const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f) } }

const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms))
export const isMobile = () => window.matchMedia('(max-width: 900px)').matches

export function markDone() { try { localStorage.setItem(DONE_KEY, '1') } catch { /* stockage indisponible */ } }
export function isDone() { try { return localStorage.getItem(DONE_KEY) === '1' } catch { return false } }

/** Identifiant du projet ouvert, lu dans l'URL (#/projet/<id>/<écran>). */
export function currentProjectId(): string | null {
  const m = location.hash.match(/^#\/projet\/([^/?]+)/)
  return m ? decodeURIComponent(m[1]) : null
}
function currentScreen(): string | null {
  const m = location.hash.match(/^#\/projet\/[^/?]+(?:\/([\w-]+))?/)
  return m ? (m[1] || 'tableau') : null
}
function navigate(route: string) {
  const id = currentProjectId(); if (!id) return
  if (currentScreen() !== route) location.hash = `#/projet/${encodeURIComponent(id)}/${route}`
}

// ---------------------------------------------------------------- cibles
export function visibleEls(selector: string): Element[] {
  let list: Element[] = []
  try { list = [...document.querySelectorAll(selector)] } catch { return [] }
  return list.filter(e => {
    const r = e.getBoundingClientRect()
    return r.width > 0 && r.height > 0 && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden'
  })
}
/** Cible d'une étape : le premier élément visible de chaque sélecteur de la liste (séparés par des virgules). */
export function targetEls(selector: string): Element[] {
  return selector.split(',').map(s => visibleEls(s.trim())[0]).filter(Boolean)
}
export interface Box { left: number; top: number; width: number; height: number }
export function unionBox(els: Element[]): Box | null {
  if (!els.length) return null
  let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity
  for (const e of els) { const x = e.getBoundingClientRect(); l = Math.min(l, x.left); t = Math.min(t, x.top); r = Math.max(r, x.right); b = Math.max(b, x.bottom) }
  return { left: l, top: t, width: r - l, height: b - t }
}
export const targetBox = (selector: string) => unionBox(targetEls(selector))

async function poll<T>(fn: () => T | null | undefined | false, tok: number, timeout = POLL_MS): Promise<T | null> {
  const t0 = performance.now()
  for (;;) {
    const v = fn(); if (v) return v
    if (tok !== seq || performance.now() - t0 > timeout) return null
    await sleep(80)
  }
}

/** Zone libre de l'écran (hors bulle) dans laquelle la cible doit rester. Sur mobile, la bulle occupe le bas. */
export function freeArea() {
  const top = document.querySelector('.topbar')?.getBoundingClientRect().bottom ?? 0
  const bottomReserve = isMobile() ? Math.min(innerHeight * 0.46, 330) + 8 : 0
  return { top: Math.max(0, top) + 6, bottom: innerHeight - bottomReserve }
}
function scrollParent(el: Element): HTMLElement | null {
  for (let p = el.parentElement; p; p = p.parentElement) {
    const o = getComputedStyle(p).overflowY
    if ((o === 'auto' || o === 'scroll') && p.scrollHeight > p.clientHeight + 1) return p
  }
  return null
}
function reveal(els: Element[]) {
  const first = els[0]; if (!first) return
  first.scrollIntoView({ block: 'center', inline: 'nearest' })
  const box = unionBox(els); if (!box) return
  const a = freeArea(); const room = a.bottom - a.top
  // cible plus haute que la zone libre : on aligne son bord haut ; sinon on la centre dans la zone libre
  const want = box.height > room ? a.top + 4 : a.top + (room - box.height) / 2
  const dy = box.top - want
  if (Math.abs(dy) > 2) { const sp = scrollParent(first); if (sp) sp.scrollTop += dy; else window.scrollBy(0, dy) }
}
async function settle(selector: string, tok: number) {
  let prev = ''; let same = 0
  for (let i = 0; i < 14 && tok === seq; i++) {
    const b = targetBox(selector); const k = b ? [b.left, b.top, b.width, b.height].map(Math.round).join() : ''
    same = k === prev ? same + 1 : 0; prev = k
    if (same >= 2) return
    await sleep(50)
  }
}

// ---------------------------------------------------------------- étapes
async function enter(i: number) {
  const tok = ++seq
  const steps = state.steps
  const prev = steps[state.index]
  if (prev && prev !== steps[i]) { try { prev.leave?.() } catch { /* remise en état best effort */ } }
  const idx = Math.max(0, Math.min(i, steps.length - 1))
  const step = steps[idx]
  set({ phase: 'running', index: idx, status: 'loading', found: false })
  dispatchEvent(new CustomEvent('ontoforge:tour-menu', { detail: { open: !!step.drawer && isMobile() } }))
  if (step.route) navigate(step.route)
  if (step.waitFor) await poll(() => visibleEls(step.waitFor!).length > 0, tok)
  if (tok !== seq) return
  try { await step.action?.() } catch (e) { console.warn('[tour] action', step.id, e) }
  if (tok !== seq) return
  let els: Element[] = []
  if (step.target) {
    await poll(() => targetEls(step.target!).length > 0, tok)
    if (tok !== seq) return
    els = targetEls(step.target)
    if (els.length) {
      reveal(els); await settle(step.target, tok)
      if (tok !== seq) return
      els = targetEls(step.target)
    } else console.warn('[tour] cible introuvable :', step.id, step.target)
  }
  set({ status: 'ready', found: els.length > 0 })
}

async function createDemo() {
  if (!host) return
  set({ phase: 'creating', error: null })
  try {
    await host.createDemo()
    await enter(0)
  } catch (e) { set({ phase: 'ask-demo', error: (e as Error).message || 'error' }) }
}

function start(opts: StartOptions = {}) {
  if (!host) { pendingStart = opts; return Promise.resolve() }
  const steps = host.buildSteps()
  set({ ...IDLE, active: true, phase: 'running', steps, error: null })
  if (!currentProjectId()) {
    if (opts.demo) return createDemo()
    set({ phase: 'ask-demo' }); return Promise.resolve()
  }
  return enter(opts.from ?? 0)
}
function stop() {
  seq++
  const step = state.steps[state.index]
  if (state.active && state.phase === 'running') { try { step?.leave?.() } catch { /* */ } }
  dispatchEvent(new CustomEvent('ontoforge:tour-menu', { detail: { open: false } }))
  markDone()
  set({ ...IDLE })
}
function goto(i: number) {
  if (!state.active) return start({ from: i, demo: true })
  return enter(i)
}
function next() {
  if (!state.active || state.phase !== 'running') return Promise.resolve()
  return state.index >= state.steps.length - 1 ? (stop(), Promise.resolve()) : enter(state.index + 1)
}
function prev() {
  if (!state.active || state.phase !== 'running') return Promise.resolve()
  return enter(state.index - 1)
}

export const tour = { start, stop, goto, next, prev, createDemo }

export function registerHost(h: TourHost) {
  host = h
  if (pendingStart) { const o = pendingStart; pendingStart = null; void start(o) }
  return () => { if (host === h) host = null }
}

export interface PublicTour {
  start(opts?: StartOptions): Promise<void>
  stop(): void
  next(): Promise<void>
  prev(): Promise<void>
  goto(i: number): Promise<void>
  state(): { active: boolean; phase: string; index: number; total: number; id: string | null; hasTarget: boolean; found: boolean; ready: boolean }
}
declare global { interface Window { ontoforgeTour: PublicTour } }
window.ontoforgeTour = {
  start: o => start(o), stop, next, prev, goto,
  state: () => {
    const s = state.steps[state.index]
    return { active: state.active, phase: state.phase, index: state.index, total: state.steps.length, id: s?.id ?? null, hasTarget: !!s?.target, found: state.found, ready: state.status === 'ready' }
  },
}
