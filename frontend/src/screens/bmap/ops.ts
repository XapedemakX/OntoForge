// Modifications pures de la carte (carte -> carte). L'écran les applique, empile l'état précédent pour « Annuler » et enregistre.
import type { BMap, BNode, BScenario, BZone } from './types'

const uid = (p: string) => `${p}-${Date.now().toString(36)}${Math.floor(Math.random() * 1e3).toString(36)}`
const inRect = (z: { x: number; y: number; w: number; h: number }, x: number, y: number) => x >= z.x && x <= z.x + z.w && y >= z.y && y <= z.y + z.h

/** Zone qui contient le point (la plus petite si elles se recouvrent). */
export function zoneAt(m: BMap, x: number, y: number): BZone | null {
  return m.zones.filter(z => inRect(z, x, y)).sort((a, b) => a.w * a.h - b.w * b.h)[0] ?? null
}

/** Emplacement libre dans une zone : point de la grille le plus éloigné des autres nœuds, sous le titre. */
export function freeSpot(m: BMap, zone: BZone, r: number, skip: string): { x: number; y: number } {
  const others = m.nodes.filter(n => n.id !== skip)
  const top = zone.y + Math.min(110, zone.h * 0.3) + r, step = Math.max(12, r / 2)
  let best = { x: zone.x + zone.w / 2, y: zone.y + zone.h / 2 }, score = -1
  for (let x = zone.x + r + 10; x <= zone.x + zone.w - r - 10; x += step) {
    for (let y = top; y <= zone.y + zone.h - r - 10; y += step) {
      const d = Math.min(1e9, ...others.map(n => Math.hypot(n.x - x, n.y - y) - n.r - r))
      if (d > score) { score = d; best = { x, y } }
    }
  }
  return best
}

const withNodes = (m: BMap, nodes: BNode[]): BMap => ({ ...m, nodes, zones: m.zones.map(z => ({ ...z, members: nodes.filter(n => n.zone === z.id).map(n => n.id) })) })

export function setNode(m: BMap, id: string, patch: Partial<BNode>): BMap {
  return withNodes(m, m.nodes.map(n => (n.id === id ? { ...n, ...patch } : n)))
}
/** Change la zone d'un nœud. `place` : replace le nœud dans la zone d'arrivée si sa position n'y est pas déjà. */
export function moveToZone(m: BMap, id: string, zoneId: string | null, place = true): BMap {
  const n = m.nodes.find(x => x.id === id); if (!n || n.zone === zoneId) return m
  const z = zoneId ? m.zones.find(x => x.id === zoneId) : null
  const patch: Partial<BNode> = { zone: zoneId }
  if (z && place && !inRect(z, n.x, n.y)) Object.assign(patch, freeSpot(m, z, n.r, id), { pinned: false })
  return setNode(m, id, patch)
}
export function setZone(m: BMap, id: string, patch: Partial<BZone>): BMap {
  return { ...m, zones: m.zones.map(z => (z.id === id ? { ...z, ...patch } : z)) }
}
export function addZone(m: BMap, title: string): { map: BMap; id: string } {
  const id = uid('z'), hues = ['#7c5cff', '#2f9e6e', '#d9822b', '#3b82f6', '#d6477a', '#14a3a3']
  const w = 420, h = 280, y = m.canvas.h + 30
  const z: BZone = { id, title, subtitle: '', color: hues[m.zones.length % hues.length], members: [], x: 30, y, w, h }
  return { map: { ...m, zones: [...m.zones, z], canvas: { ...m.canvas, h: y + h + 30 } }, id }
}
export function delZone(m: BMap, id: string): BMap {
  return withNodes({ ...m, zones: m.zones.filter(z => z.id !== id) }, m.nodes.map(n => (n.zone === id ? { ...n, zone: null } : n)))
}
export function setScenario(m: BMap, id: string, patch: Partial<BScenario>): BMap {
  return { ...m, scenarios: m.scenarios.map(s => (s.id === id ? { ...s, ...patch } : s)) }
}
export function addScenario(m: BMap, name: string): { map: BMap; id: string } {
  const id = uid('s')
  return { map: { ...m, scenarios: [...m.scenarios, { id, name, description: '', edge_styles: {}, nodes: [] }] }, id }
}
export const delScenario = (m: BMap, id: string): BMap => ({ ...m, scenarios: m.scenarios.filter(s => s.id !== id) })
/** Style d'une arête dans un scénario ; `null` retire la surcharge (retour au style de base). */
export function setEdgeStyle(m: BMap, scId: string, edgeId: string, style: string | null): BMap {
  const sc = m.scenarios.find(s => s.id === scId); if (!sc) return m
  const es = { ...sc.edge_styles }
  if (style) es[edgeId] = style; else delete es[edgeId]
  return setScenario(m, scId, { edge_styles: es })
}
export function toggleScenarioNode(m: BMap, scId: string, nodeId: string): BMap {
  const sc = m.scenarios.find(s => s.id === scId); if (!sc) return m
  return setScenario(m, scId, { nodes: sc.nodes.includes(nodeId) ? sc.nodes.filter(x => x !== nodeId) : [...sc.nodes, nodeId] })
}
