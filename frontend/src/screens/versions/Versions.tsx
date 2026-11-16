import { useState } from 'react'
import { api, type ProjectVersions, type StandardsRef, type VersionKey } from '../../api'
import type { ScreenProps } from '../../shell/types'
import { Button, Fold, Icon } from '../../kit'
import { useT } from '../../i18n'
import { useAssistantContext } from '../../lib/assistantContext'
import { ErrorView, Spin, useLoad, useToast } from '../../ui'
import { VersionRows } from './VersionRows'
import '../settings/settings.css'
import './versions.css'

/** Écran « Versions » du projet : versions de normes et de cibles utilisées par les générateurs, avec le statut de chacune. */
export function Versions({ p, setP }: ScreenProps) {
  const t = useT()
  const toast = useToast()
  useAssistantContext({ screen: 'versions', projectId: p.id, extra: { versions: p.target_versions ?? {} } })
  const [tick, setTick] = useState(0)
  const ver = useLoad(() => api.versions(p.id), [p.id, tick])
  const chk = useLoad(() => api.versionsCheck(p.id), [p.id, tick])
  const ref = useLoad<StandardsRef>(() => api.standards(), [])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<unknown>(null)

  const refresh = async (v?: ProjectVersions) => {
    setP(await api.getProject(p.id))     // updated_at change : les exports se régénèrent
    setTick(x => x + 1)
    return v
  }
  const change = async (key: VersionKey, value: string | null) => {
    setBusy(true); setErr(null)
    try { await api.putVersions(p.id, { [key]: value }); await refresh() } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const applyRecommended = async () => {
    if (!chk.data) return
    setBusy(true); setErr(null)
    try { await api.putVersions(p.id, chk.data.recommended); await refresh(); toast(t('ver.applied')) } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const data = ver.data
  const gaps = chk.data?.gaps ?? []
  const rec = chk.data?.recommended ?? {}
  const shacl = data?.versions.shacl ?? '1.0'
  return (
    <div className="page ver-page">
      <div className="page-head"><h1>{t('ver.title')}</h1><span className="sub">{t('ver.sub')}</span></div>
      {ver.loading && !data && <Spin />}
      <ErrorView error={ver.error ?? err} what={t('ver.what')} />
      {data && <>
        <p className="set-hint">{t('ver.intro')}</p>
        {gaps.length > 0 && (
          <Fold screen="versions" id="gaps" title={<><Icon name="triangle-exclamation" /> {t('ver.gaps.title')}</>} desc={t('fold.versions.gaps')} defaultOpen={!!chk.data?.needs_attention} tone={chk.data?.needs_attention ? 'review' : 'info'}>
            <ul className="ver-gaps" data-testid="ver-gaps">
              {gaps.map((g, i) => <li key={i} className={g.severity}><span>{g.message}</span>{g.recommendation && <span className="muted"> {g.recommendation.message}</span>}</li>)}
            </ul>
            {Object.keys(rec).length > 0 && <Button variant="primary" icon="wand-magic-sparkles" disabled={busy} onClick={() => void applyRecommended()}>{t('ver.apply')}</Button>}
          </Fold>)}
        {gaps.length === 0 && <div className="set-res ok" role="status"><Icon name="circle-check" /><span>{t('ver.gaps.none')}</span></div>}
        <Fold screen="versions" id="targets" title={<><Icon name="tags" /> {t('ver.card.targets')}</>} desc={t('fold.versions.targets')} defaultOpen>
          <VersionRows rows={data.rows} values={Object.fromEntries(data.rows.map(r => [r.key, r.pinned ? r.value : null]))} allowDefault disabled={busy}
            onChange={(k, v) => void change(k, v)} />
          <p className="set-hint" style={{ marginTop: 'var(--s2)' }}>{t('ver.default.hint')} <a href="#/parametres">{t('ver.default.link')}</a></p>
        </Fold>
        {ref.data && <>
          <Fold screen="versions" id="shacl" title={<><Icon name="shield-halved" /> {t('ver.shacl.title')}</>} desc={t('fold.versions.shacl')}>
            <p className="set-hint">{t('ver.shacl.intro', { v: shacl })}</p>
            <ul className="ver-feat">
              {ref.data.w3c.shacl.features.map(f => (
                <li key={f.id} data-feature={f.id}><code>{f.id}</code> <span className="set-chip">{f.since}</span> <span className="set-chip">{f.maturity}</span>
                  <span className="muted"> {f.label} · </span>
                  <b>{shacl === '1.0' ? t('ver.shacl.disabled') : t('ver.shacl.unavailable')}</b></li>))}
            </ul>
          </Fold>
          <Fold screen="versions" id="libs" title={<><Icon name="cubes" /> {t('ver.libs.title')}</>} desc={t('fold.versions.libs')}>
            <p className="set-hint">{ref.data.libraries.note}</p>
            <table className="set-table"><thead><tr><th>{t('ver.libs.name')}</th><th>{t('ver.libs.used')}</th><th>{t('ver.libs.latest')}</th></tr></thead>
              <tbody>{ref.data.libraries.items.map(l => <tr key={l.id}><td className="mono">{l.id}</td><td className="mono">{l.used}</td><td className="mono">{l.latest ?? '—'}</td></tr>)}</tbody></table>
          </Fold>
          <p className="set-hint">{t('ver.ref', { d: ref.data.updated })}</p>
        </>}
      </>}
    </div>
  )
}
