import { tr } from '../i18n'
import type { Project } from '../api'
import type { AssistantContext } from '../lib/assistantContext'
import type { AgentAction } from './store'

async function call<T>(path: string, body?: unknown): Promise<T> {
  let r: Response
  try { r = await fetch('/api' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body !== undefined ? JSON.stringify(body) : undefined }) }
  catch { throw new Error('Serveur injoignable') }
  if (!r.ok) {
    let d = tr('ui.http', { s: r.status })
    try { const j = await r.json(); d = typeof j.detail === 'string' ? j.detail : Array.isArray(j.detail) ? j.detail.map((x: { msg?: string }) => x.msg).join(' ; ') : d } catch { /* non JSON */ }
    throw new Error(d)
  }
  return r.json() as Promise<T>
}
export interface AgentReply { reply: string; actions: AgentAction[]; warnings: string[]; proposal: unknown | null }
export interface OpsRes { ok: boolean; project: Project; errors: { message: string }[]; warnings: string[] }
export const gapi = {
  chat: (project_id: string, messages: { role: string; content: string }[], provider_id: string | undefined, context: AssistantContext, attachments?: unknown[]) =>
    call<AgentReply>('/assistant/chat', { project_id, messages, provider_id: provider_id || undefined, context, attachments: attachments?.length ? attachments : undefined }),
  ops: (pid: string, ops: unknown[], label: string) => call<OpsRes>(`/projects/${encodeURIComponent(pid)}/ops`, { ops, label }),
  undo: (pid: string) => call<OpsRes>(`/projects/${encodeURIComponent(pid)}/ops/undo`),
  shapes: (project_id: string, patches: unknown[]) => call<{ project: Project }>('/assistant/shapes/apply', { project_id, patches }),
}
