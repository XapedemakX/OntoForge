/** Chargement des frames de Krakie (mêmes SVG animés que le composant Krakie) en canvas 32×32 pour le jeu. */
export type GamePose = 'accueil' | 'graphe' | 'inquiete' | 'contente'
export interface PoseFrames { frames: HTMLCanvasElement[]; durations: number[] }
export type KrakieSprites = Partial<Record<GamePose, PoseFrames>>

const loadImg = (src: string) => new Promise<HTMLImageElement | null>(res => {
  const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = src
})

export async function loadKrakieSprites(poses: GamePose[]): Promise<KrakieSprites> {
  const out: KrakieSprites = {}
  let manifest: Record<string, number[]> = {}
  try { const r = await fetch('/krakie/anim/manifest.json'); if (r.ok) manifest = await r.json() } catch { /* repli : image fixe */ }
  await Promise.all(poses.map(async pose => {
    const durations = manifest[pose]
    const urls = durations && durations.length > 1 ? durations.map((_, n) => `/krakie/anim/${pose}-${n + 1}.svg`) : [`/krakie/${pose}.svg`]
    const imgs = await Promise.all(urls.map(loadImg))
    if (imgs.some(i => !i)) return
    const frames = imgs.map(img => {
      const c = document.createElement('canvas'); c.width = c.height = 32
      const x = c.getContext('2d')!; x.imageSmoothingEnabled = false; x.drawImage(img!, 0, 0, 32, 32)
      return c
    })
    out[pose] = { frames, durations: durations && durations.length === frames.length ? durations : [1000] }
  }))
  return out
}
