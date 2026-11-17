import { useEffect, useMemo, useRef, useState } from 'react'
import { api, type Project, type SchemaOptions, type SchemaPreview } from '../../api'
import { Button, Icon, Segmented } from '../../kit'
import { useI18n } from '../../i18n'
import { ErrorView, Spin } from '../../ui'
import { useReadOnly } from '../../collab/readonly'
import './import.css'

const DEFAULTS: SchemaOptions = { singularize: true, required_from_sample: false, dialect: 'auto', exclude: [], choices: {} }
const KIND_ICON: Record<string, string> = { sql: 'database', csv: 'file-csv', 'json-schema': 'file-code' }
export const SCHEMA_EXT = /\.(sql|ddl|csv|tsv|json)$/i

/** Import déterministe (L48) : aperçu de ce qui sera créé, arbitrages, éléments ignorés, puis application.
 *  Sans `project` : crée le projet (nom donné) au moment d'appliquer. Aucun appel à un LLM, rien n'est écrit avant « Appliquer ». */
export function SchemaImport({ files, project, name, onDone, onCancel }: {
  files: File[]; project?: Project; name?: string; onDone: (id: string, p?: Project) => void; onCancel: () => void
}) {
  const { t } = useI18n()
  const ro = useReadOnly()   // l'écran du tableau de bord est « data-safe » : on désactive explicitement pour un lecteur
  const [opts, setOpts] = useState<SchemaOptions>(DEFAULTS)
  const [pv, setPv] = useState<SchemaPreview | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [applying, setApplying] = useState(false)
  const base = useRef<string | undefined>(undefined)
  const seq = useRef(0)

  useEffect(() => {
    const my = ++seq.current
    setBusy(true)
    const h = setTimeout(() => {
      api.schemaPreview(files, opts, base.current, project?.id)
        .then(r => { if (my === seq.current) { base.current = r.base_iri; setPv(r); setErr(null) } })
        .catch(e => { if (my === seq.current) setErr(e) })
        .finally(() => { if (my === seq.current) setBusy(false) })
    }, pv ? 250 : 0)
    return () => clearTimeout(h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files, opts, project?.id])

  const apply = async () => {
    if (!pv) return
    setApplying(true); setErr(null)
    try {
      let id = project?.id
      let created = false
      if (!id) { id = (await api.createProject({ name: (name || files[0]?.name.replace(/\.[^.]+$/, '') || t('proj.default')).slice(0, 120) })).id; created = true }
      try {
        const r = await api.schemaApply(id, files, opts, pv.base_iri, pv.digest)
        onDone(id, r.project)
      } catch (e) { if (created) await api.deleteProject(id).catch(() => {}); throw e }
    } catch (e) { setErr(e) } finally { setApplying(false) }
  }

  const set = (patch: Partial<SchemaOptions>) => setOpts(o => ({ ...o, ...patch }))
  const toggleClass = (n: string) => set({ exclude: opts.exclude.includes(n) ? opts.exclude.filter(x => x !== n) : [...opts.exclude, n] })
  const counts = useMemo(() => {
    const c = { warning: 0, review: 0, info: 0 }
    pv?.notices.forEach(n => { c[n.level]++ })
    return c
  }, [pv])
  const kinds = pv ? pv.kind : null

  return (
    <section className="card imp" aria-label={t('imp.title')} data-testid="schema-import">
      <div className="hd"><Icon name={KIND_ICON[kinds ?? 'sql']} /><b>{t('imp.title')}</b>
        <span className="muted imp-files">{files.map(f => f.name).join(', ')}</span><span className="grow" />
        {pv && <span className="badge info">{t('imp.kind.' + pv.kind)}{pv.dialect && pv.kind === 'sql' ? ' · ' + pv.dialect : ''}</span>}</div>
      <div className="bd col">
        <p className="muted" style={{ margin: 0 }}>{t('imp.intro')}</p>
        <ErrorView error={err} what={t('imp.op')} />
        {!pv && busy && <Spin />}
        {pv && <>
          <div className="imp-sum" data-testid="imp-summary" aria-live="polite">
            {(['classes', 'object_properties', 'datatype_properties', 'keys', 'enumerations', 'shapes'] as const).map(k =>
              <span key={k}><b>{pv.summary[k] ?? 0}</b> {t('imp.sum.' + k)}</span>)}
            <span className={'badge ' + (pv.conformance.profiles.DL ? 'auto' : 'lost')}>{pv.conformance.profiles.DL ? t('imp.dl.ok') : t('imp.dl.ko')}</span>
            {busy && <span className="muted">{t('imp.refresh')}</span>}
          </div>

          <div className="row imp-opts" data-testid="imp-options">
            {pv.kind !== 'json-schema' && <label className="chk"><input type="checkbox" checked={opts.singularize} onChange={e => set({ singularize: e.target.checked })} /> {t('imp.opt.singular')}</label>}
            {pv.kind === 'csv' && <label className="chk"><input type="checkbox" checked={opts.required_from_sample} onChange={e => set({ required_from_sample: e.target.checked })} /> {t('imp.opt.required')}</label>}
            {pv.kind === 'sql' && <label className="f inl">{t('imp.opt.dialect')}
              <select value={opts.dialect} onChange={e => set({ dialect: e.target.value })} data-testid="imp-dialect">
                {['auto', 'postgresql', 'mysql', 'sqlserver', 'generic'].map(d => <option key={d} value={d}>{t('imp.dialect.' + d)}</option>)}</select></label>}
          </div>

          {pv.decisions.length > 0 && <div className="imp-dec" data-testid="imp-decisions">
            <h3>{t('imp.dec.title', { n: pv.decisions.length })}</h3>
            {pv.decisions.map(d => (
              <div key={d.id} className="imp-dec-row">
                <span>{d.message}</span>
                <Segmented label={d.subject} value={d.chosen} onChange={v => set({ choices: { ...opts.choices, [d.id]: v } })}
                  items={d.options.map(o => [o, t('imp.choice.' + o)] as [string, string])} />
              </div>))}
          </div>}

          <div className="imp-classes" data-testid="imp-classes">
            <h3>{t('imp.classes.title', { n: pv.classes.length })}</h3>
            {pv.classes.map(c => (
              <details key={c.iri} className={'imp-class' + (opts.exclude.includes(c.key) ? ' off' : '')}>
                <summary>
                  <input type="checkbox" aria-label={t('imp.include', { name: c.name })} checked={!opts.exclude.includes(c.key)} onClick={e => e.stopPropagation()} onChange={() => toggleClass(c.key)} />
                  <b>{c.name}</b>
                  {c.kind !== 'class' && <span className="badge review">{t('imp.kind.' + c.kind)}</span>}
                  {pv.conflicts.includes(c.name) && <span className="badge warning">{t('imp.exists')}</span>}
                  {c.parents.length > 0 && <span className="muted">⊂ {c.parents.join(', ')}</span>}
                  <span className="muted grow">{t('imp.counts', { p: c.props.length, r: c.rels.length })}</span>
                  <span className="muted imp-src">{c.source}</span>
                </summary>
                <div className="imp-body">
                  {c.keys.length > 0 && <div><Icon name="key" /> {c.keys.map(k => k.join(' + ')).join(' ; ')}{c.assumed_key && <span className="badge review">{t('imp.assumed')}</span>}</div>}
                  <ul>
                    {c.rels.map(r => <li key={r.name}><Icon name="arrow-right" /> <code>{r.name}</code> → {r.target}{r.many ? ' (0..n)' : r.required ? ' (1)' : ' (0..1)'}</li>)}
                    {c.props.map(p => <li key={p.name}><code>{p.name}</code> <span className="muted">{p.type}{p.many ? '[]' : ''}</span>
                      {p.required && <span className="badge auto">{t('imp.required')}</span>}
                      {p.enum && <span className="badge info" title={p.enum.join(', ')}>{t('imp.enum', { n: p.enum.length })}</span>}
                      {p.degraded && <span className="badge warning" title={t('imp.degraded', { t: p.degraded })}>{p.degraded}</span>}</li>)}
                  </ul>
                </div>
              </details>))}
          </div>

          {pv.notices.length > 0 && <details className="imp-notices" open={counts.warning + counts.review > 0} data-testid="imp-notices">
            <summary><b>{t('imp.notices.title')}</b> {counts.warning > 0 && <span className="badge warning">{t('imp.n.warning', { n: counts.warning })}</span>} {counts.review > 0 && <span className="badge review">{t('imp.n.review', { n: counts.review })}</span>} {counts.info > 0 && <span className="badge info">{t('imp.n.info', { n: counts.info })}</span>}</summary>
            <ul>{[...pv.notices].sort((a, b) => ['warning', 'review', 'info'].indexOf(a.level) - ['warning', 'review', 'info'].indexOf(b.level)).map((n, i) =>
              <li key={i}><span className={'badge ' + n.level}>{t('imp.lvl.' + n.level)}</span> {n.message}</li>)}</ul>
          </details>}

          <details className="imp-ignored" open={pv.ignored.length > 0} data-testid="imp-ignored">
            <summary><b>{t('imp.ignored.title')}</b> <span className="muted">{pv.ignored.length ? t('imp.ignored.n', { n: pv.ignored.reduce((s, x) => s + x.count, 0) }) : t('imp.ignored.none')}</span></summary>
            <ul>{pv.ignored.map(x => <li key={x.category}><b>{x.message}</b> <span className="badge">{x.count}</span>
              {x.examples.length > 0 && <span className="muted"> — {x.examples.join(' ; ')}</span>}</li>)}</ul>
            {pv.ignored.length > 0 && <p className="muted">{t('imp.ignored.hint')}</p>}
          </details>

          {pv.conflicts.length > 0 && <div className="notice warn" role="status"><Icon name="triangle-exclamation" /><span>{t('imp.conflicts', { n: pv.conflicts.length })}</span></div>}
        </>}
        <div className="row">
          <Button variant="primary" icon="check" data-write data-testid="imp-apply" title={ro ? t('collab.ro.hint') : undefined} disabled={ro || !pv || busy || applying || (pv.classes.length - opts.exclude.length) <= 0} onClick={apply}>{project ? t('imp.apply') : t('imp.apply.new')}</Button>
          <Button variant="ghost" disabled={applying} onClick={onCancel} data-testid="imp-cancel">{t('proj.staged.cancel')}</Button>
          <span className="muted">{t('imp.undo')}</span>
        </div>
      </div>
    </section>
  )
}
