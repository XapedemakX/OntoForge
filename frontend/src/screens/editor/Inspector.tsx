import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { curie, labelOf, localName, type OntoModel, type Characteristic } from '../../api'
import { Button, Icon, IconButton } from '../../kit'
import { useI18n } from '../../i18n'
import { IconPicker } from './IconPicker'
import { toLocalName } from './layout'
import type { Op, Sel } from './types'

const XSD = 'http://www.w3.org/2001/XMLSchema#'
const DTS = ['string', 'integer', 'decimal', 'boolean', 'dateTime', 'date', 'float', 'double', 'anyURI'].map(x => XSD + x)
const CHARS: Characteristic[] = ['functional', 'inverseFunctional', 'transitive', 'symmetric', 'asymmetric', 'reflexive', 'irreflexive']
const CARDS = ['*', '1', '0..1', '1..*'] as const
type Card = typeof CARDS[number]

function Sec({ title, children, count }: { title: string; children: ReactNode; count?: number }) {
  return <section className="of-sec"><h4>{title}{count !== undefined && <span className="cnt-s">{count}</span>}</h4>{children}</section>
}
/** Champ texte validé à la sortie du champ (ou Entrée). */
function Commit({ value, onCommit, area, ph, label }: { value: string; onCommit: (v: string) => void; area?: boolean; ph?: string; label: string }) {
  const [v, setV] = useState(value)
  useEffect(() => setV(value), [value])
  const done = () => { if (v !== value) onCommit(v) }
  return area
    ? <textarea aria-label={label} placeholder={ph} rows={3} value={v} onChange={e => setV(e.target.value)} onBlur={done} />
    : <input type="text" aria-label={label} placeholder={ph} value={v} onChange={e => setV(e.target.value)} onBlur={done} onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
}
function Chips({ items, onRemove, onClick, ro }: { items: { iri: string; label: string }[]; onRemove?: (iri: string) => void; onClick?: (iri: string) => void; ro: boolean }) {
  return <div className="chips">{items.map(i => <span key={i.iri} className="chip">
    <button type="button" className="chip-l" onClick={() => onClick?.(i.iri)} title={i.iri}>{i.label}</button>
    {!ro && onRemove && <button type="button" aria-label="×" onClick={() => onRemove(i.iri)}><Icon name="xmark" /></button>}</span>)}</div>
}

interface Props {
  onto: OntoModel; sel: NonNullable<Sel>; lang: string; readOnly: boolean; icon: string | null
  apply: (ops: Op[], label?: string) => Promise<boolean>
  select: (s: Sel) => void; close: () => void
}
export function Inspector({ onto, sel, lang, readOnly, icon, apply, select, close }: Props) {
  const { t } = useI18n()
  const pf = onto.meta.prefixes || {}
  const clsList = useMemo(() => Object.values(onto.classes).map(c => ({ iri: c.iri, label: labelOf(c, c.iri, lang) })).sort((a, b) => a.label.localeCompare(b.label)), [onto, lang])
  const lbl = (iri: string) => labelOf(onto.classes[iri] || onto.object_properties[iri] || onto.datatype_properties[iri], iri, lang)
  const ent = onto.classes[sel.iri] || onto.object_properties[sel.iri]
  const [iconOpen, setIconOpen] = useState(false)
  const [renIri, setRenIri] = useState<string | null>(null)
  useEffect(() => { setIconOpen(false); setRenIri(null) }, [sel.iri])
  if (!ent) return <div className="of-insp-empty muted">{t('ed.insp.gone')}</div>
  const langs = Array.from(new Set(['fr', 'en', lang]))
  const setLabel = (l: string) => (v: string) => apply([{ op: 'set_label', iri: sel.iri, text: v, lang: l }])
  const head = (
    <header className="of-insp-h">
      {sel.kind === 'class' && <button type="button" className="of-icobtn" onClick={() => !readOnly && setIconOpen(o => !o)} title={t('ed.icon.title')} disabled={readOnly}><Icon name={icon || 'circle-nodes'} /></button>}
      {sel.kind === 'prop' && <span className="of-icobtn static"><Icon name="arrow-right-long" /></span>}
      <div className="grow">
        <b>{labelOf(ent, sel.iri, lang)}</b>
        {renIri === null
          ? <div className="iri" title={sel.iri}>{curie(sel.iri, pf)}{!readOnly && <button type="button" className="lnk" onClick={() => setRenIri(localName(sel.iri))}>{t('ed.iri.rename')}</button>}</div>
          : <div className="row"><input type="text" autoFocus value={renIri} onChange={e => setRenIri(e.target.value)} onKeyDown={e => {
              if (e.key === 'Escape') setRenIri(null)
              if (e.key === 'Enter') { const base = sel.iri.slice(0, sel.iri.length - localName(sel.iri).length); apply([{ op: 'rename_entity', iri: sel.iri, new_iri: base + toLocalName(renIri) }]).then(ok => ok && setRenIri(null)) }
            }} /><small className="muted">{t('ed.iri.hint')}</small></div>}
      </div>
      <IconButton icon="angles-right" label={t('ed.insp.close')} onClick={close} />
      {iconOpen && <IconPicker value={icon} onClose={() => setIconOpen(false)} onPick={id => { setIconOpen(false); apply([{ op: 'set_icon', iri: sel.iri, icon: id }]) }} />}
    </header>
  )
  const labels = (
    <Sec title={t('ed.insp.labels')}>
      {langs.map(l => <label key={l} className="f lang"><span>{l}</span><Commit label={`${t('ed.insp.label')} ${l}`} value={ent.labels[l] || ''} onCommit={setLabel(l)} /></label>)}
      <label className="f"><span>{t('ed.insp.comment')}</span><Commit area label={t('ed.insp.comment')} value={ent.comments[lang] || ''} onCommit={v => apply([{ op: 'set_comment', iri: sel.iri, text: v, lang }])} /></label>
    </Sec>
  )
  const del = !readOnly && <Button variant="danger" size="sm" icon="trash" onClick={() => window.dispatchEvent(new CustomEvent('of:delete', { detail: [sel.iri] }))}>{t('ed.delete')}</Button>

  if (sel.kind === 'prop') {
    const o = onto.object_properties[sel.iri]
    const others = Object.values(onto.object_properties).filter(x => x.iri !== sel.iri).map(x => ({ iri: x.iri, label: lbl(x.iri) }))
    const addDR = (key: 'domain' | 'range', iri: string) => iri && apply([{ op: 'set_domain_range', iri: sel.iri, [key]: [...o[key], iri] }])
    const rmDR = (key: 'domain' | 'range') => (iri: string) => apply([{ op: 'set_domain_range', iri: sel.iri, [key]: o[key].filter(x => x !== iri) }])
    const pick = (onPick: (v: string) => void, label: string, list = clsList) => (
      <select aria-label={label} value="" onChange={e => onPick(e.target.value)}><option value="">+ {label}</option>{list.map(c => <option key={c.iri} value={c.iri}>{c.label}</option>)}</select>)
    return <div className="of-insp">{head}<fieldset disabled={readOnly}>
      {labels}
      <Sec title={t('ed.insp.domain')}><Chips ro={readOnly} items={o.domain.map(i => ({ iri: i, label: lbl(i) }))} onRemove={rmDR('domain')} onClick={i => select({ kind: 'class', iri: i })} />{pick(v => addDR('domain', v), t('ed.insp.add'))}</Sec>
      <Sec title={t('ed.insp.range')}><Chips ro={readOnly} items={o.range.map(i => ({ iri: i, label: lbl(i) }))} onRemove={rmDR('range')} onClick={i => select({ kind: 'class', iri: i })} />{pick(v => addDR('range', v), t('ed.insp.add'))}</Sec>
      <Sec title={t('ed.insp.inverse')}>
        <select aria-label={t('ed.insp.inverse')} value={o.inverse_of || ''} onChange={e => apply([{ op: 'set_inverse', iri: sel.iri, inverse: e.target.value || null }])}>
          <option value="">{t('ed.none')}</option>{others.map(c => <option key={c.iri} value={c.iri}>{c.label}</option>)}</select>
      </Sec>
      <Sec title={t('ed.insp.chars')}><div className="of-chars">{CHARS.map(c => <label key={c} className="chk"><input type="checkbox" checked={o.characteristics.includes(c)}
        onChange={e => apply([{ op: 'set_characteristic', iri: sel.iri, characteristic: c, value: e.target.checked }])} />{t('ed.char.' + c)}</label>)}</div></Sec>
    </fieldset>{del && <div className="of-insp-f">{del}</div>}</div>
  }

  // ---- classe ----
  const c = onto.classes[sel.iri]
  const children = Object.values(onto.classes).filter(x => x.sub_class_of.includes(sel.iri)).map(x => ({ iri: x.iri, label: lbl(x.iri) }))
  const dps = Object.values(onto.datatype_properties).filter(d => d.domain.includes(sel.iri))
  const ops = Object.values(onto.object_properties)
  const cardOf = (dp: string): Card => {
    const r = c.restrictions.find(x => x.property === dp && !x.inverse && ['min', 'max', 'exactly'].includes(x.kind))
    if (!r) return '*'
    if (r.kind === 'exactly' && r.n === 1) return '1'
    if (r.kind === 'max' && r.n === 1) return '0..1'
    if (r.kind === 'min' && r.n === 1) return '1..*'
    return '*'
  }
  const setCard = (dp: string, card: Card): Op[] => {
    const rm = c.restrictions.filter(x => x.property === dp && ['min', 'max', 'exactly'].includes(x.kind)).map(x => ({ op: 'remove_restriction', iri: sel.iri, property: dp, kind: x.kind }))
    const add: Op[] = card === '1' ? [{ op: 'set_restriction', iri: sel.iri, property: dp, kind: 'exactly', n: 1 }] : card === '0..1' ? [{ op: 'set_restriction', iri: sel.iri, property: dp, kind: 'max', n: 1 }] : card === '1..*' ? [{ op: 'set_restriction', iri: sel.iri, property: dp, kind: 'min', n: 1 }] : []
    return [...rm, ...add]
  }
  return <div className="of-insp">{head}<fieldset disabled={readOnly}>
    {labels}
    <Sec title={t('ed.insp.parents')} count={c.sub_class_of.length}>
      <Chips ro={readOnly} items={c.sub_class_of.map(i => ({ iri: i, label: lbl(i) }))} onRemove={i => apply([{ op: 'remove_subclass', iri: sel.iri, parent: i }])} onClick={i => select({ kind: 'class', iri: i })} />
      <select aria-label={t('ed.insp.addparent')} value="" onChange={e => e.target.value && apply([{ op: 'add_subclass', iri: sel.iri, parent: e.target.value }])}>
        <option value="">+ {t('ed.insp.addparent')}</option>{clsList.filter(x => x.iri !== sel.iri && !c.sub_class_of.includes(x.iri)).map(x => <option key={x.iri} value={x.iri}>{x.label}</option>)}</select>
      {!!children.length && <div className="sub"><span className="muted">{t('ed.insp.children')}</span><Chips ro items={children} onClick={i => select({ kind: 'class', iri: i })} /></div>}
    </Sec>
    <Sec title={t('ed.insp.dprops')} count={dps.length}>
      {dps.map(d => <div key={d.iri} className="of-dp">
        <button type="button" className="lnk name" title={d.iri} onClick={() => { const n = prompt(t('ed.rename'), labelOf(d, d.iri, lang)); if (n) apply([{ op: 'set_label', iri: d.iri, text: n, lang }]) }}>{labelOf(d, d.iri, lang)}</button>
        <select aria-label={t('ed.dp.type')} value={d.range[0] || ''} onChange={e => apply([{ op: 'set_domain_range', iri: d.iri, range: [e.target.value] }])}>
          {[...new Set([...DTS, ...d.range])].map(x => <option key={x} value={x}>{localName(x)}</option>)}</select>
        <select aria-label={t('ed.dp.card')} className="card" value={cardOf(d.iri)} onChange={e => apply(setCard(d.iri, e.target.value as Card))}>{CARDS.map(x => <option key={x}>{x}</option>)}</select>
        {!readOnly && <IconButton icon="xmark" label={t('ed.delete')} onClick={() => apply([{ op: 'delete_entity', iri: d.iri }])} />}
      </div>)}
      {!readOnly && <DpAdd t={t} onAdd={(name, type, card) => {
        const iri = sel.iri.slice(0, sel.iri.length - localName(sel.iri).length) + toLocalName(name).replace(/^./, s => s.toLowerCase())
        apply([{ op: 'add_datatype_property', iri, label: name, lang, domain: sel.iri, range: type }, ...setCard(iri, card)])
      }} />}
    </Sec>
    <Sec title={t('ed.insp.oprops')} count={ops.filter(o => o.domain.includes(sel.iri) || o.range.includes(sel.iri)).length}>
      <div className="chips">{ops.filter(o => o.domain.includes(sel.iri) || o.range.includes(sel.iri)).map(o => <button key={o.iri} type="button" className="chip chip-btn" onClick={() => select({ kind: 'prop', iri: o.iri })}>
        {o.domain.includes(sel.iri) ? '→' : '←'} {labelOf(o, o.iri, lang)}</button>)}</div>
    </Sec>
    <Sec title={t('ed.insp.restr')} count={c.restrictions.length}>
      {c.restrictions.map((r, i) => <div key={i} className="of-restr"><code>{lbl(r.property)} {r.kind}{r.n != null ? ' ' + r.n : ''} {r.filler ? lbl(r.filler) : typeof r.value === 'string' ? lbl(r.value) : r.value?.value ?? ''}</code>
        {!readOnly && <IconButton icon="xmark" label={t('ed.delete')} onClick={() => apply([{ op: 'remove_restriction', iri: sel.iri, property: r.property, kind: r.kind }])} />}</div>)}
      {!readOnly && <RestrAdd t={t} props={[...ops, ...Object.values(onto.datatype_properties)].map(p => ({ iri: p.iri, label: lbl(p.iri) }))} classes={clsList}
        onAdd={(op) => apply([{ op: 'set_restriction', iri: sel.iri, ...op }])} />}
    </Sec>
    <Sec title={t('ed.insp.keys')} count={c.has_keys.length}>
      {c.has_keys.map((k, i) => <div key={i} className="of-restr"><code>{k.map(lbl).join(' + ')}</code>
        {!readOnly && <IconButton icon="xmark" label={t('ed.delete')} onClick={() => apply([{ op: 'set_key', iri: sel.iri, properties: [], index: i }])} />}</div>)}
      {!readOnly && !!dps.length && <KeyAdd t={t} props={dps.map(d => ({ iri: d.iri, label: lbl(d.iri) }))} onAdd={ps => apply([{ op: 'set_key', iri: sel.iri, properties: ps, index: c.has_keys.length }])} />}
    </Sec>
    <Sec title={t('ed.insp.disjoint')} count={c.disjoint_with.length}>
      <Chips ro={readOnly} items={c.disjoint_with.map(i => ({ iri: i, label: lbl(i) }))} onRemove={i => apply([{ op: 'remove_disjoint', iri: sel.iri, other: i }])} onClick={i => select({ kind: 'class', iri: i })} />
      <select aria-label={t('ed.insp.adddisj')} value="" onChange={e => e.target.value && apply([{ op: 'add_disjoint', iri: sel.iri, other: e.target.value }])}>
        <option value="">+ {t('ed.insp.adddisj')}</option>{clsList.filter(x => x.iri !== sel.iri && !c.disjoint_with.includes(x.iri)).map(x => <option key={x.iri} value={x.iri}>{x.label}</option>)}</select>
    </Sec>
  </fieldset>{del && <div className="of-insp-f">{del}</div>}</div>
}

type TFn = (k: string, p?: Record<string, string | number>) => string
function DpAdd({ t, onAdd }: { t: TFn; onAdd: (name: string, type: string, card: Card) => void }) {
  const [name, setName] = useState(''); const [type, setType] = useState(XSD + 'string'); const [card, setCard] = useState<Card>('*')
  const go = () => { if (name.trim()) { onAdd(name.trim(), type, card); setName('') } }
  return <div className="of-dp add">
    <input type="text" placeholder={t('ed.dp.new')} aria-label={t('ed.dp.new')} value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && go()} />
    <select aria-label={t('ed.dp.type')} value={type} onChange={e => setType(e.target.value)}>{DTS.map(x => <option key={x} value={x}>{localName(x)}</option>)}</select>
    <select aria-label={t('ed.dp.card')} className="card" value={card} onChange={e => setCard(e.target.value as Card)}>{CARDS.map(x => <option key={x}>{x}</option>)}</select>
    <IconButton icon="plus" label={t('ed.dp.add')} onClick={go} disabled={!name.trim()} /></div>
}
function RestrAdd({ t, props, classes, onAdd }: { t: TFn; props: { iri: string; label: string }[]; classes: { iri: string; label: string }[]; onAdd: (o: Record<string, unknown>) => void }) {
  const [p, setP] = useState(''); const [k, setK] = useState('some'); const [n, setN] = useState(1); const [f, setF] = useState('')
  const num = ['min', 'max', 'exactly'].includes(k)
  return <div className="of-dp add wrap">
    <select aria-label={t('ed.restr.prop')} value={p} onChange={e => setP(e.target.value)}><option value="">{t('ed.restr.prop')}</option>{props.map(x => <option key={x.iri} value={x.iri}>{x.label}</option>)}</select>
    <select aria-label={t('ed.restr.kind')} value={k} onChange={e => setK(e.target.value)}>{['some', 'only', 'min', 'max', 'exactly'].map(x => <option key={x}>{x}</option>)}</select>
    {num && <input type="number" min={0} value={n} aria-label="n" className="n" onChange={e => setN(+e.target.value)} />}
    <select aria-label={t('ed.restr.filler')} value={f} onChange={e => setF(e.target.value)}><option value="">{t('ed.restr.any')}</option>{classes.map(x => <option key={x.iri} value={x.iri}>{x.label}</option>)}</select>
    <IconButton icon="plus" label={t('ed.dp.add')} disabled={!p} onClick={() => { onAdd({ property: p, kind: k, ...(num ? { n } : {}), ...(f ? { filler: f } : {}) }); setP('') }} /></div>
}
function KeyAdd({ t, props, onAdd }: { t: TFn; props: { iri: string; label: string }[]; onAdd: (ps: string[]) => void }) {
  const [ch, setCh] = useState<string[]>([])
  return <div className="of-keyadd"><div className="chips">{props.map(p => <button key={p.iri} type="button" aria-pressed={ch.includes(p.iri)} className="chip chip-btn" onClick={() => setCh(c => c.includes(p.iri) ? c.filter(x => x !== p.iri) : [...c, p.iri])}>{p.label}</button>)}</div>
    <Button size="sm" disabled={!ch.length} onClick={() => { onAdd(ch); setCh([]) }}>{t('ed.key.add')}</Button></div>
}
