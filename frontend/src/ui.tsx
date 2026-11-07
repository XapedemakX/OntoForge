import { createContext, useCallback, useContext, useEffect, useRef, useState, lazy, Suspense, type ReactNode } from 'react'
import { ApiError } from './api'
import { Krakie } from './krakie/Krakie'
import { useT, tr } from './i18n'

// ---------- chargement asynchrone ----------
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let live = true
    setLoading(true)
    fn().then(d => { if (live) { setData(d); setError(null) } })
      .catch(e => { if (live) { setError(e instanceof ApiError ? e : new ApiError(0, String(e))); setData(null) } })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])
  return { data, error, loading, reload: useCallback(() => setTick(x => x + 1), []), setData }
}

// ---------- messages ----------
export function ErrorView({ error, what }: { error: unknown; what?: string }) {
  const t = useT()
  if (!error) return null
  const e = error as ApiError
  if (e.status === 501) return <div className="notice soon"><span>⏳</span><div><b>{what ? t('ui.soon.what', { what }) : t('ui.soon')}</b><div>{e.message}. {t('ui.soon.body')}</div></div></div>
  return <div className="notice error" role="alert"><div><b>{what ? t('ui.fail.what', { what }) : t('ui.fail')}</b><div>{e.message ?? String(error)}</div></div></div>
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty empty-state"><Krakie pose="accueil" size={64} /><b>{title}</b>{children}</div>
}
export const Spin = () => { const t = useT(); return <div className="muted" style={{ padding: 12 }}>{t('common.loading')}</div> }

// ---------- toasts ----------
const ToastCtx = createContext<(m: string) => void>(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastHost({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; m: string }[]>([])
  const push = useCallback((m: string) => {
    const id = Date.now() + Math.random()
    setItems(x => [...x, { id, m }])
    setTimeout(() => setItems(x => x.filter(i => i.id !== id)), 3500)
  }, [])
  return <ToastCtx.Provider value={push}>{children}<div className="toasts" role="status">{items.map(i => <div key={i.id} className="toast">{i.m}</div>)}</div></ToastCtx.Provider>
}

// ---------- petits composants ----------
export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: [T, string][] }) {
  return <div className="tabs" role="tablist">{items.map(([k, l]) => <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)}>{l}</button>)}</div>
}
export function Chips({ items, onRemove, render }: { items: string[]; onRemove?: (i: number) => void; render?: (s: string) => string }) {
  return <span className="chips">{items.map((s, i) => <span className="chip" key={s + i} title={s}>{render ? render(s) : s}{onRemove && <button aria-label={tr('ui.remove')} onClick={() => onRemove(i)}>×</button>}</span>)}</span>
}
export function Pick({ options, onPick, placeholder }: { options: { value: string; label: string }[]; onPick: (v: string) => void; placeholder: string }) {
  return <select value="" onChange={e => { if (e.target.value) onPick(e.target.value) }} aria-label={placeholder}>
    <option value="">{placeholder}</option>{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
}

export function download(name: string, content: string, mime = 'text/plain') {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([content], { type: mime })); a.download = name; a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}
export async function copy(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true } catch {
    const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select()
    const ok = document.execCommand('copy'); ta.remove(); return ok
  }
}
export function esc(s: string) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;') }


const CodeEditorImpl = lazy(() => import('./CodeEditor').then(m => ({ default: m.CodeEditor })))
export type CodeEditorProps = {
  value: string; onChange?: (v: string) => void; filename?: string; readOnly?: boolean
  errors?: { line: number; message: string }[]; minHeight?: number
}
export function CodeEditor(props: CodeEditorProps) {
  return <Suspense fallback={<div className="muted" style={{ padding: 12, minHeight: props.minHeight }}>{tr('common.loading')}</div>}><CodeEditorImpl {...props} /></Suspense>
}
