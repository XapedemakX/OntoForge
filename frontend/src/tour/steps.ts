import type { TourStep } from './controller'
import { setUi } from '../assistant-global/store'

const $ = <T extends Element = HTMLElement>(s: string) => document.querySelector<T>(s)
const click = (s: string) => { $(s)?.click() }
const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms))
async function until(fn: () => unknown, ms = 2500) { const t0 = performance.now(); while (!fn() && performance.now() - t0 < ms) await sleep(80) }

let legendWasOpen = false

/** Les 19 étapes de la visite « Découvrir OntoForge » ; textes dans i18n (tour.s.<id>.t / .b). */
export function buildSteps(t: (k: string) => string): TourStep[] {
  const S = (id: string, rest: Omit<TourStep, 'id' | 'title' | 'body'>): TourStep => ({ id, title: t(`tour.s.${id}.t`), body: t(`tour.s.${id}.b`), ...rest })
  return [
    S('welcome', { route: 'tableau', waitFor: '[data-tour="dash-next"]', pose: 'accueil' }),
    S('nav', { route: 'tableau', target: '[data-tour="nav"]', placement: 'right', drawer: true, pose: 'graphe' }),
    S('target', { route: 'tableau', target: '[data-tour="target"]', placement: 'bottom', pose: 'loupe' }),
    S('dashboard', { route: 'tableau', target: '[data-tour="dash-next"], [data-tour="dash-steps"]', placement: 'bottom', pose: 'contente' }),
    S('ed-canvas', {
      route: 'ontologie', waitFor: '.react-flow__node', target: '[data-tour="ed-canvas"], [data-tour="ed-inspector"]', placement: 'bottom', pose: 'graphe',
      action: async () => { if (!$('[data-tour="ed-inspector"] .of-insp-h')) { click('.react-flow__node'); await until(() => $('[data-tour="ed-inspector"] .of-insp-h')) } },
    }),
    S('ed-quick', {
      route: 'ontologie', waitFor: '[data-tour="ed-quick"]', target: '[data-tour="ed-quick"]', placement: 'top', pose: 'lit',
      action: async () => { if ($('.of-dslhead[aria-expanded="false"]')) { click('.of-dslhead'); await until(() => $('[data-tour="ed-quick"] textarea')) } },
      leave: () => click('.of-dslhead[aria-expanded="true"]'),
    }),
    S('legend', {
      route: 'ontologie', waitFor: '[data-tour="ed-legend-btn"]', target: '[data-tour="ed-legend"]', placement: 'left', pose: 'loupe',
      action: async () => { legendWasOpen = !!$('[data-tour="ed-legend"]'); if (!legendWasOpen) { click('[data-tour="ed-legend-btn"]'); await until(() => $('[data-tour="ed-legend"]')) } },
      leave: () => { if (!legendWasOpen && $('[data-tour="ed-legend"]')) click('[data-tour="ed-legend-btn"]') },
    }),
    S('list', {
      route: 'ontologie-liste', waitFor: '.ol-tree .nm', target: '[data-tour="ol"]', placement: 'bottom', pose: 'lit',
      action: async () => {
        if ($('.ol.has-sel')) return
        const items = [...document.querySelectorAll<HTMLElement>('.ol-tree .nm')]
        ;(items.find(e => /v[ée]hicule|vehicle/i.test(e.textContent ?? '')) ?? items[0])?.click()
        await until(() => $('.ol.has-sel'))
      },
    }),
    S('shapes', { route: 'shapes', waitFor: '[data-tour="shapes-split"]', target: '[data-tour="shapes-split"]', placement: 'bottom', pose: 'lit' }),
    S('conformite', { route: 'conformite', waitFor: '[data-tour="conf-profiles"]', target: '[data-tour="conf-profiles"]', placement: 'bottom', pose: 'loupe' }),
    S('shacl', { route: 'shacl', waitFor: '[data-tour="shacl-valid"]', target: '[data-tour="shacl-valid"]', placement: 'bottom', pose: 'loupe' }),
    S('an-counters', { route: 'analyse', waitFor: '[data-tour="an-counters"]', target: '[data-tour="an-counters"]', placement: 'bottom', pose: 'graphe' }),
    S('an-finding', {
      route: 'analyse', waitFor: '[data-tour="an-rule"]', target: '[data-tour="an-finding"]', placement: 'top', pose: 'inquiete',
      action: async () => {
        const rule = $('[data-tour="an-group-review"] [data-tour="an-rule"]') ?? $('[data-tour="an-rule"]')
        const head = rule?.querySelector<HTMLElement>('.ttl')
        if (head && head.getAttribute('aria-expanded') !== 'true') { head.click(); await until(() => $('[data-tour="an-finding"]')) }
      },
    }),
    S('model', { route: 'modele', waitFor: '[data-tour="model-diagram"]', target: '[data-tour="model-diagram"]', placement: 'bottom', pose: 'graphe' }),
    S('exports', { route: 'exports', waitFor: '[data-tour="exports"]', target: '[data-tour="exports"]', placement: 'bottom', pose: 'bolide' }),
    S('q-nl', { route: 'requetes', waitFor: '[data-tour="q-nl"]', target: '[data-tour="q-nl"]', placement: 'bottom', pose: 'loupe' }),
    S('q-values', {
      route: 'requetes', waitFor: '[data-tour="q-builder"]', target: '[data-tour="q-builder"]', placement: 'bottom', pose: 'lit',
      action: async () => {
        if (!$('.qn.root')) {
          await until(() => $('.qpick-list .qc'))
          const chips = [...document.querySelectorAll<HTMLElement>('.qpick-list .qc')]
          const known = (e: HTMLElement) => parseInt(e.querySelector('.qc-meta')?.textContent ?? '0', 10) || 0
          chips.sort((a, b) => known(b) - known(a))[0]?.click()
          await until(() => $('.qn.root'))
        }
        await until(() => $('[data-tour="q-oneof"]'), 1500)
        click('[data-tour="q-oneof"]')
        await sleep(400)
      },
    }),
    S('q-endpoint', {
      route: 'requetes', waitFor: '[data-tour="q-endpoint"]', target: '[data-tour="q-temp"]', placement: 'bottom', pose: 'reflechit',
      action: async () => {
        if ($('[data-tour="q-temp"]')) return
        const sel = $<HTMLSelectElement>('[data-tour="q-endpoint"] select'); if (!sel) return
        Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')!.set!.call(sel, '__new')
        sel.dispatchEvent(new Event('change', { bubbles: true }))
        await until(() => $('[data-tour="q-temp"]'))
      },
      leave: () => click('[data-tour="q-temp"] .btn.ghost'),
    }),
    S('fab', { route: 'requetes', target: '[data-tour="krakie-fab"]', placement: 'left', pose: 'contente', action: () => setUi({ open: false }) }),
  ]
}
