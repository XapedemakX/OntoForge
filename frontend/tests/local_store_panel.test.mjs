// L53 (revue devfront it1) : après un échec d'une action du panneau du triplestore local (503 « places prises », 413 « espace plein »),
// l'état affiché (case d'inférence, sémantique) doit être relu du serveur, qui a rétabli l'état précédent.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/screens/queries/LocalStorePanel.tsx', import.meta.url), 'utf8')

test('LocalStorePanel : act recharge storeStats dans le catch', () => {
  const act = src.slice(src.indexOf('const act = async'), src.indexOf('const inf = ()'))
  const catchPart = act.slice(act.indexOf('catch (e)'))
  assert.match(catchPart, /setErr\(\(e as Error\)\.message\)/, 'le message d\'erreur reste affiché')
  assert.match(catchPart, /apply\(await qapi\.storeStats\(pid\)\)/, 'storeStats relu puis appliqué (case et sémantique)')
  assert.ok(catchPart.indexOf('setErr') < catchPart.indexOf('storeStats'), 'l\'erreur est posée avant la relecture (elle ne dépend pas d\'elle)')
})

test('LocalStorePanel : apply reprend l\'inférence et la sémantique du serveur', () => {
  const apply = src.slice(src.indexOf('const apply = useCallback'), src.indexOf('useEffect('))
  assert.match(apply, /setInfer\(!!s\.inference\)/)
  assert.match(apply, /setSem\(s\.inference\.semantics\)/)
})

test('LocalStorePanel : le message de purge du serveur est affiché', () => {
  assert.match(src, /st\?\.purged &&/)
  assert.match(src, /data-testid="local-purged"/)
})
