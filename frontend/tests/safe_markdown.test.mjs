// Non-régression SEC-08 : aucun lien ni image actif dans le rendu Markdown des explications.
// Lancement : npm test (node --test). Les schémas d'attaque sont assemblés à l'exécution.
import test from 'node:test'
import assert from 'node:assert/strict'
import { renderSafeMarkdown, safeHref } from '../src/lib/safeMarkdown.ts'

const S = ['java', 'script'].join('')
const bad = [S + ':alert(1)', ['da', 'ta'].join('') + ':text/html;base64,AAAA', ['vb', 'script'].join('') + ':x', ' ' + S + ':alert(1)',
  S.toUpperCase() + ':alert(1)', 'jav\tascr\nipt:alert(1)', '&#106;avascript:alert(1)', '//evil.example/x', 'relative/path']

test('liens et images avec schémas dangereux : ni href ni src actif', () => {
  for (const u of bad) {
    for (const md of [`[clic](${u})`, `![x](${u})`, `[clic][r]\n\n[r]: ${u}`, `<a href="${u}">x</a>`, `<${u}>`]) {
      const html = renderSafeMarkdown(md)
      assert.doesNotMatch(html, /<a\b[^>]*href="(?!https?:|mailto:)/i, `href actif pour ${md}`)
      assert.doesNotMatch(html, /<img\b/i, `image pour ${md}`)
      assert.doesNotMatch(html, /<(a|img|script|iframe)\b[^>]*\s(src|href)=("|')?\s*(java|data:|vb)/i, md)
    }
  }
})

test('liens http, https et mailto conservés, ouverts sans référent', () => {
  const html = renderSafeMarkdown('[a](https://example.org/x) [b](http://example.org) [c](mailto:a@example.org)')
  assert.equal((html.match(/<a href="/g) || []).length, 3)
  assert.match(html, /rel="noopener noreferrer"/)
})

test('HTML brut affiché comme texte', () => {
  const html = renderSafeMarkdown('<img src=x onerror=alert(1)> <script>alert(1)</script>')
  assert.doesNotMatch(html, /<img|<script/i)
  assert.match(html, /&lt;script&gt;/)
})

test('safeHref : liste blanche', () => {
  assert.equal(safeHref('https://example.org'), 'https://example.org')
  assert.equal(safeHref(S + ':alert(1)'), null)
  assert.equal(safeHref(null), null)
})
