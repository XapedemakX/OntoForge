# L53 DF-B12 : réponse aux relectures it2 (query KO, curiosity KO, neo4j OK)

Pilote : devback. Détail : `journal/L53/corrections-b12.md#it3`, `#df-b18`, `#comparaison-it3`. Tests : `backend/tests/test_l53_b12.py`, 51 tests (20 rouges sur 0e70f58). Suite complète : 1699 verts.

## Bloquants

| Revue | Bloquant | Fait |
|---|---|---|
| query 1 | Sous-motif sur une variable d'OPTIONAL non liée, écart à SPARQL avec `lossy = false` | Formes exactes : `MINUS` → `(v IS NULL OR …)` (§18.5) ; `EXISTS` / `NOT EXISTS` réduits à un typage → `CASE WHEN v IS NULL THEN [NOT] EXISTS { MATCH (_any1) WHERE … } ELSE … END` (§18.6), sur les deux cibles. Autres cas (propriété, relation, `MINUS` sur une autre variable) : `[perte]`, `lossy = true`. Le test l. 225 attend la forme `CASE` ; `not lossy` y reste, puisque la forme est exacte. Tests : `test_it3_subpattern_on_unbound_optional_variable_is_exact` (3 formes × 2 cibles) et `test_it3_subpattern_on_optional_variable_without_exact_form_is_a_loss` (3 formes × 2 cibles). |
| curiosity 1 | Filtre C# sur un nœud d'OPTIONAL perdu sans marque | `curiosity()` suit les nœuds dont les filtres sont écrits (chaîne, sous-ensembles) ; tout autre filtre met `curiosity_ok` à faux et ajoute la note `[curiosity] Filtre sur ?v (hors de la traversée…) non écrit`. Aussi : sur la cible neo4j, un typage par un sous-type d'un nœud atteint par une relation n'est plus jugé « toujours vrai » (`cs_type_check` lève `_Unsupported`, sortie partielle). Test : `test_it3_csharp_filter_on_optional_node_marks_partial` (MINUS, NOT EXISTS, EXISTS sur curiosity, MINUS sur neo4j). |

## Nouveau défaut DF-B18 (consigné et corrigé)

Consigné dans `journal/L51/defauts.md` (majeur, « corrigé L53 »). `OPTIONAL` et `BIND` restent dans le sous-motif : l'état (nœuds, propriétés, alias, blocs) est restauré après le rendu. Un `OPTIONAL` est ignoré quand c'est exact, sinon `[perte]`. Un `BIND` sur une variable principale donne `[perte]`. Les variables propres au sous-motif projetées valent `null` (`[info]`). Plus aucun Cypher invalide sur les cas de la revue. Tests : `test_b18_optional_inside_subpattern_stays_inside`, `test_b18_bind_inside_subpattern_stays_inside`, `test_b18_subpattern_variables_do_not_leak_into_projection` (deux cibles).

## Non-bloquants

- Coquille de `diff3.py` (étape niée étiquetée « negfilter ») : corrigée.
- C# des éléments absents sous négation (`.Where(n => false)` plutôt qu'une sortie partielle complète) : non traité, cosmétique tant que la sortie est marquée partielle.
- Fusion avec L53-b13 : aucun appel nouveau à l'analyseur rdflib dans `translate.py`.
- Formes Neo4j (`CASE … EXISTS { … }`, `WITH *`, `coalesce`) : toujours `À VÉRIFIER` sur une base Neo4j 5.

## Sorties changées

168 traductions : 76 changées depuis 23b0e1c, 24 depuis l'it2 (variables d'OPTIONAL et DF-B18 seulement). Requêtes des tests : 1 changée sur 80, la même qu'en it2. Aucun `MATCH` vide.
