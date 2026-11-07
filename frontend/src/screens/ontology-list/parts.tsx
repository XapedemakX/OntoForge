import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react'
import { Icon } from '../../kit'
import { useT } from '../../i18n'

export interface Item { id: string; label: string; hint?: string; icon?: string }

/** Combobox à recherche (ARIA combobox/listbox) : remplace les <select> natifs pour les listes longues. */
export function Combobox({ items, onPick, placeholder, label, disabled, clearOnPick = true }: {
  items: Item[]; onPick: (id: string) => void; placeholder: string; label?: string; disabled?: boolean; clearOnPick?: boolean
}) {
  const t = useT()
  const [q, setQ] = useState(''); const [open, setOpen] = useState(false); const [act, setAct] = useState(0)
  const root = useRef<HTMLDivElement>(null); const id = useId()
  const shown = useMemo(() => {
    const s = q.trim().toLowerCase()
    return items.filter(i => !s || (i.label + ' ' + (i.hint ?? '')).toLowerCase().includes(s)).slice(0, 50)
  }, [items, q])
  useEffect(() => setAct(0), [q, open])
  useEffect(() => {
    if (!open) return
    const f = (e: MouseEvent) => { if (!root.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', f); return () => document.removeEventListener('mousedown', f)
  }, [open])
  const pick = (i: Item) => { onPick(i.id); setOpen(false); if (clearOnPick) setQ('') }
  return (
    <div className="ol-combo" ref={root}>
      <Icon name="magnifying-glass" />
      <input type="text" role="combobox" aria-expanded={open} aria-controls={id} aria-autocomplete="list" aria-label={label ?? placeholder} disabled={disabled}
        placeholder={placeholder} value={q} onFocus={() => setOpen(true)} onChange={e => { setQ(e.target.value); setOpen(true) }}
        onKeyDown={e => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setAct(a => Math.min(a + 1, shown.length - 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setAct(a => Math.max(a - 1, 0)) }
          else if (e.key === 'Enter' && open && shown[act]) { e.preventDefault(); pick(shown[act]) }
          else if (e.key === 'Escape') setOpen(false)
        }} />
      {open && (
        <ul className="ol-combo-list" role="listbox" id={id}>
          {shown.map((i, n) => (
            <li key={i.id} role="option" aria-selected={n === act} className={n === act ? 'on' : ''} onMouseEnter={() => setAct(n)} onMouseDown={e => { e.preventDefault(); pick(i) }}>
              {i.icon && <Icon name={i.icon} />}<span>{i.label}</span>{i.hint && <small>{i.hint}</small>}
            </li>
          ))}
          {!shown.length && <li className="none">{t('ol.combo.none')}</li>}
        </ul>
      )}
    </div>
  )
}

/** Texte édité en place : validé à la sortie du champ ou par Entrée, Échap annule. */
export function InlineText({ value, onCommit, area, ph, label, disabled }: { value: string; onCommit: (v: string) => void; area?: boolean; ph?: string; label: string; disabled?: boolean }) {
  const [v, setV] = useState(value)
  useEffect(() => setV(value), [value])
  const done = () => { if (v !== value) onCommit(v) }
  const common = { 'aria-label': label, placeholder: ph, value: v, disabled, className: 'ol-inline', onChange: (e: { target: { value: string } }) => setV(e.target.value), onBlur: done }
  return area
    ? <textarea {...common} rows={Math.max(2, Math.min(5, v.split('\n').length + Math.floor(v.length / 60)))} onKeyDown={e => { if (e.key === 'Escape') { setV(value); (e.target as HTMLElement).blur() } }} />
    : <input type="text" {...common} onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLElement).blur(); if (e.key === 'Escape') { setV(value) } }} />
}

export interface ChipItem { id: string; label: string; icon?: string; title?: string }
/** Puces cliquables (navigation) avec retrait optionnel. */
export function Chips({ items, onOpen, onRemove, empty }: { items: ChipItem[]; onOpen?: (id: string) => void; onRemove?: (id: string) => void; empty?: string }) {
  const t = useT()
  if (!items.length) return empty ? <span className="ol-none">{empty}</span> : null
  return (
    <ul className="ol-chips">
      {items.map(i => (
        <li key={i.id} className="ol-chip">
          {onOpen
            ? <button type="button" className="go" onClick={() => onOpen(i.id)} title={i.title ?? i.id}>{i.icon && <Icon name={i.icon} />}{i.label}</button>
            : <span className="go static" title={i.title}>{i.icon && <Icon name={i.icon} />}{i.label}</span>}
          {onRemove && <button type="button" className="rm" aria-label={`${t('ol.remove')} ${i.label}`} title={t('ol.remove')} onClick={() => onRemove(i.id)}><Icon name="xmark" /></button>}
        </li>
      ))}
    </ul>
  )
}

/** Interrupteur lisible : libellé + explication en langage courant. */
export function Switch({ checked, onChange, label, hint, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string; disabled?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={checked} className="ol-switch" disabled={disabled} onClick={() => onChange(!checked)}>
      <span className="track"><span className="knob" /></span>
      <span className="txt"><b>{label}</b>{hint && <small>{hint}</small>}</span>
    </button>
  )
}

export function Section({ title, count, actions, children, tone, id }: { title: string; count?: number; actions?: ReactNode; children: ReactNode; tone?: 'warn'; id?: string }) {
  return (
    <section className={`ol-sec ${tone ?? ''}`} aria-labelledby={id}>
      <header><h3 id={id}>{title}</h3>{count !== undefined && <span className="ol-count">{count}</span>}<span className="grow" />{actions}</header>
      <div className="ol-sec-b">{children}</div>
    </section>
  )
}
