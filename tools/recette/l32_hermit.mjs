// Recette L32 : raisonner avec HermiT. Usage : node tools/recette/l32_hermit.mjs   (BACKEND_PORT, FRONT_PORT optionnels ; front déjà buildé ; Java + owlready2 requis)
// Projet 1 : ontologie cohérente avec classe insatisfiable, définition (sous-classe + équivalence inférées) et individu reclassé.
// Projet 2 : individu dans deux classes disjointes (incohérente). Vérifie carte, clic -> éditeur en rouge, « Ajouter au modèle » + annulation, Krakie, anglais.
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
const SHOTS = path.join(ROOT, 'journal/L32/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8932, FP = process.env.FRONT_PORT || 4932
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const report = []
const log = (name, ok, detail = '') => { report.push({ name, ok }); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l32-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const HEAD = `@prefix : <http://example.org/reason#> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n<http://example.org/reason> a owl:Ontology .\n`
const OK_TTL = HEAD + `
:Person a owl:Class ; rdfs:label "Personne"@fr . :Vehicle a owl:Class . :Car a owl:Class ; rdfs:subClassOf :Vehicle .
:Dog a owl:Class ; owl:disjointWith :Cat . :Cat a owl:Class . :Chimera a owl:Class ; rdfs:subClassOf :Dog, :Cat .
:owns a owl:ObjectProperty .
:CarOwner a owl:Class ; owl:equivalentClass [ a owl:Restriction ; owl:onProperty :owns ; owl:someValuesFrom :Car ] .
:Motorist a owl:Class ; owl:equivalentClass [ a owl:Class ; owl:intersectionOf ( :Person [ a owl:Restriction ; owl:onProperty :owns ; owl:someValuesFrom :Car ] ) ] .
:Driver a owl:Class ; rdfs:subClassOf :Person, [ a owl:Restriction ; owl:onProperty :owns ; owl:someValuesFrom :Car ] .
:alice a owl:NamedIndividual, :Person ; :owns :c1 . :c1 a owl:NamedIndividual, :Car .\n`
const KO_TTL = HEAD + `:Dog a owl:Class ; owl:disjointWith :Cat . :Cat a owl:Class . :rex a owl:NamedIndividual, :Dog, :Cat .\n`
async function mk(name, ttl) {
  const pr = await (await fetch(B + '/projects', { method: 'POST', headers: J, body: JSON.stringify({ name }) })).json()
  const f = new FormData(); f.append('file', new Blob([ttl], { type: 'text/turtle' }), 'o.ttl'); f.append('kind', 'ontology')
  const r = await fetch(`${B}/projects/${pr.id}/import`, { method: 'POST', body: f }); if (!r.ok) throw new Error('import ' + r.status + await r.text())
  return pr.id
}
const pid = await mk('raisonner', OK_TTL), pidKo = await mk('incoherente', KO_TTL)
const browser = await chromium.launch()
async function session(vp, opts = {}) {
  const ctx = await browser.newContext({ viewport: vp, locale: opts.locale || 'fr-FR', colorScheme: opts.dark ? 'dark' : 'light' })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1') } catch {} })
  const page = await ctx.newPage(); const errs = []
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('response', r => { if (r.status() >= 500 || (r.status() >= 400 && r.url().includes('/api/') && ![404, 409].includes(r.status()))) errs.push(`HTTP ${r.status()} ${r.url().replace(base, '')}`) })
  return { ctx, page, errs }
}
const shot = (s, name) => s.page.screenshot({ path: path.join(SHOTS, name + '.png') })
const step = async (name, s, fn) => { const b = s.errs.length; try { const d = await fn(); const e = s.errs.slice(b); log(name, e.length === 0, (d || '') + (e.length ? ' ' + JSON.stringify(e.slice(0, 3)) : '')) } catch (err) { log(name, false, 'EXCEPTION ' + String(err).slice(0, 260)) } }
const txt = (s, sel) => s.page.locator(sel).innerText()
const must = (c, m) => { if (!c) throw new Error(m) }

await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'fr', labels: 'fr', assistant: 'fr' } }) })
const s = await session({ width: 1360, height: 900 })
const gotoConf = async id => { await s.page.goto(`${base}/#/projet/${id}/conformite`, { waitUntil: 'load' }); await s.page.reload({ waitUntil: 'load' }); await s.page.waitForSelector('[data-testid=rz-run]', { timeout: 15000 }) }
await gotoConf(pid)
await step('R1 carte présente avant le calcul', s, async () => { await shot(s, '01-avant'); must(await s.page.locator('[data-testid=rz-card]').count() === 1, 'carte absente'); return 'ok' })
await step('R2 raisonnement : badge cohérent, classe insatisfiable, inférences, individu reclassé', s, async () => {
  await s.page.click('[data-testid=rz-run]'); await s.page.waitForSelector('[data-testid=rz-badge]', { timeout: 40000 })
  must((await txt(s, '[data-testid=rz-badge]')).includes('Cohérente'), 'badge')
  must(await s.page.locator('[data-testid=rz-unsat-link]').count() === 1, 'une classe insatisfiable attendue (Chimera)')
  must(await s.page.locator('[data-testid=rz-add]').count() >= 2, 'deux sous-classes inférées attendues')
  must((await txt(s, '[data-testid=rz-ind]')).includes('Motorist'), 'alice reclassée Motorist')
  await shot(s, '02-resultats'); return (await txt(s, '[data-testid=rz-card]')).split('\n').slice(0, 3).join(' | ')
})
await step('R3 « Ajouter au modèle » passe par /ops et s\'annule', s, async () => {
  const cnt = async () => { const o = (await (await fetch(`${B}/projects/${pid}`)).json()).onto; return Object.values(o.classes).reduce((n, c) => n + c.sub_class_of.length, 0) }
  const before = await cnt(); await s.page.locator('[data-testid=rz-add]').first().click(); await sleep(1200)
  must(await cnt() === before + 1, 'sous-classe non ajoutée'); await shot(s, '03-ajoute')
  const h = await (await fetch(`${B}/projects/${pid}/ops/history`)).json(); must(h.can_undo, 'annulation indisponible')
  await s.page.getByRole('button', { name: /Annuler le dernier ajout/ }).click(); await sleep(1000)
  must(await cnt() === before, 'annulation sans effet'); return `${before} -> ${before + 1} -> ${before}`
})
await step('R4 clic sur la classe insatisfiable : éditeur, nœud en rouge, bandeau', s, async () => {
  await gotoConf(pid); await s.page.click('[data-testid=rz-run]'); await s.page.waitForSelector('[data-testid=rz-unsat-link]', { timeout: 40000 })
  await s.page.click('[data-testid=rz-unsat-link]'); await s.page.waitForSelector('.react-flow__node', { timeout: 15000 }); await sleep(1500)
  must(s.page.url().endsWith('/ontologie'), 'pas dans l\'éditeur : ' + s.page.url())
  const n = await s.page.locator('.of-node.err').count(); must(n === 1, `nœuds en rouge : ${n}`)
  must(await s.page.locator('[data-testid=unsat-banner]').count() === 1, 'bandeau absent')
  await s.page.locator('[data-testid=legend-panel] header button').last().click().catch(() => {}); await s.page.keyboard.press('Escape'); await sleep(500); await shot(s, '04-editeur-rouge'); return 'Chimera en rouge'
})
await step('R5 ontologie incohérente : badge, pistes, avertissement de justification', s, async () => {
  await gotoConf(pidKo); await s.page.click('[data-testid=rz-run]'); await s.page.waitForSelector('[data-testid=rz-badge]', { timeout: 40000 })
  must((await txt(s, '[data-testid=rz-badge]')).includes('Incohérente'), 'badge')
  const e = await txt(s, '[data-testid=rz-explain]'); must(e.includes('rex') && e.includes('justification'), 'pistes: ' + e.slice(0, 120)); await shot(s, '05-incoherente'); return 'ok'
})
await step('R6 Krakie : « vérifie la cohérence » et « run the reasoner »', s, async () => {
  const chat = async (m) => (await (await fetch(B + '/assistant/chat', { method: 'POST', headers: J, body: JSON.stringify({ project_id: pid, messages: [{ role: 'user', content: m }], context: {} }) })).json())
  const a = await chat('vérifie la cohérence'); must(/cohérente/.test(a.reply), 'fr: ' + a.reply.slice(0, 100))
  const b = await chat('run the reasoner'); must(/consistent/.test(b.reply) && /HermiT/.test(b.reply), 'en: ' + b.reply.slice(0, 100))
  return a.reply.slice(0, 140)
})
await s.ctx.close()
await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'en', labels: 'en', assistant: 'en' } }) })
const e = await session({ width: 1360, height: 900 }, { locale: 'en-GB' })
await step('R7 anglais : carte traduite', e, async () => {
  await e.page.goto(`${base}/#/projet/${pid}/conformite`, { waitUntil: 'load' }); await e.page.reload({ waitUntil: 'load' }); await e.page.waitForSelector('[data-testid=rz-run]')
  await e.page.click('[data-testid=rz-run]'); await e.page.waitForSelector('[data-testid=rz-badge]', { timeout: 40000 })
  const t = await txt(e, '[data-testid=rz-card]'); must(/Consistent/.test(t) && /Reason with HermiT/.test(t) && !/Cohérente|Classes insatisfiables/.test(t), t.slice(0, 200)); await shot(e, '06-anglais'); return 'ok'
})
await e.ctx.close()
// R8 : attente (réponse ralentie 2,5 s) : Krakie forge pendant le calcul, trophée si cohérente, inquiète sinon ; image fixe en mouvement réduit
for (const [label, id, expect, reduced] of [['cohérente', pid, 'trophee', false], ['incohérente', pidKo, 'inquiete', false], ['mouvement réduit', pid, 'trophee', true]]) {
  const w = await session({ width: 1360, height: 900 })
  if (reduced) await w.page.emulateMedia({ reducedMotion: 'reduce' })
  await w.ctx.route(`${base}/api/**/reason`, async route => { await sleep(2500); await route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }) })
  await step(`R8 attente HermiT (${label})`, w, async () => {
    await w.page.goto(`${base}/#/projet/${id}/conformite`, { waitUntil: 'load' }); await w.page.reload({ waitUntil: 'load' }); await w.page.waitForSelector('[data-testid=rz-run]')
    await w.page.click('[data-testid=rz-run]')
    await w.page.waitForSelector('[data-testid=rz-card] [data-kstatus=forge]', { timeout: 3000 })
    must((await txt(w, '[data-testid=rz-card] .kstatus')).match(/HermiT (raisonne|is reasoning)/), 'texte d\'attente')
    if (!reduced) { const a = await w.page.getAttribute('[data-testid=rz-card] .kstatus img', 'src'); await sleep(400); const b = await w.page.getAttribute('[data-testid=rz-card] .kstatus img', 'src'); must(a !== b, 'forge non animée') }
    else { const a = await w.page.getAttribute('[data-testid=rz-card] .kstatus img', 'src'); await sleep(500); must(a === await w.page.getAttribute('[data-testid=rz-card] .kstatus img', 'src') && a.endsWith('forge.svg'), 'image non fixe : ' + a) }
    if (id === pid && !reduced) await shot(w, '07-attente-forge')
    await w.page.waitForSelector(`[data-testid=rz-card] [data-kstatus=${expect}]`, { timeout: 40000 })
    if (!reduced) await shot(w, expect === 'trophee' ? '08-fin-trophee' : '09-fin-inquiete')
    await w.page.waitForSelector('[data-testid=rz-card] .kstatus', { state: 'detached', timeout: 5000 })
    return expect
  })
  await w.ctx.close()
}
await browser.close(); procs.forEach(p => p.kill())
const ko = report.filter(r => !r.ok).length
console.log(`\n=== L32 : ${report.length - ko} OK / ${ko} KO`); process.exit(ko ? 1 : 0)
