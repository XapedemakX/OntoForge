import { useCallback, useEffect, useState } from 'react'
import { EmptyState, Tabs } from '../../kit'
import { useI18n } from '../../i18n'
import { settingsApi, errMsg, type SettingsView } from './settingsApi'
import { ErrorLine } from './shared'
import { LlmSection } from './LlmSection'
import { LanguageSection } from './LanguageSection'
import { DefaultsSection } from './DefaultsSection'
import { EndpointsSection } from './EndpointsSection'
import './settings.css'

type Sec = 'llm' | 'lang' | 'defaults' | 'sparql'

/** Écran Paramètres (route globale #/parametres) : fournisseurs LLM, langues, valeurs par défaut, endpoints SPARQL. */
export function Settings() {
  const { t } = useI18n()
  const [s, setS] = useState<SettingsView | null>(null)
  const [err, setErr] = useState('')
  const [sec, setSec] = useState<Sec>('llm')
  const reload = useCallback(async () => { try { setS(await settingsApi.get()); setErr('') } catch (e) { setErr(errMsg(e)) } }, [])
  useEffect(() => { reload() }, [reload])
  return (
    <div className="page set-page">
      <div className="page-head"><h1 style={{ margin: 0 }}>{t('settings.title')}</h1><span className="sub">{t('settings.sub')}</span></div>
      <Tabs value={sec} onChange={setSec} items={[['llm', t('settings.tab.llm')], ['lang', t('settings.tab.lang')], ['defaults', t('settings.tab.defaults')], ['sparql', t('settings.tab.sparql')]]} />
      <ErrorLine msg={err} />
      {!s ? (err ? <EmptyState pose="reflechit" title={t('common.error')} /> : <p className="muted">{t('common.loading')}</p>) : (
        <>
          {sec === 'llm' && <LlmSection s={s} reload={reload} />}
          {sec === 'lang' && <LanguageSection s={s} reload={reload} />}
          {sec === 'defaults' && <DefaultsSection s={s} reload={reload} />}
          {sec === 'sparql' && <EndpointsSection />}
        </>)}
    </div>)
}
