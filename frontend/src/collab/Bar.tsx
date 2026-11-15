import { useState } from 'react'
import { Icon } from '../kit'
import { useI18n } from '../i18n'
import { useAuth } from '../auth/AuthGate'
import type { PresenceView } from '../api'
import type { CollabState } from './useCollab'
import { SharePanel } from './SharePanel'
import './collab.css'

export function initials(login: string): string {
  const parts = login.split(/[\s._-]+/).filter(Boolean)
  const s = parts.length > 1 ? parts[0][0] + parts[1][0] : login.slice(0, 2)
  return s.toUpperCase()
}
function hue(login: string): number { let h = 0; for (const c of login) h = (h * 31 + c.charCodeAt(0)) % 360; return h }

export function Dot({ user, title, me }: { user: string; title: string; me?: boolean }) {
  return <span className={'collab-dot' + (me ? ' me' : '')} style={{ background: `hsl(${hue(user)} 45% 36%)` }} title={title} aria-label={title} role="img" data-user={user}>{initials(user)}</span>
}

export function PresenceDots({ presence }: { presence: PresenceView | null }) {
  const { t } = useI18n()
  if (!presence || presence.present.length === 0) return null
  return (
    <span className="collab-dots" data-testid="presence" aria-label={t('collab.presence')}>
      {presence.present.map(w => <Dot key={w.user} user={w.user} me={w.me} title={`${w.user}${w.me ? ' ' + t('collab.you') : ''} · ${t('collab.role.' + w.role)}`} />)}
    </span>
  )
}

/** Barre de collaboration de l'en-tête du projet : présence, « lecture seule », bouton Partager. */
export function CollabBar({ pid, collab }: { pid: string; collab: CollabState }) {
  const { t } = useI18n()
  const auth = useAuth()
  const [open, setOpen] = useState(false)
  return (
    <>
      {auth.enabled && <PresenceDots presence={collab.presence} />}
      {collab.readOnly && <span className="badge collab-ro collab-keep" data-testid="readonly-chip" title={t('collab.ro.hint')}><Icon name="lock" /> {t('collab.ro')}</span>}
      <button type="button" className="btn sm collab-keep" data-testid="share-btn" data-tour="share" onClick={() => setOpen(true)} aria-haspopup="dialog">
        <Icon name="user-group" /><span>{t('collab.share')}</span></button>
      {open && <SharePanel pid={pid} onClose={() => { setOpen(false); collab.beat() }} />}
    </>
  )
}
