// L44 : reproduction locale de la version web (Cloud Run, deploy/cloudrun/Dockerfile) et de la version locale (docker compose).
//
// Usage en ligne de commande (laisse tourner, Ctrl+C pour arrêter) :
//   BACKEND_PORT=9011 FRONT_PORT=5011 node tools/recette/web_server.mjs            # version web : https://127.0.0.1:5011
//   BACKEND_PORT=9013 FRONT_PORT=5013 node tools/recette/web_server.mjs --local    # version locale : http://127.0.0.1:5013
// Usage en module (recettes) : import { startWeb } from './web_server.mjs' ; const srv = await startWeb({ mode: 'web' }) ; … ; await srv.stop()
//
// Version web, fidèle au Dockerfile Cloud Run :
//   - uvicorn sert l'API ET le front compilé (ONTOFORGE_STATIC_DIR=frontend/dist, à construire avant : cd frontend && npm run build) ;
//   - ONTOFORGE_PUBLIC=1, ONTOFORGE_AUTH=password, ONTOFORGE_LLM_PROVIDER=mock, ONTOFORGE_SAMPLES, ONTOFORGE_SECRET_FILE, cookie Secure (__Host-) ;
//   - variables de deploy/cloudrun/env.yaml (ONTOFORGE_AUTH_ADMINS, ONTOFORGE_EGRESS_ALLOW, ONTOFORGE_SHACL_SLOTS, ONTOFORGE_HERMIT_MAX_MB) ;
//   - comptes jerem (administrateur), alice, bob : mots de passe tirés au hasard à l'exécution, hachés par `python -m ontoforge.auth hash --stdin` ;
//     ONTOFORGE_SECRET_KEY générée par `python -m ontoforge.auth secret`. Rien n'est écrit dans le dépôt ;
//   - devant uvicorn, un frontal HTTPS (certificat auto-signé généré par openssl dans le dossier temporaire) qui joue le rôle du frontal Google :
//     Host conservé, X-Forwarded-Proto: https, X-Forwarded-For ajouté. Comme sur Cloud Run, uvicorn ne croit PAS ces en-têtes
//     (--forwarded-allow-ips limité à une adresse qui n'est pas celle du frontal) : seuls ceux que l'application lit elle-même comptent ;
//   - /data = dossier temporaire (ou WEB_DATA) ; WEB_LATENCY_MS ajoute une latence à chaque requête /api (bucket monté, démarrage à froid).
// Version locale (--local), fidèle à docker compose : backend sans authentification, front servi par un petit serveur qui reproduit
// frontend/nginx.conf (en-têtes de frontend/security-headers.conf, /api relayé avec le Host d'origine, 404 sur /assets et /krakie manquants).
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, existsSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import http from 'node:http'
import https from 'node:https'
import { randomBytes } from 'node:crypto'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const PY = process.env.PYTHON || '/home/claude/venv/bin/python'
const BACK = path.join(ROOT, 'backend')
const DIST = path.join(ROOT, 'frontend/dist')
const sleep = ms => new Promise(r => setTimeout(r, ms))

// deploy/cloudrun/env.yaml : lu tel quel (clé: "valeur"), pour ne pas dériver du fichier de déploiement
export function cloudRunEnvYaml() {
  const out = {}
  for (const line of readFileSync(path.join(ROOT, 'deploy/cloudrun/env.yaml'), 'utf8').split('\n')) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*:\s*"?([^"#]*)"?\s*$/)
    if (m) out[m[1]] = m[2].trim()
  }
  return out
}

const rndPw = () => 'web-' + randomBytes(12).toString('hex')
const hashOf = (user, pw) => execFileSync(PY, ['-m', 'ontoforge.auth', 'hash', '--stdin', '--user', user], { cwd: BACK, input: pw }).toString().trim()

function selfSigned(dir) {
  const key = path.join(dir, 'tls.key'), crt = path.join(dir, 'tls.crt')
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', key, '-out', crt, '-days', '2', '-subj', '/CN=127.0.0.1',
    '-addext', 'subjectAltName=IP:127.0.0.1,DNS:localhost'], { stdio: 'ignore' })
  return { key: readFileSync(key), cert: readFileSync(crt) }
}

async function waitFor(url, insecure = false) {
  for (let i = 0; i < 120; i++) {
    try {
      const ok = await new Promise(res => {
        const mod = url.startsWith('https') ? https : http
        const rq = mod.get(url, { rejectUnauthorized: !insecure }, r => { r.resume(); res(r.statusCode < 500) }); rq.on('error', () => res(false))
      })
      if (ok) return true
    } catch {}
    await sleep(500)
  }
  throw new Error('serveur injoignable : ' + url)
}

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.ico': 'image/x-icon', '.md': 'text/markdown', '.webp': 'image/webp', '.gif': 'image/gif' }
function nginxHeaders() {   // frontend/security-headers.conf, lu tel quel
  const h = {}
  for (const m of readFileSync(path.join(ROOT, 'frontend/security-headers.conf'), 'utf8').matchAll(/add_header\s+([\w-]+)\s+"([^"]*)"/g)) h[m[1].toLowerCase()] = m[2]
  return h
}

/**
 * Démarre la version web (mode 'web') ou locale (mode 'local').
 * Retourne { base, mode, users: { jerem, alice, bob } (mots de passe, mode web), data, stop() }.
 */
export async function startWeb({ mode = 'web', backendPort, frontPort, data, latencyMs, log = false } = {}) {
  const BP = Number(backendPort || process.env.BACKEND_PORT || (mode === 'web' ? 9011 : 9013))
  const FP = Number(frontPort || process.env.FRONT_PORT || (mode === 'web' ? 5011 : 5013))
  const lat = Number(latencyMs ?? process.env.WEB_LATENCY_MS ?? 0)
  if (!existsSync(path.join(DIST, 'index.html'))) throw new Error('frontend/dist absent : cd frontend && npm run build')
  const dir = data || process.env.WEB_DATA || mkdtempSync(path.join(tmpdir(), `of-${mode}-`))
  mkdirSync(dir, { recursive: true })
  const priv = mkdtempSync(path.join(tmpdir(), `of-${mode}-run-`))   // hors de /data : clé maître, certificat, triplestore (disque de l'instance)
  const procs = []
  const users = {}
  let env
  if (mode === 'web') {
    for (const u of ['jerem', 'alice', 'bob']) users[u] = rndPw()
    const secret = execFileSync(PY, ['-m', 'ontoforge.auth', 'secret'], { cwd: BACK }).toString().trim()
    env = {
      ...process.env,
      // ENV du Dockerfile Cloud Run
      ONTOFORGE_DATA: dir, ONTOFORGE_SAMPLES: path.join(ROOT, 'samples'), ONTOFORGE_STATIC_DIR: DIST,
      ONTOFORGE_LOCAL_STORE_DIR: path.join(priv, 'triplestore'), ONTOFORGE_PUBLIC: '1', ONTOFORGE_AUTH: 'password',
      ONTOFORGE_LLM_PROVIDER: 'mock', ONTOFORGE_SECRET_FILE: path.join(priv, 'master.key'),
      // deploy/cloudrun/env.yaml
      ...cloudRunEnvYaml(),
      // secrets (Secret Manager sur Cloud Run)
      ONTOFORGE_SECRET_KEY: secret, ONTOFORGE_AUTH_USERS: Object.entries(users).map(([u, p]) => hashOf(u, p)).join(';'),
    }
    delete env.ONTOFORGE_COOKIE_SECURE; delete env.ONTOFORGE_CORS_ORIGINS
  } else {
    env = { ...process.env, ONTOFORGE_DATA: dir, ONTOFORGE_LLM_PROVIDER: 'mock', ONTOFORGE_SAMPLES: path.join(ROOT, 'samples'),
      ONTOFORGE_LOCAL_STORE_DIR: path.join(priv, 'triplestore'), ONTOFORGE_SECRET_FILE: path.join(priv, 'master.key'), ONTOFORGE_PROXY_HOPS: '1' }
    for (const k of ['ONTOFORGE_PUBLIC', 'ONTOFORGE_AUTH', 'ONTOFORGE_STATIC_DIR', 'ONTOFORGE_AUTH_USERS', 'ONTOFORGE_SECRET_KEY']) delete env[k]
  }
  // CMD du Dockerfile : --proxy-headers, frontaux de confiance = défaut 127.0.0.1 ; ici le frontal EST 127.0.0.1, on désigne donc une
  // autre adresse pour retrouver le comportement en ligne (en-têtes X-Forwarded-* non réécrits par uvicorn).
  const args = ['-m', 'uvicorn', 'ontoforge.main:app', '--host', '127.0.0.1', '--port', String(BP), '--log-level', 'warning']
  if (mode === 'web') args.push('--proxy-headers', '--forwarded-allow-ips=192.0.2.1', '--no-server-header')
  const back = spawn(PY, args, { cwd: BACK, env, stdio: log ? 'inherit' : ['ignore', 'ignore', 'pipe'] })
  let backErr = ''
  back.stderr?.on('data', d => { backErr = (backErr + d).slice(-4000) })
  procs.push(back)
  const backUrl = `http://127.0.0.1:${BP}`
  try { await waitFor(backUrl + '/api/health') } catch (e) { back.kill(); throw new Error(e.message + '\n' + backErr) }

  const relay = (req, res, headers) => {
    const go = () => {
      const up = http.request({ host: '127.0.0.1', port: BP, path: req.url, method: req.method, headers }, r => { res.writeHead(r.statusCode, r.headers); r.pipe(res) })
      up.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end() }); req.pipe(up)
    }
    if (lat > 0 && req.url.startsWith('/api/')) setTimeout(go, lat); else go()
  }
  let server, base
  if (mode === 'web') {
    // frontal Google : tout part vers uvicorn (API + front)
    server = https.createServer(selfSigned(priv), (req, res) => {
      const xff = [req.headers['x-forwarded-for'], req.socket.remoteAddress].filter(Boolean).join(', ')
      relay(req, res, { ...req.headers, 'x-forwarded-proto': 'https', 'x-forwarded-for': xff })
    })
    base = `https://127.0.0.1:${FP}`
  } else {
    const sec = nginxHeaders()
    server = http.createServer((req, res) => {
      if (req.url.startsWith('/api/')) return relay(req, res, { ...req.headers, 'x-forwarded-for': req.socket.remoteAddress })
      const u = decodeURIComponent(req.url.split('?')[0])
      let f = path.join(DIST, u)
      const missing = !f.startsWith(DIST) || !existsSync(f) || statSync(f).isDirectory()
      if (missing && /^\/(assets|krakie)\//.test(u)) { res.writeHead(404, sec); return res.end() }
      if (missing) f = path.join(DIST, 'index.html')
      res.writeHead(200, { ...sec, 'content-type': MIME[path.extname(f)] || 'application/octet-stream', 'cache-control': 'no-cache' }); res.end(readFileSync(f))
    })
    base = `http://127.0.0.1:${FP}`
  }
  await new Promise((r, j) => { server.once('error', j); server.listen(FP, '127.0.0.1', r) })
  await waitFor(base + '/', true)
  let stopped = false
  const stop = async () => {
    if (stopped) return; stopped = true
    server.close()
    for (const p of procs) { p.kill(); await new Promise(r => { if (p.exitCode !== null) return r(); p.once('exit', r); setTimeout(r, 4000) }) }
  }
  process.on('exit', () => { for (const p of procs) try { p.kill() } catch {} })
  return { base, mode, users, data: dir, backendUrl: backUrl, stop }
}

// ---- outils pour les recettes ----------------------------------------------------------------------------------------
/** Requêtes HTTPS « navigateur » côté Node : cookie de session, jeton CSRF, Origin du site. */
export function apiClient(base) {
  let cookie = '', csrf = ''
  const call = (method, url, body) => new Promise((res, rej) => {
    const u = new URL(url, base)
    const mod = u.protocol === 'https:' ? https : http
    const data = body === undefined ? undefined : Buffer.from(JSON.stringify(body))
    const headers = { origin: base, accept: 'application/json', ...(data ? { 'content-type': 'application/json', 'content-length': data.length } : {}),
      ...(cookie ? { cookie } : {}), ...(csrf ? { 'x-csrf-token': csrf } : {}) }
    const rq = mod.request(u, { method, headers, rejectUnauthorized: false }, r => {
      const sc = r.headers['set-cookie']; if (sc) cookie = sc.map(c => c.split(';')[0]).join('; ')
      let buf = ''; r.on('data', d => { buf += d }); r.on('end', () => { let json = null; try { json = JSON.parse(buf) } catch {} res({ status: r.statusCode, json, headers: r.headers }) })
    })
    rq.on('error', rej); if (data) rq.write(data); rq.end()
  })
  return {
    call,
    async login(user, password) {
      const r = await call('POST', '/api/auth/login', { username: user, password })
      if (r.status === 200) csrf = r.json?.csrf || (await call('GET', '/api/auth/session')).json?.csrf || ''
      return r
    },
    get cookie() { return cookie },
  }
}

// ---- ligne de commande ------------------------------------------------------------------------------------------------
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const mode = process.argv.includes('--local') ? 'local' : 'web'
  const srv = await startWeb({ mode, log: process.argv.includes('--log') })
  console.log(`OntoForge (${mode === 'web' ? 'version web, comme Cloud Run' : 'version locale, comme docker compose'}) : ${srv.base}`)
  console.log(`Données : ${srv.data}`)
  if (mode === 'web') {
    const f = path.join(srv.data, '..', path.basename(srv.data) + '.comptes.txt')
    writeFileSync(f, Object.entries(srv.users).map(([u, p]) => `${u} ${p}`).join('\n') + '\n', { mode: 0o600 })
    console.log(`Comptes (jerem administrateur, alice, bob) : ${f}  — certificat auto-signé : accepter l'avertissement du navigateur`)
  }
  const bye = async () => { await srv.stop(); process.exit(0) }
  process.on('SIGINT', bye); process.on('SIGTERM', bye)
}
