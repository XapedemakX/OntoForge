import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type AccessView, type PresenceView } from '../api'
import { getRev, setCurrentProject } from './rev'

const BEAT_MS = 20_000   // battement de présence ; le serveur oublie un compte après 60 s sans battement

export interface CollabState {
  role: 'owner' | 'editor' | 'reader' | null
  readOnly: boolean
  presence: PresenceView | null
  /** Quelqu'un d'autre a enregistré depuis le dernier chargement de ce projet. */
  stale: { actor: string } | null
  beat: () => void
  dismissStale: () => void
}

/** Présence (battement toutes les ~20 s) et sondage léger de la version du projet ouvert. Pas de WebSocket. */
export function useCollab(pid: string | null): CollabState {
  const [presence, setPresence] = useState<PresenceView | null>(null)
  const [dismissed, setDismissed] = useState<number>(-1)
  const live = useRef(true)
  useEffect(() => { setCurrentProject(pid); return () => setCurrentProject(null) }, [pid])
  const beat = useCallback(() => {
    if (!pid) return
    api.presence(pid).then(v => { if (live.current) setPresence(v) }).catch(() => { /* accès retiré ou serveur absent : on réessaie au prochain battement */ })
  }, [pid])
  useEffect(() => {
    live.current = true
    setPresence(null); setDismissed(-1)
    if (!pid) return
    beat()
    const id = setInterval(() => { if (document.visibilityState !== 'hidden') beat() }, BEAT_MS)
    const vis = () => { if (document.visibilityState === 'visible') beat() }
    document.addEventListener('visibilitychange', vis)
    return () => { live.current = false; clearInterval(id); document.removeEventListener('visibilitychange', vis) }
  }, [pid, beat])
  const known = pid ? getRev(pid) : undefined
  const stale = presence && known !== undefined && presence.rev > known && presence.last_actor && presence.last_actor !== presence.me && presence.rev > dismissed
    ? { actor: presence.last_actor } : null
  const role = presence?.role ?? null
  return { role, readOnly: role === 'reader', presence, stale, beat, dismissStale: () => setDismissed(presence?.rev ?? -1) }
}

export async function loadAccess(pid: string): Promise<AccessView> { return api.access(pid) }
