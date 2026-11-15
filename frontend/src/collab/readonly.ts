import { useEffect } from 'react'

/**
 * Lecture seule (L40) : un lecteur ne peut rien modifier. Le serveur refuse toute écriture (403) ; ici on désactive en plus, dans
 * l'en-tête et le contenu, les boutons d'action (primaires et dangereux), les envois de fichiers, les zones de texte et ce qui porte
 * `data-write`. Un écran de consultation pure se déclare avec `data-safe` ; le panneau de partage reste actif.
 * Ce qui n'est pas listé ici reste protégé par le serveur : un refus affiche « lecture seule » (voir Banners).
 */
const TARGETS = '.btn.primary, .btn.danger, textarea, input[type=file], [data-write], [data-ro-write] button, [data-ro-write] select'
const KEEP = '[data-safe], .collab-panel, .collab-keep'

export function applyReadOnly(root: ParentNode, on: boolean, label: string): void {
  root.querySelectorAll<HTMLElement>(TARGETS).forEach(el => {
    if (on) {
      if (el.closest(KEEP) || el.dataset.roDone) return
      el.dataset.roDone = '1'
      if (el instanceof HTMLTextAreaElement && !el.readOnly) { el.readOnly = true; el.dataset.roText = '1' }
      else if (!(el as HTMLButtonElement).disabled) { (el as HTMLButtonElement).disabled = true; el.dataset.roDis = '1' }
      el.title = label
    } else if (el.dataset.roDone) {
      delete el.dataset.roDone
      if (el.dataset.roText) { (el as HTMLTextAreaElement).readOnly = false; delete el.dataset.roText }
      if (el.dataset.roDis) { (el as HTMLButtonElement).disabled = false; delete el.dataset.roDis }
      el.removeAttribute('title')
    }
  })
}

export function useReadOnlyGuard(on: boolean, label: string, root: () => HTMLElement | null, deps: unknown[]): void {
  useEffect(() => {
    const el = root()
    if (!el) return
    document.body.classList.toggle('of-readonly', on)
    applyReadOnly(el, on, label)
    if (!on) return () => { document.body.classList.remove('of-readonly') }
    let queued = false
    const mo = new MutationObserver(() => { if (queued) return; queued = true; requestAnimationFrame(() => { queued = false; applyReadOnly(el, true, label) }) })
    mo.observe(el, { childList: true, subtree: true })
    return () => { mo.disconnect(); document.body.classList.remove('of-readonly'); applyReadOnly(el, false, label) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [on, label, ...deps])
}
