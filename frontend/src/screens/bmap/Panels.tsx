// Panneaux latéraux de la carte métier : inspecteur, zones, scénarios.
import { useState } from 'react'
import { Button, Icon } from '../../kit'
import { useT } from '../../i18n'
import { EDGE_STYLES, ZONE_STRATEGIES, styleOf, type BEdge, type BMap, type BNode, type BScenario, type ZoneStrategy } from './types'
import { palette, roleOrder, roleInk } from './palette'
import { roleLabel } from './render'
import { setEdgeStyle as setStyle, setNode, moveToZone, toggleScenarioNode, setZone, addZone, delZone, addScenario, setScenario, delScenario } from './ops'

export type BSel = { kind: 'node' | 'edge'; id: string } | null
export interface PanelCtx {
  map: BMap; ro: boolean; sel: BSel; setSel: (s: BSel) => void; scenario: BScenario | null
  edit: (f: (m: BMap) => BMap) => void
  setActive: (id: string | null) => void
}

const Row = ({ k, children }: { k: string; children: React.ReactNode }) => <div className="bm-row"><span className="bm-k">{k}</span><span className="bm-v">{children}</span></div>

export function Inspector({ c }: { c: PanelCtx }) {
  const t = useT(); const { map, sel, ro } = c
  if (!sel) return <div className="bm-empty muted" data-testid="bm-insp-empty">{t('bm.insp.pick')}</div>
  if (sel.kind === 'node') {
    const n = map.nodes.find(x => x.id === sel.id); if (!n) return null
    return <NodeInspector c={c} n={n} />
  }
  const e = map.edges.find(x => x.id === sel.id); if (!e) return null
  const st = styleOf(e, c.scenario), by = (id: string) => map.nodes.find(n => n.id === id)?.label ?? id
  return <div className="bm-insp" data-testid="bm-insp-edge">
    <h3>{e.label}</h3>
    <Row k={t('bm.insp.from')}>{e.frame ? (map.frames.find(f => f.id === e.frame)?.title ?? e.frame) : by(e.from)}</Row>
    <Row k={t('bm.insp.to')}>{by(e.to)}</Row>
    {e.inverse_label && <Row k={t('bm.insp.inverse')}>{e.inverse_label}</Row>}
    {e.link && <Row k={t('bm.insp.link')}>{t('bm.insp.link.' + e.link)}</Row>}
    <Row k={t('bm.insp.style')}>{t('bm.style.' + st)}</Row>
    {e.union && <div className="muted" data-testid="bm-insp-union">{t('bm.insp.union')}</div>}
    {c.scenario && !e.frame && !ro ? <div className="bm-styles" role="group" aria-label={t('bm.insp.setStyle', { name: c.scenario.name })}>
      <span className="bm-k">{t('bm.insp.setStyle', { name: c.scenario.name })}</span>
      {EDGE_STYLES.map(s => <button key={s} type="button" className={'bm-chip' + (c.scenario!.edge_styles[e.id] === s ? ' on' : '')} aria-pressed={c.scenario!.edge_styles[e.id] === s} data-style={s}
        onClick={() => c.edit(m => setStyle(m, c.scenario!.id, e.id, c.scenario!.edge_styles[e.id] === s ? null : s))}>
        <i className="bm-sw" style={{ background: palette(false).edge[s].color }} />{t('bm.style.' + s)}</button>)}
    </div> : !c.scenario && <div className="muted">{t('bm.insp.noScenario')}</div>}
  </div>
}


function NodeInspector({ c, n }: { c: PanelCtx; n: BNode }) {
  const t = useT(); const { map, ro } = c
  const roles = roleOrder(map.nodes)
  const out = map.edges.filter(e => e.from === n.id), inc = map.edges.filter(e => e.to === n.id)
  const by = (id: string) => map.nodes.find(x => x.id === id)?.label ?? id
  const [newRole, setNewRole] = useState('')
  const ink = roleInk(n.role ? roles.indexOf(n.role) : -1, palette(false), map.legend.find(l => l.role === n.role)?.color)
  const rel = (e: BEdge, other: string, dir: string) => <li key={e.id}><button type="button" className="bm-link" onClick={() => c.setSel({ kind: 'edge', id: e.id })}>{dir} {e.label} · {by(other)}</button></li>
  return <div className="bm-insp" data-testid="bm-insp-node">
    <h3><i className="bm-dot" style={{ background: ink.fill, borderColor: ink.stroke }} />{n.label}</h3>
    <Row k={t('bm.insp.class')}><code>{n.id.split(/[#/]/).pop()}</code></Row>
    <Row k={t('bm.insp.zone')}>
      <select value={n.zone ?? ''} disabled={ro} aria-label={t('bm.insp.zone')} onChange={e => c.edit(m => moveToZone(m, n.id, e.target.value || null))}>
        <option value="">{t('bm.zones.none')}</option>{map.zones.map(z => <option key={z.id} value={z.id}>{z.title}</option>)}</select></Row>
    <Row k={t('bm.insp.role')}>
      <select value={n.role} disabled={ro} aria-label={t('bm.insp.role')} data-testid="bm-role" onChange={e => c.edit(m => setNode(m, n.id, { role: e.target.value }))}>
        <option value="">{t('bm.role.none')}</option>{[...new Set([...roles, n.role].filter(Boolean))].map(r => <option key={r} value={r}>{roleLabel(t, r)}</option>)}</select>
      <span className="muted bm-src" data-testid="bm-role-src">{n.role ? t(n.roleSource === 'manual' ? 'bm.insp.chosen' : 'bm.insp.derived') : ''}</span>
      {!ro && <span className="bm-inline"><input value={newRole} placeholder={t('bm.insp.newRole')} aria-label={t('bm.insp.newRole')} onChange={e => setNewRole(e.target.value)} />
        <Button size="sm" disabled={!newRole.trim()} onClick={() => { c.edit(m => setNode(m, n.id, { role: newRole.trim() })); setNewRole('') }}>{t('common.apply')}</Button></span>}
    </Row>
    <Row k={t('bm.insp.count')}>{n.count == null ? <span className="muted">—</span> : n.count.toLocaleString()}</Row>
    <label className="bm-chk"><input type="checkbox" checked={n.faded} disabled={ro} onChange={e => c.edit(m => setNode(m, n.id, { faded: e.target.checked }))} data-testid="bm-faded" />{t('bm.insp.faded')}</label>
    <label className="bm-chk"><input type="checkbox" checked={n.pinned} disabled={ro} onChange={e => c.edit(m => setNode(m, n.id, { pinned: e.target.checked }))} data-testid="bm-pinned" />{t('bm.insp.pinned')}</label>
    {c.scenario && <label className="bm-chk"><input type="checkbox" checked={c.scenario.nodes.includes(n.id)} disabled={ro} onChange={() => c.edit(m => toggleScenarioNode(m, c.scenario!.id, n.id))} />{t('bm.insp.inScenario', { name: c.scenario.name })}</label>}
    <h4>{t('bm.insp.rels', { n: out.length + inc.length })}</h4>
    <ul className="bm-rels">{out.map(e => rel(e, e.to, '→'))}{inc.map(e => rel(e, e.from, '←'))}</ul>
  </div>
}

// ---------------------------------------------------------------- zones
export function ZonesPanel({ c, suggest, busy }: { c: PanelCtx; suggest: (s: ZoneStrategy) => void; busy: boolean }) {
  const t = useT(); const { map, ro } = c
  const [strategy, setStrategy] = useState<ZoneStrategy>('perimeters')
  const [over, setOver] = useState<string | null>(null)
  const label = (id: string) => map.nodes.find(n => n.id === id)?.label ?? id
  const drop = (zoneId: string | null) => (e: React.DragEvent) => { e.preventDefault(); setOver(null); const id = e.dataTransfer.getData('text/plain'); if (id) c.edit(m => moveToZone(m, id, zoneId)) }
  const chip = (id: string) => <span key={id} className="bm-cls" draggable={!ro} data-node={id} onDragStart={e => { e.dataTransfer.setData('text/plain', id); e.dataTransfer.effectAllowed = 'move' }}
    onClick={() => c.setSel({ kind: 'node', id })} title={label(id)}>{label(id)}</span>
  const unzoned = map.nodes.filter(n => !n.zone)
  const zoneBox = (key: string, zoneId: string | null, head: React.ReactNode, ids: string[]) => <div key={key} className={'bm-zone' + (over === key ? ' over' : '')} data-testid="bm-zone" data-zone={key}
    onDragOver={e => { if (!ro) { e.preventDefault(); setOver(key) } }} onDragLeave={() => setOver(o => (o === key ? null : o))} onDrop={drop(zoneId)}>
    {head}<div className="bm-cls-list">{ids.map(chip)}{ids.length === 0 && <span className="muted">{t('bm.zones.empty')}</span>}</div></div>
  return <div className="bm-zones">
    {!ro && <div className="bm-suggest">
      <select value={strategy} onChange={e => setStrategy(e.target.value as ZoneStrategy)} aria-label={t('bm.zones.strategy')} data-testid="bm-strategy">
        {ZONE_STRATEGIES.map(s => <option key={s} value={s}>{t('bm.strat.' + s)}</option>)}</select>
      <Button size="sm" variant="primary" icon="wand-magic-sparkles" disabled={busy} onClick={() => suggest(strategy)} data-testid="bm-suggest-zones">{t('bm.zones.suggest')}</Button>
    </div>}
    <p className="muted bm-hint">{t('bm.strat.' + strategy + '.d')}</p>
    {map.zones.map(z => zoneBox(z.id, z.id, <div className="bm-zhead">
      <input type="color" value={/^#[0-9a-f]{6}$/i.test(z.color) ? z.color : '#94a3b8'} disabled={ro} aria-label={t('bm.zones.color')} onChange={e => c.edit(m => setZone(m, z.id, { color: e.target.value }))} />
      <input className="bm-zt" value={z.title} disabled={ro} aria-label={t('bm.zones.title')} onChange={e => c.edit(m => setZone(m, z.id, { title: e.target.value }))} />
      {!ro && <button type="button" className="btn ghost sm" aria-label={t('bm.zones.del', { name: z.title })} title={t('bm.zones.del', { name: z.title })} onClick={() => c.edit(m => delZone(m, z.id))}><Icon name="trash" /></button>}
      <input className="bm-zs" value={z.subtitle} disabled={ro} placeholder={t('bm.zones.subtitle')} aria-label={t('bm.zones.subtitle')} onChange={e => c.edit(m => setZone(m, z.id, { subtitle: e.target.value }))} />
    </div>, z.members))}
    {(unzoned.length > 0 || !ro) && zoneBox('none', null, <div className="bm-zhead"><b>{t('bm.zones.none')}</b></div>, unzoned.map(n => n.id))}
    {!ro && <Button size="sm" icon="plus" onClick={() => c.edit(m => addZone(m, t('bm.zones.newName')).map)} data-testid="bm-add-zone">{t('bm.zones.add')}</Button>}
  </div>
}

// ---------------------------------------------------------------- scénarios
export function ScenariosPanel({ c }: { c: PanelCtx }) {
  const t = useT(); const { map, ro, scenario } = c
  const [name, setName] = useState(''); const [q, setQ] = useState('')
  const by = (id: string) => map.nodes.find(n => n.id === id)?.label ?? id
  const edges = map.edges.filter(e => !e.frame && (!q || (e.label + by(e.from) + by(e.to)).toLowerCase().includes(q.toLowerCase())))
  return <div className="bm-scen">
    <div className="bm-suggest">
      <select value={scenario?.id ?? ''} onChange={e => c.setActive(e.target.value || null)} aria-label={t('bm.sc.active')} data-testid="bm-sc-select">
        <option value="">{t('bm.sc.none')}</option>{map.scenarios.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
    </div>
    {!ro && <form className="bm-suggest" onSubmit={e => { e.preventDefault(); if (!name.trim()) return; const r = addScenario(map, name.trim()); c.edit(() => r.map); c.setActive(r.id); setName('') }}>
      <input value={name} onChange={e => setName(e.target.value)} placeholder={t('bm.sc.newName')} aria-label={t('bm.sc.newName')} data-testid="bm-sc-name" />
      <Button size="sm" variant="primary" icon="plus" type="submit" disabled={!name.trim()} data-testid="bm-sc-add">{t('bm.sc.add')}</Button>
    </form>}
    {scenario && <>
      <label className="bm-lab"><span>{t('bm.sc.name')}</span><input value={scenario.name} disabled={ro} onChange={e => c.edit(m => setScenario(m, scenario.id, { name: e.target.value }))} /></label>
      <label className="bm-lab"><span>{t('bm.sc.notes')}</span><textarea rows={7} value={scenario.description} disabled={ro} placeholder={t('bm.sc.notesPh')} data-testid="bm-sc-notes" onChange={e => c.edit(m => setScenario(m, scenario.id, { description: e.target.value }))} /></label>
      <small className="muted">{t('bm.sc.md')}</small>
      <h4>{t('bm.sc.styles')}</h4>
      <input value={q} onChange={e => setQ(e.target.value)} placeholder={t('bm.sc.filter')} aria-label={t('bm.sc.filter')} />
      <ul className="bm-edgelist">{edges.map(e => <li key={e.id} className={c.sel?.id === e.id ? 'on' : ''}>
        <button type="button" className="bm-link" onClick={() => c.setSel({ kind: 'edge', id: e.id })}>{by(e.from)} → {by(e.to)} · {e.label}</button>
        <select value={scenario.edge_styles[e.id] ?? ''} disabled={ro} aria-label={t('bm.insp.style') + ' ' + e.label} onChange={ev => c.edit(m => setStyle(m, scenario.id, e.id, ev.target.value || null))}>
          <option value="">{t('bm.sc.base')}</option>{EDGE_STYLES.map(s => <option key={s} value={s}>{t('bm.style.' + s)}</option>)}</select></li>)}</ul>
      {!ro && <Button size="sm" variant="danger" icon="trash" onClick={() => { const id = scenario.id; c.setActive(null); c.edit(m => delScenario(m, id)) }}>{t('bm.sc.del')}</Button>}
    </>}
    {!scenario && <p className="muted">{t('bm.sc.hint')}</p>}
  </div>
}
