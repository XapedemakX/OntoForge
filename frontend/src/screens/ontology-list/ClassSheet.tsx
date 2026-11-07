import { useMemo, useState } from 'react'
import { tr } from '../../i18n'
import { localName, type OntClass } from '../../api'
import { Button, Icon, IconButton, Segmented } from '../../kit'
import { toLocalName } from '../editor/layout'
import type { Op } from '../editor/types'
import type { SheetCtx } from './ctx'
import { Header } from './Header'
import { CARD_PRESETS, DATATYPES, cardOps, cardText, ancestors, childrenMap, classProps, classUsage, exprText, presetOf, restrText, type PropRow } from './model'
import { Chips, Combobox, InlineText, Section, type Item } from './parts'

export function IdentityCard({ c, iri }: { c: SheetCtx; iri: string }) {
  const { t, onto } = c
  const e = onto.classes[iri] || onto.object_properties[iri] || onto.datatype_properties[iri] || onto.individuals[iri]
  const langs = Array.from(new Set(['fr', 'en', c.lang]))
  return (
    <Section title={t('ol.identity')} id="ol-identity">
      <div className="ol-langs">
        {langs.map(l => (
          <div key={l} className="ol-lang">
            <span className="tag">{l}</span>
            <label><span>{t('ol.label')}</span>
              <InlineText label={`${t('ol.label')} ${l}`} value={e.labels[l] || ''} ph={t('ol.label.ph')} onCommit={v => c.apply([{ op: 'set_label', iri, text: v, lang: l }], tr('hist.libelle'))} /></label>
            <label><span>{t('ol.comment')}</span>
              <InlineText area label={`${t('ol.comment')} ${l}`} value={e.comments[l] || ''} ph={t('ol.comment.ph')} onCommit={v => c.apply([{ op: 'set_comment', iri, text: v, lang: l }], tr('hist.commentaire'))} /></label>
          </div>
        ))}
      </div>
    </Section>
  )
}

export function ClassSheet({ c, iri }: { c: SheetCtx; iri: string }) {
  const { t, onto, lang } = c
  const cls = onto.classes[iri]
  const ancs = useMemo(() => ancestors(onto, iri), [onto, iri])
  const kids = useMemo(() => childrenMap(onto, lang).get(iri) ?? [], [onto, iri, lang])
  const rows = useMemo(() => classProps(onto, iri, lang), [onto, iri, lang])
  const usage = useMemo(() => classUsage(onto, c.p.shapes, iri, lang), [onto, c.p.shapes, iri, lang])
  const classItems: Item[] = useMemo(() => Object.values(onto.classes).map(k => ({ id: k.iri, label: c.lbl(k.iri), hint: k.iri.split(/[#/]/).pop() })).sort((a, b) => a.label.localeCompare(b.label)), [onto, c])
  const except = (ids: string[]) => classItems.filter(i => i.id !== iri && !ids.includes(i.id))
  const lbl = c.lbl
  const open = (i: string) => c.go(i)
  const sub = (kind: 'class' | 'op' | 'dp') => (i: string) => c.select(i, kind === 'class' ? 'class' : kind === 'op' ? 'objectProperty' : 'datatypeProperty')
  const suggestions = [
    { text: t('ol.sugg.addprop', { name: lbl(iri) }), send: false },
    { text: t('ol.sugg.explain', { name: lbl(iri) }), send: true },
    { text: t('ol.sugg.shapes', { name: lbl(iri) }), send: true },
    { text: t('ol.sugg.restr', { name: lbl(iri) }), send: true },
  ]
  return (
    <>
      <Header c={c} kind="class" iri={iri} suggestions={suggestions} />
      <IdentityCard c={c} iri={iri} />

      <Section title={t('ol.hier')} id="ol-hier">
        <div className="ol-two">
          <div>
            <h4>{t('ol.parents')}<span className="ol-count">{cls.sub_class_of.length}</span></h4>
            <Chips items={cls.sub_class_of.map(i => ({ id: i, label: lbl(i), icon: c.icons[i] || 'circle-nodes' }))} onOpen={open}
              onRemove={i => c.apply([{ op: 'remove_subclass', iri, parent: i }], tr('hist.retirer_un_parent'))} empty={t('ol.parents.none')} />
            <Combobox items={except([...cls.sub_class_of, ...kids, ...ancs.filter(a => !cls.sub_class_of.includes(a))])} placeholder={t('ol.parents.add')}
              onPick={i => c.apply([{ op: 'add_subclass', iri, parent: i }], tr('hist.ajouter_un_parent'))} />
          </div>
          <div>
            <h4>{t('ol.children')}<span className="ol-count">{kids.length}</span></h4>
            <Chips items={kids.map(i => ({ id: i, label: lbl(i), icon: c.icons[i] || 'circle-nodes' }))} onOpen={open}
              onRemove={i => c.apply([{ op: 'remove_subclass', iri: i, parent: iri }], tr('hist.retirer_une_sous_classe'))} empty={t('ol.children.none')} />
            <Combobox items={except([...kids, ...cls.sub_class_of, ...ancs])} placeholder={t('ol.children.add')}
              onPick={i => c.apply([{ op: 'add_subclass', iri: i, parent: iri }], tr('hist.ajouter_une_sous_classe'))} />
          </div>
        </div>
      </Section>

      <PropsTable c={c} iri={iri} cls={cls} rows={rows} classItems={classItems} onOpen={(i, k) => sub(k === 'data' ? 'dp' : 'op')(i)} onOrigin={open} />

      <Section title={t('ol.restr')} count={cls.restrictions.length} id="ol-restr">
        {cls.restrictions.length === 0 && <p className="ol-none">{t('ol.restr.none')}</p>}
        <ul className="ol-sentences">
          {cls.restrictions.map((r, i) => (
            <li key={i}>
              <Icon name="angle-right" />
              <span>{t('ol.restr.every', { name: lbl(iri) })} <b>{restrText(r, lbl, t)}</b></span>
              <IconButton icon="xmark" label={t('ol.remove')} onClick={() => c.apply([{ op: 'remove_restriction', iri, property: r.property, kind: r.kind }], tr('hist.retirer_une_restriction'))} />
            </li>
          ))}
        </ul>
        {cls.super_expressions.length > 0 && <>
          <h4>{t('ol.restr.complex')}</h4>
          <ul className="ol-sentences ro">{cls.super_expressions.map((e, i) => <li key={i}><Icon name="angle-right" /><span>{exprText(e, lbl, t)}</span></li>)}</ul>
        </>}
        <RestrAdd c={c} iri={iri} classItems={classItems} />
      </Section>

      <div className="ol-two grid">
        <Section title={t('ol.disj')} id="ol-disj">
          <h4>{t('ol.disj.with')}<span className="ol-count">{cls.disjoint_with.length}</span></h4>
          <Chips items={cls.disjoint_with.map(i => ({ id: i, label: lbl(i), icon: 'ban' }))} onOpen={open} onRemove={i => c.apply([{ op: 'remove_disjoint', iri, other: i }], tr('hist.retirer_une_disjonction'))} empty={t('ol.none')} />
          <Combobox items={except(cls.disjoint_with)} placeholder={t('ol.disj.add')} onPick={i => c.apply([{ op: 'add_disjoint', iri, other: i }], tr('hist.disjonction'))} />
          <h4>{t('ol.equiv')}<span className="ol-count">{cls.equivalent_to.length + cls.disjoint_union_of.length}</span></h4>
          {cls.equivalent_to.length + cls.disjoint_union_of.length === 0 && <span className="ol-none">{t('ol.none')}</span>}
          <ul className="ol-chips">
            {cls.equivalent_to.map((e, i) => <li key={'e' + i} className="ol-chip"><span className="go static"><Icon name="equals" />{exprText(e, lbl, t)}</span></li>)}
            {cls.disjoint_union_of.map((u, i) => <li key={'u' + i} className="ol-chip"><span className="go static"><Icon name="code-merge" />{t('ol.equiv.union', { list: u.map(lbl).join(', ') })}</span></li>)}
          </ul>
        </Section>
        <KeysCard c={c} iri={iri} cls={cls} rows={rows} />
      </div>

      <Section title={t('ol.usage')} id="ol-usage">
        <dl className="ol-usage">
          <dt>{t('ol.usage.domain')}</dt>
          <dd><Chips items={usage.asDomain.map(i => ({ id: i, label: lbl(i), icon: onto.object_properties[i] ? 'arrow-right-long' : 'font' }))} onOpen={i => c.select(i, onto.object_properties[i] ? 'objectProperty' : 'datatypeProperty')} empty={t('ol.none')} /></dd>
          <dt>{t('ol.usage.range')}</dt>
          <dd><Chips items={usage.asRange.map(i => ({ id: i, label: lbl(i), icon: 'arrow-right-long' }))} onOpen={i => c.select(i, 'objectProperty')} empty={t('ol.none')} /></dd>
          <dt>{t('ol.usage.restr')}</dt>
          <dd><Chips items={usage.inRestrictions.map(i => ({ id: i, label: lbl(i), icon: c.icons[i] || 'circle-nodes' }))} onOpen={open} empty={t('ol.none')} /></dd>
          <dt>{t('ol.usage.shapes')}</dt>
          <dd><Chips items={usage.shapes.map(s => ({ id: s.id, label: `${s.label} · ${t('ol.usage.nconstr', { n: s.constraints })}`, icon: 'shapes' }))} empty={t('ol.usage.noshape')} /></dd>
        </dl>
      </Section>
    </>
  )
}

function PropsTable({ c, iri, cls, rows, classItems, onOpen, onOrigin }: { c: SheetCtx; iri: string; cls: OntClass; rows: PropRow[]; classItems: Item[]; onOpen: (iri: string, k: 'data' | 'object') => void; onOrigin: (i: string) => void }) {
  const { t, onto, lang } = c
  const setCard = (r: PropRow, key: string) => {
    const p = CARD_PRESETS.find(([k]) => k === key)?.[1]; if (p) c.apply(cardOps(onto, iri, r.iri, p) as Op[], tr('hist.cardinalite'))
  }
  const toggleRequired = (r: PropRow, on: boolean) => c.apply(cardOps(onto, iri, r.iri, { min: on ? 1 : 0, max: r.card.max }) as Op[], tr('hist.obligatoire'))
  const toggleKey = (r: PropRow, on: boolean) => {
    const keys = cls.has_keys
    if (on) return c.apply([{ op: 'set_key', iri, properties: [r.iri], index: keys.length }], tr('hist.cle'))
    const idx = keys.findIndex(k => k.includes(r.iri))
    if (idx < 0) return c.toast(t('ol.key.inherited'))
    const rest = keys[idx].filter(x => x !== r.iri)
    return c.apply([{ op: 'set_key', iri, properties: rest, index: idx }], tr('hist.cle'))
  }
  return (
    <Section title={t('ol.props')} count={rows.length} id="ol-props">
      <div className="ol-tablewrap">
        <table className="ol-table">
          <thead><tr><th>{t('ol.col.name')}</th><th>{t('ol.col.type')}</th><th>{t('ol.col.card')}</th><th className="c">{t('ol.col.required')}</th><th className="c">{t('ol.col.key')}</th><th>{t('ol.col.origin')}</th><th /></tr></thead>
          <tbody>
            {rows.map(r => {
              const pr = presetOf(r.card)
              return (
                <tr key={r.iri} className={r.origin ? 'inh' : ''}>
                  <td><button type="button" className="ol-link" onClick={() => onOpen(r.iri, r.kind)}><Icon name={r.kind === 'data' ? 'font' : 'arrow-right-long'} />{r.label}</button></td>
                  <td>{r.kind === 'object'
                    ? <span className="ol-target">{r.targetIri ? <button type="button" className="ol-link" onClick={() => c.go(r.targetIri!)}><Icon name={c.icons[r.targetIri] || 'circle-nodes'} />{r.target}</button> : '—'}</span>
                    : <code className="ol-dt">{r.target}</code>}</td>
                  <td>
                    <select aria-label={`${t('ol.col.card')} ${r.label}`} className="ol-sel" value={pr} onChange={e => setCard(r, e.target.value)}>
                      {CARD_PRESETS.map(([k, p]) => <option key={k} value={k}>{cardText(p, t)}</option>)}
                      {pr === 'custom' && <option value="custom">{cardText(r.card, t)}</option>}
                    </select>
                  </td>
                  <td className="c"><input type="checkbox" aria-label={`${t('ol.col.required')} ${r.label}`} checked={r.required} onChange={e => toggleRequired(r, e.target.checked)} /></td>
                  <td className="c">{r.kind === 'data' ? <button type="button" className={'ol-keybtn' + (r.key ? ' on' : '')} aria-pressed={r.key} title={t('ol.col.key')} aria-label={`${t('ol.col.key')} ${r.label}`} onClick={() => toggleKey(r, !r.key)}><Icon name="key" /></button> : <span className="muted">·</span>}</td>
                  <td>{r.origin ? <button type="button" className="ol-origin inherited" onClick={() => onOrigin(r.origin!)} title={c.lbl(r.origin)}><Icon name="arrow-turn-up" />{t('ol.origin.inherited', { name: c.lbl(r.origin) })}</button> : <span className="ol-origin own">{t('ol.origin.own')}</span>}</td>
                  <td className="c">{!r.origin && <IconButton icon="xmark" label={`${t('ol.delete')} ${r.label}`} onClick={() => c.apply([{ op: 'delete_entity', iri: r.iri }], tr('hist.supprimer'))} />}</td>
                </tr>
              )
            })}
            {!rows.length && <tr><td colSpan={7} className="ol-none">{t('ol.props.none')}</td></tr>}
          </tbody>
        </table>
      </div>
      <PropAdd c={c} iri={iri} classItems={classItems} lang={lang} />
    </Section>
  )
}

function PropAdd({ c, iri, classItems, lang }: { c: SheetCtx; iri: string; classItems: Item[]; lang: string }) {
  const { t, onto } = c
  const [kind, setKind] = useState<'data' | 'object'>('data')
  const [name, setName] = useState(''); const [dt, setDt] = useState(DATATYPES[0]); const [target, setTarget] = useState<Item | null>(null); const [pr, setPr] = useState('free')
  const ready = name.trim() && (kind === 'data' || target)
  const go = async () => {
    if (!ready) return
    const local = toLocalName(name).replace(/^./, s => s.toLowerCase())
    const piri = iri.slice(0, iri.length - localName(iri).length) + local
    const add: Op = kind === 'data'
      ? { op: 'add_datatype_property', iri: piri, label: name.trim(), lang, domain: iri, range: dt }
      : { op: 'add_object_property', iri: piri, label: name.trim(), lang, domain: iri, range: target!.id }
    const card = CARD_PRESETS.find(([k]) => k === pr)![1]
    const extra = (card.min || card.max !== null) ? cardOps({ ...onto, classes: onto.classes }, iri, piri, card) as Op[] : []
    if (await c.apply([add, ...extra], tr('hist.nouvelle_propriete'))) { setName(''); setTarget(null); setPr('free') }
  }
  return (
    <div className="ol-add" role="group" aria-label={t('ol.padd.title')}>
      <Segmented<'data' | 'object'> label={t('ol.padd.kind')} value={kind} onChange={setKind} items={[['data', t('ol.padd.data')], ['object', t('ol.padd.rel')]]} />
      <input type="text" className="ol-add-name" placeholder={t('ol.padd.name')} aria-label={t('ol.padd.name')} value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && go()} />
      {kind === 'data'
        ? <select aria-label={t('ol.col.type')} value={dt} onChange={e => setDt(e.target.value)}>{DATATYPES.map(x => <option key={x} value={x}>{localName(x)}</option>)}</select>
        : target
          ? <span className="ol-chip"><span className="go static"><Icon name="bullseye" />{target.label}</span><button type="button" className="rm" aria-label={t('ol.remove')} onClick={() => setTarget(null)}><Icon name="xmark" /></button></span>
          : <Combobox items={classItems} placeholder={t('ol.padd.target')} onPick={id => setTarget(classItems.find(i => i.id === id) ?? null)} />}
      <select aria-label={t('ol.col.card')} value={pr} onChange={e => setPr(e.target.value)}>{CARD_PRESETS.map(([k, p]) => <option key={k} value={k}>{cardText(p, t)}</option>)}</select>
      <Button variant="primary" icon="plus" disabled={!ready} onClick={go}>{t('ol.padd.add')}</Button>
    </div>
  )
}

function RestrAdd({ c, iri, classItems }: { c: SheetCtx; iri: string; classItems: Item[] }) {
  const { t, onto } = c
  const [prop, setProp] = useState<Item | null>(null); const [kind, setKind] = useState('exactly'); const [n, setN] = useState(1); const [filler, setFiller] = useState<Item | null>(null)
  const props: Item[] = useMemo(() => [...Object.values(onto.object_properties), ...Object.values(onto.datatype_properties)].map(p => ({ id: p.iri, label: c.lbl(p.iri), icon: onto.object_properties[p.iri] ? 'arrow-right-long' : 'font' })).sort((a, b) => a.label.localeCompare(b.label)), [onto, c])
  const num = ['min', 'max', 'exactly'].includes(kind)
  const isObj = !!prop && !!onto.object_properties[prop.id]
  const go = async () => {
    if (!prop) return
    const op: Op = { op: 'set_restriction', iri, property: prop.id, kind, ...(num ? { n } : {}), ...(filler && isObj ? { filler: filler.id } : {}) }
    if (await c.apply([op], tr('hist.restriction'))) { setProp(null); setFiller(null) }
  }
  return (
    <div className="ol-add" role="group" aria-label={t('ol.radd.title')}>
      <span className="ol-add-l">{t('ol.radd.every')}</span>
      <select aria-label={t('ol.radd.kind')} value={kind} onChange={e => setKind(e.target.value)}>
        {['exactly', 'min', 'max', 'some', 'only'].map(k => <option key={k} value={k}>{t('ol.radd.k.' + k)}</option>)}</select>
      {num && <input type="number" min={0} className="ol-n" aria-label="n" value={n} onChange={e => setN(Math.max(0, +e.target.value))} />}
      {prop
        ? <span className="ol-chip"><span className="go static">{prop.label}</span><button type="button" className="rm" aria-label={t('ol.remove')} onClick={() => setProp(null)}><Icon name="xmark" /></button></span>
        : <Combobox items={props} placeholder={t('ol.radd.prop')} onPick={id => setProp(props.find(i => i.id === id) ?? null)} />}
      {isObj && (filler
        ? <span className="ol-chip"><span className="go static">{t('ol.radd.of', { name: filler.label })}</span><button type="button" className="rm" aria-label={t('ol.remove')} onClick={() => setFiller(null)}><Icon name="xmark" /></button></span>
        : <Combobox items={classItems} placeholder={t('ol.radd.filler')} onPick={id => setFiller(classItems.find(i => i.id === id) ?? null)} />)}
      <Button variant="primary" icon="plus" disabled={!prop} onClick={go}>{t('ol.padd.add')}</Button>
    </div>
  )
}

function KeysCard({ c, iri, cls, rows }: { c: SheetCtx; iri: string; cls: OntClass; rows: PropRow[] }) {
  const { t } = c
  const [draft, setDraft] = useState<string[]>([])
  const cand: Item[] = rows.filter(r => r.kind === 'data' && !draft.includes(r.iri)).map(r => ({ id: r.iri, label: r.label }))
  return (
    <Section title={t('ol.keys')} count={cls.has_keys.length} id="ol-keys">
      {cls.has_keys.length === 0 && draft.length === 0 && <p className="ol-none">{t('ol.keys.none')}</p>}
      <ul className="ol-chips">
        {cls.has_keys.map((k, i) => (
          <li key={i} className="ol-chip key"><span className="go static"><Icon name="key" />{k.map(c.lbl).join(' + ')}</span>
            <button type="button" className="rm" aria-label={t('ol.remove')} onClick={() => c.apply([{ op: 'set_key', iri, properties: [], index: i }], tr('hist.retirer_la_cle'))}><Icon name="xmark" /></button></li>
        ))}
      </ul>
      <div className="ol-keydraft">
        {draft.length > 0 && <Chips items={draft.map(d => ({ id: d, label: c.lbl(d), icon: 'key' }))} onRemove={d => setDraft(x => x.filter(y => y !== d))} />}
        <Combobox items={cand} placeholder={draft.length ? t('ol.keys.more') : t('ol.keys.add')} onPick={id => setDraft(x => [...x, id])} />
        {draft.length > 0 && <Button size="sm" variant="primary" onClick={async () => { if (await c.apply([{ op: 'set_key', iri, properties: draft, index: cls.has_keys.length }], tr('hist.cle'))) setDraft([]) }}>{t('ol.keys.create')}</Button>}
      </div>
    </Section>
  )
}
