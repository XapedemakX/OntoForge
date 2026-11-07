# Correction shacl — itération 1 (revue W3C)
1. xsd:pattern : `owl_to_shacl.apply_data_range` émet `^(?:p)$` + note [PARTIEL] (échappements XSD non traduits) ; note [PARTIEL] ajoutée pour length sur hexBinary/base64Binary.
2. sh:datatype : nouveau `set_datatype` — pour un type XSD ayant des sous-types (decimal, integer, long, int, short, nonNegativeInteger, string, dateTime…) génère `sh:or` des datatypes compatibles + note [RENFORCÉ]. Choix `sh:or` plutôt qu'une simple note : la shape reste exacte vis-à-vis de l'espace de valeurs OWL ; repli sur datatype exact + note si `sh:or` est déjà occupé. Appliqué aux portées, DataRange et `only`.
Tests : `test_pattern_anchored_and_datatype_subtypes` (ABCDE rejeté, xsd:int/integer acceptés pour decimal). Suite : 395 verts, 2 échecs dans test_mapping_oracle.py (C09b neo4j, couverture) — hors de mon périmètre (mapping).
Skill shacl-modeling mis à jour (pièges XSD).
