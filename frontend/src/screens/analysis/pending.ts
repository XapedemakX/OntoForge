import type { Finding } from '../../api'

/** Un point « à arbitrer » : constat à revoir ou perdu, avec au moins une option, pas encore tranché. Définition unique : badge d'Arbitrer, pastilles et progression de l'arbitrage (L44). */
export const isPending = (f: Finding) => (f.severity === 'review' || f.severity === 'lost') && !f.chosen && f.options.length > 0
export const pendingCount = (fs: Finding[]) => fs.filter(isPending).length
