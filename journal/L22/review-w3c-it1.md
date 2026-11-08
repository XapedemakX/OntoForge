# L22 — revue w3c, itération 1

Relecteur : expert W3C (agent `w3c`). Date : 7/11/2026. Périmètre : `backend/ontoforge/editing/files.py`, `backend/ontoforge/api/files.py`, diagnostics Turtle, texte canonique, diff de triplets.
Tests ajoutés : `backend/tests/test_files_editor_review.py` (30 cas). Suite complète : 642 verts.

## Ce qui a été vérifié
- **Aller-retour sans perte** (texte → modèle → texte canonique) :
  - `automaint.ttl` (583 triplets) : graphes isomorphes, aucune perte.
  - `automaint-shapes.ttl` et `trap-shapes.ttl` : isomorphes, et le texte canonique est idempotent.
  - `trap.ttl` : 20 triplets réécrits, 0 perdu. `owl:AllDisjointClasses` n-aire devient des `owl:disjointWith` par paires, et `owl:distinctMembers` (OWL 1) devient `owl:members`. Les deux réécritures sont équivalentes (Mapping to RDF Graphs, tableaux 1 et 2) et annoncées par `[nary_disjoint_expanded]`.
  - `trap-nondl.ttl` : `rdf:Property` non typée devient `owl:AnnotationProperty` (avertissement `[untyped_property]`), et les déclarations manquantes sont ajoutées.
  - Les triplets hors modèle sont conservés (`unmapped`).
- **Nœuds blancs et listes** : deux restrictions identiques (nœuds automorphes), deux listes identiques (pas de partage de nœuds de liste, que le §2.3 du mapping interdirait), `owl:oneOf`, annotation sur nœud blanc. Tout est isomorphe et le nombre de triplets est conservé.
- **Diff +N / −M** : `graph_diff` compare les graphes canoniques, ce qui revient à un isomorphisme et non à une comparaison naïve. Un même graphe dont les nœuds blancs sont ré-étiquetés et les triplets réordonnés donne 0 / 0, sans changement. Changer une cardinalité donne un écart local (≤ 4 triplets).
- **Diagnostics** : ligne et colonne justes avec des accents, préfixe non déclaré placé correctement malgré les leurres (commentaire, chaîne, IRI `http://zz:8080`), point manquant, chaîne non terminée. L'étiquette de langue `fr-FR` est conservée, et `"1.50"^^xsd:decimal` aussi.

## Verdict

```
verdict: KO
bloquants:
  - [frontend/src/i18n/fr.json:1245, en.json:1245 ; frontend/src/screens/files/index.tsx:289] le choix du texte canonique est acceptable : rdflib ne garde ni les commentaires ni l'ordre, et les commentaires ne font pas partie du graphe (RDF 1.1 Turtle §2). L'avertissement, lui, est trompeur et peu visible. La note dit « les commentaires … sont normalisés » alors qu'ils sont **supprimés**. En plus, l'aperçu compare canonique à canonique : le texte saisi n'apparaît d'aucun côté, l'utilisateur ne voit donc jamais ses commentaires disparaître. → Écrire « Les commentaires (#) et la mise en forme ne sont pas conservés : le fichier est réécrit sous forme normalisée ». Compter les commentaires du texte saisi (`_mask` existe déjà : lignes avec `#` hors chaîne et hors IRI) et, s'il y en a, afficher un avertissement visible dans l'aperçu : « N commentaire(s) seront supprimés ». (fr.json est en cours de réécriture par un autre agent : non corrigé ici.)
  - [backend/ontoforge/editing/files.py:545] le résumé +N / −M compare le modèle avant au modèle après, jamais le texte saisi au résultat. Les réécritures de l'import (AllDisjointClasses éclaté, rdf:Property retypée, déclarations ajoutées) ne sont donc visibles qu'au fond d'un « {n} remarque(s) » replié. → Ajouter au résumé `rewritten` = `graph_diff(graphe du texte saisi, graphe après)` (nombre et échantillon), et l'afficher à côté de +N / −M (« dont K triplets de votre texte réécrits »). C'est la seule façon de prouver à l'utilisateur qu'il n'y a pas de perte.
non-bloquants:
  - [backend/ontoforge/editing/files.py:59] un texte collé sans `@prefix` (N-Triples par exemple) donne 0 / 0 triplets mais `changed = true` : les préfixes du projet (dcterms, skos) sont remplacés par `ns1:`, `ns2:`. Fusionner les préfixes du projet avec ceux du texte, ou dire dans l'aperçu « seuls les préfixes changent ».
  - [backend/ontoforge/editing/files.py] rdflib normalise certaines formes lexicales à l'analyse (`"01"^^xsd:integer` lu comme `1`). Ce sont deux termes distincts selon RDF 1.1 Concepts §3.3. Effet limité, mais le dire dans le guide (« les littéraux numériques peuvent être réécrits sous forme canonique »).
  - [backend/ontoforge/editing/files.py:197] « point attendu » est signalé au début de l'instruction **suivante** (où rdflib s'arrête). Si la ligne précédente n'est pas vide, placer plutôt le diagnostic à sa fin.
  - [backend/ontoforge/editing/files.py:198-201] erreurs non `BadSyntax` (étiquette de langue invalide `@1fr`) : toujours ligne 1, colonne 1. Chercher le jeton fautif dans le texte, comme pour les préfixes.
  - [backend/ontoforge/editing/files.py:217] `Locator` ne retrouve pas un sujet écrit en IRI relative résolue par `@base` : il retombe sur 1:1. Mineur.
  - [backend/ontoforge/io/rdf_import.py:165] même défaut d'IRI relative à l'import de fichiers (voir la revue w3c L21). Lot d'import.
corrigé par le relecteur (backend/ontoforge/editing/files.py, tests dans test_files_editor_review.py) :
  - **IRI relative sans @base** : rdflib la résolvait contre le répertoire courant du serveur, si bien que `<Truc>` devenait `file:///home/…/backend/Truc` (ou `file:///app/backend/Truc` dans l'image Docker) et entrait dans l'ontologie, sans aucun diagnostic. L'analyse se fait maintenant avec une base sentinelle ; toute IRI qui en hérite donne une **erreur** localisée (`turtle-relative-iri`, Turtle §6.3). Avec `@base`, le comportement est inchangé.
  - **IRI avec espace ou caractère interdit** (`<http://e.org/a b>`) : rdflib l'acceptait. C'est maintenant une erreur `turtle-bad-iri` (production IRIREF, Turtle §6.4).
  - **Littéral mal typé** (`"abc"^^xsd:integer`) : rien n'était signalé. Il donne maintenant un avertissement `ill-typed-literal` sur sa ligne : RDF l'admet, mais il rend l'ontologie incohérente en OWL 2 DL (Direct Semantics §2.3.1).
skill: w3c-ontology-conformance → « Éditeur Turtle : publicID sentinelle pour détecter les IRI relatives ; refuser les IRIREF contenant espace ou <>\"{}|^`\\ ; signaler Literal.ill_typed ; un diff de graphes avec nœuds blancs passe par rdflib.compare.graph_diff (canonique), jamais par une différence d'ensembles brute. »
```
