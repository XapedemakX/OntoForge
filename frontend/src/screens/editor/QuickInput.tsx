import { useState } from 'react'
import { Button, Icon } from '../../kit'
import { useT } from '../../i18n'
import { api, type Project } from '../../api'

const EXAMPLES = ['ed.dsl.ex.label', 'ElectricVehicle < Vehicle', 'Vehicle.vin : string [1] key', 'RepairOrder -concerns-> Vehicle [1]', 'FuelType : {Diesel, Petrol, Electric}']

/** Saisie rapide (DSL) : une ligne = un axiome ; appliquée en fusion, le graphe se met à jour aussitôt. */
export function QuickInput({ pid, hint, onApplied, onToast }: { pid: string; hint: string | null; onApplied: (p: Project) => void; onToast: (m: string) => void }) {
  const t = useT()
  const [text, setText] = useState(''); const [errs, setErrs] = useState<{ line: number; message: string }[]>([]); const [busy, setBusy] = useState(false)
  const run = async () => {
    if (!text.trim() || busy) return
    setBusy(true)
    try {
      const r = await api.dsl(pid, text, true)
      onApplied(r.project)
      const bad = new Set(r.errors.map(e => e.line))
      const lines = text.split('\n')
      setErrs(r.errors); setText(bad.size ? lines.filter((_, i) => bad.has(i + 1)).join('\n') : '')
      if (r.errors.length) onToast(t('ed.dsl.partial', { n: r.errors.length }))
      else onToast(t('ed.dsl.done'))
    } catch (e) { onToast((e as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="of-dsl">
      <div className="of-dsl-main">
        <textarea aria-label={t('ed.dsl.title')} rows={3} spellCheck={false} placeholder={t('ed.dsl.ph')} value={text} onChange={e => setText(e.target.value)}
          onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); run() } }} />
        <div className="of-dsl-side">
          <Button variant="primary" icon="bolt" onClick={run} disabled={busy || !text.trim()}>{t('ed.dsl.apply')}</Button>
          <small className="muted">{t('ed.dsl.ctrl')}</small>
        </div>
      </div>
      {errs.length > 0 && <ul className="of-dsl-err">{errs.map((e, i) => <li key={i}><Icon name="triangle-exclamation" /> {t('ed.dsl.line', { n: e.line })} : {e.message}</li>)}</ul>}
      <div className="of-dsl-ex">
        {hint && <button type="button" className="chip chip-btn" onClick={() => setText(x => (x ? x + '\n' : '') + hint + '.')}>{t('ed.dsl.addto', { name: hint })}</button>}
        {EXAMPLES.map(k => { const x = k.startsWith('ed.') ? t(k) : k; return <button key={k} type="button" className="chip chip-btn" onClick={() => setText(v => (v ? v + '\n' : '') + x)}>{x}</button> })}
      </div>
    </div>
  )
}
