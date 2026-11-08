// Légende flottante de l'éditeur (L26) : ne montre que les encodages présents dans la vue, selon le mode d'affichage.
import { Icon, IconButton } from '../../kit'
import { useT } from '../../i18n'
import { CSS_PAL } from './glyphs'
import { LEGEND, LEGEND_H, LEGEND_W, type LegendEntry, type LegendFlags } from './legendDefs'
import type { LegendState, Mode } from './prefs'

type T = (k: string, p?: Record<string, string | number>) => string
/** Mots affichés dans les mini-dessins (traduits). */
export const legendWords = (t: T): Record<string, string> => ({
  abs: t('lg.w.abs'), dep: t('lg.w.dep'), inv: t('lg.w.inv'), ext: t('lg.w.ext'), subOf: t('lg.w.subOf'), fn: t('lg.w.fn'), tr: t('lg.w.tr'), disj: t('lg.w.disj'), cls: t('lg.w.cls'), has: t('lg.w.has'), name: t('lg.w.name'), extb: t('lg.w.extb'), depn: t('lg.w.depn'),
})
export function legendEntries(mode: Mode, f: LegendFlags): LegendEntry[] {
  return LEGEND.filter(e => e.modes.includes(mode) && e.show(f))
}
export const GROUPS: LegendEntry['group'][] = ['nodes', 'links', 'states']

export function Legend({ mode, flags, state, setState }: { mode: Mode; flags: LegendFlags; state: LegendState; setState: (s: LegendState) => void }) {
  const t = useT()
  const entries = legendEntries(mode, flags); const words = legendWords(t)
  if (state === 'closed') return null
  return (
    <aside className={'of-legend' + (state === 'folded' ? ' folded' : '')} aria-label={t('lg.title')} data-tour="ed-legend" data-testid="legend-panel">
      <header>
        <Icon name="circle-info" /><b className="grow">{t('lg.title')}<small>{t(mode === 'vowl' ? 'lg.mode.vowl' : 'lg.mode.classic')}</small></b>
        <IconButton icon={state === 'folded' ? 'chevron-down' : 'chevron-up'} label={t(state === 'folded' ? 'lg.unfold' : 'lg.fold')} aria-expanded={state !== 'folded'} onClick={() => setState(state === 'folded' ? 'open' : 'folded')} />
        <IconButton icon="xmark" label={t('lg.close')} onClick={() => setState('closed')} />
      </header>
      {state === 'open' && <div className="of-lg-body">
        {GROUPS.map(g => { const es = entries.filter(e => e.group === g); return es.length ? (
          <section key={g}><h4>{t('lg.g.' + g)}</h4>
            <ul>{es.map(e => <li key={e.id} data-legend={e.id}>
              <svg width={LEGEND_W} height={LEGEND_H} viewBox={`-2 -2 ${LEGEND_W + 4} ${LEGEND_H + 4}`} role="img" aria-label={t(`lg.${e.id}.t`)} dangerouslySetInnerHTML={{ __html: e.draw(CSS_PAL, words) }} />
              <span><b>{t(`lg.${e.id}.t`)}</b><small>{t(`lg.${e.id}.d`)}</small></span></li>)}</ul></section>) : null })}
        <p className="of-lg-note"><Icon name="hand-pointer" />{t(mode === 'vowl' ? 'lg.note.vowl' : 'lg.note.classic')}</p>
        {mode === 'vowl' && flags.datatype && <p className="of-lg-note ro"><Icon name="lock" />{t('lg.note.dtro')}</p>}
      </div>}
    </aside>
  )
}
