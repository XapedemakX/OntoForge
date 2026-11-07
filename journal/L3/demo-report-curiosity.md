# Rapport de transposition — AutoMaint — ontologie de maintenance automobile → Curiosity

Ontologie source : `https://w3id.org/ontoforge/automaint` · cible : **Curiosity** · OntoForge 0.1.0

## Synthèse

| Indicateur | Valeur |
|---|---|
| Constats | 166 |
| Transposés automatiquement (auto) | 117 |
| À arbitrer (review) | 48 |
| Perdus sans compensation native (lost) | 1 |
| Arbitrés / non arbitrés (review + lost) | 0 / 49 |
| Types de nœuds / relations | 18 / 24 |
| Validations à implémenter / matérialisations | 83 / 1 |

> **Hypothèse de monde clos.** OWL raisonne en monde ouvert, sans hypothèse du nom unique : un axiome y *infère* des faits (domaine, portée, restrictions, clés). Le schéma property graph est un *contrat d'ingestion* en monde clos : ces axiomes deviennent ici des contraintes ou des validations, ce qui est un renforcement (ce qui manque est une erreur, deux clés différentes sont deux nœuds). Ce rappel vaut pour tout le rapport.

**49 constat(s) non arbitré(s)** : la recommandation pour Curiosity a été appliquée (marquée « non arbitré »).

## Types de nœuds

| Type | Labels | Clé | Propriétés | Classes OWL sources |
|---|---|---|---|---|
| Brand | Brand | Uri | Uri*: String, BrandName*: String | am:Brand |
| Customer | Customer | Uri | Uri*: String | am:Customer |
| DiagnosticTroubleCode | DiagnosticTroubleCode | Uri | Uri*: String, DtcCode*: String | am:DiagnosticTroubleCode |
| Engine | Engine | Uri | Uri*: String, EngineKind: String, DisplacementCc: Integer, PowerKw: Float | am:Engine, am:ElectricMotor, am:InternalCombustionEngine |
| FuelType | FuelType | Uri | Uri*: String, LabelEn: String, LabelFr: String | am:FuelType |
| Garage | Garage | Uri | Uri*: String | am:Garage |
| MaintenancePlan | MaintenancePlan | Uri | Uri*: String, IntervalKm: Integer, IntervalMonths: Integer | am:MaintenancePlan |
| MileageReading | MileageReading | Uri | Uri*: String, ReadingDate*: DateTime, ReadingMileageKm*: Float | am:MileageReading |
| Part | Part | Uri | Uri*: String | am:Part |
| PartReference | PartReference | Uri | Uri*: String, ManufacturerPartNumber*: String, UnitPrice: Float | am:PartReference |
| Party | Party | Uri | Uri*: String, PartyKind: String, DisplayName*: String | am:Party, am:Organization, am:Person |
| Recall | Recall | Uri | Uri*: String, IssuedAt: DateTime, RecallNumber*: String | am:Recall |
| RepairOrder | RepairOrder | Uri | Uri*: String, ClosedAt: DateTime, OpenedAt*: DateTime, OrderNumber*: String | am:RepairOrder |
| ServiceOperation | ServiceOperation | Uri | Uri*: String, OperationCode*: String, StandardDurationMin: Integer | am:ServiceOperation |
| Technician | Technician | Uri | Uri*: String | am:Technician |
| Vehicle | Vehicle | Uri | Uri*: String, VehicleKind: String, FirstRegistrationDate: DateTime, RegistrationNumber: String, Vin*: String | am:Vehicle, am:CombustionVehicle, am:ElectricVehicle |
| VehicleModel | VehicleModel | Uri | Uri*: String, ModelName*: String, ModelYear: Integer | am:VehicleModel |
| Warranty | Warranty | Uri | Uri*: String, WarrantyDurationMonths*: Integer, WarrantyMaxKm: Integer | am:Warranty |

`*` obligatoire · `[]` liste.

## Relations

| Relation | De | Vers | Retour | Cardinalité (sortie / entrée) | Propriétés | Source | Note |
|---|---|---|---|---|---|---|---|
| Addresses | ServiceOperation | DiagnosticTroubleCode | AddressesInverse | 0..* / 0..* | — | am:addresses |  |
| AppliesToModel | Recall | VehicleModel | AppliesToModelInverse | 1..* / 0..* | — | am:appliesToModel |  |
| AssignedTo | RepairOrder | Technician | AssignedToInverse | 0..* / 0..* | — | am:assignedTo |  |
| Concerns | RepairOrder | Vehicle | HasRepairOrder | 1 / 0..* | — | am:concerns |  |
| ConcernsPart | Recall | PartReference | ConcernsPartInverse | 0..* / 0..* | — | am:concernsPart |  |
| Covers | Warranty | Vehicle | CoversInverse | 1 / 0..* | — | am:covers |  |
| HasActiveCode | Vehicle | DiagnosticTroubleCode | ActiveCodeOf | 0..* / 0..* | — | am:hasActiveCode |  |
| HasEngine | Vehicle | Engine | EngineOf | 0..* / 0..* | — | am:hasEngine |  |
| HasManufacturer | PartReference | Brand | ManufacturerOf | 1 / 0..* | — | am:hasManufacturer |  |
| IncludesOperation | RepairOrder | ServiceOperation | IncludesOperationInverse | 1..* / 0..* | — | am:includesOperation |  |
| InstalledIn | Part | Vehicle | InstalledInInverse | 0..* / 0..* | — | am:installedIn |  |
| InstanceOf | Part | PartReference | HasInstance | 1 / 0..* | — | am:instanceOf |  |
| MadeBy | VehicleModel | Brand | MadeByInverse | 1 / 0..* | — | am:madeBy |  |
| OfModel | Vehicle | VehicleModel | OfModelInverse | 1 / 0..* | — | am:ofModel |  |
| OwnedBy | Vehicle | Customer | OwnedByInverse | 0..* / 0..* | — | am:ownedBy |  |
| PartOf | Part | Part | HasPart | 0..* / 0..* | — | am:partOf |  |
| PartOfTransitive | Part | Part | PartOfTransitiveInverse | 0..* / 0..* | — | am:partOf | dérivée; Fermeture transitive de PartOf, recalculée après ingestion. |
| PerformedAt | RepairOrder | Garage | PerformedAtInverse | 1..* / 0..* | — | am:performedAt |  |
| PlannedFor | MaintenancePlan | VehicleModel | PlannedForInverse | 1 / 0..* | — | am:plannedFor |  |
| Prescribes | MaintenancePlan | ServiceOperation | PrescribesInverse | 1..* / 0..* | — | am:prescribes |  |
| ReadingOf | MileageReading | Vehicle | HasMileageReading | 1 / 0..* | — | am:readingOf |  |
| UsesFuel | Engine | FuelType | UsesFuelInverse | 0..* / 0..* | — | am:usesFuel |  |
| UsesPart | ServiceOperation | PartReference | UsesPartInverse | 0..* / 0..* | — | am:usesPart |  |
| WorksAt | Technician | Garage | WorksAtInverse | 1..* / 0..* | — | am:worksAt |  |

## Ce qui est perdu ou à risque

### Perdu (aucun équivalent natif) — 1

| Règle | Sujet | Constat | Option retenue | Impact | Compensation |
|---|---|---|---|---|---|
| O06 | am:partOf | Propriété transitive : am:partOf : transitive (propriété non simple). | `materialize_closure` *(non arbitré, recommandé)* | Arête dérivée `<nom>Transitive` recalculée après ingestion. | 1 matérialisation(s) |

### À risque (à arbitrer) — 48

| Règle | Sujet | Constat | Option retenue | Impact | Compensation |
|---|---|---|---|---|---|
| C02 | am:Engine | Héritage simple : Hiérarchie de am:Engine : 2 sous-classe(s) à parent unique (am:ElectricMotor, am:InternalCombustionEngine) ; une décision pour toute la hiérarchie. | `flatten_into_leaves` *(non arbitré, recommandé)* | Les sous-classes de la hiérarchie sont repliées dans le type de nœud de la racine concrète (propriétés recopiées) avec un discriminant `<racine>Kind` ; leurs restrictions deviennent des validations filtrées par discriminant ; requêtes par sous-type = filtre. | — |
| C02 | am:Party | Héritage simple : Hiérarchie de am:Party : 2 sous-classe(s) à parent unique (am:Organization, am:Person) ; une décision pour toute la hiérarchie. | `flatten_into_leaves` *(non arbitré, recommandé)* | Les sous-classes de la hiérarchie sont repliées dans le type de nœud de la racine concrète (propriétés recopiées) avec un discriminant `<racine>Kind` ; leurs restrictions deviennent des validations filtrées par discriminant ; requêtes par sous-type = filtre. | — |
| C02 | am:Vehicle | Héritage simple : Hiérarchie de am:Vehicle : 2 sous-classe(s) à parent unique (am:CombustionVehicle, am:ElectricVehicle) ; une décision pour toute la hiérarchie. | `flatten_into_leaves` *(non arbitré, recommandé)* | Les sous-classes de la hiérarchie sont repliées dans le type de nœud de la racine concrète (propriétés recopiées) avec un discriminant `<racine>Kind` ; leurs restrictions deviennent des validations filtrées par discriminant ; requêtes par sous-type = filtre. | — |
| C04 | am:Organization | Classe probablement abstraite : am:Organization a des sous-classes (am:Brand, am:Garage) et aucune instance directe connue : probablement abstraite (heuristique, OWA). | `merge_into_leaves` *(non arbitré, recommandé)* | Pas de type de nœud : ses propriétés et relations sont recopiées dans chaque sous-type concret. | requête |
| C04 | am:Person | Classe probablement abstraite : am:Person a des sous-classes (am:Customer, am:Technician) et aucune instance directe connue : probablement abstraite (heuristique, OWA). | `merge_into_leaves` *(non arbitré, recommandé)* | Pas de type de nœud : ses propriétés et relations sont recopiées dans chaque sous-type concret. | requête |
| C08 | am:FuelType | Classe énumérée : am:FuelType = {am:Diesel, am:Petrol, am:Electric, am:Hydrogen}. | `reference_nodes` *(non arbitré, recommandé)* | Un type, un nœud par valeur, relié par une relation : facettes liées, renommage sans dénormalisation. | 1 validation(s) |
| D05 | am:powerKw | Type de données avec perte : am:powerKw : decimal → Float. Décimal exact -> double. Curiosity a FieldType.Decimal (C# decimal) mais PGType n'a pas Decimal : demande de contrat L4. | `native_type` *(non arbitré, recommandé)* | decimal → flottant (précision), dateTimeStamp → date-heure à fuseau, gYear → entier… | validation applicative |
| D05 | am:readingMileageKm | Type de données avec perte : am:readingMileageKm : decimal → Float. Décimal exact -> double. Curiosity a FieldType.Decimal (C# decimal) mais PGType n'a pas Decimal : demande de contrat L4. | `native_type` *(non arbitré, recommandé)* | decimal → flottant (précision), dateTimeStamp → date-heure à fuseau, gYear → entier… | validation applicative |
| D05 | am:unitPrice | Type de données avec perte : am:unitPrice : decimal → Float. Décimal exact -> double. Curiosity a FieldType.Decimal (C# decimal) mais PGType n'a pas Decimal : demande de contrat L4. | `native_type` *(non arbitré, recommandé)* | decimal → flottant (précision), dateTimeStamp → date-heure à fuseau, gYear → entier… | validation applicative |
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
| K02 | am:Brand | Clé OWL (hasKey) : HasKey(am:Brand am:brandName) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `uri_key` *(non arbitré, recommandé)* | La clé reste l'IRI ; l'unicité des valeurs hasKey devient une validation applicative. | 1 validation(s) |
| K02 | am:DiagnosticTroubleCode | Clé OWL (hasKey) : HasKey(am:DiagnosticTroubleCode am:dtcCode) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `uri_key` *(non arbitré, recommandé)* | La clé reste l'IRI ; l'unicité des valeurs hasKey devient une validation applicative. | 1 validation(s) |
| K02 | am:Recall | Clé OWL (hasKey) : HasKey(am:Recall am:recallNumber) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `uri_key` *(non arbitré, recommandé)* | La clé reste l'IRI ; l'unicité des valeurs hasKey devient une validation applicative. | 1 validation(s) |
| K02 | am:RepairOrder | Clé OWL (hasKey) : HasKey(am:RepairOrder am:orderNumber) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `uri_key` *(non arbitré, recommandé)* | La clé reste l'IRI ; l'unicité des valeurs hasKey devient une validation applicative. | 1 validation(s) |
| K02 | am:ServiceOperation | Clé OWL (hasKey) : HasKey(am:ServiceOperation am:operationCode) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `uri_key` *(non arbitré, recommandé)* | La clé reste l'IRI ; l'unicité des valeurs hasKey devient une validation applicative. | 1 validation(s) |
| K02 | am:Vehicle | Clé OWL (hasKey) : HasKey(am:Vehicle am:vin) : en OWL, deux individus nommés de mêmes valeurs sont owl:sameAs ; ni existence ni unicité ne sont imposées. | `uri_key` *(non arbitré, recommandé)* | La clé reste l'IRI ; l'unicité des valeurs hasKey devient une validation applicative. | 1 validation(s) |
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

## Transposé automatiquement — 117

- A01 — Annotations : 12
- C01 — Classe → type de nœud : 24
- C07 — Disjonction de classes : 3
- D01 — Propriété de données : 25
- D13 — Restriction sur propriété de données : 12
- K01 — Identité IRI : 4
- K03 — Pas de clé métier : 9
- M01 — Métadonnées d'ontologie : 1
- O01 — Propriété objet → relation : 25
- O04 — Propriétés inverses : 2

## Validations à implémenter — 83

Contrôles applicatifs (connecteur / requêtes de détection) : la base ne les impose pas nativement.

| Id | Type | Cible | Description | Origine |
|---|---|---|---|---|
| `C08:am:FuelType#v1` | enum | FuelType | Les nœuds FuelType appartiennent à l'énumération {Diesel, Electric, Hydrogen, Petrol}. | am:FuelType |
| `D09:am:ModelYear#v1` | range | VehicleModel.ModelYear | VehicleModel.ModelYear respecte am:ModelYear (max=2100, min=1886). | am:ModelYear |
| `D13:am:Brand:am:brandName#v1` | cardinality | Brand.BrandName | Brand.BrandName : exactly 1. | am:Brand |
| `D13:am:DiagnosticTroubleCode:am:dtcCode#v1` | cardinality | DiagnosticTroubleCode.DtcCode | DiagnosticTroubleCode.DtcCode : exactly 1. | am:DiagnosticTroubleCode |
| `D13:am:Engine:am:displacementCc#v1` | cardinality | Engine.DisplacementCc | Engine.DisplacementCc : max 1. | am:Engine |
| `D13:am:Engine:am:powerKw#v1` | cardinality | Engine.PowerKw | Engine.PowerKw : max 1. | am:Engine |
| `D13:am:MaintenancePlan:am:intervalKm#v1` | cardinality | MaintenancePlan.IntervalKm | MaintenancePlan.IntervalKm : max 1. | am:MaintenancePlan |
| `D13:am:MaintenancePlan:am:intervalMonths#v1` | cardinality | MaintenancePlan.IntervalMonths | MaintenancePlan.IntervalMonths : max 1. | am:MaintenancePlan |
| `D13:am:MileageReading:am:readingDate#v1` | cardinality | MileageReading.ReadingDate | MileageReading.ReadingDate : exactly 1. | am:MileageReading |
| `D13:am:MileageReading:am:readingMileageKm#v1` | cardinality | MileageReading.ReadingMileageKm | MileageReading.ReadingMileageKm : exactly 1. | am:MileageReading |
| `D13:am:PartReference:am:manufacturerPartNumber#v1` | cardinality | PartReference.ManufacturerPartNumber | PartReference.ManufacturerPartNumber : exactly 1. | am:PartReference |
| `D13:am:PartReference:am:unitPrice#v1` | cardinality | PartReference.UnitPrice | PartReference.UnitPrice : max 1. | am:PartReference |
| `D13:am:Party:am:displayName#v1` | cardinality | Party.DisplayName | Party.DisplayName : exactly 1. | am:Party |
| `D13:am:Recall:am:issuedAt#v1` | cardinality | Recall.IssuedAt | Recall.IssuedAt : max 1. | am:Recall |
| `D13:am:Recall:am:recallNumber#v1` | cardinality | Recall.RecallNumber | Recall.RecallNumber : exactly 1. | am:Recall |
| `D13:am:RepairOrder:am:closedAt#v1` | cardinality | RepairOrder.ClosedAt | RepairOrder.ClosedAt : max 1. | am:RepairOrder |
| `D13:am:RepairOrder:am:openedAt#v1` | cardinality | RepairOrder.OpenedAt | RepairOrder.OpenedAt : exactly 1. | am:RepairOrder |
| `D13:am:RepairOrder:am:orderNumber#v1` | cardinality | RepairOrder.OrderNumber | RepairOrder.OrderNumber : exactly 1. | am:RepairOrder |
| `D13:am:ServiceOperation:am:operationCode#v1` | cardinality | ServiceOperation.OperationCode | ServiceOperation.OperationCode : exactly 1. | am:ServiceOperation |
| `D13:am:ServiceOperation:am:standardDurationMin#v1` | cardinality | ServiceOperation.StandardDurationMin | ServiceOperation.StandardDurationMin : max 1. | am:ServiceOperation |
| `D13:am:Vehicle:am:firstRegistrationDate#v1` | cardinality | Vehicle.FirstRegistrationDate | Vehicle.FirstRegistrationDate : max 1. | am:Vehicle |
| `D13:am:Vehicle:am:registrationNumber#v1` | cardinality | Vehicle.RegistrationNumber | Vehicle.RegistrationNumber : max 1. | am:Vehicle |
| `D13:am:Vehicle:am:vin#v1` | cardinality | Vehicle.Vin | Vehicle.Vin : exactly 1. | am:Vehicle |
| `D13:am:VehicleModel:am:modelName#v1` | cardinality | VehicleModel.ModelName | VehicleModel.ModelName : exactly 1. | am:VehicleModel |
| `D13:am:VehicleModel:am:modelYear#v1` | cardinality | VehicleModel.ModelYear | VehicleModel.ModelYear : max 1. | am:VehicleModel |
| `D13:am:Warranty:am:warrantyDurationMonths#v1` | cardinality | Warranty.WarrantyDurationMonths | Warranty.WarrantyDurationMonths : exactly 1. | am:Warranty |
| `D13:am:Warranty:am:warrantyMaxKm#v1` | cardinality | Warranty.WarrantyMaxKm | Warranty.WarrantyMaxKm : max 1. | am:Warranty |
| `K02:am:Brand#v1` | other | Brand | Unicité de (BrandName) sur Brand (hasKey OWL, contrôle applicatif ; la clé reste uri). | am:Brand |
| `K02:am:DiagnosticTroubleCode#v1` | other | DiagnosticTroubleCode | Unicité de (DtcCode) sur DiagnosticTroubleCode (hasKey OWL, contrôle applicatif ; la clé reste uri). | am:DiagnosticTroubleCode |
| `K02:am:Recall#v1` | other | Recall | Unicité de (RecallNumber) sur Recall (hasKey OWL, contrôle applicatif ; la clé reste uri). | am:Recall |
| `K02:am:RepairOrder#v1` | other | RepairOrder | Unicité de (OrderNumber) sur RepairOrder (hasKey OWL, contrôle applicatif ; la clé reste uri). | am:RepairOrder |
| `K02:am:ServiceOperation#v1` | other | ServiceOperation | Unicité de (OperationCode) sur ServiceOperation (hasKey OWL, contrôle applicatif ; la clé reste uri). | am:ServiceOperation |
| `K02:am:Vehicle#v1` | other | Vehicle | Unicité de (Vin) sur Vehicle (hasKey OWL, contrôle applicatif ; la clé reste uri). | am:Vehicle |
| `O09:am:MaintenancePlan:am:plannedFor#v1` | cardinality | MaintenancePlan [PlannedFor] | MaintenancePlan : am:MaintenancePlan ⊑ am:plannedFor exactly 1. | am:MaintenancePlan |
| `O09:am:MileageReading:am:readingOf#v1` | cardinality | MileageReading [ReadingOf] | MileageReading : am:MileageReading ⊑ am:readingOf exactly 1. | am:MileageReading |
| `O09:am:Part:am:instanceOf#v1` | cardinality | Part [InstanceOf] | Part : am:Part ⊑ am:instanceOf exactly 1. | am:Part |
| `O09:am:PartReference:am:hasManufacturer#v1` | cardinality | PartReference [HasManufacturer] | PartReference : am:PartReference ⊑ am:hasManufacturer exactly 1. | am:PartReference |
| `O09:am:RepairOrder:am:concerns#v1` | cardinality | RepairOrder [Concerns] | RepairOrder : am:RepairOrder ⊑ am:concerns exactly 1. | am:RepairOrder |
| `O09:am:RepairOrder:am:performedAt#v1` | cardinality | RepairOrder [PerformedAt] | RepairOrder : am:RepairOrder ⊑ am:performedAt exactly 1. | am:RepairOrder |
| `O09:am:Technician:am:worksAt#v1` | cardinality | Technician [WorksAt] | Technician : am:Technician ⊑ am:worksAt exactly 1. | am:Technician |
| `O09:am:Vehicle:am:ofModel#v1` | cardinality | Vehicle [OfModel] | Vehicle : am:Vehicle ⊑ am:ofModel exactly 1. | am:Vehicle |
| `O09:am:VehicleModel:am:madeBy#v1` | cardinality | VehicleModel [MadeBy] | VehicleModel : am:VehicleModel ⊑ am:madeBy exactly 1. | am:VehicleModel |
| `O09:am:Warranty:am:covers#v1` | cardinality | Warranty [Covers] | Warranty : am:Warranty ⊑ am:covers exactly 1. | am:Warranty |
| `O10:am:CombustionVehicle:am:hasEngine#v1` | existence | Vehicle [HasEngine] | Vehicle [si VehicleKind ∈ {CombustionVehicle}] : am:CombustionVehicle ⊑ am:hasEngine some am:InternalCombustionEngine. | am:CombustionVehicle |
| `O10:am:ElectricVehicle:am:hasEngine#v1` | existence | Vehicle [HasEngine] | Vehicle [si VehicleKind ∈ {ElectricVehicle}] : am:ElectricVehicle ⊑ am:hasEngine some am:ElectricMotor. | am:ElectricVehicle |
| `O10:am:MaintenancePlan:am:prescribes#v1` | existence | MaintenancePlan [Prescribes] | MaintenancePlan : am:MaintenancePlan ⊑ am:prescribes min 1. | am:MaintenancePlan |
| `O10:am:Recall:am:appliesToModel#v1` | existence | Recall [AppliesToModel] | Recall : am:Recall ⊑ am:appliesToModel min 1. | am:Recall |
| `O10:am:RepairOrder:am:includesOperation#v1` | existence | RepairOrder [IncludesOperation] | RepairOrder : am:RepairOrder ⊑ am:includesOperation min 1. | am:RepairOrder |
| `SH:am:Brand:am:brandName#v1` | existence | Brand.BrandName | Brand.BrandName obligatoire (sh:minCount 1). | _:brandName-1c28bdac |
| `SH:am:DiagnosticTroubleCode:am:dtcCode#v1` | existence | DiagnosticTroubleCode.DtcCode | DiagnosticTroubleCode.DtcCode obligatoire (sh:minCount 1). | _:dtcCode-eda38a4e |
| `SH:am:DiagnosticTroubleCode:am:dtcCode#v2` | pattern | DiagnosticTroubleCode.DtcCode | DiagnosticTroubleCode.DtcCode ~ ^[PCBU][0-9A-F]{4}$ | _:dtcCode-eda38a4e |
| `SH:am:MileageReading:am:readingDate#v1` | existence | MileageReading.ReadingDate | MileageReading.ReadingDate obligatoire (sh:minCount 1). | _:readingDate-e065d31b |
| `SH:am:MileageReading:am:readingMileageKm#v1` | existence | MileageReading.ReadingMileageKm | MileageReading.ReadingMileageKm obligatoire (sh:minCount 1). | _:readingMileageKm-da0ef657 |
| `SH:am:MileageReading:am:readingMileageKm#v2` | cardinality | MileageReading.ReadingMileageKm | MileageReading.ReadingMileageKm : au plus 1 valeur(s). | _:readingMileageKm-da0ef657 |
| `SH:am:MileageReading:am:readingMileageKm#v3` | range | MileageReading.ReadingMileageKm | MileageReading.ReadingMileageKm : bornes {'min_inclusive': '0'}. | _:readingMileageKm-da0ef657 |
| `SH:am:PartReference:am:hasManufacturer#v1` | existence | PartReference [HasManufacturer] | PartReference : au moins 1 relation HasManufacturer. | _:hasManufacturer-90a157f4 |
| `SH:am:PartReference:am:hasManufacturer#v2` | cardinality | PartReference [HasManufacturer] | PartReference : au plus 1 HasManufacturer. | _:hasManufacturer-90a157f4 |
| `SH:am:PartReference:am:hasManufacturer#v3` | allValuesFrom | PartReference [HasManufacturer] | HasManufacturer → am:Brand (sh:class). | _:hasManufacturer-90a157f4 |
| `SH:am:PartReference:am:manufacturerPartNumber#v1` | existence | PartReference.ManufacturerPartNumber | PartReference.ManufacturerPartNumber obligatoire (sh:minCount 1). | _:manufacturerPartNumber-b54fa84b |
| `SH:am:Recall:am:appliesToModel#v1` | existence | Recall [AppliesToModel] | Recall : au moins 1 relation AppliesToModel. | _:appliesToModel-164ac8d9 |
| `SH:am:Recall:am:appliesToModel#v2` | allValuesFrom | Recall [AppliesToModel] | AppliesToModel → am:VehicleModel (sh:class). | _:appliesToModel-164ac8d9 |
| `SH:am:RepairOrder:am:closedAt#v1` | cardinality | RepairOrder.ClosedAt | RepairOrder.ClosedAt : au plus 1 valeur(s). | _:closedAt-b34b4d35 |
| `SH:am:RepairOrder:am:includesOperation#v1` | existence | RepairOrder [IncludesOperation] | RepairOrder : au moins 1 relation IncludesOperation. | _:includesOperation-6aa8ac53 |
| `SH:am:RepairOrder:am:includesOperation#v2` | allValuesFrom | RepairOrder [IncludesOperation] | IncludesOperation → am:ServiceOperation (sh:class). | _:includesOperation-6aa8ac53 |
| `SH:am:RepairOrder:am:openedAt#v1` | existence | RepairOrder.OpenedAt | RepairOrder.OpenedAt obligatoire (sh:minCount 1). | _:openedAt-151b9102 |
| `SH:am:RepairOrder:am:openedAt#v2` | cardinality | RepairOrder.OpenedAt | RepairOrder.OpenedAt : au plus 1 valeur(s). | _:openedAt-151b9102 |
| `SH:am:RepairOrder:am:openedAt#v3` | other | RepairOrder.OpenedAt | RepairOrder.OpenedAt < am:closedAt (sh:lessThan). | _:openedAt-151b9102 |
| `SH:am:RepairOrder:am:performedAt#v1` | existence | RepairOrder [PerformedAt] | RepairOrder : au moins 1 relation PerformedAt. | _:performedAt-ba7fe47e |
| `SH:am:RepairOrder:am:performedAt#v2` | allValuesFrom | RepairOrder [PerformedAt] | PerformedAt → am:Garage (sh:class). | _:performedAt-ba7fe47e |
| `SH:am:Technician:am:worksAt#v1` | existence | Technician [WorksAt] | Technician : au moins 1 relation WorksAt. | _:worksAt-77cb091f |
| `SH:am:Technician:am:worksAt#v2` | allValuesFrom | Technician [WorksAt] | WorksAt → am:Garage (sh:class). | _:worksAt-77cb091f |
| `SH:am:Vehicle:am:hasEngine#v1` | allValuesFrom | Vehicle [HasEngine] | HasEngine → am:Engine (sh:class). | _:hasEngine-79a6ce87 |
| `SH:am:Vehicle:am:ofModel#v1` | existence | Vehicle [OfModel] | Vehicle : au moins 1 relation OfModel. | _:ofModel-7a9d147f |
| `SH:am:Vehicle:am:ofModel#v2` | cardinality | Vehicle [OfModel] | Vehicle : au plus 1 OfModel. | _:ofModel-7a9d147f |
| `SH:am:Vehicle:am:ofModel#v3` | allValuesFrom | Vehicle [OfModel] | OfModel → am:VehicleModel (sh:class). | _:ofModel-7a9d147f |
| `SH:am:Vehicle:am:vin#v1` | existence | Vehicle.Vin | VIN : 17 caractères, sans I, O ni Q | _:vin-3f1140e6 |
| `SH:am:Vehicle:am:vin#v2` | cardinality | Vehicle.Vin | Vehicle.Vin : au plus 1 valeur(s). | _:vin-3f1140e6 |
| `SH:am:Vehicle:am:vin#v3` | pattern | Vehicle.Vin | VIN : 17 caractères, sans I, O ni Q | _:vin-3f1140e6 |
| `SH:am:VehicleModel:am:madeBy#v1` | existence | VehicleModel [MadeBy] | VehicleModel : au moins 1 relation MadeBy. | _:madeBy-888a8ae0 |
| `SH:am:VehicleModel:am:madeBy#v2` | cardinality | VehicleModel [MadeBy] | VehicleModel : au plus 1 MadeBy. | _:madeBy-888a8ae0 |
| `SH:am:VehicleModel:am:madeBy#v3` | allValuesFrom | VehicleModel [MadeBy] | MadeBy → am:Brand (sh:class). | _:madeBy-888a8ae0 |
| `SH:am:VehicleModel:am:modelYear#v1` | range | VehicleModel.ModelYear | VehicleModel.ModelYear : bornes {'min_inclusive': '1886', 'max_inclusive': '2100'}. | _:modelYear-e6b84422 |
| `SH:am:Warranty:am:warrantyDurationMonths#v1` | range | Warranty.WarrantyDurationMonths | Warranty.WarrantyDurationMonths : bornes {'min_inclusive': '0'}. | _:warrantyDurationMonths-0d3f0183 |

## Matérialisations — 1

| Type | Cible | Description | Origine |
|---|---|---|---|
| transitiveClosure | PartOfTransitive | Calculer la fermeture transitive de PartOf (Part → Part) dans PartOfTransitive. | am:partOf |

## Arbitrages

Aucun arbitrage enregistré : toutes les recommandations sont appliquées par défaut.
