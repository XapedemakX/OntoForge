import { useEffect } from 'react'
import { Icon } from '../kit'
import { useI18n } from '../i18n'

/** Barre d'onglets du téléphone (L44) : Accueil · Ontologie · Requêtes · Arbitrer · Plus. */
export const ONTO_KEY = 'ontoforge.mobile.onto'
const readOnto = () => { try { return localStorage.getItem(ONTO_KEY) === 'ontologie-liste' ? 'ontologie-liste' : 'ontologie' } catch { return 'ontologie' } }
export type TabKey = 'home' | 'onto' | 'queries' | 'arbitrate' | 'more'
const ROOT: Record<string, TabKey> = { tableau: 'home', ontologie: 'onto', 'ontologie-liste': 'onto', requetes: 'queries', analyse: 'arbitrate', plus: 'more' }
export const tabOf = (screen: string): TabKey => ROOT[screen] ?? 'more'
/** Écrans qui sont la racine d'un onglet (pas de bouton retour) ; les autres reviennent au menu « Plus ». */
export const isRootScreen = (screen: string) => screen in ROOT

export function MobileTabBar({ pid, screen, pending }: { pid: string; screen: string; pending: number }) {
  const { t } = useI18n()
  useEffect(() => { if (screen === 'ontologie' || screen === 'ontologie-liste') { try { localStorage.setItem(ONTO_KEY, screen) } catch { /* ignoré */ } } }, [screen])
  const cur = tabOf(screen)
  const go = (s: string) => { location.hash = `#/projet/${encodeURIComponent(pid)}/${s}` }
  const items: { k: TabKey; icon: string; label: string; to: () => string; badge?: number }[] = [
    { k: 'home', icon: 'gauge-high', label: t('mob.tab.home'), to: () => 'tableau' },
    { k: 'onto', icon: 'sitemap', label: t('nav.ontologie'), to: readOnto },
    { k: 'queries', icon: 'magnifying-glass-chart', label: t('nav.requetes'), to: () => 'requetes' },
    { k: 'arbitrate', icon: 'scale-balanced', label: t('mob.tab.arbitrate'), to: () => 'analyse', badge: pending },
    { k: 'more', icon: 'ellipsis', label: t('mob.tab.more'), to: () => 'plus' },
  ]
  return (
    <nav className="mtabs" aria-label={t('mob.tabs')} data-testid="tabbar">
      {items.map(i => (
        <button key={i.k} type="button" data-tab={i.k} aria-current={cur === i.k ? 'page' : undefined} aria-label={i.badge ? `${i.label} (${i.badge})` : i.label}
          onClick={() => { if (cur !== i.k || screen !== i.to()) go(i.to()) }}>
          <span className="ic"><Icon name={i.icon} />{!!i.badge && <b className="mbadge" data-testid="pending-badge" title={t('nav.pendingTitle')}>{i.badge > 99 ? '99+' : i.badge}</b>}</span>
          <span className="lb">{i.label}</span>
        </button>))}
    </nav>
  )
}
