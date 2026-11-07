# Revue W3C — L13 (itération 1)

Relecteur : w3c — 3 nov. 2026. Fichiers relus : `journal/L13/rapport.md`, `mapping/reverse_names.py`, les profils (decimal), et la section L13 d'`ecarts-oracle.md`. J'ai exécuté le moteur sur automaint et sur trap (Curiosity), puis contrôlé par script les collisions entre les reverse dérivés et les noms des propriétés OWL.

```
verdict: KO
bloquants:
  - [mapping/reverse_names.py règle 3 + collisions] Un nom de reverse dérivé reprend le nom local d'une propriété OWL existante qui n'est pas l'inverse de l'arête. Le schéma présente alors comme « am:hasRepairOrder » une relation qui n'est pas am:hasRepairOrder. Cas relevés par script :
    - automaint : AssignedTo (RepairOrder→Technician) et PerformedAt (→Garage) ont pour reverse « HasRepairOrder ». Or am:hasRepairOrder existe (Vehicle→RepairOrder, inverse de concerns) ;
    - trap : CheckedBy et PerformedAt ont pour reverse « HasRepairOrder » ; InstanceOfReference (Part→PartReference) a pour reverse « HasPart », alors que am:hasPart existe (inverse de partOf, Vehicle→Part).
    En Curiosity, les noms d'arêtes sont des constantes globales (Edges.X) : un lecteur ou une requête qui utilise Edges.HasRepairOrder mélange trois relations. Le cas « HasVehicle » pour l'inverse de OwnedBy est en revanche acceptable : aucune propriété am:hasVehicle n'existe.
    → Avant de retenir un nom dérivé, l'exclure s'il est égal (sans tenir compte de la casse) au nom local d'une propriété de l'ontologie, sauf si c'est l'inverse déclaré de l'arête. Se replier alors sur `<Arête>Of<Source>` (ex. PerformedAtOfRepairOrder) ou sur la forme participe (« AssignedRepairOrder »). Ajouter les 3 cas à test_reverse_names.py.
non-bloquants:
  - Decimal : correct. xsd:decimal → Decimal sans perte en Curiosity (C# decimal, 28-29 chiffres significatifs : un xsd:decimal au-delà de cette précision reste théoriquement à perte, à mentionner dans la note). En Neo4j, Float avec perte (D05). owl:real et owl:rational restent Float avec perte dans les deux cibles, ce qui est juste. Le `GetDouble` dans les requêtes C# perd la précision gagnée : remplacer par une API decimal confirmée (À VÉRIFIER), ou le noter.
  - xsd:integer → Integer en Curiosity reste lossy (64 bits) : cohérent. Une alternative Decimal pour les entiers non bornés pourrait être proposée.
  - I01/C08 : la suppression du doublon est justifiée. Un membre d'owl:oneOf est porté par C08 ; le must_not I01 sur am:Petrol est correct. I01 reste émis pour les membres d'un AllDifferent seul, ce qui est juste : pas d'énumération fermée.
  - Les reverse au participe (« IncludedBy », « AddressedBy », « PrescribedBy ») sont corrects. « HasPart » pour l'inverse d'InstalledIn (Part→Vehicle) sur automaint ne trompe pas (pas d'am:hasPart dans automaint), mais il serait bloqué par la règle ci-dessus sur trap.
  - La docstring de profiles/curiosity.py::reverse_name mentionne encore le suffixe Inverse : à aligner (agent curiosity).
skill: curiosity-schema-design — « un nom de reverse dérivé ne doit jamais coïncider avec une propriété OWL qui n'est pas l'inverse déclaré ».
```
