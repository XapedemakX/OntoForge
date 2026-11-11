// Recette L35 : bandeau latéral repliable en icônes. Usage : node tools/recette/l35_sidebar.mjs   (BACKEND_PORT, FRONT_PORT optionnels ; front déjà buildé)
// Teste : repli / dépli (bouton, Ctrl+B), mémorisation, logo « mark », infobulles (survol, clavier, sans débordement), badge visible replié,
// repli automatique (éditeur, fichiers), préférence « toujours ouvert » respectée, réglage Paramètres › Affichage, mobile inchangé, anglais,
// prefers-reduced-motion, visite guidée (étape « nav » dans les deux modes), canevas redimensionné. Captures : journal/L35/screens/.
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
const SHOTS = path.join(ROOT, 'journal/L35/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8935, FP = process.env.FRONT_PORT || 4935
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const report = []
const log = (name, ok, detail = '') => { report.push(ok); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
const J = { 'content-type': 'application/json' }
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l35-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const pid = (await (await fetch(B + '/projects', { method: 'POST', headers: J, body: JSON.stringify({ name: 'bandeau', sample: 'automaint' }) })).json()).id
await fetch(`${B}/projects/${pid}/analyze?target=curiosity`, { method: 'POST' })

const browser = await chromium.launch()
async function session(vp, opts = {}) {
  const ctx = await browser.newContext({ viewport: vp, locale: opts.locale || 'fr-FR', reducedMotion: opts.reduced ? 'reduce' : 'no-preference' })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.setItem('ontoforge.ed.legend', 'closed') } catch {} })
  const page = await ctx.newPage(); const errs = []
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)) })
  return { ctx, page, errs }
}
const w = page => page.evaluate(() => Math.round(document.querySelector('.side').getBoundingClientRect().width))
const goto = async (page, h, wait = '.side nav button') => { await page.goto(`${base}/#/${h}`, { waitUntil: 'load' }); await page.reload({ waitUntil: 'load' }); await page.waitForSelector(wait, { timeout: 15000 }); await sleep(500) }
const shot = (page, n) => page.screenshot({ path: path.join(SHOTS, n + '.png') })
const pref = page => page.evaluate(() => { try { return localStorage.getItem('ontoforge.side') } catch { return 'ERR' } })
const T = `projet/${pid}/tableau`, E = `projet/${pid}/ontologie`, F = `projet/${pid}/fichiers`, A = `projet/${pid}/analyse`

// ---------------- 1. repli / dépli / mémorisation
const d = await session({ width: 1440, height: 900 }); const p = d.page
await goto(p, T)
log('1a ouvert par défaut (automatique)', (await w(p)) >= 220 && (await p.locator('.logo-word').count()) === 1 && (await pref(p)) === null, `largeur ${await w(p)}`)
await shot(p, '01-ouvert')
await p.getByTestId('side-toggle').click(); await sleep(450)
const wc = await w(p)
log('1b clic sur le bouton : replié ~56 px', wc >= 54 && wc <= 58, `largeur ${wc}`)
log('1c logo = tête de Krakie seule', (await p.locator('.side .logo.mark').count()) === 1 && (await p.locator('.logo-word').count()) === 0)
log('1d mémorisé (localStorage) puis après rechargement', (await pref(p)) === 'closed' && (await (async () => { await p.reload({ waitUntil: 'load' }); await p.waitForSelector('.side nav button'); await sleep(500); return w(p) })()) <= 58)
log('1e icônes centrées, libellés masqués', await p.evaluate(() => { const b = document.querySelector('.side nav button:not(.x)'); const i = b.querySelector('i').getBoundingClientRect(), r = b.getBoundingClientRect(); return Math.abs((i.left + i.width / 2) - (r.left + r.width / 2)) <= 1.5 && getComputedStyle(b.querySelector('.lbl')).opacity === '0' }))
log('1f pastilles 1 à 4 visibles et libellés des étapes absents', await p.evaluate(() => { const n = [...document.querySelectorAll('.step-title .num')]; return n.length === 4 && n.every((e, i) => e.textContent === String(i + 1) && e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().right < 56) }))
log('1g section Outils séparée par un trait', await p.evaluate(() => { const g = document.querySelector('.step-group.tools'); return !!g && getComputedStyle(g).borderTopWidth === '1px' }))
await shot(p, '02-replie')
await p.keyboard.press('Control+b'); await sleep(450)
log('1h Ctrl+B déplie', (await w(p)) >= 220 && (await pref(p)) === 'open', `pref ${await pref(p)}`)
await p.keyboard.press('Control+b'); await sleep(450)
log('1i Ctrl+B replie', (await w(p)) <= 58)
// Ctrl+B ignoré dans un champ de saisie
await goto(p, 'parametres', '.set-page'); await p.getByRole('tab', { name: 'Valeurs par défaut' }).click(); await p.locator('.set-page input').first().focus(); const w0 = await w(p), inField = await p.evaluate(() => document.activeElement.tagName === 'INPUT')
await p.keyboard.press('Control+b'); await sleep(300)
log('1j Ctrl+B ignoré dans un champ', (await w(p)) === w0 && inField)

// ---------------- 2. infobulles, aria, badge
await goto(p, A)
const an = p.locator('.side nav button[aria-current="page"]')
log('2a aria-current sur l\'élément actif + aria-label', (await an.count()) === 1 && /Analyse/.test(await an.getAttribute('aria-label')), await an.getAttribute('aria-label'))
const bg = await an.evaluate(e => getComputedStyle(e).backgroundColor), bg2 = await p.locator('.side nav button:not([aria-current])').first().evaluate(e => getComputedStyle(e).backgroundColor)
log('2b état actif distinct', bg !== bg2 && bg !== 'rgba(0, 0, 0, 0)', `${bg} / ${bg2}`)
await p.locator('.side nav button', { hasText: /Modèle cible/ }).hover(); await sleep(250)
const tip = await p.evaluate(() => { const t = document.querySelector('.side-tip'); if (!t) return null; const r = t.getBoundingClientRect(), b = [...document.querySelectorAll('.side nav button')].find(e => /Modèle cible/.test(e.getAttribute('aria-label'))).getBoundingClientRect(); return { text: t.textContent, left: r.left, right: r.right, top: r.top, bottom: r.bottom, bR: b.right, vw: innerWidth, vh: innerHeight, role: t.getAttribute('role') } })
log('2c infobulle au survol, à droite, sans débordement', !!tip && tip.text === 'Modèle cible' && tip.left >= tip.bR && tip.right <= tip.vw && tip.top >= 0 && tip.bottom <= tip.vh && tip.role === 'tooltip', JSON.stringify(tip))
await shot(p, '03-infobulle-survol')
await p.mouse.move(800, 400); await sleep(200)
log('2d infobulle retirée à la sortie', (await p.locator('.side-tip').count()) === 0)
await p.locator('.side nav button').first().focus(); await p.keyboard.press('Tab'); await p.keyboard.press('Tab'); await sleep(250)
log('2e infobulle au focus clavier', (await p.locator('.side-tip').count()) === 1, await p.locator('.side-tip').textContent().catch(() => ''))
await p.keyboard.press('Escape'); await sleep(150)
log('2f Échap ferme l\'infobulle', (await p.locator('.side-tip').count()) === 0)
await p.locator('.step-title .num').nth(2).hover(); await sleep(250)
log('2g infobulle d\'une pastille d\'étape', /Étape 3 : Transposer/.test(await p.locator('.side-tip').textContent().catch(() => '')), await p.locator('.side-tip').textContent().catch(() => ''))
// dernier bouton (bas du bandeau) : infobulle dans la fenêtre
await p.getByTestId('side-toggle').hover(); await sleep(250)
log('2h infobulle du bouton du bas dans la fenêtre', await p.evaluate(() => { const t = document.querySelector('.side-tip')?.getBoundingClientRect(); return !!t && t.bottom <= innerHeight && /Déplier/.test(document.querySelector('.side-tip').textContent) }))
await shot(p, '04-infobulle-bas')
await p.mouse.move(800, 400)
const bd = await p.evaluate(() => { const c = document.querySelector('.side .cnt'); if (!c) return null; const r = c.getBoundingClientRect(), a = document.querySelector('.side').getBoundingClientRect(), b = c.closest('button').getBoundingClientRect(); return { n: c.textContent, vis: r.width > 8 && r.height > 8, inside: r.left >= a.left && r.right <= a.right, onBtn: r.right <= b.right + 1 && r.top >= b.top - 1 && getComputedStyle(c).position === 'absolute' } })
log('2i badge d\'Analyse visible replié sur l\'icône', !!bd && Number(bd.n) > 0 && bd.vis && bd.inside && bd.onBtn, JSON.stringify(bd))
log('2j aria-label du badge', /\(\d+\)/.test(await p.locator('.side nav button', { has: p.locator('.cnt') }).getAttribute('aria-label')))
await shot(p, '05-replie-analyse-badge')

// ---------------- 3. repli automatique et préférence « ouvert »
await p.evaluate(() => localStorage.removeItem('ontoforge.side'))
await goto(p, T, '.side nav button')
log('3a automatique : tableau ouvert', (await w(p)) >= 220)
const canvasOpen = await (async () => { await goto(p, T); return 0 })()
await p.locator('.side nav button', { hasText: /^\s*Ontologie/ }).first().click()
await p.waitForSelector('.react-flow__node'); await sleep(900)
const wE = await w(p), cw = await p.evaluate(() => Math.round(document.querySelector('.of-canvas, .react-flow').getBoundingClientRect().width))
log('3b automatique : éditeur replié', wE <= 58, `bandeau ${wE}, canevas ${cw}`)
log('3c préférence non écrasée par le repli automatique', (await pref(p)) === null)
await shot(p, '06-editeur-replie-auto')
const fit = await p.evaluate(() => { const c = document.querySelector('.react-flow').getBoundingClientRect(); const ns = [...document.querySelectorAll('.react-flow__node')].map(n => n.getBoundingClientRect()); return { cw: c.width, inside: ns.filter(r => r.left >= c.left - 2 && r.right <= c.right + 2).length, total: ns.length, left: Math.min(...ns.map(r => r.left)) - c.left, right: c.right - Math.max(...ns.map(r => r.right)) } })
log('3d canevas redimensionné et graphe cadré', fit.inside >= fit.total * 0.9 && fit.left > -2 && fit.right > -2, JSON.stringify(fit))
await p.locator('.side nav button', { hasText: /^\s*Fichiers/ }).first().click(); await p.waitForSelector('.side nav button[aria-current="page"]'); await sleep(700)
log('3e automatique : Fichiers replié', (await w(p)) <= 58)
// déplier à la main sur l'éditeur = « toujours ouvert »
await p.getByTestId('side-toggle').click(); await sleep(450)
log('3f dépli manuel : ouvert et mémorisé « open »', (await w(p)) >= 220 && (await pref(p)) === 'open')
await goto(p, E, '.react-flow__node'); await sleep(600)
log('3g « toujours ouvert » respecté sur l\'éditeur', (await w(p)) >= 220, `largeur ${await w(p)}`)
await shot(p, '07-editeur-ouvert-explicite')
// réglage Paramètres › Affichage
await goto(p, 'parametres', '.set-page')
await p.getByRole('tab', { name: 'Affichage' }).click(); await sleep(300)
log('3h onglet Affichage : trois choix, « Ouvert » sélectionné', (await p.locator('.set-page .seg button').count()) === 3 && (await p.locator('.set-page .seg button[aria-pressed="true"]').textContent()) === 'Ouvert')
await shot(p, '08-parametres-affichage')
await p.locator('.set-page .seg button', { hasText: 'Automatique' }).click(); await sleep(200)
log('3i réglage « Automatique » : mémorisé', (await pref(p)) === 'auto')
await goto(p, E, '.react-flow__node'); await sleep(600)
log('3j de nouveau replié sur l\'éditeur', (await w(p)) <= 58)
await goto(p, 'parametres', '.set-page'); await p.getByRole('tab', { name: 'Affichage' }).click()
await p.locator('.set-page .seg button', { hasText: 'Replié' }).click(); await sleep(450)
log('3k réglage « Replié » : replié sur Paramètres', (await w(p)) <= 58 && (await pref(p)) === 'closed')
await goto(p, '', 'main'); log('3l replié aussi sur la liste des projets', (await w(p)) <= 58)

// ---------------- 4. visite guidée dans les deux modes
const tourNav = async mode => {
  await p.evaluate(m => localStorage.setItem('ontoforge.side', m), mode)
  await goto(p, T)
  await p.evaluate(() => window.ontoforgeTour.start({ demo: false })); await sleep(700)
  await p.evaluate(() => window.ontoforgeTour.next())
  for (let k = 0; k < 40; k++) { const s = await p.evaluate(() => window.ontoforgeTour.state()); if (s.ready && s.index === 1) break; await sleep(120) }
  await sleep(600)
  const g = await p.evaluate(() => { const h = document.querySelector('.tour-hole')?.getBoundingClientRect(), n = document.querySelector('[data-tour="nav"]').getBoundingClientRect(), b = document.querySelector('[data-tour-bubble]')?.getBoundingClientRect(); return { hole: h && { l: h.left, w: h.width }, nav: { l: n.left, w: n.width }, bubbleL: b?.left } })
  await shot(p, mode === 'closed' ? '09-visite-replie' : '10-visite-ouvert')
  await p.evaluate(() => window.ontoforgeTour.stop()); await sleep(300)
  return g
}
for (const mode of ['open', 'closed']) {
  const g = await tourNav(mode)
  log(`4 visite, étape « nav » (${mode})`, !!g.hole && Math.abs(g.hole.w - g.nav.w) <= 14 && g.bubbleL >= g.nav.l + g.nav.w - 2, JSON.stringify(g))
}

// ---------------- 5. prefers-reduced-motion
const r = await session({ width: 1440, height: 900 }, { reduced: true }); await goto(r.page, T)
await r.page.getByTestId('side-toggle').click(); await sleep(150)
log('5 reduced-motion : aucune transition, replié aussitôt', (await r.page.evaluate(() => getComputedStyle(document.querySelector('.shell')).transitionDuration)) === '0s' && (await w(r.page)) <= 58)
await r.ctx.close()

// ---------------- 6. mobile inchangé
const m = await session({ width: 390, height: 844 })
await m.page.addInitScript(() => { try { localStorage.setItem('ontoforge.side', 'closed') } catch {} })
await goto(m.page, T, '.menu-btn')
const mob = await m.page.evaluate(() => ({ toggle: !!document.querySelector('.side-toggle'), side: document.querySelector('.side').getBoundingClientRect(), h: document.documentElement.scrollWidth > innerWidth + 2, cls: document.querySelector('.shell').className }))
log('6a mobile : pas de bouton de repli, tiroir hors écran, pas de classe collapsed', !mob.toggle && mob.side.right <= 1 && !mob.h && !/collapsed/.test(mob.cls), JSON.stringify(mob))
await m.page.locator('.menu-btn').click(); await sleep(400)
log('6b mobile : tiroir ouvert avec libellés et logo complet', await m.page.evaluate(() => { const s = document.querySelector('.side').getBoundingClientRect(); const l = document.querySelector('.side .lbl'); return s.left >= -1 && s.width > 240 && getComputedStyle(l).opacity === '1' && !!document.querySelector('.side .logo-word') }))
await shot(m.page, '11-mobile-tiroir')
log('6c mobile : pas d\'infobulle', (await m.page.locator('.side-tip').count()) === 0)
await m.ctx.close()

// ---------------- 7. anglais
await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'en', labels: 'en', assistant: 'en' } }) })
const en = await session({ width: 1440, height: 900 }, { locale: 'en-GB' })
await en.page.addInitScript(() => { try { localStorage.setItem('ontoforge.side', 'closed') } catch {} })
await goto(en.page, A); await sleep(300)
await en.page.locator('.side nav button[aria-current="page"]').hover(); await sleep(250)
const et = await en.page.locator('.side-tip').textContent().catch(() => '')
log('7a anglais : infobulle traduite', /^Analysis & decisions \(\d+\)$/.test(et), et)
await en.page.locator('.step-title .num').first().hover(); await sleep(250)
log('7b anglais : pastille d\'étape', (await en.page.locator('.side-tip').textContent()) === 'Step 1: Design', await en.page.locator('.side-tip').textContent())
await en.page.getByTestId('side-toggle').hover(); await sleep(250)
log('7c anglais : bouton Expand', /^Expand the sidebar \(Ctrl\+B\)$/.test(await en.page.locator('.side-tip').textContent()))
await shot(en.page, '12-replie-en')
await goto(en.page, 'parametres', '.set-page'); await en.page.getByRole('tab', { name: 'Display' }).click(); await sleep(300)
log('7d anglais : réglage Display', (await en.page.locator('.set-page .seg button').allTextContents()).join('|') === 'Automatic|Open|Collapsed')
await shot(en.page, '13-parametres-display-en')
await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'fr', labels: 'fr', assistant: 'fr' } }) })

// ---------------- erreurs
const errs = [...d.errs, ...m.errs, ...en.errs].filter(e => !/favicon/.test(e))
log('8 aucune erreur de console ni exception', errs.length === 0, JSON.stringify(errs.slice(0, 3)))
await browser.close(); procs.forEach(x => x.kill())
const ko = report.filter(x => !x).length
console.log(`\n=== L35 : ${report.length - ko} OK / ${ko} KO`); process.exit(ko ? 1 : 0)
