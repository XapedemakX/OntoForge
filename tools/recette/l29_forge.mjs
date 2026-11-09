// Recette L29 : Krakie forgeronne pendant un traitement, trophée à la fin.
// Usage : node tools/recette/l29_forge.mjs   (BACKEND_PORT, FRONT_PORT optionnels ; front déjà buildé : cd frontend && npm run build)
// Couvre : exports et analyse ralentis par une route Playwright (pose forge visible pendant, trophée ensuite, retour à l'état normal), génération depuis le tableau
// de bord (toast avec trophée), mouvement réduit (images fixes). Captures : journal/L29/screens/.
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
const SHOTS = path.join(ROOT, 'journal/L29/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8929, FP = process.env.FRONT_PORT || 4929
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const report = []
const log = (name, ok, detail = '') => { report.push({ name, ok }); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l29-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
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

const DELAY = 1800
const slow = async ctx => { await ctx.route(/\/api\/projects\/[^/]+\/(generate\/(curiosity|neo4j)|analyze)(\?.*)?$/, async route => { await sleep(DELAY); await route.continue() }) }
const poseOf = page => page.locator('[data-kstatus]').first().evaluate(el => ({ kind: el.getAttribute('data-kstatus'), src: el.querySelector('img')?.getAttribute('src'), pose: el.querySelector('img')?.getAttribute('data-pose') })).catch(() => null)
const noKstatus = async page => (await page.locator('[data-kstatus]').count()) === 0

try {
  const ctxs = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'fr-FR' })
  await ctxs.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await slow(ctxs)
  const page = await ctxs.newPage(); const errs = []
  page.on('pageerror', e => errs.push(String(e).slice(0, 200)))
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 200)) })

  // ---------------- 1. exports
  await page.goto(`${base}/#/projet/${pid}/exports`, { waitUntil: 'load' })
  await page.waitForSelector('[data-kstatus=forge]', { timeout: 10000 })
  const f1 = await poseOf(page)
  log('1a exports : pose forge pendant le traitement', f1?.kind === 'forge' && f1.pose === 'forge' && /\/krakie\/(anim\/forge-\d\.svg|forge\.svg)$/.test(f1.src ?? ''), JSON.stringify(f1))
  await page.screenshot({ path: path.join(SHOTS, '01-exports-forge.png') })
  const seen = new Set(); for (let i = 0; i < 8; i++) { const s = (await poseOf(page))?.src; if (s) seen.add(s); await sleep(120) }
  log('1b exports : la forge s\'anime (plusieurs images)', seen.size >= 3, [...seen].join(' '))
  await page.waitForSelector('[data-kstatus=trophee]', { timeout: 10000 })
  const t1 = await poseOf(page)
  log('1c exports : trophée à la fin', t1?.pose === 'trophee', JSON.stringify(t1))
  await page.screenshot({ path: path.join(SHOTS, '02-exports-trophee.png') })
  await page.waitForSelector('.exports', { timeout: 5000 })
  await page.waitForFunction(() => !document.querySelector('[data-kstatus]'), null, { timeout: 5000 })
  log('1d exports : retour à l\'état normal après ~2 s', await noKstatus(page) && (await page.locator('.exports .flist button').count()) > 0)

  // ---------------- 2. analyse
  await page.goto(`${base}/#/projet/${pid}/analyse`, { waitUntil: 'load' })
  await page.waitForSelector('[data-kstatus=forge]', { timeout: 10000 })
  log('2a analyse : pose forge pendant le traitement', (await poseOf(page))?.pose === 'forge')
  await page.screenshot({ path: path.join(SHOTS, '03-analyse-forge.png') })
  await page.waitForSelector('[data-kstatus=trophee]', { timeout: 10000 })
  log('2b analyse : trophée à la fin', (await poseOf(page))?.pose === 'trophee')
  await page.screenshot({ path: path.join(SHOTS, '04-analyse-trophee.png') })
  await page.waitForFunction(() => !document.querySelector('[data-kstatus]'), null, { timeout: 5000 })
  log('2c analyse : retour à l\'état normal', await noKstatus(page))

  // ---------------- 3. tableau de bord : génération (Krakie + toast trophée)
  // tout arbitrer (y compris les pertes) pour que l'étape suivante soit « générer »
  await fetch(B + `/projects/${pid}/decisions/curiosity/accept-recommended?include_lost=true`, { method: 'POST' })
  await page.goto(`${base}/#/projet/${pid}/tableau`, { waitUntil: 'load' }); await page.waitForSelector('[data-tour="dash-next"] button.primary, [data-tour="dash-next"] .btn.primary', { timeout: 15000 })
  const act = page.locator('[data-tour="dash-next"] .btn.primary').first()
  await page.waitForFunction(() => document.querySelector('[data-tour="dash-next"] img')?.getAttribute('data-pose') !== 'reflechit', null, { timeout: 15000 })  // analyses ralenties : attendre la fin du chargement
  const label = await act.innerText()
  if (/Générer/.test(label)) {
    log('3a tableau de bord : invitation à générer avec Krakie forgeronne', (await page.locator('[data-tour="dash-next"] img').first().getAttribute('data-pose')) === 'forge')
    await act.click(); await sleep(400)
    log('3b tableau de bord : forge pendant la génération', (await page.locator('[data-tour="dash-next"] img').first().getAttribute('data-pose')) === 'forge')
    await page.waitForSelector('.toast.with-krakie', { timeout: 10000 })
    log('3c tableau de bord : toast avec trophée', (await page.locator('.toast.with-krakie img').getAttribute('data-pose')) === 'trophee')
    log('3d tableau de bord : Krakie tient le trophée', (await page.locator('[data-tour="dash-next"] img').first().getAttribute('data-pose')) === 'trophee')
    await page.screenshot({ path: path.join(SHOTS, '05-tableau-trophee.png') })
    await page.waitForFunction(() => !document.querySelector('.toast.with-krakie'), null, { timeout: 6000 })
    log('3e tableau de bord : le toast disparaît', true)
  } else log('3 tableau de bord (étape suivante n\'est pas « générer »)', true, label)

  // ---------------- 4. mouvement réduit : image fixe
  const rctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'fr-FR', reducedMotion: 'reduce' })
  await rctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await slow(rctx)
  const rp = await rctx.newPage()
  await rp.goto(`${base}/#/projet/${pid}/exports`, { waitUntil: 'load' })
  await rp.waitForSelector('[data-kstatus=forge]', { timeout: 10000 })
  const rs = new Set(); for (let i = 0; i < 8; i++) { const s = (await poseOf(rp))?.src; if (s) rs.add(s); await sleep(150) }
  log('4a mouvement réduit : forge en image fixe', rs.size === 1 && [...rs][0] === '/krakie/forge.svg', [...rs].join(' '))
  await rp.screenshot({ path: path.join(SHOTS, '06-reduit-forge.png') })
  await rp.waitForSelector('[data-kstatus=trophee]', { timeout: 10000 })
  log('4b mouvement réduit : trophée fixe', (await poseOf(rp)).src === '/krakie/trophee.svg')
  await rctx.close()

  // ---------------- 5. mobile
  const mctx = await browser.newContext({ viewport: { width: 390, height: 800 }, locale: 'fr-FR' })
  await mctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await slow(mctx)
  const mp = await mctx.newPage()
  await mp.goto(`${base}/#/projet/${pid}/exports`, { waitUntil: 'load' })
  await mp.waitForSelector('[data-kstatus=forge]', { timeout: 10000 })
  log('5a mobile : pas de défilement horizontal', await mp.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2))
  await mp.screenshot({ path: path.join(SHOTS, '07-mobile-forge.png') })
  await mctx.close()
  log('6 aucune erreur console', errs.length === 0, errs.slice(0, 3).join(' || '))
} catch (err) { log('exception', false, String(err).slice(0, 300)) }
await browser.close(); procs.forEach(p => p.kill())
const ko = report.filter(x => !x.ok).length
console.log(`\n=== L29 : ${report.length - ko} OK / ${ko} KO`); process.exit(ko ? 1 : 0)
