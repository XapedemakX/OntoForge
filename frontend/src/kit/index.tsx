// Composants de base du design system OntoForge. Les écrans importent depuis '../kit'.
import { useId, useState, type ButtonHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'
import { Krakie, type Pose } from '../krakie/Krakie'
import { useT } from '../i18n'
import { useMobile } from '../shell/sidePref'
export { ToastHost, useToast } from '../ui'

/** Icône Font Awesome gratuite : name = 'diagram-project' (solid) ou 'regular:bell'. Ne porte aucun sens seule : ajouter un libellé. */
export function Icon({ name, className = '' }: { name: string; className?: string }) {
  const [style, n] = name.includes(':') ? name.split(':') : ['solid', name]
  return <i className={`fa-${style} fa-${n.replace(/^fa-/, '')} ${className}`} aria-hidden="true" />
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'primary' | 'ghost' | 'danger'; size?: 'md' | 'sm'; icon?: string }
export function Button({ variant = 'default', size = 'md', icon, className = '', children, ...rest }: BtnProps) {
  const cls = ['btn', variant !== 'default' && variant, size === 'sm' && 'sm', className].filter(Boolean).join(' ')
  return <button type="button" {...rest} className={cls}>{icon && <Icon name={icon} />}{children}</button>
}
export function IconButton({ icon, label, className = '', ...rest }: Omit<BtnProps, 'children' | 'icon'> & { icon: string; label: string }) {
  return <button type="button" {...rest} className={`btn ghost iconly ${className}`} aria-label={label} title={label}><Icon name={icon} /></button>
}

/** Champ étiqueté : le libellé est lié au contrôle enfant. */
export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return <label className="f"><span>{label}</span>{children}{hint && <small className="muted">{hint}</small>}</label>
}
export function Select({ options, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { options: { value: string; label: string }[] }) {
  return <select {...rest}>{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
}
export function Segmented<T extends string>({ value, onChange, items, label }: { value: T; onChange: (v: T) => void; items: [T, string][]; label: string }) {
  return <div className="seg" role="group" aria-label={label}>{items.map(([k, l]) => <button key={k} type="button" aria-pressed={value === k} onClick={() => onChange(k)}>{l}</button>)}</div>
}
export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: [T, string][] }) {
  return <div className="tabs" role="tablist">{items.map(([k, l]) => <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)}>{l}</button>)}</div>
}

/** Panneau rabattable (inspecteur, arbre…). `open` non contrôlé par défaut. */
export function Panel({ title, children, defaultOpen = true, actions, side }: { title: string; children: ReactNode; defaultOpen?: boolean; actions?: ReactNode; side?: 'left' | 'right' }) {
  const [open, setOpen] = useState(defaultOpen); const id = useId()
  return (
    <section className={`kpanel ${open ? 'open' : 'shut'} ${side ?? ''}`}>
      <header>
        <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(o => !o)}><Icon name={open ? 'chevron-down' : 'chevron-right'} /><h3>{title}</h3></button>
        {actions}
      </header>
      {open && <div id={id} className="kpanel-body">{children}</div>}
    </section>
  )
}

/* Panneau repliable du téléphone (L45). Sous 700 px : en-tête-bouton (aria-expanded) ; replié = titre + description courte en gris, ouvert = titre seul.
   Au-delà : rendu inchangé (une carte, ou le contenu tel quel avec `bare`). État mémorisé par écran dans localStorage (try/catch, repli en mémoire). */
const FOLD_KEY = 'ontoforge.fold.v1'
const foldMem: Record<string, boolean> = {}
function readFold(key: string, def: boolean): boolean {
  try { const v = JSON.parse(localStorage.getItem(FOLD_KEY) || '{}')[key]; if (typeof v === 'boolean') return v } catch { /* stockage indisponible */ }
  return key in foldMem ? foldMem[key] : def
}
function writeFold(key: string, v: boolean) {
  foldMem[key] = v
  try { const o = JSON.parse(localStorage.getItem(FOLD_KEY) || '{}'); o[key] = v; localStorage.setItem(FOLD_KEY, JSON.stringify(o)) } catch { /* ignoré */ }
}
export function Fold({ screen, id, title, desc, defaultOpen = false, tone, className = '', bare = false, children }:
  { screen: string; id: string; title: ReactNode; desc: string; defaultOpen?: boolean; tone?: Severity; className?: string; bare?: boolean; children: ReactNode }) {
  const mob = useMobile(); const bodyId = useId(); const key = `${screen}/${id}`
  const [open, setOpen] = useState(() => readFold(key, defaultOpen))
  if (!mob) return bare ? <>{children}</> : <Card title={title} tone={tone} className={className}>{children}</Card>
  const toggle = () => setOpen(o => { writeFold(key, !o); return !o })
  return (
    <section className={`fold card ${open ? 'open' : 'shut'} ${tone ? 'tone-' + tone : ''} ${className}`} data-fold={key}>
      <h2 className="fold-h">
        <button type="button" className="fold-btn" aria-expanded={open} aria-controls={bodyId} onClick={toggle}>
          <span className="fold-tx"><b className="fold-t">{title}</b>{!open && <><span className="fold-sep" aria-hidden="true"> — </span><span className="fold-d">{desc}</span></>}</span>
          <Icon name={open ? 'chevron-up' : 'chevron-down'} className="fold-chev" />
        </button>
      </h2>
      <div id={bodyId} className="bd fold-bd" hidden={!open}>{children}</div>
    </section>
  )
}

export type Severity = 'auto' | 'review' | 'lost' | 'info'
const SEV_ICON: Record<Severity, string> = { auto: 'circle-check', review: 'scale-balanced', lost: 'triangle-exclamation', info: 'circle-info' }
/** Badge de sévérité : toujours icône + libellé (jamais la couleur seule). */
export function SeverityBadge({ severity, count, label }: { severity: Severity; count?: number; label?: string }) {
  const t = useT()
  return <span className={`sev ${severity}`}><Icon name={SEV_ICON[severity]} />{count !== undefined && <b>{count}</b>}{label ?? t('sev.' + severity)}</span>
}

export function Card({ title, actions, children, className = '', tone }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; tone?: Severity }) {
  return (
    <section className={`card ${tone ? 'tone-' + tone : ''} ${className}`}>
      {(title || actions) && <div className="hd">{title && <h2 className="grow">{title}</h2>}{actions}</div>}
      <div className="bd">{children}</div>
    </section>
  )
}
export function Toolbar({ children, end }: { children: ReactNode; end?: ReactNode }) {
  return <div className="toolbar" role="toolbar">{children}{end && <><span className="grow" />{end}</>}</div>
}
/** État vide : Krakie + message + action. Une phrase qui dit quoi faire. */
export function EmptyState({ title, children, pose = 'accueil', action }: { title: string; children?: ReactNode; pose?: Pose; action?: ReactNode }) {
  return (
    <div className="empty empty-state">
      <Krakie pose={pose} size={72} />
      <b>{title}</b>
      {children && <p>{children}</p>}
      {action && <div className="row">{action}</div>}
    </div>
  )
}
export { Krakie }
export { BottomSheet, type Snap, type SheetApi } from './BottomSheet'
export { useLongPress } from './useLongPress'
