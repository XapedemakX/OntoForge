// Recette L40 : projets nominatifs et partage collaboratif, avec deux comptes (alice, administratrice ; bob).
// Usage : BACKEND_PORT=8987 FRONT_PORT=4987 node tools/recette/l40_partage.mjs   (front déjà buildé : cd frontend && npm run build)
// Démarre un backend temporaire (authentification activée, mock) et un petit serveur de front (dist + relais /api qui transmet l'hôte d'origine,
// comme nginx ; `vite preview` réécrit l'hôte et le contrôle d'origine du serveur refuserait la connexion), puis : A crée un projet, B ne le voit pas, A le partage en lecteur,
// B le voit en lecture seule, A passe B éditeur, B modifie, conflit simulé (409, « recharger et réappliquer »), présence des deux côtés, bandeau
// « a modifié le projet », journal d'activité, réglages réservés à l'administrateur, version anglaise. Captures (clair / sombre, fr / en) : journal/L40/screens/.
import { createRequire } from 'node:module'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, existsSync, readFileSync, statSync } from 'node:fs'
import http from 'node:http'
import { randomBytes } from 'node:crypto'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L40/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8987, FP = process.env.FRONT_PORT || 4987
const PY = process.env.PYTHON || '/home/claude/venv/bin/python'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
process.on('exit', () => procs.forEach(p => p.kill()))
let ko = 0
const log = (name, ok, detail = '') => { if (!ok) ko++; console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

// mots de passe de recette tirés au hasard à l'exécution (aucun secret en clair dans le dépôt)
const PW = { alice: 'rc-' + randomBytes(9).toString('hex'), bob: 'rc-' + randomBytes(9).toString('hex') }
const hashOf = u => execFileSync(PY, ['-m', 'ontoforge.auth', 'hash', '--stdin', '--user', u], { cwd: path.join(ROOT, 'backend'), input: PW[u] }).toString().trim()
const secret = execFileSync(PY, ['-m', 'ontoforge.auth', 'secret'], { cwd: path.join(ROOT, 'backend') }).toString().trim()
const data = mkdtempSync(path.join(tmpdir(), 'of-l40-'))
run(PY, ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'], {
  cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: data, ONTOFORGE_LOCAL_STORE_DIR: path.join(data, 'ls'), ONTOFORGE_LLM_PROVIDER: 'mock',
    ONTOFORGE_AUTH: 'password', ONTOFORGE_AUTH_USERS: `${hashOf('alice')};${hashOf('bob')}`, ONTOFORGE_SECRET_KEY: secret, ONTOFORGE_COOKIE_SECURE: '0' } })
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ico': 'image/x-icon', '.md': 'text/markdown', '.webp': 'image/webp' }
const DIST = path.join(ROOT, 'frontend/dist')
const front = http.createServer((req, res) => {
  if (req.url.startsWith('/api/')) {
    const up = http.request({ host: '127.0.0.1', port: BP, path: req.url, method: req.method, headers: { ...req.headers, 'x-forwarded-host': req.headers.host } }, r => { res.writeHead(r.statusCode, r.headers); r.pipe(res) })
    up.on('error', () => { res.writeHead(502); res.end() }); req.pipe(up); return
  }
  let f = path.join(DIST, decodeURIComponent(req.url.split('?')[0]))
  if (!f.startsWith(DIST) || !existsSync(f) || statSync(f).isDirectory()) f = path.join(DIST, 'index.html')
  res.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' }); res.end(readFileSync(f))
}).listen(Number(FP), '127.0.0.1')
process.on('exit', () => front.close())
const base = `http://127.0.0.1:${FP}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(`http://127.0.0.1:${BP}/api/health`)).ok) break } catch {} await sleep(500) }
for (let i = 0; i < 60; i++) { try { if ((await fetch(base)).ok) break } catch {} await sleep(500) }

const browser = await chromium.launch()
const errs = []
const open = async (who, { locale = 'fr-FR', scheme = 'light', lang = 'fr', vp = { width: 1360, height: 820 } } = {}) => {
  const ctx = await browser.newContext({ viewport: vp, locale, colorScheme: scheme, deviceScaleFactor: 1 })
  await ctx.addInitScript(l => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.setItem('ontoforge.lang', l) } catch {} }, lang)
  const page = await ctx.newPage()
  page.on('pageerror', e => errs.push(`${who} pageerror: ` + String(e).slice(0, 200)))
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(`${who} console: ` + m.text().slice(0, 200)) })
  await page.goto(base + '/', { waitUntil: 'load' })
  await page.waitForSelector('[data-testid=login]')
  await page.fill('[data-testid=login-user]', who); await page.fill('[data-testid=login-password]', PW[who]); await page.click('[data-testid=login-submit]')
  await page.waitForSelector('[data-testid=logout]', { timeout: 10000 })
  // L42 : la langue d'interface est celle du compte (côté serveur) ; on la fixe pour la capture
  const cur = await page.evaluate(() => document.documentElement.lang)
  if (cur !== lang) { await page.evaluate(async l => { const csrf = (await (await fetch('/api/auth/session')).json()).csrf; await fetch('/api/auth/preferences', { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ lang: l }) }) }, lang); await page.reload(); await page.waitForSelector('[data-testid=logout]') }
  return { ctx, page }
}
const calm = async page => { try { await page.waitForFunction(() => document.querySelectorAll('.toast').length === 0, null, { timeout: 7000 }) } catch {} await sleep(150) }
const shot = async (page, name) => { await calm(page); await page.screenshot({ path: path.join(SHOTS, name + '.png') }) }
const beat = page => page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')))   // déclenche un battement de présence sans attendre 20 s
const cards = page => page.locator('.proj-grid .proj h2').allInnerTexts()
const fetchJ = (page, method, url, body, headers = {}) => page.evaluate(async ([m, u, b, h]) => {
  const r = await fetch(u, { method: m, headers: { 'Content-Type': 'application/json', ...h }, body: b === undefined ? undefined : JSON.stringify(b) })
  return { status: r.status, json: await r.json().catch(() => null) }
}, [method, url, body, headers])

const A = await open('alice'), B = await open('bob')
await sleep(600)

// 1. A crée un projet nominatif ; B ne le voit pas
await A.page.fill('.page input[type=text]', 'Atelier partagé')
await A.page.selectOption('.page select', 'automaint')
await A.page.click('text=Créer le projet')
await A.page.waitForFunction(() => /#\/projet\/[^/]+\/tableau/.test(location.hash), null, { timeout: 30000 })
const pid = decodeURIComponent(A.page.url().match(/#\/projet\/([^/]+)/)[1])
log('A crée le projet', !!pid, pid)
await B.page.reload(); await B.page.waitForSelector('.proj-grid, .empty-state')
log('B ne voit pas le projet d\'A', !(await cards(B.page)).includes('Atelier partagé'))
const direct = await fetchJ(B.page, 'GET', `/api/projects/${pid}`)
log('B : accès direct par identifiant -> 404', direct.status === 404, String(direct.status))

// 2. A partage en lecteur
await A.page.click('[data-testid=share-btn]')
await A.page.waitForSelector('[data-testid=share-panel]')
await A.page.fill('[data-testid=share-login]', 'inconnu')
await A.page.click('[data-testid=share-add]')
await A.page.waitForSelector('[data-testid=share-error]')
log('identifiant inconnu : message neutre', /compte inconnu, ou déjà propriétaire/.test(await A.page.locator('[data-testid=share-error]').innerText()))
await A.page.fill('[data-testid=share-login]', 'bob'); await A.page.selectOption('[data-testid=share-newrole]', 'reader')
await A.page.click('[data-testid=share-add]')
await A.page.waitForSelector('[data-testid=share-row-bob]')
log('A : bob apparaît dans la liste des accès (lecteur)', (await A.page.locator('[data-testid=share-role-bob]').inputValue()) === 'reader')
await sleep(300); await shot(A.page, '01-partage-panneau-fr-clair')
await A.page.keyboard.press('Escape')

// 3. B voit le projet, en lecture seule
await B.page.reload(); await B.page.waitForSelector('.proj-grid .proj')
log('B voit le projet partagé, badge « Lecture seule » et propriétaire', (await cards(B.page)).includes('Atelier partagé')
  && /Lecture seule/.test(await B.page.locator('[data-testid=proj-shared]').first().innerText()) && /alice/.test(await B.page.locator('[data-testid=proj-owner]').first().innerText()))
await shot(B.page, '02-liste-projets-partages-fr-clair')
await B.page.locator('.proj', { hasText: 'Atelier partagé' }).click()
await B.page.waitForFunction(() => /\/tableau/.test(location.hash)); await B.page.waitForSelector('[data-testid=readonly-chip]')
log('B : mention « lecture seule » dans l\'en-tête', /Lecture seule/.test(await B.page.locator('[data-testid=readonly-chip]').innerText()))
await B.page.goto(`${base}/#/projet/${pid}/ontologie-liste`); await B.page.waitForSelector('.page'); await sleep(900)
const dis = await B.page.evaluate(() => [...document.querySelectorAll('.btn.primary, .btn.danger')].filter(b => !b.closest('[data-safe], .collab-panel')).map(b => b.disabled))
log('B : boutons d\'action désactivés', dis.length > 0 && dis.every(Boolean), `${dis.length} bouton(s)`)
await shot(B.page, '03-lecture-seule-fr-clair')
const put = await fetchJ(B.page, 'PUT', `/api/projects/${pid}`, { name: 'piraté' })
log('B : une écriture directe est refusée par le serveur (403)', put.status === 403 && put.json?.code === 'read_only', String(put.status))
const exp = await fetchJ(B.page, 'GET', `/api/projects/${pid}/export/ontology`)
log('B : l\'export reste possible', exp.status === 200)

// 4. présence des deux côtés
await A.page.goto(`${base}/#/projet/${pid}/tableau`); await A.page.waitForSelector('.dash')
await B.page.goto(`${base}/#/projet/${pid}/tableau`); await B.page.waitForSelector('.dash')
await sleep(700); await beat(A.page); await beat(B.page); await sleep(900); await beat(A.page); await beat(B.page); await sleep(900)
const pa = await A.page.locator('[data-testid=presence] .collab-dot').evaluateAll(e => e.map(x => x.dataset.user).sort())
const pb = await B.page.locator('[data-testid=presence] .collab-dot').evaluateAll(e => e.map(x => x.dataset.user).sort())
log('présence : A voit alice et bob', pa.join() === 'alice,bob', pa.join())
log('présence : B voit alice et bob', pb.join() === 'alice,bob', pb.join())
await shot(A.page, '04-presence-fr-clair')

// 5. A passe B éditeur ; B modifie
await A.page.click('[data-testid=share-btn]'); await A.page.waitForSelector('[data-testid=share-row-bob]')
await A.page.selectOption('[data-testid=share-role-bob]', 'editor'); await sleep(500)
log('A : bob passe éditeur', (await A.page.locator('[data-testid=share-role-bob]').inputValue()) === 'editor')
await A.page.keyboard.press('Escape')
await B.page.goto(`${base}/#/`); await B.page.reload(); await B.page.waitForSelector('.proj-grid .proj')
await B.page.locator('.proj', { hasText: 'Atelier partagé' }).locator('button[aria-label="Renommer"]').click()
await B.page.locator('.proj input[type=text]').fill('Atelier partagé (revu par bob)')
await B.page.click('.proj >> text=Enregistrer')
await B.page.waitForFunction(() => [...document.querySelectorAll('.proj h2')].some(h => /revu par bob/.test(h.textContent || '')), null, { timeout: 8000 })
log('B (éditeur) modifie le projet', true)

// 6. A, resté sur l'ancienne version : bandeau « a modifié », puis conflit à l'enregistrement
await beat(A.page); await A.page.waitForSelector('[data-testid=stale-banner]', { timeout: 8000 })
log('A : bandeau « bob a modifié le projet »', /bob a modifié le projet/.test(await A.page.locator('[data-testid=stale-banner]').innerText()))
await shot(A.page, '05-bandeau-modifie-fr-clair')
await A.page.locator('.seg button', { hasText: 'Neo4j' }).click()   // écriture du projet sur une version périmée
await A.page.waitForSelector('[data-testid=conflict-dialog]')
log('A : conflit 409 expliqué clairement, rien d\'écrasé', /modifié par bob/.test(await A.page.locator('[data-testid=conflict-msg]').innerText())
  && (await fetchJ(A.page, 'GET', `/api/projects/${pid}`)).json.name === 'Atelier partagé (revu par bob)')
await shot(A.page, '06-conflit-fr-clair')
await A.page.click('[data-testid=conflict-reload]'); await A.page.waitForSelector('[data-testid=conflict-dialog]', { state: 'detached' })
log('A : recharger et réappliquer ferme le dialogue, bandeau disparu', (await A.page.locator('[data-testid=stale-banner]').count()) === 0)
await A.page.locator('.seg button', { hasText: 'Neo4j' }).click(); await sleep(700)
log('A : après rechargement l\'enregistrement passe', (await A.page.locator('[data-testid=conflict-dialog]').count()) === 0 && (await fetchJ(A.page, 'GET', `/api/projects/${pid}`)).json.target === 'neo4j')

// 7. journal d'activité
await A.page.goto(`${base}/#/projet/${pid}/tableau`); await A.page.waitForSelector('[data-testid=activity]'); await sleep(500)
const act = await A.page.locator('[data-testid=activity]').innerText()
log('journal : création, partage, changement de rôle, modification par bob', /alice\s+a créé le projet/.test(act) && /a partagé le projet avec bob/.test(act) && /changé le rôle de bob/.test(act) && /bob\s+a modifié le projet/.test(act))
await shot(A.page, '07-activite-fr-clair')

// 8. réglages réservés à l'administrateur
await B.page.goto(`${base}/#/parametres`); await B.page.waitForSelector('[data-testid=settings-locked]')
const st = await fetchJ(B.page, 'PUT', '/api/settings', { language: { ui: 'fr' } })
log('B : réglages verrouillés (avis + 403)', st.status === 403 && st.json?.code === 'admin_only')
await A.page.goto(`${base}/#/parametres`); await A.page.waitForSelector('[data-testid=set-sec-llm]')
log('A (administratrice) : réglages accessibles', (await A.page.locator('[data-testid=settings-locked]').count()) === 0)

// 9. A transfère nulle part : retrait d'accès, B perd le projet
await A.page.goto(`${base}/#/projet/${pid}/tableau`); await A.page.waitForSelector('.dash')
await A.page.click('[data-testid=share-btn]'); await A.page.waitForSelector('[data-testid=share-remove-bob]')
await A.page.click('[data-testid=share-remove-bob]'); await sleep(500)
log('A retire bob : plus de ligne', (await A.page.locator('[data-testid=share-row-bob]').count()) === 0)
log('B : projet à nouveau introuvable', (await fetchJ(B.page, 'GET', `/api/projects/${pid}`)).status === 404)
await A.ctx.close(); await B.ctx.close()

// 10. captures clair / sombre, français / anglais : panneau de partage (A) et lecture seule (B)
for (const [lang, locale] of [['fr', 'fr-FR'], ['en', 'en-US']]) for (const scheme of ['light', 'dark']) {
  const tag = `${lang}-${scheme === 'light' ? 'clair' : 'sombre'}`
  const A2 = await open('alice', { locale, lang, scheme }), B2 = await open('bob', { locale, lang, scheme })
  await fetchJ(A2.page, 'POST', `/api/projects/${pid}/access/members`, { login: 'bob', role: 'reader' })
  await A2.page.goto(`${base}/#/projet/${pid}/tableau`); await A2.page.waitForSelector('.dash')
  await B2.page.goto(`${base}/#/projet/${pid}/tableau`); await B2.page.waitForSelector('[data-testid=readonly-chip]')
  await sleep(500); await beat(A2.page); await beat(B2.page); await sleep(900)
  await A2.page.click('[data-testid=share-btn]'); await A2.page.waitForSelector('[data-testid=share-row-bob]')
  log(`panneau de partage (${tag})`, new RegExp(lang === 'fr' ? 'Partager ce projet' : 'Share this project').test(await A2.page.locator('#collab-title').innerText())
    && new RegExp(lang === 'fr' ? 'Le lecteur consulte' : 'A reader views').test(await A2.page.locator('.collab-rules').innerText()))
  await shot(A2.page, `10-partage-panneau-${tag}`)
  await A2.page.keyboard.press('Escape')
  await B2.page.goto(`${base}/#/projet/${pid}/ontologie-liste`); await B2.page.waitForSelector('[data-testid=readonly-chip]'); await sleep(900)
  log(`lecture seule (${tag})`, new RegExp(lang === 'fr' ? 'Lecture seule' : 'Read-only').test(await B2.page.locator('[data-testid=readonly-chip]').innerText()))
  await shot(B2.page, `11-lecture-seule-${tag}`)
  if (scheme === 'light') { await A2.page.goto(`${base}/#/`); await A2.page.reload(); await A2.page.waitForSelector('.proj-grid .proj'); await shot(A2.page, `12-liste-proprietaire-${tag}`) }
  await fetchJ(A2.page, 'DELETE', `/api/projects/${pid}/access/members/bob`)
  await A2.ctx.close(); await B2.ctx.close()
}

log('aucune erreur de console ou de page', errs.length === 0, errs.slice(0, 3).join(' | '))
await browser.close()
console.log(ko ? `\n${ko} échec(s)` : '\nRecette L40 : tout est vert')
process.exit(ko ? 1 : 0)
