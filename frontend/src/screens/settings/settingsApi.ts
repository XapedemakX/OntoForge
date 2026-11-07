import { tr } from '../../i18n'
// Client API des paramètres (L8 + endpoints SPARQL L15). Contrat : docs/CONTRACTS.md §4 et §6.
// Les secrets ne sont jamais relus : seuls has_key / key_last4 / has_secret sont exposés.

export type ProviderKind = 'anthropic' | 'openai_compat' | 'ollama' | 'mock'
export interface ProviderView { id: string; name: string; kind: ProviderKind; base_url?: string | null; model: string; has_key: boolean; key_last4: string; key_unreadable: boolean; configured: boolean }
export interface ProviderInput { name?: string; kind?: ProviderKind; base_url?: string | null; model?: string; api_key?: string | null }
export type Lang = 'fr' | 'en'
export type Target = 'curiosity' | 'neo4j'
export interface SettingsView {
  llm_providers: ProviderView[]; default_provider_id: string
  language: { ui: Lang; labels: Lang; assistant: Lang }
  defaults: { base_iri: string; prefixes: Record<string, string>; target: Target; naming: Record<string, string> }
  active_endpoint_id?: string | null
}
export type EndpointAuth = 'none' | 'basic' | 'bearer'
export interface EndpointView { id: string; name: string; url: string; auth: EndpointAuth; username?: string | null; has_secret: boolean; secret_unreadable: boolean; default_graph?: string | null; timeout_s: number }
export interface EndpointInput { name?: string; url?: string; auth?: EndpointAuth; username?: string | null; secret?: string | null; default_graph?: string | null; timeout_s?: number }
export interface TestResult { ok: boolean; latency_ms?: number; model?: string; message: string }

export class SettingsError extends Error {
  status: number
  constructor(status: number, m: string) { super(m); this.status = status }
  /** 404/501 : routes pas encore disponibles côté serveur. */
  get notReady() { return this.status === 404 || this.status === 501 }
}
async function sreq<T>(method: string, path: string, body?: unknown): Promise<T> {
  let r: Response
  try {
    r = await fetch('/api/settings' + path, { method, headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined, body: body !== undefined ? JSON.stringify(body) : undefined })
  } catch { throw new SettingsError(0, tr('ui.unreachable')) }
  if (!r.ok) {
    let d = tr('ui.http', { s: r.status })
    try { const j = await r.json(); d = typeof j.detail === 'string' ? j.detail : Array.isArray(j.detail) ? j.detail.map((x: { loc?: string[]; msg?: string }) => (x.loc?.slice(-1)[0] ? x.loc.slice(-1)[0] + ' : ' : '') + x.msg).join(' ; ') : d } catch { /* non JSON */ }
    throw new SettingsError(r.status, d)
  }
  return r.json() as Promise<T>
}

export const settingsApi = {
  get: () => sreq<SettingsView>('GET', ''),
  put: (b: Partial<{ default_provider_id: string; language: SettingsView['language']; defaults: SettingsView['defaults'] }>) => sreq<SettingsView>('PUT', '', b),
  addProvider: (b: ProviderInput) => sreq<ProviderView>('POST', '/providers', b),
  updateProvider: (id: string, b: ProviderInput) => sreq<ProviderView>('PUT', `/providers/${encodeURIComponent(id)}`, b),
  deleteProvider: (id: string) => sreq<{ deleted: string; default_provider_id: string }>('DELETE', `/providers/${encodeURIComponent(id)}`),
  testProvider: (id: string, b?: ProviderInput) => sreq<TestResult>('POST', `/providers/${encodeURIComponent(id)}/test`, b ?? {}),
  endpoints: () => sreq<{ endpoints: EndpointView[]; active_endpoint_id: string | null }>('GET', '/endpoints'),
  addEndpoint: (b: EndpointInput) => sreq<EndpointView>('POST', '/endpoints', b),
  updateEndpoint: (id: string, b: EndpointInput) => sreq<EndpointView>('PUT', `/endpoints/${encodeURIComponent(id)}`, b),
  deleteEndpoint: (id: string) => sreq<{ deleted: string; active_endpoint_id: string | null }>('DELETE', `/endpoints/${encodeURIComponent(id)}`),
  setActiveEndpoint: (id: string | null) => sreq<{ active_endpoint_id: string | null }>('PUT', '/endpoints/active', { id }),
  testEndpoint: (id: string, b?: EndpointInput) => sreq<TestResult>('POST', `/endpoints/${encodeURIComponent(id)}/test`, b ?? {}),
}
export const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e))
