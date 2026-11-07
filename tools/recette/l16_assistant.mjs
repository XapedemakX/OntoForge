// L16 : parcours Playwright de l'assistant global (Ctrl+K, application d'une action, tableau de bord, mobile).
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
const SHOTS = path.join(ROOT, 'journal/L16/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = 8931, FP = 4931
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (c, a, o) => { const p = spawn(c, a, { stdio: 'ignore', ...o }); procs.push(p); return p }
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l16-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const pid = (await (await fetch(B + '/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'l16', sample: 'automaint' }) })).json()).id
const out = []; const ok = (n, c, d = '') => { out.push(c); console.log((c ? 'OK  ' : 'KO  ') + n + ' ' + d) }
const browser = await chromium.launch()
try {
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 860 } })).newPage()
  const errs = []; page.on('pageerror', e => errs.push(String(e))); page.on('console', m => { if (m.type() === 'error') errs.push(m.text()) })
  await page.goto(`${base}/#/projet/${pid}/ontologie`); await page.waitForSelector('.react-flow__node', { timeout: 20000 })
  await page.click('.react-flow__node >> text=Véhicule', { timeout: 5000 }).catch(() => {})
  await page.screenshot({ path: `${SHOTS}/01-editeur-fab.png` })
  await page.keyboard.press('Control+k'); await page.waitForSelector('.ag-panel')
  ok('Ctrl+K ouvre le panneau', true)
  const ctxTxt = await page.locator('.ag-ctx').innerText(); ok('ligne de contexte', /Éditeur/.test(ctxTxt), ctxTxt.replace(/\n/g, ' '))
  await page.fill('.ag-box textarea', 'ajoute la classe Pneu sous Pièce avec une propriété pression en bar'); await page.keyboard.press('Enter')
  await page.waitForSelector('.ag-card.ops'); await sleep(300)
  await page.screenshot({ path: `${SHOTS}/02-apercu.png` })
  const prev = await page.locator('.ag-card.ops .ag-preview').innerText(); ok('aperçu lisible', /Pneu/.test(prev) && /Pièce/.test(prev), prev.replace(/\n/g, ' | '))
  await page.click('.ag-card.ops >> text=Appliquer'); await page.waitForSelector('.ag-card.applied'); await sleep(900)
  await page.screenshot({ path: `${SHOTS}/03-applique.png` })
  const proj = await (await fetch(`${B}/projects/${pid}`)).json()
  ok('classe Pneu créée', Object.keys(proj.onto.classes).some(k => k.endsWith('#Pneu')))
  ok('propriété pression créée', Object.keys(proj.onto.datatype_properties).some(k => k.endsWith('#pression')))
  ok('Pneu visible dans l\'éditeur', await page.locator('.react-flow__node', { hasText: 'Pneu' }).count() > 0)
  await page.click('.ag-card.applied >> text=Annuler'); await page.waitForSelector('.ag-card.undone'); await sleep(300)
  const p2 = await (await fetch(`${B}/projects/${pid}`)).json(); ok('annulation', !Object.keys(p2.onto.classes).some(k => k.endsWith('#Pneu')))
  // tableau de bord
  await page.goto(`${base}/#/projet/${pid}/tableau`); await page.waitForSelector('.ag-panel', { timeout: 15000 }); ok('le panneau reste ouvert d\'un écran à l\'autre', true); await sleep(800)
  await page.fill('.ag-box textarea', 'cherche les véhicules dont le kilométrage dépasse 100000'); await page.keyboard.press('Enter')
  await page.waitForSelector('.ag-card.guided_query'); await sleep(300)
  await page.screenshot({ path: `${SHOTS}/04-tableau-requete.png` })
  await page.click('text=Ouvrir dans Requêtes'); await sleep(800)
  ok('navigation vers Requêtes', page.url().endsWith('/requetes'))
  ok('aucune erreur console', errs.length === 0, errs.slice(0, 3).join(' || '))
  // mobile
  const m = await (await browser.newContext({ viewport: { width: 390, height: 800 } })).newPage()
  await m.goto(`${base}/#/projet/${pid}/tableau`); await m.waitForSelector('.ag-fab', { timeout: 15000 }); await sleep(600)
  await m.screenshot({ path: `${SHOTS}/05-mobile-fab.png` })
  await m.click('.ag-fab'); await m.waitForSelector('.ag-panel'); await sleep(300)
  await m.screenshot({ path: `${SHOTS}/06-mobile-panneau.png` })
  const w = await m.evaluate(() => document.documentElement.scrollWidth); ok('mobile sans défilement horizontal', w <= 391, String(w))
} catch (e) { console.log('KO exception', e); out.push(false) } finally { await browser.close(); procs.forEach(p => p.kill()); process.exit(out.every(Boolean) ? 0 : 1) }
