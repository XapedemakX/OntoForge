import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button, EmptyState, Icon, IconButton } from '../../kit'
import { useT } from '../../i18n'
import { ClassChip } from './ClassChip'
import { qapi, type InlineEndpoint, type OptionValue, type ClassSuggest, type DataSuggest, type FilterKind, type ObjSuggest, type RootClass, type Target } from './qapi'
import { allNodes, entityFilter, isEntityFilter, localName, colId, defaultFilter, effectiveCols, isActive, mapNode, uid, varFor, walk, type QFilter, type QNode, type QState } from './model'

export type SugMap = Record<string, ClassSuggest | 'loading' | 'error'>
export interface Ctx {
  pid: string; lang: string; endpointId: string | null; inline: InlineEndpoint | null; sug: SugMap; roots: RootClass[]
  set: (f: (s: QState) => QState) => void; state: QState
  openAdd: string | null; setOpenAdd: (id: string | null) => void
  seed: string; setSeed: (s: string) => void
}

export function useSuggestions(pid: string, lang: string, classes: string[]) {
  const [sug, setSug] = useState<SugMap>({})
  const seen = useRef(new Set<string>())
  useEffect(() => { seen.current = new Set(); setSug({}) }, [pid, lang])
  useEffect(() => {
    for (const c of classes) {
      if (!c || seen.current.has(c)) continue
      seen.current.add(c); setSug(s => ({ ...s, [c]: 'loading' }))
      qapi.suggest(pid, c, lang).then(r => setSug(s => ({ ...s, [c]: r }))).catch(() => setSug(s => ({ ...s, [c]: 'error' })))
    }
  }, [pid, lang, classes.join('|')]) // eslint-disable-line react-hooks/exhaustive-deps
  return sug
}
const ready = (x: SugMap[string] | undefined): ClassSuggest | null => (x && x !== 'loading' && x !== 'error' ? x : null)

const AUTO_LIST = 40  // une classe énumérée ou peu peuplée propose d'emblée « est l'un de »
const KIND_KEYS: Record<FilterKind, string> = { text_contains: 'q.kind.text_contains', equals: 'q.kind.equals', regex: 'q.kind.regex', lang: 'q.kind.lang', number_range: 'q.kind.number_range', date_range: 'q.kind.date_range', in_values: 'q.kind.in_values' }

export function Builder({ ctx }: { ctx: Ctx }) {
  const { state } = ctx
  if (!state.root) return <RootPicker ctx={ctx} />
  return (
    <div className="qb">
      <NodeView node={state.root} ctx={ctx} />
      <ColumnsBar ctx={ctx} />
    </div>
  )
}

/* ---------- classe racine ---------- */
function RootPicker({ ctx, onPick }: { ctx: Ctx; onPick?: () => void }) {
  const t = useT()
  const [q, setQ] = useState(ctx.seed)
  const list = useMemo(() => {
    const n = q.trim().toLowerCase()
    return ctx.roots.filter(c => !n || c.label.toLowerCase().includes(n) || c.iri.toLowerCase().includes(n)).sort((a, b) => a.label.localeCompare(b.label))
  }, [ctx.roots, q])
  const pick = (c: RootClass) => {
    ctx.set(s => ({ ...s, cols: null, order: null, root: { id: uid(), varName: varFor(c.label, new Set()), classIri: c.iri, label: c.label, filters: [], children: [] } }))
    onPick?.()
  }
  return (
    <div className="qroot">
      {!onPick && <EmptyState pose="loupe" title={t('q.empty.title')}>{t('q.empty.body')}</EmptyState>}
      <div className="qpick">
        <div className="qsearch"><Icon name="magnifying-glass" /><input type="text" autoFocus={!!onPick} value={q} onChange={e => setQ(e.target.value)} placeholder={t('q.root.search')} aria-label={t('q.root.search')} /></div>
        <div className="qpick-list">
          {list.map(c => <ClassChip key={c.iri} iri={c.iri} label={c.label} meta={c.known ? t('q.known', { n: c.known }) : undefined} onClick={() => pick(c)} />)}
          {list.length === 0 && <span className="muted">{t('q.root.none')}</span>}
        </div>
      </div>
    </div>
  )
}

/* ---------- nœud (une ligne de la phrase) ---------- */
function NodeView({ node, ctx }: { node: QNode; ctx: Ctx }) {
  const t = useT()
  const { state, set } = ctx
  const parent = useMemo(() => { let p: QNode | null = null; if (state.root) walk(state.root, (n, par) => { if (n.id === node.id) p = par }); return p as QNode | null }, [state.root, node.id])
  const own = ready(ctx.sug[node.classIri])
  const pSug = parent ? ready(ctx.sug[parent.classIri]) : null
  const edgeLabel = node.edge ? (pSug ? [...pSug.outgoing, ...pSug.incoming].find(o => o.iri === node.edge!.prop && o.inverse === node.edge!.inverse)?.label : undefined) ?? node.edge.propLabel : ''
  const isRoot = !node.edge
  const [swap, setSwap] = useState(false)
  const upd = (f: (n: QNode) => QNode | null) => set(s => ({ ...s, root: s.root ? mapNode(s.root, node.id, f) : s.root }))
  const adding = ctx.openAdd === node.id
  const negated = !!node.edge?.negated
  const known = ctx.roots.find(c => c.iri === node.classIri)?.known ?? 0
  return (
    <div className={`qn ${isRoot ? 'root' : ''} ${negated ? 'neg' : ''}`}>
      <div className="qn-line">
        {isRoot ? <span className="qw">{t('q.root.lead')}</span> : (
          <>
            <span className="qw">{negated ? t('q.edge.not') : node.edge!.optional ? t('q.edge.maybe') : t('q.edge.who')}</span>
            <span className={`qe ${node.edge!.inverse ? 'inv' : ''}`} title={node.edge!.inverse ? t('q.edge.inverse', { p: edgeLabel }) : edgeLabel}>
              {node.edge!.inverse && <Icon name="arrow-left-long" />}<span>{edgeLabel}</span>{!node.edge!.inverse && <Icon name="arrow-right-long" />}
            </span>
          </>
        )}
        <ClassChip iri={node.classIri} label={node.label} onClick={isRoot ? () => setSwap(s => !s) : undefined} active={swap} caret={isRoot} title={isRoot ? t('q.root.change') : undefined} />
        <span className="qn-opts">
          {!isRoot && <>
            <button type="button" className={`qo ${node.edge!.optional ? 'on' : ''}`} aria-pressed={node.edge!.optional} disabled={negated} onClick={() => upd(n => ({ ...n, edge: { ...n.edge!, optional: !n.edge!.optional } }))} title={t('q.opt.optional.tip')}><Icon name="circle-half-stroke" />{t('q.opt.optional')}</button>
            <button type="button" className={`qo ${negated ? 'on neg' : ''}`} aria-pressed={negated} onClick={() => upd(n => ({ ...n, edge: { ...n.edge!, negated: !n.edge!.negated, optional: false } }))} title={t('q.opt.not.tip')}><Icon name="ban" />{t('q.opt.not')}</button>
          </>}
          {known > 0 && !node.filters.some(isEntityFilter) && <button type="button" className="qo" data-tour="q-oneof" onClick={() => upd(n => ({ ...n, filters: [...n.filters, entityFilter()] }))} title={t('q.f.oneof.tip')}><Icon name="list-check" />{t('q.f.oneof')}</button>}
          <button type="button" className={`qo add ${adding ? 'on' : ''}`} aria-expanded={adding} onClick={() => ctx.setOpenAdd(adding ? null : node.id)}><Icon name="plus" />{t('q.add')}</button>
          {!isRoot && <IconButton icon="xmark" label={t('q.remove')} onClick={() => upd(() => null)} />}
        </span>
      </div>
      {isRoot && swap && <RootPicker ctx={ctx} onPick={() => setSwap(false)} />}
      {node.filters.map(f => isEntityFilter(f) ? <EntityFilter key={f.id} f={f} node={node} ctx={ctx}
        onChange={nf => upd(n => ({ ...n, filters: n.filters.map(x => (x.id === f.id ? nf : x)) }))}
        onRemove={() => upd(n => ({ ...n, filters: n.filters.filter(x => x.id !== f.id) }))} /> : <FilterRow key={f.id} f={f} node={node} own={own} ctx={ctx}
        onChange={nf => upd(n => ({ ...n, filters: n.filters.map(x => (x.id === f.id ? nf : x)) }))}
        onRemove={() => upd(n => ({ ...n, filters: n.filters.filter(x => x.id !== f.id) }))} />)}
      {adding && <AddPanel node={node} sug={own} ctx={ctx} />}
      {node.children.length > 0 && <div className="qn-kids">{node.children.map(c => <NodeView key={c.id} node={c} ctx={ctx} />)}</div>}
    </div>
  )
}

/* ---------- ajouter : relation ou filtre ---------- */
function AddPanel({ node, sug, ctx }: { node: QNode; sug: ClassSuggest | null; ctx: Ctx }) {
  const t = useT()
  const [q, setQ] = useState(ctx.seed); const [pick, setPick] = useState<ObjSuggest | null>(null)
  const needle = q.trim().toLowerCase()
  const match = (s: string) => !needle || s.toLowerCase().includes(needle)
  const addStep = (o: ObjSuggest, tg: Target) => {
    ctx.set(s => {
      if (!s.root) return s
      const taken = new Set(allNodes(s.root).map(n => n.varName))
      const child: QNode = { id: uid(), varName: varFor(tg.label, taken), classIri: tg.iri, label: tg.label, edge: { prop: o.iri, propLabel: o.label, inverse: o.inverse, optional: false, negated: false }, filters: tg.known && tg.known <= AUTO_LIST ? [entityFilter()] : [], children: [] }
      return { ...s, cols: s.cols ? [...s.cols, { id: colId(child.varName, null, false), varName: child.varName, prop: null, label: false, title: child.label }] : null, root: mapNode(s.root, node.id, n => ({ ...n, children: [...n.children, child] })) }
    })
    ctx.setOpenAdd(null)
  }
  const addFilter = (d: DataSuggest) => {
    ctx.set(s => ({ ...s, root: s.root ? mapNode(s.root, node.id, n => ({ ...n, filters: [...n.filters, defaultFilter(d)] })) : s.root }))
    ctx.setOpenAdd(null)
  }
  if (!sug) return <div className="qadd muted">{t('q.loading')}</div>
  const rels = [...sug.outgoing, ...sug.incoming].filter(o => match(o.label) || o.targets.some(x => match(x.label)))
  const datas = sug.data_properties.filter(d => match(d.label))
  return (
    <div className="qadd" role="region" aria-label={t('q.add')}>
      <div className="qsearch"><Icon name="magnifying-glass" /><input type="text" autoFocus value={q} onChange={e => { setQ(e.target.value); setPick(null) }} placeholder={t('q.add.search', { c: node.label })} aria-label={t('q.add.search', { c: node.label })} /></div>
      {pick ? (
        <div className="qadd-targets">
          <div className="muted">{t('q.add.target', { p: pick.label })}</div>
          <div className="qpick-list">{pick.targets.map(tg => <ClassChip key={tg.iri} iri={tg.iri} label={tg.label} meta={tg.known ? t('q.known', { n: tg.known }) : undefined} onClick={() => addStep(pick, tg)} title={tg.direct ? undefined : t('q.add.subclass')} />)}</div>
          <Button size="sm" variant="ghost" icon="arrow-left" onClick={() => setPick(null)}>{t('q.back')}</Button>
        </div>
      ) : (
        <div className="qadd-cols">
          <div>
            <h4>{t('q.add.relations')}</h4>
            {rels.length === 0 && <p className="muted">{t('q.add.norel')}</p>}
            {rels.map(o => (
              <button type="button" key={o.direction + o.iri} className="qadd-item" onClick={() => (o.targets.length === 1 ? addStep(o, o.targets[0]) : setPick(o))}>
                <Icon name={o.inverse ? 'arrow-left-long' : 'arrow-right-long'} className="dir" />
                <span className="lab">{o.label}</span>
                <span className="tg">{o.targets.slice(0, 3).map(x => x.label).join(', ')}{o.targets.length > 3 ? '…' : ''}</span>
                {o.inherited_from && <span className="muted tiny">{t('q.add.inherited')}</span>}
              </button>
            ))}
          </div>
          <div>
            <h4>{t('q.add.data')}</h4>
            {datas.length === 0 && <p className="muted">{t('q.add.nodata')}</p>}
            {datas.map(d => (
              <button type="button" key={d.iri} className="qadd-item" onClick={() => addFilter(d)}>
                <Icon name={d.value_kind === 'number' ? 'hashtag' : d.value_kind === 'date' ? 'calendar-days' : d.value_kind === 'boolean' ? 'toggle-on' : 'font'} className="dir" />
                <span className="lab">{d.label}</span><span className="tg">{t('q.vk.' + d.value_kind)}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/* ---------- filtre ---------- */
function FilterRow({ f, node, own, ctx, onChange, onRemove }: { f: QFilter; node: QNode; own: ClassSuggest | null; ctx: Ctx; onChange: (f: QFilter) => void; onRemove: () => void }) {
  const t = useT()
  const datas = own?.data_properties ?? []
  const d = datas.find(x => x.iri === f.prop) ?? null
  const kinds = d?.filter_kinds ?? [f.kind]
  const propLabel = d?.label ?? f.propLabel
  const [opts, setOpts] = useState<OptionValue[]>([])
  const timer = useRef<number>()
  const id = useMemo(() => `dl-${f.id}`, [f.id])
  const isTextual = f.kind === 'equals' || f.kind === 'text_contains' || f.kind === 'regex'
  const suggest = useCallback((text: string) => {
    if (!f.prop || (!isTextual && f.kind !== 'in_values') || f.valueKind === 'date') return
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(async () => {
      // 1. valeurs connues de l'ontologie (sans endpoint)  2. complétées par l'endpoint s'il y en a un
      const known: OptionValue[] = await qapi.options(ctx.pid, node.classIri, f.prop!, text, ctx.lang).then(r => r.values).catch(() => [])
      const live = ctx.endpointId || ctx.inline ? await qapi.values(ctx.pid, node.classIri, f.prop!, text, ctx.endpointId ?? undefined, ctx.inline).then(r => r.values.map(v => ({ value: v.value, label: v.label, is_iri: v.is_iri }))).catch(() => []) : []
      const seen = new Set<string>(); const all: OptionValue[] = []
      for (const v of [...known, ...live]) if (!seen.has(v.value)) { seen.add(v.value); all.push(v) }
      setOpts(all)
    }, 250)
  }, [f.prop, f.kind, isTextual, f.valueKind, ctx.pid, ctx.lang, ctx.endpointId, ctx.inline, node.classIri])
  useEffect(() => { if (f.kind === 'in_values') suggest('') }, [f.kind, f.prop, suggest])
  useEffect(() => () => window.clearTimeout(timer.current), [])
  const change = (p: Partial<QFilter>) => onChange({ ...f, ...p })
  const setProp = (iri: string) => {
    const nd = datas.find(x => x.iri === iri); if (!nd) return
    change({ prop: iri, propLabel: nd.label, valueKind: nd.value_kind, kind: nd.filter_kinds.includes(f.kind) ? f.kind : nd.filter_kinds[0], value: '', value2: '' })
  }
  const numeric = f.valueKind === 'number'
  const dated = f.valueKind === 'date'
  const inputType = (numeric ? 'number' : dated ? 'date' : 'text')
  return (
    <div className={`qf ${isActive(f) ? '' : 'idle'}`}>
      <span className="qw">{f.negate ? t('q.f.butnot') : t('q.f.where')}</span>
      <select aria-label={t('q.f.prop')} value={f.prop ?? ''} onChange={e => setProp(e.target.value)}>
        {!d && <option value={f.prop ?? ''}>{propLabel || f.prop}</option>}
        {datas.map(x => <option key={x.iri} value={x.iri}>{x.label}</option>)}
      </select>
      <select aria-label={t('q.f.kind')} value={f.kind} onChange={e => change({ kind: e.target.value as FilterKind, value: '', value2: '' })}>
        {kinds.map(k => <option key={k} value={k}>{t(KIND_KEYS[k])}</option>)}
      </select>
      {f.kind === 'number_range' || f.kind === 'date_range' ? (
        <>
          <input type={f.kind === 'date_range' ? 'date' : 'number'} aria-label={t('q.f.from')} value={f.value} onChange={e => change({ value: e.target.value })} />
          <span className="qw">{t('q.f.to')}</span>
          <input type={f.kind === 'date_range' ? 'date' : 'number'} aria-label={t('q.f.upto')} value={f.value2} onChange={e => change({ value2: e.target.value })} />
        </>
      ) : f.kind === 'in_values' ? (
        opts.length > 0
          ? <ValueChecklist items={opts.map(o => ({ value: o.value, label: o.label }))} value={f.value} onChange={v => change({ value: v })} />
          : <textarea rows={2} aria-label={t('q.f.list')} placeholder={t('q.f.list.ph')} value={f.value} onChange={e => change({ value: e.target.value })} />
      ) : f.kind === 'lang' ? (
        <input type="text" className="short" aria-label={t('q.f.lang')} placeholder="fr" maxLength={8} value={f.value} onChange={e => change({ value: e.target.value })} />
      ) : f.valueKind === 'boolean' ? (
        <select aria-label={t('q.f.value')} value={f.value} onChange={e => change({ value: e.target.value })}><option value="">…</option><option value="true">{t('q.f.true')}</option><option value="false">{t('q.f.false')}</option></select>
      ) : (
        <>
          <input type={inputType} list={isTextual && !numeric && !dated ? id : undefined} aria-label={t('q.f.value')} placeholder={f.kind === 'regex' ? '^VF1' : t('q.f.value')} value={f.value}
            onFocus={() => suggest(f.value)} onChange={e => { change({ value: e.target.value }); suggest(e.target.value) }} />
          {isTextual && <datalist id={id}>{opts.map(o => <option key={o.value} value={o.value} />)}</datalist>}
        </>
      )}
      <button type="button" className={`qo ${f.negate ? 'on neg' : ''}`} aria-pressed={f.negate} onClick={() => change({ negate: !f.negate })} title={t('q.opt.not.tip')}><Icon name="ban" />{t('q.opt.not')}</button>
      <IconButton icon="xmark" label={t('q.remove')} onClick={onRemove} />
    </div>
  )
}

/* ---------- colonnes, tri, limite ---------- */
function ColumnsBar({ ctx }: { ctx: Ctx }) {
  const t = useT()
  const { state, set } = ctx
  const cols = effectiveCols(state)
  const has = (id: string) => cols.some(c => c.id === id)
  const nodes: QNode[] = []; if (state.root) walk(state.root, (n, _p, h) => { if (!h) nodes.push(n) })
  const propTitle = (c: { varName: string; prop: string | null }) => ready(ctx.sug[nodes.find(n => n.varName === c.varName)?.classIri ?? ''])?.data_properties.find(d => d.iri === c.prop)?.label ?? localName(c.prop ?? '')
  const move = (i: number, d: number) => set(s => { const a = [...effectiveCols(s)]; const j = i + d; if (j < 0 || j >= a.length) return s; [a[i], a[j]] = [a[j], a[i]]; return { ...s, cols: a } })
  const toggle = (n: QNode, prop: string | null, label: boolean, title: string) => {
    const id = colId(n.varName, prop, label)
    set(s => {
      const cur = effectiveCols(s)
      const next = cur.some(c => c.id === id) ? cur.filter(c => c.id !== id) : [...cur, { id, varName: n.varName, prop, label, title }]
      return { ...s, cols: next, order: s.order && !next.some(c => c.id === s.order!.colId) ? null : s.order }
    })
  }
  return (
    <div className="qcols">
      <div className="qcols-hd"><Icon name="table-columns" /><b>{t('q.cols')}</b><span className="muted">{t('q.cols.hint')}</span></div>
      <ol className="qshown" aria-label={t('q.cols.shown')}>
        {cols.map((c, i) => (
          <li key={c.id}>
            <span className="qshown-t"><b>{c.title}</b>{c.prop ? <span className="muted"> · {propTitle(c)}</span> : c.label ? <span className="muted"> · {t('q.cols.label')}</span> : null}</span>
            <IconButton icon="arrow-left" label={t('q.cols.left')} disabled={i === 0} onClick={() => move(i, -1)} />
            <IconButton icon="arrow-right" label={t('q.cols.right')} disabled={i === cols.length - 1} onClick={() => move(i, 1)} />
            <IconButton icon="xmark" label={t('q.remove')} onClick={() => set(s => ({ ...s, cols: effectiveCols(s).filter(x => x.id !== c.id), order: s.order?.colId === c.id ? null : s.order }))} />
          </li>
        ))}
        {cols.length === 0 && <li className="muted">{t('q.cols.empty')}</li>}
      </ol>
      <div className="qcols-grid">
        {nodes.map(n => {
          const s = ready(ctx.sug[n.classIri])
          return (
            <div key={n.id} className="qcol-group">
              <ClassChip iri={n.classIri} label={n.label} />
              <div className="qcol-toggles">
                <label className="qt"><input type="checkbox" checked={has(colId(n.varName, null, false))} onChange={() => toggle(n, null, false, n.label)} />{t('q.cols.entity')}</label>
                <label className="qt"><input type="checkbox" checked={has(colId(n.varName, null, true))} onChange={() => toggle(n, null, true, n.label)} />{t('q.cols.label')}</label>
                {(s?.data_properties ?? []).filter(d => d.iri !== 'http://www.w3.org/2000/01/rdf-schema#label').map(d => (
                  <label className="qt" key={d.iri}><input type="checkbox" checked={has(colId(n.varName, d.iri, false))} onChange={() => toggle(n, d.iri, false, d.label)} />{d.label}</label>
                ))}
              </div>
            </div>
          )
        })}
      </div>
      <div className="qcols-opts">
        <label className="f"><span>{t('q.order')}</span>
          <select value={state.order ? state.order.colId : ''} onChange={e => set(s => ({ ...s, order: e.target.value ? { colId: e.target.value, desc: s.order?.desc ?? false } : null }))}>
            <option value="">{t('q.order.none')}</option>
            {cols.map(c => <option key={c.id} value={c.id}>{c.title}{c.prop ? ` · ${(ready(ctx.sug[nodes.find(n => n.varName === c.varName)?.classIri ?? '']))?.data_properties.find(d => d.iri === c.prop)?.label ?? c.prop}` : c.label ? ` · ${t('q.cols.label')}` : ''} ({c.varName})</option>)}
          </select></label>
        {state.order && <button type="button" className="qo on" onClick={() => set(s => ({ ...s, order: s.order ? { ...s.order, desc: !s.order.desc } : null }))}><Icon name={state.order.desc ? 'arrow-down-wide-short' : 'arrow-up-short-wide'} />{state.order.desc ? t('q.order.desc') : t('q.order.asc')}</button>}
        <label className="f"><span>{t('q.limit')}</span>
          <select value={state.limit} onChange={e => set(s => ({ ...s, limit: Number(e.target.value) }))}>{[10, 50, 100, 500, 1000, 5000].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
        <label className="qt sub" title={t('q.sub.tip')}><input type="checkbox" checked={state.subclasses} onChange={e => set(s => ({ ...s, subclasses: e.target.checked }))} />{t('q.sub')}</label>
      </div>
    </div>
  )
}

/* ---------- liste à cocher (valeurs séparées par des retours à la ligne) ---------- */
export function ValueChecklist({ items, value, onChange, extra }: { items: { value: string; label: string }[]; value: string; onChange: (v: string) => void; extra?: React.ReactNode }) {
  const t = useT()
  const [q, setQ] = useState('')
  const sel = useMemo(() => new Set(value.split('\n').map(x => x.trim()).filter(Boolean)), [value])
  const shown = items.filter(i => !q.trim() || i.label.toLowerCase().includes(q.trim().toLowerCase()))
  const toggle = (v: string) => { const n = new Set(sel); if (n.has(v)) n.delete(v); else n.add(v); onChange([...n].join('\n')) }
  const orphan = [...sel].filter(v => !items.some(i => i.value === v))
  return (
    <div className="qchk">
      {items.length > 8 && <div className="qsearch sm"><Icon name="magnifying-glass" /><input type="text" value={q} onChange={e => setQ(e.target.value)} placeholder={t('q.f.filterlist')} aria-label={t('q.f.filterlist')} /></div>}
      <div className="qchk-list" role="group" aria-label={t('q.f.list')}>
        {[...orphan.map(v => ({ value: v, label: localName(v) })), ...shown].map(i => (
          <label key={i.value} className={`qchk-i ${sel.has(i.value) ? 'on' : ''}`}><input type="checkbox" checked={sel.has(i.value)} onChange={() => toggle(i.value)} />{i.label}</label>))}
        {shown.length === 0 && <span className="muted">{t('q.f.nomatch')}</span>}
      </div>
      {extra}
    </div>
  )
}

/* ---------- « est l'un de » sur l'entité : individus connus (ontologie) + valeurs de l'endpoint ---------- */
function EntityFilter({ f, node, ctx, onChange, onRemove }: { f: QFilter; node: QNode; ctx: Ctx; onChange: (f: QFilter) => void; onRemove: () => void }) {
  const t = useT()
  const [items, setItems] = useState<{ value: string; label: string }[]>([])
  const [live, setLive] = useState<'idle' | 'ok' | 'err'>('idle')
  useEffect(() => {
    let ok = true
    ;(async () => {
      const known = await qapi.options(ctx.pid, node.classIri, null, '', ctx.lang).then(r => r.values).catch(() => [] as OptionValue[])
      let extra: { value: string; label: string }[] = []
      if (ctx.endpointId || ctx.inline) {
        try { extra = (await qapi.values(ctx.pid, node.classIri, null, '', ctx.endpointId ?? undefined, ctx.inline)).values.filter(v => v.is_iri).map(v => ({ value: v.value, label: v.label })); if (ok) setLive('ok') } catch { if (ok) setLive('err') }
      } else if (ok) setLive('idle')
      const seen = new Set<string>(); const all: { value: string; label: string }[] = []
      for (const v of [...known.filter(k => k.is_iri), ...extra]) if (!seen.has(v.value)) { seen.add(v.value); all.push({ value: v.value, label: v.label }) }
      if (ok) setItems(all)
    })()
    return () => { ok = false }
  }, [ctx.pid, ctx.lang, ctx.endpointId, ctx.inline, node.classIri])
  return (
    <div className={`qf qf-ent ${isActive(f) ? '' : 'idle'}`}>
      <span className="qw">{f.negate ? t('q.f.butnot') : t('q.f.where')}</span>
      <span className="qf-lead">{t('q.f.oneof.lead', { c: node.label })}</span>
      <ValueChecklist items={items} value={f.value} onChange={v => onChange({ ...f, value: v })}
        extra={<span className="muted tiny">{t('q.f.oneof.src', { n: items.length })}{live === 'ok' ? ' · ' + t('q.f.oneof.live') : live === 'err' ? ' · ' + t('q.f.oneof.liveErr') : ''}</span>} />
      <button type="button" className={`qo ${f.negate ? 'on neg' : ''}`} aria-pressed={f.negate} onClick={() => onChange({ ...f, negate: !f.negate })} title={t('q.opt.not.tip')}><Icon name="ban" />{t('q.opt.not')}</button>
      <IconButton icon="xmark" label={t('q.remove')} onClick={onRemove} />
    </div>
  )
}
