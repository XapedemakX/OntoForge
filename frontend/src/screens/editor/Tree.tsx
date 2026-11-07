import { useEffect, useMemo, useState } from 'react'
import { Icon } from '../../kit'
import { useT } from '../../i18n'
import type { GEdge, GNode } from './types'

/** Arbre des classes (parents -> enfants), synchronisé avec la sélection du canevas. */
export function Tree({ nodes, edges, selected, props, onSelect, onSelectProp, onClose }: {
  nodes: GNode[]; edges: GEdge[]; selected: Set<string>
  props: { iri: string; label: string }[]
  onSelect: (iri: string, additive: boolean) => void; onSelectProp: (iri: string) => void; onClose: () => void
}) {
  const t = useT()
  const [shut, setShut] = useState<Set<string>>(new Set())
  const [q, setQ] = useState('')
  const { kids, roots, byId } = useMemo(() => {
    const byId = new Map(nodes.filter(n => n.kind === 'class').map(n => [n.id, n]))
    const kids = new Map<string, string[]>(); const hasParent = new Set<string>()
    for (const e of edges) if (e.kind === 'subClassOf' && byId.has(e.source) && byId.has(e.target)) { (kids.get(e.target) ?? kids.set(e.target, []).get(e.target)!).push(e.source); hasParent.add(e.source) }
    const sort = (a: string, b: string) => byId.get(a)!.label.localeCompare(byId.get(b)!.label)
    kids.forEach(v => v.sort(sort))
    return { kids, byId, roots: [...byId.keys()].filter(i => !hasParent.has(i)).sort(sort) }
  }, [nodes, edges])
  // déplie les ancêtres d'une classe sélectionnée
  useEffect(() => {
    if (selected.size !== 1) return
    const [s] = selected; const up = edges.filter(e => e.kind === 'subClassOf' && e.source === s).map(e => e.target)
    if (up.some(u => shut.has(u))) setShut(x => { const n = new Set(x); up.forEach(u => n.delete(u)); return n })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected])
  const match = (i: string) => !q || byId.get(i)!.label.toLowerCase().includes(q.toLowerCase())
  const row = (i: string, depth: number, path: string[]): React.ReactNode => {
    const n = byId.get(i)!; const k = (kids.get(i) ?? []).filter(x => !path.includes(x))
    const open = !shut.has(i) || !!q
    return <li key={path.join('>') + i} role="treeitem" aria-expanded={k.length ? open : undefined} aria-selected={selected.has(i)}>
      <div className={'of-trow' + (selected.has(i) ? ' sel' : '') + (match(i) ? '' : ' dim')} style={{ paddingLeft: 6 + depth * 14 }}>
        {k.length ? <button type="button" className="tg" aria-label={open ? t('ed.tree.fold') : t('ed.tree.unfold')} onClick={() => setShut(x => { const s = new Set(x); s.has(i) ? s.delete(i) : s.add(i); return s })}><Icon name={open ? 'chevron-down' : 'chevron-right'} /></button> : <span className="tg" />}
        <button type="button" className="nm" onClick={e => onSelect(i, e.shiftKey || e.metaKey || e.ctrlKey)}><Icon name={n.icon || 'circle-nodes'} /><span className={n.abstract ? 'abs' : ''}>{n.label}</span></button>
      </div>
      {k.length > 0 && open && <ul role="group">{k.map(c => row(c, depth + 1, [...path, i]))}</ul>}
    </li>
  }
  return (
    <aside className="of-tree" aria-label={t('ed.tree')}>
      <header><b>{t('ed.tree')}</b><span className="grow" /><button type="button" className="btn ghost iconly" aria-label={t('ed.tree.hide')} title={t('ed.tree.hide')} onClick={onClose}><Icon name="angles-left" /></button></header>
      <div className="of-tsearch"><Icon name="magnifying-glass" /><input type="text" aria-label={t('ed.search')} placeholder={t('ed.tree.filter')} value={q} onChange={e => setQ(e.target.value)} /></div>
      <ul role="tree" className="of-tlist">{roots.map(r => row(r, 0, []))}</ul>
      {!!props.length && <div className="of-tprops"><h4>{t('ed.tree.props')}</h4>
        <ul>{props.map(p => <li key={p.iri}><button type="button" onClick={() => onSelectProp(p.iri)}><Icon name="arrow-right-long" />{p.label}</button></li>)}</ul></div>}
    </aside>
  )
}
