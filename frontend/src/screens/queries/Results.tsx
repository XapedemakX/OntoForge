import { useEffect, useMemo, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import { Button, EmptyState, Icon, SeverityBadge, Tabs } from '../../kit'
import { useT, tr } from '../../i18n'
import { download } from '../../ui'
import type { Cell, RunResult } from './qapi'

const short = (c: Cell | null | undefined) => (c ? (c.type === 'uri' ? c.value.replace(/^.*[#/]/, '') : c.value) : '')
function csvOf(r: RunResult): string {
  const q = (s: string) => (/[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s)
  return [r.columns.map(q).join(','), ...r.rows.map(row => r.columns.map(c => q(row[c]?.value ?? '')).join(','))].join('\n')
}

export function Results({ res, busy, error, ranOnce }: { res: RunResult | null; busy: boolean; error: string | null; ranOnce: boolean }) {
  const t = useT()
  const [view, setView] = useState<'table' | 'graph'>('table')
  const [sort, setSort] = useState<{ col: string; desc: boolean } | null>(null)
  useEffect(() => setSort(null), [res])
  const rows = useMemo(() => {
    if (!res) return []
    if (!sort) return res.rows
    const k = (r: Record<string, Cell | null>) => short(r[sort.col])
    const num = res.rows.every(r => { const v = k(r); return v === '' || !isNaN(Number(v)) })
    return [...res.rows].sort((a, b) => { const x = k(a), y = k(b); const c = num ? Number(x) - Number(y) : x.localeCompare(y, undefined, { numeric: true }); return sort.desc ? -c : c })
  }, [res, sort])
  const hasGraph = !!res && res.graph.nodes.length > 0
  return (
    <section className="qres" aria-label={t('q.res')} aria-busy={busy}>
      <div className="qres-hd">
        <h2>{t('q.res')}</h2>
        {res && <>
          <span className="sev info"><Icon name="list-ol" /><b>{res.boolean != null ? String(res.boolean) : res.rows.length}</b>{res.boolean != null ? 'ASK' : t('q.res.rows')}</span>
          <span className="sev info"><Icon name="stopwatch" /><b>{res.elapsed_ms}</b>ms</span>
          {res.truncated && <SeverityBadge severity="review" label={t('q.res.truncated')} />}
        </>}
        <span className="grow" />
        {res && res.rows.length > 0 && <Button size="sm" icon="file-csv" onClick={() => download('resultats.csv', csvOf(res), 'text/csv')}>{t('q.res.csv')}</Button>}
        <Tabs value={view} onChange={setView} items={[['table', t('q.res.table')], ['graph', t('q.res.graph')]]} />
      </div>
      {error && <div className="notice error" role="alert"><Icon name="circle-exclamation" /><div><b>{t('q.err.title')}</b><div>{error}</div></div></div>}
      {!error && !res && !busy && <p className="muted qres-empty">{ranOnce ? '' : t('q.res.idle')}</p>}
      {busy && <p className="muted qres-empty"><Icon name="spinner" className="fa-spin" /> {t('q.running')}</p>}
      {!error && res && view === 'table' && (res.rows.length === 0
        ? <EmptyState pose="loupe" title={t('q.res.none.title')}>{t('q.res.none.body')}</EmptyState>
        : <div className="qtable-wrap"><table className="qtable"><thead><tr>
            {res.columns.map(c => <th key={c} aria-sort={sort?.col === c ? (sort.desc ? 'descending' : 'ascending') : 'none'}><button type="button" onClick={() => setSort(s => (s?.col === c ? { col: c, desc: !s.desc } : { col: c, desc: false }))}>{c}<Icon name={sort?.col === c ? (sort.desc ? 'sort-down' : 'sort-up') : 'sort'} /></button></th>)}
          </tr></thead><tbody>
            {rows.map((r, i) => <tr key={i}>{res.columns.map(c => { const v = r[c]; return <td key={c} title={v?.value} className={v?.type === 'uri' ? 'uri' : ''}>{short(v)}{v?.['xml:lang'] && <sup>{v['xml:lang']}</sup>}</td> })}</tr>)}
          </tbody></table></div>)}
      {!error && res && view === 'graph' && (hasGraph ? <GraphView res={res} /> : <p className="muted qres-empty">{t('q.res.nograph')}</p>)}
    </section>
  )
}

function GraphView({ res }: { res: RunResult }) {
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!host.current) return
    const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()
    const [panel, ink, accent, line] = [css('--panel'), css('--ink'), css('--accent'), css('--line-strong')]
    const cols = [...new Set(res.graph.nodes.map(n => n.column ?? ''))]
    const palette = [css('--accent'), css('--info'), css('--review'), css('--lost')]
    const cy = cytoscape({
      container: host.current, wheelSensitivity: 0.3,
      elements: [
        ...res.graph.nodes.map(n => ({ data: { id: n.id, label: n.label, ci: cols.indexOf(n.column ?? '') } })),
        ...res.graph.edges.map(e => ({ data: { id: e.id, source: e.source, target: e.target, label: e.label } })),
      ],
      style: ([
        { selector: 'node', style: { 'background-color': panel, 'border-width': 2, 'border-color': (n: cytoscape.NodeSingular) => palette[n.data('ci') % palette.length], label: 'data(label)', color: ink, 'font-size': 13, 'text-valign': 'center', 'text-wrap': 'wrap', 'text-max-width': 120, shape: 'round-rectangle', width: 'label', height: 'label', padding: '8px' } },
        { selector: 'edge', style: { width: 1.4, 'line-color': line, 'target-arrow-color': line, 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', label: 'data(label)', 'font-size': 11, color: ink, 'text-background-color': panel, 'text-background-opacity': 0.85, 'text-background-padding': '1px', 'edge-text-rotation': 'autorotate' } },
        { selector: ':selected', style: { 'border-color': accent, 'line-color': accent, 'border-width': 3 } },
      ] as unknown) as cytoscape.StylesheetStyle[],
      layout: { name: 'cose', animate: false, padding: 24, nodeRepulsion: () => 40000, idealEdgeLength: () => 140 } as cytoscape.LayoutOptions,
    })
    return () => cy.destroy()
  }, [res])
  return <div className="qgraph" ref={host} role="img" aria-label={tr('q.graph.aria')} />
}
