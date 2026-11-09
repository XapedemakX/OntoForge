import { tr } from './i18n'
// Client API typé unique d'OntoForge. Les types reflètent backend/ontoforge/core/*.py.

export type LangText = Record<string, string>
export type Characteristic = 'functional' | 'inverseFunctional' | 'transitive' | 'symmetric' | 'asymmetric' | 'reflexive' | 'irreflexive'
export type RestrictionKind = 'some' | 'only' | 'min' | 'max' | 'exactly' | 'value' | 'self'
export type Target = 'curiosity' | 'neo4j'

export interface LiteralValue { value: string; datatype?: string | null; lang?: string | null }
export interface Annotation { property: string; value: string; is_iri: boolean; datatype?: string | null; lang?: string | null }
export interface ClassExpr {
  op: string; iri?: string | null; args: ClassExpr[]; individuals: string[]; property?: string | null
  inverse: boolean; n?: number | null; filler?: ClassExpr | null; data_range?: string | null; value?: LiteralValue | string | null
}
export interface Restriction {
  property: string; inverse: boolean; kind: RestrictionKind; n?: number | null
  filler?: string | null; filler_expr?: ClassExpr | null; value?: LiteralValue | string | null
}
export interface Entity { iri: string; labels: LangText; comments: LangText; annotations: Annotation[]; deprecated: boolean }
export interface OntClass extends Entity {
  sub_class_of: string[]; restrictions: Restriction[]; super_expressions: ClassExpr[]; equivalent_to: ClassExpr[]
  disjoint_with: string[]; disjoint_union_of: string[][]; has_keys: string[][]; one_of?: string[] | null
}
export interface ObjectProperty extends Entity {
  domain: string[]; range: string[]; domain_union: string[]; range_union: string[]
  domain_expr?: ClassExpr | null; range_expr?: ClassExpr | null; inverse_of?: string | null
  sub_property_of: string[]; equivalent_to: string[]; disjoint_with: string[]; chains: string[][]
  characteristics: Characteristic[]
}
export interface DatatypeProperty extends Entity {
  domain: string[]; domain_union: string[]; domain_expr?: ClassExpr | null; range: string[]; range_expr?: unknown
  functional: boolean; sub_property_of: string[]; equivalent_to: string[]; disjoint_with: string[]
}
export interface Fact { property: string; value: string; is_iri: boolean; datatype?: string | null; lang?: string | null; negative: boolean }
export interface Individual extends Entity { types: string[]; facts: Fact[]; same_as: string[]; different_from: string[] }
export interface OntologyMeta extends Entity { version_iri?: string | null; imports: string[]; prefixes: Record<string, string> }
export interface UnmappedAxiom { description: string; triples: [string, string, string][]; subject?: string | null }
export interface OntoModel {
  meta: OntologyMeta
  classes: Record<string, OntClass>
  object_properties: Record<string, ObjectProperty>
  datatype_properties: Record<string, DatatypeProperty>
  annotation_properties: Record<string, Entity>
  datatypes: Record<string, Entity>
  individuals: Record<string, Individual>
  all_different: string[][]
  unmapped: UnmappedAxiom[]
}

// SHACL
export interface ShPath { kind: string; iri?: string | null; args: ShPath[] }
export interface ShConstraints {
  class?: string[]; datatype?: string | null; node_kind?: string | null; node?: string[]; in?: unknown[]
  has_value?: unknown[]; pattern?: string | null; min_length?: number | null; max_length?: number | null
  min_inclusive?: string | null; max_inclusive?: string | null; min_exclusive?: string | null; max_exclusive?: string | null
  and?: string[]; or?: string[]; xone?: string[]; not?: string[]; sparql?: string[]
  severity: 'Violation' | 'Warning' | 'Info'; messages: Record<string, string>; deactivated: boolean
  [k: string]: unknown
}
export interface PropertyShape extends ShConstraints {
  id: string; path: ShPath; names: Record<string, string>; min_count?: number | null; max_count?: number | null
  unique_lang: boolean; qualified: { shape: string; min_count?: number | null; max_count?: number | null }[]
}
export interface NodeShape extends ShConstraints {
  id: string
  targets: { target_class: string[]; target_node: string[]; target_subjects_of: string[]; target_objects_of: string[] }
  properties: PropertyShape[]; closed: boolean; ignored_properties: string[]; labels: Record<string, string>
}
export interface ShapesModel { shapes: Record<string, NodeShape>; property_shapes: Record<string, PropertyShape>; prefixes: Record<string, string>; warnings: string[] }
export interface ShaclResult { focus: string; path?: string | null; severity: string; constraint: string; message: string; value?: string | null; shape?: string | null }
export interface ShaclReport { conforms: boolean; results: ShaclResult[] }

// Property graph
export interface PGProperty {
  name: string; type: string; is_list: boolean; required: boolean; unique: boolean; indexed: boolean
  source?: string | null; description?: string | null; enum: string[]; default?: unknown; pattern?: string | null
  lang?: string | null; note?: string | null
}
export interface NodeType {
  name: string; labels: string[]; source: string[]; key: string[]; properties: PGProperty[]
  description?: string | null; icon?: string | null; abstract: boolean; discriminator?: string | null; discriminator_values: string[]
}
export interface EdgeType {
  name: string; from: string; to: string; reverse?: string | null; source?: string | null; description?: string | null
  properties: PGProperty[]; cardinality: { out: string; in: string }; directed: boolean; symmetric: boolean
  derived: boolean; note?: string | null
}
export interface PGValidation {
  id: string; kind: string; node_type?: string | null; edge_type?: string | null; property?: string | null
  params: Record<string, unknown>; description: string; source?: string | null; severity: string
}
export interface Materialization {
  id: string; kind: string; edge_type?: string | null; chain: string[]; parent?: string | null; node_type?: string | null
  definition?: string | null; description: string; source?: string | null
}
export interface Option { id: string; label: string; impact: string; recommended_for: Target[] }
export type FindingSeverity = 'auto' | 'review' | 'lost' | 'info'
export interface Finding {
  id: string; rule: string; severity: FindingSeverity; title: string; detail: string; subject: string
  related: string[]; options: Option[]; recommended?: string | null; chosen?: string | null; rationale?: string | null
}
export interface PGModel {
  target: Target
  meta: { name: string; iri?: string | null; generated_at?: string | null; ontoforge_version: string }
  node_types: Record<string, NodeType>
  edge_types: EdgeType[]
  validations: PGValidation[]
  materializations: Materialization[]
  findings: Finding[]
  decisions: Record<string, string>
}

export interface Project {
  id: string; name: string; description: string; created_at: string; updated_at: string; target: Target
  onto: OntoModel; shapes: ShapesModel; decisions: Record<string, Record<string, string>>
  source_files: string[]; notes?: string | null
  target_versions?: Partial<Record<VersionKey, string>>
}
export type VersionKey = 'neo4j' | 'cypher' | 'curiosity_library' | 'shacl' | 'sparql' | 'rdf'
export type Support = 'recommended' | 'supported' | 'obsolete' | 'end_of_support' | 'unknown'
export interface VersionChoice { id: string; label: string; support: Support; maturity?: string | null; note: string }
export interface VersionRow { key: VersionKey; family: string; value: string; pinned: boolean; source: 'project' | 'default'; support: Support; status: string; maturity?: string | null; note: string; choices: VersionChoice[] }
export interface VersionGap { key: VersionKey; family: string; value: string; kind: string; severity: 'info' | 'warning' | 'error'; message: string; recommendation: { key: VersionKey; value: string; message: string } | null }
export interface VersionCheck { updated: string; versions: Record<VersionKey, string>; explicit: Partial<Record<VersionKey, string>>; gaps: VersionGap[]; ok: boolean; needs_attention: boolean; recommended: Partial<Record<VersionKey, string>> }
export interface ProjectVersions { versions: Record<VersionKey, string>; explicit: Partial<Record<VersionKey, string>>; defaults: Record<VersionKey, string>; rows: VersionRow[]; standards_updated: string }
export interface ShaclFeature { id: string; since: string; maturity: string; implemented: boolean; label: string }
export interface StandardsRef {
  updated: string; lang: string; legend: Record<string, string>
  w3c: { shacl: { features: ShaclFeature[] } }
  libraries: { note: string; items: { id: string; used: string; latest: string | null; support: Support }[] }
}
export interface ProjectSummary {
  id: string; name: string; description: string; created_at: string; updated_at: string; source_files: string[]; target: Target
  stats: { classes: number; object_properties: number; datatype_properties: number; individuals: number; shapes: number }
}
export interface GenerationRecord { target: Target; perimeter: string | null; at: string; files: string[]; findings_summary: { auto: number; review: number; lost: number; pending: number }; project_updated_at: string }
export interface Perimeter { id: string; name: string; description?: string; classes: string[]; properties: string[]; include_descendants: boolean }
export interface PublicSettings { language?: { ui?: string; labels?: string; assistant?: string }; sparql_endpoint?: { url?: string } | null; sparql_endpoints?: { id: string; name?: string; url: string; active?: boolean }[]; active_sparql_endpoint?: string | null; defaults?: { target?: Target } }
export interface Sample { name: string; title: string; files: unknown }
export interface ConformanceIssue { level: 'error' | 'warning' | 'info'; code: string; message: string; subject?: string | null; spec_ref?: string | null }
export interface ConformanceReport { profiles: Record<string, boolean>; issues: ConformanceIssue[] }
export interface ReasonResult {
  reasoner: string; version: string; status: 'ok' | 'timeout' | 'error'; consistent: boolean | null; duration_ms: number; timeout_s: number; max_memory_mb: number
  dl: { conformant: boolean; violations: string[] }; warnings: string[]; error: string | null
  explanation: null | { justification: boolean; source: string; note: string; individuals: string[]; classes: string[]; items: { individual: string; classes: string[]; kind: string; message: string }[] }
  unsatisfiable: string[]
  hierarchy: { new_subclass: { sub: string; sup: string }[]; new_equivalent: string[][]; counts: Record<string, number> }
  reclassified: { individual: string; declared: string[]; inferred: string[] }[]
}
export interface TranslationResult { cypher?: string | null; curiosity?: string | null; graphql?: string | null; notes: string[]; lossy: boolean }
export interface CompetencyQuestion { question: string; sparql: string; cypher?: string; curiosity?: string }
export interface GenerateResult { files: Record<string, string>; missing?: string[] }
export interface AssistantStatus { provider: string; model: string; configured: boolean }
export interface DraftResult { proposal: OntoModel; explanation: string; warnings: string[] }

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
  /** 501 = module backend pas encore livré */
  get notReady() { return this.status === 501 }
}

const BASE = '/api'

async function req<T>(method: string, path: string, body?: unknown, form?: FormData, text = false): Promise<T> {
  const init: RequestInit = { method }
  if (form) init.body = form
  else if (body !== undefined) { init.body = JSON.stringify(body); init.headers = { 'Content-Type': 'application/json' } }
  let r: Response
  try { r = await fetch(BASE + path, init) } catch { throw new ApiError(0, tr('ui.unreachable')) }
  if (!r.ok) {
    let detail = tr('ui.http', { s: r.status })
    try {
      const j = await r.json()
      detail = typeof j.detail === 'string' ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: { msg?: string }) => d.msg).join(' ; ') : detail
    } catch { /* corps non JSON */ }
    throw new ApiError(r.status, detail)
  }
  return (text ? await r.text() : await r.json()) as T
}

const p = (id: string) => `/projects/${encodeURIComponent(id)}`

export const api = {
  health: () => req<{ status: string; version: string }>('GET', '/health'),
  samples: () => req<Sample[]>('GET', '/samples'),
  listProjects: () => req<ProjectSummary[]>('GET', '/projects'),
  createProject: (b: { name: string; description?: string; sample?: string }) => req<Project>('POST', '/projects', b),
  getProject: (id: string) => req<Project>('GET', p(id)),
  putProject: (pr: Project) => req<Project>('PUT', p(pr.id), pr),
  deleteProject: (id: string) => req<Project>('DELETE', p(id)),
  importFile: (id: string, file: File, kind: 'ontology' | 'shapes' | 'auto' = 'auto') => {
    const f = new FormData(); f.append('file', file); f.append('kind', kind)
    return req<{ project: Project; warnings: string[]; kind?: string }>('POST', p(id) + '/import', undefined, f)
  },
  putOnto: (id: string, o: OntoModel) => req<Project>('PUT', p(id) + '/onto', o),
  putShapes: (id: string, s: ShapesModel) => req<Project>('PUT', p(id) + '/shapes', s),
  dsl: (id: string, text: string, merge: boolean) => req<{ project: Project; errors: { line: number; message: string }[] }>('POST', p(id) + '/dsl', { text, merge }),
  exportOntology: (id: string, format: string) => req<string>('GET', p(id) + `/export/ontology?format=${format}`, undefined, undefined, true),
  exportShapes: (id: string) => req<string>('GET', p(id) + '/export/shapes?format=turtle', undefined, undefined, true),
  reason: (id: string, timeout?: number) => req<ReasonResult>('POST', p(id) + '/reason', { reasoner: 'hermit', ...(timeout ? { timeout } : {}) }),
  conformance: (id: string) => req<ConformanceReport>('GET', p(id) + '/conformance'),
  shaclGenerate: (id: string, merge: boolean) => req<{ project: Project; notes: string[] }>('POST', p(id) + '/shacl/generate', { merge }),
  shaclGenerateDry: (id: string) => req<{ generated: ShapesModel; notes: string[] }>('POST', p(id) + '/shacl/generate', { merge: false, dry_run: true }),
  shaclValidate: (id: string, file: File) => { const f = new FormData(); f.append('file', file); return req<ShaclReport>('POST', p(id) + '/shacl/validate', undefined, f) },
  analyze: (id: string, t: Target) => req<PGModel>('POST', p(id) + `/analyze?target=${t}`),
  decide: (id: string, t: Target, d: Record<string, string | null>) => req<PGModel>('PUT', p(id) + `/decisions/${t}`, d),
  acceptRecommended: (id: string, t: Target, includeLost = false) => req<PGModel>('POST', p(id) + `/decisions/${t}/accept-recommended${includeLost ? '?include_lost=true' : ''}`),
  generate: (id: string, t: Target) => req<GenerateResult>('GET', p(id) + `/generate/${t}`),
  generations: (id: string) => req<GenerationRecord[]>('GET', p(id) + '/generations'),
  zipUrl: (id: string, t: Target) => `${BASE}${p(id)}/generate/${t}/zip`,
  translate: (id: string, t: Target, sparql: string) => req<TranslationResult>('POST', p(id) + `/queries/translate?target=${t}`, { sparql }),
  competency: (id: string, t: Target) => req<CompetencyQuestion[]>('GET', p(id) + `/queries/competency?target=${t}`),
  settings: () => req<PublicSettings>('GET', '/settings'),
  standards: () => req<StandardsRef>('GET', '/standards'),
  versions: (id: string) => req<ProjectVersions>('GET', p(id) + '/versions'),
  putVersions: (id: string, patch: Partial<Record<VersionKey, string | null>>) => req<ProjectVersions>('PUT', p(id) + '/versions', patch),
  versionsCheck: (id: string) => req<VersionCheck>('GET', p(id) + '/versions/check'),
  perimeters: (id: string) => req<Perimeter[]>('GET', p(id) + '/perimeters'),
  setActivePerimeter: (id: string, pid: string | null) => req<{ active_perimeter: string | null }>('PUT', p(id) + '/perimeters/active', { id: pid }),
  assistantStatus: () => req<AssistantStatus>('GET', '/assistant/status'),
  assistantDraft: (text: string, kind: 'text' | 'csv' | 'sql', base_iri?: string) => req<DraftResult>('POST', '/assistant/draft', { text, kind, base_iri: base_iri || null }),
  assistantExplain: (project_id: string, target: Target, finding_id: string) => req<{ text: string }>('POST', '/assistant/explain', { project_id, target, finding_id }),
}

// ---- utilitaires IRI ----
export function localName(iri: string): string {
  for (const s of ['#', '/', ':']) if (iri.includes(s)) { const t = iri.slice(iri.lastIndexOf(s) + 1); if (t) return t }
  return iri
}
/** Compacte une IRI en CURIE avec les préfixes de l'ontologie ; sinon nom local. */
export function curie(iri: string, prefixes: Record<string, string> = {}): string {
  let best = ''; let bp = ''
  for (const [k, v] of Object.entries(prefixes)) if (v && iri.startsWith(v) && v.length > best.length) { best = v; bp = k }
  if (best) return (bp ? bp + ':' : ':') + iri.slice(best.length)
  return localName(iri)
}
export function labelOf(e: { iri: string; labels: LangText } | undefined, iri: string, lang = 'fr'): string {
  const l = e?.labels
  return (l && (l[lang] || l.en || l[''] || Object.values(l)[0])) || localName(iri)
}
