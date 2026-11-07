import { startServers, newPage, chromium, sleep, stopAll } from './lib.mjs'
const srv = await startServers()
const browser = await chromium.launch()
const { page } = await newPage(browser, srv, { scale: 1 })
const screens = process.argv.slice(2)
await page.goto(srv.base + '/#/'); await sleep(1500)
const dump = async (label) => {
  const items = await page.evaluate(() => [...document.querySelectorAll('button, a, input, select, textarea, [data-tour], [role=tab]')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 }).map(e => `${e.tagName.toLowerCase()}${e.dataset.tour ? '[data-tour=' + e.dataset.tour + ']' : ''}${e.className && typeof e.className === 'string' ? '.' + e.className.split(' ').slice(0, 2).join('.') : ''} «${(e.innerText || e.placeholder || e.value || e.title || e.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 50)}»`))
  console.log('\n=== ' + label + ' (' + page.url().replace(srv.base, '') + ')\n' + [...new Set(items)].join('\n'))
}
await dump('accueil')
const proj = await (await fetch(srv.B + '/projects', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: 'x', sample: 'automaint' }) })).json()
for (const s of screens) { await page.goto(`${srv.base}/#/projet/${proj.id}/${s}`); await sleep(1800); await dump(s) }
await browser.close(); stopAll(); process.exit(0)
