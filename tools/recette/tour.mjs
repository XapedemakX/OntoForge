// Recette L18 : visite guidée. Usage : node tools/recette/tour.mjs   (BACKEND_PORT, FRONT_PORT optionnels ; front déjà buildé)
// Desktop 1440x900 : parcourt les étapes au clavier (→), une capture par étape dans journal/L18/screens/, échoue si une cible manque.
// Mobile 390 px : aucune cible requise, mais pas de débordement horizontal et bulle dans l'écran.
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
const SHOTS = path.join(ROOT, 'journal/L18/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8921, FP = process.env.FRONT_PORT || 4921
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const report = []
const log = (name, ok, detail) => { report.push(ok); console.log((ok ? 'OK  ' : 'KO  ') + name + ' :: ' + detail) }

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-tour-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
const base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const proj = await (await fetch(B + '/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'visite', sample: 'automaint' }) })).json()
const pid = proj.id

const browser = await chromium.launch()
async function session(vp) {
  const ctx = await browser.newContext({ viewport: vp, locale: 'fr-FR' })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  const page = await ctx.newPage(); const errs = []
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 200)) })
  page.on('pageerror', e => errs.push(String(e).slice(0, 200)))
  return { ctx, page, errs }
}
const st = page => page.evaluate(() => window.ontoforgeTour.state())
const ready = async (page, i) => { for (let k = 0; k < 120; k++) { const s = await st(page); if (s.active && s.index === i && s.ready) return s; await sleep(100) } return st(page) }
const geom = page => page.evaluate(() => {
  const b = document.querySelector('[data-tour-bubble]')?.getBoundingClientRect()
  return { bubble: b ? { l: b.left, t: b.top, r: b.right, b: b.bottom } : null, vw: innerWidth, vh: innerHeight, hOverflow: document.documentElement.scrollWidth > innerWidth + 2,
    hole: !!document.querySelector('.tour-hole'), focusInBubble: !!document.querySelector('[data-tour-bubble]')?.contains(document.activeElement) || document.activeElement === document.querySelector('[data-tour-bubble]') }
})

// ---------------- desktop
const d = await session({ width: 1440, height: 900 })
await d.page.goto(`${base}/#/projet/${pid}/tableau?tour=1`, { waitUntil: 'load' })
let s = await ready(d.page, 0)
log('D-start (?tour=1)', s.active && s.total >= 14 && s.total <= 18, `${s.total} étapes`)
const total = s.total
let idx = 0
for (let i = 0; i < total; i++) {
  if (i > 0) await d.page.keyboard.press('ArrowRight')
  s = await ready(d.page, i)
  await sleep(500)
  const g = await geom(d.page)
  const inside = g.bubble && g.bubble.l >= -1 && g.bubble.t >= -1 && g.bubble.r <= g.vw + 1 && g.bubble.b <= g.vh + 1
  const okTarget = !s.hasTarget || (s.found && g.hole)
  await d.page.screenshot({ path: path.join(SHOTS, `${String(i + 1).padStart(2, '0')}-${s.id}.png`) })
  log(`D${String(i + 1).padStart(2, '0')}-${s.id}`, s.index === i && okTarget && inside && !g.hOverflow && g.focusInBubble,
    `cible=${s.hasTarget ? (s.found ? 'trouvée' : 'ABSENTE') : 'aucune'} bulle-dans-écran=${inside} focus=${g.focusInBubble}`)
}
// clavier : ← revient, Échap ferme, goto/next d'API
await d.page.keyboard.press('ArrowLeft'); s = await ready(d.page, total - 2)
log('D-clavier ←', s.index === total - 2, `index=${s.index}`)
await d.page.evaluate(() => window.ontoforgeTour.goto(4)); s = await ready(d.page, 4)
await d.page.evaluate(() => window.ontoforgeTour.next()); s = await ready(d.page, 5)
log('D-API goto/next', s.index === 5 && s.id === 'ed-quick', `id=${s.id}`)
await d.page.keyboard.press('Escape'); await sleep(300)
s = await st(d.page)
const done = await d.page.evaluate(() => localStorage.getItem('ontoforge.tour.done'))
log('D-Échap ferme + ontoforge.tour.done', !s.active && done === '1', `active=${s.active} done=${done}`)
log('D-erreurs console', d.errs.length === 0, JSON.stringify(d.errs.slice(0, 3)))

// ---------------- sans projet : proposition de créer la démo
const n = await session({ width: 1440, height: 900 })
await n.page.goto(`${base}/#/`, { waitUntil: 'load' }); await sleep(800)
await n.page.evaluate(() => window.ontoforgeTour.start()); await sleep(500)
const ask = await n.page.locator('[data-tour-bubble]').innerText()
log('N-sans projet : propose la démo', /démo/i.test(ask), ask.split('\n')[0])
await n.page.screenshot({ path: path.join(SHOTS, '00-sans-projet.png') })
await n.page.getByRole('button', { name: /Créer le projet de démo/ }).click()
s = await ready(n.page, 0)
log('N-démo créée puis visite lancée', s.active && /#\/projet\/.+\/tableau/.test(await n.page.evaluate(() => location.hash)), await n.page.evaluate(() => location.hash))

// ---------------- mobile 390 px
const m = await session({ width: 390, height: 844 })
await m.page.goto(`${base}/#/projet/${pid}/tableau?tour=1`, { waitUntil: 'load' })
s = await ready(m.page, 0)
for (let i = 0; i < total; i++) {
  if (i > 0) await m.page.evaluate(() => window.ontoforgeTour.next())
  s = await ready(m.page, i); await sleep(500)
  const g = await geom(m.page)
  const full = g.bubble && g.bubble.l <= 1 && g.bubble.r >= g.vw - 1 && g.bubble.b <= g.vh + 1
  await m.page.screenshot({ path: path.join(SHOTS, `m-${String(i + 1).padStart(2, '0')}-${s.id}.png`) })
  log(`M${String(i + 1).padStart(2, '0')}-${s.id}`, !g.hOverflow && full, `débordement=${g.hOverflow} bulle-pleine-largeur=${!!full}`)
}
await browser.close(); procs.forEach(p => p.kill())
const ko = report.filter(x => !x).length
console.log(`\n=== Visite : ${report.length - ko} OK / ${ko} KO`); process.exit(ko ? 1 : 0)
