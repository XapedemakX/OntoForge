import { useState } from 'react'
import { api, type Project } from '../../api'
import { Button, Icon } from '../../kit'
import { useT } from '../../i18n'

const EXAMPLES = ['ed.dsl.ex.label', 'ElectricVehicle < Vehicle', 'Vehicle.vin : string [1] key', 'RepairOrder -concerns-> Vehicle [1]']

/** Saisie rapide (DSL) repliable : une ligne = un axiome. */
export function QuickPanel({ pid, hint, onApplied, toast }: { pid: string; hint: string | null; onApplied: (p: Project) => void; toast: (m: string) => void }) {
  const t = useT()
  const [open, setOpen] = useState(false); const [text, setText] = useState(''); const [busy, setBusy] = useState(false); const [errs, setErrs] = useState<{ line: number; message: string }[]>([])
  const run = async () => {
    if (!text.trim() || busy) return
    setBusy(true)
    try {
      const r = await api.dsl(pid, text, true); onApplied(r.project)
      const bad = new Set(r.errors.map(e => e.line)); setErrs(r.errors)
      setText(bad.size ? text.split('\n').filter((_, i) => bad.has(i + 1)).join('\n') : '')
      toast(r.errors.length ? t('ed.dsl.partial', { n: r.errors.length }) : t('ed.dsl.done'))
    } catch (e) { toast((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <section className={'ol-quick' + (open ? ' open' : '')}>
      <button type="button" className="ol-quick-h" aria-expanded={open} onClick={() => setOpen(o => !o)}>
        <Icon name={open ? 'chevron-down' : 'chevron-up'} /><Icon name="bolt" /><b>{t('ed.dsl.title')}</b><small className="muted">{t('ed.dsl.sub')}</small>
      </button>
      {open && (
        <div className="ol-quick-b">
          <textarea aria-label={t('ed.dsl.title')} rows={3} spellCheck={false} placeholder={t('ed.dsl.ph')} value={text} onChange={e => setText(e.target.value)}
            onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); run() } }} />
          <div className="ol-quick-s"><Button variant="primary" icon="bolt" onClick={run} disabled={busy || !text.trim()}>{t('ed.dsl.apply')}</Button><small className="muted">{t('ed.dsl.ctrl')}</small></div>
          {errs.length > 0 && <ul className="ol-quick-err">{errs.map((e, i) => <li key={i}><Icon name="triangle-exclamation" /> {t('ed.dsl.line', { n: e.line })} : {e.message}</li>)}</ul>}
          <div className="ol-chips ex">
            {hint && <button type="button" className="ol-sugg-b" onClick={() => setText(x => (x ? x + '\n' : '') + hint + '.')}>{t('ed.dsl.addto', { name: hint })}</button>}
            {EXAMPLES.map(k => { const x = k.startsWith('ed.') ? t(k) : k; return <button key={k} type="button" className="ol-sugg-b mono" onClick={() => setText(v => (v ? v + '\n' : '') + x)}>{x}</button> })}
          </div>
        </div>
      )}
    </section>
  )
}
