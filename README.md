# OntoForge

[English version](README.en.md)

OntoForge sert à concevoir une ontologie OWL 2 / SHACL, vérifier sa conformité W3C, puis la transposer en modèle property graph prêt à l'emploi pour Curiosity (cible prioritaire) ou Neo4j. Ce qui passe tout seul est transposé automatiquement. Ce qui se perd ou risque de se perdre est mis en avant, avec une recommandation par cible, et c'est vous qui arbitrez.

## Démarrer (Docker)

```bash
cd OntoForge
docker compose up --build
```
Puis ouvrir http://localhost:8088 (port modifiable via ONTOFORGE_PORT dans .env). Le premier build prend quelques minutes (images Python, Node, Java pour le raisonneur).

Assistant IA (optionnel) : copier `.env.example` en `.env`, mettre `ONTOFORGE_LLM_PROVIDER=anthropic` et renseigner `ANTHROPIC_API_KEY`. Sans clé, l'assistant tourne en mode `mock` (et les brouillons depuis CSV / SQL utilisent un analyseur déterministe). Fournisseurs possibles : `anthropic`, `openai_compat` (Azure OpenAI, vLLM, LM Studio…), `ollama`, `mock`.

## Parcours de démo (10 minutes)
1. Projets : « Nouveau projet » depuis l'exemple automaint (maintenance automobile : 24 classes, shapes SHACL, données de test). Le tableau de bord s'ouvre et Krakie propose la prochaine action.
2. Ontologie (éditeur graphique) : double-clic sur le fond pour créer une classe, glisser la poignée d'un nœud pour une sous-classe ou une propriété, Ctrl+Z, Saisie rapide en bas. Créer un périmètre depuis quelques classes. Ouvrir Krakie (bouton flottant ou Ctrl+K) : elle connaît l'écran et la sélection. Essayer « ajoute la classe Pneu sous Pièce avec une propriété pression en bar », relire la carte, Appliquer puis Annuler. Essayer aussi la Vue liste (fiche d'une classe, ajout de propriété en ligne).
3. Conformité (profils OWL 2 DL / EL / QL / RL, bonnes pratiques), puis SHACL (écran Shapes : grille éditable, aperçu de génération). Valider `samples/automaint/automaint-data.ttl` : 4 violations attendues.
4. Analyse & arbitrage : choisir Curiosity ou Neo4j, parcourir les constats *auto / à arbitrer / perdus*, « Accepter toutes les recommandations » puis affiner. Modèle cible : diagramme du property graph.
5. Exports : `Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `Connector.cs` (Curiosity) ou `schema.cypher`, `ingest.cypher`, `validation.cypher` (Neo4j), `schema.graphql`, rapport de transposition, zip.
6. Paramètres, Endpoints : déclarer un endpoint SPARQL contenant `samples/automaint/automaint-demo-data.ttl` (40 véhicules, 120 ordres de réparation) et l'activer. On peut aussi tester un endpoint temporaire dans Requêtes, sans le sauvegarder. Ajouter un fournisseur LLM (clé chiffrée côté serveur).
7. Requêtes : saisir « véhicules réparés par Camille ». L'outil propose une phrase guidée modifiable (cases à cocher pour les carburants Diesel, Essence, Hydrogène, Électricité, sans endpoint). Exécuter (tableau ou graphe), comparer les versions SPARQL / Cypher / Curiosity côte à côte, puis sauvegarder.
8. Assistant (plein écran) : déposer un CSV, obtenir un brouillon, accepter élément par élément, puis Voir dans l'éditeur. Depuis le tableau de bord, demander à Krakie « cherche les véhicules … » ouvre la requête guidée dans Requêtes.

L'exemple trap est l'ontologie « piège » de test. Elle exerce les 66 règles de transposition.

## Ce qu'il faut savoir
- Le code Curiosity généré n'a pas été compilé (pas de SDK .NET dans l'environnement de construction). Les appels marqués `À VÉRIFIER` sont à confirmer sur votre version de Curiosity.Library
- Le Cypher Neo4j n'a pas été exécuté sur une base réelle. Les contraintes Enterprise-only sont séparées et commentées
- `xsd:decimal` : décimal exact côté Curiosity (`decimal` C#). Neo4j n'a pas de décimal natif, d'où un nombre flottant (perte signalée) ou une chaîne
- Les clés d'API et secrets d'endpoints sont chiffrés côté serveur. Définir `ONTOFORGE_SECRET_KEY` dans `.env`, sinon une clé est générée dans le volume. Pas d'authentification ni de filtrage SSRF : poste local uniquement
- Requêtes : exécution en lecture seule sur l'endpoint SPARQL actif. La traduction Curiosity (Query API) est entièrement `À VÉRIFIER`. Les fournisseurs LLM réels et la question en langage naturel n'ont pas été éprouvés sur un vrai modèle
- Projets stockés dans le volume Docker `ontoforge-data` (un dossier par projet : `project.json`, `onto.ttl`, `shapes.ttl`, `decisions.json`)

## Organisation du dépôt
| Dossier | Contenu |
|---|---|
| `backend/` | API FastAPI (`ontoforge/`), 560+ tests (`cd backend && pytest -q`) |
| `frontend/` | Application React + TypeScript |
| `samples/` | Ontologies d'exemple (automaint, trap) |
| `docs/` | Plan, architecture, contrats d'interface, catalogue des 66 règles (`RULES.md`) |
| `skills/` | 10 skills Claude réutilisables (transposition OWL → LPG, SHACL, conformité W3C, Curiosity, Neo4j, requêtes, conception rapide, pilotage d'équipe d'agents, cadrage produit, documentation technique) |
| `.claude/agents/` | Fiches des agents experts (W3C, SHACL, requêtage, Curiosity, Neo4j, chef de projet) |
| `journal/`, `lots/` | Contrats de lot, revues croisées, corrections, décisions |

## Développement sans Docker
```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
ONTOFORGE_LLM_PROVIDER=mock uvicorn ontoforge.main:app --port 8000
cd ../frontend && npm install && npm run dev   # http://localhost:5173, proxy /api → :8000
```
