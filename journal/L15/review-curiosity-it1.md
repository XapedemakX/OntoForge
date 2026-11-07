# L15 — revue Curiosity du requêtage (itération 2) + correctif

Agent : curiosity. Verdict : **APPROUVÉ SOUS RÉSERVE** (1 bloquant corrigé, 0 bloquant ouvert, 4 non-bloquants). Tests : 527 verts.

## Diagnostic du bug de l'écran 04
Technician n'était pas replié : type à part avec `['Uri']` seul (idem Garage, Customer, Brand). Cause : `node_targets` (mapping/rules/classes.py) ne traversait pas les classes repliées (Person -> Party) et ne distribuait donc pas aux feuilles propres en dessous les propriétés héritées. La note de perte du traducteur était exacte pour ce PG ; le schéma C# perdait `DisplayName` en silence.

## Correctifs (décision lead D-L15-01 : pas de repli de Technician/Garage/Customer/Brand dans Party)
1. `node_targets` : les sous-classes concrètes (types propres) sous une classe repliée reçoivent les propriétés/relations héritées (recopie dans les feuilles). Technician, Garage, Customer, Brand restent des types distincts avec `DisplayName`. `hierarchy_root` inchangé. Party reste un type concret (restriction sur displayName : non abstrait) avec `PartyKind` pour Person/Organization.
2. `translate.py` : filtre discriminant pour un vrai repli (Cypher `WHERE v.VehicleKind = 'ElectricVehicle'`, Curiosity `.WhereString(N.Vehicle.Type, N.Vehicle.VehicleKind, ...)`) ; `type_family` pour les labels secondaires Neo4j ; marqueur `À VÉRIFIER : WhereString`.
3. Tests : `test_curiosity_abstract_ancestor_props_copied_into_leaves`, `test_curiosity_folded_subclass_uses_root_and_discriminant`, `test_neo4j_inherited_property_through_secondary_labels`. Suite 528 verts, oracle 100 %.

## Revue de la génération Curiosity (guidé + NL)
`builder.build_all` et `nl.py` réutilisent `translate` : pas de code Curiosity dupliqué, cohérent. Le C# produit relève de la Query API, **absente de l'« API C# vérifiée »** du skill (seuls schéma/connecteur le sont) : tout reste `À VÉRIFIER`, ce qui est justifié et signalé en en-tête.

### Bloquants
- Aucun ouvert (le bug de perte d'héritage est corrigé ci-dessus). Condition de levée : Jerem relance l'analyse du projet (les PG déjà générés gardent l'ancien modèle) et confirme sur son instance les signatures Query API.

### Non-bloquants
1. L'en-tête du code cite `.../apis-and-customization/custom-endpoints/graph-query-language` alors que le skill référence S6 `.../workspace-api/graph-query-language` : aligner l'URL après vérification.
2. `OPTIONAL` et colonnes multiples : la Query API ne renvoie que les nœuds de fin de traversée ; les colonnes sont à lire en C# (notes présentes). Les « colonnes » de l'écran guidé ne sont donc pas toutes reproduites côté Curiosity : à dire à l'utilisateur dans l'UI.
3. Nom du retour de `WorksAt` après repli : `HasParty` (hérité de la dérivation N01 de `Party→Party`), peu parlant ; préférer `EmploysParty`/`HasEmployee` via un nom retour explicite (règle O0x, à revoir côté mapping).
4. Sans Query API vérifiée, `n.UID`, `Emit`, `AsEnumerable` restent hypothétiques ; pas de test d'exécution possible sans instance.
5. `Party` reste un type concret (non abstrait) : une consigne « aucun type Party » ne tient pas sur automaint sans décision explicite.
