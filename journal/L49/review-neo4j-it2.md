verdict: KO
bloquants:
  - [backend/ontoforge/mapping/rules/annotations.py:118-137 (exclusion_losses)] Même défaut que dans la revue curiosity, vérifié aussi en cible Neo4j : une relation sans domaine ni portée, résolue par restriction (O02, `Car ⊑ ∃locatedNear.Garage`), vers une classe dépréciée et exclue, ne produit aucun `[:LOCATED_NEAR]`. Aucun constat ne le dit : O02 reste `review` avec « résolution : ex:Car → ex:Garage », et A03 et le rapport ne listent rien. → calculer les pertes avec `objects.resolve` (même résolution que `build_edges`), avec un test du cas O02.
vérifié:
  - Bloquant it1 n°1 corrigé. Exemple trap, `ServiceBooklet`, `claimDate` et `appliesToModel` gardées avec drapeau, en direct et par l'API, en fr et en en :
    - `schema.cypher` : `// [DÉPRÉCIÉ] :ServiceBooklet — type déprécié gardé avec drapeau (A03) : ne plus y créer de données.` et `// [DÉPRÉCIÉ] WarrantyClaim.claimDate — …`, avant les contraintes.
    - `ingest.cypher` : `// [DÉPRÉCIÉ] :ServiceBooklet`, `// [DÉPRÉCIÉ] claimDate` et `// [DÉPRÉCIÉ] [:APPLIES_TO_MODEL]`, en tête des blocs.
    - `README-neo4j.md` : `` `:ServiceBooklet` **[DÉPRÉCIÉ]** ``, `claimDate [DÉPRÉCIÉ]`, et la remarque `[DÉPRÉCIÉ]` sur `:APPLIES_TO_MODEL`.
    - `model.mmd` : `<<deprecated>>`, `note for WarrantyClaim "[DÉPRÉCIÉ] claimDate"` et `APPLIES_TO_MODEL [DÉPRÉCIÉ]`.
    - En anglais, `[DEPRECATED]` partout, sans reste français. Exclusion par défaut : aucune marque et aucun `:ServiceBooklet` ingéré.
  - Bloquant it1 n°2 corrigé pour les extrémités déclarées : `hasBooklet` et `bookletRef` sont listées dans A03 et dans le rapport, et leurs O01 et D01 passent en `lost`.
  - Tests : suite complète, 1335 réussis.
non-bloquants:
  - Union (`bookletOrPlan` → `MaintenancePlan ⊔ ServiceBooklet`) : A03 annonce la perte alors que `[:BOOKLET_OR_PLAN]` vers `MaintenancePlan` est généré. La perte est partielle (voir revue curiosity).
  - `model.mmd` : `<<abstract deprecated>>` (deux mots dans un stéréotype) et `[` `]` dans l'étiquette d'une relation de `classDiagram`. D'après la grammaire Mermaid, l'annotation `<<…>>` et le texte après `:` sont libres, mais je n'ai pas pu le rendre ici (Mermaid n'est pas installé) : **À VÉRIFIER** au rendu. Repli possible : `deprecated` sans crochets dans l'étiquette.
  - Dans la table des relations du README, une **propriété** de relation dépréciée n'est pas marquée (seule la relation l'est). Le cas est rare.
  - Un type abstrait déprécié n'a pas de marque dans `ingest.cypher` (on sort avant). C'est cohérent, puisqu'il n'est pas ingéré.
  - Toujours ouvert depuis it1 : une requête de détection des nœuds dépréciés restants dans `validation.cypher`.
skill: neo4j-schema-design : un marqueur de dépréciation se vérifie dans chacun des cinq fichiers et dans les deux langues ; une perte induite se calcule avec la résolution d'extrémités de la construction.
