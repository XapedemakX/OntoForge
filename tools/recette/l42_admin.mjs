// Recette L42 : administration des comptes, langue par compte, administrateur sur tous les projets, lecteur sans génération.
// Usage : BACKEND_PORT=8997 FRONT_PORT=4997 node tools/recette/l42_admin.mjs   (front déjà buildé : cd frontend && npm run build)
// Démarre un backend temporaire (authentification activée, mock) et un petit serveur de front (comme l40_partage.mjs), puis : alice (administratrice,
// compte de la configuration) crée « carol » (mot de passe provisoire affiché une fois), carol se connecte, change son mot de passe, choisit l'anglais
// (interface en anglais pour elle seule), alice voit le projet de carol (trace « en tant qu'administrateur »), bob (lecteur) n'a pas de bouton de génération.
// Captures (fr / en, clair / sombre) : journal/L42/screens/.
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
const SHOTS = path.join(ROOT, 'journal/L42/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8997, FP = process.env.FRONT_PORT || 4997
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
const data = mkdtempSync(path.join(tmpdir(), 'of-l42-'))
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

// ouvre un navigateur connecté ; la langue d'interface est celle du COMPTE (L42) : on la fixe par l'API quand elle diffère
const open = async (who, pw, { locale = 'fr-FR', scheme = 'light', lang = 'fr', vp = { width: 1360, height: 820 }, setLang = true } = {}) => {
  const ctx = await browser.newContext({ viewport: vp, locale, colorScheme: scheme, deviceScaleFactor: 1 })
  await ctx.addInitScript(l => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.setItem('ontoforge.lang', l) } catch {} }, lang)
  const page = await ctx.newPage()
  page.on('pageerror', e => errs.push(`${who} pageerror: ` + String(e).slice(0, 200)))
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(`${who} console: ` + m.text().slice(0, 200)) })
  await page.goto(base + '/', { waitUntil: 'load' })
  await page.waitForSelector('[data-testid=login]')
  await page.fill('[data-testid=login-user]', who); await page.fill('[data-testid=login-password]', pw); await page.click('[data-testid=login-submit]')
  await page.waitForSelector('[data-testid=logout], [data-testid=change-password]', { timeout: 10000 })
  if (setLang && await page.locator('[data-testid=logout]').count()) {
    const cur = await page.evaluate(() => document.documentElement.lang)
    if (cur !== lang) { await fetchJ(page, 'PUT', '/api/auth/preferences', { lang }); await page.reload(); await page.waitForSelector('[data-testid=logout]') }
  }
  return { ctx, page }
}
const calm = async page => { try { await page.waitForFunction(() => document.querySelectorAll('.toast').length === 0, null, { timeout: 7000 }) } catch {} await sleep(150) }
const shot = async (page, name) => { await calm(page); await page.screenshot({ path: path.join(SHOTS, name + '.png') }) }
const cards = page => page.locator('.proj-grid .proj h2').allInnerTexts()
const fetchJ = (page, method, url, body, headers = {}) => page.evaluate(async ([m, u, b, h]) => {
  const r = await fetch(u, { method: m, headers: { 'Content-Type': 'application/json', ...h }, body: b === undefined ? undefined : JSON.stringify(b) })
  return { status: r.status, json: await r.json().catch(() => null) }
}, [method, url, body, headers])
const NEWPW = 'rc-' + randomBytes(9).toString('hex')

const A = await open('alice', PW.alice), B = await open('bob', PW.bob)
await sleep(500)

// 1. administration : seuls les administrateurs la voient
log('alice (admin) : entrée « Administration » dans le menu', (await A.page.locator('.side-foot button', { hasText: 'Administration' }).count()) === 1)
log('bob (non admin) : pas d\'entrée « Administration » ni de bouton admin dans son menu de compte', (await B.page.locator('.side-foot button', { hasText: 'Administration' }).count()) === 0)
await B.page.click('[data-testid=account-menu]')
log('bob : menu du compte sans lien d\'administration', (await B.page.locator('[data-testid=account-admin]').count()) === 0 && (await B.page.locator('[data-testid=account-lang]').count()) === 1)
await B.page.keyboard.press('Escape')
await B.page.goto(`${base}/#/administration`); await B.page.waitForSelector('[data-testid=admin-denied]')
log('bob : écran d\'administration refusé', true)
log('bob : API d\'administration refusée (403)', (await fetchJ(B.page, 'GET', '/api/admin/accounts')).status === 403)
await B.page.goto(`${base}/#/`)
await A.page.goto(`${base}/#/administration`); await A.page.waitForSelector('[data-testid=adm-table]')
const rowTxt = async l => (await A.page.locator(`[data-testid=adm-row-${l}]`).innerText()).replace(/\s+/g, ' ')
log('liste : alice et bob « gérés par la configuration », sans désactivation ni suppression (L43 : mot de passe réinitialisable)', /Géré par la configuration/.test(await rowTxt('bob')) && (await A.page.locator('[data-testid=adm-toggle-bob], [data-testid=adm-delete-bob], [data-testid=adm-admin-bob]').count()) === 0 && /Administrateur/.test(await rowTxt('alice')))
await shot(A.page, '01-admin-comptes-fr-clair')

// 2. création de carol : mot de passe provisoire affiché une seule fois
await A.page.fill('[data-testid=adm-login]', 'carol'); await A.page.click('[data-testid=adm-create]')
await A.page.waitForSelector('[data-testid=adm-prov-pw]')
const prov = (await A.page.locator('[data-testid=adm-prov-pw]').innerText()).trim()
log('carol créée : mot de passe provisoire généré et affiché', prov.length >= 16 && /Mot de passe à changer/.test(await rowTxt('carol')), prov.length + ' caractères')
await shot(A.page, '02-mot-de-passe-provisoire-fr-clair')
await A.page.click('[data-testid=adm-prov-close]')
log('le mot de passe provisoire ne se réaffiche pas', (await A.page.locator('[data-testid=adm-prov-pw]').count()) === 0 && !(await A.page.content()).includes(prov))
await A.page.reload(); await A.page.waitForSelector('[data-testid=adm-table]')
log('après rechargement : introuvable dans la page', !(await A.page.content()).includes(prov))

// 3. carol se connecte avec le provisoire : écran de changement obligatoire
const C = await open('carol', prov)
await C.page.waitForSelector('[data-testid=change-password]')
log('carol : écran « Choisissez votre mot de passe » avant tout autre écran', (await C.page.locator('[data-testid=logout]').count()) === 0)
const early = await fetchJ(C.page, 'GET', '/api/projects')
log('carol : l\'API refuse tout tant que le mot de passe provisoire n\'est pas changé (403)', early.status === 403 && early.json?.code === 'password_change_required')
await C.page.fill('[data-testid=pw-current]', prov); await C.page.fill('[data-testid=pw-new]', 'court'); await C.page.fill('[data-testid=pw-confirm]', 'court')
log('carol : 10 caractères au moins (bouton inactif)', await C.page.locator('[data-testid=pw-submit]').isDisabled())
await shot(C.page, '03-changer-mot-de-passe-fr-clair')
await C.page.fill('[data-testid=pw-new]', NEWPW); await C.page.fill('[data-testid=pw-confirm]', NEWPW); await C.page.click('[data-testid=pw-submit]')
await C.page.waitForSelector('[data-testid=logout]', { timeout: 10000 })
log('carol : mot de passe changé, accès à l\'application', /Projets/.test(await C.page.locator('h1').first().innerText()))

// 4. carol choisit l'anglais : interface en anglais pour elle seule
await C.page.click('[data-testid=account-menu]'); await C.page.waitForSelector('[data-testid=account-pop]')
await C.page.selectOption('[data-testid=account-lang]', 'en'); await sleep(500)
log('carol : interface en anglais', /^Projects$/.test((await C.page.locator('h1').first().innerText()).trim()) && (await C.page.evaluate(() => document.documentElement.lang)) === 'en')
await shot(C.page, '04-langue-compte-en-clair')
await C.page.keyboard.press('Escape'); await C.page.reload(); await C.page.waitForSelector('[data-testid=logout]'); await sleep(300)
log('carol : choix conservé après rechargement (enregistré côté serveur)', /^Projects$/.test((await C.page.locator('h1').first().innerText()).trim()))
await A.page.goto(`${base}/#/`); await A.page.reload(); await A.page.waitForSelector('.proj-grid, .empty-state')
log('alice reste en français', /^Projets$/.test((await A.page.locator('h1').first().innerText()).trim()))
log('bob reste en français', /Projets/.test(await B.page.locator('h1').first().innerText()))
const errEn = await fetchJ(C.page, 'GET', '/api/projects/introuvable')
const errFr = await fetchJ(A.page, 'GET', '/api/projects/introuvable')
log('messages du serveur dans la langue de chaque compte', /not found/.test(errEn.json?.detail) && /introuvable/.test(errFr.json?.detail))

// 5. carol crée un projet ; alice (admin) le voit et agit dessus
const pid = (await fetchJ(C.page, 'POST', '/api/projects', { name: 'Carol workshop', sample: 'automaint' })).json.id
log('carol crée un projet', !!pid, pid)
await B.page.reload(); await B.page.waitForSelector('.proj-grid, .empty-state')
log('bob ne voit pas le projet de carol (404 direct)', !(await cards(B.page)).includes('Carol workshop') && (await fetchJ(B.page, 'GET', `/api/projects/${pid}`)).status === 404)
await A.page.reload(); await A.page.waitForSelector('.proj-grid .proj')
log('alice voit le projet de carol, propriétaire carol, badge administrateur', (await cards(A.page)).includes('Carol workshop')
  && /carol/.test(await A.page.locator('.proj', { hasText: 'Carol workshop' }).locator('[data-testid=proj-owner]').innerText())
  && (await A.page.locator('.proj', { hasText: 'Carol workshop' }).locator('[data-testid=proj-admin]').count()) === 1)
await A.page.click('[data-testid=proj-scope] >> text=Mes projets')
log('filtre « Mes projets » : le projet de carol disparaît', !(await cards(A.page)).includes('Carol workshop'))
await A.page.click('[data-testid=proj-scope] >> text=Tous')
log('filtre « Tous » : il revient', (await cards(A.page)).includes('Carol workshop'))
await shot(A.page, '05-admin-voit-tous-les-projets-fr-clair')
await A.page.locator('.proj', { hasText: 'Carol workshop' }).click()
await A.page.waitForFunction(() => /\/tableau/.test(location.hash)); await A.page.waitForSelector('.dash')
const cur = (await fetchJ(A.page, 'GET', `/api/projects/${pid}`)).json
const put = await fetchJ(A.page, 'PUT', `/api/projects/${pid}`, { ...cur, notes: 'relu par l\'administratrice' })
log('alice modifie le projet de carol (droits du propriétaire)', put.status === 200)
await A.page.reload(); await A.page.waitForSelector('[data-testid=activity]'); await sleep(400)
log('journal du projet : « en tant qu\'administrateur »', (await A.page.locator('[data-testid=as-admin]').count()) >= 1 && /alice/.test(await A.page.locator('[data-testid=activity]').innerText()))
await shot(A.page, '06-activite-en-tant-qu-admin-fr-clair')

// 6. bob, lecteur : pas de génération
await fetchJ(C.page, 'POST', `/api/projects/${pid}/access/members`, { login: 'bob', role: 'reader' })
await B.page.goto(`${base}/#/projet/${pid}/tableau`); await B.page.waitForSelector('[data-testid=readonly-chip]'); await sleep(900)
log('bob (lecteur) : bouton de génération désactivé « lecture seule »', await B.page.locator('[data-testid=gen-btn]').isDisabled() && /Lecture seule/.test((await B.page.locator('[data-testid=gen-btn]').getAttribute('title')) || ''))
await shot(B.page, '07-lecteur-sans-generation-fr-clair')
await B.page.goto(`${base}/#/projet/${pid}/exports`); await B.page.waitForSelector('[data-testid=gen-readonly]'); await sleep(500)
log('bob : écran Exports en lecture seule, boutons désactivés', (await B.page.locator('.page-head .btn[data-write]').evaluateAll(b => b.map(x => x.disabled))).every(Boolean))
const g = await fetchJ(B.page, 'GET', `/api/projects/${pid}/generate/curiosity`)
log('bob : génération refusée par le serveur (403)', g.status === 403 && g.json?.code === 'read_only')
log('bob : l\'export de l\'existant reste possible', (await fetchJ(B.page, 'GET', `/api/projects/${pid}/export/ontology`)).status === 200)
await shot(B.page, '08-exports-lecture-seule-fr-clair')
await fetchJ(C.page, 'POST', `/api/projects/${pid}/access/members`, { login: 'bob', role: 'editor' })
await B.page.goto(`${base}/#/projet/${pid}/tableau`); await B.page.reload(); await B.page.waitForSelector('.dash'); await sleep(900)
log('bob passé éditeur : il peut générer', !(await B.page.locator('[data-testid=gen-btn]').isDisabled()) && (await fetchJ(B.page, 'GET', `/api/projects/${pid}/generate/curiosity`)).status === 200)
await fetchJ(C.page, 'DELETE', `/api/projects/${pid}/access/members/bob`)

// 7. désactivation : la session de carol est coupée tout de suite ; réactivation ; journal
await A.page.goto(`${base}/#/administration`); await A.page.waitForSelector('[data-testid=adm-table]')
await A.page.click('[data-testid=adm-toggle-carol]'); await sleep(500)
log('alice désactive carol', /Non/.test(await rowTxt('carol')))
const dead = await fetchJ(C.page, 'GET', '/api/projects')
log('session de carol coupée immédiatement (401)', dead.status === 401)
await C.page.reload(); await C.page.waitForSelector('[data-testid=login]')
await C.page.fill('[data-testid=login-user]', 'carol'); await C.page.fill('[data-testid=login-password]', NEWPW); await C.page.click('[data-testid=login-submit]')
await C.page.waitForSelector('[data-testid=login-msg]:not(:empty)'); await sleep(300)
log('carol désactivée ne peut pas se reconnecter', (await C.page.locator('[data-testid=logout]').count()) === 0)
await A.page.click('[data-testid=adm-toggle-carol]'); await sleep(500)
log('alice réactive carol', /Oui/.test(await rowTxt('carol')))
await A.page.click('[data-testid=adm-admin-carol]'); await sleep(400)
log('promotion puis rétrogradation', /Administrateur/.test(await rowTxt('carol')))
await A.page.click('[data-testid=adm-admin-carol]'); await sleep(400)
await A.page.click('[data-testid=adm-reset-carol]'); await A.page.click('[data-testid=adm-reset-yes]'); await A.page.waitForSelector('[data-testid=adm-prov-pw]')
const prov2 = (await A.page.locator('[data-testid=adm-prov-pw]').innerText()).trim()
log('réinitialisation : nouveau provisoire différent', prov2.length >= 16 && prov2 !== prov)
await A.page.click('[data-testid=adm-prov-close]')
await A.page.click('[data-testid=adm-delete-carol]'); await A.page.waitForSelector('[data-testid=adm-ask-delete]')
log('suppression : choix du compte qui reçoit ses projets', (await A.page.locator('[data-testid=adm-transfer]').count()) === 1)
await A.page.selectOption('[data-testid=adm-transfer]', 'bob'); await A.page.click('[data-testid=adm-delete-yes]'); await sleep(600)
log('carol supprimée, son projet transféré à bob', (await A.page.locator('[data-testid=adm-row-carol]').count()) === 0 && (await fetchJ(B.page, 'GET', `/api/projects/${pid}/access`)).json?.owner === 'bob')
await A.page.click('[role=tab]:has-text("Journal d\'administration")'); await A.page.waitForSelector('[data-testid=adm-audit]')
const aud = await A.page.locator('[data-testid=adm-audit]').innerText()
log('journal d\'administration : actions tracées, aucun mot de passe', /a créé le compte/.test(aud) && /a supprimé le compte/.test(aud) && !aud.includes(prov) && !aud.includes(prov2) && !aud.includes(NEWPW))
await shot(A.page, '09-journal-admin-fr-clair')
await A.ctx.close(); await B.ctx.close(); await C.ctx.close()

// 8. captures fr / en, clair / sombre : comptes (admin), liste des projets (admin), menu du compte
for (const [lang, locale] of [['fr', 'fr-FR'], ['en', 'en-US']]) for (const scheme of ['light', 'dark']) {
  const tag = `${lang}-${scheme === 'light' ? 'clair' : 'sombre'}`
  const A2 = await open('alice', PW.alice, { locale, lang, scheme })
  const dn = 'dora-' + lang + scheme[0]
  await A2.page.goto(`${base}/#/administration`); await A2.page.waitForSelector('[data-testid=adm-table]')
  await A2.page.fill('[data-testid=adm-login]', dn); await A2.page.click('[data-testid=adm-create]'); await A2.page.waitForSelector('[data-testid=adm-prov-pw]'); await sleep(300)
  log(`administration des comptes (${tag})`, new RegExp(lang === 'fr' ? 'Administration › Comptes' : 'Administration › Accounts').test(await A2.page.locator('h1').first().innerText()))
  await shot(A2.page, `10-admin-comptes-${tag}`)
  await A2.page.goto(`${base}/#/`); await A2.page.reload(); await A2.page.waitForSelector('.proj-grid .proj')
  await A2.page.click('[data-testid=account-menu]'); await A2.page.waitForSelector('[data-testid=account-pop]'); await sleep(200)
  log(`menu du compte (${tag})`, (await A2.page.locator('[data-testid=account-lang]').inputValue()) === lang)
  await shot(A2.page, `11-menu-compte-${tag}`)
  await A2.page.keyboard.press('Escape'); await A2.page.mouse.click(5, 400)
  if (scheme === 'light') await shot(A2.page, `12-liste-admin-${tag}`)
  await A2.ctx.close()
}
// alice remet sa langue (le compte garde son choix)
const Z = await open('alice', PW.alice); await fetchJ(Z.page, 'PUT', '/api/auth/preferences', { lang: 'fr' }); await Z.ctx.close()

log('aucune erreur de console ou de page', errs.length === 0, errs.slice(0, 3).join(' | '))
await browser.close()
console.log(ko ? `\n${ko} échec(s)` : '\nRecette L42 : tout est vert')
process.exit(ko ? 1 : 0)
