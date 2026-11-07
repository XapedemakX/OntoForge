import { useState } from 'react'
import type { Project } from '../api'
import { Button, Icon } from '../kit'
import { useI18n } from '../i18n'
import { applyAction, go, openGuidedQuery, undoAction } from './run'
import { getLastApplied, useDockUi, type AgentAction } from './store'

const ICON: Record<string, string> = { ops: 'pen-ruler', proposal: 'wand-magic-sparkles', shapes: 'shield-halved', guided_query: 'magnifying-glass-chart', navigate: 'arrow-up-right-from-square' }

/** Cartes d'actions d'un message : aperçu lisible, puis « Appliquer » (jamais automatique) et « Annuler ». */
export function ActionCards({ pid, msgId, actions, setP }: { pid: string; msgId: string; actions: AgentAction[]; setP: (p: Project) => void }) {
  const { t } = useI18n()
  useDockUi() // se met à jour quand la dernière action appliquée change
  const [open, setOpen] = useState<Record<number, boolean>>({})
  return (
    <div className="ag-actions">
      {actions.map((a, i) => {
        const st = a.status ?? 'idle'
        const busy = st === 'busy'
        const preview: { text: string }[] = a.payload.preview ?? []
        const canUndo = st === 'applied' && getLastApplied(pid) === `${msgId}:${i}`
        return (
          <section key={i} className={'ag-card ' + a.kind + ' ' + st} aria-label={t('ag.kind.' + a.kind)}>
            <header><Icon name={ICON[a.kind]} /><b>{t('ag.kind.' + a.kind)}</b>
              {st === 'applied' && <span className="ag-state ok"><Icon name="check" />{t('ag.applied')}</span>}
              {st === 'undone' && <span className="ag-state"><Icon name="rotate-left" />{t('ag.undone')}</span>}
            </header>
            {(a.kind === 'ops' || a.kind === 'shapes') && (
              <ul className="ag-preview">{preview.map((x, j) => <li key={j}>{x.text}</li>)}</ul>
            )}
            {a.kind === 'proposal' && (
              <ul className="ag-preview">
                {(a.payload.labels ?? []).map((x: { label: string; kind: string; type: string }, j: number) => <li key={j} className={x.kind}><i>{x.kind === 'add' ? '+' : '~'}</i>{x.label}<span className="muted"> · {t('asst.type.' + x.type)}</span></li>)}
                {(a.payload.count ?? 0) > 8 && <li className="muted">{t('ag.more', { n: a.payload.count - 8 })}</li>}
                {a.payload.count === 0 && <li className="muted">{t('asst.nothingNew')}</li>}
              </ul>
            )}
            {a.kind === 'guided_query' && (
              <div className="ag-query">
                <p>{a.summary}</p>
                {a.payload.sparql && <>
                  <button className="ag-link" aria-expanded={!!open[i]} onClick={() => setOpen(o => ({ ...o, [i]: !o[i] }))}><Icon name={open[i] ? 'chevron-down' : 'chevron-right'} />SPARQL</button>
                  {open[i] && <pre>{a.payload.sparql}</pre>}</>}
              </div>
            )}
            {a.kind === 'navigate' && <p>{a.summary}</p>}
            {a.error && <p className="ag-err" role="alert"><Icon name="triangle-exclamation" />{a.error}</p>}
            <footer>
              {a.kind === 'ops' && st !== 'applied' && st !== 'undone' && <Button size="sm" variant="primary" icon="check" disabled={busy} onClick={() => void applyAction(pid, msgId, i, a, setP)}>{busy ? '…' : t('ag.apply')}</Button>}
              {a.kind === 'shapes' && st !== 'applied' && st !== 'undone' && <Button size="sm" variant="primary" icon="check" disabled={busy} onClick={() => void applyAction(pid, msgId, i, a, setP)}>{busy ? '…' : t('ag.apply')}</Button>}
              {a.kind === 'proposal' && <Button size="sm" variant="primary" icon="diagram-project" onClick={() => go(pid, 'ontologie')}>{t('asst.toEditor')}</Button>}
              {a.kind === 'guided_query' && <Button size="sm" variant="primary" icon="magnifying-glass-chart" onClick={() => openGuidedQuery(pid, a)}>{t('ag.openQuery')}</Button>}
              {a.kind === 'navigate' && <Button size="sm" variant="primary" icon="arrow-right" onClick={() => go(pid, a.payload.screen)}>{t('ag.open')}</Button>}
              {a.kind === 'shapes' && st === 'applied' && <Button size="sm" icon="rotate-left" disabled={!canUndo} onClick={() => void undoAction(pid, msgId, i, setP)}>{t('ag.undo')}</Button>}
              {a.kind === 'ops' && st === 'applied' && <>
                <Button size="sm" icon="rotate-left" disabled={!canUndo} title={canUndo ? undefined : t('ag.undo.no')} onClick={() => void undoAction(pid, msgId, i, setP)}>{t('ag.undo')}</Button>
                <Button size="sm" variant="ghost" icon="diagram-project" onClick={() => go(pid, 'ontologie')}>{t('ag.seeEditor')}</Button></>}
            </footer>
          </section>
        )
      })}
    </div>
  )
}
