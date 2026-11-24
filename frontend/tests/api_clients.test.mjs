// DF-F01 / F02 / F04 / F05 / F06 : garde-fous de code sur les clients API et l'interface.
// Chaque contrôle lit les sources ; une régression (nouveau fetch en dur, message français codé en dur,
// évènement sans récepteur…) fait échouer `npm test`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'

const SRC = new URL('../src', import.meta.url).pathname
const files = (d = SRC) => readdirSync(d, { withFileTypes: true }).flatMap(e => e.isDirectory() ? files(join(d, e.name)) : /\.(ts|tsx)$/.test(e.name) ? [join(d, e.name)] : [])
const rel = f => relative(SRC, f).replaceAll('\\', '/')
const code = f => readFileSync(f, 'utf8').split('\n').filter(l => !/^\s*(\/\/|\*|\/\*)/.test(l)).join('\n')
const all = files().map(f => [rel(f), code(f)])

test('DF-F02 : les clients API passent tous par lib/http.ts (aucun fetch + lecture de detail dupliqué)', () => {
  const clients = ['api.ts', 'assistant-global/gapi.ts', 'screens/assistant/aapi.ts', 'screens/editor/types.ts', 'screens/queries/qapi.ts', 'screens/settings/settingsApi.ts', 'screens/files/fapi.ts', 'lib/proposal.ts']
  for (const [f, s] of all) if (clients.includes(f)) {
    assert.doesNotMatch(s, /\bfetch\(/, `${f} appelle fetch directement`)
    assert.doesNotMatch(s, /\.detail\b/, `${f} lit detail lui-même`)
    assert.match(s, /from '(\.\.\/)*(\.\/)?(lib\/)?http'/, `${f} n'importe pas lib/http`)
  }
})

test('DF-F02 : `detail` n\'est lu que dans lib/httpDetail.ts (et par les consommateurs de réponses déjà décodées)', () => {
  const readers = all.filter(([, s]) => /\b(j|js|json|body|res|resp)\??\.detail\b|\[['\"`]detail['\"`]\]|\bdetail\s*[,}]\s*=|typeof [\w.?]*detail|\.detail\)?\s*===?\s*'string'/.test(s)).map(([f]) => f)
  // collab/rev.ts lit le corps déjà décodé d'un 409/428 (conflit), pas une réponse brute
  assert.deepEqual(readers.filter(f => f !== 'lib/httpDetail.ts' && f !== 'collab/rev.ts'), [])
})

test('DF-F01 : aucun « Serveur injoignable » en dur (clé ui.unreachable)', () => {
  const hits = all.filter(([, s]) => /Serveur injoignable|Server unreachable/.test(s)).map(([f]) => f)
  assert.deepEqual(hits, [])
})

test('DF-F04 : aucun évènement window « ontoforge:authed » ou « ontoforge:project » (sans récepteur)', () => {
  const hits = all.filter(([, s]) => /ontoforge:(authed|project)\b/.test(s)).map(([f]) => f)
  assert.deepEqual(hits, [])
})

test('DF-F04 : tout évènement « ontoforge:* » émis a un récepteur', () => {
  const src = all.map(([, s]) => s).join('\n')
  const names = new Set([...src.matchAll(/(?:Event|CustomEvent)\('(ontoforge:[\w-]+)'/g)].map(m => m[1]))
  const listened = n => {
    const c = src.match(new RegExp(`const (\\w+) = '${n}'`))?.[1]   // nom porté par une constante (ex. OPEN_EVENT)
    return new RegExp(`addEventListener\\((?:'${n}'${c ? `|${c}` : ''})`).test(src)
  }
  const orphan = [...names].filter(n => !listened(n))
  assert.deepEqual(orphan, [])
})

test('DF-F05 : ApiError n\'expose plus de getter notReady mort', () => {
  const api = all.find(([f]) => f === 'api.ts')[1]
  assert.doesNotMatch(api, /get notReady/)
  const used = all.filter(([f, s]) => f !== 'screens/settings/settingsApi.ts' && /\.notReady\b/.test(s) && !/SettingsError/.test(s)).map(([f]) => f)
  assert.deepEqual(used, [])
})

test('DF-F06 : chaque page citée dans ORDER (lib/docs.ts) existe dans docs/guide', () => {
  const m = readFileSync(join(SRC, 'lib/docs.ts'), 'utf8').match(/const ORDER = \[([^\]]*)\]/)
  const pages = [...m[1].matchAll(/'([\w-]+)'/g)].map(x => x[1])
  assert.ok(pages.length > 3)
  const guide = join(SRC, '../../docs/guide')
  assert.deepEqual(pages.filter(p => !readdirSync(guide).some(f => f.toLowerCase() === p + '.md')), [])
})
