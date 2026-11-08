# L22 : éditeur de fichiers intégré (écran « Fichiers »)

Demande de Jerem : un éditeur façon VS Code dans l'appli, pour éditer les fichiers directement, avec application, validation, coloration, etc.

## Livré

| Zone | Contenu |
|---|---|
| Backend | `editing/files.py` (texte canonique, diagnostics, diff, préparation), `api/files.py` : `GET /files`, `GET /files/{path}`, `POST /files/validate`, `POST /files/diff`, `PUT /files/{path}` (422 syntaxe, 403 généré, 409 conflit, historique de `/ops`). Contrat : `docs/CONTRACTS.md` §8 |
| Front | `screens/files/` : arborescence, onglets avec point « modifié », panneau Problèmes repliable, barre d'état, CodeMirror 6 (Turtle, JSON, C#, Cypher, GraphQL maison, repli, Ctrl+F / Ctrl+H, multi-curseur, accolades, thème clair/sombre par jetons), autocomplétion, aperçu merge view + « +N / −M triplets », conflit, annulation, Krakie (`screen: "files"`), mobile en lecture seule |
| Dépendances | `@codemirror/autocomplete` 6.20.4 et `@codemirror/merge` 6.12.3 (versions épinglées) |
| Tests | `backend/tests/test_files_editor.py` (10 tests) ; `tools/recette/l22_files.mjs` (16 contrôles) ; captures dans `journal/L22/screens/` |
| Docs | `docs/CONTRACTS.md` §8, `docs/guide/utilisateur.md` section « Éditeur de fichiers » |

## Choix et limites à connaître

1. Texte canonique. rdflib ordonne les nœuds blancs au hasard : la sérialisation existante n'est pas stable d'une lecture à l'autre (constaté sur l'exemple automaint). L'éditeur ré-étiquette donc le graphe (`to_canonical_graph`) avant d'écrire le Turtle. L'etag est le hash de ce texte. Conséquence : **les commentaires et la mise en forme saisis sont normalisés à l'application** (indiqué dans l'aperçu et le guide).
2. Un seul message de syntaxe par passage : l'analyseur rdflib s'arrête à la première erreur.
3. Position des erreurs. `BadSyntax._i` est un indice de caractère, pas un octet : avec des accents, un calcul sur les octets décale la ligne (bug trouvé et corrigé, test de non-régression). Pour « préfixe non déclaré », rdflib ne donne pas la bonne position : on cherche la première utilisation du préfixe hors chaînes, IRIs et commentaires.
4. Conformité. Calculée sans raisonneur (W06, insatisfiabilité, absent du direct pour tenir l'anti-rebond). Les constats `error` sont remontés en `warning` : seule la syntaxe bloque l'application.
5. Historique. Une application = une entrée `/ops` (champ `onto`, `shapes` ou `decisions`). `view` et périmètres sont conservés ; un IRI renommé dans le texte n'est pas suivi dans les périmètres (comportement d'un remplacement, pas d'un `rename_entity`).
6. Visite guidée : étape non ajoutée. `tools/recette/tour.mjs` borne le total à 18 étapes (`s.total <= 18`) et la visite en compte déjà 18 ; l'ajouter obligerait à changer cette borne. Non fait, à décider.
7. Mobile : lecture seule (aussi côté éditeur : `contenteditable=false`), bandeau « consultation » du shell.
8. À VÉRIFIER : appel `pyshacl.validate(..., shacl_graph=<shacl-shacl>)` sur pySHACL 0.29 (fonctionne ici ; un changement d'API en 0.40 est signalé par la veille L21).

## Vérifications

pytest 588 verts ; `npm run build` vert ; `node tools/recette/e2e_ui.mjs` 30/30 (un premier passage lancé en même temps que la recette L22 a donné 28/30, passage seul : 30/30) ; `node tools/recette/l22_files.mjs` 16/16.

## Relectures demandées

| Relecteur | À vérifier en priorité |
|---|---|
| **w3c** | Validation Turtle et diagnostics : fidélité des lignes/colonnes (point 3), rattachement des constats W01–W07 / BP à la ligne du sujet (`Locator`), choix de ne pas bloquer sur la conformité, normalisation canonique (perte des commentaires) et diff de triplets par graphes isomorphes (`graph_diff`) |
| **shacl** | Méta-validation shacl-shacl (`_shacl_shacl`) : ancrage des résultats sur nœuds blancs (recherche du prédicat et de la valeur fautifs), cas `sh:minCount "x"` où l'import des shapes échoue (`shapes-import`, bloquant) alors que shacl-shacl le signale déjà |
| **scout** | UX : disposition IDE, aperçu avant application, message de conflit à trois choix, bouton Krakie (« explique », « corrige »), lecture seule sur mobile, absence d'étape dans la visite |
