import { useEffect, useState } from 'react'
import { renderSafeMarkdown } from '../lib/safeMarkdown'
import { api, curie, type DecisionNote, type Finding, type FindingSeverity } from '../api'
import type { ScreenProps } from '../shell/types'
import { Button, Card, Icon } from '../kit'
import { useT } from '../i18n'
import { KrakieStatus, useResultFlash } from '../krakie/Krakie'
import { Empty, ErrorView, useLoad, useToast } from '../ui'
import { useMobile } from '../shell/sidePref'
import { Deck } from './analysis/Deck'


export function Analysis({ p, target }: ScreenProps) {
  const toast = useToast()
  const t = useT()
  const mob = useMobile()
  const [confirm, setConfirm] = useState(false)
  const [onlyReview, setOnlyReview] = useState(true)
  const { data: pg, error, loading, setData, reload } = useLoad(() => api.analyze(p.id, target), [p.id, target, p.updated_at])
  const [err, setErr] = useState<unknown>(null)
  const [onlyPending, setOnlyPending] = useState(false)
  const [q, setQ] = useState('')
  const [openAuto, setOpenAuto] = useState(false)
  const [busy, setBusy] = useState(false)
  const pf = p.onto.meta.prefixes
  const done = useResultFlash(loading, !!pg && !error)

  const decide = async (fid: string, opt: string | null, reason?: string) => {
    setErr(null)
    try { setData(await api.decide(p.id, target, { [fid]: opt }, reason !== undefined ? { reason } : undefined)) } catch (e) { setErr(e) }
  }
  const decideMany = async (d: Record<string, string | null>, reason?: string, via: 'rule' | 'manual' = 'rule') => {
    setErr(null); setBusy(true)
    try { setData(await api.decide(p.id, target, d, reason !== undefined ? { reason, via } : undefined)) } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const branch = async (b: { root: string; rule?: string; option?: string; reason?: string; overwrite?: boolean }) => {   // L47 : une décision par racine de hiérarchie
    setErr(null); setBusy(true)
    try { const r = await api.decideBranch(p.id, target, b); setData(r.model); toast(t('an.branch.done', { n: r.applied.length, s: r.skipped.length })) } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const notes = pg?.decision_notes ?? {}
  const tn = target === 'curiosity' ? 'Curiosity' : 'Neo4j'
  const acceptAll = async () => {
    setBusy(true); setErr(null)
    try {
      if (onlyReview && pg) {
        // les perdus ne sont jamais acceptés en bloc dans ce mode : seules les recommandations des « à arbitrer »
        const d = Object.fromEntries(pg.findings.filter(f => f.severity === 'review' && !f.chosen && f.recommended).map(f => [f.id, f.recommended!]))
        setData(await api.decide(p.id, target, d)); toast(t('an.accepted', { n: Object.keys(d).length }))
      } else { setData(await api.acceptRecommended(p.id, target, true)); toast(t('an.accepted', { n: sum?.pending ?? 0 })) }
      setConfirm(false)
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  const sum = pg ? pg.findings.reduce((a, f) => { if (f.severity === 'info') return a; a[f.severity]++; if (f.severity !== 'auto') a[f.chosen ? 'decided' : 'pending']++; return a }, { auto: 0, review: 0, lost: 0, decided: 0, pending: 0 }) : null
  const pend = (sv: FindingSeverity) => pg?.findings.filter(f => f.severity === sv && !f.chosen && f.recommended).length ?? 0
  const reclass = pg?.findings.filter(f => f.auto_reason).length ?? 0
  const total = pg?.findings.length || 1
  const todo = sum ? sum.review + sum.lost : 0
  const match = (f: Finding) => (!onlyPending || ((f.severity === 'review' || f.severity === 'lost') && !f.chosen)) && (!q || (f.title + f.rule + f.subject + f.detail).toLowerCase().includes(q.toLowerCase()))
  const group = (s: FindingSeverity) => (pg?.findings ?? []).filter(f => f.severity === s && match(f)).sort((a, b) => Number(!!a.chosen) - Number(!!b.chosen))

  if (mob) return (   // L44 : une carte par point à arbitrer
    <div className="page deck-page">
      <ErrorView error={error} what={t('an.what')} /><ErrorView error={err} what={t('an.what.decide')} />
      {loading && !pg && <div className="muted">{t('common.loading')}</div>}
      {pg && sum && <Deck pid={p.id} target={target} findings={pg.findings} pf={pf} summary={sum} decide={decide} decideMany={decideMany} busy={busy} />}
    </div>)
  return (
    <div className="page">
      <div className="page-head">
        <h1>{t('an.title')}</h1><span className="badge">{t('an.badge', { target: tn })}</span>
        <span className="grow" />
        <Button variant="ghost" icon="rotate" onClick={reload}>{t('an.rerun')}</Button>
        <Button disabled={busy || !sum || sum.pending === 0} onClick={() => setConfirm(c => !c)} aria-expanded={confirm}>{t('an.accept')}</Button>
      </div>
      {confirm && sum && <Card tone="review" title={t('an.confirm.t')}>
        <ul className="col" style={{ margin: '0 0 10px', paddingLeft: 18 }}>
          <li>{t('an.confirm.auto', { n: sum.auto })}</li>
          <li>{t('an.confirm.review', { n: pend('review'), target: tn })}</li>
          <li>{t('an.confirm.lost', { n: sum.lost - (pg?.findings.filter(f => f.severity === 'lost' && f.chosen).length ?? 0), mode: onlyReview ? t('an.confirm.lost.skip') : t('an.confirm.lost.take') })}</li>
        </ul>
        <label className="row" style={{ marginBottom: 10 }}><input type="checkbox" checked={onlyReview} onChange={e => setOnlyReview(e.target.checked)} />{t('an.confirm.only')}</label>
        <div className="row"><Button variant="primary" icon="check" disabled={busy} onClick={acceptAll}>{t('an.confirm.go', { n: onlyReview ? pend('review') : pend('review') + pend('lost') })}</Button>
          <Button variant="ghost" onClick={() => setConfirm(false)}>{t('an.confirm.cancel')}</Button></div>
      </Card>}
      <KrakieStatus busy={loading} done={done} label={t('krakie.forge.analysis')} doneLabel={t('krakie.done.analysis')} />
      <ErrorView error={error} what={t('an.what')} /><ErrorView error={err} what={t('an.what.decide')} />
      {pg && sum && <>
        <div className="card triage" data-tour="an-counters">
          <div className="kpis">
            <div className="kpi auto"><b>{sum.auto}</b><span>{t('an.kpi.auto')}</span>{reclass > 0 && <small className="muted" data-testid="kpi-reclass"> {t('an.kpi.reclass', { n: reclass })}</small>}</div>
            <div className="kpi review"><b>{sum.review}</b><span>{t('an.kpi.review')}</span></div>
            <div className="kpi lost"><b>{sum.lost}</b><span>{t('an.kpi.lost')}</span></div>
            <div className="kpi"><b>{sum.decided}<span style={{ fontSize: 13 }}> / {todo}</span></b><span>{t('an.kpi.decided')}</span></div>
            <div className="kpi"><b>{sum.pending}</b><span>restants</span></div>
          </div>
          <div className="bar" aria-label={t('an.bar.aria')}><div className="a" style={{ width: `${sum.auto / total * 100}%` }} /><div className="r" style={{ width: `${sum.review / total * 100}%` }} /><div className="l" style={{ width: `${sum.lost / total * 100}%` }} /></div>
          <div className="bar prog" aria-label="Progression de l'arbitrage"><div className="d" style={{ width: todo ? `${sum.decided / todo * 100}%` : '100%' }} /></div>
        </div>
        <div className="row sticky-bar">
          <label className="row"><input type="checkbox" checked={onlyPending} onChange={e => setOnlyPending(e.target.checked)} />{t('an.onlyPending')}</label>
          <input type="text" placeholder={t('an.filter')} value={q} onChange={e => setQ(e.target.value)} style={{ width: 260 }} />
        </div>
        {pg.findings.length === 0 && <Empty title={t('an.empty.t')}>{t('an.empty.b')}</Empty>}
        {(['lost', 'review'] as const).some(s => byRoot(group(s)).length > 0) && <div className="muted" data-testid="branch-hint">{t('an.branch.hint')}</div>}
        {(['lost', 'review'] as const).map(s => { const g = group(s); return g.length > 0 && <section key={s} className="col" data-tour={'an-group-' + s}>
          <div className="row"><span className={'badge ' + s}>{t('an.sev.' + s)}</span><span className="muted">{t('an.count', { n: g.length, r: byRule(g).length })}</span></div>
          {byRoot(g).map(([root, fs]) => <BranchGroup key={s + 'b' + root} root={root} fs={fs} pf={pf} projectId={p.id} target={target} notes={notes} decide={decide} decideMany={decideMany} branch={branch} busy={busy} />)}
          {byRule(g.filter(f => !f.root)).map(([rule, fs]) => <RuleGroup key={s + rule} rule={rule} fs={fs} pf={pf} projectId={p.id} target={target} notes={notes} decide={decide} decideMany={decideMany} busy={busy} />)}</section> })}
        {group('info').length > 0 && <section className="col"><div className="group-h"><span className="sev info"><Icon name="circle-info" />{t('an.sev.info')}</span><span className="muted">{t('an.nodecision', { n: group('info').length })}</span></div>
          {byRule(group('info')).map(([rule, fs]) => <RuleGroup key={'i' + rule} rule={rule} fs={fs} pf={pf} projectId={p.id} target={target} notes={notes} decide={decide} decideMany={decideMany} busy={busy} />)}</section>}
        {group('auto').length > 0 && <section className="col">
          <div className="group-h" onClick={() => setOpenAuto(o => !o)} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && setOpenAuto(o => !o)}><span className="tw">{openAuto ? '▾' : '▸'}</span><span className="badge auto">{t('an.sev.auto')}</span><span className="muted">{t('an.nodecision', { n: group('auto').length })}</span></div>
          {openAuto && byRule(group('auto')).map(([rule, fs]) => <RuleGroup key={'a' + rule} rule={rule} fs={fs} pf={pf} projectId={p.id} target={target} notes={notes} decide={decide} decideMany={decideMany} busy={busy} />)}</section>}
      </>}
    </div>
  )
}

function byRule(fs: Finding[]): [string, Finding[]][] {
  const m = new Map<string, Finding[]>()
  for (const f of fs) { if (!m.has(f.rule)) m.set(f.rule, []); m.get(f.rule)!.push(f) }
  return [...m.entries()].sort((a, b) => b[1].filter(f => !f.chosen).length - a[1].filter(f => !f.chosen).length || a[0].localeCompare(b[0]))
}
/** L47 : constats d'héritage regroupés par racine de hiérarchie (`Finding.root`) ; les plus à décider d'abord. */
function byRoot(fs: Finding[]): [string, Finding[]][] {
  const m = new Map<string, Finding[]>()
  for (const f of fs) if (f.root) { if (!m.has(f.root)) m.set(f.root, []); m.get(f.root)!.push(f) }
  return [...m.entries()].sort((a, b) => b[1].filter(f => !f.chosen).length - a[1].filter(f => !f.chosen).length || a[0].localeCompare(b[0]))
}

type Decide = (id: string, o: string | null, reason?: string) => void
type DecideMany = (d: Record<string, string | null>, reason?: string, via?: 'rule' | 'manual') => void
type Notes = Record<string, DecisionNote>

function ReasonInput({ value, onChange, onCommit, id }: { value: string; onChange: (v: string) => void; onCommit?: () => void; id?: string }) {
  const t = useT()
  return <input type="text" data-write data-testid="why-input" id={id} className="why-input" maxLength={280} value={value} placeholder={t('an.why.ph')} aria-label={t('an.why')}
    onChange={e => onChange(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && onCommit) onCommit() }} style={{ flex: 1, minWidth: 180 }} />
}

/** Une racine de hiérarchie : une décision pour toute la branche (P-02), avec une raison commune. */
function BranchGroup({ root, fs, pf, projectId, target, notes, decide, decideMany, branch, busy }: {
  root: string; fs: Finding[]; pf: Record<string, string>; projectId: string; target: 'curiosity' | 'neo4j'; notes: Notes
  decide: Decide; decideMany: DecideMany; branch: (b: { root: string; rule?: string; option?: string; reason?: string; overwrite?: boolean }) => void; busy: boolean
}) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [pick, setPick] = useState<Record<string, string>>({})
  const todo = fs.filter(f => !f.chosen && f.recommended && f.severity !== 'lost')
  const left = fs.filter(f => !f.chosen).length
  const rules = byRule(fs)
  const recoText = rules.map(([r, rfs]) => `${r} : ${rfs.find(f => f.recommended)?.options.find(o => o.id === rfs.find(f => f.recommended)?.recommended)?.label ?? '—'}`).join(' · ')
  const common = (rfs: Finding[]) => rfs[0].options.map(o => o.id).filter(id => rfs.every(f => f.options.some(o => o.id === id)))
  return (
    <div className={`finding ${fs[0].severity}`} style={{ gap: 4 }} data-tour="an-branch" data-testid="branch-group" data-root={root}>
      <div className="ttl" style={{ cursor: 'pointer' }} onClick={() => setOpen(o => !o)} role="button" tabIndex={0} aria-expanded={open} onKeyDown={e => e.key === 'Enter' && setOpen(o => !o)}>
        <span className="tw muted" style={{ width: 14 }}>{open ? '▾' : '▸'}</span><span className="badge">{rules.map(([r]) => r).join(' · ')}</span>
        <h3>{t('an.branch.title', { root: curie(root, pf) })}</h3><span className={'badge ' + (left === 0 ? 'ok' : 'review')}>{left === 0 ? t('an.branch.applied') : t('an.branch.count', { n: fs.length, todo: left })}</span><span className="grow" />
      </div>
      {todo.length > 0 && <div className="muted" style={{ paddingLeft: 22 }} data-testid="branch-reco">{t('an.recoOption')} {recoText}</div>}
      <div className="row" style={{ paddingLeft: 22 }}>
        <ReasonInput value={reason} onChange={setReason} />
        <button className="btn sm primary" data-testid="branch-apply" disabled={busy || todo.length === 0} onClick={() => branch({ root, ...(reason.trim() ? { reason: reason.trim() } : {}) })}>{t('an.branch.apply', { n: todo.length })}</button>
      </div>
      {open && <div className="col" style={{ marginTop: 6 }}>
        {rules.map(([rule, rfs]) => { const opts = common(rfs); const sel = pick[rule] ?? opts[0]; return opts.length > 1 && <div key={rule} className="row" style={{ paddingLeft: 22 }}>
          <span className="badge mono">{rule}</span><span className="muted">{t('an.branch.impose')}</span>
          <select data-write value={sel} aria-label={t('an.branch.impose') + ' ' + rule} onChange={e => setPick(x => ({ ...x, [rule]: e.target.value }))}>{opts.map(id => <option key={id} value={id}>{rfs[0].options.find(o => o.id === id)?.label ?? id}</option>)}</select>
          <button className="btn sm" data-testid={'branch-impose-' + rule} disabled={busy} onClick={() => branch({ root, rule, option: sel, overwrite: true, ...(reason.trim() ? { reason: reason.trim() } : {}) })}>{t('an.branch.imposeGo', { rule })}</button></div> })}
        {fs.map(f => <FindingCard key={f.id} f={f} pf={pf} projectId={projectId} target={target} note={notes[f.id]} decide={decide} />)}
      </div>}
    </div>
  )
}

function RuleGroup({ rule, fs, pf, projectId, target, notes, decide, decideMany, busy }: {
  rule: string; fs: Finding[]; pf: Record<string, string>; projectId: string; target: 'curiosity' | 'neo4j'; notes: Notes
  decide: Decide; decideMany: DecideMany; busy: boolean
}) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const decidable = fs.filter(f => f.options.length > 0)
  const counts = new Map<string, number>()
  for (const f of decidable) if (f.recommended) counts.set(f.recommended, (counts.get(f.recommended) ?? 0) + 1)
  const dom = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]
  const domLabel = dom ? decidable.flatMap(f => f.options).find(o => o.id === dom[0])?.label ?? dom[0] : null
  const todo = decidable.filter(f => !f.chosen && f.recommended)
  const done = decidable.filter(f => f.chosen).length
  const sev = fs[0].severity
  return (
    <div className={`finding ${sev}`} style={{ gap: 4 }} data-tour="an-rule">
      <div className="ttl" style={{ cursor: 'pointer' }} onClick={() => setOpen(o => !o)} role="button" tabIndex={0} aria-expanded={open} onKeyDown={e => e.key === 'Enter' && setOpen(o => !o)}>
        <span className="tw muted" style={{ width: 14 }}>{open ? '▾' : '▸'}</span><span className="badge mono">{rule}</span><h3>{fs[0].title}</h3>
        <span className="badge">{t('an.nfind', { n: fs.length })}</span>
        {decidable.length > 0 && <span className={'badge ' + (done === decidable.length ? 'ok' : 'review')}>{t('an.decidedOf', { d: done, n: decidable.length })}</span>}
        <span className="grow" />
      </div>
      {domLabel && <div className="row" style={{ paddingLeft: 22 }}>
        <span>{t('an.recoOption')} <b>{domLabel}</b>{dom && dom[1] < decidable.length ? <span className="muted"> ({dom[1]}/{decidable.length})</span> : null}</span><span className="grow" />
        {todo.length > 0 && sev !== 'auto' && <ReasonInput value={reason} onChange={setReason} />}
        <button className="btn sm primary" disabled={busy || todo.length === 0} onClick={() => decideMany(Object.fromEntries(todo.map(f => [f.id, f.recommended!])), reason.trim() || undefined, 'rule')}>
          {todo.length === 0 ? t('an.recoApplied') : t('an.recoApply', { n: todo.length })}</button></div>}
      {!domLabel && !open && <div className="muted" style={{ paddingLeft: 22 }}>{fs[0].detail}</div>}
      {sev === 'auto' && fs[0].auto_reason && <div className="muted" style={{ paddingLeft: 22 }} data-testid="auto-reason">{t('an.auto.reclass', { reason: fs[0].auto_reason })}</div>}
      {open && <div className="col" style={{ marginTop: 6 }}>{fs.map(f => <FindingCard key={f.id} f={f} pf={pf} projectId={projectId} target={target} note={notes[f.id]} decide={decide} />)}</div>}
    </div>
  )
}

function FindingCard({ f, pf, projectId, target, note, decide }: { f: Finding; pf: Record<string, string>; projectId: string; target: 'curiosity' | 'neo4j'; note?: DecisionNote; decide: Decide }) {
  const t = useT()
  const [exp, setExp] = useState<string | null>(null)
  const [expErr, setExpErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [reason, setReason] = useState(note?.reason ?? '')
  useEffect(() => { setReason(note?.reason ?? '') }, [note?.reason, f.chosen])
  const explain = async () => {
    setBusy(true); setExpErr(null)
    try { setExp((await api.assistantExplain(projectId, target, f.id)).text) } catch (e) { setExpErr(e) } finally { setBusy(false) }
  }
  const decidable = f.severity === 'review' || f.severity === 'lost'
  return (
    <div className={`finding ${f.severity}` + (f.chosen ? ' done' : '')} data-tour="an-finding">
      <div className="ttl"><span className="badge mono">{f.rule}</span><h3>{f.title}</h3><span className="mono muted" title={f.subject}>{curie(f.subject, pf)}</span><span className="grow" />
        {decidable && (f.chosen ? <span className="badge ok">{t('an.decided')}</span> : <span className="badge review">{t('an.undecided')}</span>)}</div>
      <div>{f.detail}</div>
      {f.auto_reason && <div className="muted" data-testid="auto-reason">{t('an.auto.reclass', { reason: f.auto_reason })}</div>}
      {f.options.length > 0 && <div className="opts" role="radiogroup" aria-label={t('an.optionsFor', { title: f.title })}>
        {f.options.map(o => <label key={o.id} className={'opt' + (f.chosen === o.id ? ' chosen' : '')}>
          <input type="radio" name={f.id} checked={f.chosen === o.id} onChange={() => { const same = !f.chosen || f.chosen === o.id; if (!same) setReason(''); decide(f.id, o.id, same ? reason.trim() || undefined : undefined) }} />
          <span><b>{o.label}</b>{f.recommended === o.id && <span className="reco">{t('an.recoFor', { target: target === 'curiosity' ? 'Curiosity' : 'Neo4j' })}</span>}</span>
          <span className="imp">{o.impact}</span></label>)}
      </div>}
      {f.rationale && <div className="rationale">{f.rationale}</div>}
      {f.options.length > 0 && <div className="row">
        <ReasonInput value={reason} onChange={setReason} onCommit={f.chosen ? () => decide(f.id, f.chosen!, reason.trim()) : undefined} />
        {f.chosen && reason.trim() !== (note?.reason ?? '') && <button className="btn sm" data-testid="why-save" onClick={() => decide(f.id, f.chosen!, reason.trim())}>{t('an.why.save')}</button>}
      </div>}
      {f.chosen && <div className="muted" data-testid="decision-by">{note?.by ? t('an.why.by', { by: note.by, at: note.at.slice(0, 16).replace('T', ' ') }) : t('an.why.legacy')}</div>}
      <div className="row">
        {f.options.length > 0 && <button className="btn sm" disabled={busy} onClick={explain}>{busy ? t('an.thinking') : t('an.explain')}</button>}
        {f.chosen && <button className="btn sm ghost" onClick={() => decide(f.id, null)}>{t('an.undo')}</button>}
        {f.related.length > 0 && <span className="muted">{t('an.related')} {f.related.map(r => curie(r, pf)).join(', ')}</span>}
      </div>
      <ErrorView error={expErr} what={t('an.what.assistant')} />
      {exp && <div className="explain" dangerouslySetInnerHTML={{ __html: renderSafeMarkdown(exp) }} />}
    </div>
  )
}
