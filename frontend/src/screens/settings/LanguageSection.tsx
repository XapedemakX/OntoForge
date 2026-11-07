import { useState } from 'react'
import { Card, Field, Icon, Select } from '../../kit'
import { useI18n } from '../../i18n'
import { settingsApi, type Lang, type SettingsView } from './settingsApi'
import { SaveBar, useSaver } from './shared'

export function LanguageSection({ s, reload }: { s: SettingsView; reload: () => Promise<void> }) {
  const { t, setLang } = useI18n()
  const [v, setV] = useState(s.language)
  const saver = useSaver()
  const opts = [{ value: 'fr', label: t('settings.lang.fr') }, { value: 'en', label: t('settings.lang.en') }]
  const dirty = JSON.stringify(v) !== JSON.stringify(s.language)
  return (
    <Card title={<><Icon name="language" /> {t('settings.lang.title')}</>}>
      <p className="set-hint">{t('settings.lang.intro')}</p>
      <div className="set-grid" style={{ marginTop: 'var(--s3)' }}>
        <Field label={t('settings.lang.ui')} hint={t('settings.lang.uiHint')}>
          <Select value={v.ui} options={opts} onChange={e => { const l = e.target.value as Lang; setV({ ...v, ui: l }); setLang(l) }} /></Field>
        <Field label={t('settings.lang.labels')} hint={t('settings.lang.labelsHint')}>
          <Select value={v.labels} options={opts} onChange={e => setV({ ...v, labels: e.target.value as Lang })} /></Field>
        <Field label={t('settings.lang.assistant')} hint={t('settings.lang.assistantHint')}>
          <Select value={v.assistant} options={opts} onChange={e => setV({ ...v, assistant: e.target.value as Lang })} /></Field>
      </div>
      <SaveBar saver={saver} dirty={dirty || saver.state !== 'saved'} onSave={() => saver.run(async () => { await settingsApi.put({ language: v }); await reload() })} />
    </Card>)
}
