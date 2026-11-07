import { useEffect, useState } from 'react'
import { tr } from '../../i18n'
import { curie, localName } from '../../api'
import { Button, Icon, IconButton } from '../../kit'
import { IconPicker } from '../editor/IconPicker'
import { toLocalName } from '../editor/layout'
import type { SheetCtx } from './ctx'
import type { Kind } from './model'

const KIND_ICON: Record<Kind, string> = { class: 'circle-nodes', objectProperty: 'arrow-right-long', datatypeProperty: 'font', individual: 'cube' }

/** En-tête de fiche : icône, libellé, IRI compacte copiable/renommable, badges, Krakie, suppression. */
export function Header({ c, kind, iri, suggestions }: { c: SheetCtx; kind: Kind; iri: string; suggestions: { text: string; send: boolean }[] }) {
  const { t, onto, lang } = c
  const pf = onto.meta.prefixes || {}
  const [ren, setRen] = useState<string | null>(null)
  const [icoOpen, setIcoOpen] = useState(false)
  const [sure, setSure] = useState(false)
  useEffect(() => { setRen(null); setIcoOpen(false); setSure(false) }, [iri])
  const ent = onto.classes[iri] || onto.object_properties[iri] || onto.datatype_properties[iri] || onto.individuals[iri]
  const label = c.lbl(iri)
  const copy = async () => {
    try { await navigator.clipboard.writeText(iri); c.toast(t('ol.iri.copied')) } catch { c.toast(iri) }
  }
  const rename = async () => {
    if (ren === null) return
    const base = iri.slice(0, iri.length - localName(iri).length)
    const nn = toLocalName(ren)
    if (!nn || nn === localName(iri)) { setRen(null); return }
    if (await c.apply([{ op: 'rename_entity', iri, new_iri: base + nn }], tr('hist.renommer'))) { c.select(base + nn, kind); setRen(null) }
  }
  const abstract = kind === 'class' && c.abstract.has(iri)
  const icon = (kind === 'class' && c.icons[iri]) || KIND_ICON[kind]
  return (
    <header className="ol-head">
      <div className="ol-head-main">
        {kind === 'class'
          ? <button type="button" className="ol-ico edit" onClick={() => setIcoOpen(o => !o)} title={t('ol.icon.edit')} aria-label={t('ol.icon.edit')}><Icon name={icon} /><span className="pen"><Icon name="pen" /></span></button>
          : <span className="ol-ico" aria-hidden="true"><Icon name={icon} /></span>}
        <div className="ol-head-t">
          <h2>{label}</h2>
          {ren === null ? (
            <div className="ol-iri">
              <code title={iri}>{curie(iri, pf)}</code>
              <IconButton icon="copy" label={t('ol.iri.copy')} onClick={copy} />
              <IconButton icon="pen" label={t('ol.iri.rename')} onClick={() => setRen(localName(iri))} />
              {abstract && <span className="ol-badge" title={t('ol.abstract.hint')}>{t('ol.abstract')}</span>}
              {ent?.deprecated && <span className="ol-badge warn">{t('ol.deprecated')}</span>}
            </div>
          ) : (
            <div className="ol-iri">
              <input type="text" autoFocus value={ren} aria-label={t('ol.iri.rename')} onChange={e => setRen(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') rename(); if (e.key === 'Escape') setRen(null) }} />
              <Button size="sm" variant="primary" onClick={rename}>{t('ol.ok')}</Button>
              <Button size="sm" variant="ghost" onClick={() => setRen(null)}>{t('ol.cancel')}</Button>
              <small className="muted">{t('ol.iri.hint')}</small>
            </div>
          )}
        </div>
        <div className="ol-head-a">
          <Button variant="primary" icon="wand-magic-sparkles" onClick={() => c.ask('', false)}>{t('ol.krakie.ask')}</Button>
          {sure
            ? <Button variant="danger" icon="trash" onBlur={() => setSure(false)} onClick={async () => { if (await c.apply([{ op: 'delete_entity', iri }], tr('hist.supprimer'))) c.select('', kind) }}>{t('ol.delete.confirm')}</Button>
            : <IconButton icon="trash" label={t('ol.delete')} onClick={() => setSure(true)} onBlur={() => setSure(false)} />}
        </div>
        {icoOpen && <IconPicker value={c.icons[iri] ?? null} onClose={() => setIcoOpen(false)} onPick={id => { setIcoOpen(false); c.apply([{ op: 'set_icon', iri, icon: id }], tr('hist.icone')) }} />}
      </div>
      <div className="ol-sugg" aria-label={t('ol.krakie.sugg')}>
        <span className="muted">{t('ol.krakie.sugg')}</span>
        {suggestions.map(s => <button key={s.text} type="button" className="ol-sugg-b" onClick={() => c.ask(s.text, s.send)}><Icon name="wand-magic-sparkles" />{s.text}</button>)}
      </div>
    </header>
  )
}
