import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ScreenProps } from '../../shell/types'
import { Icon, Button, Segmented } from '../../kit'
import { useT, useI18n } from '../../i18n'
import { useToast } from '../../ui'
import { announceActiveEndpoint, useActiveEndpoint } from '../settings/activeEndpoint'
import { Builder, useSuggestions, type Ctx } from './Builder'
import { CodePanel } from './CodePanel'
import { Results } from './Results'
import { Library } from './Library'
import { FreeSparql } from './FreeSparql'
import { NlBox } from './NlBox'
import { TempEndpointForm } from './TempEndpoint'
import { tempStore, useTempEndpoint } from './tempEndpoint'
import { qapi, type BuildResult, type Endpoint, type Guided, type RootClass, type RunResult, type SavedQuery } from './qapi'
import { EMPTY, allNodes, fromGuided, localName, toGuided, type QState } from './model'
import { useAssistantContext } from '../../lib/assistantContext'
import './queries.css'

export function Queries({ p, target }: ScreenProps) {
  const t = useT(); const { lang } = useI18n(); const toast = useToast()
  const savedActive = useActiveEndpoint()
  const { temp, using } = useTempEndpoint()
  const inline = using ? temp : null
  const active = inline ? { id: 'temporaire', name: t('q.tmp.name.short'), url: inline.url } : savedActive
  const [tmpOpen, setTmpOpen] = useState(false)
  const [mode, setMode] = useState<'guided' | 'free'>('guided')
  const [state, setState] = useState<QState>(EMPTY)
  const [free, setFree] = useState(() => `PREFIX : <${(p.onto.meta.iri ?? 'https://example.org/onto').replace(/[#/]?$/, '#')}>\nSELECT ?s ?o WHERE {\n  ?s a :Vehicle .\n  ?s ?p ?o .\n} LIMIT 10`)
  const [roots, setRoots] = useState<RootClass[]>([])
  const [openAdd, setOpenAdd] = useState<string | null>(null); const [seed, setSeed] = useState('')
  const [build, setBuild] = useState<BuildResult | null>(null); const [buildErr, setBuildErr] = useState<string | null>(null); const [building, setBuilding] = useState(false)
  const [res, setRes] = useState<RunResult | null>(null); const [runErr, setRunErr] = useState<string | null>(null); const [busy, setBusy] = useState(false); const [ranOnce, setRanOnce] = useState(false)
  const [endpoints, setEndpoints] = useState<Endpoint[]>([])
  const [libKey, setLibKey] = useState(0); const [activeSaved, setActiveSaved] = useState<string | null>(null)
  const resRef = useRef<HTMLDivElement>(null)

  useEffect(() => { qapi.roots(p.id, lang).then(r => setRoots(r.classes)).catch(() => setRoots([])) }, [p.id, lang, p.updated_at])
  useEffect(() => { qapi.endpoints().then(r => setEndpoints(r.endpoints)).catch(() => setEndpoints([])) }, [savedActive?.id, tmpOpen])
  useEffect(() => { setState(EMPTY); setBuild(null); setRes(null); setActiveSaved(null) }, [p.id])

  const classes = useMemo(() => allNodes(state.root).map(n => n.classIri), [state.root])
  const sug = useSuggestions(p.id, lang, classes)
  const guided = useMemo(() => toGuided(state), [state])
  const guidedKey = JSON.stringify(guided)

  // traduction en continu (SPARQL / Cypher / Curiosity / GraphQL) avec petite attente
  useEffect(() => {
    if (!guided) { setBuild(null); setBuildErr(null); return }
    setBuilding(true)
    const h = window.setTimeout(() => {
      qapi.build(p.id, guided, target).then(b => { setBuild(b); setBuildErr(null) }).catch(e => setBuildErr((e as Error).message)).finally(() => setBuilding(false))
    }, 300)
    return () => window.clearTimeout(h)
  }, [guidedKey, target, p.id, p.updated_at]) // eslint-disable-line react-hooks/exhaustive-deps

  const exec = useCallback(async (body: { guided?: Guided; sparql?: string }, limit?: number) => {
    setBusy(true); setRunErr(null); setRanOnce(true)
    try {
      setRes(await qapi.run(p.id, { ...body, ...(inline ? { endpoint: inline } : { endpoint_id: active?.id }), limit }))
      requestAnimationFrame(() => resRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }))
    } catch (e) { setRes(null); setRunErr(readable((e as Error).message, t)) } finally { setBusy(false) }
  }, [p.id, active?.id, inline, t])
  const labelOf = useCallback((iri: string) => {
    const r = roots.find(c => c.iri === iri); if (r) return r.label
    for (const s of Object.values(sug)) if (s && typeof s === 'object') { const o = [...s.outgoing, ...s.incoming].find(x => x.iri === iri); if (o) return o.label; const d = s.data_properties.find(x => x.iri === iri); if (d) return d.label }
    return localName(iri)
  }, [roots, sug])
  const load = (q: SavedQuery, run: boolean) => {
    setActiveSaved(q.id)
    if (q.guided) { setMode('guided'); setState(fromGuided(q.guided, labelOf)); if (run) void exec({ guided: q.guided }) }
    else if (q.sparql) { setMode('free'); setFree(q.sparql); if (run) void exec({ sparql: q.sparql }) }
  }
  // Requête guidée envoyée par l'assistant global (Krakie) : clé localStorage + évènement window.
  useEffect(() => {
    const take = (payload: { guided?: Guided; sparql?: string } | null) => {
      if (!payload) return
      if (payload.guided) { setMode('guided'); setState(fromGuided(payload.guided, labelOf)) }
      else if (payload.sparql) { setMode('free'); setFree(payload.sparql) }
    }
    const key = 'ontoforge.pending-query.' + p.id
    try { const raw = localStorage.getItem(key); if (raw) { localStorage.removeItem(key); take(JSON.parse(raw)) } } catch { /* stockage indisponible */ }
    const h = (e: Event) => { try { localStorage.removeItem(key) } catch { /* */ } take((e as CustomEvent).detail) }
    window.addEventListener('ontoforge:open-query', h)
    return () => window.removeEventListener('ontoforge:open-query', h)
  }, [p.id, roots.length]) // eslint-disable-line react-hooks/exhaustive-deps
  useAssistantContext({ screen: 'queries', projectId: p.id, target, extra: { mode, guided: guided ?? undefined, sparql: mode === 'free' ? free.slice(0, 2000) : undefined },
    suggestions: [t('q.ai.s1'), t('q.ai.s2'), t('q.ai.s3')] }, [guidedKey, mode])
  const save = async (name: string) => {
    try {
      const s = mode === 'guided' ? await qapi.save(p.id, { name, guided }) : await qapi.save(p.id, { name, sparql: free })
      setActiveSaved(s.id); setLibKey(k => k + 1); toast(t('q.saved', { n: name }))
    } catch (e) { toast((e as Error).message) }
  }
  const pickEndpoint = async (id: string) => {
    if (id === '__new') { setTmpOpen(true); return }
    if (id === '__temp') { tempStore.use(true); return }
    tempStore.use(false)
    try { await qapi.setActive(id || null); const e = endpoints.find(x => x.id === id); announceActiveEndpoint(e ? { id: e.id, name: e.name, url: e.url } : null) } catch (e) { toast((e as Error).message) }
  }
  const savedAsActive = async (id: string) => {
    setTmpOpen(false)
    try { await qapi.setActive(id); const r = await qapi.endpoints(); setEndpoints(r.endpoints); const e = r.endpoints.find(x => x.id === id); announceActiveEndpoint(e ? { id: e.id, name: e.name, url: e.url } : null); toast(t('q.tmp.saved')) } catch (e) { toast((e as Error).message) }
  }
  const ctx: Ctx = { pid: p.id, lang, endpointId: inline ? null : active?.id ?? null, inline, sug, roots, state, set: f => setState(f), openAdd, setOpenAdd, seed, setSeed }
  const canRun = mode === 'guided' ? !!guided : !!free.trim()

  return (
    <div className="page qpage">
      <div className="page-head">
        <h1>{t('nav.requetes')}</h1>
        <span className="grow" />
        <label className="qep" data-tour="q-endpoint"><Icon name="plug" /><span className="sr">{t('head.sparql')}</span>
          <select value={inline ? '__temp' : savedActive?.id ?? ''} onChange={e => void pickEndpoint(e.target.value)} aria-label={t('head.sparql')}>
            {!active && <option value="">{t('head.sparqlNone')}</option>}
            {endpoints.map(e => <option key={e.id} value={e.id}>{e.name || e.url}</option>)}
            {temp && <option value="__temp">{t('q.tmp.opt', { u: temp.url.replace(/^https?:\/\//, '') })}</option>}
            <option value="__new">{t('q.tmp.new')}</option>
          </select></label>
      </div>
      {tmpOpen && <TempEndpointForm pid={p.id} initial={temp} onClose={() => setTmpOpen(false)} onSaved={id => void savedAsActive(id)} />}
      <div className="desk"><NlBox pid={p.id} onResult={r => { if (r.guided) { setMode('guided'); setActiveSaved(null); setState(fromGuided(r.guided, labelOf)); setRes(null) } }}
        onTerm={w => { setMode('guided'); setSeed(w); setOpenAdd(state.root?.id ?? null); if (!state.root) setState(EMPTY) }} /></div>
      <div className="qmain">
        <div className="qleft">
          <div className="qmode desk"><Segmented label={t('q.mode')} value={mode} onChange={setMode} items={[['guided', t('q.mode.guided')], ['free', t('q.mode.free')]]} /></div>
          <div className="qbuilder desk" data-tour="q-builder">
            {mode === 'guided' ? <Builder ctx={ctx} /> : <FreeSparql pid={p.id} target={target} sparql={free} setSparql={setFree} onRun={() => void exec({ sparql: free })} busy={busy} />}
          </div>
          <div className="qrun desk">
            {mode === 'guided' && state.root && <Button size="sm" variant="ghost" icon="rotate-left" onClick={() => { setState(EMPTY); setRes(null); setActiveSaved(null) }}>{t('q.reset')}</Button>}
            <span className="grow" />
            {!active && <span className="muted"><Icon name="plug-circle-xmark" /> {t('q.noendpoint')}</span>}
            <Button variant="primary" icon="play" disabled={busy || !canRun || !active} onClick={() => void exec(mode === 'guided' ? { guided: guided! } : { sparql: free }, mode === 'guided' ? state.limit : undefined)}>{t('q.run')}</Button>
          </div>
          <div ref={resRef} className="qres-anchor"><Results res={res} busy={busy} error={runErr} ranOnce={ranOnce} /></div>
        </div>
        <aside className="qright">
          {mode === 'guided' && <div className="desk"><CodePanel build={build} error={buildErr} building={building} /></div>}
          <Library pid={p.id} lang={lang} target={target} reloadKey={libKey} activeId={activeSaved} canSave={mode === 'guided' ? !!guided : !!free.trim()}
            onSave={save} onOpen={q => load(q, false)} onRun={q => load(q, true)} onFree={s => { setMode('free'); setFree(s) }} />
        </aside>
      </div>
    </div>
  )
}

/** Rend un message d'erreur d'exécution lisible (codes HTTP du garde-fou). */
function readable(m: string, t: (k: string, p?: Record<string, string | number>) => string): string {
  if (/aucun endpoint/i.test(m)) return t('q.err.noendpoint')
  if (/délai|timeout/i.test(m)) return t('q.err.timeout', { m })
  return m
}
