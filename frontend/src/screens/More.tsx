import { Icon, useToast } from '../kit'
import { useI18n } from '../i18n'
import type { ScreenProps } from '../shell/types'
import { SCREENS, STEPS } from '../shell/registry'
import { useAuth } from '../auth/AuthGate'
import { useTheme } from '../shell/theme'
import { AccountMenu } from '../auth/AccountMenu'
import { sendLink } from '../shell/DesktopHint'
import { helpFor, openDoc } from '../lib/docs'
import { ROUTE_SCREEN } from '../assistant-global/context'
import { useActiveEndpoint } from './settings/activeEndpoint'
import { tabOf } from '../shell/MobileTabBar'

/** Menu « Plus » du téléphone (L44) : tout ce qui n'est pas dans la barre d'onglets, la carte métier en tête ; « Sur ordinateur » signale l'édition lourde. */
export function More({ p }: ScreenProps) {
  const { t } = useI18n(); const toast = useToast(); const auth = useAuth()
  const [theme, cycleTheme] = useTheme()
  const endpoint = useActiveEndpoint('project')
  const go = (s: string) => { location.hash = `#/projet/${encodeURIComponent(p.id)}/${s}` }
  const def = (k: string) => SCREENS.find(s => s.key === k)!
  const row = (key: string) => {
    const s = def(key)
    return (
      <li key={key}><button type="button" className="mrow" onClick={() => go(key)} data-screen={key}>
        <span className="ico"><Icon name={s.icon} /></span>
        <span className="tx"><b>{t(s.labelKey)}</b><small>{t('mob.more.sub.' + key)}</small></span>
        {s.desktop && <span className="mtag" title={t('mob.tag.title')}><Icon name="desktop" />{t('mob.tag.desktop')}</span>}
        <Icon name="chevron-right" className="chev" /></button></li>)
  }
  const inMore = (k: string) => { const s = def(k); return tabOf(k) === 'more' && !s.mobileOnly && k !== 'carte-metier' }
  const themeLabel = t('head.theme.' + theme)
  return (
    <div className="page more" data-safe data-testid="more">
      <ul className="mlist first">{row('carte-metier')}</ul>
      {STEPS.map(st => { const ks = SCREENS.filter(s => s.step === st && inMore(s.key)).map(s => s.key); return ks.length > 0 && (
        <section key={st}><h2 className="mh">{t('step.' + st)}</h2><ul className="mlist">{ks.map(row)}</ul></section>) })}
      <section><h2 className="mh">{t('step.autres')}</h2><ul className="mlist">{['assistant'].map(row)}
        <li><button type="button" className="mrow" onClick={() => { const h = helpFor(ROUTE_SCREEN['tableau']?.name ?? 'tableau'); openDoc(p.id, h.page, h.anchor) }}>
          <span className="ico"><Icon name="book-open" /></span><span className="tx"><b>{t('nav.documentation')}</b><small>{t('mob.more.sub.documentation')}</small></span><Icon name="chevron-right" className="chev" /></button></li></ul></section>
      <section><h2 className="mh">{t('mob.more.account')}</h2><ul className="mlist">
        <li><button type="button" className="mrow" onClick={() => { location.hash = '#/parametres' }} data-testid="more-settings"><span className="ico"><Icon name="gear" /></span>
          <span className="tx"><b>{t('nav.parametres')}</b><small>{endpoint ? (endpoint.name || endpoint.url) : t('head.sparqlNone')}</small></span><Icon name="chevron-right" className="chev" /></button></li>
        {auth.enabled && auth.admin && <li><button type="button" className="mrow" onClick={() => { location.hash = '#/administration' }}><span className="ico"><Icon name="user-shield" /></span>
          <span className="tx"><b>{t('nav.admin')}</b></span><Icon name="chevron-right" className="chev" /></button></li>}
        <li><button type="button" className="mrow" onClick={cycleTheme}><span className="ico"><Icon name={theme === 'system' ? 'circle-half-stroke' : theme === 'light' ? 'sun' : 'moon'} /></span>
          <span className="tx"><b>{t('mob.more.theme')}</b><small>{themeLabel}</small></span></button></li>
        {auth.enabled && <li className="macct"><span className="ico"><Icon name="circle-user" /></span><span className="tx"><b>{auth.user}</b><small>{t('mob.more.account.hint')}</small></span><AccountMenu /></li>}
        {auth.enabled && <li><button type="button" className="mrow" data-testid="logout" onClick={() => void auth.logout()}><span className="ico"><Icon name="right-from-bracket" /></span><span className="tx"><b>{t('auth.logout')}</b></span></button></li>}
      </ul></section>
      <section className="mdesk"><Icon name="desktop" /><div><b>{t('mob.more.desktop.t')}</b><p className="muted">{t('mob.more.desktop.d')}</p>
        <button type="button" className="btn" onClick={() => void sendLink(toast, t)}><Icon name="paper-plane" />{t('mob.link')}</button></div></section>
    </div>
  )
}
