import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Button, Icon } from '../kit'
import { useI18n, type Lang } from '../i18n'
import { api, ApiError } from '../api'
import { openDoc } from '../lib/docs'
import { useToast } from '../ui'
import { useAuth } from './AuthGate'

/** Menu du compte (L42) : langue de l'interface (propre au compte, enregistrée côté serveur), changement de mot de passe, accès à l'administration. */
export function AccountMenu() {
  const { t, lang } = useI18n()
  const auth = useAuth()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [pwOpen, setPwOpen] = useState(false)
  const [pwDone, setPwDone] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) { setPwOpen(false); setPwDone(false); return }
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    const c = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false) }
    addEventListener('keydown', k); addEventListener('mousedown', c)
    return () => { removeEventListener('keydown', k); removeEventListener('mousedown', c) }
  }, [open])
  if (!auth.enabled) return null
  const pick = async (l: Lang) => { try { await auth.setAccountLang(l) } catch (e) { toast((e as Error).message) } }
  return (
    <div className="acct" ref={box}>
      <button type="button" className="btn sm ghost acct-btn" data-testid="account-menu" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(o => !o)} title={t('acct.menu')}>
        <Icon name="circle-user" /><span className="nm">{auth.user}</span></button>
      {open && (
        <div className="acct-pop collab-keep" role="dialog" aria-label={t('acct.menu')} data-testid="account-pop">
          <div><h3>{auth.user}</h3>
            <div className="row" style={{ marginTop: 4 }}>
              {auth.admin && <span className="badge ok" data-testid="acct-admin-badge">{t('acct.admin')}</span>}
              {auth.source === 'config' && <span className="badge">{t('acct.config')}</span>}
            </div></div>
          <label className="f">{t('acct.lang')}
            <select value={lang} data-testid="account-lang" onChange={e => void pick(e.target.value as Lang)}>
              <option value="fr">{t('settings.lang.fr')}</option><option value="en">{t('settings.lang.en')}</option></select></label>
          <p className="muted" style={{ margin: 0, fontSize: 'var(--fs-xs)' }}>{t('acct.lang.hint')}{' '}
            <button type="button" className="auth-link" onClick={() => { setOpen(false); openDoc(null, 'utilisateur', 'langue-de-l-interface') }}>{t('acct.lang.help')}</button></p>
          <hr className="sep" />
          {pwDone && <p className="acct-ok" role="status" data-testid="account-pw-done"><Icon name="circle-check" /> {t('acct.pw.done.inline')}</p>}
          {pwOpen ? <PasswordForm config={auth.source === 'config'} onDone={() => { setPwOpen(false); setPwDone(true); toast(t('acct.pw.done')) }} onCancel={() => setPwOpen(false)} />
            : <Button size="sm" icon="key" data-testid="account-pw" onClick={() => { setPwDone(false); setPwOpen(true) }}>{t('acct.pw')}</Button>}
          {auth.admin && <Button size="sm" icon="user-shield" data-testid="account-admin" onClick={() => { setOpen(false); location.hash = '#/administration' }}>{t('acct.adminLink')}</Button>}
        </div>)}
    </div>
  )
}

function PasswordForm({ config, onDone, onCancel }: { config: boolean; onDone: () => void; onCancel: () => void }) {
  const { t } = useI18n()
  const auth = useAuth()
  const [cur, setCur] = useState(''), [pw, setPw] = useState(''), [pw2, setPw2] = useState('')
  const [show, setShow] = useState(false)
  const [err, setErr] = useState(''), [busy, setBusy] = useState(false)
  const first = useRef<HTMLInputElement>(null)
  useEffect(() => { first.current?.focus() }, [])
  const valid = !!cur && pw.length >= 10 && pw === pw2
  const kind = show ? 'text' : 'password'
  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (!valid || busy) return
    setBusy(true); setErr('')
    try { const r = await api.changePassword(cur, pw); auth.renewed(r.csrf); onDone() }
    catch (x) { const a = x as ApiError; setErr(a.code && ['bad_current_password', 'password_too_short', 'password_unchanged', 'rate_limited'].includes(a.code) ? t('auth.pw.err.' + a.code) : a.message) }
    finally { setBusy(false) }
  }
  return (
    <form onSubmit={submit} noValidate data-testid="account-pw-form">
      {config && <p className="muted" style={{ margin: 0, fontSize: 'var(--fs-sm)' }} data-testid="account-pw-config"><Icon name="lock" /> {t('acct.pw.config')}</p>}
      <label className="f">{t('acct.pw.current')}<input ref={first} type={kind} autoComplete="current-password" value={cur} data-testid="account-pw-current" onChange={e => setCur(e.target.value)} /></label>
      <label className="f">{t('auth.pw.new')}<input type={kind} autoComplete="new-password" value={pw} data-testid="account-pw-new" onChange={e => setPw(e.target.value)} /></label>
      <label className="f">{t('auth.pw.confirm')}<input type={kind} autoComplete="new-password" value={pw2} data-testid="account-pw-confirm" onChange={e => setPw2(e.target.value)} /></label>
      <label className="adm-check"><input type="checkbox" checked={show} data-testid="account-pw-show" onChange={e => setShow(e.target.checked)} /> {t('auth.show')}</label>
      <div className="acct-err" role="alert" data-testid="account-pw-err">{err || (pw && pw.length < 10 ? t('auth.pw.err.password_too_short') : pw2 && pw !== pw2 ? t('auth.pw.mismatch') : '')}</div>
      <p className="muted" style={{ margin: 0, fontSize: 'var(--fs-xs)' }}>{t('acct.pw.rule')}{' '}
        <button type="button" className="auth-link" onClick={() => openDoc(null, 'utilisateur', 'changer-mon-mot-de-passe')}>{t('acct.pw.help')}</button></p>
      <div className="row"><Button size="sm" variant="primary" type="submit" data-testid="account-pw-submit" disabled={!valid || busy}>{t('acct.pw.save')}</Button><Button size="sm" variant="ghost" type="button" onClick={onCancel}>{t('common.cancel')}</Button></div>
    </form>)
}
