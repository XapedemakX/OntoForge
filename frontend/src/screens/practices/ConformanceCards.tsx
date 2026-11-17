// Écran Conformité (L49) : complétude des fiches, en-tête de l'ontologie (métadonnées éditables), versions publiées (diff SemVer).
import { useState } from 'react'
import { api, labelOf, type Completeness, type Project, type ReleasePreview } from '../../api'
import { Button, useToast } from '../../kit'
import { useT } from '../../i18n'
import { ErrorView, Spin, useLoad } from '../../ui'
import { eapi, type Op } from '../editor/types'
import { DCT, P } from './card'
import { ScoreBadge } from './EntityCard'
import './practices.css'

const go = (id: string, s: string) => { location.hash = `#/projet/${encodeURIComponent(id)}/${s}` }

export function CompletenessCard({ p, c }: { p: Project; c: Completeness }) {
  const t = useT()
  const worst = Object.values(c.entities).filter(e => e.score < 100).sort((a, b) => a.score - b.score).slice(0, 8)
  const lab = (iri: string) => labelOf(p.onto.classes[iri] || p.onto.object_properties[iri] || p.onto.datatype_properties[iri], iri)
  return (
    <div className="card" data-testid="bp-completeness"><div className="hd"><h2>{t('bp.completeness')}</h2><span className="grow" /><ScoreBadge score={c.score} title={t('bp.score.onto')} /></div>
      <div className="bd">
        <p className="muted">{t('bp.completeness.sub', { n: Object.keys(c.entities).length, h: c.header.score })}</p>
        <div className="bp-crit">{Object.entries(c.criteria).map(([k, v]) => <span key={k} className={'pill ' + (v.ok === v.of ? 'on' : 'off')}>{t('bp.crit.' + k)} {v.ok}/{v.of}</span>)}</div>
        {c.deprecated.length > 0 && <p data-testid="bp-deprecated-list"><span className="badge lost">{t('ed.deprecated')}</span> {c.deprecated.map(lab).join(', ')}</p>}
        {worst.length > 0 && <><h3>{t('bp.worst')}</h3><ul className="plain">{worst.map(e => <li key={e.iri} className="row">
          <ScoreBadge score={e.score} /><button type="button" className="lnk" onClick={() => go(p.id, 'ontologie')}>{lab(e.iri)}</button>
          <span className="muted">{e.missing.map(m => t('bp.crit.' + m)).join(', ')}</span></li>)}</ul></>}
      </div></div>
  )
}

function Line({ label, value, onCommit, ro, testid, ph }: { label: string; value: string; onCommit: (v: string) => void; ro: boolean; testid: string; ph?: string }) {
  const [v, setV] = useState(value)
  const [last, setLast] = useState(value)
  if (value !== last) { setLast(value); setV(value) }
  return <label className="bp-f"><span>{label}</span><input type="text" aria-label={label} data-testid={testid} disabled={ro} placeholder={ph} value={v}
    onChange={e => setV(e.target.value)} onBlur={() => v !== value && onCommit(v)} onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} /></label>
}

export function HeaderCard({ p, setP, readOnly }: { p: Project; setP: (p: Project) => void; readOnly: boolean }) {
  const t = useT()
  const toast = useToast()
  const { data, error, loading } = useLoad(() => api.metadata(p.id), [p.id, p.updated_at])
  if (loading && !data) return <Spin />
  if (error || !data) return <ErrorView error={error} what={t('bp.header')} />
  const h = data.header
  const iri = h.iri
  const list = (s: string) => s.split(/;/).map(x => x.trim()).filter(Boolean)
  const run = async (ops: Op[]) => {
    try { const r = await eapi.ops(p.id, ops, t('bp.hist.header')); if (r.ok) setP(r.project); else toast(r.errors.map(e => e.message).join(' ; ')) } catch (e) { toast((e as Error).message) }
  }
  const set = (prop: string, values: string[], lang?: string) => run([{ op: 'set_annotations', iri, property: prop, values, ...(lang !== undefined ? { lang } : {}) }])
  const day = (s: string | null) => (s ?? '').slice(0, 10)
  return (
    <div className="card" data-testid="bp-header"><div className="hd"><h2>{t('bp.header')}</h2><span className="grow" /><ScoreBadge score={data.card.score} title={t('bp.score.header')} /></div>
      <div className="bd">
        {data.card.missing.length > 0 && <p className="muted">{t('bp.missing')} {data.card.missing.map(k => t('bp.h.' + k)).join(', ')}</p>}
        <div className="bp-grid">
          {['fr', 'en'].map(l => <Line key={'t' + l} ro={readOnly} testid={'bp-h-title-' + l} label={`${t('bp.h.title')} (${l})`} value={h.title[l] ?? ''} onCommit={v => set(DCT + 'title', v ? [v] : [], l)} />)}
          {['fr', 'en'].map(l => <Line key={'d' + l} ro={readOnly} testid={'bp-h-description-' + l} label={`${t('bp.h.description')} (${l})`} value={h.description[l] ?? ''} onCommit={v => set(DCT + 'description', v ? [v] : [], l)} />)}
          <Line ro={readOnly} testid="bp-h-version" label={t('bp.h.version_info')} value={h.version_info ?? ''} ph="1.0.0" onCommit={v => set(P.versionInfo, v ? [v] : [])} />
          <Line ro={readOnly} testid="bp-h-version-iri" label={t('bp.h.version_iri')} value={h.version_iri ?? ''} ph={iri.replace(/[#/]$/, '') + '/1.0.0'} onCommit={v => run([{ op: 'set_version_iri', version_iri: v || null }])} />
          <Line ro={readOnly} testid="bp-h-created" label={t('bp.h.created')} value={day(h.created)} ph="2026-11-17" onCommit={v => set(DCT + 'created', v ? [v] : [])} />
          <Line ro={readOnly} testid="bp-h-modified" label={t('bp.h.modified')} value={day(h.modified)} ph="2026-11-17" onCommit={v => set(DCT + 'modified', v ? [v] : [])} />
          <Line ro={readOnly} testid="bp-h-creators" label={t('bp.h.creators')} value={h.creators.join('; ')} ph={t('bp.list.ph')} onCommit={v => set(DCT + 'creator', list(v))} />
          <Line ro={readOnly} testid="bp-h-contributors" label={t('bp.h.contributors')} value={h.contributors.join('; ')} ph={t('bp.list.ph')} onCommit={v => set(DCT + 'contributor', list(v))} />
          <Line ro={readOnly} testid="bp-h-references" label={t('bp.h.references')} value={h.references.join('; ')} ph="http://www.w3.org/2004/02/skos/core" onCommit={v => set(DCT + 'references', list(v))} />
          <Line ro={readOnly} testid="bp-h-subjects" label={t('bp.h.subjects')} value={h.subjects.map(s => s.value).join('; ')} ph={t('bp.list.ph')} onCommit={v => set(DCT + 'subject', list(v))} />
          <Line ro={readOnly} testid="bp-h-sources" label={t('bp.h.sources')} value={h.sources.join('; ')} ph={t('bp.list.ph')} onCommit={v => set(DCT + 'source', list(v))} />
          <Line ro={readOnly} testid="bp-h-license" label={t('bp.h.license')} value={h.license ?? ''} ph="https://creativecommons.org/licenses/by/4.0/" onCommit={v => set(DCT + 'license', v ? [v] : [])} />
        </div>
        <p className="muted">{t('bp.header.hint')}</p>
      </div></div>
  )
}

export function ReleasesCard({ p, setP, readOnly }: { p: Project; setP: (p: Project) => void; readOnly: boolean }) {
  const t = useT()
  const toast = useToast()
  const pv = useLoad(() => api.releasePreview(p.id), [p.id, p.updated_at])
  const hist = useLoad(() => api.releases(p.id), [p.id, p.updated_at])
  const [version, setVersion] = useState('')
  const [busy, setBusy] = useState(false)
  const [shown, setShown] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const d: ReleasePreview | null = pv.data
  const save = async () => {
    setBusy(true)
    try { const r = await api.createRelease(p.id, { version: version.trim() || undefined }); setP(r.project); setVersion(''); toast(t('bp.rel.done', { v: r.release.version })) }
    catch (e) { toast((e as Error).message) } finally { setBusy(false) }
  }
  const open = async (v: string) => {
    if (shown === v) { setShown(null); return }
    try { const r = await api.release(p.id, v); setShown(v); setNote(r.note ?? '') } catch (e) { toast((e as Error).message) }
  }
  return (
    <div className="card" data-testid="bp-releases"><div className="hd"><h2>{t('bp.rel.title')}</h2></div>
      <div className="bd">
        {pv.loading && !d && <Spin />}<ErrorView error={pv.error} what={t('bp.rel.title')} />
        {d && <>
          <p data-testid="bp-rel-summary">{d.previous === null ? t('bp.rel.first', { v: d.proposed }) : d.unchanged || !d.level ? t('bp.rel.unchanged', { prev: d.previous }) : t('bp.rel.summary', { prev: d.previous, lvl: t('bp.lvl.' + d.level), v: d.proposed })}</p>
          {d.previous !== null && <div className="bp-crit">{(['major', 'minor', 'patch'] as const).map(l => <span key={l} className={'badge ' + (l === 'major' ? 'lost' : l === 'minor' ? 'review' : 'auto')}>{t('bp.lvl.' + l)} {d.counts[l]}</span>)}</div>}
          <details><summary>{t('bp.rel.note')}</summary><pre className="bp-note" data-testid="bp-rel-note">{d.note}</pre></details>
          {!readOnly && <div className="row">
            <input type="text" aria-label={t('bp.rel.version')} data-testid="bp-rel-version" placeholder={d.proposed} value={version} onChange={e => setVersion(e.target.value)} style={{ width: 140 }} />
            <Button variant="primary" icon="tag" disabled={busy || (!!d.unchanged && !version.trim())} data-testid="bp-rel-save" onClick={save}>{t('bp.rel.save')}</Button>
            <span className="muted">{t('bp.rel.hint')}</span></div>}
        </>}
        <h3>{t('bp.rel.history')}</h3>
        {hist.data && hist.data.releases.length === 0 && <p className="muted">{t('bp.rel.none')}</p>}
        {hist.data && hist.data.releases.length > 0 && <p className="muted">{t('bp.rel.limit')}</p>}
        <ul className="plain" data-testid="bp-rel-history">{hist.data?.releases.map(r => <li key={r.version}>
          <button type="button" className="lnk" onClick={() => open(r.version)}><b>{r.version}</b></button> <span className="muted">{r.at.slice(0, 10)}{r.by ? ' · ' + r.by : ''}{r.previous && r.level ? ' · ' + t('bp.lvl.' + r.level) : ''}{r.downgraded ? ' · ' + t('bp.rel.downgraded') : ''}</span>
          {shown === r.version && note !== null && <pre className="bp-note">{note}</pre>}</li>)}</ul>
      </div></div>
  )
}
