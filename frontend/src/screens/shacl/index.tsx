import { useEffect, useMemo, useState } from 'react'
import { api, curie, type NodeShape, type ShapesModel, type ShaclReport, type ShaclResult } from '../../api'
import type { ScreenProps } from '../../shell/types'
import { CodeEditor, ErrorView, download } from '../../ui'
import { Button, EmptyState, Icon, Tabs, useToast } from '../../kit'
import { useI18n } from '../../i18n'
import { KrakieStatus, useResultFlash } from '../../krakie/Krakie'
import { openAssistant, useAssistantContext } from '../../lib/assistantContext'
import { eapi } from '../editor/types'
import { ShapeList } from './ShapeList'
import { ShapeDetail } from './ShapeDetail'
import { Validation } from './Validation'
import { diffGenerated, otherChips, pathLabel, pathStr, shapeTitle, type GenDiff, type ShapeCheck } from './helpers'
import './shacl.css'

type Tab = 'shapes' | 'ttl' | 'valid'
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x))

export function Shacl({ p, setP, initialTab = 'shapes' }: ScreenProps & { initialTab?: Tab }) {
  const { t, lang } = useI18n()
  const toast = useToast()
  const [tab, setTab] = useState<Tab>(initialTab)
  useEffect(() => setTab(initialTab), [initialTab])
  const [err, setErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState<ShapesModel>(() => clone(p.shapes))
  const [sel, setSel] = useState<string | null>(null)
  const [rep, setRep] = useState<ShaclReport | null>(null)
  const [fileName, setFileName] = useState('')
  const [ttl, setTtl] = useState('')
  const [diff, setDiff] = useState<{ d: GenDiff; notes: string[] } | null>(null)
  const [icons, setIcons] = useState<Record<string, string>>(() => ({ ...((p as any).view?.icons ?? {}) }))
  const [hl, setHl] = useState<Set<string>>(new Set())
  useEffect(() => { setDraft(clone(p.shapes)) }, [p.shapes])
  useEffect(() => { setRep(null); setFileName(''); setDiff(null); setSel(null) }, [p.id])
  useEffect(() => {
    eapi.graph(p.id, '', lang).then(g => setIcons(i => { const o = { ...i }; for (const n of g.nodes) if (n.icon && !o[n.id]) o[n.id] = n.icon; return o })).catch(() => {})
  }, [p.id, lang])

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(p.shapes), [draft, p.shapes])
  const shapes = useMemo(() => Object.values(draft.shapes), [draft])
  useEffect(() => { if (!sel || !draft.shapes[sel]) setSel(shapes[0]?.id ?? null) }, [shapes, sel, draft.shapes])
  const shape = sel ? draft.shapes[sel] : null
  const pf = { ...draft.prefixes, ...p.onto.meta.prefixes }

  const check = useMemo<ShapeCheck | null>(() => {
    if (!rep) return null
    const byShape: Record<string, ShaclResult[]> = {}
    for (const r of rep.results) if (r.shape) (byShape[r.shape] ??= []).push(r)
    return { n: rep.results.length, byShape }
  }, [rep])

  const sTitle = shape ? shapeTitle(shape, p.onto, lang).title : ''
  useAssistantContext({
    screen: tab === 'valid' ? 'shacl' : 'shapes', projectId: p.id,
    selection: shape ? { kind: 'shape', id: shape.id, label: sTitle } : null,
    extra: { tab, shapes: shapes.length, dirty, violations: rep?.results.length ?? null },
    suggestions: shape ? [t('sh.k.add', { v: sTitle }), t('sh.k.explain', { v: sTitle }), ...(rep && !rep.conforms ? [t('sh.k.whyAny')] : [])] : [t('sh.k.gen')],
  }, [tab, shapes.length, dirty, rep])

  const [genning, setGenning] = useState(false)
  const genDone = useResultFlash(genning, !!diff)
  const run = async (f: () => Promise<void>) => { setErr(null); setBusy(true); try { await f() } catch (e) { setErr(e) } finally { setBusy(false) } }
  const ask = (prompt: string, extra?: Record<string, unknown>) => openAssistant({ prompt, send: true, context: { screen: tab === 'valid' ? 'shacl' : 'shapes', projectId: p.id, selection: shape ? { kind: 'shape', id: shape.id, label: sTitle } : null, extra } })
  const upd = (fn: (s: NodeShape) => void) => { if (!sel) return; setDraft(d => { const n = clone(d); fn(n.shapes[sel]); return n }) }
  const save = () => run(async () => { const np = await api.putShapes(p.id, draft); setP(np); toast(t('sh.saved')) })
  const gen = () => run(async () => {
    // Aperçu (dry_run) : le serveur ne modifie pas le projet ; rien n'est appliqué avant confirmation.
    setGenning(true)
    try {
      const r = await api.shaclGenerateDry(p.id)
      setDiff({ d: diffGenerated(draft, r.generated), notes: r.notes })
    } finally { setGenning(false) }
  })
  const applyGen = () => { if (!diff) return; setDraft(diff.d.merged); setDiff(null); toast(t('sh.gen.staged')) }
  const imp = (f: File) => run(async () => { const r = await api.importFile(p.id, f, 'shapes'); setP(r.project); toast(t('sh.imported')) })
  const validate = (f: File) => run(async () => { setFileName(f.name); setRep(await api.shaclValidate(p.id, f)) })
  const showTtl = () => run(async () => { setTtl(await api.exportShapes(p.id)); setTab('ttl') })
  const openShape = (id: string, propId?: string) => { setSel(id); setTab('shapes'); setHl(new Set(propId ? [propId] : [])); if (propId) setTimeout(() => document.getElementById('ps-' + propId)?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 60) }

  const empty = shapes.length === 0 && Object.keys(draft.property_shapes).length === 0
  const nAdd = diff ? diff.d.newShapes.length + diff.d.extra.reduce((a, e) => a + e.props.length, 0) : 0

  return (
    <div className="page shacl">
      <div className="page-head">
        <h1>{tab === 'valid' ? t('sh.title.valid') : t('sh.title')}</h1>
        <span className="sub">{t('sh.sub')}</span><span className="grow" />
        <Button icon="wand-magic-sparkles" variant="primary" disabled={busy} onClick={gen}>{t('sh.gen')}</Button>
        <label className="btn"><Icon name="file-import" />{t('sh.import')}<input type="file" hidden onChange={e => { const f = e.target.files?.[0]; if (f) imp(f); e.target.value = '' }} /></label>
        <Button icon="file-code" onClick={showTtl}>{t('sh.ttl')}</Button>
      </div>
      <ErrorView error={err} what="SHACL" />
      {diff && (
        <section className="shdiff" role="dialog" aria-label={t('sh.diff.title')}>
          <header><Icon name="code-compare" /><h2>{t('sh.diff.title')}</h2><span className="grow" />
            <Button onClick={() => setDiff(null)}>{t('sh.cancel')}</Button>
            <Button variant="primary" icon="check" disabled={nAdd === 0} onClick={applyGen}>{t('sh.diff.apply', { n: nAdd })}</Button></header>
          {nAdd === 0 ? <p className="muted">{t('sh.diff.none')}</p> : (
            <div className="shdiff-body">
              {diff.d.newShapes.map(s => (
                <div className="dgrp" key={s.id}><h3><span className="plus">+</span>{t('sh.diff.newshape', { v: shapeTitle(s, p.onto, lang).title })}<span className="muted">{t('sh.list.count', { n: s.properties.length })}</span></h3>
                  <ul>{s.properties.map(ps => <li key={ps.id}><span className="plus">+</span><b>{pathLabel(ps.path, p.onto, lang)}</b><span className="mono muted">{pathStr(ps.path, pf)}</span><span className="muted">{[ps.min_count ? t('sh.diff.req') : '', ps.datatype ? curie(ps.datatype, pf) : ps.class?.length ? curie(ps.class[0], pf) : '', ...otherChips(ps, pf, p.onto, lang, t).map(c => c.text)].filter(Boolean).join(' · ')}</span></li>)}</ul></div>))}
              {diff.d.extra.map(e => (
                <div className="dgrp" key={e.shape.id}><h3><span className="plus">+</span>{t('sh.diff.onshape', { v: shapeTitle(e.shape, p.onto, lang).title })}</h3>
                  <ul>{e.props.map(ps => <li key={ps.id}><span className="plus">+</span><b>{pathLabel(ps.path, p.onto, lang)}</b><span className="mono muted">{pathStr(ps.path, pf)}</span></li>)}</ul></div>))}
            </div>)}
          {diff.d.skipped > 0 && <p className="muted">{t('sh.diff.skipped', { n: diff.d.skipped })}</p>}
          {diff.notes.length > 0 && <details className="shdiff-notes"><summary>{t('sh.diff.notes', { n: diff.notes.length })}</summary><ul>{diff.notes.map((n, i) => <li key={i}>{n}</li>)}</ul></details>}
        </section>
      )}
      <KrakieStatus busy={genning} done={genDone} label={t('krakie.forge.shapes')} doneLabel={t('krakie.done.shapes')} />
      <Tabs value={tab} onChange={setTab} items={[['shapes', t('sh.tab.shapes', { n: shapes.length })], ['valid', t('sh.tab.valid') + (rep ? (rep.conforms ? ' ✓' : ` (${rep.results.length})`) : '')], ['ttl', t('sh.tab.ttl')]]} />
      {tab === 'shapes' && (empty
        ? <EmptyState title={t('sh.empty.t')} pose="accueil" action={<><Button variant="primary" icon="wand-magic-sparkles" onClick={gen}>{t('sh.gen')}</Button><Button icon="comment-dots" onClick={() => openAssistant({ prompt: t('sh.k.gen'), send: true, context: { screen: 'shapes', projectId: p.id } })}>{t('sh.empty.krakie')}</Button></>}>{t('sh.empty.d')}</EmptyState>
        : <div className="shsplit" data-tour="shapes-split">
          <ShapeList p={{ ...p, shapes: draft }} shapes={shapes} icons={icons} selected={sel} onSelect={id => { setSel(id); setHl(new Set()) }} check={check} />
          <div className="shmain">
            {dirty && <div className="shsave" role="status"><Icon name="pen" /><span>{t('sh.dirty')}</span><span className="grow" /><Button size="sm" onClick={() => setDraft(clone(p.shapes))}>{t('sh.revert')}</Button><Button size="sm" variant="primary" icon="floppy-disk" disabled={busy} onClick={save}>{t('sh.save')}</Button></div>}
            {shape && <ShapeDetail p={{ ...p, shapes: draft }} shape={shape} icons={icons} upd={upd} onAskKrakie={ask} highlight={hl} />}
            {draft.warnings.length > 0 && <div className="notice warn"><div>{draft.warnings.map((w, i) => <div key={i}>{w}</div>)}</div></div>}
          </div>
        </div>)}
      {tab === 'valid' && <Validation p={{ ...p, shapes: draft }} rep={rep} fileName={fileName} busy={busy} onFile={validate} onOpenShape={openShape}
        onAsk={(r, sid) => openAssistant({ prompt: t('sh.k.whyOne', { node: curie(r.focus, pf), path: r.path ? curie(r.path, pf) : '', msg: r.message }), send: true, context: { screen: 'shacl', projectId: p.id, selection: sid ? { kind: 'shape', id: sid, label: shapeTitle(draft.shapes[sid], p.onto, lang).title } : null, extra: { violation: r } } })} />}
      {tab === 'ttl' && (ttl ? <><div className="row"><Button icon="download" onClick={() => download('shapes.ttl', ttl)}>{t('sh.download')}</Button></div><div className="pane" style={{ height: 480 }}><CodeEditor value={ttl} readOnly filename="shapes.ttl" /></div></>
        : <EmptyState title={t('sh.ttl.t')} pose="accueil" action={<Button icon="file-code" onClick={showTtl}>{t('sh.ttl')}</Button>}>{t('sh.ttl.d')}</EmptyState>)}
    </div>
  )
}
