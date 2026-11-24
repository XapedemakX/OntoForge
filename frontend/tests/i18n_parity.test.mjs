// DF-F08 : parité de fr.json et en.json. Mêmes clés, mêmes espaces réservés {x} pour chaque clé,
// aucune valeur vide. Lancement : npm test (node --test).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const load = f => JSON.parse(readFileSync(new URL(`../src/i18n/${f}.json`, import.meta.url), 'utf8'))
const fr = load('fr'), en = load('en')
const holders = s => [...new Set([...String(s).matchAll(/\{(\w+)\}/g)].map(m => m[1]))].sort()

test('fr.json et en.json ont exactement les mêmes clés', () => {
  const kf = new Set(Object.keys(fr)), ke = new Set(Object.keys(en))
  const onlyFr = [...kf].filter(k => !ke.has(k)), onlyEn = [...ke].filter(k => !kf.has(k))
  assert.deepEqual({ onlyFr, onlyEn }, { onlyFr: [], onlyEn: [] }, `clés sans équivalent : fr seul ${onlyFr.slice(0, 10)} ; en seul ${onlyEn.slice(0, 10)}`)
})

test('chaque clé porte les mêmes espaces réservés {x} en français et en anglais', () => {
  const bad = Object.keys(fr).filter(k => k in en && holders(fr[k]).join() !== holders(en[k]).join())
    .map(k => `${k} : fr {${holders(fr[k])}} / en {${holders(en[k])}}`)
  assert.deepEqual(bad, [], 'espaces réservés divergents :\n' + bad.slice(0, 20).join('\n'))
})

test('aucune valeur vide ni non textuelle', () => {
  const bad = ['fr', 'en'].flatMap(l => Object.entries(l === 'fr' ? fr : en).filter(([, v]) => typeof v !== 'string' || !v.trim()).map(([k]) => `${l}:${k}`))
  assert.deepEqual(bad, [])
})
