---
name: neo4j-schema-design
description: Modéliser un schéma Neo4j 5 (labels, types de relation, contraintes, index, ingestion MERGE, validations Cypher) à partir d'une ontologie OWL ou d'un besoin métier, et relire le schema.cypher / ingest.cypher / validation.cypher générés par OntoForge. À utiliser pour décider multi-labels vs discriminant, clé simple vs composite, Community vs Enterprise, relation porteuse de propriétés vs nœud, et comparer avec neosemantics (n10s).
---

# Concevoir un schéma Neo4j depuis une ontologie

Cible n°2 d'OntoForge. Implémentation : `backend/ontoforge/mapping/profiles/neo4j.py` (capacités, types XSD, nommage,
recommandations par règle), `backend/ontoforge/targets/neo4j.py` (génération), tests `test_profile_neo4j.py` et
`test_target_neo4j.py`. Tout point non confirmé porte `À VÉRIFIER` ; ne jamais l'affirmer à un client sans test sur son instance.

## Sources
- [S1] Contraintes (création, types, éditions) : https://neo4j.com/docs/cypher-manual/current/constraints/
  et `.../constraints/managing-constraints/`, `.../constraints/examples/`
- [S2] Index RANGE / TEXT / POINT / FULLTEXT : https://neo4j.com/docs/cypher-manual/current/indexes/
- [S3] Types de valeurs et propriétés stockables : https://neo4j.com/docs/cypher-manual/current/values-and-types/
- [S4] Cypher Style Guide (nommage) : https://neo4j.com/docs/cypher-manual/current/styleguide/
- [S5] `MERGE`, `UNWIND`, `CALL { } IN TRANSACTIONS` : https://neo4j.com/docs/cypher-manual/current/clauses/
- [S6] Sous-requêtes `COUNT { }`, `EXISTS { }` : https://neo4j.com/docs/cypher-manual/current/subqueries/
- [S7] neosemantics : https://neo4j.com/labs/neosemantics/ (procédures `n10s.*`)
- [S8] Modélisation de graphe : https://neo4j.com/docs/getting-started/data-modeling/

## 1. Capacités Neo4j 5 qui orientent le mapping
| Besoin OWL / SHACL | Neo4j | Édition | Remarque |
|---|---|---|---|
| Classe | label PascalCase | toutes | plusieurs labels par nœud : héritage natif (C02/C03) |
| Propriété d'objet | type de relation UPPER_SNAKE | toutes | pas de type inverse stocké : traverser `<-[:T]-` (O04) |
| Propriété de relation | propriétés sur la relation | toutes | dé-réification R01 ; une relation ne peut pas être cible d'une autre |
| Unicité (nœud) | `REQUIRE n.p IS UNIQUE` (composite possible) | Community + Enterprise | crée un index de support |
| Unicité (relation) | `FOR ()-[r:T]-() REQUIRE r.p IS UNIQUE` (5.7+) | À VÉRIFIER : Community | |
| Clé (existence + unicité) | `IS NODE KEY` (nœud ; relation 5.7+) | Enterprise | remplace l'UNIQUE de même schéma |
| Existence | `IS NOT NULL` | Enterprise | |
| Type de propriété | `IS :: STRING \| INTEGER \| FLOAT \| BOOLEAN \| DATE \| LOCAL DATETIME \| ZONED DATETIME \| LOCAL TIME \| ZONED TIME \| DURATION \| POINT \| LIST<T NOT NULL>` (5.9+, listes 5.10+) | Enterprise | pas de DECIMAL natif |
| Cardinalité de relation, disjonction de labels, énumération, regex, allValuesFrom | aucune contrainte | — | requête de détection (§5) |
| Recherche | index RANGE (défaut), TEXT, FULLTEXT, POINT | toutes | un TEXT/RANGE n'indexe pas les éléments d'une liste |

Versions minimales retenues par OntoForge : 5.7 (Community : UNIQUE, index), 5.11 (section Enterprise : types,
NODE KEY, existence, listes). Les noms de contraintes et d'index partagent un seul espace de noms : le générateur les
produit stables (`<label>_<propriété>_<unique|node_key|not_null|type|range|text>`), suffixés si collision, et préfixés
`rel_` pour les relations.

## 2. Règles de transposition (profil Neo4j)
Option normative = identifiant du vocabulaire de `samples/trap/expected-findings.yaml`. Le profil recommande ; l'humain
arbitre tout ce qui est `review` ou `lost`.
- Héritage (C02/C03/I05) : `multi_label`. Alternative `flatten_into_leaves` / `primary_parent_discriminator` seulement
  si l'aval (Curiosity) l'exige. La contrainte de clé se pose sur le label le plus général ayant cette clé.
- Classe abstraite (C04) : `secondary_label` (aucun nœud n'a que ce label, il porte les contraintes communes).
- Équivalence (C05) : `merge_types` (nom canonique, alias documenté).
- Classe définie, GCI, complément (C06/C11/C13) : `computed_label` = requête `SET n:Label` rejouée après ingestion (pas de raisonneur).
- Disjonction (C07) : `validation` = `MATCH (n:A) WHERE n:B`.
- Énumération de classe (C08) : `reference_nodes` ; énumération de datatype (D08) : `enum_property` + validation.
- Clés : K01 `unique_constraint` sur `uri` (compatible n10s) ; K02 `node_key` est un renforcement (l'OWL `hasKey` n'impose pas l'existence) : ne jamais le présenter comme équivalence ; K03/K04 `generated_key` ; K05 `materialize_key`.
- Datatypes (D05) : `native_type` selon `XSD_TYPE_MAP` ; decimal → FLOAT avec perte (option `string_lexical` si l'exactitude prime, ou entier mis à l'échelle documenté) ; hexBinary/base64Binary → STRING ; gYear → INTEGER ; dateTimeStamp → ZONED DATETIME ; xsd:dateTime sans fuseau → LOCAL DATETIME. Multivalué (D04) : liste homogène `LIST<T NOT NULL>`, jamais `null` ni types mixtes. Multilingue (D06) : `per_language_property` (`label_fr`).
- Relations : O04 `single_direction` (un seul sens stocké), O05 `undirected_query`, O06 `var_length_query` (`[:T*1..]`), avec `materialize_closure` seulement si la profondeur ou le volume l'exigent ; O07 `most_specific_type` (`-[:CHILD|PARENT]-`) ; O09/O10/O15/O16 `validation` (jamais de contrainte de cardinalité inventée) ; O13/O11 `validation` du label cible.
- Réification (R01/R02) : `dereify_relationship` si exactement 2 rôles fonctionnels, `keep_node` dès 3 rôles ou si la relation doit être référencée ailleurs.
- Individus : I01 `reference_nodes` ; I02 `merge_nodes` (sameAs) ; I03 `noop_una` (le graphe suppose l'UNA : renforcement à noter).

## 3. Nommage (Cypher Style Guide [S4])
Labels `PascalCase`, types de relation `UPPER_SNAKE_CASE`, propriétés `camelCase`, propriétés par langue `label_fr`.
Tout identifiant hors `[A-Za-z_][A-Za-z0-9_]*` va entre backticks (`` ` `` doublé pour un backtick littéral). Éviter les
collisions label/relation insensibles à la casse (`Warranty` vs `warranty`) (à vérifier en revue).

## 4. Ingestion idempotente
```cypher
UNWIND $rows AS row
MERGE (n:Vehicle {vin: row.vin})          // MERGE sur la SEULE clé
SET n:ElectricVehicle                     // labels additionnels
SET n.fuelType = row.fuelType,            // le reste en SET : rejouable
    n.firstRegistrationDate = date(row.firstRegistrationDate);
```
- Nœuds d'abord (une instruction par type), relations ensuite ; `MERGE` sur les deux extrémités par clé, puis sur la relation (`MERGE (a)-[r:INSTALLED_ON]->(b)`) et `SET r.prop = …`. Pour plusieurs relations parallèles distinguables, inclure leur clé dans le motif du MERGE.
- Convertir côté Cypher (`toInteger`, `toFloat`, `date()`, `datetime()`, `localdatetime()`, `duration()`) ; les chaînes ISO 8601 sont acceptées par ces fonctions.
- Lots de 1 000 à 10 000 lignes par transaction côté driver ; en Cypher pur : `CALL (row) { … } IN TRANSACTIONS OF 1000 ROWS` (variable-scope 5.23+, à VÉRIFIER ; avant : `CALL { WITH row … }`). `IN TRANSACTIONS` exige une transaction implicite (`:auto` dans cypher-shell/Browser).
- `SET n.p = null` supprime la propriété : un rechargement complet par type reste cohérent.
- Créer les contraintes avant les données (le MERGE s'appuie sur leur index et reste atomique sous concurrence).
- Super-nœuds : une clé de relation à très forte cardinalité (ex. « pays ») dégrade les traversées ; préférer propriété + index, ou typer les relations.

## 5. Validations Cypher (ce que le schéma ne garantit pas)
Une requête de détection par `PGModel.validations`, qui retourne `validation, severity, focus (elementId), uri, detail` ; 0 ligne = conforme.
| kind | Patron |
|---|---|
| cardinality / functional | `MATCH (n:A) WITH n, COUNT { (n)-[:R]->(:B) } AS c WHERE c < min OR c > max` |
| existence | `WHERE NOT EXISTS { (n)-[:R]->() }` ou `n.p IS NULL` (Community) |
| disjoint | `MATCH (n:A) WHERE n:B` |
| allValuesFrom | `MATCH (n:A)-[:R]->(m) WHERE NOT m:B` |
| enum | `WHERE NOT n.p IN [...]` (listes : `any(x IN n.p WHERE NOT x IN [...])`) |
| irreflexive / asymmetric | `(n)-[:R]->(n)` ; `(n)-[:R]->(m)-[:R]->(n) WHERE elementId(n) < elementId(m)` |
| pattern | `WHERE NOT n.p =~ '…'` — `=~` exige une correspondance complète : retirer `^…$` des regex XSD/SHACL ; regex Java |
| range | `WHERE n.p < min OR n.p > max` |
| closed | `WHERE size([k IN keys(n) WHERE NOT k IN [...]]) > 0` |
Contraintes SHACL non traduisibles automatiquement (SPARQL) : patron commenté, jamais une requête qui échoue ou qui ment.
Matérialisations (fermeture transitive, chaîne, super-propriété, classification) : `DELETE` des relations dérivées puis `MERGE`, à rejouer après chaque ingestion ; la relation dérivée porte un nom distinct (`PART_OF_TRANSITIVE`).

## 6. OntoForge vs neosemantics (n10s) [S7]
| | n10s (import RDF « brut ») | OntoForge |
|---|---|---|
| Entrée | triplets RDF (données) ; `onto.import` pour le vocabulaire | ontologie + shapes → schéma, puis données via ETL |
| Modèle | `(:Resource {uri})`, labels = `rdf:type` (`handleRDFTypes`), propriétés = prédicats littéraux, relations = prédicats objet ; préfixes raccourcis (`handleVocabUris: SHORTEN`) ; multivalué `handleMultival: OVERWRITE\|ARRAY` | modèle métier : labels PascalCase, relations UPPER_SNAKE, types Neo4j, clés métier |
| Contraintes | une seule : `Resource.uri IS UNIQUE` (`n10s.graphconfig` doit être initialisé) | UNIQUE / NODE KEY / types / index générés, Enterprise séparé |
| Ontologie | importée comme graphe `:Class`, `SCO`, `SPO`, `DOMAIN`, `RANGE` (à interroger, pas appliquée) | transposée en schéma ; ce qui se perd est listé et arbitré |
| Validation | SHACL via `n10s.validation.shacl.*` | requêtes Cypher (une par contrainte), SHACL conservé à part |
| Inférence | `n10s.inference.*` (subClassOf, etc.) à la demande | fermetures matérialisées ou requêtes `*1..` |
| Aller-retour RDF | oui (`n10s.rdf.export`) | uri conservé (K01) → export possible, non garanti |
Règle pratique : n10s pour charger vite des données RDF telles quelles ; OntoForge pour concevoir un modèle propre, typé, contraint, avec les pertes visibles. Les deux se combinent : garder `uri` (K01) et un `Resource` implicite évite de s'interdire n10s. Détails des noms de procédures et options : À VÉRIFIER sur la version installée.

## 7. Checklist de relecture
- [ ] Chaque contrainte/index est idempotent (`IF NOT EXISTS`), nommé, nom unique dans la base.
- [ ] Rien d'Enterprise dans la partie active ; section Enterprise commentée avec `DROP CONSTRAINT … IF EXISTS` de l'UNIQUE remplacée par un NODE KEY.
- [ ] `NODE KEY` / `IS NOT NULL` présentés comme renforcement (K02) rattaché à une décision d'arbitrage.
- [ ] Contrainte de clé sur le label le plus général ; pas de doublon sur les sous-labels.
- [ ] Aucune contrainte de cardinalité de relation, de disjonction, d'énumération ou de regex inventée.
- [ ] Types : pas de DECIMAL/gYear natifs → perte signalée (D05) ; listes homogènes sans null.
- [ ] Ingestion : MERGE sur la clé seule, nœuds avant relations, relations dérivées non ingérées.
- [ ] Une requête de validation par `validations`, une section par `materializations` ; cas non traduisible commenté.
- [ ] Identifiants à risque entre backticks ; regex sans ancres pour `=~`.
- [ ] Chaque constat `lost` apparaît (`// LOST <id>`) et au README ; constats non arbitrés listés.
- [ ] Tout ce qui n'est pas confirmé par une source est marqué `À VÉRIFIER`.

## 8. Pièges connus
- `SET n:Label` ne retire rien : pour une classification rejouable, `REMOVE` d'abord (le générateur le fait).
- Une contrainte UNIQUE ignore les `null` : sans `NOT NULL`/`NODE KEY`, plusieurs nœuds sans clé coexistent → validation d'existence en Community.
- `MERGE` sur plusieurs propriétés dont une `null` échoue : valider la clé avant chargement.
- Les durées XSD (`xsd:duration`) et ISO 8601 de Cypher diffèrent pour les mois/années : À VÉRIFIER sur les données réelles.
- Un index TEXT n'accélère pas `=~` arbitraire ; FULLTEXT s'interroge par `db.index.fulltext.queryNodes`, pas par `WHERE`.
