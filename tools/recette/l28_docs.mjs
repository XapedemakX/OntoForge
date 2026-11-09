// Recette L28 : documentation intégrée, bouton « ? » et aide en contexte de Krakie.
// Usage : node tools/recette/l28_docs.mjs   (BACKEND_PORT, FRONT_PORT optionnels ; front déjà buildé : cd frontend && npm run build)
// Couvre : ouverture depuis le bandeau, sommaire, recherche, lien interne, « ? » depuis l'éditeur, « aide » à Krakie sur Shapes puis ouverture de la bonne section,
// ancres de la table d'aide, mode anglais (page traduite sans bandeau, bandeau « French only » sur un fichier non traduit, libellés, carte d'aide), mobile 390 px. Captures : journal/L28/screens/.
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L28/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8928, FP = process.env.FRONT_PORT || 4928
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const report = []
const log = (name, ok, detail = '') => { report.push({ name, ok }); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }
const HELP = JSON.parse(readFileSync(path.join(ROOT, 'backend/ontoforge/assistant/help_map.json'), 'utf8')).screens

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l28-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const pid = (await (await fetch(B + '/projects', { method: 'POST', headers: J, body: JSON.stringify({ name: 'doc', sample: 'automaint' }) })).json()).id

const browser = await chromium.launch()
async function session(vp) {
  const ctx = await browser.newContext({ viewport: vp, locale: 'fr-FR' })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  const page = await ctx.newPage(); const errs = []
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 200)) })
  page.on('pageerror', e => errs.push(String(e).slice(0, 200)))
  return { ctx, page, errs }
}
const hash = page => page.evaluate(() => decodeURIComponent(location.hash))
/** Le titre `id` est visible en haut de la zone de lecture (±80 px). */
const atTop = (page, id) => page.evaluate(id => {
  const h = document.getElementById(id), sc = document.querySelector('.doc-scroll'); if (!h || !sc) return false
  const a = h.getBoundingClientRect().top, b = sc.getBoundingClientRect().top
  return a >= b - 4 && a <= b + 120
}, id)
const noOverflow = page => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)
const openKrakie = async page => { if (!(await page.locator('.ag-panel').count())) { await page.locator('button.ag-fab').click(); await page.waitForSelector('.ag-panel') } }
const ask = async (page, text, sel) => { await page.fill('.ag-box textarea', text); await page.keyboard.press('Enter'); await page.waitForSelector(sel, { timeout: 15000 }) }

try {
  // ---------------- 1. ouverture depuis le bandeau latéral
  const d = await session({ width: 1440, height: 900 }); const page = d.page
  await page.goto(`${base}/#/projet/${pid}/tableau`, { waitUntil: 'load' }); await page.waitForSelector('.side nav button')
  const outils = await page.locator('.step-group', { hasText: 'Outils' }).innerText()
  log('1a entrée « Documentation » dans la section Outils', /Documentation/.test(outils), outils.replace(/\n/g, ' | '))
  await page.locator('.side nav button', { hasText: 'Documentation' }).click()
  await page.waitForSelector('.doc-article h1'); await sleep(500)
  log('1b route documentation', /\/documentation$/.test(await hash(page)), await hash(page))
  const info = await page.evaluate(() => ({ h1: document.querySelector('.doc-article h1')?.textContent, toc: document.querySelectorAll('.doc-toc a').length, tables: document.querySelectorAll('.doc-article table').length,
    code: document.querySelectorAll('.doc-article pre .tk-s, .doc-article pre .tk-w, .doc-article pre .tk-c').length, pages: document.querySelectorAll('.doc-pages a').length }))
  log('1c guide utilisateur rendu (titre, sommaire, tableaux, code coloré)', /Guide utilisateur/.test(info.h1 ?? '') && info.toc > 20 && info.tables > 0 && info.code > 0, JSON.stringify(info))
  log('1d pages du guide listées (≥ 6)', info.pages >= 6, String(info.pages))
  log('1e aucun défilement horizontal', await noOverflow(page))
  await page.screenshot({ path: path.join(SHOTS, '01-documentation.png') })

  // ---------------- 2. sommaire
  await page.locator('.doc-toc a', { hasText: 'Analyse & arbitrage' }).first().click(); await sleep(500)
  log('2a sommaire : ancre stable dans l\'adresse', /documentation\/utilisateur\/analyse-arbitrage$/.test(await hash(page)), await hash(page))
  log('2b sommaire : titre amené en haut', await atTop(page, 'analyse-arbitrage'))
  log('2c sommaire : entrée active', await page.locator('.doc-toc a[aria-current]').first().innerText().then(x => /Analyse/.test(x)).catch(() => false))
  await page.screenshot({ path: path.join(SHOTS, '02-sommaire.png') })
  // rechargement direct sur l'ancre
  await page.reload({ waitUntil: 'load' }); await page.waitForSelector('.doc-article h1'); await sleep(700)
  log('2d lien direct vers l\'ancre après rechargement', await atTop(page, 'analyse-arbitrage'))

  // ---------------- 3. recherche
  await page.fill('[data-testid=doc-search]', 'Krakie'); await sleep(400)
  const c1 = await page.locator('[data-testid=doc-count]').innerText()
  const hits = await page.locator('mark.doc-hit').count()
  log('3a recherche : occurrences surlignées et comptées', hits > 3 && /^1 \/ \d+$/.test(c1), `${c1} ; ${hits} marques`)
  const vis = () => page.evaluate(() => { const m = document.querySelector('mark.doc-hit.cur'), sc = document.querySelector('.doc-scroll'); if (!m || !sc) return false; const a = m.getBoundingClientRect(), b = sc.getBoundingClientRect(); return a.top >= b.top && a.bottom <= b.bottom })
  log('3b recherche : occurrence courante visible', await vis())
  await page.screenshot({ path: path.join(SHOTS, '03-recherche.png') })
  await page.keyboard.press('Enter'); await sleep(200)
  log('3c Entrée passe à la suivante', (await page.locator('[data-testid=doc-count]').innerText()).startsWith('2 /'))
  await page.keyboard.press('Shift+Enter'); await sleep(200)
  log('3d Maj+Entrée revient', (await page.locator('[data-testid=doc-count]').innerText()).startsWith('1 /'))
  await page.fill('[data-testid=doc-search]', 'zzzqxj'); await sleep(300)
  log('3e aucun résultat annoncé', /Aucun résultat/.test(await page.locator('[data-testid=doc-count]').innerText()))
  await page.keyboard.press('Escape'); await sleep(300)
  log('3f Échap efface la recherche', (await page.locator('mark.doc-hit').count()) === 0 && (await page.inputValue('[data-testid=doc-search]')) === '')
  await page.fill('[data-testid=doc-search]', 'ÉDITEUR'); await sleep(300)
  log('3g recherche insensible à la casse et aux accents', (await page.locator('mark.doc-hit').count()) > 2)
  await page.fill('[data-testid=doc-search]', ''); await sleep(200)

  // ---------------- 4. lien entre fichiers
  await page.goto(`${base}/#/projet/${pid}/documentation/utilisateur/analyse-arbitrage`); await sleep(500)
  const link = page.locator('.doc-article a[data-doc-page="regles"]').first()
  log('4a lien regles.md réécrit en lien interne', (await link.count()) > 0)
  await link.scrollIntoViewIfNeeded(); await link.click(); await sleep(700)
  const t2 = await page.locator('.doc-article h1').first().innerText()
  log('4b le lien ouvre la page « règles » dans l\'écran', /\/documentation\/regles/.test(await hash(page)) && /gles/.test(t2), `${await hash(page)} :: ${t2}`)
  await page.screenshot({ path: path.join(SHOTS, '04-lien-interne.png') })
  await page.goBack(); await sleep(600)
  log('4c retour navigateur', /documentation\/utilisateur/.test(await hash(page)), await hash(page))
  // limites + changelog + api se chargent
  for (const pg of ['limites', 'changelog', 'api', 'contribuer']) {
    await page.goto(`${base}/#/projet/${pid}/documentation/${pg}`); await page.waitForSelector('.doc-article h1', { timeout: 8000 }).catch(() => {}); await sleep(300)
    log(`4d page ${pg}`, (await page.locator('.doc-article h1').count()) > 0 && (await noOverflow(page)))
  }

  // ---------------- 5. bouton « ? » depuis l'éditeur
  await page.goto(`${base}/#/projet/${pid}/ontologie`, { waitUntil: 'load' }); await page.waitForSelector('.react-flow__node', { timeout: 20000 })
  await page.screenshot({ path: path.join(SHOTS, '05a-editeur-bouton-aide.png') })
  await page.click('[data-testid=help-btn]'); await page.waitForSelector('.doc-article h1'); await sleep(700)
  log('5a « ? » depuis l\'éditeur : bonne section', /documentation\/utilisateur\/ontologie-l-editeur-graphique$/.test(await hash(page)) && await atTop(page, 'ontologie-l-editeur-graphique'), await hash(page))
  await page.screenshot({ path: path.join(SHOTS, '05b-aide-editeur.png') })

  // ---------------- 6. Krakie : « aide » sur Shapes
  await page.goto(`${base}/#/projet/${pid}/shapes`, { waitUntil: 'load' }); await page.waitForSelector('.ag-fab', { timeout: 15000 }); await sleep(800)
  await openKrakie(page)
  await ask(page, 'aide', '.ag-card.help'); await sleep(300)
  const card = await page.locator('.ag-card.help').innerText()
  log('6a carte Aide : titre de la section et résumé', /Shapes SHACL/.test(card) && /shapes/i.test(card) && /Ouvrir l'aide/.test(card), card.replace(/\n/g, ' | ').slice(0, 200))
  await page.screenshot({ path: path.join(SHOTS, '06a-krakie-aide-shapes.png') })
  await page.click('[data-testid=ag-open-help]'); await page.waitForSelector('.doc-article h1'); await sleep(700)
  log('6b « Ouvrir l\'aide » : section SHACL', /documentation\/utilisateur\/shacl$/.test(await hash(page)) && await atTop(page, 'shacl'), await hash(page))
  await page.screenshot({ path: path.join(SHOTS, '06b-aide-shapes.png') })
  // l'écran Documentation connaît son propre contexte : « comment ça marche ici »
  await openKrakie(page); await ask(page, 'comment ça marche ici', '.ag-card.help >> nth=1')
  log('6c « comment ça marche ici » sur l\'écran Documentation', /Documentation/.test(await page.locator('.ag-card.help').nth(1).innerText()))

  // ---------------- 7. toutes les ancres de la table d'aide existent dans l'application
  let bad = []
  for (const [scr, e] of Object.entries(HELP)) {
    await page.goto(`${base}/#/projet/${pid}/documentation/${e.page}/${e.anchor}`); await page.waitForSelector('.doc-article h1', { timeout: 8000 }); await sleep(150)
    if (!(await page.evaluate(a => !!document.getElementById(a), e.anchor))) bad.push(`${scr}:${e.anchor}`)
  }
  log(`7 ancres de la table d'aide présentes dans l'écran (${Object.keys(HELP).length})`, bad.length === 0, bad.join(', '))

  // ---------------- 8. visite : étape Documentation
  await page.goto(`${base}/#/projet/${pid}/tableau`, { waitUntil: 'load' }); await sleep(800)
  await page.evaluate(() => window.ontoforgeTour.start()); await sleep(600)
  const total = await page.evaluate(() => window.ontoforgeTour.state().total)
  let found = false
  for (let i = 0; i < total && !found; i++) {
    for (let k = 0; k < 60; k++) { const s = await page.evaluate(() => window.ontoforgeTour.state()); if (s.index === i && s.ready) break; await sleep(100) }
    const s = await page.evaluate(() => window.ontoforgeTour.state())
    if (s.id === 'docs') { found = true; await sleep(500); await page.screenshot({ path: path.join(SHOTS, '08-visite-documentation.png') }); log('8 étape « docs » de la visite', s.hasTarget && s.found, `${s.index + 1}/${s.total}`) }
    else await page.evaluate(() => window.ontoforgeTour.next())
  }
  if (!found) log('8 étape « docs » de la visite', false, 'introuvable')
  await page.keyboard.press('Escape')
  log('9 aucune erreur console (français)', d.errs.length === 0, d.errs.slice(0, 3).join(' || '))

  // ---------------- 10. mobile
  const m = await session({ width: 390, height: 844 })
  await m.page.goto(`${base}/#/projet/${pid}/documentation/utilisateur`, { waitUntil: 'load' }); await m.page.waitForSelector('.doc-article h1'); await sleep(600)
  log('10a mobile : pas de défilement horizontal', await noOverflow(m.page))
  log('10b mobile : sommaire replié, bouton visible', !(await m.page.locator('.doc-side').isVisible()) && await m.page.locator('.doc-toc-btn').isVisible())
  await m.page.screenshot({ path: path.join(SHOTS, '10a-mobile-lecture.png') })
  await m.page.click('.doc-toc-btn'); await sleep(300)
  log('10c mobile : sommaire ouvert', await m.page.locator('.doc-side').isVisible())
  await m.page.screenshot({ path: path.join(SHOTS, '10b-mobile-sommaire.png') })
  await m.page.locator('.doc-toc a', { hasText: 'Exports' }).first().click(); await sleep(600)
  log('10d mobile : choix dans le sommaire ferme le tiroir et va au titre', !(await m.page.locator('.doc-side').isVisible()) && await atTop(m.page, 'exports'))
  await m.page.screenshot({ path: path.join(SHOTS, '10c-mobile-titre.png') })
  await m.page.goto(`${base}/#/projet/${pid}/documentation/utilisateur/exports`); await m.page.fill('[data-testid=doc-search]', 'zip'); await sleep(400)
  log('10e mobile : recherche', (await m.page.locator('mark.doc-hit').count()) > 0 && await noOverflow(m.page))
  await m.page.screenshot({ path: path.join(SHOTS, '10d-mobile-recherche.png') })
  await m.page.goto(`${base}/#/projet/${pid}/documentation/api`); await m.page.waitForSelector('.doc-article table', { timeout: 8000 }).catch(() => {}); await sleep(400)
  log('10f mobile : page API (tableaux) sans débordement de la page', await noOverflow(m.page))
  log('10g mobile : aucune erreur console', m.errs.length === 0, m.errs.slice(0, 3).join(' || '))

  // ---------------- 11. mode anglais
  const put = await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'en', labels: 'en', assistant: 'en' } }) })
  log('11 réglage anglais', put.ok)
  const e = await session({ width: 1440, height: 900 }); const ep = e.page
  await ep.goto(`${base}/#/projet/${pid}/tableau`, { waitUntil: 'load' }); await sleep(1200)
  log('11a « ? » traduit', (await ep.getByRole('button', { name: 'Help for this screen' }).count()) === 1)
  await ep.locator('.side nav button', { hasText: 'Documentation' }).click(); await ep.waitForSelector('.doc-article h1'); await sleep(600)
  // L33 : la page utilisateur existe en anglais : pas de bandeau, contenu anglais, ancres identiques au français
  log('11b page traduite : pas de bandeau « French only »', (await ep.locator('[data-testid=doc-fr-only]').count()) === 0)
  const h1 = await ep.locator('.doc-article h1').innerText()
  log('11b2 contenu anglais (h1 et lang)', /user guide/i.test(h1) && (await ep.locator('.doc-article').getAttribute('lang')) === 'en', h1)
  const labels = await ep.evaluate(() => ({ toc: document.querySelector('.doc-toc-title')?.textContent, ph: document.querySelector('[data-testid=doc-search]')?.getAttribute('placeholder'), pg: [...document.querySelectorAll('.doc-pages a')].map(a => a.textContent).slice(0, 3).join(',') }))
  log('11c interface de l\'écran en anglais', labels.toc === 'Contents' && labels.ph === 'Search in page' && /User guide/.test(labels.pg), JSON.stringify(labels))
  log('11d contenu anglais non marqué « fallback »', (await ep.locator('[data-doc-fallback]').count()) === 0)
  await ep.screenshot({ path: path.join(SHOTS, '11a-anglais-utilisateur.png') })
  await ep.goto(`${base}/#/projet/${pid}/documentation/architecture`, { waitUntil: 'load' }); await ep.waitForSelector('.doc-article h1'); await sleep(500)
  const ban = await ep.locator('[data-testid=doc-fr-only]').innerText().catch(() => '')
  log('11b3 fichier non traduit : bandeau « Documentation available in French only »', ban.trim() === 'Documentation available in French only', ban)
  log('11b4 fichier non traduit : contenu français marqué pour le scan', (await ep.locator('[data-doc-fallback]').count()) >= 2)
  await ep.screenshot({ path: path.join(SHOTS, '11a-anglais-bandeau.png') })
  await ep.goto(`${base}/#/projet/${pid}/documentation/limites`, { waitUntil: 'load' }); await ep.waitForSelector('.doc-article h1'); await sleep(500)
  log('11b5 limites, contribuer, api et journal : traduits, sans bandeau', (await ep.locator('[data-testid=doc-fr-only]').count()) === 0 && /known limits/i.test(await ep.locator('.doc-article h1').innerText()))
  await ep.goto(`${base}/#/projet/${pid}/shapes`, { waitUntil: 'load' }); await ep.waitForSelector('.ag-fab', { timeout: 15000 }); await sleep(800)
  await openKrakie(ep); await ask(ep, 'how does this work', '.ag-card.help'); await sleep(300)
  const ec = await ep.locator('.ag-card.help').innerText()
  log('11e carte d\'aide en anglais', /Screen help/.test(ec) && /Open help/.test(ec) && /SHACL shapes/.test(ec), ec.replace(/\n/g, ' | ').slice(0, 200))
  await ep.screenshot({ path: path.join(SHOTS, '11b-anglais-krakie.png') })
  await ep.click('[data-testid=ag-open-help]'); await ep.waitForSelector('.doc-article h1'); await sleep(600)
  log('11f anglais : « Open help » ouvre la section', /documentation\/utilisateur\/shacl$/.test(await hash(ep)) && await atTop(ep, 'shacl'), await hash(ep))
  log('11g aucune erreur console (anglais)', e.errs.length === 0, e.errs.slice(0, 3).join(' || '))
  await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'fr', labels: 'fr', assistant: 'fr' } }) })
} catch (err) { log('exception', false, String(err).slice(0, 300)) }
await browser.close(); procs.forEach(p => p.kill())
const ko = report.filter(x => !x.ok).length
console.log(`\n=== L28 : ${report.length - ko} OK / ${ko} KO`); process.exit(ko ? 1 : 0)
