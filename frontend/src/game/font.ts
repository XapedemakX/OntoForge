/** Police bitmap 3×5 (majuscules, chiffres, quelques signes) pour le texte dessiné dans le canvas. */
const G: Record<string, number[]> = {
  A: [2, 5, 7, 5, 5], B: [6, 5, 6, 5, 6], C: [3, 4, 4, 4, 3], D: [6, 5, 5, 5, 6], E: [7, 4, 6, 4, 7], F: [7, 4, 6, 4, 4],
  G: [3, 4, 5, 5, 3], H: [5, 5, 7, 5, 5], I: [7, 2, 2, 2, 7], J: [1, 1, 1, 5, 2], K: [5, 5, 6, 5, 5], L: [4, 4, 4, 4, 7],
  M: [5, 7, 7, 5, 5], N: [6, 5, 5, 5, 5], O: [2, 5, 5, 5, 2], P: [6, 5, 6, 4, 4], Q: [2, 5, 5, 6, 3], R: [6, 5, 6, 5, 5],
  S: [3, 4, 2, 1, 6], T: [7, 2, 2, 2, 2], U: [5, 5, 5, 5, 7], V: [5, 5, 5, 5, 2], W: [5, 5, 7, 7, 5], X: [5, 5, 2, 5, 5],
  Y: [5, 5, 2, 2, 2], Z: [7, 1, 2, 4, 7],
  '0': [7, 5, 5, 5, 7], '1': [2, 6, 2, 2, 7], '2': [6, 1, 2, 4, 7], '3': [6, 1, 2, 1, 6], '4': [5, 5, 7, 1, 1],
  '5': [7, 4, 6, 1, 6], '6': [3, 4, 7, 5, 7], '7': [7, 1, 2, 2, 2], '8': [7, 5, 7, 5, 7], '9': [7, 5, 7, 1, 6],
  ':': [0, 2, 0, 2, 0], '.': [0, 0, 0, 0, 2], '-': [0, 0, 7, 0, 0], '!': [2, 2, 2, 0, 2], '?': [6, 1, 2, 0, 2],
  '/': [1, 1, 2, 4, 4], '+': [0, 2, 7, 2, 0], '>': [4, 2, 1, 2, 4], '<': [1, 2, 4, 2, 1], ' ': [0, 0, 0, 0, 0],
}

/** Majuscules ASCII sans accents (la police n'a pas de diacritiques). */
export const norm = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase()
export const textWidth = (s: string) => Math.max(0, s.length * 4 - 1)

const cache = new Map<string, HTMLCanvasElement>()
export function textCanvas(raw: string, color: string): HTMLCanvasElement {
  const s = norm(raw)
  const key = color + '|' + s
  let c = cache.get(key)
  if (c) return c
  c = document.createElement('canvas'); c.width = Math.max(1, textWidth(s)); c.height = 5
  const x = c.getContext('2d')!
  x.fillStyle = color
  ;[...s].forEach((ch, i) => (G[ch] ?? G['?']).forEach((row, y) => { for (let b = 0; b < 3; b++) if (row & (4 >> b)) x.fillRect(i * 4 + b, y, 1, 1) }))
  cache.set(key, c)
  return c
}
export function drawText(ctx: CanvasRenderingContext2D, s: string, x: number, y: number, color: string) {
  ctx.drawImage(textCanvas(s, color), Math.round(x), Math.round(y))
}
