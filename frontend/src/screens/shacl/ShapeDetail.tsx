import { useMemo } from 'react'
import { curie, localName, type NodeShape, type PropertyShape, type Project } from '../../api'
import { Button, Icon, IconButton } from '../../kit'
import { useI18n } from '../../i18n'
import { DATATYPES, PRESET_VALUES, ancestors, cardPreset, cardText, classLabel, newPropertyShape, otherChips, pathIri, pathLabel, pathStr, sev, SEV_ICON, shapeTitle, XSD, type CardPreset } from './helpers'

type Upd = (fn: (s: NodeShape) => void) => void

function CardCell({ ps, set }: { ps: PropertyShape; set: (patch: Partial<PropertyShape>) => void }) {
  const { t } = useI18n()
  const preset = cardPreset(ps.min_count, ps.max_count)
  const onPreset = (v: CardPreset) => { if (v === 'custom') set({ min_count: ps.min_count ?? 1, max_count: ps.max_count ?? 3 }); else { const [a, b] = PRESET_VALUES[v]; set({ min_count: a, max_count: b }) } }
  const num = (v: string): number | null => (v === '' ? null : Math.max(0, parseInt(v, 10) || 0))
  return (
    <div className="cell-stack">
      <select value={preset} aria-label={t('sh.col.card')} onChange={e => onPreset(e.target.value as CardPreset)}>
        <option value="opt">{t('sh.card.opt')}</option>
        <option value="req1">{t('sh.card.req1')}</option>
        <option value="min1">{t('sh.card.min1')}</option>
        <option value="opt1">{t('sh.card.opt1')}</option>
        <option value="custom">{preset === 'custom' ? cardText(ps.min_count, ps.max_count, t) : t('sh.card.custom')}</option>
      </select>
      {preset === 'custom' && <span className="mm"><input type="number" min={0} value={ps.min_count ?? ''} aria-label={t('sh.card.minlabel')} onChange={e => set({ min_count: num(e.target.value) })} /><span>{t('sh.card.to')}</span><input type="number" min={0} value={ps.max_count ?? ''} placeholder="∞" aria-label={t('sh.card.maxlabel')} onChange={e => set({ max_count: num(e.target.value) })} /></span>}
    </div>
  )
}

function TypeCell({ ps, p, set }: { ps: PropertyShape; p: Project; set: (patch: Partial<PropertyShape>) => void }) {
  const { t, lang } = useI18n()
  const classes = Object.keys(p.onto.classes).sort((a, b) => classLabel(a, p.onto, lang).localeCompare(classLabel(b, p.onto, lang), lang))
  const val = ps.datatype ? 'dt:' + ps.datatype : ps.class?.length ? 'cl:' + ps.class[0] : ''
  const known = val === '' || DATATYPES.some(d => 'dt:' + d === val) || classes.some(c => 'cl:' + c === val)
  const on = (v: string) => {
    if (v === '') set({ datatype: null, class: [] })
    else if (v.startsWith('dt:')) set({ datatype: v.slice(3), class: [] })
    else set({ datatype: null, class: [v.slice(3)] })
  }
  const multi = (ps.class?.length ?? 0) > 1
  return (
    <select value={val} aria-label={t('sh.col.type')} onChange={e => on(e.target.value)}>
      <option value="">{t('sh.type.any')}</option>
      {!known && <option value={val}>{curie(val.slice(3), p.shapes.prefixes)}</option>}
      <optgroup label={t('sh.type.datatypes')}>{DATATYPES.map(d => <option key={d} value={'dt:' + d}>{d.replace(XSD, '')}</option>)}</optgroup>
      <optgroup label={t('sh.type.classes')}>{classes.map(c => <option key={c} value={'cl:' + c}>{classLabel(c, p.onto, lang)}{multi && c === ps.class![0] ? ' +' + (ps.class!.length - 1) : ''}</option>)}</optgroup>
    </select>
  )
}

export function ShapeDetail({ p, shape, icons, upd, onAskKrakie, highlight }: {
  p: Project; shape: NodeShape; icons: Record<string, string>; upd: Upd; onAskKrakie: (prompt: string) => void; highlight: Set<string>
}) {
  const { t, lang } = useI18n()
  const pf = { ...p.shapes.prefixes, ...p.onto.meta.prefixes }
  const { title, cls } = shapeTitle(shape, p.onto, lang)
  const setProp = (id: string, patch: Partial<PropertyShape>) => upd(s => { const i = s.properties.findIndex(x => x.id === id); if (i >= 0) s.properties[i] = { ...s.properties[i], ...patch } })
  const addable = useMemo(() => {
    const used = new Set(shape.properties.map(x => pathIri(x.path)))
    const anc = cls ? ancestors(p.onto, cls) : new Set<string>()
    const all = [...Object.values(p.onto.object_properties), ...Object.values(p.onto.datatype_properties)].filter(x => !used.has(x.iri))
    const mine = all.filter(x => x.domain.some(d => anc.has(d))), other = all.filter(x => !mine.includes(x))
    const lab = (x: { iri: string; labels: Record<string, string> }) => pathLabel({ kind: 'predicate', iri: x.iri, args: [] }, p.onto, lang)
    const sort = (l: typeof all) => l.sort((a, b) => lab(a).localeCompare(lab(b), lang)).map(x => ({ iri: x.iri, label: lab(x) }))
    return { mine: sort(mine), other: sort(other) }
  }, [shape, cls, p.onto, lang])
  const sevOf = sev(shape.severity)
  const targets: string[] = [
    ...shape.targets.target_class.map(c => t('sh.target.class', { v: classLabel(c, p.onto, lang) })),
    ...shape.targets.target_node.map(c => t('sh.target.node', { v: curie(c, pf) })),
    ...shape.targets.target_subjects_of.map(c => t('sh.target.subjects', { v: curie(c, pf) })),
    ...shape.targets.target_objects_of.map(c => t('sh.target.objects', { v: curie(c, pf) })),
  ]
  const prompts = [t('sh.k.add', { v: title }), t('sh.k.explain', { v: title })]
  return (
    <article className="shd">
      <header className="shd-head">
        <div className="shd-ico"><Icon name={(cls && icons[cls]) || 'shapes'} /></div>
        <div className="shd-id">
          <h2>{title}</h2>
          <div className="shd-sub"><span className="mono" title={shape.id}>{curie(shape.id, pf)}</span></div>
          <p className="shd-target">{targets.length ? targets.join(' ; ') : t('sh.target.none')}</p>
          <div className="shd-meta">
            <label className="shd-toggle" title={t('sh.closed.hint')}><input type="checkbox" checked={shape.closed} onChange={e => upd(s => { s.closed = e.target.checked })} />{shape.closed ? t('sh.closed') : t('sh.open')}</label>
            <label className={'shsev ' + sevOf}><Icon name={SEV_ICON[sevOf]} />
              <select value={sevOf} aria-label={t('sh.col.sev')} onChange={e => upd(s => { s.severity = e.target.value as any })}>
                {(['Violation', 'Warning', 'Info'] as const).map(v => <option key={v} value={v}>{t('sh.sev.' + v)}</option>)}
              </select></label>
          </div>
        </div>
        <div className="shd-krakie">
          <Button variant="primary" icon="wand-magic-sparkles" onClick={() => onAskKrakie(prompts[0])}>{t('sh.k.btn')}</Button>
        </div>
      </header>
      <div className="shd-chips" aria-label={t('sh.k.ask')}>
        {prompts.map(x => <button key={x} type="button" className="chip" onClick={() => onAskKrakie(x)}>{x}</button>)}
      </div>
      <div className="shgrid-wrap">
        <table className="shgrid">
          <colgroup><col className="c-path" /><col className="c-card" /><col className="c-type" /><col className="c-other" /><col className="c-sev" /><col className="c-msg" /><col className="c-act" /></colgroup>
          <thead><tr><th>{t('sh.col.path')}</th><th>{t('sh.col.card')}</th><th>{t('sh.col.type')}</th><th>{t('sh.col.other')}</th><th>{t('sh.col.sev')}</th><th>{t('sh.col.msg')}</th><th><span className="sr">{t('sh.col.act')}</span></th></tr></thead>
          <tbody>
            {shape.properties.map(ps => {
              const sv = sev(ps.severity); const chips = otherChips(ps, pf, p.onto, lang, t)
              const lbl = pathLabel(ps.path, p.onto, lang)
              const msg = ps.messages[lang] ?? ps.messages.fr ?? ps.messages.en ?? ps.messages[''] ?? Object.values(ps.messages)[0] ?? ''
              return (
                <tr key={ps.id} id={'ps-' + ps.id} className={highlight.has(ps.id) ? 'hl' : ''}>
                  <td><div className="pth"><b>{lbl || pathStr(ps.path, pf)}</b><span className="mono">{pathStr(ps.path, pf)}</span></div></td>
                  <td><CardCell ps={ps} set={patch => setProp(ps.id, patch)} /></td>
                  <td><TypeCell ps={ps} p={p} set={patch => setProp(ps.id, patch)} /></td>
                  <td>{chips.length ? <ul className="chips">{chips.map((c, i) => <li key={i} title={c.title ?? c.text}><Icon name={c.icon} />{c.text}</li>)}</ul> : <span className="muted">{t('sh.none')}</span>}</td>
                  <td><label className={'shsev ' + sv}><Icon name={SEV_ICON[sv]} /><select value={sv} aria-label={t('sh.col.sev')} onChange={e => setProp(ps.id, { severity: e.target.value as any })}>{(['Violation', 'Warning', 'Info'] as const).map(v => <option key={v} value={v}>{t('sh.sev.' + v)}</option>)}</select></label></td>
                  <td><textarea rows={2} className="msg" value={msg} placeholder={t('sh.msg.ph')} aria-label={t('sh.col.msg')} onChange={e => setProp(ps.id, { messages: e.target.value ? { ...ps.messages, [lang]: e.target.value } : Object.fromEntries(Object.entries(ps.messages).filter(([k]) => k !== lang)) })} /></td>
                  <td className="act"><IconButton icon="trash-can" label={t('sh.del', { v: lbl || localName(pathIri(ps.path) ?? '') })} onClick={() => upd(s => { s.properties = s.properties.filter(x => x.id !== ps.id) })} /></td>
                </tr>
              )
            })}
            {shape.properties.length === 0 && <tr><td colSpan={7} className="muted shgrid-empty">{t('sh.noprops')}</td></tr>}
          </tbody>
        </table>
      </div>
      <footer className="shd-add">
        <Icon name="plus" />
        <select value="" aria-label={t('sh.add')} onChange={e => { const iri = e.target.value; if (iri) upd(s => { s.properties.push(newPropertyShape(iri, p.onto)) }) }}>
          <option value="">{t('sh.add')}</option>
          {addable.mine.length > 0 && <optgroup label={t('sh.add.mine')}>{addable.mine.map(x => <option key={x.iri} value={x.iri}>{x.label}</option>)}</optgroup>}
          {addable.other.length > 0 && <optgroup label={t('sh.add.other')}>{addable.other.map(x => <option key={x.iri} value={x.iri}>{x.label}</option>)}</optgroup>}
        </select>
        <span className="grow" />
        <button type="button" className="linkish" onClick={() => onAskKrakie(prompts[0])}><Icon name="wand-magic-sparkles" />{t('sh.add.krakie')}</button>
      </footer>
    </article>
  )
}
