import { Button, Card, Krakie } from '../kit'
import { useT } from '../i18n'
import { tour } from './controller'

/** Carte du tableau de bord : lance la visite guidée. */
export function TourCard() {
  const t = useT()
  return (
    <Card title={t('tour.card.t')} className="tour-card">
      <div className="row" style={{ alignItems: 'flex-start', gap: 14 }}>
        <Krakie pose="graphe" size={64} />
        <div className="col" style={{ flex: 1, minWidth: 0, gap: 10 }}>
          <p className="muted" style={{ margin: 0 }}>{t('tour.card.d')}</p>
          <div><Button variant="primary" icon="route" onClick={() => void tour.start()}>{t('tour.card.go')}</Button></div>
        </div>
      </div>
    </Card>
  )
}
