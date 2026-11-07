# Revue W3C — L4 requêtes + profils de types (itération 2)

Relecteur : w3c — 3 nov. 2026. J'ai rejoué les cas de l'it1 sur les fixtures régénérées (script c9.py). Le contrôle des cartes de types a été refait par script. La suite complète passe (412 tests).

Ce qui est levé :
- **Classe absente** : elle donne `WHERE false` avec lossy=True, avec ou sans ontologie.
- **Deux sous-types sur un même discriminant** (ElectricVehicle et CombustionVehicle) : `AND false` et [perte]. Le cas « Vehicle puis ElectricVehicle » garde bien le type le plus précis.
- **owl:inverseOf** : am:concerns donne `<-[:HAS_REPAIR_ORDER]-` et am:readingOf donne `<-[:HAS_MILEAGE_READING]-`, sans perte. Sans ontologie, les deux sont notés [perte], ce qui est attendu. am:ownedBy et am:ofModel sont maintenant des edges stockés.
- **Profils** : curiosity hexBinary et base64Binary sont lossy=True. rdf:langString est retiré de OWL2_DATATYPES (Curiosity) et a owl2=False (Neo4j). La différence avec OWL2_DATATYPE_MAP est vide.

```
verdict: KO
bloquants:
  - [queries/translate.py:360-362] Le même défaut que le bloquant 1 de l'it1 existe pour les propriétés. Une propriété absente du PG dans un motif obligatoire est « ignorée ». `?v am:ownedBy ?c . ?v am:nope ?x` donne `MATCH (v)-[:OWNED_BY]->(c) RETURN …` : c'est un sur-ensemble, car SPARQL rend 0 ligne. `{ ?o am:concerns ?v }` sans ontologie donne `RETURN null AS o, null AS v` : 1 ligne de nulls au lieu de 0. → Dans un bloc obligatoire, ajouter `false` aux conditions du bloc, comme fait déjà NodeVar.empty pour les classes. Dans un OPTIONAL, garder le comportement actuel (variable non liée → null), qui est correct. Ajouter un test pour chacun des deux cas.
non-bloquants:
  - Toujours ouverts depuis l'it1 : la note sur le zéro saut de `*`, et Long au lieu de Int en GraphQL (targets/graphql.py:24).
skill: graph-query-translation — généraliser la règle : « une classe ou une propriété inconnue dans un motif obligatoire → motif vide (false), jamais un triplet ignoré ».
```

Verdicts par producteur : query = KO (1 bloquant) ; curiosity = OK ; neo4j = OK.
