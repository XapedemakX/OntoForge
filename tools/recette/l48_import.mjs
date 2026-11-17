// Recette L48 : import déterministe de schémas SQL, CSV et JSON Schema (sans IA), aperçu obligatoire puis application.
// Usage : BACKEND_PORT=9148 FRONT_PORT=5148 node tools/recette/l48_import.mjs   (front déjà buildé : cd frontend && npm run build)
// Démarre un backend temporaire (mock, sans authentification) et un petit serveur de front (dist + relais /api), puis :
// dépôt d'un DDL PostgreSQL sur l'écran Projets, aperçu (classes, décisions, ignorés), exclusion d'une classe, choix d'une décision,
// application, ontologie créée ; import d'un CSV et d'un JSON Schema dans le projet (tableau de bord) ; refus d'un fichier hostile ;
// annulation ; version anglaise. Captures : journal/L48/screens/.
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, existsSync, readFileSync, statSync } from 'node:fs'
import http from 'node:http'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L48/screens'); mkdirSync(SHOTS, { recursive: true })
const FIX = path.join(ROOT, 'backend/tests/fixtures/l48')
const BP = process.env.BACKEND_PORT || 9148, FP = process.env.FRONT_PORT || 5148
const PY = process.env.PYTHON || '/home/claude/venv/bin/python'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
process.on('exit', () => procs.forEach(p => p.kill()))
let ko = 0, ok = 0
const log = (name, good, detail = '') => { if (good) ok++; else ko++; console.log((good ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }
const fr = JSON.parse(readFileSync(path.join(ROOT, 'frontend/src/i18n/fr.json'), 'utf-8'))

const data = mkdtempSync(path.join(tmpdir(), 'of-l48-'))
run(PY, ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'], {
  cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: data, ONTOFORGE_LOCAL_STORE_DIR: path.join(data, 'ls'), ONTOFORGE_LLM_PROVIDER: 'mock' } })
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2' }
const DIST = path.join(ROOT, 'frontend/dist')
const front = http.createServer((req, res) => {
  if (req.url.startsWith('/api/')) {
    const up = http.request({ host: '127.0.0.1', port: BP, path: req.url, method: req.method, headers: { ...req.headers, 'x-forwarded-host': req.headers.host } }, r => { res.writeHead(r.statusCode, r.headers); r.pipe(res) })
    up.on('error', () => { res.writeHead(502); res.end() }); req.pipe(up); return
  }
  let f = path.join(DIST, decodeURIComponent(req.url.split('?')[0]))
  if (!f.startsWith(DIST) || !existsSync(f) || statSync(f).isDirectory()) f = path.join(DIST, 'index.html')
  res.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' }); res.end(readFileSync(f))
}).listen(Number(FP), '127.0.0.1')
process.on('exit', () => front.close())
const base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(`http://127.0.0.1:${BP}/api/health`)).ok) break } catch {} await sleep(500) }

const browser = await chromium.launch()
const errs = []
const open = async lang => {
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: lang === 'fr' ? 'fr-FR' : 'en-US' })
  await ctx.addInitScript(l => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.setItem('ontoforge.lang', l) } catch {} }, lang)
  const page = await ctx.newPage()
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push('console: ' + m.text().slice(0, 200)) })
  return { ctx, page }
}
const shot = async (page, name) => { await sleep(300); await page.screenshot({ path: path.join(SHOTS, name + '.png') }) }
const count = (page, sel) => page.locator(sel).count()

const { ctx, page } = await open('fr')
await page.goto(base + '/', { waitUntil: 'load' })
await page.waitForSelector('.page')

// 1. dépôt d'un DDL PostgreSQL sur l'écran Projets
await page.locator('.page input[type=file]').first().setInputFiles(path.join(FIX, 'postgres.sql'))
await page.waitForSelector('[data-testid=staged-schema]')
log('fichier déposé : bouton d\'aperçu sans IA', true)
await page.click('[data-testid=staged-schema]')
await page.waitForSelector('[data-testid=schema-import] [data-testid=imp-summary]', { timeout: 20000 })
log('aperçu affiché (résumé)', (await page.locator('[data-testid=imp-summary]').innerText()).length > 0)
const nCls = await count(page, '[data-testid=imp-classes] input[type=checkbox]')
log('classes listées avec case d\'inclusion', nCls >= 3, String(nCls))
log('décisions à arbitrer présentes', await count(page, '[data-testid=imp-decisions]') === 1)
log('éléments ignorés rapportés', await count(page, '[data-testid=imp-ignored]') === 1)
log('avis rapportés', await count(page, '[data-testid=imp-notices]') === 1)
await shot(page, '01-apercu-postgres')

// 2. exclusion d'une classe : le résumé change
const sum0 = await page.locator('[data-testid=imp-summary]').innerText()
await page.locator('[data-testid=imp-classes] input[type=checkbox]').last().uncheck()
await page.waitForFunction(s => document.querySelector('[data-testid=imp-summary]')?.textContent !== s, sum0, { timeout: 15000 }).catch(() => {})
log('exclure une classe recalcule l\'aperçu', (await page.locator('[data-testid=imp-summary]').innerText()) !== sum0)
await page.locator('[data-testid=imp-classes] input[type=checkbox]').last().check()
await sleep(800)

// 3. application : un projet est créé et contient l'ontologie
await page.click('[data-testid=imp-apply]')
await page.waitForFunction(() => /#\/projet\/[^/]+\//.test(location.hash), null, { timeout: 30000 })
const pid = decodeURIComponent(page.url().match(/#\/projet\/([^/]+)/)[1])
const pj = await (await fetch(`${base}/api/projects/${pid}`)).json()
const nc = Object.keys(pj.onto?.classes ?? {}).length || (pj.onto?.classes?.length ?? 0)
log('projet créé avec les classes importées', nc >= 3, `${pid} / ${nc}`)
const shapes = JSON.stringify(pj.shapes ?? {})
log('formes SHACL générées', shapes.length > 50)

// 4. import d'un CSV puis d'un JSON Schema dans le projet (tableau de bord)
await page.goto(`${base}/#/projet/${pid}/tableau`); await page.waitForSelector('[data-testid=dash-import-input]', { state: 'attached', timeout: 15000 })
const csvIn = page.locator('[data-testid=dash-import-input]')
await csvIn.setInputFiles([path.join(FIX, 'customers.csv'), path.join(FIX, 'orders.csv')])
await page.waitForSelector('[data-testid=imp-summary]', { timeout: 20000 })
log('CSV : aperçu avec décisions de référence', await count(page, '[data-testid=imp-decisions]') === 1)
await shot(page, '02-apercu-csv')
await page.click('[data-testid=imp-cancel]')
log('annuler ferme l\'aperçu sans écrire', await count(page, '[data-testid=imp-summary]') === 0)
await csvIn.setInputFiles(path.join(FIX, 'shop.schema.json'))
await page.waitForSelector('[data-testid=imp-summary]', { timeout: 20000 })
await page.click('[data-testid=imp-apply]')
await page.waitForFunction(() => document.querySelector('[data-testid=imp-summary]') === null, null, { timeout: 20000 }).catch(() => {})
const pj2 = await (await fetch(`${base}/api/projects/${pid}`)).json()
const n2 = Object.keys(pj2.onto?.classes ?? {}).length || (pj2.onto?.classes?.length ?? 0)
log('JSON Schema appliqué : de nouvelles classes', n2 > nc, `${nc} -> ${n2}`)

// 5. fichier hostile : refus localisé, rien d'écrit
const csrf = ''
const hostile = await page.evaluate(async () => {
  const fd = new FormData(); fd.append('files', new File(['CREATE TABLE a (' + Array.from({ length: 5000 }, (_, i) => 'c' + i + ' int,').join('') + 'y int);'], 'big.sql'))
  const r = await fetch('/api/import/schema/preview', { method: 'POST', body: fd }); return { status: r.status, body: await r.text() }
})
log('table de 5000 colonnes refusée proprement', hostile.status >= 400 && hostile.status < 500, String(hostile.status))
const nul = await page.evaluate(async () => {
  const fd = new FormData(); fd.append('files', new File([new Uint8Array([0, 1, 2, 0, 0])], 'bin.sql'))
  const r = await fetch('/api/import/schema/preview', { method: 'POST', body: fd }); return r.status
})
log('fichier binaire refusé', nul >= 400 && nul < 500, String(nul))

// 6. annulation de l'import (undo) via l'API d'opérations
const und = await page.evaluate(async id => { const r = await fetch(`/api/projects/${id}/ops/undo`, { method: 'POST' }); return r.status }, pid)
log('import annulable (undo)', und === 200, String(und))

// 7. version anglaise
const setui = await page.evaluate(async () => (await fetch('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ language: { ui: 'en' } }) })).status)
log('langue de l\'instance passée en anglais', setui === 200, String(setui))
const en = await open('en')
await en.page.goto(base + '/', { waitUntil: 'load' }); await en.page.waitForSelector('.page')
await en.page.locator('.page input[type=file]').first().setInputFiles(path.join(FIX, 'mysql.sql'))
await en.page.click('[data-testid=staged-schema]')
await en.page.waitForSelector('[data-testid=imp-summary]', { timeout: 20000 })
const txt = await en.page.locator('[data-testid=schema-import]').innerText()
const fm = txt.match(/Appliquer|Aperçu|Importer|Annuler|Classes? /)
log('version anglaise sans texte français', !fm, fm ? fm[0] + ' :: ' + txt.slice(0, 400).replace(/\n/g, ' | ') : '')
await shot(en.page, '03-preview-mysql-en')
await en.ctx.close()
void fr; void csrf

log('aucune erreur de console ou de page', errs.length === 0, errs.slice(0, 3).join(' | '))
await browser.close()
console.log(`\n${ok} vérifications OK` + (ko ? `, ${ko} échec(s)` : '\nRecette L48 : tout est vert'))
process.exit(ko ? 1 : 0)
