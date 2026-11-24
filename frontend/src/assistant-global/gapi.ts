import { request } from '../lib/http'
import type { Project } from '../api'
import type { AssistantContext } from '../lib/assistantContext'
import type { AgentAction } from './store'

async function call<T>(path: string, body?: unknown): Promise<T> {
  const o = await request('/api' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body !== undefined ? JSON.stringify(body) : undefined })
  if (!o.ok) throw new Error(o.message)
  const r = o.res
  return r.json() as Promise<T>
}
export interface AgentReply { reply: string; actions: AgentAction[]; warnings: string[]; proposal: unknown | null }
export interface OpsRes { ok: boolean; project: Project; errors: { message: string }[]; warnings: string[] }
export const gapi = {
  /** `project_id` null : Krakie sur l'écran Paramètres (L38), le serveur n'accepte alors que le contexte « settings ». */
  chat: (project_id: string | null, messages: { role: string; content: string }[], provider_id: string | undefined, context: AssistantContext, attachments?: unknown[]) =>
    call<AgentReply>('/assistant/chat', { project_id: project_id || undefined, messages, provider_id: provider_id || undefined, context, attachments: attachments?.length ? attachments : undefined }),
  ops: (pid: string, ops: unknown[], label: string) => call<OpsRes>(`/projects/${encodeURIComponent(pid)}/ops`, { ops, label }),
  undo: (pid: string) => call<OpsRes>(`/projects/${encodeURIComponent(pid)}/ops/undo`),
  shapes: (project_id: string, patches: unknown[]) => call<{ project: Project }>('/assistant/shapes/apply', { project_id, patches }),
}
