import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import fr from './fr.json'
import en from './en.json'

export type Lang = 'fr' | 'en'
const DICTS: Record<Lang, Record<string, string>> = { fr, en }
export type Params = Record<string, string | number>

/** Ajoute des chaînes à un dictionnaire (chunks chargés à la demande, ex. le mini-jeu caché) : évite d'alourdir le bundle principal. */
export function extendDicts(fr_: Record<string, string>, en_: Record<string, string>) { Object.assign(DICTS.fr, fr_); Object.assign(DICTS.en, en_) }

/** Traduit `key` ; repli sur le français puis sur la clé elle-même. `{nom}` est remplacé par params.nom. */
export function translate(lang: Lang, key: string, params?: Params): string {
  let s = DICTS[lang][key] ?? DICTS.fr[key] ?? key
  if (params) for (const [k, v] of Object.entries(params)) s = s.split(`{${k}}`).join(String(v))
  return s
}

/** Langue courante pour le code hors composants (api.ts, messages) ; tenue à jour par le provider. */
let CURRENT: Lang = 'fr'
export const tr = (key: string, params?: Params) => translate(CURRENT, key, params)

type Ctx = { lang: Lang; setLang: (l: Lang) => void }
const LangCtx = createContext<Ctx>({ lang: 'fr', setLang: () => {} })

/** Langue de l'interface : français par défaut, remplacée par GET /api/settings → language.ui. */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>('fr')
  useEffect(() => {
    const load = () => fetch('/api/settings').then(r => (r.ok ? r.json() : null)).then(s => {
      const l = s?.language?.ui; if (l === 'fr' || l === 'en') setLangState(l)
    }).catch(() => { /* backend absent : français */ })
    void load()
    // instance protégée par mot de passe : les réglages ne sont lisibles qu'après la connexion (L27) ; un choix fait sur la page de connexion prime
    const onAuthed = () => { let chosen = false; try { chosen = !!localStorage.getItem('ontoforge.lang') } catch { /* ignoré */ } if (!chosen) void load() }
    addEventListener('ontoforge:authed', onAuthed)
    return () => removeEventListener('ontoforge:authed', onAuthed)
  }, [])
  CURRENT = lang
  useEffect(() => { document.documentElement.lang = lang }, [lang])
  const v = useMemo(() => ({ lang, setLang: setLangState }), [lang])
  return <LangCtx.Provider value={v}>{children}</LangCtx.Provider>
}
/** Hook : `const { t, lang } = useI18n()` puis `t('nav.ontologie')`, `t('dash.stat.classes', { n: 3 })`. */
export function useI18n() {
  const { lang, setLang } = useContext(LangCtx)
  const t = useCallback((key: string, params?: Params) => translate(lang, key, params), [lang])
  return { t, lang, setLang }
}
export const useT = () => useI18n().t
