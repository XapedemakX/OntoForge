import { useEffect, useState } from 'react'
import { Button, Icon } from '../kit'
import { useI18n } from '../i18n'
import { useToast } from '../ui'
import type { ConflictInfo } from './rev'
import type { CollabState } from './useCollab'

export const RELOAD = 'ontoforge:reload-project'

/** Bandeau « X a modifié le projet — recharger » (sondage de version, sans WebSocket). */
export function StaleBanner({ collab }: { collab: CollabState }) {
  const { t } = useI18n()
  if (!collab.stale) return null
  return (
    <div className="notice warn collab-banner collab-keep" role="status" data-testid="stale-banner">
      <Icon name="arrows-rotate" /><span className="grow">{t('collab.stale', { who: collab.stale.actor })}</span>
      <Button size="sm" variant="primary" data-testid="stale-reload" onClick={() => dispatchEvent(new Event(RELOAD))}>{t('collab.reload')}</Button>
      <Button size="sm" variant="ghost" onClick={collab.dismissStale}>{t('common.close')}</Button>
    </div>
  )
}

/** Conflit d'enregistrement (409) : rien n'est écrasé ; l'utilisateur recharge puis, si c'est sans risque, son changement est rejoué. */
export function ConflictDialog({ reload }: { reload: () => Promise<void> }) {
  const { t } = useI18n()
  const toast = useToast()
  const [c, setC] = useState<ConflictInfo | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    const f = (e: Event) => setC((e as CustomEvent<ConflictInfo>).detail)
    const ro = () => toast(t('collab.ro.refused'))
    addEventListener('ontoforge:conflict', f); addEventListener('ontoforge:readonly', ro)
    return () => { removeEventListener('ontoforge:conflict', f); removeEventListener('ontoforge:readonly', ro) }
  }, [toast, t])
  if (!c) return null
  const go = async () => {
    setBusy(true)
    try {
      await reload()
      if (c.replay) {
        const r = await fetch(c.replay.url, { method: c.replay.method, headers: { 'Content-Type': c.replay.contentType }, body: c.replay.body })
        if (r.ok) { toast(t('collab.replayed')); await reload() } else toast(t('collab.replay.failed'))
      } else toast(t('collab.reloaded.manual'))
      setC(null)
    } catch { toast(t('common.error')) } finally { setBusy(false) }
  }
  return (
    <div className="collab-scrim">
      <div className="collab-panel card" role="alertdialog" aria-modal="true" aria-labelledby="conf-title" data-testid="conflict-dialog">
        <div className="hd"><b id="conf-title"><Icon name="triangle-exclamation" /> {t('collab.conflict.title')}</b></div>
        <div className="collab-body">
          <p data-testid="conflict-msg">{c.detail}</p>
          <p className="muted">{c.replay ? t('collab.conflict.replay') : t('collab.conflict.noreplay')}</p>
          <div className="row"><Button variant="primary" data-testid="conflict-reload" disabled={busy} onClick={() => void go()}>{c.replay ? t('collab.reapply') : t('collab.reload')}</Button>
            <Button variant="ghost" disabled={busy} onClick={() => setC(null)}>{t('common.close')}</Button></div>
        </div>
      </div>
    </div>
  )
}
