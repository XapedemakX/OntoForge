// Recette L44 : application sur téléphone et tablette (iPhone 15, Pixel 7, iPad mini), en version locale ET en version web (Cloud Run reproduite).
// Usage : BACKEND_PORT=9031 FRONT_PORT=5031 node tools/recette/mobile_l44.mjs [--mode=local|web] [--devices=iphone15,pixel7,ipadmini] [--shots]
// Front buildé avant (cd frontend && npm run build). Sans --mode, les deux versions se suivent sur les mêmes ports.
// Vérifie : barre d'onglets et retour, feuilles du bas, gestes du graphe et de la carte (glisser, pincer qui change l'échelle, toucher qui ouvre la fiche,
// appui long), modification limitée depuis la fiche (sous-classe ajoutée puis présente dans le modèle), lecteur sans modification (version web),
// cibles tactiles >= 44 px (seuil : 95 % des cibles visibles ; le contenu des canevas — nœuds du graphe, éléments de la carte — est dispensé : il se zoome),
// aucun débordement horizontal, aucune erreur de console ni violation de CSP. iPad mini (768 px de large) garde la mise en page large.
// Comptes et secrets tirés au hasard à l'exécution (web_server.mjs). Captures facultatives (--shots) : journal/L44/recette/.
import { createRequire } from 'node:module'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { startWeb, apiClient, ROOT } from './web_server.mjs'
const require = createRequire(import.meta.url)
let pw
try { pw = require('playwright') } catch { pw = require('/opt/node22/lib/node_modules/playwright') }
const { chromium, devices } = pw
const sleep = ms => new Promise(r => setTimeout(r, ms))
const arg = (k, d) => (process.argv.find(a => a.startsWith(`--${k}=`)) || '').split('=')[1] || d
const SHOTS = process.argv.includes('--shots') ? path.join(ROOT, 'journal/L44/recette') : null
if (SHOTS) mkdirSync(SHOTS, { recursive: true })
const DEV = { iphone15: devices['iPhone 15'], pixel7: devices['Pixel 7'], ipadmini: devices['iPad Mini'] }
const want = arg('devices', 'iphone15,pixel7,ipadmini').split(',')
const modes = arg('mode', 'local,web').split(',')
let ko = 0
const log = (name, ok, detail = '') => { if (!ok) ko++; console.log((ok ? 'OK  ' : 'KO  ') + name + (detail ? ' :: ' + detail : '')) }

// ---- gestes (CDP) -----------------------------------------------------------------------------------------------------
const touch = (cdp, type, pts) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: pts.map((p, i) => ({ x: p[0], y: p[1], id: i })) })
async function drag1(cdp, x, y, dx, dy) { await touch(cdp, 'touchStart', [[x, y]]); for (let i = 1; i <= 8; i++) { await touch(cdp, 'touchMove', [[x + dx * i / 8, y + dy * i / 8]]); await sleep(16) } await touch(cdp, 'touchEnd', []) }
async function pinch(cdp, x, y, from, to) {
  await touch(cdp, 'touchStart', [[x - from, y], [x + from, y]])
  for (let i = 1; i <= 10; i++) { const d = from + (to - from) * i / 10; await touch(cdp, 'touchMove', [[x - d, y], [x + d, y]]); await sleep(16) }
  await touch(cdp, 'touchEnd', [])
}
const tapAt = async (cdp, x, y) => { await touch(cdp, 'touchStart', [[x, y]]); await sleep(60); await touch(cdp, 'touchEnd', []) }
const longPressAt = async (cdp, x, y) => { await touch(cdp, 'touchStart', [[x, y]]); await sleep(900); await touch(cdp, 'touchEnd', []) }

// ---- mesure des cibles et du débordement -----------------------------------------------------------------------------
const measure = () => {
  const W = innerWidth, H = innerHeight
  const rectOf = el => { const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return null; if (r.bottom <= 0 || r.top >= H || r.right <= 0 || r.left >= W) return null
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) return null; return r }
  const label = el => (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || el.getAttribute('placeholder') || el.tagName).trim().replace(/\s+/g, ' ').slice(0, 40)
  const inter = [...document.querySelectorAll('a[href], button, input, select, textarea, [role=button], [role=tab], [role=menuitem], [tabindex]:not([tabindex="-1"])')]
    .filter(el => !el.closest('[aria-hidden=true]') && !el.disabled && !el.closest('[inert]'))
    // contenu de canevas (zoomable) : dispensé
    .filter(el => !el.closest('.react-flow__node, .react-flow__edge, .react-flow__handle, .react-flow__renderer, svg.bm-svg, .cy canvas, .monaco-editor, .cm-editor, .ol-tabs-skip'))
  let n = 0; const small = []
  for (const el of inter) {
    // cases et boutons radio : la cible est leur étiquette
    const box = (el.type === 'checkbox' || el.type === 'radio') ? (el.closest('label') || el) : el
    const r = rectOf(box); if (!r) continue
    n++; if (r.width < 43.5 || r.height < 43.5) small.push(`${label(el)} ${Math.round(r.width)}x${Math.round(r.height)}`)
  }
  const inputs = inter.filter(el => /INPUT|SELECT|TEXTAREA/.test(el.tagName) && !['checkbox', 'radio', 'range', 'color'].includes(el.type) && rectOf(el))
  const tiny = inputs.filter(el => parseFloat(getComputedStyle(el).fontSize) < 16).map(label)
  return { n, small, tiny, vw: W, pageW: document.documentElement.scrollWidth, overflow: document.documentElement.scrollWidth > W + 1 }
}

const SCREENS = ['tableau', 'ontologie', 'ontologie-liste', 'carte-metier', 'analyse', 'modele', 'exports', 'requetes', 'assistant', 'versions', 'shacl', 'fichiers', 'plus']

async function run(mode) {
  console.log(`\n=== version ${mode === 'web' ? 'web (Cloud Run reproduite)' : 'locale'} ===`)
  const srv = await startWeb({ mode, backendPort: process.env.BACKEND_PORT || 9031, frontPort: process.env.FRONT_PORT || 5031 })
  const base = srv.base
  const api = apiClient(base)
  if (mode === 'web') await api.login('jerem', srv.users.jerem)
  const pid = (await api.call('POST', '/api/projects', { name: 'Automaint', sample: 'automaint' })).json.id
  if (mode === 'web') log('partage en lecteur (bob)', (await api.call('POST', `/api/projects/${pid}/access/members`, { login: 'bob', role: 'reader' })).status < 300)
  const browser = await chromium.launch()
  const classCount = async () => Object.keys((await api.call('GET', `/api/projects/${pid}`)).json?.onto?.classes || {}).length
  const labelsOf = async () => Object.values((await api.call('GET', `/api/projects/${pid}`)).json?.onto?.classes || {}).map(c => JSON.stringify(c.labels || c.label || ''))

  const newPage = async (key, who = 'jerem', theme = 'light') => {
    const d = { ...DEV[key] }; delete d.defaultBrowserType
    const ctx = await browser.newContext({ ...d, locale: 'fr-FR', colorScheme: theme, ignoreHTTPSErrors: true })
    await ctx.addInitScript(() => { window.__csp = []; document.addEventListener('securitypolicyviolation', e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI)) })
    const page = await ctx.newPage()
    const errs = []
    page.on('pageerror', e => errs.push('pageerror: ' + String(e).slice(0, 160)))
    page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource.*(401|403|404)/.test(m.text())) errs.push('console: ' + m.text().slice(0, 160)) })
    await page.goto(base + '/', { waitUntil: 'load' })
    if (mode === 'web') {
      await page.waitForSelector('[data-testid=login]')
      await page.fill('[data-testid=login-user]', who); await page.fill('[data-testid=login-password]', srv.users[who]); await page.click('[data-testid=login-submit]')
    }
    await page.waitForSelector('.proj-grid, .proj, h1', { timeout: 15000 })
    return { ctx, page, errs, cdp: await ctx.newCDPSession(page) }
  }
  const go = async (page, s) => { await page.goto(`${base}/#/projet/${pid}/${s}`); await sleep(1300) }
  const shot = async (page, name) => { if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${mode}-${name}.png`) }) }

  for (const key of want) {
    const tag = `${mode}/${key}`
    const phone = key !== 'ipadmini'
    const { ctx, page, errs, cdp } = await newPage(key)
    const SHEET = '[data-testid=sheet], [data-testid=fiche-sheet]'
    const sheetOpen = async () => page.locator(SHEET).first().isVisible().catch(() => false)

    // 1. mise en page : barre d'onglets (téléphone) ou mise en page large (iPad)
    await go(page, 'tableau')
    const hasTabs = await page.locator('[data-testid=tabbar]').isVisible().catch(() => false)
    log(`barre d'onglets ${phone ? 'présente' : 'absente (mise en page large)'} (${tag})`, hasTabs === phone)
    log(`en-tête court sans tiroir (${tag})`, !phone || (await page.locator('.menu-btn, .scrim').count()) === 0)

    if (phone) {
      // 2. navigation par onglets et retour
      const tabs = { home: 'tableau', onto: 'ontologie', queries: 'requetes', arbitrate: 'analyse', more: 'plus' }
      for (const [k, route] of Object.entries(tabs)) {
        await page.locator(`[data-tab=${k}]`).tap(); await sleep(700)
        log(`onglet ${k} -> ${route} (${tag})`, page.url().includes('/' + route), page.url().split('#')[1])
        log(`onglet ${k} marqué actif (${tag})`, (await page.locator(`[data-tab=${k}]`).getAttribute('aria-current')) === 'page')
      }
      await page.locator('[data-tab=more]').tap(); await sleep(500)
      const carte = page.locator('[data-testid=more] [data-screen=carte-metier]').first()
      if (await carte.count()) { await carte.tap(); await sleep(900); log(`carte métier accessible depuis Plus (${tag})`, page.url().includes('carte-metier'))
        if (await page.locator('.mback').count()) { await page.locator('.mback').tap(); await sleep(700); log(`retour depuis un écran secondaire (${tag})`, !page.url().includes('carte-metier') || page.url().includes('plus')) } }
      else log(`carte métier accessible depuis Plus (${tag})`, false, 'lien absent')

      // 3. graphe : glisser, pincer, toucher un nœud, appui long
      await go(page, 'ontologie'); await sleep(600)
      // cadrage initial lisible et liens tracés (retour de Jerem : « il manque les liens dans le graphe »)
      const g0 = await page.evaluate(() => {
        const inView = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.right > 0 && r.left < innerWidth && r.bottom > 0 && r.top < innerHeight }
        const edges = [...document.querySelectorAll('.react-flow__edge')].filter(inView)
        const nodes = [...document.querySelectorAll('.react-flow__node')].filter(inView)
        return { edges: edges.length, nodes: nodes.length, minH: Math.min(...nodes.map(n => n.getBoundingClientRect().height)), labels: document.querySelectorAll('.of-elabel, .of-vl').length }
      })
      log(`graphe : des arêtes sont rendues et visibles au chargement (${tag})`, g0.edges > 0, `${g0.edges} arêtes, ${g0.labels} libellés`)
      log(`graphe : nœuds lisibles au chargement, au moins 32 px de haut (${tag})`, g0.nodes > 0 && g0.minH >= 32, `${g0.nodes} nœuds, plus petit ${Math.round(g0.minH)} px`)
      await page.locator('[data-testid=fit-all]').tap().catch(() => {}); await sleep(600)
      log(`graphe : « Tout voir » garde les arêtes (${tag})`, (await page.locator('.react-flow__edge').count()) > 0)
      const tf = sel => page.evaluate(s => document.querySelector(s)?.style.transform || null, sel)
      const sc = t => Number((String(t).match(/scale\(([\d.]+)/) || [])[1])
      const gbox = await page.locator('.react-flow__pane').first().boundingBox()
      let t0 = await tf('.react-flow__viewport')
      const free = await page.evaluate(([bx, by, bw, bh]) => { for (let fy = 0.2; fy < 0.9; fy += 0.07) for (let fx = 0.1; fx < 0.9; fx += 0.07) { const el = document.elementFromPoint(bx + bw * fx, by + bh * fy); if (el?.classList.contains('react-flow__pane')) return [bx + bw * fx, by + bh * fy] } return [bx + bw / 2, by + bh / 2] }, [gbox.x, gbox.y, gbox.width, gbox.height])
      await drag1(cdp, free[0], free[1], 70, 40); await sleep(300); let t1 = await tf('.react-flow__viewport')
      log(`graphe : glisser déplace la vue (${tag})`, t0 !== t1)
      t0 = t1; await pinch(cdp, gbox.x + gbox.width / 2, gbox.y + gbox.height / 2, 40, 120); await sleep(400); t1 = await tf('.react-flow__viewport')
      log(`graphe : pincer change l'échelle (${tag})`, sc(t1) > sc(t0) * 1.2, `${sc(t0)} -> ${sc(t1)}`)
      await page.locator('[data-testid=fit-all]').tap().catch(() => {}); await sleep(600)
      const nodePos = await page.evaluate(() => { const H = innerHeight - 140; for (const n of document.querySelectorAll('.react-flow__node')) { const r = n.getBoundingClientRect(); if (r.left > 4 && r.right < innerWidth - 4 && r.top > 110 && r.bottom < H) return [r.left + r.width / 2, r.top + r.height / 2] } return null })
      log(`graphe : un nœud est visible entièrement après « Tout voir » (${tag})`, !!nodePos)
      if (nodePos) {
        const before = await tf('.react-flow__viewport')
        await drag1(cdp, nodePos[0], nodePos[1], 0, 0); await sleep(200)
        const npos = n => page.evaluate(() => document.querySelector('.react-flow__node')?.style.transform)
        const p0 = await npos(); await drag1(cdp, nodePos[0], nodePos[1], 30, 30); await sleep(300)
        log(`graphe : pas de déplacement accidentel d'un nœud (${tag})`, p0 === await npos())
        const np2 = await page.evaluate(() => { const H = innerHeight - 140; for (const n of document.querySelectorAll('.react-flow__node')) { const r = n.getBoundingClientRect(); if (r.left > 4 && r.right < innerWidth - 4 && r.top > 110 && r.bottom < H) return [r.left + r.width / 2, r.top + r.height / 2] } return nodePos })
        await tapAt(cdp, np2[0], np2[1]); await sleep(700)
        log(`graphe : toucher un nœud ouvre la fiche du bas (${tag})`, await sheetOpen())
        log(`graphe : le voisinage du nœud sélectionné ressort (arêtes proches / estompées) (${tag})`, (await page.locator('.react-flow__edge .of-edge.near, .react-flow__edge.near, .of-edge.near').count()) > 0 || (await page.locator('.of-edge.dim, .of-elabel.dim').count()) > 0)
        await shot(page, `${key}-graphe-fiche`)
        await page.locator(`:is(${SHEET}) .sheet-x`).first().tap().catch(() => {}); await sleep(500)
        log(`fiche : fermer la feuille (${tag})`, !(await sheetOpen()))
        await longPressAt(cdp, np2[0], np2[1]); await sleep(600)
        log(`graphe : appui long ouvre les actions (${tag})`, await page.locator('[data-testid=act-view], [data-testid=act-sub]').first().isVisible().catch(() => false))
        await shot(page, `${key}-graphe-appui-long`)
        await page.keyboard.press('Escape'); await sleep(400)
        void before
      }
      // recherche qui centre
      await page.locator('[data-testid=graph-search]').fill('Garantie').catch(() => {}); await page.keyboard.press('Enter').catch(() => {}); await sleep(900)
      log(`graphe : la recherche ouvre ou centre le nœud (${tag})`, (await sheetOpen()) || (await page.locator('.react-flow__node.selected').count()) > 0)
      await page.keyboard.press('Escape').catch(() => {}); await sleep(300)

      // 4. carte métier : glisser, pincer, toucher
      await go(page, 'carte-metier')
      const mbox = await page.locator('svg.bm-svg').first().boundingBox()
      const mtf = () => page.evaluate(() => { const g = document.querySelector('svg.bm-svg g'); return g?.getAttribute('transform') })
      let m0 = await mtf(); await drag1(cdp, mbox.x + mbox.width * 0.2, mbox.y + mbox.height * 0.8, 50, 30); await sleep(300); let m1 = await mtf()
      log(`carte : glisser déplace la vue (${tag})`, m0 !== m1)
      m0 = m1; await pinch(cdp, mbox.x + mbox.width / 2, mbox.y + mbox.height / 2, 40, 120); await sleep(400); m1 = await mtf()
      log(`carte : pincer change l'échelle (${tag})`, sc(m1) > sc(m0) * 1.2, `${sc(m0)} -> ${sc(m1)}`)
      await go(page, 'carte-metier')
      const mn = await page.evaluate(() => { for (const n of document.querySelectorAll('[data-n]')) { const r = n.getBoundingClientRect(); const x = r.left + r.width / 2, y = r.top + r.height / 2; if (x > 10 && x < innerWidth - 10 && y > 110 && y < innerHeight - 140 && n.contains(document.elementFromPoint(x, y))) return [x, y] } return null })
      if (mn) {
        await tapAt(cdp, mn[0], mn[1]); await sleep(700)
        log(`carte : toucher un nœud ouvre la fiche (${tag})`, await sheetOpen())
        await shot(page, `${key}-carte-fiche`)
        await page.locator(`:is(${SHEET}) .sheet-x`).first().tap().catch(() => {}); await sleep(400)
      } else log(`carte : un nœud est visible (${tag})`, false)
      log(`carte : aucune modification possible sur téléphone (${tag})`, (await page.locator('[data-testid=bm-edit], .bm-tools [data-write]').count()) === 0)

      // 5. modification limitée : sous-classe depuis la fiche, présente ensuite dans le modèle
      await go(page, 'ontologie-liste')
      const before = await classCount()
      await page.locator('.ol-trow .nm', { hasText: 'Garantie' }).first().tap(); await sleep(800)
      log(`liste : toucher une classe ouvre la fiche (${tag})`, await sheetOpen())
      const addSub = page.locator('[data-testid=fiche-add-sub]')
      if (!(await addSub.isVisible().catch(() => false))) await page.locator(`:is(${SHEET}) .sheet-grip`).first().tap().catch(() => {})
      await sleep(400)
      await addSub.tap(); await sleep(400)
      const nm = 'Garantie prolongée ' + key
      await page.locator('[data-testid=fiche-sub-name]').fill(nm)
      await page.locator('[data-testid=fiche-sub-ok]').tap(); await sleep(1200)
      const after = await classCount()
      log(`modification limitée : sous-classe ajoutée au modèle (${tag})`, after === before + 1, `${before} -> ${after}`)
      log(`modification limitée : présente dans la liste (${tag})`, (await page.locator('.ol-trow .nm', { hasText: nm }).count()) > 0 || (await page.locator(SHEET, { hasText: nm }).count()) > 0)
      await shot(page, `${key}-fiche-edition`)
      // renommer
      if (await page.locator('[data-testid=fiche-rename]').isVisible().catch(() => false)) {
        await page.locator('[data-testid=fiche-rename]').tap(); await sleep(400)
        await page.locator('[data-testid=fiche-label]').fill('Garantie prolongée renommée'); await page.locator('[data-testid=fiche-rename-ok]').tap(); await sleep(1100)
        log(`modification limitée : renommer depuis la fiche (${tag})`, (await labelsOf()).some(l => l.includes('renommée')))
      }

      // 6. arbitrage : une carte par point, première décision en un toucher
      await go(page, 'analyse')
      const card = page.locator('[data-testid=deck-card]').first()
      log(`arbitrage : une carte de recommandation (${tag})`, await card.isVisible().catch(() => false))
      await shot(page, `${key}-arbitrage`)
      // comptes cohérents : badge = À arbitrer + Perdus = dénominateur de la progression ; rien sous Krakie ; pas d'accents graves en clair
      const cnt = await page.evaluate(() => {
        const n = sel => Number((document.querySelector(sel)?.innerText.match(/\d+/) || [NaN])[0])
        const fab = document.querySelector('[data-testid=krakie-fab]')?.getBoundingClientRect()
        const under = [...document.querySelectorAll('.dcard .ot, .dcard .det, .dcard h2, .dcard .why')].filter(el => { const r = el.getBoundingClientRect(), g = document.createRange(); g.selectNodeContents(el); const t = g.getBoundingClientRect(); return fab && t.width > 0 && t.left < fab.right && t.right > fab.left && t.top < fab.bottom && t.bottom > fab.top }).map(el => el.innerText.slice(0, 30))
        return { badge: n('[data-testid=pending-badge]'), todo: n('[data-testid=pill-todo]'), lost: n('[data-testid=pill-lost]'), total: Number((document.querySelector('.deck-sub')?.innerText.match(/sur (\d+)/) || document.querySelector('.deck-sub')?.innerText.match(/of (\d+)/) || [0, NaN])[1]), done: n('[data-testid=pill-done]'), under, ticks: /`/.test(document.querySelector('[data-testid=deck-card]')?.innerText || '') }
      })
      log(`arbitrage : badge = À arbitrer + Perdus (${tag})`, cnt.badge === cnt.todo + cnt.lost, JSON.stringify(cnt))
      log(`arbitrage : progression « x sur N » avec N = badge + faits (${tag})`, cnt.total === cnt.badge + cnt.done, JSON.stringify(cnt))
      log(`arbitrage : aucun texte de la carte sous le bouton Krakie (${tag})`, cnt.under.length === 0, cnt.under.join(' | '))
      log(`arbitrage : aucun accent grave affiché en clair (${tag})`, !cnt.ticks)
      const doneN = async () => Number(((await page.locator('.dpill.done').first().innerText().catch(() => '0')).match(/\d+/) || [0])[0])
      const d0 = await doneN()
      await page.locator('[data-testid=deck-validate]').tap().catch(() => {}); await sleep(1500)
      log(`arbitrage : première décision en 1 toucher (option recommandée présélectionnée) (${tag})`, (await doneN()) === d0 + 1, `${d0} -> ${await doneN()}`)
      log(`arbitrage : la carte suivante s'affiche (${tag})`, await page.locator('[data-testid=deck-card]').first().isVisible().catch(() => false))

      // 7. requêtes : saisie en langage naturel et résultats en cartes
      await go(page, 'requetes')
      log(`requêtes : saisie en langage naturel visible (${tag})`, await page.locator('textarea, input[type=text]').first().isVisible().catch(() => false))

      // 8. Krakie : bouton fixe au-dessus de la barre d'onglets, feuille plein écran
      await go(page, 'tableau')
      const fab = page.locator('[data-testid=krakie-fab]')
      const fb = await fab.boundingBox().catch(() => null)
      const tb = await page.locator('[data-testid=tabbar]').boundingBox()
      log(`Krakie : bouton fixe 56 px au-dessus de la barre (${tag})`, !!fb && fb.width >= 56 - 1 && fb.y + fb.height <= tb.y + 1, fb ? `${Math.round(fb.width)}x${Math.round(fb.height)} bas ${Math.round(fb.y + fb.height)} / barre ${Math.round(tb.y)}` : 'absent')
      await fab.tap(); await sleep(800)
      log(`Krakie : feuille ouverte (${tag})`, await page.locator('[data-testid=krakie-sheet]').isVisible().catch(() => false))
      await shot(page, `${key}-krakie`)
      await page.keyboard.press('Escape'); await sleep(400)

      // 9. thème sombre : captures et pas d'erreur
      await page.emulateMedia({ colorScheme: 'dark' }); await go(page, 'tableau'); await shot(page, `${key}-sombre-tableau`); await page.emulateMedia({ colorScheme: 'light' })
    } else {
      // iPad : mise en page large, pas de barre ; le graphe reste consultable au toucher
      await go(page, 'ontologie')
      const tb = await page.evaluate(() => { const t = document.querySelector('.topbar'); return { fits: t.scrollWidth <= t.clientWidth + 1, right: Math.max(...[...t.children].map(c => c.getBoundingClientRect().right)), vw: innerWidth } })
      log(`iPad : barre du haut entière, rien de rogné à droite (${tag})`, tb.fits && tb.right <= tb.vw, JSON.stringify(tb))
      log(`iPad : graphe affiché (${tag})`, (await page.locator('.react-flow__node').count()) > 0)
      await shot(page, `${key}-graphe`)
    }

    // 10. cibles >= 44 px et débordement sur tous les écrans
    let n = 0, small = 0; const bad = [], over = [], tiny = []
    for (const s of SCREENS) {
      await go(page, s); await sleep(500)
      const m = await page.evaluate(measure)
      n += m.n; small += m.small.length
      if (m.small.length) bad.push(`${s}: ${m.small.slice(0, process.env.VERBOSE ? 99 : 4).join(' | ')}`)
      if (m.overflow) over.push(`${s} (${m.pageW}>${m.vw})`)
      if (m.tiny.length) tiny.push(`${s}: ${m.tiny.slice(0, 3).join(', ')}`)
    }
    const pct = n ? Math.round((1 - small / n) * 1000) / 10 : 100
    log(`cibles >= 44 px : ${pct} % de ${n} cibles visibles (seuil 95 %) (${tag})`, pct >= 95, bad.slice(0, process.env.VERBOSE ? 99 : 5).join(' ; '))
    log(`aucun débordement horizontal (${tag})`, over.length === 0, over.join(', '))
    if (phone) log(`champs >= 16 px (${tag})`, tiny.length === 0, tiny.join(' ; '))
    const csp = await page.evaluate(() => window.__csp || [])
    log(`aucune violation de CSP (${tag})`, csp.length === 0, csp.join(', '))
    log(`aucune erreur de console (${tag})`, errs.length === 0, errs.slice(0, 3).join(' ; '))
    await ctx.close()
  }

  // lecteur : consulte sans modifier (version web : compte bob, lecteur du projet)
  if (mode === 'web') {
    const { ctx, page, errs } = await newPage('iphone15', 'bob')
    await go(page, 'ontologie-liste'); await page.waitForSelector('.ol-trow .nm', { timeout: 10000 }).catch(() => {})
    log('lecteur : le projet partagé est visible (mobile)', (await page.locator('.ol-trow .nm').count()) > 0)
    await page.locator('.ol-trow .nm', { hasText: 'Garantie' }).first().tap(); await sleep(800)
    const sheet = await page.locator('[data-testid=sheet], [data-testid=fiche-sheet]').first().isVisible().catch(() => false)
    log('lecteur : la fiche s\'ouvre en lecture (mobile)', sheet)
    log('lecteur : aucune action de modification dans la fiche (mobile)', (await page.locator('[data-testid=fiche-add-sub], [data-testid=fiche-add-prop], [data-testid=fiche-rename]').count()) === 0)
    log('lecteur : mention de lecture seule (mobile)', (await page.locator('[data-testid=readonly-chip]').count()) > 0 || /lecture seule/i.test(await page.locator('body').innerText()))
    await shot(page, 'lecteur-fiche')
    const r = await (async () => { const c = apiClient(base); await c.login('bob', srv.users.bob); return c.call('PUT', `/api/projects/${pid}/onto`, { x: 1 }) })()
    log('lecteur : l\'API refuse l\'écriture (403)', r.status === 403 || r.status === 401, String(r.status))
    log('lecteur : aucune erreur de console', errs.length === 0, errs.slice(0, 2).join(' ; '))
    await ctx.close()
  }
  await browser.close(); await srv.stop()
}

for (const m of modes) await run(m)
console.log(ko ? `\n${ko} échec(s)` : '\nTout est vert')
process.exit(ko ? 1 : 0)
