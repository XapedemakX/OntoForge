// Recette L26 : légende, notation VOWL, filtres et export du graphe. Usage : node tools/recette/l26_legend.mjs   (BACKEND_PORT, FRONT_PORT optionnels ; front déjà buildé)
// Démarre un backend temporaire (mock) + `vite preview`, crée un projet automaint enrichi (classe externe, équivalence, union, propriété sans image…),
// ouvre la légende dans les deux modes, applique filtres et densité, exporte SVG et PNG, vérifie les fichiers, puis rejoue l'essentiel en anglais.
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { mkdtempSync, mkdirSync, readFileSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L26/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8926, FP = process.env.FRONT_PORT || 4926
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const report = []
const log = (name, ok, detail = '') => { report.push({ name, ok }); console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l26-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const NS = 'https://w3id.org/ontoforge/automaint#'
const proj = await (await fetch(B + '/projects', { method: 'POST', headers: J, body: JSON.stringify({ name: 'automaint', sample: 'automaint' }) })).json()
const pid = proj.id
{ // enrichissement : tous les encodages présents dans la vue
  const o = (await (await fetch(`${B}/projects/${pid}`)).json()).onto
  const c = n => o.classes[NS + n]
  c('Recall').deprecated = true
  c('Vehicle').annotations.push({ property: 'urn:ontoforge:abstract', value: 'true', is_iri: false })
  c('Person').sub_class_of.push('http://xmlns.com/foaf/0.1/Agent')
  c('Brand').equivalent_to = [{ op: 'named', iri: 'http://schema.org/Brand' }]
  c('Party').equivalent_to = [{ op: 'or', args: [{ op: 'named', iri: NS + 'Person' }, { op: 'named', iri: NS + 'Organization' }] }]
  c('Technician').disjoint_with = [NS + 'Customer']
  o.object_properties[NS + 'assignedTo'].characteristics = ['functional']
  const r = await fetch(`${B}/projects/${pid}/onto`, { method: 'PUT', headers: J, body: JSON.stringify(o) })
  if (!r.ok) throw new Error('PUT onto ' + r.status + ' ' + (await r.text()))
  const ops = await (await fetch(`${B}/projects/${pid}/ops`, { method: 'POST', headers: J, body: JSON.stringify({ ops: [
    { op: 'add_object_property', iri: NS + 'owns', label: 'possède', lang: 'fr', domain: NS + 'Customer', range: NS + 'Vehicle', inverse_of: NS + 'ownedBy' },
    { op: 'add_object_property', iri: NS + 'relatedTo', label: 'lié à', lang: 'fr', domain: NS + 'Part' },
    { op: 'set_label', iri: NS + 'owns', text: 'owns', lang: 'en' }, { op: 'set_label', iri: NS + 'relatedTo', text: 'related to', lang: 'en' },
  ] }) })).json()
  if (!ops.ok) throw new Error('ops ' + JSON.stringify(ops.errors))
}
const browser = await chromium.launch()
async function session(vp, opts = {}) {
  const ctx = await browser.newContext({ viewport: vp, locale: opts.locale || 'fr-FR', colorScheme: opts.dark ? 'dark' : 'light', acceptDownloads: true })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1') } catch {} })
  if (opts.proposal) await ctx.addInitScript(p => { try { localStorage.setItem('ontoforge.proposal', JSON.stringify(p)) } catch {} }, opts.proposal)
  const page = await ctx.newPage(); const errs = []
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 200)) })
  page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 200)))
  page.on('response', r => { if (r.status() >= 500 || (r.status() >= 400 && r.url().includes('/api/') && ![404, 409].includes(r.status()))) errs.push(`HTTP ${r.status()} ${r.url().replace(base, '')}`) })
  return { ctx, page, errs }
}
const shot = (s, name) => s.page.screenshot({ path: path.join(SHOTS, name + '.png') })
const open = async s => { await s.page.goto(`${base}/#/projet/${pid}/ontologie`, { waitUntil: 'load' }); await s.page.reload({ waitUntil: 'load' }); await s.page.waitForSelector('.react-flow__node', { timeout: 15000 }).catch(async e => { await s.page.screenshot({ path: path.join(SHOTS, 'debug.png') }); console.log(s.errs.slice(0, 5), (await s.page.locator('body').innerText()).slice(0, 300)); throw e }); await sleep(1200) }
const step = async (name, s, fn) => { const b = s.errs.length; try { const d = await fn(); const e = s.errs.slice(b); log(name, e.length === 0, (d || '') + (e.length ? ' ' + JSON.stringify(e.slice(0, 3)) : '')) } catch (err) { log(name, false, 'EXCEPTION ' + String(err).slice(0, 260)) } }
const renderSvg = async (file, name) => { // affiche le fichier exporté dans une page nue (le SVG seul, hors application) et le photographie
  const p = await (await browser.newContext({ viewport: { width: 1500, height: 1000 } })).newPage()
  await p.setContent(`<body style="margin:0"><img id="x" style="max-width:1500px;display:block" src="data:image/svg+xml;base64,${readFileSync(file).toString('base64')}"></body>`); await sleep(400)
  await p.locator('#x').screenshot({ path: path.join(SHOTS, name + '.png') }); await p.context().close()
}
const legendIds = s => s.page.$$eval('[data-legend]', els => els.map(e => e.getAttribute('data-legend')))
const counter = s => s.page.locator('[data-testid=counter]').innerText()
const nums = t => (t.match(/\d+/g) || []).map(Number)
// la légende s'ouvre seule au premier usage (repliée sous 900 px) : on l'ouvre et la déplie si besoin, sans la refermer
const ensureLegend = async s => {
  if (!(await s.page.locator('[data-testid=legend-panel]').count())) { await s.page.locator('[data-testid=legend-btn]').click(); await sleep(300) }
  if (!(await s.page.locator('.of-lg-body').count())) { await s.page.locator('[data-testid=legend-panel] header button').first().click(); await sleep(300) }
}

// ===================================================================== français, clair
const d = await session({ width: 1440, height: 900 })
await open(d)
await step('L1 classique : légende ouverte au premier usage, bouton présent, fermeture mémorisée', d, async () => {
  if (!(await d.page.locator('[data-testid=legend-panel] .of-lg-body').count())) throw new Error('légende non ouverte au premier usage')
  if (!(await d.page.locator('[data-testid=legend-btn]').count())) throw new Error('bouton absent')
  await d.page.locator('[data-testid=legend-btn]').click(); await sleep(200)
  await d.page.reload(); await d.page.waitForSelector('.react-flow__node'); await sleep(600)
  if (await d.page.locator('[data-testid=legend-panel]').count()) throw new Error('fermeture non mémorisée'); return 'ok'
})
await step('L2 classique : ouverture, entrées présentes seulement', d, async () => {
  await d.page.locator('[data-testid=legend-btn]').click(); await sleep(400)
  const ids = await legendIds(d); await shot(d, '01-classique-legende')
  const must = ['c-class', 'c-sub', 'c-obj', 'c-inv', 'c-disj', 'c-abstract', 'c-dep', 'c-err', 'c-sel']
  const miss = must.filter(x => !ids.includes(x)); if (miss.length) throw new Error('manquantes ' + miss)
  if (ids.some(x => x.startsWith('v-'))) throw new Error('entrées VOWL en mode classique')
  if (ids.includes('c-add') || ids.includes('c-mod')) throw new Error('états de proposition sans proposition')
  return ids.length + ' entrées : ' + ids.join(' ')
})
await step('L3 classique : état mémorisé après rechargement', d, async () => {
  await d.page.reload(); await d.page.waitForSelector('.react-flow__node'); await sleep(800)
  const st = await d.page.evaluate(() => localStorage.getItem('ontoforge.ed.legend'))
  if (!(await d.page.locator('[data-testid=legend-panel]').count())) throw new Error('légende refermée après rechargement'); return 'legend=' + st
})
await step('L4 replier / déplier / fermer la légende', d, async () => {
  await d.page.getByRole('button', { name: 'Replier la légende' }).click(); await sleep(200)
  const folded = await d.page.locator('.of-lg-body').count(); await d.page.getByRole('button', { name: 'Déplier la légende' }).click(); await sleep(200)
  const open = await d.page.locator('.of-lg-body').count(); if (folded !== 0 || open !== 1) throw new Error(`folded=${folded} open=${open}`); return 'ok'
})
await step('V1 mode VOWL : sélecteur, persistance, cercles', d, async () => {
  await d.page.getByRole('button', { name: 'Notation VOWL' }).click(); await d.page.waitForSelector('.of-vn', { timeout: 10000 }); await sleep(1800)
  const dt0 = await d.page.locator('.of-vn.vk-datatype').count(); await shot(d, '02a-vowl-defaut')
  await d.page.locator('[data-testid=show-btn]').click(); const was = await d.page.locator('[data-testid=show-dt]').isChecked(); await d.page.locator('[data-testid=show-dt]').check(); await d.page.keyboard.press('Escape'); await sleep(1500)
  if (dt0 !== 0 || was) throw new Error(`types de données affichés d'emblée sur un grand graphe (dt=${dt0}, case=${was})`)
  const m = await d.page.evaluate(() => localStorage.getItem('ontoforge.ed.mode')); const n = await d.page.locator('.of-vn.vk-class').count()
  if (m !== 'vowl' || n < 20) throw new Error(`mode=${m} classes=${n}`)
  await shot(d, '02-vowl-legende'); return `${n} classes en cercles`
})
await step('V2 VOWL : légende suit le mode, nouveautés présentes', d, async () => {
  const ids = await legendIds(d); if (ids.some(x => x.startsWith('c-') && !['c-'].includes(x[0]) )) throw new Error('entrée classique en VOWL')
  const must = ['v-class', 'v-ext', 'v-dep', 'v-eq', 'v-thing', 'v-or', 'v-dt', 'v-sub', 'v-obj', 'v-inv', 'v-chars', 'v-dp', 'v-disj', 'v-anon', 'v-abs', 'v-err', 'v-sel']
  const miss = must.filter(x => !ids.includes(x)); if (miss.length) throw new Error('manquantes ' + miss + ' / présentes ' + ids)
  if (ids.some(x => x.startsWith('c-'))) throw new Error('entrée classique en VOWL'); return ids.length + ' entrées'
})
await step('V3 VOWL : le mode survit au rechargement', d, async () => {
  await d.page.reload(); await d.page.waitForSelector('.of-vn', { timeout: 10000 }); await sleep(800)
  if (!(await d.page.locator('.ed.vowl').count())) throw new Error('mode perdu'); return 'ok'
})
await step('V6 VOWL : noms de classes lisibles en vue d\'ensemble (≥ 10 px à l\'écran) et masqués sous 30 %', d, async () => {
  await d.page.locator('.react-flow__controls-fitview').click(); await sleep(700)
  const r = await d.page.evaluate(() => {
    const z = new DOMMatrixReadOnly(getComputedStyle(document.querySelector('.react-flow__viewport')).transform).a
    const px = [...document.querySelectorAll('.of-vn.vk-class .vt b')].map(b => parseFloat(getComputedStyle(b).fontSize) * z)
    return { z, min: Math.min(...px), n: px.length }
  })
  await shot(d, '03c-vowl-ensemble-lisible')
  if (r.min < 10) throw new Error(`zoom ${r.z.toFixed(2)} : police ${r.min.toFixed(1)} px à l'écran`)
  await d.page.evaluate(() => { const vp = document.querySelector('.react-flow__pane'); vp.dispatchEvent(new WheelEvent('wheel', { deltaY: 900, clientX: 900, clientY: 500, bubbles: true })) }); await sleep(500)
  const z2 = await d.page.evaluate(() => new DOMMatrixReadOnly(getComputedStyle(document.querySelector('.react-flow__viewport')).transform).a)
  const tiny = await d.page.locator('.of-vn.tiny').count()
  if (z2 < 0.3 && tiny === 0) throw new Error('libellés non masqués sous 30 %')
  await d.page.locator('.react-flow__controls-fitview').click(); await sleep(500)
  return `zoom ${(r.z * 100).toFixed(0)} %, ${r.n} noms, police mini ${r.min.toFixed(1)} px ; zoom ${(z2 * 100).toFixed(0)} % → ${tiny} masqués`
})
await step('V4 VOWL : sélection, inspecteur, glisser pour créer', d, async () => {
  await d.page.getByRole('button', { name: 'Replier la légende' }).click(); await sleep(200)
  // deux classes déclarées dont le centre n'est recouvert par rien (mini-carte, contrôles, légende)
  const ids = await d.page.evaluate(() => [...document.querySelectorAll('.react-flow__node:has(.of-vn.vk-class)')].filter(n => {
    const r = n.getBoundingClientRect(); const e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return n.contains(e) && r.x > 480 && r.y > 150 && r.right < 1200 && r.bottom < 650
  }).map(n => n.getAttribute('data-id')))
  if (ids.length < 2) throw new Error('moins de deux classes accessibles : ' + ids.length)
  const src = d.page.locator(`.react-flow__node[data-id="${ids[0]}"]`); const tgt = d.page.locator(`.react-flow__node[data-id="${ids[1]}"]`)
  await src.click(); await sleep(700)
  if (!(await d.page.locator('[data-tour=ed-inspector] .of-insp-h').count())) throw new Error('inspecteur absent')
  await src.hover(); const h = await src.locator('.of-handle').boundingBox(); const t = await tgt.boundingBox()
  if (!h || !t) throw new Error('poignée ou cible introuvable')
  await d.page.mouse.move(h.x + h.width / 2, h.y + h.height / 2); await d.page.mouse.down(); await d.page.mouse.move(t.x + t.width / 2, t.y + t.height / 2, { steps: 12 }); await d.page.mouse.up(); await sleep(500)
  const menu = await d.page.locator('.of-menu').count(); await shot(d, '03-vowl-menu-creation'); await d.page.keyboard.press('Escape'); await sleep(200)
  await d.page.getByRole('button', { name: 'Déplier la légende' }).click(); await sleep(200)
  if (!menu) throw new Error('menu de création absent'); return `sélection + menu de création OK (${ids[0].split('#')[1]} → ${ids[1].split('#')[1]})`
})
await step('V5 VOWL : propriété objet sélectionnable (clic sur son libellé)', d, async () => {
  for (let i = 0; i < 3; i++) await d.page.locator('.react-flow__controls-zoomin').click()
  await sleep(500); await shot(d, '03b-vowl-zoom')
  await d.page.locator('.of-vl.objectProperty').first().click({ force: true }); await sleep(500)
  const t = await d.page.locator('[data-tour=ed-inspector]').innerText(); return t.split('\n')[0]
})
await step('F1 menu Afficher : propriétés de données, compteur', d, async () => {
  const before = nums(await counter(d)); const dt0 = await d.page.locator('.of-vn.vk-datatype').count()
  await d.page.locator('[data-testid=show-btn]').click(); await sleep(300); await shot(d, '04-menu-afficher')
  await d.page.locator('[data-testid=show-dt]').uncheck(); await sleep(700)
  const after = nums(await counter(d)); const dt1 = await d.page.locator('.of-vn.vk-datatype').count()
  if (!(dt0 > 0 && dt1 === 0 && after[0] < before[0] && after[1] < before[1] && after[2] === before[2])) throw new Error(`dt ${dt0}→${dt1} compteur ${before}→${after}`)
  await d.page.locator('[data-testid=show-dt]').check(); await sleep(500); return `${dt0} types de données masqués puis rétablis ; ${await counter(d)}`
})
await step('F2 filtres : sous-classes, relations, disjonctions, dépréciées', d, async () => {
  await sleep(800)
  const cls = () => d.page.locator('.react-flow__edge').count()
  const e0 = await cls()
  await d.page.locator('[data-testid=show-sub]').uncheck(); await sleep(500); const e1 = await cls()
  await d.page.locator('[data-testid=show-sub]').check()
  await d.page.locator('[data-testid=show-rel]').uncheck(); await sleep(500); const e2 = await cls()
  await d.page.locator('[data-testid=show-rel]').check()
  const dis0 = await d.page.locator('.of-edge.disjointWith').count(); await d.page.locator('[data-testid=show-disj]').uncheck(); await sleep(500); const dis1 = await d.page.locator('.of-edge.disjointWith').count(); const eq1 = await d.page.locator('.of-vn.eq').count()
  await d.page.locator('[data-testid=show-disj]').check(); await sleep(500)
  const n0 = await d.page.locator('.of-vn.vk-class').count(); await d.page.locator('[data-testid=show-dep]').uncheck(); await sleep(500); const n1 = await d.page.locator('.of-vn.vk-class').count()
  const depLeft = await d.page.locator('.of-vn.deprecated').count(); await d.page.locator('[data-testid=show-dep]').check(); await sleep(400)
  if (!(e1 < e0 && e2 < e0 && dis0 > 0 && dis1 === 0 && eq1 === 0 && n1 === n0 - 1 && depLeft === 0)) throw new Error(`arêtes ${e0}/${e1}/${e2} disj ${dis0}→${dis1} éq ${eq1} classes ${n0}→${n1} dépréciées ${depLeft}`)
  return `arêtes ${e0} → ${e1} (sans sous-classes) / ${e2} (sans relations) ; classes ${n0} → ${n1} sans dépréciées`
})
await step('F3 densité : replie les nœuds de degré ≤ N', d, async () => {
  const n0 = await d.page.locator('.of-vn.vk-class').count()
  await d.page.locator('[data-testid=density]').fill('2'); await sleep(900)
  const n2 = await d.page.locator('.of-vn.vk-class').count(); const badge = await d.page.locator('.of-hid').count(); const txt = await counter(d)
  await shot(d, '05-vowl-densite'); const legend = await legendIds(d)
  if (!(n2 < n0 && badge > 0)) throw new Error(`classes ${n0}→${n2} badges ${badge}`)
  if (!legend.includes('v-hid')) throw new Error('légende sans entrée « voisines repliées »')
  await d.page.locator('[data-testid=density]').fill('0'); await sleep(700)
  if ((await d.page.locator('.of-vn.vk-class').count()) !== n0) throw new Error('densité 0 ne rétablit pas'); return `${n0} → ${n2} classes ; ${txt}`
})
await step('F4 filtres mémorisés après rechargement', d, async () => {
  await d.page.locator('[data-testid=show-krakie]').uncheck(); await d.page.keyboard.press('Escape'); await d.page.reload(); await d.page.waitForSelector('.of-vn'); await sleep(600)
  await d.page.locator('[data-testid=show-btn]').click(); const checked = await d.page.locator('[data-testid=show-krakie]').isChecked(); await d.page.locator('[data-testid=show-krakie]').check(); await d.page.keyboard.press('Escape')
  if (checked) throw new Error('filtre non mémorisé'); return 'ok'
})
await step('E1 export SVG (VOWL, légende incluse) : fichier valide avec libellés', d, async () => {
  await d.page.locator('[data-testid=export-btn]').click(); await sleep(300); await shot(d, '06-menu-export')
  const [dl] = await Promise.all([d.page.waitForEvent('download'), d.page.locator('[data-testid=export-svg]').click()])
  const file = path.join(mkdtempSync(path.join(tmpdir(), 'of-svg-')), dl.suggestedFilename()); await dl.saveAs(file)
  const svg = readFileSync(file, 'utf8')
  const parsed = await d.page.evaluate(s => { const doc = new DOMParser().parseFromString(s, 'image/svg+xml'); return { err: !!doc.querySelector('parsererror'), root: doc.documentElement.tagName, texts: [...doc.querySelectorAll('text')].map(t => t.textContent) } }, svg)
  const need = ['Véhicule', 'Garage', 'Personne', 'Légende du graphe', 'Classe', 'Type de données']
  const miss = need.filter(n => !parsed.texts.some(t => t.includes(n)))
  if (parsed.err || parsed.root !== 'svg') throw new Error('SVG invalide')
  if (/var\(--/.test(svg) || /foreignObject/.test(svg) || !/font-family/.test(svg)) throw new Error('styles non en ligne ou polices manquantes')
  if (miss.length) throw new Error('libellés manquants ' + miss)
  await renderSvg(file, '07-export-vowl')
  return `${dl.suggestedFilename()} ${statSync(file).size} o, ${parsed.texts.length} textes`
})
await step('E2 export PNG', d, async () => {
  await d.page.locator('[data-testid=export-btn]').click(); await d.page.locator('[data-testid=export-legend]').uncheck()
  const [dl] = await Promise.all([d.page.waitForEvent('download'), d.page.locator('[data-testid=export-png]').click()])
  const file = path.join(mkdtempSync(path.join(tmpdir(), 'of-png-')), dl.suggestedFilename()); await dl.saveAs(file)
  const b = readFileSync(file); if (!(b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) || b.length < 5000) throw new Error('PNG invalide ' + b.length); return `${dl.suggestedFilename()} ${b.length} o`
})
await step('C1 retour classique : export SVG classique', d, async () => {
  await d.page.keyboard.press('Escape'); await d.page.getByRole('button', { name: 'Classique' }).click(); await d.page.waitForSelector('.of-node', { timeout: 10000 }); await sleep(1200)
  await shot(d, '08-classique-final')
  await d.page.locator('[data-testid=export-btn]').click(); await d.page.locator('[data-testid=export-legend]').check()
  const [dl] = await Promise.all([d.page.waitForEvent('download'), d.page.locator('[data-testid=export-svg]').click()])
  const file = path.join(mkdtempSync(path.join(tmpdir(), 'of-svgc-')), dl.suggestedFilename()); await dl.saveAs(file); const svg = readFileSync(file, 'utf8')
  const ok = await d.page.evaluate(s => !new DOMParser().parseFromString(s, 'image/svg+xml').querySelector('parsererror'), svg)
  if (!ok || !svg.includes('Véhicule')) throw new Error('SVG classique invalide')
  await renderSvg(file, '09-export-classique')
  return dl.suggestedFilename()
})
// proposition de Krakie injectée dans le même stockage que l'assistant (lib/proposal.ts) : une classe ajoutée, une propriété ajoutée, une classe modifiée
const ontoNow = (await (await fetch(`${B}/projects/${pid}`)).json()).onto
const proposal = { projectId: pid, onto: ontoNow, source: 'recette L26', accepted: 0, rejected: 0, busy: false, error: null, items: [
  { id: 'i1', kind: 'add', type: 'class', entity_iri: NS + 'Tyre', label: 'Pneu', ops: [{ op: 'add_class', name: 'Tyre', label: 'Pneu', lang: 'fr' }, { op: 'add_subclass', iri: NS + 'Tyre', parent: NS + 'Part' }] },
  { id: 'i2', kind: 'add', type: 'objectProperty', entity_iri: NS + 'hasTyre', label: 'a pour pneu', source: NS + 'Vehicle', target: NS + 'Tyre', needs: ['i1'], ops: [{ op: 'add_object_property', name: 'hasTyre', label: 'a pour pneu', lang: 'fr', domain: NS + 'Vehicle', range: NS + 'Tyre' }] },
  { id: 'i3', kind: 'modify', type: 'class', entity_iri: NS + 'Garage', label: 'Garage', ops: [{ op: 'set_comment', iri: NS + 'Garage', text: 'Atelier de réparation', lang: 'fr' }] },
] }
const pr = await session({ width: 1600, height: 1000 }, { proposal })
await open(pr)
await step('P1 proposition de Krakie : états « proposé » et « modifié » en classique, en VOWL, dans la légende, masquables', pr, async () => {
  await ensureLegend(pr)
  const c = await pr.page.locator('.of-node.add').count(), cm = await pr.page.locator('.of-node.modify').count(); const lg = await legendIds(pr); await shot(pr, '15-proposition-classique')
  await pr.page.getByRole('button', { name: 'Notation VOWL' }).click(); await sleep(1800)
  const v = await pr.page.locator('.of-vn.add').count(), vm = await pr.page.locator('.of-vn.modify').count(); const lg2 = await legendIds(pr); await shot(pr, '16-proposition-vowl')
  const ghostEdge = await pr.page.locator('.react-flow__edge .of-edge.add').count()
  await pr.page.locator('[data-testid=show-btn]').click(); await pr.page.locator('[data-testid=show-krakie]').uncheck(); await sleep(700)
  const hidden = await pr.page.locator('.of-vn.add').count(), hiddenMod = await pr.page.locator('.of-vn.modify').count(); await pr.page.locator('[data-testid=show-krakie]').check(); await pr.page.keyboard.press('Escape')
  if (!(c === 1 && cm === 1 && lg.includes('c-add') && lg.includes('c-mod') && v === 1 && vm === 1 && lg2.includes('v-add') && lg2.includes('v-mod') && ghostEdge >= 1 && hidden === 0 && hiddenMod === 0))
    throw new Error(`classique add=${c} mod=${cm} légende=${lg.includes('c-add')}/${lg.includes('c-mod')} ; vowl add=${v} mod=${vm} arêtes proposées=${ghostEdge} légende=${lg2.includes('v-add')}/${lg2.includes('v-mod')} ; masquées ${hidden}/${hiddenMod}`)
  return 'classe ajoutée, propriété ajoutée, classe modifiée : visibles dans les deux modes, listées dans la légende, masquables'
})
log('D erreurs navigateur (fr)', d.errs.length === 0, JSON.stringify(d.errs.slice(0, 3)))

// ===================================================================== sombre
const k = await session({ width: 1440, height: 900 }, { dark: true })
await open(k)
await step('K1 thème sombre : VOWL + légende lisibles', k, async () => {
  await ensureLegend(k); await k.page.getByRole('button', { name: 'Notation VOWL' }).click(); await k.page.waitForSelector('.of-vn'); await sleep(1500); await shot(k, '10-sombre-vowl'); return 'capture'
})

// ===================================================================== anglais
await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'en', labels: 'en', assistant: 'en' } }) })
const en = await session({ width: 1440, height: 900 }, { locale: 'en-US' })
await open(en)
const FR = /[éèàçùêâîôûëïüœ]|\b(Légende|Classe|Sous-classe|Afficher|Exporter|nœuds|arêtes|propriété|Disjonction|déprécié|replier)\b/i
await step('A1 anglais : légende classique sans français', en, async () => {
  await ensureLegend(en); await shot(en, '11-en-classique-legende')
  const txt = await en.page.locator('[data-testid=legend-panel]').innerText(); const bar = await en.page.locator('.of-bar').innerText()
  const bad = (txt + '\n' + bar).split('\n').filter(l => FR.test(l)); if (bad.length) throw new Error('français : ' + JSON.stringify(bad.slice(0, 5))); return bar.replace(/\n/g, ' | ').slice(0, 160)
})
await step('A2 anglais : VOWL, légende, menu, export sans français', en, async () => {
  await en.page.getByRole('button', { name: 'VOWL notation' }).click(); await en.page.waitForSelector('.of-vn'); await sleep(1500)
  await en.page.locator('[data-testid=show-btn]').click(); await sleep(300)
  const menu = await en.page.locator('.of-showmenu').innerText(); await shot(en, '12-en-vowl-menu')
  await en.page.keyboard.press('Escape')
  const txt = await en.page.locator('[data-testid=legend-panel]').innerText(); await shot(en, '13-en-vowl-legende')
  const bad = (txt + '\n' + menu).split('\n').filter(l => FR.test(l)); if (bad.length) throw new Error('français : ' + JSON.stringify(bad.slice(0, 5)))
  await en.page.locator('[data-testid=export-btn]').click()
  const [dl] = await Promise.all([en.page.waitForEvent('download'), en.page.locator('[data-testid=export-svg]').click()])
  const file = path.join(mkdtempSync(path.join(tmpdir(), 'of-svge-')), dl.suggestedFilename()); await dl.saveAs(file); const svg = readFileSync(file, 'utf8')
  const texts = [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(m => m[1]); const badSvg = texts.filter(t => FR.test(t))
  if (badSvg.length || !texts.includes('Graph legend — VOWL notation')) throw new Error('SVG anglais : ' + JSON.stringify(badSvg.slice(0, 5)) + ' / ' + texts.slice(0, 3)); return `${texts.length} textes SVG, aucun français`
})
log('A erreurs navigateur (en)', en.errs.length === 0, JSON.stringify(en.errs.slice(0, 3)))

// ===================================================================== mobile
await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'fr', labels: 'fr', assistant: 'fr' } }) })
const m = await session({ width: 390, height: 844 })
await open(m)
await step('M1 mobile : légende repliée au premier usage, sans débordement', m, async () => {
  if (!(await m.page.locator('[data-testid=legend-panel]').count()) || await m.page.locator('.of-lg-body').count()) throw new Error('attendu : légende repliée sous 900 px')
  await ensureLegend(m); await shot(m, '14-mobile-legende')
  const over = await m.page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2); if (over) throw new Error('débordement horizontal'); return 'ok'
})
await browser.close(); procs.forEach(p => p.kill())
const ko = report.filter(r => !r.ok).length
console.log(`\n=== L26 : ${report.length - ko} OK / ${ko} KO`); process.exit(ko ? 1 : 0)
