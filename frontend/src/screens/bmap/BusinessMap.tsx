// Écran « Carte métier » : le schéma en zones métier teintées (ontologie ou modèle cible), avec scénarios de mise en avant.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api'
import type { ScreenProps } from '../../shell/types'
import { useMedia, useMobile } from '../../shell/sidePref'
import { FicheSheet } from '../../mobile/Fiche'
import { BottomSheet, Button, Icon, IconButton, Segmented, useLongPress, useToast } from '../../kit'
import { Empty, ErrorView, Spin, Tabs } from '../../ui'
import { useI18n } from '../../i18n'
import { useAssistantContext } from '../../lib/assistantContext'
import { download, svgToPng } from '../editor/exporter'
import { buildMapSvg, buildParts } from './render'
import { isDarkTheme, palette } from './palette'
import { normalizeMap, type BMap, type Source, type ZoneStrategy } from './types'
import { moveToZone, setNode, zoneAt } from './ops'
import { useBMap } from './useBMap'
import { Inspector, ScenariosPanel, ZonesPanel, type BSel } from './Panels'
import './bmap.css'

const MIN_READABLE = 0.45  // zoom minimal d'ouverture sur mobile : au-dessous, types et libellés ne se lisent plus
const SRC_KEY = 'ontoforge.bmap.source'
const scKey = (pid: string, s: string) => `ontoforge.bmap.sc.${pid}.${s}`
const lsGet = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }
const lsSet = (k: string, v: string | null) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v) } catch { /* ignoré */ } }
type View = { k: number; x: number; y: number }

export function BusinessMap({ p, setP, target }: ScreenProps) {
  const { t, lang } = useI18n(); const toast = useToast()
  const mobile = useMobile()   // L44 : pincer, appui long, fiche du bas ; la carte reste en lecture (édition sur ordinateur)
  const ro = useMedia('(max-width: 760px)') || mobile
  const [source, setSourceState] = useState<Source>(() => (lsGet(SRC_KEY) === 'target' ? 'target' : 'ontology'))
  const setSource = (s: Source) => { lsSet(SRC_KEY, s); setSourceState(s); setSel(null) }
  const { map, error, loading, saving, commit, undo, canUndo, setError } = useBMap(p.id, source, p.updated_at)
  const [sel, setSel] = useState<BSel>(null)
  const [tab, setTab] = useState<'insp' | 'zones' | 'scen'>('insp')
  const [activeId, setActiveId] = useState<string | null>(() => lsGet(scKey(p.id, source)))
  useEffect(() => { setActiveId(lsGet(scKey(p.id, source))) }, [p.id, source])
  const setActive = useCallback((id: string | null) => { setActiveId(id); lsSet(scKey(p.id, source), id) }, [p.id, source])
  const [busy, setBusy] = useState('')
  const [draft, setDraft] = useState<Record<string, { x: number; y: number }> | null>(null)
  const [dark, setDark] = useState(isDarkTheme())
  useEffect(() => { const o = new MutationObserver(() => setDark(isDarkTheme())); o.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] }); const mq = matchMedia('(prefers-color-scheme: dark)'); const f = () => setDark(isDarkTheme()); mq.addEventListener('change', f); return () => { o.disconnect(); mq.removeEventListener('change', f) } }, [])

  const scenario = useMemo(() => map?.scenarios.find(s => s.id === activeId) ?? null, [map, activeId])
  const shown = useMemo<BMap | null>(() => (map && draft ? { ...map, nodes: map.nodes.map(n => (draft[n.id] ? { ...n, ...draft[n.id] } : n)) } : map), [map, draft])
  const pal = useMemo(() => palette(dark), [dark])
  const parts = useMemo(() => (shown ? buildParts({ map: shown, scenario, pal, t, lang, withLegend: true, interactive: true }) : null), [shown, scenario, pal, t, lang])

  // ---------- Krakie
  const selNode = sel?.kind === 'node' ? map?.nodes.find(n => n.id === sel.id) : null
  useAssistantContext({
    screen: 'business-map', projectId: p.id, target,
    selection: sel && map ? { kind: sel.kind === 'node' ? 'class' : 'relation', id: sel.id, label: selNode?.label ?? map.edges.find(e => e.id === sel.id)?.label } : null,
    extra: { source, scenario: scenario?.name ?? null, zones: map?.zones.map(z => z.title) ?? [], nodes: map?.nodes.length ?? 0 },
    suggestions: [t('bm.k.zones'), selNode ? t('bm.k.highlightNode', { v: selNode.label }) : t('bm.k.highlight')],
  }, [source, scenario?.id, map?.zones.length, map?.nodes.length])

  // ---------- zoom et déplacement
  const svgRef = useRef<SVGSVGElement>(null), vpRef = useRef<SVGGElement>(null), view = useRef<View>({ k: 1, x: 0, y: 0 })
  const [zoomPct, setZoomPct] = useState(100)
  const applyView = useCallback(() => { const v = view.current; vpRef.current?.setAttribute('transform', `translate(${v.x} ${v.y}) scale(${v.k})`); setZoomPct(Math.round(v.k * 100)) }, [])
  /** « Tout voir » : toute la carte dans la fenêtre. */
  const fit = useCallback(() => {
    const el = svgRef.current, pt = parts; if (!el || !pt) return
    const r = el.getBoundingClientRect(); if (!r.width) return
    const k = Math.min(r.width / pt.w, r.height / pt.h) * 0.98
    view.current = { k, x: (r.width - pt.w * k) / 2, y: (r.height - pt.h * k) / 2 }; applyView()
  }, [parts, applyView])
  /** Vue d'ouverture : ajustée à l'écran ; sur un écran étroit, zoom lisible (45 % au moins) cadré sur la zone la plus peuplée, le reste se parcourt au doigt. */
  const fitStart = useCallback(() => {
    const el = svgRef.current, pt = parts, mp = map; if (!el || !pt || !mp) return
    const r = el.getBoundingClientRect(); if (!r.width) return
    const k = Math.min(r.width / pt.w, r.height / pt.h) * 0.98
    if (r.width > 560 || k >= MIN_READABLE) { fit(); return }
    const z = [...mp.zones].sort((x, y) => y.members.length - x.members.length)[0]
    const ks = Math.max(k, MIN_READABLE), zx = pt.origin.x + (z ? z.x : 0), zy = pt.origin.y + (z ? z.y : 0)
    view.current = { k: ks, x: 8 - zx * ks, y: 8 - zy * ks }; applyView()
  }, [parts, map, fit, applyView])
  const fitted = useRef(''), lastW = useRef(0)
  useLayoutEffect(() => { const k = p.id + source + (map ? 'm' : ''); if (parts && fitted.current !== k) { fitted.current = k; fitStart() } }, [parts, p.id, source, map, fitStart])
  // un redimensionnement de la largeur recadre la vue ; un simple changement de hauteur (barre d'adresse mobile) ne défait pas le déplacement de l'utilisateur
  useEffect(() => { const el = svgRef.current; if (!el) return; const ro_ = new ResizeObserver(() => { const w = el.getBoundingClientRect().width; if (fitted.current && Math.abs(w - lastW.current) > 4) { lastW.current = w; fitStart() } }); lastW.current = el.getBoundingClientRect().width; ro_.observe(el); return () => ro_.disconnect() }, [fitStart, map])
  const zoomAt = useCallback((f: number, cx?: number, cy?: number) => {
    const el = svgRef.current; if (!el) return
    const r = el.getBoundingClientRect(), v = view.current, px = cx ?? r.width / 2, py = cy ?? r.height / 2
    const k = Math.max(0.05, Math.min(8, v.k * f))
    view.current = { k, x: px - ((px - v.x) / v.k) * k, y: py - ((py - v.y) / v.k) * k }; applyView()
  }, [applyView])
  useEffect(() => {
    const el = svgRef.current; if (!el) return
    const h = (e: WheelEvent) => { e.preventDefault(); const r = el.getBoundingClientRect(); zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top) }
    el.addEventListener('wheel', h, { passive: false }); return () => el.removeEventListener('wheel', h)
  }, [zoomAt, map])

  // ---------- survol et sélection (manipulation directe du DOM : la carte est une chaîne SVG)
  const hover = useCallback((nid: string | null, eid: string | null = null) => {
    const el = svgRef.current; if (!el) return
    el.classList.toggle('bm-dim', !!(nid || eid))
    el.querySelectorAll('.bm-on').forEach(x => x.classList.remove('bm-on'))
    if (!nid && !eid) return
    const keep = new Set<string>(); if (nid) keep.add(nid)
    el.querySelectorAll<SVGElement>('[data-a]').forEach(x => {
      const a = x.getAttribute('data-a')!, b = x.getAttribute('data-b')!
      if ((nid && (a === nid || b === nid)) || (eid && x.getAttribute('data-e') === eid)) { x.classList.add('bm-on'); keep.add(a); keep.add(b) }
    })
    el.querySelectorAll<SVGElement>('[data-n]').forEach(x => { if (keep.has(x.getAttribute('data-n')!)) x.classList.add('bm-on') })
  }, [])
  useLayoutEffect(() => {
    const el = svgRef.current; if (!el) return
    el.querySelectorAll('.bm-sel').forEach(x => x.classList.remove('bm-sel'))
    if (sel) el.querySelectorAll(sel.kind === 'node' ? `[data-n]` : `[data-e]`).forEach(x => { if (x.getAttribute(sel.kind === 'node' ? 'data-n' : 'data-e') === sel.id) x.classList.add('bm-sel') })
  }, [parts, sel])

  // ---------- pointeur : glisser un nœud, déplacer le fond, cliquer
  const gesture = useRef<null | { kind: 'node' | 'pan' | 'edge'; id?: string; sx: number; sy: number; moved: boolean; ox?: number; oy?: number; vx?: number; vy?: number }>(null)
  const toCanvas = (cx: number, cy: number) => {
    const r = svgRef.current!.getBoundingClientRect(), v = view.current
    return { x: (cx - r.left - v.x) / v.k - parts!.origin.x, y: (cy - r.top - v.y) / v.k - parts!.origin.y }
  }
  // pincer (L44) : table des pointeurs actifs ; à deux doigts, rapport des distances → zoomAt, déplacement du milieu → translation ; aucun rendu React par image (applyView agit sur le DOM)
  const ptrs = useRef(new Map<number, { x: number; y: number }>())
  const pinch = useRef<{ d: number; mx: number; my: number } | null>(null)
  const pinched = useRef(false)
  const pinchStep = () => {
    const [a, b] = [...ptrs.current.values()]; const r = svgRef.current!.getBoundingClientRect()
    const d = Math.hypot(a.x - b.x, a.y - b.y) || 1, mx = (a.x + b.x) / 2 - r.left, my = (a.y + b.y) / 2 - r.top
    const last = pinch.current
    if (last) { const v = view.current; view.current = { ...v, x: v.x + (mx - last.mx), y: v.y + (my - last.my) }; zoomAt(d / last.d, mx, my) }
    pinch.current = { d, mx, my }
  }
  const onDown = (e: React.PointerEvent) => {
    if (e.button !== 0 || !map || !parts) return
    ptrs.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (ptrs.current.size >= 2) { gesture.current = null; setDraft(null); pinched.current = true; pinch.current = null; try { svgRef.current!.setPointerCapture(e.pointerId) } catch { /* ignoré */ } pinchStep(); return }
    pinched.current = false
    const tgt = e.target as Element
    const n = tgt.closest('[data-n]'), ed = tgt.closest('[data-e]')
    const base = { sx: e.clientX, sy: e.clientY, moved: false }
    if (n) { const id = n.getAttribute('data-n')!; const nd = map.nodes.find(x => x.id === id)!; gesture.current = { ...base, kind: 'node', id, ox: nd.x, oy: nd.y } }
    else if (ed) gesture.current = { ...base, kind: 'edge', id: ed.getAttribute('data-e')! }
    else gesture.current = { ...base, kind: 'pan', vx: view.current.x, vy: view.current.y }
    svgRef.current!.setPointerCapture(e.pointerId)
  }
  const onMove = (e: React.PointerEvent) => {
    if (ptrs.current.has(e.pointerId)) ptrs.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    if (ptrs.current.size >= 2) { pinchStep(); return }
    const g = gesture.current
    if (!g) {
      const tgt = e.target as Element, n = tgt.closest('[data-n]'), ed = tgt.closest('[data-e]')
      if (n) hover(n.getAttribute('data-n')); else if (ed) hover(null, ed.getAttribute('data-e')); else hover(null)
      return
    }
    const dx = e.clientX - g.sx, dy = e.clientY - g.sy
    if (!g.moved && Math.hypot(dx, dy) < 4) return
    g.moved = true
    if (g.kind === 'pan') { view.current = { ...view.current, x: g.vx! + dx, y: g.vy! + dy }; applyView() }
    else if (g.kind === 'node' && !ro) { const k = view.current.k; setDraft({ [g.id!]: { x: g.ox! + dx / k, y: g.oy! + dy / k } }) }
  }
  const onUp = (e: React.PointerEvent) => {
    ptrs.current.delete(e.pointerId)
    try { svgRef.current!.releasePointerCapture(e.pointerId) } catch { /* ignoré */ }
    if (pinched.current) {   // fin d'un pincement : jamais de sélection ; le doigt restant continue en déplacement de la vue
      pinch.current = null
      const left = [...ptrs.current.entries()][0]
      if (left) gesture.current = { kind: 'pan', sx: left[1].x, sy: left[1].y, moved: true, vx: view.current.x, vy: view.current.y }; else { gesture.current = null; pinched.current = false }
      return
    }
    const g = gesture.current; gesture.current = null
    if (!g || !map) return
    if (g.kind === 'node') {
      if (g.moved && !ro && draft?.[g.id!]) {
        const d = draft[g.id!]
        commit(m => {
          let r = setNode(m, g.id!, { x: Math.round(d.x), y: Math.round(d.y), pinned: true })
          const z = zoneAt(r, d.x, d.y), cur = r.nodes.find(x => x.id === g.id)!.zone
          if (z && z.id !== cur) r = moveToZone(r, g.id!, z.id, false)
          return r
        })
        setDraft(null)
      } else { setDraft(null); setSel({ kind: 'node', id: g.id! }); setTab('insp') }
    } else if (g.kind === 'edge') { if (!g.moved) { setSel({ kind: 'edge', id: g.id! }); setTab('insp') } }
    else if (!g.moved) setSel(null)
  }

  // ---------- propositions du serveur
  const run = async (what: string, fn: () => Promise<unknown>, ok: string) => {
    if (busy) return; setBusy(what)
    try { const res = (await fn()) as { map?: unknown }; if (res?.map) { commit(normalizeMap(res.map), false); toast(ok) } } catch (e) { setError(e as never) } finally { setBusy('') }
  }
  // propositions : d'abord un aperçu (le serveur ne retient rien), puis « Appliquer » rappelle avec apply: true
  type Preview = { kind: 'zones' | 'frames'; strategy?: ZoneStrategy; lines: string[]; warnings: string[] }
  const [preview, setPreview] = useState<Preview | null>(null)
  const ask = async (kind: 'zones' | 'frames', strategy?: ZoneStrategy) => {
    if (busy) return; setBusy(kind)
    try {
      const r = (await (kind === 'zones' ? api.bmSuggestZones(p.id, source, strategy!) : api.bmSuggestFrames(p.id, source))) as { zones?: { title: string; members: string[] }[]; frames?: { title: string; members: string[]; note: string }[]; warnings?: string[] }
      const items = kind === 'zones' ? r.zones ?? [] : r.frames ?? []
      setPreview({ kind, strategy, warnings: r.warnings ?? [], lines: items.map(z => `${z.title} · ${t('bm.prev.n', { n: z.members.length })}${'note' in z && z.note ? ' · ' + z.note : ''}`) })
    } catch (e) { setError(e as never) } finally { setBusy('') }
  }
  const applyPreview = () => { const pv = preview; setPreview(null); if (pv) void run(pv.kind, () => (pv.kind === 'zones' ? api.bmSuggestZones(p.id, source, pv.strategy!, true) : api.bmSuggestFrames(p.id, source, true)), t(pv.kind === 'zones' ? 'bm.done.zones' : 'bm.done.frames')) }
  const suggestZones = (s: ZoneStrategy) => void ask('zones', s)
  const suggestFrames = () => void ask('frames')
  const relayout = () => void run('layout', () => api.bmLayout(p.id, source), t('bm.done.layout'))

  // ---------- export
  const [withLegend, setWithLegend] = useState(true)
  const [expTheme, setExpTheme] = useState<'cur' | 'light' | 'dark'>('light')
  const [exp, setExp] = useState(false)
  const doExport = async (kind: 'svg' | 'png2' | 'png4') => {
    if (!map) return; setExp(false)
    const palX = palette(expTheme === 'cur' ? dark : expTheme === 'dark')
    const name = `carte-metier-${p.name.replace(/[^\w-]+/g, '_')}-${source}`
    const b = buildMapSvg({ map, scenario, pal: palX, t, lang, withLegend, interactive: false }, map.meta.title || p.name)
    try {
      if (kind === 'svg') download(new Blob([b.svg], { type: 'image/svg+xml;charset=utf-8' }), name + '.svg')
      else download(await svgToPng(b.svg, b.w, b.h, kind === 'png4' ? 4 : 2), `${name}@${kind === 'png4' ? 4 : 2}x.png`)
    } catch { setError({ status: 0, message: t('bm.exp.fail') } as never) }
  }
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) { e.preventDefault(); if (!ro) undo() } }
    addEventListener('keydown', k); return () => removeEventListener('keydown', k)
  }, [undo, ro])

  const ctx = { map: map as BMap, ro, sel, setSel, scenario, edit: (f: (m: BMap) => BMap) => commit(f), setActive }
  // ---------- téléphone : recherche qui centre le type, appui long, fiche du bas
  const [q, setQ] = useState(''); const [qOpen, setQOpen] = useState(false); const [longId, setLongId] = useState<string | null>(null)
  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
  const centerOn = useCallback((id: string) => {
    const el = svgRef.current, nd = map?.nodes.find(n => n.id === id); if (!el || !nd || !parts) return
    const r = el.getBoundingClientRect(), k = Math.max(view.current.k, 0.9)
    view.current = { k, x: r.width / 2 - (parts.origin.x + nd.x) * k, y: r.height * 0.3 - (parts.origin.y + nd.y) * k }
    if (!reduced) { const g = vpRef.current; g?.animate?.([{ opacity: 0.6 }, { opacity: 1 }], { duration: 160 }) }
    applyView()
  }, [map, parts, reduced, applyView])
  const hits = useMemo(() => (q.trim() ? (map?.nodes ?? []).filter(n => n.label.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 8) : []), [q, map])
  const pickHit = (id: string) => { setQ(''); setQOpen(false); setSel({ kind: 'node', id }); centerOn(id) }
  const canvasRef = useRef<HTMLDivElement>(null)
  useLongPress(canvasRef, tgt => { const id = tgt.closest('[data-n]')?.getAttribute('data-n'); if (id) { gesture.current = null; setDraft(null); setLongId(id); setSel({ kind: 'node', id }) } }, { enabled: mobile })
  const empty = map && map.nodes.length === 0
  return (
    <div className="bm" data-testid="bmap" data-readonly={ro ? '1' : '0'}>
      <div className="bm-bar" role="toolbar" aria-label={t('bm.toolbar')}>
        <h1 className="bm-h"><Icon name="map" />{t('bm.title')}</h1>
        <Segmented<Source> label={t('bm.source')} value={source} onChange={setSource} items={[['ontology', t('bm.src.ontology')], ['target', t('bm.src.target')]]} />
        {mobile && <div className="msearch bm-search"><Icon name="magnifying-glass" />
          <input type="text" role="combobox" aria-expanded={qOpen && !!hits.length} aria-label={t('bm.search')} placeholder={t('bm.search')} value={q} data-testid="bm-search" enterKeyHint="search"
            onChange={e => { setQ(e.target.value); setQOpen(true) }} onFocus={() => setQOpen(true)} onBlur={() => setTimeout(() => setQOpen(false), 150)} onKeyDown={e => { if (e.key === 'Enter' && hits[0]) pickHit(hits[0].id) }} />
          {qOpen && hits.length > 0 && <ul className="of-hits" role="listbox">{hits.map(h => <li key={h.id}><button type="button" role="option" aria-selected={false} onMouseDown={e => e.preventDefault()} onClick={() => pickHit(h.id)}><Icon name="circle-nodes" />{h.label}</button></li>)}</ul>}</div>}
        <select className="bm-scsel" value={scenario?.id ?? ''} onChange={e => setActive(e.target.value || null)} aria-label={t('bm.sc.active')} data-testid="bm-active">
          <option value="">{t('bm.sc.none')}</option>{map?.scenarios.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <span className="grow" />
        {!ro && <>
          <Button size="sm" icon="object-group" disabled={!map || !!busy} onClick={suggestFrames} data-testid="bm-frames">{t('bm.frames')}</Button>
          <Button size="sm" icon="arrows-up-down-left-right" disabled={!map || !!busy} onClick={relayout} data-testid="bm-layout" title={t('bm.layout.tip')}>{t('bm.layout')}</Button>
          <Button size="sm" icon="rotate-left" disabled={!canUndo} onClick={undo} data-testid="bm-undo" title={t('bm.undo.tip')}>{t('bm.undo')}</Button>
        </>}
        <div className="bm-expwrap">
          <Button size="sm" icon="file-export" disabled={!map} onClick={() => setExp(x => !x)} aria-expanded={exp} data-testid="bm-export">{t('bm.export')}</Button>
          {exp && <div className="bm-menu" role="menu">
            <label className="bm-chk"><input type="checkbox" checked={withLegend} onChange={e => setWithLegend(e.target.checked)} />{t('bm.exp.legend')}</label>
            <label className="bm-lab"><span>{t('bm.exp.theme')}</span><select value={expTheme} onChange={e => setExpTheme(e.target.value as never)}><option value="light">{t('bm.exp.light')}</option><option value="dark">{t('bm.exp.dark')}</option><option value="cur">{t('bm.exp.cur')}</option></select></label>
            <button type="button" role="menuitem" className="btn sm" data-testid="bm-exp-svg" onClick={() => void doExport('svg')}>SVG</button>
            <button type="button" role="menuitem" className="btn sm" data-testid="bm-exp-png2" onClick={() => void doExport('png2')}>{t('bm.exp.png', { n: 2 })}</button>
            <button type="button" role="menuitem" className="btn sm" data-testid="bm-exp-png4" onClick={() => void doExport('png4')}>{t('bm.exp.png', { n: 4 })}</button>
          </div>}
        </div>
        <span className="bm-state muted" role="status">{saving ? t('bm.saving') : ''}</span>
      </div>
      <ErrorView error={error} what={t('bm.title')} />
      {map?.meta.generated && <div className="notice soon bm-gen" role="status" data-testid="bm-generated"><Icon name="wand-magic-sparkles" /> {t('bm.generated')}</div>}
      {map && map.meta.skipped.length > 0 && <div className="notice soon bm-warn" role="status" data-testid="bm-skipped">
        <Icon name="triangle-exclamation" /> {t('bm.warn.skipped', { n: map.meta.skipped.length })}
        <details><summary>{t('bm.warn.skipped.list')}</summary><ul>{map.meta.skipped.map(s => <li key={s.id}>{s.label}</li>)}</ul></details></div>}
      {map && map.meta.unions > 0 && <div className="notice soon bm-warn" role="status" data-testid="bm-unions"><Icon name="triangle-exclamation" /> {t('bm.warn.union', { n: map.meta.unions })}</div>}
      {loading && !map && <Spin />}
      {empty && <Empty title={t('bm.empty.t')}>{t('bm.empty.b')}</Empty>}
      {map && !empty && <div className="bm-body">
        <div className="bm-canvas" data-tour="bmap-canvas" ref={canvasRef}>
          {preview && <div className="bm-preview" role="dialog" aria-label={t('bm.prev.title')} data-testid="bm-preview">
            <b>{t(preview.kind === 'zones' ? 'bm.prev.zones' : 'bm.prev.frames', { n: preview.lines.length })}</b>
            <ul>{preview.lines.slice(0, 12).map((l, i) => <li key={i}>{l}</li>)}</ul>
            {preview.lines.length === 0 && <span className="muted">{t('bm.prev.none')}</span>}
            {preview.warnings.map((w, i) => <div key={i} className="muted">⚠ {w}</div>)}
            <div className="bm-prev-btns"><Button size="sm" variant="primary" disabled={preview.lines.length === 0} onClick={applyPreview} data-testid="bm-preview-apply">{t('common.apply')}</Button><Button size="sm" onClick={() => setPreview(null)}>{t('bm.prev.ignore')}</Button></div>
          </div>}
          <svg ref={svgRef} className="bm-svg" data-testid="bm-svg" role="img" aria-label={t('bm.aria', { n: map.nodes.length })} style={{ background: pal.bg }}
            onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onPointerLeave={() => { if (!gesture.current) hover(null) }}>
            <g ref={vpRef}><g dangerouslySetInnerHTML={{ __html: parts?.inner ?? '' }} transform={`translate(0 0)`} /></g>
          </svg>
          <div className="bm-zoom" role="group" aria-label={t('mo.zoom.group')}>
            <button type="button" onClick={() => zoomAt(1.25)} title={t('mo.zoom.in')} aria-label={t('mo.zoom.in')}>+</button>
            <button type="button" onClick={() => zoomAt(0.8)} title={t('mo.zoom.out')} aria-label={t('mo.zoom.out')}>−</button>
            <button type="button" onClick={fit} title={t('mo.fit.title')} aria-label={t('mo.fit')} data-testid="bm-fit">{t('bm.fit.all')}</button>
            <span className="bm-pct" aria-live="off">{zoomPct}%</span>
          </div>
        </div>
        {!mobile && <aside className="bm-side" aria-label={t('bm.side')}>
          <Tabs value={tab} onChange={setTab} items={ro ? [['insp', t('bm.tab.insp')]] : [['insp', t('bm.tab.insp')], ['zones', t('bm.tab.zones', { n: map.zones.length })], ['scen', t('bm.tab.scen', { n: map.scenarios.length })]]} />
          <div className="bm-pane">
            {tab === 'insp' && <Inspector c={ctx} />}
            {tab === 'zones' && <ZonesPanel c={ctx} suggest={suggestZones} busy={!!busy} />}
            {tab === 'scen' && <ScenariosPanel c={ctx} />}
          </div>
          {ro && <p className="muted bm-ro"><IconButton icon="eye" label={t('head.mobileReadOnly')} />{t('head.mobileReadOnly')}</p>}
        </aside>}
      </div>}
      {mobile && sel && (sel.kind === 'node' && p.onto.classes[sel.id]
        ? <FicheSheet p={p} setP={setP} iri={sel.id} lang={lang} initial={longId === sel.id ? 'half' : 'peek'} onClose={() => { setSel(null); setLongId(null) }}
            onOpen={i => { if (map?.nodes.some(n => n.id === i)) { setSel({ kind: 'node', id: i }); centerOn(i) } }} />
        : <BottomSheet open onClose={() => setSel(null)} title={t('bm.tab.insp')} heading={sel.kind === 'node' ? (selNode?.label ?? '') : (map?.edges.find(e => e.id === sel.id)?.label ?? '')} icon="circle-nodes" initial="half" testid="bm-sheet"><Inspector c={ctx} /></BottomSheet>)}
    </div>
  )
}
