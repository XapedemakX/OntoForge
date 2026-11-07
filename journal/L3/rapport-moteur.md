# L3 — Rapport du moteur de mapping (lead)

## Livré
- `backend/ontoforge/mapping/engine.py` : `analyze(onto, shapes, target, decisions) -> PGModel` (déterministe, environ 20 ms par cible sur trap).
- `mapping/rules/` : `catalog.py` (66 règles + S01/S02/G02, vocabulaire d'options de l'oracle), `_base.py` (contexte,
  relecture des triplets non mappés, ids D-035), une famille par module : `classes` C01–C13, `keys` K01–K05,
  `data` D01–D13, `objects` O01–O21, `reification` R01–R02, `annotations` A01–A03/M01–M02/G01, `individuals` I01–I05,
  `naming` N01, `shacl` S01–S02. Chaque règle = `detect(ctx)` pure + application (plan ou construction).
- `mapping/decisions.py` : rejeu des décisions, une option invalide donne un constat G02, les décisions orphelines sont conservées.
- `mapping/profile_api.py` : interface `Profile` au-dessus de `profiles/curiosity.py` et `profiles/neo4j.py`, avec repli interne.
- `targets/report.py` : rapport Markdown français. Démos : `journal/L3/demo-report-curiosity.md` et `demo-report-neo4j.md`.
- `docs/RULES.md` (rendu du catalogue), `skills/owl-to-property-graph/SKILL.md`.
- Tests : `test_mapping_oracle.py` (oracle complet × 2 cibles, must_not, aucune perte silencieuse),
  `test_mapping_engine.py` (invariants, déterminisme, décisions, option invalide, accepter tout, registre,
  performance, automaint), `test_report.py`. Suite complète : 431 tests verts.

## Couverture de l'oracle
- **100 %** : 79/79 constats (règle, sujet, sévérité, recommandation) pour Curiosity et pour Neo4j ; 6/6 `must_not`.
- Les générateurs `targets/curiosity.py`, `targets/neo4j.py` et `targets/graphql.py` tournent sans erreur sur le PGModel produit.

## Limites connues
- Volume d'arbitrage sur trap : environ 130 constats `review` (un I01 par individu, un K03 par type racine). C'est utile
  pour la traçabilité mais bruyant. Proposition pour l'itération 2 : regroupement par règle dans l'interface et
  « accepter la règle ».
- D08 `reference_nodes` et C08 `enum_property` sont acceptés mais transposés de façon minimale (description et
  validation, pas de type de nœud dédié ni de suppression de l'arête).
- O05 `edge_pair` côté Neo4j (stocker les deux sens) n'ajoute pas l'arête retour. O12 `materialize_at_ingest` ne
  produit qu'une matérialisation.
- Les constructs anonymes sont relus depuis `OntoModel.unmapped`. Si l'import (w3c) les structure un jour
  (`domain_union`, `range_expr`, `super_expressions`), les règles lisent déjà ces champs en priorité.
- La conformité de la convention Curiosity (PascalCase partout, `Link(a, b, X, X)` pour symétrique) reste À VÉRIFIER (expert curiosity).
- Écarts au contrat de lot : `journal/L3/ecarts-oracle.md`. Demandes de contrat : `journal/L3/demandes-contrat.md`.
