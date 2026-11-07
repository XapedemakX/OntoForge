import { useMemo } from 'react'
import { tr } from '../../i18n'
import { localName, type Characteristic, type Individual } from '../../api'
import { Icon } from '../../kit'
import type { SheetCtx } from './ctx'
import { Header } from './Header'
import { IdentityCard } from './ClassSheet'
import { DATATYPES, cardText, cardinality, restrText } from './model'
import { Chips, Combobox, Section, Switch, type Item } from './parts'

const CHARS: Characteristic[] = ['functional', 'inverseFunctional', 'transitive', 'symmetric', 'asymmetric', 'reflexive', 'irreflexive']

function useClassItems(c: SheetCtx): Item[] {
  return useMemo(() => Object.values(c.onto.classes).map(k => ({ id: k.iri, label: c.lbl(k.iri), icon: c.icons[k.iri] || 'circle-nodes' })).sort((a, b) => a.label.localeCompare(b.label)), [c])
}
function UsedBy({ c, iri }: { c: SheetCtx; iri: string }) {
  const { t, onto } = c
  const used = Object.values(onto.classes).filter(k => k.restrictions.some(r => r.property === iri))
  const shapes = Object.values(c.p.shapes.shapes).filter(s => s.properties.some(ps => ps.path?.iri === iri))
  return (
    <Section title={t('ol.usage')} id="ol-usage">
      <dl className="ol-usage">
        <dt>{t('ol.usage.restrof')}</dt>
        <dd>{used.length === 0 ? <span className="ol-none">{t('ol.none')}</span>
          : <ul className="ol-sentences">{used.map(k => <li key={k.iri}><Icon name="angle-right" /><span><button type="button" className="ol-link" onClick={() => c.go(k.iri)}>{c.lbl(k.iri)}</button> {k.restrictions.filter(r => r.property === iri).map(r => restrText(r, c.lbl, t)).join(' ; ')}</span></li>)}</ul>}</dd>
        <dt>{t('ol.usage.shapes')}</dt>
        <dd><Chips items={shapes.map(s => ({ id: s.id, label: s.labels?.[c.lang] || s.labels?.fr || localName(s.id), icon: 'shapes' }))} empty={t('ol.usage.noshape')} /></dd>
      </dl>
    </Section>
  )
}
function DomainRange({ c, iri, kind }: { c: SheetCtx; iri: string; kind: 'objectProperty' | 'datatypeProperty' }) {
  const { t, onto } = c
  const p = kind === 'objectProperty' ? onto.object_properties[iri] : onto.datatype_properties[iri]
  const items = useClassItems(c)
  const set = (key: 'domain' | 'range', v: string[]) => c.apply([{ op: 'set_domain_range', iri, [key]: v }], key === 'domain' ? tr('hist.domaine') : tr('hist.portee'))
  const side = (key: 'domain' | 'range') => {
    const cur = p[key] as string[]
    return (
      <div>
        <h4>{t('ol.' + key)}<span className="ol-hint">{t('ol.' + key + '.hint')}</span></h4>
        <Chips items={cur.map(i => ({ id: i, label: c.lbl(i), icon: c.icons[i] || 'circle-nodes' }))} onOpen={i => c.select(i, 'class')} onRemove={i => set(key, cur.filter(x => x !== i))} empty={t('ol.none')} />
        <Combobox items={items.filter(i => !cur.includes(i.id))} placeholder={t('ol.' + key + '.add')} onPick={i => set(key, [...cur, i])} />
      </div>
    )
  }
  return (
    <Section title={t('ol.domrange')} id="ol-dr">
      <div className="ol-two">
        {side('domain')}
        {kind === 'objectProperty' ? side('range') : (
          <div>
            <h4>{t('ol.dtype')}<span className="ol-hint">{t('ol.dtype.hint')}</span></h4>
            <select className="ol-sel wide" aria-label={t('ol.dtype')} value={(p.range as string[])[0] ?? ''} onChange={e => set('range', [e.target.value])}>
              {[...new Set([...DATATYPES, ...(p.range as string[])])].map(x => <option key={x} value={x}>{localName(x)}</option>)}</select>
          </div>
        )}
      </div>
    </Section>
  )
}

export function ObjectPropSheet({ c, iri }: { c: SheetCtx; iri: string }) {
  const { t, onto } = c
  const p = onto.object_properties[iri]
  const others: Item[] = Object.values(onto.object_properties).filter(x => x.iri !== iri).map(x => ({ id: x.iri, label: c.lbl(x.iri) })).sort((a, b) => a.label.localeCompare(b.label))
  const sentence = p.domain.length && p.range.length ? t('ol.p.sentence', { d: p.domain.map(c.lbl).join(' / '), p: c.lbl(iri).toLowerCase(), r: p.range.map(c.lbl).join(' / ') }) : null
  const suggestions = [
    { text: t('ol.sugg.pexplain', { name: c.lbl(iri) }), send: true },
    { text: t('ol.sugg.pcheck', { name: c.lbl(iri) }), send: true },
    { text: t('ol.sugg.pinverse', { name: c.lbl(iri) }), send: true },
  ]
  return (
    <>
      <Header c={c} kind="objectProperty" iri={iri} suggestions={suggestions} />
      {sentence && <p className="ol-sentence"><Icon name="arrow-right-long" />{sentence}</p>}
      <IdentityCard c={c} iri={iri} />
      <DomainRange c={c} iri={iri} kind="objectProperty" />
      <Section title={t('ol.inverse')} id="ol-inv">
        <p className="ol-hint block">{t('ol.inverse.hint')}</p>
        {p.inverse_of
          ? <Chips items={[{ id: p.inverse_of, label: c.lbl(p.inverse_of), icon: 'right-left' }]} onOpen={i => c.select(i, 'objectProperty')} onRemove={() => c.apply([{ op: 'set_inverse', iri, inverse: null }], tr('hist.inverse'))} />
          : <span className="ol-none">{t('ol.none')}</span>}
        <Combobox items={others} placeholder={t('ol.inverse.set')} onPick={i => c.apply([{ op: 'set_inverse', iri, inverse: i }], tr('hist.inverse'))} />
      </Section>
      <Section title={t('ol.chars')} id="ol-chars">
        <div className="ol-switches">
          {CHARS.map(k => <Switch key={k} checked={p.characteristics.includes(k)} label={t('ol.char.' + k)} hint={t('ol.char.' + k + '.hint')}
            onChange={v => c.apply([{ op: 'set_characteristic', iri, characteristic: k, value: v }], tr('hist.caracteristique'))} />)}
        </div>
      </Section>
      {p.sub_property_of.length > 0 && <Section title={t('ol.subprop')} id="ol-sp"><Chips items={p.sub_property_of.map(i => ({ id: i, label: c.lbl(i), icon: 'arrow-right-long' }))} onOpen={i => c.select(i, 'objectProperty')} /></Section>}
      <UsedBy c={c} iri={iri} />
    </>
  )
}

export function DataPropSheet({ c, iri }: { c: SheetCtx; iri: string }) {
  const { t, onto } = c
  const p = onto.datatype_properties[iri]
  const suggestions = [{ text: t('ol.sugg.pexplain', { name: c.lbl(iri) }), send: true }, { text: t('ol.sugg.pcheck', { name: c.lbl(iri) }), send: true }]
  // le caractère « fonctionnel » d'une propriété de données n'a pas d'opération dédiée : PUT /onto
  const setFunctional = (v: boolean) => c.edit(o => { o.datatype_properties[iri].functional = v }, 'Fonctionnelle')
  const usedBy = Object.values(onto.classes).filter(k => p.domain.includes(k.iri)).map(k => ({ k, card: cardinality(onto, k.iri, iri, p.functional).card }))
  return (
    <>
      <Header c={c} kind="datatypeProperty" iri={iri} suggestions={suggestions} />
      <IdentityCard c={c} iri={iri} />
      <DomainRange c={c} iri={iri} kind="datatypeProperty" />
      <Section title={t('ol.chars')} id="ol-chars">
        <div className="ol-switches">
          <Switch checked={p.functional} label={t('ol.char.dfunctional')} hint={t('ol.char.dfunctional.hint')} onChange={setFunctional} />
        </div>
      </Section>
      <Section title={t('ol.usage.cards')} id="ol-cards">
        {usedBy.length === 0 ? <span className="ol-none">{t('ol.none')}</span>
          : <ul className="ol-sentences">{usedBy.map(({ k, card }) => <li key={k.iri}><Icon name="angle-right" /><span><button type="button" className="ol-link" onClick={() => c.go(k.iri)}>{c.lbl(k.iri)}</button> : {cardText(card, t)}</span></li>)}</ul>}
      </Section>
      <UsedBy c={c} iri={iri} />
    </>
  )
}

export function IndividualSheet({ c, iri }: { c: SheetCtx; iri: string }) {
  const { t, onto } = c
  const ind: Individual = onto.individuals[iri]
  const items = useClassItems(c)
  const setTypes = (types: string[]) => c.edit(o => { o.individuals[iri].types = types }, 'Types')
  const suggestions = [{ text: t('ol.sugg.iexplain', { name: c.lbl(iri) }), send: true }, { text: t('ol.sugg.ifacts', { name: c.lbl(iri) }), send: false }]
  const siblings = Object.values(onto.individuals).filter(i => i.iri !== iri && i.types.some(x => ind.types.includes(x)))
  return (
    <>
      <Header c={c} kind="individual" iri={iri} suggestions={suggestions} />
      <IdentityCard c={c} iri={iri} />
      <Section title={t('ol.itypes')} count={ind.types.length} id="ol-types">
        <Chips items={ind.types.map(i => ({ id: i, label: c.lbl(i), icon: c.icons[i] || 'circle-nodes' }))} onOpen={i => c.select(i, 'class')} onRemove={i => setTypes(ind.types.filter(x => x !== i))} empty={t('ol.itypes.none')} />
        <Combobox items={items.filter(i => !ind.types.includes(i.id))} placeholder={t('ol.itypes.add')} onPick={i => setTypes([...ind.types, i])} />
      </Section>
      <Section title={t('ol.facts')} count={ind.facts.length} id="ol-facts">
        {ind.facts.length === 0 ? <p className="ol-none">{t('ol.facts.none')}</p> : (
          <table className="ol-table"><thead><tr><th>{t('ol.col.name')}</th><th>{t('ol.facts.value')}</th><th>{t('ol.col.type')}</th></tr></thead>
            <tbody>{ind.facts.map((f, i) => (
              <tr key={i}><td>{f.negative && <Icon name="ban" />} {c.lbl(f.property)}</td>
                <td>{f.is_iri ? <button type="button" className="ol-link" onClick={() => c.go(f.value)}>{c.lbl(f.value)}</button> : f.value}</td>
                <td><code className="ol-dt">{f.datatype ? localName(f.datatype) : f.lang ?? '—'}</code></td></tr>))}</tbody></table>)}
      </Section>
      {(ind.same_as.length > 0 || ind.different_from.length > 0) && (
        <Section title={t('ol.iident')} id="ol-ident">
          <dl className="ol-usage"><dt>{t('ol.same')}</dt><dd><Chips items={ind.same_as.map(i => ({ id: i, label: c.lbl(i) }))} onOpen={i => c.select(i, 'individual')} empty={t('ol.none')} /></dd>
            <dt>{t('ol.diff')}</dt><dd><Chips items={ind.different_from.map(i => ({ id: i, label: c.lbl(i) }))} onOpen={i => c.select(i, 'individual')} empty={t('ol.none')} /></dd></dl>
        </Section>)}
      <Section title={t('ol.usage')} id="ol-usage">
        <dl className="ol-usage"><dt>{t('ol.isame')}</dt>
          <dd><Chips items={siblings.map(i => ({ id: i.iri, label: c.lbl(i.iri), icon: 'cube' }))} onOpen={i => c.select(i, 'individual')} empty={t('ol.none')} /></dd></dl>
      </Section>
    </>
  )
}
