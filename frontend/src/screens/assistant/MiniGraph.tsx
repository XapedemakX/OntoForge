import { useMemo } from 'react'
import { labelOf, type OntoModel } from '../../api'
import type { ProposalItem } from '../../lib/proposal'

/** Mini-graphe de la proposition : vert = ajout, orange = modification, gris = classe existante citée. */
export function MiniGraph({ onto, cur, items, lang, onPick, picked }: { onto: OntoModel; cur: OntoModel; items: ProposalItem[]; lang: string; onPick?: (id: string) => void; picked?: string | null }) {
  const g = useMemo(() => {
    const status = new Map<string, 'add' | 'modify' | 'ctx'>()
    const owner = new Map<string, string>() // IRI de classe -> id d'élément
    const props = new Map<string, string[]>()
    const edges: { a: string; b: string; kind: 'isa' | 'rel'; item: string; label?: string }[] = []
    const touch = (iri: string | undefined, s: 'add' | 'modify' | 'ctx') => { if (iri && (onto.classes[iri] || cur.classes[iri]) && (!status.has(iri) || s !== 'ctx')) status.set(iri, s) }
    for (const it of items) {
      if (it.type === 'class') { touch(it.entity_iri, it.kind); owner.set(it.entity_iri, it.id) }
      if (it.type === 'datatypeProperty' && it.source) { touch(it.source, 'ctx'); props.set(it.source, [...(props.get(it.source) ?? []), it.label]) }
    }
    for (const it of items) {
      if (it.type === 'subClassOf' && it.source && it.target) { touch(it.source, 'ctx'); touch(it.target, 'ctx'); edges.push({ a: it.source, b: it.target, kind: 'isa', item: it.id }) }
      if (it.type === 'objectProperty' && it.source && it.target) { touch(it.source, 'ctx'); touch(it.target, 'ctx'); edges.push({ a: it.source, b: it.target, kind: 'rel', item: it.id, label: it.label }) }
      if (it.type === 'class') for (const p of onto.classes[it.entity_iri]?.sub_class_of ?? []) { touch(p, 'ctx'); edges.push({ a: it.entity_iri, b: p, kind: 'isa', item: it.id }) }
    }
    const iris = [...status.keys()]
    const W = 440; const n = iris.length
    const cols = Math.max(1, Math.min(3, Math.ceil(Math.sqrt(n))))
    const rows = Math.ceil(n / cols)
    const cw = W / cols; const rh = 92
    const pos = new Map(iris.map((iri, i) => [iri, { x: cw * (i % cols) + cw / 2 + (Math.floor(i / cols) % 2 ? cw * 0.06 : 0), y: 40 + Math.floor(i / cols) * rh }]))
    return { iris, status, pos, edges, props, owner, W, H: Math.max(120, rows * rh + 24) }
  }, [onto, cur, items])
  if (!g.iris.length) return null
  const col = (s: string) => (s === 'add' ? 'var(--auto)' : s === 'modify' ? 'var(--review-edge)' : 'var(--line-strong)')
  return (
    <svg className="mgraph" viewBox={`0 0 ${g.W} ${g.H}`} role="img" aria-label="Mini-graphe de la proposition">
      <defs><marker id="mg-arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1 L9 5 L1 9" fill="none" stroke="context-stroke" strokeWidth="1.4" /></marker></defs>
      {g.edges.map((e, i) => {
        const a = g.pos.get(e.a); const b = g.pos.get(e.b); if (!a || !b) return null
        const mx = (a.x + b.x) / 2; const my = (a.y + b.y) / 2
        const isNew = items.find(x => x.id === e.item)?.kind === 'add'
        return <g key={i} className={'mg-edge ' + e.kind} style={{ color: isNew ? 'var(--auto)' : 'var(--review-edge)' }}>
          <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="currentColor" strokeWidth="1.6" strokeDasharray={e.kind === 'isa' ? '5 3' : undefined} markerEnd="url(#mg-arr)" />
          {e.label && <text x={mx} y={my - 4} textAnchor="middle" className="mg-elabel">{e.label}</text>}
        </g>
      })}
      {g.iris.map(iri => {
        const p = g.pos.get(iri)!; const s = g.status.get(iri)!
        const label = labelOf(onto.classes[iri] ?? cur.classes[iri], iri, lang)
        const w = Math.max(70, Math.min(150, label.length * 7.4 + 24)); const id = g.owner.get(iri)
        const at = g.props.get(iri) ?? []; 
        return <g key={iri} className={'mg-node' + (id && picked === id ? ' on' : '')} onClick={() => id && onPick?.(id)} style={{ cursor: id && onPick ? 'pointer' : 'default' }}>
          <rect x={p.x - w / 2} y={p.y - 16} width={w} height="32" rx="7" fill="var(--panel)" stroke={col(s)} strokeWidth={s === 'ctx' ? 1.2 : 2} strokeDasharray={s === 'ctx' ? '3 3' : undefined} />
          <text x={p.x} y={p.y + 4} textAnchor="middle" className="mg-label">{label.length > 20 ? label.slice(0, 19) + '…' : label}</text>
          {at.length > 0 && <text x={p.x} y={p.y + 30} textAnchor="middle" className="mg-sub">{at.length} attr.</text>}
          {s !== 'ctx' && <circle cx={p.x + w / 2 - 2} cy={p.y - 16} r="5" fill={col(s)} />}
        </g>
      })}
    </svg>
  )
}
