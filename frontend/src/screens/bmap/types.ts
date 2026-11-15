// Carte métier : types du contrat GET/PUT /api/projects/{id}/business-map (docs/CONTRACTS.md, section « Carte métier »)
// et normalisation défensive de la réponse (le dessin ne doit jamais planter sur un champ absent).

export type EdgeStyle = 'scored' | 'gate' | 'read' | 'context' | 'context_off' | 'grouped' | 'disabled' | 'both' | 'mention' | 'oneway'
export const EDGE_STYLES: EdgeStyle[] = ['scored', 'gate', 'read', 'context', 'context_off', 'grouped', 'disabled', 'both', 'mention', 'oneway']
/** Style tiré d'un cadre (une seule flèche pour tous les membres) : jamais choisi à la main. */
export type DrawnStyle = EdgeStyle | 'bundle' | 'subclass' | 'plain' | 'symmetric'
export const isEdgeStyle = (s: unknown): s is EdgeStyle => typeof s === 'string' && (EDGE_STYLES as string[]).includes(s)

export type Source = 'ontology' | 'target'
/** Identifiants attendus par POST …/suggest-zones (`llm` = Krakie). */
export type ZoneStrategy = 'perimeters' | 'hierarchy' | 'namespace' | 'communities' | 'llm'
export const ZONE_STRATEGIES: ZoneStrategy[] = ['perimeters', 'hierarchy', 'namespace', 'communities', 'llm']

export interface BRect { x: number; y: number; w: number; h: number }
export interface BZone extends BRect { id: string; title: string; subtitle: string; color: string; members: string[] }
export interface BNode { id: string; label: string; role: string; roleSource: 'auto' | 'manual'; zone: string | null; count: number | null; faded: boolean; pinned: boolean; x: number; y: number; r: number }
export interface BEdge { id: string; from: string; to: string; label: string; kind: string; both: boolean; inverse_label: string | null; frame: string | null; link: 'inverse' | 'symmetric' | null; union: boolean }
export interface BLegendRole { role: string; label: string; color: string; count: number }
export interface BFrame extends BRect { id: string; title: string; members: string[]; note: string }
export interface BScenario { id: string; name: string; description: string; edge_styles: Record<string, string>; nodes: string[] }
export interface BMeta { title: string; date: string; types: number; relations: number; generated: boolean; skipped: { id: string; label: string }[]; unions: number }
export interface BMap {
  zones: BZone[]; nodes: BNode[]; edges: BEdge[]; frames: BFrame[]; scenarios: BScenario[]; legend: BLegendRole[]
  canvas: { w: number; h: number }; meta: BMeta
}

const num = (v: unknown, d = 0) => (typeof v === 'number' && isFinite(v) ? v : d)
const str = (v: unknown, d = '') => (typeof v === 'string' ? v : v == null ? d : String(v))
const arr = <T = unknown>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : [])
type Raw = Record<string, unknown>
const rectOf = (o: Raw): BRect => {
  const r = (o.rect ?? o.rectangle) as Raw | undefined
  const s = r && typeof r === 'object' ? r : o
  return { x: num(s.x), y: num(s.y), w: num(s.w ?? s.width, 200), h: num(s.h ?? s.height, 150) }
}

/** Accepte le rectangle à plat (x, y, w, h) ou imbriqué (rect / rectangle) ; ne garde que la forme à plat. */
export function normalizeMap(raw: unknown): BMap {
  const m = (raw ?? {}) as Raw
  const nodes: BNode[] = arr<Raw>(m.nodes).map(n => ({
    id: str(n.id), label: str(n.label ?? n.id), role: str(n.role), roleSource: n.role_source === 'manual' ? 'manual' : 'auto', zone: n.zone == null ? null : str(n.zone),
    count: typeof n.count === 'number' ? n.count : null, faded: !!n.faded, pinned: !!n.pinned, x: num(n.x), y: num(n.y), r: num(n.r, 40) || 40,
  }))
  const zones: BZone[] = arr<Raw>(m.zones).map(z => ({ id: str(z.id), title: str(z.title ?? z.id), subtitle: str(z.subtitle), color: str(z.color, '#94a3b8'), members: arr<string>(z.members).map(String), ...rectOf(z) }))
  const edges: BEdge[] = arr<Raw>(m.edges).map(e => ({
    id: str(e.id), from: str(e.from ?? e.source), to: str(e.to ?? e.target), label: str(e.label), kind: str(e.kind),
    both: e.both != null ? !!e.both : e.direction === 'both', inverse_label: e.inverse_label == null || e.inverse_label === '' ? null : str(e.inverse_label),
    // une arête de cadre part du cadre : `source_kind: 'frame'` (serveur) ou `frame` (forme à plat)
    frame: e.source_kind === 'frame' ? str(e.source) : e.frame == null || e.frame === '' ? null : str(e.frame),
    link: e.link === 'symmetric' ? 'symmetric' : e.link === 'inverse' ? 'inverse' : null, union: !!e.union,
  }))
  const frames: BFrame[] = arr<Raw>(m.frames).map(f => ({ id: str(f.id), title: str(f.title ?? f.id), members: arr<string>(f.members).map(String), note: str(f.note), ...rectOf(f) }))
  const scenarios: BScenario[] = arr<Raw>(m.scenarios).map(s => ({
    id: str(s.id), name: str(s.name ?? s.id), description: str(s.description),
    edge_styles: Object.fromEntries(Object.entries((s.edge_styles ?? {}) as Raw).map(([k, v]) => [k, str(v)])), nodes: arr<string>(s.nodes).map(String),
  }))
  const c = (m.canvas ?? {}) as Raw
  const legend: BLegendRole[] = arr<Raw>(m.legend).map(l => ({ role: str(l.role), label: str(l.label ?? l.role), color: str(l.color), count: num(l.count) }))
  const xs = nodes.map(n => n.x + n.r), ys = nodes.map(n => n.y + n.r)
  const meta = (m.meta ?? {}) as Raw
  return {
    zones, nodes, edges, frames, scenarios, legend,
    canvas: { w: num(c.w ?? c.width, Math.max(800, ...xs, ...zones.map(z => z.x + z.w)) + 40), h: num(c.h ?? c.height, Math.max(600, ...ys, ...zones.map(z => z.y + z.h)) + 40) },
    meta: { title: str(meta.title), date: str(meta.date ?? meta.model_date), types: num(meta.types ?? meta.n_types, nodes.length), relations: num(meta.relations ?? meta.n_relations, edges.filter(e => e.kind !== 'subclass' && !e.frame).length), generated: !!meta.generated,
      skipped: arr<Raw>(meta.skipped).map(s => ({ id: str(s.id), label: str(s.label ?? s.id) })), unions: num(meta.n_union) },
  }
}

/** Corps du PUT : seul ce que l'humain décide est envoyé (le serveur recalcule arêtes, rectangles de zone et rôles déduits). */
export function toPut(m: BMap) {
  const ids = (f: (n: BNode) => boolean) => m.nodes.filter(f).map(n => n.id)
  return {
    zones: m.zones.map(z => ({ id: z.id, title: z.title, subtitle: z.subtitle, color: z.color, members: ids(n => n.zone === z.id) })),
    roles: Object.fromEntries(m.nodes.filter(n => n.role.trim()).map(n => [n.id, n.role.trim().slice(0, 40)])),
    faded: ids(n => n.faded), pinned: ids(n => n.pinned),
    positions: Object.fromEntries(m.nodes.map(n => [n.id, { x: n.x, y: n.y }])),
    frames: m.frames.map(f => ({ id: f.id, title: f.title, members: f.members, note: f.note })),
    scenarios: m.scenarios.map(s => ({ id: s.id, name: s.name, description: s.description, edge_styles: s.edge_styles, nodes: s.nodes })),
  }
}

export function styleOf(e: BEdge, sc: BScenario | null): EdgeStyle | 'subclass' | 'plain' | 'symmetric' {
  const s = sc?.edge_styles[e.id]
  if (isEdgeStyle(s)) return s
  if (isEdgeStyle(e.kind)) return e.kind
  if (e.kind === 'subclass') return 'subclass'
  return e.both ? (e.link === 'symmetric' ? 'symmetric' : 'both') : 'plain'
}
export const drawnStyle = (e: BEdge, sc: BScenario | null): DrawnStyle => (e.frame ? 'bundle' : styleOf(e, sc))
