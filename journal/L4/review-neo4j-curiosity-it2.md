# Revue croisée it2 — relecteur neo4j, cible Curiosity (4 bloquants it1)

verdict: OK

C# régénéré sur pg_neo4j_automaint.json et pg_curiosity_automaint.json ; tests curiosity (27) verts.

bloquants:
  (aucun) — it1 : (1) clé composite OK : `%`→`%25` puis `|`→`%7C`, composants nuls/vides rejetés AVANT WithComputedKey (Connector.cs IngestVehicleModel) ; (2) arêtes OK : `COLLEAGUE_OF` → `ColleagueOf` aller = retour (Link(a,b,X,X)), `HAS_MODEL`→`HasModel`/`ModelOf`, constantes uniques, `Nodes`/`LinkSet` en tuples ; (3) validations OK : chaque Vxx produit Report, Guaranteed ou NotChecked (avertissement runtime + compteur) sur les deux fixtures ; V04 (`default`) et V08 (liste) désormais implémentés ; (4) tests ajoutés.

non-bloquants:
  - V12 (neo4j) est incohérent : `NotChecked` dans ValidateElectricVehicle (n'émet que si un ElectricVehicle est ingéré) mais `Guaranteed("V12","contrôlé à l'ingestion…")` dans CheckGraph, ce qui affirme à tort un contrôle. Émettre uniquement NotChecked (au niveau CheckGraph) ou contrôler le discriminant.
  - Le mélange de constantes `OWNS`/`COVERS` (un mot, restées en majuscules) et `ColleagueOf` (PascalCase) reste hétérogène ; cosmétique, à documenter.
  - V15 (closed) et V16/V13 (other) restent non contrôlées : acceptable car signalées à l'exécution, à lister dans le rapport du lot.
  - Appels Curiosity.Library toujours À VÉRIFIER (AddOrUpdate, Link 4 args, SetAutoCommitCost).

skill: rien de plus que la checklist déjà complétée ; ajouter « une validation garantie ne doit pas prétendre à un contrôle inexistant ».
