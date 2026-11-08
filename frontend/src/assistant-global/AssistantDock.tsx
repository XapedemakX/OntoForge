import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { localName, type Project, type Target } from '../api'
import { Button, Icon, IconButton, Krakie, Select } from '../kit'
import type { Pose } from '../krakie/Krakie'
import { useI18n } from '../i18n'
import { onAssistantContext, onAssistantOpen, type AssistantContext, type OpenAssistantOptions } from '../lib/assistantContext'
import { aapi, type AStatus } from '../screens/assistant/aapi'
import { DocImport } from '../screens/assistant/DocImport'
import { DocResult } from '../screens/assistant/DocResult'
import { ProposalCards } from '../screens/assistant/ProposalCards'
import { useProposal } from '../lib/proposal'
import { ActionCards } from './ActionCards'
import { effectiveContext, forSend, ROUTE_SCREEN, type CtxMode } from './context'
import { runChat, go } from './run'
import { getMsgs, getUi, setMsgs, setUi, uid, useConversation, useDockUi, type Msg } from './store'
import './dock.css'

const SEL_KEY: Record<string, string> = { class: 'class', prop: 'prop', property: 'prop', shape: 'shape', finding: 'finding', query: 'query' }

export function AssistantDock({ p, setP, target, screen, perimeter }: { p: Project; setP: (p: Project) => void; target: Target; screen: string; perimeter: string | null }) {
  const { t, lang } = useI18n()
  const ui = useDockUi()
  const [msgs] = useConversation(p.id)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [happy, setHappy] = useState(false)
  const [status, setStatus] = useState<AStatus | null>(null)
  const [declared, setDeclared] = useState<AssistantContext | undefined>(undefined)
  const [mode, setMode] = useState<CtxMode>('full')
  const [docOpen, setDocOpen] = useState(false)
  const prop = useProposal()
  const [oneShot, setOneShot] = useState<Partial<AssistantContext> | null>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const hidden = screen === 'assistant'

  useEffect(() => onAssistantContext(setDeclared), [])
  useEffect(() => { setMode('full'); setOneShot(null) }, [screen, p.id])
  useEffect(() => { aapi.status().then(s => { setStatus(s); if (!getUi().provider) setUi({ provider: s.default_provider_id || s.providers?.find(x => x.default)?.id || s.providers?.[0]?.id || '' }) }).catch(() => {}) }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [msgs, busy, ui.open])

  const ctx = useMemo(() => {
    const c = effectiveContext(screen, p.id, target, perimeter, declared)
    return oneShot ? { ...c, ...oneShot, extra: { ...c.extra, ...oneShot.extra } } : c
  }, [screen, p.id, target, perimeter, declared, oneShot])

  const send = useCallback(async (content: string, override?: Partial<AssistantContext>) => {
    const body = content.trim(); if (!body || busy) return
    const c = forSend(override ? { ...ctx, ...override } : ctx, mode, p.id)
    const user: Msg = { id: uid(), role: 'user', content: body }
    setMsgs(p.id, m => [...m, user]); setText(''); setBusy(true); setHappy(false)
    const reply = await runChat({ p, setP, lang, history: getMsgs(p.id), provider: ui.provider, context: c })
    setMsgs(p.id, m => [...m, reply]); setBusy(false); setHappy(!reply.error && !!reply.actions?.length); setOneShot(null)
  }, [busy, ctx, mode, p, setP, lang, ui.provider])
  const sendRef = useRef(send); sendRef.current = send

  const open = useCallback((o: OpenAssistantOptions = {}) => {
    setUi({ open: true })
    if (o.context) setOneShot(o.context)
    if (o.prompt) { if (o.send) setTimeout(() => void sendRef.current(o.prompt!, o.context), 0); else setText(o.prompt) }
    setTimeout(() => taRef.current?.focus(), 60)
  }, [])
  useEffect(() => onAssistantOpen(o => { if (!hidden) open(o) }), [open, hidden])
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k' && !e.shiftKey && !e.altKey && !hidden) {
        e.preventDefault()
        if (getUi().open && document.activeElement === taRef.current) setUi({ open: false }); else open()
      } else if (e.key === 'Escape' && getUi().open && taRef.current && document.activeElement === taRef.current) setUi({ open: false })
    }
    addEventListener('keydown', f); return () => removeEventListener('keydown', f)
  }, [open, hidden])

  // redimensionnement par la poignée gauche
  const drag = useRef<{ x: number; w: number } | null>(null)
  const onDown = (e: React.PointerEvent) => { drag.current = { x: e.clientX, w: ui.width }; (e.target as HTMLElement).setPointerCapture(e.pointerId) }
  const onMove = (e: React.PointerEvent) => { if (drag.current) setUi({ width: Math.round(Math.min(Math.max(drag.current.w + drag.current.x - e.clientX, 340), Math.max(380, innerWidth * 0.8))) }) }
  const onUp = () => { drag.current = null }
  const onHandleKey = (e: React.KeyboardEvent) => { if (e.key === 'ArrowLeft') setUi({ width: Math.min(ui.width + 24, innerWidth * 0.8) }); if (e.key === 'ArrowRight') setUi({ width: Math.max(ui.width - 24, 340) }) }

  if (hidden) return null
  const lastMsg = msgs[msgs.length - 1]
  const pose: Pose = busy ? 'reflechit' : lastMsg?.error ? 'inquiete' : happy ? 'contente' : 'accueil'
  const providers = status?.providers ?? []
  const screenLabel = t('ag.screen.' + (ROUTE_SCREEN[screen]?.name ?? screen))
  const sel = ctx.selection
  const selText = sel ? t('ag.sel.' + (SEL_KEY[sel.kind] ?? 'other'), { label: sel.label || localName(sel.id) }) : ''
  const suggestions = (mode === 'none' ? [] : ctx.suggestions?.length ? ctx.suggestions : defaultSuggestions(screen, t)).slice(0, 4)
  const pendingActions = msgs.reduce((n, m) => n + (m.actions?.filter(a => (a.kind === 'ops' || a.kind === 'shapes') && (a.status ?? 'idle') === 'idle').length ?? 0), 0)

  return (
    <>
      {!ui.open && (
        <button className={'ag-fab' + (busy ? ' busy' : '')} data-tour="krakie-fab" onClick={() => open()} aria-label={t('ag.open.label')} title={t('ag.open.title')}>
          <Krakie pose={pose} size={44} float={false} />
          {pendingActions > 0 && <b className="ag-badge">{pendingActions}</b>}
        </button>
      )}
      {ui.open && (
        <aside className="ag-panel" style={{ ['--ag-w' as string]: ui.width + 'px' }} role="dialog" aria-label={t('ag.title')}>
          <div className="ag-handle" role="separator" aria-orientation="vertical" aria-label={t('ag.resize')} tabIndex={0}
            onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onKeyDown={onHandleKey} />
          <header className="ag-head">
            <Krakie pose={pose} size={40} float={busy} />
            <div className="ag-ttl"><b>{t('ag.title')}</b><span className="muted">{busy ? t('asst.thinking') : t('ag.sub')}</span></div>
            <span className="grow" />
            {providers.length > 0 && <Select aria-label={t('asst.provider')} value={ui.provider} onChange={e => setUi({ provider: e.target.value })}
              options={providers.map(x => ({ value: x.id, label: `${x.name}${x.configured ? '' : ' ' + t('asst.notConfigured')}` }))} />}
            <IconButton icon="up-right-and-down-left-from-center" label={t('ag.fullscreen')} onClick={() => { setUi({ open: false }); go(p.id, 'assistant') }} />
            {msgs.length > 0 && <IconButton icon="eraser" label={t('asst.clear')} onClick={() => setMsgs(p.id, [])} />}
            <IconButton icon="xmark" label={t('common.close')} onClick={() => setUi({ open: false })} />
          </header>

          <div className="ag-ctx" role="group" aria-label={t('ag.ctx')}>
            <span className="muted">{t('ag.ctx')}</span>
            {mode === 'none'
              ? <button className="ag-chip off" onClick={() => setMode('full')}><Icon name="rotate-left" />{t('ag.ctx.restore')}</button>
              : <>
                <span className="ag-chip"><Icon name="location-dot" />{screenLabel}<button aria-label={t('ag.ctx.drop')} title={t('ag.ctx.drop')} onClick={() => setMode('none')}><Icon name="xmark" /></button></span>
                {sel && (mode === 'full'
                  ? <span className="ag-chip sel"><Icon name="arrow-pointer" />{selText}<button aria-label={t('ag.ctx.dropSel')} title={t('ag.ctx.dropSel')} onClick={() => setMode('screen')}><Icon name="xmark" /></button></span>
                  : <button className="ag-chip off" onClick={() => setMode('full')}><Icon name="plus" />{t('ag.ctx.addSel', { label: sel.label || localName(sel.id) })}</button>)}
              </>}
          </div>

          <div className="ag-log" role="log" aria-live="polite">
            {msgs.length === 0 && (
              <div className="ag-hello"><Krakie pose="accueil" size={72} /><b>{t('ag.hello')}</b><p className="muted">{t('ag.hello.d')}</p></div>
            )}
            {msgs.map(m => (
              <div key={m.id} className={'ag-msg ' + m.role + (m.error ? ' err' : '')}>
                <div className="ag-bubble">
                  {m.content && <p>{m.content}</p>}
                  {m.warnings?.map((w, i) => <p key={i} className="ag-warn"><Icon name="circle-info" />{w}</p>)}
                  {m.doc && <DocResult doc={m.doc} />}
                  {m.doc && prop && prop.projectId === p.id && prop.doc?.id === m.doc.id && prop.items.length > 0 &&
                    <ProposalCards compact mine={prop} prefixes={p.onto.meta.prefixes} onEditor={() => go(p.id, 'ontologie')} />}
                  {m.actions && m.actions.length > 0 && <ActionCards pid={p.id} msgId={m.id} actions={m.actions} setP={setP} />}
                </div>
              </div>
            ))}
            {busy && <div className="ag-msg assistant"><div className="ag-bubble ag-dots" aria-label={t('asst.thinking')}><i /><i /><i /></div></div>}
            <div ref={endRef} />
          </div>

          <div className="ag-compose">
            {suggestions.length > 0 && !text && <div className="ag-sugg" role="group" aria-label={t('ag.suggestions')}>
              {suggestions.map(s => <button key={s} className="ag-pill" disabled={busy} onClick={() => setText(s)}>{s}</button>)}</div>}
            {docOpen && <DocImport compact p={p} setP={setP} provider={ui.provider || undefined} onBusy={setBusy} onClose={() => setDocOpen(false)} />}
            <div className="ag-box">
              <textarea ref={taRef} rows={2} value={text} placeholder={t('ag.placeholder')} aria-label={t('ag.placeholder')} onChange={e => setText(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(text) } }} />
              <IconButton icon="file-import" label={t('doc.open')} aria-expanded={docOpen} disabled={busy} onClick={() => setDocOpen(o => !o)} />
              <Button variant="primary" icon="paper-plane" disabled={busy || !text.trim()} onClick={() => void send(text)}>{t('asst.send')}</Button>
            </div>
            <span className="muted ag-hint">{t('ag.hint')}</span>
          </div>
        </aside>
      )}
    </>
  )
}

function defaultSuggestions(screen: string, t: (k: string) => string): string[] {
  const k = ROUTE_SCREEN[screen]?.name ?? screen
  const out = [t('ag.sugg.' + k), t('ag.sugg.' + k + '.2')].filter(x => !x.startsWith('ag.sugg.'))
  return out.length ? out : [t('ag.sugg.default')]
}
