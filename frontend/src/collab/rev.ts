/**
 * Version des projets (L40). Le serveur renvoie la version d'un projet dans l'en-tête `ETag` ; toute écriture porte `If-Match`.
 * Ce module suit la dernière version connue par projet, sérialise les écritures d'un même projet (pour qu'elles ne se
 * contredisent pas entre elles) et signale un conflit (409, ou 428 « version absente ») sans jamais écraser en silence.
 */
const revs = new Map<string, number>()
const chains = new Map<string, Promise<unknown>>()
let current: string | null = null

export const getRev = (pid: string) => revs.get(pid)
export const setCurrentProject = (pid: string | null) => { current = pid }
export function noteRev(pid: string, n: number) { if (!Number.isNaN(n) && n > (revs.get(pid) ?? -1)) revs.set(pid, n) }
export function forceRev(pid: string, n: number) { revs.set(pid, n) }

const PROJECT_URL = /^(?:https?:\/\/[^/]+)?\/api\/projects\/([^/?#]+)(\/[^?#]*)?/
/** Projet visé par une requête : l'identifiant de l'URL, ou le projet ouvert pour les routes de l'assistant qui le portent dans le corps. */
export function projectOf(url: string, method: string): string | null {
  const m = PROJECT_URL.exec(url)
  if (m) return decodeURIComponent(m[1])
  if (method !== 'GET' && /\/api\/assistant\/shapes\/apply/.test(url)) return current
  return null
}
/** Les battements de présence ne disent rien de la version que cet onglet connaît. */
export const tracksRev = (url: string) => !/\/presence(\?|$)/.test(url) && !/\/access(\/|\?|$)/.test(url) && !/\/activity(\?|$)/.test(url)

export function queued<T>(pid: string, fn: () => Promise<T>): Promise<T> {
  const prev = chains.get(pid) ?? Promise.resolve()
  const run = prev.then(fn, fn)
  chains.set(pid, run.catch(() => undefined))
  return run
}

export interface ConflictInfo { pid: string; status: number; detail: string; lastActor?: string | null; currentRev?: number; replay?: { method: string; url: string; body: string; contentType: string } | null }
/** Écritures qu'on peut rejouer sans rien écraser après rechargement : opérations unitaires, décisions, périmètres, requêtes enregistrées, versions. */
const REPLAYABLE = /\/(ops|decisions\/[^/]+|perimeters(\/[^/]+)?|queries\/saved(\/[^/]+)?|versions)(\?|$)/
export function conflictFrom(pid: string, status: number, j: { detail?: string; last_actor?: string; current_rev?: number }, method: string, url: string, init?: RequestInit): ConflictInfo {
  const body = typeof init?.body === 'string' ? init.body : null
  const ct = new Headers(init?.headers).get('Content-Type') ?? 'application/json'
  const replay = body !== null && REPLAYABLE.test(url.split('?')[0] + '?') ? { method, url, body, contentType: ct } : null
  return { pid, status, detail: String(j.detail ?? ''), lastActor: j.last_actor, currentRev: j.current_rev, replay }
}
