import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Icon } from '../../kit'
import { useT } from '../../i18n'
import { qapi, type Semantics, type ShaclCheck, type StoreStats } from './qapi'

const localName = (iri: string) => iri.replace(/^.*[#/]/, '')

/** Panneau du triplestore local (L19) : contenu, chargement de données de démo ou d'un fichier, inférence, validation SHACL, vidage. */
export function LocalStorePanel({ pid, version }: { pid: string; version: string }) {
  const t = useT()
  const [st, setSt] = useState<StoreStats | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [infer, setInfer] = useState(false)
  const [sem, setSem] = useState<Semantics>('rdfs')
  const [shacl, setShacl] = useState<ShaclCheck | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const apply = useCallback((s: StoreStats) => {
    setSt(s); setInfer(!!s.inference); if (s.inference) setSem(s.inference.semantics)
  }, [])
  useEffect(() => { qapi.storeStats(pid).then(s => { setSt(s); setInfer(!!s.inference); if (s.inference) setSem(s.inference.semantics) }).catch(e => setErr((e as Error).message)) }, [pid, version])

  const act = async (name: string, f: () => Promise<StoreStats>) => {
    setBusy(name); setErr(null); setShacl(null)
    try { apply(await f()) } catch (e) { setErr((e as Error).message) } finally { setBusy(null) }
  }
  const inf = (): Semantics | 'none' => (infer ? sem : 'none')
  const validate = async () => {
    setBusy('validate'); setErr(null)
    try { setShacl(await qapi.storeValidate(pid)) } catch (e) { setErr((e as Error).message) } finally { setBusy(null) }
  }
  const kindLabel = (k: string) => t('q.local.k.' + k)
  const n = (x: number) => x.toLocaleString('fr-FR').replace(/ /g, ' ')

  return (
    <div className="qtmp qlocal" data-tour="q-local" data-testid="local-panel" role="group" aria-label={t('q.local.title')}>
      <div className="qtmp-row">
        <b><Icon name="database" /> {t('q.local.title')}</b>
        <span className="muted tiny grow">{t('q.local.note')}</span>
        <span className="qlocal-n" data-testid="local-count" role="status">{st ? t('q.local.count', { n: n(st.triples) }) : '…'}</span>
      </div>
      {st && st.graphs.length > 0 && (
        <ul className="qshown qlocal-g" aria-label={t('q.local.graphs')}>
          {st.graphs.map(g => <li key={g.graph} title={g.kind === 'data' ? g.name : g.graph}>{kindLabel(g.kind)}{g.kind === 'data' ? ` ${g.name}` : g.kind === 'inferred' ? ` ${g.name.toUpperCase()}` : ''} <b>{n(g.triples)}</b></li>)}
        </ul>
      )}
      <div className="qtmp-row">
        {st?.demo && <Button size="sm" icon="flask" disabled={!!busy} data-testid="local-demo" onClick={() => void act('demo', () => qapi.storeLoad(pid, { sample: 'demo', inference: inf() }))}>{busy === 'demo' ? t('q.local.loading') : t('q.local.demo')}</Button>}
        <Button size="sm" icon="file-import" disabled={!!busy} onClick={() => fileRef.current?.click()}>{busy === 'file' ? t('q.local.loading') : t('q.local.file')}</Button>
        <input ref={fileRef} type="file" hidden data-testid="local-file" accept=".ttl,.nt,.jsonld,.json,.rdf,.owl,.xml,text/turtle"
          onChange={e => { const f = e.target.files?.[0]; if (f) void act('file', () => qapi.storeLoad(pid, { file: f, inference: inf() })); e.target.value = '' }} />
        <label className="qt"><input type="checkbox" data-testid="local-infer" checked={infer} disabled={!!busy} onChange={e => { setInfer(e.target.checked); void act('infer', () => qapi.storeLoad(pid, { inference: e.target.checked ? sem : 'none' })) }} />{t('q.local.infer')}</label>
        <select aria-label={t('q.local.sem')} value={sem} disabled={!infer || !!busy} onChange={e => { const v = e.target.value as Semantics; setSem(v); if (infer) void act('infer', () => qapi.storeLoad(pid, { inference: v })) }}>
          <option value="rdfs">RDFS</option><option value="owlrl">OWL RL</option><option value="both">{t('q.local.sem.both')}</option></select>
        <span className="grow" />
        <Button size="sm" icon="circle-check" disabled={!!busy || !st?.exists} data-testid="local-validate" onClick={() => void validate()}>{busy === 'validate' ? t('q.local.loading') : t('q.local.validate')}</Button>
        {st?.ontology_stale && <Button size="sm" icon="rotate" disabled={!!busy} onClick={() => void act('sync', () => qapi.storeLoad(pid, { inference: inf() }))}>{t('q.local.sync')}</Button>}
        <Button size="sm" variant="ghost" icon="trash-can" disabled={!!busy || !st?.exists} data-testid="local-clear" onClick={() => void act('clear', () => qapi.storeClear(pid))}>{t('q.local.clear')}</Button>
      </div>
      {st?.inference && <p className="muted tiny" data-testid="local-inf-info">{t('q.local.inf.info', { n: n(st.inference.triples), s: st.inference.semantics === 'both' ? 'RDFS + OWL RL' : st.inference.semantics === 'rdfs' ? 'RDFS' : 'OWL RL' })}{st.inference.stale ? ' ' + t('q.local.inf.stale') : ''}{(st.inference.notes ?? []).map((x, i) => <span key={i}> {x}</span>)}</p>}
      {err && <p className="qtmp-ko" role="alert">{err}</p>}
      {shacl && (
        <div className="qlocal-shacl" role="status" data-testid="local-shacl">
          <span className={shacl.conforms ? 'qtmp-ok' : 'qtmp-ko'}><Icon name={shacl.conforms ? 'circle-check' : 'circle-xmark'} /> {shacl.conforms ? t('q.local.shacl.ok', { n: n(shacl.validated_triples) }) : t('q.local.shacl.ko', { n: shacl.results.length })}</span>
          {(shacl.warnings ?? []).map((w, i) => <span key={i} className="muted tiny"> {w}</span>)}
          {!shacl.conforms && <ul className="qlocal-res">{shacl.results.slice(0, 5).map((r, i) => <li key={i}><b>{localName(r.focus)}</b>{r.path ? ` · ${localName(r.path)}` : ''} — {r.message || r.severity}</li>)}{shacl.results.length > 5 && <li className="muted">{t('q.local.shacl.more', { n: shacl.results.length - 5 })}</li>}</ul>}
        </div>
      )}
      <p className="muted tiny">{t('q.local.limits', { mb: st?.limits.max_upload_mb ?? 25, t: st ? n(st.limits.max_triples) : '…', s: st?.limits.query_timeout_s ?? 20 })}</p>
    </div>
  )
}
