// Recette L27 : authentification, page de connexion, SSRF, déconnexion — dans les conditions de Cloud Run
// (un seul processus FastAPI qui sert le front compilé, ONTOFORGE_AUTH=password, ONTOFORGE_PUBLIC=1, données dans un dossier simulant le montage).
// Usage : cd frontend && npm run build && cd .. && node tools/recette/l27_auth.mjs      (PORT=8921 optionnel)
// Captures : journal/L27/screens/
import { createRequire } from 'node:module'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const require = createRequire(import.meta.url)
let chromium
try { ({ chromium } = require('playwright')) } catch { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')) }
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SHOTS = path.join(ROOT, 'journal/L27/screens'); mkdirSync(SHOTS, { recursive: true })
const PORT = process.env.PORT || 8921
const PY = process.env.PYTHON || '/home/claude/venv/bin/python'
const sleep = ms => new Promise(r => setTimeout(r, ms))
const PASSWORD = 'phrase de passe démo'
const hash = execFileSync(PY, ['-m', 'ontoforge.auth', 'hash', '--stdin', '--user', 'demo'], { cwd: path.join(ROOT, 'backend'), input: PASSWORD }).toString().trim()
const secret = execFileSync(PY, ['-m', 'ontoforge.auth', 'secret'], { cwd: path.join(ROOT, 'backend') }).toString().trim()
const tmp = mkdtempSync(path.join(tmpdir(), 'of-l27-'))
const server = spawn(PY, ['-m', 'uvicorn', 'ontoforge.main:app', '--port', String(PORT), '--log-level', 'warning', '--proxy-headers', '--forwarded-allow-ips=*'], {
  cwd: path.join(ROOT, 'backend'), stdio: 'ignore',
  env: { ...process.env, PORT: String(PORT), ONTOFORGE_DATA: path.join(tmp, 'mnt-data'), ONTOFORGE_LOCAL_STORE_DIR: path.join(tmp, 'tmp-ts'),
    ONTOFORGE_STATIC_DIR: path.join(ROOT, 'frontend/dist'), ONTOFORGE_PUBLIC: '1', ONTOFORGE_AUTH: 'password', ONTOFORGE_AUTH_USERS: hash,
    ONTOFORGE_SECRET_KEY: secret, ONTOFORGE_LLM_PROVIDER: 'mock', ONTOFORGE_PROXY_HOPS: '0', ONTOFORGE_COOKIE_SECURE: process.env.COOKIE_SECURE ?? '1' } })
process.on('exit', () => server.kill())
const base = `http://127.0.0.1:${PORT}`
for (let i = 0; i < 60; i++) { try { if ((await fetch(base + '/api/health')).ok) break } catch {} await sleep(500) }

let ko = 0
const check = (name, ok, detail = '') => { if (!ok) ko++; console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }
const shot = (page, name) => page.screenshot({ path: path.join(SHOTS, name + '.png') })

// 1. sans session : tout est refusé sauf /api/health ; le front reste public
check('API sans session -> 401', (await fetch(base + '/api/projects')).status === 401)
check('API inconnue sans session -> 401', (await fetch(base + '/api/n-importe-quoi')).status === 401)
check('/api/health public', (await fetch(base + '/api/health')).status === 200)
check('page de connexion servie sans session', (await fetch(base + '/')).status === 200)
const h = (await fetch(base + '/api/health')).headers
check('en-têtes CSP + nosniff + frame-ancestors', /frame-ancestors 'none'/.test(h.get('content-security-policy') || '') && h.get('x-content-type-options') === 'nosniff')

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'fr-FR' })
const page = await ctx.newPage(); const errs = []
page.on('pageerror', e => errs.push(String(e).slice(0, 200)))
page.on('console', m => { if (m.type() === 'error' && !/401|403|429/.test(m.text())) errs.push(m.text().slice(0, 200)) })
await page.goto(base + '/', { waitUntil: 'load' })
await page.waitForSelector('[data-testid=login]')
check('page de connexion affichée (fr)', /Se connecter/.test(await page.locator('[data-testid=login-submit]').innerText()))
await sleep(900)
check('Krakie présent (pose accueil)', (await page.locator('.auth-krakie img').count()) === 1)
await shot(page, '01-connexion-desktop-fr')

// 2. mauvais mot de passe : message aimable, Krakie inquiet
await page.fill('[data-testid=login-user]', 'demo'); await page.fill('[data-testid=login-password]', 'pas le bon'); await page.click('[data-testid=login-submit]')
await page.waitForSelector('.auth-krakie.wrong'); await sleep(500)
const bad = await page.locator('[data-testid=login-msg]').innerText()
check('mauvais mot de passe : message + Krakie inquiet', /reconnais pas/.test(bad) && (await page.locator('.auth-krakie').getAttribute('data-mood')) === 'wrong', bad)
check('aucun cookie de session après échec', (await ctx.cookies()).length === 0)
await shot(page, '02-connexion-erreur-fr')

// 3. anglais
await page.click('.auth-lang button:has-text("EN")'); await sleep(300)
check('bascule en anglais', /Sign in/.test(await page.locator('[data-testid=login-submit]').innerText()) && /Demo instance/.test(await page.locator('.auth-sub').innerText()))
await shot(page, '03-connexion-en')
await page.click('.auth-lang button:has-text("FR")'); await sleep(200)

// 4. bon mot de passe : Krakie content puis application
await page.fill('[data-testid=login-user]', 'demo'); await page.fill('[data-testid=login-password]', PASSWORD); await page.click('[data-testid=login-submit]')
await page.waitForSelector('.auth-krakie.happy'); await sleep(500)
check('réussite : Krakie content + message de bienvenue', /Bienvenue/.test(await page.locator('[data-testid=login-msg]').innerText()))
await shot(page, '04-connexion-reussie')
await page.waitForSelector('[data-testid=logout]', { timeout: 8000 })
const ck = (await ctx.cookies()).find(c => c.name.includes('ontoforge_session'))
check('cookie HttpOnly + SameSite=Lax' + (ck?.secure ? ' + Secure' : ''), !!ck && ck.httpOnly && ck.sameSite === 'Lax' && (process.env.COOKIE_SECURE === '0' || ck.secure))
check('application affichée avec « Se déconnecter »', await page.locator('.shell').count() === 1)
await sleep(1200); await shot(page, '05-application-connectee')

// 5. API avec session ; CSRF ; SSRF
const st = await page.evaluate(async () => (await fetch('/api/projects')).status)
check('API avec session -> 200', st === 200)
// fetch d'une iframe vierge : celui du navigateur, sans l'ajout automatique du jeton CSRF
const noCsrf = await page.evaluate(async () => { const f = document.createElement('iframe'); document.body.appendChild(f)
  const r = await f.contentWindow.fetch('/api/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'sans-csrf' }) }); f.remove(); return r.status })
check('POST sans jeton CSRF (cookie présent) -> 403', noCsrf === 403, String(noCsrf))
const pid = await page.evaluate(async () => (await (await fetch('/api/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'recette-l27', sample: 'automaint' }) })).json()).id)
check('POST via l\'interface (jeton CSRF ajouté) crée un projet', !!pid)
const ssrf = await page.evaluate(async (pid) => {
  const out = {}
  for (const [k, url] of [['meta', 'http://169.254.169.254/'], ['gcp', 'http://metadata.google.internal/computeMetadata/v1/'], ['local', 'http://127.0.0.1:8000/'], ['v6', 'http://[::ffff:10.0.0.1]/']]) {
    const r = await fetch(`/api/projects/${pid}/query/endpoint-test`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, auth: 'none' }) })
    out[k] = await r.json()
  }
  const run = await fetch(`/api/projects/${pid}/query/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sparql: 'SELECT * WHERE {?s ?p ?o}', endpoint: { url: 'http://169.254.169.254/', auth: 'none' } }) })
  out.run = { status: run.status, body: await run.json() }
  return out
}, pid)
for (const k of ['meta', 'gcp', 'local', 'v6']) check(`SSRF refusé sur endpoint temporaire (${k})`, ssrf[k].ok === false && /Adresse refusée/.test(ssrf[k].message), ssrf[k].message)
check('SSRF refusé sur /query/run (403)', ssrf.run.status === 403 && /Adresse refusée/.test(ssrf.run.body.detail))

// 6. déconnexion
await page.click('[data-testid=logout]'); await page.waitForSelector('[data-testid=login]')
check('déconnexion : retour à la page de connexion', true)
check('API après déconnexion -> 401', (await page.evaluate(async () => (await fetch('/api/projects')).status)) === 401)
check('ancien cookie supprimé', !(await ctx.cookies()).some(c => c.name.includes('ontoforge_session') && c.value))

// 7. trop d'essais : délai progressif et message de Krakie
for (let i = 0; i < 3; i++) {
  await page.fill('[data-testid=login-user]', 'demo'); await page.fill('[data-testid=login-password]', 'faux' + i)
  if (await page.locator('[data-testid=login-submit]').isDisabled()) { await sleep(2500); }
  await page.click('[data-testid=login-submit]'); await sleep(900)
}
const wait = await page.locator('[data-testid=login-msg]').innerText()
check('limitation : message de patience avec compte à rebours', /Réessayez dans \d+ s/.test(wait), wait)
check('bouton désactivé pendant le délai', await page.locator('[data-testid=login-submit]').isDisabled())
await shot(page, '06-connexion-trop-d-essais')

// 8. mobile
const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: 'en-US' })
const mp = await mctx.newPage()
await mp.goto(base + '/', { waitUntil: 'load' }); await mp.waitForSelector('[data-testid=login]'); await sleep(900)
const ov = await mp.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
check('mobile : pas de défilement horizontal', ov <= 0, 'débord ' + ov)
const box = await mp.locator('[data-testid=login-submit]').boundingBox()
check('mobile : bouton de connexion >= 44 px', box && box.height >= 44, String(box?.height))
await shot(mp, '07-connexion-mobile')
await mp.fill('[data-testid=login-user]', 'x'); await mp.fill('[data-testid=login-password]', 'secret'); await mp.click('.auth-eye'); await sleep(200)
check('mobile : bouton afficher le mot de passe', (await mp.locator('[data-testid=login-password]').getAttribute('type')) === 'text')
check('aucune erreur JS', errs.length === 0, errs.join(' | '))
await browser.close()
console.log(ko ? `\n${ko} contrôle(s) en échec` : '\nTous les contrôles sont OK')
server.kill(); process.exit(ko ? 1 : 0)
