# L13 — reliquats de l'itération 1 (lead)

Tests : 462 verts (442 + 20 nouveaux). `npm run build` OK.

1. **Decimal** (D-L13-01, `journal/decisions.md`) : `PGType` + `Decimal`. Curiosity : xsd:decimal -> `Decimal` (C# `decimal`, sans perte, plus de D05 ; bornes de plage suffixées `m`). Neo4j : arbitrage = `Float` avec perte signalée (D05), alternatives STRING/centimes dans la note. GraphQL : scalaire `Decimal`. Requêtes C# : `GetDouble` (pas d'API `GetDecimal` confirmée, À VÉRIFIER). Oracle : f-D05a `absent` côté Curiosity (`journal/L3/ecarts-oracle.md`). Tests : `tests/test_decimal.py`.
2. **Reverse** : `mapping/reverse_names.py` (règles documentées en tête de fichier) : verbe-s -> `CoveredBy`/`UsedBy` ; participe/préposition -> `Has<Source>` (OwnedBy -> HasVehicle) ; `XxxTransitive` -> `HasPartTransitive` ; sinon `<Nom>Of<Source>` ; collisions résolues par type d'arrivée. Plus aucun `…Inverse` sur automaint ni trap. Tests : `tests/test_reverse_names.py`.
3. **I01/C08** : I01 n'est plus émis pour un membre d'owl:oneOf ; C08 `reference_nodes` crée désormais lui-même les nœuds de référence. Oracle : f-I01 retiré + must_not I01 sur am:Petrol (tracé dans ecarts-oracle.md) ; le test d'oracle comprend `absent: true`.
4. **Diagramme** (`frontend/src/screens/Model.tsx`, composant Diagram + styles `.cy-zoom`) : police nœuds 14 px / relations 12 px à l'écran (compensée au zoom d'ajustement), fit au chargement, molette, boutons + / − / Ajuster. Non vérifié visuellement (pas de navigateur).
5. **Script .NET** : `tools/dotnet/check-curiosity.ps1` + `README.md` (classlib net8.0 temporaire, `dotnet add package Curiosity.Library`, build, erreurs listées). Non exécuté ici (pas de SDK/Windows) ; le nom NuGet du package est À VÉRIFIER.

Reste : revue W3C du moteur it2 (autre agent) ; docstring de `profiles/curiosity.py::reverse_name` encore mentionne le suffixe `Inverse` (propriété d'un autre agent, le moteur le remplace après coup).

## Itération 2 (revue w3c it1)
- **Bloquant corrigé** : `uniquify_reverses(..., reserved=...)` exclut tout nom dérivé égal (insensible à la casse) à une propriété OWL (objet ou données) ou à un nom d'arête/retour explicite ; repli `<Arête>Of<Source>` (ex. `PerformedAtOfRepairOrder`). Le moteur passe les noms locaux des propriétés de l'ontologie. Tests ajoutés : cas synthétique AssignedTo/hasRepairOrder, et contrôle automaint + trap (aucun reverse égal à une propriété OWL hors inverse déclaré ; trap : `InstanceOfReference` != `HasPart`, `PerformedAt` != `HasRepairOrder`).
- **Non-bloquants** : requêtes C# Decimal -> `GetDouble` marqué `# À VÉRIFIER` (API decimal non confirmée) ; docstring de `profiles/curiosity.py::reverse_name` alignée. Note de précision (decimal C# 28-29 chiffres, xsd:decimal plus long théoriquement à perte) non ajoutée dans les profils.
- Suite : 475 tests verts, aucun test assistant en échec.
