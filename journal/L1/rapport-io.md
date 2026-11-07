# Rapport L1 — io RDF / DSL (w3c) — 3 nov. 2026

Reprise d'un travail interrompu : `rdf_import.py` (mapping inverse complet) et `rdf_export.py` existaient déjà et fonctionnaient ; ajoutés/corrigés :
- Round-trip rendu exact : forme lexicale xsd:decimal normalisée (0 ≡ 0.0), xsd:string ≡ littéral simple, préfixes standard non mémorisés, descriptions `unmapped` indépendantes des préfixes. Vérifié sur turtle, RDF/XML, JSON-LD, N-Triples, les 7 fixtures, trap.ttl et AutoMaint.
- `io/dsl.py` créé : `parse_dsl` (erreurs par ligne, rollback d'une ligne fautive, jamais d'exception), `DSL_HELP` en français avec exemple vérifié par test. Choix : plusieurs classes pour une même propriété = union (domain_union) ; cardinalités = restrictions sur la classe ; `key` = hasKey.
- `samples/automaint/automaint.ttl|.owl|quickstart.dsl` : 24 classes, 25 propriétés objet, 25 de données, datatype défini am:ModelYear, labels fr/en, aucune propriété hors carte DL. IRIs alignées sur automaint-shapes.ttl / automaint-data.ttl.
- Tests : `test_io_import_export.py`, `test_io_dsl.py` (92 tests backend verts). Section « Import/export RDF : pièges » ajoutée au skill.

Points pour les autres agents (non bloquants) :
- shacl : `automaint-shapes.ttl` utilise `xsd:date` pour `am:readingDate` ; l'ontologie le type `xsd:dateTime` (xsd:date est hors OWL 2 DL) → aligner la shape. `am:dtc_code` (snake_case) conservé car utilisé par shapes/data, à renommer `dtcCode` si les deux fichiers suivent.
- Conformité : automaint.ttl n'a pas été passé dans `check_conformance` (module absent à ce stade) ; contrôle DL fait à la main.
- Le sérialiseur RDF/XML de rdflib émet des UserWarning sur les listes (sans conséquence).
