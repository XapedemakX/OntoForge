// Jetons de couleur de la carte métier : une palette claire et une sombre, résolues en valeurs fixes
// (le SVG exporté doit s'ouvrir identique hors de l'application, sans variables CSS).
import type { DrawnStyle } from './types'

export interface EdgeInk { color: string; text: string; w: number; dash?: string; round?: boolean }
export interface Pal {
  dark: boolean
  bg: string; ink: string; muted: string; soft: string
  zoneLine: string; zoneTitle: string; zoneSub: string
  frame: string; frameFill: string; labelBg: string; ring: string
  noteBg: string; noteLine: string; noteInk: string
  edge: Record<DrawnStyle, EdgeInk>
}

const LIGHT: Pal = {
  dark: false, bg: '#ffffff', ink: '#1a202c', muted: '#4a5568', soft: '#718096',
  zoneLine: '#cbd5e0', zoneTitle: '#2d3748', zoneSub: '#718096',
  frame: '#2b6cb0', frameFill: '#ffffff', labelBg: '#ffffff', ring: '#dd6b20',
  noteBg: '#fffaf0', noteLine: '#dd6b20', noteInk: '#7b341e',
  edge: {
    scored: { color: '#dd6b20', text: '#9c4221', w: 4.6 },
    gate: { color: '#2b7bd0', text: '#1f5a9e', w: 4.2 },
    read: { color: '#ed8936', text: '#c05621', w: 2.6 },
    context: { color: '#4299e1', text: '#2b6cb0', w: 2.4 },
    context_off: { color: '#90cdf4', text: '#4a7fb0', w: 2.2, dash: '7 6' },
    grouped: { color: '#2b6cb0', text: '#2b6cb0', w: 2.4, dash: '11 6' },
    disabled: { color: '#a0aec0', text: '#718096', w: 2.2, dash: '11 6' },
    both: { color: '#4a5568', text: '#2d3748', w: 2 },
    symmetric: { color: '#0b6e6e', text: '#0b6e6e', w: 2 },
    mention: { color: '#718096', text: '#718096', w: 1.7, dash: '1.5 5', round: true },
    oneway: { color: '#b83280', text: '#97266d', w: 2.2 },
    bundle: { color: '#3b4252', text: '#1a202c', w: 3.6 },
    subclass: { color: '#805ad5', text: '#6b46c1', w: 2, dash: '9 6' },
    plain: { color: '#718096', text: '#4a5568', w: 1.9 },
  },
}
const DARK: Pal = {
  dark: true, bg: '#0e1627', ink: '#e8edf6', muted: '#a9b6cb', soft: '#8494ad',
  zoneLine: '#3b4d6d', zoneTitle: '#dbe4f2', zoneSub: '#8fa0ba',
  frame: '#7db2f5', frameFill: '#0e1627', labelBg: '#0e1627', ring: '#f08a3c',
  noteBg: '#2a2112', noteLine: '#f08a3c', noteInk: '#f7d9b4',
  edge: {
    scored: { color: '#f08a3c', text: '#ffb375', w: 4.6 },
    gate: { color: '#5ea6ff', text: '#9cc8ff', w: 4.2 },
    read: { color: '#e49a56', text: '#f2b784', w: 2.6 },
    context: { color: '#66b2ee', text: '#9fd0f6', w: 2.4 },
    context_off: { color: '#4d7ea8', text: '#7fa9cd', w: 2.2, dash: '7 6' },
    grouped: { color: '#7db2f5', text: '#9cc8ff', w: 2.4, dash: '11 6' },
    disabled: { color: '#6d7c93', text: '#8494ad', w: 2.2, dash: '11 6' },
    both: { color: '#a9b6cb', text: '#d3dcea', w: 2 },
    symmetric: { color: '#3cc4bb', text: '#7fdad3', w: 2 },
    mention: { color: '#8494ad', text: '#8494ad', w: 1.7, dash: '1.5 5', round: true },
    oneway: { color: '#e272b4', text: '#f0a0cf', w: 2.2 },
    bundle: { color: '#c7d1e2', text: '#f1f5fb', w: 3.6 },
    subclass: { color: '#a78bfa', text: '#c4b5fd', w: 2, dash: '9 6' },
    plain: { color: '#8494ad', text: '#c0cbdc', w: 1.9 },
  },
}
export const palette = (dark: boolean): Pal => (dark ? DARK : LIGHT)

/** Thème courant de l'application (jeton --dark posé par design/tokens.css). */
export function isDarkTheme(): boolean {
  try { return getComputedStyle(document.documentElement).getPropertyValue('--dark').trim() === '1' } catch { return false }
}

// ---------- couleurs de zone : mélange d'une teinte avec le fond ----------
const hexRe = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i
export function toRgb(c: string): [number, number, number] | null {
  if (!hexRe.test(c)) return null
  let h = c.slice(1); if (h.length === 3) h = h.split('').map(x => x + x).join('')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}
const hex2 = (n: number) => Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, '0')
export function mix(c: string, bg: string, a: number): string {
  const x = toRgb(c) ?? [148, 163, 184], y = toRgb(bg) ?? [255, 255, 255]
  return '#' + [0, 1, 2].map(i => hex2(x[i] * a + y[i] * (1 - a))).join('')
}
const lum = (c: string) => { const x = toRgb(c); return x ? (0.299 * x[0] + 0.587 * x[1] + 0.114 * x[2]) / 255 : 0.8 }
function hsl(c: string): [number, number, number] {
  const x = toRgb(c) ?? [148, 163, 184], r = x[0] / 255, g = x[1] / 255, b = x[2] / 255
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn
  if (!d) return [0, 0, l]
  const s = d / (1 - Math.abs(2 * l - 1))
  const h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4
  return [Math.round((h * 60 + 360) % 360), s, l]
}
/** Fond d'une zone. Le serveur donne déjà une teinte claire ; une couleur franche (choisie à la main) est éclaircie. En sombre, la teinte est reprise en version profonde. */
export function zoneTint(color: string, p: Pal): string {
  if (!toRgb(color)) return p.dark ? '#18233a' : '#f1f4f8'
  if (!p.dark) return lum(color) > 0.85 ? color : mix(color, p.bg, 0.1)
  const [h, s] = hsl(color)
  return `hsl(${h} ${Math.round(Math.min(0.34, s * 0.3 + 0.04) * 100)}% ${lum(color) > 0.85 ? 14 : 12}%)`
}

// ---------- couleurs des rôles : une teinte par rôle, dans l'ordre fourni ----------
const HUES = [152, 188, 345, 214, 38, 262, 78, 24]
export interface RoleInk { fill: string; stroke: string }
export function roleInk(index: number, p: Pal, color?: string): RoleInk {
  if (color && toRgb(color)) return p.dark ? { fill: mix(color, p.bg, 0.3), stroke: mix(color, '#ffffff', 0.72) } : { fill: mix(color, '#ffffff', 0.16), stroke: color }
  if (index < 0) return { fill: p.dark ? '#26324a' : '#e2e8f0', stroke: p.dark ? '#8494ad' : '#4a5568' }
  if (index >= HUES.length) return { fill: p.dark ? '#222d44' : '#e8ecf3', stroke: p.dark ? '#93a3bd' : '#4a5568' }
  const h = HUES[index]
  return p.dark ? { fill: `hsl(${h} 38% 22%)`, stroke: `hsl(${h} 58% 62%)` } : { fill: `hsl(${h} 62% 90%)`, stroke: `hsl(${h} 45% 36%)` }
}
/** Rôles distincts, du plus fréquent au plus rare (ordre stable : même couleur à chaque rendu tant que les données ne changent pas). */
export function roleOrder(nodes: { role: string }[]): string[] {
  const n = new Map<string, number>()
  for (const x of nodes) if (x.role) n.set(x.role, (n.get(x.role) ?? 0) + 1)
  return [...n.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(e => e[0])
}
