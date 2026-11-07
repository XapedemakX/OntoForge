import { useState } from 'react'
import { Krakie } from '../krakie/Krakie'

/**
 * Logo OntoForge : tête de Krakie (sprite d'accueil recadré, animé seulement au survol / focus) + wordmark en IBM Plex Sans 600,
 * « Onto » en encre claire, « Forge » en couleur pieuvre.
 * variant : « full » (barre latérale), « mark » (Krakie seul : barre repliée, en-tête mobile).
 */
export function Logo({ variant = 'full', className = '' }: { variant?: 'full' | 'mark'; className?: string }) {
  const [hot, setHot] = useState(false)
  return (
    <a className={`logo ${variant} ${className}`} href="#/" aria-label="OntoForge" onMouseEnter={() => setHot(true)} onMouseLeave={() => setHot(false)}
      onFocus={() => setHot(true)} onBlur={() => setHot(false)}>
      <span className="logo-mark" aria-hidden="true"><Krakie pose="accueil" size={48} float={false} animated={hot} /></span>
      {variant === 'full' && <span className="logo-word"><span className="o">Onto</span><span className="f">Forge</span></span>}
    </a>
  )
}
