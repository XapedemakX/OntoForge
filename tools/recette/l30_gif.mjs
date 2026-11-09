// GIF de démonstration L30 (jeu en action, ~7 s). Usage : node tools/recette/l30_gif.mjs  (front buildé ; ffmpeg requis)
// Sortie : journal/L30/krakie-en-action-v2.gif
import { createRequire } from 'node:module'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const OUT = path.join(ROOT, 'journal/L30'); mkdirSync(OUT, { recursive: true })
const BP = 8931, FP = 4931, sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []; const run = (c, a, o) => { const p = spawn(c, a, { stdio: 'ignore', ...o }); procs.push(p) }
process.on('exit', () => procs.forEach(p => p.kill()))
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'], { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l30g-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const vdir = mkdtempSync(path.join(tmpdir(), 'of-l30v-'))
const browser = await chromium.launch()
const ctx = await browser.newContext({ locale: 'fr-FR', viewport: { width: 760, height: 780 }, recordVideo: { dir: vdir, size: { width: 760, height: 780 } } })
await ctx.route(`${base}/api/**`, r => r.continue({ url: r.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.game.debug', '1') } catch {} })
const tVideo = Date.now()
const page = await ctx.newPage()
await page.goto(base + '/#/', { waitUntil: 'load' }); await sleep(1200)
for (const k of ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a']) await page.keyboard.press(k)
await page.locator('div.game').waitFor(); await sleep(500)
await page.keyboard.press('Enter')
const tStart = Date.now()
await page.evaluate(() => { const e = window.__ontoforgeGame; e.level = 3; e.triples = 4; e.spawnT = 0.1 })
const snap = () => page.evaluate(() => window.__ontoforgeGame.snapshot())
// mise en scène : Krakie nage en va-et-vient, événements déclenchés à heure fixe (vrais appels du moteur)
let held = null
const hold = async d => { if (d === held) return; if (held) await page.keyboard.up(held); held = d; if (d) await page.keyboard.down(d) }
const ev = {
  ok: () => page.evaluate(() => { const e = window.__ontoforgeGame, s = e.snapshot(); e.catchTok(s.kind, s.want[0], e.kx, e.ky) }),
  inf: () => page.evaluate(() => window.__ontoforgeGame.collide({ type: 'inf', label: 'INF', x: 100, y: 100, w: 10, h: 9 })),
  shacl: () => page.evaluate(() => window.__ontoforgeGame.collide({ type: 'shacl', label: 'SHACL', x: 100, y: 100, w: 10, h: 9 })),
  bad: () => page.evaluate(() => { const e = window.__ontoforgeGame; e.invuln = 0; e.collide({ type: 'bad', label: '!', x: 100, y: 100, w: 10, h: 9 }) }),
}
const plan = [[0.8, 'ok'], [1.8, 'ok'], [2.3, 'ok'], [3.4, 'inf'], [4.6, 'shacl'], [5.8, 'bad'], [6.6, 'bad']]
const t1 = Date.now(); let n = 0
while (Date.now() - t1 < 8200) {
  const el = (Date.now() - t1) / 1000
  while (n < plan.length && el >= plan[n][0]) await ev[plan[n++][1]]()
  const s = await snap(); if (s.phase !== 'playing') break
  await hold(Math.floor(el / 0.9) % 2 === 0 ? 'ArrowRight' : 'ArrowLeft'); await sleep(30)
}
await hold(null)
const box = await page.locator('canvas.g-canvas').boundingBox()
await ctx.close(); await browser.close()
const webm = path.join(vdir, readdirSync(vdir).find(f => f.endsWith('.webm')))
const crop = `crop=${Math.round(box.width) & ~1}:${Math.round(box.height) & ~1}:${Math.round(box.x)}:${Math.round(box.y)}`
const vf = `${crop},fps=15,scale=${Math.round(box.width * 0.8) & ~1}:-1:flags=neighbor,split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=none`
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', String(Math.max(0, (tStart - tVideo) / 1000 + 0.25).toFixed(2)), '-t', '7.8', '-i', webm, '-vf', vf, path.join(OUT, 'krakie-en-action-v2.gif')])
rmSync(vdir, { recursive: true, force: true }); process.exit(0)
