// Recette L36b : écran « Carte métier ». Usage : node tools/recette/l36_business_map.mjs   (BACKEND_PORT, FRONT_PORT optionnels ; front déjà buildé)
// Teste : rendu (zones, nœuds, arêtes, légende), survol, épinglage persistant, proposition de zones, scénario (style, notes),
// export SVG valide, mode sombre, anglais, mobile en lecture seule. Données : samples/automaint. Captures : journal/L36/screens/.
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L36/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8996, FP = process.env.FRONT_PORT || 4996
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const report = []
const log = (name, ok, detail = '') => { report.push(ok); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`, J = { 'content-type': 'application/json' }
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l36-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const pid = (await (await fetch(B + '/projects', { method: 'POST', headers: J, body: JSON.stringify({ name: 'carte', sample: 'automaint' }) })).json()).id
const getMap = async (src = 'ontology') => (await fetch(`${B}/projects/${pid}/business-map?source=${src}`)).json()

const browser = await chromium.launch()
async function session(vp, opts = {}) {
  const ctx = await browser.newContext({ viewport: vp, locale: opts.locale || 'fr-FR', colorScheme: opts.dark ? 'dark' : 'light', acceptDownloads: true })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.removeItem('ontoforge.bmap.source') } catch {} })
  const page = await ctx.newPage(); const errs = []
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)) })
  return { ctx, page, errs }
}
const open = async page => { await page.goto(`${base}/#/projet/${pid}/carte-metier`, { waitUntil: 'load' }); await page.reload({ waitUntil: 'load' }); await page.waitForSelector('[data-testid=bm-svg] .bm-n', { timeout: 20000 }); await sleep(600) }
const shot = (page, n) => page.screenshot({ path: path.join(SHOTS, n + '.png') })

// ---------------- 1. rendu
const d = await session({ width: 1600, height: 1000 }); const p = d.page
await open(p)
const m0 = await getMap()
const cnt = await p.evaluate(() => ({ n: document.querySelectorAll('[data-testid=bm-svg] [data-n]').length, z: document.querySelectorAll('[data-testid=bm-svg] [data-zone]').length, e: new Set([...document.querySelectorAll('[data-testid=bm-svg] [data-e]')].map(x => x.getAttribute('data-e'))).size, txt: document.querySelector('[data-testid=bm-svg]').textContent }))
log('1a nœuds dessinés = types du schéma', cnt.n === m0.nodes.length && cnt.n > 5, `${cnt.n}/${m0.nodes.length}`)
log('1b zones visibles avec titre', cnt.z === m0.zones.length && m0.zones.every(z => cnt.txt.includes(z.title)), `${cnt.z} zones`)
log('1c arêtes dessinées (une par relation)', cnt.e >= m0.edges.filter(e => !e.loop).length - 1, `${cnt.e}/${m0.edges.length}`)
log('1d légende et sous-titre (date, nombre de types)', cnt.txt.includes('Légende') && cnt.txt.includes(String(m0.meta.n_types) + ' types') && cnt.txt.includes(m0.meta.title))
log('1f bandeau « carte proposée automatiquement » (meta.generated)', await p.getByTestId('bm-generated').count() === 1 && m0.meta.generated === true)
log('1e en-tête de la page : sélecteur de source et lien Modèle cible', await p.getByRole('button', { name: 'Modèle cible' }).count() >= 1)
await shot(p, '01-carte-claire')

// ---------------- 2. survol
const firstNode = p.locator('[data-testid=bm-svg] [data-n]').nth(3)
await firstNode.hover(); await sleep(250)
const hv = await p.evaluate(() => ({ dim: document.querySelector('[data-testid=bm-svg]').classList.contains('bm-dim'), on: document.querySelectorAll('[data-testid=bm-svg] .bm-on').length, total: document.querySelectorAll('[data-testid=bm-svg] [data-n]').length }))
log('2a survol : le reste est atténué, les arêtes du nœud en surbrillance', hv.dim && hv.on >= 1 && hv.on < hv.total + 40, JSON.stringify(hv))
await shot(p, '02-survol')
await p.mouse.move(5, 500); await sleep(200)
log('2b la sortie rétablit tout', !(await p.evaluate(() => document.querySelector('[data-testid=bm-svg]').classList.contains('bm-dim'))))

// ---------------- 3. clic -> inspecteur, rôle, estompé
await firstNode.click(); await sleep(300)
log('3a clic : inspecteur du type', await p.getByTestId('bm-insp-node').count() === 1)
const nid = await p.evaluate(() => document.querySelector('[data-testid=bm-svg] .bm-sel')?.getAttribute('data-n'))
await p.getByTestId('bm-role').selectOption({ index: 2 }); await sleep(600)
const role = await p.getByTestId('bm-role').inputValue()
await p.getByTestId('bm-faded').check(); await sleep(700)
const mf = await getMap(); const nf = mf.nodes.find(n => n.id === nid)
log('3b rôle et estompé enregistrés côté serveur', nf?.faded === true && nf?.role === role, `${nf?.role}/${nf?.faded}`)
await shot(p, '03-inspecteur')
await p.getByTestId('bm-faded').uncheck(); await sleep(600)

// ---------------- 4. glisser : épinglage persistant
const box = await p.locator(`[data-testid=bm-svg] [data-n] circle.bm-c`).nth(5).boundingBox()
const nid5 = await p.locator('[data-testid=bm-svg] [data-n]').nth(5).getAttribute('data-n')
const before = (await getMap()).nodes.find(n => n.id === nid5)
await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await p.mouse.down(); await p.mouse.move(box.x + box.width / 2 + 25, box.y + box.height / 2 + 18, { steps: 6 }); await p.mouse.up(); await sleep(900)
const after = (await getMap()).nodes.find(n => n.id === nid5)
log('4a nœud glissé : position changée et épinglé', after.pinned === true && (Math.abs(after.x - before.x) > 3 || Math.abs(after.y - before.y) > 3), `${before.x},${before.y} -> ${after.x},${after.y}`)
await p.reload({ waitUntil: 'load' }); await p.waitForSelector('[data-testid=bm-svg] .bm-n'); await sleep(500)
log('4b épinglage conservé après rechargement (point sur le nœud) et bandeau « proposée automatiquement » retiré', await p.locator('[data-testid=bm-svg] .bm-pin').count() >= 1 && (await p.getByTestId('bm-generated').count()) === 0)

// ---------------- 5. zones : proposition et glisser-déposer
await p.getByRole('tab', { name: /^Zones/ }).click(); await sleep(300)
const zonesBefore = (await getMap()).zones.map(z => z.title).join('|')
await p.getByTestId('bm-strategy').selectOption('namespace')
await p.getByTestId('bm-suggest-zones').click(); await p.waitForSelector('[data-testid=bm-preview]'); await sleep(300)
log('5a0 aperçu sans rien enregistrer', (await getMap()).zones.map(z => z.title).join('|') === zonesBefore)
await p.getByTestId('bm-preview-apply').click(); await sleep(2500)
const mz = await getMap()
log('5a « Proposer des zones » (espaces de noms) applique des zones', mz.zones.length >= 1 && (await p.getByTestId('bm-zone').count()) >= mz.zones.length, `${mz.zones.map(z => z.title).join(', ')}`)
await p.getByTestId('bm-undo').click(); await sleep(1500)
log('5b annuler restaure les zones précédentes', (await getMap()).zones.map(z => z.title).join('|') === zonesBefore)
await p.getByTestId('bm-add-zone').click(); await sleep(900)
log('5c ajouter une zone (visible dans le panneau, y compris vide)', await p.locator('[data-testid=bm-zone]').count() >= zonesBefore.split('|').length + 1)
const ez = (await getMap()).zones.find(z => z.members.length === 0 && z.title === 'Nouvelle zone')
log('5c2 la zone vide est conservée par le serveur (GET) avec un rectangle', !!ez && ez.rect.w > 0 && ez.rect.h > 0, JSON.stringify(ez?.rect))
const fresh = await session({ width: 1600, height: 1000 }); await open(fresh.page)
log('5c3 la zone vide survit à un rechargement de page (dessinée dans la carte)', !!ez && await fresh.page.locator(`[data-testid=bm-svg] [data-zone="${ez.id}"]`).count() === 1)
await fresh.ctx.close()
// glisser une classe vers la zone ajoutée
const target = p.locator('[data-testid=bm-zone]:not([data-zone=none])').last()
const chip = p.locator('.bm-cls').first(); const chipId = await chip.getAttribute('data-node')
await chip.dragTo(target); await sleep(1200)
const mm = await getMap(); const moved = mm.nodes.find(n => n.id === chipId)
log('5d glisser une classe dans une autre zone', mm.zones.find(z => z.id === moved.zone)?.title === 'Nouvelle zone', `${moved.zone}`)
await shot(p, '04-zones')
await p.getByTestId('bm-undo').click(); await sleep(700); await p.getByTestId('bm-undo').click(); await sleep(900)

// ---------------- 6. scénario
await p.getByRole('tab', { name: /^Scénarios/ }).click(); await sleep(300)
await p.getByTestId('bm-sc-name').fill('Lecture atelier'); await p.getByTestId('bm-sc-add').click(); await sleep(800)
await p.getByTestId('bm-sc-notes').fill('# Lecture\n- première relation mise en avant\n**À vérifier avec le métier**'); await sleep(500)
const edge = p.locator('.bm-edgelist select').first(); await edge.selectOption('scored'); await sleep(900)
const ms = await getMap(); const sc = ms.scenarios[0]
log('6a scénario créé avec notes et style d\'arête enregistrés', sc?.name === 'Lecture atelier' && Object.values(sc.edge_styles).includes('scored') && sc.description.includes('Lecture'))
const scored = await p.evaluate(() => [...document.querySelectorAll('[data-testid=bm-svg] [data-e] path:not(.bm-hit)')].some(x => x.getAttribute('stroke') === '#dd6b20' && parseFloat(x.getAttribute('stroke-width')) > 3))
log('6b le style « scored » s\'affiche (orange épais) et les notes sous la légende', scored && (await p.evaluate(() => document.querySelector('[data-testid=bm-svg]').textContent)).includes('À vérifier avec le métier'))
await p.getByRole('tab', { name: /^Inspecteur/ }).click()
await p.locator('[data-testid=bm-svg] [data-e].bm-lab').first().click({ force: true }).catch(() => {}); await sleep(300)
await shot(p, '05-scenario')

// ---------------- 7. export SVG
await p.getByTestId('bm-export').click()
const [dl] = await Promise.all([p.waitForEvent('download'), p.getByTestId('bm-exp-svg').click()])
const f = await dl.path(); const svg = readFileSync(f, 'utf8')
const okXml = await p.evaluate(s => { const x = new DOMParser().parseFromString(s, 'image/svg+xml'); return !x.querySelector('parsererror') && x.documentElement.tagName === 'svg' }, svg)
log('7a export SVG : document valide avec légende, notes et sans interaction', okXml && svg.includes('Légende') && svg.includes('À vérifier avec le métier') && !svg.includes('data-n=') && !svg.includes('var(--'), `${svg.length} octets`)
await p.getByTestId('bm-export').click()
const [dl2] = await Promise.all([p.waitForEvent('download'), p.getByTestId('bm-exp-png2').click()])
const png = readFileSync(await dl2.path()); log('7b export PNG ×2 : fichier PNG non vide', png.slice(1, 4).toString() === 'PNG' && png.length > 20000, `${png.length} octets`)
await p.getByTestId('bm-export').click()
const [dl4] = await Promise.all([p.waitForEvent('download'), p.getByTestId('bm-exp-png4').click()])
const png4 = readFileSync(await dl4.path()); log('7c export PNG ×4 plus lourd que ×2', png4.slice(1, 4).toString() === 'PNG' && png4.length > png.length, `${png4.length} octets`)

// ---------------- 8. modèle cible, raccourci
// l'écran Modèle attend la fin de l'analyse (api.analyze) : on la lance côté API et on attend sa fin (sans plafond court), puis l'écran
const t0 = Date.now(); const tgt = await getMap('target'); log('8.0 analyse du modèle cible terminée (source « target »)', tgt.source === 'target' && tgt.nodes.length > 0, `${Date.now() - t0} ms`)
await p.goto(`${base}/#/projet/${pid}/modele`); await p.waitForSelector('[data-testid=mo-bmap]', { state: 'visible', timeout: 120000 })
await p.getByTestId('mo-bmap').click(); await p.waitForSelector('[data-testid=bm-svg] .bm-n', { timeout: 20000 }); await sleep(500)
log('8a raccourci du modèle cible : source « Modèle cible » active', await p.getByRole('button', { name: 'Modèle cible', pressed: true }).count() === 1)
await shot(p, '06-modele-cible')
log('8b aucune erreur console (desktop)', d.errs.length === 0, d.errs.join(' | '))
await d.ctx.close()

// ---------------- 9. sombre
const k = await session({ width: 1600, height: 1000 }, { dark: true }); await open(k.page)
const bg = await k.page.evaluate(() => getComputedStyle(document.querySelector('[data-testid=bm-svg]')).backgroundColor)
log('9 thème sombre : fond de la carte sombre', /rgb\(1[0-9]?, /.test(bg) || bg.startsWith('rgb(14'), bg)
await shot(k.page, '07-carte-sombre'); await k.ctx.close()

// ---------------- 10. anglais
await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'en', labels: 'en', assistant: 'en' } }) })
const e = await session({ width: 1600, height: 1000 }, { locale: 'en-US' }); await open(e.page)
const txt = await e.page.evaluate(() => document.querySelector('.bm').innerText + document.querySelector('[data-testid=bm-svg]').textContent)
log('10 anglais : libellés traduits', txt.includes('Business map') && txt.includes('Legend') && txt.includes('Suggest frames') && !/Légende|Proposer|Réorganiser/.test(txt))
await shot(e.page, '08-carte-en'); await e.ctx.close()
await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'fr', labels: 'fr', assistant: 'fr' } }) })

// ---------------- 11. mobile : lecture seule
const mo = await session({ width: 390, height: 800 }); await open(mo.page)
const ro = await mo.page.evaluate(() => ({ ro: document.querySelector('[data-testid=bmap]').dataset.readonly, layout: !!document.querySelector('[data-testid=bm-layout]'), over: document.documentElement.scrollWidth > innerWidth + 2 }))
log('11 mobile : lecture seule, pas de boutons d\'édition, pas de débordement', ro.ro === '1' && !ro.layout && !ro.over, JSON.stringify(ro))
const pct0 = parseInt(await mo.page.locator('.bm-pct').innerText())
log('11b mobile : ouverture sur un zoom lisible (45 % au moins)', pct0 >= 45, `${pct0} %`)
await mo.page.getByTestId('bm-fit').click(); await sleep(200)
const pct1 = parseInt(await mo.page.locator('.bm-pct').innerText())
log('11c mobile : « Tout voir » ajuste toute la carte (zoom plus petit)', pct1 < pct0, `${pct1} %`)
await mo.page.getByTestId('bm-fit').click(); await sleep(100)
await shot(mo.page, '09-mobile-tout'); await mo.page.reload({ waitUntil: 'load' }); await mo.page.waitForSelector('[data-testid=bm-svg] .bm-n', { timeout: 20000 }); await sleep(400)
await shot(mo.page, '09-mobile'); await mo.ctx.close()

await browser.close(); procs.forEach(p => p.kill())
const ko = report.filter(x => !x).length
console.log(`\n${report.length - ko}/${report.length} OK`); process.exit(ko ? 1 : 0)
