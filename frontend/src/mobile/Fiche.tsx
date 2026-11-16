import { useMemo, useState } from 'react'
import { curie, labelOf, localName, type OntoModel, type Project } from '../api'
import { BottomSheet, Icon, useToast, type SheetApi } from '../kit'
import { useI18n, tr } from '../i18n'
import { useReadOnly } from '../collab/readonly'
import { eapi, type Op } from '../screens/editor/types'
import { toLocalName } from '../screens/editor/layout'
import { DATATYPES, ancestors, cardText, childrenMap, classProps, kindOf, lblOf, restrText } from '../screens/ontology-list/model'
import './fiche.css'

/**
 * Fiche d'une classe ou d'une propriété sur téléphone (L44), dans une feuille du bas.
 * Modification limitée (décision D-L44-01) : ajouter une sous-classe, ajouter une propriété (attribut ou relation), renommer le libellé et le commentaire.
 * Le reste (restrictions, clés, disjonctions, déplacement) est affiché en lecture ; l'édition lourde est « Sur ordinateur ».
 * Les écritures passent par /ops (même chemin que l'éditeur de bureau : If-Match, journal d'activité, rôle lecteur refusé par le serveur).
 */
export function FicheSheet({ p, setP, iri, lang, onClose, onOpen, initial = 'peek', actions, startMode }: {
  p: Project; setP: (p: Project) => void; iri: string; lang: string; onClose: () => void; onOpen: (iri: string) => void; initial?: 'peek' | 'half' | 'full'; startMode?: 'sub' | 'prop' | null
  actions?: (a: SheetApi) => React.ReactNode
}) {
  const { t } = useI18n()
  const k = kindOf(p.onto, iri)
  const title = k ? lblOf(p.onto, iri, lang) : t('mob.fiche.gone')
  return (
    <BottomSheet open onClose={onClose} title={t('mob.fiche.title', { name: title })} heading={title} icon={k === 'class' ? 'circle-nodes' : k === 'objectProperty' ? 'arrow-right-long' : 'font'} initial={initial} testid="fiche-sheet">
      {api => k === 'class' ? <ClassBody key={iri} p={p} setP={setP} iri={iri} lang={lang} api={api} onOpen={onOpen} extra={actions?.(api)} startMode={startMode} />
        : k ? <PropBody key={iri} p={p} setP={setP} iri={iri} lang={lang} api={api} onOpen={onOpen} /> : <p className="muted">{t('mob.fiche.gone')}</p>}
    </BottomSheet>)
}

function useOps(p: Project, setP: (p: Project) => void) {
  const toast = useToast()
  return async (ops: Op[], label?: string): Promise<boolean> => {
    try {
      const r = await eapi.ops(p.id, ops, label)
      if (!r.ok) { toast(r.errors.map(e => e.message).join(' ; ') || tr('common.error')); return false }
      setP(r.project); if (r.warnings?.[0]) toast(r.warnings[0]); return true
    } catch (e) { toast((e as Error).message); return false }
  }
}
const baseIri = (onto: OntoModel) => (onto.meta.iri || 'https://example.org/onto').replace(/[#/]?$/, '#')

function ClassBody({ p, setP, iri, lang, api, onOpen, extra, startMode }: { startMode?: 'sub' | 'prop' | null; p: Project; setP: (p: Project) => void; iri: string; lang: string; api: SheetApi; onOpen: (i: string) => void; extra?: React.ReactNode }) {
  const { t } = useI18n(); const onto = p.onto; const cls = onto.classes[iri]
  const ro = useReadOnly()
  const apply = useOps(p, setP)
  const [mode, setMode] = useState<null | 'sub' | 'prop' | 'rename'>(startMode ?? null)
  const kids = useMemo(() => childrenMap(onto, lang).get(iri) ?? [], [onto, iri, lang])
  const rows = useMemo(() => classProps(onto, iri, lang), [onto, iri, lang])
  const comment = cls.comments[lang] || cls.comments.en || cls.comments.fr || ''
  const full = api.snap !== 'peek'
  const open = (m: 'sub' | 'prop' | 'rename') => { setMode(m); if (api.snap === 'peek') api.setSnap('half') }
  return (
    <div className="fiche" data-testid="fiche-class">
      <div className="iri mono" title={iri}>{curie(iri, onto.meta.prefixes)}</div>
      {mode !== 'rename' && (comment ? <p className={'desc' + (full ? '' : ' clamp')}>{comment}</p> : <p className="desc muted">{t('mob.fiche.nodesc')}</p>)}
      <div className="counts">
        <span><b>{rows.length}</b> {t('mob.fiche.props')}</span><span><b>{kids.length}</b> {t('mob.fiche.subs')}</span><span><b>{cls.sub_class_of.filter(x => onto.classes[x]).length}</b> {t('mob.fiche.parents')}</span>
      </div>
      {mode === null && <div className="acts">
        {!ro && <button type="button" className="btn primary" data-testid="fiche-add-sub" onClick={() => open('sub')}><Icon name="plus" />{t('mob.fiche.addsub')}</button>}
        {!ro && full && <button type="button" className="btn" data-testid="fiche-add-prop" onClick={() => open('prop')}><Icon name="plus" />{t('mob.fiche.addprop')}</button>}
        {!full && <button type="button" className="btn" onClick={() => api.setSnap('full')}>{t('mob.fiche.more')}<Icon name="chevron-up" /></button>}
        {extra}
      </div>}
      {mode === 'sub' && <AddSub onto={onto} iri={iri} lang={lang} apply={apply} done={() => setMode(null)} />}
      {mode === 'prop' && <AddProp onto={onto} iri={iri} lang={lang} apply={apply} done={() => setMode(null)} />}
      {mode === 'rename' && <Rename onto={onto} iri={iri} lang={lang} apply={apply} done={() => setMode(null)} />}
      {full && mode === null && <>
        {!ro && <div className="acts"><button type="button" className="btn" data-testid="fiche-rename" onClick={() => open('rename')}><Icon name="pen" />{t('mob.fiche.rename')}</button>{extra}</div>}
        <h3 className="fh">{t('mob.fiche.props')} <span className="cnt">{rows.length}</span></h3>
        {rows.length === 0 && <p className="muted">{t('ol.props.none')}</p>}
        <ul className="cards">{rows.map(r => (
          <li key={r.iri}><button type="button" className="card-row" onClick={() => onOpen(r.iri)}>
            <Icon name={r.kind === 'data' ? 'font' : 'arrow-right-long'} className="ci" />
            <span className="tx"><b>{r.label}</b><small>{r.kind === 'data' ? r.target : '→ ' + r.target} · {cardText(r.card, t)}{r.origin ? ' · ' + t('ol.origin.inherited', { name: lblOf(onto, r.origin, lang) }) : ''}</small></span>
            <Icon name="chevron-right" className="chev" /></button></li>))}</ul>
        <h3 className="fh">{t('mob.fiche.hier')}</h3>
        <ChipRow label={t('ol.parents')} ids={cls.sub_class_of.filter(x => onto.classes[x])} onto={onto} lang={lang} onOpen={onOpen} />
        <ChipRow label={t('ol.children')} ids={kids} onto={onto} lang={lang} onOpen={onOpen} />
        {ancestors(onto, iri).length > cls.sub_class_of.length && <ChipRow label={t('mob.fiche.ancestors')} ids={ancestors(onto, iri)} onto={onto} lang={lang} onOpen={onOpen} />}
        {(cls.restrictions.length > 0 || cls.has_keys.length > 0 || cls.disjoint_with.length > 0) && <>
          <h3 className="fh">{t('mob.fiche.rules')} <span className="cnt">{cls.restrictions.length + cls.has_keys.length + cls.disjoint_with.length}</span></h3>
          <ul className="rules">
            {cls.restrictions.map((r, i) => <li key={'r' + i}><Icon name="angle-right" /><span>{t('ol.restr.every', { name: lblOf(onto, iri, lang) })} <b>{restrText(r, i2 => lblOf(onto, i2, lang), t)}</b></span></li>)}
            {cls.has_keys.map((kk, i) => <li key={'k' + i}><Icon name="key" /><span>{kk.map(x => lblOf(onto, x, lang)).join(' + ')}</span></li>)}
            {cls.disjoint_with.map(d => <li key={'d' + d}><Icon name="ban" /><span>{t('ol.disj.with')} <b>{lblOf(onto, d, lang)}</b></span></li>)}
          </ul>
          <p className="muted small"><Icon name="desktop" /> {t('mob.fiche.rules.hint')}</p></>}
      </>}
    </div>)
}

function ChipRow({ label, ids, onto, lang, onOpen }: { label: string; ids: string[]; onto: OntoModel; lang: string; onOpen: (i: string) => void }) {
  return <div className="chiprow"><span className="muted">{label}</span><div className="chips">{ids.length === 0 ? <span className="muted">—</span> : ids.map(i => <button key={i} type="button" className="mchip" onClick={() => onOpen(i)}>{lblOf(onto, i, lang)}</button>)}</div></div>
}

type Apply = (ops: Op[], label?: string) => Promise<boolean>
function AddSub({ onto, iri, lang, apply, done }: { onto: OntoModel; iri: string; lang: string; apply: Apply; done: () => void }) {
  const { t } = useI18n(); const [name, setName] = useState(''); const [busy, setBusy] = useState(false)
  const go = async () => {
    const label = name.trim(), local = toLocalName(label)
    if (!label || !local || busy) return
    setBusy(true)
    const n = baseIri(onto) + local.replace(/^./, s => s.toUpperCase())
    const ok = await apply([{ op: 'add_class', iri: n, label, lang }, { op: 'add_subclass', iri: n, parent: iri }], tr('hist.ajouter_une_sous_classe'))
    setBusy(false); if (ok) done()
  }
  return (
    <form className="addform" onSubmit={e => { e.preventDefault(); void go() }} data-testid="fiche-sub-form">
      <label className="f"><span>{t('mob.fiche.sub.name', { parent: lblOf(onto, iri, lang) })}</span>
        <input type="text" autoFocus value={name} onChange={e => setName(e.target.value)} placeholder={t('mob.fiche.sub.ph')} data-testid="fiche-sub-name" autoCapitalize="sentences" enterKeyHint="done" /></label>
      <div className="acts"><button type="submit" className="btn primary" disabled={!name.trim() || busy} data-testid="fiche-sub-ok">{t('mob.fiche.add')}</button><button type="button" className="btn" onClick={done}>{t('common.cancel')}</button></div>
    </form>)
}
function AddProp({ onto, iri, lang, apply, done }: { onto: OntoModel; iri: string; lang: string; apply: Apply; done: () => void }) {
  const { t } = useI18n()
  const [kind, setKind] = useState<'data' | 'object'>('data'); const [name, setName] = useState(''); const [dt, setDt] = useState(DATATYPES[0]); const [target, setTarget] = useState(''); const [busy, setBusy] = useState(false)
  const classes = Object.values(onto.classes).map(c => ({ iri: c.iri, label: labelOf(c, c.iri, lang) })).sort((a, b) => a.label.localeCompare(b.label))
  const ready = name.trim() && (kind === 'data' || target)
  const go = async () => {
    if (!ready || busy) return
    setBusy(true)
    const local = toLocalName(name.trim()).replace(/^./, s => s.toLowerCase())
    const piri = iri.slice(0, iri.length - localName(iri).length) + local
    const op: Op = kind === 'data' ? { op: 'add_datatype_property', iri: piri, label: name.trim(), lang, domain: iri, range: dt } : { op: 'add_object_property', iri: piri, label: name.trim(), lang, domain: iri, range: target }
    const ok = await apply([op], tr('hist.nouvelle_propriete')); setBusy(false); if (ok) done()
  }
  return (
    <form className="addform" onSubmit={e => { e.preventDefault(); void go() }} data-testid="fiche-prop-form">
      <div className="seg" role="group" aria-label={t('ol.padd.kind')}>
        <button type="button" aria-pressed={kind === 'data'} onClick={() => setKind('data')}>{t('ol.padd.data')}</button>
        <button type="button" aria-pressed={kind === 'object'} onClick={() => setKind('object')}>{t('ol.padd.rel')}</button></div>
      <label className="f"><span>{t('ol.padd.name')}</span><input type="text" autoFocus value={name} onChange={e => setName(e.target.value)} data-testid="fiche-prop-name" enterKeyHint="done" /></label>
      {kind === 'data'
        ? <label className="f"><span>{t('ol.col.type')}</span><select value={dt} onChange={e => setDt(e.target.value)}>{DATATYPES.map(x => <option key={x} value={x}>{localName(x)}</option>)}</select></label>
        : <label className="f"><span>{t('ol.padd.target')}</span><select value={target} onChange={e => setTarget(e.target.value)} data-testid="fiche-prop-target"><option value="">—</option>{classes.map(c => <option key={c.iri} value={c.iri}>{c.label}</option>)}</select></label>}
      <div className="acts"><button type="submit" className="btn primary" disabled={!ready || busy} data-testid="fiche-prop-ok">{t('mob.fiche.add')}</button><button type="button" className="btn" onClick={done}>{t('common.cancel')}</button></div>
    </form>)
}
function Rename({ onto, iri, lang, apply, done }: { onto: OntoModel; iri: string; lang: string; apply: Apply; done: () => void }) {
  const { t } = useI18n()
  const e = onto.classes[iri] || onto.object_properties[iri] || onto.datatype_properties[iri]
  const [label, setLabel] = useState(e.labels[lang] || labelOf(e, iri, lang)); const [comment, setComment] = useState(e.comments[lang] || '')
  const go = async () => {
    const ops: Op[] = []
    if (label.trim() && label.trim() !== (e.labels[lang] || '')) ops.push({ op: 'set_label', iri, text: label.trim(), lang })
    if (comment !== (e.comments[lang] || '')) ops.push({ op: 'set_comment', iri, text: comment, lang })
    if (!ops.length || await apply(ops, tr('hist.libelle'))) done()
  }
  return (
    <form className="addform" onSubmit={ev => { ev.preventDefault(); void go() }} data-testid="fiche-rename-form">
      <label className="f"><span>{t('ol.label')} ({lang})</span><input type="text" autoFocus value={label} onChange={ev => setLabel(ev.target.value)} data-testid="fiche-label" /></label>
      <label className="f"><span>{t('ol.comment')} ({lang})</span><textarea rows={3} value={comment} onChange={ev => setComment(ev.target.value)} data-testid="fiche-comment" /></label>
      <div className="acts"><button type="submit" className="btn primary" data-testid="fiche-rename-ok">{t('common.save')}</button><button type="button" className="btn" onClick={done}>{t('common.cancel')}</button></div>
    </form>)
}

function PropBody({ p, setP, iri, lang, api, onOpen }: { p: Project; setP: (p: Project) => void; iri: string; lang: string; api: SheetApi; onOpen: (i: string) => void }) {
  const { t } = useI18n(); const onto = p.onto; const ro = useReadOnly(); const apply = useOps(p, setP)
  const [mode, setMode] = useState(false)
  const o = onto.object_properties[iri]; const d = onto.datatype_properties[iri]; const e = o || d
  const dom = e.domain.filter(x => onto.classes[x]), rng = o ? o.range.filter(x => onto.classes[x]) : []
  return (
    <div className="fiche" data-testid="fiche-prop">
      <div className="iri mono" title={iri}>{curie(iri, onto.meta.prefixes)}</div>
      {!mode && (e.comments[lang] ? <p className="desc">{e.comments[lang]}</p> : <p className="desc muted">{t('mob.fiche.nodesc')}</p>)}
      {!mode && <>
        <ChipRow label={t('ed.insp.domain')} ids={dom} onto={onto} lang={lang} onOpen={onOpen} />
        {o ? <ChipRow label={t('ed.insp.range')} ids={rng} onto={onto} lang={lang} onOpen={onOpen} />
          : <div className="chiprow"><span className="muted">{t('ol.col.type')}</span><div className="chips"><span className="mchip static">{d.range[0] ? localName(d.range[0]) : '—'}</span></div></div>}
        {o && o.characteristics.length > 0 && <div className="chiprow"><span className="muted">{t('ed.insp.chars')}</span><div className="chips">{o.characteristics.map(c => <span key={c} className="mchip static">{t('ed.char.' + c)}</span>)}</div></div>}
        {!ro && <div className="acts"><button type="button" className="btn" onClick={() => { setMode(true); if (api.snap === 'peek') api.setSnap('half') }}><Icon name="pen" />{t('mob.fiche.rename')}</button></div>}
      </>}
      {mode && <Rename onto={onto} iri={iri} lang={lang} apply={apply} done={() => setMode(false)} />}
    </div>)
}
