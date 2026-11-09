// Captures image par image de Krakie en déplacement continu (diagnostic L30 fix-deformation).
// Usage : node tools/recette/l30_frames.mjs <dossier de sortie>   (front buildé requis)
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const OUT = path.resolve(process.argv[2] || '/tmp/frames'); mkdirSync(OUT, { recursive: true })
const BP = 8941, FP = 4941, sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []; const run = (c, a, o) => { const p = spawn(c, a, { stdio: 'ignore', ...o }); procs.push(p) }
process.on('exit', () => procs.forEach(p => p.kill()))
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'], { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-fr-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const browser = await chromium.launch()
const ctx = await browser.newContext({ locale: 'fr-FR', viewport: { width: 760, height: 780 } })
await ctx.route(`${base}/api/**`, r => r.continue({ url: r.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.game.debug', '1') } catch {} })
const page = await ctx.newPage()
await page.goto(base + '/#/', { waitUntil: 'load' }); await sleep(1200)
for (const k of ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a']) await page.keyboard.press(k)
await page.locator('div.game').waitFor(); await sleep(500)
await page.keyboard.press('Enter'); await sleep(300)
await page.evaluate(() => { const e = window.__ontoforgeGame; e.spawnT = 99; e.invuln = 0; e.lives = 3; e.kx = 60 })
await page.keyboard.down('ArrowRight')
await sleep(250)
// un cliché du canvas à chaque image d'animation
const frames = await page.evaluate(() => new Promise(res => {
  const e = window.__ontoforgeGame, cv = document.querySelector('canvas.g-canvas'), out = []
  const tick = () => { out.push({ url: cv.toDataURL('image/png'), kx: e.kx, ky: e.ky, lean: e.lean, W: cv.width, H: cv.height }); out.length < 40 ? requestAnimationFrame(tick) : res(out) }
  requestAnimationFrame(tick)
}))
await page.keyboard.up('ArrowRight')
frames.forEach((f, i) => writeFileSync(path.join(OUT, `f${String(i).padStart(2, '0')}.png`), Buffer.from(f.url.split(',')[1], 'base64')))
writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify(frames.map(f => ({ kx: f.kx, ky: f.ky, lean: f.lean, W: f.W, H: f.H }))))
await browser.close(); process.exit(0)
