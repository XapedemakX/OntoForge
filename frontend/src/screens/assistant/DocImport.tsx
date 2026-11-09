import { useCallback, useEffect, useRef, useState } from 'react'
import type { Project } from '../../api'
import { Button, Icon, IconButton, useToast } from '../../kit'
import { useI18n } from '../../i18n'
import { buildItems, setProposal } from '../../lib/proposal'
import { setMsgs, uid, type Msg } from '../../assistant-global/store'
import { KrakieStatus } from '../../krakie/Krakie'
import { aapi, type DocDraft, type DocFile, type DocPlan } from './aapi'
import './doc.css'

const ACCEPT = '.pdf,.txt,.md,.markdown'
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** Import d'un document (.pdf à texte natif, .txt, .md) : lecture locale, estimation, avertissement de confidentialité, puis analyse.
 *  Le résultat est déposé dans la conversation et dans la proposition (éléments « à confirmer »). Rien n'est appliqué au projet. */
export function DocImport({ p, setP, provider, onClose, initialFile, compact, onBusy }: {
  p: Project; setP: (p: Project) => void; provider?: string; onClose: () => void; initialFile?: File | null; compact?: boolean; onBusy?: (b: boolean) => void
}) {
  const { t, lang } = useI18n()
  const toast = useToast()
  const [file, setFile] = useState<DocFile | null>(null)
  const [plan, setPlan] = useState<DocPlan | null>(null)
  const [phase, setPhase] = useState<'idle' | 'reading' | 'ready' | 'running'>('idle')
  const [err, setErr] = useState('')
  const [ok, setOk] = useState(false)
  const [drag, setDrag] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const read = useCallback(async (f: File) => {
    setErr(''); setPhase('reading'); setFile(null); setPlan(null); setOk(false)
    try { setFile(await aapi.docUpload(f)); setPhase('ready') } catch (e) { setErr(msg(e)); setPhase('idle') }
  }, [])
  const demo = useCallback(async () => {
    try {
      const r = await fetch('/api/assistant/document/demo')
      if (!r.ok) throw new Error(String(r.status))
      await read(new File([await r.blob()], 'automaint-cahier-des-charges.pdf', { type: 'application/pdf' }))
    } catch { setErr(t('doc.demo.err')) }
  }, [read, t])
  useEffect(() => { if (initialFile) void read(initialFile) }, [initialFile, read])
  useEffect(() => {
    if (!file) return
    let live = true
    setOk(false)
    aapi.docEstimate({ name: file.name, pages: file.pages }, provider).then(x => { if (live) setPlan(x) }).catch(e => { if (live) { setPlan(null); setErr(msg(e)) } })
    return () => { live = false }
  }, [file, provider])

  async function run() {
    if (!file || !plan || phase === 'running') return
    setPhase('running'); setErr(''); onBusy?.(true)
    try {
      const r = await aapi.docDraft(p.id, { name: file.name, pages: file.pages }, provider, ok)
      deliver(r)
      setFile(null); setPlan(null); setPhase('idle'); onClose()
    } catch (e) { setErr(msg(e)); setPhase('ready') } finally { onBusy?.(false) }
  }

  function deliver(r: DocDraft) {
    const id = uid()
    const items = buildItems(p.onto, r.proposal, lang).map(it => {
      const lint = r.lint.filter(l => l.subject === it.entity_iri).map(l => ({ code: l.code, message: l.message, level: l.level }))
      return { ...it, provenance: r.provenance[it.entity_iri], lint }
    })
    const docLint = r.lint.map(l => ({ code: l.code, message: l.message, level: l.level }))
    if (items.length) setProposal({ projectId: p.id, onto: r.proposal, source: r.document.name, items, doc: { id, name: r.document.name, lint: docLint, approximate: r.approximate, skipped: r.skipped.length, lang: r.document.lang }, onProject: setP })
    const content = items.length ? t('doc.msg.done', { name: r.document.name, pages: r.document.pages, n: items.length }) : t('doc.msg.none', { name: r.document.name })
    const reply: Msg = {
      id: uid(), role: 'assistant', content, warnings: [...new Set(r.warnings)], count: items.length,
      doc: { id, name: r.document.name, pages: r.document.pages, provider: r.provider, approximate: r.approximate, calls: r.stats.calls, items: items.length, skipped: r.skipped.length, questions: r.questions, lint: docLint },
    }
    setMsgs(p.id, m => [...m, { id: uid(), role: 'user', content: t('doc.msg.user', { name: r.document.name }), files: [r.document.name] }, reply])
    toast(t('doc.toast', { n: items.length }), items.length ? { pose: 'trophee' } : undefined)
  }

  const needOk = !!plan?.hosted
  const hostedName = plan?.provider ?? ''
  return (
    <section className={'di' + (compact ? ' compact' : '')} aria-label={t('doc.title')}
      onDragOver={e => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); e.stopPropagation(); setDrag(true) } }}
      onDragLeave={() => setDrag(false)}
      onDrop={e => { e.preventDefault(); e.stopPropagation(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) void read(f) }}>
      <header className="di-h"><Icon name="file-import" /><b>{t('doc.title')}</b><span className="grow" /><IconButton icon="xmark" label={t('asst.close')} onClick={onClose} /></header>
      {!file && phase !== 'reading' && (
        <button className={'di-drop' + (drag ? ' on' : '')} onClick={() => input.current?.click()}>
          <Icon name="file-arrow-up" /><span><b>{t('doc.choose')}</b><br /><span className="muted">{t('doc.formats')}</span></span>
        </button>
      )}
      {!file && phase !== 'reading' && <button className="di-demo" onClick={() => void demo()}><Icon name="wand-magic-sparkles" />{t('doc.demo')}</button>}
      <input ref={input} type="file" hidden accept={ACCEPT} onChange={e => { const f = e.target.files?.[0]; if (f) void read(f); e.target.value = '' }} />
      <KrakieStatus busy={phase === 'running'} done={false} label={t('krakie.forge.doc')} doneLabel="" size={48} />
      {phase === 'reading' && <p className="di-wait" role="status"><Icon name="spinner" className="fa-spin" />{t('doc.reading')}</p>}
      {file && (
        <div className="di-file">
          <div className="di-fh"><Icon name={file.name.toLowerCase().endsWith('.pdf') ? 'file-pdf' : 'file-lines'} /><b>{file.name}</b>
            <span className="muted">{t('doc.meta', { pages: file.page_count, chars: file.chars.toLocaleString(lang) })}</span><span className="grow" />
            <IconButton icon="trash" label={t('doc.remove')} disabled={phase === 'running'} onClick={() => { setFile(null); setPlan(null); setPhase('idle') }} /></div>
          {plan && (
            <p className="di-est"><Icon name="gauge" />{plan.engine === 'heuristic'
              ? t('doc.estimate.local')
              : plan.hosted
                ? t('doc.estimate.llm', { calls: plan.calls, chunks: plan.chunks, chars: plan.chars_sent.toLocaleString(lang) })
                : t('doc.estimate.ollama', { calls: plan.calls, chunks: plan.chunks, chars: plan.chars_total.toLocaleString(lang) })}</p>
          )}
          {needOk && (
            <div className="di-warn" role="alert">
              <p><Icon name="shield-halved" />{t('doc.hosted.warn', { provider: hostedName })}</p>
              <label className="di-ok"><input type="checkbox" checked={ok} onChange={e => setOk(e.target.checked)} />{t('doc.hosted.confirm', { provider: hostedName })}</label>
            </div>
          )}
          <div className="di-actions">
            <Button variant="primary" icon="wand-magic-sparkles" disabled={!plan || phase === 'running' || (needOk && !ok)} onClick={() => void run()}>{phase === 'running' ? t('doc.running') : t('doc.run')}</Button>
            {phase === 'running' && <Icon name="spinner" className="fa-spin" />}
          </div>
        </div>
      )}
      {err && <p className="di-err" role="alert"><Icon name="triangle-exclamation" />{err}</p>}
    </section>
  )
}
