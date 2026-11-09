import { api, type GenerationRecord, type PGModel, type Target } from '../api'
import type { ScreenProps } from '../shell/types'
import { Button, Card, EmptyState, Icon, Krakie, SeverityBadge } from '../kit'
import type { Pose } from '../krakie/Krakie'
import { useT } from '../i18n'
import { useAssistantContext } from '../lib/assistantContext'
import { useLoad, useToast } from '../ui'
import { useState } from 'react'
import { TourCard } from '../tour'

const go = (id: string, s: string) => { location.hash = `#/projet/${encodeURIComponent(id)}/${s}` }
const count = (m: PGModel | null | undefined) => {
  const c = { auto: 0, review: 0, lost: 0 }
  m?.findings.forEach(f => { if (f.severity === 'auto') c.auto++; else if (f.severity !== 'info' && !f.chosen) c[f.severity]++ })
  return c
}

export function Dashboard({ p, target }: ScreenProps) {
  const t = useT()
  useAssistantContext({ screen: 'dashboard', projectId: p.id, target })
  const tn = (x: Target) => (x === 'curiosity' ? 'Curiosity' : 'Neo4j')
  const conf = useLoad(() => api.conformance(p.id), [p.id, p.updated_at])
  const cur = useLoad(() => api.analyze(p.id, 'curiosity'), [p.id, p.updated_at])
  const neo = useLoad(() => api.analyze(p.id, 'neo4j'), [p.id, p.updated_at])
  const peri = useLoad(() => api.perimeters(p.id).catch(() => []), [p.id])
  const toast = useToast()
  const [genBusy, setGenBusy] = useState(false)
  const [genTick, setGenTick] = useState(0)
  const [trophy, setTrophy] = useState(false)
  const hist = useLoad(() => api.generations(p.id).catch(() => []), [p.id, genTick])
  // l'état du projet côté serveur (le `p` du shell peut être en retard d'une décision)
  const srv = useLoad(() => api.getProject(p.id).then(x => x.updated_at), [p.id, p.updated_at, genTick])
  const curUpd = srv.data ?? p.updated_at
  const history = hist.data ?? []
  const gens: Partial<Record<Target, GenerationRecord>> = {}
  for (const g of history) if (!gens[g.target]) gens[g.target] = g   // la plus récente d'abord
  const generate = async () => {
    setGenBusy(true)
    try { const r = await api.generate(p.id, target); toast(t('dash.gen.done', { target: tn(target), n: Object.keys(r.files).length }), { pose: 'trophee' }); setGenTick(x => x + 1); setTrophy(true); setTimeout(() => setTrophy(false), 2000) }
    catch (e) { toast((e as Error).message) } finally { setGenBusy(false) }
  }
  const o = p.onto
  const nCls = Object.keys(o.classes).length
  const nProps = Object.keys(o.object_properties).length + Object.keys(o.datatype_properties).length
  const nShapes = Object.keys(p.shapes.shapes).length
  const dl = conf.data ? conf.data.profiles.DL : null
  const dlIssues = conf.data?.issues.filter(i => i.level === 'error').length ?? 0
  const counts: Record<Target, ReturnType<typeof count>> = { curiosity: count(cur.data), neo4j: count(neo.data) }
  const cc = counts[target]
  const loaded = !!(conf.data && cur.data && neo.data)
  const stale = (x: Target) => !!gens[x] && gens[x]!.project_updated_at !== curUpd

  // Prochaine action : règles simples, première qui s'applique.
  type Next = { pose: Pose; title: string; text: string; action: string; to?: string; run?: () => void; extra?: { label: string; icon: string; to?: string; href?: string }[] }
  const tp = { target: tn(target) }
  let next: Next
  if (nCls === 0) next = { pose: 'accueil', title: t('dash.next.empty.t'), text: t('dash.next.empty.d'), action: t('dash.next.empty.a1'), to: 'ontologie-liste',
    extra: [{ label: t('dash.next.empty.a2'), icon: 'file-import', to: 'ontologie-liste' }, { label: t('dash.next.empty.a3'), icon: 'wand-magic-sparkles', to: 'assistant' }] }
  else if (dl === false) next = { pose: 'loupe', title: t('dash.next.dl.t', { n: dlIssues }), text: t('dash.next.dl.d'), action: t('dash.next.dl.a'), to: 'conformite' }
  else if (nShapes === 0) next = { pose: 'lit', title: t('dash.next.shapes.t'), text: t('dash.next.shapes.d'), action: t('dash.next.shapes.a'), to: 'shacl' }
  else if (cc.lost > 0) next = { pose: 'inquiete', title: t('dash.next.lost.t', { n: cc.lost, ...tp }), text: t('dash.next.lost.d'), action: t('dash.next.lost.a'), to: 'analyse' }
  else if (cc.review > 0) next = { pose: 'graphe', title: t('dash.next.review.t', { n: cc.review, ...tp }), text: t('dash.next.review.d'), action: t('dash.next.review.a'), to: 'analyse' }
  else if (stale(target)) next = { pose: 'forge', title: t('dash.next.regen.t', tp), text: t('dash.next.regen.d', tp), action: t('dash.gen.btn', tp), run: generate }
  else if (!gens[target]) next = { pose: 'forge', title: t('dash.next.gen.t', tp), text: t('dash.next.gen.d', tp), action: t('dash.gen.btn', tp), run: generate }
  else next = { pose: 'contente', title: t('dash.next.done.t', tp), text: t('dash.next.done.d'), action: t('dash.next.done.a'), run: undefined, to: undefined,
    extra: [{ label: t('dash.gen.files'), icon: 'file-lines', to: 'exports' }, { label: t('dash.next.ok.a'), icon: 'magnifying-glass-chart', to: 'requetes' }] }
  if (!loaded && nCls > 0) next = { ...next, pose: 'reflechit' }

  const lastGen = Object.values(gens).sort((a, b) => b!.at.localeCompare(a!.at))[0]
  const steps: { k: string; to: string; icon: string; sub: string; tone?: 'ok' | 'review' | 'lost' }[] = [
    { k: 'concevoir', to: 'ontologie', icon: 'sitemap', sub: nCls ? t('dash.step.concevoir.sub', { classes: nCls, props: nProps }) : t('dash.step.concevoir.empty') },
    { k: 'verifier', to: 'conformite', icon: 'clipboard-check', tone: dl === false ? 'review' : dl ? 'ok' : undefined,
      sub: (dl === null ? '…' : dl ? t('dash.step.verifier.dl') : t('dash.step.verifier.notdl', { n: dlIssues })) + ' · ' + (nShapes ? t('dash.step.verifier.shapes', { n: nShapes }) : t('dash.step.verifier.noshapes')) },
    { k: 'transposer', to: 'analyse', icon: 'scale-balanced', tone: !loaded ? undefined : cc.lost ? 'lost' : cc.review ? 'review' : 'ok',
      sub: !loaded ? '…' : cc.lost + cc.review ? t('dash.step.transposer.left', { n: cc.lost + cc.review, ...tp }) : t('dash.step.transposer.done', tp) },
    { k: 'generer', to: 'exports', icon: 'file-export', tone: lastGen ? (stale(lastGen.target) ? 'review' : 'ok') : undefined,
      sub: lastGen ? t('dash.step.generer.sub', { target: tn(lastGen.target) }) : t('dash.step.generer.none') },
  ]
  const fmt = (iso: string) => new Date(iso).toLocaleString(document.documentElement.lang || 'fr', { dateStyle: 'medium', timeStyle: 'short' })

  return (
    <div className="page dash">
      <div className="page-head"><div><h1>{t('dash.title')}</h1><div className="sub">{t('dash.subtitle', { name: p.name })}</div></div></div>

      <section className={`next ${next.pose}`} aria-label={t('dash.next')} data-tour="dash-next">
        <Krakie pose={genBusy ? 'forge' : trophy ? 'trophee' : next.pose} size={96} title="Krakie" />
        <div className="bubble">
          <h2>{next.title}</h2>
          <p>{next.text}</p>
          <div className="row">
            {next.to || next.run ? <Button variant="primary" icon={next.run ? 'bolt' : undefined} disabled={genBusy} onClick={() => (next.run ? next.run() : go(p.id, next.to!))}>{genBusy ? t('dash.gen.busy') : next.action}</Button>
              : <a className="btn primary" href={api.zipUrl(p.id, target)}><Icon name="download" /> {next.action}</a>}
            {next.extra?.map(x => <Button key={x.label} icon={x.icon} onClick={() => go(p.id, x.to!)}>{x.label}</Button>)}
          </div>
        </div>
      </section>

      <div className="steps" data-tour="dash-steps" role="list" aria-label={t('dash.steps')}>
        {steps.map((s, i) => (
          <button key={s.k} role="listitem" className={`step ${s.tone ?? ''}`} onClick={() => go(p.id, s.to)}>
            <span className="num">{i + 1}</span>
            <span className="st-body"><b>{t('step.' + s.k)}</b><span>{s.sub}</span></span>
            <Icon name={s.tone === 'ok' ? 'circle-check' : s.tone === 'lost' ? 'triangle-exclamation' : s.tone === 'review' ? 'scale-balanced' : s.icon} className="st-ico" />
          </button>))}
      </div>

      <div className="dash-grid">
        <Card title={t('dash.findings')}>
          {(['curiosity', 'neo4j'] as Target[]).map(x => {
            const c = counts[x]; const tot = c.auto + c.review + c.lost || 1
            return (
              <div key={x} className="bars">
                <div className="row"><b>{tn(x)}</b><span className="grow" />
                  <SeverityBadge severity="auto" count={c.auto} /><SeverityBadge severity="review" count={c.review} /><SeverityBadge severity="lost" count={c.lost} /></div>
                <div className="stack" role="img" aria-label={`${tn(x)} : ${t('dash.count.auto', { n: c.auto })}, ${t('dash.count.review', { n: c.review })}, ${t('dash.count.lost', { n: c.lost })}`}>
                  <i className="auto" style={{ width: `${(c.auto / tot) * 100}%` }} /><i className="review" style={{ width: `${(c.review / tot) * 100}%` }} /><i className="lost" style={{ width: `${(c.lost / tot) * 100}%` }} />
                </div>
              </div>)
          })}
          {!loaded && <div className="muted">{t('dash.loading')}</div>}
        </Card>

        <Card title={t('dash.gen.title')} tone={loaded && cc.review + cc.lost === 0 ? 'auto' : undefined}>
          <p className="muted" style={{ margin: '0 0 10px' }}>{loaded ? (cc.review + cc.lost === 0 ? t('dash.gen.ready', tp) : t('dash.gen.blocked', { n: cc.review + cc.lost, ...tp })) : t('dash.loading')}</p>
          <div className="row" style={{ marginBottom: 12 }}>
            <Button variant={loaded && cc.review + cc.lost === 0 ? 'primary' : 'default'} icon="bolt" disabled={genBusy || nCls === 0} onClick={generate}>{genBusy ? t('dash.gen.busy') : t('dash.gen.btn', tp)}</Button>
            {gens[target] && <a className="btn" href={api.zipUrl(p.id, target)}><Icon name="download" /> {t('dash.gen.zip')}</a>}
          </div>
          <h3 style={{ fontSize: 'var(--fs-sm)', margin: '0 0 6px' }}>{t('dash.generations')}</h3>
          {history.length === 0 ? <div className="muted">{t('dash.noGeneration')}</div> :
            <ul className="gens">{history.slice(0, 5).map(g => (
              <li key={g.at + g.target}><b>{tn(g.target)}</b><span className="muted">{fmt(g.at)}</span><span className="muted">{t('dash.gen.row', { files: g.files.length, pending: g.findings_summary.pending ?? 0 })}</span><span className="grow" />
                {g === gens[g.target] && (g.project_updated_at !== curUpd ? <span title={t('dash.stale.hint')}><SeverityBadge severity="review" label={t('dash.stale')} /></span> : <SeverityBadge severity="auto" label={t('dash.upToDate')} />)}</li>))}</ul>}
        </Card>

        <Card title={t('dash.perimeters')}>
          {peri.data && peri.data.length ? <ul className="gens">{peri.data.map(x => <li key={x.id}><b>{x.name}</b><span className="muted">{t('dash.stat.classes', { n: x.classes.length })}</span></li>)}</ul> : <EmptyState pose="loupe" title={t('dash.perimeters.none')} action={<Button size="sm" icon="plus" onClick={() => go(p.id, 'ontologie')}>{t('dash.perimeters.create')}</Button>}>{t('dash.perimeters.hint')}</EmptyState>}
        </Card>

        <TourCard />

        <Card title={t('dash.shortcuts')}>
          <div className="row">
            <Button icon="sitemap" onClick={() => go(p.id, 'ontologie')}>{t('nav.ontologie')}</Button>
            <Button icon="wand-magic-sparkles" onClick={() => go(p.id, 'assistant')}>{t('nav.assistant')}</Button>
            <Button icon="file-export" onClick={() => go(p.id, 'exports')}>{t('nav.exports')}</Button>
            <Button icon="magnifying-glass-chart" onClick={() => go(p.id, 'requetes')}>{t('nav.requetes')}</Button>
          </div>
        </Card>
      </div>
    </div>
  )
}
