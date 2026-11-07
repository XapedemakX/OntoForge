# OntoForge — démarrage rapide : cœur de l'ontologie AutoMaint (maintenance automobile) en DSL.
# Coller ce texte dans l'éditeur DSL pour obtenir les classes, relations et attributs principaux.
# Les ajouts du fichier automaint.ttl (définitions, datatype ModelYear, métadonnées) ne sont pas exprimables en DSL.
@prefix am: <https://w3id.org/ontoforge/automaint#>
@base <https://w3id.org/ontoforge/automaint#>

# --- Acteurs ---------------------------------------------------------------
Party "Partie"@fr "Party"@en doc "Personne ou organisation intervenant dans la maintenance."@fr
Person "Personne"@fr "Person"@en
Organization "Organisation"@fr "Organization"@en
Person < Party
Organization < Party
Person <> Organization
Customer "Client"@fr "Customer"@en
Technician "Technicien"@fr "Technician"@en
Customer < Person
Technician < Person
Garage "Garage"@fr "Garage"@en
Brand "Marque"@fr "Brand"@en
Garage < Organization
Brand < Organization
Party.displayName : string [1] "nom affiché"@fr "display name"@en

# --- Véhicules -------------------------------------------------------------
Vehicle "Véhicule"@fr "Vehicle"@en doc "Véhicule identifié par son VIN, suivi en atelier."@fr
ElectricVehicle "Véhicule électrique"@fr "Electric vehicle"@en
CombustionVehicle "Véhicule thermique"@fr "Combustion vehicle"@en
ElectricVehicle < Vehicle
CombustionVehicle < Vehicle
VehicleModel "Modèle de véhicule"@fr "Vehicle model"@en
Engine "Moteur"@fr "Engine"@en
InternalCombustionEngine "Moteur thermique"@fr "Internal combustion engine"@en
ElectricMotor "Moteur électrique"@fr "Electric motor"@en
InternalCombustionEngine < Engine
ElectricMotor < Engine
FuelType : {Diesel, Petrol, Electric, Hydrogen} "Carburant"@fr "Fuel type"@en
Vehicle.vin : string [1] key "VIN"@fr "VIN"@en
Vehicle.registrationNumber : string [0..1] "immatriculation"@fr "registration number"@en
Vehicle.firstRegistrationDate : dateTime [0..1] "date de première mise en circulation"@fr "first registration date"@en
VehicleModel.modelName : string [1] "nom du modèle"@fr "model name"@en
VehicleModel.modelYear : integer [0..1] "année modèle"@fr "model year"@en
Engine.displacementCc : integer [0..1] "cylindrée (cm3)"@fr "displacement (cc)"@en
Engine.powerKw : decimal [0..1] "puissance (kW)"@fr "power (kW)"@en
Brand.brandName : string [1] key "nom de marque"@fr "brand name"@en
Vehicle -ofModel-> VehicleModel [1] "a pour modèle"@fr "has model"@en
VehicleModel -madeBy-> Brand [1] "fabriqué par"@fr "made by"@en
Vehicle -hasEngine-> Engine "a pour moteur"@fr "has engine"@en
Vehicle -ownedBy-> Customer "appartient à"@fr "owned by"@en
Engine -usesFuel-> FuelType "utilise le carburant"@fr "uses fuel"@en

# --- Pièces ----------------------------------------------------------------
Part "Pièce"@fr "Part"@en
PartReference "Référence de pièce"@fr "Part reference"@en
Vehicle <> Part
PartReference.manufacturerPartNumber : string [1] "référence fabricant"@fr "manufacturer part number"@en
PartReference.unitPrice : decimal [0..1] "prix unitaire"@fr "unit price"@en
PartReference -hasManufacturer-> Brand [1] "fabriquée par"@fr "manufactured by"@en
Part -instanceOf-> PartReference [1] "est une instance de"@fr "instance of"@en
Part -installedIn-> Vehicle "installée dans"@fr "installed in"@en
Part -partOf-> Part transitive "composant de"@fr "part of"@en

# --- Atelier ---------------------------------------------------------------
ServiceOperation "Opération de service"@fr "Service operation"@en
MaintenancePlan "Plan d'entretien"@fr "Maintenance plan"@en
RepairOrder "Ordre de réparation"@fr "Repair order"@en
DiagnosticTroubleCode "Code défaut"@fr "Diagnostic trouble code"@en
ServiceOperation.operationCode : string [1] key "code opération"@fr "operation code"@en
ServiceOperation.standardDurationMin : integer [0..1] "durée standard (min)"@fr "standard duration (min)"@en
MaintenancePlan.intervalKm : integer [0..1] "intervalle (km)"@fr "interval (km)"@en
MaintenancePlan.intervalMonths : integer [0..1] "intervalle (mois)"@fr "interval (months)"@en
RepairOrder.orderNumber : string [1] key "numéro d'ordre"@fr "order number"@en
RepairOrder.openedAt : dateTime [1] "ouvert le"@fr "opened at"@en
RepairOrder.closedAt : dateTime [0..1] "clos le"@fr "closed at"@en
DiagnosticTroubleCode.dtcCode : string [1] key "code"@fr "code"@en
RepairOrder -concerns-> Vehicle [1] inverse hasRepairOrder "concerne"@fr "concerns"@en
hasRepairOrder "a pour ordre de réparation"@fr "has repair order"@en
RepairOrder -performedAt-> Garage [1] "réalisé dans"@fr "performed at"@en
RepairOrder -assignedTo-> Technician "affecté à"@fr "assigned to"@en
RepairOrder -includesOperation-> ServiceOperation [1..*] "comprend l'opération"@fr "includes operation"@en
ServiceOperation -usesPart-> PartReference "utilise la référence"@fr "uses part reference"@en
ServiceOperation -addresses-> DiagnosticTroubleCode "traite le code"@fr "addresses code"@en
Technician -worksAt-> Garage [1] "travaille à"@fr "works at"@en
MaintenancePlan -plannedFor-> VehicleModel [1] "prévu pour"@fr "planned for"@en
MaintenancePlan -prescribes-> ServiceOperation [1..*] "prescrit"@fr "prescribes"@en
Vehicle -hasActiveCode-> DiagnosticTroubleCode "a le code actif"@fr "has active code"@en

# --- Kilométrage, rappels, garanties --------------------------------------
MileageReading "Relevé kilométrique"@fr "Mileage reading"@en
Recall "Rappel constructeur"@fr "Recall"@en
Warranty "Garantie"@fr "Warranty"@en
MileageReading.readingMileageKm : decimal [1] "kilométrage relevé"@fr "mileage (km)"@en
MileageReading.readingDate : dateTime [1] "date du relevé"@fr "reading date"@en
Recall.recallNumber : string [1] key "numéro de rappel"@fr "recall number"@en
Recall.issuedAt : dateTime [0..1] "émis le"@fr "issued at"@en
Warranty.warrantyDurationMonths : integer [1] "durée de garantie (mois)"@fr "warranty duration (months)"@en
Warranty.warrantyMaxKm : integer [0..1] "kilométrage maximal"@fr "maximum mileage"@en
MileageReading -readingOf-> Vehicle [1] inverse hasMileageReading "relevé de"@fr "reading of"@en
Recall -appliesToModel-> VehicleModel [1..*] "concerne le modèle"@fr "applies to model"@en
Recall -concernsPart-> PartReference "concerne la référence"@fr "concerns part reference"@en
Warranty -covers-> Vehicle [1] "couvre"@fr "covers"@en
