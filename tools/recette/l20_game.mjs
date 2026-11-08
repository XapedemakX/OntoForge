// Recette L20 : easter egg « Krakie's Triple Catch ». Usage : node tools/recette/l20_game.mjs   (front déjà buildé : cd frontend && npm run build)
// Variables : BACKEND_PORT, FRONT_PORT. Captures dans journal/L20/screens/. Code de sortie 1 s'il reste un KO.
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
const SHOTS = path.join(ROOT, 'journal/L20/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8920, FP = process.env.FRONT_PORT || 4920
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const stop = () => procs.forEach(p => p.kill())
process.on('exit', stop)
let ko = 0
const log = (name, ok, detail = '') => { if (!ok) ko++; console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l20-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
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

// ---------------------------------------------------------------- desktop
const d = await session({ viewport: { width: 1280, height: 800 } })
const { page } = d
await page.goto(base + '/#/parametres', { waitUntil: 'load' }); await sleep(1500)
const hint = (await page.locator('body').innerText()).includes('Krakie aime les codes rétro')
log('indice discret dans Paramètres', hint)
const noGame = async () => (await dlg(page).count()) === 0
log('jeu fermé au départ', await noGame())

// le clavier n'est pas capturé quand le jeu est fermé
await page.evaluate(() => { window.__dp = []; document.addEventListener('keydown', e => window.__dp.push(e.defaultPrevented)) })
await page.keyboard.press('ArrowLeft'); await page.keyboard.press('Space')
log('clavier non capturé (jeu fermé)', (await page.evaluate(() => window.__dp)).every(x => x === false))

// frappe dans un champ : aucun déclenchement
await page.goto(base + '/#/', { waitUntil: 'load' }); await sleep(1200)
await page.evaluate(() => { const i = document.createElement('input'); i.id = 'tmp-in'; document.body.appendChild(i) })
await page.locator('#tmp-in').focus(); await page.keyboard.type('krakie'); for (const k of KONAMI) await page.keyboard.press(k)
await sleep(400); log('pas de déclenchement dans un champ de saisie', await noGame())
await page.evaluate(() => document.getElementById('tmp-in').remove()); await page.locator('body').click({ position: { x: 5, y: 5 } })

// code Konami
for (const k of KONAMI) await page.keyboard.press(k)
await dlg(page).waitFor({ timeout: 8000 }).catch(() => {})
log('Konami ouvre le jeu', (await dlg(page).count()) === 1)
await sleep(900)
log('carte de départ affichée', (await phaseOf(page)) === 'ready' && (await page.locator('.g-card h3').innerText()).toLowerCase().includes('triple catch'))
log('appli inerte derrière le jeu', await page.evaluate(() => document.getElementById('root').inert === true))
await page.screenshot({ path: path.join(SHOTS, '01-depart.png') })

// partie : on joue avec le pilote, capture quand un triplet est complété
await page.keyboard.press('Enter'); await sleep(300)
log('partie lancée (Entrée)', (await phaseOf(page)) === 'playing')
await bot(page, 70000, { stopWhen: s => s.triples >= 3 || s.phase !== 'playing' })
await sleep(700)
const s1 = await snap(page)
log('triplets formés', s1.triples >= 2, `triplets=${s1.triples} score=${s1.score} niveau=${s1.level} vies=${s1.lives}`)
await page.screenshot({ path: path.join(SHOTS, '02-partie.png') })

// pause avec P, reprise
await page.keyboard.press('p'); await sleep(250)
const pausedAt = await snap(page); const okP = (await phaseOf(page)) === 'paused'; await sleep(600)
const after = await snap(page)
log('pause (P) fige la partie', okP && pausedAt.items.length === after.items.length && pausedAt.items.every((it, i) => Math.abs(it.y - after.items[i].y) < 0.01))
await page.keyboard.press('p'); await sleep(250); log('reprise (P)', (await phaseOf(page)) === 'playing')

// fin de partie : on fonce dans les dangers
await bot(page, 90000, { kamikaze: true })
for (let i = 0; i < 60 && (await phaseOf(page)) !== 'over'; i++) await sleep(500)
log('fin de partie atteinte', (await phaseOf(page)) === 'over')
await sleep(900)
const overTxt = await page.locator('.g-card').innerText()
log('écran de fin : score, meilleur score, phrase', /points/.test(overTxt) && /Meilleur score/.test(overTxt) && /«/.test(overTxt), overTxt.replace(/\n+/g, ' | ').slice(0, 160))
await page.screenshot({ path: path.join(SHOTS, '03-fin.png') })
const best = await page.evaluate(() => localStorage.getItem('ontoforge.game.best'))
log('meilleur score en localStorage', Number(best) > 0, `best=${best}`)

// Échap : retour à l'appli
await page.keyboard.press('Escape'); await sleep(500)
log('Échap ferme le jeu', await noGame())
log('appli de nouveau active', await page.evaluate(() => !document.getElementById('root').inert))
await page.goto(base + '/#/parametres', { waitUntil: 'load' }); await sleep(1200)
log('Paramètres fonctionnent après le jeu', (await page.locator('body').innerText()).includes('Paramètres'))

// variante : taper « krakie » hors champ
await page.locator('body').click({ position: { x: 5, y: 5 } }); await page.keyboard.type('krakie')
await dlg(page).waitFor({ timeout: 5000 }).catch(() => {})
log('« krakie » tapé ouvre le jeu', (await dlg(page).count()) === 1); await page.keyboard.press('Escape'); await sleep(300)
// variante : 5 clics sur le logo
const logo = page.locator('aside .logo').first()
for (let i = 0; i < 5; i++) await logo.click()
await dlg(page).waitFor({ timeout: 5000 }).catch(() => {})
log('5 clics sur le logo ouvrent le jeu', (await dlg(page).count()) === 1); await page.keyboard.press('Escape'); await sleep(300)
log('aucune erreur console (desktop)', d.errs.length === 0, JSON.stringify(d.errs.slice(0, 3)))

// ---------------------------------------------------------------- mouvement réduit + anglais + mobile
const r = await session({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true, reducedMotion: 'reduce' })
await r.page.goto(base + '/#/', { waitUntil: 'load' }); await sleep(1200)
for (let i = 0; i < 5; i++) await r.page.locator('.logo-top').first().click().catch(() => {})
await dlg(r.page).waitFor({ timeout: 5000 }).catch(() => {})
log('mobile + mouvement réduit : le jeu s\'ouvre (clics logo)', (await dlg(r.page).count()) === 1)
await sleep(800)
await r.page.screenshot({ path: path.join(SHOTS, '04-mobile-depart.png') })
await r.page.locator('.g-card .g-btn.primary').tap(); await sleep(300)
const padVisible = await r.page.locator('.g-pad').isVisible()
log('boutons ← → visibles sur mobile', padVisible)
await r.page.locator('.g-btn.pad').nth(1).dispatchEvent('pointerdown', { pointerId: 1, isPrimary: true }); await sleep(700)
const mk = (await snap(r.page)).kx
await r.page.locator('.g-btn.pad').nth(1).dispatchEvent('pointerup', { pointerId: 1, isPrimary: true })
await bot(r.page, 6000).catch(() => {})
await r.page.screenshot({ path: path.join(SHOTS, '05-mobile-partie.png') })
log('mobile : Krakie se déplace avec le bouton →', mk > 110, `kx=${Math.round(mk)}`)
const tapOk = await r.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)
log('mobile : pas de débordement horizontal', tapOk)
log('aucune erreur console (mobile réduit)', r.errs.length === 0, JSON.stringify(r.errs.slice(0, 3)))

await browser.close(); stop()
console.log(`\n=== L20 : ${ko ? ko + ' KO' : 'tout OK'}`); process.exit(ko ? 1 : 0)
