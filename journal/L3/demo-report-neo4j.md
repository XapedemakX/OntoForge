# Rapport de transposition — AutoMaint — ontologie de maintenance automobile → Neo4j

Ontologie source : `https://w3id.org/ontoforge/automaint` · cible : **Neo4j** · OntoForge 0.1.0

## Synthèse

| Indicateur | Valeur |
|---|---|
| Constats | 166 |
| Transposés automatiquement (auto) | 114 |
| À arbitrer (review) | 48 |
| Perdus sans compensation native (lost) | 4 |
| Arbitrés / non arbitrés (review + lost) | 0 / 52 |
| Types de nœuds / relations | 24 / 23 |
| Validations à implémenter / matérialisations | 80 / 0 |

> **Hypothèse de monde clos.** OWL raisonne en monde ouvert, sans hypothèse du nom unique : un axiome y *infère* des faits (domaine, portée, restrictions, clés). Le schéma property graph est un *contrat d'ingestion* en monde clos : ces axiomes deviennent ici des contraintes ou des validations, ce qui est un renforcement (ce qui manque est une erreur, deux clés différentes sont deux nœuds). Ce rappel vaut pour tout le rapport.

**52 constat(s) non arbitré(s)** : la recommandation pour Neo4j a été appliquée (marquée « non arbitré »).

## Types de nœuds

| Type | Labels | Clé | Propriétés | Classes OWL sources |
|---|---|---|---|---|
| Brand | Brand, Organization, Party | brandName | uri*: String, brandName*: String | am:Brand |
| CombustionVehicle | CombustionVehicle, Vehicle | vin | uri*: String | am:CombustionVehicle |
| Customer | Customer, Person, Party | uri | uri*: String | am:Customer |
| DiagnosticTroubleCode | DiagnosticTroubleCode | dtcCode | uri*: String, dtcCode*: String | am:DiagnosticTroubleCode |
| ElectricMotor | ElectricMotor, Engine | uri | uri*: String | am:ElectricMotor |
| ElectricVehicle | ElectricVehicle, Vehicle | vin | uri*: String | am:ElectricVehicle |
| Engine | Engine | uri | uri*: String, displacementCc: Integer, powerKw: Float | am:Engine |
| FuelType | FuelType | uri | uri*: String, label_en: String, label_fr: String | am:FuelType |
| Garage | Garage, Organization, Party | uri | uri*: String | am:Garage |
| InternalCombustionEngine | InternalCombustionEngine, Engine | uri | uri*: String | am:InternalCombustionEngine |
| MaintenancePlan | MaintenancePlan | uri | uri*: String, intervalKm: Integer, intervalMonths: Integer | am:MaintenancePlan |
| MileageReading | MileageReading | uri | uri*: String, readingDate*: DateTime, readingMileageKm*: Float | am:MileageReading |
| Organization *(abstrait)* | Organization, Party | uri | uri*: String | am:Organization |
| Part | Part | uri | uri*: String | am:Part |
| PartReference | PartReference | uri | uri*: String, manufacturerPartNumber*: String, unitPrice: Float | am:PartReference |
| Party | Party | uri | uri*: String, displayName*: String | am:Party |
| Person *(abstrait)* | Person, Party | uri | uri*: String | am:Person |
| Recall | Recall | recallNumber | uri*: String, issuedAt: DateTime, recallNumber*: String | am:Recall |
| RepairOrder | RepairOrder | orderNumber | uri*: String, closedAt: DateTime, openedAt*: DateTime, orderNumber*: String | am:RepairOrder |
| ServiceOperation | ServiceOperation | operationCode | uri*: String, operationCode*: String, standardDurationMin: Integer | am:ServiceOperation |
| Technician | Technician, Person, Party | uri | uri*: String | am:Technician |
| Vehicle | Vehicle | vin | uri*: String, firstRegistrationDate: DateTime, registrationNumber: String, vin*: String | am:Vehicle |
| VehicleModel | VehicleModel | uri | uri*: String, modelName*: String, modelYear: Integer | am:VehicleModel |
| Warranty | Warranty | uri | uri*: String, warrantyDurationMonths*: Integer, warrantyMaxKm: Integer | am:Warranty |

`*` obligatoire · `[]` liste.

## Relations

| Relation | De | Vers | Retour | Cardinalité (sortie / entrée) | Propriétés | Source | Note |
|---|---|---|---|---|---|---|---|
| ADDRESSES | ServiceOperation | DiagnosticTroubleCode | — | 0..* / 0..* | — | am:addresses |  |
| APPLIES_TO_MODEL | Recall | VehicleModel | — | 1..* / 0..* | — | am:appliesToModel |  |
| ASSIGNED_TO | RepairOrder | Technician | — | 0..* / 0..* | — | am:assignedTo |  |
| CONCERNS | RepairOrder | Vehicle | — | 1 / 0..* | — | am:concerns |  |
| CONCERNS_PART | Recall | PartReference | — | 0..* / 0..* | — | am:concernsPart |  |
| COVERS | Warranty | Vehicle | — | 1 / 0..* | — | am:covers |  |
| HAS_ACTIVE_CODE | Vehicle | DiagnosticTroubleCode | — | 0..* / 0..* | — | am:hasActiveCode |  |
| HAS_ENGINE | Vehicle | Engine | — | 0..* / 0..* | — | am:hasEngine |  |
| HAS_MANUFACTURER | PartReference | Brand | — | 1 / 0..* | — | am:hasManufacturer |  |
| INCLUDES_OPERATION | RepairOrder | ServiceOperation | — | 1..* / 0..* | — | am:includesOperation |  |
| INSTALLED_IN | Part | Vehicle | — | 0..* / 0..* | — | am:installedIn |  |
| INSTANCE_OF | Part | PartReference | — | 1 / 0..* | — | am:instanceOf |  |
| MADE_BY | VehicleModel | Brand | — | 1 / 0..* | — | am:madeBy |  |
| OF_MODEL | Vehicle | VehicleModel | — | 1 / 0..* | — | am:ofModel |  |
| OWNED_BY | Vehicle | Customer | — | 0..* / 0..* | — | am:ownedBy |  |
| PART_OF | Part | Part | — | 0..* / 0..* | — | am:partOf | Transitive : interroger avec -[:PART_OF*1..]-> (compensation complète en lecture, aucune contrainte). |
| PERFORMED_AT | RepairOrder | Garage | — | 1..* / 0..* | — | am:performedAt |  |
| PLANNED_FOR | MaintenancePlan | VehicleModel | — | 1 / 0..* | — | am:plannedFor |  |
| PRESCRIBES | MaintenancePlan | ServiceOperation | — | 1..* / 0..* | — | am:prescribes |  |
| READING_OF | MileageReading | Vehicle | — | 1 / 0..* | — | am:readingOf |  |
| USES_FUEL | Engine | FuelType | — | 0..* / 0..* | — | am:usesFuel |  |
| USES_PART | ServiceOperation | PartReference | — | 0..* / 0..* | — | am:usesPart |  |
| WORKS_AT | Technician | Garage | — | 1..* / 0..* | — | am:worksAt |  |

## Ce qui est perdu ou à risque

### Perdu (aucun équivalent natif) — 4

| Règle | Sujet | Constat | Option retenue | Impact | Compensation |
|---|---|---|---|---|---|
| C07 | am:ElectricVehicle | Disjonction de classes : am:ElectricVehicle disjointe de am:CombustionVehicle. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| C07 | am:Person | Disjonction de classes : am:Person disjointe de am:Organization. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| C07 | am:Vehicle | Disjonction de classes : am:Vehicle disjointe de am:Part. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O06 | am:partOf | Propriété transitive : am:partOf : transitive (propriété non simple). | `var_length_query` *(non arbitré, recommandé)* | -[:T*1..]-> : compensation complète en lecture, aucune contrainte. | matérialisation |

### À risque (à arbitrer) — 48

| Règle | Sujet | Constat | Option retenue | Impact | Compensation |
|---|---|---|---|---|---|
| C02 | am:Engine | Héritage simple : Hiérarchie de am:Engine : 2 sous-classe(s) à parent unique (am:ElectricMotor, am:InternalCombustionEngine) ; une décision pour toute la hiérarchie. | `multi_label` *(non arbitré, recommandé)* | Neo4j : le nœud porte son label et ceux de ses ancêtres (requêtes sur le parent naturelles). Curiosity : pas de multi-type, repli en liste de types `types` (propriété multivaluée) dans le type concret. | — |
| C02 | am:Party | Héritage simple : Hiérarchie de am:Party : 2 sous-classe(s) à parent unique (am:Organization, am:Person) ; une décision pour toute la hiérarchie. | `multi_label` *(non arbitré, recommandé)* | Neo4j : le nœud porte son label et ceux de ses ancêtres (requêtes sur le parent naturelles). Curiosity : pas de multi-type, repli en liste de types `types` (propriété multivaluée) dans le type concret. | — |
| C02 | am:Vehicle | Héritage simple : Hiérarchie de am:Vehicle : 2 sous-classe(s) à parent unique (am:CombustionVehicle, am:ElectricVehicle) ; une décision pour toute la hiérarchie. | `multi_label` *(non arbitré, recommandé)* | Neo4j : le nœud porte son label et ceux de ses ancêtres (requêtes sur le parent naturelles). Curiosity : pas de multi-type, repli en liste de types `types` (propriété multivaluée) dans le type concret. | — |
| C04 | am:Organization | Classe probablement abstraite : am:Organization a des sous-classes (am:Brand, am:Garage) et aucune instance directe connue : probablement abstraite (heuristique, OWA). | `secondary_label` *(non arbitré, recommandé)* | Type abstrait : le label est porté par les nœuds des sous-classes, jamais seul. | requête |
| C04 | am:Person | Classe probablement abstraite : am:Person a des sous-classes (am:Customer, am:Technician) et aucune instance directe connue : probablement abstraite (heuristique, OWA). | `secondary_label` *(non arbitré, recommandé)* | Type abstrait : le label est porté par les nœuds des sous-classes, jamais seul. | requête |
| C08 | am:FuelType | Classe énumérée : am:FuelType = {am:Diesel, am:Petrol, am:Electric, am:Hydrogen}. | `reference_nodes` *(non arbitré, recommandé)* | Un type, un nœud par valeur, relié par une relation : facettes liées, renommage sans dénormalisation. | 1 validation(s) |
| D05 | am:powerKw | Type de données avec perte : am:powerKw : decimal → Float. Pas de décimal Neo4j : FLOAT perd la précision (montants). Alternative : INTEGER en centimes ou STRING. | `native_type` *(non arbitré, recommandé)* | decimal → flottant (précision), dateTimeStamp → date-heure à fuseau, gYear → entier… | validation applicative |
| D05 | am:readingMileageKm | Type de données avec perte : am:readingMileageKm : decimal → Float. Pas de décimal Neo4j : FLOAT perd la précision (montants). Alternative : INTEGER en centimes ou STRING. | `native_type` *(non arbitré, recommandé)* | decimal → flottant (précision), dateTimeStamp → date-heure à fuseau, gYear → entier… | validation applicative |
| D05 | am:unitPrice | Type de données avec perte : am:unitPrice : decimal → Float. Pas de décimal Neo4j : FLOAT perd la précision (montants). Alternative : INTEGER en centimes ou STRING. | `native_type` *(non arbitré, recommandé)* | decimal → flottant (précision), dateTimeStamp → date-heure à fuseau, gYear → entier… | validation applicative |
| D09 | am:ModelYear | Datatype à facettes : Datatype am:ModelYear = integer [max=2100, min=1886] ; utilisé par am:modelYear. | `validation` *(non arbitré, recommandé)* | Le type de base natif est utilisé ; bornes et motifs deviennent des validations. | 1 validation(s) |
| D13 | am:Brand | Restriction sur propriété de données : am:Brand : am:brandName exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:DiagnosticTroubleCode | Restriction sur propriété de données : am:DiagnosticTroubleCode : am:dtcCode exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:MileageReading | Restriction sur propriété de données : am:MileageReading : am:readingDate exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:MileageReading | Restriction sur propriété de données : am:MileageReading : am:readingMileageKm exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:PartReference | Restriction sur propriété de données : am:PartReference : am:manufacturerPartNumber exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:Party | Restriction sur propriété de données : am:Party : am:displayName exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:Recall | Restriction sur propriété de données : am:Recall : am:recallNumber exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:RepairOrder | Restriction sur propriété de données : am:RepairOrder : am:openedAt exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:RepairOrder | Restriction sur propriété de données : am:RepairOrder : am:orderNumber exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:ServiceOperation | Restriction sur propriété de données : am:ServiceOperation : am:operationCode exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:Vehicle | Restriction sur propriété de données : am:Vehicle : am:vin exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:VehicleModel | Restriction sur propriété de données : am:VehicleModel : am:modelName exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| D13 | am:Warranty | Restriction sur propriété de données : am:Warranty : am:warrantyDurationMonths exactly 1. | `validation` *(non arbitré, recommandé)* | exactly 1 / min 1 → propriété obligatoire + contrôle. | 1 validation(s) |
| I01 | am:Diesel | Individu : Individu am:Diesel (am:FuelType) : membre d'une énumération / d'un référentiel. | `reference_nodes` *(non arbitré, recommandé)* | Ingéré comme donnée de référence (facettes). | arbitrage humain |
| I01 | am:Electric | Individu : Individu am:Electric (am:FuelType) : membre d'une énumération / d'un référentiel. | `reference_nodes` *(non arbitré, recommandé)* | Ingéré comme donnée de référence (facettes). | arbitrage humain |
| I01 | am:Hydrogen | Individu : Individu am:Hydrogen (am:FuelType) : membre d'une énumération / d'un référentiel. | `reference_nodes` *(non arbitré, recommandé)* | Ingéré comme donnée de référence (facettes). | arbitrage humain |
| I01 | am:Petrol | Individu : Individu am:Petrol (am:FuelType) : membre d'une énumération / d'un référentiel. | `reference_nodes` *(non arbitré, recommandé)* | Ingéré comme donnée de référence (facettes). | arbitrage humain |
| K02 | am:Brand | Clé OWL (hasKey) : HasKey(am:Brand am:brandName) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `node_key` *(non arbitré, recommandé)* | Neo4j : NODE KEY (existence + unicité, Enterprise ; UNIQUE en Community). Curiosity : [Key] = la propriété. RENFORCEMENT : hasKey n'impose ni existence ni unicité. | validation applicative |
| K02 | am:DiagnosticTroubleCode | Clé OWL (hasKey) : HasKey(am:DiagnosticTroubleCode am:dtcCode) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `node_key` *(non arbitré, recommandé)* | Neo4j : NODE KEY (existence + unicité, Enterprise ; UNIQUE en Community). Curiosity : [Key] = la propriété. RENFORCEMENT : hasKey n'impose ni existence ni unicité. | validation applicative |
| K02 | am:Recall | Clé OWL (hasKey) : HasKey(am:Recall am:recallNumber) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `node_key` *(non arbitré, recommandé)* | Neo4j : NODE KEY (existence + unicité, Enterprise ; UNIQUE en Community). Curiosity : [Key] = la propriété. RENFORCEMENT : hasKey n'impose ni existence ni unicité. | validation applicative |
| K02 | am:RepairOrder | Clé OWL (hasKey) : HasKey(am:RepairOrder am:orderNumber) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `node_key` *(non arbitré, recommandé)* | Neo4j : NODE KEY (existence + unicité, Enterprise ; UNIQUE en Community). Curiosity : [Key] = la propriété. RENFORCEMENT : hasKey n'impose ni existence ni unicité. | validation applicative |
| K02 | am:ServiceOperation | Clé OWL (hasKey) : HasKey(am:ServiceOperation am:operationCode) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `node_key` *(non arbitré, recommandé)* | Neo4j : NODE KEY (existence + unicité, Enterprise ; UNIQUE en Community). Curiosity : [Key] = la propriété. RENFORCEMENT : hasKey n'impose ni existence ni unicité. | validation applicative |
| K02 | am:Vehicle | Clé OWL (hasKey) : HasKey(am:Vehicle am:vin) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `node_key` *(non arbitré, recommandé)* | Neo4j : NODE KEY (existence + unicité, Enterprise ; UNIQUE en Community). Curiosity : [Key] = la propriété. RENFORCEMENT : hasKey n'impose ni existence ni unicité. | validation applicative |
| O09 | am:MaintenancePlan | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:MaintenancePlan ⊑ am:plannedFor exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O09 | am:MileageReading | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:MileageReading ⊑ am:readingOf exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O09 | am:Part | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:Part ⊑ am:instanceOf exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O09 | am:PartReference | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:PartReference ⊑ am:hasManufacturer exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O09 | am:RepairOrder | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:RepairOrder ⊑ am:concerns exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O09 | am:RepairOrder | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:RepairOrder ⊑ am:performedAt exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O09 | am:Technician | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:Technician ⊑ am:worksAt exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O09 | am:Vehicle | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:Vehicle ⊑ am:ofModel exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O09 | am:VehicleModel | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:VehicleModel ⊑ am:madeBy exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O09 | am:Warranty | Cardinalité ≤ 1 d'une relation (max / exactly / fonctionnelle) : am:Warranty ⊑ am:covers exactly 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O10 | am:CombustionVehicle | Existence d'une relation : am:CombustionVehicle ⊑ am:hasEngine some am:InternalCombustionEngine. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O10 | am:ElectricVehicle | Existence d'une relation : am:ElectricVehicle ⊑ am:hasEngine some am:ElectricMotor. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O10 | am:MaintenancePlan | Existence d'une relation : am:MaintenancePlan ⊑ am:prescribes min 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O10 | am:Recall | Existence d'une relation : am:Recall ⊑ am:appliesToModel min 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |
| O10 | am:RepairOrder | Existence d'une relation : am:RepairOrder ⊑ am:includesOperation min 1. | `validation` *(non arbitré, recommandé)* | La contrainte devient un contrôle exécuté à l'ingestion (connecteur) ou une requête de détection ; rien n'est bloqué nativement par la base. | 1 validation(s) |

## Transposé automatiquement — 114

- A01 — Annotations : 12
- C01 — Classe → type de nœud : 24
- D01 — Propriété de données : 25
- D13 — Restriction sur propriété de données : 12
- K01 — Identité IRI : 4
- K03 — Pas de clé métier : 9
- M01 — Métadonnées d'ontologie : 1
- O01 — Propriété objet → relation : 25
- O04 — Propriétés inverses : 2

## Validations à implémenter — 80

Contrôles applicatifs (connecteur / requêtes de détection) : la base ne les impose pas nativement.

| Id | Type | Cible | Description | Origine |
|---|---|---|---|---|
| `C07:am:ElectricVehicle#v1` | disjoint | ElectricVehicle | Aucun nœud n'est à la fois am:ElectricVehicle et am:CombustionVehicle. | am:ElectricVehicle |
| `C07:am:Person#v1` | disjoint | Person | Aucun nœud n'est à la fois am:Person et am:Organization. | am:Person |
| `C07:am:Vehicle#v1` | disjoint | Vehicle | Aucun nœud n'est à la fois am:Vehicle et am:Part. | am:Vehicle |
| `C08:am:FuelType#v1` | enum | FuelType | Les nœuds FuelType appartiennent à l'énumération {Diesel, Electric, Hydrogen, Petrol}. | am:FuelType |
| `D09:am:ModelYear#v1` | range | VehicleModel.modelYear | VehicleModel.modelYear respecte am:ModelYear (max=2100, min=1886). | am:ModelYear |
| `D13:am:Brand:am:brandName#v1` | cardinality | Brand.brandName | Brand.brandName : exactly 1. | am:Brand |
| `D13:am:DiagnosticTroubleCode:am:dtcCode#v1` | cardinality | DiagnosticTroubleCode.dtcCode | DiagnosticTroubleCode.dtcCode : exactly 1. | am:DiagnosticTroubleCode |
| `D13:am:Engine:am:displacementCc#v1` | cardinality | Engine.displacementCc | Engine.displacementCc : max 1. | am:Engine |
| `D13:am:Engine:am:powerKw#v1` | cardinality | Engine.powerKw | Engine.powerKw : max 1. | am:Engine |
| `D13:am:MaintenancePlan:am:intervalKm#v1` | cardinality | MaintenancePlan.intervalKm | MaintenancePlan.intervalKm : max 1. | am:MaintenancePlan |
| `D13:am:MaintenancePlan:am:intervalMonths#v1` | cardinality | MaintenancePlan.intervalMonths | MaintenancePlan.intervalMonths : max 1. | am:MaintenancePlan |
| `D13:am:MileageReading:am:readingDate#v1` | cardinality | MileageReading.readingDate | MileageReading.readingDate : exactly 1. | am:MileageReading |
| `D13:am:MileageReading:am:readingMileageKm#v1` | cardinality | MileageReading.readingMileageKm | MileageReading.readingMileageKm : exactly 1. | am:MileageReading |
| `D13:am:PartReference:am:manufacturerPartNumber#v1` | cardinality | PartReference.manufacturerPartNumber | PartReference.manufacturerPartNumber : exactly 1. | am:PartReference |
| `D13:am:PartReference:am:unitPrice#v1` | cardinality | PartReference.unitPrice | PartReference.unitPrice : max 1. | am:PartReference |
| `D13:am:Party:am:displayName#v1` | cardinality | Party.displayName | Party.displayName : exactly 1. | am:Party |
| `D13:am:Recall:am:issuedAt#v1` | cardinality | Recall.issuedAt | Recall.issuedAt : max 1. | am:Recall |
| `D13:am:Recall:am:recallNumber#v1` | cardinality | Recall.recallNumber | Recall.recallNumber : exactly 1. | am:Recall |
| `D13:am:RepairOrder:am:closedAt#v1` | cardinality | RepairOrder.closedAt | RepairOrder.closedAt : max 1. | am:RepairOrder |
| `D13:am:RepairOrder:am:openedAt#v1` | cardinality | RepairOrder.openedAt | RepairOrder.openedAt : exactly 1. | am:RepairOrder |
| `D13:am:RepairOrder:am:orderNumber#v1` | cardinality | RepairOrder.orderNumber | RepairOrder.orderNumber : exactly 1. | am:RepairOrder |
| `D13:am:ServiceOperation:am:operationCode#v1` | cardinality | ServiceOperation.operationCode | ServiceOperation.operationCode : exactly 1. | am:ServiceOperation |
| `D13:am:ServiceOperation:am:standardDurationMin#v1` | cardinality | ServiceOperation.standardDurationMin | ServiceOperation.standardDurationMin : max 1. | am:ServiceOperation |
| `D13:am:Vehicle:am:firstRegistrationDate#v1` | cardinality | Vehicle.firstRegistrationDate | Vehicle.firstRegistrationDate : max 1. | am:Vehicle |
| `D13:am:Vehicle:am:registrationNumber#v1` | cardinality | Vehicle.registrationNumber | Vehicle.registrationNumber : max 1. | am:Vehicle |
| `D13:am:Vehicle:am:vin#v1` | cardinality | Vehicle.vin | Vehicle.vin : exactly 1. | am:Vehicle |
| `D13:am:VehicleModel:am:modelName#v1` | cardinality | VehicleModel.modelName | VehicleModel.modelName : exactly 1. | am:VehicleModel |
| `D13:am:VehicleModel:am:modelYear#v1` | cardinality | VehicleModel.modelYear | VehicleModel.modelYear : max 1. | am:VehicleModel |
| `D13:am:Warranty:am:warrantyDurationMonths#v1` | cardinality | Warranty.warrantyDurationMonths | Warranty.warrantyDurationMonths : exactly 1. | am:Warranty |
| `D13:am:Warranty:am:warrantyMaxKm#v1` | cardinality | Warranty.warrantyMaxKm | Warranty.warrantyMaxKm : max 1. | am:Warranty |
| `O09:am:MaintenancePlan:am:plannedFor#v1` | cardinality | MaintenancePlan [PLANNED_FOR] | MaintenancePlan : am:MaintenancePlan ⊑ am:plannedFor exactly 1. | am:MaintenancePlan |
| `O09:am:MileageReading:am:readingOf#v1` | cardinality | MileageReading [READING_OF] | MileageReading : am:MileageReading ⊑ am:readingOf exactly 1. | am:MileageReading |
| `O09:am:Part:am:instanceOf#v1` | cardinality | Part [INSTANCE_OF] | Part : am:Part ⊑ am:instanceOf exactly 1. | am:Part |
| `O09:am:PartReference:am:hasManufacturer#v1` | cardinality | PartReference [HAS_MANUFACTURER] | PartReference : am:PartReference ⊑ am:hasManufacturer exactly 1. | am:PartReference |
| `O09:am:RepairOrder:am:concerns#v1` | cardinality | RepairOrder [CONCERNS] | RepairOrder : am:RepairOrder ⊑ am:concerns exactly 1. | am:RepairOrder |
| `O09:am:RepairOrder:am:performedAt#v1` | cardinality | RepairOrder [PERFORMED_AT] | RepairOrder : am:RepairOrder ⊑ am:performedAt exactly 1. | am:RepairOrder |
| `O09:am:Technician:am:worksAt#v1` | cardinality | Technician [WORKS_AT] | Technician : am:Technician ⊑ am:worksAt exactly 1. | am:Technician |
| `O09:am:Vehicle:am:ofModel#v1` | cardinality | Vehicle [OF_MODEL] | Vehicle : am:Vehicle ⊑ am:ofModel exactly 1. | am:Vehicle |
| `O09:am:VehicleModel:am:madeBy#v1` | cardinality | VehicleModel [MADE_BY] | VehicleModel : am:VehicleModel ⊑ am:madeBy exactly 1. | am:VehicleModel |
| `O09:am:Warranty:am:covers#v1` | cardinality | Warranty [COVERS] | Warranty : am:Warranty ⊑ am:covers exactly 1. | am:Warranty |
| `O10:am:CombustionVehicle:am:hasEngine#v1` | existence | CombustionVehicle | CombustionVehicle : am:CombustionVehicle ⊑ am:hasEngine some am:InternalCombustionEngine. | am:CombustionVehicle |
| `O10:am:ElectricVehicle:am:hasEngine#v1` | existence | ElectricVehicle | ElectricVehicle : am:ElectricVehicle ⊑ am:hasEngine some am:ElectricMotor. | am:ElectricVehicle |
| `O10:am:MaintenancePlan:am:prescribes#v1` | existence | MaintenancePlan [PRESCRIBES] | MaintenancePlan : am:MaintenancePlan ⊑ am:prescribes min 1. | am:MaintenancePlan |
| `O10:am:Recall:am:appliesToModel#v1` | existence | Recall [APPLIES_TO_MODEL] | Recall : am:Recall ⊑ am:appliesToModel min 1. | am:Recall |
| `O10:am:RepairOrder:am:includesOperation#v1` | existence | RepairOrder [INCLUDES_OPERATION] | RepairOrder : am:RepairOrder ⊑ am:includesOperation min 1. | am:RepairOrder |
| `SH:am:Brand:am:brandName#v1` | existence | Brand.brandName | Brand.brandName obligatoire (sh:minCount 1). | _:brandName-1c28bdac |
| `SH:am:DiagnosticTroubleCode:am:dtcCode#v1` | existence | DiagnosticTroubleCode.dtcCode | DiagnosticTroubleCode.dtcCode obligatoire (sh:minCount 1). | _:dtcCode-eda38a4e |
| `SH:am:DiagnosticTroubleCode:am:dtcCode#v2` | pattern | DiagnosticTroubleCode.dtcCode | DiagnosticTroubleCode.dtcCode ~ ^[PCBU][0-9A-F]{4}$ | _:dtcCode-eda38a4e |
| `SH:am:MileageReading:am:readingDate#v1` | existence | MileageReading.readingDate | MileageReading.readingDate obligatoire (sh:minCount 1). | _:readingDate-e065d31b |
| `SH:am:MileageReading:am:readingMileageKm#v1` | existence | MileageReading.readingMileageKm | MileageReading.readingMileageKm obligatoire (sh:minCount 1). | _:readingMileageKm-da0ef657 |
| `SH:am:MileageReading:am:readingMileageKm#v2` | cardinality | MileageReading.readingMileageKm | MileageReading.readingMileageKm : au plus 1 valeur(s). | _:readingMileageKm-da0ef657 |
| `SH:am:MileageReading:am:readingMileageKm#v3` | range | MileageReading.readingMileageKm | MileageReading.readingMileageKm : bornes {'min_inclusive': '0'}. | _:readingMileageKm-da0ef657 |
| `SH:am:PartReference:am:hasManufacturer#v1` | existence | PartReference [HAS_MANUFACTURER] | PartReference : au moins 1 relation HAS_MANUFACTURER. | _:hasManufacturer-90a157f4 |
| `SH:am:PartReference:am:hasManufacturer#v2` | cardinality | PartReference [HAS_MANUFACTURER] | PartReference : au plus 1 HAS_MANUFACTURER. | _:hasManufacturer-90a157f4 |
| `SH:am:PartReference:am:hasManufacturer#v3` | allValuesFrom | PartReference [HAS_MANUFACTURER] | HAS_MANUFACTURER → am:Brand (sh:class). | _:hasManufacturer-90a157f4 |
| `SH:am:PartReference:am:manufacturerPartNumber#v1` | existence | PartReference.manufacturerPartNumber | PartReference.manufacturerPartNumber obligatoire (sh:minCount 1). | _:manufacturerPartNumber-b54fa84b |
| `SH:am:Recall:am:appliesToModel#v1` | existence | Recall [APPLIES_TO_MODEL] | Recall : au moins 1 relation APPLIES_TO_MODEL. | _:appliesToModel-164ac8d9 |
| `SH:am:Recall:am:appliesToModel#v2` | allValuesFrom | Recall [APPLIES_TO_MODEL] | APPLIES_TO_MODEL → am:VehicleModel (sh:class). | _:appliesToModel-164ac8d9 |
| `SH:am:RepairOrder:am:closedAt#v1` | cardinality | RepairOrder.closedAt | RepairOrder.closedAt : au plus 1 valeur(s). | _:closedAt-b34b4d35 |
| `SH:am:RepairOrder:am:includesOperation#v1` | existence | RepairOrder [INCLUDES_OPERATION] | RepairOrder : au moins 1 relation INCLUDES_OPERATION. | _:includesOperation-6aa8ac53 |
| `SH:am:RepairOrder:am:includesOperation#v2` | allValuesFrom | RepairOrder [INCLUDES_OPERATION] | INCLUDES_OPERATION → am:ServiceOperation (sh:class). | _:includesOperation-6aa8ac53 |
| `SH:am:RepairOrder:am:openedAt#v1` | existence | RepairOrder.openedAt | RepairOrder.openedAt obligatoire (sh:minCount 1). | _:openedAt-151b9102 |
| `SH:am:RepairOrder:am:openedAt#v2` | cardinality | RepairOrder.openedAt | RepairOrder.openedAt : au plus 1 valeur(s). | _:openedAt-151b9102 |
| `SH:am:RepairOrder:am:openedAt#v3` | other | RepairOrder.openedAt | RepairOrder.openedAt < am:closedAt (sh:lessThan). | _:openedAt-151b9102 |
| `SH:am:RepairOrder:am:performedAt#v1` | existence | RepairOrder [PERFORMED_AT] | RepairOrder : au moins 1 relation PERFORMED_AT. | _:performedAt-ba7fe47e |
| `SH:am:RepairOrder:am:performedAt#v2` | allValuesFrom | RepairOrder [PERFORMED_AT] | PERFORMED_AT → am:Garage (sh:class). | _:performedAt-ba7fe47e |
| `SH:am:Technician:am:worksAt#v1` | existence | Technician [WORKS_AT] | Technician : au moins 1 relation WORKS_AT. | _:worksAt-77cb091f |
| `SH:am:Technician:am:worksAt#v2` | allValuesFrom | Technician [WORKS_AT] | WORKS_AT → am:Garage (sh:class). | _:worksAt-77cb091f |
| `SH:am:Vehicle:am:hasEngine#v1` | allValuesFrom | Vehicle [HAS_ENGINE] | HAS_ENGINE → am:Engine (sh:class). | _:hasEngine-79a6ce87 |
| `SH:am:Vehicle:am:ofModel#v1` | existence | Vehicle [OF_MODEL] | Vehicle : au moins 1 relation OF_MODEL. | _:ofModel-7a9d147f |
| `SH:am:Vehicle:am:ofModel#v2` | cardinality | Vehicle [OF_MODEL] | Vehicle : au plus 1 OF_MODEL. | _:ofModel-7a9d147f |
| `SH:am:Vehicle:am:ofModel#v3` | allValuesFrom | Vehicle [OF_MODEL] | OF_MODEL → am:VehicleModel (sh:class). | _:ofModel-7a9d147f |
| `SH:am:Vehicle:am:vin#v1` | existence | Vehicle.vin | VIN : 17 caractères, sans I, O ni Q | _:vin-3f1140e6 |
| `SH:am:Vehicle:am:vin#v2` | cardinality | Vehicle.vin | Vehicle.vin : au plus 1 valeur(s). | _:vin-3f1140e6 |
| `SH:am:Vehicle:am:vin#v3` | pattern | Vehicle.vin | VIN : 17 caractères, sans I, O ni Q | _:vin-3f1140e6 |
| `SH:am:VehicleModel:am:madeBy#v1` | existence | VehicleModel [MADE_BY] | VehicleModel : au moins 1 relation MADE_BY. | _:madeBy-888a8ae0 |
| `SH:am:VehicleModel:am:madeBy#v2` | cardinality | VehicleModel [MADE_BY] | VehicleModel : au plus 1 MADE_BY. | _:madeBy-888a8ae0 |
| `SH:am:VehicleModel:am:madeBy#v3` | allValuesFrom | VehicleModel [MADE_BY] | MADE_BY → am:Brand (sh:class). | _:madeBy-888a8ae0 |
| `SH:am:VehicleModel:am:modelYear#v1` | range | VehicleModel.modelYear | VehicleModel.modelYear : bornes {'min_inclusive': '1886', 'max_inclusive': '2100'}. | _:modelYear-e6b84422 |
| `SH:am:Warranty:am:warrantyDurationMonths#v1` | range | Warranty.warrantyDurationMonths | Warranty.warrantyDurationMonths : bornes {'min_inclusive': '0'}. | _:warrantyDurationMonths-0d3f0183 |

## Matérialisations — 0

Aucune.

## Arbitrages

Aucun arbitrage enregistré : toutes les recommandations sont appliquées par défaut.
