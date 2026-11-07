import { useState } from 'react'
import { marked } from 'marked'
import { api, curie, type Finding, type FindingSeverity } from '../api'
import type { ScreenProps } from '../shell/types'
import { Button, Card, Icon } from '../kit'
import { useT } from '../i18n'
import { Empty, ErrorView, Spin, esc, useLoad, useToast } from '../ui'


export function Analysis({ p, target }: ScreenProps) {
  const toast = useToast()
  const t = useT()
  const [confirm, setConfirm] = useState(false)
  const [onlyReview, setOnlyReview] = useState(true)
  const { data: pg, error, loading, setData, reload } = useLoad(() => api.analyze(p.id, target), [p.id, target, p.updated_at])
  const [err, setErr] = useState<unknown>(null)
  const [onlyPending, setOnlyPending] = useState(false)
  const [q, setQ] = useState('')
  const [openAuto, setOpenAuto] = useState(false)
  const [busy, setBusy] = useState(false)
  const pf = p.onto.meta.prefixes

  const decide = async (fid: string, opt: string | null) => {
    setErr(null)
    try { setData(await api.decide(p.id, target, { [fid]: opt })) } catch (e) { setErr(e) }
  }
  const decideMany = async (d: Record<string, string | null>) => {
    setErr(null); setBusy(true)
    try { setData(await api.decide(p.id, target, d)) } catch (e) { setErr(e) } finally { setBusy(false) }
  }
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
  const total = pg?.findings.length || 1
  const todo = sum ? sum.review + sum.lost : 0
  const match = (f: Finding) => (!onlyPending || ((f.severity === 'review' || f.severity === 'lost') && !f.chosen)) && (!q || (f.title + f.rule + f.subject + f.detail).toLowerCase().includes(q.toLowerCase()))
  const group = (s: FindingSeverity) => (pg?.findings ?? []).filter(f => f.severity === s && match(f)).sort((a, b) => Number(!!a.chosen) - Number(!!b.chosen))

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
      {loading && !pg && <Spin />}
      <ErrorView error={error} what={t('an.what')} /><ErrorView error={err} what={t('an.what.decide')} />
      {pg && sum && <>
        <div className="card triage" data-tour="an-counters">
          <div className="kpis">
            <div className="kpi auto"><b>{sum.auto}</b><span>{t('an.kpi.auto')}</span></div>
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
        {(['lost', 'review'] as const).map(s => { const g = group(s); return g.length > 0 && <section key={s} className="col" data-tour={'an-group-' + s}>
          <div className="row"><span className={'badge ' + s}>{t('an.sev.' + s)}</span><span className="muted">{t('an.count', { n: g.length, r: byRule(g).length })}</span></div>
          {byRule(g).map(([rule, fs]) => <RuleGroup key={s + rule} rule={rule} fs={fs} pf={pf} projectId={p.id} target={target} decide={decide} decideMany={decideMany} busy={busy} />)}</section> })}
        {group('info').length > 0 && <section className="col"><div className="group-h"><span className="sev info"><Icon name="circle-info" />{t('an.sev.info')}</span><span className="muted">{t('an.nodecision', { n: group('info').length })}</span></div>
          {byRule(group('info')).map(([rule, fs]) => <RuleGroup key={'i' + rule} rule={rule} fs={fs} pf={pf} projectId={p.id} target={target} decide={decide} decideMany={decideMany} busy={busy} />)}</section>}
        {group('auto').length > 0 && <section className="col">
          <div className="group-h" onClick={() => setOpenAuto(o => !o)} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && setOpenAuto(o => !o)}><span className="tw">{openAuto ? '▾' : '▸'}</span><span className="badge auto">{t('an.sev.auto')}</span><span className="muted">{t('an.nodecision', { n: group('auto').length })}</span></div>
          {openAuto && byRule(group('auto')).map(([rule, fs]) => <RuleGroup key={'a' + rule} rule={rule} fs={fs} pf={pf} projectId={p.id} target={target} decide={decide} decideMany={decideMany} busy={busy} />)}</section>}
      </>}
    </div>
  )
}

function byRule(fs: Finding[]): [string, Finding[]][] {
  const m = new Map<string, Finding[]>()
  for (const f of fs) { if (!m.has(f.rule)) m.set(f.rule, []); m.get(f.rule)!.push(f) }
  return [...m.entries()].sort((a, b) => b[1].filter(f => !f.chosen).length - a[1].filter(f => !f.chosen).length || a[0].localeCompare(b[0]))
}

function RuleGroup({ rule, fs, pf, projectId, target, decide, decideMany, busy }: {
  rule: string; fs: Finding[]; pf: Record<string, string>; projectId: string; target: 'curiosity' | 'neo4j'
  decide: (id: string, o: string | null) => void; decideMany: (d: Record<string, string | null>) => void; busy: boolean
}) {
  const t = useT()
  const [open, setOpen] = useState(false)
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
        <button className="btn sm primary" disabled={busy || todo.length === 0} onClick={() => decideMany(Object.fromEntries(todo.map(f => [f.id, f.recommended!])))}>
          {todo.length === 0 ? t('an.recoApplied') : t('an.recoApply', { n: todo.length })}</button></div>}
      {!domLabel && !open && <div className="muted" style={{ paddingLeft: 22 }}>{fs[0].detail}</div>}
      {open && <div className="col" style={{ marginTop: 6 }}>{fs.map(f => <FindingCard key={f.id} f={f} pf={pf} projectId={projectId} target={target} decide={decide} />)}</div>}
    </div>
  )
}

function FindingCard({ f, pf, projectId, target, decide }: { f: Finding; pf: Record<string, string>; projectId: string; target: 'curiosity' | 'neo4j'; decide: (id: string, o: string | null) => void }) {
  const t = useT()
  const [exp, setExp] = useState<string | null>(null)
  const [expErr, setExpErr] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const explain = async () => {
    setBusy(true); setExpErr(null)
    try { setExp((await api.assistantExplain(projectId, target, f.id)).text) } catch (e) { setExpErr(e) } finally { setBusy(false) }
  }
  return (
    <div className={`finding ${f.severity}` + (f.chosen ? ' done' : '')} data-tour="an-finding">
      <div className="ttl"><span className="badge mono">{f.rule}</span><h3>{f.title}</h3><span className="mono muted" title={f.subject}>{curie(f.subject, pf)}</span><span className="grow" />
        {(f.severity === 'review' || f.severity === 'lost') && (f.chosen ? <span className="badge ok">{t('an.decided')}</span> : <span className="badge review">{t('an.undecided')}</span>)}</div>
      <div>{f.detail}</div>
      {f.options.length > 0 && <div className="opts" role="radiogroup" aria-label={t('an.optionsFor', { title: f.title })}>
        {f.options.map(o => <label key={o.id} className={'opt' + (f.chosen === o.id ? ' chosen' : '')}>
          <input type="radio" name={f.id} checked={f.chosen === o.id} onChange={() => decide(f.id, o.id)} />
          <span><b>{o.label}</b>{f.recommended === o.id && <span className="reco">{t('an.recoFor', { target: target === 'curiosity' ? 'Curiosity' : 'Neo4j' })}</span>}</span>
          <span className="imp">{o.impact}</span></label>)}
      </div>}
      {f.rationale && <div className="rationale">{f.rationale}</div>}
      <div className="row">
        {f.options.length > 0 && <button className="btn sm" disabled={busy} onClick={explain}>{busy ? t('an.thinking') : t('an.explain')}</button>}
        {f.chosen && <button className="btn sm ghost" onClick={() => decide(f.id, null)}>{t('an.undo')}</button>}
        {f.related.length > 0 && <span className="muted">{t('an.related')} {f.related.map(r => curie(r, pf)).join(', ')}</span>}
      </div>
      <ErrorView error={expErr} what={t('an.what.assistant')} />
      {exp && <div className="explain" dangerouslySetInnerHTML={{ __html: marked.parse(esc(exp), { async: false }) as string }} />}
    </div>
  )
}
