# Corrections de recette it2 (lot L14) — lead, 4 nov. 2026

Résultat : pytest **551 passés** ; `npm run build` OK ; recette API **38/38**, UI **30/30**.

## 1. SHACL piège : 9 -> 8 (D-L14-01)
- Pas une perte d'aller-retour ShapesModel : `parse_shapes(serialize_shapes(shapes))` donne bien 8.
- Cause : le chemin projet passe l'`OntoModel` entier comme `ont_graph` ; pySHACL le fusionne aux données, donc les **individus de l'ontologie** (`trap.ttl` : `ro_2026_0001` -> `op_oil_change` typé `PreventiveOperation`, sans inférence pas `MaintenanceOperation`) étaient validés comme des données. Faux positif sur l'ABox d'exemple, pas sur le fichier de données.
- Correction : `shacl/validate.py` ne fournit que la TBox (individus retirés). Test `test_trap_with_project_ontology_still_eight` (inclut l'aller-retour des shapes). Oracle, README et plan de recette : 8 conservé (README ne cite pas ce nombre ; note ajoutée dans `limites.md` et `plan-recette.md`).

## 2. accept-recommended (D-L14-02)
`?include_lost=false` par défaut : seuls les `review` sont acceptés, les `lost` restent à arbitrer. `?include_lost=true` = mode « tout ». Front : `api.acceptRecommended(..., true)` uniquement quand « seulement les constats à arbitrer » est décoché. Tests : `tests/test_accept_recommended.py` ; CONTRACTS et `guide/api.md` mis à jour ; étape 14 du script de recette resserrée (aucun perdu accepté).

## 3. Cosmétiques (D-L14-03)
- Classe CSV : nom du fichier en PascalCase singulier (`vehicules.csv` -> `Vehicule`) ; chat (nom de la pièce jointe) et `/assistant/draft` (champ facultatif `filename`). Test ajouté.
- Menu Concevoir > Shapes : écran `Shacl` (onglet shapes) ; Vérifier > SHACL ouvre l'onglet validation.
- Bundle : écrans en `React.lazy` + `CodeEditor` chargé à la demande (`src/CodeEditor.tsx`). JS initial 621 ko -> 243 ko, plus d'avertissement > 500 ko. **`dist` total reste 2,7 Mo** (polices 376 ko en woff+woff2, Krakie 780 ko, chunks à la demande) : le seuil `du -sk dist < 2000` n'est pas atteint ; le réduire demanderait de ne livrer que le woff2 et d'alléger les animations Krakie (non fait).
- Anomalie 4 (Cypher `MATCH (v)`) non traitée : comportement attendu après décision « aplatir ».
