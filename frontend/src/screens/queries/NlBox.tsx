import { useState } from 'react'
import { Button, Icon, Krakie } from '../../kit'
import { useT } from '../../i18n'
import { qapi, type NlResult } from './qapi'
import { ApiError } from '../../api'

const term = (u: string | { term?: string; text?: string }) => (typeof u === 'string' ? u : u.term ?? u.text ?? '')

/** « Pose ta question » : le résultat remplit la phrase guidée, qui reste modifiable. */
export function NlBox({ pid, onResult, onTerm }: { pid: string; onResult: (r: NlResult) => void; onTerm: (term: string) => void }) {
  const t = useT()
  const [q, setQ] = useState(''); const [busy, setBusy] = useState(false)
  const [soon, setSoon] = useState(false); const [err, setErr] = useState<string | null>(null); const [res, setRes] = useState<NlResult | null>(null)
  const go = async () => {
    if (!q.trim()) return
    setBusy(true); setErr(null); setSoon(false)
    try { const r = await qapi.nl(pid, q.trim()); setRes(r); onResult(r) }
    catch (e) { const a = e as ApiError; if (a.status === 404 || a.status === 501) setSoon(true); else setErr(a.message) }
    finally { setBusy(false) }
  }
  const conf = res?.confidence == null ? null : typeof res.confidence === 'number' ? (res.confidence <= 1 ? Math.round(res.confidence * 100) : Math.round(res.confidence)) : null
  const level = conf == null ? null : conf >= 75 ? 'auto' : conf >= 45 ? 'review' : 'lost'
  const unmatched = (res?.unmatched ?? []).map(term).filter(Boolean)
  return (
    <section className="qnl" aria-label={t('q.nl')} data-tour="q-nl">
      <form className="qnl-form" onSubmit={e => { e.preventDefault(); void go() }}>
        <span className="qnl-k"><Krakie pose={busy ? 'reflechit' : 'loupe'} size={36} float={busy} /></span>
        <input type="text" value={q} onChange={e => setQ(e.target.value)} placeholder={t('q.nl.ph')} aria-label={t('q.nl')} />
        <Button variant="primary" icon="wand-magic-sparkles" type="submit" disabled={busy || !q.trim()}>{busy ? t('q.nl.busy') : t('q.nl.go')}</Button>
      </form>
      {soon && <div className="notice soon"><Icon name="hourglass-half" /><div><b>{t('q.nl.soon')}</b><div>{t('q.nl.soon.body')}</div></div></div>}
      {err && <div className="notice error" role="alert">{err}</div>}
      {res && !err && (
        <div className="qnl-out">
          {conf != null && <span className={`sev ${level}`} title={t('q.nl.conf.tip')}><Icon name="gauge" /><b>{conf}%</b>{t('q.nl.conf')}</span>}
          {res.explanation && <p className="qnl-exp">{res.explanation}</p>}
          {!res.guided && <p className="muted">{t('q.nl.noguided')}</p>}
          {unmatched.length > 0 && (
            <div className="qnl-un"><span className="muted">{t('q.nl.unmatched')}</span>
              {unmatched.map(u => <button type="button" key={u} className="qo add" onClick={() => onTerm(u)} title={t('q.nl.assoc')}><Icon name="link" />{u}</button>)}</div>
          )}
        </div>
      )}
    </section>
  )
}
