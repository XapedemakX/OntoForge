import { Icon } from '../kit'
import { useI18n } from '../i18n'
import { CollabBar } from '../collab/Bar'
import type { CollabState } from '../collab/useCollab'
import { isRootScreen } from './MobileTabBar'
import type { Perimeter, Project, Target } from '../api'
import { AccountMenu } from '../auth/AccountMenu'

/** En-tête court du téléphone (L44) : retour, titre, sous-titre cible · périmètre (ouvre la feuille de contexte), partage. */
export function MobileHeader({ kind, p, pid, screen, labelKey, target, peris, activePeri, collab, onContext }: {
  kind: 'projects' | 'settings' | 'admin' | 'help' | 'project'; p: Project | null; pid: string | null; screen: string; labelKey?: string
  target: Target; peris: Perimeter[] | null; activePeri: string; collab: CollabState; onContext: () => void
}) {
  const { t } = useI18n()
  const home = kind === 'project' && screen === 'tableau'
  const back = kind !== 'projects' && !(kind === 'project' && !home && isRootScreen(screen))
  const goBack = () => {
    if (kind === 'project') location.hash = home ? '#/' : `#/projet/${encodeURIComponent(pid!)}/plus`
    else if (kind === 'help') { if (history.length > 1) history.back(); else location.hash = '#/' }
    else location.hash = '#/'
  }
  const tn = target === 'curiosity' ? 'Curiosity' : 'Neo4j'
  const peri = peris?.find(x => x.id === activePeri)?.name ?? t('head.perimeterAll')
  const title = kind === 'project' ? (home ? (p?.name ?? '…') : screen === 'analyse' ? t('mob.tab.arbitrate') : t(labelKey ?? 'nav.tableau')) : kind === 'settings' ? t('nav.parametres') : kind === 'admin' ? t('nav.admin') : kind === 'help' ? t('nav.documentation') : t('common.projects')
  return (
    <header className="mhead" data-testid="mobile-header">
      {back && <button type="button" className="mback" aria-label={t('mob.back')} onClick={goBack}><Icon name="chevron-left" /></button>}
      <div className="mtitle">
        <h1 title={title}>{title}</h1>
        {kind === 'project' && (home
          ? <button type="button" className="msub ctx" onClick={onContext} aria-haspopup="dialog" data-testid="ctx-btn">{tn} · {peri}<Icon name="chevron-down" /></button>
          : <span className="msub">{p?.name} · {tn}</span>)}
      </div>
      {kind === 'project' && pid && <CollabBar pid={pid} collab={collab} />}
      {kind === 'projects' && <><a className="btn ghost iconly mgear" href="#/parametres" aria-label={t('nav.parametres')}><Icon name="gear" /></a><AccountMenu /></>}
    </header>
  )
}
