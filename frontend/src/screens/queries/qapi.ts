// Client du requêtage guidé (CONTRACTS §6). Types alignés sur backend/ontoforge/queries/builder.py.
import { tr } from '../../i18n'
import { ApiError } from '../../api'

export type FilterKind = 'text_contains' | 'equals' | 'regex' | 'lang' | 'number_range' | 'date_range' | 'in_values'
export type ValueKind = 'text' | 'number' | 'date' | 'boolean' | 'other'

export interface GStep { from_var: string; property_iri: string; inverse: boolean; to_var: string; to_class_iri?: string | null; optional: boolean; negated: boolean }
export interface GFilter { var: string; kind: FilterKind; property_iri?: string | null; value?: string | null; value2?: string | null; values?: string[]; lang?: string | null; datatype?: string | null; is_iri?: boolean; case_insensitive?: boolean; negate?: boolean }
export interface GSelect { var: string; property_iri?: string | null; label?: boolean }
export interface GOrder { var: string; property_iri?: string | null; desc: boolean }
export interface Guided {
  root: { var: string; class_iri?: string | null }; steps: GStep[]; filters: GFilter[]; select: GSelect[]; order_by: GOrder[]
  limit: number; offset?: number; distinct?: boolean; subclasses?: boolean; label_lang?: string | null
}

export interface RootClass { iri: string; label: string; parents: string[]; known?: number }
export interface Target { iri: string; label: string; direct: boolean; known?: number }
export interface ObjSuggest { iri: string; label: string; direction: 'out' | 'in'; inverse: boolean; inherited_from?: string | null; untyped: boolean; targets: Target[]; targets_restricted: boolean; required: boolean; max_count?: number | null; note?: string | null }
export interface DataSuggest { iri: string; label: string; datatype?: string; value_kind: ValueKind; filter_kinds: FilterKind[]; required: boolean; max_count?: number | null }
export interface ClassSuggest { class: string; label: string; ancestors: { iri: string; label: string }[]; subclasses: { iri: string; label: string }[]; outgoing: ObjSuggest[]; incoming: ObjSuggest[]; data_properties: DataSuggest[] }

export interface Cell { type: string; value: string; datatype?: string; 'xml:lang'?: string }
export interface RunResult {
  columns: string[]; rows: Record<string, Cell | null>[]; truncated: boolean; elapsed_ms: number; boolean?: boolean | null
  sparql: string; endpoint_id: string; graph: { nodes: { id: string; label: string; column?: string }[]; edges: { id: string; source: string; target: string; label: string }[] }
}
export interface BuildResult { sparql: string; cypher: string | null; curiosity: string | null; graphql: string | null; notes: string[]; lossy: boolean; supported?: boolean; warnings?: string[] }
export interface ValueSuggestion { value: string; label: string; is_iri: boolean; datatype?: string; lang?: string }
export interface SavedQuery { id: string; name: string; description?: string; guided: Guided | null; sparql: string | null; created_at: string; updated_at: string }
export interface Competency { id: string; question: string; pattern: string; sparql: string; guided: Guided | null; reason?: string | null }
export interface NlResult { guided: Guided | null; explanation?: string; confidence?: number | string; unmatched?: (string | { term?: string; text?: string })[]; sparql?: string; cypher?: string | null; curiosity?: string | null }
export interface Endpoint { id: string; name: string; url: string }
/** Endpoint temporaire : gardé en mémoire dans le navigateur, jamais persisté (le secret non plus). */
export interface InlineEndpoint { url: string; auth: 'none' | 'basic' | 'bearer'; username?: string; secret?: string; default_graph?: string }
/** Triplestore local du projet (L19) : `endpoint: {kind: 'local'}` à la place de `endpoint_id` ou d'un endpoint temporaire. */
export interface LocalEndpoint { kind: 'local'; timeout_s?: number }
export type InlineOrLocal = InlineEndpoint | LocalEndpoint
export type Semantics = 'rdfs' | 'owlrl' | 'both'
export interface StoreGraph { graph: string; kind: 'ontology' | 'individuals' | 'data' | 'inferred'; name: string; triples: number; format?: string; source?: string }
export interface StoreStats {
  ephemeral?: boolean
  exists: boolean; triples: number; graphs: StoreGraph[]; ontology_stale: boolean; size_kb?: number; engine: string
  inference: { semantics: Semantics; triples: number; source_triples: number; stale: boolean; notes?: string[] } | null
  demo: { sample: string; file: string } | null
  limits: { max_triples: number; max_upload_mb: number; max_inference_triples: number; query_timeout_s: number }
}
export interface ShaclCheck { conforms: boolean; validated_triples: number; warnings?: string[]; results: { focus: string; path?: string | null; severity: string; message?: string | null }[] }
export interface OptionValue { value: string; label: string; is_iri: boolean; lang?: string | null; source?: string }
export interface OptionsResult { kind: string; known_count: number; enumerated: boolean; values: OptionValue[]; truncated: boolean }

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  let r: Response
  try {
    r = await fetch('/api' + path, { method, ...(body !== undefined ? { body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } } : {}) })
  } catch { throw new ApiError(0, 'Serveur injoignable.') }
  if (!r.ok) {
    let d = tr('ui.http', { s: r.status })
    try { const j = await r.json(); d = typeof j.detail === 'string' ? j.detail : Array.isArray(j.detail) ? j.detail.map((x: { msg?: string }) => x.msg).join(' ; ') : d } catch { /* corps non JSON */ }
    throw new ApiError(r.status, d)
  }
  return r.json() as Promise<T>
}
const q = (o: Record<string, string | undefined>) => '?' + Object.entries(o).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(v!)}`).join('&')
const P = (id: string) => `/projects/${encodeURIComponent(id)}`

async function formCall<T>(path: string, fd: FormData): Promise<T> {
  let r: Response
  try { r = await fetch('/api' + path, { method: 'POST', body: fd }) } catch { throw new ApiError(0, 'Serveur injoignable.') }
  if (!r.ok) {
    let d = tr('ui.http', { s: r.status })
    try { const j = await r.json(); if (typeof j.detail === 'string') d = j.detail } catch { /* corps non JSON */ }
    throw new ApiError(r.status, d)
  }
  return r.json() as Promise<T>
}

export const qapi = {
  roots: (id: string, lang?: string) => call<{ classes: RootClass[] }>('GET', P(id) + '/query/suggest' + q({ lang })),
  suggest: (id: string, cls: string, lang?: string) => call<ClassSuggest>('GET', P(id) + '/query/suggest' + q({ class: cls, lang })),
  build: (id: string, guided: Guided, target?: string) => call<BuildResult>('POST', P(id) + '/query/build', { guided, target }),
  run: (id: string, b: { guided?: Guided; sparql?: string; endpoint_id?: string; endpoint?: InlineOrLocal; limit?: number }) => call<RunResult>('POST', P(id) + '/query/run', b),
  values: (id: string, cls: string, prop: string | null, text: string, endpoint_id?: string, endpoint?: InlineOrLocal | null) => endpoint
    ? call<{ values: ValueSuggestion[]; truncated: boolean }>('POST', P(id) + '/query/values', { class: cls, property: prop || undefined, q: text, endpoint })
    : call<{ values: ValueSuggestion[]; truncated: boolean }>('GET', P(id) + '/query/values' + q({ class: cls, property: prop ?? undefined, q: text, endpoint_id })),
  options: (id: string, cls: string, prop: string | null, text: string, lang?: string) => call<OptionsResult>('GET', P(id) + '/query/options' + q({ class: cls, property: prop ?? undefined, q: text, lang })),
  testInline: (id: string, e: InlineEndpoint) => call<{ ok: boolean; latency_ms?: number; message?: string }>('POST', P(id) + '/query/endpoint-test', e),
  saveEndpoint: (e: InlineEndpoint & { name: string }) => call<Endpoint>('POST', '/settings/endpoints', e),
  nl: (id: string, question: string, provider_id?: string) => call<NlResult>('POST', P(id) + '/query/nl', { question, provider_id }),
  saved: (id: string) => call<SavedQuery[]>('GET', P(id) + '/queries/saved'),
  save: (id: string, b: { name: string; description?: string; guided?: Guided | null; sparql?: string | null }) => call<SavedQuery>('POST', P(id) + '/queries/saved', b),
  update: (id: string, qid: string, b: { name: string; description?: string; guided?: Guided | null; sparql?: string | null }) => call<SavedQuery>('PUT', P(id) + `/queries/saved/${qid}`, b),
  remove: (id: string, qid: string) => call<{ deleted: boolean }>('DELETE', P(id) + `/queries/saved/${qid}`),
  competency: (id: string, target?: string) => call<Competency[]>('GET', P(id) + '/queries/competency/guided' + q({ target })),
  storeStats: (id: string) => call<StoreStats>('GET', P(id) + '/store/stats'),
  storeLoad: (id: string, o: { file?: File; sample?: string; inference?: Semantics | 'none' }) => {
    const fd = new FormData()
    if (o.file) fd.append('file', o.file)
    if (o.sample) fd.append('sample', o.sample)
    if (o.inference) fd.append('inference', o.inference)
    return formCall<StoreStats>(P(id) + '/store/load', fd)
  },
  storeClear: (id: string) => call<StoreStats>('DELETE', P(id) + '/store'),
  storeValidate: (id: string, inference?: string) => call<ShaclCheck>('POST', P(id) + '/store/validate', { inference: inference || 'none' }),
  endpoints: () => call<{ endpoints: Endpoint[]; active_endpoint_id: string | null }>('GET', '/settings/endpoints'),
  setActive: (eid: string | null) => call<{ active_endpoint_id: string | null }>('PUT', '/settings/endpoints/active', { id: eid }),
}
