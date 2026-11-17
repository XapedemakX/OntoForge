import { useEffect, useState } from 'react'
import { Icon } from '../kit'
import { useReadOnly } from '../collab/readonly'
import { api } from '../api'
import type { ScreenProps } from '../shell/types'
import { CodeEditor, Empty, ErrorView, copy, download, useLoad, useToast } from '../ui'
import { useT } from '../i18n'
import { KrakieStatus, useResultFlash } from '../krakie/Krakie'

export function Exports({ p, target }: ScreenProps) {
  const t = useT()
  const toast = useToast()
  const roBody = useReadOnly()
  const [denied, setDenied] = useState(false)   // le serveur a refusé (403 read_only) avant que la présence ait appris le rôle
  const ro = roBody || denied   // L42 : un lecteur ne génère pas (la génération écrit l'historique) ; il consulte l'historique existant
  const { data, error, loading, reload } = useLoad(() => (ro ? Promise.resolve(null) : api.generate(p.id, target)), [p.id, target, p.updated_at, ro])
  useEffect(() => { if (error?.code === 'read_only') setDenied(true) }, [error])
  const past = useLoad(() => (ro ? api.generations(p.id) : Promise.resolve([])), [p.id, ro])
  const [file, setFile] = useState('')
  const done = useResultFlash(loading, !!data && !error)
  const names = data ? Object.keys(data.files).sort() : []
  useEffect(() => { if (names.length && !names.includes(file)) setFile(names[0]) }, [data])
  const content = data?.files[file] ?? ''
  const [jerr, setJerr] = useState<unknown>(null)
  const getJust = async (fmt: 'html' | 'md') => {   // L47 : lecture seule, ouvert au lecteur
    setJerr(null)
    try { download(`justification-${p.id}-${target}.${fmt}`, await api.justification(p.id, target, fmt), fmt === 'html' ? 'text/html' : 'text/markdown') } catch (e) { setJerr(e) }
  }
  return (
    <div className="page" data-safe>
      <div className="page-head"><h1>{t('ex.title')}</h1>
        <span className="badge">{target === 'curiosity' ? 'Curiosity' : 'Neo4j'}</span>
        <span className="grow" />
        <button className="btn" data-write disabled={ro} onClick={reload} title={ro ? t('collab.ro.hint') : undefined}>{t('ex.regen')}</button>
        <button className="btn" data-write disabled={ro} title={ro ? t('collab.ro.hint') : undefined} onClick={() => void api.downloadZip(p.id, target).catch(e => toast((e as Error).message))}>{t('ex.zip')}</button></div>
      {ro && <div className="notice soon" data-testid="gen-readonly"><span><Icon name="lock" /></span><div><b>{t('ex.ro.t')}</b><div>{t('ex.ro.b')}</div></div></div>}
      {ro && (past.data ?? []).length > 0 && <ul className="collab-activity" data-testid="gen-history">
        {(past.data ?? []).slice(0, 10).map((g, i) => <li key={i}><span className="muted">{new Date(g.at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })}</span> <b>{g.target === 'curiosity' ? 'Curiosity' : 'Neo4j'}</b> · {t('ex.files', { n: g.files.length })}</li>)}</ul>}
      <section className="card" data-testid="justification" style={{ margin: 'var(--s3) 0' }}>
        <div className="row"><div className="grow"><b>{t('ex.just.t')}</b><div className="muted">{t('ex.just.b')}</div></div>
          <button className="btn" data-testid="just-html" onClick={() => void getJust('html')}>{t('ex.just.html')}</button>
          <button className="btn" data-testid="just-md" onClick={() => void getJust('md')}>{t('ex.just.md')}</button></div>
        <ErrorView error={jerr} what={t('ex.just.what')} />
      </section>
      <KrakieStatus busy={loading} done={done} label={t('krakie.forge.exports')} doneLabel={t('krakie.done.exports')} />
      <ErrorView error={error?.code === 'read_only' ? null : error} what={t('ex.what')} />
      {data?.missing && data.missing.length > 0 && <div className="notice soon">{t('ex.missing', { list: data.missing.join(', ') })}</div>}
      {data && names.length === 0 && <Empty title={t('ex.empty.t')}>{t('ex.empty.b')}</Empty>}
      {data && names.length > 0 && <div className="exports" data-tour="exports">
        <div className="pane"><div className="hd"><b>{t('ex.files', { n: names.length })}</b></div><div className="scroll flist">{names.map(n => <button key={n} aria-current={n === file} onClick={() => setFile(n)} title={n}>{n}</button>)}</div></div>
        <div className="pane"><div className="hd"><code className="grow">{file}</code><span className="muted">{t('ex.lines', { n: content.split("\n").length })}</span>
          <button className="btn sm" onClick={async () => toast((await copy(content)) ? t('ex.copied') : t('ex.copyfail'))}>{t('ex.copy')}</button>
          <button className="btn sm" onClick={() => download(file.split('/').pop() || file, content)}>{t('ex.download')}</button></div>
          <div className="codeview"><CodeEditor key={file} value={content} readOnly filename={file} /></div></div>
      </div>}
    </div>
  )
}
