import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useI18n, type Lang } from '../i18n'
import { Login } from './Login'
import './auth.css'

/**
 * Authentification (L27). `GET /api/auth/session` dit si l'instance exige un mot de passe ; sans authentification activée
 * (usage local, docker compose) l'application s'ouvre directement. Le jeton CSRF est ajouté par un `fetch` global à toute requête
 * /api qui modifie, et un 401 renvoie à la page de connexion.
 */
export interface AuthState { enabled: boolean; user: string | null; logout: () => Promise<void> }
const Ctx = createContext<AuthState>({ enabled: false, user: null, logout: async () => {} })
export const useAuth = () => useContext(Ctx)

let csrf: string | null = null
const SAFE = new Set(['GET', 'HEAD', 'OPTIONS'])
if (typeof window !== 'undefined' && !(window as unknown as { __ofFetch?: boolean }).__ofFetch) {
  (window as unknown as { __ofFetch?: boolean }).__ofFetch = true
  const orig = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const isApi = url.startsWith('/api/') || url.startsWith(location.origin + '/api/')
    const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
    if (isApi && csrf && !SAFE.has(method)) {
      const h = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
      h.set('X-CSRF-Token', csrf)
      init = { ...init, headers: h }
    }
    const r = await orig(input, init)
    if (r.status === 401 && isApi && !url.includes('/api/auth/')) dispatchEvent(new Event('ontoforge:auth-required'))
    return r
  }
}

export interface SessionInfo { enabled: boolean; authenticated: boolean; user: string | null; csrf: string | null; lang?: string; session_hours?: number }
type Phase = 'loading' | 'login' | 'open'

export function AuthGate({ children }: { children: ReactNode }) {
  const { setLang } = useI18n()
  const [phase, setPhase] = useState<Phase>('loading')
  const [info, setInfo] = useState<SessionInfo | null>(null)

  const apply = useCallback((s: SessionInfo) => {
    csrf = s.csrf
    setInfo(s)
    setPhase(!s.enabled || s.authenticated ? 'open' : 'login')
  }, [])
  useEffect(() => {
    let live = true
    fetch('/api/auth/session').then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((s: SessionInfo) => {
        if (!live) return
        let saved: string | null = null
        try { saved = localStorage.getItem('ontoforge.lang') } catch { /* stockage indisponible */ }
        const l = (saved ?? s.lang ?? (navigator.language || 'fr').slice(0, 2)) as string
        if (s.enabled && !s.authenticated && (l === 'fr' || l === 'en')) setLang(l as Lang)
        apply(s)
      })
      .catch(() => { if (live) setPhase('open') })   // serveur injoignable : l'application affiche ses propres erreurs
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apply])
  useEffect(() => {
    const f = () => { csrf = null; setInfo(i => (i && i.enabled ? { ...i, authenticated: false, user: null, csrf: null } : i)); setPhase(p => (info?.enabled ? 'login' : p)) }
    addEventListener('ontoforge:auth-required', f)
    return () => removeEventListener('ontoforge:auth-required', f)
  }, [info?.enabled])

  const logout = useCallback(async () => {
    try { await fetch('/api/auth/logout', { method: 'POST' }) } catch { /* hors ligne : on revient quand même à la connexion */ }
    csrf = null
    setInfo(i => (i ? { ...i, authenticated: false, user: null, csrf: null } : i))
    setPhase('login')
    location.hash = '#/'
  }, [])
  const value = useMemo<AuthState>(() => ({ enabled: !!info?.enabled, user: info?.user ?? null, logout }), [info?.enabled, info?.user, logout])

  if (phase === 'loading') return <div className="auth-boot" aria-busy="true" />
  if (phase === 'login') return <Login hours={info?.session_hours} onSuccess={s => { apply(s); dispatchEvent(new Event('ontoforge:authed')) }} />
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
