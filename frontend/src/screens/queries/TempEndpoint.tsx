import { useState } from 'react'
import { Button } from '../../kit'
import { useT } from '../../i18n'
import { qapi, type InlineEndpoint } from './qapi'
import { tempStore } from './tempEndpoint'

/** Petit formulaire en ligne : endpoint utilisé pour la session seulement (secret jamais persisté). */
export function TempEndpointForm({ pid, initial, onClose, onSaved }: { pid: string; initial: InlineEndpoint | null; onClose: () => void; onSaved: (id: string) => void }) {
  const t = useT()
  const [e, setE] = useState<InlineEndpoint>(initial ?? { url: '', auth: 'none' })
  const [save, setSave] = useState(false); const [name, setName] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null); const [busy, setBusy] = useState(false)
  const clean = (): InlineEndpoint => ({ ...e, url: e.url.trim(), username: e.auth === 'basic' ? e.username : undefined, secret: e.auth === 'none' ? undefined : e.secret || undefined, default_graph: e.default_graph?.trim() || undefined })
  const test = async () => {
    setBusy(true); setMsg(null)
    try { const r = await qapi.testInline(pid, clean()); setMsg({ ok: r.ok, text: r.ok ? t('q.tmp.ok', { ms: r.latency_ms ?? 0 }) : r.message || t('q.tmp.ko') }) }
    catch (x) { setMsg({ ok: false, text: (x as Error).message }) } finally { setBusy(false) }
  }
  const use = async () => {
    const c = clean()
    if (save) {
      setBusy(true)
      try {
        const created = await qapi.saveEndpoint({ ...c, name: name.trim() || c.url.replace(/^https?:\/\//, '').split('/')[0] })
        tempStore.set(null); onSaved(created.id); return
      } catch (x) { setMsg({ ok: false, text: (x as Error).message }); setBusy(false); return }
    }
    tempStore.set(c, true); onClose()
  }
  const f = (p: Partial<InlineEndpoint>) => setE(x => ({ ...x, ...p }))
  return (
    <div className="qtmp" data-tour="q-temp" role="group" aria-label={t('q.tmp.title')}>
      <div className="qtmp-row">
        <label className="f grow"><span>{t('q.tmp.url')}</span><input type="url" autoFocus value={e.url} onChange={x => f({ url: x.target.value })} placeholder="https://…/sparql" /></label>
        <label className="f"><span>{t('q.tmp.auth')}</span>
          <select value={e.auth} onChange={x => f({ auth: x.target.value as InlineEndpoint['auth'] })}>
            <option value="none">{t('q.tmp.auth.none')}</option><option value="basic">Basic</option><option value="bearer">Bearer</option></select></label>
        {e.auth === 'basic' && <label className="f"><span>{t('q.tmp.user')}</span><input type="text" autoComplete="off" value={e.username ?? ''} onChange={x => f({ username: x.target.value })} /></label>}
        {e.auth !== 'none' && <label className="f"><span>{t('q.tmp.secret')}</span><input type="password" autoComplete="new-password" value={e.secret ?? ''} onChange={x => f({ secret: x.target.value })} /></label>}
        <label className="f"><span>{t('q.tmp.graph')}</span><input type="text" value={e.default_graph ?? ''} onChange={x => f({ default_graph: x.target.value })} placeholder="http://…/graph" /></label>
      </div>
      <div className="qtmp-row">
        <label className="qt"><input type="checkbox" checked={save} onChange={x => setSave(x.target.checked)} />{t('q.tmp.save')}</label>
        {save && <input type="text" aria-label={t('q.tmp.name')} placeholder={t('q.tmp.name')} value={name} onChange={x => setName(x.target.value)} />}
        <span className="grow" />
        {msg && <span className={msg.ok ? 'qtmp-ok' : 'qtmp-ko'} role="status">{msg.text}</span>}
        <Button size="sm" variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
        <Button size="sm" icon="vial" disabled={busy || !e.url.trim()} onClick={() => void test()}>{t('q.tmp.test')}</Button>
        <Button size="sm" variant="primary" disabled={busy || !e.url.trim()} onClick={() => void use()}>{t('q.tmp.use')}</Button>
      </div>
      <p className="muted tiny">{save ? t('q.tmp.note.saved') : t('q.tmp.note')}</p>
    </div>
  )
}
