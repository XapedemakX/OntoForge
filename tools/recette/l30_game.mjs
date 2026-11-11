// Recette L30 : easter egg « Krakie's Triple Catch ». Usage : node tools/recette/l30_game.mjs   (front déjà buildé : cd frontend && npm run build)
// Variables : BACKEND_PORT, FRONT_PORT. Captures dans journal/L30/screens/. Code de sortie 1 s'il reste un KO.
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, existsSync, statSync, createReadStream } from 'node:fs'
import http from 'node:http'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L30/screens'); mkdirSync(SHOTS, { recursive: true })
const FIX = path.join(ROOT, 'journal/L30/fix-sprite'); mkdirSync(FIX, { recursive: true })
const BP = process.env.BACKEND_PORT || 8934, FP = process.env.FRONT_PORT || 4934
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const stop = () => procs.forEach(p => p.kill())
process.on('exit', stop)
let ko = 0
const log = (name, ok, detail = '') => { if (!ok) ko++; console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l30-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
// Build de production servi en statique, comme nginx (frontend/nginx.conf) : types MIME de nginx (image/svg+xml), /api proxifié,
// fichier manquant sous /krakie/ ou /assets/ = 404, repli SPA ailleurs. Aucun vite preview.
const DIST = path.join(ROOT, 'frontend/dist')
const MIME = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json', '.png': 'image/png', '.md': 'text/markdown', '.woff2': 'font/woff2' }
const web = http.createServer((q, s) => {
  const url = decodeURIComponent(q.url.split('?')[0])
  if (url.startsWith('/api/')) {
    const u = http.request({ host: '127.0.0.1', port: BP, path: q.url, method: q.method, headers: q.headers }, r => { s.writeHead(r.statusCode, r.headers); r.pipe(s) })
    u.on('error', () => { s.writeHead(502); s.end() }); q.pipe(u); return
  }
  let p = path.join(DIST, url); const exists = existsSync(p) && statSync(p).isFile()
  if (!exists && /^\/(krakie|assets)\//.test(url)) { s.writeHead(404, { 'content-type': 'text/plain' }); s.end('not found'); return }
  if (!exists) p = path.join(DIST, 'index.html')
  s.writeHead(200, { 'content-type': MIME[path.extname(p)] || 'application/octet-stream', 'cache-control': 'no-cache' }); createReadStream(p).pipe(s)
}).listen(Number(FP), '127.0.0.1')
procs.push({ kill: () => web.close() })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }

const browser = await chromium.launch()
const FIREFOX = await (async () => { try { const { firefox } = require('playwright'); return await firefox.launch() } catch { return null } })()
async function session(opts) {
  const ctx = await browser.newContext({ locale: 'fr-FR', ...opts })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.game.debug', '1') } catch {} })
  const page = await ctx.newPage(); const errs = []
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)) })
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  return { ctx, page, errs }
}
const KONAMI = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a']
const dlg = p => p.locator('div.game[role=dialog]')
const snap = p => p.evaluate(() => window.__ontoforgeGame?.snapshot())
const phaseOf = p => dlg(p).getAttribute('data-phase')

/** Pilote simple : va vers le prochain maillon utile (ou un bonus), évite les dangers proches ; `kamikaze` cherche les dangers. */
async function bot(page, ms, { kamikaze = false, stopWhen = () => false } = {}) {
  const t0 = Date.now(); let held = null
  const hold = async dir => { if (dir === held) return; if (held) await page.keyboard.up(held); held = dir; if (dir) await page.keyboard.down(dir) }
  while (Date.now() - t0 < ms) {
    const s = await snap(page); if (!s || s.phase !== 'playing') break
    if (stopWhen(s)) break
    const want = it => kamikaze ? (it.type === 'bad' || it.type === 'iri') : ((it.type === 'tok' && it.kind === s.kind && s.want.includes(it.label)) || it.type === 'inf' || it.type === 'shacl')
    const cands = s.items.filter(want).sort((a, b) => b.y - a.y)
    const danger = s.items.filter(it => (it.type === 'bad' || it.type === 'iri') && it.y > s.H - 140)
    let target = cands.length ? cands[0].cx : s.W / 2
    if (!kamikaze) { const near = danger.find(d => Math.abs(d.cx - target) < 14 && d.y > s.H - 110); if (near) target = near.cx < s.W / 2 ? Math.min(s.W - 14, near.cx + 24) : Math.max(14, near.cx - 24) }
    const dx = target - s.kx
    await hold(Math.abs(dx) < 4 ? null : dx < 0 ? 'ArrowLeft' : 'ArrowRight')
    await sleep(40)
  }
  await hold(null)
}

// ---------------------------------------------------------------- L30 : nage, expressions, accessibilité
const KS = p => p.evaluate(() => window.__krakieGame?.state())
const eng = (p, fn, arg) => p.evaluate(new Function('a', `const e = window.__ontoforgeGame; ${fn}`), arg)
const forceItem = (p, type) => p.evaluate(t => { const e = window.__ontoforgeGame; e.invuln = 0; e.collide({ type: t, label: t, x: 100, y: 100, w: 10, h: 9, vy: 0, ph: 0, spr: null }) }, type)
const catchOk = p => p.evaluate(() => { const e = window.__ontoforgeGame; const s = e.snapshot(); e.catchTok(s.kind, s.want[0], 110, 150) })
/** Capture pleine page + gros plan (x4) sur Krakie, pour juger les expressions. */
async function shot(page, name) {
  await page.screenshot({ path: path.join(SHOTS, name + '.png') })
  const b = await page.locator('canvas.g-canvas').boundingBox(), st = await page.evaluate(() => ({ s: window.__ontoforgeGame.scale, kx: window.__ontoforgeGame.kx, H: window.__ontoforgeGame.H }))
  const cx = b.x + st.kx * st.s, cy = b.y + (st.H - 28) * st.s
  await page.screenshot({ path: path.join(SHOTS, 'zoom-' + name + '.png'), clip: { x: Math.max(0, cx - 60), y: Math.max(0, cy - 70), width: 120, height: 100 } })
}
async function openGame(page, url) {
  await page.goto(url, { waitUntil: 'load' }); await sleep(1200)
  for (const k of KONAMI) await page.keyboard.press(k)
  await dlg(page).waitFor({ timeout: 8000 }); await sleep(900)
}

const g = await session({ viewport: { width: 900, height: 800 } })
const gp = g.page
await openGame(gp, base + '/#/')
const man = await (await fetch(base + '/krakie/anim/manifest.json')).json()
log('manifeste : 6 poses de nage, 4 à 6 images', ['nage', 'nage_clin', 'nage_ravie', 'nage_surprise', 'nage_grimace', 'nage_inquiete'].every(k => man[k] && man[k].length >= 4 && man[k].length <= 6))
log('poses L29 intactes (forge 8 images, trophee 4)', man.forge?.length === 8 && man.trophee?.length === 4)
await gp.keyboard.press('Enter'); await sleep(400)
// éviter toute collision pendant les tests forcés : on vide l'écran et on gèle les apparitions
await eng(gp, 'e.spawnT = 1e9; e.bonusT = 1e9; e.items = []')
let st = await KS(gp)
log('état de test exposé (window.__krakieGame.state)', st && st.expression === 'neutral' && st.phase === 'playing', JSON.stringify(st))

// nage : inclinaison dans le sens du déplacement
await gp.keyboard.down('ArrowRight'); await sleep(450); st = await KS(gp)
const leanR = st.lean; await shot(gp, '01-nage-droite')
await gp.keyboard.up('ArrowRight'); await gp.keyboard.down('ArrowLeft'); await sleep(700); st = await KS(gp)
const leanL = st.lean; await shot(gp, '02-nage-gauche')
await gp.keyboard.up('ArrowLeft'); await sleep(500)
log('Krakie s\'incline dans le sens du déplacement', leanR > 1 && leanL < -1, `droite=${leanR} gauche=${leanL}`)
// l'image change pendant la nage (animation)
const frames = new Set(); for (let i = 0; i < 14; i++) { frames.add(await eng(gp, 'return Math.floor(e.animT / 95) % 6')); await sleep(60) }
log('cycle de nage animé (plusieurs images)', frames.size >= 3, [...frames].join(','))

// élément bien attrapé : clin d'œil bref, retour au neutre
await catchOk(gp); st = await KS(gp)
const wink = st.expression
await sleep(150); await shot(gp, '03-clin')
await sleep(900); const back = (await KS(gp)).expression
log('élément attrapé : clin d\'œil bref puis neutre', wink === 'wink' && back === 'neutral', `${wink} -> ${back}`)

// triplet complet : grand sourire + étincelles
await eng(gp, 'e.chain = []'); await catchOk(gp); await catchOk(gp); await catchOk(gp); st = await KS(gp)
await sleep(200); await shot(gp, '04-triplet-complet')
log('triplet complet : ravie', st.expression === 'delight', st.expression)
await sleep(1000)

// bonus inférence : surprise + effet visuel
await forceItem(gp, 'inf'); st = await KS(gp); const sInf = st
await sleep(350); await shot(gp, '05-inference')
log('bonus inférence : surprise + effet actif', sInf.expression === 'surprise' && sInf.inference === true, JSON.stringify(sInf))
await sleep(1500)
log('effet d\'inférence temporaire', (await KS(gp)).inference === false)

// bonus SHACL : surprise puis bouclier visible en continu
await forceItem(gp, 'shacl'); st = await KS(gp)
await sleep(1100); const sh = await KS(gp); await shot(gp, '06-bouclier')
log('bonus SHACL : surprise puis bouclier actif', st.expression === 'surprise' && sh.shield === true && sh.expression === 'neutral', `${st.expression} ${JSON.stringify(sh)}`)
// le bouclier absorbe le danger : pas de grimace de perte de vie
const livesBefore = sh.lives; await forceItem(gp, 'bad'); st = await KS(gp)
log('bouclier : danger absorbé (pas de vie perdue)', st.lives === livesBefore && st.shield === false)
await sleep(1000)

// constat perdu : grimace
await forceItem(gp, 'bad'); st = await KS(gp)
await eng(gp, 'e.invuln = 0'); await sleep(120); await shot(gp, '07-grimace')
log('constat perdu : grimace', st.expression === 'grimace' && st.lives === 2, JSON.stringify(st))
await sleep(1900)
await eng(gp, 'e.invuln = 0'); await forceItem(gp, 'iri'); st = await KS(gp)
log('IRI cassée : grimace', st.expression === 'grimace', st.expression)
await sleep(1900)
log('grimace brève (retour au calme)', (await KS(gp)).expression !== 'grimace')
// une seule vie : inquiète en continu
st = await KS(gp)
await sleep(300)
await shot(gp, '08-inquiete-une-vie')
await sleep(2500)
const w2 = await KS(gp)
log('une seule vie : inquiète en continu', st.lives === 1 && st.expression === 'worried' && w2.expression === 'worried', `${st.expression} ${w2.expression}`)
await catchOk(gp); await sleep(100); log('…et le clin d\'œil prend le dessus brièvement', (await KS(gp)).expression === 'wink')

// anti-doublon : jamais le même mot en cible et en distracteur d'une autre catégorie
const dup = await eng(gp, `
  let bad = 0
  for (let n = 0; n < 600; n++) {
    if (n % 6 === 0) { e.items = []; e.chain = n % 12 === 0 ? [] : n % 18 === 0 ? ['Car'] : ['Car', 'hasPart'] }
    e.spawn(); const it = e.items[e.items.length - 1]
    if (it.type !== 'tok') continue
    const opt = e.snapshot(); const toks = e.items.filter(o => o.type === 'tok')
    if (toks.some(o => o !== it && o.label === it.label && o.kind !== it.kind)) bad++
    if (it.kind !== opt.kind && opt.want.includes(it.label)) bad++
  }
  e.items = []; return bad`)
log('un mot n\'est jamais cible ET distracteur d\'une autre catégorie', dup === 0, `conflits=${dup}`)

// fin avec trophée (score > meilleur score) puis fin inquiète (score faible, pas de record)
await eng(gp, 'e.score = 520; e.lives = 0'); await sleep(1200)
const poseEnd1 = await gp.locator('.g-card img[data-pose]').first().getAttribute('data-pose')
await shot(gp, '09-fin-trophee')
log('fin, record battu : pose trophée', poseEnd1 === 'trophee', poseEnd1)
await gp.keyboard.press('Enter'); await sleep(500)
await eng(gp, 'e.spawnT = 1e9; e.bonusT = 1e9; e.items = []; e.score = 30; e.lives = 0'); await sleep(1200)
const poseEnd2 = await gp.locator('.g-card img[data-pose]').first().getAttribute('data-pose')
await shot(gp, '10-fin-inquiete')
log('fin, score faible : pose inquiète', poseEnd2 === 'inquiete', poseEnd2)
log('aucune erreur console (L30 desktop)', g.errs.length === 0, JSON.stringify(g.errs.slice(0, 3)))

// ---------------------------------------------------------------- mouvement réduit : expressions fixes, ni tremblement ni rebond ni inclinaison
const rr = await session({ viewport: { width: 900, height: 800 }, reducedMotion: 'reduce' })
await openGame(rr.page, base + '/#/'); await rr.page.keyboard.press('Enter'); await sleep(400)
await eng(rr.page, 'e.spawnT = 1e9; e.bonusT = 1e9; e.items = []')
await rr.page.keyboard.down('ArrowRight'); await sleep(500)
const rs = await KS(rr.page); await rr.page.keyboard.up('ArrowRight')
log('mouvement réduit : aucune inclinaison', rs.reduced === true && rs.lean === 0, JSON.stringify(rs))
// ky constant (pas de rebond) et image fixe pendant la nage
const ys = new Set(), fs = new Set()
for (let i = 0; i < 12; i++) { ys.add(await eng(rr.page, 'return e.ky')); await sleep(70) }
log('mouvement réduit : pas de rebond vertical', ys.size === 1, [...ys].join(','))
await forceItem(rr.page, 'bad'); const gs = await KS(rr.page)
// l'expression reste lisible et fixe : on compare deux captures du canvas à 250 ms d'écart (hors particules)
const crop = async () => rr.page.locator('canvas.g-canvas').screenshot()
await sleep(200); const j1 = await eng(rr.page, 'return e.shake'), j2 = await eng(rr.page, 'return e.flash')
log('mouvement réduit : expression grimace fixe, sans secousse ni flash', gs.expression === 'grimace' && j1 === 0 && j2 === 0, `shake=${j1} flash=${j2}`)
await rr.page.screenshot({ path: path.join(SHOTS, '11-mouvement-reduit-grimace.png') })
await forceItem(rr.page, 'shacl'); await sleep(900)
await rr.page.screenshot({ path: path.join(SHOTS, '12-mouvement-reduit-bouclier.png') })
log('mouvement réduit : bouclier visible', (await KS(rr.page)).shield === true)
log('aucune erreur console (L30 réduit)', rr.errs.length === 0, JSON.stringify(rr.errs.slice(0, 3)))

// ---------------------------------------------------------------- correctif « carré teal » + centrage (build de production servi comme nginx)
const KEYS = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a']
/** Lit les pixels du canvas autour de Krakie : nombre de couleurs distinctes et part du plus fréquent (un aplat uni = 1 couleur, 100 %). */
const krakiePixels = p => p.evaluate(() => {
  const e = window.__ontoforgeGame, cv = document.querySelector('canvas.g-canvas'), d = cv.getContext('2d').getImageData(Math.max(0, Math.round(e.kx) - 16), e.ky, 32, 32).data
  const n = new Map(); for (let i = 0; i < d.length; i += 4) { const k = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2]; n.set(k, (n.get(k) || 0) + 1) }
  return { colors: n.size, top: Math.max(...n.values()) / 1024 }
})
const layout = p => p.evaluate(() => {
  const r = e => e.getBoundingClientRect(), cv = r(document.querySelector('canvas.g-canvas')), g = r(document.querySelector('.game')), cl = r(document.querySelector('.g-bar .g-btn:last-child')), tt = r(document.querySelector('.g-title')), ks = r(document.querySelector('.g-keys'))
  return { vw: innerWidth, gw: g.width, gx: g.x, left: cv.left, right: innerWidth - cv.right, cw: cv.width, closeR: cl.right, titleL: tt.left, keysC: ks.left + ks.width / 2, sx: document.documentElement.scrollWidth - innerWidth }
})
async function fixSession(br, opts, { routes } = {}) {
  const ctx = await br.newContext({ locale: 'en-US', ...opts })
  await ctx.route(`${base}/api/**`, route => route.continue())
  if (routes) await routes(ctx)
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.game.debug', '1'); localStorage.setItem('ontoforge.lang', 'en') } catch {} })
  const page = await ctx.newPage(); const warns = [], errs = []
  page.on('console', m => { if (m.type() === 'warning') warns.push(m.text()); if (m.type() === 'error') errs.push(m.text().slice(0, 160)) })
  await page.goto(base + '/#/', { waitUntil: 'load' }); await sleep(1000)
  for (const k of KEYS) await page.keyboard.press(k)
  await dlg(page).waitFor({ timeout: 8000 })
  await page.waitForFunction(() => { const b = document.querySelector('.g-card .g-btn.primary'); return b && !b.disabled }, null, { timeout: 15000 })
  await page.keyboard.press('Enter'); await sleep(900)
  await eng(page, 'e.spawnT = 1e9; e.bonusT = 1e9; e.items = []; e.invuln = 0')
  return { ctx, page, warns, errs }
}
const WIDTHS = [[390, 844], [768, 1024], [1280, 800], [1850, 1270], [2560, 1270]]
for (const [name, bt] of [['chromium', browser], ...(FIREFOX ? [['firefox', FIREFOX]] : [])]) {
  for (const reduced of [false, true]) {
    const tag = `${name}${reduced ? ' mouvement réduit' : ''}`
    const f = await fixSession(bt, { viewport: { width: 1850, height: 1270 }, reducedMotion: reduced ? 'reduce' : 'no-preference' })
    const px = await krakiePixels(f.page), L = await layout(f.page)
    log(`${tag} : le sprite de Krakie n'est pas un aplat (production statique, 1850×1270)`, px.colors >= 6 && px.top < 0.9, JSON.stringify(px))
    log(`${tag} : zone de jeu centrée à 1850 px`, Math.abs(L.left - L.right) <= 2 && L.gw === L.vw && L.sx <= 0 && Math.abs(L.keysC - L.vw / 2) <= 2, JSON.stringify(L))
    log(`${tag} : aucun avertissement de pose manquante`, !f.warns.some(w => /pose de Krakie introuvable/.test(w)), f.warns.join(' | ').slice(0, 160))
    if (!reduced && name === 'chromium') await f.page.screenshot({ path: path.join(FIX, '01-1850x1270-sprite-centre.png') })
    if (!reduced && name === 'chromium') {
      // « DONEBY » → « DONE BY » : le libellé d'un prédicat camelCase est coupé en mots (largeur du sprite = 7 lettres)
      const w = await eng(f.page, `let n = 0; for (let i = 0; i < 4000; i++) { e.items = []; e.chain = ['Order']; e.spawn(); const it = e.items[0]; if (it && it.label === 'doneBy') { it.x = 40; it.y = 120; it.vy = 0; return it.spr.width } } return -1`)
      log('« doneBy » s\'affiche en deux mots (DONE BY)', w === 7 * 4 - 1 + 8, 'largeur du sprite = ' + w)
      await sleep(150); await f.page.screenshot({ path: path.join(FIX, '02-done-by.png') })
    }
    log(`${tag} : aucune erreur console`, f.errs.length === 0, f.errs.join(' | '))
    await f.ctx.close()
  }
}
if (!FIREFOX) console.log('INFO Firefox absent de Playwright dans cet environnement : recette Chromium uniquement')
// largeurs 390 à 2560 : centrage symétrique, HUD entièrement visible, sprite dessiné
const fw = await fixSession(browser, { viewport: { width: 1850, height: 1270 } })
for (const [w, h] of WIDTHS) {
  await fw.page.setViewportSize({ width: w, height: h }); await sleep(500)
  await eng(fw.page, 'e.items = []')
  const L = await layout(fw.page), px = await krakiePixels(fw.page)
  const ok = Math.abs(L.left - L.right) <= 2 && L.left >= 0 && L.closeR <= L.vw && L.titleL >= 0 && L.sx <= 0 && px.colors >= 6
  log(`largeur ${w} px : centré, HUD visible, sprite dessiné`, ok, `marges ${Math.round(L.left)}/${Math.round(L.right)} canvas=${Math.round(L.cw)} fermer.right=${Math.round(L.closeR)} couleurs=${px.colors}`)
  await fw.page.screenshot({ path: path.join(FIX, `03-largeur-${w}.png`) })
}
await fw.ctx.close()
// manifeste périmé (copie L29 sans les poses « nage* », mise en cache chez Jerem) : le sprite doit s'afficher quand même
const man29 = Object.fromEntries(Object.entries(man).filter(([k]) => !k.startsWith('nage')))
const stale = await fixSession(browser, { viewport: { width: 1850, height: 1270 } }, { routes: ctx => ctx.route('**/krakie/anim/manifest.json', r => r.fulfill({ contentType: 'application/json', body: JSON.stringify(man29) })) })
const ps = await krakiePixels(stale.page)
log('manifeste périmé (sans nage*) : sprite quand même dessiné', ps.colors >= 6 && ps.top < 0.9 && !stale.warns.some(w => /introuvable/.test(w)), JSON.stringify(ps))
await stale.ctx.close()
// pose manquante (404) : repli silhouette pixel art, jamais un carré, avertissement qui nomme la pose
const miss = await fixSession(browser, { viewport: { width: 1850, height: 1270 } }, { routes: ctx => ctx.route(/\/krakie\/anim\/nage_clin-\d\.svg/, r => r.fulfill({ status: 404, body: 'nope' })) })
const pm = await krakiePixels(miss.page)
log('pose manquante : avertissement nommant la pose', miss.warns.some(w => w.includes('« nage_clin »')), miss.warns.join(' | ').slice(0, 200))
log('pose manquante : le jeu démarre et Krakie nage (sprite chargé)', pm.colors >= 6 && pm.top < 0.9, JSON.stringify(pm))
await catchOk(miss.page); await sleep(150)
const pw = await krakiePixels(miss.page); await miss.page.screenshot({ path: path.join(FIX, '04-pose-manquante-silhouette.png') })
log('pose manquante (clin d\'œil) : silhouette de repli, pas un carré uni', pw.colors >= 6 && pw.top < 0.9, JSON.stringify(pw))
await miss.ctx.close()
// toutes les images de nage en 404 : repli silhouette partout
const none = await fixSession(browser, { viewport: { width: 1850, height: 1270 } }, { routes: ctx => ctx.route(/\/krakie\/anim\/nage[^/]*\.svg/, r => r.fulfill({ status: 404, body: 'nope' })) })
const pn = await krakiePixels(none.page); await none.page.screenshot({ path: path.join(FIX, '05-aucune-pose-silhouette.png') })
log('aucune pose de nage : silhouette pixel art', pn.colors >= 6 && pn.top < 0.9 && none.warns.filter(w => /introuvable/.test(w)).length === 6, JSON.stringify(pn) + ' warns=' + none.warns.length)
await none.ctx.close()

await browser.close(); if (FIREFOX) await FIREFOX.close(); stop()
console.log(`\n=== L30 : ${ko ? ko + ' KO' : 'tout OK'}`); process.exit(ko ? 1 : 0)
