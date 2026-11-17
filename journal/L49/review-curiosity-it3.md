verdict: OK
bloquants: []
vérifié (cible Curiosity, rejoué en direct sur l'exemple de test et sur trap enrichi, puis en `lang=en` par `localize_pg_for_export`) :
  - Bloquant it2 corrigé. `Car ⊑ ∃locatedNear.Garage`, `Garage` dépréciée et exclue : A03 liste `locatedNear` (« Exclure entraîne la perte de : … »), O02 passe en `lost` avec « Non générée : ex:Garage est dépréciée et exclue (A03:…) », aucune arête `LocatedNear`. Même résultat sur trap avec `keptIn` (restriction vers `ServiceBooklet`) : A03 liste `keptIn`, O02 `lost`, rapport colonne « Entraîne la perte de ».
  - Union partielle `bookletOrPlan` (Vehicle → MaintenancePlan ⊔ ServiceBooklet) : A03 « En partie : am:bookletOrPlan », O03 reste `review` avec « Générée en partie… », arête vers `MaintenancePlan` générée, rapport « en partie : am:bookletOrPlan ». Plus listée comme perdue.
  - Inverse : `hostedIn` (inverse de `hosts`, `hosts` : Garage → Car) est listée et passe en `lost` (O04) avec sa primaire ; aucune arête.
  - Attribut dont tous les domaines sont exclus (`openingHours`, `bkAttr`) : D01 `lost`, propriété absente. Attribut à deux domaines (`gname`, Garage + Vehicle) : perte partielle, propriété générée sur `Car` (Vehicle).
  - Gardée avec drapeau : A03 sans « perte », `related` vide, constats O01/O02/D01 inchangés, arêtes et propriétés générées, colonne « — ».
  - Anglais : « Excluding also removes », « Partly: », « Partly generated: the endpoints towards … », « Not generated: … ». Aucun reste français dans les constats ni le rapport.
  - `apply_m01` : `git diff master -- annotations.py` ne montre `apply_m01` qu'en contexte (corps identique à master, ligne par ligne). Seul écart : une seule ligne vide avant `def apply_m01` au lieu de deux (cosmétique).
  - Tests : `-k "l49 or mapping or targets"` 235 réussis ; suite complète 1337 réussis.
non-bloquants:
  - [annotations.py:153 et ~182] PEP 8 : deux lignes vides superflues avant `_endpoints` (l. 114-115) et une seule avant `def apply_m01` (E303/E302). À nettoyer au passage, sans toucher au corps de `apply_m01`.
  - `_endpoints` ignore les cas où la construction saute une propriété (`prop_alias`, `skip_edge`, rôles de dé-réification R01) : une propriété sans arête propre peut être déclarée « perdue » à tort (ou l'inverse pour les arêtes de dé-réification, construites à partir des portées des rôles). Je n'ai pas pu produire de faux positif sur les exemples ; à surveiller si un constat étrange apparaît sur une ontologie réifiée.
  - Toujours ouvert depuis it1/it2 : `curiosity.generate` appelé sans `localize_pg_for_export` mélange `[DEPRECATED]` (Edges.cs) et `[DÉPRÉCIÉ]` (Schema.cs) ; `Report("deprecated", …)` dans le connecteur ; remplaçant dans `<remarks>`. `[Obsolete]` : non posé (décision it1), à VÉRIFIER auprès de Curiosity.Library.
skill: curiosity-schema-design : une perte induite se rejoue avec cinq cas (restriction O02, union partielle, inverse, attribut à domaines tous exclus, entité gardée avec drapeau) et dans les deux langues.
