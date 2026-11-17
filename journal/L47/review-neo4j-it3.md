verdict: OK
bloquants:
  - aucun.
non-bloquants:
  - Neo4j inchangé : `git diff 43033cb b89f895` ne touche ni `targets/neo4j.py` ni la branche Neo4j du moteur ; `_tightens_curiosity` n'agit que pour `ctx.target == "curiosity"`. Les 29 reclassements Neo4j (D13 x13, O09 x10, O10 x5, D09 x1) sont identiques à l'it2.
  - Mesure reproduite par `analyze(automaint.ttl, None, "neo4j", {})` : 19 constats (K02 6, C02 3, C07 3, D05 3, C04 2, C08 1, O06 1), 8 groupes (3 racines + K02, C07, D05, C08, O06), dont 4 perdus. Conforme à fix-it2, rapport, D-L47-01, guide, CHANGELOG.
  - Motif D09 Neo4j (« requêtes Cypher de détection, non bloquantes ; une valeur absente n'est pas une violation ») : exact, une comparaison Cypher sur une propriété nulle ne renvoie pas la ligne (voir le générateur, branche `range`).
  - Tests : suite complète 1324 passed ; test_target_neo4j, test_mapping_oracle verts.
skill: rien (neo4j-schema-design : les validations Neo4j sont des requêtes de détection, jamais bloquantes ; c'est ce qui justifie l'auto, contrairement à Curiosity).
