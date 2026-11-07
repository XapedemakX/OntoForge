import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ScreenProps } from '../shell/types'
import { CodeEditor, Empty, ErrorView, Spin, copy, download, useLoad, useToast } from '../ui'
import { useT } from '../i18n'

export function Exports({ p, target }: ScreenProps) {
  const t = useT()
  const toast = useToast()
  const { data, error, loading, reload } = useLoad(() => api.generate(p.id, target), [p.id, target, p.updated_at])
  const [file, setFile] = useState('')
  const names = data ? Object.keys(data.files).sort() : []
  useEffect(() => { if (names.length && !names.includes(file)) setFile(names[0]) }, [data])
  const content = data?.files[file] ?? ''
  return (
    <div className="page">
      <div className="page-head"><h1>{t('ex.title')}</h1>
        <span className="badge">{target === 'curiosity' ? 'Curiosity' : 'Neo4j'}</span>
        <span className="grow" /><button className="btn" onClick={reload}>{t('ex.regen')}</button>
        <a className="btn" href={api.zipUrl(p.id, target)} style={{ textDecoration: 'none', color: 'inherit' }}>{t('ex.zip')}</a></div>
      {loading && !data && <Spin />}<ErrorView error={error} what={t('ex.what')} />
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
