import { useEffect, useState } from 'react'
import { api } from '../api'
import { Button, Krakie } from '../kit'
import { useI18n } from '../i18n'
import { Overlay } from './Overlay'
import { buildSteps } from './steps'
import { currentProjectId, getState, isDone, markDone, registerHost, subscribe, tour } from './controller'
import { useSyncExternalStore } from 'react'
import './tour.css'

/** Monté une fois dans la coque : moteur, ?tour=1, proposition au premier projet. */
export function TourHost() {
  const { t } = useI18n()
  useEffect(() => registerHost({
    buildSteps: () => buildSteps(t),
    createDemo: async () => {
      const name = t('tour.demo.name')
      const found = (await api.listProjects().catch(() => [])).find(x => x.name === name)
      const pr = found ?? await api.createProject({ name, sample: 'automaint' })
      location.hash = `#/projet/${encodeURIComponent(pr.id)}/tableau`
      return pr.id
    },
  }), [t])
  useEffect(() => {
    const check = () => {
      if (!/[?&]tour=1\b/.test(location.hash)) return
      history.replaceState(null, '', location.pathname + location.search + location.hash.replace(/[?&]tour=1\b/, ''))
      void tour.start()
    }
    check(); addEventListener('hashchange', check); return () => removeEventListener('hashchange', check)
  }, [])
  return <><Overlay /><Proposal /></>
}

let proposed = false
function Proposal() {
  const { t } = useI18n()
  const st = useSyncExternalStore(subscribe, getState)
  const [show, setShow] = useState(false)
  useEffect(() => {
    const check = () => { if (!proposed && currentProjectId() && !isDone()) { proposed = true; setTimeout(() => { if (!getState().active && !isDone()) setShow(true) }, 2500) } }
    check(); addEventListener('hashchange', check); return () => removeEventListener('hashchange', check)
  }, [])
  useEffect(() => { if (!show) return; const h = setTimeout(() => setShow(false), 25000); return () => clearTimeout(h) }, [show])
  if (!show || st.active) return null
  return (
    <aside className="tour-prop" aria-label={t('tour.prop.t')}>
      <Krakie pose="accueil" size={48} />
      <div className="tour-txt">
        <b>{t('tour.prop.t')}</b>
        <p>{t('tour.prop.d')}</p>
        <div className="tour-btns">
          <Button size="sm" variant="primary" icon="route" onClick={() => { setShow(false); void tour.start() }}>{t('tour.prop.go')}</Button>
          <Button size="sm" variant="ghost" onClick={() => setShow(false)}>{t('tour.prop.later')}</Button>
          <Button size="sm" variant="ghost" onClick={() => { markDone(); setShow(false) }}>{t('tour.prop.never')}</Button>
        </div>
      </div>
    </aside>
  )
}
