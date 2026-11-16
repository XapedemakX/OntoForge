import { useEffect, useMemo, useRef, useState } from 'react'
import { api, curie, type Finding } from '../../api'
import { Icon } from '../../kit'
import { useI18n } from '../../i18n'
import { renderSafeMarkdown } from '../../lib/safeMarkdown'
import { useReadOnly } from '../../collab/readonly'
import './deck.css'

type Pill = 'todo' | 'lost' | 'done'
/** Rendu inline minimal : `code` entre accents graves devient <code> (les textes de règles en contiennent), le reste reste du texte. */
const Md = ({ text }: { text: string }) => <>{text.split(/(`[^`]+`)/g).map((x, i) => (x.length > 2 && x.startsWith('`') && x.endsWith('`') ? <code key={i}>{x.slice(1, -1)}</code> : x))}</>
const isReview = (f: Finding) => f.severity === 'review'
const isLost = (f: Finding) => f.severity === 'lost'

/**
 * Arbitrage sur téléphone (L44) : une carte par point à arbitrer, option recommandée présélectionnée, « Valider ce choix » = 1 toucher.
 * Balayage horizontal pour naviguer (jamais de décision par balayage). « Appliquer aux N de la règle » est annulable pendant 5 s.
 * Même API que l'écran de bureau (api.decide) : aucun changement de contrat.
 */
export function Deck({ pid, target, findings, pf, decide, decideMany, summary, busy }: {
  pid: string; target: 'curiosity' | 'neo4j'; findings: Finding[]; pf: Record<string, string>; summary: { auto: number; decided: number; pending: number; review: number; lost: number }
  decide: (id: string, o: string | null) => Promise<void> | void; decideMany: (d: Record<string, string | null>) => Promise<void> | void; busy: boolean
}) {
  const { t } = useI18n(); const ro = useReadOnly()
  const lists = useMemo(() => ({
    todo: findings.filter(f => isReview(f) && !f.chosen && f.options.length > 0), lost: findings.filter(f => isLost(f) && !f.chosen && f.options.length > 0),
    done: findings.filter(f => (isReview(f) || isLost(f)) && f.chosen),
  }), [findings])
  const [pill, setPill] = useState<Pill>(() => (findings.some(f => isLost(f) && !f.chosen && f.options.length > 0) ? 'lost' : 'todo'))
  const [idx, setIdx] = useState(0); const [q, setQ] = useState(''); const [searching, setSearching] = useState(false)
  const [pick, setPick] = useState<Record<string, string>>({}); const [why, setWhy] = useState<string | null>(null)
  const [undo, setUndo] = useState<{ ids: string[]; n: number } | null>(null)
  const [exp, setExp] = useState<{ id: string; text?: string; err?: string; busy?: boolean } | null>(null)
  const list = useMemo(() => lists[pill].filter(f => !q || (f.title + f.rule + f.subject + f.detail).toLowerCase().includes(q.toLowerCase())), [lists, pill, q])
  const i = Math.min(idx, Math.max(0, list.length - 1)); const f = list[i]
  useEffect(() => { setIdx(0) }, [pill, q])
  // la liste affichée est vide (dernier point tranché) : on passe à la suivante qui a encore des points
  useEffect(() => { if (q || pill === 'done' || lists[pill].length) return; const nx = (['todo', 'lost'] as Pill[]).find(k => lists[k].length); if (nx) setPill(nx) }, [lists, pill, q])
  useEffect(() => { if (!undo) return; const h = setTimeout(() => setUndo(null), 5000); return () => clearTimeout(h) }, [undo])
  useEffect(() => { setWhy(null); setExp(null) }, [f?.id])
  const tn = target === 'curiosity' ? 'Curiosity' : 'Neo4j'
  const decidedN = lists.done.length, todoTotal = lists.todo.length + lists.lost.length + decidedN   // mêmes définitions que le badge (pending.ts)
  const chosenOpt = f ? (pick[f.id] ?? f.chosen ?? f.recommended ?? f.options[0]?.id) : undefined
  const sameRule = f ? lists.todo.concat(lists.lost).filter(x => x.rule === f.rule && !x.chosen && x.recommended) : []
  const go = (d: number) => { if (list.length > 1) setIdx(x => (x + d + list.length) % list.length) }

  // balayage horizontal : seulement de la navigation
  const sw = useRef<{ x: number; y: number } | null>(null)
  const onDown = (e: React.PointerEvent) => { sw.current = { x: e.clientX, y: e.clientY } }
  const onUp = (e: React.PointerEvent) => {
    const s = sw.current; sw.current = null; if (!s) return
    const dx = e.clientX - s.x, dy = e.clientY - s.y
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) go(dx < 0 ? 1 : -1)
  }
  const validate = async () => { if (f && chosenOpt) await decide(f.id, chosenOpt) }
  const applyRule = async () => {
    const ids = sameRule.map(x => x.id)
    await decideMany(Object.fromEntries(sameRule.map(x => [x.id, x.recommended!])))
    setUndo({ ids, n: ids.length })
  }
  const explain = async () => {
    if (!f) return
    setExp({ id: f.id, busy: true })
    try { setExp({ id: f.id, text: (await api.assistantExplain(pid, target, f.id)).text }) } catch (e) { setExp({ id: f.id, err: (e as Error).message }) }
  }
  const pills: [Pill, string, number][] = [['todo', t('mob.arb.todo'), lists.todo.length], ['lost', t('mob.arb.lost'), lists.lost.length], ['done', t('mob.arb.done'), lists.done.length]]
  return (
    <div className="deck" data-testid="deck">
      <div className="deck-top">
        <div className="deck-prog" role="progressbar" aria-valuemin={0} aria-valuemax={todoTotal} aria-valuenow={decidedN} aria-label={t('mob.arb.progress', { d: decidedN, n: todoTotal })}>
          <div className="d" style={{ width: todoTotal ? `${(decidedN / todoTotal) * 100}%` : '100%' }} /></div>
        <p className="deck-sub"><b>{tn}</b> · {t('mob.arb.progress', { d: decidedN, n: todoTotal })}{lists.lost.length > 0 && <span> · {t('mob.arb.ofwhich', { n: lists.lost.length })}</span>}{summary.auto > 0 && <span className="muted"> · {t('mob.arb.auto', { n: summary.auto })}</span>}</p>
        <div className="deck-pills" role="tablist" aria-label={t('mob.arb.filter')}>
          {pills.map(([k, l, n]) => <button key={k} type="button" role="tab" aria-selected={pill === k} className={'dpill ' + k} data-testid={'pill-' + k} onClick={() => setPill(k)}>{l} <b>{n}</b></button>)}
          <button type="button" className="dsearch" aria-label={t('mob.arb.search')} aria-pressed={searching} onClick={() => { setSearching(s => !s); if (searching) setQ('') }}><Icon name="magnifying-glass" /></button>
        </div>
        {searching && <input type="search" className="deck-q" autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder={t('an.filter')} aria-label={t('an.filter')} />}
      </div>
      {!f && <div className="deck-empty" role="status"><Icon name={pill === 'done' ? 'circle-info' : 'circle-check'} /><b>{t(pill === 'done' ? 'mob.arb.none.done' : 'mob.arb.none.todo')}</b>
        {pill !== 'done' && <p className="muted">{t('mob.arb.none.todo.d', { target: tn })}</p>}</div>}
      {f && <>
        <article className={'dcard ' + f.severity + (f.chosen ? ' done' : '')} data-testid="deck-card" data-finding={f.id} onPointerDown={onDown} onPointerUp={onUp} aria-label={f.title}>
          <header><span className="badge mono">{f.rule}</span>
            <span className="muted grow">{sameRule.length > 1 || lists[pill].filter(x => x.rule === f.rule).length > 1 ? t('mob.arb.inrule', { n: lists[pill].filter(x => x.rule === f.rule).length }) : t(f.severity === 'lost' ? 'mob.arb.islost' : 'mob.arb.isreview')}</span>
            <span className="dpos" aria-live="polite">{i + 1} / {list.length}</span></header>
          <h2>{f.title} <span className="subj mono" title={f.subject}>{curie(f.subject, pf)}</span></h2>
          <p className="det"><Md text={f.detail} /></p>
          <div className="dopts" role="radiogroup" aria-label={t('an.optionsFor', { title: f.title })}>
            {f.options.map(o => (
              <label key={o.id} className={'dopt' + (chosenOpt === o.id ? ' on' : '')}>
                <input type="radio" name={'o-' + f.id} checked={chosenOpt === o.id} disabled={ro || !!f.chosen} onChange={() => setPick(p => ({ ...p, [f.id]: o.id }))} />
                <span className="ot"><b><Md text={o.label} /></b>{f.recommended === o.id && <span className="reco">{t('an.recoFor', { target: tn })}</span>}<small><Md text={o.impact} /></small></span>
              </label>))}
          </div>
          <button type="button" className="why" aria-expanded={why === f.id} onClick={() => setWhy(w => (w === f.id ? null : f.id))}><Icon name="circle-info" />{t('mob.arb.why')}</button>
          {why === f.id && <div className="whybox">{f.rationale ? <p>{f.rationale}</p> : <p className="muted">{t('mob.arb.why.none')}</p>}
            <button type="button" className="btn sm" disabled={exp?.busy} onClick={explain}><Icon name="wand-magic-sparkles" />{exp?.busy ? t('an.thinking') : t('an.explain')}</button>
            {exp?.err && <p className="err">{exp.err}</p>}{exp?.text && <div className="explain" dangerouslySetInnerHTML={{ __html: renderSafeMarkdown(exp.text) }} />}</div>}
          {sameRule.length > 1 && !f.chosen && <button type="button" className="rulebtn" disabled={busy || ro} data-testid="apply-rule" onClick={applyRule}><Icon name="layer-group" />{t('mob.arb.applyrule', { n: sameRule.length })}</button>}
          {f.chosen && <button type="button" className="btn" disabled={busy || ro} data-testid="undo-decision" onClick={() => decide(f.id, null)}><Icon name="rotate-left" />{t('an.undo')}</button>}
        </article>
        {!f.chosen && <div className="deck-bar" data-ag-lift>
          <button type="button" className="btn" disabled={list.length < 2} onClick={() => go(1)} data-testid="deck-skip">{t('mob.arb.skip')}</button>
          <button type="button" className="btn primary" disabled={busy || ro || !chosenOpt} onClick={() => void validate()} data-testid="deck-validate">{t('mob.arb.validate')}</button>
        </div>}
        {f.chosen && list.length > 1 && <div className="deck-bar" data-ag-lift><button type="button" className="btn" onClick={() => go(-1)}><Icon name="chevron-left" />{t('mob.arb.prev')}</button><button type="button" className="btn" onClick={() => go(1)}>{t('mob.arb.next')}<Icon name="chevron-right" /></button></div>}
      </>}
      {undo && <div className="deck-undo" role="status" data-testid="deck-undo"><span>{t('mob.arb.applied', { n: undo.n })}</span>
        <button type="button" onClick={() => { void decideMany(Object.fromEntries(undo.ids.map(id => [id, null]))); setUndo(null) }}>{t('mob.arb.undo')}</button></div>}
    </div>)
}
