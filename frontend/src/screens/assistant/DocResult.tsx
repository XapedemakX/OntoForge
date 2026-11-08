import { Button, Icon } from '../../kit'
import { useI18n } from '../../i18n'
import type { DocMsg } from '../../assistant-global/store'
import { LintSummary } from './ProposalCards'
import './doc.css'

/** Résultat d'un amorçage depuis un document, dans la conversation : origine, questions de compétence (couvert / non couvert), lint W3C. */
export function DocResult({ doc, onReview }: { doc: DocMsg; onReview?: () => void }) {
  const { t } = useI18n()
  const covered = doc.questions.filter(q => q.covered).length
  return (
    <section className="dr" aria-label={t('doc.q.title')}>
      <div className="dr-head">
        <Icon name="file-lines" /><b>{doc.name}</b>
        <span className="muted">{t('doc.pages', { n: doc.pages })}</span>
        <span className={'dr-engine' + (doc.approximate ? ' approx' : '')}>{doc.approximate ? t('doc.approx') : doc.provider}</span>
      </div>
      <h3 className="dr-h"><Icon name="circle-question" />{t('doc.q.title')} <span className="muted">{t('doc.q.sub', { covered, n: doc.questions.length })}</span></h3>
      <ol className="dr-q">
        {doc.questions.map(q => (
          <li key={q.id} className={q.covered ? 'ok' : 'ko'}>
            <span className="dr-qt">{q.text}</span>
            <span className={'dr-badge ' + (q.covered ? 'ok' : 'ko')}><Icon name={q.covered ? 'check' : 'circle-exclamation'} />{q.covered ? t('doc.q.covered') : t('doc.q.uncovered')}</span>
            <span className="muted dr-terms">{q.covered ? t('doc.q.terms', { terms: q.terms.join(', ') }) : t('doc.q.none')}</span>
          </li>
        ))}
      </ol>
      <LintSummary lint={doc.lint} skipped={doc.skipped} />
      {onReview && doc.items > 0 && <Button size="sm" variant="primary" icon="arrow-right" onClick={onReview}>{t('doc.review')}</Button>}
    </section>
  )
}
