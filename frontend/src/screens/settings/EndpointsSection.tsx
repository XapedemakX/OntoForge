import { Fragment, useCallback, useEffect, useState } from 'react'
import { Button, Card, EmptyState, Field, Icon, Segmented } from '../../kit'
import { useT } from '../../i18n'
import { announceActiveEndpoint } from './activeEndpoint'
import { settingsApi, errMsg, SettingsError, type EndpointAuth, type EndpointView, type TestResult } from './settingsApi'
import { ErrorLine, SaveBar, SecretField, TestOutcome, secretPatch, useSaver, type SecretState } from './shared'

type Data = { endpoints: EndpointView[]; active: string | null }

function EndpointForm({ initial, onDone, onCancel }: { initial?: EndpointView; onDone: () => void; onCancel: () => void }) {
  const t = useT()
  const [name, setName] = useState(initial?.name ?? '')
  const [url, setUrl] = useState(initial?.url ?? '')
  const [auth, setAuth] = useState<EndpointAuth>(initial?.auth ?? 'none')
  const [user, setUser] = useState(initial?.username ?? '')
  const [graph, setGraph] = useState(initial?.default_graph ?? '')
  const [timeout, setTimeoutS] = useState(String(initial?.timeout_s ?? 30))
  const [sec, setSec] = useState<SecretState>({ mode: 'keep', value: '' })
  const [test, setTest] = useState<TestResult | 'loading'>()
  const saver = useSaver()
  const body = () => {
    const b: Record<string, unknown> = { name: name.trim(), url: url.trim(), auth, default_graph: graph.trim() || null, timeout_s: Number(timeout) }
    if (auth === 'basic') b.username = user.trim()
    if (auth !== 'none') { const s = secretPatch(sec); if ('v' in s) b.secret = s.v }
    return b
  }
  const check = () => {
    if (!name.trim()) throw new Error(t('settings.ep.nameRequired'))
    if (!/^https?:\/\//.test(url.trim())) throw new Error(t('settings.ep.urlInvalid'))
    const n = Number(timeout); if (!(n >= 1 && n <= 300)) throw new Error(t('settings.ep.timeoutInvalid'))
  }
  const save = () => saver.run(async () => { check(); if (initial) await settingsApi.updateEndpoint(initial.id, body()); else await settingsApi.addEndpoint(body()); onDone() })
  const doTest = async () => {
    setTest('loading')
    try {
      check()
      if (initial) setTest(await settingsApi.testEndpoint(initial.id, body()))
      else {  // endpoint non enregistré : pas de route de test sans id -> enregistrer d'abord
        setTest({ ok: false, message: t('settings.ep.testAfterSave') })
      }
    } catch (e) { setTest({ ok: false, message: errMsg(e) }) }
  }
  return (
    <form className="set-form" onSubmit={e => { e.preventDefault(); save() }} aria-label={initial ? t('settings.ep.edit') : t('settings.ep.add')}>
      <h3>{initial ? t('settings.ep.edit') : t('settings.ep.add')}</h3>
      <div className="set-grid">
        <Field label={t('settings.ep.name')}><input type="text" value={name} onChange={e => setName(e.target.value)} /></Field>
        <Field label="URL"><input type="text" className="mono" value={url} placeholder="https://example.org/sparql" onChange={e => setUrl(e.target.value)} /></Field>
        <div className="f"><span className="muted" style={{ fontSize: 'var(--fs-xs)' }}>{t('settings.ep.auth')}</span>
          <Segmented label={t('settings.ep.auth')} value={auth} onChange={setAuth} items={[['none', t('settings.ep.auth.none')], ['basic', 'Basic'], ['bearer', 'Bearer']]} /></div>
        {auth === 'basic' && <Field label={t('settings.ep.user')}><input type="text" autoComplete="off" value={user} onChange={e => setUser(e.target.value)} /></Field>}
        {auth !== 'none' && <SecretField label={auth === 'basic' ? t('settings.ep.password') : t('settings.ep.token')} has={!!initial?.has_secret && initial.auth === auth} unreadable={initial?.secret_unreadable} st={sec} setSt={setSec} />}
        <Field label={t('settings.ep.graph')}><input type="text" className="mono" value={graph} placeholder="https://example.org/graph" onChange={e => setGraph(e.target.value)} /></Field>
        <Field label={t('settings.ep.timeout')}><input type="number" min={1} max={300} value={timeout} onChange={e => setTimeoutS(e.target.value)} /></Field>
      </div>
      <div className="set-row"><Button icon="plug" onClick={doTest} disabled={test === 'loading'}>{t('settings.ep.test')}</Button></div>
      <TestOutcome r={test} />
      <SaveBar saver={saver} onSave={save} />
      <div><Button variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button></div>
    </form>)
}

export function EndpointsSection() {
  const t = useT()
  const [data, setData] = useState<Data | null>(null)
  const [soon, setSoon] = useState(false)
  const [err, setErr] = useState('')
  const [form, setForm] = useState<'new' | string | null>(null)
  const [confirm, setConfirm] = useState<string | null>(null)
  const [tests, setTests] = useState<Record<string, TestResult | 'loading'>>({})
  const load = useCallback(async (announce = false) => {
    try {
      const r = await settingsApi.endpoints()
      setData({ endpoints: r.endpoints, active: r.active_endpoint_id }); setSoon(false)
      if (announce) { const a = r.endpoints.find(e => e.id === r.active_endpoint_id); announceActiveEndpoint(a ? { id: a.id, name: a.name, url: a.url } : null) }
    } catch (e) { if (e instanceof SettingsError && e.notReady) setSoon(true); else setErr(errMsg(e)) }
  }, [])
  useEffect(() => { load() }, [load])
  const act = async (fn: () => Promise<unknown>) => { setErr(''); try { await fn(); await load(true) } catch (e) { setErr(errMsg(e)) } }
  const test = async (e: EndpointView) => {
    setTests(x => ({ ...x, [e.id]: 'loading' }))
    try { const r = await settingsApi.testEndpoint(e.id); setTests(x => ({ ...x, [e.id]: r })) } catch (er) { setTests(x => ({ ...x, [e.id]: { ok: false, message: errMsg(er) } })) }
  }
  const title = <><Icon name="database" /> {t('settings.ep.title')}</>
  if (soon) return <Card title={title}><div className="set-soon"><Icon name="hourglass-half" /><span>{t('common.soon')} — {t('settings.ep.soon')}</span></div></Card>
  const editing = form && form !== 'new' ? data?.endpoints.find(e => e.id === form) : undefined
  return (
    <Card title={title} actions={<Button icon="plus" onClick={() => setForm('new')}>{t('settings.ep.add')}</Button>}>
      <p className="set-hint">{t('settings.ep.intro')}</p>
      <ErrorLine msg={err} />
      {!data ? <p className="muted">{t('common.loading')}</p> : data.endpoints.length === 0 ? <EmptyState pose="reflechit" title={t('settings.ep.none')} /> : (
        <table className="set-table">
          <thead><tr><th>{t('settings.ep.active')}</th><th>{t('settings.ep.name')}</th><th>URL</th><th>{t('settings.ep.auth')}</th><th>{t('settings.ep.graph')}</th><th>{t('settings.ep.timeout')}</th><th /></tr></thead>
          <tbody>
            {data.endpoints.map(e => (
              <Fragment key={e.id}>
                <tr>
                  <td><label className="set-row" style={{ gap: 6 }}>
                    <input type="radio" name="active-endpoint" checked={data.active === e.id} onChange={() => act(async () => { await settingsApi.setActiveEndpoint(e.id) })} aria-label={t('settings.ep.makeActive', { name: e.name })} />
                    {data.active === e.id && <span className="set-chip on">{t('settings.ep.activeBadge')}</span>}</label></td>
                  <td><b>{e.name}</b></td>
                  <td className="mono">{e.url}</td>
                  <td>{e.auth === 'none' ? t('settings.ep.auth.none') : <>{e.auth === 'basic' ? 'Basic' : 'Bearer'} <span className="set-key">{e.secret_unreadable ? t('settings.secret.unreadable') : e.has_secret ? '••••' : t('settings.secret.none')}</span></>}</td>
                  <td className="mono">{e.default_graph || '—'}</td>
                  <td>{e.timeout_s} s</td>
                  <td className="acts">
                    <Button size="sm" icon="plug" onClick={() => test(e)}>{t('settings.ep.test')}</Button>{' '}
                    <Button size="sm" icon="pen" onClick={() => setForm(e.id)} aria-label={t('settings.ep.edit') + ' ' + e.name}>{t('common.edit')}</Button>{' '}
                    <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirm(e.id)} aria-label={t('common.delete') + ' ' + e.name}>{t('common.delete')}</Button>
                  </td>
                </tr>
                {(tests[e.id] || confirm === e.id) && (
                  <tr><td colSpan={7}>
                    <TestOutcome r={tests[e.id]} />
                    {confirm === e.id && (
                      <div className="set-confirm" role="alertdialog" aria-label={t('settings.ep.confirmDelete', { name: e.name })}>
                        <span className="grow">{t('settings.ep.confirmDelete', { name: e.name })}</span>
                        <Button variant="danger" icon="trash" onClick={() => act(async () => { await settingsApi.deleteEndpoint(e.id); setConfirm(null) })}>{t('common.delete')}</Button>
                        <Button onClick={() => setConfirm(null)}>{t('common.cancel')}</Button>
                      </div>)}
                  </td></tr>)}
              </Fragment>))}
          </tbody>
        </table>)}
      {form && (form === 'new' || editing) && <EndpointForm key={form} initial={editing} onCancel={() => setForm(null)} onDone={async () => { setForm(null); await load(true) }} />}
    </Card>)
}
