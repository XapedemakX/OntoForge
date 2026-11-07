# L9 — corrections après revue W3C it1 (lead)

| Bloquant | Correction | Test |
|---|---|---|
| §11.2 dans les ClassExpr imbriquées | `integrity_errors` parcourt toutes les expressions (`equivalent_to`, `super_expressions`, `filler_expr`, `domain_expr`, `range_expr`, récursivement) via `_all_exprs` | `test_w3c1_nested_cardinality_blocks_non_simple` |
| Disjonction avec propriété non simple | contrôle dès que p **ou** un élément de `p.disjoint_with` est dans `ns` | `test_w3c2_disjoint_properties_need_simple_on_both_sides` |
| Vocabulaire réservé | `add_class`, `add_object_property`, `add_datatype_property` et `rename_entity` refusent toute IRI dans rdf:, rdfs:, owl:, xsd: | `test_w3c3_reserved_vocabulary` (4 IRIs × 3 opérations) |
| `delete_entity` tronque les expressions | retrait de l'**axiome entier** (`equivalent_to`, `super_expressions`, restriction à `filler_expr`, `domain_union`/`range_union`, `domain_expr`/`range_expr`, `one_of`, définition de datatype) avant le nettoyage des listes simples ; avertissement listant les axiomes retirés ; test de présence d'IRI sur la forme citée (plus de faux positifs sur préfixes) | `test_w3c4_delete_removes_whole_axioms`, `test_w3c4_delete_keeps_prefix_lookalikes` |
| P01 absent pour propriété héritée | `touched` inclut les ancêtres hors périmètre dont une classe du périmètre descend ; le détail dit « serait héritée par … » | `test_w3c5_inherited_property_reports_p01` |

**D-L9-02** : `NodeType.icon` (rempli dans `run_analysis` depuis `Project.view.icons`, première classe source illustrée ; transmis au diagramme Mermaid Neo4j par `note for X "icône : fa-…"`) ; sévérité `info` pour P00–P03, ignorée par `PGModel.summary()` et par tous les consommateurs de « à arbitrer » (`!= "auto"` remplacé par `in ("review","lost")` dans analysis, report, neo4j). Test : `test_d_l9_02_info_severity_and_icon`. Front : type `info`, section « Informations (périmètre) » dans Analysis, compteurs du tableau de bord et de l'analyse inchangés ; `NodeType.icon` typé. Les tests de périmètre attendent `info`.
Suite : 545 verts ; `npm run build` vert. Points « vendredi » et non-bloquants : non traités.

## Itération 2 — bloquants « vendredi »
| Bloquant | Correction | Test |
|---|---|---|
| Propriété héritée perdue | `perimeter.restrict` projette une extrémité unique hors périmètre (domaine ou portée) sur ses descendants du périmètre : une cible → liste, plusieurs → `domain_union`/`range_union`. Une propriété avec union ou expression hors périmètre reste exclue ; une propriété non listée dans `properties` n'est jamais projetée. P01 « Relation / Attribut restreint(e) » explique la projection. Dans l'analyse, V→G devient Car→G | `test_w3c_it2_inherited_property_is_projected_on_perimeter_subclass` (+ mise à jour de `test_w3c5_…`) |
| `hasValue` mal typé | `check_literal` : forme lexicale (entiers et bornes, décimal, flottants, booléen, dateTime/dateTimeStamp, date, hexBinary) ; `value_lang` incompatible avec un datatype autre que rdf:langString refusé | `test_w3c_it2_hasvalue_literal_must_be_well_typed` |
| Disjonction de classes équivalentes | `equivalence_class` (clôture des `equivalent_to` nommés, deux sens) et `related_by_subclass_or_equiv` : refus à `add_disjoint` et contrôle d'intégrité global (directe, par chaîne, ou via sous-classe d'une équivalente) | `test_w3c_it2_disjoint_equivalent_classes_refused` |
Suite : 548 verts.
