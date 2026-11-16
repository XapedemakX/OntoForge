// L44 (phase 1) : audit mobile — parcours réels sur appareils émulés, mesures et captures. N'échoue pas : il mesure.
// Usage : BACKEND_PORT=9021 FRONT_PORT=5021 node tools/recette/mobile_audit.mjs [--local] [--devices=iphone15,pixel7,ipadmini] [--dark]
// Front buildé avant (cd frontend && npm run build). Version web par défaut (tools/recette/web_server.mjs : authentification, CSP, HTTPS),
// --local pour la version docker compose. Comptes et secrets tirés au hasard à l'exécution. Projet « Automaint » créé depuis samples/automaint.
// Sorties : journal/L44/avant/<appareil>-<thème>-<écran>.png et journal/L44/avant/mesures-<mode>.json
// Mesures par écran : éléments interactifs visibles, cibles < 44 px, débordement horizontal, textes coupés, champs < 16 px,
// éléments masqués par Krakie (bouton flottant / aquarium), erreurs de console et violations de CSP.
// Les captures sont écrites en pleine résolution (DPR de l'appareil) ; pour le journal, elles ont été réduites à 480 px (640 px iPad)
// et quantifiées à 128 couleurs avec Pillow avant le commit.
// Gestes (éditeur graphique et carte métier) via CDP Input.dispatchTouchEvent : glisser, pincer, toucher un nœud, appui long.
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { startWeb, apiClient, ROOT } from './web_server.mjs'
const require = createRequire(import.meta.url)
let pw
try { pw = require('playwright') } catch { pw = require('/opt/node22/lib/node_modules/playwright') }
const { chromium, devices } = pw
const sleep = ms => new Promise(r => setTimeout(r, ms))
const arg = (k, d) => (process.argv.find(a => a.startsWith(`--${k}=`)) || '').split('=')[1] || d
const MODE = process.argv.includes('--local') ? 'local' : 'web'
const OUT = path.join(ROOT, 'journal/L44/avant'); mkdirSync(OUT, { recursive: true })
const DEV = {
  iphone15: devices['iPhone 15'], pixel7: devices['Pixel 7'], ipadmini: devices['iPad Mini'],
}
const want = arg('devices', 'iphone15,pixel7,ipadmini').split(',')
const DARK = process.argv.includes('--dark')

const srv = await startWeb({ mode: MODE, backendPort: process.env.BACKEND_PORT || 9021, frontPort: process.env.FRONT_PORT || 5021 })
const base = srv.base
const api = apiClient(base)
if (MODE === 'web') await api.login('jerem', srv.users.jerem)
const proj = (await api.call('POST', '/api/projects', { name: 'Automaint', sample: 'automaint' })).json
const pid = proj.id
console.log('projet', pid)

const SCREENS = ['tableau', 'ontologie', 'ontologie-liste', 'carte-metier', 'analyse', 'modele', 'exports', 'requetes', 'assistant', 'versions', 'shacl', 'fichiers']

// ---- mesures dans la page --------------------------------------------------------------------------------------------
const measure = () => {
  const W = innerWidth, H = innerHeight
  const vis = el => { const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return null; if (r.bottom <= 0 || r.top >= H || r.right <= 0 || r.left >= W) return null
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) return null; return r }
  const label = el => (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || el.getAttribute('placeholder') || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 40)
  const inter = [...document.querySelectorAll('a[href], button, input, select, textarea, [role=button], [role=tab], [role=menuitem], [tabindex]:not([tabindex="-1"])')]
    .filter(el => !el.closest('[aria-hidden=true]') && !el.disabled)
  const shown = inter.map(el => [el, vis(el)]).filter(([, r]) => r)
  const small = shown.filter(([, r]) => r.width < 44 || r.height < 44).map(([el, r]) => `${label(el)} ${Math.round(r.width)}×${Math.round(r.height)}`)
  const inputs = shown.filter(([el]) => /INPUT|SELECT|TEXTAREA/.test(el.tagName) && !['checkbox', 'radio', 'range', 'color'].includes(el.type))
  const tinyFont = inputs.filter(([el]) => parseFloat(getComputedStyle(el).fontSize) < 16).map(([el]) => `${label(el)} ${getComputedStyle(el).fontSize}`)
  // textes coupés : contenu plus large que la boîte et débordement masqué
  const cut = []
  for (const el of document.querySelectorAll('body *')) {
    if (cut.length > 40) break
    if (!el.childNodes.length || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue
    const r = vis(el); if (!r) continue
    const cs = getComputedStyle(el)
    if ((cs.overflowX === 'hidden' || cs.textOverflow === 'ellipsis' || cs.overflow === 'hidden') && el.scrollWidth > el.clientWidth + 2) cut.push(el.innerText.trim().replace(/\s+/g, ' ').slice(0, 40))
  }
  // éléments qui sortent de l'écran à droite (sans défilement de page)
  const offRight = shown.filter(([, r]) => r.right > W + 1).map(([el, r]) => `${label(el)} (x ${Math.round(r.left)}→${Math.round(r.right)})`).slice(0, 15)
  // Krakie : bouton flottant et aquarium au-dessus d'éléments interactifs
  const kr = [...document.querySelectorAll('.ag-fab, .aq-reef, .aq-krakie, .ag-aquarium, [class*=aquarium]')].map(vis).filter(Boolean)
  const hidden = []
  for (const [el, r] of shown) {
    if (el.closest('.ag-fab, [class*=aquarium], .ag-dock')) continue
    for (const k of kr) {
      const ix = Math.min(r.right, k.right) - Math.max(r.left, k.left), iy = Math.min(r.bottom, k.bottom) - Math.max(r.top, k.top)
      if (ix > 4 && iy > 4) { hidden.push(`${label(el)} (${Math.round(ix * iy / (r.width * r.height) * 100)} %)`); break }
    }
  }
  const words = (document.body.innerText.match(/\S+/g) || []).length
  const visText = [...document.querySelectorAll('h1,h2,h3,h4,p,li,td,th,label,span,b,small,div')].filter(el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1) && vis(el)).length
  return {
    vw: W, vh: H, pageW: document.documentElement.scrollWidth, hOverflow: document.documentElement.scrollWidth > W + 1,
    interactive: shown.length, small: small.length, smallList: small.slice(0, 30), tinyFont, cut: cut.slice(0, 20), offRight,
    krakieHides: hidden.slice(0, 15), textBlocks: visText, words,
    headerH: Math.round(document.querySelector('.topbar')?.getBoundingClientRect().height || 0),
  }
}

const results = { mode: MODE, at: new Date().toISOString(), devices: {} }
const browser = await chromium.launch()

async function touch(cdp, type, pts) { await cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map((p, i) => ({ x: p[0], y: p[1], id: i })) }) }
async function drag1(cdp, x, y, dx, dy) { await touch(cdp, 'touchStart', [[x, y]]); for (let i = 1; i <= 8; i++) { await touch(cdp, 'touchMove', [[x + dx * i / 8, y + dy * i / 8]]); await sleep(16) } await touch(cdp, 'touchEnd', []) }
async function pinch(cdp, x, y, from, to) {
  await touch(cdp, 'touchStart', [[x - from, y], [x + from, y]])
  for (let i = 1; i <= 10; i++) { const d = from + (to - from) * i / 10; await touch(cdp, 'touchMove', [[x - d, y], [x + d, y]]); await sleep(16) }
  await touch(cdp, 'touchEnd', [])
}
async function longPress(cdp, x, y) { await touch(cdp, 'touchStart', [[x, y]]); await sleep(900); await touch(cdp, 'touchEnd', []) }

async function gestures(page, cdp, kind, prefix) {
  const out = {}
  const viewSel = kind === 'editor' ? '.react-flow__viewport' : 'svg.bm-svg g'
  const tf = () => page.evaluate(s => { const e = document.querySelector(s); return e ? (e.getAttribute('transform') || e.style.transform || getComputedStyle(e).transform) : null }, viewSel)
  const box = await page.locator(kind === 'editor' ? '.react-flow__pane' : 'svg.bm-svg').first().boundingBox().catch(() => null)
  if (!box) return { error: 'canevas introuvable' }
  // point vide : on cherche un pixel du canevas sans nœud
  const empty = await page.evaluate(([bx, by, bw, bh, k]) => {
    for (let fy = 0.15; fy < 0.95; fy += 0.08) for (let fx = 0.1; fx < 0.95; fx += 0.08) {
      const x = bx + bw * fx, y = by + bh * fy, el = document.elementFromPoint(x, y)
      if (el && (k === 'editor' ? el.classList.contains('react-flow__pane') : (el.tagName === 'svg' || el.classList.contains('bm-bg') || !el.closest('[data-n],[data-e]'))) && el.closest(k === 'editor' ? '.react-flow' : '.bm-svg')) return [x, y]
    }
    return [bx + bw / 2, by + bh / 2]
  }, [box.x, box.y, box.width, box.height, kind])
  let t0 = await tf(); await drag1(cdp, empty[0], empty[1], 80, 60); await sleep(300); let t1 = await tf()
  out.pan = t0 !== t1; out.panTf = [t0, t1]
  t0 = t1; await pinch(cdp, box.x + box.width / 2, box.y + box.height / 2, 40, 120); await sleep(400); t1 = await tf()
  const sc = t => Number((String(t).match(/scale\(([\d.]+)/) || [])[1]); out.pinch = sc(t0) !== sc(t1); out.pinchTf = [t0, t1]
  await page.screenshot({ path: path.join(OUT, `${prefix}-apres-gestes.png`) })
  // toucher un nœud
  const nodeSel = kind === 'editor' ? '.react-flow__node' : '[data-n]'
  const nodes = page.locator(nodeSel)
  let nb = null
  for (let i = 0; i < Math.min(await nodes.count(), 30); i++) { const b = await nodes.nth(i).boundingBox(); if (b && b.x > 10 && b.y > box.y + 10 && b.x + b.width < box.x + box.width - 10 && b.y + b.height < box.y + box.height - 10) { nb = b; break } }
  out.nodeBox = nb && { w: Math.round(nb.width), h: Math.round(nb.height) }
  if (nb) {
    const before = await page.evaluate(() => document.body.innerText.length)
    const cx = nb.x + nb.width / 2, cy = nb.y + nb.height / 2
    await touch(cdp, 'touchStart', [[cx, cy]]); await sleep(60); await touch(cdp, 'touchEnd', []); await sleep(600)
    out.tapSelected = await page.evaluate(k => !!document.querySelector(k === 'editor' ? '.react-flow__node.selected' : '.bm-sel'), kind)
    out.tapTextDelta = (await page.evaluate(() => document.body.innerText.length)) - before
    await page.screenshot({ path: path.join(OUT, `${prefix}-toucher-noeud.png`) })
    const menusBefore = await page.locator('[role=menu], .of-menu, .bm-menu, .ctx-menu').count()
    const nb2 = await nodes.first().boundingBox()
    await longPress(cdp, nb2.x + nb2.width / 2, nb2.y + nb2.height / 2); await sleep(500)
    out.longPressMenu = (await page.locator('[role=menu], .of-menu, .bm-menu, .ctx-menu').count()) > menusBefore
    await page.screenshot({ path: path.join(OUT, `${prefix}-appui-long.png`) })
  }
  return out
}

for (const key of want) {
  const d = { ...DEV[key] }; delete d.defaultBrowserType
  for (const theme of DARK ? ['clair', 'sombre'] : ['clair']) {
    const tag = `${MODE === 'local' ? 'local-' : ''}${key}-${theme}`
    const ctx = await browser.newContext({ ...d, locale: 'fr-FR', colorScheme: theme === 'sombre' ? 'dark' : 'light', ignoreHTTPSErrors: true })
    const page = await ctx.newPage()
    const errs = []
    page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 160)))
    page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)) })
    const R = results.devices[tag] = { viewport: d.viewport, screens: {} }
    const snap = async (name, extra = {}) => {
      await sleep(900)
      try { await page.waitForFunction(() => document.querySelectorAll('.toast').length === 0, null, { timeout: 5000 }) } catch {}
      const m = await page.evaluate(measure)
      await page.screenshot({ path: path.join(OUT, `${tag}-${name}.png`) })
      R.screens[name] = { ...m, ...extra, errors: errs.splice(0) }
      console.log(tag, name.padEnd(18), `inter ${m.interactive} petites ${m.small} coupés ${m.cut.length} débord ${m.hOverflow ? 'OUI' : 'non'} krakie ${m.krakieHides.length} blocs ${m.textBlocks}`)
    }
    await page.goto(base + '/', { waitUntil: 'load' })
    if (MODE === 'web') {
      await page.waitForSelector('[data-testid=login]')
      await snap('00-connexion')
      await page.fill('[data-testid=login-user]', 'jerem'); await page.fill('[data-testid=login-password]', srv.users.jerem); await page.click('[data-testid=login-submit]')
      await page.waitForSelector('[data-testid=logout], .proj-grid', { timeout: 15000 })
    }
    await page.waitForSelector('.proj-grid, .proj, h1', { timeout: 15000 })
    await snap('01-projets')
    // menu (tiroir) ouvert
    if (await page.locator('.menu-btn').isVisible().catch(() => false)) { await page.goto(`${base}/#/projet/${pid}/tableau`); await sleep(1200); await page.click('.menu-btn'); await snap('02-menu-tiroir'); await page.click('.scrim').catch(() => {}); await page.goto(base + '/#/'); await sleep(600) }
    for (const [i, s] of SCREENS.entries()) {
      await page.goto(`${base}/#/projet/${pid}/${s}`); await sleep(1500)
      await snap(String(i + 3).padStart(2, '0') + '-' + s)
      if (s === 'ontologie' || s === 'carte-metier') {
        const cdp = await ctx.newCDPSession(page)
        R.screens[String(i + 3).padStart(2, '0') + '-' + s].gestures = await gestures(page, cdp, s === 'ontologie' ? 'editor' : 'bmap', `${tag}-${String(i + 3).padStart(2, '0')}-${s}`)
        console.log('   gestes', JSON.stringify(R.screens[String(i + 3).padStart(2, '0') + '-' + s].gestures))
      }
      if (s === 'ontologie-liste') {
        // fiche d'une classe : premier élément de la liste
        const item = page.locator('.ol-tree .row', { hasText: 'Garantie' }).first()
        if (await item.count()) { await item.click().catch(() => {}); await snap('05b-fiche-classe') }
      }
    }
    // Krakie ouvert
    await page.goto(`${base}/#/projet/${pid}/tableau`); await sleep(1200)
    if (await page.locator('.ag-fab').isVisible().catch(() => false)) {
      let blocked = null
      try { await page.locator('.ag-fab').tap({ timeout: 3000 }) } catch (e) { blocked = (String(e).match(/<[^>]+>[^<]*<\/\w+> from/) || [String(e).slice(0, 120)])[0]; await page.evaluate(() => document.querySelector('.ag-fab').click()) }
      await snap('20-krakie-ouvert', { fabBlocked: blocked }); await page.keyboard.press('Escape')
    }
    // partage
    await page.goto(`${base}/#/projet/${pid}/tableau`); await sleep(1000)
    const share = page.locator('[data-testid=share-btn], button:has-text("Partager")').first()
    if (await share.count()) { await share.click().catch(() => {}); await snap('21-partage') }
    await page.goto(`${base}/#/parametres`); await sleep(1200); await snap('22-parametres')
    if (MODE === 'web') { await page.goto(`${base}/#/administration`); await sleep(1200); await snap('23-administration') }
    await ctx.close()
  }
}
writeFileSync(path.join(OUT, `mesures-${MODE}.json`), JSON.stringify(results, null, 1))
await browser.close(); await srv.stop(); process.exit(0)
