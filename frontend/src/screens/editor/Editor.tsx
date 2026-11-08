import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, MiniMap, useReactFlow, applyNodeChanges, applyEdgeChanges,
  type Node, type Edge, type NodeChange, type EdgeChange, type OnConnectEnd,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api, curie, labelOf, localName, type Project } from '../../api'
import type { ScreenProps } from '../../shell/types'
import { Button, EmptyState, Icon, IconButton, Segmented, useToast } from '../../kit'
import { useI18n, tr } from '../../i18n'
import { autoLayout, NODE_H, NODE_W, toLocalName } from './layout'
import { ClassNode, EdgeDefs, OfEdge, type ClassNodeData, type OfEdgeData } from './parts'
import { Inspector } from './Inspector'
import { VNode, vsize, type VNodeData } from './vowl'
import { buildView, type MNode, type ViewModel } from './view'
import { DEFAULT_SHOW, KEYS, lsGet, readShow, useStored, type LegendState, type Mode, type ShowPrefs } from './prefs'
import { Legend } from './Legend'
import { legendFlags } from './legendDefs'
import { ExportMenu, ShowMenu } from './ShowMenu'
import { resolvePal } from './glyphs'
import { buildSvg, download, svgToPng } from './exporter'
import { Tree } from './Tree'
import { QuickInput } from './QuickInput'
import { useAssistantContext } from '../../lib/assistantContext'
import { acceptAll, acceptItem, bindProjectSetter, rejectAll, rejectItem, useProposal } from '../../lib/proposal'
import { eapi, type GraphData, type Op, type OpResult, type ProposalItem, type Sel } from './types'
import './editor.css'

const nodeTypes = { cls: ClassNode, vn: VNode }
const edgeTypes = { of: OfEdge }
const MARKER: Record<string, string> = { subClassOf: 'of-hollow', objectProperty: 'of-solid' }
// VOWL : l'espacement de la disposition (pensée pour des rectangles de 196 × 52) est élargi pour laisser de la place aux cercles et aux libellés d'arêtes
const SX = 1.0, SY = 1.65
const VOWL_INCLUDE = 'datatypes,external,anonymous,thing'
type EdgeFilter = 'isa' | 'rel' | 'all'
const serMode = (m: Mode) => m
const serLegend = (s: LegendState) => s
const serShow = (s: ShowPrefs) => JSON.stringify(s)

function useMedia(q: string) {
  const [m, setM] = useState(() => matchMedia(q).matches)
  useEffect(() => { const mq = matchMedia(q); const f = () => setM(mq.matches); mq.addEventListener('change', f); return () => mq.removeEventListener('change', f) }, [q])
  return m
}
const isField = (el: EventTarget | null) => el instanceof HTMLElement && ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)

export type EditorProps = ScreenProps
/** Écran « Ontologie » : éditeur graphique. La proposition de l'assistant (store lib/proposal.ts, L10) est affichée en surbrillance. */
export function OntologyEditor(props: EditorProps) {
  return <ReactFlowProvider><Inner {...props} /></ReactFlowProvider>
}
export function Editor(props: ScreenProps) { return <OntologyEditor {...props} /> }

function Inner({ p, setP }: EditorProps) {
  const store = useProposal()
  const { t, lang: uiLang } = useI18n()
  const toast = useToast()
  const rf = useReactFlow()
  const readOnly = useMedia('(max-width: 767px)')
  const wrap = useRef<HTMLDivElement>(null)

  const [lang, setLang] = useState(uiLang)
  const [peri, setPeri] = useState<string>((p as Project & { active_perimeter?: string | null }).active_perimeter ?? '')
  const [periName, setPeriName] = useState('')
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [mode, setMode] = useStored<Mode>(KEYS.mode, () => (lsGet(KEYS.mode) === 'vowl' ? 'vowl' : 'classic'), serMode)
  // légende ouverte au premier usage (Jerem ne la trouvait pas) ; repliée sur écran étroit pour ne pas couvrir le graphe ; ensuite, le dernier choix est mémorisé
  const [legend, setLegend] = useStored<LegendState>(KEYS.legend, () => { const v = lsGet(KEYS.legend); return v === 'open' || v === 'folded' || v === 'closed' ? v : (typeof window !== 'undefined' && window.innerWidth < 900 ? 'folded' : 'open') }, serLegend)
  // cadrage : la légende ouverte (330 px, en surimpression à droite) ne doit pas masquer de nœud après « ajuster la vue »
  const fitPad = legend === 'open' && typeof window !== 'undefined' && window.innerWidth >= 768 ? { top: '6%', bottom: '6%', left: '4%', right: '350px' } as const : 0.12
  const [showStored, setShowStored] = useStored<ShowPrefs>(KEYS.show, readShow, serShow)
  const [chosen, setChosen] = useState(() => lsGet(KEYS.show) !== null)
  const setShow = useCallback((s: ShowPrefs) => { setChosen(true); setShowStored(s) }, [setShowStored])
  const [shown, setShown] = useState<{ vm: ViewModel; total: { n: number; m: number } } | null>(null)
  const vowl = mode === 'vowl'
  // sans choix mémorisé, les types de données ne s'affichent d'emblée que sur un graphe assez petit pour rester lisible (au-delà : case « Propriétés de données »)
  const nClasses = graph?.nodes.filter(n => n.kind === 'class').length ?? 0
  const show = useMemo<ShowPrefs>(() => (chosen ? showStored : { ...showStored, dt: nClasses <= 16 }), [chosen, showStored, nClasses])
  const filter: EdgeFilter | '' = show.sub && show.rel && show.disj ? 'all' : show.sub && !show.rel && !show.disj ? 'isa' : !show.sub && show.rel && !show.disj ? 'rel' : ''
  const setFilter = (f: EdgeFilter) => setShow({ ...show, sub: f !== 'rel', rel: f !== 'isa', disj: f === 'all' })
  const satRef = useRef(new Map<string, { owner: string; dx: number; dy: number; w: number; h: number }>())
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [sel, setSel] = useState<Sel>(null)
  useAssistantContext({
    screen: 'editor', projectId: p.id, perimeter: peri || null,
    selection: sel ? { kind: sel.kind === 'class' ? 'class' : 'prop', id: sel.iri, label: labelOf((p.onto.classes[sel.iri] ?? p.onto.object_properties[sel.iri] ?? p.onto.datatype_properties[sel.iri]) as never, sel.iri, uiLang) } : null,
  }, [peri, sel?.iri, p.updated_at])
  const [selIds, setSelIds] = useState<Set<string>>(new Set())
  const [inspPref, setInspPref] = useState<boolean | null>(null)
  const [treeOpen, setTreeOpen] = useState(() => innerWidth >= 1100)
  const [dslOpen, setDslOpen] = useState(false)
  const [creating, setCreating] = useState<{ fx: number; fy: number; sx: number; sy: number } | null>(null)
  const [newName, setNewName] = useState('')
  const [renaming, setRenaming] = useState<string | null>(null)
  const [pendingDel, setPendingDel] = useState<{ ops: Op[]; text: string } | null>(null)
  const [menu, setMenu] = useState<{ src: string; tgt: string; x: number; y: number; step: 'choose' | 'name' } | null>(null)
  const [propName, setPropName] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const [errIris, setErrIris] = useState<Set<string>>(new Set())
  const [can, setCan] = useState({ undo: false, redo: false })
  const [q, setQ] = useState(''); const [qOpen, setQOpen] = useState(false)
  const [periForm, setPeriForm] = useState<{ name: string; desc: boolean } | null>(null)

  const posRef = useRef(new Map<string, { x: number; y: number }>())
  const pending = useRef(new Map<string, { x: number; y: number }>())
  const moveTimer = useRef<ReturnType<typeof setTimeout>>()
  const pendingSel = useRef<string | null>(null)
  const fitted = useRef(false)
  const pid = p.id

  // ---------- langue des labels, périmètre actif ----------
  useEffect(() => { api.settings().then(s => { const l = s.language?.labels; if (l === 'fr' || l === 'en') setLang(l) }).catch(() => {}) }, [])
  useEffect(() => { const f = (e: Event) => setPeri((e as CustomEvent<string>).detail ?? ''); addEventListener('of:perimeter', f); return () => removeEventListener('of:perimeter', f) }, [])
  useEffect(() => { if (!peri) { setPeriName(''); return } api.perimeters(pid).then(l => setPeriName(l.find(x => x.id === peri)?.name ?? '')).catch(() => setPeriName('')) }, [peri, pid])
  useEffect(() => { eapi.history(pid).then(h => setCan({ undo: h.can_undo, redo: h.can_redo })).catch(() => {}) }, [pid])

  // ---------- graphe ----------
  useEffect(() => {
    let live = true
    eapi.graph(pid, peri, lang, vowl ? VOWL_INCLUDE : '').then(g => { if (live) setGraph(g) }).catch(e => { if (live) toast((e as Error).message) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid, p.updated_at, peri, lang, vowl])
  useEffect(() => { fitted.current = false }, [mode])

  // proposition de l'assistant : éléments du store convertis (+ arêtes des sous-classes portées par l'ajout d'une classe)
  useEffect(() => { bindProjectSetter(setP); return () => bindProjectSetter(null) }, [setP])
  const visibleItems = useMemo<ProposalItem[]>(() => {
    if (!store || store.projectId !== pid) return []
    const out: ProposalItem[] = []
    for (const i of store.items) {
      out.push({ key: i.id, status: i.kind, kind: i.type, iri: i.entity_iri, label: i.label, detail: i.detail, ops: i.ops, source: i.source, target: i.target })
      if (i.type === 'class' && i.kind === 'add') for (const o of i.ops) if (o.op === 'add_subclass' && typeof o.parent === 'string')
        out.push({ key: `${i.id}>${o.parent}`, status: 'add', kind: 'subClassOf', iri: i.entity_iri, label: i.label, source: i.entity_iri, target: o.parent, ops: [] })
    }
    return out
  }, [store, pid])
  useEffect(() => { if (store?.error && store.projectId === pid) { setErrors([store.error]); toast(store.error) } }, [store?.error, store?.projectId, pid, toast])

  // reconstruit nœuds et arêtes quand le graphe, les filtres ou la proposition changent
  useEffect(() => {
    if (!graph) return
    const pf = p.onto.meta.prefixes || {}
    const ghostClass = visibleItems.filter(i => i.kind === 'class' && i.status === 'add' && !graph.nodes.some(n => n.id === i.iri))
    const ids = [...graph.nodes.filter(n => n.kind === 'class').map(n => n.id), ...ghostClass.map(i => i.iri)]
    // positions : celles du serveur d'abord, puis le cache de session, puis disposition automatique
    for (const n of graph.nodes) if (n.kind === 'class' && n.position && !pending.current.has(n.id)) posRef.current.set(n.id, n.position)
    for (const k of [...posRef.current.keys()]) if (!ids.includes(k)) posRef.current.delete(k)
    const missing = ids.filter(i => !posRef.current.has(i))
    if (missing.length) {
      const isa: [string, string][] = [...graph.edges.filter(e => e.kind === 'subClassOf').map(e => [e.source, e.target] as [string, string]), ...visibleItems.filter(i => i.kind === 'subClassOf').map(i => [i.source!, i.target!] as [string, string])]
      const rel: [string, string][] = graph.edges.filter(e => e.kind === 'objectProperty').map(e => [e.source, e.target])
      const lay = autoLayout(ids, isa, rel)
      const taken = [...posRef.current.values()]
      for (const m of missing) {
        const pos = { ...lay.get(m)! }
        const parent = isa.find(([c]) => c === m)?.[1]
        if (taken.length && parent && posRef.current.has(parent) && missing.length < ids.length / 2) { const pp = posRef.current.get(parent)!; pos.x = pp.x; pos.y = pp.y + NODE_H + 70 }
        while (taken.some(o => Math.abs(o.x - pos.x) < NODE_W + 12 && Math.abs(o.y - pos.y) < NODE_H + 16)) pos.x += NODE_W + 24
        posRef.current.set(m, pos); taken.push(pos)
      }
    }
    const modClasses = new Set(visibleItems.filter(i => i.status === 'modify' && i.kind === 'class').map(i => i.iri))
    visibleItems.filter(i => i.kind === 'datatypeProperty' && i.source && graph.nodes.some(n => n.id === i.source)).forEach(i => modClasses.add(i.source!))
    const onRename = (iri: string, text: string | null) => {
      setRenaming(null)
      const cur = p.onto.classes[iri]
      if (text && text !== labelOf(cur, iri, lang)) apply([{ op: 'set_label', iri, text, lang }])
    }
    const pk = new Map(visibleItems.filter(i => i.kind === 'class' && i.ops.length).map(i => [i.iri, i.key]))
    const onProposal = (key: string, ok: boolean) => { if (ok) acceptItem(key); else rejectItem(key) }
    const modProps = new Set(visibleItems.filter(i => i.status === 'modify' && i.kind === 'objectProperty').map(i => i.iri))
    const ghostEdges = visibleItems.filter(i => i.status === 'add' && (i.kind === 'subClassOf' || i.kind === 'objectProperty') && i.source && i.target)
    const vin = { graph, ghostClasses: ghostClass, ghostEdges, mode, show, modClasses, modProps, keep: selIds, declared: (i: string) => !!p.onto.classes[i] }
    const vm = buildView(vin)
    const all = buildView({ ...vin, show: { ...DEFAULT_SHOW, krakie: true }, keep: new Set() })

    // ---- nœuds ----
    const center = (id: string) => { const q = posRef.current.get(id)!; return { x: (q.x + NODE_W / 2) * (vowl ? SX : 1), y: (q.y + NODE_H / 2) * (vowl ? SY : 1) } }
    const sizes = new Map<string, ReturnType<typeof vsize>>(vm.nodes.map(n => [n.id, vsize(n)]))
    // satellites (types de données, Thing, classes anonymes) : rangés sous leur classe porteuse
    satRef.current.clear()
    const byOwner = new Map<string, MNode[]>()
    for (const n of vm.nodes) if (n.vk !== 'class' && n.owner && posRef.current.has(n.owner)) byOwner.set(n.owner, [...(byOwner.get(n.owner) ?? []), n])
    for (const [owner, sats] of byOwner) {
      const r = (sizes.get(owner)?.h ?? 96) / 2
      sats.sort((a, b) => a.vk.localeCompare(b.vk) || a.id.localeCompare(b.id))
      // éventail sous la classe : les types de données s'écartent assez pour que leurs libellés d'arête ne se recouvrent pas
      const n = sats.length
      const FAN: Record<number, number[]> = { 1: [0], 2: [-34, 34], 3: [-50, 0, 50], 4: [-62, -22, 22, 62] }
      sats.forEach((sat, i) => {
        const z = sizes.get(sat.id)!
        const ring = n > 4 ? Math.floor(i / 4) : 0, k = n > 4 ? i % 4 : i, cnt = n > 4 ? Math.min(4, n - ring * 4) : n
        const ang = ((FAN[cnt] ?? FAN[4])[k] * Math.PI) / 180
        const R = r + 60 + z.h / 2 + ring * 52
        satRef.current.set(sat.id, { owner, dx: R * Math.sin(ang) * 1.25, dy: R * Math.cos(ang), w: z.w, h: z.h })
      })
    }
    const ns: Node[] = vm.nodes.flatMap((n): Node[] => {
      if (n.vk !== 'class' && !satRef.current.has(n.id)) return []
      const err = errIris.has(n.id)
      if (!vowl) {
        const q = posRef.current.get(n.id)!
        return [{
          id: n.id, type: 'cls', position: q, selected: selIds.has(n.id), draggable: !readOnly && !n.status,
          data: { label: n.label, curie: curie(n.id, pf), icon: n.icon, abstract: n.abstract, deprecated: n.deprecated, status: n.status, error: err, readOnly: readOnly || !!n.status, editing: renaming === n.id, onRename, pkey: pk.get(n.id), onProposal, hid: n.hid } satisfies ClassNodeData,
        }]
      }
      const z = sizes.get(n.id)!
      const sat = satRef.current.get(n.id)
      const c = sat ? (() => { const o = center(sat.owner); return { x: o.x + sat.dx, y: o.y + sat.dy } })() : center(n.id)
      const isClass = n.vk === 'class'
      return [{
        id: n.id, type: 'vn', position: { x: c.x - z.w / 2, y: c.y - z.h / 2 }, width: z.w, height: z.h, style: { width: z.w, height: z.h },
        selected: isClass && selIds.has(n.id), selectable: isClass, focusable: isClass, connectable: isClass && n.declared && !readOnly, draggable: isClass && n.declared && !readOnly && !n.status,
        data: { vk: n.vk, label: n.label, curie: curie(n.id, pf), abstract: n.abstract, deprecated: n.deprecated, external: n.external, merged: n.merged, op: n.op, status: n.status, error: err,
          readOnly: readOnly || !!n.status || !n.declared, editing: renaming === n.id && n.declared, onRename, pkey: pk.get(n.id), onProposal, hid: n.hid, shape: z.shape } satisfies VNodeData,
      }]
    })
    const es: Edge[] = vm.edges.map(e => {
      const own = e.kind === 'datatypeProperty' || e.kind === 'anonymousOf'
      const hollow = e.status === 'add' ? 'of-hollow-add' : vowl ? 'v-hollow' : MARKER.subClassOf
      const solid = e.status === 'add' ? 'of-solid-add' : vowl ? 'v-solid' : MARKER.objectProperty
      return {
        id: e.id, source: e.source, target: e.target, type: 'of', selected: sel?.kind === 'prop' && e.iri === sel.iri, deletable: false, selectable: !own,
        markerEnd: e.kind === 'subClassOf' ? hollow : e.kind === 'objectProperty' || e.kind === 'datatypeProperty' ? solid : undefined,
        markerStart: vowl && e.inverse ? solid : undefined,
        data: { kind: e.kind, label: e.label, inverse: e.inverse, offset: e.offset, status: e.status, iri: e.iri, err: !!(e.iri && errIris.has(e.iri)), vowl, chars: e.chars, deprecated: e.deprecated } satisfies OfEdgeData & { iri: string | null },
      }
    })
    setShown({ vm, total: { n: all.nodes.length, m: all.edges.length } })
    setNodes(ns); setEdges(es)
    if (!fitted.current && ns.length) { fitted.current = true; setTimeout(() => rf.fitView({ padding: fitPad, maxZoom: 1, minZoom: 0.3 }), 50) }
    if (pendingSel.current) { const f = ns.find(n => localName(n.id) === pendingSel.current); if (f) { pendingSel.current = null; setTimeout(() => selectClass(f.id, false), 0) } }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, mode, show, visibleItems, readOnly, errIris, renaming, lang])

  // ---------- opérations ----------
  const flash = useCallback((ids: string[]) => { setErrIris(new Set(ids)); setTimeout(() => setErrIris(new Set()), 6000) }, [])
  const handle = useCallback((r: OpResult, ops: Op[]) => {
    setCan({ undo: r.can_undo, redo: r.can_redo })
    if (r.ok) { setErrors([]); setP(r.project); if (r.warnings?.length) toast(r.warnings[0]); return true }
    const msgs = r.errors.map(e => e.message)
    setErrors(msgs); toast(msgs[0] + (msgs.length > 1 ? ` (+${msgs.length - 1})` : ''))
    flash(r.errors.flatMap(e => { const o = ops[e.index]; return o ? [o.iri, o.parent, o.other, o.domain, o.range, o.property].flat().filter((x): x is string => typeof x === 'string') : [] }))
    return false
  }, [setP, toast, flash])
  const apply = useCallback(async (ops: Op[], label?: string) => {
    try { return handle(await eapi.ops(pid, ops, label), ops) } catch (e) { toast((e as Error).message); return false }
  }, [pid, handle, toast])
  const undoRedo = useCallback(async (kind: 'undo' | 'redo') => {
    try { const r = await (kind === 'undo' ? eapi.undo(pid) : eapi.redo(pid)); setCan({ undo: r.can_undo, redo: r.can_redo }); setP(r.project); setErrors([]); posRef.current.clear(); toast(t(kind === 'undo' ? 'ed.undone' : 'ed.redone', { label: r.label ?? '' })) }
    catch (e) { toast((e as Error).message) }
  }, [pid, setP, toast, t])
  const flushMoves = useCallback(() => {
    clearTimeout(moveTimer.current)
    const ops: Op[] = [...pending.current].filter(([iri]) => !!p.onto.classes[iri]).map(([iri, { x, y }]) => ({ op: 'move_node', iri, x: Math.round(x), y: Math.round(y) }))
    if (!ops.length) return
    pending.current.clear()
    eapi.ops(pid, ops, tr('hist.deplacer')).then(r => { setCan({ undo: r.can_undo, redo: r.can_redo }); if (r.ok) setP(r.project) }).catch(() => {})
  }, [pid, setP, p.onto.classes])
  useEffect(() => () => flushMoves(), [flushMoves])

  // ---------- sélection ----------
  const selectClass = useCallback((iri: string, additive: boolean) => {
    setNodes(ns => ns.map(n => ({ ...n, selected: n.id === iri ? true : additive ? n.selected : false })))
    setEdges(es => es.map(e => ({ ...e, selected: false })))
    const n = rf.getNode(iri)
    if (n) rf.setCenter(n.position.x + NODE_W / 2, n.position.y + NODE_H / 2, { zoom: Math.max(rf.getZoom(), 0.9), duration: 350 })
  }, [rf])
  const selectProp = useCallback((iri: string) => {
    setSel({ kind: 'prop', iri }); setInspPref(null)
    setNodes(ns => ns.map(n => ({ ...n, selected: false })))
    setEdges(es => es.map(e => ({ ...e, selected: (e.data as { iri?: string } | undefined)?.iri === iri })))
  }, [])
  const onSelectionChange = useCallback(({ nodes: ns, edges: es }: { nodes: Node[]; edges: Edge[] }) => {
    const ids = new Set(ns.map(n => n.id))
    setSelIds(prev => (prev.size === ids.size && [...ids].every(i => prev.has(i)) ? prev : ids))
    if (ns.length === 1 && !es.length) { if (p.onto.classes[ns[0].id]) { setSel({ kind: 'class', iri: ns[0].id }); setInspPref(null) } }
    else if (!ns.length && es.length === 1) { const iri = (es[0].data as { iri?: string }).iri; if (iri && p.onto.object_properties[iri]) { setSel({ kind: 'prop', iri }); setInspPref(null) } else setSel(null) }
    else if (!ns.length && !es.length) setSel(s => (s?.kind === 'prop' ? s : null))
    else setSel(null)
  }, [p.onto])

  // ---------- suppression ----------
  const requestDelete = useCallback((iris?: string[]) => {
    if (readOnly) return
    const ops: Op[] = []; let nc = 0, nr = 0
    const targets = iris ?? [...selIds]
    for (const i of targets) { ops.push({ op: 'delete_entity', iri: i }); if (p.onto.classes[i]) nc++; else nr++ }
    if (!iris) for (const e of edges.filter(x => x.selected)) {
      const d = e.data as unknown as OfEdgeData & { iri: string | null }
      if (d.kind === 'subClassOf') { ops.push({ op: 'remove_subclass', iri: e.source, parent: e.target }); nr++ }
      else if (d.kind === 'disjointWith') { ops.push({ op: 'remove_disjoint', iri: e.source, other: e.target }); nr++ }
      else if (d.kind === 'objectProperty' && d.iri && !ops.some(o => o.iri === d.iri)) { ops.push({ op: 'delete_entity', iri: d.iri }); nr++ }
    }
    if (!ops.length) return
    setPendingDel({ ops, text: t('ed.confirm.del', { c: nc, r: nr }) })
  }, [readOnly, selIds, edges, p.onto, t])
  useEffect(() => { const f = (e: Event) => requestDelete((e as CustomEvent<string[]>).detail); addEventListener('of:delete', f); return () => removeEventListener('of:delete', f) }, [requestDelete])

  const onKeyDown = (e: KeyboardEvent) => {
    if (isField(e.target) || (e.target as HTMLElement)?.closest?.('[role=dialog]')) return
    const mod = e.ctrlKey || e.metaKey
    if (mod && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); if (!readOnly) undoRedo('undo') }
    else if (mod && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) { e.preventDefault(); if (!readOnly) undoRedo('redo') }
    else if (e.key === 'Delete') { e.preventDefault(); requestDelete() }
    else if (e.key === 'F2' && sel?.kind === 'class' && !readOnly) { e.preventDefault(); setRenaming(sel.iri) }
    else if (e.key === 'Escape') { setCreating(null); setMenu(null); setPendingDel(null); setPeriForm(null) }
  }

  const keyRef = useRef(onKeyDown); keyRef.current = onKeyDown
  useEffect(() => { const f = (e: KeyboardEvent) => keyRef.current(e); addEventListener('keydown', f); return () => removeEventListener('keydown', f) }, [])

  // ---------- gestes ----------
  const rel = (cx: number, cy: number) => { const r = wrap.current!.getBoundingClientRect(); return { x: cx - r.left, y: cy - r.top } }
  const startCreate = (cx?: number, cy?: number) => {
    if (readOnly) return
    const r = wrap.current!.getBoundingClientRect()
    const x = cx ?? r.left + r.width / 2 - NODE_W / 2, y = cy ?? r.top + r.height / 2 - 20
    const f = rf.screenToFlowPosition({ x, y }); const s = rel(x, y)
    setNewName(''); setCreating({ fx: f.x - NODE_W / 2, fy: f.y - NODE_H / 2, sx: s.x, sy: s.y })
  }
  const submitCreate = async () => {
    const label = newName.trim(); const c = creating
    if (!label || !c) { setCreating(null); return }
    const name = toLocalName(label)
    pendingSel.current = name
    setCreating(null)
    const ok = await apply([{ op: 'add_class', name, label, lang, x: Math.round(c.fx), y: Math.round(c.fy) }], tr('hist.nouvelle_classe'))
    if (!ok) pendingSel.current = null
  }
  const onConnectEnd: OnConnectEnd = (ev, st) => {
    if (readOnly || !st.fromNode) return
    const pt = 'changedTouches' in ev ? ev.changedTouches[0] : (ev as MouseEvent)
    const el = document.elementFromPoint(pt.clientX, pt.clientY)?.closest('.react-flow__node') as HTMLElement | null
    const tgt = el?.dataset.id
    if (!tgt || !p.onto.classes[tgt] || !p.onto.classes[st.fromNode.id]) return
    const r = rel(pt.clientX, pt.clientY)
    setPropName(''); setMenu({ src: st.fromNode.id, tgt, x: r.x, y: r.y, step: 'choose' })
  }
  const lbl = (iri: string) => labelOf(p.onto.classes[iri], iri, lang)
  const applyMenu = async (kind: 'sub' | 'disj') => {
    if (!menu) return; const m = menu; setMenu(null)
    await apply([kind === 'sub' ? { op: 'add_subclass', iri: m.src, parent: m.tgt } : { op: 'add_disjoint', iri: m.src, other: m.tgt }])
  }
  const submitProp = async () => {
    if (!menu || !propName.trim()) return; const m = menu; setMenu(null)
    const name = toLocalName(propName).replace(/^./, s => s.toLowerCase())
    await apply([{ op: 'add_object_property', name, label: propName.trim(), lang, domain: m.src, range: m.tgt }], tr('hist.nouvelle_propriete'))
  }
  const relayout = async () => {
    if (!graph) return
    const ids = graph.nodes.filter(n => n.kind === 'class').map(n => n.id)
    const lay = autoLayout(ids, graph.edges.filter(e => e.kind === 'subClassOf').map(e => [e.source, e.target]), graph.edges.filter(e => e.kind === 'objectProperty').map(e => [e.source, e.target]))
    lay.forEach((v, k) => posRef.current.set(k, v))
    setNodes(ns => ns.map(n => { const v = lay.get(n.id); if (!v) return n; return { ...n, position: vowl ? { x: (v.x + NODE_W / 2) * SX - (n.width ?? 96) / 2, y: (v.y + NODE_H / 2) * SY - (n.height ?? 96) / 2 } : v } }))
    setTimeout(() => rf.fitView({ padding: fitPad, maxZoom: 1, minZoom: 0.3, duration: 300 }), 30)
    await apply([...lay].filter(([iri]) => !!p.onto.classes[iri]).map(([iri, v]) => ({ op: 'move_node', iri, x: v.x, y: v.y })), tr('hist.reorganiser'))
  }
  const createPerimeter = async () => {
    if (!periForm?.name.trim()) return
    try {
      const per = await eapi.createPerimeter(pid, { name: periForm.name.trim(), classes: [...selIds], properties: [], include_descendants: periForm.desc })
      await eapi.setActive(pid, per.id)
      setPeriForm(null); setPeri(per.id); dispatchEvent(new CustomEvent('of:perimeter', { detail: per.id })); dispatchEvent(new Event('of:perimeters'))
      toast(t('ed.peri.created', { name: per.name }))
    } catch (e) { toast((e as Error).message) }
  }

  // ---------- proposition ----------
  const accept = (its: ProposalItem[]) => (its.length === visibleItems.filter(i => i.ops.length).length && its.length > 1 ? acceptAll() : Promise.all(its.map(i => acceptItem(i.key))))
  const reject = (its: ProposalItem[]) => (its.length > 1 ? rejectAll() : its.forEach(i => rejectItem(i.key)))
  const listed = visibleItems.filter(i => i.ops.length)

  // ---------- recherche ----------
  const hits = useMemo(() => q.trim() ? (graph?.nodes ?? []).filter(n => n.label.toLowerCase().includes(q.toLowerCase()) || localName(n.id).toLowerCase().includes(q.toLowerCase())).slice(0, 8) : [], [q, graph])
  const goTo = (iri: string) => { setQ(''); setQOpen(false); selectClass(iri, false) }

  /** Position de l'écran → coordonnées classiques mémorisées (le VOWL élargit l'espacement et ancre les cercles par leur centre). */
  const toClassic = (n: Node) => vowl
    ? { x: (n.position.x + (n.width ?? 96) / 2) / SX - NODE_W / 2, y: (n.position.y + (n.height ?? 96) / 2) / SY - NODE_H / 2 }
    : n.position
  /** Pendant un déplacement, les satellites d'une classe (types de données, Thing, classes anonymes) la suivent. */
  const followSats = (dragged: Node[]) => {
    const moved = new Map(dragged.map(n => [n.id, { x: n.position.x + (n.width ?? 96) / 2, y: n.position.y + (n.height ?? 96) / 2 }]))
    setNodes(ns => ns.map(n => { const sat = satRef.current.get(n.id); const c = sat && moved.get(sat.owner); return c && sat ? { ...n, position: { x: c.x + sat.dx - sat.w / 2, y: c.y + sat.dy - sat.h / 2 } } : n }))
  }
  const onNodesChange = useCallback((c: NodeChange[]) => setNodes(ns => applyNodeChanges(c, ns)), [])
  const onEdgesChange = useCallback((c: EdgeChange[]) => setEdges(es => applyEdgeChanges(c, es)), [])
  const inspOpen = inspPref ?? !!sel
  const classNodes = graph?.nodes.filter(n => n.kind === 'class') ?? []
  const empty = !!graph && !classNodes.length && !listed.length
  const hint = sel?.kind === 'class' ? localName(sel.iri) : null
  const propsList = Object.values(p.onto.object_properties).map(o => ({ iri: o.iri, label: labelOf(o, o.iri, lang) })).sort((a, b) => a.label.localeCompare(b.label))

  const doExport = async (fmt: 'svg' | 'png', withLegend: boolean) => {
    if (!shown) return
    try {
      const root = wrap.current?.closest('.ed') ?? document.body
      const out = buildSvg({ nodes: rf.getNodes(), edges: rf.getEdges(), mode, pal: resolvePal(root), t, flags: legendFlags(shown.vm), withLegend, title: p.name || 'OntoForge' })
      const base = `${(p.name || 'ontologie').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase() || 'ontologie'}-${mode}`
      if (fmt === 'svg') download(new Blob([out.svg], { type: 'image/svg+xml;charset=utf-8' }), `${base}.svg`)
      else download(await svgToPng(out.svg, out.w, out.h), `${base}.png`)
      toast(t('ed.exp.done', { f: fmt.toUpperCase() }))
    } catch (e) { toast((e as Error).message) }
  }

  return (
    <div className={'ed' + (readOnly ? ' ro' : '') + (vowl ? ' vowl' : '')}>
      <div className="of-bar" role="toolbar" aria-label={t('ed.toolbar')}>
        {!treeOpen && <IconButton icon="angles-right" label={t('ed.tree.show')} onClick={() => setTreeOpen(true)} />}
        <div className="of-search">
          <Icon name="magnifying-glass" />
          <input type="text" role="combobox" aria-expanded={qOpen && !!hits.length} aria-label={t('ed.search')} placeholder={t('ed.search')} value={q}
            onChange={e => { setQ(e.target.value); setQOpen(true) }} onFocus={() => setQOpen(true)} onBlur={() => setTimeout(() => setQOpen(false), 150)}
            onKeyDown={e => { if (e.key === 'Enter' && hits[0]) goTo(hits[0].id) }} />
          {qOpen && hits.length > 0 && <ul className="of-hits" role="listbox">{hits.map(h => <li key={h.id}><button type="button" role="option" aria-selected={false} onMouseDown={e => e.preventDefault()} onClick={() => goTo(h.id)}><Icon name={h.icon || 'circle-nodes'} />{h.label}</button></li>)}</ul>}
        </div>
        <Segmented<EdgeFilter> label={t('ed.filter')} value={filter as EdgeFilter} onChange={setFilter} items={[['isa', t('ed.filter.isa')], ['rel', t('ed.filter.rel')], ['all', t('ed.filter.all')]]} />
        <Segmented<Mode> label={t('ed.mode')} value={mode} onChange={setMode} items={[['classic', t('ed.mode.classic')], ['vowl', t('ed.mode.vowl')]]} />
        <ShowMenu mode={mode} show={show} setShow={setShow} collapsed={shown?.vm.collapsed ?? 0} />
        {shown && <span className="of-count muted" data-testid="counter" role="status">{t('ed.count', { n: shown.vm.nodes.length, m: shown.vm.edges.length, tn: shown.total.n, tm: shown.total.m })}</span>}
        <Button size="sm" icon="wand-magic" onClick={relayout} disabled={readOnly || !classNodes.length}>{t('ed.relayout')}</Button>
        <span className="grow" />
        {periName && <span className="of-periflag" title={t('ed.peri.active')}><Icon name="crop-simple" />{periName}</span>}
        {!readOnly && <>
          <Button size="sm" icon="plus" variant="primary" onClick={() => startCreate()}>{t('ed.newclass')}</Button>
          <IconButton icon="rotate-left" label={t('ed.undo') + ' (Ctrl+Z)'} disabled={!can.undo} onClick={() => undoRedo('undo')} />
          <IconButton icon="rotate-right" label={t('ed.redo') + ' (Ctrl+Y)'} disabled={!can.redo} onClick={() => undoRedo('redo')} />
          <Button size="sm" icon="crop-simple" disabled={!selIds.size} onClick={() => setPeriForm({ name: '', desc: false })} title={t('ed.peri.fromsel')}>{t('ed.peri.fromsel')}</Button>
        </>}
        {sel === null && !readOnly && <IconButton icon={inspOpen ? 'angles-right' : 'sliders'} label={t(inspOpen ? 'ed.insp.close' : 'ed.insp.open')} onClick={() => setInspPref(inspOpen ? false : true)} aria-pressed={inspOpen} />}
      </div>

      <div className="of-body">
        {treeOpen && <Tree nodes={graph?.nodes ?? []} edges={graph?.edges ?? []} selected={selIds} props={propsList}
          onSelect={(i, add) => selectClass(i, add)} onSelectProp={selectProp} onClose={() => setTreeOpen(false)} />}

        <div className="of-canvas" ref={wrap} tabIndex={-1} data-tour="ed-canvas">
          <EdgeDefs />
          <div className="of-cvtools">
            <Button size="sm" icon="circle-info" aria-pressed={legend !== 'closed'} data-testid="legend-btn" data-tour="ed-legend-btn" onClick={() => setLegend(legend === 'closed' ? 'open' : 'closed')}>{t('lg.btn')}</Button>
            <ExportMenu onExport={doExport} disabled={!nodes.length} />
          </div>
          {shown && <Legend mode={mode} flags={legendFlags(shown.vm)} state={legend} setState={setLegend} />}
          <ReactFlow
            nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onSelectionChange={onSelectionChange}
            nodesDraggable={!readOnly} nodesConnectable={!readOnly} elementsSelectable
            deleteKeyCode={null} zoomOnDoubleClick={false} minZoom={0.15} maxZoom={2.2}
            multiSelectionKeyCode={['Control', 'Meta']} selectionKeyCode="Shift"
            onNodeDrag={(_, __, dragged) => { if (vowl) followSats(dragged) }}
            onNodeDragStop={(_, __, dragged) => { dragged.forEach(n => { const q = toClassic(n); posRef.current.set(n.id, q); pending.current.set(n.id, q) }); clearTimeout(moveTimer.current); moveTimer.current = setTimeout(flushMoves, 600) }}
            onConnectEnd={onConnectEnd}
            onNodeDoubleClick={(_, n) => { if (!readOnly && p.onto.classes[n.id]) setRenaming(n.id) }}
            onDoubleClick={e => { if (!readOnly && (e.target as HTMLElement).classList.contains('react-flow__pane')) startCreate(e.clientX, e.clientY) }}
            onPaneClick={() => { setMenu(null); setCreating(null); wrap.current?.focus() }}
            proOptions={{ hideAttribution: true }} fitViewOptions={{ padding: fitPad === 0.12 ? 0.2 : fitPad, maxZoom: 1 }}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} />
            <Controls showInteractive={false} position="bottom-left" />
            <MiniMap pannable zoomable position="bottom-right" ariaLabel={t('ed.minimap')} nodeStrokeWidth={4} nodeColor={n => ((n.data as ClassNodeData)?.status === 'add' ? 'var(--ed-add)' : 'var(--accent)')} maskColor="var(--ed-mask)" />
          </ReactFlow>

          {errors.length > 0 && <div className="of-errors" role="alert"><Icon name="triangle-exclamation" /><div className="grow"><b>{t('ed.err.title')}</b><ul>{errors.slice(0, 4).map((m, i) => <li key={i}>{m}</li>)}</ul></div><IconButton icon="xmark" label={t('ed.close')} onClick={() => setErrors([])} /></div>}

          {empty && <div className="of-empty"><EmptyState pose="graphe" title={t('ed.empty.t')}
            action={<><Button variant="primary" icon="plus" onClick={() => startCreate()} disabled={readOnly}>{t('ed.newclass')}</Button><Button icon="wand-magic-sparkles" onClick={() => { location.hash = `#/projet/${encodeURIComponent(pid)}/assistant` }}>{t('ed.empty.assistant')}</Button></>}>{t('ed.empty.d')}</EmptyState></div>}

          {creating && <div className="of-inline" style={{ left: creating.sx, top: creating.sy }}>
            <input type="text" autoFocus aria-label={t('ed.newclass.name')} placeholder={t('ed.newclass.name')} value={newName} onChange={e => setNewName(e.target.value)}
              onKeyDown={e => { e.stopPropagation(); if (e.key === 'Enter') submitCreate(); if (e.key === 'Escape') setCreating(null) }} onBlur={() => newName.trim() ? submitCreate() : setCreating(null)} />
            <small>{t('ed.newclass.hint')}</small></div>}

          {menu && <div className="of-pop of-menu" style={{ left: Math.min(menu.x, (wrap.current?.clientWidth ?? 600) - 290), top: Math.min(menu.y, (wrap.current?.clientHeight ?? 600) - (menu.step === 'choose' ? 190 : 120)) }} role="menu">
            {menu.step === 'choose' ? <>
              <small className="muted">{lbl(menu.src)} → {lbl(menu.tgt)}</small>
              <button type="button" role="menuitem" onClick={() => applyMenu('sub')} disabled={menu.src === menu.tgt}><Icon name="arrow-up-long" />{t('ed.menu.sub', { a: lbl(menu.src), b: lbl(menu.tgt) })}</button>
              <button type="button" role="menuitem" onClick={() => setMenu({ ...menu, step: 'name' })}><Icon name="arrow-right-long" />{t('ed.menu.prop')}</button>
              <button type="button" role="menuitem" onClick={() => applyMenu('disj')} disabled={menu.src === menu.tgt}><Icon name="ban" />{t('ed.menu.disj')}</button>
            </> : <>
              <small className="muted">{lbl(menu.src)} → {lbl(menu.tgt)}</small>
              <input type="text" autoFocus aria-label={t('ed.menu.propname')} placeholder={t('ed.menu.propname')} value={propName} onChange={e => setPropName(e.target.value)}
                onKeyDown={e => { e.stopPropagation(); if (e.key === 'Enter') submitProp(); if (e.key === 'Escape') setMenu(null) }} />
              <small className="muted">{t('ed.newclass.hint')}</small></>}
          </div>}

          {pendingDel && <div className="of-confirm" role="alertdialog" aria-label={t('ed.delete')}><Icon name="trash" /><span className="grow">{pendingDel.text}</span>
            <Button variant="danger" size="sm" onClick={() => { const o = pendingDel.ops; setPendingDel(null); apply(o, t('ed.delete')) }}>{t('ed.delete')}</Button>
            <Button size="sm" onClick={() => setPendingDel(null)}>{t('ed.cancel')}</Button></div>}

          {periForm && <div className="of-pop of-periform" role="dialog" aria-label={t('ed.peri.fromsel')}>
            <b>{t('ed.peri.title', { n: selIds.size })}</b>
            <input type="text" autoFocus placeholder={t('ed.peri.name')} aria-label={t('ed.peri.name')} value={periForm.name} onChange={e => setPeriForm({ ...periForm, name: e.target.value })} onKeyDown={e => { e.stopPropagation(); if (e.key === 'Enter') createPerimeter(); if (e.key === 'Escape') setPeriForm(null) }} />
            <label className="chk"><input type="checkbox" checked={periForm.desc} onChange={e => setPeriForm({ ...periForm, desc: e.target.checked })} />{t('ed.peri.desc')}</label>
            <div className="row"><Button variant="primary" size="sm" onClick={createPerimeter} disabled={!periForm.name.trim()}>{t('ed.peri.create')}</Button><Button size="sm" onClick={() => setPeriForm(null)}>{t('ed.cancel')}</Button></div></div>}

          {listed.length > 0 && <aside className="of-proposal" aria-label={t('ed.prop.title')}>
            <header><Icon name="wand-magic-sparkles" /><b className="grow">{t('ed.prop.title')}</b>
              <Button size="sm" variant="primary" icon="check" onClick={() => accept(listed)}>{t('ed.prop.acceptall')}</Button>
              <Button size="sm" icon="xmark" onClick={() => reject(listed)}>{t('ed.prop.rejectall')}</Button></header>
            <ul>{listed.map(i => <li key={i.key} className={i.status}>
              <span className="tag"><Icon name={i.status === 'add' ? 'plus' : 'pen'} />{t('ed.prop.' + i.status)}</span>
              <span className="grow"><b>{i.label}</b><small>{t('ed.prop.kind.' + i.kind)}{i.detail ? ' · ' + i.detail : ''}</small></span>
              <IconButton icon="check" label={t('ed.prop.accept')} onClick={() => accept([i])} /><IconButton icon="xmark" label={t('ed.prop.reject')} onClick={() => reject([i])} /></li>)}</ul>
          </aside>}
        </div>

        {(inspOpen || (readOnly && sel)) && <aside className="of-insp-wrap" aria-label={t('ed.insp')} data-tour="ed-inspector">
          {sel
            ? <Inspector onto={p.onto} sel={sel} lang={lang} readOnly={readOnly} icon={graph?.nodes.find(n => n.id === sel.iri)?.icon ?? null} apply={apply} select={s => (s?.kind === 'class' ? selectClass(s.iri, false) : s ? selectProp(s.iri) : setSel(null))} close={() => { setInspPref(false); setSel(null); setNodes(ns => ns.map(n => ({ ...n, selected: false }))); setEdges(es => es.map(e => ({ ...e, selected: false }))) }} />
            : <div className="of-insp-empty"><Icon name="hand-pointer" /><p>{selIds.size > 1 ? t('ed.insp.multi', { n: selIds.size }) : t('ed.insp.none')}</p></div>}
        </aside>}
      </div>

      {!readOnly && <section className={'of-dslwrap' + (dslOpen ? ' open' : '')} data-tour="ed-quick">
        <button type="button" className="of-dslhead" aria-expanded={dslOpen} onClick={() => setDslOpen(o => !o)}><Icon name={dslOpen ? 'chevron-down' : 'chevron-up'} /><Icon name="bolt" /><b>{t('ed.dsl.title')}</b><small className="muted">{t('ed.dsl.sub')}</small></button>
        {dslOpen && <QuickInput pid={pid} hint={hint} onApplied={setP} onToast={toast} />}
      </section>}
    </div>
  )
}
