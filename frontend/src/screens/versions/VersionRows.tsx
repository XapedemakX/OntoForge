import { Select } from '../../kit'
import { useT } from '../../i18n'
import type { VersionKey, VersionRow } from '../../api'

const DEFAULT = '__default'

/** Tableau des versions : un sélecteur par famille, avec le statut de la valeur choisie.
 * `onChange(key, valeur)` : `null` = revenir au défaut global (projet seulement, `allowDefault`). */
export function VersionRows({ rows, values, allowDefault, onChange, disabled }: {
  rows: VersionRow[]; values: Partial<Record<VersionKey, string | null>>; allowDefault?: boolean
  onChange: (key: VersionKey, value: string | null) => void; disabled?: boolean
}) {
  const t = useT()
  return (
    <table className="set-table ver-table">
      <thead><tr><th>{t('ver.col.family')}</th><th>{t('ver.col.version')}</th><th>{t('ver.col.status')}</th><th>{t('ver.col.note')}</th></tr></thead>
      <tbody>
        {rows.map(r => {
          const val = values[r.key]
          const cur = val === null || val === undefined ? (allowDefault ? null : r.value) : val
          const shown = cur ?? r.value                      // valeur effective (le défaut quand rien n'est fixé)
          const choice = r.choices.find(c => c.id === shown)
          const sup = choice?.support ?? 'unknown'
          const opts = [...(allowDefault ? [{ value: DEFAULT, label: t('ver.useDefault', { v: r.value }) }] : []), ...r.choices.map(c => ({ value: c.id, label: c.label }))]
          return (
            <tr key={r.key} data-version={r.key}>
              <td><b>{r.family}</b></td>
              <td><Select aria-label={t('ver.pick', { f: r.family })} disabled={disabled} value={cur === null ? DEFAULT : cur} options={opts}
                onChange={e => onChange(r.key, e.target.value === DEFAULT ? null : e.target.value)} /></td>
              <td>
                <span className={'set-chip ver-st ' + (sup === 'recommended' ? 'on' : sup === 'obsolete' || sup === 'end_of_support' ? 'warn' : '')} data-support={sup}>{t('ver.st.' + sup)}</span>
                {choice?.maturity && choice.maturity !== 'REC' && <span className="set-chip" title={t('ver.mat.' + choice.maturity)}> {choice.maturity}</span>}
                {allowDefault && <span className="muted ver-origin"> · {cur === null ? t('ver.origin.default') : t('ver.origin.project')}</span>}
              </td>
              <td className="muted ver-note">{choice?.note || (sup === 'unknown' ? t('ver.unknown') : '')}</td>
            </tr>)
        })}
      </tbody>
    </table>
  )
}
