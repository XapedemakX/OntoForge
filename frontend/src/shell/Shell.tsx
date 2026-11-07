import { Suspense, useCallback, useEffect, useState } from 'react'
import { api, type Perimeter, type Project, type Target } from '../api'
import { Icon, IconButton, Segmented } from '../kit'
import { ErrorView, useToast } from '../ui'
import { useI18n } from '../i18n'
import { Projects } from '../screens/Projects'
import { Settings } from '../screens/Settings'
import { useActiveEndpoint } from '../screens/settings/activeEndpoint'
import { AssistantDock } from '../assistant-global'
import { TourHost, tour } from '../tour'
import { SCREENS, STEPS } from './registry'
import { useTheme } from './theme'
import { Logo } from './Logo'
import type { ScreenProps } from './types'

type Route = { kind: 'projects' } | { kind: 'settings' } | { kind: 'project'; id: string; screen: string }
function parseHash(): Route {
  const h = location.hash
  if (h.startsWith('#/parametres')) return { kind: 'settings' }
  const m = h.match(/^#\/projet\/([^/]+)(?:\/([\w-]+))?/)
  return m ? { kind: 'project', id: decodeURIComponent(m[1]), screen: m[2] || 'tableau' } : { kind: 'projects' }
}

export function Shell() {
  const { t } = useI18n()
  const toast = useToast()
  const [route, setRoute] = useState<Route>(parseHash())
  const [p, setP] = useState<Project | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const [target, setTargetState] = useState<Target>('curiosity')
  const [pending, setPending] = useState(0)
  const [menu, setMenu] = useState(false)
  const [themePref, cycleTheme] = useTheme()
  const [peris, setPeris] = useState<Perimeter[] | null>(null)
  const [activePeri, setActivePeri] = useState<string>('')
  const pid = route.kind === 'project' ? route.id : null
  const screen = route.kind === 'project' ? route.screen : ''

  // la visite guidée ouvre le tiroir de navigation sur mobile
  useEffect(() => { const f = (e: Event) => setMenu(!!(e as CustomEvent).detail?.open); addEventListener('ontoforge:tour-menu', f); return () => removeEventListener('ontoforge:tour-menu', f) }, [])
  useEffect(() => { const f = () => { setRoute(parseHash()); setMenu(false) }; addEventListener('hashchange', f); return () => removeEventListener('hashchange', f) }, [])
  useEffect(() => {
    setErr(null)
    if (!pid) { setP(null); return }
    if (p?.id === pid) return
    api.getProject(pid).then(x => { setP(x); setTargetState(x.target); setActivePeri((x as { active_perimeter?: string | null }).active_perimeter ?? '') }).catch(e => { setErr(e); setP(null) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid])
  useEffect(() => { if (!pid) { setPeris(null); return } api.perimeters(pid).then(setPeris).catch(() => setPeris(null)) }, [pid, screen])
  useEffect(() => {
    if (!p) { setPending(0); return }
    api.analyze(p.id, target).then(pg => setPending(pg.findings.filter(f => f.severity !== 'auto' && !f.chosen).length)).catch(() => setPending(0))
  }, [p?.id, p?.updated_at, target, screen])

  const setTarget = useCallback((x: Target) => {
    setTargetState(x)
    setP(prev => { if (prev) api.putProject({ ...prev, target: x }).then(setP).catch(() => toast(t('common.error'))); return prev })
  }, [toast, t])
  const pickPeri = (v: string) => { setActivePeri(v); if (pid) api.setActivePerimeter(pid, v || null).catch(() => toast(t('common.error'))); dispatchEvent(new CustomEvent('of:perimeter', { detail: v })) }
  // l'éditeur graphique (L9) signale un périmètre créé ou activé
  useEffect(() => {
    const onActive = (e: Event) => setActivePeri((e as CustomEvent<string>).detail ?? '')
    const onList = () => { if (pid) api.perimeters(pid).then(setPeris).catch(() => {}) }
    addEventListener('of:perimeter', onActive); addEventListener('of:perimeters', onList)
    return () => { removeEventListener('of:perimeter', onActive); removeEventListener('of:perimeters', onList) }
  }, [pid])

  const go = (s: string) => { location.hash = `#/projet/${encodeURIComponent(pid!)}/${s}` }
  const sp: ScreenProps | null = p ? { p, setP, target, setTarget } : null
  const def = SCREENS.find(s => s.key === screen)
  const endpoint = useActiveEndpoint(route.kind)  // écoute l'événement « ontoforge:endpoint-changed » des Paramètres
  const themeIcon = themePref === 'system' ? 'circle-half-stroke' : themePref === 'light' ? 'sun' : 'moon'

  const navItem = (key: string, labelKey: string, icon: string, active: boolean, onClick: () => void, badge?: number) => (
    <button key={key} aria-current={active ? 'page' : undefined} onClick={onClick}><Icon name={icon} /><span className="grow">{t(labelKey)}</span>
      {!!badge && <span className="cnt" title={t('nav.pendingTitle')}>{badge}</span>}</button>)

  return (
    <div className={'shell' + (menu ? ' menu-open' : '')}>
      <aside className="side" aria-label={t('nav.menu')}>
        <div className="brand"><Logo /></div>
        <nav className="nav" aria-label={t('nav.projectScreens')} data-tour="nav">
          {navItem('projects', 'nav.projets', 'folder-open', route.kind === 'projects', () => { location.hash = '#/' })}
          {p && pid && <>
            <div className="proj-chip"><b title={p.name}>{p.name}</b></div>
            {navItem('tableau', 'nav.tableau', 'gauge-high', screen === 'tableau', () => go('tableau'))}
            {STEPS.map((st, i) => (
              <div className="step-group" key={st}>
                <div className="step-title"><span className="num">{i + 1}</span>{t('step.' + st)}</div>
                {SCREENS.filter(s => s.step === st).map(s => navItem(s.key, s.labelKey, s.icon, screen === s.key, () => go(s.key), s.badge === 'pending' ? pending : 0))}
              </div>))}
            <div className="step-group">
              <div className="step-title">{t('step.autres')}</div>
              {SCREENS.filter(s => !s.step && s.key !== 'tableau').map(s => navItem(s.key, s.labelKey, s.icon, screen === s.key, () => go(s.key)))}
            </div>
          </>}
        </nav>
        <div className="side-foot">
          {navItem('settings', 'nav.parametres', 'gear', route.kind === 'settings', () => { location.hash = '#/parametres' })}
        </div>
      </aside>
      {menu && <button className="scrim" aria-label={t('common.close')} onClick={() => setMenu(false)} />}
      <div className="main">
        <header className="topbar">
          <IconButton className="menu-btn" icon="bars" label={t('nav.menu')} onClick={() => setMenu(m => !m)} />
          <Logo variant="mark" className="logo-top" />
          <div className="crumb">{p && pid ? <><b title={p.name}>{p.name}</b>{def && <span className="muted"> / {t(def.labelKey)}</span>}</> : <b>{route.kind === 'settings' ? t('nav.parametres') : t('common.projects')}</b>}</div>
          <span className="grow" />
          {p && <>
            <span className="tour-wrap" data-tour="target"><Segmented label={t('head.target')} value={target} onChange={setTarget} items={[['curiosity', 'Curiosity'], ['neo4j', 'Neo4j']]} /></span>
            <label className="peri" title={t('head.perimeter')}><Icon name="crop-simple" /><span className="sr">{t('head.perimeter')}</span>
              <select value={activePeri} onChange={e => pickPeri(e.target.value)} disabled={!peris}>
                <option value="">{t('head.perimeterAll')}</option>{(peris ?? []).map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          </>}
          <a className={'endpoint' + (endpoint ? ' on' : '')} href="#/parametres" title={endpoint?.url ?? t('head.sparqlNone')}>
            <Icon name="database" /><span>{endpoint ? (endpoint.name || endpoint.url.replace(/^https?:\/\//, '')) : t('head.sparqlNone')}</span></a>
          <IconButton icon="route" label={t('tour.btn')} onClick={() => void tour.start()} />
          <IconButton icon={themeIcon} label={t('head.theme.' + themePref)} onClick={cycleTheme} />
        </header>
        <main className={'content' + (def?.fullBleed ? ' bleed' : '')}>
          {def?.editing && <div className="notice soon mobile-only">{t('head.mobileReadOnly')}</div>}
          {route.kind === 'projects' && <Projects />}
          {route.kind === 'settings' && <Settings />}
          {route.kind === 'project' && err != null && <div className="page"><ErrorView error={err} what={t('common.projects')} /></div>}
          {sp && (def ? <Suspense key={def.key} fallback={<div className="page muted">…</div>}>{def.render(sp)}</Suspense> : <div className="page"><ErrorView error={new Error('?')} /></div>)}
        </main>
      </div>
      <TourHost />
      {p && pid && <AssistantDock p={p} setP={setP} target={target} screen={screen} perimeter={activePeri || null} />}
    </div>
  )
}
