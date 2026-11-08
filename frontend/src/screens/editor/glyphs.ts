// Dessins SVG (chaînes) partagés par la légende et l'export : la légende utilise les variables CSS de l'éditeur,
// l'export les valeurs résolues, de sorte que le fichier s'ouvre identique hors de l'application.
export const PAL_KEYS = {
  bg: '--bg', panel: '--panel', panel2: '--panel2', line: '--line', lineStrong: '--line-strong', ink: '--ink', muted: '--muted',
  accent: '--accent', accentSoft: '--accent-soft', accentInk: '--accent-ink', info: '--info', infoSoft: '--info-soft', lost: '--lost', lostSoft: '--lost-soft',
  add: '--ed-add', addSoft: '--ed-add-soft', mod: '--ed-mod', modSoft: '--ed-mod-soft', review: '--review', reviewSoft: '--review-soft',
  vwClass: '--vw-class', vwInk: '--vw-ink', vwExt: '--vw-ext', vwExtInk: '--vw-ext-ink', vwDep: '--vw-dep', vwDt: '--vw-dt', vwDp: '--vw-dp', vwGfx: '--vw-gfx', vwThing: '--vw-thing', vwLine: '--vw-line',
} as const
export type Pal = Record<keyof typeof PAL_KEYS, string>
export const CSS_PAL = Object.fromEntries(Object.entries(PAL_KEYS).map(([k, v]) => [k, `var(${v})`])) as Pal
export function resolvePal(el: Element): Pal {
  const cs = getComputedStyle(el)
  return Object.fromEntries(Object.entries(PAL_KEYS).map(([k, v]) => [k, cs.getPropertyValue(v).trim() || '#888'])) as Pal
}
export const FONT = "'IBM Plex Sans', 'Segoe UI', Helvetica, Arial, sans-serif"
export const MONO = "'IBM Plex Mono', Menlo, Consolas, 'Courier New', monospace"

export const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
type St = { fill?: string; stroke?: string; sw?: number; dash?: string; op?: number; cap?: string }
const st = (o: St) => ` style="fill:${o.fill ?? 'none'};stroke:${o.stroke ?? 'none'};stroke-width:${o.sw ?? 1};${o.dash ? `stroke-dasharray:${o.dash};` : ''}${o.cap ? `stroke-linecap:${o.cap};` : ''}${o.op !== undefined ? `opacity:${o.op};` : ''}"`

export const rect = (x: number, y: number, w: number, h: number, r: number, o: St) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}"${st(o)}/>`
export const circ = (cx: number, cy: number, r: number, o: St) => `<circle cx="${cx}" cy="${cy}" r="${r}"${st(o)}/>`
export const line = (x1: number, y1: number, x2: number, y2: number, o: St) => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"${st(o)}/>`
export const path = (d: string, o: St) => `<path d="${d}"${st(o)}/>`
export interface TxtO { size?: number; weight?: number; fill: string; anchor?: 'start' | 'middle' | 'end'; italic?: boolean; strike?: boolean; mono?: boolean }
export const text = (x: number, y: number, s: string, o: TxtO) =>
  `<text x="${x}" y="${y}" text-anchor="${o.anchor ?? 'start'}" font-family="${o.mono ? MONO : FONT}" font-size="${o.size ?? 12}" font-weight="${o.weight ?? 400}"${o.italic ? ' font-style="italic"' : ''}${o.strike ? ' text-decoration="line-through"' : ''} style="fill:${o.fill}">${esc(s)}</text>`
/** Pointe de flèche dont la pointe est en (x, y), orientée vers `ang` (radians). */
export function arrow(x: number, y: number, ang: number, kind: 'hollow' | 'solid', fill: string, stroke: string, size = 10): string {
  const d = `M ${-size} ${-size * 0.5} L 0 0 L ${-size} ${size * 0.5} Z`
  return `<path d="${d}" transform="translate(${x} ${y}) rotate(${(ang * 180) / Math.PI})"${st({ fill: kind === 'hollow' ? fill : stroke, stroke, sw: 1.4 })} stroke-linejoin="round"/>`
}
