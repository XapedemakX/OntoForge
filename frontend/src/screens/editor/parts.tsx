import { memo, useEffect, useRef, useState } from 'react'
import { Handle, Position, BaseEdge, useStore, EdgeLabelRenderer, useInternalNode, type NodeProps, type EdgeProps, type InternalNode } from '@xyflow/react'
import { Icon } from '../../kit'
import { useT } from '../../i18n'
import { NODE_H, NODE_W } from './layout'

export interface ClassNodeData extends Record<string, unknown> {
  label: string; curie: string; icon: string | null; abstract: boolean; deprecated: boolean
  status?: 'add' | 'modify'; error?: boolean; readOnly: boolean; editing: boolean
  onRename: (iri: string, text: string | null) => void
  pkey?: string; onProposal?: (key: string, accept: boolean) => void
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
      {d.status && <span className="of-flag" title={t('ed.prop.' + d.status)}><Icon name={d.status === 'add' ? 'plus' : 'pen'} /></span>}
      {d.status && d.pkey && d.onProposal && <span className="of-pbtn nodrag nopan">
        <button type="button" className="ok" aria-label={t('ed.prop.accept')} title={t('ed.prop.accept')} onClick={e => { e.stopPropagation(); d.onProposal!(d.pkey!, true) }}><Icon name="check" /></button>
        <button type="button" className="no" aria-label={t('ed.prop.reject')} title={t('ed.prop.reject')} onClick={e => { e.stopPropagation(); d.onProposal!(d.pkey!, false) }}><Icon name="xmark" /></button></span>}
      {!d.readOnly && <Handle type="source" position={Position.Bottom} className="of-handle" title={t('ed.drag')} />}
      <Handle type="target" position={Position.Top} className="of-handle-in" isConnectable={false} />
    </div>
  )
})

// ---- arêtes flottantes : le segment relie les bords des nœuds, quel que soit l'emplacement des poignées ----
function border(n: InternalNode, tx: number, ty: number) {
  const w = n.measured.width ?? NODE_W, h = n.measured.height ?? NODE_H
  const p = n.internals.positionAbsolute
  const cx = p.x + w / 2, cy = p.y + h / 2
  const dx = tx - cx, dy = ty - cy
  if (!dx && !dy) return { x: cx, y: cy }
  const k = 1 / Math.max(Math.abs(dx) / (w / 2), Math.abs(dy) / (h / 2))
  return { x: cx + dx * k, y: cy + dy * k }
}
export interface OfEdgeData extends Record<string, unknown> { kind: string; label: string; inverse?: string; offset: number; status?: 'add' | 'modify'; err?: boolean }
export const OfEdge = memo(function OfEdge({ id, source, target, data, selected, markerEnd }: EdgeProps) {
  const d = data as OfEdgeData
  const zoom = useStore(st => st.transform[2])
  const s = useInternalNode(source), tg = useInternalNode(target)
  if (!s || !tg) return null
  const sc = { x: s.internals.positionAbsolute.x + (s.measured.width ?? NODE_W) / 2, y: s.internals.positionAbsolute.y + (s.measured.height ?? NODE_H) / 2 }
  const tc = { x: tg.internals.positionAbsolute.x + (tg.measured.width ?? NODE_W) / 2, y: tg.internals.positionAbsolute.y + (tg.measured.height ?? NODE_H) / 2 }
  let path: string, lx: number, ly: number
  if (source === target) {
    const x = sc.x + (s.measured.width ?? NODE_W) / 2, y = sc.y - 8
    path = `M ${x} ${y} C ${x + 70} ${y - 50}, ${x + 70} ${y + 50}, ${x} ${y + 16}`; lx = x + 62; ly = y
  } else {
    const a = border(s, tc.x, tc.y), b = border(tg, sc.x, sc.y)
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
    const len = Math.hypot(b.x - a.x, b.y - a.y) || 1
    const nx = -(b.y - a.y) / len, ny = (b.x - a.x) / len
    const o = d.offset * 34
    const qx = mx + nx * o * 2, qy = my + ny * o * 2
    path = o ? `M ${a.x} ${a.y} Q ${qx} ${qy} ${b.x} ${b.y}` : `M ${a.x} ${a.y} L ${b.x} ${b.y}`
    lx = mx + nx * o; ly = my + ny * o
  }
  const showLabel = (d.kind === 'objectProperty' || d.kind === 'equivalentClass') && (zoom >= 0.7 || !!selected)
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} className={`of-edge ${d.kind} ${selected ? 'sel' : ''} ${d.status ?? ''} ${d.err ? 'err' : ''}`} interactionWidth={16} />
      <EdgeLabelRenderer>
        {showLabel && <div className={`of-elabel ${d.kind} ${selected ? 'sel' : ''} ${d.status ?? ''}`} style={{ transform: `translate(-50%,-50%) translate(${lx}px,${ly}px)` }}>
          {d.label}{d.inverse && <small> ⇄ {d.inverse}</small>}</div>}
        {d.kind === 'disjointWith' && <div className="of-disj" title="disjointWith" style={{ transform: `translate(-50%,-50%) translate(${lx}px,${ly}px)` }}>⟂</div>}
        {d.kind === 'equivalentClass' && !d.label && <div className="of-elabel equivalentClass" style={{ transform: `translate(-50%,-50%) translate(${lx}px,${ly}px)` }}>≡</div>}
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
        <marker id="of-hollow-add" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="12" markerHeight="12" orient="auto-start-reverse"><path d="M1 1 L11 6 L1 11 Z" className="m-hollow add" /></marker>
      </defs>
    </svg>
  )
}
