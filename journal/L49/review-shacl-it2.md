verdict: OK
bloquants:
  (aucun)
vérifié:
  - Bloquant it1 corrigé : `_Gen.deactivate_deprecated_properties` (`shacl/owl_to_shacl.py:309-326`) est appelée dans `run()` après les classes et les propriétés. Elle pose `sh:deactivated true` sur toute property shape, en ligne ou autonome, dont le chemin (y compris un chemin composé, par récursion sur `args`) passe par une propriété dépréciée, avec la note `[IGNORÉ] … propriété dépréciée`.
  - Validation réelle avec pySHACL : `Car ⊑ ≥1 vin` et `Car ⊑ =1 servicedBy`, les deux propriétés dépréciées, donnée `ex:c1 a ex:Car` sans valeur → `conforms: True`. Une fois les propriétés « ré-approuvées » → `conforms: False`. Les shapes `VehicleShape-vin`, `CarShape-vin` et `CarShape-servicedBy` sont désactivées ; la shape d'usage de l'inverse non déprécié `services` reste active, ce qui est correct.
  - Exemple trap par l'API (`appliesToModel` et `claimDate` dépréciées) : `ServiceBookletShape` (node shape), `MaintenancePlanShape-appliesToModel` et `WarrantyClaimShape-claimDate` sont désactivées, avec trois notes `[IGNORÉ]`.
  - Node shapes des classes dépréciées : toujours désactivées (comportement antérieur, conservé).
décision (cas « gardée avec drapeau ») : **non bloquant**. Motifs :
  1. La génération des shapes part de l'ontologie et ne dépend pas de la cible. Un même projet peut garder la classe avec drapeau pour Curiosity et l'exclure pour Neo4j, donc il n'existe pas un arbitrage A03 unique à suivre.
  2. L'échec est permissif : une shape désactivée ne rejette aucune donnée, elle cesse de valider. C'est l'inverse du défaut it1, qui rejetait toute donnée conforme.
  3. C'est annoncé : note `[IGNORÉ]` à la génération, et le guide écrit « Les shapes SHACL générées d'une classe ou d'une propriété dépréciée sont désactivées ».
  4. C'est réversible : `sh:deactivated` se retire dans le Turtle des shapes (écran Fichiers) ; l'écran Shapes se contente de l'afficher (pastille « désactivée »).
non-bloquants:
  - Guide fr/en (`utilisateur.md:316`) : ajouter que la désactivation vaut **même si l'entité est gardée avec drapeau**, et que les données encore générées pour elle ne sont alors plus validées (réactiver la shape au besoin). Une demi-phrase suffit.
  - Plus tard : si toutes les cibles arbitrées gardent l'entité avec drapeau, produire une shape active en `sh:severity sh:Warning` avec `sh:message` « dépréciée » plutôt que `sh:deactivated`.
  - Rappel it1, toujours ouvert : `set_deprecated` ne retouche pas les shapes déjà présentes dans le projet (il faut les régénérer). Un avertissement « shapes à régénérer » renvoyé par l'opération serait utile.
  - Les property shapes imbriquées dans `sh:node` ou `sh:qualifiedValueShape` d'une autre shape ne sont pas parcourues. Le générateur n'en produit pas aujourd'hui ; à garder en tête si cela change.
skill: shacl-modeling : la désactivation d'une shape pour dépréciation suit l'ontologie, pas la cible ; documenter que « garder avec drapeau » côté cible ne réactive pas la validation.
