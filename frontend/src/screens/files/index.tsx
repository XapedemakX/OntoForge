import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Project } from '../../api'
import { Button, Icon, IconButton, useToast } from '../../kit'
import { useI18n } from '../../i18n'
import type { ScreenProps } from '../../shell/types'
import { openAssistant, useAssistantContext } from '../../lib/assistantContext'
import { CodeHost, type CodeHostApi } from './CodeHost'
import { DiffView } from './DiffView'
import { fapi, type ApplyResult, type Diag, type DiffResult, type FileEntry, type FileTree, type SourceNote } from './fapi'
import './files.css'

interface Buf { saved: string; content: string; etag: string; rev: number; language: string; editable: boolean; generated: boolean; source?: SourceNote | null }
type Modal =
  | { kind: 'diff'; path: string; diff: DiffResult }
  | { kind: 'conflict'; path: string; currentEtag: string; currentContent: string; content: string }
  | null

const DEBOUNCE_MS = 500
const FILE_ICON: Record<string, string> = { turtle: 'diagram-project', json: 'code', csharp: 'hashtag', cypher: 'circle-nodes', graphql: 'share-nodes', markdown: 'file-lines', text: 'file' }

function useNarrow() {
  const q = '(max-width: 900px)'
  const [m, setM] = useState(() => typeof matchMedia !== 'undefined' && matchMedia(q).matches)
  useEffect(() => { const mq = matchMedia(q); const f = () => setM(mq.matches); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f) }, [])
  return m
}

export function Files({ p, setP }: ScreenProps) {
  const { t, lang } = useI18n()
  const toast = useToast()
  const narrow = useNarrow()
  const [tree, setTree] = useState<FileTree | null>(null)
  const [treeErr, setTreeErr] = useState('')
  const [tabs, setTabs] = useState<string[]>([])
  const [active, setActive] = useState('')
  const [bufs, setBufs] = useState<Record<string, Buf>>({})
  const [diags, setDiags] = useState<Record<string, Diag[]>>({})
  const [validating, setValidating] = useState(false)
  const [validated, setValidated] = useState<Record<string, boolean>>({})
  const [cursor, setCursor] = useState({ line: 1, col: 1, sel: '' })
  const [problemsOpen, setProblemsOpen] = useState(true)
  const [modal, setModal] = useState<Modal>(null)
  const [busy, setBusy] = useState(false)
  const [applied, setApplied] = useState<{ path: string; added: number; removed: number; unit: string; rewritten: number } | null>(null)
  const [askOpen, setAskOpen] = useState(false)
  const host = useRef<CodeHostApi>(null)
  const seq = useRef(0)
  const projRef = useRef<Project>(p); projRef.current = p
  const bufsRef = useRef(bufs); bufsRef.current = bufs

  const buf = bufs[active]
  const dirty = (path: string) => { const b = bufs[path]; return !!b && b.content !== b.saved }
  const anyDirty = Object.keys(bufs).some(dirty)
  const ds = useMemo(() => diags[active] ?? [], [diags, active])
  const errors = ds.filter(d => d.severity === 'error').length
  const warns = ds.filter(d => d.severity !== 'error').length
  const readOnly = !buf || !buf.editable || narrow

  // ---- arbre ----
  const loadTree = useCallback(async () => {
    const r = await fapi.tree(p.id)
    if (r.ok) { setTree(r.data); setTreeErr('') } else setTreeErr(r.data.detail ?? t('common.error'))
  }, [p.id, t])
  useEffect(() => { void loadTree() }, [loadTree])

  // ---- ouverture d'un fichier ----
  const open = useCallback(async (path: string) => {
    setTabs(x => (x.includes(path) ? x : [...x, path]))
    setActive(path)
    if (bufsRef.current[path]) return
    const r = await fapi.read(p.id, path)
    if (!r.ok) { toast(r.data.detail ?? t('common.error')); setTabs(x => x.filter(y => y !== path)); return }
    const d = r.data
    setBufs(b => ({ ...b, [path]: { saved: d.content, content: d.content, etag: d.etag, rev: 1, language: d.language, editable: d.editable, generated: d.generated, source: d.source } }))
  }, [p.id, toast, t])
  useEffect(() => { void open('onto.ttl') }, [p.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const close = (path: string) => {
    if (dirty(path) && !confirm(t('fx.closeDirty', { f: path }))) return
    setTabs(x => { const n = x.filter(y => y !== path); if (active === path) setActive(n[n.length - 1] ?? ''); return n })
    setBufs(b => { const n = { ...b }; delete n[path]; return n })
    setDiags(d => { const n = { ...d }; delete n[path]; return n })
  }

  // ---- validation en direct (anti-rebond 500 ms) ----
  const validateNow = useCallback(async (path: string, content: string): Promise<Diag[]> => {
    const n = ++seq.current
    setValidating(true)
    const r = await fapi.validate(p.id, path, content)
    if (n === seq.current) setValidating(false)
    const list = r.ok ? r.data.diagnostics : []
    setDiags(d => ({ ...d, [path]: list })); setValidated(v => ({ ...v, [path]: r.ok }))
    return list
  }, [p.id])
  const content = buf?.content
  const rev = buf?.rev
  useEffect(() => {
    if (!active || content === undefined || !buf?.editable) return
    const h = setTimeout(() => { void validateNow(active, content) }, rev === 1 && validated[active] === undefined ? 0 : DEBOUNCE_MS)
    return () => clearTimeout(h)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, content, rev, buf?.editable, validateNow])

  useEffect(() => { const f = (e: BeforeUnloadEvent) => { if (anyDirty) e.preventDefault() }; addEventListener('beforeunload', f); return () => removeEventListener('beforeunload', f) }, [anyDirty])

  // ---- rafraîchit les onglets propres depuis le serveur (après application, annulation, conflit) ----
  const reloadClean = useCallback(async (except?: string) => {
    for (const [path, b] of Object.entries(bufsRef.current)) {
      if (path === except || b.content !== b.saved) continue
      const r = await fapi.read(p.id, path)
      if (r.ok) setBufs(x => (x[path] ? { ...x, [path]: { ...x[path], saved: r.data.content, content: r.data.content, etag: r.data.etag, source: r.data.source, rev: x[path].rev + 1 } } : x))
    }
    void loadTree()
  }, [p.id, loadTree])

  // ---- appliquer ----
  const apply = useCallback(async () => {
    const b = bufsRef.current[active]
    if (!b || !b.editable || busy || narrow) return
    if (b.content === b.saved) { toast(t('fx.nothing')); return }
    setBusy(true)
    try {
      const list = await validateNow(active, b.content)
      if (list.some(d => d.severity === 'error')) { setProblemsOpen(true); toast(t('fx.blocked')); return }
      const r = await fapi.diff(p.id, active, b.content)
      if (!r.ok) { if (r.data.diagnostics) setDiags(d => ({ ...d, [active]: r.data.diagnostics! })); setProblemsOpen(true); toast(r.data.detail ?? t('common.error')); return }
      setModal({ kind: 'diff', path: active, diff: r.data })
    } finally { setBusy(false) }
  }, [active, busy, narrow, validateNow, p.id, toast, t])

  const confirmApply = async (path: string, force = false) => {
    const b = bufsRef.current[path]; if (!b) return
    setBusy(true)
    try {
      const r = await fapi.apply(p.id, path, b.content, b.etag, force)
      if (r.status === 409) { setModal({ kind: 'conflict', path, currentEtag: r.data.current_etag ?? '', currentContent: r.data.current_content ?? '', content: b.content }); return }
      if (!r.ok) { if (r.data.diagnostics) setDiags(d => ({ ...d, [path]: r.data.diagnostics! })); setModal(null); setProblemsOpen(true); toast(r.data.detail ?? t('common.error')); return }
      const d = r.data as ApplyResult
      setModal(null)
      setP(d.project)
      setBufs(x => ({ ...x, [path]: { ...x[path], saved: d.content, content: d.content, etag: d.etag, source: d.source, rev: x[path].rev + 1 } }))
      setDiags(x => ({ ...x, [path]: d.diagnostics }))
      setApplied({ path, added: d.summary.added, removed: d.summary.removed, unit: d.summary.unit, rewritten: d.summary.rewritten?.count ?? 0 })
      void reloadClean(path)
    } finally { setBusy(false) }
  }

  const undo = async () => {
    setBusy(true)
    try {
      const r = await fapi.undo(p.id)
      if (!r.ok) { toast(r.data.detail ?? t('common.error')); return }
      setP(r.data.project); setApplied(null); toast(t('fx.undone'))
      // l'annulation remplace aussi les onglets modifiés : on les recharge tous (le travail non appliqué reste sauvegardé dans l'éditeur tant qu'il n'est pas écrasé)
      await reloadClean()
    } finally { setBusy(false) }
  }

  // ---- conflit : recharger la version du projet ----
  const takeServer = async (path: string) => {
    const r = await fapi.read(p.id, path); setModal(null)
    if (r.ok) setBufs(x => ({ ...x, [path]: { ...x[path], saved: r.data.content, content: r.data.content, etag: r.data.etag, source: r.data.source, rev: x[path].rev + 1 } }))
    const pr = await fapi.getProject(p.id); if (pr.ok) setP(pr.data)
  }

  // ---- Krakie ----
  const sel = cursor.sel
  useAssistantContext({
    screen: 'files', projectId: p.id, target: p.target,
    selection: active ? { kind: 'file', id: active, label: active } : null,
    extra: { file: active, language: buf?.language, line: cursor.line, col: cursor.col, selection: sel.slice(0, 1500), errors: ds.filter(d => d.severity === 'error').slice(0, 5).map(d => ({ line: d.line, message: d.message })) },
  }, [active, sel.length, cursor.line, ds.length])
  const ask = (kind: 'explain' | 'fix') => {
    setAskOpen(false)
    const lines = (buf?.content ?? '').split('\n')
    const near = [...ds].filter(d => d.severity === 'error').sort((a, b) => Math.abs(a.line - cursor.line) - Math.abs(b.line - cursor.line))[0]
    const snippet = sel || lines[cursor.line - 1] || ''
    const prompt = kind === 'explain'
      ? t('fx.ask.explainPrompt', { f: active, snippet: snippet.slice(0, 1500) })
      : t('fx.ask.fixPrompt', { f: active, line: near?.line ?? cursor.line, msg: near?.message ?? t('fx.ask.noErr'), snippet: (near ? lines[near.line - 1] ?? '' : snippet).slice(0, 600) })
    openAssistant({ prompt, send: true, context: { screen: 'files', projectId: p.id, selection: { kind: 'file', id: active, label: active }, extra: { file: active, line: cursor.line, selection: sel.slice(0, 1500) } } })
  }

  const model = useMemo(() => ({ onto: p.onto, lang }), [p.onto, lang])
  const modelRef = useRef(model); modelRef.current = model
  const getModel = useCallback(() => modelRef.current, [])
  const onChange = useCallback((path: string, doc: string) => setBufs(b => (b[path] && b[path].content !== doc ? { ...b, [path]: { ...b[path], content: doc } } : b)), [])
  const onSave = useCallback(() => { void apply() }, [apply])
  const saveRef = useRef(onSave); saveRef.current = onSave

  const editable = (tree?.files ?? []).filter(f => !f.generated)
  const generated = (tree?.files ?? []).filter(f => f.generated)
  const sevIcon = (s: Diag['severity']) => (s === 'error' ? 'circle-xmark' : s === 'warning' ? 'triangle-exclamation' : 'circle-info')
  const status = !buf?.editable ? '' : validating || validated[active] === undefined ? 'checking' : errors ? 'errors' : warns ? 'warnings' : 'ok'
  const treeBtn = (f: FileEntry) => (
    <button key={f.path} type="button" className={'fx-file' + (active === f.path ? ' on' : '')} aria-current={active === f.path ? 'true' : undefined} onClick={() => void open(f.path)} title={f.path}>
      <Icon name={FILE_ICON[f.language] ?? 'file'} /><span className="nm">{f.name}</span>
      {f.generated && <Icon name="lock" className="lk" />}{dirty(f.path) && <span className="dot" aria-label={t('fx.modified')} />}
    </button>)

  return (
    <div className="fx" data-tour="files">
      <aside className="fx-tree" aria-label={t('fx.tree')}>
        <div className="fx-h">{t('fx.project')}</div>
        {editable.map(treeBtn)}
        <div className="fx-h">{t('fx.generated', { target: tree?.target === 'neo4j' ? 'Neo4j' : 'Curiosity' })}</div>
        {generated.length ? generated.map(treeBtn) : <div className="fx-empty muted">{tree ? t('fx.noGenerated') : '…'}</div>}
        {treeErr && <div className="fx-empty err">{treeErr}</div>}
      </aside>

      <section className="fx-main">
        <div className="fx-bar">
          <div className="fx-tabs" role="tablist" aria-label={t('fx.tabs')}>
            {tabs.map(path => (
              <div key={path} className={'fx-tab' + (active === path ? ' on' : '')} role="presentation">
                <button type="button" role="tab" aria-selected={active === path} onClick={() => setActive(path)}>
                  {bufs[path]?.generated && <Icon name="lock" />}{path.replace(/^generated\//, '')}{dirty(path) && <span className="dot" aria-label={t('fx.modified')} />}
                </button>
                <button type="button" className="x" aria-label={t('fx.closeTab', { f: path })} onClick={() => close(path)}><Icon name="xmark" /></button>
              </div>))}
          </div>
          <div className="fx-actions">
            <div className="fx-ask">
              <Button size="sm" icon="wand-magic-sparkles" aria-haspopup="menu" aria-expanded={askOpen} disabled={!active} onClick={() => setAskOpen(o => !o)}>{t('fx.ask')}</Button>
              {askOpen && <div className="fx-menu" role="menu">
                <button type="button" role="menuitem" onClick={() => ask('explain')}>{t('fx.ask.explain')}</button>
                <button type="button" role="menuitem" onClick={() => ask('fix')} disabled={!errors && !warns}>{t('fx.ask.fix')}</button>
              </div>}
            </div>
            {!narrow && buf?.editable && <>
              <Button size="sm" variant="primary" icon="check" disabled={busy || !dirty(active)} onClick={() => void apply()} title="Ctrl+S">{t('fx.apply')}</Button>
              <IconButton icon="rotate-left" label={t('fx.revert')} disabled={busy} onClick={() => void undo()} />
            </>}
          </div>
        </div>

        {narrow && <div className="notice soon">{t('fx.mobile')}</div>}
        {buf?.generated && <div className="fx-banner gen" role="note"><Icon name="lock" />{t('fx.genBanner')}</div>}
        {buf?.source?.state === 'canonical' && <div className="fx-banner" role="note" data-testid="fx-canon-note"><Icon name="circle-info" />{buf.source.comment_lines > 0 ? t('fx.note.canonicalN', { n: buf.source.comment_lines }) : t('fx.note.canonical0')}</div>}
        {applied && <div className="fx-banner ok" role="status" data-testid="fx-applied">
          <Icon name="circle-check" /><span>{applied.unit !== 'triples' ? t('fx.appliedDec', { a: applied.added, r: applied.removed }) : applied.added + applied.removed === 0 ? t('fx.appliedText') : t('fx.applied', { a: applied.added, r: applied.removed })}</span>
          <Button size="sm" icon="rotate-left" disabled={busy} onClick={() => void undo()}>{t('fx.revert')}</Button>
          <IconButton icon="xmark" label={t('common.close')} onClick={() => setApplied(null)} />
        </div>}

        <div className="fx-edit">
          {buf ? <CodeHost ref={host} path={active} language={buf.language} readOnly={readOnly} initial={buf.content} rev={buf.rev} lang={lang}
            diagnostics={ds} getModel={getModel} onChange={onChange} onSave={() => saveRef.current()} onCursor={(line, col, s) => setCursor({ line, col, sel: s })} />
            : <div className="fx-none muted">{t('fx.pick')}</div>}
        </div>

        <div className={'fx-problems' + (problemsOpen ? ' open' : '')} data-testid="fx-problems">
          <button type="button" className="fx-ph" aria-expanded={problemsOpen} onClick={() => setProblemsOpen(o => !o)}>
            <Icon name={problemsOpen ? 'chevron-down' : 'chevron-right'} />{t('fx.problems')}
            <span className="cnt err" title={t('fx.errors')}><Icon name="circle-xmark" />{errors}</span>
            <span className="cnt warn" title={t('fx.warnings')}><Icon name="triangle-exclamation" />{warns}</span>
          </button>
          {problemsOpen && <ul className="fx-plist">
            {!ds.length && <li className="muted empty">{buf?.editable ? (status === 'checking' ? t('fx.checking') : t('fx.noProblems')) : t('fx.noValidation')}</li>}
            {ds.map((d, i) => (
              <li key={i}><button type="button" onClick={() => host.current?.goto(d.line, d.col)} className={'sv-' + d.severity}>
                <Icon name={sevIcon(d.severity)} /><span className="msg">{d.message}</span><span className="code">{d.code}</span><span className="pos">{d.line}:{d.col}</span>
              </button></li>))}
          </ul>}
        </div>

        <footer className="fx-status" role="status">
          <span data-testid="fx-pos">{t('fx.pos', { l: cursor.line, c: cursor.col })}</span>
          {sel && <span>{t('fx.selChars', { n: sel.length })}</span>}
          <span>{buf ? t('fx.fmt.' + buf.language) : ''}</span>
          {status && <span className={'st ' + status} data-testid="fx-valid"><Icon name={status === 'ok' ? 'circle-check' : status === 'checking' ? 'spinner' : status === 'errors' ? 'circle-xmark' : 'triangle-exclamation'} />{t('fx.st.' + status, { e: errors, w: warns })}</span>}
          {buf && !buf.editable && <span><Icon name="lock" />{t('fx.readonly')}</span>}
          <span className="grow" />
          <span className="muted">{t('fx.hint')}</span>
        </footer>
      </section>

      {modal?.kind === 'diff' && (
        <div className="fx-modal" role="dialog" aria-modal="true" aria-label={t('fx.diff.title')} onKeyDown={e => { if (e.key === 'Escape') setModal(null) }}>
          <div className="box">
            <h2>{t('fx.diff.title')} — {modal.path}</h2>
            {modal.diff.changed ? <>
              <p className="sum" data-testid="fx-summary">
                {modal.diff.summary.unit === 'triples'
                  ? t('fx.diff.triples', { a: modal.diff.summary.added, r: modal.diff.summary.removed })
                  : t('fx.diff.decisions', { a: modal.diff.summary.added, r: modal.diff.summary.removed, c: modal.diff.summary.changed ?? 0 })}
              </p>
              {modal.diff.summary.unit === 'triples' && modal.diff.summary.added + modal.diff.summary.removed === 0 && <p className="muted small" data-testid="fx-textonly">{t('fx.diff.textOnly')}</p>}
              {(modal.diff.summary.comments_lost ?? 0) > 0 && <div className="fx-banner warn" role="alert" data-testid="fx-comments-lost"><Icon name="triangle-exclamation" /><span>{t('fx.diff.commentsLost', { n: modal.diff.summary.comments_lost ?? 0 })}</span></div>}
              {(modal.diff.summary.comments_lost ?? 0) === 0 && (modal.diff.summary.comment_lines ?? 0) > 0 && <p className="muted small" data-testid="fx-comments-kept"><Icon name="circle-check" /> {t('fx.diff.commentsKept', { n: modal.diff.summary.comment_lines ?? 0 })}</p>}
              {(modal.diff.summary.rewritten?.count ?? 0) > 0 && <details className="fx-warns" open data-testid="fx-rewritten"><summary>{t('fx.diff.rewritten', { n: modal.diff.summary.rewritten!.count })}</summary>
                <div className="fx-rw"><div><strong>{t('fx.diff.rewrittenFrom')}</strong><ul>{modal.diff.summary.rewritten!.samples.from.slice(0, 20).map((x, i) => <li key={i}><code>{x}</code></li>)}</ul></div>
                  <div><strong>{t('fx.diff.rewrittenTo')}</strong><ul>{modal.diff.summary.rewritten!.samples.to.slice(0, 20).map((x, i) => <li key={i}><code>{x}</code></li>)}</ul></div></div></details>}
              {(modal.diff.summary.samples.added.length + modal.diff.summary.samples.removed.length) > 0 && <details className="fx-warns" data-testid="fx-samples"><summary>{t('fx.diff.samples')}</summary>
                <div className="fx-rw"><div><strong>{t('fx.diff.sampAdded')} (+{modal.diff.summary.added})</strong><ul>{modal.diff.summary.samples.added.slice(0, 15).map((x, i) => <li key={i}><code>{x}</code></li>)}</ul></div>
                  <div><strong>{t('fx.diff.sampRemoved')} (−{modal.diff.summary.removed})</strong><ul>{modal.diff.summary.samples.removed.slice(0, 15).map((x, i) => <li key={i}><code>{x}</code></li>)}</ul></div></div></details>}
              {modal.diff.warnings.length > 0 && <details className="fx-warns"><summary>{t('fx.diff.warns', { n: modal.diff.warnings.length })}</summary><ul>{modal.diff.warnings.slice(0, 20).map((w, i) => <li key={i}>{w}</li>)}</ul></details>}
              <DiffView a={modal.diff.current} b={modal.diff.after} />
              <p className="muted small">{modal.path === 'decisions.json' ? t('fx.diff.note') : modal.diff.summary.source_kept === false ? t('fx.diff.noteCanon') : t('fx.diff.noteKept')}</p>
            </> : <p>{t('fx.diff.same')}</p>}
            <div className="row">
              <Button onClick={() => setModal(null)}>{t('common.cancel')}</Button>
              <Button variant="primary" icon="check" autoFocus disabled={busy} onClick={() => void confirmApply(modal.path)}>{t('fx.apply')}</Button>
            </div>
          </div>
        </div>)}
      {modal?.kind === 'conflict' && (
        <div className="fx-modal" role="alertdialog" aria-modal="true" aria-label={t('fx.conflict.title')} onKeyDown={e => { if (e.key === 'Escape') setModal(null) }}>
          <div className="box small">
            <h2><Icon name="triangle-exclamation" /> {t('fx.conflict.title')}</h2>
            <p>{t('fx.conflict.body')}</p>
            <div className="row">
              <Button onClick={() => setModal(null)}>{t('fx.conflict.keep')}</Button>
              <Button onClick={() => void takeServer(modal.path)}>{t('fx.conflict.reload')}</Button>
              <Button variant="danger" autoFocus onClick={() => void confirmApply(modal.path, true)}>{t('fx.conflict.force')}</Button>
            </div>
          </div>
        </div>)}
    </div>
  )
}
