// Modèle d'affichage de l'éditeur (L26) : du graphe du serveur, du mode (classique / VOWL) et des filtres aux nœuds et arêtes réellement dessinés.
// Fonction pure : l'éditeur la rejoue pour obtenir les totaux (« affichés sur X »), l'export SVG lit le résultat tel qu'affiché.
import type { GraphData, ProposalItem } from './types'
import type { Mode, ShowPrefs } from './prefs'

export type VK = 'class' | 'thing' | 'datatype' | 'anon'
export interface MNode {
  id: string; vk: VK; label: string; icon: string | null; abstract: boolean; deprecated: boolean; external: boolean
  /** Libellés des classes équivalentes fusionnées dans ce nœud (VOWL : double cercle). */
  merged: string[]; op?: 'and' | 'or' | 'not'; status?: 'add' | 'modify'
  /** Classe qui porte ce satellite (datatype, Thing, classe anonyme) : sa position en dérive. */
  owner?: string
  /** Voisins repliés par le curseur de densité (badge « +n »). */
  hid: number
  /** La classe existe dans l'ontologie (modifiable) ; faux pour les classes externes et les propositions. */
  declared: boolean
}
export interface MEdge {
  id: string; source: string; target: string; kind: string; label: string; iri: string | null; status?: 'add' | 'modify'
  inverse?: string; chars: string[]; deprecated: boolean; offset: number
}
export interface ViewModel { nodes: MNode[]; edges: MEdge[]; collapsed: number }
export interface ViewIn {
  graph: GraphData; ghostClasses: ProposalItem[]; ghostEdges: ProposalItem[]; mode: Mode; show: ShowPrefs
  modClasses: Set<string>; modProps: Set<string>; keep: Set<string>; declared: (iri: string) => boolean
}

const dtName = (iri: string) => iri.split(/[#/]/).pop() || iri

export function buildView(inp: ViewIn): ViewModel {
  const { graph, mode, show } = inp
  const vowl = mode === 'vowl'
  const byId = new Map(graph.nodes.map(n => [n.id, n]))
  const nodes = new Map<string, MNode>()
  const mk = (n: Partial<MNode> & { id: string; vk: VK; label: string }): MNode => ({ icon: null, abstract: false, deprecated: false, external: false, merged: [], hid: 0, declared: false, ...n })

  // ---- classes (et satellites propres au VOWL) ----
  for (const n of graph.nodes) {
    if (n.kind === 'class') {
      if (!show.dep && n.deprecated) continue
      nodes.set(n.id, mk({ id: n.id, vk: 'class', label: n.label, icon: n.icon, abstract: n.abstract, deprecated: n.deprecated, external: !!vowl && !!n.external, declared: inp.declared(n.id), status: inp.modClasses.has(n.id) && show.krakie ? 'modify' : undefined }))
    } else if (vowl && n.kind === 'thing') nodes.set(n.id, mk({ id: n.id, vk: 'thing', label: n.label }))
    else if (vowl && (n.kind as string) === 'anonymous') nodes.set(n.id, mk({ id: n.id, vk: 'anon', label: n.label, op: (n as unknown as { op: 'and' | 'or' | 'not' }).op }))
  }
  if (show.krakie) for (const i of inp.ghostClasses) if (!nodes.has(i.iri)) nodes.set(i.iri, mk({ id: i.iri, vk: 'class', label: i.label, status: 'add' }))

  // ---- classes équivalentes fusionnées (VOWL) ----
  const rep = new Map<string, string>()
  const find = (x: string): string => { let r = x; while (rep.has(r) && rep.get(r) !== r) r = rep.get(r)!; return r }
  if (vowl && show.disj) {
    for (const e of graph.edges) if (e.kind === 'equivalentClass' && nodes.get(e.source)?.vk === 'class' && nodes.get(e.target)?.vk === 'class') {
      const a = find(e.source), b = find(e.target)
      if (a !== b) { const pa = nodes.get(a)!, pb = nodes.get(b)!; const aFirst = pa.external !== pb.external ? !pa.external : a < b; const [lo, hi] = aFirst ? [a, b] : [b, a]; rep.set(hi, lo); rep.set(lo, lo) }
    }
    for (const id of [...nodes.keys()]) {
      const r = find(id)
      if (r !== id) { nodes.get(r)!.merged.push(nodes.get(id)!.label); nodes.delete(id) }
    }
  }
  const map = (id: string) => (rep.has(id) ? find(id) : id)

  // ---- arêtes ----
  const hiddenIds = new Set<string>(); const inv = new Map<string, string>()
  const eById = new Map(graph.edges.map(e => [e.id, e]))
  // inverses : fusion en une arête à double pointe seulement si les extrémités se correspondent (a : X→Y, b : Y→X) ;
  // sinon les deux arêtes restent, car masquer b ferait perdre son domaine et son image propres (revue w3c L26).
  for (const e of graph.edges) if (e.kind === 'inverseOf') {
    const a = eById.get(e.source), b = eById.get(e.target)
    if (a && b && a.source === b.target && a.target === b.source) { inv.set(a.id, b.label); hiddenIds.add(b.id) }
  }
  // inverse sans domaine ni image propres : le serveur porte son libellé sur les arêtes de l'autre propriété
  for (const e of graph.edges) if (e.inverse_label && !inv.has(e.id)) inv.set(e.id, e.inverse_label)
  const modProp = (iri: string | null) => (iri && inp.modProps.has(iri) && show.krakie ? ('modify' as const) : undefined)
  const raw: MEdge[] = []
  const push = (e: Omit<MEdge, 'offset' | 'chars' | 'deprecated'> & { chars?: string[]; deprecated?: boolean }) => raw.push({ chars: [], deprecated: false, offset: 0, ...e })
  for (const e of graph.edges) {
    if (hiddenIds.has(e.id) || e.kind === 'inverseOf') continue
    const k = e.kind
    const visibleKind = k === 'subClassOf' ? show.sub : k === 'objectProperty' ? show.rel : k === 'disjointWith' || k === 'equivalentClass' ? show.disj : k === 'anonymousOf' ? true : false
    if (k === 'datatypeProperty') {
      if (!vowl || !show.dt) continue
      const src = map(e.source); if (!nodes.has(src)) continue
      const id = `dt|${e.id}`
      nodes.set(id, mk({ id, vk: 'datatype', label: dtName(e.target), owner: src }))
      push({ id: e.id, source: src, target: id, kind: k, label: e.label, iri: e.iri, chars: (e as { functional?: boolean }).functional ? ['functional'] : [], deprecated: !!(e as { deprecated?: boolean }).deprecated })
      continue
    }
    if (!visibleKind) continue
    let s = map(e.source), t = map(e.target)
    const sn = nodes.get(s), tn = nodes.get(t)
    if (!sn || !tn) continue
    if (sn.vk === 'anon' || tn.vk === 'anon') { // classe anonyme : visible si l'axiome qui la porte l'est
      const own = sn.vk === 'anon' ? sn : tn
      if (k === 'anonymousOf') { own.owner = own.owner ?? graph.edges.find(x => x.target === own.id && x.kind !== 'anonymousOf')?.source }
      else own.owner = own.owner ?? (sn.vk === 'anon' ? t : s)
    }
    if (sn.vk === 'thing' || tn.vk === 'thing') { const th = sn.vk === 'thing' ? sn : tn; th.owner = sn.vk === 'thing' ? t : s }
    if (s === t && k !== 'objectProperty') continue
    push({ id: e.id, source: s, target: t, kind: k, label: k === 'objectProperty' ? e.label : k === 'anonymousOf' ? e.label : '', iri: e.iri, inverse: inv.get(e.id),
      chars: (e as { characteristics?: string[] }).characteristics ?? [], deprecated: !!(e as { deprecated?: boolean }).deprecated, status: modProp(e.iri) })
  }
  if (show.krakie) for (const i of inp.ghostEdges) {
    if (!i.source || !i.target) continue
    const s = map(i.source), t = map(i.target)
    if (!nodes.has(s) || !nodes.has(t)) continue
    if (i.kind === 'subClassOf' ? !show.sub : !show.rel) continue
    push({ id: `ghost|${i.kind}|${i.source}|${i.target}|${i.iri}`, source: s, target: t, kind: i.kind, label: i.kind === 'objectProperty' ? i.label : '', iri: i.kind === 'objectProperty' ? i.iri : null, status: 'add' })
  }
  // doublons après fusion des équivalentes
  const seen = new Set<string>(); let edges = raw.filter(e => { const k = `${e.kind}|${e.iri}|${e.source}|${e.target}`; if (seen.has(k)) return false; seen.add(k); return true })

  // classes anonymes dont l'axiome porteur est masqué : retirées avec leurs arêtes
  for (const [id, n] of [...nodes]) if (n.vk === 'anon' && !edges.some(e => e.kind !== 'anonymousOf' && (e.source === id || e.target === id))) nodes.delete(id)
  edges = edges.filter(e => nodes.has(e.source) && nodes.has(e.target))

  // ---- densité : replie les classes de degré ≤ N (WebVOWL « degree of collapsing ») ----
  let collapsed = 0
  if (show.density > 0) {
    const deg = new Map<string, number>(); const nb = new Map<string, string[]>()
    for (const e of edges) {
      if (!['subClassOf', 'objectProperty'].includes(e.kind) || e.source === e.target) continue
      if (nodes.get(e.source)?.vk !== 'class' || nodes.get(e.target)?.vk !== 'class') continue
      for (const [a, b] of [[e.source, e.target], [e.target, e.source]]) { deg.set(a, (deg.get(a) ?? 0) + 1); nb.set(a, [...(nb.get(a) ?? []), b]) }
    }
    const drop = new Set<string>()
    for (const n of nodes.values()) {
      if (n.vk !== 'class' || n.status || inp.keep.has(n.id)) continue
      if ((deg.get(n.id) ?? 0) <= show.density) drop.add(n.id)
    }
    for (const id of drop) { const ns = nb.get(id) ?? []; if (ns.length === 1 && !drop.has(ns[0])) nodes.get(ns[0])!.hid++ }
    for (const n of nodes.values()) if (n.owner && drop.has(n.owner)) drop.add(n.id)
    collapsed = [...drop].filter(id => nodes.get(id)?.vk === 'class').length
    for (const id of drop) nodes.delete(id)
    edges = edges.filter(e => nodes.has(e.source) && nodes.has(e.target))
  }
  // satellites sans propriétaire ou orphelins après filtrage : on les retire
  for (const [id, n] of [...nodes]) if (n.vk !== 'class' && !edges.some(e => e.source === id || e.target === id)) nodes.delete(id)

  // ---- arcs parallèles ----
  const groups = new Map<string, number>(); const idx = new Map<string, number>()
  const gk = (e: MEdge) => [e.source, e.target].sort().join('|')
  edges.forEach(e => groups.set(gk(e), (groups.get(gk(e)) ?? 0) + 1))
  edges = edges.map(e => { const k = gk(e); const i = idx.get(k) ?? 0; idx.set(k, i + 1); const n = groups.get(k)!; return { ...e, offset: n > 1 ? i - (n - 1) / 2 : 0 } })
  void byId
  return { nodes: [...nodes.values()], edges, collapsed }
}
