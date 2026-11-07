# Plan OntoForge — itération 1 mardi 3 novembre 2026 au soir, itération 2 vendredi 6

## Décisions (Jerem, 2 nov.)
- Nom : OntoForge. Backend **Python FastAPI** + front web. Exécution **Docker uniquement** (docker-compose).
- **SHACL dès la v0.1.** Cibles : **Curiosity (prio 1)** puis Neo4j.
- **Assistant IA de conception** : Claude par défaut, fournisseur configurable (Anthropic, compatible OpenAI/Azure, Bedrock, Ollama), propositions toujours soumises à revue humaine.
- Équipe de 6 agents qui s'auto-valident (docs/TEAM.md) + skills réutilisables.
- Suivi depuis le téléphone : Salle des agents (artifact claude.ai).
- **Itération 1 avancée à mardi 3 nov. au soir** (décision Jerem, lundi 22h34) ; vendredi = itération 2.
- Domaine de l'exercice de base : maintenance automobile.
- Minimum d'action de Jerem : il ne valide que les démos ; questions métier non bloquantes dans `journal/questions-jerem.md`.

## Définition de « concret » pour vendredi
`docker compose up` → http://localhost:8088 :
1. Créer une ontologie (éditeur + saisie rapide) ou charger un .ttl / .owl / .rdf et des shapes SHACL.
2. Rapport de conformité W3C (profil OWL 2, erreurs, bonnes pratiques) et validation SHACL.
3. Analyse vers Curiosity ou Neo4j : constats auto / à arbitrer / perdu, recommandations, arbitrage mémorisé.
4. Génération : Schema.cs + Edges + connecteur Curiosity ; DDL + ingestion + validations Cypher ; schéma GraphQL ; traductions de requêtes ; rapport de transposition.
5. Assistant IA : brouillon d'ontologie depuis un texte / CSV / DDL SQL, génération de shapes, explication d'un constat.

## Architecture technique
```
OntoForge/
  docker-compose.yml          backend (8000) + frontend (8088 par défaut, ONTOFORGE_PORT, nginx, proxy /api)
  .env.example                ONTOFORGE_LLM_PROVIDER, ANTHROPIC_API_KEY, ...
  backend/
    Dockerfile                python:3.12-slim + openjdk-17-jre-headless (raisonneur)
    pyproject.toml            fastapi, uvicorn, pydantic v2, rdflib, pyshacl, owlrl, owlready2, httpx, pytest
    ontoforge/
      main.py                 app FastAPI, routers /api/*
      core/onto_model.py      OntoModel (pydantic) — contrat
      core/shapes_model.py    ShapesModel (SHACL) — contrat
      core/pg_model.py        PGModel + Finding — contrat
      io/                     rdf_import.py, rdf_export.py, dsl.py
      conformance/            profiles.py (OWL 2 DL/EL/QL/RL), lint.py, reasoner.py (owlrl / HermiT optionnel)
      shacl/                  import_shapes.py, owl_to_shacl.py, validate.py, shacl_to_pg.py
      mapping/                rules/ (un module par famille), engine.py, decisions.py, profiles.py (cibles)
      targets/                curiosity.py, neo4j.py, graphql.py, report.py
      queries/                translate.py (SPARQL ↔ Cypher ↔ Curiosity), competency.py
      assistant/              providers/ (anthropic, openai_compat, ollama, mock), prompts/, service.py
      projects/store.py       un projet = un dossier (onto.ttl, shapes.ttl, decisions.json, project.json)
    tests/
  frontend/                   React + TypeScript + Vite ; Cytoscape (diagramme) ; CodeMirror (code)
  samples/                    ontologies et shapes d'exemple + ontologie piège + résultats attendus
  skills/<8 skills>/SKILL.md  skills réutilisables
  .claude/agents/*.md         fiches des agents
  lots/ journal/ docs/
```

## Lots et enchaînement
| Lot | Pilote | Relecteurs | Dépend de | Cible |
|---|---|---|---|---|
| L0 Cadrage | chef (+w3c : ontologie piège) | w3c, lead | — | lun. soir |
| L1 Socle backend + Docker + contrats pydantic | w3c (+lead) | chef, shacl | L0 | mar. matin |
| L2 Conformité + SHACL | shacl, w3c | w3c, shacl (croisé), query | L1 | mar. |
| L3 Moteur de mapping | lead (+curiosity, neo4j pour les règles cible) | w3c, curiosity, neo4j | L1 | mar.–mer. |
| L4 Générateurs + requêtes | curiosity, neo4j, query | croisés + w3c | L3 | mer. |
| L5 Front | lead | chef, w3c | L1 (API), L3 | mer.–jeu. |
| L6 Assistant IA | lead | w3c, shacl | L1, L2 | jeu. |
| L7 Recette + livraison | chef | tous + relecteur en aveugle | tout | jeu. soir–ven. |

Démos pour Jerem : fin L3 (API + rapport d'analyse sur l'ontologie piège), fin L5 (appli complète).
