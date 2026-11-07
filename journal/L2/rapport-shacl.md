# Rapport L2 — shacl
- Modules déjà écrits par l'agent précédent : vérifiés (import/export round-trip sur trap, automaint, core-full ; validate ; owl_to_shacl ; shacl_to_pg).
- Changé : `validate()` défaut `inference="none"` (CONTRACTS.md à aligner : voir demandes-contrat.md).
- trap-data.ttl avec inference="none" : exactement les 8 violations de l'oracle (rdfs : mêmes 8 sur trap-data seul).
- Ajouté : tests `test_shacl_{io,validate,owl_to_shacl,to_pg}.py` (suite complète : 41 verts), samples/automaint/automaint-{shapes,data}.ttl (4 violations commentées), skill shacl-modeling.
- Alignement automaint : samples/automaint/automaint.ttl absent à ce jour ; shapes écrites sur les classes/propriétés de trap.ttl (am:). À revérifier quand l'ontologie existera.
- Limites : owl_to_shacl testé sur un OntoModel construit à la main (pas d'import RDF→OntoModel disponible dans mon périmètre) ; contraintes Neo4j du skill à vérifier selon version.
- events.jsonl utilisé (ArtifactData non chargé).
