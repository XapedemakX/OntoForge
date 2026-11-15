import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Krakie } from '../krakie/Krakie'
import { Icon } from '../kit'
import { useI18n } from '../i18n'
import { api, ApiError } from '../api'

const MIN = 10

/** Écran de changement du mot de passe provisoire (L42) : obligatoire à la première connexion, avant tout autre écran. Krakie accompagne. */
export function ChangePassword({ user, onDone, onLogout }: { user: string; onDone: (csrf: string) => void; onLogout: () => void }) {
  const { t } = useI18n()
  const [cur, setCur] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [ok, setOk] = useState(false)
  const first = useRef<HTMLInputElement>(null)
  useEffect(() => { first.current?.focus() }, [])
  const tooShort = pw.length > 0 && pw.length < MIN
  const mismatch = pw2.length > 0 && pw !== pw2
  const valid = !!cur && pw.length >= MIN && pw === pw2
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!valid || busy) return
    setBusy(true); setErr('')
    try {
      const r = await api.changePassword(cur, pw)
      setOk(true); setCur(''); setPw(''); setPw2('')
      setTimeout(() => onDone(r.csrf), 900)
    } catch (x) {
      const a = x as ApiError
      setErr(a.code && ['bad_current_password', 'password_too_short', 'password_unchanged', 'rate_limited'].includes(a.code) ? t('auth.pw.err.' + a.code) : a.message)
    } finally { setBusy(false) }
  }
  return (
    <div className="auth-page">
      <main className="auth-card" data-testid="change-password">
        <div className={'auth-krakie ' + (ok ? 'happy' : err ? 'wrong' : 'idle')}><Krakie pose={ok ? 'contente' : err ? 'inquiete' : 'accueil'} size={104} title="Krakie" float={false} /></div>
        <h1 className="auth-word" style={{ fontSize: 22 }}>{t('auth.pw.title')}</h1>
        <p className="auth-sub">{t('auth.pw.sub', { user })}</p>
        <form onSubmit={submit} noValidate>
          <label className="auth-field"><span>{t('auth.pw.current')}</span>
            <input ref={first} type={show ? 'text' : 'password'} autoComplete="current-password" value={cur} onChange={e => setCur(e.target.value)} data-testid="pw-current" /></label>
          <label className="auth-field"><span>{t('auth.pw.new')}</span>
            <input type={show ? 'text' : 'password'} autoComplete="new-password" value={pw} onChange={e => setPw(e.target.value)} aria-invalid={tooShort} data-testid="pw-new" /></label>
          <label className="auth-field"><span>{t('auth.pw.confirm')}</span>
            <input type={show ? 'text' : 'password'} autoComplete="new-password" value={pw2} onChange={e => setPw2(e.target.value)} aria-invalid={mismatch} data-testid="pw-confirm" /></label>
          <label className="auth-check"><input type="checkbox" checked={show} onChange={e => setShow(e.target.checked)} /> {t('auth.show')}</label>
          <div className={'auth-msg ' + (ok ? 'ok' : err || tooShort || mismatch ? 'ko' : '')} role={ok ? 'status' : 'alert'} aria-live="polite" data-testid="pw-msg">
            {ok ? t('auth.pw.done') : err || (tooShort ? t('auth.pw.err.password_too_short') : mismatch ? t('auth.pw.mismatch') : t('auth.pw.rule', { n: MIN }))}</div>
          <button className="auth-submit" type="submit" disabled={!valid || busy || ok} data-testid="pw-submit">{busy ? t('auth.busy') : t('auth.pw.submit')}</button>
        </form>
        <p className="auth-foot"><button type="button" className="auth-link" onClick={onLogout} data-testid="pw-logout"><Icon name="right-from-bracket" /> {t('auth.logout')}</button></p>
      </main>
    </div>
  )
}
