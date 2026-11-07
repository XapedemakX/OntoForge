# Recette itération 2 (lot L14) — chef, 4 nov. 2026

Scripts : `tools/recette/e2e_api.py` (API, résultats `journal/L14/recette-api.json`), `tools/recette/e2e_ui.mjs` (Playwright, `recette-ui.json`, captures `journal/L14/screens/recette-*.png`). Backend en `mock`, données temporaires, serveur SPARQL rdflib local (automaint-demo-data.ttl, 4136 triplets).

## Synthèse
- API : **37 OK / 1 KO** sur 38 étapes. UI : **30 OK / 0 KO** (13 écrans bureau, 13 écrans mobile 390 px, 4 interactions) sans erreur console ni HTTP >= 500.
- `pytest -q` : **548 passés**, 0 échec. `npm run build` : OK (dist 2,7 Mo). `docker compose config -q` : valide.
- Aucun bloquant de démo. 1 gênant (SHACL piège via API), le reste cosmétique / à noter.

## Étapes API
| # | Étape | Résultat | Détail |
|---|---|---|---|
| 00 | Santé + exemples | OK | automaint, trap |
| 01 | Projet depuis automaint | OK | 24 classes |
| 02 | SHACL demo-data | OK | 0 violation |
| 03 | SHACL automaint-data | OK | 4 violations |
| 04 | Conformité | OK | DL vrai, 1 issue, 0 erreur |
| 05-07 | Ajout Pneu, Pneu ⊑ Part, propriété objet monteSur | OK | |
| 08 | Undo / redo | OK | |
| 09 | Cycle rejeté | OK | `ok=false`, message « Cycle de sous-classes » |
| 10 | Graphe | OK | 25 nœuds, 42 arêtes |
| 11-12 | Périmètre Maintenance + analyse restreinte | OK | 9 classes ; 78 constats dont 19 info (162 en complet) ; 6 types de nœuds contre 18 |
| 13 | Analyse Curiosity / Neo4j | OK | Curiosity 119 auto / 42 à arbitrer / 1 perdu ; Neo4j 116 / 45 / 4 ; aucun X00 |
| 14 | Accepter les recommandations | OK* | voir anomalie 2 |
| 15 | Génération + zip | OK | Curiosity 8 fichiers (Schema/Edges/RegisterSchema/Connector.cs, rapport…), Neo4j 8 fichiers |
| 16 | Historique des générations | OK | 2 entrées |
| 17 | Traduction + questions de compétence | OK | 9 questions |
| 20-21 | Fournisseur mock, clé jamais renvoyée, chiffrée sur disque | OK | aucune fuite |
| 22 | Endpoint SPARQL local, test, activation | OK | |
| 23 | Requête guidée Véhicule → ordre → technicien | OK | 20 lignes, graphe 46 nœuds |
| 24-25, 27 | Requêtes sauvegardées, valeurs, compétence guidée | OK | 3/10 convertibles |
| 26 | 3 questions NL du PLAN (Martin, garages Toulouse, ordres ouverts) | OK | 41 / 1 / 5 lignes, confiance 0,95, mode déterministe |
| 30-33 | Assistant : statut, chat, upload CSV + draft, explain | OK | projet inchangé |
| 34-35 | Exports, persistance décisions + périmètre | OK | |
| 36 | Projet piège : DL + SHACL 8 violations | **KO** | 9 violations (voir anomalie 1) |

## UI (captures vues : éditeur + inspecteur, requêtes NL, assistant + proposition, analyse, éditeur mobile)
Tous les écrans rendent, 0 erreur console, pas de débordement horizontal à 390 px. Mobile : éditeur en consultation avec bandeau explicatif, conforme au plan.

## Anomalies
**Gênant**
1. SHACL du projet piège via l'API : **9 résultats au lieu de 8**. Résultat supplémentaire : `ro_2026_0001`, `sh:QualifiedMinCountConstraintComponent` sur `am:includesOperation` (inférence `none`). Les mêmes fichiers validés directement par la bibliothèque (`parse_shapes` + `validate` sans ontologie) donnent 8, comme `tests/test_shacl_validate.py`. Piste : le passage par le projet (ontologie fournie à `validate`, ou shapes relues du modèle) change le résultat. Reproduction : `python tools/recette/e2e_api.py` étape 36 ; ou créer le projet `trap`, POST `/shacl/validate` avec `samples/trap/trap-data.ttl`. À trancher : faux positif ou 8e/9e violation légitime ; le plan it1 et le test disent 8.
2. `POST /decisions/{target}/accept-recommended` accepte aussi les constats **perdus** (1 en Curiosity, 4 en Neo4j) ; l'UI évite cela en mode « à arbitrer seulement » mais l'API et le mode « tout » les valident en bloc, ce qui contredit « ce qui se perd est arbitré par l'humain ». Reproduction : étape 14, « perdus restants = 0 ».

**Cosmétique / à noter**
3. Upload CSV dans l'assistant : la classe proposée s'appelle `Record` (avertissement « Nom de classe non déterminé ») alors que le fichier s'appelle `vehicules.csv` ; le nom du fichier pourrait servir.
4. Traduction `?v a am:Vehicle` en Cypher : `MATCH (v)` sans étiquette dans un projet où Vehicle est aplati (le plan it1 attendait `(v:Vehicle)`). Probablement voulu après décision « aplatir », à confirmer.
5. Écran « Shapes » : encore un `ComingSoon` (placeholder) dans le menu Concevoir.
6. `dist` = 2,7 Mo (seuil de la recette it1 : 2 Mo) ; avertissement Vite sur les chunks > 500 ko.
7. `docs/PLAN` it1 §1 (8 violations) et README doivent être alignés une fois l'anomalie 1 tranchée.

## Non vérifiable ici : à faire chez Jerem
1. `cp .env.example .env && docker compose up --build` : deux conteneurs sains, http://localhost:8088 (le proxy nginx `/api` et le volume `ontoforge-data` ne sont pas testés ; seul `docker compose config` est validé).
2. Compiler le C# Curiosity généré (`tools/dotnet/check-curiosity.ps1`) avec le vrai SDK .NET et Curiosity.Library ; confirmer les appels `À VÉRIFIER` ; traduction Curiosity Query API.
3. Un vrai fournisseur LLM (Anthropic / openai_compat / Ollama) : test de connexion, chat, brouillon CSV, question en langage naturel en mode « llm » ; le mock est le seul exercé.
4. Cypher généré (`schema.cypher`, `ingest.cypher`) sur une vraie base Neo4j.
5. Endpoint SPARQL réel (Fuseki/GraphDB) avec authentification, et revue visuelle des écrans (animations Krakie, thème sombre, `prefers-reduced-motion`).
6. Trancher l'anomalie 1 (SHACL piège 8 ou 9).
