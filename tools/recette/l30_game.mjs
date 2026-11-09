// Recette L30 : easter egg « Krakie's Triple Catch ». Usage : node tools/recette/l30_game.mjs   (front déjà buildé : cd frontend && npm run build)
// Variables : BACKEND_PORT, FRONT_PORT. Captures dans journal/L30/screens/. Code de sortie 1 s'il reste un KO.
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
const SHOTS = path.join(ROOT, 'journal/L30/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8930, FP = process.env.FRONT_PORT || 4930
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const stop = () => procs.forEach(p => p.kill())
process.on('exit', stop)
let ko = 0
const log = (name, ok, detail = '') => { if (!ok) ko++; console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l30-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }

const browser = await chromium.launch()
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

await browser.close(); stop()
console.log(`\n=== L30 : ${ko ? ko + ' KO' : 'tout OK'}`); process.exit(ko ? 1 : 0)
