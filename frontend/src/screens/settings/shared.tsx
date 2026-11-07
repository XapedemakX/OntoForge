import { useState } from 'react'
import { Button, Icon } from '../../kit'
import { useT } from '../../i18n'
import { errMsg, type TestResult } from './settingsApi'

/** Enregistrement explicite : état, message « Enregistré » ou erreur lisible. */
export function useSaver() {
  const [state, setState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [error, setError] = useState('')
  const run = async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setState('saving'); setError('')
    try { const r = await fn(); setState('saved'); return r } catch (e) { setError(errMsg(e)); setState('error') }
  }
  return { state, error, run, reset: () => { setState('idle'); setError('') } }
}
export function SaveBar({ saver, onSave, dirty = true, label }: { saver: ReturnType<typeof useSaver>; onSave: () => void; dirty?: boolean; label?: string }) {
  const t = useT()
  return (
    <div className="set-row" style={{ marginTop: 'var(--s3)' }}>
      <Button variant="primary" icon="floppy-disk" disabled={saver.state === 'saving' || !dirty} onClick={onSave}>{label ?? t('common.save')}</Button>
      <span role="status" aria-live="polite">
        {saver.state === 'saved' && <span className="set-saved"><Icon name="check" /> {t('settings.saved')}</span>}
        {saver.state === 'saving' && <span className="muted">{t('common.loading')}</span>}
      </span>
      {saver.state === 'error' && <div className="set-err grow" role="alert"><Icon name="triangle-exclamation" /> {saver.error}</div>}
    </div>
  )
}
export function ErrorLine({ msg }: { msg: string }) {
  return msg ? <div className="set-err" role="alert"><Icon name="triangle-exclamation" /> {msg}</div> : null
}
export function TestOutcome({ r }: { r: TestResult | 'loading' | undefined }) {
  const t = useT()
  if (!r) return null
  if (r === 'loading') return <div className="set-res" role="status"><Icon name="spinner" /> {t('settings.test.running')}</div>
  return (
    <div className={'set-res ' + (r.ok ? 'ok' : 'ko')} role="status">
      <Icon name={r.ok ? 'circle-check' : 'circle-xmark'} />
      <span><b>{r.ok ? t('settings.test.ok') : t('settings.test.ko')}</b>
        {r.latency_ms != null && <> · {r.latency_ms} ms</>}{r.model && <> · {r.model}</>} — {r.message}</span>
    </div>
  )
}
/** Champ secret : jamais relu ; « •••• abcd » + remplacer / supprimer. */
export type SecretState = { mode: 'keep' | 'replace' | 'remove'; value: string }
export function SecretField({ label, has, last4, unreadable, st, setSt }: { label: string; has: boolean; last4?: string; unreadable?: boolean; st: SecretState; setSt: (s: SecretState) => void }) {
  const t = useT()
  if (st.mode === 'replace' || (!has && st.mode !== 'remove'))
    return (
      <label className="f"><span>{label}</span>
        <div className="set-row">
          <input type="password" autoComplete="new-password" className="grow" value={st.value} onChange={e => setSt({ mode: 'replace', value: e.target.value })} placeholder={has ? t('settings.secret.new') : ''} />
          {has && <Button size="sm" onClick={() => setSt({ mode: 'keep', value: '' })}>{t('common.cancel')}</Button>}
        </div></label>)
  return (
    <div className="f"><span className="muted" style={{ fontSize: 'var(--fs-xs)' }}>{label}</span>
      <div className="set-row">
        {st.mode === 'remove' ? <span className="set-chip warn">{t('settings.secret.willRemove')}</span>
          : unreadable ? <span className="set-chip warn"><Icon name="triangle-exclamation" /> {t('settings.secret.unreadable')}</span>
          : <span className="set-key" aria-label={t('settings.secret.masked')}>•••• {last4 || '••••'}</span>}
        <Button size="sm" icon="key" onClick={() => setSt({ mode: 'replace', value: '' })}>{t('settings.secret.replace')}</Button>
        {st.mode === 'remove' ? <Button size="sm" onClick={() => setSt({ mode: 'keep', value: '' })}>{t('common.cancel')}</Button>
          : <Button size="sm" variant="danger" icon="eraser" onClick={() => setSt({ mode: 'remove', value: '' })}>{t('settings.secret.remove')}</Button>}
      </div></div>)
}
/** Valeur à envoyer pour un secret : absent = inchangé, null = supprimé, chaîne = remplacé. */
export function secretPatch(st: SecretState): { v?: string | null } {
  if (st.mode === 'remove') return { v: null }
  if (st.mode === 'replace' && st.value) return { v: st.value }
  return {}
}
