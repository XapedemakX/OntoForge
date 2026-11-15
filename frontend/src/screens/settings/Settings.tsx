import { useCallback, useEffect, useRef, useState } from 'react'
import { EmptyState, Tabs } from '../../kit'
import { useI18n } from '../../i18n'
import { onSettingsGoto, useAssistantContext } from '../../lib/assistantContext'
import { settingsApi, errMsg, type SettingsView } from './settingsApi'
import { ErrorLine } from './shared'
import { LlmSection } from './LlmSection'
import { LanguageSection } from './LanguageSection'
import { DefaultsSection } from './DefaultsSection'
import { EndpointsSection } from './EndpointsSection'
import { VersionsSection } from './VersionsSection'
import { DisplaySection } from './DisplaySection'
import './settings.css'

type Sec = 'llm' | 'lang' | 'defaults' | 'versions' | 'display' | 'sparql'
const SECS: Sec[] = ['llm', 'lang', 'defaults', 'versions', 'display', 'sparql']

/** Écran Paramètres (route globale #/parametres) : fournisseurs LLM, langues, valeurs par défaut, endpoints SPARQL. */
export function Settings() {
  const { t, lang } = useI18n()
  const [s, setS] = useState<SettingsView | null>(null)
  const [err, setErr] = useState('')
  const [sec, setSec] = useState<Sec>('llm')
  const reload = useCallback(async () => { try { setS(await settingsApi.get()); setErr('') } catch (e) { setErr(errMsg(e)) } }, [])
  useEffect(() => { reload() }, [reload])
  // Krakie (L38) : l'onglet affiché et deux suggestions propres à l'onglet ; « Aller à cette section » change d'onglet, fait défiler et met le bloc en évidence
  useAssistantContext({ screen: 'settings', extra: { section: sec }, suggestions: [t(`ag.sugg.settings.${sec}`), t(`ag.sugg.settings.${sec}.2`)] }, [sec, lang])
  const [flash, setFlash] = useState<{ sec: Sec; n: number } | null>(null)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => onSettingsGoto(x => { if ((SECS as string[]).includes(x)) { setSec(x as Sec); setFlash({ sec: x as Sec, n: Date.now() }) } }), [])
  useEffect(() => {
    if (!flash) return
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    const go = setTimeout(() => box.current?.scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' }), 60)
    const off = setTimeout(() => setFlash(null), 2800)
    return () => { clearTimeout(go); clearTimeout(off) }
  }, [flash])
  return (
    <div className="page set-page">
      <div className="page-head"><h1 style={{ margin: 0 }}>{t('settings.title')}</h1><span className="sub">{t('settings.sub')}</span></div>
      <Tabs value={sec} onChange={setSec} items={[['llm', t('settings.tab.llm')], ['lang', t('settings.tab.lang')], ['defaults', t('settings.tab.defaults')], ['versions', t('settings.tab.versions')], ['display', t('settings.tab.display')], ['sparql', t('settings.tab.sparql')]]} />
      <ErrorLine msg={err} />
      <div ref={box} className={'set-sec' + (flash?.sec === sec ? ' flash' : '')} data-set-sec={sec} data-testid={'set-sec-' + sec}>
      {sec === 'display' && <DisplaySection />}
      {sec === 'display' ? null : !s ? (err ? <EmptyState pose="reflechit" title={t('common.error')} /> : <p className="muted">{t('common.loading')}</p>) : (
        <>
          {sec === 'llm' && <LlmSection s={s} reload={reload} />}
          {sec === 'lang' && <LanguageSection s={s} reload={reload} />}
          {sec === 'defaults' && <DefaultsSection s={s} reload={reload} />}
          {sec === 'versions' && <VersionsSection key={JSON.stringify(s.versions)} s={s} reload={reload} />}
          {sec === 'sparql' && <EndpointsSection />}
        </>)}
      </div>
      <p className="set-hint set-retro">{t('settings.hint.retro')}</p>
    </div>)
}
