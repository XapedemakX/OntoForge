# Réponse à review-w3c-it1.md (conformance/)
1. DatatypeDefinition : corrigé, plus rejetée ; on évalue sa portée (ModelYear reste hors profil pour « facettes »). Test test_it1_datatype_definition_allowed_in_all_profiles.
2. _dr_bad : DataIntersectionOf permis ; Union/Complement interdits partout ; DataOneOf seulement EL à 1 littéral. Test paramétré test_it1_data_ranges_per_profile (5 cas).
3. FunctionalDataProperty admise en EL (QL la rejette toujours). test_it1_functional_data_property.
4. Assertions négatives : attribuées à QL, plus à EL. test_it1_negative_assertions_ql_not_el.
5. QL DataSomeValuesFrom en sous-classe : rdfs:Literal exigé. test_it1_ql_data_some_values_from_sub_requires_literal.
6. RL owl:Thing interdit en sous- et super-classe (le filler Thing d'un ∃ reste admis, PROF §4.2). test_it1_rl_owl_thing_forbidden.
7. Littéraux mal typés : W01 error (`ill_typed`). test_it1_ill_typed_literal.
Non-bloquants traités : « À VÉRIFIER » DisjointUnion retiré (PROF cités) ; W07 ignore les vocabulaires réutilisés (dcterms, skos, vann…) ; libellé DisjointDataProperties ; skill mis à jour.
Non traités (hors périmètre, propriétaire shacl) : sh:pattern ancré et sh:datatype/hiérarchie XSD dans owl_to_shacl.py (bloquants 8 et 9 de la revue), notes de longueur hexBinary.
Suite complète : 408 verts.
