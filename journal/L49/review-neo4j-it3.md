verdict: OK
bloquants: []
vérifié (cible Neo4j, mêmes rejeux que la revue curiosity, exemple de test et trap enrichi, fr et en) :
  - Bloquant it2 corrigé : `Car ⊑ ∃locatedNear.Garage` avec `Garage` exclue → A03 liste `locatedNear`, O02 `lost` avec la raison, aucun `[:LOCATED_NEAR]`. `keptIn` sur trap : idem (restriction vers `ServiceBooklet`), listée dans A03 et dans la colonne « Entraîne la perte de » du rapport.
  - Union partielle `bookletOrPlan` : « En partie », O03 en `review` « Générée en partie », `[:BOOKLET_OR_PLAN]` vers `MaintenancePlan` générée, non listée comme perdue.
  - Inverse (`hostedIn` / `hosts`) : perte listée, O04 `lost`. Attribut à domaines tous exclus : D01 `lost`, aucune propriété. Deux domaines dont un exclu (`gname`) : générée sur `Vehicle`, perte partielle.
  - Gardée avec drapeau : rien de perdu, arêtes `LOCATED_NEAR`, `HOSTS` et propriété `openingHours` générées, colonne « — ». Fichiers générés (`schema.cypher`, `ingest.cypher`, `README-neo4j.md`, `model.mmd`, `validation.cypher`) sans `ServiceBooklet` en exclusion.
  - `apply_m01` identique à master (diff en contexte seulement).
  - Anglais : constats et rapport traduits (« Partly: », « Partly generated: … », « Not generated: … »).
  - Tests : 235 réussis (l49, mapping, targets), suite complète 1337 réussis.
non-bloquants:
  - Mêmes remarques de forme et de couverture que la revue curiosity (lignes vides avant `_endpoints` et `apply_m01` ; propriétés sautées par la construction : alias, `skip_edge`, dé-réification).
  - Toujours ouverts : `<<abstract deprecated>>` et `[ ]` dans une étiquette de relation de `model.mmd` (À VÉRIFIER au rendu Mermaid) ; propriété de relation dépréciée non marquée dans le README ; requête de détection des nœuds dépréciés restants dans `validation.cypher`.
skill: neo4j-schema-design : même règle de résolution des extrémités pour les pertes induites ; vérifier les cinq fichiers et les deux langues.
