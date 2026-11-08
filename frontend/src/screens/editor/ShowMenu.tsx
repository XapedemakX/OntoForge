// Menus « Afficher » et « Exporter » de la barre de l'éditeur (L26).
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Button, Icon } from '../../kit'
import { useT } from '../../i18n'
import type { Mode, ShowPrefs } from './prefs'

/** Bouton + panneau flottant fermé par clic extérieur ou Échap. */
export function Pop({ icon, label, testid, children, align = 'left', tour }: { icon: string; label: string; testid: string; children: (close: () => void) => ReactNode; align?: 'left' | 'right'; tour?: string }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const down = (e: MouseEvent) => { if (!root.current?.contains(e.target as Node)) setOpen(false) }
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', down); document.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', down); document.removeEventListener('keydown', key) }
  }, [open])
  return (
    <div className="of-popwrap" ref={root} data-tour={tour}>
      <Button size="sm" icon={icon} aria-expanded={open} aria-haspopup="true" data-testid={testid} onClick={() => setOpen(o => !o)}>{label}</Button>
      {open && <div className={'of-pop of-showmenu ' + align} role="group" aria-label={label}>{children(() => setOpen(false))}</div>}
    </div>
  )
}

export function ShowMenu({ mode, show, setShow, collapsed }: { mode: Mode; show: ShowPrefs; setShow: (s: ShowPrefs) => void; collapsed: number }) {
  const t = useT()
  const row = (k: Exclude<keyof ShowPrefs, 'density'>, key: string, only?: Mode) => {
    const off = only !== undefined && mode !== only
    return <label className={'chk' + (off ? ' off' : '')} title={off ? t('ed.show.onlyvowl') : undefined}>
      <input type="checkbox" checked={show[k]} disabled={off} data-testid={'show-' + k} onChange={e => setShow({ ...show, [k]: e.target.checked })} />{t('ed.show.' + k)}</label>
  }
  return (
    <Pop icon="eye" label={t('ed.show')} testid="show-btn" tour="ed-show">{() => <>
      {row('dt', 'dt', 'vowl')}{row('sub', 'sub')}{row('rel', 'rel')}{row('disj', 'disj')}{row('dep', 'dep')}{row('krakie', 'krakie')}
      <div className="of-density">
        <label htmlFor="of-density">{t('ed.show.density')}<b data-testid="density-val">{show.density === 0 ? t('ed.show.density0') : `≤ ${show.density}`}</b></label>
        <input id="of-density" type="range" min={0} max={6} step={1} value={show.density} data-testid="density" onChange={e => setShow({ ...show, density: Number(e.target.value) })} />
        <small className="muted">{show.density === 0 ? t('ed.show.densityhint') : t('ed.show.collapsed', { n: collapsed })}</small>
      </div>
      <Button size="sm" icon="rotate-left" onClick={() => setShow({ dt: true, sub: true, rel: true, disj: true, dep: true, krakie: true, density: 0 })}>{t('ed.show.reset')}</Button>
    </>}</Pop>
  )
}

export function ExportMenu({ onExport, disabled }: { onExport: (fmt: 'svg' | 'png', legend: boolean) => void; disabled: boolean }) {
  const t = useT()
  const [legend, setLegend] = useState(true)
  return (
    <Pop icon="download" label={t('ed.exp')} testid="export-btn" align="right" tour="ed-export">{close => <>
      <label className="chk"><input type="checkbox" checked={legend} data-testid="export-legend" onChange={e => setLegend(e.target.checked)} />{t('ed.exp.legend')}</label>
      <div className="row">
        <Button size="sm" icon="file-code" disabled={disabled} data-testid="export-svg" onClick={() => { onExport('svg', legend); close() }}>SVG</Button>
        <Button size="sm" icon="image" disabled={disabled} data-testid="export-png" onClick={() => { onExport('png', legend); close() }}>PNG</Button>
      </div>
      <small className="muted"><Icon name="circle-info" /> {t('ed.exp.hint')}</small>
    </>}</Pop>
  )
}
