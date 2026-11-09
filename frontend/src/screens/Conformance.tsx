import { useState } from 'react'
import { api, labelOf, type ReasonResult } from '../api'
import { eapi } from './editor/types'
import { setReasonerFlags, clearReasonerFlags } from '../lib/reasonerFlags'
import { Button, Icon, useToast } from '../kit'
import type { ScreenProps } from '../shell/types'
import { Empty, ErrorView, Spin, useLoad } from '../ui'
import { useT } from '../i18n'
import { KrakieStatus, useResultFlash } from '../krakie/Krakie'

const PROFILE_NAMES: Record<string, string> = { DL: 'OWL 2 DL', EL: 'OWL 2 EL', QL: 'OWL 2 QL', RL: 'OWL 2 RL', RDFS: 'RDFS' }

const go = (id: string, s: string) => { location.hash = `#/projet/${encodeURIComponent(id)}/${s}` }

/** Carte « Raisonner avec HermiT » (L32) : cohérence, classes insatisfiables cliquables, inférences à ajouter au modèle, individus reclassés. */
function ReasonerCard({ p, setP }: Pick<ScreenProps, 'p' | 'setP'>) {
  const t = useT()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [res, setRes] = useState<ReasonResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [added, setAdded] = useState<Record<string, boolean>>({})
  const [undoStack, setUndoStack] = useState<string[]>([]) // ajouts de cette carte, du plus ancien au plus récent
  const canUndo = undoStack.length > 0
  const flash = useResultFlash(busy, !!res && res.status === 'ok')
  const lab = (iri: string) => { const c = p.onto.classes[iri] ?? p.onto.individuals?.[iri]; return labelOf(c as never, iri) }
  const run = async () => {
    setBusy(true); setErr(null); setAdded({}); setUndoStack([])
    try { const r = await api.reason(p.id); setRes(r); setReasonerFlags(p.id, r.unsatisfiable) }
    catch (e) { setRes(null); clearReasonerFlags(); setErr((e as Error).message) }
    finally { setBusy(false) }
  }
  const open = (iri: string) => { setReasonerFlags(p.id, res?.unsatisfiable ?? [], iri); go(p.id, 'ontologie') }
  const add = async (sub: string, sup: string) => {
    const r = await eapi.ops(p.id, [{ op: 'add_subclass', iri: sub, parent: sup }], t('rz.opLabel', { a: lab(sub), b: lab(sup) })).catch(e => ({ ok: false, errors: [{ index: 0, message: (e as Error).message }] }) as never)
    if (r.ok) { const k = sub + '>' + sup; setAdded(a => ({ ...a, [k]: true })); setUndoStack(s => [...s, k]); setP(r.project); toast(t('rz.added')) } else toast(r.errors[0]?.message ?? '')
  }
  // n'annule que le dernier ajout : les autres restent marqués « Ajouté » (avant L32-it1, tous les badges disparaissaient)
  const undo = async () => { try { const r = await eapi.undo(p.id); const k = undoStack[undoStack.length - 1]; setP(r.project); setUndoStack(s => s.slice(0, -1)); setAdded(a => { const n = { ...a }; delete n[k]; return n }); toast(t('rz.undone')) } catch (e) { toast((e as Error).message) } }
  const badge = res && res.status === 'ok' && res.consistent !== null && <span className={'badge ' + (res.consistent ? 'auto' : 'error')} data-testid="rz-badge">{res.consistent ? t('rz.consistent') : t('rz.inconsistent')}</span>
  return (
    <div className="card" data-testid="rz-card" data-tour="conf-reasoner">
      <div className="hd"><h2>{t('rz.title')}</h2>{badge}<span className="grow" />
        <Button variant="primary" size="sm" icon="gears" disabled={busy} onClick={run} data-testid="rz-run">{busy ? t('rz.running') : t('rz.run')}</Button></div>
      <div className="bd rz-stack">
        <KrakieStatus busy={busy} done={flash} label={t('rz.forge')} doneLabel={res?.consistent === false ? t('rz.done.ko') : t('rz.done.ok')} donePose={res?.consistent === false ? 'inquiete' : 'trophee'} size={48} />
        {!res && !err && !busy && <p className="muted">{t('rz.intro')}</p>}
        {err && <p role="alert" className="badge error" style={{ whiteSpace: 'normal' }} data-testid="rz-error">{err}</p>}
        {res && <>
          <p className="muted">{res.version} · {t('rz.took', { ms: res.duration_ms })}</p>
          {res.warnings.map((w, i) => <p key={i} className="badge review" style={{ whiteSpace: 'normal' }}><Icon name="triangle-exclamation" /> {w}</p>)}
          {res.status === 'error' && <p className="badge error" style={{ whiteSpace: 'normal' }}>{res.error}</p>}
          {res.consistent === false && res.explanation && <div data-testid="rz-explain"><h3>{t('rz.why')}</h3><p className="muted">{res.explanation.note}</p>
            <ul>{res.explanation.items.map((it, i) => <li key={i}>{it.message}</li>)}</ul></div>}
          {res.status === 'ok' && res.consistent && <>
            <div data-testid="rz-unsat"><h3>{t('rz.unsat')} ({res.unsatisfiable.length})</h3>
              {res.unsatisfiable.length === 0 ? <p className="muted">{t('rz.unsat.none')}</p> :
                <><p className="muted">{t('rz.unsat.hint')}</p><div className="row" style={{ flexWrap: 'wrap' }}>{res.unsatisfiable.map(c => <button key={c} className="btn sm danger" data-testid="rz-unsat-link" title={c} onClick={() => open(c)}>{lab(c)}</button>)}</div></>}</div>
            <div data-testid="rz-infer"><h3>{t('rz.infer')}</h3>
              {res.hierarchy.new_subclass.length + res.hierarchy.new_equivalent.length === 0 ? <p className="muted">{t('rz.infer.none')}</p> : <>
                <ul className="plain">{res.hierarchy.new_subclass.map(x => { const k = x.sub + '>' + x.sup; return <li key={k} className="row"><span>{t('rz.subclass', { a: lab(x.sub), b: lab(x.sup) })}</span><span className="grow" />
                  {added[k] ? <span className="badge auto">{t('rz.addedBadge')}</span> : <Button size="sm" icon="plus" data-testid="rz-add" onClick={() => add(x.sub, x.sup)}>{t('rz.add')}</Button>}</li> })}
                {res.hierarchy.new_equivalent.map((g, i) => <li key={'e' + i} className="row"><span>{t('rz.equiv', { list: g.map(lab).join(' ≡ ') })}</span><span className="grow" /><span className="muted">{t('rz.equiv.noop')}</span></li>)}</ul>
                {canUndo && <Button size="sm" variant="ghost" icon="rotate-left" onClick={undo}>{t('rz.undo')}</Button>}</>}</div>
            <div data-testid="rz-ind"><h3>{t('rz.ind')} ({res.reclassified.length})</h3>
              {res.reclassified.length === 0 ? <p className="muted">{t('rz.ind.none')}</p> :
                <ul className="plain">{res.reclassified.map(r => <li key={r.individual}>{t('rz.ind.row', { i: lab(r.individual), types: r.inferred.map(lab).join(', ') })}</li>)}</ul>}</div>
          </>}
          <p className="muted">{t('rz.caveat')}</p>
        </>}
      </div>
    </div>
  )
}

export function Conformance({ p, setP }: ScreenProps) {
  const t = useT()
  const { data, error, loading, reload } = useLoad(() => api.conformance(p.id), [p.id, p.updated_at])
  const [lv, setLv] = useState<Record<string, boolean>>({ error: true, warning: true, info: true })
  const [q, setQ] = useState('')
  const issues = (data?.issues ?? []).filter(i => lv[i.level] && (!q || (i.code + i.message + (i.subject ?? '')).toLowerCase().includes(q.toLowerCase())))
  const n = (l: string) => data?.issues.filter(i => i.level === l).length ?? 0
  const ref = (s?: string | null) => !s ? null : /^https?:/.test(s) ? <a href={s} target="_blank" rel="noreferrer">{s.replace(/^https?:\/\/(www\.)?/, '')}</a> : <span>{s}</span>
  return (
    <div className="page">
      <div className="page-head"><h1>{t('cf.title')}</h1><span className="sub">{t('cf.sub')}</span><span className="grow" /><button className="btn" onClick={reload}>{t('cf.recheck')}</button></div>
      {loading && <Spin />}<ErrorView error={error} what={t('cf.what')} />
      {data && <>
        <div className="card" data-tour="conf-profiles"><div className="hd"><h2>{t('conf.profiles')}</h2></div><div className="bd row">
          {Object.entries(data.profiles).map(([k, ok]) => <span key={k} className={'pill ' + (ok ? 'on' : 'off')} title={ok ? t('cf.profile.ok') : t('cf.profile.ko')}>{PROFILE_NAMES[k] ?? k}</span>)}
          {Object.keys(data.profiles).length === 0 && <span className="muted">{t('cf.noprofile')}</span>}</div></div>
        <ReasonerCard p={p} setP={setP} />
        <div className="row">
          {(['error', 'warning', 'info'] as const).map(l => <label key={l} className="row"><input type="checkbox" checked={lv[l]} onChange={e => setLv({ ...lv, [l]: e.target.checked })} /><span className={'badge ' + l}>{t('cf.level.' + l)} {n(l)}</span></label>)}
          <input type="text" placeholder={t('cf.filter')} value={q} onChange={e => setQ(e.target.value)} style={{ width: 260 }} />
        </div>
        {data.issues.length === 0 ? <Empty title={t('cf.empty.t')}>{t('cf.empty.b')}</Empty> :
          <div className="tscroll" style={{ maxHeight: 'none' }}><table className="t"><thead><tr><th>{t('cf.col.level')}</th><th>{t('cf.col.code')}</th><th>{t('cf.col.message')}</th><th>{t('cf.col.subject')}</th><th>{t('cf.col.spec')}</th></tr></thead><tbody>
            {issues.map((i, k) => <tr key={k}><td><span className={'badge ' + i.level}>{t('cf.level.' + i.level)}</span></td><td className="mono">{i.code}</td><td>{i.message}</td><td className="mono" title={i.subject ?? ''}>{i.subject ? i.subject.split(/[#/]/).pop() : ''}</td><td>{ref(i.spec_ref)}</td></tr>)}
          </tbody></table></div>}
      </>}
    </div>
  )
}
