# Réponse à la revue W3C it1 (agent query)
- Bloquant 1 (classe absente -> `MATCH (x)` sur-ensemble) : corrigé. `NodeVar.empty` ; la classe absente donne `WHERE false` + `[perte]`, lossy=True. Tests `test_unknown_class_never_untyped_superset`.
- Bloquant 2 (deux types sur un discriminant) : corrigé. Intersection des valeurs ; vide -> `[perte]` « types multiples non représentables par un discriminant mono-valué » + `WHERE false`. « Parent puis sous-type » conservé. Tests `test_two_discriminant_types_lossy`, `test_parent_then_subtype_keeps_precise`.
- Bloquants 3-4 (profils curiosity/neo4j) : hors de mes fichiers, non traités (à voir par leurs propriétaires).
- Fixtures régénérées : `onto_automaint.json` depuis `parse_ontology(automaint.ttl)` ; `pg_automaint.json` construit par script avec les vraies IRIs am: (ownedBy, ofModel, hasRepairOrder, ElectricVehicle/CombustionVehicle aplatis, concerns/readingOf non stockés car inverses déclarés ; usesFuel volontairement absent = perte). q02, q03, q05, q06, q09 réécrites. competency.py inchangé et fonctionne (10 questions, aucune lossy).
- Non-bloquant ajouté : test `owl:inverseOf` avec onto -> traversée inverse, lossy False. Non traités : note zéro saut de `*`, Long GraphQL.
- Suite complète : 412 tests verts.

## Itération 2 (revue W3C it2)
- Bloquant (translate.py ~l.360, propriété absente du PG dans un motif obligatoire) : corrigé. Hors OPTIONAL, la condition `false` est ajoutée au bloc + `[perte]` « motif obligatoire insatisfiable, le bloc ne renvoie rien » + lossy=True. Dans un OPTIONAL, comportement conservé (triplet ignoré, variables non liées, note `[perte]`).
- Tests ajoutés : `test_missing_property_in_mandatory_pattern_gives_empty_block` (`ownedBy` + `nope`), `test_missing_edge_without_onto_gives_empty_block` (`am:concerns` sans ontologie), `test_missing_property_in_optional_keeps_rows`.
- Suite complète : 431 tests verts.
