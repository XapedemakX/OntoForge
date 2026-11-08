// L25 : amorcer une ontologie depuis un document (PDF de démo, fournisseur mock = repli sans LLM, aucun réseau).
// Usage : node tools/recette/l25_document.mjs   (front déjà buildé : cd frontend && npm run build)
import { createRequire } from 'node:module'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L25/screens'); mkdirSync(SHOTS, { recursive: true })
const PDF = path.join(ROOT, 'samples/automaint/automaint-cahier-des-charges.pdf')
if (!existsSync(PDF)) execFileSync('python3', [path.join(ROOT, 'samples/automaint/make_cahier_des_charges.py')])
const BP = 8935, FP = 4935
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (c, a, o) => { const p = spawn(c, a, { stdio: 'ignore', ...o }); procs.push(p); return p }
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l25-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const pid = (await (await fetch(B + '/projects', { method: 'POST', headers: J, body: JSON.stringify({ name: 'l25' }) })).json()).id
const out = []; const ok = (n, c, d = '') => { out.push(c); console.log((c ? 'OK  ' : 'KO  ') + n + ' ' + d) }
const proj = async () => (await fetch(`${B}/projects/${pid}`)).json()
const browser = await chromium.launch()
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1') } catch {} })
  const page = await ctx.newPage()
  const errs = []; const reqs = []
  page.on('pageerror', e => errs.push(String(e))); page.on('console', m => { if (m.type() === 'error') errs.push(m.text()) })
  page.on('request', r => { const u = new URL(r.url()); if (!['127.0.0.1', 'localhost'].includes(u.hostname)) reqs.push(r.url()) })
  await page.goto(`${base}/#/projet/${pid}/assistant`); await page.waitForSelector('.as-qa', { timeout: 20000 })

  // 1. dépôt du PDF
  await page.click('button:has-text("Amorcer depuis un document")')
  await page.waitForSelector('.di-drop')
  await page.screenshot({ path: `${SHOTS}/01-import.png` })
  ok('lien « Essayer avec le cahier des charges de démo »', await page.locator('.di-demo').count() === 1)
  const t0 = Date.now()
  await page.click('.di-demo')
  await page.waitForSelector('.di-file .di-est', { timeout: 15000 })
  ok('démo chargée en un clic', /automaint-cahier-des-charges\.pdf/.test(await page.locator('.di-fh').innerText()), `${Date.now() - t0} ms`)
  const meta = await page.locator('.di-fh').innerText()
  ok('PDF lu : 2 pages', /2 p\./.test(meta), meta.replace(/\n/g, ' '))
  const est = await page.locator('.di-est').innerText(); ok('estimation affichée, rien envoyé en mock', /Rien n'est envoyé/.test(est), est)
  ok('pas d\'avertissement d\'envoi en mock', await page.locator('.di-warn').count() === 0)
  await page.screenshot({ path: `${SHOTS}/02-estimation.png` })

  // 2. analyse : questions de compétence puis proposition
  await page.click('.di button:has-text("Lancer l\'analyse")')
  await page.waitForSelector('.dr-q li', { timeout: 30000 })
  const nq = await page.locator('.dr-q li').count(); ok('5 à 10 questions de compétence', nq >= 5 && nq <= 10, String(nq))
  ok('badges couvert / non couvert', await page.locator('.dr-badge.ok').count() > 0 && await page.locator('.dr-badge.ko').count() > 0)
  ok('brouillon signalé approximatif', await page.locator('.dr-engine.approx').count() === 1)
  await page.waitForSelector('.pc-item', { timeout: 10000 })
  const items = await page.locator('.pc-item').count(); ok('éléments proposés', items >= 10, String(items))
  const tags = await page.locator('.pc-tag.confirm').count(); ok('badge « À confirmer » sur chaque élément', tags === items, `${tags}/${items}`)
  const labels = await page.locator('.pc-item >> .as-item-t b').allInnerTexts()
  ok('classes Véhicule, Garage, Pneu, Contrôle technique', ['Véhicule', 'Garage', 'Pneu', 'Contrôle technique'].every(x => labels.includes(x)), labels.slice(0, 6).join(', '))
  const lintTxt = await page.locator('.as-prop .pc-lint').innerText()
  ok('lint : W07 en une ligne d\'information repliable, pas d\'orange', await page.locator('.as-prop .pc-lint .pc-info').count() === 1 && await page.locator('.as-prop .pc-lint details:not(.pc-info)').count() === 0 && !/\d+ avertissement/.test(lintTxt), lintTxt.replace(/\n/g, ' | ').slice(0, 120))
  const grp = await page.locator('.pc-gt').allInnerTexts()
  ok('groupes avec compteurs', grp.length === 3 && grp.every(x => /\d/.test(x)), grp.join(' / ').replace(/\n/g, ' '))
  ok('un « Tout accepter » par groupe', await page.locator('.pc-gh button:has-text("Tout accepter")').count() === 3)
  const vis = await page.locator('.pc-item').evaluateAll(els => els.filter(e => { const r = e.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight - 60 }).length)
  ok('au moins 12 éléments visibles à 1440×900', vis >= 12, String(vis))
  await page.fill('.pc-filter input', 'pneu')
  const nf = await page.locator('.pc-item').count(); ok('filtre texte', nf > 0 && nf < items, `${nf}/${items}`)
  await page.screenshot({ path: `${SHOTS}/03b-filtre.png` })
  await page.fill('.pc-filter input', '')
  const before = await proj(); ok('rien appliqué avant acceptation', Object.keys(before.onto.classes).length === 0)
  await page.screenshot({ path: `${SHOTS}/03-proposition.png` })

  // 3. extrait source repliable (au clic sur la ligne)
  const pneu = page.locator('.pc-item', { has: page.locator('b', { hasText: /^Pneu$/ }) }).first()
  ok('extrait replié par défaut', await pneu.locator('.pc-quote').count() === 0)
  await pneu.locator('.pc-toggle').click()
  const quote = await pneu.locator('.pc-quote blockquote').innerText()
  ok('extrait source visible avec sa page', /Pneu/.test(quote) && /page 1/.test(await pneu.locator('.pc-quote').innerText()), quote)
  ok('extrait ≤ 300 caractères', quote.length <= 300)
  await page.screenshot({ path: `${SHOTS}/04-extrait.png` })

  // 4. accepter une partie, rejeter un élément
  const garage = page.locator('.pc-item', { has: page.locator('b', { hasText: /^Garage$/ }) }).first()
  await garage.locator('button.ok').click(); await sleep(1200)
  let p2 = await proj(); ok('Garage appliqué après acceptation', Object.keys(p2.onto.classes).some(k => k.endsWith('#Garage')))
  ok('les autres restent non appliqués', !Object.keys(p2.onto.classes).some(k => k.endsWith('#Pneu')))
  const nb = await page.locator('.pc-item').count()
  await page.locator('.pc-item >> button.ko').last().click(); await sleep(300)
  ok('rejet : un élément de moins', await page.locator('.pc-item').count() === nb - 1)
  await page.click('.as-foot button:has-text("Tout accepter")'); await sleep(2000)
  p2 = await proj()
  ok('Tout accepter applique le reste', ['Pneu', 'Vehicule', 'ControleTechnique'].every(n => Object.keys(p2.onto.classes).some(k => k.endsWith('#' + n))))
  await page.screenshot({ path: `${SHOTS}/05-accepte.png` })

  // 5. retrouvé dans l'éditeur
  await page.click('button:has-text("Voir dans l\'éditeur")')
  await page.waitForSelector('.react-flow__node', { timeout: 20000 })
  ok('Pneu visible dans l\'éditeur', await page.locator('.react-flow__node', { hasText: 'Pneu' }).count() > 0)
  await page.screenshot({ path: `${SHOTS}/06-editeur.png` })

  // 5b. fournisseur hébergé factice : l'appel n'a jamais lieu (estimation seulement, la 409 vient avant tout envoi)
  const hostedId = (await (await fetch(B + '/settings/providers', { method: 'POST', headers: J, body: JSON.stringify({ name: 'Fournisseur hébergé (démo)', kind: 'anthropic', api_key: 'cle-factice-jamais-utilisee' }) })).json()).id
  const hctx = await browser.newContext({ viewport: { width: 1440, height: 900 } }); await hctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1') } catch {} })
  const hp = await hctx.newPage(); hp.on('request', r => { const u = new URL(r.url()); if (!['127.0.0.1', 'localhost'].includes(u.hostname)) reqs.push(r.url()) })
  await hp.goto(`${base}/#/projet/${pid}/assistant`); await hp.waitForSelector('.as-qa', { timeout: 20000 })
  await hp.selectOption('.as-prov select', { label: 'Fournisseur hébergé (démo)' })
  await hp.click('button:has-text("Amorcer depuis un document")'); await hp.click('.di-demo')
  await hp.waitForSelector('.di-warn', { timeout: 15000 })
  const runBtn = hp.locator('.di-actions button')
  ok('hébergé : avertissement de confidentialité affiché', /Confidentialité/.test(await hp.locator('.di-warn').innerText()))
  ok('hébergé : envoi bloqué tant que la case est décochée', await runBtn.isDisabled())
  ok('hébergé : estimation des appels et de la taille', /appels/.test(await hp.locator('.di-est').innerText()), await hp.locator('.di-est').innerText())
  await hp.screenshot({ path: `${SHOTS}/09-hosted-avant.png` })
  await hp.check('.di-ok input'); ok('hébergé : case cochée débloque l\'envoi', await runBtn.isEnabled())
  await hp.screenshot({ path: `${SHOTS}/09-hosted.png` })
  const r409 = await fetch(`${B}/assistant/document/draft`, { method: 'POST', headers: J, body: JSON.stringify({ project_id: pid, provider_id: hostedId, document: { name: 'x.txt', pages: [{ page: 1, text: 'Un garage est un lieu.' }] }, confirm_hosted: false }) })
  ok('hébergé : 409 sans confirmation, avant tout appel réseau', r409.status === 409, String(r409.status))
  await hctx.close()

  // 6. panneau Krakie
  await page.keyboard.press('Control+k'); await page.waitForSelector('.ag-panel')
  await page.click('.ag-box button[aria-label="Amorcer depuis un document"]'); await page.waitForSelector('.di.compact .di-drop')
  await page.setInputFiles('.di.compact input[type=file]', PDF); await page.waitForSelector('.di.compact .di-est', { timeout: 15000 })
  await page.click('.di.compact button:has-text("Lancer l\'analyse")'); await page.waitForSelector('.ag-panel .dr-q li', { timeout: 30000 })
  ok('panneau Krakie : questions de compétence', await page.locator('.ag-panel .dr-q li').count() >= 5)
  await sleep(300); await page.screenshot({ path: `${SHOTS}/07-krakie.png` })
  ok('aucune requête hors de la machine', reqs.length === 0, reqs.slice(0, 2).join(' '))
  ok('aucune erreur console', errs.length === 0, errs.slice(0, 3).join(' || '))

  // 7. mobile
  const m = await (await browser.newContext({ viewport: { width: 390, height: 800 } })).newPage()
  await m.goto(`${base}/#/projet/${pid}/assistant`); await m.waitForSelector('.as-qa', { timeout: 15000 })
  await m.click('button:has-text("Amorcer depuis un document")'); await m.setInputFiles('.di input[type=file]', PDF)
  await m.waitForSelector('.di-est', { timeout: 15000 }); await m.click('.di button:has-text("Lancer l\'analyse")'); await m.waitForSelector('.dr-q li', { timeout: 30000 }); await sleep(300)
  await m.screenshot({ path: `${SHOTS}/08-mobile.png` })
  ok('mobile sans défilement horizontal', await m.evaluate(() => document.documentElement.scrollWidth) <= 391)
} catch (e) { console.log('KO exception', e); out.push(false) } finally { await browser.close(); procs.forEach(p => p.kill()); process.exit(out.every(Boolean) ? 0 : 1) }
