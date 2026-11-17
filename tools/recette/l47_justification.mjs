// Recette L47 : arbitrage par racine, raison d'une décision, constats sans choix à faire, dossier de justification (HTML / Markdown).
// Usage : BACKEND_PORT=9147 FRONT_PORT=5147 node tools/recette/l47_justification.mjs   (front déjà buildé : cd frontend && npm run build)
// Démarre un backend temporaire (IA simulée) + `vite preview`. Captures : journal/L47/screens/.
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
const SHOTS = path.join(ROOT, 'journal/L47/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 9147, FP = process.env.FRONT_PORT || 5147
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
process.on('exit', () => procs.forEach(p => p.kill()))
const report = []
const log = (name, ok, detail = '') => { report.push({ name, ok }); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }
const fr = JSON.parse(readFileSync(path.join(ROOT, 'frontend/src/i18n/fr.json'), 'utf8'))
const en = JSON.parse(readFileSync(path.join(ROOT, 'frontend/src/i18n/en.json'), 'utf8'))

const PY = process.env.PYTHON || '/home/claude/venv/bin/python'
run(PY, ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l47-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 80; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 80; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(B + p, { method: m, headers: J, body: b === undefined ? undefined : JSON.stringify(b) }); return r.json() }
const pid = (await api('POST', '/projects', { name: 'justification', sample: 'automaint' })).id

const browser = await chromium.launch()
const session = async () => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'fr-FR', acceptDownloads: true })
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
const goAnalyse = async s => { await s.page.goto(`${base}/#/projet/${pid}/analyse`, { waitUntil: 'load' }); await s.page.reload({ waitUntil: 'load' }); await s.page.waitForSelector('[data-tour=an-counters]', { timeout: 20000 }); await sleep(500) }
const pendingCount = pg => pg.findings.filter(f => ['review', 'lost'].includes(f.severity) && !f.chosen && f.options.length).length

const s = await session()
await step('A1 constats sans choix : reclassés par cible, Neo4j < 25 constats, 9 groupes max de décision, motif affiché', s, async () => {
  const groups = pg => new Set(pg.findings.filter(f => ['review', 'lost'].includes(f.severity) && !f.chosen && f.options.length).map(f => f.root ? 'root:' + f.root : 'rule:' + f.rule)).size
  const cur = await api('POST', `/projects/${pid}/analyze?target=curiosity`)
  const neo = await api('POST', `/projects/${pid}/analyze?target=neo4j`)
  const rules = pg => [...new Set(pg.findings.filter(f => f.auto_reason).map(f => f.rule))].sort().join()
  if (pendingCount(neo) >= 25) throw new Error('neo4j restants ' + pendingCount(neo))
  if (rules(neo) !== 'D09,D13,O09,O10' || rules(cur) !== 'D09') throw new Error(`reclassés neo4j ${rules(neo)} curiosity ${rules(cur)}`)
  if (groups(cur) > 9 || groups(neo) > 8) throw new Error(`groupes ${groups(cur)}/${groups(neo)}`)
  if ([cur, neo].some(pg => pg.findings.some(f => f.severity === 'lost' && f.auto_reason))) throw new Error('un perdu reclassé')
  await goAnalyse(s)
  const k = await s.page.locator('[data-testid=kpi-reclass]').innerText()
  if (!/\d+/.test(k)) throw new Error('compteur ' + k)
  await shot(s, '01-analyse-reclasses'); return `curiosity ${pendingCount(cur)} constats / ${groups(cur)} groupes, neo4j ${pendingCount(neo)} / ${groups(neo)}, ${k.trim()}`
})
await step('A2 groupe de branche : une raison, « toute la branche », décisions tracées via=branch', s, async () => {
  const g = s.page.locator('[data-testid=branch-group]').first()
  await g.waitFor({ timeout: 10000 })
  const root = await g.getAttribute('data-root')
  await g.locator('[data-testid=why-input]').first().fill('Hiérarchie aplatie d\'un bloc <b>par cohérence</b>')
  await shot(s, '02-branche-avant')
  await g.locator('[data-testid=branch-apply]').click(); await sleep(1500)
  const pg = await api('POST', `/projects/${pid}/analyze?target=curiosity`)
  const mine = pg.findings.filter(f => f.root === root)
  if (!mine.length || !mine.every(f => f.chosen)) throw new Error('branche non décidée')
  const notes = mine.map(f => pg.decision_notes[f.id])
  if (!notes.every(x => x && x.via === 'branch' && x.by === 'local' && x.reason.includes('<b>par cohérence</b>'))) throw new Error(JSON.stringify(notes[0]))
  await shot(s, '03-branche-apres'); return `${mine.length} constats, racine ${root.split('#').pop()}`
})
await step('A3 décision d\'un constat avec raison, puis « décidé par » affiché', s, async () => {
  const rg = s.page.locator('[data-tour=an-rule]').filter({ hasText: 'K02' }).first()
  await rg.locator('.ttl').click()
  const card = rg.locator('[data-tour=an-finding]').first()
  await card.locator('[data-testid=why-input]').fill('NODE KEY validée avec le client')
  await card.locator('input[type=radio]').first().click(); await sleep(1200)
  const by = await s.page.locator('[data-tour=an-rule]').filter({ hasText: 'K02' }).first().locator('[data-testid=decision-by]').first().innerText()
  if (!by.includes('local')) throw new Error(by)
  const pg = await api('POST', `/projects/${pid}/analyze?target=curiosity`)
  const n = Object.values(pg.decision_notes).filter(x => x.reason === 'NODE KEY validée avec le client')
  if (n.length !== 1 || n[0].via !== 'manual') throw new Error(JSON.stringify(n))
  await shot(s, '04-decision-raison'); return by
})
await step('A3b changer l\'option d\'un constat décidé vide la raison (jamais attribuée à l\'autre option)', s, async () => {
  const rg = s.page.locator('[data-tour=an-rule]').filter({ hasText: 'K02' }).first()
  const decided = '[data-tour=an-finding]'
  const card = rg.locator(decided).filter({ has: s.page.locator('[data-testid=decision-by]') }).first()
  await card.locator('input[type=radio]').nth(1).click(); await sleep(1200)
  const v = await s.page.locator('[data-tour=an-rule]').filter({ hasText: 'K02' }).first().locator('[data-tour=an-finding]').filter({ has: s.page.locator('[data-testid=decision-by]') }).first().locator('[data-testid=why-input]').inputValue()
  if (v !== '') throw new Error('champ non vidé : ' + v)
  const pg = await api('POST', `/projects/${pid}/analyze?target=curiosity`)
  if (Object.values(pg.decision_notes).some(x => x.reason === 'NODE KEY validée avec le client')) throw new Error('ancienne raison conservée ' + JSON.stringify(Object.entries(pg.decision_notes).filter(([, x]) => x.reason.includes('NODE')).map(([k, x]) => [k.slice(-30), x.option, x.reason])))
  return 'ok'
})
await step('A4 un constat perdu n\'est pas décidé par la branche ni par « accepter » (D-L14-02)', s, async () => {
  const pg = await api('POST', `/projects/${pid}/analyze?target=neo4j`)
  const lost = pg.findings.filter(f => f.severity === 'lost')
  if (!lost.length) throw new Error('aucun perdu')
  const after = await api('POST', `/projects/${pid}/decisions/neo4j/accept-recommended`)
  if (after.findings.some(f => f.severity === 'lost' && f.chosen)) throw new Error('perdu décidé seul')
  return `${lost.length} perdus restent à arbitrer`
})
await step('E1 Exports : dossier HTML téléchargé, autonome, échappé, avec qui / quand / pourquoi', s, async () => {
  await s.page.goto(`${base}/#/projet/${pid}/exports`, { waitUntil: 'load' }); await s.page.reload({ waitUntil: 'load' })
  await s.page.waitForSelector('[data-testid=justification]', { timeout: 20000 })
  const [dl] = await Promise.all([s.page.waitForEvent('download'), s.page.locator('[data-testid=just-html]').click()])
  const file = path.join(mkdtempSync(path.join(tmpdir(), 'of-l47-dl-')), dl.suggestedFilename()); await dl.saveAs(file)
  const t = readFileSync(file, 'utf8')
  if (!/\.html$/.test(dl.suggestedFilename())) throw new Error(dl.suggestedFilename())
  for (const bad of ['<script', 'onerror=', 'onclick=', '<iframe', '<link', '@import', 'url(']) if (t.includes(bad)) throw new Error('contient ' + bad)
  if (/(src|href)=["']?(https?:|\/\/)/.test(t)) throw new Error('ressource distante')
  if (!t.includes('&lt;b&gt;par cohérence&lt;/b&gt;') || t.includes('<b>par cohérence')) throw new Error('raison non échappée')
  if (!t.includes('local') || !t.includes('Hiérarchie aplatie')) throw new Error('décision absente')
  if (!/http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;/.test(t)) throw new Error('CSP absente')
  await shot(s, '05-exports-dossier'); return `${t.length} octets`
})
await step('E2 Exports : dossier Markdown téléchargé', s, async () => {
  const [dl] = await Promise.all([s.page.waitForEvent('download'), s.page.locator('[data-testid=just-md]').click()])
  const file = path.join(mkdtempSync(path.join(tmpdir(), 'of-l47-dl-')), dl.suggestedFilename()); await dl.saveAs(file)
  const t = readFileSync(file, 'utf8')
  if (!/\.md$/.test(dl.suggestedFilename()) || !t.startsWith('# Dossier de justification')) throw new Error(t.slice(0, 60))
  if (t.includes('<b>par')) throw new Error('HTML actif dans le Markdown')
  return dl.suggestedFilename()
})
await step('E3 dossier rendu dans le navigateur : aucune exécution de script, sections présentes', s, async () => {
  const v = await s.ctx.newPage(); let ran = false
  await v.exposeFunction('__ran', () => { ran = true })
  const html = await (await fetch(`${B}/projects/${pid}/justification/curiosity?format=html`)).text()
  await v.setContent(html, { waitUntil: 'load' })
  const h2 = await v.locator('h2').allInnerTexts()
  if (!['Ce qui est perdu', 'Ce qui est compensé', 'Décisions humaines', 'Recommandations non suivies'].every(x => h2.includes(x))) throw new Error(h2.join('|'))
  if (ran) throw new Error('script exécuté')
  await v.screenshot({ path: path.join(SHOTS, '06-dossier-html.png'), fullPage: false }); await v.close(); return h2.length + ' sections'
})

// lecteur : lit le dossier ; version anglaise
await api('PUT', '/settings', { language: { ui: 'en', labels: 'en', assistant: 'en' } })
const e = await session()
await step('L1 anglais : bouton et dossier en anglais', e, async () => {
  await e.page.goto(`${base}/#/projet/${pid}/exports`, { waitUntil: 'load' }); await e.page.reload({ waitUntil: 'load' })
  await e.page.waitForSelector('[data-testid=justification]', { timeout: 20000 })
  const t = await e.page.locator('[data-testid=justification]').innerText()
  if (!t.includes(en['ex.just.t']) || /[éèàçêâîô]/.test(t)) throw new Error(t)
  const md = await (await fetch(`${B}/projects/${pid}/justification/neo4j?format=md`)).text()
  if (!md.startsWith('# Justification file') || md.includes('Dossier de justification')) throw new Error(md.slice(0, 60))
  await shot(e, '07-exports-en'); return 'ok'
})
await step('L2 anglais : écran Arbitrer sans français dans les libellés ajoutés', e, async () => {
  await e.page.goto(`${base}/#/projet/${pid}/analyse`, { waitUntil: 'load' }); await e.page.reload({ waitUntil: 'load' }); await e.page.waitForSelector('[data-tour=an-counters]', { timeout: 20000 })
  const k = await e.page.locator('[data-testid=kpi-reclass]').innerText()
  if (/[éèàçêâîô]/.test(k) || !/no choice|need/.test(k)) throw new Error(k)
  return k.trim()
})
await api('PUT', '/settings', { language: { ui: 'fr', labels: 'fr', assistant: 'fr' } })

const bad = report.filter(r => !r.ok)
console.log(`\n${report.length - bad.length}/${report.length} OK`)
await browser.close()
process.exit(bad.length ? 1 : 0)
