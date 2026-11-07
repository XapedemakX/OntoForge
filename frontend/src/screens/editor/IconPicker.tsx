import { useEffect, useState } from 'react'
import { Icon } from '../../kit'
import { useI18n } from '../../i18n'
import { eapi, type IconDef } from './types'

/** Sélecteur d'icône : recherche dans le catalogue /icons (accents ignorés). */
export function IconPicker({ value, onPick, onClose }: { value: string | null; onPick: (id: string | null) => void; onClose: () => void }) {
  const { t, lang } = useI18n()
  const [q, setQ] = useState(''); const [list, setList] = useState<IconDef[]>([])
  useEffect(() => { const h = setTimeout(() => eapi.icons(q).then(r => setList(r.icons)).catch(() => setList([])), 120); return () => clearTimeout(h) }, [q])
  useEffect(() => { const f = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }; addEventListener('keydown', f); return () => removeEventListener('keydown', f) }, [onClose])
  return (
    <div className="of-pop of-icons" role="dialog" aria-label={t('ed.icon.title')}>
      <div className="row"><input type="text" autoFocus className="grow" placeholder={t('ed.icon.search')} value={q} onChange={e => setQ(e.target.value)} />
        <button type="button" className="btn ghost sm" onClick={() => onPick(null)} disabled={!value}>{t('ed.icon.none')}</button></div>
      <div className="of-icongrid">
        {list.map(i => <button key={i.id} type="button" className={i.id === value ? 'on' : ''} title={i.label[lang]} aria-label={i.label[lang]} onClick={() => onPick(i.id)}><Icon name={i.id} /></button>)}
        {!list.length && <span className="muted">{t('ed.icon.empty')}</span>}
      </div>
    </div>
  )
}
