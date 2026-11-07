// Outils communs pour filmer OntoForge : serveurs, contexte navigateur, capture CDP (screencast JPEG horodaté), faux curseur.
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
export const HERE = path.join(ROOT, 'tools/video')
export const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
export const stopAll = () => procs.forEach(p => { try { p.kill() } catch {} })
process.on('exit', stopAll)

export async function startServers({ BP = 8941, FP = 4941, SP = 8931 } = {}) {
  run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
    { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-vid-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
  run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend') })
  run('/home/claude/venv/bin/python', [path.join(HERE, 'sparql_server.py'), String(SP)], {})
  const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
  for (let i = 0; i < 80; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
  for (let i = 0; i < 80; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
  return { B, base, BP, FP, sparql: `http://127.0.0.1:${SP}/sparql` }
}

export async function newPage(browser, srv, { width = 1440, height = 810, scale = 4 / 3 } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: scale, locale: 'en-US', colorScheme: 'light' })
  await ctx.route(`${srv.base}/api/**`, route => route.continue({ url: route.request().url().replace(srv.base, `http://127.0.0.1:${srv.BP}`) }))
  await ctx.route(`${srv.base}/__video/**`, route => {
    const u = new URL(route.request().url())
    if (u.pathname.startsWith('/__video/font/')) return route.fulfill({ body: readFileSync(path.join(ROOT, 'frontend/node_modules/@fontsource/ibm-plex-sans/files', path.basename(u.pathname))), contentType: 'font/woff2' })
    return route.fulfill({ body: readFileSync(path.join(HERE, path.basename(u.pathname))), contentType: 'text/html; charset=utf-8' })
  })
  await ctx.addInitScript({ content: readFileSync(path.join(HERE, 'overlay.js'), 'utf8') })
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1') } catch {} })
  const page = await ctx.newPage()
  const errs = []; page.on('pageerror', e => errs.push(String(e)))
  return { ctx, page, errs }
}

export { chromium }

// Mouvement de souris lisible (courbe douce), puis clic.
export function mouse(page) {
  let cur = { x: 720, y: 420 }
  const ease = t => t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
  async function moveTo(x, y, ms = 650) {
    const n = Math.max(8, Math.round(ms / 16)); const from = { ...cur }
    for (let i = 1; i <= n; i++) { const t = ease(i / n); await page.mouse.move(from.x + (x - from.x) * t, from.y + (y - from.y) * t); await sleep(ms / n) }
    cur = { x, y }
  }
  async function to(locator, ms) {
    const l = (typeof locator === 'string' ? page.locator(locator) : locator).first()
    await l.waitFor({ state: 'visible', timeout: 8000 }); await l.scrollIntoViewIfNeeded()
    const b = await l.boundingBox(); await moveTo(b.x + b.width / 2, b.y + b.height / 2, ms); return l
  }
  async function click(locator, { ms, pause = 250 } = {}) { await to(locator, ms); await sleep(pause); await page.mouse.down(); await sleep(70); await page.mouse.up(); await sleep(350) }
  async function type(locator, text, { delay = 45 } = {}) { await click(locator); await page.keyboard.type(text, { delay }) }
  return { moveTo, to, click, type, get pos() { return cur } }
}

// Capture : screencast CDP (images JPEG horodatées, envoyées seulement quand l'écran change).
export async function startCapture(page, { quality = 92, maxWidth = 1920, maxHeight = 1080 } = {}) {
  const cdp = await page.context().newCDPSession(page)
  const frames = []
  cdp.on('Page.screencastFrame', async f => { frames.push({ t: f.metadata.timestamp, data: f.data }); try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }) } catch {} })
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality, maxWidth, maxHeight, everyNthFrame: 1 })
  return { frames, async stop() { await cdp.send('Page.stopScreencast').catch(() => {}) } }
}

export const caption = (page, html) => page.evaluate(h => window.__vid && window.__vid.caption(h), html)
export const chapter = (page, t) => page.evaluate(h => window.__vid && window.__vid.chapter(h), t)
