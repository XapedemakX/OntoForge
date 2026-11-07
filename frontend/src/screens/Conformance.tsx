import { useState } from 'react'
import { api } from '../api'
import type { ScreenProps } from '../shell/types'
import { Empty, ErrorView, Spin, useLoad } from '../ui'
import { useT } from '../i18n'

const PROFILE_NAMES: Record<string, string> = { DL: 'OWL 2 DL', EL: 'OWL 2 EL', QL: 'OWL 2 QL', RL: 'OWL 2 RL', RDFS: 'RDFS' }

export function Conformance({ p }: ScreenProps) {
  const t = useT()
  const { data, error, loading, reload } = useLoad(() => api.conformance(p.id), [p.id, p.updated_at])
  const [lv, setLv] = useState<Record<string, boolean>>({ error: true, warning: true, info: true })
  const [q, setQ] = useState('')
  const issues = (data?.issues ?? []).filter(i => lv[i.level] && (!q || (i.code + i.message + (i.subject ?? '')).toLowerCase().includes(q.toLowerCase())))
  const n = (l: string) => data?.issues.filter(i => i.level === l).length ?? 0
  const ref = (s?: string | null) => !s ? null : /^https?:/.test(s) ? <a href={s} target="_blank" rel="noreferrer">{s.replace(/^https?:\/\/(www\.)?/, '')}</a> : <span>{s}</span>
  return (
    <div className="page">
      <div className="page-head"><h1>{t('cf.title')}</h1><span className="sub">{t('cf.sub')}</span><span className="grow" /><button className="btn" onClick={reload}>{t('cf.recheck')}</button></div>
      {loading && <Spin />}<ErrorView error={error} what={t('cf.what')} />
      {data && <>
        <div className="card" data-tour="conf-profiles"><div className="hd"><h2>{t('conf.profiles')}</h2></div><div className="bd row">
          {Object.entries(data.profiles).map(([k, ok]) => <span key={k} className={'pill ' + (ok ? 'on' : 'off')} title={ok ? t('cf.profile.ok') : t('cf.profile.ko')}>{PROFILE_NAMES[k] ?? k}</span>)}
          {Object.keys(data.profiles).length === 0 && <span className="muted">{t('cf.noprofile')}</span>}</div></div>
        <div className="row">
          {(['error', 'warning', 'info'] as const).map(l => <label key={l} className="row"><input type="checkbox" checked={lv[l]} onChange={e => setLv({ ...lv, [l]: e.target.checked })} /><span className={'badge ' + l}>{t('cf.level.' + l)} {n(l)}</span></label>)}
          <input type="text" placeholder={t('cf.filter')} value={q} onChange={e => setQ(e.target.value)} style={{ width: 260 }} />
        </div>
        {data.issues.length === 0 ? <Empty title={t('cf.empty.t')}>{t('cf.empty.b')}</Empty> :
          <div className="tscroll" style={{ maxHeight: 'none' }}><table className="t"><thead><tr><th>{t('cf.col.level')}</th><th>{t('cf.col.code')}</th><th>{t('cf.col.message')}</th><th>{t('cf.col.subject')}</th><th>{t('cf.col.spec')}</th></tr></thead><tbody>
            {issues.map((i, k) => <tr key={k}><td><span className={'badge ' + i.level}>{t('cf.level.' + i.level)}</span></td><td className="mono">{i.code}</td><td>{i.message}</td><td className="mono" title={i.subject ?? ''}>{i.subject ? i.subject.split(/[#/]/).pop() : ''}</td><td>{ref(i.spec_ref)}</td></tr>)}
          </tbody></table></div>}
      </>}
    </div>
  )
}
