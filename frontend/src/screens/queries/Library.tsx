import { useState } from 'react'
import { Button, Icon, IconButton } from '../../kit'
import { useT } from '../../i18n'
import { useLoad, useToast, ErrorView } from '../../ui'
import { qapi, type Competency, type SavedQuery } from './qapi'

const when = (iso: string, lang: string) => { try { return new Date(iso).toLocaleDateString(lang, { day: 'numeric', month: 'short' }) } catch { return '' } }

export function Library({ pid, lang, target, reloadKey, onOpen, onRun, onFree, canSave, onSave, activeId }: {
  pid: string; lang: string; target: string; reloadKey: number; activeId: string | null
  onOpen: (q: SavedQuery) => void; onRun: (q: SavedQuery) => void; onFree: (sparql: string) => void
  canSave: boolean; onSave: (name: string) => Promise<void>
}) {
  const t = useT(); const toast = useToast()
  const saved = useLoad(() => qapi.saved(pid), [pid, reloadKey])
  const comp = useLoad(() => qapi.competency(pid, target), [pid, target, reloadKey])
  const [name, setName] = useState(''); const [naming, setNaming] = useState(false)
  const [renaming, setRenaming] = useState<string | null>(null); const [rname, setRname] = useState('')
  const [del, setDel] = useState<string | null>(null)
  const run = (c: Competency) => {
    if (c.guided) onRun({ id: c.id, name: c.question, guided: c.guided, sparql: null, created_at: '', updated_at: '' })
  }
  const rename = async (q: SavedQuery) => {
    const n = rname.trim(); if (!n) return
    try { await qapi.update(pid, q.id, { name: n, description: q.description, guided: q.guided, sparql: q.sparql }); setRenaming(null); saved.reload(); toast(t('q.lib.renamed')) } catch (e) { toast(String((e as Error).message)) }
  }
  const remove = async (q: SavedQuery) => { try { await qapi.remove(pid, q.id); setDel(null); saved.reload(); toast(t('q.lib.deleted')) } catch (e) { toast(String((e as Error).message)) } }
  return (
    <section className="qlib" aria-label={t('q.lib')}>
      <div className="qlib-hd"><h2>{t('q.lib.saved')}</h2><span className="grow" />
        {canSave && !naming && <Button size="sm" icon="floppy-disk" onClick={() => setNaming(true)}>{t('q.save')}</Button>}</div>
      {naming && (
        <form className="qlib-name" onSubmit={async e => { e.preventDefault(); if (!name.trim()) return; await onSave(name.trim()); setName(''); setNaming(false); saved.reload() }}>
          <input type="text" autoFocus value={name} onChange={e => setName(e.target.value)} placeholder={t('q.save.ph')} aria-label={t('q.save.ph')} />
          <Button size="sm" variant="primary" type="submit" disabled={!name.trim()}>{t('q.save.go')}</Button>
          <IconButton icon="xmark" label={t('common.cancel')} onClick={() => setNaming(false)} />
        </form>
      )}
      <ErrorView error={saved.error} what={t('q.lib.saved')} />
      {saved.data && saved.data.length === 0 && <p className="muted qlib-none">{t('q.lib.none')}</p>}
      <ul className="qlib-list">
        {saved.data?.map(q => (
          <li key={q.id} className={activeId === q.id ? 'on' : ''}>
            {renaming === q.id ? (
              <form className="qlib-name" onSubmit={e => { e.preventDefault(); void rename(q) }}>
                <input type="text" autoFocus value={rname} onChange={e => setRname(e.target.value)} aria-label={t('q.lib.rename')} />
                <Button size="sm" variant="primary" type="submit">{t('q.ok')}</Button>
                <IconButton icon="xmark" label={t('common.cancel')} onClick={() => setRenaming(null)} />
              </form>
            ) : del === q.id ? (
              <div className="qlib-confirm"><span>{t('q.lib.confirm', { n: q.name })}</span>
                <Button size="sm" variant="danger" onClick={() => void remove(q)}>{t('common.delete')}</Button><Button size="sm" onClick={() => setDel(null)}>{t('common.cancel')}</Button></div>
            ) : (
              <>
                <button type="button" className="qlib-main" onClick={() => onRun(q)} title={t('q.lib.run')}>
                  <Icon name="play" /><span className="nm">{q.name}</span><span className="muted tiny">{q.sparql && !q.guided ? 'SPARQL · ' : ''}{when(q.updated_at, lang)}</span>
                </button>
                <span className="qlib-act">
                  <span className="desk"><IconButton icon="pen-to-square" label={t('q.lib.open')} onClick={() => onOpen(q)} />
                  <IconButton icon="i-cursor" label={t('q.lib.rename')} onClick={() => { setRenaming(q.id); setRname(q.name) }} />
                  <IconButton icon="trash" label={t('common.delete')} onClick={() => setDel(q.id)} /></span>
                </span>
              </>
            )}
          </li>
        ))}
      </ul>
      <div className="qlib-hd"><h2>{t('q.lib.comp')}</h2></div>
      <ErrorView error={comp.error} what={t('q.lib.comp')} />
      {comp.data && comp.data.length === 0 && <p className="muted qlib-none">{t('q.lib.comp.none')}</p>}
      <ul className="qlib-list comp">
        {comp.data?.map(c => (
          <li key={c.id}>
            <button type="button" className="qlib-main" disabled={!c.guided && !c.sparql} onClick={() => (c.guided ? run(c) : onFree(c.sparql))}
              title={c.guided ? t('q.lib.comp.run') : t('q.lib.comp.free', { r: c.reason ?? '' })}>
              <Icon name={c.guided ? 'circle-question' : 'code'} /><span className="nm">{c.question}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
