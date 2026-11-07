# L15 - rapport front (requêtage guidé)

Agent : query. `npm run build` vert. Captures : `journal/L15/screens/` (01 vide, 01-vide-nl, 02 un pas, 03 chaîne + filtre, 04 résultats, 05 graphe, 06 côte à côte + sauvegarde, 07 SPARQL libre, 08 mobile 390, 09-10 question en langage naturel).

## Livré (`frontend/src/screens/queries/`)
- `index.tsx` écran (remplace `screens/Queries.tsx`, supprimé) ; entrée `requetes` du registre pointe dessus (`editing: true` : bandeau mobile). Deux modes : « Phrase guidée » et « SPARQL libre » (traduction d'origine conservée + exécution).
- `Builder.tsx` : classe racine par liste avec recherche ; relations sortantes et entrantes proposées par `/query/suggest` (cibles multiples = choix de la classe) ; branches multiples depuis une même variable ; options par étape (facultatif, pas/négation) ; filtres selon le type (contient, égal, regex, langue, plage numérique, plage de dates, liste) avec valeurs suggérées par `/query/values` (datalist) ; panneau de colonnes : liste ordonnée et réordonnable (flèches), cases par variable (identifiant, libellé, propriétés de données), tri, limite, sous-classes.
- `NlBox.tsx` : champ « Pose ta question » (Krakie « réfléchit » pendant l'appel) vers `POST /query/nl` ; 404/501 = « Bientôt disponible » ; le résultat remplit la phrase (modifiable), explication, indicateur de confiance, termes non reconnus cliquables (ouvrent la recherche de relation pré-remplie). Format de `unmatched` supposé : liste de chaînes ou `{term|text}`.
- `Results.tsx` : tableau (tri par colonne, CSV), graphe cytoscape, durée, « tronqué », erreurs lisibles. `CodePanel.tsx` : onglets SPARQL / Cypher / Curiosity / GraphQL ou « côte à côte », notes perte/info/à vérifier, copier. `Library.tsx` : requêtes sauvegardées (exécuter, ouvrir, renommer, supprimer avec confirmation, enregistrer) et questions de compétence rejouables en un clic (SPARQL libre si pas de version guidée).
- Endpoint : sélecteur dans l'en-tête de l'écran (liste `/settings/endpoints`, `PUT .../active`, puis `announceActiveEndpoint`) ; lit l'actif via `useActiveEndpoint`.
- Krakie en état vide (« Commence par choisir ce que tu cherches »). Mobile (< 900 px) : bibliothèque + exécution des sauvegardées + résultats ; construction masquée.
- i18n : clés `q.*` dans fr.json et en.json.

## Test d'exécution (méthode)
Backend : `ONTOFORGE_LLM_PROVIDER=mock ONTOFORGE_DATA=<scratchpad>/data-l15 uvicorn ontoforge.main:app --port 8015`. Endpoint SPARQL local : `<scratchpad>/sparql_server.py` (rdflib, http://127.0.0.1:3030/sparql, POST `query=`, résultats JSON) chargé de `samples/automaint/automaint-data.ttl` + `extra.ttl` (liens véhicule -> ordre -> technicien, noms ; ajoutés car les données d'exemple n'ont pas cette chaîne). Déclaré via `POST /api/settings/endpoints` puis `PUT .../active`. Vite : `ONTOFORGE_API=http://localhost:8015 npx vite --port 5175`. Parcours Playwright Véhicule -> ordre de réparation -> technicien, filtre « nom affiché contient Camille » : 1 ligne (veh_ok / ro_ok / tech_ok). `/query/nl` simulé par interception de route (backend pas encore livré : 404 réel affiché comme « Bientôt disponible »).

## Limites
- « Inclure les sous-classes » est global (le contrat `GuidedQuery.subclasses` n'est pas par étape).
- Le propriétaire des libellés de propriétés d'une requête rechargée est résolu à l'affichage depuis les suggestions.
- « Côte à côte » reste dans la colonne de droite (étroit) ; à élargir si Jerem le veut.
- Pas de glisser-déposer pour les colonnes : flèches (accessibles au clavier).
- Un état `tsc` rouge passager venait d'autres lots (editor, AssistantPage) ; vert à la fin.
