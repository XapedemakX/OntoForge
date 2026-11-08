import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Krakie, type Pose } from '../krakie/Krakie'
import { Icon } from '../kit'
import { useI18n, type Lang } from '../i18n'
import type { SessionInfo } from './AuthGate'

type Mood = 'idle' | 'busy' | 'wrong' | 'wait' | 'happy'
const POSE: Record<Mood, Pose> = { idle: 'accueil', busy: 'reflechit', wrong: 'inquiete', wait: 'inquiete', happy: 'contente' }

/** Page de connexion : Krakie réagit (réfléchit pendant la vérification, inquiet si les identifiants sont faux ou si trop d'essais, content à la réussite). */
export function Login({ onSuccess, hours }: { onSuccess: (s: SessionInfo) => void; hours?: number }) {
  const { t, lang, setLang } = useI18n()
  const [user, setUser] = useState('')
  const [pw, setPw] = useState('')
  const [show, setShow] = useState(false)
  const [mood, setMood] = useState<Mood>('idle')
  const [wait, setWait] = useState(0)
  const [netErr, setNetErr] = useState(false)
  const userRef = useRef<HTMLInputElement>(null)
  useEffect(() => { userRef.current?.focus() }, [])
  useEffect(() => {
    if (wait <= 0) return
    const id = setTimeout(() => setWait(w => { if (w <= 1) { setMood('idle'); return 0 } return w - 1 }), 1000)
    return () => clearTimeout(id)
  }, [wait])

  const pick = (l: Lang) => { setLang(l); try { localStorage.setItem('ontoforge.lang', l) } catch { /* ignoré */ } }
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (mood === 'busy' || mood === 'happy' || wait > 0 || !user.trim() || !pw) return
    setMood('busy'); setNetErr(false)
    try {
      const r = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: user, password: pw }) })
      const j = await r.json().catch(() => ({}))
      if (r.ok && j.authenticated) {
        setMood('happy'); setPw('')
        setTimeout(() => onSuccess(j as SessionInfo), 1100)
      } else if (r.status === 429 || (j.retry_after && r.status === 401)) {
        setWait(Math.max(1, Number(j.retry_after) || 3)); setMood(r.status === 429 ? 'wait' : 'wrong'); setPw('')
      } else { setMood('wrong'); setPw('') }
    } catch { setNetErr(true); setMood('wrong') }
  }

  const msg = mood === 'happy' ? t('auth.ok') : wait > 0 ? t('auth.wait', { n: wait }) : netErr ? t('auth.net') : mood === 'wrong' ? t('auth.bad') : ''
  return (
    <div className="auth-page">
      <div className="auth-lang" role="group" aria-label={t('common.language')}>
        {(['fr', 'en'] as Lang[]).map(l => <button key={l} type="button" aria-pressed={lang === l} onClick={() => pick(l)}>{l.toUpperCase()}</button>)}
      </div>
      <main className="auth-card" data-testid="login">
        <div className={'auth-krakie ' + mood} data-mood={mood}>
          <Krakie pose={POSE[mood]} size={112} title={t('auth.krakie.' + mood)} float={false} />
        </div>
        <h1 className="auth-word"><span className="o">Onto</span><span className="f">Forge</span></h1>
        <p className="auth-sub">{t('auth.subtitle')}</p>
        <form onSubmit={submit} noValidate>
          <label className="auth-field"><span>{t('auth.user')}</span>
            <input ref={userRef} name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} value={user}
              onChange={e => setUser(e.target.value)} aria-invalid={mood === 'wrong'} data-testid="login-user" /></label>
          <label className="auth-field"><span>{t('auth.password')}</span>
            <span className="auth-pw">
              <input name="password" type={show ? 'text' : 'password'} autoComplete="current-password" value={pw}
                onChange={e => setPw(e.target.value)} aria-invalid={mood === 'wrong'} data-testid="login-password" />
              <button type="button" className="auth-eye" aria-label={show ? t('auth.hide') : t('auth.show')} aria-pressed={show} onClick={() => setShow(s => !s)}><Icon name={show ? 'eye-slash' : 'eye'} /></button>
            </span></label>
          <div className={'auth-msg ' + (mood === 'happy' ? 'ok' : msg ? 'ko' : '')} role={mood === 'happy' ? 'status' : 'alert'} aria-live="polite" data-testid="login-msg">{msg}</div>
          <button className="auth-submit" type="submit" disabled={mood === 'busy' || mood === 'happy' || wait > 0 || !user.trim() || !pw} data-testid="login-submit">
            {mood === 'busy' ? t('auth.busy') : t('auth.submit')}</button>
        </form>
        <p className="auth-foot">{t('auth.foot', { h: hours ?? 8 })}</p>
      </main>
    </div>
  )
}
