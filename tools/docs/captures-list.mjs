// Liste ordonnée des captures de la documentation (utilisée par captures.mjs). Chaque entrée : { name, group, run(c) }.
// `c` : page Playwright, t() (libellés de l'interface dans la langue courante), X (textes par langue), snap(), go()/goTo(), etc.
// Les captures qui modifient le projet sont placées après celles qui ont besoin de l'état initial (voir l'ordre).
export const CAPS = []
const cap = (group, name, run) => CAPS.push({ group, name, run })

// ============================================================================ projets, tableau de bord, visite
cap('projets', 'projets-liste', async c => {
  await c.go('', { wait: 'main' }); await c.sleep(600)
  await c.snap('projets-liste')
})
cap('projets', 'projets-nouveau', async c => {
  await c.go('', { wait: 'main' })
  const name = c.page.locator('input').first(); await name.fill(c.lang === 'fr' ? 'Flotte de véhicules' : 'Vehicle fleet')
  const card = c.page.locator('main .card, main section, main form').filter({ has: c.page.locator('select') }).first()
  await c.snap('projets-nouveau', { target: card, pad: 10, ann: [{ at: name, n: 1, box: true, pos: 'tl' }, { at: c.page.locator('select').first(), n: 2, box: true, pos: 'tr' }] })
})
cap('tableau', 'tableau-de-bord', async c => {
  await c.goTo('tableau', { wait: '.side nav button' }); await c.sleep(1200)
  await c.snap('tableau-de-bord', { fab: true, ann: [
    { at: c.page.locator('button.btn.primary').first(), n: 1, box: true, pos: 'tr' },
    { at: c.page.locator('button.step').first(), n: 2, box: true, pos: 'tl' },
    { at: c.page.locator('.card', { hasText: c.t('dash.findings') }).first(), n: 3, box: true, pos: 'tr' },
  ] })
})
cap('tableau', 'visite-guidee', async c => {
  await c.goTo('tableau', { wait: '.side nav button' })
  await c.page.evaluate(() => window.ontoforgeTour.start({ demo: false })); await c.sleep(900)
  for (let i = 0; i < 4; i++) { await c.page.evaluate(() => window.ontoforgeTour.next()); await c.sleep(500) }
  for (let k = 0; k < 40; k++) { const s = await c.page.evaluate(() => window.ontoforgeTour.state()); if (s.ready) break; await c.sleep(150) }
  await c.sleep(700)
  await c.snap('visite-guidee')
  await c.page.evaluate(() => window.ontoforgeTour.stop()); await c.sleep(300)
})

// ============================================================================ éditeur graphique
const openEditor = async c => { await c.goTo('ontologie', { wait: '.react-flow__node' }); await c.sleep(1800) }
cap('editeur', 'editeur-graphe', async c => {
  await openEditor(c)
  await c.snap('editeur-graphe', { ann: [
    { at: '.of-tree', n: 1, box: true, pos: 'tr' },
    { at: '.of-canvas', n: 2, box: false, pos: 'tl' },
    { at: '.of-bar', n: 3, box: true, pos: 'tr' },
    { at: '.of-dslhead', n: 4, box: true, pos: 'tr' },
  ] })
})
cap('editeur', 'editeur-inspecteur', async c => {
  await openEditor(c)
  await c.click(c.page.locator('.react-flow__node', { hasText: new RegExp(c.lang === 'fr' ? '^\\s*Ordre de r' : '^\\s*Repair order', 'i') })); await c.sleep(1200)
  await c.snap('editeur-inspecteur', { ann: [{ at: '.of-insp-wrap', n: 1, box: true, pos: 'tl' }] })
})

cap('editeur', 'editeur-creation', async c => {
  await openEditor(c)
  const pane = c.page.locator('.react-flow__pane').first(), bb = await pane.boundingBox()
  await c.page.mouse.dblclick(bb.x + bb.width * 0.2, bb.y + bb.height * 0.82); await c.sleep(500)
  await c.page.keyboard.type(c.lang === 'fr' ? 'Pneu' : 'Tyre', { delay: 40 }); await c.sleep(400)
  await c.snap('editeur-creation', { target: '.of-canvas', pad: 0, ann: [{ at: 'input:focus', n: 1, box: true, pos: 'tr' }] })
  await c.page.keyboard.press('Escape'); await c.sleep(300)
})
cap('editeur', 'editeur-saisie-rapide', async c => {
  await openEditor(c)
  await c.click('.of-dslhead'); await c.sleep(600)
  const ta = c.page.locator('.of-dsl-main textarea').first()
  await ta.fill('Tyre "Pneu"@fr "Tyre"@en < Part\nTyre.pressure : decimal [0..1]\nTyre -fittedTo-> Vehicle [1]'); await c.sleep(500)
  await c.snap('editeur-saisie-rapide', { ann: [{ at: '.of-dsl', n: 1, box: true, pos: 'tr' }] })
})
// glisser la poignée d'un nœud vers un autre : menu des trois gestes ; choisir « sous-classe » vers une sous-classe existante crée un cycle, refusé par le serveur
const dragHandle = async (c, fromName, toName) => {
  const node = n => c.page.locator(`.react-flow__node[data-id="${c.NS}${n}"]`).first()
  const from = node(fromName), to = node(toName)
  await from.hover(); await c.sleep(300)
  const h = from.locator('.react-flow__handle[data-handlepos="bottom"]').first(); const hb = await h.boundingBox(), tb = await to.boundingBox()
  await c.page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2); await c.page.mouse.down()
  await c.page.mouse.move(tb.x + tb.width / 2, tb.y + tb.height / 2, { steps: 12 }); await c.page.mouse.up(); await c.sleep(700)
}
cap('editeur', 'editeur-geste-menu', async c => {
  await openEditor(c)
  await dragHandle(c, 'Vehicle', 'Garage')
  await c.snap('editeur-geste-menu', { ann: [{ at: '.of-menu', n: 1, box: true, pos: 'tr' }] })
  await c.page.keyboard.press('Escape')
})
cap('editeur', 'editeur-erreur-validation', async c => {
  await openEditor(c)
  await dragHandle(c, 'Vehicle', 'ElectricVehicle')
  const items = c.page.locator('.of-menu button'); const n = await items.count()
  await items.first().click(); await c.sleep(1200)
  await c.snap('editeur-erreur-validation', { ann: [{ at: '.of-errors', n: 1, box: true, pos: 'tr' }] })
})
cap('editeur', 'editeur-legende', async c => {
  await openEditor(c)
  await c.click('[data-testid=legend-btn]'); await c.sleep(700)
  await c.snap('editeur-legende', { target: '.of-canvas', pad: 0, ann: [{ at: '[data-testid=legend-panel]', n: 1, box: true, pos: 'tl' }, { at: '[data-testid=legend-btn]', n: 2, box: true, pos: 'bl' }] })
})
cap('editeur', 'editeur-vowl', async c => {
  await openEditor(c)
  await c.click(c.btn(c.t('ed.mode.vowl'))); await c.page.waitForSelector('.of-vn', { timeout: 10000 }); await c.sleep(2200)
  await c.snap('editeur-vowl', { ann: [{ at: c.btn(c.t('ed.mode.vowl')), n: 1, box: true, pos: 'tr' }] })
})
cap('editeur', 'editeur-vowl-details', async c => {
  await openEditor(c)
  await c.click(c.btn(c.t('ed.mode.vowl'))); await c.page.waitForSelector('.of-vn', { timeout: 10000 }); await c.sleep(1500)
  await c.click('[data-testid=show-btn]'); await c.sleep(400)
  await c.page.locator('[data-testid=show-dt]').check().catch(() => {}); await c.sleep(300)
  await c.snap('editeur-filtres', { ann: [{ at: '.of-pop', n: 1, box: true, pos: 'tl' }, { at: '[data-testid=show-btn]', n: 2, box: true, pos: 'tr' }] })
  await c.page.keyboard.press('Escape'); await c.sleep(1800)
  await c.snap('editeur-vowl-proprietes')
  await c.click(c.btn(c.t('ed.mode.classic'))); await c.sleep(500)
})
cap('editeur', 'editeur-export', async c => {
  await openEditor(c)
  await c.click(c.page.getByRole('button', { name: c.t('ed.exp'), exact: true }).first()); await c.sleep(600)
  await c.snap('editeur-export', { target: '.of-canvas', pad: 0 })
  await c.page.keyboard.press('Escape')
})

// ============================================================================ Vue liste
const nmBtn = (c, fr, en) => c.page.locator('button.nm', { hasText: new RegExp(c.lang === 'fr' ? fr : en, 'i') }).first()
cap('liste', 'liste-classe', async c => {
  await c.goTo('ontologie-liste', { wait: 'button.nm' })
  await c.click(nmBtn(c, '^\\s*Ordre de r', '^\\s*Repair order')); await c.sleep(900)
  await c.snap('liste-classe', { ann: [{ at: '.ol-head', n: 1, box: true, pos: 'tr' }, { at: '.ol-table', n: 2, box: true, pos: 'tr' }, { at: '.ol-sentences', n: 3, box: true, pos: 'tr' }] })
})
cap('liste', 'liste-propriete', async c => {
  await c.goTo('ontologie-liste', { wait: 'button.nm' })
  await c.click(c.page.locator('button', { hasText: /^(Propriétés objet|Object properties)/ })); await c.sleep(600)
  const items = c.page.locator('[role=tab]').first().locator('xpath=ancestor::*[.//button[not(@role="tab")]][1]').locator('button:not([role=tab])')
  await c.click(items.nth(4)); await c.sleep(900)
  await c.snap('liste-propriete')
})

// ============================================================================ Fichiers
const openFiles = async c => { await c.goTo('fichiers', { wait: '.fx .cm-content' }); await c.page.waitForSelector('[data-testid="fx-valid"]:not(:has-text("…"))', { timeout: 15000 }).catch(() => {}); await c.sleep(800) }
cap('fichiers', 'fichiers-editeur', async c => {
  await openFiles(c)
  await c.snap('fichiers-editeur', { ann: [{ at: '.fx-file >> nth=0', n: 1, box: true, pos: 'tr', out: true }, { at: '.cm-content', n: 2, box: false, pos: 'tl' }, { at: '[data-testid=fx-problems]', n: 3, box: true, pos: 'tr' }] })
})
cap('fichiers', 'fichiers-diagnostic', async c => {
  await openFiles(c)
  await c.page.locator('.cm-content').click(); await c.page.keyboard.press('Control+End')
  await c.page.keyboard.insertText('\nfoo:Bar a .\n')
  await c.page.waitForSelector('.cm-lintRange-error', { timeout: 8000 }); await c.page.waitForSelector('.fx-plist .sv-error'); await c.sleep(500)
  await c.snap('fichiers-diagnostic', { ann: [{ at: '.cm-lintRange-error', n: 1, box: true, pos: 'tr', out: true }, { at: '.fx-plist .sv-error', n: 2, box: true, pos: 'tr' }] })
})
cap('fichiers', 'fichiers-diff', async c => {
  await openFiles(c)
  await c.page.locator('.cm-content').click(); await c.page.keyboard.press('Control+End')
  await c.page.keyboard.insertText(`\n# Ajout\n<${c.NS}Tyre> a <http://www.w3.org/2002/07/owl#Class> ;\n    <http://www.w3.org/2000/01/rdf-schema#label> "Pneu"@fr, "Tyre"@en .\n`)
  await c.page.waitForSelector('[data-testid="fx-valid"]:not(:has-text("…"))', { timeout: 8000 }); await c.sleep(900)
  await c.page.keyboard.press('Control+s'); await c.page.waitForSelector('.fx-modal [data-testid="fx-summary"]', { timeout: 8000 }); await c.sleep(600)
  await c.snap('fichiers-diff', { ann: [{ at: '[data-testid="fx-summary"]', n: 1, box: true, pos: 'tr', out: true }, { at: '.fx-diff', n: 2, box: false, pos: 'tl' }] })
  await c.click(c.page.locator('.fx-modal').getByRole('button', { name: c.t('common.cancel') }))
})
cap('fichiers', 'fichiers-genere', async c => {
  await openFiles(c)
  await c.click(c.page.getByRole('button', { name: 'Schema.cs', exact: true })); await c.page.waitForSelector('.fx-banner.gen'); await c.sleep(600)
  await c.snap('fichiers-genere', { ann: [{ at: '.fx-banner.gen', n: 1, box: true, pos: 'tr' }, { at: '.fx-file:has(.lk) >> nth=0', n: 2, box: true, pos: 'tr', out: true }] })
})

// ============================================================================ Shapes, SHACL
cap('shacl', 'shapes-liste', async c => {
  await c.goTo('shapes', { wait: '.shl-item' })
  await c.click(c.page.locator('.shl-item', { hasText: /RepairOrder/ })); await c.sleep(800)
  await c.snap('shapes-liste', { ann: [{ at: '.shl-scroll', n: 1, box: true, pos: 'tr' }, { at: c.page.locator('button.btn.primary', { hasText: c.t('sh.gen') }), n: 2, box: true, pos: 'bl', out: true }] })
})
cap('shacl', 'shapes-generation', async c => {
  await c.goTo('shapes', { wait: '.shl-item' })
  await c.click(c.page.getByRole('button', { name: c.t('sh.gen') })); await c.sleep(1500)
  await c.snap('shapes-generation')
  await c.page.keyboard.press('Escape')
})
cap('shacl', 'shacl-validation', async c => {
  await c.goTo('shacl', { wait: '[data-testid=valid-file], .shl-item' })
  await c.sleep(300)
  await c.page.locator('[data-testid=valid-file]').setInputFiles(c.path.join(c.ROOT, 'samples/automaint/automaint-data.ttl'))
  await c.page.getByText(/\d+ violations?/i).first().waitFor({ timeout: 20000 }); await c.sleep(1000)
  await c.snap('shacl-validation')
})

// ============================================================================ Conformité, HermiT
cap('conformite', 'conformite-profils', async c => {
  await c.goTo('conformite', { wait: '[data-testid=rz-run]' }); await c.sleep(800)
  await c.snap('conformite-profils', { ann: [{ at: '[data-testid=rz-card]', n: 1, box: true, pos: 'tr' }] })
})
cap('conformite', 'hermit-resultats', async c => {
  await c.go(`projet/${c.pidHermit}/conformite`, { wait: '[data-testid=rz-run]' })
  await c.click('[data-testid=rz-run]'); await c.page.waitForSelector('[data-testid=rz-badge]', { timeout: 60000 }); await c.sleep(900)
  await c.snap('hermit-resultats', { ann: [{ at: '[data-testid=rz-badge]', n: 1, box: true, pos: 'tr', out: true }, { at: '[data-testid=rz-unsat]', n: 2, box: true, pos: 'tr' }, { at: '[data-testid=rz-infer]', n: 3, box: true, pos: 'tr' }, { at: '[data-testid=rz-ind]', n: 4, box: true, pos: 'tr' }] })
})
cap('conformite', 'hermit-classe-rouge', async c => {
  await c.go(`projet/${c.pidHermit}/conformite`, { wait: '[data-testid=rz-run]' })
  await c.click('[data-testid=rz-run]'); await c.page.waitForSelector('[data-testid=rz-unsat-link]', { timeout: 60000 })
  await c.click('[data-testid=rz-unsat-link]'); await c.page.waitForSelector('.react-flow__node', { timeout: 15000 }); await c.sleep(1800)
  await c.snap('hermit-classe-rouge', { ann: [{ at: '[data-testid=unsat-banner]', n: 1, box: true, pos: 'tr' }, { at: '.of-node.err', n: 2, box: true, pos: 'tr', out: true }] })
})
cap('conformite', 'krakie-forgeronne', async c => {
  await c.page.route('**/reason', async r => { await c.sleep(4000); await r.continue({ url: r.request().url().replace(c.base, `http://127.0.0.1:${process.env.BACKEND_PORT || 8971}`) }) })
  await c.go(`projet/${c.pidHermit}/conformite`, { wait: '[data-testid=rz-run]' })
  await c.click('[data-testid=rz-run]'); await c.page.waitForSelector('[data-testid=rz-card] [data-kstatus=forge]', { timeout: 5000 }); await c.sleep(900)
  await c.snap('krakie-forgeronne', { target: '[data-testid=rz-card]', pad: 12 })
  await c.page.waitForSelector('[data-testid=rz-badge]', { timeout: 60000 }); await c.page.unroute('**/reason')
})

// ============================================================================ Analyse et arbitrage, modèle, exports, versions
cap('analyse', 'analyse-synthese', async c => {
  await c.goTo('analyse', { wait: '.kpis' }); await c.sleep(800)
  await c.snap('analyse-synthese', { ann: [{ at: c.btn(c.t('an.accept')), n: 1, box: true, pos: 'bl', out: true }, { at: '.kpis', n: 2, box: true, pos: 'tr' }, { at: '.group-h >> nth=0', n: 3, box: true, pos: 'tr' }] })
})
cap('analyse', 'analyse-constat', async c => {
  await c.goTo('analyse', { wait: '.kpis' })
  await c.click('[data-tour=an-rule] .ttl >> nth=0'); await c.sleep(900)
  await c.snap('analyse-constat', { target: '[data-tour=an-rule] >> nth=0', pad: 12, ann: [{ at: '[data-tour=an-finding] .rationale', n: 1, box: true, pos: 'tr' }, { at: '[data-tour=an-finding] .opts', n: 2, box: true, pos: 'tr' }, { at: '[data-tour=an-finding] .reco', n: 3, box: true, pos: 'tr', out: true }] })
})
cap('analyse', 'analyse-neo4j', async c => {
  await c.goTo('analyse', { wait: '.kpis' })
  await c.click(c.btn('Neo4j')); await c.sleep(1800)
  await c.snap('analyse-neo4j')
  await c.click(c.btn('Curiosity')); await c.sleep(800)
})
cap('analyse', 'analyse-regle-appliquee', async c => {
  await c.goTo('analyse', { wait: '.kpis' })
  const apply = c.page.locator('button', { hasText: /(Appliquer la recommandation|Apply the recommendation)/ }).nth(1)
  await c.click(apply); await c.sleep(1800)
  await c.snap('analyse-regle-appliquee', { ann: [{ at: '.kpis', n: 1, box: true, pos: 'tr' }] })
})
cap('modele', 'modele-curiosity', async c => {
  await c.goTo('analyse', { wait: '.kpis' })
  await c.post(`/projects/${c.pid}/decisions/curiosity/accept-recommended`, {}); await c.post(`/projects/${c.pid}/decisions/neo4j/accept-recommended`, {})
  await c.goTo('modele', { wait: 'tbody tr' }); await c.sleep(1800)
  await c.snap('modele-curiosity')
})
cap('modele', 'modele-detail', async c => {
  await c.goTo('modele', { wait: 'tbody tr' }); await c.sleep(1500)
  await c.click(c.page.getByText('RepairOrder', { exact: true })); await c.sleep(900)
  await c.snap('modele-detail', { ann: [{ at: c.page.getByText('RepairOrder', { exact: true }), n: 1, box: true, pos: 'tr', out: true }] })
})
cap('modele', 'modele-neo4j', async c => {
  await c.goTo('modele'); await c.sleep(1500)
  await c.click(c.btn('Neo4j')); await c.sleep(2200)
  await c.snap('modele-neo4j')
  await c.click(c.btn('Curiosity')); await c.sleep(500)
})
cap('exports', 'exports-curiosity', async c => {
  await c.goTo('exports', { wait: 'button.btn.sm' }); await c.sleep(1200)
  await c.click(c.page.getByRole('button', { name: 'Schema.cs', exact: true })); await c.sleep(1000)
  await c.snap('exports-curiosity', { ann: [{ at: c.page.getByRole('button', { name: 'Schema.cs', exact: true }), n: 1, box: true, pos: 'tr', out: true }, { at: c.btn(c.t('common.copy') === '?common.copy' ? 'Copier' : c.t('common.copy')), n: 2, box: true, pos: 'tl', out: true }] })
})
cap('exports', 'exports-neo4j', async c => {
  await c.goTo('exports', { wait: 'button.btn.sm' })
  await c.click(c.btn('Neo4j')); await c.sleep(1500)
  await c.click(c.page.getByRole('button', { name: 'schema.cypher', exact: true })); await c.sleep(1000)
  await c.snap('exports-neo4j')
  await c.click(c.btn('Curiosity')); await c.sleep(500)
})
cap('exports', 'exports-rapport', async c => {
  await c.goTo('exports', { wait: 'button.btn.sm' })
  await c.click(c.page.getByRole('button', { name: 'rapport-transposition.md', exact: true })); await c.sleep(1000)
  await c.snap('exports-rapport')
})
cap('versions', 'versions-ecran', async c => {
  await c.goTo('versions', { wait: 'select' }); await c.sleep(800)
  await c.snap('versions-ecran')
})

// ============================================================================ Requêtes
const useLocalStore = async c => {
  const sel = c.page.locator('select').filter({ hasText: c.t('q.local.opt') }).first()
  const v = await sel.evaluate((s, label) => [...s.options].find(o => o.text.includes(label))?.value, c.t('q.local.opt'))
  await sel.selectOption(v); await c.sleep(900)
}
const loadDemo = async c => { await c.click('[data-testid=local-demo]'); await c.page.waitForFunction(() => /\d{3,}/.test(document.querySelector('[data-testid=local-count]')?.textContent || ''), null, { timeout: 60000 }).catch(() => {}); await c.sleep(1500) }
const openQueries = async c => { await c.goTo('requetes', { wait: 'input[placeholder]' }); await c.sleep(700) }
const ask = async (c, text) => { await c.page.locator('input[aria-label="' + c.t('q.nl') + '"]').fill(text); await c.click(c.btn(c.t('q.nl.go'))); await c.sleep(2500) }
cap('requetes', 'requetes-question', async c => {
  await openQueries(c)
  await ask(c, c.X.nl)
  await c.snap('requetes-question', { ann: [{ at: c.page.locator('input[aria-label="' + c.t('q.nl') + '"]'), n: 1, box: true, pos: 'tr', out: true }, { at: c.btn(c.t('q.nl.go')), n: 2, box: true, pos: 'tr', out: true }] })
})
cap('requetes', 'requetes-valeurs-possibles', async c => {
  await openQueries(c)
  await ask(c, c.lang === 'fr' ? 'véhicules dont le carburant est Diesel' : 'vehicles whose fuel is Diesel')
  await c.click(c.page.getByRole('button', { name: c.t('q.f.oneof') }).first()); await c.sleep(900)
  await c.snap('requetes-valeurs-possibles', { ann: [{ at: '.qchk-list', n: 1, box: true, pos: 'tr' }] })
})
cap('requetes', 'requetes-endpoint-temporaire', async c => {
  await openQueries(c)
  const sel = c.page.locator('select').filter({ hasText: c.t('q.tmp.new') }).first()
  const v = await sel.evaluate((s, label) => [...s.options].find(o => o.text.includes(label))?.value, c.t('q.tmp.new'))
  await sel.selectOption(v); await c.sleep(800)
  await c.page.getByPlaceholder('https://…/sparql').first().fill('https://sparql.example.org/demo/sparql'); await c.sleep(400)
  await c.snap('requetes-endpoint-temporaire', { ann: [{ at: c.page.getByPlaceholder('https://…/sparql'), n: 1, box: true, pos: 'tr', out: true }] })
})
cap('requetes', 'requetes-triplestore-local', async c => {
  await openQueries(c)
  await useLocalStore(c); await loadDemo(c)
  await c.snap('requetes-triplestore-local', { ann: [{ at: '[data-testid=local-panel]', n: 1, box: true, pos: 'tr' }] })
})
cap('requetes', 'requetes-resultats', async c => {
  await openQueries(c); await useLocalStore(c); await loadDemo(c)
  await ask(c, c.lang === 'fr' ? 'véhicules dont le carburant est Diesel' : 'vehicles whose fuel is Diesel')
  await c.click(c.btn(c.t('q.run'))); await c.page.waitForSelector('.qres table, .qres tbody tr', { timeout: 40000 }); await c.sleep(1500)
  await c.page.locator('.qres').first().scrollIntoViewIfNeeded(); await c.sleep(400)
  await c.snap('requetes-resultats-tableau', { target: '.qres', pad: 10 })
  await c.snap('requetes-code', { target: '.qcode', pad: 10 })
  await c.click(c.page.getByRole('tab', { name: c.t('q.res.graph') })); await c.sleep(3200)
  await c.page.locator('.qres').first().scrollIntoViewIfNeeded(); await c.sleep(300)
  await c.snap('requetes-resultats-graphe', { target: '.qres', pad: 10 })
})

// ============================================================================ Assistant, Krakie
const clearChat = async c => { await c.page.evaluate(() => Object.keys(localStorage).filter(k => /^ontoforge\.assistant\./.test(k) && !k.endsWith('.ui')).forEach(k => localStorage.removeItem(k))); }
const openAssistant = async c => { await c.goTo('assistant', { wait: 'textarea' }); await clearChat(c); await c.page.reload(); await c.page.waitForSelector('textarea'); await c.sleep(700) }
cap('assistant', 'assistant-ecran', async c => {
  await openAssistant(c)
  await c.snap('assistant-ecran', { fab: false, ann: [{ at: '.as-start >> nth=0', n: 1, box: true, pos: 'tr' }, { at: 'textarea', n: 2, box: true, pos: 'tr', out: true }, { at: c.page.locator('button.btn.sm', { hasText: c.t('doc.open') }), n: 3, box: true, pos: 'tr', out: true }] })
})
cap('assistant', 'assistant-proposition', async c => {
  await openAssistant(c)
  await c.page.locator('textarea').first().fill(c.X.prose); await c.page.keyboard.press('Enter')
  await c.page.waitForSelector('.as-prop, .pc-item', { timeout: 30000 }); await c.sleep(1500)
  await c.snap('assistant-proposition', { ann: [{ at: '.as-prop', n: 1, box: true, pos: 'tr' }] })
  await c.click(c.page.getByRole('button', { name: c.t('asst.toEditor') }).first()); await c.page.waitForSelector('.react-flow__node', { timeout: 20000 }); await c.sleep(2200)
  await c.snap('editeur-proposition', { ann: [{ at: '.of-proposal', n: 1, box: true, pos: 'tr' }] })
})
cap('assistant', 'assistant-fichier', async c => {
  await openAssistant(c)
  const csv = c.path.join((await import('node:os')).tmpdir(), 'vehicules.csv')
  ;(await import('node:fs')).writeFileSync(csv, 'immatriculation,marque,modele,annee,kilometrage\nAB-123-CD,Renault,Clio,2019,84200\nEF-456-GH,Peugeot,208,2021,35100\nIJ-789-KL,Tesla,Model 3,2022,22800\n')
  await c.page.locator('input[type=file]').first().setInputFiles(csv); await c.sleep(1500)
  await c.snap('assistant-fichier', { ann: [{ at: '.as-file, .as-att, .as-preview', n: 1, box: true, pos: 'tr' }] })
})
cap('assistant', 'assistant-document', async c => {
  await openAssistant(c)
  await c.click(c.page.getByRole('button', { name: c.t('doc.open') }).first()); await c.page.waitForSelector('.di-drop'); await c.sleep(500)
  await c.click('.di-demo'); await c.page.waitForSelector('.di-file .di-est', { timeout: 20000 }); await c.sleep(800)
  await c.snap('assistant-document-import', { ann: [{ at: '.di-file', n: 1, box: true, pos: 'tr' }, { at: c.page.locator('.di button', { hasText: c.t('doc.run') }), n: 2, box: true, pos: 'tr', out: true }] })
  await c.click(c.page.locator('.di button', { hasText: c.t('doc.run') })); await c.page.waitForSelector('.dr-q li', { timeout: 40000 }); await c.page.waitForSelector('.pc-item', { timeout: 15000 }); await c.sleep(1000)
  const item = c.page.locator('.pc-item').first(); await item.locator('.pc-toggle').click(); await c.sleep(600)
  await c.snap('assistant-document-extrait', { ann: [{ at: '.dr-q', n: 1, box: true, pos: 'tr' }, { at: '.pc-quote', n: 2, box: true, pos: 'tr' }] })
})
cap('krakie', 'krakie-contexte', async c => {
  await c.goTo('shapes', { wait: '.shl-item' }); await clearChat(c); await c.page.reload(); await c.page.waitForSelector('.shl-item')
  await c.click(c.page.locator('.shl-item', { hasText: /RepairOrder/ })); await c.sleep(600)
  await c.openKrakie(); await c.sleep(600)
  await c.snap('krakie-contexte', { fab: true, ann: [{ at: '.ag-ctx, .ag-context', n: 1, box: true, pos: 'tr', out: true }, { at: '.ag-chips, .ag-sugg', n: 2, box: true, pos: 'tr', out: true }] })
})
cap('krakie', 'krakie-carte-action', async c => {
  await c.goTo('ontologie', { wait: '.react-flow__node' }); await clearChat(c); await c.page.reload(); await c.page.waitForSelector('.react-flow__node'); await c.sleep(1200)
  await c.openKrakie(); await c.ask(c.X.chatAdd, '.ag-card', { timeout: 25000 }); await c.sleep(800)
  await c.snap('krakie-carte-action', { fab: true, ann: [{ at: '.ag-card >> nth=0', n: 1, box: true, pos: 'tr' }] })
})
cap('krakie', 'krakie-aide', async c => {
  await c.goTo('shapes', { wait: '.shl-item' }); await clearChat(c); await c.page.reload(); await c.page.waitForSelector('.shl-item'); await c.sleep(600)
  await c.openKrakie(); await c.ask(c.X.chatHelp, '.ag-card.help'); await c.sleep(500)
  await c.snap('krakie-aide', { fab: true, ann: [{ at: '[data-testid=ag-open-help]', n: 1, box: true, pos: 'tr', out: true }] })
})

// ============================================================================ Paramètres
cap('parametres', 'parametres-llm', async c => {
  await c.addProvider(); await c.addEndpoint()
  await c.go('parametres', { wait: 'table, .card' }); await c.sleep(700)
  await c.snap('parametres-llm', { upTo: 'main .card', ann: [{ at: 'table', n: 1, box: true, pos: 'tr' }] })
})
cap('parametres', 'parametres-langues', async c => {
  await c.go('parametres', { wait: 'button' })
  await c.click(c.page.getByRole('tab', { name: c.t('settings.tab.lang') }).or(c.page.getByRole('button', { name: c.t('settings.tab.lang') })).first()); await c.sleep(600)
  await c.snap('parametres-langues', { upTo: 'main .card' })
})
cap('parametres', 'parametres-defauts', async c => {
  await c.go('parametres', { wait: 'button' })
  await c.click(c.page.getByRole('tab', { name: c.t('settings.tab.defaults') }).or(c.page.getByRole('button', { name: c.t('settings.tab.defaults') })).first()); await c.sleep(600)
  await c.snap('parametres-defauts', { upTo: 'main .card' })
})
cap('parametres', 'parametres-endpoints', async c => {
  await c.go('parametres', { wait: 'button' })
  await c.click(c.page.getByRole('tab', { name: c.t('settings.tab.sparql') }).or(c.page.getByRole('button', { name: c.t('settings.tab.sparql') })).first()); await c.sleep(700)
  await c.snap('parametres-endpoints', { upTo: 'main .card' }); await c.dropExtras()
})

// ============================================================================ Documentation, limites, mobile
cap('docs', 'documentation', async c => {
  await c.goTo('documentation/utilisateur', { wait: '.doc-article h1' }); await c.sleep(900)
  await c.snap('documentation', { ann: [{ at: '.doc-pages', n: 1, box: true, pos: 'tr' }, { at: '[data-testid=doc-search]', n: 2, box: true, pos: 'tr', out: true }, { at: '.doc-toc', n: 3, box: false, pos: 'tr' }] })
})
cap('limites', 'limites-mobile', async c => {
  const m = await c.browser.newContext({ viewport: { width: 390, height: 844 }, locale: c.lang === 'fr' ? 'fr-FR' : 'en-GB', colorScheme: 'light', deviceScaleFactor: 2 })
  await m.route(`${c.base}/api/**`, r => r.continue({ url: r.request().url().replace(c.base, `http://127.0.0.1:${process.env.BACKEND_PORT || 8971}`) }))
  await m.addInitScript(() => { try { localStorage.setItem('ontoforge.tour.done', '1'); localStorage.setItem('ontoforge.tour.offer', '1'); localStorage.setItem('ontoforge.ed.legend', 'closed') } catch {} })
  const p = await m.newPage(); await p.goto(`${c.base}/#/projet/${c.pid}/ontologie`); await p.reload(); await p.waitForSelector('.react-flow__node', { timeout: 20000 }); await c.sleep(1800)
  await p.screenshot({ path: c.path.join(c.ROOT, 'docs/guide/img', c.lang, 'limites-mobile.png'), animations: 'disabled' }); console.log(`  ${c.lang} limites-mobile`)
  await m.close()
})
cap('limites', 'limites-a-verifier', async c => {
  await c.goTo('exports', { wait: 'button.btn.sm' })
  await c.click(c.page.getByRole('button', { name: 'Connector.cs', exact: true })); await c.sleep(1200)
  await c.snap('limites-a-verifier', { target: '.main, main', pad: 0 })
})

// ============================================================================ en dernier : périmètre (modifie le projet)
cap('zz', 'editeur-perimetre', async c => {
  await c.goTo('ontologie', { wait: '.react-flow__node' }); await c.sleep(1500)
  const sel = n => c.page.locator(`.react-flow__node[data-id="${c.NS}${n}"]`).first()
  await c.click(sel('Vehicle')); for (const n of ['RepairOrder', 'Technician', 'Garage']) await sel(n).click({ modifiers: ['Control'] })
  await c.sleep(500)
  await c.click(c.btn(c.t('ed.peri.fromsel'))); await c.sleep(700)
  await c.snap('editeur-perimetre', { ann: [{ at: '.of-periform', n: 1, box: true, pos: 'tr' }] })
})
