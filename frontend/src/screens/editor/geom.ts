// Géométrie partagée des arêtes : composant React Flow et export SVG utilisent exactement les mêmes courbes.
export type Shape = 'rect' | 'ellipse'
export interface Box { cx: number; cy: number; w: number; h: number; shape: Shape }
export interface Pt { x: number; y: number }
export interface EdgeGeom { path: string; lx: number; ly: number; a: Pt; b: Pt; startAngle: number; endAngle: number }

export function borderPoint(bx: Box, tx: number, ty: number): Pt {
  const dx = tx - bx.cx, dy = ty - bx.cy
  if (!dx && !dy) return { x: bx.cx, y: bx.cy }
  if (bx.shape === 'ellipse') { const k = 1 / Math.hypot(dx / (bx.w / 2), dy / (bx.h / 2)); return { x: bx.cx + dx * k, y: bx.cy + dy * k } }
  const k = 1 / Math.max(Math.abs(dx) / (bx.w / 2), Math.abs(dy) / (bx.h / 2))
  return { x: bx.cx + dx * k, y: bx.cy + dy * k }
}

/** Courbe entre deux boîtes (segment, arc si `offset` ≠ 0, boucle si `self`). Les angles sont ceux de la tangente aux extrémités, orientée vers l'extérieur. */
export function edgeGeom(s: Box, t: Box, offset: number, self: boolean): EdgeGeom {
  if (self) {
    const x = s.cx + s.w / 2, y = s.cy - 8
    return { path: `M ${x} ${y} C ${x + 70} ${y - 50}, ${x + 70} ${y + 50}, ${x} ${y + 16}`, lx: x + 62, ly: y, a: { x, y }, b: { x, y: y + 16 }, startAngle: Math.atan2(-50, 70), endAngle: Math.atan2(-34, -70) }
  }
  const a = borderPoint(s, t.cx, t.cy), b = borderPoint(t, s.cx, s.cy)
  const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
  const len = Math.hypot(b.x - a.x, b.y - a.y) || 1
  const nx = -(b.y - a.y) / len, ny = (b.x - a.x) / len
  const o = offset * 34
  const qx = mx + nx * o * 2, qy = my + ny * o * 2
  const lx = mx + nx * o, ly = my + ny * o
  if (!o) { const ang = Math.atan2(b.y - a.y, b.x - a.x); return { path: `M ${a.x} ${a.y} L ${b.x} ${b.y}`, lx, ly, a, b, startAngle: ang + Math.PI, endAngle: ang } }
  return { path: `M ${a.x} ${a.y} Q ${qx} ${qy} ${b.x} ${b.y}`, lx, ly, a, b, startAngle: Math.atan2(a.y - qy, a.x - qx), endAngle: Math.atan2(b.y - qy, b.x - qx) }
}
