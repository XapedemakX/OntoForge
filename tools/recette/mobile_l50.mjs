// Recette L50 : téléphone — libellé du fournisseur sans doublon, écrans secondaires lisibles à 393 px (cartes étiquetées dans Paramètres,
// champs à 16 px dans Shapes et Documentation, aucun débordement horizontal de la page sur 20 écrans).
// Usage : BACKEND_PORT=9150 FRONT_PORT=5150 node tools/recette/mobile_l50.mjs      (front buildé avant : cd frontend && npm run build)
// Version web reproduite (tools/recette/web_server.mjs : authentification, CSP, HTTPS). Mots de passe tirés au hasard à l'exécution.
import { createRequire } from 'node:module'
import { startWeb, apiClient } from './web_server.mjs'
const require = createRequire(import.meta.url)
let pw
try { pw = require('playwright') } catch { pw = require('/opt/node22/lib/node_modules/playwright') }
const { chromium, devices } = pw
const sleep = ms => new Promise(r => setTimeout(r, ms))
let ko = 0, total = 0
const log = (name, ok, detail = '') => { total++; if (!ok) ko++; console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

const srv = await startWeb({ mode: 'web', backendPort: process.env.BACKEND_PORT || 9150, frontPort: process.env.FRONT_PORT || 5150 })
try {
  const api = apiClient(srv.base); await api.login('jerem', srv.users.jerem)
  const pid = (await api.call('POST', '/api/projects', { name: 'Automaint', sample: 'automaint' })).json.id
  // 2 fournisseurs configurés (mock + Claude de test, fausse clé assemblée à l'exécution) : la liste du sélecteur apparaît
  const fake = ['sk', 'ant', 'FAUXTEST', Math.random().toString(16).slice(2, 14)].join('-')
  await api.call('POST', '/api/settings/providers', { name: 'Claude (test)', kind: 'anthropic', api_key: fake, base_url: 'https://llm-' + Math.random().toString(16).slice(2, 8) + '.example.test/v1' })
  // un endpoint SPARQL (hôte de la liste d'egress du déploiement, aucune requête n'est émise) : rend les cartes « Endpoints »
  const ep = await api.call('POST', '/api/settings/endpoints', { name: 'Triplestore test', url: 'https://api.anthropic.com/sparql', auth: 'none', default_graph: '', timeout_s: 30 })
  log('endpoint SPARQL de test créé', ep.status === 201, String(ep.status) + ' ' + JSON.stringify(ep.json).slice(0, 120))
  const browser = await chromium.launch()
  const d = { ...devices['iPhone 15'] }; delete d.defaultBrowserType
  const ctx = await browser.newContext({ ...d, locale: 'fr-FR', ignoreHTTPSErrors: true })
  await ctx.addInitScript(() => { window.__csp = []; document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective))
    try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.setItem('ontoforge.lang', 'fr') } catch {} })
  const page = await ctx.newPage()
  const errs = []
  page.on('pageerror', e => errs.push(String(e).slice(0, 160)))
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(m.text().slice(0, 160)) })
  await page.goto(srv.base + '/'); await page.waitForSelector('[data-testid=login]')
  await page.fill('[data-testid=login-user]', 'jerem'); await page.fill('[data-testid=login-password]', srv.users.jerem); await page.click('[data-testid=login-submit]')
  await page.waitForSelector('.proj-grid, .proj, h1')
  const go = async h => { await page.goto(srv.base + '/#' + h); await sleep(1300) }

  // 1. sélecteur de fournisseur de Krakie : « Mock (démonstration) » sans « · mock »
  await go(`/projet/${pid}/tableau`)
  const st = await page.evaluate(async () => (await fetch('/api/assistant/status')).json())
  const opts = await (async () => {
    await page.locator('[data-testid=krakie-fab]').tap(); await sleep(900)
    return page.locator('[data-testid=ag-llm-select] option, [data-testid=ag-llm-one]').allInnerTexts().catch(() => [])
  })()
  const mockLabels = opts.filter(o => /mock/i.test(o))
  log('Krakie : le libellé du fournisseur de démonstration ne répète pas « mock »', mockLabels.length > 0 && mockLabels.every(o => (o.match(/mock/gi) || []).length === 1) && opts.length === 2, JSON.stringify(opts) + ' / ' + (st.providers || []).map(p => p.name).join())

  // 2. aucun débordement de la page sur les écrans secondaires
  const P = `/projet/${pid}/`
  const screens = ['tableau', 'ontologie', 'ontologie-liste', 'carte-metier', 'shapes', 'fichiers', 'conformite', 'shacl', 'analyse', 'modele', 'exports', 'versions', 'requetes', 'assistant', 'plus', 'documentation'].map(s => P + s).concat(['/', '/parametres', '/administration', '/aide'])
  const over = []
  for (const h of screens) { await go(h); if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)) over.push(h.replace(P, '')) }
  log(`aucun débordement horizontal de la page sur ${screens.length} écrans`, over.length === 0, over.join())

  // 3. Paramètres : tableaux recomposés en cartes étiquetées
  await go('/parametres')
  const card = await page.evaluate(() => { const td = [...document.querySelectorAll('.set-table td[data-l]')]
    const hid = [...document.querySelectorAll('.set-table td.empty')].every(e => getComputedStyle(e).display === 'none')
    return { n: td.length, labelled: td.every(e => e.dataset.l.length > 0), hid, thead: getComputedStyle(document.querySelector('.set-table thead')).display,
      before: td[0] ? getComputedStyle(td[0], '::before').content : '' } })
  log('Paramètres › Fournisseurs : cartes étiquetées (nom, type, par défaut), cellules vides masquées', card.n >= 3 && card.labelled && card.hid && card.thead === 'none' && /Nom/.test(card.before), JSON.stringify(card))

  // 3b. Paramètres › Endpoints : cartes étiquetées (actif, nom, URL, délai sans unité en double)
  await page.evaluate(() => [...document.querySelectorAll('[role=tab]')].find(e => /SPARQL/.test(e.textContent))?.click()); await sleep(900)
  const epc = await page.evaluate(() => { const td = [...document.querySelectorAll('.set-table td[data-l]')]; return { n: td.length, labels: td.map(e => e.dataset.l), thead: document.querySelector('.set-table') ? getComputedStyle(document.querySelector('.set-table thead')).display : 'absent' } })
  log('Paramètres › Endpoints : cartes étiquetées (Nom, URL, Délai)', epc.thead === 'none' && ['Nom', 'URL', 'Délai'].every(l => epc.labels.includes(l)), JSON.stringify(epc))
  // 3c. Fournisseurs : pas de libellé « Par défaut » devant la pastille « Par défaut »
  await go('/parametres')
  const dup = await page.evaluate(() => [...document.querySelectorAll('.set-table td')].filter(e => e.querySelector('.set-chip.on') && e.dataset.l).length)
  log('Fournisseurs : pas de « Par défaut : ★ Par défaut » en double', dup === 0, String(dup))

  // 4. champs à 16 px (Shapes, Documentation)
  await go(P + 'shapes')
  await page.locator('.shacl [class*=row], .shacl li, .shacl button').filter({ hasText: 'Garage' }).first().click().catch(() => {}); await sleep(700)
  const tiny = await page.evaluate(() => [...document.querySelectorAll('.shacl input:not([type=checkbox]), .shacl select')].filter(e => e.getBoundingClientRect().width > 0 && parseFloat(getComputedStyle(e).fontSize) < 16).map(e => e.getAttribute('aria-label') || e.tagName))
  log('Shapes : champs à 16 px', tiny.length === 0, tiny.join())
  await go('/aide')
  const dt = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('[data-testid=doc-search]')).fontSize))
  log('Documentation : recherche à 16 px', dt >= 16, String(dt))

  log('aucune erreur de console ni violation de CSP', errs.length === 0 && (await page.evaluate(() => window.__csp.length)) === 0, errs.join(' | '))
  await browser.close()
} finally { await srv.stop() }
console.log(`\n${total - ko}/${total} vérifications OK`)
process.exit(ko ? 1 : 0)
