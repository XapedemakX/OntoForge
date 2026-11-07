import { useEffect, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import { api, type EdgeType, type NodeType, type PGModel, type PGProperty } from '../api'
import type { ScreenProps } from '../shell/types'
import { Empty, ErrorView, Spin, Tabs, useLoad } from '../ui'
import { useT } from '../i18n'

const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()

function Diagram({ pg, onSel }: { pg: PGModel; onSel: (s: { kind: 'node'; n: NodeType } | { kind: 'edge'; e: EdgeType } | null) => void }) {
  const t = useT()
  const host = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [themeTick, setThemeTick] = useState(0)
  useEffect(() => { const o = new MutationObserver(() => setThemeTick(x => x + 1)); o.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] }); return () => o.disconnect() }, [])
  useEffect(() => {
    if (!host.current) return
    const ink = css('--ink'), accent = css('--accent'), line = css('--muted'), panel = css('--panel2'), review = css('--review')
    const nodes = Object.values(pg.node_types).map(n => ({ data: { id: n.name, label: n.name + (n.labels.length > 1 ? '\n' + n.labels.slice(1).map(l => ':' + l).join(' ') : ''), abs: n.abstract ? 1 : 0 } }))
    const names = new Set(Object.keys(pg.node_types))
    const edges = pg.edge_types.filter(e => names.has(e.from) && names.has(e.to)).map((e, i) => ({ data: { id: 'e' + i, source: e.from, target: e.to, label: e.name, derived: e.derived ? 1 : 0, idx: i } }))
    const many = edges.length > 14
    const cy = cytoscape({
      container: host.current, elements: [...nodes, ...edges], wheelSensitivity: 0.3, minZoom: 0.15, maxZoom: 3, userZoomingEnabled: true,
      style: ([
        { selector: 'node', style: { 'background-color': panel, 'border-width': 1.5, 'border-color': accent, label: 'data(label)', color: ink, 'font-size': 14, 'font-weight': 600, 'text-valign': 'center', 'text-halign': 'center', 'text-wrap': 'wrap', shape: 'round-rectangle', width: 'label', height: 'label', padding: '10px' } },
        { selector: 'node[abs = 1]', style: { 'border-style': 'dashed' } },
        { selector: 'edge', style: { width: 1.4, 'line-color': line, 'target-arrow-color': line, 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', label: 'data(label)', 'font-size': 12, 'text-opacity': many ? 0 : 1, color: ink, 'text-background-color': css('--panel'), 'text-background-opacity': 0.85, 'text-background-padding': '1px', 'edge-text-rotation': 'autorotate' } },
        { selector: 'edge[derived = 1]', style: { 'line-style': 'dashed', 'line-color': review, 'target-arrow-color': review } },
        { selector: 'edge.hl, edge:selected', style: { 'text-opacity': 1, 'z-index': 10 } },
        { selector: ':selected', style: { 'border-width': 3, 'line-color': accent, 'target-arrow-color': accent } },
      ] as unknown) as cytoscape.StylesheetStyle[],
    })
    const iso = cy.nodes().filter(n => n.degree(false) === 0)
    const conn = cy.elements().not(iso)
    if (conn.length) conn.layout({ name: 'cose', animate: false, nodeRepulsion: () => 60000, idealEdgeLength: () => 170, nodeOverlap: 80, gravity: 0.5, numIter: 3000, padding: 20, randomize: true } as cytoscape.LayoutOptions).run()
    const bb = conn.length ? conn.boundingBox() : { x1: 0, x2: 0, y1: 0, y2: 0 }
    iso.forEach((n, i) => { n.position({ x: bb.x2 + 140 + (i % 2) * 190, y: bb.y1 + 30 + Math.floor(i / 2) * 50 }) })
    cy.fit(undefined, 30)
    cyRef.current = cy
    // Lisibilité : à l'écran, jamais sous 12 px (14 px pour les nœuds) quel que soit le zoom d'ajustement.
    const rescale = () => {
      const k = Math.max(1, 1 / cy.zoom())
      cy.style().selector('node').style({ 'font-size': 14 * k }).selector('edge').style({ 'font-size': 12 * k }).update()
    }
    cy.on('zoom', rescale); rescale()
    cy.on('mouseover', 'node', ev => ev.target.connectedEdges().addClass('hl'))
    cy.on('mouseout', 'node', ev => ev.target.connectedEdges().removeClass('hl'))
    cy.on('mouseover', 'edge', ev => ev.target.addClass('hl'))
    cy.on('mouseout', 'edge', ev => ev.target.removeClass('hl'))
    cy.on('tap', 'node', ev => onSel({ kind: 'node', n: pg.node_types[ev.target.id()] }))
    cy.on('tap', 'edge', ev => onSel({ kind: 'edge', e: pg.edge_types[ev.target.data('idx')] }))
    cy.on('tap', ev => { if (ev.target === cy) onSel(null) })
    return () => { cyRef.current = null; cy.destroy() }
  }, [pg, themeTick])
  const zoomBy = (f: number) => { const cy = cyRef.current; if (cy) cy.zoom({ level: cy.zoom() * f, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } }) }
  const fitAll = () => cyRef.current?.fit(undefined, 30)
  return <div className="cy-wrap" data-tour="model-diagram"><div ref={host} className="cy" />
    <div className="cy-zoom" role="group" aria-label={t('mo.zoom.group')}>
      <button type="button" onClick={() => zoomBy(1.25)} title={t('mo.zoom.in')} aria-label={t('mo.zoom.in')}>+</button>
      <button type="button" onClick={() => zoomBy(0.8)} title={t('mo.zoom.out')} aria-label={t('mo.zoom.out')}>−</button>
      <button type="button" onClick={fitAll} title={t('mo.fit.title')} aria-label={t('mo.fit')}>{t('mo.fit')}</button>
    </div>
    <div className="legend">{t('mo.legend')}</div></div>
}

const propRow = (yes: string) => (p: PGProperty) => <tr key={p.name}><td className="mono">{p.name}</td><td>{p.type}{p.is_list ? '[]' : ''}</td><td>{p.required ? yes : ''}</td><td>{p.unique ? yes : ''}</td><td>{p.indexed ? yes : ''}</td><td className="muted">{p.note ?? p.description ?? ''}</td></tr>
const PropTable = ({ props }: { props: PGProperty[] }) => { const t = useT(); return props.length === 0 ? <span className="muted">{t('mo.noprops')}</span> :
  <table className="t"><thead><tr><th>{t('mo.col.property')}</th><th>{t('mo.col.type')}</th><th>{t('mo.col.required')}</th><th>{t('mo.col.unique')}</th><th>{t('mo.col.indexed')}</th><th>{t('mo.col.note')}</th></tr></thead><tbody>{props.map(propRow(t('common.yes')))}</tbody></table> }

export function Model({ p, target }: ScreenProps) {
  const t = useT()
  const { data: pg, error, loading } = useLoad(() => api.analyze(p.id, target), [p.id, target, p.updated_at])
  const [sel, setSel] = useState<{ kind: 'node'; n: NodeType } | { kind: 'edge'; e: EdgeType } | null>(null)
  const [tab, setTab] = useState<'nodes' | 'edges' | 'vals' | 'mats'>('nodes')
  const pending = pg?.findings.filter(f => f.severity !== 'auto' && !f.chosen).length ?? 0
  return (
    <div className="page">
      <div className="page-head"><h1>{t('mo.title')}</h1><span className="badge">{target === 'curiosity' ? 'Curiosity' : 'Neo4j'}</span>
        {pg && pending > 0 && <span className="notice warn" style={{ padding: '2px 10px' }}>{t('mo.pending', { n: pending })}</span>}</div>
      {loading && !pg && <Spin />}<ErrorView error={error} what={t('mo.title')} />
      {pg && Object.keys(pg.node_types).length === 0 && <Empty title={t('mo.empty.t')}>{t('mo.empty.b')}</Empty>}
      {pg && Object.keys(pg.node_types).length > 0 && <>
        <div className="model-grid">
          <Diagram pg={pg} onSel={setSel} />
          <div className="card" style={{ alignSelf: 'start', maxHeight: 560, overflow: 'auto' }}>
            <div className="hd"><h2>{t('mo.details')}</h2></div>
            <div className="bd col">
              {!sel && <span className="muted">{t('mo.pick')}</span>}
              {sel?.kind === 'node' && <><h3>{sel.n.name}</h3><div className="chips">{sel.n.labels.map(l => <span className="badge" key={l}>:{l}</span>)}{sel.n.abstract && <span className="badge">{t('mo.abstract')}</span>}</div>
                {sel.n.description && <div>{sel.n.description}</div>}
                {sel.n.key.length > 0 && <div>{t('mo.key')} <code>{sel.n.key.join(', ')}</code></div>}
                {sel.n.discriminator && <div>{t('mo.discriminator')} <code>{sel.n.discriminator}</code> = {sel.n.discriminator_values.join(', ')}</div>}
                {sel.n.source.length > 0 && <div className="muted">{t('mo.source')} {sel.n.source.map(s => s.split(/[#/]/).pop()).join(', ')}</div>}
                <PropTable props={sel.n.properties} /></>}
              {sel?.kind === 'edge' && <><h3>{sel.e.name}{sel.e.derived && <span className="badge review" style={{ marginLeft: 6 }}>{t('mo.derived')}</span>}</h3>
                <div className="mono">{sel.e.from} → {sel.e.to}{sel.e.reverse ? `  (${t('mo.inverse')} ${sel.e.reverse})` : ''}</div>
                <div>{t('mo.cardinality', { out: sel.e.cardinality.out, in: sel.e.cardinality.in })}</div>
                {sel.e.symmetric && <div>{t('mo.symmetric')}</div>}{sel.e.note && <div className="rationale">{sel.e.note}</div>}
                {sel.e.properties.length > 0 && <PropTable props={sel.e.properties} />}</>}
            </div>
          </div>
        </div>
        <Tabs value={tab} onChange={setTab} items={[['nodes', `${t('mo.tab.nodes')} ${Object.keys(pg.node_types).length}`], ['edges', `${t('mo.tab.edges')} ${pg.edge_types.length}`], ['vals', `${t('mo.tab.vals')} ${pg.validations.length}`], ['mats', `${t('mo.tab.mats')} ${pg.materializations.length}`]]} />
        <div className="tscroll" style={{ maxHeight: 'none' }}>
          {tab === 'nodes' && <table className="t"><thead><tr><th>{t('mo.col.type')}</th><th>{t('mo.col.labels')}</th><th>{t('mo.col.key')}</th><th>{t('mo.col.properties')}</th><th>{t('mo.col.source')}</th></tr></thead><tbody>
            {Object.values(pg.node_types).map(n => <tr key={n.name} onClick={() => setSel({ kind: 'node', n })} style={{ cursor: 'pointer' }}><td><b>{n.name}</b>{n.abstract && <span className="badge" style={{ marginLeft: 6 }}>{t('mo.abstract')}</span>}</td><td className="mono">{n.labels.join(' ')}</td><td className="mono">{n.key.join(', ')}</td><td className="mono">{n.properties.map(x => x.name + (x.required ? '*' : '')).join(', ')}</td><td className="muted">{n.source.map(s => s.split(/[#/]/).pop()).join(', ')}</td></tr>)}</tbody></table>}
          {tab === 'edges' && <table className="t"><thead><tr><th>{t('mo.col.relation')}</th><th>{t('mo.col.from')}</th><th>{t('mo.col.to')}</th><th>{t('mo.col.inverse')}</th><th>{t('mo.col.cardinality')}</th><th>{t('mo.col.properties')}</th><th>{t('mo.col.note')}</th></tr></thead><tbody>
            {pg.edge_types.map((e, i) => <tr key={i} onClick={() => setSel({ kind: 'edge', e })} style={{ cursor: 'pointer' }}><td className="mono">{e.name}{e.derived && <span className="badge review" style={{ marginLeft: 6 }}>{t('mo.derived')}</span>}</td><td>{e.from}</td><td>{e.to}</td><td className="mono">{e.reverse ?? ''}</td><td className="mono">{e.cardinality.out} / {e.cardinality.in}</td><td className="mono">{e.properties.map(x => x.name).join(', ')}</td><td className="muted">{e.note ?? ''}</td></tr>)}</tbody></table>}
          {tab === 'vals' && (pg.validations.length === 0 ? <div className="empty">{t('mo.noval')}</div> : <table className="t"><thead><tr><th>{t('mo.col.type')}</th><th>{t('mo.col.target')}</th><th>{t('mo.col.description')}</th><th>{t('mo.col.severity')}</th></tr></thead><tbody>
            {pg.validations.map(v => <tr key={v.id}><td><span className="badge">{v.kind}</span></td><td className="mono">{[v.node_type, v.edge_type, v.property].filter(Boolean).join('.')}</td><td>{v.description}</td><td><span className={'badge ' + v.severity}>{v.severity}</span></td></tr>)}</tbody></table>)}
          {tab === 'mats' && (pg.materializations.length === 0 ? <div className="empty">{t('mo.nomat')}</div> : <table className="t"><thead><tr><th>{t('mo.col.type')}</th><th>{t('mo.col.target')}</th><th>{t('mo.col.description')}</th></tr></thead><tbody>
            {pg.materializations.map(m => <tr key={m.id}><td><span className="badge">{m.kind}</span></td><td className="mono">{m.edge_type ?? m.node_type ?? ''}{m.chain.length ? ' ← ' + m.chain.join(' ∘ ') : ''}</td><td>{m.description}</td></tr>)}</tbody></table>)}
        </div>
      </>}
    </div>
  )
}
