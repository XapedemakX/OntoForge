import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, localName } from '../../api'
import { Button, EmptyState, Icon, useToast } from '../../kit'
import { useT, useI18n, tr } from '../../i18n'
import { openAssistant, useAssistantContext } from '../../lib/assistantContext'
import type { ScreenProps } from '../../shell/types'
import { toLocalName } from '../editor/layout'
import { eapi, type Op } from '../editor/types'
import { ClassSheet } from './ClassSheet'
import type { SheetCtx } from './ctx'
import { ListPane } from './ListPane'
import { kindOf, lblOf, type Kind } from './model'
import { IndividualSheet, ObjectPropSheet, DataPropSheet } from './PropSheets'
import { QuickPanel } from './QuickPanel'
import './ontology-list.css'

type Sel = { kind: Kind; iri: string } | null
const NEW_OP: Record<Kind, string> = { class: 'add_class', objectProperty: 'add_object_property', datatypeProperty: 'add_datatype_property', individual: '' }

/** Vue liste de l'ontologie : liste à gauche (recherche, onglets, arbre), fiche structurée à droite, Krakie en contexte. */
export function OntologyList({ p, setP }: ScreenProps) {
  const t = useT(); const { lang } = useI18n(); const toast = useToast()
  const onto = p.onto
  const [tab, setTab] = useState<Kind>('class'); const [sel, setSel] = useState<Sel>(null)
  const [icons, setIcons] = useState<Record<string, string>>({}); const [abstract, setAbstract] = useState<Set<string>>(new Set())
  useEffect(() => {
    let live = true
    eapi.graph(p.id, '', lang).then(g => {
      if (!live) return
      setIcons(Object.fromEntries(g.nodes.filter(n => n.icon).map(n => [n.id, n.icon!])))
      setAbstract(new Set(g.nodes.filter(n => n.abstract).map(n => n.id)))
    }).catch(() => {})
    return () => { live = false }
  }, [p.id, p.updated_at, lang])
  // la sélection disparaît si l'élément n'existe plus
  const cur = sel && kindOf(onto, sel.iri) ? sel : null
  useEffect(() => { if (sel && !kindOf(onto, sel.iri)) setSel(null) }, [onto, sel])

  const select = useCallback((iri: string, kind: Kind) => { if (!iri) { setSel(null); return } setSel({ kind, iri }); setTab(kind) }, [])
  const go = useCallback((iri: string) => { const k = kindOf(onto, iri); if (k) select(iri, k) }, [onto, select])

  const apply = useCallback(async (ops: Op[], label?: string) => {
    try {
      const r = await eapi.ops(p.id, ops, label)
      if (!r.ok) { toast(r.errors.map(e => e.message).join(' ; ') || t('ol.err')); return false }
      setP(r.project); if (r.warnings[0]) toast(r.warnings[0]); return true
    } catch (e) { toast((e as Error).message); return false }
  }, [p.id, setP, toast, t])
  const edit = useCallback(async (fn: (o: typeof onto) => void) => {
    try { const o = structuredClone(p.onto); fn(o); setP(await api.putOnto(p.id, o)); return true } catch (e) { toast((e as Error).message); return false }
  }, [p, setP, toast])

  const lbl = useCallback((i: string) => lblOf(onto, i, lang), [onto, lang])
  const label = cur ? lbl(cur.iri) : ''
  const ask = useCallback((prompt: string, send = false) => {
    openAssistant({ prompt: prompt || undefined, send, context: { screen: 'ontology-list', projectId: p.id, selection: cur ? { kind: cur.kind, id: cur.iri, label } : null } })
  }, [p.id, cur, label])

  const create = async (kind: Kind, name: string) => {
    const local = toLocalName(name); if (!local) { toast(t('ol.new.invalid')); return false }
    const base = (onto.meta.iri || 'https://example.org/onto').replace(/[#/]?$/, '#')
    const iri = base + (kind === 'class' ? local.replace(/^./, s => s.toUpperCase()) : kind === 'individual' ? local : local.replace(/^./, s => s.toLowerCase()))
    let ok: boolean
    if (kind === 'individual') {
      if (kindOf(onto, iri)) { toast(t('ol.new.exists')); return false }
      ok = await edit(o => { o.individuals[iri] = { iri, labels: { [lang]: name }, comments: {}, annotations: [], deprecated: false, types: [], facts: [], same_as: [], different_from: [] } })
    } else ok = await apply([{ op: NEW_OP[kind], iri, label: name, lang }], tr('hist.nouvel_element'))
    if (ok) select(iri, kind)
    return ok
  }

  const c: SheetCtx = { p, onto, lang, t, apply, edit, go, toast, icons, abstract, lbl, ask, select }
  const suggestions = useMemo(() => cur
    ? (cur.kind === 'class'
      ? [t('ol.sugg.addprop', { name: label }), t('ol.sugg.explain', { name: label }), t('ol.sugg.shapes', { name: label })]
      : cur.kind === 'individual' ? [t('ol.sugg.iexplain', { name: label })]
      : [t('ol.sugg.pexplain', { name: label }), t('ol.sugg.pcheck', { name: label })])
    : [t('ol.sugg.propose'), t('ol.sugg.review')], [cur, label, t])
  useAssistantContext({ screen: 'ontology-list', projectId: p.id, target: p.target, selection: cur ? { kind: cur.kind, id: cur.iri, label } : null, suggestions, extra: { tab } }, [label, suggestions.join('|'), tab])

  const empty = Object.keys(onto.classes).length === 0 && Object.keys(onto.object_properties).length === 0
  return (
    <div className={'ol' + (cur ? ' has-sel' : '')} data-tour="ol">
      <ListPane onto={onto} lang={lang} tab={tab} setTab={setTab} sel={cur?.iri ?? null} onSelect={select} icons={icons} onCreate={create} />
      <div className="ol-right">
        <div className="ol-scroll-main">
          <div className="ol-sheet">
            {cur && <button type="button" className="ol-back" onClick={() => setSel(null)}><Icon name="arrow-left" />{t('ol.back')}</button>}
            {cur?.kind === 'class' && <ClassSheet c={c} iri={cur.iri} />}
            {cur?.kind === 'objectProperty' && <ObjectPropSheet c={c} iri={cur.iri} />}
            {cur?.kind === 'datatypeProperty' && <DataPropSheet c={c} iri={cur.iri} />}
            {cur?.kind === 'individual' && <IndividualSheet c={c} iri={cur.iri} />}
            {!cur && (
              <div className="ol-empty">
                <EmptyState pose="accueil" title={empty ? t('ol.empty.none.title') : t('ol.empty.title')}
                  action={<>
                    <Button variant="primary" icon="wand-magic-sparkles" onClick={() => openAssistant({ prompt: empty ? t('ol.sugg.propose') : t('ol.sugg.review'), send: false, context: { screen: 'ontology-list', projectId: p.id } })}>{t('ol.krakie.ask')}</Button>
                    <Button icon="plus" onClick={() => setTab('class')}>{t('ol.new.class')}</Button>
                  </>}>
                  {empty ? t('ol.empty.none.body') : t('ol.empty.body')}
                </EmptyState>
                <div className="ol-sugg center">{suggestions.map(s => <button key={s} type="button" className="ol-sugg-b" onClick={() => openAssistant({ prompt: s, send: false, context: { screen: 'ontology-list', projectId: p.id } })}><Icon name="wand-magic-sparkles" />{s}</button>)}</div>
              </div>
            )}
          </div>
        </div>
        <QuickPanel pid={p.id} hint={cur?.kind === 'class' ? localName(cur.iri) : null} onApplied={setP} toast={toast} />
      </div>
    </div>
  )
}
