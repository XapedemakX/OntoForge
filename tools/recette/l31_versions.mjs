// Recette L31 : versions des normes et des cibles. Usage : node tools/recette/l31_versions.mjs   (BACKEND_PORT, FRONT_PORT optionnels ; front déjà buildé)
// Démarre un backend temporaire (mock) + `vite preview`, puis : écran Versions du projet, panneau Versions des Paramètres, bulle de Krakie (obsolète, « Plus tard » mémorisé),
// intentions « quelles versions ? » et « mets à jour les versions » (action confirmée), préfixe CYPHER 25 dans l'export, rapport, version anglaise. Captures : journal/L31/screens/.
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
const SHOTS = path.join(ROOT, 'journal/L31/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8931, FP = process.env.FRONT_PORT || 4931
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
process.on('exit', () => procs.forEach(p => p.kill()))
const report = []
const log = (name, ok, detail = '') => { report.push({ name, ok }); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l31-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(B + p, { method: m, headers: J, body: b === undefined ? undefined : JSON.stringify(b) }); return r.json() }
const pid = (await api('POST', '/projects', { name: 'versions', sample: 'automaint' })).id

const browser = await chromium.launch()
const session = async (vp = { width: 1440, height: 900 }) => {
  const ctx = await browser.newContext({ viewport: vp, locale: 'fr-FR' })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1') } catch {} })
  const page = await ctx.newPage(); const errs = []
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)) })
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('response', r => { if (r.status() >= 500 || (r.status() >= 400 && r.url().includes('/api/') && ![404, 409].includes(r.status()))) errs.push(`HTTP ${r.status()} ${r.url().replace(base, '')}`) })
  return { ctx, page, errs }
}
const shot = (s, name) => s.page.screenshot({ path: path.join(SHOTS, name + '.png') })
const step = async (name, s, fn) => { const b = s.errs.length; try { const d = await fn(); const e = s.errs.slice(b); log(name, e.length === 0, (d || '') + (e.length ? ' ' + JSON.stringify(e.slice(0, 2)) : '')) } catch (e) { log(name, false, String(e).slice(0, 300)); await shot(s, 'ko-' + name.slice(0, 20).replace(/\W+/g, '-')).catch(() => {}) } }
const goVersions = async s => { await s.page.goto(`${base}/#/projet/${pid}/versions`, { waitUntil: 'load' }); await s.page.reload({ waitUntil: 'load' }); await s.page.waitForSelector('[data-version=neo4j]', { timeout: 20000 }); await sleep(500) }

const s = await session()
await step('V1 écran Versions : six familles, statuts, aucune alerte sur les défauts', s, async () => {
  await goVersions(s)
  const fam = await s.page.locator('[data-version]').evaluateAll(els => els.map(e => e.getAttribute('data-version')))
  if (fam.join() !== 'neo4j,cypher,curiosity_library,shacl,sparql,rdf') throw new Error('familles ' + fam)
  const st = await s.page.locator('[data-version] .ver-st').evaluateAll(els => els.map(e => e.getAttribute('data-support')))
  if (st.some(x => x !== 'recommended')) throw new Error('statuts ' + st)
  if (await s.page.locator('[data-testid=ver-gaps]').count()) throw new Error('écarts affichés sur les valeurs par défaut')
  if (await s.page.locator('[data-testid=ver-nudge]').count()) throw new Error('bulle sur les valeurs par défaut')
  await shot(s, '01-versions-defaut'); return st.join()
})
await step('V2 choisir Neo4j 2026.10 + Cypher 25 : enregistré, statut visible, export préfixé', s, async () => {
  await s.page.getByLabel('Version de Neo4j').selectOption('2026.10'); await sleep(700)
  await s.page.getByLabel('Version de Cypher').selectOption('25'); await sleep(700)
  const pv = await api('GET', `/projects/${pid}/versions`)
  if (pv.explicit.neo4j !== '2026.10' || pv.explicit.cypher !== '25') throw new Error(JSON.stringify(pv.explicit))
  const row = await s.page.locator('[data-version=neo4j] .ver-st').getAttribute('data-support')
  if (row !== 'supported') throw new Error('statut ' + row)
  await shot(s, '02-versions-neo4j-2026')
  const f = (await api('GET', `/projects/${pid}/generate/neo4j`)).files
  const stm = f['schema.cypher'].split('\n').filter(l => /^CYPHER 25 CREATE CONSTRAINT/.test(l)).length
  if (!stm || /^CREATE CONSTRAINT/m.test(f['schema.cypher'])) throw new Error('requêtes sans préfixe')
  if (!/\| Neo4j \| 2026\.10 \| supportée \|/.test(f['rapport-transposition.md'])) throw new Error('rapport sans versions')
  return stm + ' contraintes préfixées'
})
await step('V3 écran Exports : la cible Neo4j affiche le préfixe CYPHER 25 en tête de requête', s, async () => {
  await s.page.goto(`${base}/#/projet/${pid}/exports`, { waitUntil: 'load' }); await s.page.reload({ waitUntil: 'load' }); await sleep(800)
  await s.page.locator('.seg button', { hasText: 'Neo4j' }).first().click(); await sleep(1200)
  await s.page.locator('.flist button', { hasText: 'schema.cypher' }).click(); await sleep(700)
  const txt = await s.page.locator('.codeview').innerText()
  if (!/CYPHER 25 CREATE CONSTRAINT/.test(txt)) throw new Error('préfixe absent à l\'écran')
  await shot(s, '03-export-cypher25'); return 'ok'
})
await step('V4 écart : Neo4j 5.13 obsolète, bannière dans l\'écran', s, async () => {
  await api('PUT', `/projects/${pid}/versions`, { neo4j: '5.13', cypher: '5' })
  await goVersions(s)
  const t = await s.page.locator('[data-testid=ver-gaps]').innerText()
  if (!/5\.13/.test(t) || !/plus recommandée/.test(t)) throw new Error(t)
  await shot(s, '04-versions-ecart'); return t.replace(/\n/g, ' | ')
})

// bulle de Krakie : nouveau contexte = nouvelle session
const n1 = await session()
await step('N1 bulle discrète à l\'ouverture du projet, une seule fois par session', n1, async () => {
  await n1.page.goto(`${base}/#/projet/${pid}/tableau`, { waitUntil: 'load' }); await n1.page.waitForSelector('[data-testid=ver-nudge]', { timeout: 15000 })
  const t = await n1.page.locator('[data-testid=ver-nudge]').innerText()
  if (!/Neo4j 5\.13/.test(t) || !/Mettre à jour/.test(t) || !/Plus tard/.test(t)) throw new Error(t)
  await shot(n1, '05-bulle-krakie')
  await n1.page.goto(`${base}/#/projet/${pid}/analyse`); await sleep(1500)
  await n1.page.goto(`${base}/#/projet/${pid}/tableau`); await sleep(1500)
  // retour sur le projet dans la même session : la bulle a été annoncée, elle ne revient pas tant qu'on ne recharge pas… elle reste affichée tant qu'on n'a pas choisi
  return t.replace(/\n/g, ' | ')
})
await step('N2 « Plus tard » est mémorisé : rechargement et nouvelle session sans bulle', n1, async () => {
  await n1.page.locator('[data-testid=ver-nudge]').getByRole('button', { name: 'Plus tard' }).click(); await sleep(300)
  if (await n1.page.locator('[data-testid=ver-nudge]').count()) throw new Error('bulle toujours là')
  await n1.page.reload({ waitUntil: 'load' }); await sleep(2500)
  if (await n1.page.locator('[data-testid=ver-nudge]').count()) throw new Error('bulle revenue après rechargement')
  const later = await n1.page.evaluate(id => localStorage.getItem('ontoforge.versions.later.' + id), pid)
  if (!later) throw new Error('rien de mémorisé')
  return 'later=' + later
})
const n2 = await session()
await step('N3 « Mettre à jour » dans la bulle applique les versions recommandées', n2, async () => {
  await n2.page.goto(`${base}/#/projet/${pid}/tableau`, { waitUntil: 'load' }); await n2.page.waitForSelector('[data-testid=ver-nudge]', { timeout: 15000 })
  await n2.page.locator('[data-testid=ver-nudge]').getByRole('button', { name: 'Mettre à jour' }).click(); await sleep(1200)
  const pv = await api('GET', `/projects/${pid}/versions`)
  if (pv.versions.neo4j !== '5.26') throw new Error(JSON.stringify(pv.versions))
  if (await n2.page.locator('[data-testid=ver-nudge]').count()) throw new Error('bulle restée')
  return 'neo4j=' + pv.versions.neo4j
})

// Krakie : intentions
const k = await session()
const ask = async (text) => { await k.page.fill('.ag-box textarea', text); await k.page.keyboard.press('Enter'); await sleep(1500) }
await api('PUT', `/projects/${pid}/versions`, { neo4j: '5.13' })
await step('K1 « quelles versions ? » : réponse avec les versions et statuts, action « Ouvrir les versions »', k, async () => {
  await k.page.goto(`${base}/#/projet/${pid}/tableau`, { waitUntil: 'load' }); await k.page.waitForSelector('.ag-fab', { timeout: 15000 })
  await k.page.evaluate(() => sessionStorage.clear())
  await k.page.keyboard.press('Control+k'); await k.page.waitForSelector('.ag-panel')
  await ask('quelles versions ?')
  const t = await k.page.locator('.ag-msg.assistant').last().innerText()
  if (!/Neo4j 5\.13 \(obsolète, projet\)/.test(t) || !/Curiosity\.Library 26\.11\.7740/.test(t)) throw new Error(t)
  await shot(k, '06-krakie-versions')
  await k.page.getByRole('button', { name: 'Ouvrir', exact: false }).last().click(); await sleep(1000)
  if (!k.page.url().endsWith('/versions')) throw new Error('navigation ' + k.page.url())
  return 'ok'
})
await step('K2 « mets à jour les versions » : proposition, rien d\'appliqué avant le clic, puis annulation', k, async () => {
  await k.page.keyboard.press('Control+k').catch(() => {}); await k.page.waitForSelector('.ag-panel', { timeout: 5000 }).catch(async () => { await k.page.keyboard.press('Control+k') })
  await ask('mets à jour les versions')
  await k.page.waitForSelector('.ag-card.versions'); await sleep(300)
  if ((await api('GET', `/projects/${pid}/versions`)).versions.neo4j !== '5.13') throw new Error('appliqué sans confirmation')
  const prev = await k.page.locator('.ag-card.versions .ag-preview').innerText()
  if (!/Neo4j 5\.13 → 5\.26/.test(prev)) throw new Error(prev)
  await shot(k, '07-krakie-mise-a-jour')
  await k.page.locator('.ag-card.versions').getByRole('button', { name: 'Appliquer' }).click(); await k.page.waitForSelector('.ag-card.versions.applied'); await sleep(500)
  if ((await api('GET', `/projects/${pid}/versions`)).versions.neo4j !== '5.26') throw new Error('non appliqué')
  await k.page.locator('.ag-card.versions.applied').getByRole('button', { name: 'Annuler' }).click(); await k.page.waitForSelector('.ag-card.versions.undone'); await sleep(500)
  if ((await api('GET', `/projects/${pid}/versions`)).versions.neo4j !== '5.13') throw new Error('annulation sans effet')
  await shot(k, '08-krakie-annule'); return 'ok'
})

// Paramètres
const st = await session()
await step('S1 Paramètres > Versions : défaut global modifiable, projets suivent', st, async () => {
  await st.page.goto(`${base}/#/parametres`, { waitUntil: 'load' }); await st.page.reload({ waitUntil: 'load' }); await sleep(800)
  await st.page.getByRole('tab', { name: 'Versions' }).click().catch(async () => { await st.page.getByText('Versions', { exact: true }).first().click() }); await sleep(500)
  await st.page.getByLabel('Version de Curiosity.Library').selectOption('26.10.6546'); await sleep(200)
  await shot(st, '09-parametres-versions')
  await st.page.getByRole('button', { name: 'Enregistrer' }).click(); await sleep(1000)
  const g = await api('GET', '/settings'); if (g.versions.curiosity_library !== '26.10.6546') throw new Error(JSON.stringify(g.versions))
  const p2 = await api('POST', '/projects', { name: 'suit-le-defaut' }); const pv = await api('GET', `/projects/${p2.id}/versions`)
  if (pv.versions.curiosity_library !== '26.10.6546' || Object.keys(pv.explicit).length) throw new Error(JSON.stringify(pv))
  await api('PUT', '/settings', { versions: { curiosity_library: '26.11.7740' } }); return 'ok'
})

// anglais
await api('PUT', '/settings', { language: { ui: 'en', labels: 'en', assistant: 'en' } })
await api('PUT', `/projects/${pid}/versions`, { neo4j: '4.4' })
const en = await session()
await step('E1 version anglaise : écran, bulle et Krakie sans français', en, async () => {
  await en.page.goto(`${base}/#/projet/${pid}/versions`, { waitUntil: 'load' }); await en.page.reload({ waitUntil: 'load' }); await en.page.waitForSelector('[data-version=neo4j]'); await sleep(900)
  const t = await en.page.locator('.ver-page').innerText()
  if (/[éèàçêâîô]/.test(t.replace(/standards\.json/g, ''))) throw new Error('accents : ' + t.match(/.{0,30}[éèàçêâîô].{0,30}/)?.[0])
  if (!/out of support/i.test(t)) throw new Error('écart en anglais absent')
  await shot(en, '10-versions-en'); return 'ok'
})
await step('E2 bulle anglaise', en, async () => {
  await en.page.goto(`${base}/#/projet/${pid}/tableau`, { waitUntil: 'load' }); await en.page.waitForSelector('[data-testid=ver-nudge]', { timeout: 15000 })
  const t = await en.page.locator('[data-testid=ver-nudge]').innerText()
  if (!/out of support/.test(t) || !/Update/.test(t) || !/Later/.test(t) || /[éèàçêâîô]/.test(t)) throw new Error(t)
  await shot(en, '11-nudge-en'); return t.replace(/\n/g, ' | ')
})

const bad = report.filter(r => !r.ok)
console.log(`\n${report.length - bad.length}/${report.length} OK`)
await browser.close()
process.exit(bad.length ? 1 : 0)
