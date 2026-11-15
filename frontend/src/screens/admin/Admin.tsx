import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError, type AdminAccount, type AuditEntry } from '../../api'
import { Button, Card, Icon, Tabs } from '../../kit'
import { useI18n } from '../../i18n'
import { copy, ErrorView, useToast } from '../../ui'
import { useAuth } from '../../auth/AuthGate'
import { setAssistantContext } from '../../lib/assistantContext'
import '../settings/settings.css'
import './admin.css'

type Tab = 'accounts' | 'audit'
type Ask = { kind: 'reset' | 'delete' | 'revert'; login: string }
type Prov = { login: string; password: string; kind: 'create' | 'reset' }

/** Administration › Comptes (L42, administrateurs seulement) : liste, création, réinitialisation, désactivation, suppression, rôle, journal. */
export function Admin() {
  const { t, lang } = useI18n()
  const toast = useToast()
  const auth = useAuth()
  const [tab, setTab] = useState<Tab>('accounts')
  const [rows, setRows] = useState<AdminAccount[] | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const [prov, setProv] = useState<Prov | null>(null)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ login: '', password: '', admin: false })
  const [showPw, setShowPw] = useState(false)
  const [ask, setAsk] = useState<Ask | null>(null)
  const [target, setTarget] = useState('')
  const [audit, setAudit] = useState<AuditEntry[] | null>(null)
  useEffect(() => { setAssistantContext({ screen: 'admin' }) }, [])
  const load = useCallback(async () => { try { setRows((await api.adminAccounts()).accounts); setErr(null) } catch (e) { setErr(e) } }, [])
  useEffect(() => { void load() }, [load])
  useEffect(() => { if (tab === 'audit') api.adminAudit().then(r => setAudit(r.entries)).catch(setErr) }, [tab, rows])
  const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString(lang, { dateStyle: 'short', timeStyle: 'short' }) : t('adm.never'))
  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    setBusy(true); setErr(null)
    try { await fn(); if (ok) toast(ok); await load() } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const create = async (e: FormEvent) => {
    e.preventDefault()
    if (!form.login.trim()) return
    await run(async () => {
      const r = await api.adminCreate({ login: form.login.trim(), password: form.password || undefined, admin: form.admin })
      setProv(r.provisional_password ? { login: r.account.login, password: r.provisional_password, kind: 'create' } : null)
      if (!r.provisional_password) toast(t('adm.created.typed', { login: r.account.login }))
      setForm({ login: '', password: '', admin: false })
    })
  }
  const others = (rows ?? []).filter(a => a.active && a.login !== ask?.login)
  const doDelete = () => ask && run(async () => {
    const r = await api.adminDelete(ask.login, target || undefined)
    setAsk(null); toast(t('adm.deleted', { login: ask.login, n: r.projects_moved }))
  })
  const doReset = () => ask && run(async () => {
    const r = await api.adminReset(ask.login)
    setProv(r.provisional_password ? { login: ask.login, password: r.provisional_password, kind: 'reset' } : null); setAsk(null)
  })
  const doRevert = () => ask && run(async () => { await api.adminRevert(ask.login); setAsk(null); toast(t('adm.reverted', { login: ask.login })) })
  const diverged = (rows ?? []).filter(a => a.cfg_changed).map(a => a.login)
  const errText = err instanceof ApiError && err.code ? (t('adm.err.' + err.code) !== 'adm.err.' + err.code ? t('adm.err.' + err.code) : err.message) : null
  return (
    <div className="page set-page adm-page" data-testid="admin-page">
      <div className="page-head"><h1 style={{ margin: 0 }}>{t('adm.title')}</h1><span className="sub">{t('adm.sub')}</span></div>
      <Tabs value={tab} onChange={setTab} items={[['accounts', t('adm.tab.accounts')], ['audit', t('adm.tab.audit')]]} />
      {errText ? <div className="notice error" role="alert" data-testid="adm-error"><div>{errText}</div></div> : <ErrorView error={err} what={t('adm.title')} />}
      {tab === 'accounts' && <>
        {prov && (
          <div className="adm-prov" role="status" data-testid="adm-prov">
            <b><Icon name="key" /> {t(prov.kind === 'create' ? 'adm.prov.create' : 'adm.prov.reset', { login: prov.login })}</b>
            <code data-testid="adm-prov-pw">{prov.password}</code>
            <span className="muted">{t('adm.prov.once')}</span>
            <div className="row"><Button size="sm" icon="copy" onClick={async () => toast((await copy(prov.password)) ? t('ex.copied') : t('ex.copyfail'))}>{t('ex.copy')}</Button>
              <Button size="sm" variant="ghost" data-testid="adm-prov-close" onClick={() => setProv(null)}>{t('adm.prov.close')}</Button></div>
          </div>)}
        {diverged.length > 0 && <div className="notice warn" role="alert" data-testid="adm-cfg-warning"><div><b><Icon name="triangle-exclamation" /> {t('adm.cfgChanged')}</b><div>{t('adm.cfgChanged.warn', { logins: diverged.map(l => '« ' + l + ' »').join(', ') })}</div></div></div>}
        <Card title={<><Icon name="user-plus" /> {t('adm.new')}</>}>
          <form onSubmit={create} className="adm-form" noValidate>
            <label className="f">{t('adm.login')}<input type="text" value={form.login} autoComplete="off" autoCapitalize="none" spellCheck={false} data-testid="adm-login" placeholder={t('adm.login.ph')} onChange={e => setForm({ ...form, login: e.target.value })} /></label>
            <label className="f">{t('adm.password')}<input type={showPw ? 'text' : 'password'} value={form.password} autoComplete="new-password" spellCheck={false} data-testid="adm-password" placeholder={t('adm.password.ph')} onChange={e => setForm({ ...form, password: e.target.value })} />
              <span className="adm-check" style={{ minHeight: 28 }}><input type="checkbox" checked={showPw} data-testid="adm-password-show" aria-label={t('adm.password.show')} onChange={e => setShowPw(e.target.checked)} /> <small>{t('adm.password.show')}</small></span></label>
            <label className="adm-check"><input type="checkbox" checked={form.admin} data-testid="adm-isadmin" onChange={e => setForm({ ...form, admin: e.target.checked })} /> {t('adm.isadmin')}</label>
            <Button variant="primary" type="submit" icon="user-plus" data-testid="adm-create" disabled={busy || !form.login.trim()}>{t('adm.create')}</Button>
          </form>
          <p className="muted" style={{ margin: '8px 0 0', fontSize: 'var(--fs-sm)' }}>{t('adm.new.hint')}</p>
        </Card>
        <Card title={<><Icon name="users" /> {t('adm.list')}</>}>
          {!rows ? <p className="muted">{t('common.loading')}</p> : (
            <div className="adm-wrap"><table className="adm-table" data-testid="adm-table">
              <thead><tr><th>{t('adm.col.login')}</th><th>{t('adm.col.role')}</th><th>{t('adm.col.source')}</th><th>{t('adm.col.active')}</th><th>{t('adm.col.last')}</th><th>{t('adm.col.projects')}</th><th /></tr></thead>
              <tbody>{rows.map(a => (
                <tr key={a.login} data-testid={`adm-row-${a.login}`} className={a.active ? '' : 'adm-off'}>
                  <td data-l={t('adm.col.login')}><b>{a.login}</b>{a.login === auth.user && <span className="muted"> {t('collab.you')}</span>}{a.must_change && <span className="set-chip warn" style={{ marginLeft: 6 }}>{t('adm.mustchange')}</span>}</td>
                  <td data-l={t('adm.col.role')}>{a.admin ? <span className="badge ok">{t('adm.role.admin')}</span> : <span className="badge">{t('adm.role.user')}</span>}</td>
                  <td data-l={t('adm.col.source')}>{a.managed ? <><span className="set-chip" title={t('adm.managed.hint')}><Icon name="lock" /> {t('adm.managed')}</span>
                    {a.pw_override && <span className="set-chip on" style={{ marginLeft: 6 }} title={t('adm.pwOverride.hint')} data-testid={`adm-override-${a.login}`}><Icon name="key" /> {t('adm.pwOverride')}</span>}
                    {a.cfg_changed && <span className="set-chip warn" style={{ marginLeft: 6 }} title={t('adm.cfgChanged.hint')} data-testid={`adm-cfgchanged-${a.login}`}><Icon name="triangle-exclamation" /> {t('adm.cfgChanged')}</span>}</> : <span className="set-chip">{t('adm.source.interface')}</span>}</td>
                  <td data-l={t('adm.col.active')}>{a.active ? <span className="set-chip on">{t('adm.yes')}</span> : <span className="set-chip warn">{t('adm.no')}</span>}</td>
                  <td data-l={t('adm.col.last')}>{fmt(a.last_login)}</td>
                  <td data-l={t('adm.col.projects')}>{a.projects ?? 0}</td>
                  <td className="acts">{a.managed ? <>
                    <Button size="sm" icon="key" data-testid={`adm-reset-${a.login}`} disabled={busy} onClick={() => setAsk({ kind: 'reset', login: a.login })}>{t('adm.reset')}</Button>
                    {a.pw_override && <Button size="sm" icon="rotate-left" data-testid={`adm-revert-${a.login}`} disabled={busy} onClick={() => setAsk({ kind: 'revert', login: a.login })}>{t('adm.revert')}</Button>}
                    <div className="muted" style={{ fontSize: 'var(--fs-xs)' }}>{t('adm.cfgOnly')}</div></> : <>
                    <Button size="sm" icon="key" data-testid={`adm-reset-${a.login}`} disabled={busy} onClick={() => setAsk({ kind: 'reset', login: a.login })}>{t('adm.reset')}</Button>
                    <Button size="sm" icon={a.active ? 'user-slash' : 'user-check'} data-testid={`adm-toggle-${a.login}`} disabled={busy} onClick={() => void run(() => api.adminActive(a.login, !a.active))}>{a.active ? t('adm.disable') : t('adm.enable')}</Button>
                    <Button size="sm" icon="user-shield" data-testid={`adm-admin-${a.login}`} disabled={busy} onClick={() => void run(() => api.adminSetAdmin(a.login, !a.admin))}>{a.admin ? t('adm.demote') : t('adm.promote')}</Button>
                    <Button size="sm" variant="danger" icon="trash" data-testid={`adm-delete-${a.login}`} disabled={busy} onClick={() => { setAsk({ kind: 'delete', login: a.login }); setTarget(auth.user ?? '') }}>{t('adm.delete')}</Button></>}</td>
                </tr>))}</tbody></table></div>)}
          {ask?.kind === 'reset' && (
            <div className="notice warn adm-ask" role="alert" data-testid="adm-ask-reset"><div><b>{t('adm.reset.ask', { login: ask.login })}</b><div>{t(rows?.find(a => a.login === ask.login)?.managed ? 'adm.reset.body.cfg' : 'adm.reset.body')}</div>
              <div className="row" style={{ marginTop: 8 }}><Button size="sm" variant="primary" data-testid="adm-reset-yes" disabled={busy} onClick={doReset}>{t('adm.reset.yes')}</Button><Button size="sm" variant="ghost" onClick={() => setAsk(null)}>{t('common.cancel')}</Button></div></div></div>)}
          {ask?.kind === 'revert' && (
            <div className="notice warn adm-ask" role="alert" data-testid="adm-ask-revert"><div><b>{t('adm.revert.ask', { login: ask.login })}</b><div>{t('adm.revert.body')}</div>
              <div className="row" style={{ marginTop: 8 }}><Button size="sm" variant="primary" data-testid="adm-revert-yes" disabled={busy} onClick={doRevert}>{t('adm.revert.yes')}</Button><Button size="sm" variant="ghost" onClick={() => setAsk(null)}>{t('common.cancel')}</Button></div></div></div>)}
          {ask?.kind === 'delete' && (() => {
            const owned = rows?.find(a => a.login === ask.login)?.projects ?? 0
            return (
              <div className="notice error adm-ask" role="alert" data-testid="adm-ask-delete"><div><b>{t('adm.delete.ask', { login: ask.login })}</b><div>{t('adm.delete.body')}</div>
                {owned > 0 && <label className="f" style={{ marginTop: 8 }}>{t('adm.delete.transfer', { n: owned })}
                  <select value={target} data-testid="adm-transfer" onChange={e => setTarget(e.target.value)}>
                    {others.map(a => <option key={a.login} value={a.login}>{a.login}</option>)}</select></label>}
                <div className="row" style={{ marginTop: 8 }}><Button size="sm" variant="danger" data-testid="adm-delete-yes" disabled={busy || (owned > 0 && !target)} onClick={doDelete}>{t('adm.delete.yes')}</Button><Button size="sm" variant="ghost" onClick={() => setAsk(null)}>{t('common.cancel')}</Button></div></div></div>)
          })()}
        </Card>
        <p className="set-hint">{t('adm.rules')}</p>
      </>}
      {tab === 'audit' && (
        <Card title={<><Icon name="clipboard-list" /> {t('adm.audit')}</>}>
          <p className="set-hint">{t('adm.audit.hint')}</p>
          {!audit ? <p className="muted">{t('common.loading')}</p> : audit.length === 0 ? <p className="muted">{t('adm.audit.none')}</p> : (
            <div className="adm-wrap"><table className="adm-table" data-testid="adm-audit">
              <thead><tr><th>{t('adm.audit.when')}</th><th>{t('adm.audit.who')}</th><th>{t('adm.audit.what')}</th><th>{t('adm.audit.target')}</th></tr></thead>
              <tbody>{audit.slice(0, 100).map((e, i) => (
                <tr key={i}><td data-l={t('adm.audit.when')}>{fmt(e.at)}</td><td data-l={t('adm.audit.who')}><b>{e.actor}</b></td>
                  <td data-l={t('adm.audit.what')}>{t('adm.act.' + e.action) === 'adm.act.' + e.action ? e.action : t('adm.act.' + e.action)}{e.detail?.as_admin ? <span className="muted"> · {t('collab.asAdmin')}</span> : null}</td>
                  <td data-l={t('adm.audit.target')}>{e.target}</td></tr>))}</tbody></table></div>)}
        </Card>)}
    </div>
  )
}
