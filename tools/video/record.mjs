// Vidéo de démo d'OntoForge (prototype) : parcours filmé par screencast CDP, sous-titres incrustés dans la page, faux curseur.
// Usage : node tools/video/record.mjs [sortie.mp4]     → frames dans journal/L18/video/frames, vidéo assemblée par assemble.py
import { mkdirSync, writeFileSync, rmSync } from 'node:fs'
import path from 'node:path'
import { ROOT, HERE, startServers, newPage, chromium, sleep, stopAll, mouse, startCapture, caption, chapter } from './lib.mjs'

const OUT = path.join(ROOT, 'journal/L18/video'); const FR = path.join(OUT, 'frames')
rmSync(FR, { recursive: true, force: true }); mkdirSync(FR, { recursive: true })
const srv = await startServers()
// Interface, libellés et assistant en anglais
{ const st = await (await fetch(srv.B + '/settings')).json(); st.language = { ...(st.language || {}), ui: 'en', labels: 'en', assistant: 'en' }
  const r = await fetch(srv.B + '/settings', { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify(st) }); if (!r.ok) console.log('réglages langue refusés', r.status, (await r.text()).slice(0, 200)) }
const browser = await chromium.launch()
const { page, errs } = await newPage(browser, srv)
const m = mouse(page)
const log = []; const t0 = Date.now()
const step = async (name, fn) => { const s = Date.now(); try { await fn(); log.push(`OK  ${name} (${((Date.now() - s) / 1000).toFixed(1)} s)`) } catch (e) { log.push(`KO  ${name} :: ${String(e).split('\n')[0]}`); console.log('KO', name, String(e).split('\n')[0]) } }
const nav = name => m.click(page.locator('nav button, aside button').filter({ hasText: new RegExp('^' + name) }).first())
const cap = async (html, hold = 0) => { await caption(page, html); if (hold) await sleep(hold) }
const card = q => page.goto(`${srv.base}/__video/card.html?${new URLSearchParams(q)}`)

// Prépare la page avant de filmer (polices, cache)
await page.goto(srv.base + '/#/'); await sleep(1200)
await card({ pose: 'accueil', kick: 'Prototype · iteration 2', sub: 'From an OWL 2 / SHACL ontology to a ready-to-use Curiosity or Neo4j property graph.', chips: 'Design|Check|Transpose|Generate' })
await sleep(600)
const capture = await startCapture(page)
const marks = []; const mark = n => marks.push({ n, t: Date.now() / 1000 })

await step('carte titre', async () => { mark('titre'); await sleep(6500) })

await step('création du projet', async () => {
  mark('projet'); await page.goto(srv.base + '/#/'); await sleep(900)
  await chapter(page, '1 · Design')
  await cap('Start from a sample: <b>car maintenance</b> (24 classes, SHACL shapes, test data).')
  await m.type(page.getByPlaceholder('E.g. Fleet maintenance'), 'Car maintenance demo', { delay: 55 })
  await m.to(page.locator('select').first()); await page.locator('select').first().selectOption({ label: /automaint/i }).catch(async () => {
    const v = await page.locator('select').first().evaluate(s => [...s.options].find(o => /automaint/i.test(o.text))?.value); await page.locator('select').first().selectOption(v) })
  await sleep(700)
  await m.click(page.getByRole('button', { name: 'Create project' }))
  await page.waitForURL(/#\/projet\//, { timeout: 15000 }); await sleep(800)
  await cap('The <b>dashboard</b> tracks the four stages and suggests the next action.', 4200)
})

await step('éditeur graphique', async () => {
  mark('editeur'); await nav('Ontology'); await sleep(1500)
  await cap('The ontology is drawn in an <b>interactive graph</b>: classes, subclasses, relations.', 2200)
  await m.click(page.locator('button.nm', { hasText: /^Vehicle$/ }).first()); await sleep(2200)
})

await step('Krakie ajoute une classe', async () => {
  mark('krakie')
  await cap('<b>Krakie</b>, the assistant, is on every screen and knows what you are looking at.')
  await m.click(page.locator('button.ag-fab')); await sleep(900)
  const box = page.locator('textarea').last()
  await m.click(box); await page.keyboard.type('add the class Tyre under Part with a property pressure in bar', { delay: 38 }); await sleep(400)
  await page.keyboard.press('Enter')
  const apply = page.getByRole('button', { name: /^Apply/ }).last()
  await apply.waitFor({ timeout: 15000 }); await sleep(900)
  await cap('It <b>proposes</b>, you <b>approve</b>: nothing changes without your click.', 1600)
  await m.click(apply); await sleep(1500)
  await page.keyboard.press('Escape').catch(() => {})
  const close = page.locator('[aria-label="Close"], button[title="Close"]').last(); if (await close.isVisible().catch(() => false)) await m.click(close)
  await sleep(500)
  const pneu = page.locator('button.nm', { hasText: /^Tyre$/ }).first()
  if (await pneu.isVisible().catch(() => false)) await m.click(pneu)
  await cap('The <b>Tyre</b> class and its <b>pressure (bar)</b> property are in the model; Ctrl+Z to undo.', 3000)
})

await step('vue liste', async () => {
  mark('liste'); await nav('List view'); await sleep(1300)
  const item = page.getByText(/^Repair order$/i).first(); await m.click(item); await sleep(800)
  await cap('The <b>list view</b> details each class: properties, cardinalities, keys, restrictions in plain words.', 3600)
  await page.mouse.wheel(0, 380); await sleep(1800); await page.mouse.wheel(0, -380); await sleep(500)
})

await step('conformité', async () => {
  mark('conformite'); await chapter(page, '2 · Check'); await nav('Conformance'); await sleep(1300)
  await cap('Check: <b>W3C</b> conformance, OWL 2 DL / EL / QL / RL profiles and best practices.', 3800)
})

await step('validation SHACL', async () => {
  mark('shacl'); await nav('SHACL'); await sleep(1200)
  const tab = page.getByRole('button', { name: 'Data validation' }); if (await tab.isVisible().catch(() => false)) await m.click(tab)
  await sleep(600)
  await cap('<b>SHACL</b> shapes validate real data: every violation is explained.')
  await m.to(page.locator('label.btn', { hasText: 'Choose a file' })); await sleep(250); await page.mouse.down(); await sleep(70); await page.mouse.up()
  await page.locator('[data-testid=valid-file]').setInputFiles(path.join(ROOT, 'samples/automaint/automaint-data.ttl'))
  await page.getByText(/violations? in/).first().waitFor({ timeout: 15000 }).catch(() => console.log('pas de résultat SHACL'))
  await sleep(1200); await page.mouse.move(800, 500); await page.mouse.wheel(0, 260); await sleep(3000)
})

await step('analyse et arbitrage', async () => {
  mark('analyse'); await chapter(page, '3 · Transpose'); await nav('Analysis'); await sleep(1500)
  await cap('Transpose to <b>Curiosity</b>: the trivial parts map automatically, what gets lost is flagged.', 3000)
  await page.mouse.move(700, 500); await page.mouse.wheel(0, 300); await sleep(1600)
  await cap('Each finding comes with options and a <b>recommendation</b> for the target; you decide.', 1500)
  await page.mouse.wheel(0, -300); await sleep(500)
  await m.click(page.getByRole('button', { name: 'Accept all recommendations' })); await sleep(2600)
})

await step('modèle cible', async () => {
  mark('modele'); await nav('Target model'); await sleep(1800)
  await cap('The resulting <b>property graph model</b>: node types, keys, paired edges.', 3800)
})

await step('exports', async () => {
  mark('exports'); await chapter(page, '4 · Generate'); await nav('Exports')
  await cap('Generate: the <b>Curiosity</b> schema in C#, the connector, the transposition report.'); await sleep(1200)
  await m.click(page.locator('button').filter({ hasText: /^\s*Schema\.cs\s*$/ }).first()); await sleep(3000)
  await m.click(page.getByRole('button', { name: 'Neo4j', exact: true })); await sleep(1800)
  await cap('One click to switch to <b>Neo4j</b>: Cypher constraints, ingestion, GraphQL.')
  const cy = page.getByText('schema.cypher', { exact: true }).first(); await cy.waitFor({ timeout: 6000 }).catch(() => {}); if (await cy.isVisible().catch(() => false)) await m.click(cy)
  await sleep(3000)
  await m.click(page.getByRole('button', { name: 'Curiosity', exact: true })); await sleep(800)
})

await step('requêtes', async () => {
  mark('requetes'); await chapter(page, 'Query'); await nav('Queries'); await sleep(1400)
  await cap('A plain-English question becomes a <b>guided query</b> you can edit block by block.')
  await m.type(page.getByPlaceholder(/Ask your question/), 'vehicles whose fuel is Diesel', { delay: 45 })
  await m.click(page.getByRole('button', { name: 'Ask', exact: true })); await sleep(2800)
  await cap('Plug in a <b>temporary SPARQL endpoint</b>, no trip to the settings.')
  const sel = page.locator('select').filter({ hasText: /Temporary endpoint/i }).first()
  await m.to(sel); const v = await sel.evaluate(s => [...s.options].find(o => /temporary/i.test(o.text))?.value); await sel.selectOption(v); await sleep(900)
  const url = page.getByPlaceholder('https://…/sparql').first()
  await m.click(url); await page.keyboard.type(srv.sparql, { delay: 18 }); await sleep(400)
  await m.click(page.getByRole('button', { name: /^Use$/ }).first()); await sleep(1200)
  await m.click(page.getByRole('button', { name: 'Run', exact: true }))
  await page.getByText(/row\(s\)/).first().waitFor({ timeout: 12000 }).catch(() => console.log('pas de résultats'))
  await cap('<b>Diesel vehicles</b>, as a table or a graph, with SPARQL, Cypher and the Curiosity query side by side.')
  await page.evaluate(() => { const h = [...document.querySelectorAll('h2,h3,b,strong,span')].find(e => e.textContent.trim() === 'Results'); h && h.scrollIntoView({ behavior: 'smooth', block: 'start' }) }); await sleep(3200)
  const g = page.locator('button, [role=tab]').filter({ hasText: /^\s*Graph\s*$/ }).last(); if (await g.isVisible().catch(() => false)) { await m.click(g); await sleep(3600) }
  await page.mouse.wheel(0, -520); await sleep(400)
})

await step('visite guidée', async () => {
  mark('visite'); await chapter(page, 'Getting started')
  await cap('And a <b>guided tour</b>: Krakie walks through every screen, highlighting what matters.')
  await m.click(page.locator('header button:has(.fa-route), button[aria-label="Guided tour"], button[title="Guided tour"]').first()); await sleep(1400); await cap(''); await chapter(page, ''); await sleep(1600)
  for (const i of [1, 10, 15]) { await page.evaluate(n => window.ontoforgeTour.goto(n), i); await sleep(3600) }
  await page.evaluate(() => window.ontoforgeTour.stop()); await sleep(600)
  await cap(''); await chapter(page, '')
})

await step('carte de fin', async () => {
  mark('fin'); await card({ pose: 'contente', kick: 'Prototype · your turn', sub: 'Design, check, transpose, generate: an ontology becomes a ready-to-use graph.', chips: 'Curiosity|Neo4j|SHACL|Krakie' })
  await sleep(6500)
})

const tEnd = Date.now() / 1000
await capture.stop(); await sleep(300)
const frames = capture.frames
frames.forEach((f, i) => writeFileSync(path.join(FR, String(i).padStart(5, '0') + '.jpg'), Buffer.from(f.data, 'base64')))
const lines = []
for (let i = 0; i < frames.length; i++) {
  const d = Math.max(1 / 60, ((i + 1 < frames.length ? frames[i + 1].t : tEnd) - frames[i].t))
  lines.push(`file 'frames/${String(i).padStart(5, '0')}.jpg'`, `duration ${d.toFixed(4)}`)
}
lines.push(`file 'frames/${String(frames.length - 1).padStart(5, '0')}.jpg'`)
writeFileSync(path.join(OUT, 'frames.txt'), lines.join('\n') + '\n')
writeFileSync(path.join(OUT, 'marks.json'), JSON.stringify({ start: frames[0]?.t, end: tEnd, marks }, null, 1))
console.log(log.join('\n')); console.log(`${frames.length} images, ${(tEnd - frames[0].t).toFixed(1)} s, erreurs page : ${errs.length}`, errs.slice(0, 3))
await browser.close(); stopAll(); process.exit(0)
