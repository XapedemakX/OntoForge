// Nœuds de la notation VOWL (L26) : cercles pour les classes, rectangles pour les types de données.
// Notation d'après la spécification VOWL 2 (voir docs/guide/utilisateur.md) ; aucun code de WebVOWL n'est repris.
import { memo, useEffect, useRef, useState } from 'react'
import { Handle, Position, useStore, type NodeProps } from '@xyflow/react'
import { Icon } from '../../kit'
import { useT } from '../../i18n'
import type { MNode, VK } from './view'
import type { Shape } from './geom'

export interface VNodeData extends Record<string, unknown> {
  vk: VK; label: string; curie: string; abstract: boolean; deprecated: boolean; external: boolean; merged: string[]; op?: 'and' | 'or' | 'not'
  status?: 'add' | 'modify'; error?: boolean; readOnly: boolean; editing: boolean; hid: number; shape: Shape
  onRename: (iri: string, text: string | null) => void
  pkey?: string; onProposal?: (key: string, accept: boolean) => void
}
/** Dimensions d'un nœud VOWL : le diamètre croît avec la longueur du libellé pour que le texte tienne dans le cercle. */
export function vsize(n: MNode): { w: number; h: number; shape: Shape } {
  if (n.vk === 'datatype') return { w: Math.max(54, Math.min(130, 24 + n.label.length * 7)), h: 26, shape: 'rect' }
  if (n.vk === 'thing') return { w: 54, h: 54, shape: 'ellipse' }
  if (n.vk === 'anon') return { w: 54, h: 54, shape: 'ellipse' }
  const extra = n.merged.length ? 10 : 0
  const d = Math.round(Math.min(150, 92 + Math.max(0, Math.max(n.label.length, ...n.merged.map(m => m.length)) - 11) * 2.6) + extra)
  return { w: d, h: d, shape: 'ellipse' }
}

export const VNode = memo(function VNode({ id, data, selected }: NodeProps) {
  const d = data as VNodeData
  const t = useT()
  // zoom sémantique : en vue d'ensemble, le texte grossit (dans la limite du cercle) et les crochets disparaissent
  const zoom = useStore(st => st.transform[2])
  const compact = zoom < 0.6 && !d.editing
  // lisibilité (revue scout L26) : en vue d'ensemble, le nom d'une classe garde au moins 11 px à l'écran et peut déborder du cercle
  // (halo de fond) ; sous 30 % il est masqué, le survol (title) le donne. Les types de données gardent leur couleur et leur info-bulle.
  const tiny = zoom < 0.3 && !d.editing
  const fs = compact ? (d.vk === 'datatype' ? Math.min(14, Math.round(9 / zoom)) : d.vk === 'class' ? Math.min(37, Math.round(11 / zoom)) : undefined) : undefined
  const [v, setV] = useState(d.label)
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { if (d.editing) { setV(d.label); setTimeout(() => ref.current?.select(), 0) } }, [d.editing, d.label])
  const cls = ['of-vn', 'vk-' + d.vk, compact && 'compact', tiny && 'tiny', d.vk === 'datatype' && d.label === 'Literal' && 'lit', selected && 'sel', d.abstract && 'abstract', d.deprecated && 'deprecated', d.external && !d.deprecated && 'external', d.merged.length > 0 && 'eq', d.status, d.error && 'err'].filter(Boolean).join(' ')
  const sym = d.vk === 'anon' ? { and: '∩', or: '∪', not: '¬' }[d.op ?? 'or'] : null
  const brackets = [d.deprecated && t('ed.deprecated').toLowerCase(), d.external && t('lg.w.extb')].filter(Boolean) as string[]
  const sub = d.merged.length ? `[${d.merged.join(', ')}]` : brackets.length ? `[${brackets.join(', ')}]` : ''
  return (
    <div className={cls} style={fs ? { fontSize: fs } : undefined} title={d.vk === 'class' ? `${d.label} — ${d.curie}${d.merged.length ? ' ≡ ' + d.merged.join(', ') : ''}` : d.label}>
      {sym ? <span className="sym">{sym}</span>
        : d.editing
          ? <input ref={ref} className="nodrag nopan of-rename" value={v} aria-label={t('ed.rename')} onChange={e => setV(e.target.value)}
              onKeyDown={e => { e.stopPropagation(); if (e.key === 'Enter') d.onRename(id, v.trim() || null); if (e.key === 'Escape') d.onRename(id, null) }}
              onBlur={() => d.onRename(id, v.trim() || null)} />
          : <span className="vt"><b>{d.label}</b>{sub && <small>{sub}</small>}</span>}
      {d.status && <span className="of-flag" title={t('ed.prop.' + d.status)}><Icon name={d.status === 'add' ? 'plus' : 'pen'} /></span>}
      {d.hid > 0 && <span className="of-hid" title={t('ed.show.hidbadge', { n: d.hid })}>+{d.hid}</span>}
      {d.status && d.pkey && d.onProposal && <span className="of-pbtn nodrag nopan">
        <button type="button" className="ok" aria-label={t('ed.prop.accept')} title={t('ed.prop.accept')} onClick={e => { e.stopPropagation(); d.onProposal!(d.pkey!, true) }}><Icon name="check" /></button>
        <button type="button" className="no" aria-label={t('ed.prop.reject')} title={t('ed.prop.reject')} onClick={e => { e.stopPropagation(); d.onProposal!(d.pkey!, false) }}><Icon name="xmark" /></button></span>}
      {d.vk === 'class' && !d.readOnly && <Handle type="source" position={Position.Bottom} className="of-handle" title={t('ed.drag')} />}
      <Handle type="target" position={Position.Top} className="of-handle-in" isConnectable={false} />
    </div>
  )
})
