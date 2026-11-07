---
name: graph-query-translation
description: Traduire des requêtes SPARQL vers Cypher, GraphQL et la Query API Curiosity à partir d'un PGModel OntoForge ; savoir ce qui est intraduisible, comment le compenser, et écrire des requêtes de validation / questions de compétence. À utiliser pour valider qu'un modèle property graph répond encore aux questions de l'ontologie.
---
# Traduction de requêtes SPARQL ↔ Cypher ↔ GraphQL ↔ Curiosity

Code : `backend/ontoforge/queries/translate.py` (`translate(sparql, pg, onto=None) -> TranslationResult`), `competency.py`, `targets/graphql.py`. Principe : les IRI SPARQL sont résolus via les champs `source` du PGModel (NodeType, PGProperty, EdgeType) ; l'ontologie (`onto`) ajoute inverseOf, sous-classes, transitivité. Jamais d'exception : ce qui est perdu devient une note `[perte]` et `lossy=True`.

## Correspondances
| SPARQL | Cypher | GraphQL (schéma généré) | Curiosity (C#, À VÉRIFIER) |
|---|---|---|---|
| `?x a :C` | `(x:C)` ; si C fusionné par discriminant : `(x:Parent) WHERE x.kind='C'` | `type C` / interface + `__resolveType` | `StartAt(N.C.Type)` |
| `?x :dp ?v` | `x.dp` | champ scalaire | `GetString/GetInt(N.C.Dp)` |
| `?x :op ?y` | `(x)-[:OP]->(y)` | champ relation (les deux sens via `reverse`) | `.Out(N.T.Type, E.Op)` (le sens retour = edge `reverse`) |
| `^:op` | `(x)<-[:OP]-(y)` | champ du `reverse` | edge `reverse` |
| `:op+` / `:op*` | `-[:OP*1..]->` / `*0..` (+ `DISTINCT`) | non (matérialiser) | `OutMany(n, …)` profondeur bornée |
| `:a/:b`, `:a\|:b` | chaîne de relations ; `[:A\|B]` | champs imbriqués | traversées successives |
| `OPTIONAL` | `OPTIONAL MATCH` | champ imbriqué nullable | boucle sur les voisins en C# |
| `FILTER(regex)` | `=~` (motif encadré `.*`) | — | `Regex.IsMatch` |
| `COUNT/GROUP BY` | `count()` avec regroupement implicite | — | regroupement en C# |
| `ORDER BY/LIMIT/OFFSET` | idem | `first`/`offset` | LINQ `OrderBy/Take/Skip` |
| `ASK` | `RETURN count(*)>0` | — | `.Any()` |

## Intraduisible et compensations
- **Raisonnement (RDFS/OWL)** : `rdfs:subClassOf*`, `subPropertyOf`, `inverseOf`, transitivité ne sont pas inférés en PG. Compenser : labels multiples ou discriminant (Neo4j / Curiosity), edges `derived` matérialisés, `reverse` pour l'inverse, `*1..` pour la fermeture.
- **Prédicat variable `?p`**, métamodèle (`?s a ?c`) : relations et propriétés sont du schéma ; énumérer les types connus ou passer par `CALL db.labels()`.
- **Graphes nommés (`GRAPH`)** : propriété `graph`/`source` sur les nœuds ; sinon perte signalée.
- **Hypothèse du monde ouvert**, `NOT EXISTS` : lu en monde clos en PG.
- **Propriété ontologique non transposée** (ex. inverse non retenue) : note `[perte]`, triplet ignoré -> décision humaine à arbitrer.
- **Curiosity** : pas de tuples ni de jointure externe ; la Query API renvoie les nœuds de fin de traversée.
- **Écarts sans perte** : `DISTINCT` ajouté sur chemins variables ; sémantique `=~` complète.

## Patrons de requêtes de validation
1. Comptage par type : `MATCH (n:T) RETURN count(n)` vs `SELECT (COUNT(?x)...) { ?x a :T }` : doivent être égaux après chargement.
2. Une question de compétence par patron : liste, relation, comptage, OPTIONAL, transitive, filtre, sous-classe aplatie, chemin à 2 sauts (`competency_questions`).
3. Orphelins : `MATCH (n:T) WHERE NOT (n)-[:R]->() RETURN n` pour une cardinalité min 1.
4. Violation de fonctionnalité : `MATCH (n)-[r:R]->() WITH n,count(r) c WHERE c>1`.
5. Si une question de compétence sort `lossy`, la perte correspondante doit figurer dans le rapport d'arbitrage.

## Points À VÉRIFIER
API Curiosity (`Q().StartAt`, `OutMany`, accesseurs `Get*`, `Emit`) : documentation https://docs.curiosity.ai/workspace-build/apis-and-customization/custom-endpoints/graph-query-language ; schéma GraphQL pour Curiosity = API custom (pas de génération native) ; Neo4j GraphQL Library (`@relationship`) à brancher côté README.

## Règles de sûreté (revue W3C it1)
- Une classe ou propriété inconnue ne doit jamais élargir le résultat : motif qui ne renvoie rien (`WHERE false`) + note `[perte]`, jamais un `MATCH (x)` non typé.
- Plusieurs types sur un discriminant mono-valué (ElectricVehicle ET CombustionVehicle) = perte (OWL ne les rend pas disjoints) ; « parent puis sous-type » garde le type le plus précis.
- `owl:inverseOf` n'est exploité que si l'ontologie est fournie à `translate` (traversée inverse sans perte) ; sinon `[perte]`.

## Requêtage guidé (L15)
- Une requête guidée = racine + étapes (propriété objet, sens, classe cible, optionnel / nié) + filtres + sélection : `queries/builder.py` produit le SPARQL, puis `translate.translate` donne Cypher / Curiosity / GraphQL (ne jamais dupliquer la traduction).
- Suggestions : domaine / portée effectifs = déclarés, sinon hérités des super-propriétés puis de l'inverse ; une classe hérite des propriétés de ses ancêtres ; les cibles incluent les sous-classes ; une shape `sh:class` / `sh:minCount` restreint / marque obligatoire. Propriété sans domaine déclaré : proposée en sortant seulement (`untyped`).
- Mapping des constructions : étape niée -> `FILTER NOT EXISTS` (-> `WHERE NOT (a)-[:R]->(b)`), optionnelle -> `OPTIONAL` (-> `OPTIONAL MATCH`), sens inverse -> triplet renversé (flèche inversée), `subclasses` -> `rdf:type/rdfs:subClassOf*` (-> labels multiples ou discriminant).
- Exécution : lecture seule vérifiée par le parseur (UPDATE refusé avant tout appel réseau), LIMIT forcé à `limit`+1 pour détecter la troncature, valeurs d'autocomplétion = `CONTAINS(LCASE(STR(?v)), q)` sur la propriété ou les libellés (`rdfs:label`, `skos:prefLabel`, propriétés « nom »).
- Les questions de compétence se convertissent en requêtes guidées quand le motif est un BGP / OPTIONAL / chemin en séquence ; agrégats, chemins `+` / `*`, filtres sont expliqués (`reason`) et restent en SPARQL libre.
