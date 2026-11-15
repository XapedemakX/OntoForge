// L37b : captures de l'aquarium de Krakie (clair/sombre, desktop/mobile, écrans sensibles) + GIF. Usage : BACKEND_PORT=.. FRONT_PORT=.. node tools/recette/l37_aquarium.mjs  (front buildé ; ffmpeg requis)
import { createRequire } from 'node:module'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const OUT = path.join(ROOT, 'journal/L37b'), SHOTS = path.join(OUT, 'screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8975, FP = process.env.FRONT_PORT || 4975, sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []; const run = (c, a, o) => { procs.push(spawn(c, a, { stdio: 'ignore', ...o })) }
process.on('exit', () => procs.forEach(p => p.kill()))
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'], { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l37b-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const pid = (await (await fetch(B + '/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'l37b', sample: 'automaint' }) })).json()).id
const browser = await chromium.launch()
const only = process.env.ONLY || 'all'
for (const [theme, dsf] of [['light', 2], ['dark', 2]]) for (const [dev, vp] of [['desktop', { width: 1440, height: 860 }], ['mobile', { width: 390, height: 800 }]]) {
  const ctx = await browser.newContext({ viewport: vp, colorScheme: theme, deviceScaleFactor: dsf, locale: 'fr-FR' })
  await ctx.route(`${base}/api/**`, r => r.continue({ url: r.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  const page = await ctx.newPage()
  for (const scr of dev === 'mobile' ? ['tableau'] : ['ontologie', 'requetes', 'exports', 'documentation/accueil', 'fichiers', 'tableau']) {
    await page.goto(`${base}/#/projet/${pid}/${scr}`, { waitUntil: 'load' }); await page.waitForSelector('.ag-fab', { timeout: 15000 }); await sleep(2500)
    await page.screenshot({ path: `${SHOTS}/${dev}-${theme}-${scr.replace('/', '-')}.png` })
    if (scr === 'fichiers' && dev === 'desktop') { // L37c : le récif se pose sur la barre d'état, sans la recouvrir
      const bar = await page.locator('.fx-status').boundingBox(), fab = await page.locator('.ag-fab').boundingBox()
      if (!bar || !fab || fab.y + fab.height > bar.y + 1) { console.error('KO fichiers : Krakie recouvre la barre d\'état', bar, fab); process.exitCode = 1 } else console.log('OK fichiers : récif posé sur la barre d\'état')
      await page.screenshot({ path: `${SHOTS}/zoom-fichiers-${theme}.png`, clip: { x: vp.width - 520, y: vp.height - 260, width: 520, height: 260 } })
    }
    if (scr === 'tableau' && dev === 'desktop') { const b = await page.locator('.ag-fab').boundingBox(); await page.screenshot({ path: `${SHOTS}/zoom-${theme}.png`, clip: { x: Math.max(0, b.x - 60), y: b.y - 40, width: Math.min(vp.width, b.x + b.width + 12) - Math.max(0, b.x - 60), height: b.height + 40 } }) }
  }
  if (dev === 'desktop') { // panneau assistant ouvert : l'aquarium disparaît, rien d'autre ne bouge
    await page.keyboard.press('Control+k'); await sleep(900); await page.screenshot({ path: `${SHOTS}/desktop-${theme}-panneau-ouvert.png` })
  }
  await ctx.close()
}
// GIF : zoom sur l'aquarium, 5 s, desktop clair (curseur qui survole à mi-parcours)
const vdir = mkdtempSync(path.join(tmpdir(), 'of-l37v-'))
const ctx = await browser.newContext({ viewport: { width: 1000, height: 300 }, deviceScaleFactor: 1, locale: 'fr-FR', recordVideo: { dir: vdir, size: { width: 1000, height: 300 } } })
await ctx.route(`${base}/api/**`, r => r.continue({ url: r.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
const g = await ctx.newPage(); const t0 = Date.now()
await g.goto(`${base}/#/projet/${pid}/tableau`, { waitUntil: 'load' }); await g.waitForSelector('.ag-fab'); await sleep(600)
const b = await g.locator('.ag-fab').boundingBox(); const tStart = (Date.now() - t0) / 1000
await sleep(3200); await g.mouse.move(b.x + 20, b.y + 30); await g.mouse.move(b.x + 40, b.y + 40, { steps: 6 }); await sleep(1100); await g.mouse.move(5, 5); await sleep(1200)
await ctx.close()
const vid = execFileSync('bash', ['-c', `ls ${vdir}/*.webm`]).toString().trim()
const crop = `crop=${2 * Math.ceil((b.width + 24) / 2)}:${2 * Math.ceil((b.height + 24) / 2)}:${Math.floor(b.x - 12)}:${Math.floor(b.y - 12)}`
execFileSync('ffmpeg', ['-y', '-ss', String(tStart + 0.3), '-t', '5.5', '-i', vid, '-vf', `fps=15,${crop},scale=iw*2:ih*2:flags=neighbor,split[a][b];[a]palettegen[p];[b][p]paletteuse`, path.join(OUT, 'aquarium.gif')], { stdio: ['ignore', 'ignore', 'inherit'] })
rmSync(vdir, { recursive: true, force: true }); await browser.close(); process.exit(0)
