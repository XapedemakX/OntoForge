// L22 : parcours Playwright de l'écran Fichiers (diagnostic en direct, diff, application, synchronisation avec le graphe, annulation, mobile).
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
const SHOTS = path.join(ROOT, 'journal/L22/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = 8932, FP = 4932
const NS = 'https://w3id.org/ontoforge/automaint#'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (c, a, o) => { const p = spawn(c, a, { stdio: 'ignore', ...o }); procs.push(p); return p }
run('/home/claude/venv/bin/python', ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'],
  { cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: mkdtempSync(path.join(tmpdir(), 'of-l22-')), ONTOFORGE_LLM_PROVIDER: 'mock' } })
run('npx', ['vite', 'preview', '--port', String(FP), '--strictPort'], { cwd: path.join(ROOT, 'frontend'), env: { ...process.env, ONTOFORGE_API: `http://127.0.0.1:${BP}` } })
const B = `http://127.0.0.1:${BP}/api`, base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(B + '/health')).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }
const pid = (await (await fetch(B + '/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'l22', sample: 'automaint' }) })).json()).id
const out = []; const ok = (n, c, d = '') => { out.push(c); console.log((c ? 'OK  ' : 'KO  ') + n + ' ' + d) }
const hasClass = async () => Object.keys((await (await fetch(`${B}/projects/${pid}`)).json()).onto.classes).includes(NS + 'Pneu')
const browser = await chromium.launch()
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 860 }, locale: 'fr-FR' })
  await ctx.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1') } catch {} })
  await ctx.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  const page = await ctx.newPage()
  const errs = []; page.on('pageerror', e => errs.push(String(e))); page.on('console', m => { if (m.type() === 'error') errs.push(m.text()) })
  await page.goto(`${base}/#/projet/${pid}/fichiers`)
  await page.waitForSelector('.fx .cm-content', { timeout: 20000 })
  await page.waitForSelector('[data-testid="fx-valid"]:not(:has-text("Validation"))', { timeout: 15000 })
  ok('onto.ttl ouvert, arborescence et onglet', await page.locator('.fx-tab.on').innerText().then(x => /onto\.ttl/.test(x)) && await page.locator('.fx-file').count() >= 4)
  ok('fichiers générés présents et verrouillés', await page.locator('.fx-file .lk').count() > 0)
  const original = await page.locator('.cm-content').innerText()
  ok('préfixe am: conservé (peu d\'IRI complètes)', /@prefix am:/.test(original) && (original.match(/<https:\/\/w3id\.org\/ontoforge\/automaint#/g) ?? []).length < 10)
  // 1. erreur de syntaxe
  await page.locator('.cm-content').click(); await page.keyboard.press('Control+End')
  await page.keyboard.insertText('\nfoo:Bar a .\n')
  await page.waitForSelector('.cm-lintRange-error', { timeout: 8000 })
  await page.waitForSelector('.fx-plist .sv-error')
  const msg = await page.locator('.fx-plist .sv-error').first().innerText()
  ok('diagnostic d\'erreur souligné et listé', /Turtle/.test(msg), msg.replace(/\n/g, ' | '))
  ok('barre d\'état : erreur', /erreur/.test(await page.locator('[data-testid="fx-valid"]').innerText()))
  await page.screenshot({ path: `${SHOTS}/01-erreur-diagnostic.png` })
  await page.click('.fx-plist .sv-error'); await sleep(200)
  ok('clic sur le problème : curseur sur la ligne', /Ligne \d+/.test(await page.locator('[data-testid="fx-pos"]').innerText()))
  await page.keyboard.press('Control+s'); await sleep(500)
  ok('Ctrl+S refusé tant que la syntaxe est invalide', await page.locator('.fx-modal').count() === 0)
  await sleep(3800) // laisse s'effacer le message d'avertissement
  // 2. correction
  await page.locator('.cm-content').click(); await page.keyboard.press('Control+z')
  await page.waitForFunction(() => !document.querySelector('.cm-lintRange-error'), null, { timeout: 8000 })
  await page.waitForSelector('[data-testid="fx-valid"]:has-text("Valide")', { timeout: 8000 })
  ok('erreur corrigée : validation verte', true)
  // 3. ajout d'une classe en Turtle
  await page.keyboard.press('Control+End')
  await page.keyboard.insertText(`\n# Ajout de l'utilisateur : le pneu\n<${NS}Pneu> a <http://www.w3.org/2002/07/owl#Class> ;\n    <http://www.w3.org/2000/01/rdf-schema#label> "Pneu"@fr .\n`)
  await page.waitForSelector('[data-testid="fx-valid"]:has-text("Valide")', { timeout: 8000 }); await sleep(700)
  await page.keyboard.press('Control+s')
  await page.waitForSelector('.fx-modal [data-testid="fx-summary"]', { timeout: 8000 }); await sleep(400)
  const sum = await page.locator('[data-testid="fx-summary"]').innerText()
  ok('diff : résumé +N triplets / -M triplets', /\+\d+ triplets \/ −\d+ triplets/.test(sum), sum)
  ok('diff : vue côte à côte', await page.locator('.fx-diff .cm-mergeView').count() === 1)
  ok('diff : commentaires conservés, annoncés', await page.locator('[data-testid="fx-comments-kept"]').count() === 1 && await page.locator('[data-testid="fx-comments-lost"]').count() === 0)
  ok('diff : aucune réécriture à l\'import', await page.locator('[data-testid="fx-rewritten"]').count() === 0)
  await page.screenshot({ path: `${SHOTS}/02-diff-avant-application.png` })
  await page.click('.fx-modal >> text=Appliquer'); await page.waitForSelector('[data-testid="fx-applied"]')
  ok('classe appliquée côté serveur', await hasClass())
  ok('texte saisi (commentaire) relu tel quel', /Ajout de l'utilisateur/.test(await (await fetch(`${B}/projects/${pid}/files/onto.ttl`)).json().then(j => j.content)))
  // 3b. réécriture à l'import : AllDisjointClasses n-aire -> avertissement chiffré, commentaires supprimés
  await page.locator('.cm-content').click(); await page.keyboard.press('Control+End')
  await page.keyboard.insertText(`\n# commentaire voué à disparaître\n[] a <http://www.w3.org/2002/07/owl#AllDisjointClasses> ; <http://www.w3.org/2002/07/owl#members> ( <${NS}Pneu> <${NS}Vehicle> <${NS}Brand> ) .\n`)
  await page.waitForSelector('[data-testid="fx-valid"]:not(:has-text("Validation"))', { timeout: 8000 }); await sleep(700)
  await page.keyboard.press('Control+s')
  await page.waitForSelector('.fx-modal [data-testid="fx-comments-lost"]', { timeout: 8000 }); await sleep(400)
  const lost = await page.locator('[data-testid="fx-comments-lost"]').innerText()
  ok('diff : avertissement chiffré « supprimées »', /\d+ ligne\(s\) de commentaire seront supprimées/.test(lost), lost.slice(0, 60))
  ok('diff : réécritures listées et dépliées', await page.locator('[data-testid="fx-rewritten"][open]').count() === 1, await page.locator('[data-testid="fx-rewritten"] summary').innerText())
  await page.screenshot({ path: `${SHOTS}/02b-diff-commentaires-supprimes.png` })
  await page.click('.fx-modal >> text=Annuler'); await page.keyboard.press('Control+z'); await sleep(300)
  // 4. synchronisation : le graphe voit la classe
  await page.goto(`${base}/#/projet/${pid}/ontologie`); await page.reload()
  await page.waitForSelector('.react-flow__node', { timeout: 20000 })
  await page.waitForSelector('.react-flow__node:has-text("Pneu")', { timeout: 10000 }).catch(() => {})
  ok('Pneu visible dans l\'éditeur graphique', await page.locator('.react-flow__node', { hasText: 'Pneu' }).count() > 0)
  await sleep(500); await page.screenshot({ path: `${SHOTS}/03-graphe-apres-application.png` })
  // 5. annulation depuis l'écran Fichiers
  await page.goto(`${base}/#/projet/${pid}/fichiers`); await page.reload()
  await page.waitForSelector('.fx .cm-content', { timeout: 20000 })
  await page.getByRole('button', { name: 'Revenir à la version précédente' }).first().click()
  await sleep(800)
  ok('annulation : classe retirée', !(await hasClass()))
  ok('annulation : l\'éditeur est rechargé', !(await page.locator('.cm-content').innerText()).includes('Pneu'))
  ok('annulation : note « forme normalisée »', await page.locator('[data-testid="fx-canon-note"]').count() === 1)
  await page.screenshot({ path: `${SHOTS}/04-annulation-texte-canonique.png` })
  // 6. fichier généré en lecture seule
  await page.getByRole('button', { name: 'Schema.cs', exact: true }).click(); await page.waitForSelector('.fx-banner.gen')
  ok('fichier généré : bandeau lecture seule, pas de bouton Appliquer', await page.getByRole('button', { name: 'Appliquer' }).count() === 0)
  // 7. mobile : lecture seule
  const m = await (await browser.newContext({ viewport: { width: 390, height: 800 }, locale: 'fr-FR' })).newPage()
  await m.route(`${base}/api/**`, route => route.continue({ url: route.request().url().replace(base, `http://127.0.0.1:${BP}`) }))
  await m.goto(`${base}/#/projet/${pid}/fichiers`); await m.waitForSelector('.fx .cm-content', { timeout: 20000 })
  ok('mobile : lecture seule', await m.getByRole('button', { name: 'Appliquer' }).count() === 0 && (await m.locator('.cm-content').getAttribute('contenteditable')) === 'false')
  ok('aucune erreur console', errs.length === 0, errs.slice(0, 3).join(' || '))
} catch (e) { out.push(false); console.log('KO  exception ' + e) }
finally { await browser.close(); procs.forEach(p => p.kill()) }
console.log(`\n${out.filter(Boolean).length}/${out.length}`)
process.exit(out.every(Boolean) ? 0 : 1)
