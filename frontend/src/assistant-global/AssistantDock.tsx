import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { localName, type Project, type Target } from '../api'
import { BottomSheet, Button, Icon, IconButton, Krakie, Select } from '../kit'
import { useMobile } from '../shell/sidePref'
import type { Pose } from '../krakie/Krakie'
import { useI18n } from '../i18n'
import { getAssistantContext, onAssistantContext, onAssistantOpen, type AssistantContext, type OpenAssistantOptions } from '../lib/assistantContext'
import { aapi, type AStatus } from '../screens/assistant/aapi'
import { DocImport } from '../screens/assistant/DocImport'
import { DocResult } from '../screens/assistant/DocResult'
import { ProposalCards } from '../screens/assistant/ProposalCards'
import { useProposal } from '../lib/proposal'
import { ActionCards } from './ActionCards'
import { Aquarium } from './Aquarium'
import { effectiveContext, forSend, forSendSettings, ROUTE_SCREEN, settingsContext, type CtxMode } from './context'
import { runChat, go } from './run'
import { getMsgs, getUi, SETTINGS_CONV, setMsgs, setUi, uid, useConversation, useDockUi, type Msg } from './store'
import './dock.css'

const SEL_KEY: Record<string, string> = { class: 'class', prop: 'prop', property: 'prop', shape: 'shape', finding: 'finding', query: 'query' }

/** `p` nul : écran Paramètres (L38), sans projet : conversation à part, contexte = onglet affiché, aucune action de modèle. */
export function AssistantDock({ p, setP, target, screen, perimeter }: { p: Project | null; setP: (p: Project) => void; target: Target; screen: string; perimeter: string | null }) {
  const { t, lang } = useI18n()
  const ui = useDockUi()
  const cid = p?.id ?? SETTINGS_CONV
  const [msgs] = useConversation(cid)
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
  const [hover, setHover] = useState(false)
  const cursor = useRef<{ x: number; y: number } | null>(null)
  const aq = useAquariumSize()
  const mobile = useMobile()   // L44 : bouton fixe de 56 px et feuille plein écran (pas d'aquarium)
  useAquariumFloor(screen)
  useMobileLift(mobile, screen)

  useEffect(() => { setDeclared(getAssistantContext()); return onAssistantContext(setDeclared) }, [])  // l'écran a pu publier son contexte avant l'abonnement du panneau (Paramètres, L38)
  useEffect(() => { setMode('full'); setOneShot(null) }, [screen, cid])
  useEffect(() => { aapi.status().then(s => { setStatus(s); if (!getUi().provider) setUi({ provider: s.default_provider_id || s.providers?.find(x => x.default)?.id || s.providers?.[0]?.id || '' }) }).catch(() => {}) }, [])
  useEffect(() => { if (mobile && status?.providers?.length && !status.providers.some(x => x.id === getUi().provider)) setUi({ provider: curProvId(status) }) }, [mobile, status])
  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [msgs, busy, ui.open])

  const ctx = useMemo(() => {
    if (!p) return settingsContext(declared)
    const c = effectiveContext(screen, p.id, target, perimeter, declared)
    return oneShot ? { ...c, ...oneShot, extra: { ...c.extra, ...oneShot.extra } } : c
  }, [screen, p?.id, target, perimeter, declared, oneShot])

  const send = useCallback(async (content: string, override?: Partial<AssistantContext>) => {
    const body = content.trim(); if (!body || busy) return
    const c = p ? forSend(override ? { ...ctx, ...override } : ctx, mode, p.id) : forSendSettings(ctx, mode)
    const user: Msg = { id: uid(), role: 'user', content: body }
    setMsgs(cid, m => [...m, user]); setText(''); setBusy(true); setHappy(false)
    const reply = await runChat({ p, setP, lang, history: getMsgs(cid), provider: ui.provider, context: c })
    setMsgs(cid, m => [...m, reply]); setBusy(false); setHappy(!reply.error && !!reply.actions?.length); setOneShot(null)
  }, [busy, ctx, mode, p, cid, setP, lang, ui.provider])
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
  const provLabel = (x: (typeof providers)[number]) => `${x.name}${x.model && x.kind !== 'mock' && !x.name.toLowerCase().includes(x.model.toLowerCase()) ? ' · ' + x.model : ''}${x.configured ? '' : ' ' + t('asst.notConfigured')}`
  const curProv = providers.find(x => x.id === ui.provider) ?? providers.find(x => x.id === status?.default_provider_id) ?? providers.find(x => x.default) ?? providers[0]
  const section = !p && typeof ctx.extra?.section === 'string' ? ctx.extra.section : ''
  const screenLabel = t('ag.screen.' + (ROUTE_SCREEN[screen]?.name ?? screen)) + (section ? ' · ' + t('settings.tab.' + section) : '')
  const sel = ctx.selection
  const selText = sel ? t('ag.sel.' + (SEL_KEY[sel.kind] ?? 'other'), { label: sel.label || localName(sel.id) }) : ''
  const suggestions = (mode === 'none' ? [] : ctx.suggestions?.length ? ctx.suggestions : defaultSuggestions(screen, t)).slice(0, 4)
  const pendingActions = msgs.reduce((n, m) => n + (m.actions?.filter(a => (a.kind === 'ops' || a.kind === 'shapes') && (a.status ?? 'idle') === 'idle').length ?? 0), 0)

  const ctxEl = (
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
  )
  const logEl = (
  <div className="ag-log" role="log" aria-live="polite">
    {msgs.length === 0 && (
      <div className="ag-hello"><Krakie pose="accueil" size={72} /><b>{t(p ? 'ag.hello' : 'ag.hello.settings')}</b><p className="muted">{t(p ? 'ag.hello.d' : 'ag.hello.settings.d')}</p></div>
    )}
    {msgs.map(m => (
      <div key={m.id} className={'ag-msg ' + m.role + (m.error ? ' err' : '')}>
        <div className="ag-bubble">
          {m.content && <p>{m.content}</p>}
          {m.warnings?.map((w, i) => <p key={i} className="ag-warn"><Icon name="circle-info" />{w}</p>)}
          {m.doc && <DocResult doc={m.doc} />}
          {p && m.doc && prop && prop.projectId === p.id && prop.doc?.id === m.doc.id && prop.items.length > 0 &&
            <ProposalCards compact mine={prop} prefixes={p.onto.meta.prefixes} onEditor={() => go(p.id, 'ontologie')} />}
          {m.actions && m.actions.length > 0 && <ActionCards pid={p?.id ?? ''} msgId={m.id} actions={m.actions} setP={setP} />}
        </div>
      </div>
    ))}
    {busy && <div className="ag-msg assistant"><div className="ag-bubble ag-dots" aria-label={t('asst.thinking')}><i /><i /><i /></div></div>}
    <div ref={endRef} />
  </div>
  )
  const composeEl = (
  <div className="ag-compose">
    {suggestions.length > 0 && !text && <div className="ag-sugg" role="group" aria-label={t('ag.suggestions')}>
      {suggestions.map(s => <button key={s} className="ag-pill" disabled={busy} onClick={() => setText(s)}>{s}</button>)}</div>}
    {p && docOpen && <DocImport compact p={p} setP={setP} provider={ui.provider || undefined} onBusy={setBusy} onClose={() => setDocOpen(false)} />}
    {mobile && curProv && (
      <div className="ag-llm" data-testid="ag-llm">
        {providers.length > 1
          ? <label><span>{t('ag.llm.label')}</span>
              <Select data-testid="ag-llm-select" value={curProv.id} onChange={e => setUi({ provider: e.target.value })} options={providers.map(x => ({ value: x.id, label: provLabel(x) }))} /></label>
          : <span className="ag-llm-one" data-testid="ag-llm-one"><Icon name="robot" />{t('ag.llm.one', { name: provLabel(curProv) })}</span>}
      </div>)}
    <div className="ag-box">
      <textarea ref={taRef} rows={2} value={text} placeholder={t(p ? 'ag.placeholder' : 'ag.placeholder.settings')} aria-label={t(p ? 'ag.placeholder' : 'ag.placeholder.settings')} onChange={e => setText(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(text) } }} />
      {p && <IconButton icon="file-import" label={t('doc.open')} aria-expanded={docOpen} disabled={busy} onClick={() => setDocOpen(o => !o)} />}
      <Button variant="primary" icon="paper-plane" disabled={busy || !text.trim()} onClick={() => void send(text)}>{t('asst.send')}</Button>
    </div>
    <span className="muted ag-hint">{t('ag.hint')}</span>
  </div>
  )

  return (
    <>
      {!ui.open && mobile && (
        <button className={'ag-fab mob' + (busy ? ' busy' : '')} data-tour="krakie-fab" data-testid="krakie-fab" onClick={() => open()} aria-label={t('ag.open.label')}>
          <Krakie pose={pose} size={44} float={false} />
          {pendingActions > 0 && <b className="ag-badge">{pendingActions}</b>}
        </button>
      )}
      {!ui.open && !mobile && (
        <button className={'ag-fab' + (busy ? ' busy' : '')} data-tour="krakie-fab" onClick={() => open()} aria-label={t('ag.open.label')} title={t('ag.open.title')}
          onPointerEnter={() => setHover(true)} onPointerLeave={() => { setHover(false); cursor.current = null }}
          onPointerMove={e => { const r = e.currentTarget.getBoundingClientRect(); cursor.current = { x: (e.clientX - r.left) / aq.scale, y: (e.clientY - r.top) / aq.scale } }}>
          <Aquarium state={busy ? 'busy' : lastMsg?.error ? 'worried' : happy ? 'happy' : 'idle'} hovered={hover} onCursor={cursor} width={aq.w} height={aq.h} scale={aq.scale} reefW={aq.rw} reefH={aq.rh} />
          {pendingActions > 0 && <b className="ag-badge">{pendingActions}</b>}
        </button>
      )}
      {ui.open && mobile && (
        <BottomSheet open onClose={() => setUi({ open: false })} title={t('ag.title')} initial="full" snaps={['full']} className="ag-sheet" testid="krakie-sheet"
          heading={<span className="ag-mh"><Krakie pose={pose} size={32} float={busy} /><span><b>{t('ag.title')}</b><small className="muted">{busy ? t('asst.thinking') : t(p ? 'ag.sub' : 'ag.sub.settings')}</small></span></span>}
          footer={composeEl}>
          {ctxEl}
          {msgs.length > 0 && <div className="ag-mact"><button type="button" className="btn sm ghost" onClick={() => setMsgs(cid, [])}><Icon name="eraser" />{t('asst.clear')}</button></div>}
          {logEl}
        </BottomSheet>
      )}
      {ui.open && !mobile && (
        <aside className="ag-panel" style={{ ['--ag-w' as string]: ui.width + 'px' }} role="dialog" aria-label={t('ag.title')}>
          <div className="ag-handle" role="separator" aria-orientation="vertical" aria-label={t('ag.resize')} tabIndex={0}
            onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onKeyDown={onHandleKey} />
          <header className="ag-head">
            <Krakie pose={pose} size={40} float={busy} />
            <div className="ag-ttl"><b>{t('ag.title')}</b><span className="muted">{busy ? t('asst.thinking') : t(p ? 'ag.sub' : 'ag.sub.settings')}</span></div>
            <span className="grow" />
            {providers.length > 0 && <Select aria-label={t('asst.provider')} value={ui.provider} onChange={e => setUi({ provider: e.target.value })}
              options={providers.map(x => ({ value: x.id, label: `${x.name}${x.configured ? '' : ' ' + t('asst.notConfigured')}` }))} />}
            {p && <IconButton icon="up-right-and-down-left-from-center" label={t('ag.fullscreen')} onClick={() => { setUi({ open: false }); go(p.id, 'assistant') }} />}
            {msgs.length > 0 && <IconButton icon="eraser" label={t('asst.clear')} onClick={() => setMsgs(cid, [])} />}
            <IconButton icon="xmark" label={t('common.close')} onClick={() => setUi({ open: false })} />
          </header>

          {ctxEl}
          {logEl}
          {composeEl}
        </aside>
      )}
    </>
  )
}

const curProvId = (s: AStatus) => s.default_provider_id || s.providers?.find(x => x.default)?.id || s.providers?.[0]?.id || ''

function defaultSuggestions(screen: string, t: (k: string) => string): string[] {
  const k = ROUTE_SCREEN[screen]?.name ?? screen
  const out = [t('ag.sugg.' + k), t('ag.sugg.' + k + '.2')].filter(x => !x.startsWith('ag.sugg.'))
  return out.length ? out : [t('ag.sugg.default')]
}

/** Aquarium (L37b) : 134×100 pixels à l'échelle 1,5 (≈201×150) sur desktop, 120×90 à l'échelle 1 sous 900 px ; récif de 120 px logiques (≈180 / 120 px) collé en bas. */
/* Une barre collée en bas de l'écran (ex. barre d'état de l'écran Fichiers) porte data-ag-floor : le récif se pose dessus au lieu de la recouvrir.
   La hauteur visible de cette barre est publiée dans --ag-floor sur <html>. */
function useAquariumFloor(screen: string) {
  useEffect(() => {
    const root = document.documentElement
    let ro: ResizeObserver | null = null, el: Element | null = null
    const measure = () => {
      if (!el || !el.isConnected) { root.style.setProperty('--ag-floor', '0px'); return }
      const r = el.getBoundingClientRect()
      const floor = r.width > 0 && r.bottom >= window.innerHeight - 2 ? Math.max(0, window.innerHeight - r.top) : 0
      root.style.setProperty('--ag-floor', `${Math.round(floor)}px`)
    }
    const attach = () => {
      const next = document.querySelector('[data-ag-floor]')
      if (next !== el) { ro?.disconnect(); el = next; if (el && 'ResizeObserver' in window) { ro = new ResizeObserver(measure); ro.observe(el) } }
      measure()
    }
    attach()
    const mo = new MutationObserver(attach); mo.observe(document.body, { childList: true, subtree: true })
    window.addEventListener('resize', measure)
    return () => { mo.disconnect(); ro?.disconnect(); window.removeEventListener('resize', measure); root.style.setProperty('--ag-floor', '0px') }
  }, [screen])
}

function useAquariumSize() {
  const q = '(max-width: 900px)'
  const [small, setSmall] = useState(() => !!window.matchMedia?.(q).matches)
  useEffect(() => { const mq = window.matchMedia?.(q); if (!mq) return; const f = () => setSmall(mq.matches); mq.addEventListener?.('change', f); return () => mq.removeEventListener?.('change', f) }, [])
  return small ? { w: 120, h: 90, scale: 1, rw: 120, rh: 22 } : { w: 134, h: 100, scale: 1.5, rw: 120, rh: 22 }
}

/** Téléphone (L44) : le bouton Krakie se range au-dessus d'une barre collée en bas (data-ag-lift : décision d'arbitrage, « Exécuter », mention « Sur ordinateur »). `--ag-lift` = distance du haut de la barre au bas de l'écran. */
function useMobileLift(mobile: boolean, screen: string) {
  useEffect(() => {
    const root = document.documentElement
    if (!mobile) { root.style.removeProperty('--ag-lift'); return }
    const measure = () => {
      let lift = 0
      document.querySelectorAll<HTMLElement>('[data-ag-lift]').forEach(el => { const r = el.getBoundingClientRect(); if (r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight) lift = Math.max(lift, innerHeight - r.top) })
      root.style.setProperty('--ag-lift', `${Math.round(lift)}px`)
    }
    measure(); const id = setInterval(measure, 350); addEventListener('resize', measure)
    return () => { clearInterval(id); removeEventListener('resize', measure); root.style.removeProperty('--ag-lift') }
  }, [mobile, screen])
}
