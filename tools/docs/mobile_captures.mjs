// Captures « téléphone » du guide (L44) : docs/guide/img/{fr,en}/mobile-*.png, iPhone 15, version locale, projet Automaint.
// Usage : BACKEND_PORT=9031 FRONT_PORT=5031 node tools/docs/mobile_captures.mjs   (front buildé ; puis réduire avec Pillow : voir tools/docs/optimize.py,
// qui réécrit toutes les images : ici seules les nouvelles sont réduites à 480 px de large et quantifiées, par mobile_captures.py).
import { createRequire } from 'node:module'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { startWeb, apiClient, ROOT } from '../recette/web_server.mjs'
const require = createRequire(import.meta.url)
let pw; try { pw = require('playwright') } catch { pw = require('/opt/node22/lib/node_modules/playwright') }
const { chromium, devices } = pw
const sleep = ms => new Promise(r => setTimeout(r, ms))
const srv = await startWeb({ mode: 'local', backendPort: process.env.BACKEND_PORT || 9031, frontPort: process.env.FRONT_PORT || 5031 })
const api = apiClient(srv.base)
const pid = (await api.call('POST', '/api/projects', { name: 'Automaint', sample: 'automaint' })).json.id
const FAKE_KEY = ['sk', 'ant', 'FAUXTEST', Math.random().toString(16).slice(2, 14)].join('-')   // assemblée à l'exécution
await api.call('POST', '/api/settings/providers', { name: 'Claude', kind: 'anthropic', api_key: FAKE_KEY })   // 2 fournisseurs (Mock + Claude) pour la capture de Krakie
const browser = await chromium.launch()
const d = { ...devices['iPhone 15'] }; delete d.defaultBrowserType
for (const lang of ['fr', 'en']) {
  await api.call('PUT', '/api/settings', { language: { ui: lang, labels: lang, assistant: lang } })
  const out = path.join(ROOT, 'docs/guide/img', lang); mkdirSync(out, { recursive: true })
  const ctx = await browser.newContext({ ...d, locale: lang === 'fr' ? 'fr-FR' : 'en-GB' })
  await ctx.addInitScript(l => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.setItem('ontoforge.lang', l) } catch {} }, lang)
  const page = await ctx.newPage()
  const go = async s => { await page.goto(`${srv.base}/#/projet/${pid}/${s}`); await sleep(1800) }
  const ONLY = process.env.ONLY   // ex. ONLY=graphe : ne refait que cette capture
  const shot = n => ONLY && ONLY !== n ? null : page.screenshot({ path: path.join(out, `mobile-${n}.png`) })
  await page.goto(srv.base + '/'); await sleep(800)
  await go('tableau'); await shot('accueil')
  await go('ontologie-liste')
  await page.locator('.ol-trow .nm').nth(3).tap(); await sleep(900); await shot('fiche')
  await go('ontologie'); await sleep(900); await shot('graphe')   // cadrage initial : lisible, centré sur la classe la plus connectée, arêtes tracées
  await go('analyse'); await shot('arbitrage')
  await go('plus'); await shot('plus')
  await go('tableau')
  await page.locator('[data-fold="tableau/scopes"] .fold-btn').tap(); await page.locator('[data-fold="tableau/findings"]').evaluate(e => e.scrollIntoView({ block: 'start' })); await sleep(500); await shot('panneaux')   // un panneau ouvert (titre seul), les autres repliés (titre + description)
  await page.locator('[data-fold="tableau/scopes"] .fold-btn').tap(); await sleep(200)
  await page.locator('[data-testid=krakie-fab]').tap(); await sleep(1200); await shot('krakie')   // sélecteur du fournisseur au-dessus de la zone de saisie
  await ctx.close()
}
await browser.close(); await srv.stop(); process.exit(0)
