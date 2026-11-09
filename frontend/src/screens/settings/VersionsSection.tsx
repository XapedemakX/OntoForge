import { useState } from 'react'
import { Button, Card, Icon } from '../../kit'
import { useT } from '../../i18n'
import type { VersionKey } from '../../api'
import { VersionRows } from '../versions/VersionRows'
import { settingsApi, type SettingsView } from './settingsApi'
import { SaveBar, useSaver } from './shared'

/** Panneau « Versions » : défaut global des versions de normes et de cibles (les projets qui n'ont rien fixé le suivent). */
export function VersionsSection({ s, reload }: { s: SettingsView; reload: () => Promise<void> }) {
  const t = useT()
  const [vals, setVals] = useState<Record<VersionKey, string>>(s.versions)
  const saver = useSaver()
  const rec = s.versions_check.recommended
  const dirty = (Object.keys(vals) as VersionKey[]).some(k => vals[k] !== s.versions[k])
  const save = () => saver.run(async () => { await settingsApi.put({ versions: vals }); await reload() })
  return (
    <Card title={<><Icon name="tags" /> {t('settings.ver.title')}</>}>
      <p className="set-hint">{t('settings.ver.intro')}</p>
      {s.versions_check.gaps.filter(g => g.severity !== 'info').length > 0 && (
        <div className="set-chip warn" style={{ margin: 'var(--s3) 0' }} role="status"><Icon name="triangle-exclamation" /> {s.versions_check.gaps.filter(g => g.severity !== 'info').map(g => g.message).join(' ')}</div>)}
      <div style={{ marginTop: 'var(--s3)' }}>
        <VersionRows rows={s.versions_view} values={vals} onChange={(k, v) => setVals(x => ({ ...x, [k]: v ?? x[k] }))} />
      </div>
      {Object.keys(rec).length > 0 && <div className="set-row" style={{ marginTop: 'var(--s2)' }}>
        <Button size="sm" icon="wand-magic-sparkles" onClick={() => setVals(x => ({ ...x, ...rec } as Record<VersionKey, string>))}>{t('settings.ver.useRec')}</Button></div>}
      <SaveBar saver={saver} onSave={save} dirty={dirty} />
    </Card>)
}
