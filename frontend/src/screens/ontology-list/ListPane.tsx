import { useEffect, useMemo, useState } from 'react'
import type { OntoModel } from '../../api'
import { Icon } from '../../kit'
import { useT } from '../../i18n'
import { ancestors, childrenMap, lblOf, type Kind } from './model'

export const TABS: { kind: Kind; icon: string; key: string; coll: 'classes' | 'object_properties' | 'datatype_properties' | 'individuals' }[] = [
  { kind: 'class', icon: 'circle-nodes', key: 'ol.tab.classes', coll: 'classes' },
  { kind: 'objectProperty', icon: 'arrow-right-long', key: 'ol.tab.oprops', coll: 'object_properties' },
  { kind: 'datatypeProperty', icon: 'font', key: 'ol.tab.dprops', coll: 'datatype_properties' },
  { kind: 'individual', icon: 'cube', key: 'ol.tab.inds', coll: 'individuals' },
]

export function ListPane({ onto, lang, tab, setTab, sel, onSelect, icons, onCreate }: {
  onto: OntoModel; lang: string; tab: Kind; setTab: (k: Kind) => void; sel: string | null
  onSelect: (iri: string, kind: Kind) => void; icons: Record<string, string>; onCreate: (kind: Kind, name: string) => Promise<boolean>
}) {
  const t = useT()
  const [q, setQ] = useState(''); const [shut, setShut] = useState<Set<string>>(new Set()); const [adding, setAdding] = useState(false); const [name, setName] = useState('')
  const kids = useMemo(() => childrenMap(onto, lang), [onto, lang])
  const lbl = (i: string) => lblOf(onto, i, lang)
  const roots = useMemo(() => Object.values(onto.classes).filter(c => !c.sub_class_of.some(p => onto.classes[p])).map(c => c.iri).sort((a, b) => lbl(a).localeCompare(lbl(b))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onto, lang])
  // déplie les ancêtres de la sélection
  useEffect(() => {
    if (!sel || !onto.classes[sel]) return
    const up = ancestors(onto, sel)
    setShut(s => (up.some(u => s.has(u)) ? new Set([...s].filter(x => !up.includes(x))) : s))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel])
  useEffect(() => { setAdding(false); setName('') }, [tab])
  const counts = { class: Object.keys(onto.classes).length, objectProperty: Object.keys(onto.object_properties).length, datatypeProperty: Object.keys(onto.datatype_properties).length, individual: Object.keys(onto.individuals).length }
  const s = q.trim().toLowerCase()
  const nProps = (iri: string) => Object.values(onto.datatype_properties).filter(d => d.domain.includes(iri)).length + Object.values(onto.object_properties).filter(o => o.domain.includes(iri)).length

  const row = (iri: string, depth: number, path: string[]) => {
    const k = kids.get(iri) ?? []; const isShut = shut.has(iri) || false
    const np = nProps(iri)
    return (
      <li key={path.join('>') + iri} role="treeitem" aria-expanded={k.length ? !isShut : undefined} aria-selected={sel === iri}>
        <div className={'ol-trow' + (sel === iri ? ' sel' : '')} style={{ paddingLeft: 6 + depth * 14 }}>
          <button type="button" className="tg" aria-label={isShut ? t('ol.expand') : t('ol.collapse')} tabIndex={-1} disabled={!k.length}
            onClick={() => setShut(x => { const n = new Set(x); n.has(iri) ? n.delete(iri) : n.add(iri); return n })}>{k.length ? <Icon name={isShut ? 'chevron-right' : 'chevron-down'} /> : null}</button>
          <button type="button" className="nm" onClick={() => onSelect(iri, 'class')} title={iri}>
            <Icon name={icons[iri] || 'circle-nodes'} /><span>{lbl(iri)}</span>
          </button>
          {np > 0 && <span className="cnt" title={t('ol.tree.props', { n: np })}><Icon name="list" />{np}</span>}
          {k.length > 0 && <span className="cnt" title={t('ol.tree.subs', { n: k.length })}><Icon name="sitemap" />{k.length}</span>}
        </div>
        {k.length > 0 && !isShut && !path.includes(iri) && <ul role="group">{k.map(x => row(x, depth + 1, [...path, iri]))}</ul>}
      </li>
    )
  }
  const cur = TABS.find(x => x.kind === tab)!
  const flat = Object.keys(onto[cur.coll]).filter(i => !s || (lbl(i) + ' ' + i).toLowerCase().includes(s)).sort((a, b) => lbl(a).localeCompare(lbl(b)))
  const hint = (iri: string): string => {
    if (tab === 'individual') return onto.individuals[iri].types.map(lbl).join(', ')
    const p = onto.object_properties[iri] || onto.datatype_properties[iri]
    const r = tab === 'objectProperty' ? (p.range as string[]).map(lbl).join(', ') : (p.range as string[])[0]?.split('#').pop() ?? ''
    return `${p.domain.map(lbl).join(', ') || '…'} → ${r || '…'}`
  }
  const create = async () => { if (name.trim() && await onCreate(tab, name.trim())) { setName(''); setAdding(false) } }
  return (
    <aside className="ol-left" aria-label={t('ol.list')}>
      <div className="ol-search">
        <Icon name="magnifying-glass" />
        <input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder={t('ol.search')} aria-label={t('ol.search')} />
      </div>
      <div className="ol-tabs" role="tablist" aria-label={t('ol.list')}>
        {TABS.map(x => (
          <button key={x.kind} type="button" role="tab" aria-selected={tab === x.kind} onClick={() => setTab(x.kind)}>
            <Icon name={x.icon} /><span>{t(x.key)}</span><b>{counts[x.kind]}</b>
          </button>
        ))}
      </div>
      <div className="ol-scroll">
        {tab === 'class' && !s
          ? <ul role="tree" className="ol-tree">{roots.map(r => row(r, 0, []))}</ul>
          : <ul role="listbox" className="ol-flat">
              {flat.map(i => (
                <li key={i} role="option" aria-selected={sel === i}>
                  <button type="button" className={sel === i ? 'sel' : ''} onClick={() => onSelect(i, tab)} title={i}>
                    <Icon name={tab === 'class' ? icons[i] || 'circle-nodes' : cur.icon} />
                    <span className="t"><b>{lbl(i)}</b>{tab !== 'class' && <small>{hint(i)}</small>}</span>
                  </button>
                </li>
              ))}
            </ul>}
        {((tab === 'class' && !s) ? roots.length === 0 : flat.length === 0) && <p className="ol-none pad">{s ? t('ol.search.none') : t('ol.list.empty')}</p>}
      </div>
      <div className="ol-new">
        {adding
          ? <div className="row">
              <input type="text" autoFocus value={name} aria-label={t('ol.new.name')} placeholder={t('ol.new.name')} onChange={e => setName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') create(); if (e.key === 'Escape') setAdding(false) }} />
              <button type="button" className="btn primary sm" onClick={create} disabled={!name.trim()}>{t('ol.new.create')}</button>
            </div>
          : <button type="button" className="btn ghost" onClick={() => setAdding(true)}><Icon name="plus" />{t('ol.new.' + tab)}</button>}
      </div>
    </aside>
  )
}
