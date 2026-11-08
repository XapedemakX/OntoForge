import { tr } from '../../i18n'
import type { Project } from '../../api'

export type Sev = 'error' | 'warning' | 'info'
export interface Diag { line: number; col: number; severity: Sev; message: string; code: string; subject?: string }
export interface FileEntry { path: string; name: string; editable: boolean; generated: boolean; language: string; etag: string; size: number }
export interface FileTree { version: string; target: string; files: FileEntry[] }
export interface SourceNote { state: 'source' | 'canonical'; comment_lines: number }
export interface FileContent { path: string; content: string; etag: string; editable: boolean; generated: boolean; language: string; version: string; source?: SourceNote | null }
export interface Rewritten { count: number; added: number; samples: { from: string[]; to: string[] } }
export interface DiffSummary {
  unit: 'triples' | 'decisions'; added: number; removed: number; changed?: number; samples: { added: string[]; removed: string[] }
  rewritten?: Rewritten; comment_lines?: number; comments_lost?: number; source_kept?: boolean
}
export interface DiffResult { changed: boolean; summary: DiffSummary; current: string; after: string; etag: string; warnings: string[]; source?: SourceNote | null }
export interface ApplyResult { ok: boolean; changed: boolean; project: Project; content: string; etag: string; source?: SourceNote | null; summary: DiffSummary; warnings: string[]; diagnostics: Diag[]; can_undo: boolean; can_redo: boolean }
export interface Reply<T> { status: number; ok: boolean; data: T & { detail?: string; diagnostics?: Diag[]; current_etag?: string; current_content?: string } }

const base = (id: string) => `/api/projects/${encodeURIComponent(id)}`
const enc = (path: string) => path.split('/').map(encodeURIComponent).join('/')

async function call<T>(method: string, url: string, body?: unknown): Promise<Reply<T>> {
  let r: Response
  try {
    r = await fetch(url, { method, ...(body !== undefined ? { body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } } : {}) })
  } catch { return { status: 0, ok: false, data: { detail: tr('ui.unreachable') } as Reply<T>['data'] } }
  let data: unknown = {}
  try { data = await r.json() } catch { /* corps vide */ }
  return { status: r.status, ok: r.ok, data: data as Reply<T>['data'] }
}

export const fapi = {
  tree: (id: string) => call<FileTree>('GET', `${base(id)}/files`),
  read: (id: string, path: string) => call<FileContent>('GET', `${base(id)}/files/${enc(path)}`),
  validate: (id: string, path: string, content: string) => call<{ diagnostics: Diag[] }>('POST', `${base(id)}/files/validate`, { path, content }),
  diff: (id: string, path: string, content: string) => call<DiffResult>('POST', `${base(id)}/files/diff`, { path, content }),
  apply: (id: string, path: string, content: string, baseEtag?: string, force = false) =>
    call<ApplyResult>('PUT', `${base(id)}/files/${enc(path)}`, { content, base_etag: baseEtag, force }),
  undo: (id: string) => call<{ project: Project; can_undo: boolean; can_redo: boolean; label?: string }>('POST', `${base(id)}/ops/undo`),
  getProject: (id: string) => call<Project>('GET', base(id)),
}
