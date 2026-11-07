import { useState } from 'react'
import { api, type ProjectSummary } from '../api'
import { Button, Card, EmptyState, Icon, IconButton } from '../kit'
import { useI18n } from '../i18n'
import { ErrorView, Spin, useLoad, useToast } from '../ui'
import { aapi, type UploadedFile } from './assistant/aapi'

const ASSISTANT_EXT = /\.(csv|tsv|sql|txt|md|markdown)$/i
export const HANDOFF_KEY = 'of-handoff-'   // sessionStorage : fichier à joindre à l'assistant du projet <id>

export function Projects() {
  const { t, lang } = useI18n()
  const toast = useToast()
  const list = useLoad(() => api.listProjects(), [])
  const samples = useLoad(() => api.samples(), [])
  const [name, setName] = useState('')
  const [sample, setSample] = useState('')
  const [over, setOver] = useState(false)
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [staged, setStaged] = useState<File | null>(null)
  const open = (id: string, screen = 'tableau') => { location.hash = `#/projet/${id}/${screen}` }
  const date = (iso: string) => new Date(iso).toLocaleDateString(lang, { dateStyle: 'medium' })

  const create = async () => {
    setBusy(true); setErr(null)
    try {
      const sm = samples.data?.find(s => s.name === sample)
      const pr = await api.createProject({ name: name.trim() || sm?.title || t('proj.default'), sample: sample || undefined })
      open(pr.id)
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const drop = async (files: FileList | File[]) => {
    const f = Array.from(files)[0]; if (!f) return
    if (ASSISTANT_EXT.test(f.name)) { setStaged(f); return }   // CSV / SQL / texte : on propose l'assistant
    setBusy(true); setErr(null)
    try {
      const pr = await api.createProject({ name: f.name.replace(/\.[^.]+$/, '') })
      try {
        const r = await api.importFile(pr.id, f, 'auto')
        if (r.warnings.length) toast(t('proj.drop.warn', { n: r.warnings.length }))
        open(pr.id)
      } catch (e) { await api.deleteProject(pr.id).catch(() => {}); throw e }
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const withAssistant = async () => {
    if (!staged) return
    setBusy(true); setErr(null)
    try {
      const up: UploadedFile = await aapi.upload(staged)
      const pr = await api.createProject({ name: staged.name.replace(/\.[^.]+$/, '') })
      try { sessionStorage.setItem(HANDOFF_KEY + pr.id, JSON.stringify(up)) } catch { /* stockage indisponible : le fichier se joint à la main */ }
      setStaged(null); open(pr.id, 'assistant')
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }

  return (
    <div className="page">
      <div className="page-head"><h1>{t('proj.title')}</h1><span className="sub">{t('proj.sub')}</span></div>
      <ErrorView error={err} what={t('proj.op')} />
      <Card title={t('proj.new')}>
        <div className="row">
          <label className="f">{t('proj.name')}<input type="text" value={name} onChange={e => setName(e.target.value)} placeholder={t('proj.name.ph')} style={{ width: 240 }} /></label>
          <label className="f">{t('proj.start')}
            <select value={sample} onChange={e => setSample(e.target.value)} style={{ width: 280 }}>
              <option value="">{t('proj.empty')}</option>
              {samples.data?.map(s => <option key={s.name} value={s.name}>{t('proj.sample', { title: s.title, name: s.name })}</option>)}
            </select></label>
          <Button variant="primary" disabled={busy} onClick={create} style={{ alignSelf: 'flex-end' }}>{t('proj.create')}</Button>
        </div>
      </Card>
      {staged ? (
        <Card tone="info" title={t('proj.staged.t', { name: staged.name })}>
          <p className="muted" style={{ margin: '0 0 10px' }}>{t('proj.staged.d')}</p>
          <div className="row">
            <Button variant="primary" icon="wand-magic-sparkles" disabled={busy} onClick={withAssistant}>{t('proj.staged.go')}</Button>
            <Button variant="ghost" disabled={busy} onClick={() => setStaged(null)}>{t('proj.staged.cancel')}</Button>
          </div>
        </Card>
      ) : (
        <div className={'drop' + (over ? ' over' : '')} onDragOver={e => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
          onDrop={e => { e.preventDefault(); setOver(false); void drop(e.dataTransfer.files) }}>
          <b>{t('proj.drop.title')}</b>
          <div>{t('proj.drop.body')}</div>
          <label className="btn" style={{ display: 'inline-block', marginTop: 8 }}>{t('proj.drop.pick')}
            <input type="file" hidden onChange={e => { if (e.target.files) void drop(e.target.files); e.target.value = '' }} /></label>
        </div>
      )}
      {list.loading && <Spin />}
      <ErrorView error={list.error} what={t('proj.list')} />
      {list.data && list.data.length === 0 && <EmptyState title={t('proj.none.t')} pose="accueil">{t('proj.none.d')}</EmptyState>}
      <div className="proj-grid">
        {list.data?.map(pr => <ProjectCard key={pr.id} pr={pr} date={date} open={() => open(pr.id)} reload={list.reload} fail={setErr} />)}
      </div>
    </div>
  )
}

function ProjectCard({ pr, date, open, reload, fail }: { pr: ProjectSummary; date: (s: string) => string; open: () => void; reload: () => void; fail: (e: unknown) => void }) {
  const { t } = useI18n()
  const [edit, setEdit] = useState(false)
  const [nm, setNm] = useState(pr.name)
  const [desc, setDesc] = useState(pr.description)
  const [ask, setAsk] = useState(false)
  const save = async () => {
    if (!nm.trim()) return
    try { const full = await api.getProject(pr.id); await api.putProject({ ...full, name: nm.trim(), description: desc.trim() }); setEdit(false); reload() } catch (e) { fail(e) }
  }
  const del = async () => { try { await api.deleteProject(pr.id); reload() } catch (e) { fail(e) } }
  const origin = pr.source_files.length ? t('proj.origin', { src: pr.source_files[0] }) : t('proj.origin.none')
  const stop = (e: { stopPropagation: () => void }) => e.stopPropagation()
  return (
    <div className="card proj" tabIndex={0} onClick={() => !edit && !ask && open()} onKeyDown={e => e.target === e.currentTarget && e.key === 'Enter' && open()}>
      {edit ? (
        <div className="col" onClick={stop}>
          <input type="text" value={nm} autoFocus aria-label={t('proj.name')} onChange={e => setNm(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') void save(); if (e.key === 'Escape') setEdit(false) }} />
          <textarea rows={2} value={desc} aria-label={t('proj.desc')} placeholder={t('proj.desc.ph')} onChange={e => setDesc(e.target.value)} style={{ fontFamily: 'var(--sans)' }} />
          <div className="row"><Button size="sm" variant="primary" onClick={save}>{t('proj.save')}</Button><Button size="sm" variant="ghost" onClick={() => { setEdit(false); setNm(pr.name); setDesc(pr.description) }}>{t('proj.staged.cancel')}</Button></div>
        </div>
      ) : (
        <>
          <div className="row"><h2 className="grow">{pr.name}</h2><span className="badge">{pr.target === 'curiosity' ? 'Curiosity' : 'Neo4j'}</span>
            <IconButton icon="pen" label={t('proj.rename')} onClick={e => { stop(e); setEdit(true) }} /></div>
          {pr.description ? <div className="muted">{pr.description}</div> : <button className="btn sm ghost" style={{ alignSelf: 'flex-start' }} onClick={e => { stop(e); setEdit(true) }}>{t('proj.desc.add')}</button>}
        </>
      )}
      <div className="stats"><span><b>{pr.stats.classes}</b> {t('proj.classes')}</span><span><b>{pr.stats.object_properties}</b> {t('proj.rels')}</span>
        <span><b>{pr.stats.datatype_properties}</b> {t('proj.props')}</span><span><b>{pr.stats.shapes}</b> {t('proj.shapes')}</span></div>
      <div className="muted"><Icon name="seedling" /> {origin}</div>
      <div className="muted">{t('proj.created', { date: date(pr.created_at) })} · {t('proj.updated', { date: date(pr.updated_at) })}</div>
      {ask ? (
        <div className="notice error" role="alert" onClick={stop}>
          <div><b>{t('proj.delete.ask', { name: pr.name })}</b>
            <div className="row" style={{ marginTop: 8 }}><Button size="sm" variant="danger" onClick={del}>{t('proj.delete.yes')}</Button><Button size="sm" variant="ghost" onClick={() => setAsk(false)}>{t('proj.staged.cancel')}</Button></div></div>
        </div>
      ) : <div className="row"><span className="grow" /><Button size="sm" variant="ghost" icon="trash" onClick={e => { stop(e); setAsk(true) }}>{t('proj.delete')}</Button></div>}
    </div>
  )
}
