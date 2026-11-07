# Catalogue normatif des règles de transposition OWL 2 / SHACL → property graph

Propriétaire : lead (L3). Source unique : `backend/ontoforge/mapping/rules/catalog.py` (ce fichier en est le rendu ; toute modification passe par le catalogue). Base : ARCHITECTURE §4 corrigé par `journal/L0/review-w3c-catalogue.md` (D-031, D-031bis : 36 + 30 = **66 règles de transposition**, sévérités K02 et C05 en `review`). Règles de conformité W01–W07 : L2 (`conformance/`). Outillage ajouté par le moteur : S01, S02 (SHACL), G02 (décision invalide).

## Conventions

- **Sévérité** : `auto` transposition triviale appliquée directement ; `review` perte possible, à arbitrer ; `lost` pas d'équivalent natif, perte certaine sans compensation.
- **Options** : identifiants du vocabulaire normatif de `samples/trap/expected-findings.yaml` (D-031). Une option marquée *(cible)* n'est proposée que pour cette cible ; une décision vers une option absente est ignorée (constat G02).
- **Recommandation** : option appliquée tant que l'humain n'a pas arbitré (`Finding.recommended`). Elle peut être surchargée par constat (ex. K03 → `generated_key` si les instances sont des nœuds blancs).
- **Id de constat** (D-035) : `<règle>:<IRI sujet>` ; suffixe `:<IRI propriété>` pour les restrictions (O09–O17, D13, I04, S01, S02) ; suffixe `:<sha1(forme canonique)[:8]>` pour un construct anonyme (K04, A02, C13, G01, I03 AllDifferent) ; suffixe `:<IRI import>` pour M02, `:domain` / `:range` pour D12 / O21.
- **Compensation** : ce que le moteur génère quand l'option la prévoit — `Validation` (contrôle applicatif / requête de détection), `Materialization` (fermeture, chaîne, classification, sameAs), propriété dérivée, documentation.
- **Hypothèse de monde clos** : OWL infère (OWA, sans UNA) ; le LPG contraint (monde clos, UNA). Transposer un axiome en contrainte est un renforcement, rappelé une fois dans le rapport.

## Pipeline du moteur (`mapping/engine.py`)

1. **Détection** : chaque règle `detect(ctx) -> list[Finding]` (pure). Les constructs que l'import n'a pas structurés (`OntoModel.unmapped`) sont relus en graphe ; chaque nœud blanc expliqué est *consommé* ; les restes → G01.
2. **Décisions** : `decisions[id]` si l'option existe pour la cible, sinon recommandation + G02.
3. **Plan** (phase 10) : disposition des classes (own / fold / merged / abstract_label / alias / computed / union / dereified / excluded), inverses, alias de propriétés, renommages.
4. **Construction** : types de nœuds (discriminants, labels) → propriétés → clés (`uri` source `urn:ontoforge:iri` sur chaque type, clé par défaut) → relations → compensations (validations, matérialisations) → SHACL → contrôle final (noms uniques, N01).
5. **Invariants** : aucune relation vers un type inexistant ; Curiosity : un label, aucune propriété d'arête, `reverse` toujours renseigné, aucun nom d'arête égal à un nom de type ; Neo4j : multi-labels (ancêtres), propriétés de relation (R01). Sortie triée, déterministe.

### SHACL

Les shapes (via `shacl/shacl_to_pg.shape_constraints`) enrichissent le modèle : `sh:minCount ≥ 1` → propriété obligatoire + validation d'existence ; `sh:maxCount 1` → scalaire ; `sh:in` → enum ; `sh:pattern` → motif ; `sh:datatype` → contrôle de type ; `sh:class` / `sh:or` / qualifiées → validation de cible ; `sh:lessThan` → validation ; `sh:closed` → validation « forme fermée » (à valider sans inférence, piège D11) ; chemin inverse → cardinalité entrante. Conflit avec OWL (maxCount > 1 sur une propriété fonctionnelle, datatype incompatible, motif différent, sh:class disjointe de la portée) → **S01** ; propriété de shape non déclarée → **S02**.

## Catalogue

### Classes (C)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **C01** ¹ | owl:Class nommée | Toute classe nommée déclarée. | auto | `node_type` *(curiosity)* : Un type de nœud [Node] (classe C#).<br>`label` *(neo4j)* : Un label PascalCase. | `node_type` | `label` | aucune |
| **C02** ¹ | rdfs:subClassOf (parent nommé unique) | **Une décision par racine concrète de hiérarchie** (sujet = racine, `related` = sous-classes à parent unique). | review | `multi_label` : Neo4j : le nœud porte son label et ceux de ses ancêtres (requêtes sur le parent naturelles). Curiosity : pas de multi-type, repli en liste de types `types` (propriété multivaluée) dans le type concret.<br>`flatten_into_leaves` : Le sous-type est replié dans le type de nœud concret le plus proche (propriétés recopiées) avec un discriminant `<racine>Kind` ; les requêtes par sous-type filtrent sur le discriminant.<br>`node_type` : Le sous-type garde son propre type de nœud, propriétés du parent recopiées ; les relations du parent sont dupliquées vers lui (Curiosity). | `flatten_into_leaves` | `multi_label` | aucune |
| **C03** ¹ | Héritage multiple | Classe ayant au moins deux parents nommés effectifs. | review | `multi_label` : Tous les parents deviennent des labels (Neo4j) ; Curiosity : liste de types.<br>`primary_parent_discriminator` : Un parent principal porte le type ; les autres appartenances deviennent des booléens `is<Parent>`.<br>`node_type` : Type propre, propriétés de tous les parents recopiées. | `primary_parent_discriminator` | `multi_label` | arbitrage humain |
| **C04** ¹ | Classe probablement abstraite | Heuristique OWA : classe avec sous-classes, sans instance directe, sans clé, impliquée dans au plus une propriété objet, hors disjointUnion (C10). | review | `merge_into_leaves` : Pas de type de nœud : ses propriétés et relations sont recopiées dans chaque sous-type concret.<br>`secondary_label` *(neo4j)* : Type abstrait : le label est porté par les nœuds des sous-classes, jamais seul.<br>`node_type` : Type concret ; les sous-types s'y replient (Curiosity). | `merge_into_leaves` | `secondary_label` | requête |
| **C05** ¹ | owl:equivalentClass entre classes nommées | equivalentClass dont l'argument est nommé. | review | `merge_types` : Un seul type ; l'autre IRI devient un alias documenté (même extension : sans perte).<br>`node_type` : Duplication des nœuds et des clés : à synchroniser. | `merge_types` | `merge_types` | documentation |
| **C06** | Classe définie (equivalentClass anonyme : restriction / intersection) | Classe nommée avec une définition nécessaire et suffisante. | lost | `computed_label` : Job de classification (requête) rejoué après chaque ingestion.<br>`materialize_at_ingest` : Booléen `is<Classe>` calculé par le connecteur.<br>`doc_only` : Rien n'est généré : la sémantique est perdue pour les données, tracée au rapport. | `materialize_at_ingest` | `computed_label` | matérialisation |
| **C07** ¹ | owl:disjointWith / owl:AllDisjointClasses | Classe déclarant des disjonctions. | lost | `validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `validation` | `validation` | validation |
| **C08** | owl:oneOf (classe énumérée) | Classe dont la définition est une énumération d'individus. | review | `reference_nodes` : Un type, un nœud par valeur, relié par une relation : facettes liées, renommage sans dénormalisation.<br>`enum_property` : Propriété texte + validation des valeurs ; la relation disparaît. | `reference_nodes` | `reference_nodes` | validation |
| **C09** | owl:unionOf / owl:intersectionOf anonymes | Union/intersection anonyme en équivalence ou en super-classe (hors définitions C06). | lost | `doc_only` : Rien n'est généré : la sémantique est perdue pour les données, tracée au rapport.<br>`secondary_label` *(neo4j)* : Le nom de l'union devient un label porté par les nœuds des classes membres. | `doc_only` | `secondary_label` | documentation |
| **C10** | owl:disjointUnionOf | Classe partitionnée en sous-classes disjointes. | review | `primary_parent_discriminator` : Un type de nœud parent + enum `<parent>Kind` obligatoire (exactement une valeur).<br>`multi_label` : Labels parent et enfants + validation « exactement un label enfant ».<br>`validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | `primary_parent_discriminator` | `multi_label` | validation |
| **C11** | owl:complementOf | Complément dans une définition ou une super-classe. | lost | `computed_label` : Classification par absence de label/propriété : monde clos, à rejouer.<br>`materialize_at_ingest` : Booléen calculé par le connecteur.<br>`doc_only` : Rien n'est généré : la sémantique est perdue pour les données, tracée au rapport. | `materialize_at_ingest` | `computed_label` | matérialisation |
| **C12** | Punning classe / individu (SS §5.9) | Même IRI déclarée classe et individu. | review | `reference_nodes` : Le type de nœud (classe) et le nœud de référence (individu) coexistent sous des noms distincts.<br>`ignore` : L'usage individu est perdu. | `reference_nodes` | `reference_nodes` | documentation |
| **C13** | Axiome général d'inclusion (GCI) | rdfs:subClassOf dont le sujet est anonyme. | lost | `computed_label` : Requête qui pose le label conclu.<br>`materialize_at_ingest` : Booléen calculé par le connecteur.<br>`doc_only` : Rien n'est généré : la sémantique est perdue pour les données, tracée au rapport. | `materialize_at_ingest` | `computed_label` | matérialisation |

### Identité et clés (K)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **K01** ¹ | Identité IRI d'un individu nommé | Individu nommé (IRI). | auto | `uri_key` *(curiosity)* : [Key] string = IRI (Curiosity).<br>`unique_constraint` *(neo4j)* : Identité RDF conservée, MERGE idempotent. | `uri_key` | `unique_constraint` | aucune |
| **K02** ¹ | owl:hasKey sur propriétés de données | Axiome HasKey ne portant que des propriétés de données. | review | `node_key` : Neo4j : NODE KEY (existence + unicité, Enterprise ; UNIQUE en Community). Curiosity : [Key] = la propriété. RENFORCEMENT : hasKey n'impose ni existence ni unicité.<br>`unique_constraint` *(neo4j)* : Unicité sans existence obligatoire.<br>`uri_key` : La clé reste l'IRI ; l'unicité des valeurs hasKey devient une validation applicative.<br>`key_concat` *(curiosity)* : Clé composite concaténée (séparateur '/'). | `uri_key` | `node_key` | validation |
| **K03** ¹ | Classe sans clé métier | Classe concrète sans hasKey (ni ancêtre à clé). | review | `uri_key` : Identifiant technique (IRI).<br>`generated_key` : Hash déterministe des valeurs identifiantes ou IRI skolem `/.well-known/genid/` (instances sans IRI).<br>`property` : Arbitrage humain : la propriété devient la clé. | `uri_key` | `uri_key` | arbitrage humain |
| **K04** | Individu anonyme (nœud blanc, SS §5.6.2) | Valeur objet nœud blanc typé. | review | `generated_key` : hash(propriétaire + propriété + valeurs) ou IRI skolem.<br>`ignore` : L'individu n'est pas ingéré. | `generated_key` | `generated_key` | matérialisation |
| **K05** | owl:hasKey incluant une propriété objet | Axiome HasKey portant au moins une propriété objet. | review | `key_concat` *(curiosity)* : Clé = valeur / clé du nœud cible.<br>`materialize_key` *(neo4j)* : Propriété `<cible>Key` recopiée à l'ingestion puis NODE KEY composite.<br>`uri_key` : Unicité composite seulement validée. | `key_concat` | `materialize_key` | matérialisation |

### Propriétés de données (D)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **D01** ¹ | Propriété de données à domaine nommé unique | Un seul rdfs:domain nommé. | auto | `property` : Propriété typée sur le nœud. | `property` | `property` | aucune |
| **D02** ¹ | Propriété de données sans domaine | Aucun rdfs:domain. | review | `attach_to_users` : Posée sur les types qui l'utilisent (restrictions, shapes, assertions) ; non posée si elle n'est utilisée que via ses sous-propriétés.<br>`ignore` : Propriété non transposée. | `attach_to_users` | `attach_to_users` | arbitrage humain |
| **D03** | Domaine = owl:unionOf (union explicite) | rdfs:domain [owl:unionOf (…)]. | review | `duplicate_per_type` : Même nom sur chaque membre de l'union. | `duplicate_per_type` | `duplicate_per_type` | aucune |
| **D04** ¹ | Propriété de données non fonctionnelle | Ni FunctionalProperty, ni max/exactly 1, ni sh:maxCount 1. | review | `list_property` : Tableau homogène (T[] / LIST<T>).<br>`scalar` : Une seule valeur ; valeurs multiples perdues à l'ingestion. | `scalar` | `scalar` | aucune |
| **D05** ¹ | Typage xsd avec perte | decimal, hexBinary/base64Binary, dateTimeStamp, owl:real/rational, types hors carte OWL 2 (gYear, date, duration… : aussi W01). | review | `native_type` : decimal → flottant (précision), dateTimeStamp → date-heure à fuseau, gYear → entier…<br>`string_lexical` : Exact mais non calculable / non comparable numériquement. | `native_type` | `native_type` | validation |
| **D06** ¹ | Valeurs multilingues (rdf:PlainLiteral, @lang) | Portée rdf:PlainLiteral / rdf:langString (non conforme, W01) ou littéraux à langue observés. | review | `per_language_property` : label_fr, label_en ; langues hors liste perdues.<br>`string_property` : Étiquette de langue perdue. | `per_language_property` | `per_language_property` | aucune |
| **D07** ¹ | owl:FunctionalProperty (données) | Propriété de données fonctionnelle. | auto | `scalar` : Valeur unique (+ contrainte de type si l'édition le permet). | `scalar` | `scalar` | aucune |
| **D08** | DataOneOf (énumération de littéraux) | Portée owl:oneOf de littéraux. | review | `enum_property` : Texte + contrôle des valeurs (pas de contrainte d'énumération native).<br>`reference_nodes` : Une valeur = un nœud ; la propriété devient une relation. | `enum_property` | `enum_property` | validation |
| **D09** | Datatype défini / facettes | rdfs:Datatype défini par owl:withRestrictions (min/max, pattern, length). | review | `validation` : Le type de base natif est utilisé ; bornes et motifs deviennent des validations.<br>`native_type` : Facettes perdues. | `validation` | `validation` | validation |
| **D10** | Portée rdfs:Literal ou absente | Portée non contrainte. | review | `string_property` : Typage d'origine perdu. | `string_property` | `string_property` | aucune |
| **D11** | rdfs:subPropertyOf entre propriétés de données | Sous-propriété de données. | lost | `most_specific_type` : La super-propriété n'est pas stockée : une requête sur le parent doit lister les sous-propriétés.<br>`materialize_closure` : Valeur recopiée dans le parent (double écriture). | `most_specific_type` | `most_specific_type` | matérialisation |
| **D12** | Plusieurs rdfs:domain / rdfs:range (données) = intersection | Au moins deux domaines nommés ou deux portées. | review | `native_type` : Type le plus restrictif + validation des bornes.<br>`intersection_domain` : Posée sur les nœuds appartenant à tous les domaines (souvent erreur de modélisation).<br>`duplicate_per_type` : Écart sémantique (rdfs2) : à n'utiliser que si l'ontologie est fautive. | `native_type` | `native_type` | validation |
| **D13** | Restriction sur propriété de données | some / only / cardinalité / onDataRange. | review | `validation` : exactly 1 / min 1 → propriété obligatoire + contrôle.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `validation` | `validation` | validation |

### Propriétés objet (O)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **O01** ¹ | Propriété objet à domaine et portée nommés uniques | Un domaine et une portée nommés. | auto | `edge_pair` *(curiosity)* : Constante aller + retour, Link(a, b, aller, retour).<br>`relationship` *(neo4j)* : UPPER_SNAKE, un sens stocké. | `edge_pair` | `relationship` | aucune |
| **O02** ¹ | Propriété objet sans domaine ou sans portée | Domaine ou portée absents. | review | `edge_pair` *(curiosity)* : Extrémités déduites des restrictions, shapes, assertions et de l'inverse.<br>`relationship` *(neo4j)* : Extrémités déduites des restrictions, shapes, assertions et de l'inverse.<br>`ignore` : Relation non transposée. | `edge_pair` | `relationship` | arbitrage humain |
| **O03** ¹ | Domaine / portée = owl:unionOf | rdfs:domain ou rdfs:range [owl:unionOf (…)]. | review | `edge_pair` *(curiosity)* : Même nom d'arête pour chaque paire.<br>`relationship` *(neo4j)* : Validation des paires autorisées. | `edge_pair` | `relationship` | validation |
| **O04** ¹ | owl:inverseOf | Paire de propriétés inverses. | auto | `edge_pair` : Curiosity : retour natif gratuit. Neo4j : les deux sens stockés (double écriture).<br>`single_direction` *(neo4j)* : L'autre sens est traversé ; le nom inverse est documenté. | `edge_pair` | `single_direction` | aucune |
| **O05** ¹ | owl:SymmetricProperty | Propriété symétrique. | review | `self_reverse` *(curiosity)* : Même constante dans les deux sens.<br>`undirected_query` *(neo4j)* : MATCH (a)-[:T]-(b) ; sens stocké arbitraire.<br>`edge_pair` : Doublons à l'agrégation. | `self_reverse` | `undirected_query` | aucune |
| **O06** ¹ | owl:TransitiveProperty | Propriété transitive. | lost | `materialize_closure` : Arête dérivée `<nom>Transitive` recalculée après ingestion.<br>`var_length_query` *(neo4j)* : -[:T*1..]-> : compensation complète en lecture, aucune contrainte.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `materialize_closure` | `var_length_query` | matérialisation |
| **O07** ¹ | rdfs:subPropertyOf (objet) | Sous-propriété objet (hors topObjectProperty). | lost | `most_specific_type` : Seule la sous-relation est stockée ; requête parent = union de types.<br>`materialize_closure` : Relation parente dérivée (double écriture). | `most_specific_type` | `most_specific_type` | matérialisation |
| **O08** | owl:propertyChainAxiom | Propriété définie par une chaîne. | lost | `materialize_closure` : Arête dérivée recalculée après ingestion.<br>`path_query` *(neo4j)* : Non stocké ; calculé à la lecture. | `materialize_closure` | `path_query` | matérialisation |
| **O09** ¹ | Fonctionnelle / max 1 / exactly 1 (objet) | FunctionalProperty ou restriction max/exactly ≤ 1. | review | `validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `validation` | `validation` | validation |
| **O10** ¹ | some / min n (objet, non qualifiée) | Restriction d'existence. | review | `validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `validation` | `validation` | validation |
| **O11** | only (allValuesFrom) | Restriction universelle. | lost | `validation` : Contrôle que la cible a le bon type.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `validation` | `validation` | validation |
| **O12** | hasValue | Restriction de valeur. | review | `validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.<br>`materialize_at_ingest` : Relation / valeur créée par le connecteur. | `validation` | `validation` | validation |
| **O13** | Réflexive / irréflexive / asymétrique | Caractéristiques de propriété. | lost | `validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.<br>`ignore` : Rien n'est généré (réflexivité : ne jamais matérialiser les boucles). | `validation` | `validation` | validation |
| **O14** | ObjectInverseOf anonyme | [owl:inverseOf :p] dans une restriction ou une chaîne. | review | `reverse_traversal` : Lecture par le sens retour de la relation.<br>`resolve_named_inverse` : Utiliser l'inverse nommé s'il existe. | `reverse_traversal` | `reverse_traversal` | validation |
| **O15** | owl:InverseFunctionalProperty | Propriété inverse-fonctionnelle. | review | `validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `validation` | `validation` | validation |
| **O16** | Cardinalité qualifiée (onClass) | min/max/exactly avec owl:onClass, propriété simple. | review | `validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `validation` | `validation` | validation |
| **O17** | owl:hasSelf | Restriction ObjectHasSelf. | lost | `materialize_at_ingest` : Booléen calculé à l'ingestion (boucle détectée).<br>`validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | `materialize_at_ingest` | `validation` | matérialisation |
| **O18** | owl:topObjectProperty / topDataProperty en super-propriété | subPropertyOf top. | auto | `ignore` : Aucun effet en LPG. | `ignore` | `ignore` | documentation |
| **O19** | owl:equivalentProperty | Propriétés objet équivalentes. | review | `merge_relationship_types` : Nom canonique + alias documenté.<br>`doc_only` : Deux types de relation pour un même fait : à synchroniser. | `merge_relationship_types` | `merge_relationship_types` | documentation |
| **O20** | owl:propertyDisjointWith / AllDisjointProperties | Propriétés disjointes. | lost | `validation` : La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `validation` | `validation` | validation |
| **O21** | Plusieurs rdfs:domain / rdfs:range (objet) = intersection | Au moins deux domaines ou portées nommés. | review | `intersection_domain` : Relation depuis chaque domaine + validation « appartient à tous » (souvent erreur de modélisation).<br>`most_specific_type` : Si l'une subsume l'autre.<br>`duplicate_per_type` : Écart sémantique : seulement si l'ontologie est fautive. | `intersection_domain` | `intersection_domain` | arbitrage humain |

### Réification (R)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **R01** ¹ | Classe de réification binaire | Exactement 2 rôles objet fonctionnels (ou max/exactly 1) + des propriétés de données, classe non cible d'autres relations. | review | `dereify_relationship` *(neo4j)* : Plus de nœud intermédiaire ; la relation porte les propriétés et ne peut être cible d'autres relations.<br>`keep_node` : Un saut de plus, extensible. | `keep_node` | `dereify_relationship` | aucune |
| **R02** ¹ | Relation n-aire (≥ 3 rôles) | Au moins 3 rôles objet fonctionnels. | review | `keep_node` : Seule représentation possible. | `keep_node` | `keep_node` | aucune |

### Annotations (A)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **A01** ¹ | Annotations (rdfs:comment, skos:*, dcterms:*) | Entité portant des annotations au-delà de rdfs:label. | auto | `schema_metadata` : Commentaires de documentation du code / schéma généré. | `schema_metadata` | `schema_metadata` | documentation |
| **A02** | Annotations d'axiome (owl:Axiom) | Réification d'axiome annotée. | review | `report` : Information conservée dans le rapport de transposition uniquement.<br>`provenance_property` *(neo4j)* : Sur la relation correspondante (Neo4j) ; sinon rapport. | `report` | `report` | documentation |
| **A03** | owl:deprecated true | Entité dépréciée. | auto | `exclude` : Non générée.<br>`flag_deprecated` : Générée, marquée dépréciée. | `exclude` | `exclude` | aucune |

### Métadonnées (M)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **M01** | En-tête d'ontologie | owl:Ontology (IRI, versionIRI, versionInfo, dcterms). | auto | `schema_metadata` : Nom, version, IRI d'origine. | `schema_metadata` | `schema_metadata` | documentation |
| **M02** | owl:imports | Import déclaré. | review | `external_reference` : Termes importés non chargés : référencés par IRI, constat.<br>`load_closure_offline` : Nécessite une copie locale. | `external_reference` | `external_reference` | arbitrage humain |

### Général (G)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **G01** | Construct non représentable (OntoModel.unmapped) | Triplets non consommés par une règle. | lost | `report` : Information conservée dans le rapport de transposition uniquement. | `report` | `report` | documentation |
| **G02** | Décision invalide | Option inconnue pour le constat visé. | review | `report` : Information conservée dans le rapport de transposition uniquement. | `report` | `report` | arbitrage humain |

### Individus (I)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **I01** | Individu nommé | Individu déclaré dans l'ontologie. | review | `reference_nodes` : Ingéré comme donnée de référence (facettes).<br>`ignore` : Donnée d'exemple non ingérée. | `reference_nodes` | `reference_nodes` | arbitrage humain |
| **I02** | owl:sameAs | Individus identiques. | lost | `merge_nodes` : Clé canonique + alias.<br>`same_as_edge` : Deux nœuds reliés ; requêtes à adapter. | `merge_nodes` | `merge_nodes` | matérialisation |
| **I03** | owl:differentFrom / owl:AllDifferent | Assertions de différence. | auto | `noop_una` : Le LPG suppose l'UNA partout (renforcement). | `noop_una` | `noop_una` | aucune |
| **I04** | owl:NegativePropertyAssertion | Assertion négative. | lost | `validation` : Contrôle applicatif.<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `validation` | `validation` | validation |
| **I05** | Individu à plusieurs types | Types non reliés par subsomption. | review | `multi_label` : Tous les types en labels.<br>`primary_parent_discriminator` : Un type porte le nœud ; les autres en discriminants. | `primary_parent_discriminator` | `multi_label` | arbitrage humain |

### Nommage (N)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **N01** ¹ | Conventions de nommage / collisions | Nom hors convention (snake_case, tiret…) ou collision après normalisation (insensible à la casse). | auto | `rename` : Nom normalisé (Curiosity : PascalCase ; Neo4j : PascalCase / UPPER_SNAKE / camelCase) ; collision → préfixe `has`.<br>`ignore` : Collision possible dans le code généré. | `rename` | `rename` | renommage |

### SHACL (S, outillage)

| ID | Construct | Détection | Sév. | Options (impact) | Reco Curiosity | Reco Neo4j | Compensation |
|---|---|---|---|---|---|---|---|
| **S01** | Conflit OWL / SHACL | Contrainte SHACL incompatible avec l'axiome OWL (cardinalité, type). | review | `shacl_wins` : Le schéma suit la shape (contrat de données).<br>`owl_wins` : La shape est ignorée pour ce point. | `shacl_wins` | `shacl_wins` | arbitrage humain |
| **S02** | Propriété SHACL non déclarée en OWL | Chemin de shape absent de l'ontologie. | review | `property` : Créée depuis la shape (type sh:datatype).<br>`ignore` : Aucune génération ni contrôle ; l'axiome est seulement listé au rapport. | `property` | `property` | aucune |

¹ règle Must de l'itération 1 (D-032). Les 66 règles sont implémentées dès l'itération 1 (`journal/L3/ecarts-oracle.md`).

## Justifications par cible (rationale)

- **C01** — Correspondance directe.
- **C02** — Curiosity : Curiosity est mono-type (un nœud = une classe C#) : la hiérarchie s'aplatit, le discriminant reste filtrable et utilisable en facette. · Neo4j : Neo4j porte plusieurs labels par nœud : l'héritage passe sans perte de requêtabilité.
- **C03** — Curiosity : Mono-type : un seul ancêtre peut définir le type de nœud (le plus riche en propriétés). · Neo4j : Aucune limite au nombre de labels.
- **C04** — Sous OWA, l'absence d'instance directe ne se prouve pas : c'est une heuristique à confirmer.
- **C05** — EquivalentClasses(A B) avec A, B nommées : extensions identiques, la fusion ne perd rien.
- **C06** — Aucun raisonneur côté LPG : l'appartenance définie doit être calculée et stockée, ou perdue.
- **C07** — Curiosity : Mono-type : la disjonction est garantie entre types distincts ; à valider si des classes sont fusionnées. · Neo4j : Aucune contrainte native : requête de détection d'un nœud portant les deux labels.
- **C08** — Les valeurs portent des labels multilingues : des nœuds de référence les conservent.
- **C09** — Pas de type anonyme en LPG ; la sémantique ensembliste est perdue sauf label de regroupement.
- **C10** — La partition devient une contrainte de complétude et d'exclusivité, à valider.
- **C11** — Le complément OWL (monde ouvert) devient une négation par défaut (monde clos) : sur-classification possible.
- **C12** — Métamodélisation légale en OWL 2 DL ; en LPG, deux éléments distincts.
- **C13** — Règle d'inférence sans équivalent LPG.
- **K01** — L'IRI est unique, stable et non vide.
- **K02** — Curiosity : [Key] Curiosity doit être non vide pour chaque nœud : poser la clé sur une propriété que l'ontologie ne rend pas obligatoire est un renforcement ; uri reste sûr, la clé métier est validée. · Neo4j : hasKey (SS §9.5) infère sameAs entre individus nommés de mêmes valeurs ; NODE KEY ajoute l'existence obligatoire : renforcement à faire valider.
- **K03** — uri si les instances ont une IRI ; clé générée si elles sont anonymes (nœuds blancs).
- **K04** — Un nœud blanc n'a pas d'IRI : aucune clé n'est dérivable (pas K01).
- **K05** — Une clé LPG ne porte que des propriétés du nœud.
- **D01** — Correspondance directe (le domaine RDFS infère ; il devient ici un contrat de schéma, monde clos).
- **D02** — Une propriété LPG appartient à un type de nœud.
- **D03** — Seule une union explicite autorise la duplication (≠ plusieurs rdfs:domain, D12).
- **D04** — OWA : l'absence de FunctionalProperty ne prouve pas la multivaluation : liste si plusieurs valeurs sont observées, scalaire sinon.
- **D05** — Pas de décimal ni de binaire natifs en LPG.
- **D06** — Pas de littéral à langue en LPG.
- **D07** — Correspondance directe.
- **D08** — Petit ensemble figé de littéraux.
- **D09** — Aucune facette native en LPG.
- **D10** — Type inconnu : texte par défaut.
- **D11** — Pas de hiérarchie de propriétés en LPG.
- **D12** — Plusieurs axiomes de domaine/portée se cumulent (RSEM rdfs2/rdfs3).
- **D13** — Les restrictions OWL infèrent ; en LPG elles deviennent des contrôles (monde clos).
- **O01** — Correspondance directe.
- **O02** — Le connecteur doit savoir quels types relier.
- **O03** — Union explicite seulement (≠ plusieurs rdfs:range : O21).
- **O04** — Un seul fait, deux noms.
- **O05** — Évite deux faits pour une relation symétrique.
- **O06** — Curiosity : Pas de chemin de longueur variable documenté : la fermeture est matérialisée. · Neo4j : Les chemins variables sont natifs en Cypher (compensation complète en lecture seulement).
- **O07** — Pas de hiérarchie de types de relation en LPG.
- **O08** — Aucune inférence côté LPG.
- **O09** — Aucune contrainte de cardinalité de relation en LPG.
- **O10** — OWA : some n'oblige pas à connaître la valeur ; en LPG c'est un contrôle de complétude.
- **O11** — only infère le type de la cible (OWA) ; ≠ sh:class qui le vérifie.
- **O12** — Pas de valeur par défaut dans un schéma LPG.
- **O13** — Aucune contrainte native ; la réflexivité globale est souvent une erreur.
- **O14** — Pas d'inverse anonyme en LPG, mais toute relation se traverse dans les deux sens.
- **O15** — Au plus une relation entrante par cible : contrôle applicatif.
- **O16** — Validation filtrée par type de la cible.
- **O17** — Une boucle n'est pas un concept de schéma LPG.
- **O18** — La propriété universelle relie tout à tout : sans contenu transposable.
- **O19** — Même extension : fusion sans perte.
- **O20** — Deux relations ne peuvent relier la même paire : contrôle applicatif.
- **O21** — rdfs2/rdfs3 : le sujet est instance des DEUX classes ; à arbitrer.
- **R01** — Curiosity : Les arêtes Curiosity ne portent pas de propriétés : dé-réifier perdrait les attributs. · Neo4j : Neo4j : les relations portent des propriétés, la réification binaire se dé-réifie.
- **R02** — Une relation LPG relie exactement deux nœuds.
- **A01** — Documentation conservée avec le schéma.
- **A02** — Les méta-données d'axiome n'ont pas d'équivalent de schéma.
- **A03** — Une entité dépréciée ne doit pas entrer dans un nouveau schéma.
- **M01** — Traçabilité.
- **M02** — Outil hors-ligne : la fermeture d'import n'est pas résolue.
- **G01** — Aucune perte silencieuse : tout ce qui n'est pas transposé est listé.
- **I01** — Membres d'énumérations et référentiels → nœuds ; autres individus : données d'exemple.
- **I02** — Pas d'UNA en OWL ; le LPG suppose l'UNA : fusion explicite.
- **I03** — Déjà garanti par des clés distinctes.
- **I04** — Pas de fait négatif en LPG (monde clos : l'absence suffit, l'interdiction se valide).
- **I05** — Mono-type Curiosity.
- **N01** — Conventions de la cible ; noms uniques exigés.
- **S01** — Les shapes décrivent le contrat de données ; OWL décrit ce qui est inférable.
- **S02** — Les shapes complètent le schéma.
- **G02** — La recommandation est appliquée à la place.

## Recommandations surchargées par constat

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

## Pièges sémantiques couverts (oracle `must_not`)

- `owl:hasKey` n'impose ni existence ni unicité (SS §9.5) : K02 n'est jamais `auto`, NODE KEY / [Key] = renforcement.
- Deux `rdfs:domain` (ou `rdfs:range`) = **intersection** (RSEM rdfs2/rdfs3) → O21 / D12, jamais O03 / D03.
- Réification à ≥ 3 rôles = relation n-aire → R02 (nœud), jamais R01.
- Propriété non simple (transitive, chaîne, ou leurs super-propriétés / inverses, SS §11.2) : aucune cardinalité (O09/O10/O16) n'est générée.
- Un nœud blanc n'a pas d'IRI : K04 (clé générée), jamais K01.

## Itération 2 (revue w3c it1) — règles de construction ajoutées

- **Chaînes** (O08) : `owl:propertyChainAxiom` est une inclusion ordonnée `p ∘ q ⊑ r` (SS §9.2.1). L'ordre et les
  répétitions sont conservés (`related` n'est jamais trié pour une séquence) ; `r` reste une relation stockée dans les
  deux cibles (assertions directes), la matérialisation (Curiosity) ou la requête de chemin (Neo4j) la complète.
- **Domaine / portée complexes** : `domain(A ⊓ B)` ⊨ `domain(A)` ∧ `domain(B)` → rattachement à chaque conjoint nommé +
  D12 / O21 ; toute autre expression → **G01** explicite (rattachée aux conjoints nommés éventuels). Jamais de perte
  silencieuse.
- **Héritage aplati** : une restriction, une shape ou un hasKey porté par une sous-classe repliée ne rend rien
  obligatoire et ne change ni la cardinalité d'arête ni la clé de la racine ; la validation porte
  `params.discriminator` + `params.values` (sous-classe et descendantes). Les extrémités d'arête issues d'une
  sous-classe repliée reçoivent une validation `EP:<propriété>:<from|to>:<type>`.
- **Cardinalités** : `some` / `min n` → `0..* ⇒ 1..*`, `0..1 ⇒ 1` ; jamais « exactement 1 » sans `max`.
- **Bruit d'arbitrage** : D13 `max 1` seul → `auto` ; K03 avec clé IRI → `auto` (review seulement si clé générée) ;
  C07 en Curiosity → `auto` quand la disjonction est garantie par construction (types distincts ou discriminant
  scalaire) ; décision groupée `"<règle>:*": option` (ex. `D13:*`, `O09:*`) appliquée à tous les constats de la règle
  sans décision individuelle.
- **Nœuds de référence** : propriétés `label_<lang>` ajoutées (libellés des individus conservés).
