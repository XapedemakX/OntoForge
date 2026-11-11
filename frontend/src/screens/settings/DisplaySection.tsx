import { Card, Icon, Segmented } from '../../kit'
import { useI18n } from '../../i18n'
import { useSidePref, type SidePref } from '../../shell/sidePref'

/** Réglage « Affichage » : comportement du bandeau latéral (mémorisé dans ce navigateur, pas sur le serveur). */
export function DisplaySection() {
  const { t } = useI18n()
  const [pref, setPref] = useSidePref()
  return (
    <Card title={<><Icon name="table-columns" /> {t('settings.display.title')}</>}>
      <p className="set-hint">{t('settings.display.intro')}</p>
      <div className="set-row" style={{ marginTop: 'var(--s3)' }}>
        <span id="side-pref-l"><b>{t('settings.display.side')}</b></span>
        <Segmented<SidePref> label={t('settings.display.side')} value={pref} onChange={setPref}
          items={[['auto', t('settings.display.auto')], ['open', t('settings.display.open')], ['closed', t('settings.display.closed')]]} />
      </div>
      <p className="set-hint" style={{ marginTop: 'var(--s2)' }}>{t('settings.display.hint.' + pref)}</p>
    </Card>)
}
