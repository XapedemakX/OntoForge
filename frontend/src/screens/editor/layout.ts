import dagre from '@dagrejs/dagre'

export const NODE_W = 196
export const NODE_H = 52

/** Disposition hiérarchique (parent en haut) à partir des liens enfant -> parent. */
export function autoLayout(ids: string[], isa: [string, string][], rel: [string, string][] = []): Map<string, { x: number; y: number }> {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'TB', nodesep: 36, ranksep: 78, marginx: 20, marginy: 20 })
  g.setDefaultEdgeLabel(() => ({}))
  const set = new Set(ids)
  ids.forEach(i => g.setNode(i, { width: NODE_W, height: NODE_H }))
  for (const [child, parent] of isa) if (set.has(child) && set.has(parent) && child !== parent) g.setEdge(parent, child, { weight: 3 })
  for (const [a, b] of rel) if (set.has(a) && set.has(b) && a !== b) g.setEdge(a, b, { weight: 1, minlen: 1 })
  dagre.layout(g)
  // rangs très larges : on les replie en plusieurs lignes pour garder un graphe lisible (proche de 16:10)
  const ranks = new Map<number, string[]>()
  ids.forEach(i => { const n = g.node(i); const k = Math.round(n.y); ranks.set(k, [...(ranks.get(k) ?? []), i]) })
  const per = Math.max(4, Math.min(7, Math.ceil(Math.sqrt(ids.length * 1.6))))
  const out = new Map<string, { x: number; y: number }>()
  let y = 0
  for (const k of [...ranks.keys()].sort((a, b) => a - b)) {
    const row = ranks.get(k)!.sort((a, b) => g.node(a).x - g.node(b).x)
    const chunks = Math.ceil(row.length / per)
    for (let c = 0; c < chunks; c++) {
      const part = row.slice(c * Math.ceil(row.length / chunks), (c + 1) * Math.ceil(row.length / chunks))
      const mid = part.reduce((s, i) => s + g.node(i).x, 0) / part.length
      const w = part.length * (NODE_W + 40)
      const x0 = chunks === 1 ? null : mid - w / 2
      part.forEach((i, j) => out.set(i, { x: Math.round(x0 === null ? g.node(i).x - NODE_W / 2 : x0 + j * (NODE_W + 40)), y }))
      y += NODE_H + (c === chunks - 1 ? 78 : 40)
    }
  }
  return out
}

/** Nom local PascalCase à partir d'un texte libre (« Pièce détachée » -> « PieceDetachee »). */
export function toLocalName(text: string): string {
  const s = text.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^A-Za-z0-9]+/g, ' ').trim()
  return s.split(' ').filter(Boolean).map(w => w[0].toUpperCase() + w.slice(1)).join('') || 'Classe'
}
