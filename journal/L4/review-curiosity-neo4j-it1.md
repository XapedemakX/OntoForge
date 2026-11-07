# Revue croisée L4 it1 — relecteur curiosity, cible relue : neo4j

verdict: KO

Périmètre : mapping/profiles/neo4j.py, targets/neo4j.py, tests test_profile_neo4j / test_target_neo4j, comparés aux fichiers Curiosity.
Vérifications : 82 tests verts (profils + cibles des deux plateformes) ; generate() exécuté sur
backend/tests/fixtures/pg_curiosity_automaint.json (5 fichiers produits, sorties dans le scratchpad) ;
comparaison règle par règle des 66 règles de RECOMMENDATIONS (mêmes identifiants des deux côtés) et contre samples/trap/expected-findings.yaml.

bloquants:
  - [backend/ontoforge/targets/neo4j.py:162-167 et :316-322] Type de nœud sans clé (VehicleModel : key=[], mais propriété `Uri` required+unique) →
    `node_pattern` émet `MATCH (b:VehicleModel {})`, qui apparie TOUS les nœuds du label : AffectsModel, MadeBy et OfModel créent
    un produit cartésien de liens, sans aucun avertissement dans la relation (seul le nœud porte « ATTENTION »). Le nœud est en plus
    ingéré par `CREATE` alors que schema.cypher pose `vehicle_model_uri_unique` : une ré-ingestion échoue au lieu d'être idempotente.
    → (1) ne jamais émettre un motif de propriétés vide : sans clé, soit utiliser la propriété unique+required comme clé de repli
    (insensible à la casse : `Uri` ici, `uri` dans le PG Neo4j), soit commenter l'instruction de relation avec un « À COMPLÉTER » explicite ;
    (2) aligner ingest et schema (MERGE sur la clé de repli dès qu'une contrainte UNIQUE existe) ; (3) test sur un type sans clé.
  - [backend/ontoforge/targets/neo4j.py:144 et :162, :367, :459] Le nom de la propriété IRI est codé en dur en minuscules (`uri`) :
    avec un PG dont la propriété est `Uri` (fixture Curiosity), `key()` ne la reconnaît pas (cause du bloquant ci-dessus) et toutes les
    validations retournent `n.uri AS uri` = toujours null (propriété inexistante). → résoudre le nom réel de la propriété IRI
    (première propriété dont name.lower()=="uri") et l'utiliser partout ; sinon renvoyer `null AS uri` explicitement quand le type n'en a pas.

non-bloquants:
  - [targets/neo4j.py:_materialization, kind transitiveClosure] `chain` contient ici l'IRI `https://example.org/auto#isPartOf` (convention du PG Curiosity)
    et non un nom d'arête (convention de la fixture Neo4j) : le motif `-[:`https://…#isPartOf`*1..]->` ne correspond à rien et PartOfAncestor
    n'est jamais peuplé, sans signal. Résoudre `chain` via EdgeType.source → nom d'arête (et inverser le sens si l'arête n'existe que par son
    `reverse`, ici PartOf = retour de HasPart), ou, à défaut, commenter. À arbitrer avec le lead : une seule convention pour MaterialiZation.chain (IRI ou nom) dans docs/CONTRACTS.md.
  - [validation.cypher V06/V09/V13] « patron à compléter » : acceptable pour V09/V13, mais V06 (disjointWith entre Recall et Warranty) pourrait être
    généré (deux types de nœuds distincts, sans multi-label dans ce PG : rien à vérifier ; avec multi-label : `WHERE n:Recall AND n:Warranty`). Même remarque côté Curiosity (V06 documenté seulement).
  - [schema.cypher section 6] sujets des pertes illisibles (`LOST C07:auto:Recall`, `O06:auto:isPartOf`) : afficher le nom court ou l'IRI complète.
  - [schema.cypher section 2] `vehicle_registration_number_range` : nom d'index suffixé `_range` alors que le modèle ne dit pas pourquoi cet index existe (source de l'« indexed »)
    ; ajouter un commentaire d'origine comme pour les clés.
  - Cohérence sémantique profils : identique sur 44 des 66 règles (D01-D13, C07, C08, C12, O07, O09-O16, O18-O21, I01-I04, K03/K04, M0x, A0x, R02, N01, G01, X00).
    Les 22 écarts sont tous justifiés par la plateforme et conformes à l'oracle : C01-C04/C10/I05 (multi-label natif vs mono-type), C06/C11/C13 (label calculé vs
    matérialisation à l'ingestion), K01/K02/K05 (contrainte UNIQUE/NODE KEY vs [Key] string), O01-O05 (relation unique orientée vs paire d'arêtes), O06/O08 (requête
    de longueur variable vs fermeture matérialisée), O17 (validation vs booléen matérialisé), R01 (garder le nœud, avec `ctx links>=3` côté Neo4j). Aucun écart non justifié.
  - Oracle vs code, identiques des deux côtés donc pas une incohérence inter-cibles : f-O13a (reflexive : oracle `ignore`, les deux profils renvoient `validation`),
    f-D05b (hexBinary : oracle `string_lexical`, les deux renvoient `native_type`), f-C09b (Neo4j : oracle `doc_only`, code `secondary_label` valable seulement pour C09a).
    Les décisions dépendent du sujet, donc d'un `ctx` : à tracer dans journal/decisions.md ou à porter par recommend(rule, ctx) des deux profils.
  - CAPABILITIES : les clés communes sont présentes des deux côtés ; Neo4j n'a pas les clés propres à Curiosity (reserved_*_fields, nullable_scalars…) : OK, le moteur les ignore.
  - Cypher 5 : syntaxe des contraintes (UNIQUE composite, NODE KEY, IS NOT NULL, IS :: LIST<STRING NOT NULL>, FULLTEXT multi-labels), `COUNT { }`, `elementId`,
    `CALL (row) {}` 5.23+ : conformes à la doc citée ; aucune erreur repérée. Ordre schema → ingest correct, propriétés absentes supprimées (SET = null) documenté.

skill: neo4j-schema-design (et curiosity-schema-design, section « différences avec Neo4j ») : documenter (1) la clé de repli pour les types sans owl:hasKey (propriété IRI
unique) et le refus d'émettre un motif de relation vide ; (2) la convention unique de `Materialization.chain` ; (3) le tableau des 22 écarts de recommandation justifiés par la plateforme.
