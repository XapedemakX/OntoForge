// Recette « version anglaise » : repère tout texte visible qui semble français quand les réglages sont language {ui,labels,assistant} = en.
// Usage : node tools/recette/english_scan.mjs   (BACKEND_PORT=8951, FRONT_PORT=4951 optionnels ; front déjà buildé : cd frontend && npm run build)
// Parcourt : Projets, Paramètres, tous les écrans d'un projet automaint (+ onglets), Assistant (message anglais), Requêtes (question anglaise),
// panneau Krakie (button.ag-fab) et visite guidée complète. Sortie : une ligne par texte suspect (écran | sélecteur | texte), code 1 s'il en reste.
import { createRequire } from 'node:module'
import { spawn } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const BP = process.env.BACKEND_PORT || 8951, FP = process.env.FRONT_PORT || 4951
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
const stop = () => procs.forEach(p => p.kill())
process.on('exit', stop)

// Exceptions justifiées (texte exact ou regex) : données utilisateur ou noms propres qui ressemblent à du français.
const EXCEPTIONS = [
  // aucune pour l'instant
]
const i18nPrefixes = [...new Set(Object.keys(JSON.parse(readFileSync(path.join(ROOT, 'frontend/src/i18n/fr.json'), 'utf8'))).map(k => k.split('.')[0]))]

run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-en-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
const base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const J = { 'content-type': 'application/json' }
const put = await fetch(B + '/settings', { method: 'PUT', headers: J, body: JSON.stringify({ language: { ui: 'en', labels: 'en', assistant: 'en' } }) })
if (!put.ok) { console.error('PUT /settings KO', put.status); process.exit(2) }
const proj = await (await fetch(B + '/projects', { method: 'POST', headers: J, body: JSON.stringify({ name: 'english-scan', sample: 'automaint' }) })).json()
const pid = proj.id
await fetch(`${B}/projects/${pid}/analyze?target=curiosity`, { method: 'POST' })
await fetch(`${B}/projects/${pid}/decisions/curiosity/accept-recommended`, { method: 'POST' })

// ----------------------------------------------------------------------------- détection (exécutée dans la page)
const SCAN = ({ prefixes }) => {
  const ACCENT = /[éèàçùêâîôûëïüœ]/i
  const WORDS = new Set(['le', 'la', 'les', 'des', 'du', 'une', 'et', 'pour', 'avec', 'aucun', 'aucune', 'propriété', 'propriétés', 'dans', 'sur', 'est', 'sont',
    'pas', 'cette', 'ces', 'vos', 'votre', 'vous', 'nous', 'ajouter', 'ajoute', 'supprimer', 'modifier', 'ouvrir', 'fermer', 'enregistrer', 'annuler', 'valeur', 'valeurs', 'ontologie',
    'obligatoire', 'optionnel', 'optionnelle', 'texte', 'nombre', 'entier', 'chaîne', 'chaine', 'tous', 'toutes', 'plus', 'moins', 'sans', 'ou', 'où', 'qui', 'que',
    'dont', 'chez', 'sous', 'vers', 'entre', 'depuis', 'aussi', 'déjà', 'voici', 'ici', 'projet', 'projets', 'ouvrez', 'créer', 'créez', 'choisir', 'choisissez', 'lancer', 'aide', 'recherche',
    'résultat', 'résultats', 'erreur', 'chargement', 'nom', 'au', 'aux', 'ce', 'son', 'sa', 'ses', 'leur', 'leurs', 'peut', 'peuvent', 'doit', 'être', 'avoir', 'un', 'mon', 'mes', 'ma'])
  // mots qu'on ne retient que s'ils sont accompagnés d'au moins un autre mot français (ambigus avec l'anglais ou des noms propres)
  const WEAK = new Set(['ou', 'un', 'au', 'ce', 'son', 'sa', 'plus', 'sans', 'est', 'sur', 'ici', 'nom', 'texte', 'relation', 'relations', 'aide', 'dont', 'que', 'qui', 'nombre', 'valeur', 'valeurs'])
  const skipTag = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'CODE', 'PRE', 'TEXTAREA', 'SVG'])
  const skipSel = '.cm-editor, pre, code, [data-user-content], svg'
  const cssPath = el => {
    const parts = []
    for (let e = el, n = 0; e && e.nodeType === 1 && e !== document.body && n < 5; e = e.parentElement, n++) {
      let s = e.tagName.toLowerCase()
      if (e.id) { parts.unshift(s + '#' + e.id); break }
      const dt = e.getAttribute('data-tour'); if (dt) s += `[data-tour="${dt}"]`
      const cls = [...e.classList].filter(c => !/^(css-|_)/.test(c)).slice(0, 2); if (cls.length) s += '.' + cls.join('.')
      parts.unshift(s)
    }
    return parts.join(' > ')
  }
  const visible = el => {
    if (!el.getClientRects().length) return false
    const cs = getComputedStyle(el)
    return cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0'
  }
  const looksLikeIri = s => /^\S*[#\/]\S*$/.test(s) || /^[A-Za-z][\w.-]*:[\w.-]+$/.test(s) || /^https?:/.test(s)
  const frenchReason = raw => {
    const s = raw.replace(/\s+/g, ' ').trim()
    if (s.length < 2 || looksLikeIri(s)) return null
    if (/^[a-z]+(\.[A-Za-z0-9_-]+)+$/.test(s) && prefixes.includes(s.split('.')[0])) return 'clé i18n brute'
    if (ACCENT.test(s)) return 'accent'
    const toks = s.toLowerCase().split(/[^a-zàâçéèêëîïôûùüÿœ']+/).flatMap(w => w.includes("'") ? [w, w.split("'").pop()] : [w]).filter(Boolean)
    const hits = toks.filter(w => WORDS.has(w))
    const strong = hits.filter(w => !WEAK.has(w))
    if (strong.length) return 'mot français : ' + [...new Set(strong)].slice(0, 4).join(', ')
    if (hits.length >= 2) return 'mots français : ' + [...new Set(hits)].slice(0, 4).join(', ')
    return null
  }
  const out = []
  const push = (text, el, kind) => { const why = frenchReason(text); if (why) out.push({ text: text.replace(/\s+/g, ' ').trim().slice(0, 160), selector: cssPath(el), why, kind }) }
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const el = n.parentElement
    if (!el || skipTag.has(el.tagName) || el.closest(skipSel) || !visible(el)) continue
    push(n.nodeValue || '', el, 'texte')
  }
  for (const el of document.body.querySelectorAll('[placeholder],[title],[aria-label],[alt]')) {
    if (el.closest(skipSel) || !visible(el)) continue
    for (const a of ['placeholder', 'title', 'aria-label', 'alt']) { const v = el.getAttribute(a); if (v) push(v, el, a) }
  }
  for (const el of document.body.querySelectorAll('input[type=button],input[type=submit],option')) { if (visible(el) || el.tagName === 'OPTION') push(el.value || el.textContent || '', el, 'valeur') }
  return out
}

// ----------------------------------------------------------------------------- navigation
const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'en-US' })
await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
const page = await ctx.newPage()
const found = new Map() // clé texte|sélecteur -> { screens:Set, ... }
let scanned = 0
async function scan(screen) {
  scanned++
  let hits = []
  try { hits = await page.evaluate(SCAN, { prefixes: i18nPrefixes }) } catch (e) { console.error('scan KO ' + screen + ' : ' + String(e).slice(0, 120)); return }
  for (const h of hits) {
    if (EXCEPTIONS.some(x => (x instanceof RegExp ? x.test(h.text) : x === h.text))) continue
    const k = h.text + '\u0000' + h.selector
    if (!found.has(k)) found.set(k, { ...h, screens: new Set() })
    found.get(k).screens.add(screen)
  }
}
const go = async hash => { await page.goto(base + '/' + hash, { waitUntil: 'load' }); await page.reload({ waitUntil: 'load' }); await sleep(1800) }
async function scanTabs(screen) {
  await scan(screen)
  for (const sel of ['[role=tab]', 'details > summary']) {
    const n = await page.locator(sel).count()
    for (let i = 0; i < Math.min(n, 12); i++) {
      try { await page.locator(sel).nth(i).click({ timeout: 1000 }); await sleep(500); await scan(`${screen} [${sel}#${i}]`) } catch { /* non cliquable */ }
    }
  }
}
const screens = ['tableau', 'ontologie', 'ontologie-liste', 'shapes', 'conformite', 'shacl', 'analyse', 'modele', 'exports', 'requetes', 'assistant']
await go('#/'); await scanTabs('projets')
await go('#/parametres'); await scanTabs('parametres')
for (const sc of screens) { await go(`#/projet/${pid}/${sc}`); await scanTabs(sc) }
// éditeur : sélection d'un nœud (inspecteur) et champ de saisie rapide
await go(`#/projet/${pid}/ontologie`)
try { await page.locator('.react-flow__node').first().click(); await sleep(600); await scan('ontologie (nœud sélectionné)') } catch {}
// requêtes : question anglaise
await go(`#/projet/${pid}/requetes`)
try {
  const inp = page.getByPlaceholder(/question/i).first()
  if (await inp.count()) { await inp.fill('vehicles whose fuel is Diesel'); await page.keyboard.press('Enter'); await sleep(2500); await scanTabs('requetes (question anglaise)') }
} catch {}
// assistant (écran) : messages anglais
await go(`#/projet/${pid}/assistant`)
for (const msg of ['add the class Tyre under Part with a property pressure in bar', 'make licensePlate required', 'open the shapes']) {
  try { const ta = page.locator('textarea').first(); await ta.fill(msg); await page.keyboard.press('Enter'); await sleep(2500); await scan('assistant : ' + msg) } catch {}
}
// panneau Krakie
await go(`#/projet/${pid}/ontologie`)
try {
  await page.locator('button.ag-fab').click(); await sleep(900); await scan('krakie (ouvert)')
  const ta = page.locator('.ag-dock textarea, .ag-panel textarea, [class*=ag-] textarea').first()
  if (await ta.count()) { await ta.fill('add the class Tyre under Part with a property pressure in bar'); await page.keyboard.press('Enter'); await sleep(3000); await scan('krakie (réponse)') }
} catch (e) { console.error('Krakie KO : ' + String(e).slice(0, 120)) }
// visite guidée complète
await go(`#/projet/${pid}/tableau`)
await page.evaluate(() => window.ontoforgeTour.start())
for (let i = 0; i < 40; i++) {
  let s
  for (let k = 0; k < 60; k++) { s = await page.evaluate(() => window.ontoforgeTour.state()); if (!s.active || (s.index === i && s.ready)) break; await sleep(100) }
  if (!s.active) break
  await sleep(500); await scan(`visite ${i + 1}/${s.total} (${s.id})`)
  await page.evaluate(() => window.ontoforgeTour.next())
}
await browser.close(); stop()

// ----------------------------------------------------------------------------- rapport
const list = [...found.values()]
for (const h of list) console.log(`FR  [${[...h.screens][0]}${h.screens.size > 1 ? ` +${h.screens.size - 1}` : ''}] ${h.selector}\n      « ${h.text} » (${h.kind}, ${h.why})`)
console.log(`\n=== ${scanned} vues scannées, ${list.length} texte(s) suspect(s) de français, ${EXCEPTIONS.length} exception(s) déclarée(s)`)
process.exit(list.length ? 1 : 0)
