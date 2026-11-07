import { useEffect, useState } from 'react'
export type ThemePref = 'system' | 'light' | 'dark'
const K = 'of-theme'
export function useTheme(): [ThemePref, () => void] {
  const [pref, setPref] = useState<ThemePref>(() => { try { const v = localStorage.getItem(K); return v === 'light' || v === 'dark' ? v : 'system' } catch { return 'system' } })
  useEffect(() => {
    if (pref === 'system') document.documentElement.removeAttribute('data-theme'); else document.documentElement.dataset.theme = pref
    try { localStorage.setItem(K, pref) } catch { /* ignoré */ }
  }, [pref])
  return [pref, () => setPref(p => (p === 'system' ? 'light' : p === 'light' ? 'dark' : 'system'))]
}
