/** Chargement des frames de Krakie (mêmes SVG animés que le composant Krakie) en canvas 32×32 pour le jeu.
 *  Garanties (L30, correctif « carré teal ») :
 *  - toutes les poses sont préchargées et attendues avant de pouvoir jouer ;
 *  - le manifeste n'est jamais requis ni mis en cache : une copie périmée (sans les poses « nage* ») ne casse plus le sprite,
 *    les 6 images de chaque pose sont devinées par convention de nommage (nage-1.svg … nage-6.svg) ;
 *  - une image qui échoue (404 rendu en index.html par nginx, MIME, SVG sans dimensions, image vide) est retentée une fois,
 *    puis la pose est remplacée par la silhouette pixel art de Krakie dessinée ici, avec un console.warn qui nomme la pose. */
export type GamePose = 'nage' | 'nage_clin' | 'nage_ravie' | 'nage_surprise' | 'nage_grimace' | 'nage_inquiete'
export const GAME_POSES: GamePose[] = ['nage', 'nage_clin', 'nage_ravie', 'nage_surprise', 'nage_grimace', 'nage_inquiete']
export interface PoseFrames { frames: HTMLCanvasElement[]; durations: number[] }
export type KrakieSprites = Partial<Record<GamePose, PoseFrames>>
export interface LoadedSprites { sprites: KrakieSprites; missing: string[] }

/** Nombre d'images et durées par défaut (design/krakie/game_poses.py : N = 6, MS par pose), utilisés si le manifeste est absent ou périmé. */
const FRAMES = 6
const DEFAULT_MS: Record<GamePose, number> = { nage: 95, nage_clin: 95, nage_ravie: 95, nage_surprise: 110, nage_grimace: 70, nage_inquiete: 130 }
const TIMEOUT = 10000
const base = () => (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/')

const mk32 = () => { const c = document.createElement('canvas'); c.width = c.height = 32; return c }

/** Vrai si le canvas contient au moins un pixel non transparent (un SVG sans dimensions peut se « dessiner » sans rien tracer). */
function inked(c: HTMLCanvasElement) {
  try { const d = c.getContext('2d')!.getImageData(0, 0, 32, 32).data; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) return true; return false } catch { return true }
}

function loadImg(src: string): Promise<HTMLImageElement | null> {
  return new Promise(res => {
    const i = new Image(); let done = false
    const end = (v: HTMLImageElement | null) => { if (!done) { done = true; clearTimeout(t); res(v) } }
    const t = setTimeout(() => end(null), TIMEOUT)
    i.onload = () => { const d = i.decode?.(); if (d) d.then(() => end(i), () => end(i)); else end(i) }
    i.onerror = () => end(null)
    i.src = src
  })
}

/** Une image → canvas 32×32 non vide, ou null (avec une seconde tentative contournant le cache). */
async function frameCanvas(url: string): Promise<HTMLCanvasElement | null> {
  for (const u of [url, url + (url.includes('?') ? '&' : '?') + 'r=' + Date.now()]) {
    const img = await loadImg(u)
    if (!img) continue
    const c = mk32(), x = c.getContext('2d')!; x.imageSmoothingEnabled = false
    try { x.drawImage(img, 0, 0, 32, 32) } catch { continue }
    if (inked(c)) return c
  }
  return null
}

/** Silhouette de Krakie en pixel art (dôme, yeux, sept tentacules), 2 images : repli quand une pose est introuvable. Jamais un aplat. */
export function silhouetteFrames(): PoseFrames {
  const K = '#0B2B33', B = '#1FA39E', H = '#7FDCD4', W = '#FFFFFF', P = '#F4A6A0'
  const frames = [0, 1].map(f => {
    const c = mk32(), x = c.getContext('2d')!
    const row = (y: number, x0: number, w: number, col: string) => { x.fillStyle = col; x.fillRect(x0, y, w, 1) }
    // dôme : demi-ellipse (rx 11, ry 13) de la ligne 3 à 16, puis flancs droits jusqu'à la ligne 18
    for (let y = 3; y <= 18; y++) {
      const t = Math.min(1, (16 - y) / 13), hw = y >= 16 ? 11 : Math.round(11 * Math.sqrt(Math.max(0, 1 - t * t)))
      row(y, 16 - hw - 1, 2 * hw + 2, K); row(y, 16 - hw, 2 * hw, B)
    }
    row(5, 11, 5, H); row(6, 9, 3, H); row(7, 8, 2, H)
    // yeux et joues
    ;[11, 18].forEach(ex => { x.fillStyle = K; x.fillRect(ex, 11, 3, 4); x.fillStyle = W; x.fillRect(ex, 11, 1, 1) })
    x.fillStyle = P; x.fillRect(8, 16, 2, 1); x.fillRect(22, 16, 2, 1)
    x.fillStyle = K; x.fillRect(14, 17, 4, 1)
    // tentacules : ondulation de ±1 px, en opposition de phase d'une à l'autre
    for (let i = 0; i < 7; i++) {
      const cx = 7 + i * 3
      for (let y = 19; y <= 29; y++) {
        const off = Math.round(Math.sin((y / 3) + i * 0.9 + f * Math.PI) * (y > 24 ? 1.2 : 0.6))
        x.fillStyle = K; x.fillRect(cx + off - 1, y, 3, 1)
        x.fillStyle = B; x.fillRect(cx + off, y, 1, 1)
      }
    }
    return c
  })
  return { frames, durations: [300, 300] }
}

export async function loadKrakieSprites(poses: GamePose[]): Promise<LoadedSprites> {
  const sprites: KrakieSprites = {}, missing: string[] = []
  const b = base()
  let manifest: Record<string, number[]> = {}
  try { const r = await fetch(b + 'krakie/anim/manifest.json', { cache: 'no-cache' }); if (r.ok) { const j = await r.json(); if (j && typeof j === 'object') manifest = j } } catch { /* manifeste facultatif : nombre d'images par convention */ }
  await Promise.all(poses.map(async pose => {
    const m = manifest[pose]
    const n = Array.isArray(m) && m.length > 1 ? m.length : FRAMES
    const urls = Array.from({ length: n }, (_, k) => `${b}krakie/anim/${pose}-${k + 1}.svg`)
    const got = await Promise.all(urls.map(frameCanvas))
    const bad = urls.filter((_, k) => !got[k])
    if (bad.length) {
      missing.push(pose)
      console.warn(`[Krakie's Triple Catch] pose de Krakie introuvable : « ${pose} » (${bad.length}/${n} images, ex. ${bad[0]}) → silhouette pixel art de repli`)
      return
    }
    sprites[pose] = { frames: got as HTMLCanvasElement[], durations: Array.isArray(m) && m.length === n ? m : Array(n).fill(DEFAULT_MS[pose]) }
  }))
  // toute pose manquante est remplacée : le moteur ne rencontre jamais de pose indéfinie
  const fb = silhouetteFrames()
  for (const p of poses) if (!sprites[p]) sprites[p] = fb
  return { sprites, missing }
}
