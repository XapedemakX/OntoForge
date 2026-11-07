# Correctifs Curiosity — réponse à la revue neo4j it1 (KO, 4 bloquants)

Suite complète : 220 tests verts (`cd backend && python -m pytest -q`).

1. **Clé composite** : `_key_part_expr` échappe `%` -> `%25` puis `|` -> `%7C` (encodage injectif) et ne convertit plus null en `""`. Le connecteur contrôle chaque composant (string : `IsNullOrWhiteSpace` ; liste : vide) AVANT `WithComputedKey()` : Report « composant de clé vide ou nul » + `continue`. Tests : `test_composite_key_escapes_percent_and_rejects_empty_components`, `test_key_encoding_is_injective`.
2. **Arêtes** : `_pascal` du profil conserve les séparateurs des noms UPPER_SNAKE (`HAS_MODEL` -> `HasModel`, retour `ModelOf`). Symétrique : retour = aller (même constante, `Link(a,b,X,X)`). Noms normalisés dans le plan (`edge_fwd`, `edge_alias`, validations incluses) ; collision avec un type de nœud -> suffixe `Edge`, entre arêtes ou identifiants -> `EdgeN`, avertissement dans le README. Tests : `test_symmetric_edge_same_constant_both_sides`, `test_edge_consts_unique_and_no_collision_with_node_types`.
3. **Validations** : plus aucune validation en simple commentaire. Chaque id produit `Report` (V04 sur DateTime via `default`, V08 sur liste d'énumérés implémentés), `Guaranteed` (garantie par construction, info) ou `NotChecked` (avertissement une fois à l'exécution, compteur `_warnings`) : V12 (hasValue sur propriété absente, valeur implicite du sous-type), V14 (propriété d'arête perdue), V15 (closed, non détectable à la désérialisation, perte documentée), V16/V13 (other). README mis à jour. Tests : `test_every_validation_has_executable_code` (2 fixtures), `test_unimplementable_validations_warn_at_runtime`.
4. **Tests** ci-dessus. Non-bloquants traités : `Degree` indexé une fois (O(liens)), `Nodes`/`LinkSet` en tuples (plus de collision sur `|`), disjonction -> `Guaranteed`, checklist du skill complétée. Non traités : `gYear -> long` reste en remarque XML.

## it2 — revue W3C (2 bloquants) et non-bloquant neo4j
- **hexBinary / base64Binary** : `lossy=True` (D05), notes explicites (octets non typés, surcoût de taille). Test `test_binary_lossy_and_langstring_off_owl2_map`.
- **rdf:langString** : retiré de `OWL2_DATATYPES` (la carte OWL 2 contient rdf:PlainLiteral) ; mapping de tolérance conservé hors carte, note « NON CONFORME OWL 2 (W01) ».
- **V12 (neo4j)** : propriété absente du type -> `NotChecked` aussi dans `CheckGraph` (plus de `Guaranteed` trompeur). Test `test_absent_property_validation_is_notchecked_not_guaranteed`.
- Suite complète verte.
