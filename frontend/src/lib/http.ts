import { tr } from '../i18n'
import { detailCode, detailMessage } from './httpDetail'

// Seul point d'entrée réseau des clients API (api.ts, aapi.ts, gapi.ts, editor/types.ts, qapi.ts,
// settingsApi.ts, fapi.ts, proposal.ts) : le `fetch` et la lecture de `detail` n'existent qu'ici.
// `fetch` est appelé à chaque requête (jamais capturé) : le `fetch` global de AuthGate.tsx y ajoute
// le jeton CSRF et `If-Match`. Chaque client garde son type d'erreur (ApiError, SettingsError, Error…).

export interface Failure { ok: false; status: number; message: string; code?: string; body: unknown }
export type Outcome = { ok: true; res: Response } | Failure

/** Envoie la requête. Ne lève jamais : réseau injoignable → `status: 0` et message `ui.unreachable` ;
 *  réponse non 2xx → `status`, `message` (lu dans `detail`, sinon « Erreur {s} »), `code` et `body` (JSON, ou undefined). */
export async function request(url: string, init?: RequestInit, opts: { withLoc?: boolean } = {}): Promise<Outcome> {
  let res: Response
  try { res = await fetch(url, init) } catch { return { ok: false, status: 0, message: tr('ui.unreachable'), body: undefined } }
  if (res.ok) return { ok: true, res }
  let body: unknown
  try { body = await res.json() } catch { /* corps non JSON */ }
  return { ok: false, status: res.status, message: detailMessage(body, tr('ui.http', { s: res.status }), opts.withLoc), code: detailCode(body), body }
}

/** Corps JSON d'une réponse, `{}` s'il est vide ou invalide. */
export async function jsonOrEmpty(res: Response): Promise<unknown> {
  try { return await res.json() } catch { return {} }
}
