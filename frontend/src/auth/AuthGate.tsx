import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useI18n, type Lang } from '../i18n'
import { Login } from './Login'
import { ChangePassword } from './ChangePassword'
import { api } from '../api'
import { conflictFrom, forceRev, noteRev, projectOf, queued, getRev, tracksRev } from '../collab/rev'
import './auth.css'

/**
 * Authentification (L27). `GET /api/auth/session` dit si l'instance exige un mot de passe ; sans authentification activée
 * (usage local, docker compose) l'application s'ouvre directement. Le jeton CSRF est ajouté par un `fetch` global à toute requête
 * /api qui modifie, et un 401 renvoie à la page de connexion.
 */
export interface AuthState {
  enabled: boolean; user: string | null; admin: boolean; logout: () => Promise<void>
  /** L42 : « config » = compte géré par la configuration (mot de passe non modifiable ici) ; « interface » = créé par un administrateur. */
  source: 'config' | 'interface' | null
  /** Langue d'interface du compte, enregistrée côté serveur ; le changement s'applique tout de suite à cet écran seulement. */
  setAccountLang: (l: Lang) => Promise<void>
  /** Remplace la session après un changement de mot de passe (nouveau jeton CSRF). */
  renewed: (csrf: string) => void
}
const Ctx = createContext<AuthState>({ enabled: false, user: null, admin: true, source: null, logout: async () => {}, setAccountLang: async () => {}, renewed: () => {} })
export const useAuth = () => useContext(Ctx)

let csrf: string | null = null
const SAFE = new Set(['GET', 'HEAD', 'OPTIONS'])
/** L42 : la génération (GET) écrit l'historique du projet : traitée comme une écriture (jeton CSRF, version, file d'attente par projet). */
const WRITE_GET = /\/api\/projects\/[^/?#]+\/generate\/[^/?#]+(\/zip)?(\?|#|$)/
if (typeof window !== 'undefined' && !(window as unknown as { __ofFetch?: boolean }).__ofFetch) {
  (window as unknown as { __ofFetch?: boolean }).__ofFetch = true
  const orig = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const isApi = url.startsWith('/api/') || url.startsWith(location.origin + '/api/')
    const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
    const write = isApi && (!SAFE.has(method) || WRITE_GET.test(url))
    if (write && csrf) {
      const h = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
      h.set('X-CSRF-Token', csrf)
      init = { ...init, headers: h }
    }
    const pid = isApi ? projectOf(url, method) : null
    let load = false   // chargement explicite d'un projet par le shell : seul un GET de ce genre fixe la version connue
    if (pid && method === 'GET' && new Headers(init?.headers).has('X-OntoForge-Load')) {
      load = true
      const h = new Headers(init?.headers); h.delete('X-OntoForge-Load'); init = { ...init, headers: h }
    }
    const send = async (): Promise<Response> => {
      let i2 = init
      if (write && pid && getRev(pid) !== undefined && tracksRev(url)) {   // L40 : toute écriture d'un projet porte la version connue
        const h = new Headers(i2?.headers ?? (input instanceof Request ? input.headers : undefined))
        if (!h.has('If-Match')) h.set('If-Match', `"${getRev(pid)}"`)
        i2 = { ...i2, headers: h }
      }
      const r = await orig(input, i2)
      if (pid && r.ok && tracksRev(url)) { const et = r.headers.get('ETag'); if (et) { const n = Number(et.replace(/"/g, '')); if (load) forceRev(pid, n); else if (write) noteRev(pid, n) } }
      if (pid && write && r.status === 403) {
        const j = await r.clone().json().catch(() => ({}))
        if (j.code === 'read_only') dispatchEvent(new Event('ontoforge:readonly'))
      }
      if (pid && write && (r.status === 409 || r.status === 428)) {
        const j = await r.clone().json().catch(() => ({}))
        if (j.code === 'conflict' || j.code === 'precondition_required') dispatchEvent(new CustomEvent('ontoforge:conflict', { detail: conflictFrom(pid, r.status, j, method, url, i2) }))
      }
      return r
    }
    const r = write && pid ? await queued(pid, send) : await send()
    if (r.status === 401 && isApi && !url.includes('/api/auth/')) dispatchEvent(new Event('ontoforge:auth-required'))
    if (r.status === 403 && isApi && !url.includes('/api/auth/')) { const j = await r.clone().json().catch(() => ({})); if (j.code === 'password_change_required') dispatchEvent(new Event('ontoforge:must-change')) }
    return r
  }
}

export interface SessionInfo { enabled: boolean; authenticated: boolean; user: string | null; admin?: boolean; csrf: string | null; lang?: string; session_hours?: number; must_change?: boolean; source?: 'config' | 'interface' | null }
type Phase = 'loading' | 'login' | 'change' | 'open'

export function AuthGate({ children }: { children: ReactNode }) {
  const { setLang } = useI18n()
  const [phase, setPhase] = useState<Phase>('loading')
  const [info, setInfo] = useState<SessionInfo | null>(null)

  const apply = useCallback((s: SessionInfo) => {
    csrf = s.csrf
    setInfo(s)
    if (s.enabled && s.authenticated && (s.lang === 'fr' || s.lang === 'en')) setLang(s.lang)   // L42 : la langue du compte l'emporte, côté serveur
    setPhase(!s.enabled || s.authenticated ? (s.must_change ? 'change' : 'open') : 'login')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    let live = true
    fetch('/api/auth/session').then(r => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((s: SessionInfo) => {
        if (!live) return
        let saved: string | null = null
        try { saved = localStorage.getItem('ontoforge.lang') } catch { /* stockage indisponible */ }
        const l = (saved ?? s.lang ?? (navigator.language || 'fr').slice(0, 2)) as string
        if (s.enabled && !s.authenticated && (l === 'fr' || l === 'en')) setLang(l as Lang)   // page de connexion : choix fait avant la connexion
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
  useEffect(() => {
    const f = () => setPhase(p => (p === 'open' ? 'change' : p))
    addEventListener('ontoforge:must-change', f)
    return () => removeEventListener('ontoforge:must-change', f)
  }, [])
  const setAccountLang = useCallback(async (l: Lang) => {
    await api.setAccountLang(l)
    setLang(l); setInfo(i => (i ? { ...i, lang: l } : i))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const renewed = useCallback((c: string) => { csrf = c; setInfo(i => (i ? { ...i, csrf: c, must_change: false } : i)); setPhase('open') }, [])
  const value = useMemo<AuthState>(() => ({ enabled: !!info?.enabled, user: info?.user ?? null, admin: info?.admin !== false, source: info?.source ?? null, logout, setAccountLang, renewed }),
    [info?.enabled, info?.user, info?.admin, info?.source, logout, setAccountLang, renewed])

  if (phase === 'loading') return <div className="auth-boot" aria-busy="true" />
  if (phase === 'change') return <ChangePassword user={info?.user ?? ''} onDone={renewed} onLogout={() => void logout()} />
  if (phase === 'login') return <Login hours={info?.session_hours} onSuccess={s => { apply(s); dispatchEvent(new Event('ontoforge:authed')); try { localStorage.removeItem('ontoforge.lang') } catch { /* ignoré */ } }} />
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}
