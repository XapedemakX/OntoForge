import { api } from '../api'
import { Card } from '../kit'
import { useI18n } from '../i18n'
import { useLoad } from '../ui'
import { useAuth } from '../auth/AuthGate'

/** Journal d'activité du projet : qui a fait quoi, et quand. Affiché quand l'authentification est activée (sinon il n'y a qu'un seul utilisateur). */
export function ActivityCard({ pid, rev }: { pid: string; rev: string }) {
  const { t, lang } = useI18n()
  const auth = useAuth()
  const log = useLoad(() => (auth.enabled ? api.activity(pid) : Promise.resolve([])), [pid, rev, auth.enabled])
  if (!auth.enabled) return null
  const fmt = (iso: string) => new Date(iso).toLocaleString(lang, { dateStyle: 'short', timeStyle: 'short' })
  const known = new Set(['create', 'share', 'role', 'unshare', 'leave', 'transfer', 'migrate', 'project', 'ontology', 'shapes', 'import', 'decisions', 'perimeters', 'business_map', 'files', 'queries', 'store', 'versions', 'edit'])
  return (
    <Card title={t('collab.activity')}>
      {(log.data ?? []).length === 0 ? <p className="muted">{t('collab.activity.none')}</p> : (
        <ul className="collab-activity" data-testid="activity">
          {(log.data ?? []).slice(0, 12).map((e, i) => (
            <li key={i}><span className="muted">{fmt(e.at)}</span> <b>{e.user}</b> {t('collab.act.' + (known.has(e.action) ? e.action : 'edit'), { login: e.detail?.login ?? '', role: e.detail?.role ? t('collab.role.' + e.detail.role) : '' })}</li>))}
        </ul>)}
    </Card>
  )
}
