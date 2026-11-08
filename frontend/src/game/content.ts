/** Vocabulaire du jeu : un petit domaine « garage » (clin d'œil à l'exemple automaint). Libellés techniques, identiques en fr et en. */
export type Kind = 'S' | 'P' | 'O'
export const TRIPLES: [string, string, string][] = [
  ['Mechanic', 'fixes', 'Car'], ['Mechanic', 'worksAt', 'Garage'], ['Owner', 'owns', 'Car'], ['Car', 'hasPart', 'Engine'],
  ['Car', 'type', 'Vehicle'], ['Garage', 'employs', 'Mechanic'], ['Engine', 'partOf', 'Car'], ['Order', 'concerns', 'Car'],
  ['Order', 'doneBy', 'Mechanic'], ['Part', 'usedIn', 'Order'], ['Truck', 'subOf', 'Vehicle'], ['Owner', 'books', 'Order'],
]
export const ALL: Record<Kind, string[]> = {
  S: [...new Set(TRIPLES.map(t => t[0]))], P: [...new Set(TRIPLES.map(t => t[1]))], O: [...new Set(TRIPLES.map(t => t[2]))],
}
/** Libellés autorisés pour le prochain maillon d'une chaîne (0 : sujets, 1 : prédicats du sujet, 2 : objets du couple). */
export function options(chain: string[]): { kind: Kind; labels: string[] } {
  if (chain.length === 0) return { kind: 'S', labels: ALL.S }
  if (chain.length === 1) return { kind: 'P', labels: [...new Set(TRIPLES.filter(t => t[0] === chain[0]).map(t => t[1]))] }
  return { kind: 'O', labels: [...new Set(TRIPLES.filter(t => t[0] === chain[0] && t[1] === chain[1]).map(t => t[2]))] }
}
