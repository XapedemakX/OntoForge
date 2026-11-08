import { useState } from 'react'
import { curie } from '../../api'
import { Button, Icon, IconButton } from '../../kit'
import { useI18n } from '../../i18n'
import { acceptAll, acceptIds, acceptItem, rejectAll, rejectItem, type ProposalState } from '../../lib/proposal'
import './doc.css'

type Item = ProposalState['items'][number]
const GROUPS: { id: 'class' | 'rel' | 'data'; icon: string; match: (i: Item) => boolean }[] = [
  { id: 'class', icon: 'circle-nodes', match: i => i.type === 'class' || i.type === 'subClassOf' },
  { id: 'rel', icon: 'right-long', match: i => i.type === 'objectProperty' },
  { id: 'data', icon: 'tag', match: i => i.type === 'datatypeProperty' },
]
const FILTER_FROM = 8

/** Liste des éléments proposés, groupés par type (Classes, Relations, Propriétés de données) avec compteurs, filtre texte, « Tout accepter » par groupe.
 *  Une ligne compacte par élément ; un clic sur le nom déplie l'extrait source. Un élément issu d'un document porte le badge « à confirmer ».
 *  Utilisée par l'écran Assistant et par le panneau Krakie. */
export function ProposalCards({ mine, prefixes, picked, onEditor, compact }: {
  mine: ProposalState; prefixes: Record<string, string>; picked?: string | null; onEditor: () => void; compact?: boolean
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState<Record<string, boolean>>({})
  const [folded, setFolded] = useState<Record<string, boolean>>({})
  const [q, setQ] = useState('')
  const fromDoc = mine.items.some(i => i.provenance)
  const toggle = (id: string) => setOpen(o => ({ ...o, [id]: !o[id] }))
  const needle = q.trim().toLowerCase()
  const visible = needle ? mine.items.filter(i => [i.label, i.detail, i.provenance?.excerpt].some(x => x?.toLowerCase().includes(needle))) : mine.items
  const row = (it: Item) => {
    const warn = (it.lint ?? []).filter(x => x.code !== 'W07')
    const isOpen = !!open[it.id]
    const title = it.type === 'subClassOf' ? `${curie(it.source!, prefixes)} ⊂ ${curie(it.target!, prefixes)}` : it.label
    const sub = `${it.type === 'subClassOf' || it.type === 'class' ? '' : t('asst.type.' + it.type) + ' · '}${it.detail ?? ''}${it.type === 'objectProperty' && it.source ? `${curie(it.source, prefixes)} → ${it.target ? curie(it.target, prefixes) : '?'}` : ''}${it.type === 'datatypeProperty' && it.source ? ` · ${curie(it.source, prefixes)}` : ''}`
    const text = (
      <span className="as-item-t">
        <b>{title}</b>
        {sub && <span className="muted">{sub}</span>}
      </span>
    )
    return (
      <li key={it.id} id={'as-' + it.id} className={'as-item pc-item ' + it.kind + (picked === it.id ? ' picked' : '')}>
        <div className="pc-row">
          {it.provenance
            ? <button className="pc-toggle" aria-expanded={isOpen} aria-controls={'src-' + it.id} title={t('doc.source')} onClick={() => toggle(it.id)}>
              <Icon name={isOpen ? 'chevron-down' : 'chevron-right'} />{text}
              {warn.length > 0 && <span className="pc-warn" title={warn.map(w => w.message).join('\n')}><Icon name="triangle-exclamation" />{warn.length}</span>}
            </button>
            : <><Icon name={GROUPS.find(g => g.match(it))?.icon ?? 'tag'} />{text}</>}
          {it.provenance
            ? <span className="pc-tag confirm" title={t('doc.confirm')} aria-label={t('doc.confirm')}><Icon name="hourglass-half" /></span>
            : <span className={'as-tag ' + it.kind}><Icon name={it.kind === 'add' ? 'plus' : 'pen'} />{t(it.kind === 'add' ? 'asst.add' : 'asst.modify')}</span>}
          <IconButton icon="check" label={t('asst.accept') + ' ' + it.label} className="ok" disabled={mine.busy} onClick={() => void acceptItem(it.id)} />
          <IconButton icon="xmark" label={t('asst.reject') + ' ' + it.label} className="ko" disabled={mine.busy} onClick={() => rejectItem(it.id)} />
        </div>
        {it.provenance && isOpen && (
          <div id={'src-' + it.id} className="pc-quote">
            <blockquote lang={mine.doc?.lang || undefined}>{it.provenance.excerpt}</blockquote>
            <span className="muted">{t('doc.source.in', { document: it.provenance.document, page: it.provenance.page })}</span>
            {warn.map((w, i) => <p key={i} className="pc-lintline"><b>{w.code}</b> {w.message}</p>)}
          </div>
        )}
      </li>
    )
  }
  return (
    <div className={'pc' + (compact ? ' compact' : '')}>
      {mine.doc && !compact && <LintSummary lint={mine.doc.lint} skipped={mine.doc.skipped} />}
      {mine.items.length >= FILTER_FROM && (
        <label className="pc-filter"><Icon name="magnifying-glass" />
          <input type="search" value={q} placeholder={t('doc.filter.ph')} aria-label={t('doc.filter')} onChange={e => setQ(e.target.value)} />
        </label>
      )}
      {GROUPS.map(g => {
        const all = mine.items.filter(g.match)
        const list = visible.filter(g.match)
        if (!all.length || (needle && !list.length)) return null
        const name = t('doc.group.' + g.id)
        const isFolded = !!folded[g.id] && !needle
        return (
          <section key={g.id} className="pc-group" aria-label={name}>
            <header className="pc-gh">
              <button className="pc-gt" aria-expanded={!isFolded} aria-label={t('doc.group.toggle', { group: name })} onClick={() => setFolded(f => ({ ...f, [g.id]: !f[g.id] }))}>
                <Icon name={isFolded ? 'chevron-right' : 'chevron-down'} /><Icon name={g.icon} /><b>{name}</b>
                <span className="pc-count">{needle ? `${list.length}/${all.length}` : all.length}</span>
              </button>
              <Button size="sm" icon="check-double" aria-label={t('doc.group.acceptAll.l', { group: name, n: list.length })} disabled={mine.busy || !list.length} onClick={() => void acceptIds(list.map(i => i.id))}>{t('doc.group.acceptAll')}</Button>
            </header>
            {!isFolded && <ul className="as-items">{list.map(row)}</ul>}
          </section>
        )
      })}
      {needle && visible.length === 0 && <p className="muted pc-none">{t('doc.filter.none')}</p>}
      <div className="as-foot">
        <Button variant="primary" icon="check-double" disabled={mine.busy} onClick={() => void acceptAll()}>{t('asst.acceptAll')}</Button>
        <Button icon="ban" disabled={mine.busy} onClick={rejectAll}>{t('asst.rejectAll')}</Button>
        <span className="grow" />
        {!compact && <Button icon="diagram-project" onClick={onEditor}>{t('asst.toEditor')}</Button>}
      </div>
      {fromDoc && <p className="muted pc-hint">{t('doc.hint')}</p>}
    </div>
  )
}

/** Résumé du lint W3C du brouillon. W07 (libellé absent dans l'autre langue) est une information repliable, pas un avertissement :
 *  l'orange est réservé aux vrais constats. */
export function LintSummary({ lint, skipped }: { lint: { code: string; message: string; level: string }[]; skipped: number }) {
  const { t } = useI18n()
  const info = lint.filter(i => i.code === 'W07')
  const real = lint.filter(i => i.code !== 'W07')
  const groups = new Map<string, { n: number; sample: string }>()
  for (const i of real) { const g = groups.get(i.code); if (g) g.n++; else groups.set(i.code, { n: 1, sample: i.message }) }
  return (
    <div className="pc-lint">
      {real.length === 0
        ? <p className="pc-lint-ok"><Icon name="circle-check" />{t('doc.lint.ok')}</p>
        : <details>
          <summary><Icon name="triangle-exclamation" />{t('doc.lint.title', { n: real.length })}</summary>
          <ul>{[...groups].map(([code, g]) => <li key={code}><b>{code}</b> ×{g.n} <span className="muted">{g.sample}</span></li>)}</ul>
        </details>}
      {info.length > 0 && (
        <details className="pc-info">
          <summary><Icon name="circle-info" />{t('doc.lint.info', { n: info.length })}</summary>
          <p className="muted">{t('doc.lint.info.d')}</p>
          <ul>{info.map((i, k) => <li key={k} className="muted">{i.message}</li>)}</ul>
        </details>
      )}
      {skipped > 0 && <p className="muted pc-skip"><Icon name="circle-info" />{t('doc.skipped', { n: skipped })}</p>}
    </div>
  )
}
