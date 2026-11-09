import { useEffect, useState } from 'react'
import { api, type Project, type VersionCheck } from '../../api'
import { Button, Krakie } from '../../kit'
import { useT } from '../../i18n'
import { useDockUi } from '../../assistant-global/store'
import { useToast } from '../../ui'
import './versions.css'

// Annoncée une seule fois par session (onglet) et par projet ; « Plus tard » est mémorisé pour ce projet jusqu'à la prochaine mise à jour de standards.json.
const seen = new Set<string>()
const laterKey = (pid: string) => `ontoforge.versions.later.${pid}`
const seenKey = (pid: string) => `ontoforge.versions.seen.${pid}`
const getS = (k: string, area: 'local' | 'session') => { try { return (area === 'local' ? localStorage : sessionStorage).getItem(k) } catch { return null } }
const setS = (k: string, v: string, area: 'local' | 'session') => { try { (area === 'local' ? localStorage : sessionStorage).setItem(k, v) } catch { /* stockage indisponible */ } }

/** Bulle discrète de Krakie : à l'ouverture d'un projet, appelle versions/check ; n'affiche quelque chose que pour une version obsolète ou en fin de support. */
export function VersionsNudge({ p, setP, screen }: { p: Project; setP: (p: Project) => void; screen: string }) {
  const t = useT()
  const toast = useToast()
  const ui = useDockUi()
  const [chk, setChk] = useState<VersionCheck | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    setChk(null)
    let live = true
    api.versionsCheck(p.id).then(c => {
      if (!live || !c.needs_attention) return
      if (seen.has(p.id) || getS(seenKey(p.id), 'session')) return          // déjà annoncée dans cette session
      if (getS(laterKey(p.id), 'local') === c.updated) return                // « plus tard » déjà choisi pour cette version de la référence
      seen.add(p.id); setS(seenKey(p.id), '1', 'session')
      setChk(c)
    }).catch(() => { /* référence indisponible : on ne dit rien */ })
    return () => { live = false }
  }, [p.id])
  if (!chk || ui.open || screen === 'assistant' || screen === 'versions') return null
  const gaps = chk.gaps.filter(g => g.severity !== 'info')
  const canApply = Object.keys(chk.recommended).length > 0
  const later = () => { setS(laterKey(p.id), chk.updated, 'local'); setChk(null) }
  const update = async () => {
    if (!canApply) { location.hash = `#/projet/${encodeURIComponent(p.id)}/versions`; setChk(null); return }
    setBusy(true)
    try { await api.putVersions(p.id, chk.recommended); setP(await api.getProject(p.id)); toast(t('ver.applied')); setChk(null) }
    catch (e) { toast((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="ver-nudge" role="status" aria-live="polite" data-testid="ver-nudge">
      <Krakie pose="inquiete" size={36} float={false} />
      <div>
        <p>{gaps[0]?.message}{gaps.length > 1 ? ' ' + t('ver.nudge.more', { n: gaps.length - 1 }) : ''}</p>
        <div className="acts">
          <Button size="sm" variant="primary" disabled={busy} onClick={() => void update()}>{canApply ? t('ver.nudge.update') : t('ver.nudge.see')}</Button>
          <Button size="sm" disabled={busy} onClick={later}>{t('ver.nudge.later')}</Button>
        </div>
      </div>
    </div>
  )
}
