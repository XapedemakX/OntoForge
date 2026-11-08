import { memo, useEffect, useRef, useState } from 'react'
import { Handle, Position, BaseEdge, useStore, EdgeLabelRenderer, useInternalNode, type NodeProps, type EdgeProps, type InternalNode } from '@xyflow/react'
import { Icon } from '../../kit'
import { useT } from '../../i18n'
import { NODE_H, NODE_W } from './layout'
import { edgeGeom, type Box, type Shape } from './geom'

export interface ClassNodeData extends Record<string, unknown> {
  label: string; curie: string; icon: string | null; abstract: boolean; deprecated: boolean
  status?: 'add' | 'modify'; error?: boolean; readOnly: boolean; editing: boolean
  onRename: (iri: string, text: string | null) => void
  pkey?: string; onProposal?: (key: string, accept: boolean) => void; hid?: number
}
export const ClassNode = memo(function ClassNode({ id, data, selected }: NodeProps) {
  const d = data as ClassNodeData
  const t = useT()
  // zoom sémantique : sous 0,6 le nœud devient compact (icône + libellé court, police agrandie pour rester lisible à l'écran)
  const zoom = useStore(st => st.transform[2])
  const compact = zoom < 0.6 && !d.editing
  const [v, setV] = useState(d.label)
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { if (d.editing) { setV(d.label); setTimeout(() => ref.current?.select(), 0) } }, [d.editing, d.label])
  const cls = ['of-node', compact && 'compact', selected && 'sel', d.abstract && 'abstract', d.deprecated && 'deprecated', d.status, d.error && 'err'].filter(Boolean).join(' ')
  return (
    <div className={cls} title={d.curie} style={{ width: NODE_W, minHeight: NODE_H, ...(compact ? { ['--of-fs' as string]: `${Math.min(30, Math.round(12.5 / zoom))}px` } : null) }}>
      <span className="of-ico"><Icon name={d.icon || 'circle-nodes'} /></span>
      <span className="of-txt">
        {d.editing
          ? <input ref={ref} className="nodrag nopan of-rename" value={v} aria-label={t('ed.rename')} onChange={e => setV(e.target.value)}
              onKeyDown={e => { e.stopPropagation(); if (e.key === 'Enter') d.onRename(id, v.trim() || null); if (e.key === 'Escape') d.onRename(id, null) }}
              onBlur={() => d.onRename(id, v.trim() || null)} />
          : <b>{d.label}</b>}
        <small>{d.curie}</small>
      </span>
      {(d.abstract || d.deprecated) && <span className="of-badges">
        {d.abstract && <em title={t('ed.abstract.hint')}>{t('ed.abstract')}</em>}
        {d.deprecated && <em className="dep">{t('ed.deprecated')}</em>}
      </span>}
      {!!d.hid && <span className="of-hid" title={t('ed.show.hidbadge', { n: d.hid })}>+{d.hid}</span>}
      {d.status && <span className="of-flag" title={t('ed.prop.' + d.status)}><Icon name={d.status === 'add' ? 'plus' : 'pen'} /></span>}
      {d.status && d.pkey && d.onProposal && <span className="of-pbtn nodrag nopan">
        <button type="button" className="ok" aria-label={t('ed.prop.accept')} title={t('ed.prop.accept')} onClick={e => { e.stopPropagation(); d.onProposal!(d.pkey!, true) }}><Icon name="check" /></button>
        <button type="button" className="no" aria-label={t('ed.prop.reject')} title={t('ed.prop.reject')} onClick={e => { e.stopPropagation(); d.onProposal!(d.pkey!, false) }}><Icon name="xmark" /></button></span>}
      {!d.readOnly && <Handle type="source" position={Position.Bottom} className="of-handle" title={t('ed.drag')} />}
      <Handle type="target" position={Position.Top} className="of-handle-in" isConnectable={false} />
    </div>
  )
})

// ---- arêtes flottantes : le segment relie les bords des nœuds (rectangles ou cercles), quel que soit l'emplacement des poignées ----
const boxOf = (n: InternalNode): Box => {
  const w = n.measured.width ?? NODE_W, h = n.measured.height ?? NODE_H, p = n.internals.positionAbsolute
  return { cx: p.x + w / 2, cy: p.y + h / 2, w, h, shape: ((n.data as { shape?: Shape }).shape) ?? 'rect' }
}
export interface OfEdgeData extends Record<string, unknown> {
  kind: string; label: string; inverse?: string; offset: number; status?: 'add' | 'modify'; err?: boolean
  vowl?: boolean; chars?: string[]; deprecated?: boolean
}
export const OfEdge = memo(function OfEdge({ id, source, target, data, selected, markerEnd, markerStart }: EdgeProps) {
  const d = data as OfEdgeData
  const t = useT()
  const zoom = useStore(st => st.transform[2])
  const s = useInternalNode(source), tg = useInternalNode(target)
  if (!s || !tg) return null
  const g = edgeGeom(boxOf(s), boxOf(tg), d.offset, source === target)
  const { lx, ly } = g
  const pos = { transform: `translate(-50%,-50%) translate(${lx}px,${ly}px)` }
  const cls = `of-edge ${d.kind} ${selected ? 'sel' : ''} ${d.status ?? ''} ${d.err ? 'err' : ''} ${d.deprecated ? 'dep' : ''}`
  if (d.vowl) {
    const prop = d.kind === 'objectProperty' || d.kind === 'datatypeProperty'
    const chars = (d.chars ?? []).map(c => t('ed.char.' + c).toLowerCase())
    if (d.deprecated) chars.push(t('ed.deprecated').toLowerCase())
    return (
      <>
        <BaseEdge id={id} path={g.path} markerEnd={markerEnd} markerStart={markerStart} className={cls} interactionWidth={16} />
        <EdgeLabelRenderer>
          {prop && (zoom >= 0.55 || !!selected) && <div className={`of-vl ${d.kind} ${selected ? 'sel' : ''} ${d.status ?? ''} ${d.deprecated ? 'dep' : ''}`} style={pos}>
            <span>{d.label}{d.inverse && <> ⇄ {d.inverse}</>}</span>{chars.length > 0 && <small>[{chars.join(', ')}]</small>}</div>}
          {d.kind === 'subClassOf' && (zoom >= 0.8 || !!selected) && <div className={`of-vl subClassOf ${d.status ?? ''}`} style={pos}><span>{t('lg.w.subOf')}</span></div>}
          {d.kind === 'disjointWith' && <div className="of-vl disjointWith" title="disjointWith" style={pos}>
            <svg width="26" height="14" viewBox="0 0 26 14" aria-hidden="true"><circle cx="8" cy="7" r="5.5" /><circle cx="18" cy="7" r="5.5" /></svg><small>[{t('lg.w.disj')}]</small></div>}
        </EdgeLabelRenderer>
      </>
    )
  }
  const showLabel = (d.kind === 'objectProperty' || d.kind === 'equivalentClass') && (zoom >= 0.7 || !!selected)
  return (
    <>
      <BaseEdge id={id} path={g.path} markerEnd={markerEnd} className={cls} interactionWidth={16} />
      <EdgeLabelRenderer>
        {showLabel && <div className={`of-elabel ${d.kind} ${selected ? 'sel' : ''} ${d.status ?? ''}`} style={pos}>
          {d.label}{d.inverse && <small> ⇄ {d.inverse}</small>}</div>}
        {d.kind === 'disjointWith' && <div className="of-disj" title="disjointWith" style={pos}>⟂</div>}
        {d.kind === 'equivalentClass' && !d.label && <div className="of-elabel equivalentClass" style={pos}>≡</div>}
      </EdgeLabelRenderer>
    </>
  )
})

/** Définitions des marqueurs de flèche (SVG partagé). */
export function EdgeDefs() {
  return (
    <svg className="of-defs" width="0" height="0" aria-hidden="true">
      <defs>
        <marker id="of-hollow" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto-start-reverse"><path d="M1 1 L11 6 L1 11 Z" className="m-hollow" /></marker>
        <marker id="of-solid" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="10" markerHeight="10" orient="auto-start-reverse"><path d="M1 1 L11 6 L1 11 Z" className="m-solid" /></marker>
        <marker id="of-solid-add" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="10" markerHeight="10" orient="auto-start-reverse"><path d="M1 1 L11 6 L1 11 Z" className="m-solid add" /></marker>
        <marker id="v-hollow" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto-start-reverse"><path d="M1 1 L11 6 L1 11 Z" className="m-vhollow" /></marker>
        <marker id="v-solid" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="10" markerHeight="10" orient="auto-start-reverse"><path d="M1 1 L11 6 L1 11 Z" className="m-vsolid" /></marker>
        <marker id="of-hollow-add" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto-start-reverse"><path d="M1 1 L11 6 L1 11 Z" className="m-hollow add" /></marker>
      </defs>
    </svg>
  )
}
