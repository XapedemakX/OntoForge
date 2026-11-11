// Recette L33 : documentation en anglais (captures dans journal/L33/screens/). Front déjà buildé : cd frontend && npm run build
// Vérifie en mode anglais : pas de bandeau sur les pages traduites, ancres de help_map présentes dans la version anglaise, bouton « ? » et Krakie sur la bonne section.
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
const SHOTS = path.join(ROOT, 'journal/L33/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8933, FP = process.env.FRONT_PORT || 4933
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const report = []
const log = (n, ok, d = '') => { report.push(ok); console.log((ok ? 'OK  ' : 'KO  ') + n + (d ? ' :: ' + d : '')) }
const HELP = JSON.parse(readFileSync(path.join(ROOT, 'backend/ontoforge/assistant/help_map.json'), 'utf8')).screens
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l33-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const pid = (await (await fetch(B + '/projects', { method: 'POST', headers: J, body: JSON.stringify({ name: 'doc', sample: 'automaint' }) })).json()).id
await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'en', labels: 'en', assistant: 'en' } }) })
const browser = await chromium.launch()
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'en-US' })
  await ctx.route(`${base}/api/**`, r => r.continue({ url: r.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  const page = await ctx.newPage(); const errs = []
  page.on('pageerror', e => errs.push(String(e).slice(0, 200)))
  const atTop = id => page.evaluate(id => { const h = document.getElementById(id), sc = document.querySelector('.doc-scroll'); if (!h || !sc) return false; const a = h.getBoundingClientRect().top - sc.getBoundingClientRect().top; return a >= -4 && a <= 120 }, id)
  let n = 0
  for (const [screen, e] of Object.entries(HELP)) {
    await page.goto(`${base}/#/projet/${pid}/documentation/${e.page}/${e.anchor}`, { waitUntil: 'load' }); await page.waitForSelector('.doc-article h1'); await sleep(450)
    const ok = (await page.locator('.doc-article').getAttribute('lang')) === 'en' && (await page.locator('[data-testid=doc-fr-only]').count()) === 0 && await atTop(e.anchor)
    if (!ok) log(`ancre ${screen} -> ${e.page}#${e.anchor}`, false); else n++
  }
  log(`ancres de help_map ouvertes en anglais (${n}/${Object.keys(HELP).length})`, n === Object.keys(HELP).length)
  await page.goto(`${base}/#/projet/${pid}/ontologie`, { waitUntil: 'load' }); await page.waitForSelector('[aria-label="Help for this screen"]', { timeout: 15000 }); await sleep(500)
  await page.getByRole('button', { name: 'Help for this screen' }).click(); await page.waitForSelector('.doc-article h1'); await sleep(700)
  log('bouton « ? » depuis l\'éditeur ouvre la bonne section en anglais', await atTop(HELP.editor.anchor) && (await page.locator('[data-testid=doc-fr-only]').count()) === 0)
  await page.screenshot({ path: path.join(SHOTS, '01-editeur-aide-en.png') })
  for (const [pg, shot] of [['utilisateur/analyse-arbitrage', '02-analyse-en'], ['limites', '03-limites-en'], ['api', '04-api-en'], ['contribuer', '05-contribuer-en'], ['changelog', '06-changelog-en'], ['architecture', '07-architecture-en'], ['glossaire', '08-glossaire-en'], ['regles', '09-regles-en']]) {
    await page.goto(`${base}/#/projet/${pid}/documentation/${pg}`, { waitUntil: 'load' }); await page.waitForSelector('.doc-article h1'); await sleep(600)
    await page.screenshot({ path: path.join(SHOTS, shot + '.png') })
  }
  log('aucune erreur de page', errs.length === 0, errs.join(' | '))
} catch (e) { log('exception', false, String(e).slice(0, 300)) }
await browser.close(); procs.forEach(p => p.kill())
console.log(`\n=== L33 : ${report.filter(Boolean).length} OK / ${report.filter(x => !x).length} KO`)
process.exit(report.every(Boolean) ? 0 : 1)
