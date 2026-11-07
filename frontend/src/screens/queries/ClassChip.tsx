import { Icon } from '../../kit'
import { classIcon, classTone } from './classIcon'
import { localName } from './model'

/** Puce de classe : icône teintée + libellé. Réutilisée dans la phrase, la liste de classes et les colonnes. */
export function ClassChip({ iri, label, onClick, active, title, caret, meta }: { iri: string; label: string; meta?: string; onClick?: () => void; active?: boolean; title?: string; caret?: boolean }) {
  const inner = <><span className={`qc-ico ${classTone(iri)}`}><Icon name={classIcon(localName(iri) + ' ' + label)} /></span><span className="qc-lab">{label}</span>{meta && <span className="qc-meta">{meta}</span>}{caret && <Icon name="chevron-down" className="qc-caret" />}</>
  return onClick
    ? <button type="button" className={`qc ${active ? 'on' : ''}`} onClick={onClick} title={title} aria-expanded={caret ? !!active : undefined}>{inner}</button>
    : <span className="qc" title={title}>{inner}</span>
}
