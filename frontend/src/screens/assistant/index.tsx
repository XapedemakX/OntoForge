import { useEffect, useMemo, useRef, useState } from 'react'
import { api, curie, type Finding, type ShapesModel, type Target } from '../../api'
import type { ScreenProps } from '../../shell/types'
import { Button, Icon, IconButton, Krakie, Select, useToast } from '../../kit'
import type { Pose } from '../../krakie/Krakie'
import { useI18n } from '../../i18n'
import { bindProjectSetter, clear, useProposal } from '../../lib/proposal'
import { aapi, type AStatus, type FileKind, type UploadedFile } from './aapi'
import { MiniGraph } from './MiniGraph'
import { DocImport } from './DocImport'
import { DocResult } from './DocResult'
import { ProposalCards } from './ProposalCards'
import './assistant.css'

import { ActionCards, runChat } from '../../assistant-global'
import { uid, useConversation, type Msg } from '../../assistant-global/store'
import { useAssistantContext } from '../../lib/assistantContext'
const EXT: Record<string, FileKind> = { csv: 'csv', tsv: 'csv', sql: 'sql', txt: 'text', md: 'markdown', markdown: 'markdown' }

function FilePreview({ f, onRemove }: { f: UploadedFile; onRemove: () => void }) {
  const { t } = useI18n()
  const tables = (f.preview.tables ?? []).map(x => (typeof x === 'string' ? x : x.name))
  return (
    <div className="as-file">
      <div className="as-file-h">
        <Icon name={f.kind === 'csv' ? 'file-csv' : f.kind === 'sql' ? 'database' : 'file-lines'} />
        <b>{f.name}</b><span className="muted">{t('asst.file.lines', { n: f.preview.total_lines })}</span>
        <span className="grow" />
        <IconButton icon="xmark" label={t('asst.file.remove')} onClick={onRemove} />
      </div>
      {f.preview.columns && <div className="as-chips" aria-label={t('asst.file.columns')}>{f.preview.columns.map(c => <span key={c} className="as-chip">{c}</span>)}</div>}
      {tables.length > 0 && <div className="as-chips" aria-label={t('asst.file.tables')}><Icon name="table" />{tables.map(c => <span key={c} className="as-chip">{c}</span>)}</div>}
      <pre className="as-pre">{f.preview.lines.slice(0, f.kind === 'csv' ? 4 : 5).join('\n')}{f.preview.truncated || f.preview.lines.length > 5 ? '\n…' : ''}</pre>
    </div>
  )
}

export function AssistantScreen({ p, setP, target }: ScreenProps) {
  const { t, lang } = useI18n()
  const toast = useToast()
  const prop = useProposal()
  const mine = prop && prop.projectId === p.id ? prop : null
  const [msgs, setMsgs] = useConversation(p.id)
  useAssistantContext({ screen: 'assistant', projectId: p.id, target })
  const [text, setText] = useState('')
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)
  const [status, setStatus] = useState<AStatus | null>(null)
  const [stErr, setStErr] = useState(false)
  const [prov, setProv] = useState('')
  const [tab, setTab] = useState<'chat' | 'prop'>('chat')
  const [happy, setHappy] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)
  const [shapes, setShapes] = useState<{ model: ShapesModel; n: number } | null>(null)
  const [explainOpen, setExplainOpen] = useState(false)
  const [docOpen, setDocOpen] = useState(false)
  const [docFile, setDocFile] = useState<File | null>(null)
  const [findings, setFindings] = useState<Finding[] | null>(null)
  const [findingId, setFindingId] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const fileIn = useRef<HTMLInputElement>(null)

  useEffect(() => { bindProjectSetter(setP); return () => bindProjectSetter(null) }, [setP])
  useEffect(() => {
    setShapes(null)
    // fichier déposé depuis l'écran Projets : joint d'office, l'aperçu des colonnes est prêt
    let handoff: UploadedFile | null = null
    try { const raw = sessionStorage.getItem('of-handoff-' + p.id); if (raw) { handoff = JSON.parse(raw); setTimeout(() => { try { sessionStorage.removeItem('of-handoff-' + p.id) } catch { /* ignoré */ } }, 1500) } } catch { /* stockage indisponible */ }
    setFiles(handoff ? [handoff] : [])
  }, [p.id])
  useEffect(() => {
    // un résultat de document est long : on montre son début (« J'ai lu… »), pas sa fin
    const last = msgs[msgs.length - 1]
    const el = last?.doc && !busy ? document.getElementById('msg-' + last.id) : null
    if (el) el.scrollIntoView({ block: 'start' }); else endRef.current?.scrollIntoView({ block: 'end' })
  }, [msgs, busy])
  useEffect(() => {
    aapi.status().then(s => { setStatus(s); setProv(v => v || s.default_provider_id || s.providers?.find(x => x.default)?.id || s.providers?.[0]?.id || '') }).catch(() => setStErr(true))
    api.settings().then(s => { void s }).catch(() => { /* paramètres indisponibles */ })
  }, [])

  const providers = status?.providers ?? []
  const real = providers.filter(x => x.kind !== 'mock' && x.configured)
  const onlyMock = !!status && real.length === 0
  const pose: Pose = busy ? 'reflechit' : happy ? 'contente' : 'accueil'
  const say = (m: Omit<Msg, 'id'>) => setMsgs(x => [...x, { ...m, id: uid() }])

  async function addFiles(list: FileList | File[]) {
    for (const f of Array.from(list).slice(0, 4)) {
      const ext = f.name.split('.').pop()?.toLowerCase() ?? ''
      if (ext === 'pdf') { setDocFile(f); setDocOpen(true); continue }
      if (!EXT[ext]) { toast(t('asst.file.bad', { name: f.name })); continue }
      try { const u = await aapi.upload(f); setFiles(x => [...x.filter(y => y.name !== u.name), u]) }
      catch (e) { toast(e instanceof Error ? e.message : String(e)) }
    }
  }

  async function send(content: string, withFiles = files) {
    const body = content.trim(); if (!body || busy) return
    const history = [...msgs, { id: 'tmp', role: 'user' as const, content: body }]
    say({ role: 'user', content: body, files: withFiles.map(f => f.name) })
    setText(''); setFiles([]); setBusy(true); setHappy(false)
    const reply = await runChat({ p, setP, lang, history: history as Msg[], provider: prov || undefined, context: { screen: 'assistant', projectId: p.id, target },
      attachments: withFiles.map(f => ({ name: f.name, kind: f.kind, content: f.content })), sourceLabel: withFiles[0]?.name ?? body.slice(0, 60) })
    if (reply.count) { setHappy(true); setPicked(null) }
    setMsgs(x => [...x, reply]); setBusy(false)
  }

  async function genShapes() {
    if (busy) return
    say({ role: 'user', content: t('asst.qa.shapes') }); setBusy(true); setHappy(false)
    try {
      const r = await aapi.shapes(p.id, prov || undefined)
      const n = Object.keys(r.proposal.shapes).length
      setShapes({ model: r.proposal, n }); setHappy(true)
      say({ role: 'assistant', content: r.explanation, count: undefined, warnings: [t('asst.shapes.msg', { n })] })
    } catch (e) { say({ role: 'assistant', content: e instanceof Error ? e.message : String(e), error: true }) }
    finally { setBusy(false) }
  }
  async function applyShapes() {
    if (!shapes) return
    const m = structuredClone(p.shapes)
    Object.assign(m.shapes, shapes.model.shapes); Object.assign(m.property_shapes, shapes.model.property_shapes); m.prefixes = { ...m.prefixes, ...shapes.model.prefixes }
    try { setP(await api.putShapes(p.id, m)); toast(t('asst.shapes.done', { n: shapes.n })); setShapes(null) } catch (e) { toast(e instanceof Error ? e.message : String(e)) }
  }
  async function openExplain() {
    setExplainOpen(o => !o)
    if (!findings) {
      try { const m = await api.analyze(p.id, target); const f = m.findings.filter(x => x.severity !== 'auto'); setFindings(f); setFindingId(f[0]?.id ?? '') } catch { setFindings([]) }
    }
  }
  async function explain() {
    const f = findings?.find(x => x.id === findingId); if (!f || busy) return
    setExplainOpen(false); say({ role: 'user', content: t('asst.explain.q', { title: f.title }) }); setBusy(true)
    try { const r = await aapi.explain(p.id, target as Target, f.id, prov || undefined); say({ role: 'assistant', content: r.text }) }
    catch (e) { say({ role: 'assistant', content: e instanceof Error ? e.message : String(e), error: true }) }
    finally { setBusy(false) }
  }

  const csvLike = files.find(f => f.kind === 'csv' || f.kind === 'sql')
  const pf = p.onto.meta.prefixes
  const pending = mine?.items.length ?? 0
  const grouped = useMemo(() => mine?.items ?? [], [mine])
  const toEditor = () => { location.hash = `#/projet/${encodeURIComponent(p.id)}/ontologie` }

  return (
    <div className="as" onDragOver={e => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setDrag(true) } }} onDragLeave={e => { if (e.currentTarget === e.target) setDrag(false) }}
      onDrop={e => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files.length) void addFiles(e.dataTransfer.files) }}>
      <div className="as-tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'chat'} onClick={() => setTab('chat')}><Icon name="comments" />{t('asst.tab.chat')}</button>
        <button role="tab" aria-selected={tab === 'prop'} onClick={() => setTab('prop')}><Icon name="wand-magic-sparkles" />{t('asst.tab.prop')}{pending > 0 && <b className="as-n">{pending}</b>}</button>
      </div>

      <section className={'as-chat' + (tab === 'chat' ? '' : ' hide-m')} aria-label={t('asst.title')}>
        <header className="as-head">
          <Krakie pose={pose} size={48} float={busy} />
          <div className="as-title"><h1>{t('asst.title')}</h1><span className="muted">{busy ? t('asst.thinking') : t('asst.sub', { name: p.name })}</span></div>
          <span className="grow" />
          {providers.length > 0 && <label className="as-prov"><span className="muted">{t('asst.provider')}</span>
            <Select aria-label={t('asst.provider')} value={prov} onChange={e => setProv(e.target.value)} options={providers.map(x => ({ value: x.id, label: `${x.name}${x.configured ? '' : ' ' + t('asst.notConfigured')}` }))} /></label>}
          {msgs.length > 0 && <IconButton icon="eraser" label={t('asst.clear')} onClick={() => { setMsgs([]); setHappy(false) }} />}
        </header>

        {onlyMock && <div className="as-note" role="note"><Icon name="plug-circle-exclamation" /><span>{t('asst.mockOnly')} <a href="#/parametres">{t('asst.mockOnly.link')}</a></span></div>}
        {stErr && <div className="as-note warn" role="alert"><Icon name="triangle-exclamation" /><span>{t('asst.statusErr')}</span></div>}

        <div className="as-log" role="log" aria-live="polite">
          {msgs.length === 0 && (
            <div className="as-hello">
              <Krakie pose="accueil" size={96} />
              <h2>{t('asst.hello')}</h2>
              <p className="muted">{t('asst.hello.d')}</p>
              <div className="as-starts">
                {(['asst.start.1', 'asst.start.2', 'asst.start.3'] as const).map(k => <button key={k} className="as-start" onClick={() => setText(t(k))}>{t(k)}</button>)}
              </div>
            </div>
          )}
          {msgs.map(m => (
            <div key={m.id} id={'msg-' + m.id} className={'as-msg ' + m.role + (m.error ? ' err' : '')}>
              {m.role === 'assistant' && <Krakie pose={m.error ? 'inquiete' : m.count ? 'contente' : 'accueil'} size={32} float={false} />}
              <div className="as-bubble">
                {m.files?.map(f => <span key={f} className="as-chip file"><Icon name="paperclip" />{f}</span>)}
                <p>{m.content}</p>
                {m.warnings?.map((w, i) => <p key={i} className="as-warn"><Icon name="circle-info" />{w}</p>)}
                {m.doc && <DocResult doc={m.doc} onReview={() => setTab('prop')} />}
                {m.actions && m.actions.length > 0 && <ActionCards pid={p.id} msgId={m.id} actions={m.actions} setP={setP} />}
                {m.count !== undefined && !m.doc && <button className="as-link" onClick={() => setTab('prop')}><Icon name="arrow-right" />{m.count ? t('asst.seeProp', { n: m.count }) : t('asst.nothingNew')}</button>}
              </div>
            </div>
          ))}
          {busy && <div className="as-msg assistant"><Krakie pose="reflechit" size={32} float={false} /><div className="as-bubble as-dots" aria-label={t('asst.thinking')}><i /><i /><i /></div></div>}
          <div ref={endRef} />
        </div>

        <div className="as-compose">
          {explainOpen && <div className="as-pop">
            {findings === null ? <span className="muted">…</span> : findings.length === 0 ? <span className="muted">{t('asst.explain.none')}</span> : <>
              <Select aria-label={t('asst.qa.explain')} value={findingId} onChange={e => setFindingId(e.target.value)} options={findings.map(f => ({ value: f.id, label: `${f.rule} · ${f.title}`.slice(0, 90) }))} />
              <Button size="sm" variant="primary" onClick={explain}>{t('asst.explain.go')}</Button></>}
          </div>}
          <div className="as-qa" role="group" aria-label={t('asst.qa')}>
            <Button size="sm" icon="file-circle-plus" disabled={busy || !csvLike} title={csvLike ? undefined : t('asst.qa.needFile')} onClick={() => send(t('asst.qa.draft.msg'))}>{t('asst.qa.draft')}</Button>
            <Button size="sm" icon="file-import" disabled={busy} aria-expanded={docOpen} onClick={() => setDocOpen(o => !o)}>{t('doc.open')}</Button>
            <Button size="sm" icon="shield-halved" disabled={busy} onClick={genShapes}>{t('asst.qa.shapes')}</Button>
            <Button size="sm" icon="circle-question" disabled={busy} onClick={openExplain} aria-expanded={explainOpen}>{t('asst.qa.explain')}</Button>
            <Button size="sm" icon="link" disabled={busy} onClick={() => send(t('asst.qa.align.msg'))}>{t('asst.qa.align')}</Button>
          </div>
          {docOpen && <DocImport p={p} setP={setP} provider={prov || undefined} initialFile={docFile} onBusy={setBusy} onClose={() => { setDocOpen(false); setDocFile(null) }} />}
          {files.map(f => <FilePreview key={f.name} f={f} onRemove={() => setFiles(x => x.filter(y => y !== f))} />)}
          <div className={'as-drop' + (drag ? ' on' : '')}>
            <textarea rows={2} value={text} placeholder={t('asst.placeholder')} aria-label={t('asst.placeholder')} onChange={e => setText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(text) } }} />
            <div className="as-actions">
              <input ref={fileIn} type="file" hidden multiple accept=".csv,.tsv,.sql,.txt,.md,.markdown,.pdf" onChange={e => { if (e.target.files) void addFiles(e.target.files); e.target.value = '' }} />
              <Button size="sm" variant="ghost" icon="paperclip" onClick={() => fileIn.current?.click()}>{t('asst.attach')}</Button>
              <span className="muted as-hint">{t('asst.dropHint')}</span><span className="grow" />
              <Button variant="primary" icon="paper-plane" disabled={busy || !text.trim()} onClick={() => send(text)}>{t('asst.send')}</Button>
            </div>
          </div>
        </div>
        {drag && <div className="as-veil"><Icon name="file-arrow-up" />{t('asst.drop')}</div>}
      </section>

      <aside className={'as-prop' + (tab === 'prop' ? '' : ' hide-m')} aria-label={t('asst.prop.title')}>
        <header className="as-phead">
          <h2>{t('asst.prop.title')}</h2>
          {mine && <span className="muted">{t('asst.prop.count', { n: pending })}</span>}
        </header>
        {!mine && !shapes && (
          <div className="as-empty"><Krakie pose="lit" size={80} /><b>{t('asst.prop.empty')}</b><p className="muted">{t('asst.prop.empty.d')}</p></div>
        )}
        {mine && (
          <div className="as-pbody">
            <p className="muted as-src"><Icon name="file-lines" /> {mine.source}</p>
            {mine.doc
              ? <details className="as-graph"><summary><Icon name="diagram-project" />{t('doc.graph')}</summary><MiniGraph onto={mine.onto} cur={p.onto} items={mine.items} lang={lang} picked={picked} onPick={id => { setPicked(id); document.getElementById('as-' + id)?.scrollIntoView({ block: 'nearest' }) }} /><div className="as-legend"><span className="add"><i />{t('asst.add')}</span><span className="modify"><i />{t('asst.modify')}</span><span className="ctx"><i />{t('asst.ctx')}</span></div></details>
              : <>
                <MiniGraph onto={mine.onto} cur={p.onto} items={mine.items} lang={lang} picked={picked} onPick={id => { setPicked(id); document.getElementById('as-' + id)?.scrollIntoView({ block: 'nearest' }) }} />
            <div className="as-legend"><span className="add"><i />{t('asst.add')}</span><span className="modify"><i />{t('asst.modify')}</span><span className="ctx"><i />{t('asst.ctx')}</span></div>
              </>}
            {mine.error && <div className="as-note warn" role="alert"><Icon name="triangle-exclamation" /><span>{mine.error}</span></div>}
            {pending === 0 ? (
              <div className="as-done"><Krakie pose="contente" size={64} /><b>{t('asst.done', { a: mine.accepted, r: mine.rejected })}</b>
                <div className="as-row"><Button variant="primary" icon="diagram-project" onClick={toEditor}>{t('asst.toEditor')}</Button><Button variant="ghost" onClick={clear}>{t('asst.close')}</Button></div></div>
            ) : (<>
              <ProposalCards mine={mine} prefixes={pf} picked={picked} onEditor={toEditor} />
            </>)}
          </div>
        )}
        {shapes && (
          <div className="as-shapes"><Icon name="shield-halved" /><div><b>{t('asst.shapes.title', { n: shapes.n })}</b><span className="muted">{Object.values(shapes.model.shapes).slice(0, 4).map(s => curie(s.targets.target_class[0] ?? s.id, pf)).join(', ')}</span></div>
            <Button size="sm" variant="primary" onClick={applyShapes}>{t('asst.shapes.apply')}</Button><IconButton icon="xmark" label={t('asst.close')} onClick={() => setShapes(null)} /></div>
        )}
      </aside>
    </div>
  )
}
