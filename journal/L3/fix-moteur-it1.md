# L3 — Réponse à la revue w3c it1 (journal/L3/review-w3c-it1.md)

Suite complète : **442 tests verts**. Non-régression : `backend/tests/test_mapping_regressions.py` (un test par bloquant + décision groupée + bruit automaint). Oracle trap : 79/79 et 6/6 `must_not` pour les deux cibles (écarts tracés dans `ecarts-oracle.md`).

## Bloquants
1. **Ordre des chaînes** : fait. `finding()` ne trie plus `related` ; O08 relit `v.chains[i]` : l'ordre et les répétitions `p ∘ p` sont conservés dans `Materialization.chain`. → `test_b1_chain_order_and_repetition`.
2. **O08 inclusion** : fait. Le texte est `p ∘ q ⊑ r`. `r` est stockée dans les deux cibles (`derived=False`, plus de saut Neo4j) ; la matérialisation (Curiosity) ou la requête de chemin (Neo4j, note) vient en complément. → `test_b2_chain_is_inclusion_and_edge_kept`.
3. **Domaine / portée complexes** : fait. `Ctx.endpoints()` : une intersection est rattachée à chaque conjoint nommé, avec D12 / O21 ; une expression non réductible donne un G01 explicite. → `test_b3_complex_domain_never_silent`.
4. **Héritage aplati** : fait. `classes.scope()` : une restriction, une shape ou un hasKey d'une sous-classe repliée ne touche ni `required`, ni la cardinalité d'arête, ni la clé de la racine ; la validation porte `discriminator` + `values`, et `target_discriminator_values` pour un filler aplati. Les extrémités d'arête issues de sous-classes repliées reçoivent une validation `EP:…`. Sur automaint, `Party.BrandName` n'est plus obligatoire. → `test_b4_flattened_subclass_restriction_is_scoped`, `test_noise_automaint`.
5. **Cardinalité inventée** : fait. `{"0..*": "1..*", "1..*": "1..*", "0..1": "1", "1": "1"}`, sans effet pour une sous-classe aplatie. → `test_b5_two_some_is_not_exactly_one`.

## Non-bloquants traités
- Bruit : D13 `max 1` → `auto` et décision groupée `D13:*` (mécanisme générique `<règle>:*`) ; K03 avec clé IRI → `auto` ; C02 par racine de hiérarchie ; C07 Curiosity → `auto` si garanti par construction.
- **Automaint, review + lost : 80 → 49 (Curiosity), 80 → 52 (Neo4j)**. Décompte auto / review / lost : Curiosity 117 / 48 / 1, Neo4j 114 / 48 / 4.
- Titre O09 corrigé ; impact de `flatten_into_leaves` réécrit ; note O04 inverse + symétrique ; ids de validation complets (CURIE) dans le rapport ; `label_<lang>` sur les nœuds de référence (libellés FuelType conservés) ; RULES.md et skill complétés.
- Démos régénérées sur automaint : `demo-report-curiosity.md`, `demo-report-neo4j.md`.

## Reporté (vendredi)
- I01 redondant avec C08 : non traité, car l'oracle f-I01 (`am:Petrol`) l'attend encore.
- Reverse « XxxInverse » sans inverse OWL : une heuristique sur les libellés reste à faire.
