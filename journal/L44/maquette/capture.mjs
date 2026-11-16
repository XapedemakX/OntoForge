// L44 : captures PNG de la maquette, un écran par fichier (cadre du téléphone seul), clair + deux en sombre, et la page entière.
// Usage : node journal/L44/maquette/capture.mjs   (après python journal/L44/maquette/inline_assets.py)
import { createRequire } from 'node:module'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let pw; try { pw = require('playwright') } catch { pw = require('/opt/node22/lib/node_modules/playwright') }
const HERE = path.dirname(fileURLToPath(import.meta.url))
const url = pathToFileURL(path.join(HERE, 'index.html')).href
const NAMES = { s1: '1-connexion', s2: '2-projets', s3: '3-accueil', s4: '4-ontologie-graphe', s5: '5-fiche-classe', s6: '6-arbitrer', s7: '7-carte-metier', s8: '8-krakie', s9: '9-plus' }
const DARK = ['s4', 's6']
const b = await pw.chromium.launch()
for (const theme of ['light', 'dark']) {
  const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 })
  await p.goto(url + '?theme=' + theme); await p.evaluate(() => document.fonts.ready)
  for (const [id, name] of Object.entries(NAMES)) {
    if (theme === 'dark' && !DARK.includes(id)) continue
    await p.locator(`#${id} .phone`).screenshot({ path: path.join(HERE, `${name}${theme === 'dark' ? '-sombre' : ''}.png`) })
  }
  if (theme === 'light') await p.locator('.brief').screenshot({ path: path.join(HERE, '0-synthese.png') })
  await p.close()
}
await b.close()
