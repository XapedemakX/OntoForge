import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type AccessView, type Role } from '../api'
import { Button, Icon } from '../kit'
import { useI18n } from '../i18n'
import { useToast } from '../ui'
import { openDoc } from '../lib/docs'
import { getAssistantContext, setAssistantContext } from '../lib/assistantContext'
import { Dot } from './Bar'

export function SharePanel({ pid, onClose }: { pid: string; onClose: () => void }) {
  const { t } = useI18n()
  const toast = useToast()
  const [v, setV] = useState<AccessView | null>(null)
  const [login, setLogin] = useState('')
  const [role, setRole] = useState<Role>('reader')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirm, setConfirm] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const box = useRef<HTMLDivElement>(null)
  // Krakie : tant que le panneau est ouvert, l'aide contextuelle porte sur le partage (entrée « sharing » de la table d'aide)
  useEffect(() => {
    const prev = getAssistantContext()
    setAssistantContext({ screen: 'sharing', projectId: pid, suggestions: [t('collab.sugg.1'), t('collab.sugg.2')] })
    return () => setAssistantContext(prev)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid])
  const load = useCallback(() => api.access(pid).then(setV).catch(e => setErr((e as Error).message)), [pid])
  useEffect(() => { void load() }, [load])
  useEffect(() => { input.current?.focus() ?? box.current?.focus() }, [v?.sharing_available])
  useEffect(() => { const f = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }; addEventListener('keydown', f); return () => removeEventListener('keydown', f) }, [onClose])

  const run = async (fn: () => Promise<AccessView>, ok?: string) => {
    setBusy(true); setErr('')
    try { setV(await fn()); if (ok) toast(ok) } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const owner = v?.role === 'owner'
  const add = async () => {
    const l = login.trim(); if (!l) return
    await run(() => api.share(pid, l, role), t('collab.added', { login: l }))
    setLogin('')
  }
  return (
    <div className="collab-scrim" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="collab-panel card" role="dialog" aria-modal="true" aria-labelledby="collab-title" data-testid="share-panel" ref={box} tabIndex={-1}>
        <div className="hd"><b id="collab-title" className="grow"><Icon name="user-group" /> {t('collab.panel.title')}</b>
          <button type="button" className="btn ghost iconly" aria-label={t('common.close')} title={t('common.close')} onClick={onClose}><Icon name="xmark" /></button></div>
        <div className="collab-body">
          {v && !v.sharing_available && <div className="notice soon" data-testid="share-noauth"><span><Icon name="circle-info" /></span><div>{t('collab.noauth')}</div></div>}
          {v && v.sharing_available && <>
            <ul className="collab-list" aria-label={t('collab.list')}>
              <li data-testid={`share-row-${v.owner}`}><Dot user={v.owner ?? '?'} title={v.owner ?? ''} /><span className="grow"><b>{v.owner}</b>{v.owner === v.me && <span className="muted"> {t('collab.you')}</span>}</span>
                <span className="badge ok">{t('collab.role.owner')}</span></li>
              {v.members.map(m => (
                <li key={m.login} data-testid={`share-row-${m.login}`}><Dot user={m.login} title={m.login} />
                  <span className="grow"><b>{m.login}</b>{m.login === v.me && <span className="muted"> {t('collab.you')}</span>}</span>
                  {owner ? <>
                    <select value={m.role} aria-label={t('collab.roleOf', { login: m.login })} data-testid={`share-role-${m.login}`} disabled={busy}
                      onChange={e => void run(() => api.share(pid, m.login, e.target.value as Role), t('collab.changed', { login: m.login }))}>
                      <option value="reader">{t('collab.role.reader')}</option><option value="editor">{t('collab.role.editor')}</option></select>
                    <Button size="sm" variant="ghost" icon="crown" data-testid={`share-transfer-${m.login}`} disabled={busy} onClick={() => setConfirm(m.login)}>{t('collab.transfer')}</Button>
                    <Button size="sm" variant="ghost" icon="user-minus" data-testid={`share-remove-${m.login}`} disabled={busy} aria-label={t('collab.removeOf', { login: m.login })}
                      onClick={() => void run(() => api.unshare(pid, m.login), t('collab.removed', { login: m.login }))}>{t('collab.remove')}</Button>
                  </> : <>
                    <span className="badge">{t('collab.role.' + m.role)}</span>
                    {m.login === v.me && <Button size="sm" variant="ghost" icon="right-from-bracket" data-testid="share-leave" disabled={busy}
                      onClick={() => void api.unshare(pid, m.login).then(() => { location.hash = '#/' }).catch(e => setErr((e as Error).message))}>{t('collab.leave')}</Button>}
                  </>}
                </li>))}
            </ul>
            {confirm && <div className="notice warn" role="alert" data-testid="share-transfer-ask"><div><b>{t('collab.transfer.ask', { login: confirm })}</b><div>{t('collab.transfer.body', { login: confirm })}</div>
              <div className="row" style={{ marginTop: 8 }}>
                <Button size="sm" variant="primary" data-testid="share-transfer-yes" disabled={busy} onClick={() => void run(() => api.transfer(pid, confirm), t('collab.transferred', { login: confirm })).then(() => setConfirm(null))}>{t('collab.transfer.yes')}</Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>{t('common.cancel')}</Button></div></div></div>}
            {owner ? (
              <form className="collab-add" onSubmit={e => { e.preventDefault(); void add() }}>
                <label className="f grow">{t('collab.login')}<input ref={input} type="text" value={login} autoComplete="off" autoCapitalize="none" spellCheck={false} data-testid="share-login"
                  placeholder={t('collab.login.ph')} onChange={e => { setLogin(e.target.value); setErr('') }} /></label>
                <label className="f">{t('collab.role')}<select value={role} data-testid="share-newrole" onChange={e => setRole(e.target.value as Role)}>
                  <option value="reader">{t('collab.role.reader')}</option><option value="editor">{t('collab.role.editor')}</option></select></label>
                <Button variant="primary" type="submit" data-testid="share-add" disabled={busy || !login.trim()}>{t('collab.add')}</Button>
              </form>) : <p className="muted">{t('collab.notowner')}</p>}
            <ul className="collab-rules muted">
              <li>{t('collab.rule.reader')}</li><li>{t('collab.rule.editor')}</li>{owner && <li>{t('collab.rule.owner')}</li>}
            </ul>
          </>}
          {err && <div className="notice error" role="alert" data-testid="share-error"><div>{err}</div></div>}
        </div>
        <div className="ft"><button type="button" className="btn sm ghost collab-keep" onClick={() => { onClose(); openDoc(pid, 'utilisateur', 'partager-un-projet') }}><Icon name="circle-question" /> {t('collab.help')}</button></div>
      </div>
    </div>
  )
}
