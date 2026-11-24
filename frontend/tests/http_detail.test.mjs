// DF-F02 : lecture de `detail` partagée par tous les clients API (lib/httpDetail.ts).
import test from 'node:test'
import assert from 'node:assert/strict'
import { detailMessage, detailCode } from '../src/lib/httpDetail.ts'

test('detail en chaîne : renvoyé tel quel', () => assert.equal(detailMessage({ detail: 'Projet introuvable' }, 'Erreur 404'), 'Projet introuvable'))
test('detail en liste : messages joints', () => {
  const body = { detail: [{ loc: ['body', 'name'], msg: 'obligatoire' }, { loc: ['body', 'url'], msg: 'invalide' }] }
  assert.equal(detailMessage(body, 'Erreur 422'), 'obligatoire ; invalide')
})
test('detail en liste avec withLoc : dernier élément de loc en préfixe', () => {
  const body = { detail: [{ loc: ['body', 'name'], msg: 'obligatoire' }, { msg: 'seul' }] }
  assert.equal(detailMessage(body, 'Erreur 422', true), 'name : obligatoire ; seul')
})
test('corps absent, vide ou de forme inconnue : message de repli', () => {
  for (const b of [undefined, null, {}, 'texte', 42, { detail: 3 }, { detail: null }]) assert.equal(detailMessage(b, 'Erreur 500'), 'Erreur 500')
})
test('code stable du serveur', () => {
  assert.equal(detailCode({ code: 'last_admin', detail: 'x' }), 'last_admin')
  for (const b of [undefined, null, {}, { code: 3 }]) assert.equal(detailCode(b), undefined)
})
