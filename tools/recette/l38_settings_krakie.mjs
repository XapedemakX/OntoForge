// Recette L38 : Krakie sur l'écran Paramètres, sans projet. Usage : BACKEND_PORT=8983 FRONT_PORT=4983 node tools/recette/l38_settings_krakie.mjs   (front déjà buildé)
// Démarre un backend temporaire (mock) + `vite preview`, puis : Paramètres sans projet, aquarium visible, question sur le LLM en mode mock (réponse pas à pas + cartes),
// « Aller à cette section », « Ouvrir l'aide » (guide hors projet), bouton « ? », fausse clé enregistrée par l'interface puis « Tester la connexion » ;
// AUCUNE trace de la clé dans les requêtes et réponses /api/assistant ; réglages inchangés ; aquarium qui ne recouvre rien d'important ; version anglaise.
// Captures (clair / sombre, desktop / mobile) : journal/L38/screens/.
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L38/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8983, FP = process.env.FRONT_PORT || 4983
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
process.on('exit', () => procs.forEach(p => p.kill()))
const report = []
const log = (name, ok, detail = '') => { report.push({ name, ok }); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l38-')), ONTOFORGE_LLM_PROVIDER: 'mock', ONTOFORGE_SECRET_KEY: 'recette-l38' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(B + p, { method: m, headers: J, body: b === undefined ? undefined : JSON.stringify(b) }); return r.json() }
const FAKE_KEY = ['sk', 'ant', 'FAUXTEST', '0123456789abcdef'].join('-') // assemblée à l'exécution : fausse clé de test, sans déclencher le détecteur de secrets du dépôt
const settingsBefore = JSON.stringify(await api('GET', '/settings'))

const browser = await chromium.launch()
const session = async ({ vp = { width: 1440, height: 860 }, scheme = 'light', locale = 'fr-FR' } = {}) => {
  const ctx = await browser.newContext({ viewport: vp, locale, colorScheme: scheme, deviceScaleFactor: 1 })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1') } catch {} })
  const page = await ctx.newPage(); const errs = []; const traffic = []
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push('console: ' + m.text().slice(0, 200)) })
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('request', r => { if (/\/api\/assistant/.test(r.url())) traffic.push({ url: r.url(), method: r.method(), body: r.postData() ?? '' }) })
  page.on('response', async r => { if (/\/api\/assistant/.test(r.url())) { try { traffic.push({ url: r.url(), status: r.status(), body: await r.text() }) } catch {} } })
  return { ctx, page, errs, traffic }
}
const ask = async (page, text, { wait = '.ag-msg.assistant .ag-bubble:not(.ag-dots)' } = {}) => {
  const n = await page.locator('.ag-msg.assistant').count()
  await page.locator('.ag-box textarea').fill(text); await page.locator('.ag-box .btn.primary').click()
  await page.waitForFunction(([sel, k]) => document.querySelectorAll(sel).length > k && !document.querySelector('.ag-dots'), [wait, n], { timeout: 30000 })
  await sleep(250)
  return page.locator('.ag-msg.assistant').last()
}
// clic de souris sur le récif (seuls Krakie et le récif captent le clic), sinon Ctrl+K
const openKrakie = async page => {
  const vp = page.viewportSize(); await page.mouse.move(vp.width - 70, vp.height - 6); await sleep(150); await page.mouse.click(vp.width - 70, vp.height - 6)
  try { await page.waitForSelector('.ag-panel', { timeout: 2500 }) } catch { console.log('   (clic récif sans effet : repli Ctrl+K)'); await page.keyboard.press('Control+k'); await page.waitForSelector('.ag-panel', { timeout: 5000 }) }
  await sleep(400)
}
const closePanel = async page => { if (await page.locator('.ag-panel').count()) { await page.locator('.ag-panel button[aria-label="Fermer"]').click(); await sleep(300) } }
const tabSel = (page, label) => page.getByRole('tab', { name: label, exact: true })

// ----------------------------------------------------------------------------- 1. desktop clair, français
const S = await session()
const { page } = S
await page.goto(`${base}/#/parametres`, { waitUntil: 'load' })
await page.waitForSelector('.set-page', { timeout: 15000 }); await page.waitForSelector('.ag-fab', { timeout: 15000 }); await sleep(2500)
log('Paramètres sans projet : Krakie (aquarium) visible', await page.locator('.ag-fab').isVisible() && (await api('GET', '/projects')).length === 0)
await page.screenshot({ path: `${SHOTS}/desktop-clair-parametres.png` })

// contexte dès le chargement (l'écran publie avant que le panneau s'abonne) : écran + onglet affiché
await openKrakie(page)
const chip0 = (await page.locator('.ag-ctx .ag-chip').first().innerText()).trim()
log('contexte dès le chargement : Paramètres · Fournisseurs LLM', /Paramètres · Fournisseurs LLM/.test(chip0), chip0)
await closePanel(page)

// l'aquarium ne recouvre rien d'important : en bas de page, aucun contrôle ne chevauche le bouton flottant
const overlaps = async (pg, tag) => {
  const bad = await pg.evaluate(async () => {
    const sc = document.querySelector('main.content') ?? document.scrollingElement
    const out = []
    for (const where of ['top', 'bottom']) {
      sc.scrollTo({ top: where === 'top' ? 0 : 1e6 }); await new Promise(r => setTimeout(r, 200))
      const f = document.querySelector('.ag-fab')?.getBoundingClientRect(); if (!f) continue
      for (const el of document.querySelectorAll('.set-page button, .set-page a, .set-page input, .set-page select, .set-page th, .set-page td, .set-page p, .set-page h1, .set-page h2, .set-page h3')) {
        let r = el.getBoundingClientRect(); if (!r.width || !r.height) continue
        if (/^(P|H1|H2|H3|TH|TD)$/.test(el.tagName)) { const g = document.createRange(); g.selectNodeContents(el); r = g.getBoundingClientRect(); if (!r.width || !r.height) continue }  // texte seulement, pas la boîte du bloc
        if (r.left < f.right && r.right > f.left && r.top < f.bottom && r.bottom > f.top) out.push(where + ':' + el.tagName + ':' + (el.textContent || '').trim().slice(0, 30))
      }
    }
    sc.scrollTo({ top: 0 }); return out
  })
  log(`aquarium : rien d'important recouvert (${tag})`, bad.length === 0, bad.join(' | '))
}
for (const [label, tab] of [['Fournisseurs LLM', 'llm'], ['Langues', 'lang'], ['Valeurs par défaut', 'defaults'], ['Versions', 'versions'], ['Affichage', 'display'], ['Endpoints SPARQL', 'sparql']]) {
  await tabSel(page, label).click(); await sleep(500); await overlaps(page, 'desktop ' + tab)
}

// mode mock : question sur le LLM depuis un autre onglet
await tabSel(page, 'Langues').click(); await sleep(300)
await openKrakie(page)
const ctxChip = (await page.locator('.ag-ctx .ag-chip').first().innerText()).trim()
log('ligne de contexte : écran + onglet affiché', /Paramètres · Langues/.test(ctxChip), ctxChip)
log('suggestions propres à l\'onglet', (await page.locator('.ag-sugg .ag-pill').allInnerTexts()).some(x => /langues/i.test(x)))
const a1 = await ask(page, 'Comment configurer le LLM ?')
const t1 = await a1.innerText()
log('mock : réponse pas à pas (1. … 4.)', /(^|\n)1\. /.test(t1) && /(^|\n)4\. /.test(t1) && /Anthropic/.test(t1) && /Ollama/.test(t1), t1.slice(0, 80).replace(/\n/g, ' '))
log('mock : cartes Aller à cette section + Ouvrir l\'aide, pas de test (rien de configuré)',
  await a1.getByTestId('ag-settings-goto').count() === 1 && await a1.getByTestId('ag-open-help').count() === 1 && await a1.getByTestId('ag-settings-test').count() === 0)
await page.screenshot({ path: `${SHOTS}/desktop-clair-panneau.png` })
// « Aller à cette section » : bascule sur l'onglet LLM, défile, met en évidence
await a1.getByTestId('ag-settings-goto').click(); await sleep(500)
log('« Aller à cette section » : onglet Fournisseurs LLM ouvert', (await tabSel(page, 'Fournisseurs LLM').getAttribute('aria-selected')) === 'true')
log('« Aller à cette section » : bloc mis en évidence', await page.locator('.set-sec.flash[data-set-sec="llm"]').count() === 1)
await page.screenshot({ path: `${SHOTS}/desktop-clair-section.png` })
// « Ouvrir l'aide » : guide hors projet, bonne ancre
await a1.getByTestId('ag-open-help').click(); await sleep(1200)
log('« Ouvrir l\'aide » : #/aide/utilisateur/parametres-fournisseurs-llm', page.url().endsWith('#/aide/utilisateur/parametres-fournisseurs-llm'), page.url())
log('guide affiché sans projet, section Fournisseurs LLM', await page.locator('.doc-article h3#parametres-fournisseurs-llm').count() === 1)
await page.screenshot({ path: `${SHOTS}/desktop-clair-aide.png` })
await page.goBack(); await page.waitForSelector('.set-page'); await sleep(800)
await closePanel(page)

// « ? » : la section du guide de l'onglet affiché
for (const [label, anchor] of [['Langues', 'parametres-langues'], ['Endpoints SPARQL', 'parametres-endpoints-sparql'], ['Versions', 'versions-des-normes-et-des-cibles']]) {
  await tabSel(page, label).click(); await sleep(300)
  await page.getByTestId('help-btn').click(); await sleep(800)
  log(`« ? » sur l'onglet ${label} -> #${anchor}`, page.url().endsWith('/' + anchor), page.url())
  await page.goBack(); await page.waitForSelector('.set-page'); await sleep(500)
}

// intention « aide » dans Krakie
await tabSel(page, 'Valeurs par défaut').click(); await sleep(300)
if (!await page.locator('.ag-panel').count()) await openKrakie(page)
const a2 = await ask(page, 'aide')
log('Krakie « aide » : carte de la section Valeurs par défaut', (await a2.getByTestId('ag-open-help').count()) === 1 && /Valeurs par défaut/.test(await a2.innerText()))

// fausse clé enregistrée par l'interface (fournisseur Anthropic non défini par défaut)
await closePanel(page)
await tabSel(page, 'Fournisseurs LLM').click(); await sleep(300)
await page.getByRole('button', { name: 'Ajouter un fournisseur' }).first().click()
const form = page.locator('form.set-form')
await form.getByLabel('Nom').fill('Claude (test)')
await form.locator('input[type=password]').fill(FAKE_KEY)
await form.getByRole('button', { name: 'Enregistrer' }).click(); await page.waitForSelector('table.set-table >> text=Claude (test)', { timeout: 10000 })
const prov = (await api('GET', '/settings')).llm_providers.find(p => p.name === 'Claude (test)')
log('fausse clé enregistrée (jamais relue : has_key seulement)', !!prov && prov.has_key === true && !JSON.stringify(prov).includes(FAKE_KEY))

await openKrakie(page)
const a3 = await ask(page, 'teste la connexion')
log('carte « Tester la connexion » proposée pour le fournisseur configuré', await a3.getByTestId('ag-settings-test').count() === 1)
await a3.getByTestId('ag-settings-test').click()
await page.waitForSelector('[data-testid=ag-settings-test-result] .set-res.ok, [data-testid=ag-settings-test-result] .set-res.ko', { timeout: 30000 })
const res = (await a3.getByTestId('ag-settings-test-result').innerText()).replace(/\s+/g, ' ')
log('test de connexion exécuté (résultat affiché, hors ligne : échec attendu, sans fuite)', res.length > 10 && !res.includes(FAKE_KEY), res.slice(0, 120))
const a4 = await ask(page, 'quelle est ma clé API ?')
log('« quelle est ma clé ? » : refus clair', /n'ai pas accès/.test(await a4.innerText()))
const a5 = await ask(page, 'où en est ma configuration ?')
log('diagnostic : le fournisseur par défaut est la démonstration alors qu\'un fournisseur est configuré', /démonstration/.test(await a5.innerText()) && /Claude \(test\)/.test(await a5.innerText()))
await page.screenshot({ path: `${SHOTS}/desktop-clair-diagnostic.png` })

// aucune trace de la clé dans le trafic /api/assistant (requêtes et réponses) ; une requête au moins par question
const sent = S.traffic.filter(x => x.method === 'POST')
const leak = S.traffic.filter(x => x.body.includes(FAKE_KEY) || x.body.includes('FAUXTEST'))
log('requêtes /api/assistant/chat sans project_id, contexte « settings »', sent.length >= 5 && sent.every(x => /\/api\/assistant\/chat$/.test(x.url) && !/project_id/.test(x.body) && /"screen":"settings"/.test(x.body)), `${sent.length} requêtes`)
log('aucune clé dans les requêtes ni les réponses /api/assistant', leak.length === 0 && S.traffic.length >= 10, `${S.traffic.length} échanges`)
log('aucun contexte de projet envoyé', sent.every(x => !/projectId|"target"|perimeter/.test(x.body)))
const settingsAfter = (await api('GET', '/settings'))
log('Krakie n\'a modifié aucun réglage (seul l\'ajout fait à la main existe)', settingsAfter.llm_providers.length === 2 && settingsAfter.default_provider_id === 'mock' && JSON.stringify({ ...settingsAfter, llm_providers: [] }) === JSON.stringify({ ...JSON.parse(settingsBefore), llm_providers: [] }))
log('aucun projet créé ni touché', (await api('GET', '/projects')).length === 0)
log('aucune erreur JS / console', S.errs.length === 0, S.errs.join(' | '))
await S.ctx.close()

// ----------------------------------------------------------------------------- 2. captures sombre, mobile
for (const [scheme, vp, tag] of [['dark', { width: 1440, height: 860 }, 'desktop-sombre'], ['light', { width: 390, height: 800 }, 'mobile-clair'], ['dark', { width: 390, height: 800 }, 'mobile-sombre']]) {
  const s = await session({ vp, scheme })
  await s.page.goto(`${base}/#/parametres`, { waitUntil: 'load' }); await s.page.waitForSelector('.ag-fab', { timeout: 15000 }); await sleep(2200)
  await s.page.screenshot({ path: `${SHOTS}/${tag}-parametres.png` })
  if (vp.width < 600) await overlaps(s.page, tag)
  await openKrakie(s.page)
  await ask(s.page, 'Comment configurer Ollama en local ?')
  await s.page.screenshot({ path: `${SHOTS}/${tag}-panneau.png` })
  await s.ctx.close()
}

// ----------------------------------------------------------------------------- 3. anglais
await api('PUT', '/settings', { language: { ui: 'en', labels: 'en', assistant: 'en' } })
const E = await session({ locale: 'en-GB' })
await E.page.goto(`${base}/#/parametres`, { waitUntil: 'load' }); await E.page.waitForSelector('.ag-fab', { timeout: 15000 }); await sleep(1500)
await openKrakie(E.page)
const e1 = await ask(E.page, 'How do I set up a SPARQL endpoint?')
const te = await e1.innerText()
log('anglais : réponse en anglais pas à pas + cartes anglaises', /(^|\n)1\. /.test(te) && /Add an endpoint/.test(te) && !/Ajouter/.test(te) && /Go to this section/.test(await e1.innerText()) && /Open help/.test(await e1.innerText()))
await e1.getByTestId('ag-settings-goto').click(); await sleep(600)
log('anglais : « Go to this section » ouvre l\'onglet SPARQL endpoints', (await tabSel(E.page, 'SPARQL endpoints').getAttribute('aria-selected')) === 'true')
await e1.getByTestId('ag-open-help').click(); await sleep(1000)
log('anglais : le guide anglais s\'ouvre à la bonne section', E.page.url().endsWith('#/aide/utilisateur/parametres-endpoints-sparql') && await E.page.locator('.doc-article h3#parametres-endpoints-sparql').count() === 1)
await E.page.screenshot({ path: `${SHOTS}/desktop-en-aide.png` })
log('anglais : aucune erreur JS', E.errs.length === 0, E.errs.join(' | '))
await E.ctx.close()
await api('PUT', '/settings', { language: { ui: 'fr', labels: 'fr', assistant: 'fr' } })

await browser.close()
const bad = report.filter(r => !r.ok)
console.log(`\n${report.length - bad.length}/${report.length} OK`)
process.exit(bad.length ? 1 : 0)
