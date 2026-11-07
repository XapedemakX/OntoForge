// Appels API de l'assistant (contrat : docs/CONTRACTS.md §4).
import { tr } from '../../i18n'
import type { OntoModel, ShapesModel, Target } from '../../api'

export interface ProviderInfo { id: string; name: string; kind: string; model: string; configured: boolean; default: boolean }
export interface AStatus { provider: string; model: string; configured: boolean; default_provider_id?: string; providers?: ProviderInfo[] }
export type FileKind = 'csv' | 'sql' | 'text' | 'markdown'
export interface UploadedFile {
  name: string; kind: FileKind; size: number; content: string
  preview: { lines: string[]; total_lines: number; truncated: boolean; columns?: string[]; tables?: (string | { name: string; columns?: unknown[] })[] }
}
export interface ChatReply { reply: string; proposal: OntoModel | null; warnings: string[] }

async function call<T>(method: string, path: string, body?: unknown, form?: FormData): Promise<T> {
  let r: Response
  try { r = await fetch('/api' + path, { method, body: form ?? (body !== undefined ? JSON.stringify(body) : undefined), headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined }) }
  catch { throw new Error('Serveur injoignable') }
  if (!r.ok) {
    let d = tr('ui.http', { s: r.status })
    try { const j = await r.json(); d = typeof j.detail === 'string' ? j.detail : Array.isArray(j.detail) ? j.detail.map((x: { msg?: string }) => x.msg).join(' ; ') : d } catch { /* non JSON */ }
    throw Object.assign(new Error(d), { status: r.status })
  }
  return r.json() as Promise<T>
}
export const aapi = {
  status: () => call<AStatus>('GET', '/assistant/status'),
  upload: (file: File) => { const f = new FormData(); f.append('file', file); return call<UploadedFile>('POST', '/assistant/upload', undefined, f) },
  chat: (project_id: string, messages: { role: 'user' | 'assistant'; content: string }[], provider_id: string | undefined, attachments: { name: string; kind: FileKind; content: string }[]) =>
    call<ChatReply>('POST', '/assistant/chat', { project_id, messages, provider_id, attachments: attachments.length ? attachments : undefined }),
  shapes: (project_id: string, provider_id?: string) => call<{ proposal: ShapesModel; explanation: string }>('POST', '/assistant/shapes', { project_id, provider_id }),
  explain: (project_id: string, target: Target, finding_id: string, provider_id?: string) => call<{ text: string }>('POST', '/assistant/explain', { project_id, target, finding_id, provider_id }),
}
