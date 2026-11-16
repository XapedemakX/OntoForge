// Recette L45 : téléphone — choix du fournisseur dans Krakie, panneaux repliables, raccourcis retirés (iPhone 15, Pixel 7 ; iPad mini = version ordinateur inchangée).
// Usage : BACKEND_PORT=9061 FRONT_PORT=5071 node tools/recette/mobile_l45.mjs [--mode=local|web] [--devices=iphone15,pixel7,ipadmini] [--shots]
// Front buildé avant (cd frontend && npm run build). Sans --mode, les deux versions se suivent sur les mêmes ports.
// Vérifie : sélecteur de fournisseur de Krakie (2 fournisseurs configurés dont mock : visible, entier dans l'écran, >= 44 px, champ >= 16 px, choix transmis à l'API,
// aucune clé ni adresse dans la page ; un seul fournisseur : lecture seule ; lecteur en version web), panneaux repliables (replié : titre + description ; ouvert : titre seul ;
// aria-expanded ; clavier ; état mémorisé ; fr et en ; replié par défaut sauf le panneau principal), absence des raccourcis sous 700 px (et présence sur iPad),
// cibles >= 44 px, aucune erreur de console ni violation de CSP. Clés et mots de passe assemblés à l'exécution. Captures facultatives (--shots) : journal/L45/recette/.
import { createRequire } from 'node:module'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { startWeb, apiClient, ROOT } from './web_server.mjs'
const require = createRequire(import.meta.url)
let pw
try { pw = require('playwright') } catch { pw = require('/opt/node22/lib/node_modules/playwright') }
const { chromium, devices } = pw
const sleep = ms => new Promise(r => setTimeout(r, ms))
const arg = (k, d) => (process.argv.find(a => a.startsWith(`--${k}=`)) || '').split('=')[1] || d
const SHOTS = process.argv.includes('--shots') ? path.join(ROOT, 'journal/L45/recette') : null
if (SHOTS) mkdirSync(SHOTS, { recursive: true })
const DEV = { iphone15: devices['iPhone 15'], pixel7: devices['Pixel 7'], ipadmini: devices['iPad Mini'] }
const want = arg('devices', 'iphone15,pixel7,ipadmini').split(',')
const modes = arg('mode', 'local,web').split(',')
const FAKE_KEY = ['sk', 'ant', 'FAUXTEST', Math.random().toString(16).slice(2, 14)].join('-')   // assemblée à l'exécution : fausse clé de test
const FAKE_URL = 'https://llm-' + Math.random().toString(16).slice(2, 8) + '.example.test/v1'
let ko = 0
const log = (name, ok, detail = '') => { if (!ok) ko++; console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

// cibles tactiles (même mesure que mobile_l44.mjs)
const measure = () => {
  const W = innerWidth, H = innerHeight
  const rectOf = el => { const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return null; if (r.bottom <= 0 || r.top >= H || r.right <= 0 || r.left >= W) return null
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) return null; return r }
  const label = el => (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || el.getAttribute('placeholder') || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 40)
  const inter = [...document.querySelectorAll('a[href], button, input, select, textarea, [role=button], [role=tab], [tabindex]:not([tabindex="-1"])')]
    .filter(el => !el.closest('[aria-hidden=true]') && !el.disabled && !el.closest('[inert]') && !el.closest('[hidden]'))
    .filter(el => !el.closest('.react-flow__node, .react-flow__edge, .react-flow__handle, .react-flow__renderer, svg.bm-svg, .cy canvas'))
  const small = []; let n = 0
  for (const el of inter) {
    const box = (el.type === 'checkbox' || el.type === 'radio') ? (el.closest('label') || el) : el
    const r = rectOf(box); if (!r) continue
    n++; if (r.width < 43.5 || r.height < 43.5) small.push(`${label(el)} ${Math.round(r.width)}x${Math.round(r.height)}`)
  }
  const tiny = inter.filter(el => /INPUT|SELECT|TEXTAREA/.test(el.tagName) && !['checkbox', 'radio', 'range', 'color'].includes(el.type) && rectOf(el) && parseFloat(getComputedStyle(el).fontSize) < 16).map(label)
  return { n, small, tiny, overflow: document.documentElement.scrollWidth > innerWidth + 1 }
}
const KEYS_RE = /Ctrl\s?\+|Ctrl\s?\/|⌘|Maj\s?\+\s?Entrée|Shift\s?\+\s?Enter|Alt\s?\+\s?clic/i

async function run(mode) {
  console.log(`\n=== version ${mode === 'web' ? 'web (Cloud Run reproduite)' : 'locale'} ===`)
  const srv = await startWeb({ mode, backendPort: process.env.BACKEND_PORT || 9061, frontPort: process.env.FRONT_PORT || 5071 })
  const base = srv.base
  const api = apiClient(base)
  if (mode === 'web') await api.login('jerem', srv.users.jerem)
  const pid = (await api.call('POST', '/api/projects', { name: 'Automaint', sample: 'automaint' })).json.id
  if (mode === 'web') log('partage en lecteur (bob)', (await api.call('POST', `/api/projects/${pid}/access/members`, { login: 'bob', role: 'reader' })).status < 300)
  // 2 fournisseurs configurés : mock (par défaut) + Claude (fausse clé)
  const add = await api.call('POST', '/api/settings/providers', { name: 'Claude (test)', kind: 'anthropic', api_key: FAKE_KEY, base_url: FAKE_URL })
  log('fournisseur Claude de test ajouté', add.status === 201, String(add.status))
  const browser = await chromium.launch()

  const newPage = async (key, who = 'jerem', lang = 'fr') => {
    const d = { ...DEV[key] }; delete d.defaultBrowserType
    const ctx = await browser.newContext({ ...d, locale: lang === 'fr' ? 'fr-FR' : 'en-GB', colorScheme: 'light', ignoreHTTPSErrors: true })
    await ctx.addInitScript(l => { window.__csp = []; document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI))
      try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); if (!localStorage.getItem('ontoforge.lang')) localStorage.setItem('ontoforge.lang', l) } catch {} }, lang)
    const page = await ctx.newPage()
    const errs = []
    page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 160)))
    page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push('console: ' + m.text().slice(0, 160)) })
    await page.goto(base + '/', { waitUntil: 'load' })
    if (mode === 'web') {
      await page.waitForSelector('[data-testid=login]')
      await page.fill('[data-testid=login-user]', who); await page.fill('[data-testid=login-password]', srv.users[who]); await page.click('[data-testid=login-submit]')
    }
    await page.waitForSelector('.proj-grid, .proj, h1', { timeout: 15000 })
    return { ctx, page, errs }
  }
  const go = async (page, s) => { await page.goto(`${base}/#/projet/${pid}/${s}`); await sleep(1300) }
  const shot = async (page, name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${mode}-${name}.png`) }) }
  const fold = (page, id) => page.locator(`[data-fold="${id}"]`)
  const uiProvider = page => page.evaluate(() => { try { return JSON.parse(localStorage.getItem('ontoforge.assistant.ui') || '{}').provider || '' } catch { return '' } })

  for (const key of want) {
    const tag = `${mode}/${key}`
    const phone = key !== 'ipadmini'
    const { ctx, page, errs } = await newPage(key)

    // ---------- 3. raccourcis ----------
    await go(page, 'tableau')
    await page.waitForSelector('.dash', { timeout: 10000 }).catch(() => {}); await sleep(1200)
    const body0 = await page.locator('body').innerText()
    log(`accueil : carte « Raccourcis » ${phone ? 'retirée' : 'conservée (version ordinateur)'} (${tag})`, /Raccourcis|Shortcuts/.test(body0) === !phone, body0.slice(-300).replace(/\n/g, " "))
    if (phone) {
      const fabTitle = await page.locator('[data-testid=krakie-fab]').getAttribute('title')
      log(`aucune indication de raccourci clavier sur le bouton Krakie (${tag})`, !fabTitle || !KEYS_RE.test(fabTitle), String(fabTitle))
      const leaks = []
      for (const s of ['tableau', 'ontologie', 'ontologie-liste', 'carte-metier', 'analyse', 'requetes', 'exports', 'versions', 'plus']) {
        await go(page, s); const tx = await page.locator('body').innerText()
        const m = tx.match(KEYS_RE); if (m) leaks.push(`${s}: ${m[0]}`)
      }
      log(`aucune indication de raccourci clavier visible sur les écrans du téléphone (${tag})`, leaks.length === 0, leaks.join(' ; '))
    }

    // ---------- 2. panneaux repliables ----------
    await go(page, 'tableau')
    const nFold = await page.locator('[data-fold]').count()
    log(`accueil : panneaux repliables ${phone ? 'présents' : 'absents (version ordinateur)'} (${tag})`, phone ? nFold >= (mode === 'web' ? 4 : 3) : nFold === 0, `${nFold}`)
    if (phone) {
      const sc = fold(page, 'tableau/scopes'); const btn = sc.locator('.fold-btn')
      log(`panneau « Périmètres » replié par défaut, aria-expanded=false (${tag})`, (await btn.getAttribute('aria-expanded')) === 'false')
      const closedTxt = (await btn.innerText()).replace(/\s+/g, ' ')
      log(`replié : titre + description courte (${tag})`, /^Périmètres — définir les périmètres de votre ontologie$/.test(closedTxt), closedTxt)
      const fs = await page.evaluate(() => { const b = document.querySelector('[data-fold="tableau/scopes"] .fold-d'); return b ? parseFloat(getComputedStyle(b).fontSize) : 0 })
      const ft = await page.evaluate(() => parseFloat(getComputedStyle(document.querySelector('[data-fold="tableau/scopes"] .fold-t')).fontSize))
      log(`description plus petite que le titre (${tag})`, fs > 0 && fs < ft, `${fs} < ${ft}`)
      log(`replié : contenu masqué (${tag})`, !(await sc.locator('.fold-bd').isVisible()))
      const bh = (await btn.boundingBox()).height
      log(`en-tête de panneau >= 44 px (${tag})`, bh >= 43.5, String(Math.round(bh)))
      await shot(page, `${key}-accueil-replie`)
      await btn.tap(); await sleep(300)
      log(`ouvert : aria-expanded=true et contenu visible (${tag})`, (await btn.getAttribute('aria-expanded')) === 'true' && await sc.locator('.fold-bd').isVisible())
      const openTxt = (await btn.innerText()).replace(/\s+/g, ' ')
      log(`ouvert : titre seul, sans description (${tag})`, openTxt === 'Périmètres', openTxt)
      await shot(page, `${key}-accueil-ouvert`)
      // mémorisé
      await page.reload(); await sleep(1500)
      log(`l'état ouvert est mémorisé après rechargement (${tag})`, (await fold(page, 'tableau/scopes').locator('.fold-btn').getAttribute('aria-expanded')) === 'true')
      // clavier : Entrée et Espace
      const b2 = fold(page, 'tableau/findings').locator('.fold-btn'); await b2.focus(); await page.keyboard.press('Enter'); await sleep(200)
      const k1 = await b2.getAttribute('aria-expanded'); await page.keyboard.press('Space'); await sleep(200)
      log(`clavier : Entrée ouvre, Espace referme (${tag})`, k1 === 'true' && (await b2.getAttribute('aria-expanded')) === 'false')
      log(`aria-controls pointe vers le contenu (${tag})`, await page.evaluate(() => { const b = document.querySelector('[data-fold="tableau/scopes"] .fold-btn'); return !!document.getElementById(b.getAttribute('aria-controls')) }))
      // mesure des cibles avec tout ouvert puis tout replié
      const m = await page.evaluate(measure)
      log(`accueil : cibles >= 44 px et champs >= 16 px (${tag})`, m.small.length === 0 && m.tiny.length === 0 && !m.overflow, [...m.small, ...m.tiny].slice(0, 4).join(' | '))
      // Versions : panneau principal ouvert, les autres repliés
      await go(page, 'versions')
      log(`versions : panneau principal ouvert, les autres repliés (${tag})`,
        (await fold(page, 'versions/targets').locator('.fold-btn').getAttribute('aria-expanded')) === 'true' && (await fold(page, 'versions/shacl').locator('.fold-btn').getAttribute('aria-expanded')) === 'false' && (await fold(page, 'versions/libs').locator('.fold-btn').getAttribute('aria-expanded')) === 'false')
      const mv = await page.evaluate(measure)
      log(`versions : cibles >= 44 px (${tag})`, mv.small.length === 0 && !mv.overflow, mv.small.slice(0, 4).join(' | '))
      // Requêtes : requêtes sauvegardées repliées
      await go(page, 'requetes')
      const q = fold(page, 'requetes/saved').locator('.fold-btn')
      log(`requêtes : « Requêtes sauvegardées » repliées avec description (${tag})`, (await q.getAttribute('aria-expanded')) === 'false' && /Requêtes sauvegardées — /.test((await q.innerText()).replace(/\s+/g, ' ')))
      await shot(page, `${key}-requetes`)
      // anglais
      await api.call('PUT', '/api/settings', { language: { ui: 'en', labels: 'en', assistant: 'en' } })
      const en = await newPage(key, 'jerem', 'en')
      await go(en.page, 'tableau'); await en.page.reload(); await sleep(1500)
      const et = (await fold(en.page, 'tableau/scopes').locator('.fold-btn').innerText()).replace(/\s+/g, ' ')
      log(`en anglais : « Scopes — define the perimeters of your ontology » (${tag})`, et === 'Scopes — define the perimeters of your ontology', et)
      await shot(en.page, `${key}-accueil-en`)
      log(`aucune erreur de console en anglais (${tag})`, en.errs.length === 0, en.errs.slice(0, 2).join(' ; '))
      await en.ctx.close()
      await api.call('PUT', '/api/settings', { language: { ui: 'fr', labels: 'fr', assistant: 'fr' } })
    }

    // ---------- 1. fournisseur dans Krakie ----------
    await go(page, 'tableau')
    if (phone) {
      await page.locator('[data-testid=krakie-fab]').tap(); await sleep(900)
      const sel = page.locator('[data-testid=ag-llm-select]')
      log(`Krakie : sélecteur de fournisseur présent (${tag})`, await sel.isVisible())
      const box = await sel.boundingBox(); const vp = page.viewportSize()
      log(`Krakie : sélecteur entier dans l'écran, non coupé (${tag})`, !!box && box.x >= 0 && box.x + box.width <= vp.width && box.y >= 0 && box.y + box.height <= vp.height, JSON.stringify(box))
      log(`Krakie : sélecteur >= 44 px de haut, texte >= 16 px (${tag})`, !!box && box.height >= 43.5 && parseFloat(await sel.evaluate(e => getComputedStyle(e).fontSize)) >= 16, `${Math.round(box?.height)} px`)
      const opts = await sel.locator('option').allInnerTexts()
      log(`Krakie : les fournisseurs configurés sont proposés (Mock et Claude) (${tag})`, opts.length === 2 && opts.some(o => /mock/i.test(o)) && opts.some(o => /Claude/.test(o)), opts.join(' | '))
      const lbl = await page.locator('.ag-llm').innerText()
      log(`Krakie : libellé du sélecteur (${tag})`, /Modèle de Krakie/.test(lbl), lbl.replace(/\s+/g, ' ').slice(0, 60))
      await shot(page, `${key}-krakie-fournisseur`)
      // choix Claude -> la requête part avec ce fournisseur
      const ids = await sel.evaluate(e => [...e.options].map(o => ({ v: o.value, t: o.text })))
      const claude = ids.find(o => /Claude/.test(o.t)), mock = ids.find(o => /mock/i.test(o.t))
      const sent = []
      page.on('request', r => { if (r.url().endsWith('/api/assistant/chat') && r.method() === 'POST') { try { sent.push(JSON.parse(r.postData() || '{}').provider_id) } catch {} } })
      await sel.selectOption(claude.v); await sleep(200)
      log(`Krakie : le choix est mémorisé (même état que sur ordinateur) (${tag})`, (await uiProvider(page)) === claude.v)
      await page.locator('.ag-box textarea').fill('bonjour'); await page.locator('.ag-box .btn.primary').tap(); await sleep(2500)
      log(`Krakie : la question part avec le fournisseur choisi (Claude) (${tag})`, sent[0] === claude.v, String(sent[0]))
      await sel.selectOption(mock.v); await sleep(200)
      await page.locator('.ag-box textarea').fill('que contient cette ontologie ?'); await page.locator('.ag-box .btn.primary').tap(); await sleep(2500)
      log(`Krakie : puis avec Mock après changement (${tag})`, sent[1] === mock.v, String(sent[1]))
      log(`Krakie : réponse de Mock affichée (${tag})`, (await page.locator('.ag-msg.assistant:not(.err) .ag-bubble').count()) > 0)
      const html = await page.content()
      log(`Krakie : aucune clé ni adresse de fournisseur dans la page (${tag})`, !html.includes(FAKE_KEY) && !html.includes(FAKE_URL) && !(await page.evaluate(() => JSON.stringify(localStorage))).includes(FAKE_KEY))
      const st = await api.call('GET', '/api/assistant/status')
      log(`Krakie : l'API d'état n'expose ni clé ni adresse (${tag})`, !JSON.stringify(st.json).includes(FAKE_KEY) && !JSON.stringify(st.json).includes(FAKE_URL))
      await shot(page, `${key}-krakie-reponse`)
      const m = await page.evaluate(measure)
      log(`Krakie : cibles >= 44 px et champs >= 16 px dans la feuille (${tag})`, m.small.length === 0 && m.tiny.length === 0, [...m.small, ...m.tiny].slice(0, 4).join(' | '))
      // un seul fournisseur : lecture seule
      await page.keyboard.press('Escape'); await page.locator('.sheet-x').first().tap().catch(() => {}); await sleep(400)
      await page.route('**/api/assistant/status', r => r.fulfill({ json: { provider: 'mock', model: 'mock', configured: true, default_provider_id: 'mock', providers: [{ id: 'mock', name: 'Mock', kind: 'mock', model: 'mock', configured: true, default: true }] } }))
      await page.reload(); await sleep(1500)
      await page.locator('[data-testid=krakie-fab]').tap(); await sleep(900)
      log(`Krakie : un seul fournisseur = affiché en lecture, sans liste (${tag})`, (await page.locator('[data-testid=ag-llm-one]').isVisible()) && (await page.locator('[data-testid=ag-llm-select]').count()) === 0, (await page.locator('.ag-llm').innerText()).replace(/\s+/g, ' '))
      await shot(page, `${key}-krakie-un-fournisseur`)
      await page.unroute('**/api/assistant/status')
    } else {
      // iPad : panneau d'ordinateur (inchangé), sélecteur dans l'en-tête
      await page.locator('.ag-fab').click({ force: true }).catch(() => {}); await page.waitForSelector('.ag-head select', { timeout: 6000 }).catch(() => {}); await sleep(300)
      log(`iPad : panneau Krakie d'ordinateur avec son sélecteur d'en-tête, sans sélecteur du téléphone (${tag})`, (await page.locator('.ag-head select').count()) === 1 && (await page.locator('[data-testid=ag-llm]').count()) === 0)
    }
    const csp = await page.evaluate(() => window.__csp || [])
    log(`aucune violation de CSP (${tag})`, csp.length === 0, csp.join(', '))
    log(`aucune erreur de console (${tag})`, errs.length === 0, errs.slice(0, 3).join(' ; '))
    await ctx.close()
  }

  // lecteur (version web) : même choix que sur ordinateur (les fournisseurs configurés sont proposés), sans clé ni adresse
  if (mode === 'web') {
    const { ctx, page, errs } = await newPage('iphone15', 'bob')
    await go(page, 'tableau')
    await page.locator('[data-testid=krakie-fab]').tap(); await sleep(900)
    const opts = await page.locator('[data-testid=ag-llm-select] option').allInnerTexts().catch(() => [])
    log('lecteur : les fournisseurs configurés sont proposés dans Krakie (comme sur ordinateur)', opts.length === 2, opts.join(' | '))
    const html = await page.content()
    log('lecteur : aucune clé ni adresse dans la page', !html.includes(FAKE_KEY) && !html.includes(FAKE_URL))
    const c = apiClient(base); await c.login('bob', srv.users.bob)
    const st = await c.call('GET', '/api/settings')
    log('lecteur : les réglages restent expurgés (ni clé ni adresse)', !JSON.stringify(st.json).includes(FAKE_KEY) && !JSON.stringify(st.json).includes(FAKE_URL))
    await shot(page, 'lecteur-krakie')
    log('lecteur : aucune erreur de console', errs.length === 0, errs.slice(0, 2).join(' ; '))
    await ctx.close()
  }
  await browser.close(); await srv.stop()
}

for (const m of modes) await run(m)
console.log(ko ? `\n${ko} échec(s)` : '\nTout est vert')
process.exit(ko ? 1 : 0)
