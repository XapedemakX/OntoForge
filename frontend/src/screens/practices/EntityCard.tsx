// Fiche complète d'une entité (L49) : score, critères manquants, définition, auteur, source, statut, justification, dépréciation.
import { useEffect, useState } from 'react'
import { labelOf, type OntoModel } from '../../api'
import { Button } from '../../kit'
import { useI18n } from '../../i18n'
import type { Op } from '../editor/types'
import { P, STATUS_VALUES, annValues, entityCard, replacedBy, scoreTone, statusOf } from './card'
import './practices.css'

function Field({ label, value, onCommit, area, ph, testid }: { label: string; value: string; onCommit: (v: string) => void; area?: boolean; ph?: string; testid?: string }) {
  const [v, setV] = useState(value)
  useEffect(() => setV(value), [value])
  const done = () => { if (v !== value) onCommit(v) }
  return <label className="bp-f"><span>{label}</span>{area
    ? <textarea aria-label={label} data-testid={testid} rows={2} placeholder={ph} value={v} onChange={e => setV(e.target.value)} onBlur={done} />
    : <input type="text" aria-label={label} data-testid={testid} placeholder={ph} value={v} onChange={e => setV(e.target.value)} onBlur={done} onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />}</label>
}

/** Score et critères seulement (listes, en-têtes). */
export function ScoreBadge({ score, title }: { score: number; title?: string }) {
  return <span className={'badge bp-score ' + scoreTone(score)} title={title} data-testid="bp-score">{score} %</span>
}

export function EntityCard({ onto, iri, lang, readOnly, apply }: { onto: OntoModel; iri: string; lang: string; readOnly: boolean; apply: (ops: Op[], label?: string) => Promise<boolean> | void }) {
  const { t } = useI18n()
  const e = onto.classes[iri] || onto.object_properties[iri] || onto.datatype_properties[iri]
  const card = entityCard(onto, iri)
  const [rep, setRep] = useState('')
  useEffect(() => setRep(''), [iri])
  if (!e || !card) return null
  const set = (property: string, values: string[], l?: string) => apply([{ op: 'set_annotations', iri, property, values, ...(l !== undefined ? { lang: l } : {}) }], t('bp.hist.card'))
  const list = (s: string) => s.split(/[;\n]/).map(x => x.trim()).filter(Boolean)
  const others = [...Object.values(onto.classes), ...Object.values(onto.object_properties), ...Object.values(onto.datatype_properties)]
    .filter(x => x.iri !== iri && !x.deprecated).map(x => ({ iri: x.iri, label: labelOf(x, x.iri, lang) })).sort((a, b) => a.label.localeCompare(b.label))
  const reps = replacedBy(e)
  return (
    <section className="of-sec bp-card" data-testid="bp-card">
      <h4>{t('bp.card')} <ScoreBadge score={card.score} title={t('bp.score.title')} /></h4>
      {card.missing.length > 0 && <p className="muted bp-missing" data-testid="bp-missing">{t('bp.missing')} {card.missing.map(k => t('bp.crit.' + k)).join(', ')}</p>}
      {e.deprecated && <p className="bp-dep" data-testid="bp-deprecated"><span className="badge lost">{t('ed.deprecated')}</span> {reps.length ? t('bp.dep.by', { list: reps.map(r => labelOf(onto.classes[r] || onto.object_properties[r] || onto.datatype_properties[r], r, lang)).join(', ') }) : t('bp.dep.norep')}</p>}
      <fieldset disabled={readOnly} className="bp-fields">
        <Field label={t('bp.definition') + ' (' + lang + ')'} testid="bp-definition" area value={annValues(e, P.definition, lang)[0] ?? ''} ph={t('bp.definition.ph')} onCommit={v => set(P.definition, v ? [v] : [], lang)} />
        <Field label={t('bp.creator')} testid="bp-creator" value={annValues(e, P.creator).join('; ')} ph={t('bp.list.ph')} onCommit={v => set(P.creator, list(v))} />
        <Field label={t('bp.source')} testid="bp-source" value={annValues(e, P.source).join('; ')} ph={t('bp.source.ph')} onCommit={v => set(P.source, list(v))} />
        <label className="bp-f"><span>{t('bp.status')}</span>
          <select aria-label={t('bp.status')} data-testid="bp-status" value={statusOf(e) ?? ''} onChange={ev => set(P.status, ev.target.value ? [ev.target.value] : [])}>
            <option value="">{t('ed.none')}</option>{STATUS_VALUES.map(s => <option key={s} value={s}>{t('bp.status.' + s)}</option>)}</select></label>
        {'justification' in card.criteria && <Field label={t('bp.justification')} testid="bp-justification" area value={annValues(e, P.editorialNote, lang)[0] ?? ''} ph={t('bp.justification.ph')} onCommit={v => set(P.editorialNote, v ? [v] : [], lang)} />}
      </fieldset>
      {!readOnly && (e.deprecated
        ? <Button size="sm" variant="ghost" icon="rotate-left" data-testid="bp-undeprecate" onClick={() => apply([{ op: 'set_deprecated', iri, value: false }], t('bp.hist.undeprecate'))}>{t('bp.undeprecate')}</Button>
        : <div className="bp-deprow">
          <select aria-label={t('bp.replacement')} data-testid="bp-replacement" value={rep} onChange={ev => setRep(ev.target.value)}>
            <option value="">{t('bp.replacement.none')}</option>{others.map(o => <option key={o.iri} value={o.iri}>{o.label}</option>)}</select>
          <Button size="sm" icon="box-archive" data-testid="bp-deprecate" onClick={() => apply([{ op: 'set_deprecated', iri, value: true, replaced_by: rep ? [rep] : [] }], t('bp.hist.deprecate'))}>{t('bp.deprecate')}</Button>
        </div>)}
      <p className="muted bp-hint">{t('bp.deprecate.hint')}</p>
    </section>
  )
}
