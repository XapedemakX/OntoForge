# Revue W3C — L3 moteur de mapping (itération 1)

Relecteur : w3c — 3 nov. 2026. Fichiers relus : `mapping/engine.py`, `rules/{_base,classes,data,objects,keys}.py` (ciblé), `targets/report.py`, `journal/L3/rapport-moteur.md`, `ecarts-oracle.md`, `demo-report-curiosity.md`.

Méthode, hors oracle :
- `analyze()` lancé sur samples/automaint pour les deux cibles (scripts m1.py et m2.py).
- 6 cas adverses (m3.py) : domaine par intersection, inverse d'une propriété symétrique, chaîne de propriétés, classe définie, hasKey avec une propriété objet, propriété de données multivaluée.
- Ordre des chaînes testé avec des noms non alphabétiques.

Scripts dans `/tmp/claude-0/-home-claude/f7ce89f1-126c-5646-9d16-c8cb9a826cdc/scratchpad/`.

Ce qui est bon :
- Neo4j sur automaint : multi-labels, clés métier issues de hasKey (vin, orderNumber…), inverses stockés dans un seul sens.
- Curiosity sur automaint : reverse = nom de l'inverse OWL (Concerns ↔ HasRepairOrder, ReadingOf ↔ HasMileageReading), propriétés héritées présentes sur le type aplati, fermeture transitive de partOf matérialisée.
- Classe définie : booléen ou label calculé, avec la définition lisible. hasKey avec propriété objet : K05 avec clé concaténée ou matérialisée.
- Le paragraphe « hypothèse de monde clos » du rapport est juste et utile.

```
verdict: KO
bloquants (À CORRIGER CE SOIR) :
  - [mapping/rules/_base.py:547] `related=sorted(set(related))` détruit l'ordre des chaînes de propriétés. Or ObjectPropertyChain est une suite ordonnée (SS §9.2.1).
    Cas trap : la matérialisation livrée dans le rapport démo est « VehicleBrand = MadeBy / OfModel », alors que l'ontologie dit ofModel ∘ madeBy. Cas adverse : (zeta alpha) devient « R = Alpha / Zeta (A → C) ». Une chaîne p ∘ p devient [p].
    → Pour O08 (et tout constat dont related est une séquence), garder l'ordre et les doublons : ne trier que les ensembles. objects.py:392 doit lire `v.chains[i]`. Ajouter un test avec des noms non alphabétiques.
  - [mapping/rules/objects.py:88 et réalisation O08] Le constat écrit « :r ≡ :p ∘ :q ». Or owl:propertyChainAxiom est une inclusion : SubObjectPropertyOf(ObjectPropertyChain(p q) r), SS §9.2.1. r peut avoir des assertions directes.
    Côté Neo4j (path_query), l'arête R n'est pas créée du tout : les triplets r assertés sont perdus. Côté Curiosity, R est marquée derived=True.
    → Écrire « ⊑ » dans le texte. Garder R comme relation stockée (données assertées) dans les deux cibles. La requête de chemin (Neo4j) ou la matérialisation (Curiosity) vient en complément.
  - [mapping/rules/data.py:53, objects.py:31 + construction] Le domaine complexe `domain_expr` est ignoré, et la propriété disparaît sans aucun constat. Cas : `:p rdfs:domain (A ⊓ B)` ne donne aucune propriété ni sur A ni sur B ; même chose pour une propriété objet (aucune arête). C'est une perte silencieuse, alors que rapport-moteur.md affirme qu'il n'y en a pas.
    → Intersection : rattacher la propriété à chaque conjoint nommé (domain(A ⊓ B) ⊨ domain(A) et domain(B), inférence correcte) et émettre un constat review. Autre expression complexe : property shape d'usage, ou constat G01 lost. Ajouter le cas au test « aucune perte silencieuse ».
  - [mapping/rules/data.py:333-335, objects.py:425-441 ; Curiosity, héritage aplati] Les restrictions d'une sous-classe s'appliquent à tout le type aplati. Sur automaint :
    - Party.BrandName passe à required=True (Brand ⊑ brandName exactly 1) : à l'ingestion, chaque Customer, Garage ou Technician serait rejeté ;
    - les validations « Party.BrandName exactly 1 », « Party WorksAt exactly 1 » (vient de Technician) et « Vehicle HasEngine some ICE » (vient de CombustionVehicle) n'ont aucun filtre de discriminant.
    → Quand la classe de la restriction n'est pas la racine du type aplati : ne pas toucher required ni la cardinalité de l'arête, et mettre dans params `discriminator` + `values` (la sous-classe et ses descendantes). Pour un filler aplati (InternalCombustionEngine dans Engine), ajouter la condition EngineKind ∈ {…}.
  - [mapping/rules/objects.py:434-435] Deux restrictions `some` sur la même arête (ElectricVehicle et CombustionVehicle ⊑ hasEngine some …) donnent cardinality.out = "1", c'est-à-dire exactement un. Or aucune restriction max n'existe dans l'ontologie (Curiosity : HasEngine = 1 ; Neo4j : 0..*).
    → `out = {"0..*": "1..*", "1..*": "1..*", "0..1": "1", "1": "1"}[out]`. Avec le bloquant précédent, une restriction qui vient d'une sous-classe aplatie ne modifie plus la cardinalité de l'arête.
non-bloquants (PEUVENT ATTENDRE VENDREDI) :
  - Bruit d'arbitrage sur automaint, une ontologie propre (Curiosity : 117 review/lost) :
    - D13 ×25 : un `max 1` sur une donnée donne une propriété scalaire, ce qui est déjà le choix par défaut : à passer en auto. `exactly 1` donne required (renforcement monde clos) : une seule décision groupée suffit.
    - O09 ×10 : justifié (Curiosity n'a pas de contrainte de cardinalité), mais à grouper. Le titre « Cardinalité maximale » est faux pour `exactly`.
    - K03 ×9 : « pas de clé, uri » devrait être auto.
    - I01 ×4 : redondant avec C08 (FuelType).
    - C02 ×10 : review est légitime (c'est un vrai choix de modèle, y compris en héritage simple), mais il faut une décision par racine de hiérarchie (Party, Vehicle, Engine), pas par classe. Sinon on peut aplatir Brand tout en gardant Organization comme type.
  - [rules/classes.py C02] Le libellé `flatten_into_leaves` est trompeur : automaint aboutit à un seul type Party avec un discriminant à 7 valeurs, ce qui est un repli sur la racine concrète. Renommer l'option, ou corriger le texte d'impact.
  - C07 en `lost` : en Curiosity, deux node types distincts ou un discriminant mono-valué garantissent la disjonction par construction. Le rapport range pourtant ces cas dans « Perdu (aucun équivalent natif) », ce qui induit l'architecte en erreur. Passer en auto (« garanti par construction »), sauf si les classes sont fusionnées avec des types multiples. Écart à l'oracle à tracer dans ecarts-oracle.md.
  - Arêtes après aplatissement : MadeBy VehicleModel → Party (portée Brand), WorksAt Party → Party, PerformedAt → Party. Le typage des extrémités n'est pas validé : il faut une validation « extrémité = discriminant ∈ {…} ». C'est lié au 4e bloquant ; à faire ce soir si le temps le permet.
  - inverse + symétrique : knownBy inverseOf knows avec knows symétrique implique knownBy ≡ knows. La note O04 pourrait le dire (aujourd'hui elle indique seulement « inverse de »).
  - Rapport :
    - toutes les validations affichent l'id `v1` (report.py:168) : afficher l'id complet, ou au moins règle + sujet + n° ;
    - le rapport démo porte sur trap : générer aussi demo-report-automaint, plus parlant pour un architecte ;
    - FuelType en nœuds de référence n'a pas de propriété label : les libellés fr/en des individus sont perdus sans le dire.
  - Les noms de reverse « XxxInverse » ne sont pas lisibles : quand une étiquette inverse existe, l'utiliser.
skill: owl-to-property-graph — ajouter :
  - « chaîne = inclusion ordonnée (⊑), jamais ≡ ; ne jamais trier related » ;
  - « domain(A ⊓ B) ⇒ domaine de chaque conjoint » ;
  - « restriction d'une sous-classe aplatie ⇒ validation filtrée par discriminant, jamais required ni cardinalité d'arête sur le type racine ».
```
