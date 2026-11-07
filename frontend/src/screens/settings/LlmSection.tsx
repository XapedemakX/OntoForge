import { Fragment, useState } from 'react'
import { Button, Card, EmptyState, Field, Icon, Select } from '../../kit'
import { useT } from '../../i18n'
import { settingsApi, errMsg, type ProviderInput, type ProviderKind, type ProviderView, type SettingsView, type TestResult } from './settingsApi'
import { ErrorLine, SaveBar, SecretField, TestOutcome, secretPatch, useSaver, type SecretState } from './shared'

const KINDS: ProviderKind[] = ['anthropic', 'openai_compat', 'ollama', 'mock']
const needsUrl = (k: ProviderKind) => k === 'openai_compat' || k === 'ollama'
const needsKey = (k: ProviderKind) => k === 'anthropic' || k === 'openai_compat'

function ProviderForm({ initial, onDone, onCancel }: { initial?: ProviderView; onDone: () => void; onCancel: () => void }) {
  const t = useT()
  const [name, setName] = useState(initial?.name ?? '')
  const [kind, setKind] = useState<ProviderKind>(initial?.kind ?? 'anthropic')
  const [url, setUrl] = useState(initial?.base_url ?? '')
  const [model, setModel] = useState(initial?.model ?? '')
  const [key, setKey] = useState<SecretState>({ mode: 'keep', value: '' })
  const saver = useSaver()
  const [test, setTest] = useState<TestResult | 'loading'>()
  const body = (): ProviderInput => {
    const b: ProviderInput = { name: name.trim(), model: model.trim() }
    if (!initial) b.kind = kind
    if (needsUrl(kind)) b.base_url = url.trim()
    if (needsKey(kind)) { const s = secretPatch(key); if ('v' in s) b.api_key = s.v }
    return b
  }
  const save = () => saver.run(async () => {
    if (!name.trim()) throw new Error(t('settings.llm.nameRequired'))
    if (needsUrl(kind) && !url.trim()) throw new Error(t('settings.llm.urlRequired'))
    if (initial) await settingsApi.updateProvider(initial.id, body()); else await settingsApi.addProvider(body())
    onDone()
  })
  const doTest = async () => {
    if (!initial) return
    setTest('loading')
    const b: ProviderInput = { model: model.trim() || undefined }
    if (needsUrl(kind)) b.base_url = url.trim()
    if (key.mode === 'replace' && key.value) b.api_key = key.value
    try { setTest(await settingsApi.testProvider(initial.id, b)) } catch (e) { setTest({ ok: false, message: errMsg(e) }) }
  }
  return (
    <form className="set-form" onSubmit={e => { e.preventDefault(); save() }} aria-label={initial ? t('settings.llm.edit') : t('settings.llm.add')}>
      <h3>{initial ? t('settings.llm.edit') : t('settings.llm.add')}</h3>
      <div className="set-grid">
        <Field label={t('settings.llm.name')}><input type="text" value={name} onChange={e => setName(e.target.value)} /></Field>
        <Field label={t('settings.llm.kind')}>
          <Select value={kind} disabled={!!initial} onChange={e => setKind(e.target.value as ProviderKind)} options={KINDS.map(k => ({ value: k, label: t('settings.kind.' + k) }))} /></Field>
        {kind !== 'mock' && <Field label={t('settings.llm.model')}><input type="text" value={model} onChange={e => setModel(e.target.value)} /></Field>}
        {needsUrl(kind) && <Field label={t('settings.llm.url')}><input type="text" value={url} placeholder={kind === 'ollama' ? 'http://localhost:11434' : 'https://api.example.org/v1'} onChange={e => setUrl(e.target.value)} /></Field>}
        {needsKey(kind) && <SecretField label={t('settings.llm.key')} has={!!initial?.has_key} last4={initial?.key_last4} unreadable={initial?.key_unreadable} st={key} setSt={setKey} />}
      </div>
      {kind === 'mock' && <p className="set-hint">{t('settings.llm.mockHint')}</p>}
      {initial && <div className="set-row"><Button icon="plug" onClick={doTest} disabled={test === 'loading'}>{t('settings.llm.test')}</Button></div>}
      {!initial && kind !== 'mock' && <p className="set-hint">{t('settings.llm.testAfterSave')}</p>}
      <TestOutcome r={test} />
      <SaveBar saver={saver} onSave={save} />
      <div><Button variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button></div>
    </form>)
}

export function LlmSection({ s, reload }: { s: SettingsView; reload: () => Promise<void> }) {
  const t = useT()
  const [form, setForm] = useState<'new' | string | null>(null)
  const [confirm, setConfirm] = useState<string | null>(null)
  const [tests, setTests] = useState<Record<string, TestResult | 'loading'>>({})
  const [err, setErr] = useState('')
  const act = async (fn: () => Promise<unknown>) => { setErr(''); try { await fn(); await reload() } catch (e) { setErr(errMsg(e)) } }
  const test = async (p: ProviderView) => {
    setTests(x => ({ ...x, [p.id]: 'loading' }))
    try { const r = await settingsApi.testProvider(p.id); setTests(x => ({ ...x, [p.id]: r })) } catch (e) { setTests(x => ({ ...x, [p.id]: { ok: false, message: errMsg(e) } })) }
  }
  const editing = form && form !== 'new' ? s.llm_providers.find(p => p.id === form) : undefined
  return (
    <Card title={<><Icon name="robot" /> {t('settings.llm.title')}</>} actions={<Button icon="plus" onClick={() => setForm('new')}>{t('settings.llm.add')}</Button>}>
      <p className="set-hint">{t('settings.llm.intro')}</p>
      <ErrorLine msg={err} />
      {s.llm_providers.length === 0 ? <EmptyState pose="reflechit" title={t('settings.llm.none')} /> : (
        <table className="set-table">
          <thead><tr><th>{t('settings.llm.name')}</th><th>{t('settings.llm.kind')}</th><th>{t('settings.llm.model')}</th><th>{t('settings.llm.url')}</th><th>{t('settings.llm.key')}</th><th>{t('settings.llm.default')}</th><th /></tr></thead>
          <tbody>
            {s.llm_providers.map(p => (
              <Fragment key={p.id}>
                <tr>
                  <td><b>{p.name}</b> {!p.configured && <span className="set-chip warn">{t('settings.llm.notConfigured')}</span>}</td>
                  <td>{t('settings.kind.' + p.kind)}</td>
                  <td className="mono">{p.kind === 'mock' ? '—' : p.model}</td>
                  <td className="mono">{p.base_url || '—'}</td>
                  <td className="set-key">{p.kind === 'mock' || p.kind === 'ollama' ? '—' : p.key_unreadable ? t('settings.secret.unreadable') : p.has_key ? `•••• ${p.key_last4 || '••••'}` : t('settings.secret.none')}</td>
                  <td>{p.id === s.default_provider_id
                    ? <span className="set-chip on"><Icon name="star" /> {t('settings.llm.default')}</span>
                    : <Button size="sm" onClick={() => act(() => settingsApi.put({ default_provider_id: p.id }))}>{t('settings.llm.makeDefault')}</Button>}</td>
                  <td className="acts">
                    <Button size="sm" icon="plug" onClick={() => test(p)}>{t('settings.llm.test')}</Button>{' '}
                    <Button size="sm" icon="pen" onClick={() => setForm(p.id)} aria-label={t('settings.llm.edit') + ' ' + p.name}>{t('common.edit')}</Button>{' '}
                    {p.kind !== 'mock' && <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirm(p.id)} aria-label={t('common.delete') + ' ' + p.name}>{t('common.delete')}</Button>}
                  </td>
                </tr>
                {(tests[p.id] || confirm === p.id) && (
                  <tr><td colSpan={7}>
                    <TestOutcome r={tests[p.id]} />
                    {confirm === p.id && (
                      <div className="set-confirm" role="alertdialog" aria-label={t('settings.llm.confirmDelete', { name: p.name })}>
                        <span className="grow">{t('settings.llm.confirmDelete', { name: p.name })}</span>
                        <Button variant="danger" icon="trash" onClick={() => act(async () => { await settingsApi.deleteProvider(p.id); setConfirm(null) })}>{t('common.delete')}</Button>
                        <Button onClick={() => setConfirm(null)}>{t('common.cancel')}</Button>
                      </div>)}
                  </td></tr>)}
              </Fragment>))}
          </tbody>
        </table>)}
      {form && (form === 'new' || editing) && <ProviderForm key={form} initial={editing} onCancel={() => setForm(null)} onDone={async () => { setForm(null); await reload() }} />}
    </Card>)
}
