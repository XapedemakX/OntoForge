// L19 : recette courte du triplestore local (écran Requêtes) : sélection de l'option, données de démo, requête guidée Diesel (10 lignes),
// inférence, validation SHACL, vidage. Usage : node tools/recette/l19_local_store.mjs (front déjà buildé : cd frontend && npm run build).
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
const SHOTS = path.join(ROOT, 'journal/L19/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8961, FP = process.env.FRONT_PORT || 4961
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (c, a, o) => { const p = spawn(c, a, { stdio: 'ignore', ...o }); procs.push(p); return p }
process.on('exit', () => procs.forEach(p => p.kill()))
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l19-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: process.env.FRONT_DIR || path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const pid = (await (await fetch(B + '/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'l19', sample: 'automaint' }) })).json()).id
const AM = 'https://w3id.org/ontoforge/automaint#'
const diesel = { root: { var: 'v', class_iri: AM + 'Vehicle' }, steps: [
  { from_var: 'v', property_iri: AM + 'hasEngine', to_var: 'm', to_class_iri: AM + 'Engine', optional: false, negated: false, inverse: false },
  { from_var: 'm', property_iri: AM + 'usesFuel', to_var: 'f', to_class_iri: AM + 'FuelType', optional: false, negated: false, inverse: false }],
  filters: [{ var: 'f', kind: 'in_values', is_iri: true, values: [AM + 'Diesel'] }],
  select: [{ var: 'v' }, { var: 'v', property_iri: AM + 'registrationNumber' }, { var: 'm' }, { var: 'f' }], order_by: [], limit: 10 }
const out = []; const ok = (n, c, d = '') => { out.push(c); console.log((c ? 'OK  ' : 'KO  ') + n + ' ' + d) }
const browser = await chromium.launch()
try {
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
  const errs = []; page.on('pageerror', e => errs.push(String(e)))
  await page.goto(`${base}/#/projet/${pid}/requetes`)
  await page.evaluate(([k, v]) => localStorage.setItem(k, v), ['ontoforge.pending-query.' + pid, JSON.stringify({ guided: diesel })])
  await page.reload(); await page.waitForSelector('.qep select', { timeout: 20000 })
  const opts = await page.locator('.qep select option').allInnerTexts()
  ok('option « Triplestore local (test) » toujours présente', opts.some(o => /local/i.test(o)), opts.join(' | '))
  await page.selectOption('.qep select', '__local'); await page.waitForSelector('[data-testid=local-panel]')
  await page.waitForFunction(() => /^0\b/.test(document.querySelector('[data-testid=local-count]')?.textContent?.trim() ?? ''), null, { timeout: 15000 }).catch(() => {})
  ok('panneau affiché, magasin vide', /^0\b/.test((await page.locator('[data-testid=local-count]').innerText()).trim()), await page.locator('[data-testid=local-count]').innerText())
  await page.screenshot({ path: `${SHOTS}/01-panneau-vide.png` })
  await page.click('[data-testid=local-demo]'); await page.waitForFunction(() => /4\s?719/.test(document.querySelector('[data-testid=local-count]')?.textContent ?? ''), null, { timeout: 30000 })
  ok('données de démo chargées (4 719 triplets)', true)
  await page.screenshot({ path: `${SHOTS}/02a-avant-execution.png` })
  await page.click('button:has-text("Exécuter")'); await page.waitForSelector('.qres tbody tr', { timeout: 30000 })
  const n = await page.locator('.qres tbody tr').count(); ok('requête guidée Diesel : 10 lignes', n === 10, String(n))
  await page.screenshot({ path: `${SHOTS}/02-diesel.png` })
  await page.check('[data-testid=local-infer]'); await page.waitForSelector('[data-testid=local-inf-info]', { timeout: 60000 })
  ok('inférence RDFS matérialisée', /RDFS/.test(await page.locator('[data-testid=local-inf-info]').innerText()), await page.locator('[data-testid=local-inf-info]').innerText())
  await page.click('[data-testid=local-validate]'); await page.waitForSelector('[data-testid=local-shacl]', { timeout: 90000 })
  const sh = await page.locator('[data-testid=local-shacl]').innerText(); ok('validation SHACL du contenu', /Conforme/.test(sh), sh.split('\n')[0])
  await page.screenshot({ path: `${SHOTS}/03-inference-shacl.png` })
  await page.click('[data-testid=local-clear]'); await page.waitForFunction(() => /^0\b/.test(document.querySelector('[data-testid=local-count]')?.textContent?.trim() ?? ''), null, { timeout: 15000 })
  ok('vidage', true)
  const ur = await fetch(`${B}/projects/${pid}/query/run`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ sparql: 'DROP ALL', endpoint: { kind: 'local' } }) })
  ok('UPDATE refusé (403)', ur.status === 403, String(ur.status))
  ok('aucune erreur JavaScript', errs.length === 0, errs.join(' ; '))
} catch (e) { ok('exception ' + e.message.split('\n')[0], false) } finally { await browser.close(); procs.forEach(p => p.kill()) }
console.log(`${out.filter(Boolean).length}/${out.length}`); process.exit(out.every(Boolean) ? 0 : 1)
