import { useState } from 'react'
import { Icon, useToast } from '../kit'
import { useI18n } from '../i18n'

/** Mention « Sur ordinateur » ciblée (L44) : remplace le bandeau bleu « consultation » ; refermable ; « M'envoyer le lien » partage ou copie l'adresse. */
export async function sendLink(toast: (m: string) => void, t: (k: string) => string) {
  const url = location.href
  try {
    if (navigator.share) { await navigator.share({ title: 'OntoForge', url }); return }
    await navigator.clipboard.writeText(url); toast(t('mob.link.copied'))
  } catch (e) { if ((e as Error)?.name !== 'AbortError') { try { await navigator.clipboard.writeText(url); toast(t('mob.link.copied')) } catch { toast(url) } } }
}
const KEY = (s: string) => `ontoforge.hint.${s}`
export function DesktopHint({ screen, kind }: { screen: string; kind: 'read' | 'full' }) {
  const { t } = useI18n(); const toast = useToast()
  const [gone, setGone] = useState(() => { try { return sessionStorage.getItem(KEY(screen)) === '1' } catch { return false } })
  if (gone) return null
  return (
    <div className="mhint" data-ag-lift role="note" data-testid="desktop-hint">
      <Icon name="desktop" /><span className="grow">{t(kind === 'full' ? 'mob.hint.full' : 'mob.hint.read')}</span>
      <button type="button" className="lnk" onClick={() => void sendLink(toast, t)}>{t('mob.link')}</button>
      <button type="button" className="mx" aria-label={t('common.close')} onClick={() => { try { sessionStorage.setItem(KEY(screen), '1') } catch { /* ignoré */ } setGone(true) }}><Icon name="xmark" /></button>
    </div>
  )
}
