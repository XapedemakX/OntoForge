# OntoForge

[Version française](README.md)

OntoForge lets you design an OWL 2 / SHACL ontology, check its W3C conformance, then map it to a ready-to-use property graph model for Curiosity (the priority target) or Neo4j. What maps cleanly is converted automatically. What is lost, or at risk of being lost, is flagged with a recommendation per target, and you decide.

## Getting started (Docker)

```bash
cd OntoForge
docker compose up --build
```
Then open http://localhost:8088 (change the port with ONTOFORGE_PORT in .env). The first build takes a few minutes (Python, Node and Java images for the reasoner).

AI assistant (optional): copy `.env.example` to `.env`, set `ONTOFORGE_LLM_PROVIDER=anthropic` and fill in `ANTHROPIC_API_KEY`. Without a key, the assistant runs in `mock` mode (and drafts from CSV / SQL use a deterministic analyser). Available providers: `anthropic`, `openai_compat` (Azure OpenAI, vLLM, LM Studio...), `ollama`, `mock`.

## Demo path (10 minutes)
1. Projects: "New project" from the automaint sample (car maintenance: 24 classes, SHACL shapes, test data). The dashboard opens and Krakie suggests the next action.
2. Ontology (graphical editor): double-click the background to create a class, drag a node's handle for a subclass or a property, Ctrl+Z, Quick input at the bottom. Create a perimeter from a few classes. Open Krakie (floating button or Ctrl+K): it knows the screen and the selection. Try "add the class Tyre under Part with a pressure property in bar", read the card, Apply then Undo. Also try the List view (class sheet, inline property creation).
3. Conformance (OWL 2 DL / EL / QL / RL profiles, best practices), then SHACL (Shapes screen: editable grid, generation preview). Validate `samples/automaint/automaint-data.ttl`: 4 violations expected.
4. Analysis & decisions: choose Curiosity or Neo4j, browse the *auto / to review / lost* findings, "Accept all recommendations" then refine. Target model: the property graph diagram.
5. Exports: `Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `Connector.cs` (Curiosity) or `schema.cypher`, `ingest.cypher`, `validation.cypher` (Neo4j), `schema.graphql`, transposition report, zip.
6. Settings, Endpoints: declare a SPARQL endpoint containing `samples/automaint/automaint-demo-data.ttl` (40 vehicles, 120 repair orders) and activate it. You can also test a temporary endpoint in Queries without saving it. Add an LLM provider (key encrypted on the server).
7. Queries: type "vehicles repaired by Camille". The tool proposes an editable guided sentence (check boxes for the fuels Diesel, Petrol, Hydrogen, Electric, without an endpoint). Run it (table or graph), compare the SPARQL / Cypher / Curiosity versions side by side, then save.
8. Assistant (full screen): drop a CSV, get a draft, accept item by item, then View in the editor. From the dashboard, asking Krakie "find the vehicles ..." opens the guided query in Queries.

The trap sample is the test "trap" ontology. It exercises the 66 transposition rules.

## What you need to know
- The generated Curiosity code has not been compiled (no .NET SDK in the build environment). Calls marked `À VÉRIFIER` need to be confirmed on your version of Curiosity.Library
- The Neo4j Cypher has not been run on a real database. Enterprise-only constraints are separated and commented
- `xsd:decimal`: exact decimal on the Curiosity side (C# `decimal`). Neo4j has no native decimal, hence a float (loss flagged) or a string
- API keys and endpoint secrets are encrypted on the server. Set `ONTOFORGE_SECRET_KEY` in `.env`, otherwise a key is generated in the volume. No authentication and no SSRF filtering: local workstation only
- Queries: read-only execution on the active SPARQL endpoint. The Curiosity translation (Query API) is entirely `À VÉRIFIER`. Real LLM providers and natural-language questions have not been tried on a real model
- Projects are stored in the Docker volume `ontoforge-data` (one folder per project: `project.json`, `onto.ttl`, `shapes.ttl`, `decisions.json`)

## Repository layout
| Folder | Contents |
|---|---|
| `backend/` | FastAPI API (`ontoforge/`), 560+ tests (`cd backend && pytest -q`) |
| `frontend/` | React + TypeScript application |
| `samples/` | Sample ontologies (automaint, trap) |
| `docs/` | Plan, architecture, interface contracts, catalog of the 66 rules (`RULES.md`) |
| `skills/` | 10 reusable Claude skills (OWL → LPG transposition, SHACL, W3C conformance, Curiosity, Neo4j, queries, fast design, agent team management, product scoping, technical documentation) |
| `.claude/agents/` | Expert agent sheets (W3C, SHACL, querying, Curiosity, Neo4j, project lead) |
| `journal/`, `lots/` | Work package contracts, cross reviews, fixes, decisions |

## Development without Docker
```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
ONTOFORGE_LLM_PROVIDER=mock uvicorn ontoforge.main:app --port 8000
cd ../frontend && npm install && npm run dev   # http://localhost:5173, proxy /api → :8000
```
