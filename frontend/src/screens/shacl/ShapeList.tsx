import { useMemo, useState } from 'react'
import { curie, localName, type NodeShape, type Project } from '../../api'
import { Icon } from '../../kit'
import { useI18n } from '../../i18n'
import { shapeTitle, type ShapeCheck } from './helpers'

export function ShapeList({ p, shapes, icons, selected, onSelect, check }: {
  p: Project; shapes: NodeShape[]; icons: Record<string, string>; selected: string | null; onSelect: (id: string) => void; check: ShapeCheck | null
}) {
  const { t, lang } = useI18n()
  const [q, setQ] = useState('')
  const pf = { ...p.shapes.prefixes, ...p.onto.meta.prefixes }
  const groups = useMemo(() => {
    const g = new Map<string, { label: string; cls: string | null; items: NodeShape[] }>()
    const needle = q.trim().toLowerCase()
    for (const s of shapes) {
      const { title, cls } = shapeTitle(s, p.onto, lang)
      const hay = (title + ' ' + localName(s.id) + ' ' + s.properties.map(x => localName(x.path.iri ?? '')).join(' ')).toLowerCase()
      if (needle && !hay.includes(needle)) continue
      const k = cls ?? ''
      if (!g.has(k)) g.set(k, { label: cls ? title : t('sh.list.nogroup'), cls, items: [] })
      g.get(k)!.items.push(s)
    }
    return [...g.values()].sort((a, b) => (a.cls ? 0 : 1) - (b.cls ? 0 : 1) || a.label.localeCompare(b.label, lang))
  }, [shapes, q, p.onto, lang, t])
  return (
    <nav className="shl" aria-label={t('sh.list.title')}>
      <div className="shl-search"><Icon name="magnifying-glass" /><input type="search" value={q} placeholder={t('sh.list.search')} aria-label={t('sh.list.search')} onChange={e => setQ(e.target.value)} /></div>
      <div className="shl-scroll">
        {groups.length === 0 && <p className="muted shl-none">{t('sh.list.none')}</p>}
        {groups.map(g => (
          <section key={g.cls ?? '_'} className="shl-group">
            <h3><Icon name={(g.cls && icons[g.cls]) || (g.cls ? 'cube' : 'bullseye')} /><span>{g.label}</span></h3>
            {g.items.map(s => {
              const n = s.properties.length
              const viol = check ? s.properties.reduce((a, ps) => a + (check.byShape[ps.id]?.length ?? 0), 0) + (check.byShape[s.id]?.length ?? 0) : null
              return (
                <button key={s.id} type="button" className="shl-item" aria-current={selected === s.id ? 'true' : undefined} onClick={() => onSelect(s.id)}>
                  <span className="nm">{curie(s.id, pf).replace(/^[^:]*:/, '').replace(/Shape$/, '')}</span>
                  <span className="cnt" title={t('sh.list.count', { n })}>{n}</span>
                  {viol === null ? <span className="st none" title={t('sh.state.none')}><Icon name="circle" /></span>
                    : viol === 0 ? <span className="st ok" title={t('sh.state.ok')}><Icon name="circle-check" /><span className="sr">{t('sh.state.ok')}</span></span>
                    : <span className="st bad" title={t('sh.state.viol', { n: viol })}><Icon name="circle-xmark" /><b>{viol}</b></span>}
                </button>
              )
            })}
          </section>
        ))}
      </div>
    </nav>
  )
}
