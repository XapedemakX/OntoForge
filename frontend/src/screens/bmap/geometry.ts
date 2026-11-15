// Géométrie du dessin : largeur de texte estimée, coupe des légendes de nœuds, courbes de Bézier quadratiques,
// rectangles orientés (OBB) pour placer les libellés d'arêtes sans qu'ils se chevauchent ni masquent un nœud.
export interface Pt { x: number; y: number }

/** Largeur approximative d'un texte sans-serif (aucune mesure du navigateur : le rendu doit aussi marcher hors DOM). */
export function textWidth(s: string, fs: number, bold = false): number {
  let w = 0
  for (const ch of s) {
    if ('ijlI|!\'.,:;'.includes(ch)) w += 0.28
    else if ('ftr()[]-/ '.includes(ch)) w += 0.34
    else if ('mwMW'.includes(ch)) w += 0.82
    else if (ch >= 'A' && ch <= 'Z') w += 0.66
    else if (ch >= '0' && ch <= '9') w += 0.56
    else w += 0.52
  }
  return w * fs * (bold ? 1.07 : 1)
}

/** Coupe un nom en deux lignes (frontière de mot ou de casse) si une seule ligne dépasse `maxW`. */
export function splitCaption(name: string, fs: number, maxW: number): string[] {
  if (textWidth(name, fs, true) <= maxW) return [name]
  const cuts: number[] = []
  for (let i = 1; i < name.length; i++) {
    const a = name[i - 1], b = name[i]
    if (a === ' ' || a === '_' || a === '-') cuts.push(i)
    else if (a >= 'a' && a <= 'z' && b >= 'A' && b <= 'Z') cuts.push(i)
  }
  if (!cuts.length) return [name]
  const best = cuts.reduce((m, i) => (Math.abs(i - name.length / 2) < Math.abs(m - name.length / 2) ? i : m))
  return [name.slice(0, best).trim().replace(/[_-]$/, ''), name.slice(best).trim()]
}

export const quad = (p0: Pt, c: Pt, p1: Pt, t: number): { p: Pt; ang: number } => {
  const u = 1 - t
  return {
    p: { x: u * u * p0.x + 2 * u * t * c.x + t * t * p1.x, y: u * u * p0.y + 2 * u * t * c.y + t * t * p1.y },
    ang: Math.atan2(2 * u * (c.y - p0.y) + 2 * t * (p1.y - c.y), 2 * u * (c.x - p0.x) + 2 * t * (p1.x - c.x)),
  }
}
export const dist = (a: Pt, b: Pt) => Math.hypot(a.x - b.x, a.y - b.y)

export function obb(c: Pt, ang: number, w: number, h: number): Pt[] {
  const ux = Math.cos(ang), uy = Math.sin(ang), vx = -uy, vy = ux
  return ([[-1, -1], [1, -1], [1, 1], [-1, 1]] as const).map(([sx, sy]) => ({ x: c.x + (sx * ux * w) / 2 + (sy * vx * h) / 2, y: c.y + (sx * uy * w) / 2 + (sy * vy * h) / 2 }))
}
/** Théorème de l'axe séparateur sur deux quadrilatères convexes. */
export function obbOverlap(a: Pt[], b: Pt[]): boolean {
  for (const poly of [a, b]) {
    for (let k = 0; k < 4; k++) {
      const p = poly[k], q = poly[(k + 1) % 4]
      const nx = q.y - p.y, ny = p.x - q.x
      const pa = a.map(v => nx * v.x + ny * v.y), pb = b.map(v => nx * v.x + ny * v.y)
      if (Math.max(...pa) < Math.min(...pb) || Math.max(...pb) < Math.min(...pa)) return false
    }
  }
  return true
}
export function circleHitsObb(c: Pt, r: number, ang: number, center: Pt, w: number, h: number): boolean {
  const dx = c.x - center.x, dy = c.y - center.y, ux = Math.cos(ang), uy = Math.sin(ang)
  const lx = dx * ux + dy * uy, ly = -dx * uy + dy * ux
  return Math.hypot(Math.max(Math.abs(lx) - w / 2, 0), Math.max(Math.abs(ly) - h / 2, 0)) < r
}
/** Angle ramené dans ]-90°, 90°] : le texte ne se lit jamais à l'envers. */
export const readable = (a: number) => (a > Math.PI / 2 ? a - Math.PI : a < -Math.PI / 2 ? a + Math.PI : a)

/** Abrège un volume : 713, 1,5k, 12k, 6,92M. */
export function shortCount(n: number | null, dec = '.'): string {
  if (n == null) return ''
  const f = (v: number, d: number) => v.toFixed(d).replace('.', dec)
  if (n < 1000) return String(n)
  if (n < 1e4) return f(n / 1e3, 1) + 'k'
  if (n < 1e6) return Math.round(n / 1e3) + 'k'
  if (n < 1e7) return f(n / 1e6, 2) + 'M'
  if (n < 1e9) return f(n / 1e6, 1) + 'M'
  return f(n / 1e9, 2) + 'G'
}

/** Notes du scénario en Markdown simple : titres (#), listes (- ou *), gras (** **), paragraphes. */
export interface NoteLine { text: string; bold: boolean; indent: number; gap?: boolean }
export function noteLines(md: string, maxW: number, fs: number): NoteLine[] {
  const out: NoteLine[] = []
  for (const raw of md.replace(/\r/g, '').split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim()) { out.push({ text: '', bold: false, indent: 0, gap: true }); continue }
    let bold = false, indent = 0, body = line.trim(), bullet = false
    const h = /^#{1,6}\s+(.*)$/.exec(body)
    if (h) { bold = true; body = h[1] }
    const b = /^[-*]\s+(.*)$/.exec(body)
    if (b) { bullet = true; body = b[1]; indent = fs * 0.9 }
    if (/^\*\*(.+)\*\*$/.test(body)) { bold = true; body = body.slice(2, -2) }
    body = body.replace(/\*\*(.+?)\*\*/g, '$1').replace(/`([^`]+)`/g, '$1')
    const words = body.split(/\s+/); let cur = bullet ? '· ' : ''; let first = true
    const avail = maxW - indent
    for (const w of words) {
      const test = cur.trim() ? cur + ' ' + w : cur + w
      if (textWidth(test, fs, bold) > avail && cur.trim()) { out.push({ text: cur, bold, indent: first ? indent : indent + (bullet ? fs * 0.6 : 0) }); first = false; cur = w } else cur = test
    }
    if (cur.trim()) out.push({ text: cur, bold, indent: first ? indent : indent + (bullet ? fs * 0.6 : 0) })
  }
  return out
}
