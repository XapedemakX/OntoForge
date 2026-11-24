# L53 DF-B12 : réponse aux relectures it1 (query KO, curiosity KO, neo4j OK)

Pilote : devback. Détail problème / correction / résultat : `journal/L53/corrections-b12.md#it2`, `#df-b14`, `#df-b15`. Tests : `backend/tests/test_l53_b12.py`, 32 tests (30 rouges sur 23b0e1c, 15 rouges sur 183f0fd). Suite complète : 1680 verts. `test_business_map.py::test_layout_automaint` est vert ici ; l'instabilité signalée par query et curiosity n'a pas été reproduite et sort du lot.

## Bloquants

| Revue | Bloquant | Fait |
|---|---|---|
| query 1 | Typage disjoint dans un sous-motif sans `[perte]` | `_check_sub_types` + `_compatible` (même type de nœud et même discriminant, ou label porté par l'autre type) : note `[perte]` « intersection non représentable », `lossy = true`, prédicat inchangé. `ev_exists_cv`, `ev_notexists_cv`, `notexists_two_types` (deux cibles) repassent en perte ; `exists_rel_typed` reste sans perte. Tests : `_loss_ok` dans les deux tests paramétrés. corrections-b12.md : l. 12, tableau et ligne « Pertes » corrigés (une seule fausse perte en it1, `exists_rel_typed` sur neo4j). |
| query 2 | Classe absente sous NOT → `true` | `sub_condition` : sous `NOT EXISTS` / `MINUS`, un sous-motif insatisfiable (classe absente, nouveau nœud vide, propriété absente) donne `false` pour toute la condition, avec une note `[perte]`, y compris avec une relation. Test `test_b12_absent_class_in_subpattern` : 5 formes niées sur 2 cibles. docs/dev/09 fr/en et corrections-b12.md mis à jour. Pas de décision d'amendement de la règle de sûreté : elle est appliquée. |
| curiosity 1 | C# de `exists_rel_typed` sans restriction ni marque partielle | Un typage capturé rend le sous-motif non simple, et `cs_expr` met `curiosity_ok` à faux pour tout `EXISTS` / `NOT EXISTS` non traduit (seconde option proposée). Tests : `test_b12_type_and_relation_in_subpattern` vérifie le C# ; `test_b12_csharp_untranslated_exists_is_partial` vérifie le cas `NOT EXISTS` avec relation (préexistant, signalé en non-bloquant). |

## Non-bloquants retenus

- Garde `_EMPTY_MATCH` : elle ignore désormais les chaînes `'…'` et les identifiants `` `…` `` (`_CY_STRINGS`). Test `test_b12_guard_ignores_string_literals`.
- `.Where(n => false)` : le commentaire devient `// aucun résultat (type du nœud)`.
- DF-B14 (MINUS sans variable partagée) : consigné puis corrigé. La condition est retirée, avec une note `[info]` qui cite §8.3.3. Test `test_b14_*`.
- DF-B15 (FILTER sur une variable d'OPTIONAL) : consigné puis corrigé. La condition passe après l'`OPTIONAL MATCH`, dans `WITH * WHERE …`. Tests `test_b15_*`.
- DF-B16 (fausse perte « Relation incompatible » vers un sous-type, neo4j) : consigné dans `journal/L51/defauts.md`, non corrigé (consigne).

## Non-bloquants laissés

- Deux idiomes C# pour le discriminant (`.WhereString` au niveau principal, `.Where(n => n.GetString(…) == …)` en sous-motif) : à unifier quand l'API Query sera confirmée (À VÉRIFIER).
- Doubles parenthèses `!((a && b))`, `v:Vehicle AND` redondant sur curiosity, relation redondante dans `EXISTS { MATCH (o)-[:CONCERNS]->(v) WHERE v:ElectricVehicle }` : cosmétique, non traité.
- Validité sur un vrai Neo4j 5 (`EXISTS { MATCH (v) WHERE … }`, `coalesce`, `WITH *` puis `WHERE`) : toujours `À VÉRIFIER`, faute de base.

## Sorties changées (scripts `/home/claude/b12tools`, rejoués)

- Corpus de 148 traductions, avant L53 → it2 : 56 changées, toutes avec `EXISTS`, `NOT EXISTS`, `MINUS` ou un `FILTER` sur une variable d'OPTIONAL. Aucune fixture, question de compétence ni requête trap ne change. it1 → it2 : 41 changées.
- Requêtes des tests : 80 entrées communes, 1 changée (C# de la question guidée « garage sans technicien », désormais marqué partiel).
- Aucun `MATCH` vide.
