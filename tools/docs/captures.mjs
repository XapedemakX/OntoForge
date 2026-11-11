// L34c : générateur reproductible des captures de la documentation.
// Usage : node tools/docs/captures.mjs [--lang fr|en|both] [--only nom1,nom2|groupe] [--no-optimize] [--keep-servers]
//   (le front doit être construit : cd frontend && npm run build ; Pillow dans le venv pour l'optimisation)
// Démarre un backend jetable (assistant « mock », données temporaires) et `vite preview`, crée l'exemple automaint,
// puis prend chaque capture dans les deux langues (interface, libellés et assistant) : docs/guide/img/<fr|en>/<nom>.png.
// Fenêtre 1440×900, thème clair, mêmes données dans les deux langues. Des annotations (pastilles numérotées, cadres)
// sont injectées dans la page juste avant la capture, puis retirées. Aucune vraie clé : seulement des valeurs factices.
import { createRequire } from 'node:module'
import { spawn, spawnSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, readdirSync, statSync, rmSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const OUT = path.join(ROOT, 'docs/guide/img')
const PY = process.env.PYTHON || '/home/claude/venv/bin/python'
const argv = process.argv.slice(2)
const opt = (n, d) => { const i = argv.indexOf('--' + n); return i < 0 ? d : (argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : true) }
const LANGS = opt('lang', 'both') === 'both' ? ['fr', 'en'] : [opt('lang')]
const ONLY = opt('only', null) ? String(opt('only')).split(',') : null
const BP = process.env.BACKEND_PORT || 8971, FP = process.env.FRONT_PORT || 4971
const sleep = ms => new Promise(r => setTimeout(r, ms))
const DICT = { fr: JSON.parse(readFileSync(path.join(ROOT, 'frontend/src/i18n/fr.json'), 'utf8')), en: JSON.parse(readFileSync(path.join(ROOT, 'frontend/src/i18n/en.json'), 'utf8')) }
const NS = 'https://w3id.org/ontoforge/automaint#'
const J = { 'content-type': 'application/json' }

// ----------------------------------------------------------------------------- serveurs
const procs = []
const run = (cmd, args, o) => { const p = spawn(cmd, args, { stdio: 'ignore', ...o }); procs.push(p); return p }
const stopAll = () => procs.forEach(p => { try { p.kill() } catch {} })
process.on('exit', stopAll)
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
if (!process.env.REUSE) run(PY, ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-docs-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
if (!process.env.REUSE) run(process.execPath, [path.join(ROOT, 'frontend/node_modules/vite/bin/vite.js'), 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: B.replace('/api', '') } })
for (let i = 0; i < 80; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 80; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }

// ----------------------------------------------------------------------------- annotations
const ANN_CSS = `
.__ann-b{position:fixed;z-index:2147483000;width:26px;height:26px;margin:-13px 0 0 -13px;border-radius:50%;background:#e8590c;color:#fff;font:700 14px/26px "IBM Plex Sans",system-ui,sans-serif;text-align:center;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);pointer-events:none}
.__ann-r{position:fixed;z-index:2147482999;border:3px solid #e8590c;border-radius:8px;box-shadow:0 0 0 2px rgba(255,255,255,.7);pointer-events:none}`
async function annotate(page, items) {
  const rects = []
  for (const it of items) {
    const loc = typeof it.at === 'string' ? page.locator(it.at).first() : it.at.first()
    let bb = null; try { await loc.waitFor({ state: 'visible', timeout: 4000 }); bb = await loc.boundingBox() } catch {}
    if (!bb) { console.log('   annotation ignorée (cible absente) : ' + (it.n ?? it.box)); continue }
    rects.push({ ...it, bb, at: undefined })
  }
  await page.evaluate(([rs, css]) => {
    const st = document.createElement('style'); st.dataset.ofAnn = '1'; st.textContent = css; document.head.append(st)
    for (const r of rs) {
      const { x, y, width: w, height: h } = r.bb, pad = r.pad ?? 3
      if (r.box) { const d = document.createElement('div'); d.className = '__ann-r'; d.dataset.ofAnn = '1'; Object.assign(d.style, { left: x - pad + 'px', top: y - pad + 'px', width: w + 2 * pad + 'px', height: h + 2 * pad + 'px' }); document.body.append(d) }
      if (r.n != null) {
        // pastille : dans le coin (cible grande) ou à cheval sur le coin (petite cible, ou r.out)
        const pos = r.pos || 'tl', d = document.createElement('div'); d.className = '__ann-b'; d.dataset.ofAnn = '1'; d.textContent = String(r.n)
        const inset = r.out === undefined ? (w > 140 && h > 50) : !r.out, k = inset ? 16 : (r.box ? pad : 0)
        const right = pos.includes('r'), bottom = pos.includes('b')
        const px = right ? x + w + (inset ? -k : k) : x + (inset ? k : -k), py = bottom ? y + h + (inset ? -k : k) : y + (inset ? k : -k)
        d.style.left = Math.min(Math.max(px, 16), innerWidth - 16) + 'px'; d.style.top = Math.min(Math.max(py, 16), innerHeight - 16) + 'px'; document.body.append(d)
      }
    }
  }, [rects, ANN_CSS])
}
const unannotate = page => page.evaluate(() => document.querySelectorAll('[data-of-ann]').forEach(e => e.remove()))

// ----------------------------------------------------------------------------- textes par langue (hors dictionnaire de l'interface)
const TXT = {
  fr: { proj: 'AutoMaint', projTrap: 'Piège (démonstration)', projHermit: 'Démo HermiT', providerName: 'Mon fournisseur (démo)', epName: 'Triplestore de démo', nl: 'véhicules dont le carburant est Diesel',
    chatAdd: 'ajoute la classe Pneu sous Pièce avec une propriété pression en bar', chatHelp: 'comment ça marche ici', prose: 'Un garage répare des véhicules. Chaque véhicule a un propriétaire.' },
  en: { proj: 'AutoMaint', projTrap: 'Trap (demo)', projHermit: 'HermiT demo', providerName: 'My provider (demo)', epName: 'Demo triplestore', nl: 'vehicles whose fuel is Diesel',
    chatAdd: 'add the class Tyre under Part with a property pressure in bar', chatHelp: 'how does this work', prose: 'A garage repairs vehicles. Each vehicle has an owner.' },
}
const HERMIT_TTL = `@prefix : <http://example.org/reason#> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://example.org/reason> a owl:Ontology .
:Person a owl:Class ; rdfs:label "Person"@en, "Personne"@fr . :Vehicle a owl:Class ; rdfs:label "Vehicle"@en, "Véhicule"@fr . :Car a owl:Class ; rdfs:subClassOf :Vehicle ; rdfs:label "Car"@en, "Voiture"@fr .
:Dog a owl:Class ; owl:disjointWith :Cat ; rdfs:label "Dog"@en, "Chien"@fr . :Cat a owl:Class ; rdfs:label "Cat"@en, "Chat"@fr .
:Chimera a owl:Class ; rdfs:subClassOf :Dog, :Cat ; rdfs:label "Chimera"@en, "Chimère"@fr .
:owns a owl:ObjectProperty ; rdfs:label "owns"@en, "possède"@fr .
:CarOwner a owl:Class ; rdfs:label "Car owner"@en, "Propriétaire de voiture"@fr ; owl:equivalentClass [ a owl:Restriction ; owl:onProperty :owns ; owl:someValuesFrom :Car ] .
:Motorist a owl:Class ; rdfs:label "Motorist"@en, "Automobiliste"@fr ; owl:equivalentClass [ a owl:Class ; owl:intersectionOf ( :Person [ a owl:Restriction ; owl:onProperty :owns ; owl:someValuesFrom :Car ] ) ] .
:Driver a owl:Class ; rdfs:label "Driver"@en, "Conducteur"@fr ; rdfs:subClassOf :Person, [ a owl:Restriction ; owl:onProperty :owns ; owl:someValuesFrom :Car ] .
:alice a owl:NamedIndividual, :Person ; :owns :c1 . :c1 a owl:NamedIndividual, :Car .\n`

// ----------------------------------------------------------------------------- une session par langue
const browser = await chromium.launch()
const results = []
let captured = 0

async function runLang(lang) {
  const t = (k, v) => { let s = DICT[lang][k] ?? ('?' + k); if (v) for (const [a, b] of Object.entries(v)) s = s.replace(`{${a}}`, b); return s }
  const X = TXT[lang], dir = path.join(OUT, lang); mkdirSync(dir, { recursive: true })
  const put = (p, body) => fetch(B + p, { method: 'PUT', headers: J, body: JSON.stringify(body) })
  const post = (p, body) => fetch(B + p, { method: 'POST', headers: J, body: JSON.stringify(body) })
  await put('/settings', { language: { ui: lang, labels: lang, assistant: lang } })
  // données : le même jeu dans les deux langues (projets créés à neuf pour chaque langue)
  const mkProject = async (name, sample) => (await (await post('/projects', { name, sample })).json()).id
  for (const p of await (await fetch(B + '/projects')).json()) await fetch(`${B}/projects/${p.id}`, { method: 'DELETE' })
  const pidTrap = await mkProject(X.projTrap, 'trap')
  const pid = await mkProject(X.proj, 'automaint')
  const pidHermit = await mkProject(X.projHermit)
  { const f = new FormData(); f.append('file', new Blob([HERMIT_TTL], { type: 'text/turtle' }), 'raisonnement.ttl'); f.append('kind', 'ontology')
    const r = await fetch(`${B}/projects/${pidHermit}/import`, { method: 'POST', body: f }); if (!r.ok) throw new Error('import HermiT ' + r.status) }
  // fournisseur et endpoint factices (aucune vraie clé) : créés à la demande par les captures qui en ont besoin, retirés au début de chaque langue
  const del = p => fetch(B + p, { method: 'DELETE' })
  const dropExtras = async () => {
    for (const e of (await (await fetch(B + '/settings/endpoints')).json()).endpoints) await del('/settings/endpoints/' + e.id)
    for (const p of (await (await fetch(B + '/settings')).json()).llm_providers ?? []) if (p.kind !== 'mock') await del('/settings/providers/' + p.id)
  }
  await dropExtras()
  const addProvider = () => post('/settings/providers', { name: X.providerName, kind: 'anthropic', model: 'claude-sonnet-4-5', api_key: 'sk-ant-FACTICE-demo-0000' })
  const addEndpoint = () => post('/settings/endpoints', { name: X.epName, url: 'https://sparql.example.org/demo/sparql', auth: 'none' })
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: lang === 'fr' ? 'fr-FR' : 'en-GB', colorScheme: 'light', deviceScaleFactor: 1, acceptDownloads: true })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.setItem('ontoforge.ed.legend', 'closed') } catch {} })
  const page = await ctx.newPage()
  await page.addInitScript(() => { const st = document.createElement('style'); st.id = 'of-hide-fab'; st.textContent = 'button.ag-fab{visibility:hidden !important}'; document.addEventListener('DOMContentLoaded', () => document.head.append(st)) })
  const errs = []
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 160)))
  page.on('response', r => { if (r.status() >= 500) errs.push(`HTTP ${r.status()} ${r.url().replace(base, '')}`) })

  const settle = async (ms = 700) => { await page.waitForLoadState('networkidle', { timeout: 2500 }).catch(() => {}); await sleep(ms) }
  const go = async (h, { wait, ms, keepProposal } = {}) => {
    const url = `${base}/#/${h.replace('PID', pid)}`
    await page.goto(url, { waitUntil: 'load' })
    if (!keepProposal) await page.evaluate(() => { try { localStorage.removeItem('ontoforge.proposal') } catch {} })
    await page.reload({ waitUntil: 'load' })
    if (wait) await page.waitForSelector(wait, { timeout: 20000, state: 'attached' })
    await settle(ms)
  }
  const goTo = (screen, o) => go(`projet/${pid}/${screen}`, o)
  /** Capture : page entière, ou `target` (locator ou sélecteur) avec une marge `pad`, annotations `ann` injectées puis retirées. */
  const snap = async (name, { target, pad = 8, ann = [], fab = false, upTo } = {}) => {
    if (fab) await page.evaluate(() => document.getElementById('of-hide-fab')?.remove())
    if (ann.length) await annotate(page, ann)
    await sleep(250)
    const file = path.join(dir, name + '.png')
    const opts = { path: file, animations: 'disabled', caret: 'hide' }
    if (target) {
      const loc = typeof target === 'string' ? page.locator(target).first() : target.first()
      await loc.waitFor({ state: 'visible', timeout: 8000 }); await loc.scrollIntoViewIfNeeded()
      let bb = await loc.boundingBox()
      const vp = page.viewportSize()
      const clip = { x: Math.max(0, bb.x - pad), y: Math.max(0, bb.y - pad), width: 0, height: 0 }
      clip.width = Math.min(vp.width - clip.x, bb.width + 2 * pad - (bb.x - pad < 0 ? pad - bb.x : 0)); clip.height = Math.min(vp.height - clip.y, bb.height + 2 * pad)
      await page.screenshot({ ...opts, clip })
    } else if (upTo) {
      // pleine largeur, du haut de la fenêtre jusqu'au bas du dernier élément `upTo` (évite une grande zone vide)
      const bottom = await page.evaluate(sel => Math.max(...[...document.querySelectorAll(sel)].map(e => e.getBoundingClientRect().bottom)), upTo)
      const vp = page.viewportSize(); await page.screenshot({ ...opts, clip: { x: 0, y: 0, width: vp.width, height: Math.min(vp.height, Math.ceil(bottom) + 24) } })
    } else await page.screenshot(opts)
    if (ann.length) await unannotate(page)
    if (fab) await page.evaluate(() => { const st = document.createElement('style'); st.id = 'of-hide-fab'; st.textContent = 'button.ag-fab{visibility:hidden !important}'; document.head.append(st) })
    captured++
    console.log(`  ${lang} ${name}`)
  }
  const click = async (loc, o) => { const l = typeof loc === 'string' ? page.locator(loc).first() : loc.first(); await l.waitFor({ state: 'visible', timeout: 10000 }); await l.click(o); }
  const btn = (name, o = {}) => page.getByRole('button', { name, exact: true, ...o }).first()
  const side = key => page.locator('.side nav button', { hasText: t(key) }).first()
  const openKrakie = async () => { if (!(await page.locator('.ag-panel').count())) { await page.keyboard.press('Control+k'); await page.waitForSelector('.ag-panel') } await sleep(500) }
  const ask = async (text, waitSel, { timeout = 20000 } = {}) => { await page.fill('.ag-box textarea', text); await page.keyboard.press('Enter'); await page.waitForSelector(waitSel, { timeout }); await sleep(600) }
  const closeKrakie = async () => { await page.keyboard.press('Escape').catch(() => {}); const c = page.locator('.ag-panel [aria-label="' + t('common.close') + '"]').first(); if (await c.count()) await c.click().catch(() => {}); await sleep(300) }
  const ctxO = { addProvider, addEndpoint, dropExtras, del, page, t, X, lang, pid, pidTrap, pidHermit, B, base, post, put, go, goTo, snap, settle, click, btn, side, openKrakie, ask, closeKrakie, sleep, ctx, browser, path, ROOT, NS, errs, readFileSync }

  // `CAPS` vient de captures-list.mjs : liste ordonnée des captures
  const { CAPS } = await import('./captures-list.mjs')
  for (const cap of CAPS) {
    if (ONLY && !ONLY.includes(cap.name) && !ONLY.includes(cap.group)) continue
    try { await cap.run(ctxO) } catch (e) {
      console.log(`KO  ${lang} ${cap.name} :: ${String(e).split('\n')[0].slice(0, 200)}`); results.push({ lang, name: cap.name, ok: false })
      try { await page.screenshot({ path: path.join(tmpdir(), `docs-ko-${lang}-${cap.name}.png`) }) } catch {}
      try { await unannotate(page) } catch {}
      continue
    }
    results.push({ lang, name: cap.name, ok: true })
  }
  if (errs.length) console.log(`  erreurs page (${lang}) : ${errs.length}`, errs.slice(0, 3))
  await ctx.close()
}
for (const l of LANGS) await runLang(l)
await browser.close()

// ----------------------------------------------------------------------------- optimisation
if (!argv.includes('--no-optimize')) {
  const r = spawnSync(PY, ['-I', path.join(ROOT, 'tools/docs/optimize.py'), OUT], { stdio: 'inherit' })
  if (r.status !== 0) console.log('optimisation en échec (Pillow installé dans le venv ?)')
}
const ko = results.filter(r => !r.ok)
console.log(`\n=== captures : ${captured} prises, ${ko.length} en échec${ko.length ? ' : ' + ko.map(k => `${k.lang}/${k.name}`).join(', ') : ''}`)
if (!argv.includes('--keep-servers')) stopAll()
process.exit(ko.length ? 1 : 0)
