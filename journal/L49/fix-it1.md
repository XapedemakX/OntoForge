# L49 : corrections de l'itération 1 (pilote w3c)

Revues : `review-*-it1.md` (w3c et scout OK ; query, shacl, curiosity, neo4j, doc KO, 8 bloquants). Tests : `cd backend && /home/claude/venv/bin/python -m pytest -q` : 1335 réussis, 0 échec, `npm run build`, recette `BACKEND_PORT=9149 FRONT_PORT=5149 node tools/recette/l49_bonnes_pratiques.mjs` : 14/14.

## Bloquants

| Revue | Bloquant | Fait |
|---|---|---|
| query | Annuler une version laisse l'entrée dans `releases.json` et bloque le réenregistrement | Option (a). L'entrée du journal s'appelle `version <x>` ; annuler la retire de `releases.json` (gardée dans `releases-undone.json`), rétablir la remet, sous `history.lock()` (`releases.on_history`, appelé par `api/editing._swap`). Une nouvelle version vide les versions rétablissables. Test API `test_api_undo_release_removes_entry_and_allows_rerecording` (annuler → historique vide → rétablir → annuler → réenregistrer 1.0.0) ; recette R13. |
| shacl | Une propriété dépréciée garde une property shape active (`minCount`) | `_Gen.deactivate_deprecated_properties` : toute property shape (en ligne ou autonome) dont le chemin passe par une propriété dépréciée reçoit `sh:deactivated true`, avec la note `[IGNORÉ] … propriété dépréciée`. Les node shapes des classes dépréciées l'étaient déjà. Test `test_deprecated_property_shape_is_deactivated`. |
| curiosity | `[DÉPRÉCIÉ]` absent des relations dans `Edges.cs` | `_edges_cs` préfixe le commentaire de l'arête aller **et** de l'arête retour (`[DÉPRÉCIÉ]` / `[DEPRECATED]` selon la langue). `[Obsolete]` non posé (risque sur `CreateEdgeSchemaAsync(typeof(Edges))`, À VÉRIFIER). Test sur le fichier généré ; recette R14. |
| curiosity, neo4j | Exclure une classe dépréciée supprime en silence les relations non dépréciées qui la visent | `annotations.after_plan` (appelé par le moteur après les décisions) : les propriétés objet non dépréciées dont une extrémité nommée est exclue et les propriétés de données dont tous les domaines nommés sont exclus s'ajoutent à `related` de A03, le détail dit « Exclure entraîne la perte de : … », et leur constat de base (O01, D01) passe de `auto` à `lost` avec la raison (« Non générée : X est dépréciée et exclue »). Rapport : colonne « Entraîne la perte de ». Rien de tout cela quand la classe est gardée avec drapeau. Test `test_deprecated_entity_end_to_end`. |
| neo4j | Aucune marque dans `schema.cypher`, `ingest.cypher`, README, `model.mmd` | `// [DÉPRÉCIÉ] :Label …` et `// [DÉPRÉCIÉ] Label.prop …` dans `schema.cypher` ; `// [DÉPRÉCIÉ] :Label`, `// [DÉPRÉCIÉ] prop`, `// [DÉPRÉCIÉ] [:REL]` avant les blocs d'`ingest.cypher` ; marque dans les tableaux nœuds, propriétés et relations du README ; stéréotype `<<deprecated>>`, note pour les propriétés et suffixe sur l'étiquette de relation dans `model.mmd`. Test sur le texte généré (fr et en) ; recette R14. |
| doc | « L'opération s'annule comme une autre » inexact | Phrase réécrite (fr/en) après le correctif : l'annulation retire les annotations et la version, rétablir la remet ; aide de la carte Versions mise à jour. |
| doc | « Générée marquée [DÉPRÉCIÉ] » faux pour Neo4j et les relations Curiosity | Vrai désormais ; guide (fr/en) et CONTRACTS §18 précisent où apparaît le drapeau dans chaque cible, les pertes induites et la désactivation des shapes. |

## Non-bloquants traités
- query : `releases.json` écrit **avant** le projet, entrée retirée si l'écriture du projet échoue.
- query : `has_keys` comparé comme ensemble d'ensembles (SS §9.5), `chains` comme ensemble de listes ordonnées (SS §9.2.4) ; test.
- query : une dépréciation ne produit plus qu'une ligne (statut et remplaçant rattachés) ; les déclarations de propriétés d'annotation posées par l'enregistrement ou la dépréciation ne comptent plus.
- query : sans changement, `level: null`, `unchanged: true`, bouton « Enregistrer » désactivé sauf numéro saisi, message « Aucun changement depuis… ».
- query : numéro plus faible que le niveau des changements → `downgraded: true`, avertissement dans la note et dans l'historique ; test.
- query : limite de 30 versions signalée sous l'historique.
- doc : `vs:term_status` présenté comme « vocabulaire publié par le W3C, non normatif » (CONTRACTS, D-L49-01, rapport) ; résultat des tests remplacé (venv du projet).
- Traductions anglaises des nouveaux fragments du moteur (pertes induites, note SHACL).

## Non retenus (pour plus tard)
- shacl : shape active en `sh:Warning` pour une classe gardée avec drapeau (aujourd'hui désactivée dès qu'elle est dépréciée, quel que soit l'arbitrage, car la génération des shapes ne dépend pas de la cible) ; `set_deprecated` ne retouche pas les shapes déjà présentes (à régénérer).
- curiosity : `[Obsolete]` sur les constantes, `Report("deprecated", …)` dans le connecteur, remplaçant dans `<remarks>` ; traduction du drapeau lors d'un appel direct à `generate(..., lang="en")` sans `localize_pg_for_export` (le drapeau des arêtes, lui, suit déjà la langue).
- neo4j : requête de détection des nœuds dépréciés restants dans `validation.cypher`.
- CONTRACTS : la renumérotation §18 / §19 avec L48 est faite à la fusion par le coordinateur.
