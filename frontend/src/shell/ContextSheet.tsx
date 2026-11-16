import { BottomSheet, Icon, Segmented } from '../kit'
import { useI18n } from '../i18n'
import type { Perimeter, Target } from '../api'

/** Cible (Curiosity / Neo4j) et périmètre : actions rares, hors de l'en-tête (L44). */
export function ContextSheet({ open, onClose, target, setTarget, peris, active, pick }: {
  open: boolean; onClose: () => void; target: Target; setTarget: (t: Target) => void; peris: Perimeter[] | null; active: string; pick: (v: string) => void
}) {
  const { t } = useI18n()
  return (
    <BottomSheet open={open} onClose={onClose} title={t('mob.ctx.title')} icon="sliders" initial="half" snaps={['half', 'full']} testid="context-sheet">
      <div className="mctx">
        <div data-ro-write><Segmented label={t('head.target')} value={target} onChange={setTarget} items={[['curiosity', 'Curiosity'], ['neo4j', 'Neo4j']]} /></div>
        <p className="muted">{t('mob.ctx.target.hint')}</p>
        <label className="f"><span><Icon name="crop-simple" /> {t('head.perimeter')}</span>
          <select value={active} onChange={e => pick(e.target.value)} disabled={!peris}>
            <option value="">{t('head.perimeterAll')}</option>{(peris ?? []).map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
        <p className="muted">{t('mob.ctx.peri.hint')}</p>
      </div>
    </BottomSheet>)
}
