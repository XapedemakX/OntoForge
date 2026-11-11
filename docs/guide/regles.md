# Les 66 règles de transposition, expliquées {#les-66-regles-de-transposition-expliquees}

Ce guide est le rendu pédagogique du catalogue normatif `backend/ontoforge/mapping/rules/catalog.py` (rendu de référence : [`docs/RULES.md`](../RULES.md)). Pour chaque règle : un exemple OWL en Turtle, la transposition recommandée vers **Curiosity** et vers **Neo4j**, ce qui se perd, et la compensation prévue.

## Lire une fiche {#lire-une-fiche}

- **Sévérité** : `auto` (trivial, appliqué sans question), `review` (perte possible, vous arbitrez), `lost` (aucun équivalent natif, perte certaine tant que vous ne choisissez pas une compensation).
- **Recommandation** : l'option appliquée tant que vous n'avez pas arbitré (`Finding.recommended`). Les identifiants d'options (`validation`, `multi_label`…) sont ceux du vocabulaire normatif de `samples/trap/expected-findings.yaml`.
- **Identifiant de constat** : `<règle>:<IRI du sujet>`, avec un suffixe pour les restrictions (`:<IRI propriété>`) ou un construct anonyme (`:<sha1[:8]>`). Décision groupée : `"<règle>:*": option`.
- **Exemple trap** : sujet de la règle dans `samples/trap/trap.ttl` (préfixe `am:` = `https://w3id.org/ontoforge/automaint#`), l'ontologie « piège » qui exerce les 66 règles.
- **Monde ouvert / monde clos** : OWL *infère* (OWA, pas d'UNA), le property graph *contraint* (monde clos, UNA). Transposer un axiome en contrainte est un **renforcement**, rappelé dans le rapport.

Tous les exemples ci-dessous partagent l'en-tête suivant (omis ensuite) et ont été **vérifiés par exécution** : chaque extrait, passé dans `parse_ontology` puis `analyze` (cibles Curiosity et Neo4j), produit bien un constat de la règle annoncée. Les déclarations de classes/propriétés nécessaires à la détection y figurent. S01 et S02 ont été vérifiés avec leurs shapes (`parse_shapes`) ; G02 est un échange JSON de l'API.

```turtle
@prefix ex: <http://example.org/doc#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
```

Les règles S01, S02 (conflits OWL/SHACL) et G02 (décision invalide) sont de l'outillage du moteur, hors des 66.

## Index {#index}

| ID | Règle | Sév. | Curiosity | Neo4j | Compensation |
|---|---|---|---|---|---|
| **C01** | Classe → type de nœud | auto | `node_type` | `label` | aucune |
| **C02** | Héritage simple | review | `flatten_into_leaves` | `multi_label` | aucune |
| **C03** | Héritage multiple | review | `primary_parent_discriminator` | `multi_label` | Arbitrage humain |
| **C04** | Classe probablement abstraite | review | `merge_into_leaves` | `secondary_label` | Requête de détection / de classification |
| **C05** | Classes nommées équivalentes | review | `merge_types` | `merge_types` | Documentation |
| **C06** | Classe définie (classification) | lost | `materialize_at_ingest` | `computed_label` | Matérialisation |
| **C07** | Disjonction de classes | lost | `validation` | `validation` | Validation |
| **C08** | Classe énumérée | review | `reference_nodes` | `reference_nodes` | Validation |
| **C09** | Expression booléenne anonyme | lost | `doc_only` | `secondary_label` | Documentation |
| **C10** | Union disjointe (partition) | review | `primary_parent_discriminator` | `multi_label` | Validation |
| **C11** | Complément de classe | lost | `materialize_at_ingest` | `computed_label` | Matérialisation |
| **C12** | Punning classe / individu | review | `reference_nodes` | `reference_nodes` | Documentation |
| **C13** | Axiome général d'inclusion | lost | `materialize_at_ingest` | `computed_label` | Matérialisation |
| **K01** | Identité IRI | auto | `uri_key` | `unique_constraint` | aucune |
| **K02** | Clé OWL (hasKey) | review | `uri_key` | `node_key` | Validation |
| **K03** | Pas de clé métier | review | `uri_key` | `uri_key` | Arbitrage humain |
| **K04** | Individu anonyme | review | `generated_key` | `generated_key` | Matérialisation |
| **K05** | Clé composite avec propriété objet | review | `key_concat` | `materialize_key` | Matérialisation |
| **D01** | Propriété de données | auto | `property` | `property` | aucune |
| **D02** | Propriété sans domaine | review | `attach_to_users` | `attach_to_users` | Arbitrage humain |
| **D03** | Domaine en union | review | `duplicate_per_type` | `duplicate_per_type` | aucune |
| **D04** | Propriété non fonctionnelle | review | `scalar` | `scalar` | aucune |
| **D05** | Type de données avec perte | review | `native_type` | `native_type` | Validation |
| **D06** | Valeurs multilingues | review | `per_language_property` | `per_language_property` | aucune |
| **D07** | Propriété fonctionnelle | auto | `scalar` | `scalar` | aucune |
| **D08** | Énumération de littéraux | review | `enum_property` | `enum_property` | Validation |
| **D09** | Datatype à facettes | review | `validation` | `validation` | Validation |
| **D10** | Littéral non typé | review | `string_property` | `string_property` | aucune |
| **D11** | Sous-propriété de données | lost | `most_specific_type` | `most_specific_type` | Matérialisation |
| **D12** | Intersection de domaines / portées | review | `native_type` | `native_type` | Validation |
| **D13** | Restriction sur propriété de données | review | `validation` | `validation` | Validation |
| **O01** | Propriété objet → relation | auto | `edge_pair` | `relationship` | aucune |
| **O02** | Domaine / portée manquants | review | `edge_pair` | `relationship` | Arbitrage humain |
| **O03** | Domaine / portée en union | review | `edge_pair` | `relationship` | Validation |
| **O04** | Propriétés inverses | auto | `edge_pair` | `single_direction` | aucune |
| **O05** | Propriété symétrique | review | `self_reverse` | `undirected_query` | aucune |
| **O06** | Propriété transitive | lost | `materialize_closure` | `var_length_query` | Matérialisation |
| **O07** | Sous-propriété objet | lost | `most_specific_type` | `most_specific_type` | Matérialisation |
| **O08** | Chaîne de propriétés | lost | `materialize_closure` | `path_query` | Matérialisation |
| **O09** | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) | review | `validation` | `validation` | Validation |
| **O10** | Existence d'une relation | review | `validation` | `validation` | Validation |
| **O11** | Restriction universelle | lost | `validation` | `validation` | Validation |
| **O12** | Valeur imposée | review | `validation` | `validation` | Validation |
| **O13** | Caractéristiques de propriété | lost | `validation` | `validation` | Validation |
| **O14** | Propriété inverse anonyme | review | `reverse_traversal` | `reverse_traversal` | Validation |
| **O15** | Propriété inverse-fonctionnelle | review | `validation` | `validation` | Validation |
| **O16** | Cardinalité qualifiée | review | `validation` | `validation` | Validation |
| **O17** | Restriction hasSelf | lost | `materialize_at_ingest` | `validation` | Matérialisation |
| **O18** | Super-propriété universelle | auto | `ignore` | `ignore` | Documentation |
| **O19** | Propriétés équivalentes | review | `merge_relationship_types` | `merge_relationship_types` | Documentation |
| **O20** | Propriétés disjointes | lost | `validation` | `validation` | Validation |
| **O21** | Intersection de domaines / portées | review | `intersection_domain` | `intersection_domain` | Arbitrage humain |
| **R01** | Réification binaire | review | `keep_node` | `dereify_relationship` | aucune |
| **R02** | Relation n-aire | review | `keep_node` | `keep_node` | aucune |
| **A01** | Annotations | auto | `schema_metadata` | `schema_metadata` | Documentation |
| **A02** | Annotation d'axiome | review | `report` | `report` | Documentation |
| **A03** | Entité dépréciée | auto | `exclude` | `exclude` | aucune |
| **M01** | Métadonnées d'ontologie | auto | `schema_metadata` | `schema_metadata` | Documentation |
| **M02** | Import d'ontologie | review | `external_reference` | `external_reference` | Arbitrage humain |
| **G01** | Construct non transposé | lost | `report` | `report` | Documentation |
| **I01** | Individu | review | `reference_nodes` | `reference_nodes` | Arbitrage humain |
| **I02** | Identité (sameAs) | lost | `merge_nodes` | `merge_nodes` | Matérialisation |
| **I03** | Différence d'individus | auto | `noop_una` | `noop_una` | aucune |
| **I04** | Assertion négative | lost | `validation` | `validation` | Validation |
| **I05** | Individu multi-typé | review | `primary_parent_discriminator` | `multi_label` | Arbitrage humain |
| **N01** | Nommage | auto | `rename` | `rename` | Renommage |
| **S01** | Conflit OWL / SHACL | review | `shacl_wins` | `shacl_wins` | Arbitrage humain |
| **S02** | Propriété issue des shapes | review | `property` | `property` | aucune |
| **G02** | Décision ignorée | review | `report` | `report` | Arbitrage humain |


## Classes (C) {#classes-c}

### C01 — Classe → type de nœud *(Must it. 1)* {#c01-classe-type-de-noeud-must-it-1}

- **Construct** : owl:Class nommée
- **Détection** : Toute classe nommée déclarée.
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:MotorVehicle`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class .
```

**Curiosity** — Recommandation `node_type` — Type de nœud : Un type de nœud [Node] (classe C#).
  Raison : Correspondance directe.

**Neo4j** — Recommandation `label` — Label : Un label PascalCase.
  Raison : Correspondance directe.

**Ce qui se perd** : Rien : correspondance directe.

**Compensation** : aucune

### C02 — Héritage simple *(Must it. 1)* {#c02-heritage-simple-must-it-1}

- **Construct** : rdfs:subClassOf (parent nommé unique)
- **Détection** : Classe ayant exactement un parent nommé effectif.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:Vehicle`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class .
ex:Car   a owl:Class ; rdfs:subClassOf ex:Vehicle .
ex:Truck a owl:Class ; rdfs:subClassOf ex:Vehicle .
ex:veh_001 a ex:Vehicle .   # instance directe : la classe n'est pas abstraite
```

**Curiosity** — Recommandation `flatten_into_leaves` — Aplatir sur la racine concrète : Les sous-classes de la hiérarchie sont repliées dans le type de nœud de la racine concrète (propriétés recopiées) avec un discriminant `<racine>Kind` ; leurs restrictions deviennent des validations filtrées par discriminant ; requêtes par sous-type = filtre.
  Raison : Curiosity est mono-type (un nœud = une classe C#) : la hiérarchie s'aplatit, le discriminant reste filtrable et utilisable en facette.
  Autres options : `multi_label` (Multi-labels), `node_type` (Type de nœud distinct).

**Neo4j** — Recommandation `multi_label` — Multi-labels : Neo4j : le nœud porte son label et ceux de ses ancêtres (requêtes sur le parent naturelles). Curiosity : pas de multi-type, repli en liste de types `types` (propriété multivaluée) dans le type concret.
  Raison : Neo4j porte plusieurs labels par nœud : l'héritage passe sans perte de requêtabilité.
  Autres options : `flatten_into_leaves` (Aplatir sur la racine concrète), `node_type` (Type de nœud distinct).

**Ce qui se perd** : Le lien `subClassOf` n'est plus inférable : sous Curiosity (mono-type) la sous-classe n'existe plus que comme valeur de discriminant ; la requête « tous les Vehicle » doit filtrer.

**Compensation** : aucune

### C03 — Héritage multiple *(Must it. 1)* {#c03-heritage-multiple-must-it-1}

- **Construct** : Héritage multiple
- **Détection** : Classe ayant au moins deux parents nommés effectifs.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:HybridVehicle`

**Exemple OWL**

```turtle
ex:Petrol   a owl:Class .
ex:Electric a owl:Class .
ex:Hybrid   a owl:Class ; rdfs:subClassOf ex:Petrol, ex:Electric .
```

**Curiosity** — Recommandation `primary_parent_discriminator` — Parent principal + discriminant : Un parent principal porte le type ; les autres appartenances deviennent des booléens `is<Parent>`.
  Raison : Mono-type : un seul ancêtre peut définir le type de nœud (le plus riche en propriétés).
  Autres options : `multi_label` (Multi-labels), `node_type` (Type de nœud distinct).

**Neo4j** — Recommandation `multi_label` — Multi-labels : Tous les parents deviennent des labels (Neo4j) ; Curiosity : liste de types.
  Raison : Aucune limite au nombre de labels.
  Autres options : `primary_parent_discriminator` (Parent principal + discriminant), `node_type` (Type de nœud distinct).

**Ce qui se perd** : Curiosity : l'appartenance aux parents secondaires devient un booléen `is<Parent>` (ou une liste) ; l'inférence d'appartenance disparaît.

**Compensation** : Arbitrage humain (aucune compensation automatique)

### C04 — Classe probablement abstraite *(Must it. 1)* {#c04-classe-probablement-abstraite-must-it-1}

- **Construct** : Classe probablement abstraite
- **Détection** : Heuristique OWA : classe avec sous-classes, sans instance directe, sans clé, impliquée dans au plus une propriété objet, hors disjointUnion (C10).
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:MotorVehicle`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class .
ex:Car   a owl:Class ; rdfs:subClassOf ex:Vehicle .
ex:Truck a owl:Class ; rdfs:subClassOf ex:Vehicle .
# aucune instance directe de ex:Vehicle, aucune clé
```

**Curiosity** — Recommandation `merge_into_leaves` — Fusionner dans les feuilles : Pas de type de nœud : ses propriétés et relations sont recopiées dans chaque sous-type concret.
  Raison : Sous OWA, l'absence d'instance directe ne se prouve pas : c'est une heuristique à confirmer.
  Autres options : `node_type` (Garder un type de nœud).

**Neo4j** — Recommandation `secondary_label` — Label secondaire seulement : Type abstrait : le label est porté par les nœuds des sous-classes, jamais seul.
  Raison : Sous OWA, l'absence d'instance directe ne se prouve pas : c'est une heuristique à confirmer.
  Autres options : `merge_into_leaves` (Fusionner dans les feuilles), `node_type` (Garder un type de nœud).

**Ce qui se perd** : L'heuristique « abstraite » est une hypothèse (monde ouvert : l'absence d'instance directe ne se prouve pas). Si elle est fausse, des instances de la classe parente n'ont plus de type.

**Compensation** : Requête de détection / de classification

### C05 — Classes nommées équivalentes *(Must it. 1)* {#c05-classes-nommees-equivalentes-must-it-1}

- **Construct** : owl:equivalentClass entre classes nommées
- **Détection** : equivalentClass dont l'argument est nommé.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:Car`

**Exemple OWL**

```turtle
ex:Car a owl:Class . ex:Automobile a owl:Class .
ex:Car owl:equivalentClass ex:Automobile .
```

**Curiosity** — Recommandation `merge_types` — Fusionner (nom canonique + alias) : Un seul type ; l'autre IRI devient un alias documenté (même extension : sans perte).
  Raison : EquivalentClasses(A B) avec A, B nommées : extensions identiques, la fusion ne perd rien.
  Autres options : `node_type` (Deux types distincts).

**Neo4j** — Recommandation `merge_types` — Fusionner (nom canonique + alias) : Un seul type ; l'autre IRI devient un alias documenté (même extension : sans perte).
  Raison : EquivalentClasses(A B) avec A, B nommées : extensions identiques, la fusion ne perd rien.
  Autres options : `node_type` (Deux types distincts).

**Ce qui se perd** : Rien sur les données si fusion (mêmes extensions) ; l'IRI alias n'existe plus que dans la documentation.

**Compensation** : Documentation (rapport de transposition)

### C06 — Classe définie (classification) {#c06-classe-definie-classification}

- **Construct** : Classe définie (equivalentClass anonyme : restriction / intersection)
- **Détection** : Classe nommée avec une définition nécessaire et suffisante.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:OverdueVehicle`

**Exemple OWL**

```turtle
ex:OverdueVehicle a owl:Class . ex:Vehicle a owl:Class . ex:Defect a owl:Class .
ex:OverdueVehicle owl:equivalentClass [ owl:intersectionOf ( ex:Vehicle
    [ a owl:Restriction ; owl:onProperty ex:hasDefect ; owl:someValuesFrom ex:Defect ] ) ] .
```

**Curiosity** — Recommandation `materialize_at_ingest` — Matérialiser à l'ingestion : Booléen `is<Classe>` calculé par le connecteur.
  Raison : Aucun raisonneur côté LPG : l'appartenance définie doit être calculée et stockée, ou perdue.
  Autres options : `computed_label` (Label calculé), `doc_only` (Documenter seulement).

**Neo4j** — Recommandation `computed_label` — Label calculé : Job de classification (requête) rejoué après chaque ingestion.
  Raison : Aucun raisonneur côté LPG : l'appartenance définie doit être calculée et stockée, ou perdue.
  Autres options : `materialize_at_ingest` (Matérialiser à l'ingestion), `doc_only` (Documenter seulement).

**Ce qui se perd** : La définition nécessaire et suffisante n'est plus exécutée : sans raisonneur, l'appartenance doit être calculée (booléen à l'ingestion ou requête de classification).

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)

### C07 — Disjonction de classes *(Must it. 1)* {#c07-disjonction-de-classes-must-it-1}

- **Construct** : owl:disjointWith / owl:AllDisjointClasses
- **Détection** : Classe déclarant des disjonctions.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:Customer`

**Exemple OWL**

```turtle
ex:Customer a owl:Class . ex:Garage a owl:Class .
ex:Customer owl:disjointWith ex:Garage .
```

**Curiosity** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Mono-type : la disjonction est garantie entre types distincts ; à valider si des classes sont fusionnées.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Aucune contrainte native : requête de détection d'un nœud portant les deux labels.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Aucune base ne refuse un nœud portant les deux types : la disjonction devient un contrôle applicatif (ou une requête de détection).

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### C08 — Classe énumérée {#c08-classe-enumeree}

- **Construct** : owl:oneOf (classe énumérée)
- **Détection** : Classe dont la définition est une énumération d'individus.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:FuelType`

**Exemple OWL**

```turtle
ex:FuelType a owl:Class .
ex:FuelType owl:equivalentClass [ a owl:Class ; owl:oneOf ( ex:Petrol ex:Diesel ) ] .
ex:Petrol a ex:FuelType . ex:Diesel a ex:FuelType .
```

**Curiosity** — Recommandation `reference_nodes` — Nœuds de référence : Un type, un nœud par valeur, relié par une relation : facettes liées, renommage sans dénormalisation.
  Raison : Les valeurs portent des labels multilingues : des nœuds de référence les conservent.
  Autres options : `enum_property` (Propriété énumérée).

**Neo4j** — Recommandation `reference_nodes` — Nœuds de référence : Un type, un nœud par valeur, relié par une relation : facettes liées, renommage sans dénormalisation.
  Raison : Les valeurs portent des labels multilingues : des nœuds de référence les conservent.
  Autres options : `enum_property` (Propriété énumérée).

**Ce qui se perd** : Le caractère fermé de l'énumération (« rien d'autre que ces valeurs ») n'est tenu que par une validation.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### C09 — Expression booléenne anonyme {#c09-expression-booleenne-anonyme}

- **Construct** : owl:unionOf / owl:intersectionOf anonymes
- **Détection** : Union/intersection anonyme en équivalence ou en super-classe (hors définitions C06).
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:Owner`

**Exemple OWL**

```turtle
ex:Owner a owl:Class . ex:Person a owl:Class . ex:Company a owl:Class .
ex:Owner owl:equivalentClass [ owl:unionOf ( ex:Person ex:Company ) ] .
```

**Curiosity** — Recommandation `doc_only` — Documenter seulement : Rien n'est généré : la sémantique est perdue pour les données, tracée au rapport.
  Raison : Pas de type anonyme en LPG ; la sémantique ensembliste est perdue sauf label de regroupement.

**Neo4j** — Recommandation `secondary_label` — Label calculé sur les membres : Le nom de l'union devient un label porté par les nœuds des classes membres.
  Raison : Pas de type anonyme en LPG ; la sémantique ensembliste est perdue sauf label de regroupement.
  Autres options : `doc_only` (Documenter seulement).

**Ce qui se perd** : La sémantique ensembliste de l'union n'a pas d'équivalent : Owner n'est plus « Person ou Company » que dans le rapport (ou par un label de regroupement sous Neo4j).

**Compensation** : Documentation (rapport de transposition)

### C10 — Union disjointe (partition) {#c10-union-disjointe-partition}

- **Construct** : owl:disjointUnionOf
- **Détection** : Classe partitionnée en sous-classes disjointes.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:MaintenanceOperation`

**Exemple OWL**

```turtle
ex:Operation a owl:Class . ex:Inspection a owl:Class . ex:Repair a owl:Class .
ex:Operation owl:disjointUnionOf ( ex:Inspection ex:Repair ) .
```

**Curiosity** — Recommandation `primary_parent_discriminator` — Type parent + discriminant obligatoire : Un type de nœud parent + enum `<parent>Kind` obligatoire (exactement une valeur).
  Raison : La partition devient une contrainte de complétude et d'exclusivité, à valider.
  Autres options : `multi_label` (Labels parent + enfants), `validation` (Validation applicative).

**Neo4j** — Recommandation `multi_label` — Labels parent + enfants : Labels parent et enfants + validation « exactement un label enfant ».
  Raison : La partition devient une contrainte de complétude et d'exclusivité, à valider.
  Autres options : `primary_parent_discriminator` (Type parent + discriminant obligatoire), `validation` (Validation applicative).

**Ce qui se perd** : Complétude et exclusivité deviennent des contrôles (« exactement une valeur de `operationKind` ») : rien n'est bloqué par la base.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### C11 — Complément de classe {#c11-complement-de-classe}

- **Construct** : owl:complementOf
- **Détection** : Complément dans une définition ou une super-classe.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:NonElectricVehicle`

**Exemple OWL**

```turtle
ex:NonElectric a owl:Class . ex:Electric a owl:Class .
ex:NonElectric owl:equivalentClass [ a owl:Class ; owl:complementOf ex:Electric ] .
```

**Curiosity** — Recommandation `materialize_at_ingest` — Matérialiser à l'ingestion : Booléen calculé par le connecteur.
  Raison : Le complément OWL (monde ouvert) devient une négation par défaut (monde clos) : sur-classification possible.
  Autres options : `computed_label` (Label calculé par requête (NOT)), `doc_only` (Documenter seulement).

**Neo4j** — Recommandation `computed_label` — Label calculé par requête (NOT) : Classification par absence de label/propriété : monde clos, à rejouer.
  Raison : Le complément OWL (monde ouvert) devient une négation par défaut (monde clos) : sur-classification possible.
  Autres options : `materialize_at_ingest` (Matérialiser à l'ingestion), `doc_only` (Documenter seulement).

**Ce qui se perd** : Le complément OWL (monde ouvert) devient une négation par défaut (monde clos) : sur-classification possible (un véhicule non encore typé serait « NonElectric »).

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)

### C12 — Punning classe / individu {#c12-punning-classe-individu}

- **Construct** : Punning classe / individu (SS §5.9)
- **Détection** : Même IRI déclarée classe et individu.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:TimingBelt`

**Exemple OWL**

```turtle
ex:PartKind a owl:Class .
ex:TimingBelt a owl:Class, ex:PartKind .   # même IRI : classe ET individu
```

**Curiosity** — Recommandation `reference_nodes` — Type + nœud de référence, noms distincts : Le type de nœud (classe) et le nœud de référence (individu) coexistent sous des noms distincts.
  Raison : Métamodélisation légale en OWL 2 DL ; en LPG, deux éléments distincts.
  Autres options : `ignore` (Ignorer l'individu).

**Neo4j** — Recommandation `reference_nodes` — Type + nœud de référence, noms distincts : Le type de nœud (classe) et le nœud de référence (individu) coexistent sous des noms distincts.
  Raison : Métamodélisation légale en OWL 2 DL ; en LPG, deux éléments distincts.
  Autres options : `ignore` (Ignorer l'individu).

**Ce qui se perd** : Le punning n'existe pas en LPG : classe et individu deviennent deux éléments distincts, le lien d'identité n'est que documenté.

**Compensation** : Documentation (rapport de transposition)

### C13 — Axiome général d'inclusion {#c13-axiome-general-d-inclusion}

- **Construct** : Axiome général d'inclusion (GCI)
- **Détection** : rdfs:subClassOf dont le sujet est anonyme.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:RequiresDPFCheck`

**Exemple OWL**

```turtle
ex:Dpf a owl:Class . ex:RequiresDPFCheck a owl:Class .
[ a owl:Restriction ; owl:onProperty ex:hasDpf ; owl:someValuesFrom ex:Dpf ]
    rdfs:subClassOf ex:RequiresDPFCheck .
```

**Curiosity** — Recommandation `materialize_at_ingest` — Matérialiser à l'ingestion : Booléen calculé par le connecteur.
  Raison : Règle d'inférence sans équivalent LPG.
  Autres options : `computed_label` (Job de classification), `doc_only` (Documenter seulement).

**Neo4j** — Recommandation `computed_label` — Job de classification : Requête qui pose le label conclu.
  Raison : Règle d'inférence sans équivalent LPG.
  Autres options : `materialize_at_ingest` (Matérialiser à l'ingestion), `doc_only` (Documenter seulement).

**Ce qui se perd** : Règle d'inférence (GCI) sans équivalent : la conclusion n'est posée que si on la calcule (booléen à l'ingestion ou requête).

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)


## Identité et clés (K) {#identite-et-cles-k}

### K01 — Identité IRI *(Must it. 1)* {#k01-identite-iri-must-it-1}

- **Construct** : Identité IRI d'un individu nommé
- **Détection** : Individu nommé (IRI).
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:veh_001`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class .
ex:veh_001 a ex:Vehicle .
```

**Curiosity** — Recommandation `uri_key` — Clé = uri : [Key] string = IRI (Curiosity).
  Raison : L'IRI est unique, stable et non vide.

**Neo4j** — Recommandation `unique_constraint` — Propriété uri + UNIQUE : Identité RDF conservée, MERGE idempotent.
  Raison : L'IRI est unique, stable et non vide.

**Ce qui se perd** : Rien : l'IRI devient la clé (`Uri` / `uri`).

**Compensation** : aucune

### K02 — Clé OWL (hasKey) *(Must it. 1)* {#k02-cle-owl-haskey-must-it-1}

- **Construct** : owl:hasKey sur propriétés de données
- **Détection** : Axiome HasKey ne portant que des propriétés de données.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:Vehicle`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class .
ex:vin a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:Vehicle ; rdfs:range xsd:string .
ex:Vehicle owl:hasKey ( ex:vin ) .
```

**Curiosity** — Recommandation `uri_key` — Clé = uri, unicité validée : La clé reste l'IRI ; l'unicité des valeurs hasKey devient une validation applicative.
  Raison : [Key] Curiosity doit être non vide pour chaque nœud : poser la clé sur une propriété que l'ontologie ne rend pas obligatoire est un renforcement ; uri reste sûr, la clé métier est validée.
  Autres options : `node_key` (Clé = propriétés hasKey), `key_concat` (Concaténation).

**Neo4j** — Recommandation `node_key` — Clé = propriétés hasKey : Neo4j : NODE KEY (existence + unicité, Enterprise ; UNIQUE en Community). Curiosity : [Key] = la propriété. RENFORCEMENT : hasKey n'impose ni existence ni unicité.
  Raison : hasKey (SS §9.5) infère sameAs entre individus nommés de mêmes valeurs ; NODE KEY ajoute l'existence obligatoire : renforcement à faire valider.
  Autres options : `unique_constraint` (UNIQUE seulement), `uri_key` (Clé = uri, unicité validée).

**Ce qui se perd** : `hasKey` n'impose ni existence ni unicité en OWL ; la clé LPG (NODE KEY / `[Key]`) les impose : c'est un renforcement, d'où la recommandation prudente côté Curiosity (clé = IRI, unicité de `vin` validée).

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### K03 — Pas de clé métier *(Must it. 1)* {#k03-pas-de-cle-metier-must-it-1}

- **Construct** : Classe sans clé métier
- **Détection** : Classe concrète sans hasKey (ni ancêtre à clé).
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:MileageReading`

**Exemple OWL**

```turtle
ex:MileageReading a owl:Class .   # aucune clé métier
```

**Curiosity** — Recommandation `uri_key` — Clé = uri : Identifiant technique (IRI).
  Raison : uri si les instances ont une IRI ; clé générée si elles sont anonymes (nœuds blancs).
  Autres options : `generated_key` (Clé générée), `property` (Choisir une propriété métier).

**Neo4j** — Recommandation `uri_key` — Clé = uri : Identifiant technique (IRI).
  Raison : uri si les instances ont une IRI ; clé générée si elles sont anonymes (nœuds blancs).
  Autres options : `generated_key` (Clé générée), `property` (Choisir une propriété métier).

**Ce qui se perd** : Pas de clé métier : l'identité est technique (IRI) ou générée ; la déduplication par valeurs n'a pas lieu.

**Compensation** : Arbitrage humain (aucune compensation automatique)

### K04 — Individu anonyme {#k04-individu-anonyme}

- **Construct** : Individu anonyme (nœud blanc, SS §5.6.2)
- **Détection** : Valeur objet nœud blanc typé.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:veh_001`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class . ex:MileageReading a owl:Class .
ex:veh_001 a ex:Vehicle ;
    ex:hasReading [ a ex:MileageReading ; ex:km 42000 ] .   # nœud blanc
ex:hasReading a owl:ObjectProperty . ex:km a owl:DatatypeProperty .
```

**Curiosity** — Recommandation `generated_key` — Clé générée : hash(propriétaire + propriété + valeurs) ou IRI skolem.
  Raison : Un nœud blanc n'a pas d'IRI : aucune clé n'est dérivable (pas K01).
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `generated_key` — Clé générée : hash(propriétaire + propriété + valeurs) ou IRI skolem.
  Raison : Un nœud blanc n'a pas d'IRI : aucune clé n'est dérivable (pas K01).
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Un nœud blanc n'a pas d'IRI : la clé est dérivée (hash ou IRI skolem) et change si les valeurs changent.

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)

### K05 — Clé composite avec propriété objet {#k05-cle-composite-avec-propriete-objet}

- **Construct** : owl:hasKey incluant une propriété objet
- **Détection** : Axiome HasKey portant au moins une propriété objet.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:PartReference`

**Exemple OWL**

```turtle
ex:PartReference a owl:Class . ex:Part a owl:Class .
ex:partOf a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:PartReference ; rdfs:range ex:Part .
ex:refCode a owl:DatatypeProperty ; rdfs:domain ex:PartReference ; rdfs:range xsd:string .
ex:PartReference owl:hasKey ( ex:partOf ex:refCode ) .
```

**Curiosity** — Recommandation `key_concat` — Concaténation avec la clé de la cible : Clé = valeur | clé du nœud cible.
  Raison : Une clé LPG ne porte que des propriétés du nœud.
  Autres options : `uri_key` (Clé = uri).

**Neo4j** — Recommandation `materialize_key` — Copier la clé de la cible + NODE KEY : Propriété `<cible>Key` recopiée à l'ingestion puis NODE KEY composite.
  Raison : Une clé LPG ne porte que des propriétés du nœud.
  Autres options : `uri_key` (Clé = uri).

**Ce qui se perd** : Une clé LPG ne porte que des propriétés du nœud : la partie « relation » de la clé est recopiée (concaténation / propriété `<cible>Key`) et doit être tenue à jour.

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)


## Propriétés de données (D) {#proprietes-de-donnees-d}

### D01 — Propriété de données *(Must it. 1)* {#d01-propriete-de-donnees-must-it-1}

- **Construct** : Propriété de données à domaine nommé unique
- **Détection** : Un seul rdfs:domain nommé.
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:vin`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class .
ex:vin a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:domain ex:Vehicle ; rdfs:range xsd:string .
```

**Curiosity** — Recommandation `property` — Propriété : Propriété typée sur le nœud.
  Raison : Correspondance directe (le domaine RDFS infère ; il devient ici un contrat de schéma, monde clos).

**Neo4j** — Recommandation `property` — Propriété : Propriété typée sur le nœud.
  Raison : Correspondance directe (le domaine RDFS infère ; il devient ici un contrat de schéma, monde clos).

**Ce qui se perd** : Le domaine RDFS infère le type ; il devient un contrat de schéma (monde clos).

**Compensation** : aucune

### D02 — Propriété sans domaine *(Must it. 1)* {#d02-propriete-sans-domaine-must-it-1}

- **Construct** : Propriété de données sans domaine
- **Détection** : Aucun rdfs:domain.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:mileageKm`

**Exemple OWL**

```turtle
ex:mileageKm a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:range xsd:integer .   # pas de domaine
```

**Curiosity** — Recommandation `attach_to_users` — Rattacher aux utilisateurs : Posée sur les types qui l'utilisent (restrictions, shapes, assertions) ; non posée si elle n'est utilisée que via ses sous-propriétés.
  Raison : Une propriété LPG appartient à un type de nœud.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `attach_to_users` — Rattacher aux utilisateurs : Posée sur les types qui l'utilisent (restrictions, shapes, assertions) ; non posée si elle n'est utilisée que via ses sous-propriétés.
  Raison : Une propriété LPG appartient à un type de nœud.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Une propriété LPG appartient à un type : sans domaine, le rattachement vient des usages (restrictions, shapes) ; sans usage, elle n'est pas posée.

**Compensation** : Arbitrage humain (aucune compensation automatique)

### D03 — Domaine en union {#d03-domaine-en-union}

- **Construct** : Domaine = owl:unionOf (union explicite)
- **Détection** : rdfs:domain [owl:unionOf (…)].
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:phoneNumber`

**Exemple OWL**

```turtle
ex:Customer a owl:Class . ex:Garage a owl:Class .
ex:phoneNumber a owl:DatatypeProperty ; rdfs:range xsd:string ;
    rdfs:domain [ a owl:Class ; owl:unionOf ( ex:Customer ex:Garage ) ] .
```

**Curiosity** — Recommandation `duplicate_per_type` — Dupliquer sur chaque type : Même nom sur chaque membre de l'union.
  Raison : Seule une union explicite autorise la duplication (≠ plusieurs rdfs:domain, D12).

**Neo4j** — Recommandation `duplicate_per_type` — Dupliquer sur chaque type : Même nom sur chaque membre de l'union.
  Raison : Seule une union explicite autorise la duplication (≠ plusieurs rdfs:domain, D12).

**Ce qui se perd** : La propriété est dupliquée sur chaque membre ; le fait qu'il s'agisse « de la même propriété » n'est plus que documenté.

**Compensation** : aucune

### D04 — Propriété non fonctionnelle *(Must it. 1)* {#d04-propriete-non-fonctionnelle-must-it-1}

- **Construct** : Propriété de données non fonctionnelle
- **Détection** : Ni FunctionalProperty, ni max/exactly 1, ni sh:maxCount 1.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:commercialName`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class .
ex:tag a owl:DatatypeProperty ; rdfs:domain ex:Vehicle ; rdfs:range xsd:string .   # non fonctionnelle
```

**Curiosity** — Recommandation `scalar` — Scalaire : Une seule valeur ; valeurs multiples perdues à l'ingestion.
  Raison : OWA : l'absence de FunctionalProperty ne prouve pas la multivaluation : liste si plusieurs valeurs sont observées, scalaire sinon.
  Autres options : `list_property` (Liste).

**Neo4j** — Recommandation `scalar` — Scalaire : Une seule valeur ; valeurs multiples perdues à l'ingestion.
  Raison : OWA : l'absence de FunctionalProperty ne prouve pas la multivaluation : liste si plusieurs valeurs sont observées, scalaire sinon.
  Autres options : `list_property` (Liste).

**Ce qui se perd** : Choix entre liste (aucune perte) et scalaire (valeurs multiples perdues à l'ingestion) ; sous OWA, l'absence de `Functional` ne prouve pas la multivaluation.

**Compensation** : aucune

### D05 — Type de données avec perte *(Must it. 1)* {#d05-type-de-donnees-avec-perte-must-it-1}

- **Construct** : Typage xsd avec perte
- **Détection** : decimal, hexBinary/base64Binary, dateTimeStamp, owl:real/rational, types hors carte OWL 2 (gYear, date, duration… : aussi W01).
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:mileageKm`

**Exemple OWL**

```turtle
ex:Part a owl:Class .
ex:price a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:Part ; rdfs:range xsd:decimal .
```

**Curiosity** — Recommandation `native_type` — Type natif le plus proche : decimal → flottant (précision), dateTimeStamp → date-heure à fuseau, gYear → entier…
  Raison : Pas de décimal ni de binaire natifs en LPG.
  Autres options : `string_lexical` (Forme lexicale en texte).

**Neo4j** — Recommandation `native_type` — Type natif le plus proche : decimal → flottant (précision), dateTimeStamp → date-heure à fuseau, gYear → entier…
  Raison : Pas de décimal ni de binaire natifs en LPG.
  Autres options : `string_lexical` (Forme lexicale en texte).

**Ce qui se perd** : **Neo4j** : pas de décimal exact natif : `xsd:decimal` → flottant (précision perdue, constat D05 conservé) ou chaîne (exact mais non comparable numériquement). **Curiosity** : depuis L13 (D-L13-01), `xsd:decimal` devient le type `decimal` C# sans perte (28-29 chiffres significatifs) et aucun constat D05 n'est émis pour ce type ; la fiche du catalogue ci-dessus, antérieure, décrit le repli en flottant.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### D06 — Valeurs multilingues *(Must it. 1)* {#d06-valeurs-multilingues-must-it-1}

- **Construct** : Valeurs multilingues (rdf:PlainLiteral, @lang)
- **Détection** : Portée rdf:PlainLiteral / rdf:langString (non conforme, W01) ou littéraux à langue observés.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:operationDescription`

**Exemple OWL**

```turtle
ex:Operation a owl:Class .
ex:description a owl:DatatypeProperty ; rdfs:domain ex:Operation ; rdfs:range rdf:PlainLiteral .
```

**Curiosity** — Recommandation `per_language_property` — Une propriété par langue : label_fr, label_en ; langues hors liste perdues.
  Raison : Pas de littéral à langue en LPG.
  Autres options : `string_property` (Texte sans langue).

**Neo4j** — Recommandation `per_language_property` — Une propriété par langue : label_fr, label_en ; langues hors liste perdues.
  Raison : Pas de littéral à langue en LPG.
  Autres options : `string_property` (Texte sans langue).

**Ce qui se perd** : L'étiquette de langue (`@fr`) est perdue, ou éclatée en une propriété par langue (`description_fr`) ; langues hors liste perdues.

**Compensation** : aucune

### D07 — Propriété fonctionnelle *(Must it. 1)* {#d07-propriete-fonctionnelle-must-it-1}

- **Construct** : owl:FunctionalProperty (données)
- **Détection** : Propriété de données fonctionnelle.
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:vin`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class .
ex:vin a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:Vehicle ; rdfs:range xsd:string .
```

**Curiosity** — Recommandation `scalar` — Scalaire : Valeur unique (+ contrainte de type si l'édition le permet).
  Raison : Correspondance directe.

**Neo4j** — Recommandation `scalar` — Scalaire : Valeur unique (+ contrainte de type si l'édition le permet).
  Raison : Correspondance directe.

**Ce qui se perd** : Rien : valeur unique.

**Compensation** : aucune

### D08 — Énumération de littéraux {#d08-enumeration-de-litteraux}

- **Construct** : DataOneOf (énumération de littéraux)
- **Détection** : Portée owl:oneOf de littéraux.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:emissionStandard`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class .
ex:emissionStandard a owl:DatatypeProperty ; rdfs:domain ex:Vehicle ;
    rdfs:range [ a rdfs:Datatype ; owl:oneOf ( "Euro5" "Euro6" ) ] .
```

**Curiosity** — Recommandation `enum_property` — Propriété énumérée + validation : Texte + contrôle des valeurs (pas de contrainte d'énumération native).
  Raison : Petit ensemble figé de littéraux.
  Autres options : `reference_nodes` (Nœuds de référence).

**Neo4j** — Recommandation `enum_property` — Propriété énumérée + validation : Texte + contrôle des valeurs (pas de contrainte d'énumération native).
  Raison : Petit ensemble figé de littéraux.
  Autres options : `reference_nodes` (Nœuds de référence).

**Ce qui se perd** : Aucune contrainte d'énumération native : les valeurs sont contrôlées par validation, ou deviennent des nœuds de référence.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### D09 — Datatype à facettes {#d09-datatype-a-facettes}

- **Construct** : Datatype défini / facettes
- **Détection** : rdfs:Datatype défini par owl:withRestrictions (min/max, pattern, length).
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:ModelYear`

**Exemple OWL**

```turtle
ex:VehicleModel a owl:Class .
ex:ModelYear a rdfs:Datatype ;
    owl:equivalentClass [ a rdfs:Datatype ; owl:onDatatype xsd:integer ;
        owl:withRestrictions ( [ xsd:minInclusive "1950"^^xsd:integer ] [ xsd:maxInclusive "2100"^^xsd:integer ] ) ] .
ex:modelYear a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:VehicleModel ; rdfs:range ex:ModelYear .
```

**Curiosity** — Recommandation `validation` — Type de base + validation : Le type de base natif est utilisé ; bornes et motifs deviennent des validations.
  Raison : Aucune facette native en LPG.
  Autres options : `native_type` (Type de base seul).

**Neo4j** — Recommandation `validation` — Type de base + validation : Le type de base natif est utilisé ; bornes et motifs deviennent des validations.
  Raison : Aucune facette native en LPG.
  Autres options : `native_type` (Type de base seul).

**Ce qui se perd** : Bornes et motifs n'ont pas d'équivalent natif : ils deviennent des validations (ou sont perdus avec `native_type`).

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### D10 — Littéral non typé {#d10-litteral-non-type}

- **Construct** : Portée rdfs:Literal ou absente
- **Détection** : Portée non contrainte.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:legacyCode`

**Exemple OWL**

```turtle
ex:Part a owl:Class .
ex:legacyCode a owl:DatatypeProperty ; rdfs:domain ex:Part ; rdfs:range rdfs:Literal .
```

**Curiosity** — Recommandation `string_property` — Texte : Typage d'origine perdu.
  Raison : Type inconnu : texte par défaut.

**Neo4j** — Recommandation `string_property` — Texte : Typage d'origine perdu.
  Raison : Type inconnu : texte par défaut.

**Ce qui se perd** : Le type d'origine n'existe pas : texte par défaut.

**Compensation** : aucune

### D11 — Sous-propriété de données {#d11-sous-propriete-de-donnees}

- **Construct** : rdfs:subPropertyOf entre propriétés de données
- **Détection** : Sous-propriété de données.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:readingMileageKm`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class . ex:MileageReading a owl:Class .
ex:mileageKm a owl:DatatypeProperty ; rdfs:domain ex:Vehicle ; rdfs:range xsd:integer .
ex:readingMileageKm a owl:DatatypeProperty ; rdfs:subPropertyOf ex:mileageKm ;
    rdfs:domain ex:MileageReading ; rdfs:range xsd:integer .
```

**Curiosity** — Recommandation `most_specific_type` — Propriété la plus spécifique : La super-propriété n'est pas stockée : une requête sur le parent doit lister les sous-propriétés.
  Raison : Pas de hiérarchie de propriétés en LPG.
  Autres options : `materialize_closure` (Dupliquer dans la super-propriété).

**Neo4j** — Recommandation `most_specific_type` — Propriété la plus spécifique : La super-propriété n'est pas stockée : une requête sur le parent doit lister les sous-propriétés.
  Raison : Pas de hiérarchie de propriétés en LPG.
  Autres options : `materialize_closure` (Dupliquer dans la super-propriété).

**Ce qui se perd** : La hiérarchie de propriétés disparaît : interroger la super-propriété demande de lister les sous-propriétés (ou une double écriture).

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)

### D12 — Intersection de domaines / portées {#d12-intersection-de-domaines-portees}

- **Construct** : Plusieurs rdfs:domain / rdfs:range (données) = intersection
- **Détection** : Au moins deux domaines nommés ou deux portées.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:warrantyDurationMonths`

**Exemple OWL**

```turtle
ex:Warranty a owl:Class . ex:Contract a owl:Class .
ex:warrantyMonths a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:range xsd:integer ;
    rdfs:domain ex:Warranty ; rdfs:domain ex:Contract .   # deux domaines = INTERSECTION
```

**Curiosity** — Recommandation `native_type` — Type natif de l'intersection : Type le plus restrictif + validation des bornes.
  Raison : Plusieurs axiomes de domaine/portée se cumulent (RSEM rdfs2/rdfs3).
  Autres options : `intersection_domain` (Domaine = intersection), `duplicate_per_type` (Traiter comme une union).

**Neo4j** — Recommandation `native_type` — Type natif de l'intersection : Type le plus restrictif + validation des bornes.
  Raison : Plusieurs axiomes de domaine/portée se cumulent (RSEM rdfs2/rdfs3).
  Autres options : `intersection_domain` (Domaine = intersection), `duplicate_per_type` (Traiter comme une union).

**Ce qui se perd** : Piège de lecture : deux `rdfs:domain` signifient « instance des DEUX classes » (rdfs2). La plupart du temps c'est une erreur de modélisation (l'auteur voulait une union).

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### D13 — Restriction sur propriété de données {#d13-restriction-sur-propriete-de-donnees}

- **Construct** : Restriction sur propriété de données
- **Détection** : some / only / cardinalité / onDataRange.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:RepairOrder`

**Exemple OWL**

```turtle
ex:RepairOrder a owl:Class .
ex:RepairOrder rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:openedAt ; owl:cardinality "1"^^xsd:nonNegativeInteger ] .
ex:openedAt a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:RepairOrder ; rdfs:range xsd:dateTime .
```

**Curiosity** — Recommandation `validation` — Validation : exactly 1 / min 1 → propriété obligatoire + contrôle.
  Raison : Les restrictions OWL infèrent ; en LPG elles deviennent des contrôles (monde clos).
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation : exactly 1 / min 1 → propriété obligatoire + contrôle.
  Raison : Les restrictions OWL infèrent ; en LPG elles deviennent des contrôles (monde clos).
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : L'axiome infère en OWL ; en LPG il ne peut que contrôler : propriété obligatoire + validation, rien n'est bloqué par la base.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)


## Propriétés objet (O) {#proprietes-objet-o}

### O01 — Propriété objet → relation *(Must it. 1)* {#o01-propriete-objet-relation-must-it-1}

- **Construct** : Propriété objet à domaine et portée nommés uniques
- **Détection** : Un domaine et une portée nommés.
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:worksAt`

**Exemple OWL**

```turtle
ex:Technician a owl:Class . ex:Garage a owl:Class .
ex:worksAt a owl:ObjectProperty ; rdfs:domain ex:Technician ; rdfs:range ex:Garage .
```

**Curiosity** — Recommandation `edge_pair` — Paire d'arêtes aller / retour : Constante aller + retour, Link(a, b, aller, retour).
  Raison : Correspondance directe.

**Neo4j** — Recommandation `relationship` — Type de relation : UPPER_SNAKE, un sens stocké.
  Raison : Correspondance directe.

**Ce qui se perd** : Rien : correspondance directe.

**Compensation** : aucune

### O02 — Domaine / portée manquants *(Must it. 1)* {#o02-domaine-portee-manquants-must-it-1}

- **Construct** : Propriété objet sans domaine ou sans portée
- **Détection** : Domaine ou portée absents.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:interchangeableWith`

**Exemple OWL**

```turtle
ex:interchangeableWith a owl:ObjectProperty .   # ni domaine ni portée
```

**Curiosity** — Recommandation `edge_pair` — Résoudre puis paire d'arêtes : Extrémités déduites des restrictions, shapes, assertions et de l'inverse.
  Raison : Le connecteur doit savoir quels types relier.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `relationship` — Résoudre puis relation : Extrémités déduites des restrictions, shapes, assertions et de l'inverse.
  Raison : Le connecteur doit savoir quels types relier.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Les extrémités sont déduites des usages ; sans usage, la relation n'est pas transposée (connecteur : quels types relier ?).

**Compensation** : Arbitrage humain (aucune compensation automatique)

### O03 — Domaine / portée en union *(Must it. 1)* {#o03-domaine-portee-en-union-must-it-1}

- **Construct** : Domaine / portée = owl:unionOf
- **Détection** : rdfs:domain ou rdfs:range [owl:unionOf (…)].
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:hasOwner`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class . ex:Person a owl:Class . ex:Company a owl:Class .
ex:hasOwner a owl:ObjectProperty ; rdfs:domain ex:Vehicle ;
    rdfs:range [ a owl:Class ; owl:unionOf ( ex:Person ex:Company ) ] .
```

**Curiosity** — Recommandation `edge_pair` — Une arête par paire de types : Même nom d'arête pour chaque paire.
  Raison : Union explicite seulement (≠ plusieurs rdfs:range : O21).

**Neo4j** — Recommandation `relationship` — Un type, plusieurs paires de labels : Validation des paires autorisées.
  Raison : Union explicite seulement (≠ plusieurs rdfs:range : O21).

**Ce qui se perd** : La portée disjonctive devient plusieurs paires d'extrémités (Curiosity) ou une validation des paires autorisées (Neo4j).

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O04 — Propriétés inverses *(Must it. 1)* {#o04-proprietes-inverses-must-it-1}

- **Construct** : owl:inverseOf
- **Détection** : Paire de propriétés inverses.
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:hasPart`

**Exemple OWL**

```turtle
ex:hasPart a owl:ObjectProperty ; owl:inverseOf ex:isPartOf .
ex:isPartOf a owl:ObjectProperty .
```

**Curiosity** — Recommandation `edge_pair` — Paire aller / retour : Curiosity : retour natif gratuit. Neo4j : les deux sens stockés (double écriture).
  Raison : Un seul fait, deux noms.

**Neo4j** — Recommandation `single_direction` — Un seul sens stocké : L'autre sens est traversé ; le nom inverse est documenté.
  Raison : Un seul fait, deux noms.
  Autres options : `edge_pair` (Paire aller / retour).

**Ce qui se perd** : Curiosity : rien (arête avec retour). Neo4j : un sens stocké recommandé, l'autre est traversé ; double écriture si on choisit de stocker les deux.

**Compensation** : aucune

### O05 — Propriété symétrique *(Must it. 1)* {#o05-propriete-symetrique-must-it-1}

- **Construct** : owl:SymmetricProperty
- **Détection** : Propriété symétrique.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:interchangeableWith`

**Exemple OWL**

```turtle
ex:Part a owl:Class .
ex:interchangeableWith a owl:ObjectProperty, owl:SymmetricProperty ; rdfs:domain ex:Part ; rdfs:range ex:Part .
```

**Curiosity** — Recommandation `self_reverse` — Arête = son propre retour : Même constante dans les deux sens.
  Raison : Évite deux faits pour une relation symétrique.
  Autres options : `edge_pair` (Stocker les deux sens).

**Neo4j** — Recommandation `undirected_query` — Un sens stocké, requêtes non orientées : MATCH (a)-[:T]-(b) ; sens stocké arbitraire.
  Raison : Évite deux faits pour une relation symétrique.
  Autres options : `edge_pair` (Stocker les deux sens).

**Ce qui se perd** : Le sens stocké est arbitraire (Neo4j) ; la symétrie n'est plus inférée, on la lit avec une requête non dirigée.

**Compensation** : aucune

### O06 — Propriété transitive *(Must it. 1)* {#o06-propriete-transitive-must-it-1}

- **Construct** : owl:TransitiveProperty
- **Détection** : Propriété transitive.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:isComponentOf`

**Exemple OWL**

```turtle
ex:Part a owl:Class .
ex:isComponentOf a owl:ObjectProperty, owl:TransitiveProperty ; rdfs:domain ex:Part ; rdfs:range ex:Part .
```

**Curiosity** — Recommandation `materialize_closure` — Matérialiser la fermeture : Arête dérivée `<nom>Transitive` recalculée après ingestion.
  Raison : Pas de chemin de longueur variable documenté : la fermeture est matérialisée.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `var_length_query` — Requête à longueur variable : -[:T*1..]-> : compensation complète en lecture, aucune contrainte.
  Raison : Les chemins variables sont natifs en Cypher (compensation complète en lecture seulement).
  Autres options : `materialize_closure` (Matérialiser la fermeture), `ignore` (Ignorer).

**Ce qui se perd** : La fermeture transitive n'est plus inférée : arête dérivée à recalculer après ingestion (Curiosity) ou requête à longueur variable (Neo4j, sans stockage).

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)

### O07 — Sous-propriété objet *(Must it. 1)* {#o07-sous-propriete-objet-must-it-1}

- **Construct** : rdfs:subPropertyOf (objet)
- **Détection** : Sous-propriété objet (hors topObjectProperty).
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:hasEngine`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class . ex:Part a owl:Class . ex:Engine a owl:Class .
ex:hasComponent a owl:ObjectProperty ; rdfs:domain ex:Vehicle ; rdfs:range ex:Part .
ex:hasEngine a owl:ObjectProperty ; rdfs:subPropertyOf ex:hasComponent ; rdfs:domain ex:Vehicle ; rdfs:range ex:Engine .
```

**Curiosity** — Recommandation `most_specific_type` — Type le plus spécifique : Seule la sous-relation est stockée ; requête parent = union de types.
  Raison : Pas de hiérarchie de types de relation en LPG.
  Autres options : `materialize_closure` (Matérialiser aussi le parent).

**Neo4j** — Recommandation `most_specific_type` — Type le plus spécifique : Seule la sous-relation est stockée ; requête parent = union de types.
  Raison : Pas de hiérarchie de types de relation en LPG.
  Autres options : `materialize_closure` (Matérialiser aussi le parent).

**Ce qui se perd** : Seule la sous-relation est stockée : interroger le parent revient à faire l'union des sous-relations (ou à dupliquer l'écriture).

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)

### O08 — Chaîne de propriétés {#o08-chaine-de-proprietes}

- **Construct** : owl:propertyChainAxiom
- **Détection** : Propriété définie par une chaîne.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:vehicleBrand`

**Exemple OWL**

```turtle
ex:VehicleModel a owl:Class . ex:Brand a owl:Class . ex:Vehicle a owl:Class .
ex:madeBy a owl:ObjectProperty ; rdfs:domain ex:VehicleModel ; rdfs:range ex:Brand .
ex:ofModel a owl:ObjectProperty ; rdfs:domain ex:Vehicle ; rdfs:range ex:VehicleModel .
ex:vehicleBrand a owl:ObjectProperty ; owl:propertyChainAxiom ( ex:ofModel ex:madeBy ) .
```

**Curiosity** — Recommandation `materialize_closure` — Matérialiser le raccourci : Arête dérivée recalculée après ingestion.
  Raison : Aucune inférence côté LPG.

**Neo4j** — Recommandation `path_query` — Requête de chemin : Non stocké ; calculé à la lecture.
  Raison : Aucune inférence côté LPG.
  Autres options : `materialize_closure` (Matérialiser le raccourci).

**Ce qui se perd** : L'inclusion `ofModel ∘ madeBy ⊑ vehicleBrand` n'est plus inférée : l'arête est matérialisée après ingestion (Curiosity) ou calculée à la lecture (Neo4j).

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)

### O09 — Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) *(Must it. 1)* {#o09-cardinalite-1-d-une-relation-max-exactly-fonctionnelle-must-it-1}

- **Construct** : Fonctionnelle / max 1 / exactly 1 (objet)
- **Détection** : FunctionalProperty ou restriction max/exactly ≤ 1.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:ofModel`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class . ex:VehicleModel a owl:Class .
ex:ofModel a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:Vehicle ; rdfs:range ex:VehicleModel .
```

**Curiosity** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Aucune contrainte de cardinalité de relation en LPG.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Aucune contrainte de cardinalité de relation en LPG.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Aucune cardinalité de relation en LPG : contrôle applicatif « au plus une relation sortante ».

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O10 — Existence d'une relation *(Must it. 1)* {#o10-existence-d-une-relation-must-it-1}

- **Construct** : some / min n (objet, non qualifiée)
- **Détection** : Restriction d'existence.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:RepairOrder`

**Exemple OWL**

```turtle
ex:RepairOrder a owl:Class . ex:Technician a owl:Class .
ex:RepairOrder rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:performedBy ; owl:someValuesFrom ex:Technician ] .
ex:performedBy a owl:ObjectProperty .
```

**Curiosity** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : OWA : some n'oblige pas à connaître la valeur ; en LPG c'est un contrôle de complétude.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : OWA : some n'oblige pas à connaître la valeur ; en LPG c'est un contrôle de complétude.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : `some` n'oblige pas à connaître la valeur en OWL (OWA) ; en LPG c'est un contrôle de complétude (relation obligatoire).

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O11 — Restriction universelle {#o11-restriction-universelle}

- **Construct** : only (allValuesFrom)
- **Détection** : Restriction universelle.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:RepairOrder`

**Exemple OWL**

```turtle
ex:RepairOrder a owl:Class . ex:Part a owl:Class .
ex:RepairOrder rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:uses ; owl:allValuesFrom ex:Part ] .
ex:uses a owl:ObjectProperty .
```

**Curiosity** — Recommandation `validation` — Validation du type de la cible : Contrôle que la cible a le bon type.
  Raison : only infère le type de la cible (OWA) ; ≠ sh:class qui le vérifie.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation du type de la cible : Contrôle que la cible a le bon type.
  Raison : only infère le type de la cible (OWA) ; ≠ sh:class qui le vérifie.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : `only` infère le type de la cible en OWL ; en LPG il ne reste qu'un contrôle du type de la cible (≠ sh:class qui vérifie).

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O12 — Valeur imposée {#o12-valeur-imposee}

- **Construct** : hasValue
- **Détection** : Restriction de valeur.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:ElectricVehicle`

**Exemple OWL**

```turtle
ex:ElectricVehicle a owl:Class .
ex:ElectricVehicle rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:fuelType ; owl:hasValue ex:Electricity ] .
ex:fuelType a owl:ObjectProperty . ex:Electricity a owl:NamedIndividual .
```

**Curiosity** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Pas de valeur par défaut dans un schéma LPG.
  Autres options : `materialize_at_ingest` (Poser la valeur à l'ingestion).

**Neo4j** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Pas de valeur par défaut dans un schéma LPG.
  Autres options : `materialize_at_ingest` (Poser la valeur à l'ingestion).

**Ce qui se perd** : Pas de valeur par défaut dans un schéma LPG : validation, ou création de la relation par le connecteur.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O13 — Caractéristiques de propriété {#o13-caracteristiques-de-propriete}

- **Construct** : Réflexive / irréflexive / asymétrique
- **Détection** : Caractéristiques de propriété.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:interchangeableWith`

**Exemple OWL**

```turtle
ex:interchangeableWith a owl:ObjectProperty, owl:IrreflexiveProperty, owl:AsymmetricProperty .
```

**Curiosity** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Aucune contrainte native ; la réflexivité globale est souvent une erreur.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Aucune contrainte native ; la réflexivité globale est souvent une erreur.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Aucune contrainte native : contrôle applicatif (« pas de boucle »). La réflexivité seule n'est jamais matérialisée (ce serait une boucle par nœud).

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O14 — Propriété inverse anonyme {#o14-propriete-inverse-anonyme}

- **Construct** : ObjectInverseOf anonyme
- **Détection** : [owl:inverseOf :p] dans une restriction ou une chaîne.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:Garage`

**Exemple OWL**

```turtle
ex:Garage a owl:Class . ex:Technician a owl:Class .
ex:Garage rdfs:subClassOf [ a owl:Restriction ;
    owl:onProperty [ owl:inverseOf ex:worksAt ] ; owl:someValuesFrom ex:Technician ] .
ex:worksAt a owl:ObjectProperty .
```

**Curiosity** — Recommandation `reverse_traversal` — Traversée inverse : Lecture par le sens retour de la relation.
  Raison : Pas d'inverse anonyme en LPG, mais toute relation se traverse dans les deux sens.
  Autres options : `resolve_named_inverse` (Inverse nommé).

**Neo4j** — Recommandation `reverse_traversal` — Traversée inverse : Lecture par le sens retour de la relation.
  Raison : Pas d'inverse anonyme en LPG, mais toute relation se traverse dans les deux sens.
  Autres options : `resolve_named_inverse` (Inverse nommé).

**Ce qui se perd** : Pas d'inverse anonyme : la restriction se lit par le sens retour de la relation (ou par l'inverse nommé s'il existe).

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O15 — Propriété inverse-fonctionnelle {#o15-propriete-inverse-fonctionnelle}

- **Construct** : owl:InverseFunctionalProperty
- **Détection** : Propriété inverse-fonctionnelle.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:hasRepairOrder`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class . ex:RepairOrder a owl:Class .
ex:hasRepairOrder a owl:ObjectProperty, owl:InverseFunctionalProperty ; rdfs:domain ex:Vehicle ; rdfs:range ex:RepairOrder .
```

**Curiosity** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Au plus une relation entrante par cible : contrôle applicatif.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Au plus une relation entrante par cible : contrôle applicatif.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : « Au plus une relation entrante par cible » n'est pas contraignable : contrôle applicatif.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O16 — Cardinalité qualifiée {#o16-cardinalite-qualifiee}

- **Construct** : Cardinalité qualifiée (onClass)
- **Détection** : min/max/exactly avec owl:onClass, propriété simple.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:Car`

**Exemple OWL**

```turtle
ex:Car a owl:Class . ex:Wheel a owl:Class .
ex:Car rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:hasWheel ;
    owl:qualifiedCardinality "4"^^xsd:nonNegativeInteger ; owl:onClass ex:Wheel ] .
ex:hasWheel a owl:ObjectProperty .
```

**Curiosity** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Validation filtrée par type de la cible.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Validation filtrée par type de la cible.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Cardinalité qualifiée : contrôle filtré par type de la cible, rien n'est bloqué nativement.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O17 — Restriction hasSelf {#o17-restriction-hasself}

- **Construct** : owl:hasSelf
- **Détection** : Restriction ObjectHasSelf.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:SelfEmployedTechnician`

**Exemple OWL**

```turtle
ex:SelfEmployedTechnician a owl:Class .
ex:SelfEmployedTechnician rdfs:subClassOf [ a owl:Restriction ; owl:onProperty ex:employs ; owl:hasSelf true ] .
ex:employs a owl:ObjectProperty .
```

**Curiosity** — Recommandation `materialize_at_ingest` — Booléen matérialisé : Booléen calculé à l'ingestion (boucle détectée).
  Raison : Une boucle n'est pas un concept de schéma LPG.
  Autres options : `validation` (Validation applicative).

**Neo4j** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Une boucle n'est pas un concept de schéma LPG.
  Autres options : `materialize_at_ingest` (Booléen matérialisé).

**Ce qui se perd** : Une boucle n'est pas un concept de schéma LPG : booléen calculé à l'ingestion ou validation.

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)

### O18 — Super-propriété universelle {#o18-super-propriete-universelle}

- **Construct** : owl:topObjectProperty / topDataProperty en super-propriété
- **Détection** : subPropertyOf top.
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:relatedTo`

**Exemple OWL**

```turtle
ex:relatedTo a owl:ObjectProperty ; rdfs:subPropertyOf owl:topObjectProperty .
```

**Curiosity** — Recommandation `ignore` — Ignorer (documenté) : Aucun effet en LPG.
  Raison : La propriété universelle relie tout à tout : sans contenu transposable.

**Neo4j** — Recommandation `ignore` — Ignorer (documenté) : Aucun effet en LPG.
  Raison : La propriété universelle relie tout à tout : sans contenu transposable.

**Ce qui se perd** : Aucun effet : la propriété universelle ne porte rien de transposable (tracé au rapport).

**Compensation** : Documentation (rapport de transposition)

### O19 — Propriétés équivalentes {#o19-proprietes-equivalentes}

- **Construct** : owl:equivalentProperty
- **Détection** : Propriétés objet équivalentes.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:ownedBy`

**Exemple OWL**

```turtle
ex:ownedBy a owl:ObjectProperty ; owl:equivalentProperty ex:hasOwner .
```

**Curiosity** — Recommandation `merge_relationship_types` — Fusionner les types de relation : Nom canonique + alias documenté.
  Raison : Même extension : fusion sans perte.
  Autres options : `doc_only` (Garder séparées).

**Neo4j** — Recommandation `merge_relationship_types` — Fusionner les types de relation : Nom canonique + alias documenté.
  Raison : Même extension : fusion sans perte.
  Autres options : `doc_only` (Garder séparées).

**Ce qui se perd** : Sans perte si fusion (nom canonique + alias documenté) ; avec deux relations, à synchroniser.

**Compensation** : Documentation (rapport de transposition)

### O20 — Propriétés disjointes {#o20-proprietes-disjointes}

- **Construct** : owl:propertyDisjointWith / AllDisjointProperties
- **Détection** : Propriétés disjointes.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:performedBy`

**Exemple OWL**

```turtle
ex:performedBy a owl:ObjectProperty ; owl:propertyDisjointWith ex:validatedBy .
```

**Curiosity** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Deux relations ne peuvent relier la même paire : contrôle applicatif.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation applicative : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.
  Raison : Deux relations ne peuvent relier la même paire : contrôle applicatif.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Deux relations ne peuvent relier la même paire : contrôle applicatif seulement.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### O21 — Intersection de domaines / portées {#o21-intersection-de-domaines-portees}

- **Construct** : Plusieurs rdfs:domain / rdfs:range (objet) = intersection
- **Détection** : Au moins deux domaines ou portées nommés.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:reportsFaultCode`

**Exemple OWL**

```turtle
ex:FaultCode a owl:Class . ex:Diagnostic a owl:Class . ex:Report a owl:Class .
ex:reportsFaultCode a owl:ObjectProperty ; rdfs:range ex:FaultCode ;
    rdfs:domain ex:Diagnostic ; rdfs:domain ex:Report .   # INTERSECTION
```

**Curiosity** — Recommandation `intersection_domain` — Domaine = intersection : Relation depuis chaque domaine + validation « appartient à tous » (souvent erreur de modélisation).
  Raison : rdfs2/rdfs3 : le sujet est instance des DEUX classes ; à arbitrer.
  Autres options : `most_specific_type` (Classe la plus spécifique), `duplicate_per_type` (Traiter comme une union).

**Neo4j** — Recommandation `intersection_domain` — Domaine = intersection : Relation depuis chaque domaine + validation « appartient à tous » (souvent erreur de modélisation).
  Raison : rdfs2/rdfs3 : le sujet est instance des DEUX classes ; à arbitrer.
  Autres options : `most_specific_type` (Classe la plus spécifique), `duplicate_per_type` (Traiter comme une union).

**Ce qui se perd** : Même piège que D12 : sujet instance des deux classes (rdfs2) ; à arbitrer car souvent fautif.

**Compensation** : Arbitrage humain (aucune compensation automatique)


## Réification (R) {#reification-r}

### R01 — Réification binaire *(Must it. 1)* {#r01-reification-binaire-must-it-1}

- **Construct** : Classe de réification binaire
- **Détection** : Exactement 2 rôles objet fonctionnels (ou max/exactly 1) + des propriétés de données, classe non cible d'autres relations.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:PartInstallation`

**Exemple OWL**

```turtle
ex:Part a owl:Class . ex:Vehicle a owl:Class .
ex:PartInstallation a owl:Class .
ex:installedPart a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:PartInstallation ; rdfs:range ex:Part .
ex:installedOn   a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:PartInstallation ; rdfs:range ex:Vehicle .
ex:installedAt   a owl:DatatypeProperty, owl:FunctionalProperty ; rdfs:domain ex:PartInstallation ; rdfs:range xsd:date .
```

**Curiosity** — Recommandation `keep_node` — Garder un nœud : Un saut de plus, extensible.
  Raison : Les arêtes Curiosity ne portent pas de propriétés : dé-réifier perdrait les attributs.

**Neo4j** — Recommandation `dereify_relationship` — Relation porteuse de propriétés : Plus de nœud intermédiaire ; la relation porte les propriétés et ne peut être cible d'autres relations.
  Raison : Neo4j : les relations portent des propriétés, la réification binaire se dé-réifie.
  Autres options : `keep_node` (Garder un nœud).

**Ce qui se perd** : Neo4j : dé-réifier fait disparaître le nœud ; la relation ne peut plus être la cible d'autres relations. Curiosity : l'arête ne porte pas de propriété, le nœud reste.

**Compensation** : aucune

### R02 — Relation n-aire *(Must it. 1)* {#r02-relation-n-aire-must-it-1}

- **Construct** : Relation n-aire (≥ 3 rôles)
- **Détection** : Au moins 3 rôles objet fonctionnels.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:WarrantyClaim`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class . ex:Part a owl:Class . ex:Garage a owl:Class .
ex:WarrantyClaim a owl:Class .
ex:claimVehicle a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:WarrantyClaim ; rdfs:range ex:Vehicle .
ex:claimPart    a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:WarrantyClaim ; rdfs:range ex:Part .
ex:claimGarage  a owl:ObjectProperty, owl:FunctionalProperty ; rdfs:domain ex:WarrantyClaim ; rdfs:range ex:Garage .
```

**Curiosity** — Recommandation `keep_node` — Garder un nœud (pattern n-aire W3C SWBP) : Seule représentation possible.
  Raison : Une relation LPG relie exactement deux nœuds.

**Neo4j** — Recommandation `keep_node` — Garder un nœud (pattern n-aire W3C SWBP) : Seule représentation possible.
  Raison : Une relation LPG relie exactement deux nœuds.

**Ce qui se perd** : Rien si le nœud est gardé (seule représentation d'une relation à 3 rôles) ; une arête LPG relie exactement deux nœuds.

**Compensation** : aucune


## Annotations (A) {#annotations-a}

### A01 — Annotations *(Must it. 1)* {#a01-annotations-must-it-1}

- **Construct** : Annotations (rdfs:comment, skos:*, dcterms:*)
- **Détection** : Entité portant des annotations au-delà de rdfs:label.
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:Vehicle`

**Exemple OWL**

```turtle
ex:Vehicle a owl:Class ; rdfs:comment "Véhicule motorisé"@fr ; skos:definition "Moyen de transport" .
```

**Curiosity** — Recommandation `schema_metadata` — Métadonnées du schéma : Commentaires de documentation du code / schéma généré.
  Raison : Documentation conservée avec le schéma.

**Neo4j** — Recommandation `schema_metadata` — Métadonnées du schéma : Commentaires de documentation du code / schéma généré.
  Raison : Documentation conservée avec le schéma.

**Ce qui se perd** : Le commentaire est conservé comme documentation du schéma généré ; il n'existe pas comme donnée.

**Compensation** : Documentation (rapport de transposition)

### A02 — Annotation d'axiome {#a02-annotation-d-axiome}

- **Construct** : Annotations d'axiome (owl:Axiom)
- **Détection** : Réification d'axiome annotée.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:Vehicle`

**Exemple OWL**

```turtle
ex:Car a owl:Class . ex:Vehicle a owl:Class .
[ a owl:Axiom ; owl:annotatedSource ex:Car ; owl:annotatedProperty rdfs:subClassOf ;
  owl:annotatedTarget ex:Vehicle ; rdfs:comment "Source : norme X" ] .
```

**Curiosity** — Recommandation `report` — Lister au rapport : Information conservée dans le rapport de transposition uniquement.
  Raison : Les méta-données d'axiome n'ont pas d'équivalent de schéma.

**Neo4j** — Recommandation `report` — Lister au rapport : Information conservée dans le rapport de transposition uniquement.
  Raison : Les méta-données d'axiome n'ont pas d'équivalent de schéma.
  Autres options : `provenance_property` (Propriété de provenance).

**Ce qui se perd** : L'annotation d'axiome n'a pas d'équivalent de schéma : conservée au rapport (ou en propriété de provenance Neo4j).

**Compensation** : Documentation (rapport de transposition)

### A03 — Entité dépréciée {#a03-entite-depreciee}

- **Construct** : owl:deprecated true
- **Détection** : Entité dépréciée.
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:ServiceBooklet`

**Exemple OWL**

```turtle
ex:ServiceBooklet a owl:Class ; owl:deprecated true .
```

**Curiosity** — Recommandation `exclude` — Exclure : Non générée.
  Raison : Une entité dépréciée ne doit pas entrer dans un nouveau schéma.
  Autres options : `flag_deprecated` (Garder avec drapeau).

**Neo4j** — Recommandation `exclude` — Exclure : Non générée.
  Raison : Une entité dépréciée ne doit pas entrer dans un nouveau schéma.
  Autres options : `flag_deprecated` (Garder avec drapeau).

**Ce qui se perd** : L'entité dépréciée n'est pas générée (ou marquée) : volontaire.

**Compensation** : aucune


## meta {#meta}

### M01 — Métadonnées d'ontologie {#m01-metadonnees-d-ontologie}

- **Construct** : En-tête d'ontologie
- **Détection** : owl:Ontology (IRI, versionIRI, versionInfo, dcterms).
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `https://w3id.org/ontoforge/automaint`

**Exemple OWL**

```turtle
<http://example.org/doc> a owl:Ontology ; owl:versionInfo "1.0" ; dcterms:title "Doc" .
```

**Curiosity** — Recommandation `schema_metadata` — En-tête du schéma généré : Nom, version, IRI d'origine.
  Raison : Traçabilité.

**Neo4j** — Recommandation `schema_metadata` — En-tête du schéma généré : Nom, version, IRI d'origine.
  Raison : Traçabilité.

**Ce qui se perd** : Rien de perdu : nom, version et IRI d'origine sont reportés en métadonnées.

**Compensation** : Documentation (rapport de transposition)

### M02 — Import d'ontologie {#m02-import-d-ontologie}

- **Construct** : owl:imports
- **Détection** : Import déclaré.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `https://w3id.org/ontoforge/automaint`

**Exemple OWL**

```turtle
<http://example.org/doc> a owl:Ontology ; owl:imports <http://www.w3.org/ns/prov-o#> .
```

**Curiosity** — Recommandation `external_reference` — Références externes : Termes importés non chargés : référencés par IRI, constat.
  Raison : Outil hors-ligne : la fermeture d'import n'est pas résolue.
  Autres options : `load_closure_offline` (Charger la fermeture (cache hors-ligne)).

**Neo4j** — Recommandation `external_reference` — Références externes : Termes importés non chargés : référencés par IRI, constat.
  Raison : Outil hors-ligne : la fermeture d'import n'est pas résolue.
  Autres options : `load_closure_offline` (Charger la fermeture (cache hors-ligne)).

**Ce qui se perd** : L'outil est hors ligne : la fermeture d'imports n'est pas chargée, les termes importés restent référencés par IRI.

**Compensation** : Arbitrage humain (aucune compensation automatique)


## Général (G) {#general-g}

### G01 — Construct non transposé {#g01-construct-non-transpose}

- **Construct** : Construct non représentable (OntoModel.unmapped)
- **Détection** : Triplets non consommés par une règle.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:tech_leroy`

**Exemple OWL**

```turtle
ex:Technician a owl:Class .
ex:tech_leroy a ex:Technician ;
    ex:certifiedFor [ a owl:Class ; owl:oneOf ( ex:hybrid ex:electric ) ] .
```

**Curiosity** — Recommandation `report` — Lister au rapport : Information conservée dans le rapport de transposition uniquement.
  Raison : Aucune perte silencieuse : tout ce qui n'est pas transposé est listé.

**Neo4j** — Recommandation `report` — Lister au rapport : Information conservée dans le rapport de transposition uniquement.
  Raison : Aucune perte silencieuse : tout ce qui n'est pas transposé est listé.

**Ce qui se perd** : Tout ce qui n'est pas transposé est listé au rapport : aucune perte silencieuse, mais l'information n'est pas exploitable.

**Compensation** : Documentation (rapport de transposition)


## Individus (I) {#individus-i}

### I01 — Individu {#i01-individu}

- **Construct** : Individu nommé
- **Détection** : Individu déclaré dans l'ontologie.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `—`

**Exemple OWL**

```turtle
ex:FuelType a owl:Class .
ex:Petrol a ex:FuelType .   # individu nommé
```

**Curiosity** — Recommandation `reference_nodes` — Nœud de référence : Ingéré comme donnée de référence (facettes).
  Raison : Membres d'énumérations et référentiels → nœuds ; autres individus : données d'exemple.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `reference_nodes` — Nœud de référence : Ingéré comme donnée de référence (facettes).
  Raison : Membres d'énumérations et référentiels → nœuds ; autres individus : données d'exemple.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Données de référence ingérées comme nœuds (facettes) ou ignorées (données d'exemple).

**Compensation** : Arbitrage humain (aucune compensation automatique)

### I02 — Identité (sameAs) {#i02-identite-sameas}

- **Construct** : owl:sameAs
- **Détection** : Individus identiques.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:garage_TLN01`

**Exemple OWL**

```turtle
ex:garage_TLN01 owl:sameAs ex:garage_toulon_01 .
```

**Curiosity** — Recommandation `merge_nodes` — Fusion des nœuds : Clé canonique + alias.
  Raison : Pas d'UNA en OWL ; le LPG suppose l'UNA : fusion explicite.
  Autres options : `same_as_edge` (Relation SAME_AS).

**Neo4j** — Recommandation `merge_nodes` — Fusion des nœuds : Clé canonique + alias.
  Raison : Pas d'UNA en OWL ; le LPG suppose l'UNA : fusion explicite.
  Autres options : `same_as_edge` (Relation SAME_AS).

**Ce qui se perd** : Le LPG suppose l'UNA : fusion explicite (clé canonique + alias) ou deux nœuds reliés ; la substitution d'identité n'est plus automatique.

**Compensation** : Matérialisation (propriété ou arête dérivée recalculée après ingestion)

### I03 — Différence d'individus {#i03-difference-d-individus}

- **Construct** : owl:differentFrom / owl:AllDifferent
- **Détection** : Assertions de différence.
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:Petrol`

**Exemple OWL**

```turtle
ex:Petrol owl:differentFrom ex:Diesel .
```

**Curiosity** — Recommandation `noop_una` — Aucun effet (UNA) : Le LPG suppose l'UNA partout (renforcement).
  Raison : Déjà garanti par des clés distinctes.

**Neo4j** — Recommandation `noop_una` — Aucun effet (UNA) : Le LPG suppose l'UNA partout (renforcement).
  Raison : Déjà garanti par des clés distinctes.

**Ce qui se perd** : Rien : l'UNA est déjà garantie par des clés distinctes (renforcement).

**Compensation** : aucune

### I04 — Assertion négative {#i04-assertion-negative}

- **Construct** : owl:NegativePropertyAssertion
- **Détection** : Assertion négative.
- **Sévérité** : lost (perte certaine sans compensation)
- **Exemple dans trap** : `am:veh_002`

**Exemple OWL**

```turtle
[ a owl:NegativePropertyAssertion ; owl:sourceIndividual ex:veh_002 ;
  owl:assertionProperty ex:hasOwner ; owl:targetIndividual ex:bob ] .
```

**Curiosity** — Recommandation `validation` — Validation (relation / valeur interdite) : Contrôle applicatif.
  Raison : Pas de fait négatif en LPG (monde clos : l'absence suffit, l'interdiction se valide).
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `validation` — Validation (relation / valeur interdite) : Contrôle applicatif.
  Raison : Pas de fait négatif en LPG (monde clos : l'absence suffit, l'interdiction se valide).
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Pas de fait négatif en LPG (l'absence suffit) : l'interdiction ne peut qu'être validée.

**Compensation** : Validation (contrôle à l'ingestion ou requête de détection)

### I05 — Individu multi-typé {#i05-individu-multi-type}

- **Construct** : Individu à plusieurs types
- **Détection** : Types non reliés par subsomption.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `am:veh_001`

**Exemple OWL**

```turtle
ex:Car a owl:Class . ex:Taxi a owl:Class .
ex:veh_001 a ex:Car, ex:Taxi .   # types non reliés par subsomption
```

**Curiosity** — Recommandation `primary_parent_discriminator` — Type principal + discriminant : Un type porte le nœud ; les autres en discriminants.
  Raison : Mono-type Curiosity.
  Autres options : `multi_label` (Multi-labels).

**Neo4j** — Recommandation `multi_label` — Multi-labels : Tous les types en labels.
  Raison : Mono-type Curiosity.
  Autres options : `primary_parent_discriminator` (Type principal + discriminant).

**Ce qui se perd** : Curiosity mono-type : un type porte le nœud, l'autre appartenance devient un discriminant.

**Compensation** : Arbitrage humain (aucune compensation automatique)


## Nommage (N) {#nommage-n}

### N01 — Nommage *(Must it. 1)* {#n01-nommage-must-it-1}

- **Construct** : Conventions de nommage / collisions
- **Détection** : Nom hors convention (snake_case, tiret…) ou collision après normalisation (insensible à la casse).
- **Sévérité** : auto (appliquée directement)
- **Exemple dans trap** : `am:dtc_code`

**Exemple OWL**

```turtle
ex:Diagnostic a owl:Class .
ex:dtc_code a owl:DatatypeProperty ; rdfs:domain ex:Diagnostic ; rdfs:range xsd:string .
```

**Curiosity** — Recommandation `rename` — Renommer : Nom normalisé (Curiosity : PascalCase ; Neo4j : PascalCase / UPPER_SNAKE / camelCase) ; collision → préfixe `has`.
  Raison : Conventions de la cible ; noms uniques exigés.
  Autres options : `ignore` (Garder le nom).

**Neo4j** — Recommandation `rename` — Renommer : Nom normalisé (Curiosity : PascalCase ; Neo4j : PascalCase / UPPER_SNAKE / camelCase) ; collision → préfixe `has`.
  Raison : Conventions de la cible ; noms uniques exigés.
  Autres options : `ignore` (Garder le nom).

**Ce qui se perd** : Le nom est normalisé (`dtcCode` / `DtcCode`) ; en cas de collision après normalisation, préfixe `has`. L'IRI d'origine reste en `source`.

**Compensation** : Renommage


## SHACL (S, outillage) {#shacl-s-outillage}

### S01 — Conflit OWL / SHACL {#s01-conflit-owl-shacl}

- **Construct** : Conflit OWL / SHACL
- **Détection** : Contrainte SHACL incompatible avec l'axiome OWL (cardinalité, type).
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `—`

**Exemple**

```turtle
# shapes (Turtle SHACL)
ex:OrderShape a sh:NodeShape ; sh:targetClass ex:RepairOrder ;
    sh:property [ sh:path ex:performedBy ; sh:maxCount 3 ] .
# ontologie : ex:performedBy a owl:FunctionalProperty
```

**Curiosity** — Recommandation `shacl_wins` — Priorité aux shapes : Le schéma suit la shape (contrat de données).
  Raison : Les shapes décrivent le contrat de données ; OWL décrit ce qui est inférable.
  Autres options : `owl_wins` (Priorité à OWL).

**Neo4j** — Recommandation `shacl_wins` — Priorité aux shapes : Le schéma suit la shape (contrat de données).
  Raison : Les shapes décrivent le contrat de données ; OWL décrit ce qui est inférable.
  Autres options : `owl_wins` (Priorité à OWL).

**Ce qui se perd** : L'un des deux contrats est écarté pour ce point : `shacl_wins` suit la shape, `owl_wins` l'ignore.

**Compensation** : Arbitrage humain (aucune compensation automatique)

### S02 — Propriété issue des shapes {#s02-propriete-issue-des-shapes}

- **Construct** : Propriété SHACL non déclarée en OWL
- **Détection** : Chemin de shape absent de l'ontologie.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `—`

**Exemple**

```turtle
# shapes (Turtle SHACL)
ex:OrderShape a sh:NodeShape ; sh:targetClass ex:RepairOrder ;
    sh:property [ sh:path ex:priority ; sh:datatype xsd:integer ] .
# ex:priority n'est déclarée nulle part dans l'ontologie
```

**Curiosity** — Recommandation `property` — Ajouter la propriété : Créée depuis la shape (type sh:datatype).
  Raison : Les shapes complètent le schéma.
  Autres options : `ignore` (Ignorer).

**Neo4j** — Recommandation `property` — Ajouter la propriété : Créée depuis la shape (type sh:datatype).
  Raison : Les shapes complètent le schéma.
  Autres options : `ignore` (Ignorer).

**Ce qui se perd** : Rien si on crée la propriété depuis la shape (typée par `sh:datatype`) ; sinon elle est ignorée.

**Compensation** : aucune


## Général (G) {#general-g-2}

### G02 — Décision ignorée {#g02-decision-ignoree}

- **Construct** : Décision invalide
- **Détection** : Option inconnue pour le constat visé.
- **Sévérité** : review (à arbitrer)
- **Exemple dans trap** : `—`

**Exemple**

```json
{ "C07:https://example.org/doc#Customer": "option_inconnue" }
```

**Curiosity** — Recommandation `report` — Lister au rapport : Information conservée dans le rapport de transposition uniquement.
  Raison : La recommandation est appliquée à la place.

**Neo4j** — Recommandation `report` — Lister au rapport : Information conservée dans le rapport de transposition uniquement.
  Raison : La recommandation est appliquée à la place.

**Ce qui se perd** : La décision est ignorée, la recommandation s'applique à la place, et G02 le signale.

**Compensation** : Arbitrage humain (aucune compensation automatique)


## Recommandations surchargées par constat {#recommandations-surchargees-par-constat}

| Règle | Condition | Recommandation |
|---|---|---|
| C09 | union en super-classe (axiome de couverture) plutôt qu'en équivalence | `doc_only` (deux cibles) |
| K03 | instances anonymes (nœuds blancs) | `generated_key` |
| D04 | plusieurs valeurs observées pour un même individu | `list_property` |
| D05 | xsd:hexBinary / base64Binary | `string_lexical` |
| D12 | plusieurs domaines (et non portées) | `intersection_domain` |
| O13 | réflexivité seule | `ignore` (ne jamais matérialiser les boucles) |
| O21 | l'un des domaines subsume l'autre | `most_specific_type` |
| I01 | individu hors énumération / référentiel (donnée d'exemple) | `ignore` |

## Pièges sémantiques couverts (oracle `must_not`) {#pieges-semantiques-couverts-oracle-mustnot}

1. `owl:hasKey` n'impose ni existence ni unicité (Structural Specification §9.5) : K02 n'est jamais `auto`, NODE KEY / `[Key]` sont des renforcements.
2. Deux `rdfs:domain` (ou `rdfs:range`) = **intersection** (rdfs2/rdfs3) : D12 / O21, jamais D03 / O03 (qui exigent une `owl:unionOf` explicite).
3. Réification à 3 rôles ou plus = relation n-aire : R02 (nœud conservé), jamais R01.
4. Propriété non simple (transitive, chaîne, ou leurs super-propriétés / inverses) : aucune cardinalité (O09/O10/O16) n'est générée.
5. Un nœud blanc n'a pas d'IRI : K04 (clé générée), jamais K01.
