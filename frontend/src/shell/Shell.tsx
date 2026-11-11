import { Suspense, useCallback, useEffect, useRef, useState, type FocusEvent, type MouseEvent } from 'react'
import { api, type Perimeter, type Project, type Target } from '../api'
import { Icon, IconButton, Segmented } from '../kit'
import { ErrorView, useToast } from '../ui'
import { useI18n } from '../i18n'
import { Projects } from '../screens/Projects'
import { Settings } from '../screens/Settings'
import { useActiveEndpoint } from '../screens/settings/activeEndpoint'
import { AssistantDock } from '../assistant-global'
import { VersionsNudge } from '../screens/versions/VersionsNudge'
import { TourHost, tour } from '../tour'
import { helpFor, openDoc } from '../lib/docs'
import { ROUTE_SCREEN } from '../assistant-global/context'
import { SCREENS, STEPS } from './registry'
import { useAuth } from '../auth/AuthGate'
import { useTheme } from './theme'
import { Logo } from './Logo'
import { useMedia, useSidePref } from './sidePref'
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
  const auth = useAuth()
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

  // bandeau repliable (L35) : sur mobile le tiroir reste tel quel
  const desk = useMedia('(min-width: 901px)')
  const [sidePref, setSidePref] = useSidePref()
  const collapsed = desk && (sidePref === 'closed' || (sidePref === 'auto' && !!def?.collapseAuto && route.kind === 'project'))
  const toggleSide = useCallback(() => setSidePref(collapsed ? 'open' : 'closed'), [collapsed, setSidePref])
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || e.key.toLowerCase() !== 'b') return
      const el = e.target as HTMLElement | null
      if (el?.closest?.('input, textarea, select, [contenteditable="true"], .cm-editor, [role=dialog]')) return
      e.preventDefault(); toggleSide()
    }
    addEventListener('keydown', f); return () => removeEventListener('keydown', f)
  }, [toggleSide])
  // le canevas de l'éditeur se recadre une fois la transition terminée
  const firstSide = useRef(true)
  useEffect(() => {
    if (firstSide.current) { firstSide.current = false; return }
    const ms = matchMedia('(prefers-reduced-motion: reduce)').matches ? 30 : 240
    const id = setTimeout(() => dispatchEvent(new Event('of:side-settled')), ms); return () => clearTimeout(id)
  }, [collapsed])

  // infobulle unique, en position fixe (le conteneur défilant du bandeau la couperait sinon)
  const [tip, setTip] = useState<{ text: string; top: number; left: number } | null>(null)
  const showTip = (e: MouseEvent | FocusEvent) => {
    if (!collapsed) return
    const el = (e.target as HTMLElement).closest<HTMLElement>('[data-tip]'); if (!el) return
    const r = el.getBoundingClientRect(); setTip({ text: el.dataset.tip!, top: r.top + r.height / 2, left: r.right + 8 })
  }
  const hideTip = () => setTip(null)
  useEffect(() => { setTip(null) }, [collapsed, screen, route.kind])
  useEffect(() => { if (!tip) return; const f = (e: KeyboardEvent) => { if (e.key === 'Escape') setTip(null) }; addEventListener('keydown', f); return () => removeEventListener('keydown', f) }, [tip])

  const navItem = (key: string, labelKey: string, icon: string, active: boolean, onClick: () => void, badge?: number) => {
    const label = t(labelKey)
    return (
      <button key={key} aria-current={active ? 'page' : undefined} aria-label={collapsed && badge ? `${label} (${badge})` : label} data-tip={collapsed ? (badge ? `${label} (${badge})` : label) : undefined} onClick={onClick}>
        <Icon name={icon} /><span className="grow lbl">{label}</span>
        {!!badge && <span className="cnt" title={t('nav.pendingTitle')}>{badge}</span>}</button>)
  }

  return (
    <div className={'shell' + (menu ? ' menu-open' : '') + (collapsed ? ' collapsed' : '')}>
      <aside className="side" aria-label={t('nav.menu')} onMouseOver={showTip} onMouseOut={hideTip} onFocus={showTip} onBlur={hideTip} data-collapsed={collapsed ? '1' : '0'}>
        <div className="brand"><Logo variant={collapsed ? 'mark' : 'full'} /></div>
        <nav className="nav" aria-label={t('nav.projectScreens')} data-tour="nav">
          {navItem('projects', 'nav.projets', 'folder-open', route.kind === 'projects', () => { location.hash = '#/' })}
          {p && pid && <>
            <div className="proj-chip"><b title={p.name}>{p.name}</b></div>
            {navItem('tableau', 'nav.tableau', 'gauge-high', screen === 'tableau', () => go('tableau'))}
            {STEPS.map((st, i) => (
              <div className="step-group" key={st} role="group" aria-label={t('step.' + st)}>
                <div className="step-title" data-tip={collapsed ? t('nav.stepTip', { n: i + 1, name: t('step.' + st) }) : undefined}><span className="num">{i + 1}</span><span className="lbl">{t('step.' + st)}</span></div>
                {SCREENS.filter(s => s.step === st).map(s => navItem(s.key, s.labelKey, s.icon, screen === s.key, () => go(s.key), s.badge === 'pending' ? pending : 0))}
              </div>))}
            <div className="step-group tools">
              <div className="step-title"><span className="lbl">{t('step.autres')}</span></div>
              {SCREENS.filter(s => !s.step && s.key !== 'tableau').map(s => navItem(s.key, s.labelKey, s.icon, screen === s.key, () => go(s.key)))}
            </div>
          </>}
        </nav>
        <div className="side-foot">
          {navItem('settings', 'nav.parametres', 'gear', route.kind === 'settings', () => { location.hash = '#/parametres' })}
          {desk && <button type="button" className="side-toggle" data-testid="side-toggle" aria-expanded={!collapsed} aria-keyshortcuts="Control+B"
            aria-label={t(collapsed ? 'nav.expandTip' : 'nav.collapseTip')} data-tip={collapsed ? t('nav.expandTip') : undefined} onClick={toggleSide}>
            <Icon name={collapsed ? 'angles-right' : 'angles-left'} /><span className="grow lbl">{t(collapsed ? 'nav.expand' : 'nav.collapse')}</span></button>}
        </div>
        {tip && <div className="side-tip" role="tooltip" style={{ top: tip.top, left: tip.left }}>{tip.text}</div>}
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
          {p && pid && <IconButton icon="circle-question" label={t('docs.helpBtn')} data-testid="help-btn" onClick={() => { const h = helpFor(ROUTE_SCREEN[screen]?.name ?? screen); openDoc(pid, h.page, h.anchor) }} />}
          <IconButton icon="route" label={t('tour.btn')} onClick={() => void tour.start()} />
          <IconButton icon={themeIcon} label={t('head.theme.' + themePref)} onClick={cycleTheme} />
          {auth.enabled && <button type="button" className="btn sm ghost logout" data-testid="logout" title={auth.user ?? ''} onClick={() => void auth.logout()}><Icon name="right-from-bracket" /><span>{t('auth.logout')}</span></button>}
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
      {p && pid && <VersionsNudge p={p} setP={setP} screen={screen} />}
      {p && pid && <AssistantDock p={p} setP={setP} target={target} screen={screen} perimeter={activePeri || null} />}
    </div>
  )
}
