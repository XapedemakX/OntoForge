import { BottomSheet, Icon, Segmented } from '../../kit'
import { useI18n } from '../../i18n'
import type { Mode, ShowPrefs } from './prefs'

type EdgeFilter = 'isa' | 'rel' | 'all'
interface Hit { id: string; label: string; icon?: string | null }

/** Barre du graphe sur téléphone (L44) : bascule Graphe / Liste, recherche qui centre le nœud, filtres dans une feuille. */
export function MobileGraphBar({ pid, q, setQ, qOpen, setQOpen, hits, goTo, onFilters, active }: {
  pid: string; q: string; setQ: (s: string) => void; qOpen: boolean; setQOpen: (b: boolean) => void; hits: Hit[]; goTo: (iri: string) => void; onFilters: () => void; active: boolean
}) {
  const { t } = useI18n()
  return (
    <div className="mgbar" role="toolbar" aria-label={t('ed.toolbar')}>
      <div className="seg" role="group" aria-label={t('mob.onto.view')}>
        <button type="button" aria-pressed="true" data-testid="view-graph">{t('mob.onto.graph')}</button>
        <button type="button" aria-pressed="false" data-testid="view-list" onClick={() => { location.hash = `#/projet/${encodeURIComponent(pid)}/ontologie-liste` }}>{t('mob.onto.list')}</button>
      </div>
      <div className="msearch">
        <Icon name="magnifying-glass" />
        <input type="text" role="combobox" aria-expanded={qOpen && !!hits.length} aria-label={t('ed.search')} placeholder={t('ed.search')} value={q} data-testid="graph-search" enterKeyHint="search"
          onChange={e => { setQ(e.target.value); setQOpen(true) }} onFocus={() => setQOpen(true)} onBlur={() => setTimeout(() => setQOpen(false), 150)}
          onKeyDown={e => { if (e.key === 'Enter' && hits[0]) goTo(hits[0].id) }} />
        {qOpen && hits.length > 0 && <ul className="of-hits" role="listbox">{hits.map(h => <li key={h.id}><button type="button" role="option" aria-selected={false} onMouseDown={e => e.preventDefault()} onClick={() => goTo(h.id)}><Icon name={h.icon || 'circle-nodes'} />{h.label}</button></li>)}</ul>}
      </div>
      <button type="button" className={'btn iconly' + (active ? ' on' : '')} aria-label={t('mob.onto.filters')} data-testid="filters-btn" onClick={onFilters}><Icon name="sliders" /></button>
    </div>)
}

export function FilterSheet({ open, onClose, filter, setFilter, mode, setMode, show, setShow, legend, setLegend, count }: {
  open: boolean; onClose: () => void; filter: EdgeFilter | ''; setFilter: (f: EdgeFilter) => void; mode: Mode; setMode: (m: Mode) => void
  show: ShowPrefs; setShow: (s: ShowPrefs) => void; legend: boolean; setLegend: (b: boolean) => void; count?: string
}) {
  const { t } = useI18n()
  const row = (k: Exclude<keyof ShowPrefs, 'density'>, only?: Mode) => {
    const off = only !== undefined && mode !== only
    return <label className={'chk' + (off ? ' off' : '')} key={k}><input type="checkbox" checked={show[k]} disabled={off} onChange={e => setShow({ ...show, [k]: e.target.checked })} />{t('ed.show.' + k)}</label>
  }
  return (
    <BottomSheet open={open} onClose={onClose} title={t('mob.onto.filters')} icon="sliders" initial="half" snaps={['half', 'full']} testid="filter-sheet">
      <div className="mfilters">
        {count && <p className="muted">{count}</p>}
        <div className="grp"><span className="gl">{t('ed.filter')}</span><Segmented<EdgeFilter> label={t('ed.filter')} value={filter as EdgeFilter} onChange={setFilter} items={[['isa', t('ed.filter.isa')], ['rel', t('ed.filter.rel')], ['all', t('ed.filter.all')]]} /></div>
        <div className="grp"><span className="gl">{t('ed.mode')}</span><Segmented<Mode> label={t('ed.mode')} value={mode} onChange={setMode} items={[['classic', t('ed.mode.classic')], ['vowl', t('ed.mode.vowl')]]} /></div>
        <div className="grp"><span className="gl">{t('ed.show')}</span><div className="checks">{row('dt', 'vowl')}{row('sub')}{row('rel')}{row('disj')}{row('dep')}{row('krakie')}</div></div>
        <label className="chk"><input type="checkbox" checked={legend} onChange={e => setLegend(e.target.checked)} />{t('lg.btn')}</label>
        <p className="muted small"><Icon name="desktop" /> {t('mob.onto.desktop')}</p>
      </div>
    </BottomSheet>)
}

/** Menu d'un appui long sur un nœud (L44). */
export function NodeActions({ label, onClose, onView, onSub, onProp, onCenter, canEdit }: { label: string; onClose: () => void; onView: () => void; onSub: () => void; onProp: () => void; onCenter: () => void; canEdit: boolean }) {
  const { t } = useI18n()
  const item = (icon: string, text: string, fn: () => void, id: string) => <li key={id}><button type="button" className="mrow" data-testid={id} onClick={() => { onClose(); fn() }}><span className="ico"><Icon name={icon} /></span><span className="tx"><b>{text}</b></span></button></li>
  return (
    <BottomSheet open onClose={onClose} title={t('mob.node.actions', { name: label })} heading={label} icon="circle-nodes" initial="half" snaps={['half']} testid="node-actions" className="short">
      <ul className="mlist">
        {item('eye', t('mob.node.view'), onView, 'act-view')}
        {canEdit && item('plus', t('mob.fiche.addsub'), onSub, 'act-sub')}
        {canEdit && item('plus', t('mob.fiche.addprop'), onProp, 'act-prop')}
        {item('crosshairs', t('mob.node.center'), onCenter, 'act-center')}
      </ul>
    </BottomSheet>)
}
