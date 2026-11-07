# Backlog OntoForge — itération 1 (mar. 3 nov. 19 h) et itération 2 (ven. 6 nov.)

Priorisation **MoSCoW** (D-022, D-032) :
- **Must** = **itération 1, mardi soir** (resserré) — c'est ce que Jerem recette avec `docker compose up` ;
- **Should** = **itération 2, vendredi** — complète le « concret » des 5 points de docs/PLAN.md ;
- **Could** = bonus ; **Won't** = hors v0.1.

Persona : **le concepteur** (Jerem) qui modélise la **maintenance automobile** (`am: <https://w3id.org/ontoforge/automaint#>`, D-030) et veut un schéma Curiosity ou Neo4j prêt à l'emploi. API et modèles : `docs/CONTRACTS.md`. Ordre de coupe : D-018.

## État réel au mar. 3 nov. 03 h (chef, it2)
Suite backend : 186 verts / 3 rouges (2 W06/W07 en cours chez w3c, 1 `samples` : D-037). Build front : rouge. Moteur L3, `report`, assistant `service` : absents.

| US | État | Preuve / reste |
|---|---|---|
| US-01 | fait côté API (`sample=automaint|trap`), UI à vérifier | `test_create_from_sample` ; D-037 sur `trap-nondl.ttl` |
| US-02 | **fait** | `test_io_import_export.py` (12 verts), round-trip 5 formats |
| US-03 | **fait** | `test_shacl_io.py` |
| US-04 | DL fait ; EL/QL/RL, reasoner **en avance** | `test_conformance_profiles.py` (2 rouges W06/W07) |
| US-05 | **fait** | 8 violations exactes (`test_shacl_validate.py`) |
| US-06, US-07 | profils faits (66 règles + X00), **moteur absent** | L3 jalons 07 h / 09 h |
| US-08, US-09 | endpoints présents (501 sans moteur) | dépend de L3 |
| US-10, US-11 | **faits sur PGModel de test** ; intégration moteur 12 h | `test_target_curiosity|neo4j.py` ; tree-sitter à brancher |
| US-12 | absent | `targets/report.py` (lead, 10 h) |
| US-13 | zip/export : API faite ; vérifié à la recette | |
| US-14 | écrans présents, **build rouge**, scripts absents | L5 |
| US-15 | providers présents, `service.py` + mock absents | L6 |
| US-16 | Dockerfile à corriger (Java) | L1 A14 |
| US-17 | `journal/events.jsonl` + Salle des agents | |
| Should déjà livrés (avance) | US-21 (DSL), US-23, US-24, US-25 (shacl générés), US-26, US-27, US-28 (traduction + compétence) | à recetter vendredi, hors périmètre mardi |

## Must — itération 1 (mardi 3 nov., 19 h)

| ID | Concret | En tant que concepteur, je veux… | Critère d'acceptation (résumé) | Lot |
|---|---|---|---|---|
| US-01 | 1 | créer un projet vide ou depuis un exemple (*Maintenance automobile*, *Ontologie piège*) | `POST /projects {sample}` → `onto.classes` contient `am:Vehicle` | L1, L5 |
| US-02 | 1 | importer un `.ttl` ou un `.owl` (RDF/XML exporté par Protégé) sans perte silencieuse | round-trip égal ; non représenté → `onto.unmapped` / warnings | L1 |
| US-03 | 1 | importer des shapes SHACL | round-trip isomorphe sur `trap-shapes.ttl` | L2 |
| US-04 | 2 | un contrôle de conformité de base : **profil OWL 2 DL seul en It1** (règles W01–W05, W07) + bonnes pratiques, avec référence de spec | trap → DL conforme ; `trap-nondl.ttl` → une erreur par règle W01–W05 | L2 |
| US-05 | 2 | valider un fichier de données (ordres de réparation, véhicules) contre les shapes | 8 violations V1–V8 sur `trap-data.ttl` | L2 |
| US-06 | 3 | analyser vers **Curiosity** : constats auto / à arbitrer / perdu, options et recommandation | 28 des 66 règles (D-031, D-032) ; les 38 autres en `X00` ; `must_not` respectés ; options = vocabulaire du YAML | L3 |
| US-07 | 3 | la même analyse vers **Neo4j** | recommandations Neo4j du YAML | L3 |
| US-08 | 3 | arbitrer un constat et retrouver mon choix après modification de l'ontologie | `PUT /decisions/{target}` ; id `rule:subject` stable | L3, L5 |
| US-09 | 3 | « Accepter toutes les recommandations » sans écraser mes choix manuels | `accept-recommended` | L3, L5 |
| US-10 | 4 | générer le schéma **Curiosity complet** : nodes `[Node]/[Key]/[Property]`, edges par paires, enregistrement, squelette de connecteur | C# sans erreur tree-sitter, golden | L4 |
| US-11 | 4 | générer le **DDL Neo4j** (contraintes, index) | formes Cypher 5, golden | L4 |
| US-12 | 4 | un rapport de transposition (perdu, pourquoi, compensation) | `rapport-transposition.md` | L3 |
| US-13 | 4 | exporter : zip des fichiers générés, Turtle de l'ontologie et des shapes | `/generate/{target}/zip`, `/export/*` | L4, L1, L5 |
| US-14 | 1–4 | un front minimal : **charger / voir constats / arbitrer / exporter** | `npm run build` + `smoke.mjs` | L5 |
| US-15 | 5 | un **brouillon d'ontologie depuis un texte** (notes d'atelier), que je sélectionne avant d'appliquer | `/assistant/draft kind=text` ; jamais d'application automatique | L6, L5 |
| US-16 | — | lancer l'outil par `docker compose up` sur http://localhost:8088 | recette J1–J3 chez Jerem mar. 19 h | L1, L7 |
| US-17 | — | suivre l'avancement depuis mon téléphone sans rien faire | Salle des agents alimentée | tous |

## Should — itération 2 (vendredi 6 nov.)

| ID | Concret | En tant que concepteur, je veux… | Lot |
|---|---|---|---|
| US-20 | 3 | les **38 règles restantes** des 66 du catalogue étendu (plus aucun `X00`) | L3 |
| US-21 | 1 | la saisie rapide DSL (`Car < Vehicle`, `RepairOrder --concernsVehicle--> Vehicle [1]`) avec aperçu | L1, L5 |
| US-22 | 1 | un éditeur de classes / propriétés façon Protégé | L5 |
| US-23 | 2 | les profils OWL 2 EL / QL / RL avec leurs raisons ; W06 (insatisfiabilité) | L2 |
| US-24 | 2 | le raisonneur OWL RL (owlrl, contournement prp-key) | L2 |
| US-25 | 2 | générer des shapes depuis l'ontologie | L2 |
| US-26 | 4 | Neo4j : ingestion `MERGE` et validations Cypher | L4 |
| US-27 | 4 | un schéma GraphQL | L4 |
| US-28 | 4 | traduire une requête SPARQL en Cypher / Curiosity ; questions de compétence du domaine | L4 |
| US-29 | 5 | brouillon depuis un CSV ou un DDL SQL de garage | L6 |
| US-30 | 5 | shapes proposées par l'assistant ; explication d'un constat | L6 |
| US-31 | 5 | fournisseurs IA compatibles OpenAI / Azure et Ollama | L6 |
| US-32 | — | diagramme Cytoscape (ontologie et modèle cible) | L5 |
| US-33 | 1 | export RDF/XML et JSON-LD | L1 |

## Could

| ID | En tant que concepteur, je veux… | Lot |
|---|---|---|
| US-40 | raisonneur OWL 2 DL HermiT (Java + owlready2) | L2 (coupé en premier) |
| US-41 | fournisseur Bedrock | L6 |
| US-42 | exécuter les sorties sur une instance Neo4j / Curiosity réelle | L7 (optionnel, chez Jerem) |
| US-43 | endpoint catalogue `GET /rules` et fusion serveur `POST /onto/merge` | L1 (décision à tracer) |

## Won't (v0.1)

| ID | Sujet | Version |
|---|---|---|
| US-50 | Diff entre deux versions d'ontologie | v0.2 |
| US-51 | Export SHACL depuis les décisions de validation | v0.2 |
| US-52 | Alignement avec des ontologies de référence (schema.org, gist, BFO) | v0.3 |
| US-53 | Cibles Neptune openCypher, Memgraph, GQL / PG-Schema | v0.3 |
| US-54 | Multi-utilisateur, authentification | v0.3+ |
