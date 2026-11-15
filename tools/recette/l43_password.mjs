// Recette L43 : changement de mot de passe pour tous les comptes, y compris ceux de la configuration (D-L43-01).
// Usage : BACKEND_PORT=8999 FRONT_PORT=4999 node tools/recette/l43_password.mjs   (front déjà buildé : cd frontend && npm run build)
// Backend temporaire (authentification activée, mock) : alice (administratrice) et carol sont déclarées dans la configuration. Carol change son mot de
// passe depuis le menu du compte, ses autres sessions sont coupées, la courante reste valide, l'ancien mot de passe (celui de la configuration) ne marche
// plus ; l'administratrice voit « mot de passe redéfini dans l'interface », réinitialise, puis revient au mot de passe de la configuration ; une
// modification du hachage de la configuration (redémarrage avec un autre hachage) laisse le masque prioritaire et affiche l'avertissement.
// Captures (fr / en, clair / sombre) : journal/L43/screens/.
import { createRequire } from 'node:module'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, existsSync, readFileSync, statSync, readdirSync } from 'node:fs'
import http from 'node:http'
import { randomBytes } from 'node:crypto'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L43/screens'); mkdirSync(SHOTS, { recursive: true })
const BP = process.env.BACKEND_PORT || 8999, FP = process.env.FRONT_PORT || 4999
const PY = process.env.PYTHON || '/home/claude/venv/bin/python'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const procs = []
const run = (cmd, args, opts) => { const p = spawn(cmd, args, { stdio: 'ignore', ...opts }); procs.push(p); return p }
process.on('exit', () => procs.forEach(p => p.kill()))
let ko = 0
const log = (name, ok, detail = '') => { if (!ok) ko++; console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

// mots de passe de recette tirés au hasard à l'exécution (aucun secret en clair dans le dépôt)
const rnd = () => 'rc-' + randomBytes(9).toString('hex')
const PW = { alice: rnd(), carol: rnd(), carol2: rnd() }   // carol2 : le « nouveau » mot de passe de carol dans la configuration (.env édité)
const hashOf = (key, user = key) => execFileSync(PY, ['-m', 'ontoforge.auth', 'hash', '--stdin', '--user', user], { cwd: path.join(ROOT, 'backend'), input: PW[key] }).toString().trim()
const secret = execFileSync(PY, ['-m', 'ontoforge.auth', 'secret'], { cwd: path.join(ROOT, 'backend') }).toString().trim()
const data = mkdtempSync(path.join(tmpdir(), 'of-l43-'))
let back
const startBackend = async carolKey => {
  back = run(PY, ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(BP), '--log-level', 'warning'], {
    cwd: path.join(ROOT, 'backend'), env: { ...process.env, ONTOFORGE_DATA: data, ONTOFORGE_LOCAL_STORE_DIR: path.join(data, 'ls'), ONTOFORGE_LLM_PROVIDER: 'mock',
      ONTOFORGE_AUTH: 'password', ONTOFORGE_AUTH_USERS: `${hashOf('alice')};${hashOf(carolKey, 'carol')}`, ONTOFORGE_AUTH_ADMINS: 'alice', ONTOFORGE_SECRET_KEY: secret, ONTOFORGE_COOKIE_SECURE: '0' } })
  for (let i = 0; i < 60; i++) { try { if ((await fetch(`http://127.0.0.1:${BP}/api/health`)).ok) return } catch {} await sleep(500) }
}
const stopBackend = async () => { const p = back; p.kill(); await new Promise(r => { p.once('exit', r); setTimeout(r, 4000) }) }
await startBackend('carol')
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
const fetchJ = (page, method, url, body, headers = {}) => page.evaluate(async ([m, u, b, h]) => {
  const r = await fetch(u, { method: m, headers: { 'Content-Type': 'application/json', ...h }, body: b === undefined ? undefined : JSON.stringify(b) })
  return { status: r.status, json: await r.json().catch(() => null) }
}, [method, url, body, headers])
const open = async (who, pw, { locale = 'fr-FR', scheme = 'light', lang = 'fr', vp = { width: 1360, height: 820 }, expect = '[data-testid=logout]' } = {}) => {
  const ctx = await browser.newContext({ viewport: vp, locale, colorScheme: scheme, deviceScaleFactor: 1 })
  await ctx.addInitScript(l => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.setItem('ontoforge.lang', l) } catch {} }, lang)
  const page = await ctx.newPage()
  page.on('pageerror', e => errs.push(`${who} pageerror: ` + String(e).slice(0, 200)))
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(`${who} console: ` + m.text().slice(0, 200)) })
  await page.goto(base + '/', { waitUntil: 'load' })
  await page.waitForSelector('[data-testid=login]')
  await page.fill('[data-testid=login-user]', who); await page.fill('[data-testid=login-password]', pw); await page.click('[data-testid=login-submit]')
  await page.waitForSelector(expect, { timeout: 5000 }).catch(() => {})   // échec de connexion : l'attente expire, loggedIn() répond faux
  if (await page.locator('[data-testid=logout]').count()) {
    const cur = await page.evaluate(() => document.documentElement.lang)
    if (cur !== lang) { await fetchJ(page, 'PUT', '/api/auth/preferences', { lang }); await page.reload(); await page.waitForSelector('[data-testid=logout]') }
  }
  return { ctx, page }
}
const calm = async page => { try { await page.waitForFunction(() => document.querySelectorAll('.toast').length === 0, null, { timeout: 7000 }) } catch {} await sleep(150) }
const shot = async (page, name) => { await calm(page); await page.screenshot({ path: path.join(SHOTS, name + '.png') }) }
const loggedIn = async (who, pw) => { try { const { ctx, page } = await open(who, pw); const ok = (await page.locator('[data-testid=logout]').count()) >= 1; if (!ok) console.log('   loggedIn', who, (await page.locator('[data-testid=login-msg]').innerText().catch(() => '?'))); await ctx.close(); return ok } catch (e) { console.log("   loggedIn:", who, String(e).slice(0, 160)); return false } }
const API = async (page, pw) => (await fetchJ(page, 'GET', '/api/projects')).status

// 1. carol (compte de la configuration) change son mot de passe depuis le menu
const C1 = await open('carol', PW.carol)        // session « ailleurs » : doit être coupée
const C = await open('carol', PW.carol)
await C.page.click('[data-testid=account-menu]'); await C.page.waitForSelector('[data-testid=account-pop]')
log('menu du compte : « Changer mon mot de passe » proposé à un compte de la configuration', (await C.page.locator('[data-testid=account-pw]').count()) === 1 && (await C.page.locator('[data-testid=account-pw]').innerText()).includes('Changer mon mot de passe'))
await C.page.click('[data-testid=account-pw]'); await C.page.waitForSelector('[data-testid=account-pw-form]')
log('formulaire : rappel que le mot de passe de la configuration est remplacé', /remplace celui de la configuration/.test(await C.page.locator('[data-testid=account-pw-config]').innerText()))
const NEW = rnd()
await C.page.fill('[data-testid=account-pw-current]', PW.carol); await C.page.fill('[data-testid=account-pw-new]', 'court'); await C.page.fill('[data-testid=account-pw-confirm]', 'court')
log('10 caractères au moins : bouton inactif, message', await C.page.locator('[data-testid=account-pw-submit]').isDisabled() && /10 caractères/.test(await C.page.locator('[data-testid=account-pw-err]').innerText()))
await C.page.fill('[data-testid=account-pw-new]', NEW); await C.page.fill('[data-testid=account-pw-confirm]', NEW + 'x')
log('confirmation différente : bouton inactif, message', await C.page.locator('[data-testid=account-pw-submit]').isDisabled() && /diffèrent/.test(await C.page.locator('[data-testid=account-pw-err]').innerText()))
log('champs masqués par défaut', (await C.page.locator('[data-testid=account-pw-new]').getAttribute('type')) === 'password')
await C.page.check('[data-testid=account-pw-show]')
log('« Afficher le mot de passe » : champs en clair', (await C.page.locator('[data-testid=account-pw-new]').getAttribute('type')) === 'text' && (await C.page.locator('[data-testid=account-pw-current]').getAttribute('type')) === 'text')
await C.page.uncheck('[data-testid=account-pw-show]')
await C.page.fill('[data-testid=account-pw-confirm]', NEW)
await shot(C.page, '01-changer-mot-de-passe-fr-clair')
await C.page.fill('[data-testid=account-pw-current]', 'faux-mot-de-passe'); await C.page.click('[data-testid=account-pw-submit]')
await C.page.waitForFunction(() => /incorrect/.test(document.querySelector('[data-testid=account-pw-err]')?.textContent || ''))
log('ancien mot de passe faux : refusé, message', true)
await C.page.fill('[data-testid=account-pw-current]', PW.carol); await C.page.click('[data-testid=account-pw-submit]')
await C.page.waitForSelector('[data-testid=account-pw-done]')
log('message de succès affiché dans le menu', /Mot de passe changé/.test(await C.page.locator('[data-testid=account-pw-done]').innerText()))
await shot(C.page, '02-mot-de-passe-change-fr-clair')
log('session courante conservée (nouvelle session émise)', (await API(C.page)) === 200)
await C.page.reload(); await C.page.waitForSelector('[data-testid=logout]')
log('… et après rechargement', (await API(C.page)) === 200)
log('autre session de carol coupée (401)', (await API(C1.page)) === 401)
await C1.page.reload(); await C1.page.waitForSelector('[data-testid=login]')
log('l\'autre session retombe sur l\'écran de connexion', true)
await C1.ctx.close()
await C.page.click('[data-testid=logout]'); await C.page.waitForSelector('[data-testid=login]')
log('ancien mot de passe (celui de la configuration) refusé', !(await loggedIn('carol', PW.carol)))
PW.carol1 = NEW
log('nouveau mot de passe accepté', await loggedIn('carol', NEW))
log('alice (autre compte de la configuration) intacte', await loggedIn('alice', PW.alice))

// 2. l'administratrice voit le masque, réinitialise, puis revient à la configuration
const A = await open('alice', PW.alice)
await A.page.goto(`${base}/#/administration`); await A.page.waitForSelector('[data-testid=adm-table]')
const rowTxt = async l => (await A.page.locator(`[data-testid=adm-row-${l}]`).innerText()).replace(/\s+/g, ' ')
log('panneau : « Mot de passe redéfini dans l\'interface » sur carol seulement', /Mot de passe redéfini dans l'interface/.test(await rowTxt('carol')) && !/redéfini/.test(await rowTxt('alice')))
log('carol : Réinitialiser et Revenir à la configuration ; alice : Réinitialiser seulement', (await A.page.locator('[data-testid=adm-revert-carol]').count()) === 1 && (await A.page.locator('[data-testid=adm-reset-alice]').count()) === 1 && (await A.page.locator('[data-testid=adm-revert-alice]').count()) === 0)
log('pas de bouton désactiver / supprimer sur un compte de la configuration', (await A.page.locator('[data-testid=adm-toggle-carol], [data-testid=adm-delete-carol], [data-testid=adm-admin-carol]').count()) === 0)
log('pas d\'avertissement tant que la configuration n\'a pas changé', (await A.page.locator('[data-testid=adm-cfg-warning]').count()) === 0)
await shot(A.page, '03-admin-masque-fr-clair')
// réinitialisation d'un compte de la configuration
const C2 = await open('carol', NEW)
await A.page.click('[data-testid=adm-reset-carol]'); await A.page.waitForSelector('[data-testid=adm-ask-reset]')
log('confirmation de réinitialisation : explique le masque', /masque celui de la configuration/.test(await A.page.locator('[data-testid=adm-ask-reset]').innerText()))
await A.page.click('[data-testid=adm-reset-yes]'); await A.page.waitForSelector('[data-testid=adm-prov-pw]')
const prov = (await A.page.locator('[data-testid=adm-prov-pw]').innerText()).trim()
log('mot de passe provisoire généré pour carol', prov.length >= 16 && /Mot de passe à changer/.test(await rowTxt('carol')))
await A.page.click('[data-testid=adm-prov-close]')
log('session de carol coupée par la réinitialisation', (await API(C2.page)) === 401)
await C2.ctx.close()
const C3 = await open('carol', prov, { expect: '[data-testid=change-password]' })
const st3 = await API(C3.page)
log('carol : écran « Choisissez votre mot de passe » avant tout autre écran', (await C3.page.locator('[data-testid=change-password]').count()) === 1 && st3 === 403, String(st3))
const NEW2 = rnd()
await C3.page.fill('[data-testid=pw-current]', prov); await C3.page.fill('[data-testid=pw-new]', NEW2); await C3.page.fill('[data-testid=pw-confirm]', NEW2); await C3.page.click('[data-testid=pw-submit]')
await C3.page.waitForSelector('[data-testid=logout]', { timeout: 10000 })
log('carol change le provisoire, accède à l\'application', (await API(C3.page)) === 200)
await C3.ctx.close()
PW.carol1 = NEW2

// 3. la configuration est éditée (nouveau hachage pour carol) : le masque reste prioritaire, avertissement dans le panneau
await stopBackend(); await startBackend('carol2')
await A.page.reload(); await A.page.waitForSelector('[data-testid=adm-table]')
log('après redémarrage : alice toujours connectée', (await API(A.page)) === 200)
log('masque prioritaire : le nouveau mot de passe de la configuration ne fonctionne pas', !(await loggedIn('carol', PW.carol2)))
log('masque prioritaire : le mot de passe de l\'interface fonctionne', await loggedIn('carol', NEW2))
await A.page.waitForSelector('[data-testid=adm-cfg-warning]')
log('avertissement : configuration modifiée, masque prioritaire', /reste prioritaire/.test(await A.page.locator('[data-testid=adm-cfg-warning]').innerText()) && (await A.page.locator('[data-testid=adm-cfgchanged-carol]').count()) === 1)
await shot(A.page, '04-admin-avertissement-fr-clair')

// 4. captures fr / en, clair / sombre : menu avec le formulaire, panneau d'administration avec masque et avertissement
for (const [lang, locale] of [['fr', 'fr-FR'], ['en', 'en-US']]) for (const scheme of ['light', 'dark']) {
  const tag = `${lang}-${scheme === 'light' ? 'clair' : 'sombre'}`
  const K = await open('carol', NEW2, { locale, lang, scheme })
  await K.page.click('[data-testid=account-menu]'); await K.page.waitForSelector('[data-testid=account-pop]')
  await K.page.click('[data-testid=account-pw]'); await K.page.waitForSelector('[data-testid=account-pw-form]')
  await K.page.fill('[data-testid=account-pw-current]', NEW2); await K.page.fill('[data-testid=account-pw-new]', 'x'.repeat(12)); await K.page.fill('[data-testid=account-pw-confirm]', 'x'.repeat(12))
  log(`menu du compte, formulaire (${tag})`, lang === 'fr' ? /Changer le mot de passe/.test(await K.page.locator('[data-testid=account-pw-submit]').innerText()) : /Change password/.test(await K.page.locator('[data-testid=account-pw-submit]').innerText()))
  await shot(K.page, `10-menu-mot-de-passe-${tag}`)
  await K.ctx.close()
  const A2 = await open('alice', PW.alice, { locale, lang, scheme })
  await A2.page.goto(`${base}/#/administration`); await A2.page.waitForSelector('[data-testid=adm-cfg-warning]'); await sleep(200)
  log(`panneau : masque et avertissement (${tag})`, new RegExp(lang === 'fr' ? 'Mot de passe redéfini dans l.interface' : 'Password redefined in the interface').test(await A2.page.locator('[data-testid=adm-row-carol]').innerText()))
  await shot(A2.page, `11-admin-masque-${tag}`)
  await A2.ctx.close()
}

// 5. retour au mot de passe de la configuration (la nouvelle valeur du .env)
await A.page.click('[data-testid=adm-revert-carol]'); await A.page.waitForSelector('[data-testid=adm-ask-revert]')
await shot(A.page, '05-admin-revenir-fr-clair')
await A.page.click('[data-testid=adm-revert-yes]'); await sleep(600)
log('retour à la configuration : masque et avertissement disparus', (await A.page.locator('[data-testid=adm-cfg-warning]').count()) === 0 && !/redéfini/.test(await rowTxt('carol')))
log('mot de passe de la configuration de nouveau valable, celui de l\'interface mort', await loggedIn('carol', PW.carol2) && !(await loggedIn('carol', NEW2)))
await A.page.click('[role=tab]:has-text("Journal d\'administration")'); await A.page.waitForSelector('[data-testid=adm-audit]')
const aud = await A.page.locator('[data-testid=adm-audit]').innerText()
log('journal : réinitialisation, changements, retour à la configuration ; aucun mot de passe', /a rétabli le mot de passe de la configuration/.test(aud) && /a changé son mot de passe/.test(aud) && /a réinitialisé le mot de passe/.test(aud) && ![NEW, NEW2, prov, PW.carol, PW.carol2].some(s => aud.includes(s)))
const file = readdirSync(data).filter(f => /^(accounts|admin-audit)/.test(f))
const blob = file.map(f => readFileSync(path.join(data, f), 'utf8')).join('\n')
log('magasin et journal : aucun mot de passe en clair, hachage argon2 seulement', ![NEW, NEW2, prov, PW.carol, PW.carol2, PW.alice].some(s => blob.includes(s)))
await A.ctx.close()

log('aucune erreur de console ou de page', errs.length === 0, errs.slice(0, 3).join(' | '))
await browser.close()
console.log(ko ? `\n${ko} échec(s)` : '\nRecette L43 : tout est vert')
process.exit(ko ? 1 : 0)
