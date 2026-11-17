import { useState } from 'react'
import { api, type ProjectSummary } from '../api'
import { BottomSheet, Button, Card, EmptyState, Icon, IconButton, Segmented } from '../kit'
import { useMobile } from '../shell/sidePref'
import { useI18n } from '../i18n'
import { ErrorView, Spin, useLoad, useToast } from '../ui'
import { useAuth } from '../auth/AuthGate'
import { aapi, type UploadedFile } from './assistant/aapi'
import { SchemaImport } from './import/SchemaImport'

const ASSISTANT_EXT = /\.(csv|tsv|sql|txt|md|markdown)$/i
const SCHEMA_EXT = /\.(sql|ddl|csv|tsv)$/i   // L48 : import déterministe ; les .json passent d'abord un essai (JSON Schema ou JSON-LD ?)
const DEFAULT_OPTS = { singularize: true, required_from_sample: false, dialect: 'auto', exclude: [] as string[], choices: {} as Record<string, string> }
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
  const auth = useAuth()
  const mob = useMobile()   // L44 : la liste d'abord ; la création passe dans une feuille du bas
  const [newOpen, setNewOpen] = useState(false)
  const [scope, setScope] = useState<'all' | 'mine' | 'shared'>('all')   // L42 : filtre de l'administrateur
  const [staged, setStaged] = useState<File[] | null>(null)
  const [schemaFiles, setSchemaFiles] = useState<File[] | null>(null)   // L48 : fichiers en cours d'aperçu d'import déterministe
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
    const fs = Array.from(files); const f = fs[0]; if (!f) return
    if (fs.every(x => SCHEMA_EXT.test(x.name))) { setStaged(fs); return }   // SQL / CSV : import déterministe, ou assistant s'il n'y a qu'un fichier
    if (fs.length === 1 && /\.json$/i.test(f.name)) {   // JSON Schema ? l'aperçu répond 422 si ce n'en est pas un : on retombe sur l'import d'ontologie (JSON-LD)
      setBusy(true); setErr(null)
      try { await api.schemaPreview([f], DEFAULT_OPTS); setSchemaFiles([f]); setBusy(false); return } catch { /* pas un JSON Schema */ }
      setBusy(false)
    }
    if (ASSISTANT_EXT.test(f.name)) { setStaged([f]); return }   // texte : on propose l'assistant
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
    if (!staged || staged.length !== 1) return
    setBusy(true); setErr(null)
    try {
      const up: UploadedFile = await aapi.upload(staged[0])
      const pr = await api.createProject({ name: staged[0].name.replace(/\.[^.]+$/, '') })
      try { sessionStorage.setItem(HANDOFF_KEY + pr.id, JSON.stringify(up)) } catch { /* stockage indisponible : le fichier se joint à la main */ }
      setStaged(null); open(pr.id, 'assistant')
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }

  const zone = schemaFiles ? (
    <SchemaImport files={schemaFiles} name={name.trim() || undefined} onCancel={() => setSchemaFiles(null)} onDone={id => { setSchemaFiles(null); open(id) }} />
  ) : staged ? (
    <Card tone="info" title={staged.length === 1 ? t('proj.staged.t', { name: staged[0].name }) : t('proj.staged.n', { n: staged.length })}>
      <p className="muted" style={{ margin: '0 0 10px' }}>{t('proj.staged.d2')}</p>
      <div className="row">
        <Button variant="primary" icon="list-check" disabled={busy} data-testid="staged-schema" onClick={() => { setSchemaFiles(staged); setStaged(null) }}>{t('proj.staged.schema')}</Button>
        {staged.length === 1 && ASSISTANT_EXT.test(staged[0].name) && <Button icon="wand-magic-sparkles" disabled={busy} data-testid="staged-assistant" onClick={withAssistant}>{t('proj.staged.go')}</Button>}
        <Button variant="ghost" disabled={busy} onClick={() => setStaged(null)}>{t('proj.staged.cancel')}</Button>
      </div>
    </Card>
  ) : (
    <div className={'drop' + (over ? ' over' : '')} onDragOver={e => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={e => { e.preventDefault(); setOver(false); void drop(e.dataTransfer.files) }}>
      <b>{t('proj.drop.title')}</b>
      <div>{t('proj.drop.body')}</div>
      <label className="btn" style={{ display: 'inline-block', marginTop: 8 }}>{t('proj.drop.pick')}
        <input type="file" hidden multiple onChange={e => { if (e.target.files) void drop(e.target.files); e.target.value = '' }} /></label>
    </div>
  )

  return (
    <div className="page">
      <div className="page-head"><h1>{t('proj.title')}</h1><span className="sub">{t('proj.sub')}</span>{mob && <><span className="grow" /><Button variant="primary" icon="plus" data-testid="new-project-btn" onClick={() => setNewOpen(true)}>{t('mob.proj.new')}</Button></>}</div>
      <ErrorView error={err} what={t('proj.op')} />
      {mob ? <BottomSheet open={newOpen} onClose={() => setNewOpen(false)} title={t('proj.new')} icon="plus" initial="full" snaps={['half', 'full']} testid="new-project-sheet"><div className="col">
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
        {zone}
      </div></BottomSheet> : <>
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
      {zone}
      </>}
      {list.loading && <Spin />}
      <ErrorView error={list.error} what={t('proj.list')} />
      {list.data && list.data.length === 0 && <EmptyState title={t('proj.none.t')} pose="accueil">{t('proj.none.d')}</EmptyState>}
      {auth.enabled && auth.admin && (list.data?.length ?? 0) > 0 && (
        <div className="row" data-testid="proj-scope"><Segmented label={t('proj.scope')} value={scope} onChange={setScope}
          items={[['mine', t('proj.scope.mine')], ['shared', t('proj.scope.shared')], ['all', t('proj.scope.all')]]} /></div>)}
      <div className="proj-grid">
        {list.data?.filter(pr => !(auth.enabled && auth.admin) || scope === 'all' || (scope === 'mine' ? pr.owner === auth.user : !!pr.owner && pr.owner !== auth.user && !pr.via_admin)).map(pr => <ProjectCard key={pr.id} pr={pr} date={date} open={() => open(pr.id)} reload={list.reload} fail={setErr} />)}
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
          <div className="row"><h2 className="grow">{pr.name}</h2>{pr.via_admin ? <span className="badge review" data-testid="proj-admin" title={t('proj.viaAdmin.hint')}>{t('proj.viaAdmin')}</span>
            : pr.shared && <span className="badge info" data-testid="proj-shared">{pr.role && pr.role !== 'owner' ? t('proj.role.' + pr.role) : t('proj.shared')}</span>}<span className="badge">{pr.target === 'curiosity' ? 'Curiosity' : 'Neo4j'}</span>
            <IconButton icon="pen" label={t('proj.rename')} onClick={e => { stop(e); setEdit(true) }} /></div>
          {pr.description ? <div className="muted">{pr.description}</div> : <button className="btn sm ghost" style={{ alignSelf: 'flex-start' }} onClick={e => { stop(e); setEdit(true) }}>{t('proj.desc.add')}</button>}
        </>
      )}
      <div className="stats"><span><b>{pr.stats.classes}</b> {t('proj.classes')}</span><span><b>{pr.stats.object_properties}</b> {t('proj.rels')}</span>
        <span><b>{pr.stats.datatype_properties}</b> {t('proj.props')}</span><span><b>{pr.stats.shapes}</b> {t('proj.shapes')}</span></div>
      {pr.owner && <div className="muted" data-testid="proj-owner"><Icon name="user" /> {t('proj.owner', { name: pr.owner })}</div>}
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
