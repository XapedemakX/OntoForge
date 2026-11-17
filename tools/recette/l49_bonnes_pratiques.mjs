// Recette L49 : bonnes pratiques d'ontologie. Usage : BACKEND_PORT=9149 FRONT_PORT=5149 node tools/recette/l49_bonnes_pratiques.mjs   (front déjà buildé)
// Démarre un backend temporaire (mock) + `vite preview`, puis : écran Conformité (complétude, en-tête, versions), fiche de la vue liste
// (définition, auteur, statut, score), dépréciation avec remplaçant (listes, graphe, constat A03 à arbitrer, rapport), version 1.0.0 puis 1.1.0
// avec note générée, export Turtle, interface anglaise. Captures : journal/L49/screens/.
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
const SHOTS = path.join(ROOT, 'journal/L49/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 9149, FP = process.env.FRONT_PORT || 5149
const PY = process.env.PYTHON || '/home/claude/venv/bin/python'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
process.on('exit', () => procs.forEach(p => { try { p.kill() } catch {} }))
const report = []
const log = (name, ok, detail = '') => { report.push({ name, ok }); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

const BACKEND = path.join(ROOT, 'backend')
run(PY, ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: BACKEND, env: { ...process.env, PYTHONPATH: BACKEND, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l49-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 80; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 80; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(B + p, { method: m, headers: J, body: b === undefined ? undefined : JSON.stringify(b) }); return r.headers.get('content-type')?.includes('json') ? r.json() : r.text() }
const pid = (await api('POST', '/projects', { name: 'bonnes pratiques', sample: 'automaint' })).id
const proj = await api('GET', `/projects/${pid}`)
const NS = Object.keys(proj.onto.classes).find(i => i.endsWith('#Vehicle')).replace(/Vehicle$/, '')
const OLD = Object.keys(proj.onto.classes).find(i => i.endsWith('#Garage')) ? NS + 'Garage' : Object.keys(proj.onto.classes).sort()[1]
const lab = (iri, l = 'fr') => (proj.onto.classes[iri] || {}).labels?.[l] || iri.split('#').pop()

const browser = await chromium.launch()
const session = async (locale = 'fr-FR') => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1') } catch {} })
  const page = await ctx.newPage(); const errs = []
  page.on('console', m => { if (m.type() === 'error' && !/501|HermiT|Java/i.test(m.text())) errs.push('console: ' + m.text().slice(0, 200)) })
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('response', r => { if (r.status() >= 500 && !r.url().includes('/reason')) errs.push(`HTTP ${r.status()} ${r.url().replace(base, '')}`) })
  return { ctx, page, errs }
}
const shot = (s, name) => s.page.screenshot({ path: path.join(SHOTS, name + '.png') })
const step = async (name, s, fn) => { const b = s.errs.length; try { const d = await fn(); const e = s.errs.slice(b); log(name, e.length === 0, (d || '') + (e.length ? ' ' + JSON.stringify(e.slice(0, 2)) : '')) } catch (e) { log(name, false, String(e).slice(0, 300)); await shot(s, 'ko-' + name.slice(0, 24).replace(/\W+/g, '-')).catch(() => {}) } }
const goto = async (s, screen, sel) => { await s.page.goto(`${base}/#/projet/${pid}/${screen}`, { waitUntil: 'load' }); await s.page.reload({ waitUntil: 'load' }); if (sel) await s.page.waitForSelector(sel, { timeout: 25000 }); await sleep(400) }
const blurFill = async (loc, v) => { await loc.fill(v); await loc.press('Tab'); await sleep(900) }
const until = async (fn, ms = 8000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await fn()) return true; await sleep(250) } return false }

const s = await session()
await step('R1 API : conformité avec complétude et constats BP08–BP16 non bloquants', s, async () => {
  const c = await api('GET', `/projects/${pid}/conformance`)
  if (!c.completeness || typeof c.completeness.score !== 'number') throw new Error('pas de completeness')
  const bp = c.issues.filter(i => i.code >= 'BP08')
  if (!bp.length || bp.some(i => i.level === 'error')) throw new Error('BP ' + bp.length)
  if (!c.profiles.DL) throw new Error('profil DL perdu')
  return `score ${c.completeness.score} %, ${bp.length} constats BP08+`
})
await step('R2 écran Conformité : cartes complétude, en-tête, versions', s, async () => {
  await goto(s, 'conformite', '[data-testid=bp-completeness]')
  for (const id of ['bp-completeness', 'bp-header', 'bp-releases']) if (!await s.page.locator(`[data-testid=${id}]`).count()) throw new Error(id)
  const sum = await s.page.locator('[data-testid=bp-rel-summary]').innerText()
  if (!/1\.0\.0/.test(sum)) throw new Error(sum)
  await shot(s, '01-conformite-cartes'); return sum
})
await step('R3 en-tête éditable : licence et auteurs enregistrés (dcterms)', s, async () => {
  await blurFill(s.page.locator('[data-testid=bp-h-license]'), 'https://creativecommons.org/licenses/by/4.0/')
  await blurFill(s.page.locator('[data-testid=bp-h-creators]'), 'Équipe modèle; Atelier données')
  const ok = await until(async () => { const m = await api('GET', `/projects/${pid}/metadata`); return m.header.license && m.header.creators.length === 2 })
  if (!ok) throw new Error(JSON.stringify((await api('GET', `/projects/${pid}/metadata`)).header))
  return 'licence + 2 auteurs'
})
await step('R4 enregistrer la version 1.0.0 : versionInfo, versionIRI, historique', s, async () => {
  await s.page.locator('[data-testid=bp-rel-save]').click()
  if (!await until(async () => (await s.page.locator('[data-testid=bp-rel-history] li').count()) === 1)) throw new Error('historique vide')
  const p = await api('GET', `/projects/${pid}`)
  if (!/\/1\.0\.0$/.test(p.onto.meta.version_iri || '')) throw new Error('versionIRI ' + p.onto.meta.version_iri)
  await shot(s, '02-version-1-0-0'); return p.onto.meta.version_iri
})
await step('R5 vue liste : fiche avec score, définition, auteur, statut', s, async () => {
  await goto(s, 'ontologie-liste', '.ol-left')
  await s.page.locator(`.ol-left button.nm[title="${NS}Vehicle"]`).click()
  await s.page.waitForSelector('[data-testid=bp-card]', { timeout: 10000 })
  const before = await s.page.locator('[data-testid=bp-card] [data-testid=bp-score]').innerText()
  await blurFill(s.page.locator('[data-testid=bp-definition]'), 'Moyen de transport suivi par le parc.')
  await blurFill(s.page.locator('[data-testid=bp-creator]'), 'Équipe modèle')
  await s.page.locator('[data-testid=bp-status]').selectOption('testing'); await sleep(900)
  const ok = await until(async () => { const p = await api('GET', `/projects/${pid}`); const a = p.onto.classes[NS + 'Vehicle'].annotations; return a.some(x => x.property.endsWith('#definition')) && a.some(x => x.property.endsWith('/creator')) && a.some(x => x.value === 'testing') })
  if (!ok) throw new Error('annotations non enregistrées : ' + JSON.stringify((await api('GET', `/projects/${pid}`)).onto.classes[NS + 'Vehicle'].annotations).slice(0, 400))
  const after = await s.page.locator('[data-testid=bp-card] [data-testid=bp-score]').innerText()
  if (parseInt(after) <= parseInt(before)) throw new Error(`score ${before} → ${after}`)
  await shot(s, '03-fiche-liste'); return `score ${before} → ${after}`
})
await step('R6 déprécier avec remplaçant : marqué dans la liste, owl:deprecated + isReplacedBy', s, async () => {
  await s.page.locator(`.ol-left button.nm[title="${OLD}"]`).click()
  await s.page.waitForSelector('[data-testid=bp-deprecate]', { timeout: 10000 })
  await s.page.locator('[data-testid=bp-replacement]').selectOption(NS + 'Vehicle')
  await s.page.locator('[data-testid=bp-deprecate]').click()
  await s.page.waitForSelector('[data-testid=bp-deprecated]', { timeout: 10000 })
  if (!await s.page.locator('.ol-left [data-testid=ol-dep]').count()) throw new Error('pas de marque dans la liste')
  const c = (await api('GET', `/projects/${pid}`)).onto.classes[OLD]
  if (!c.deprecated || !c.annotations.some(a => a.property.endsWith('/isReplacedBy') && a.value === NS + 'Vehicle')) throw new Error(JSON.stringify(c.annotations))
  await shot(s, '04-deprecie-liste'); return OLD.split('#').pop()
})
await step('R7 éditeur graphique : nœud barré, fiche dans l\'inspecteur', s, async () => {
  await goto(s, 'ontologie', '.of-node')
  const dep = await s.page.locator('.of-node.deprecated').count()
  if (!dep) throw new Error('aucun nœud déprécié')
  await s.page.locator('.of-node', { hasText: lab(NS + 'Vehicle') }).first().click(); await sleep(600)
  if (!await s.page.locator('.of-insp [data-testid=bp-card]').count()) throw new Error('fiche absente de l\'inspecteur')
  await shot(s, '05-editeur-fiche'); return dep + ' nœud(s) barré(s)'
})
await step('R8 analyse : A03 à arbitrer, non générée par défaut, ligne au rapport', s, async () => {
  const pg = await api('POST', `/projects/${pid}/analyze?target=neo4j`)
  const f = pg.findings.find(x => x.id === `A03:${OLD}`)
  if (!f || f.severity !== 'review' || f.recommended !== 'exclude') throw new Error(JSON.stringify(f))
  if (Object.values(pg.node_types).some(n => n.source.includes(OLD))) throw new Error('entité dépréciée générée')
  const g = await api('GET', `/projects/${pid}/generate/neo4j`)
  const rep = g.files['rapport-transposition.md']
  if (!/## Entités dépréciées — \d/.test(rep)) throw new Error('section absente')
  return 'A03 review, exclue, rapport OK'
})
await step('R9 version 1.1.0 proposée (mineure) avec note, enregistrée', s, async () => {
  await goto(s, 'conformite', '[data-testid=bp-releases]')
  const sum = await s.page.locator('[data-testid=bp-rel-summary]').innerText()
  if (!/1\.1\.0/.test(sum) || !/mineure/.test(sum)) throw new Error(sum)
  const note = await s.page.locator('[data-testid=bp-rel-note]').textContent()
  if (!/dépréciée/.test(note) || !/Changements mineurs/.test(note)) throw new Error(note.slice(0, 200))
  await s.page.locator('details summary').first().click()
  await shot(s, '06-version-mineure')
  await s.page.locator('[data-testid=bp-rel-save]').click()
  if (!await until(async () => (await s.page.locator('[data-testid=bp-rel-history] li').count()) === 2)) throw new Error('pas de 2e version')
  const p = await api('GET', `/projects/${pid}`)
  if (!p.onto.meta.annotations.some(a => a.property.endsWith('#priorVersion') && /\/1\.0\.0$/.test(a.value))) throw new Error('priorVersion')
  return sum
})
await step('R10 ajout d\'une classe : version mineure 1.2.0 proposée (Q-L49-1)', s, async () => {
  const r = await api('POST', `/projects/${pid}/ops`, { ops: [{ op: 'add_class', iri: NS + 'HydrogenVehicle', label: 'Véhicule à hydrogène', parent: NS + 'Vehicle' }] })
  if (!r.ok) throw new Error('ops : ' + JSON.stringify(r.errors).slice(0, 300))
  const pv = await api('GET', `/projects/${pid}/releases/preview`)
  if (pv.level !== 'minor' || pv.proposed !== '1.2.0') throw new Error(JSON.stringify({ l: pv.level, p: pv.proposed }))
  return `${pv.counts.minor} changement(s) mineur(s)`
})
await step('R11 export Turtle : en-tête, dépréciation et version conservés', s, async () => {
  const ttl = await api('GET', `/projects/${pid}/export/ontology?format=turtle`)
  for (const k of ['owl:versionIRI', 'owl:versionInfo "1.1.0"', 'owl:priorVersion', 'dcterms:license', 'dcterms:isReplacedBy', 'owl:deprecated true', 'skos:definition'])
    if (!ttl.includes(k)) throw new Error('absent : ' + k)
  return 'ok'
})
await step('R13 annuler l\'enregistrement retire la version de l\'historique (revue it1)', s, async () => {
  const before = (await api('GET', `/projects/${pid}/releases`)).releases.length
  await api('POST', `/projects/${pid}/ops/undo`)  // annule l'ajout de classe de R10
  const u = await api('POST', `/projects/${pid}/ops/undo`)
  if (u.label !== 'version 1.1.0') throw new Error('libellé ' + u.label)
  const after = (await api('GET', `/projects/${pid}/releases`)).releases.map(r => r.version)
  if (after.length !== before - 1 || after.includes('1.1.0')) throw new Error(JSON.stringify(after))
  const r = await fetch(B + `/projects/${pid}/releases`, { method: 'POST', headers: J, body: JSON.stringify({ version: '1.1.0' }) })
  if (r.status !== 201) throw new Error('réenregistrement ' + r.status)
  return `${before} → ${after.length} → ${before}`
})
await step('R14 garder avec drapeau : marque [DÉPRÉCIÉ] dans Edges.cs et les fichiers Neo4j', s, async () => {
  const rel = Object.keys((await api('GET', `/projects/${pid}`)).onto.object_properties).sort()[0]
  await api('POST', `/projects/${pid}/ops`, { ops: [{ op: 'set_deprecated', iri: rel }] })
  await api('PUT', `/projects/${pid}/decisions/neo4j`, { [`A03:${OLD}`]: 'flag_deprecated', [`A03:${rel}`]: 'flag_deprecated' })
  await api('PUT', `/projects/${pid}/decisions/curiosity`, { [`A03:${OLD}`]: 'flag_deprecated', [`A03:${rel}`]: 'flag_deprecated' })
  const n = (await api('GET', `/projects/${pid}/generate/neo4j`)).files
  for (const f of ['schema.cypher', 'ingest.cypher', 'README-neo4j.md']) if (!n[f].includes('[DÉPRÉCIÉ]')) throw new Error('neo4j ' + f)
  if (!n['model.mmd'].includes('deprecated')) throw new Error('model.mmd')
  const c = (await api('GET', `/projects/${pid}/generate/curiosity`)).files
  if (!c['Edges.cs'].includes('[DÉPRÉCIÉ]')) throw new Error('Edges.cs')
  return rel.split('#').pop()
})
await s.ctx.close()

const en = await session('en-US')
await step('R12 interface anglaise : cartes et constats traduits', en, async () => {
  await api('PUT', '/settings', { language: { ui: 'en' } })
  await goto(en, 'conformite', '[data-testid=bp-header]')
  const t = await en.page.locator('[data-testid=bp-header] h2').innerText()
  const r = await en.page.locator('[data-testid=bp-releases] h2').innerText()
  if (t !== 'Ontology header' || r !== 'Ontology versions') throw new Error(`${t} / ${r}`)
  const c = await api('GET', `/projects/${pid}/conformance`)
  const fr = c.issues.filter(i => i.code >= 'BP08' && /manquante|dépréciée|fiche incomplète|En-tête/.test(i.message))
  if (fr.length) throw new Error(fr[0].message)
  await shot(en, '07-conformite-en'); await api('PUT', '/settings', { language: { ui: 'fr' } })
  return 'ok'
})
await en.ctx.close()
await browser.close()
const ok = report.filter(r => r.ok).length
console.log(`\n${ok}/${report.length} vérifications OK`)
procs.forEach(p => { try { p.kill() } catch {} })
process.exit(ok === report.length ? 0 : 1)
