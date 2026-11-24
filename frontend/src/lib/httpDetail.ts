// Lecture du champ `detail` d'une réponse d'erreur du serveur (FastAPI). Module pur (aucune dépendance
// à l'interface) : il est chargé tel quel par les tests `node --test` (frontend/tests/http_detail.test.mjs).

/** Message d'une réponse d'erreur : `detail` en chaîne, ou en liste d'erreurs de validation (`{loc, msg}`).
 *  `withLoc` préfixe chaque message du dernier élément de `loc` (« champ : message »), pour les formulaires.
 *  Tout autre corps (absent, non JSON, forme inconnue) donne `fallback`. */
export function detailMessage(body: unknown, fallback: string, withLoc = false): string {
  const detail = (body as { detail?: unknown } | null | undefined)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d: { loc?: unknown[]; msg?: string } | null) => {
      const last = withLoc && Array.isArray(d?.loc) ? d.loc.slice(-1)[0] : undefined
      return (last ? String(last) + ' : ' : '') + (d?.msg ?? '')
    }).join(' ; ')
  }
  return fallback
}

/** Code stable du serveur (`last_admin`, `conflict`…), s'il y en a un. */
export function detailCode(body: unknown): string | undefined {
  const c = (body as { code?: unknown } | null | undefined)?.code
  return typeof c === 'string' ? c : undefined
}
