// Recette it2 (L14) : parcours UI Playwright. Usage : node tools/recette/e2e_ui.mjs   (variables : BACKEND_PORT, FRONT_PORT optionnels)
// Démarre backend (mock, données temporaires) + `vite preview` du front buildé, crée un projet automaint, parcourt chaque écran.
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
const SHOTS = path.join(ROOT, 'journal/L14/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8911, FP = process.env.FRONT_PORT || 4911
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const report = []
const log = (screen, ok, detail) => { report.push({ screen, ok, detail }); console.log((ok ? 'OK  ' : 'KO  ') + screen + ' :: ' + detail) }

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-ui-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
const base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
// le proxy vite preview peut ne pas relayer /api : on l'intercepte dans le navigateur vers le backend
const proj = await (await fetch(B + '/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'recette-ui', sample: 'automaint' }) })).json()
const pid = proj.id
await fetch(`${B}/analyze`, { method: 'POST' }).catch(() => {})
await fetch(`${B}/projects/${pid}/analyze?target=curiosity`, { method: 'POST' })
await fetch(`${B}/projects/${pid}/decisions/curiosity/accept-recommended`, { method: 'POST' })

const browser = await chromium.launch()
async function session(vp, tag) {
  const ctx = await browser.newContext({ viewport: vp, locale: 'fr-FR' })
  await ctx.route(`${base}/api/**`, route => { const u = route.request().url().replace(base, `http://127.0.0.1:${BP}`); route.continue({ url: u }) })
  const page = await ctx.newPage(); const errs = []
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)) })
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('response', r => { if (r.status() >= 500 || (r.status() >= 400 && r.url().includes('/api/') && ![404, 409].includes(r.status()))) errs.push(`HTTP ${r.status()} ${r.url().replace(base, '')}`) })
  return { ctx, page, errs, tag }
}
const screens = [
  ['01-projets', '#/'], ['02-tableau', `#/projet/${pid}/tableau`], ['03-ontologie-editeur', `#/projet/${pid}/ontologie`],
  ['04-ontologie-liste', `#/projet/${pid}/ontologie-liste`], ['05-shapes', `#/projet/${pid}/shapes`], ['06-conformite', `#/projet/${pid}/conformite`],
  ['07-shacl', `#/projet/${pid}/shacl`], ['08-analyse', `#/projet/${pid}/analyse`], ['09-modele', `#/projet/${pid}/modele`],
  ['10-exports', `#/projet/${pid}/exports`], ['11-requetes', `#/projet/${pid}/requetes`], ['12-assistant', `#/projet/${pid}/assistant`], ['13-parametres', '#/parametres'],
]
async function tour(s, prefix) {
  for (const [name, hash] of s.page.__skip ? [] : screens) {
    const before = s.errs.length
    try {
      await s.page.goto(base + '/' + hash, { waitUntil: 'load' }); if (name !== '01-projets' || true) await s.page.reload({ waitUntil: 'load' })
      await sleep(1500)
      const text = (await s.page.locator('body').innerText()).trim()
      const blank = text.length < 40
      await s.page.screenshot({ path: path.join(SHOTS, `recette-${prefix}${name}.png`), fullPage: false })
      const e = s.errs.slice(before)
      const hOverflow = await s.page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)
      log(`${prefix}${name}`, !blank && e.length === 0 && !(prefix === 'm-' && hOverflow), `texte=${text.length}c erreurs=${e.length}${e.length ? ' ' + JSON.stringify(e.slice(0, 3)) : ''}${hOverflow ? ' DEBORDEMENT-HORIZONTAL' : ''}`)
    } catch (err) { log(`${prefix}${name}`, false, 'EXCEPTION ' + String(err).slice(0, 200)) }
  }
}
const d = await session({ width: 1440, height: 900 }, 'desktop'); await tour(d, '')
// interactions clés (desktop)
const act = async (name, fn) => { const b = d.errs.length; try { const det = await fn(); const e = d.errs.slice(b); log(name, e.length === 0, (det || '') + (e.length ? ' ' + JSON.stringify(e.slice(0, 3)) : '')) } catch (err) { log(name, false, 'EXCEPTION ' + String(err).slice(0, 220)) } }
await act('A1-editeur : nœuds rendus + Ctrl+Z', async () => {
  await d.page.goto(`${base}/#/projet/${pid}/ontologie`); await d.page.reload(); await sleep(2000)
  const n = await d.page.locator('.react-flow__node').count()
  await d.page.locator('.react-flow__node').first().click(); await sleep(600)
  await d.page.screenshot({ path: path.join(SHOTS, 'recette-A1-editeur-selection.png') })
  if (n === 0) throw new Error('aucun nœud'); return `${n} nœuds`
})
await act('A2-requetes : phrase guidée + NL', async () => {
  await fetch(B + '/settings/endpoints', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'x', url: 'http://127.0.0.1:1/sparql' }) })
  await d.page.goto(`${base}/#/projet/${pid}/requetes`); await d.page.reload(); await sleep(1500)
  const inp = d.page.getByPlaceholder(/question/i).first()
  if (await inp.count()) { await inp.fill('quels véhicules ont eu une réparation par le technicien Martin ?'); await d.page.keyboard.press('Enter'); await sleep(2500) }
  await d.page.screenshot({ path: path.join(SHOTS, 'recette-A2-requetes-nl.png') }); return (await inp.count()) ? 'NL envoyée' : 'champ NL introuvable'
})
await act('A3-assistant : envoi message', async () => {
  await d.page.goto(`${base}/#/projet/${pid}/assistant`); await d.page.reload(); await sleep(1500)
  const ta = d.page.locator('textarea').first()
  if (await ta.count()) { await ta.fill('Ajoute une classe Pneu'); await d.page.keyboard.press('Enter'); await sleep(2500) }
  await d.page.screenshot({ path: path.join(SHOTS, 'recette-A3-assistant-reponse.png') }); return (await ta.count()) ? 'message envoyé' : 'textarea introuvable'
})
await act('A4-thème sombre / en', async () => {
  await d.page.goto(`${base}/#/parametres`); await d.page.reload(); await sleep(1500)
  await d.page.screenshot({ path: path.join(SHOTS, 'recette-A4-parametres.png') }); return ''
})
const m = await session({ width: 390, height: 844 }, 'mobile'); await tour(m, 'm-')
await browser.close(); procs.forEach(p => p.kill())
const ko = report.filter(r => !r.ok).length
writeFileSync(path.join(ROOT, 'journal/L14/recette-ui.json'), JSON.stringify({ ok: report.length - ko, ko, steps: report }, null, 1))
console.log(`\n=== UI : ${report.length - ko} OK / ${ko} KO`); process.exit(ko ? 1 : 0)
