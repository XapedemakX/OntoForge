# Changelog {#journal-des-versions}

Format: by version, what changes for the user, then the detail per work package. Sources: reports `journal/L*/rapport*.md`, reviews, `journal/decisions.md`. Work packages are described in `lots/`.

## L30: Krakie comes alive in the hidden game (8 Nov 2026) {#l30-krakie-vivante-dans-le-jeu-cache-8-nov-2026}

- In "Krakie's Triple Catch", Krakie swims (6 frames, waving tentacles, a slight bounce) and leans in the direction she moves.
- Short expressions: a wink for each item caught, a big smile and sparkles for a complete triple, surprise for a bonus, a grimace with a slight shake for a lost finding or a broken IRI, and constant worry on a single life. A glass halo during the SHACL shield, a purple effect during inference. At the end of a game: a trophy for a record or 400 points, worry otherwise.
- A word is no longer both a target and a distractor of another category, and the background graph stays under the score banner. With `prefers-reduced-motion`: fixed expressions, no shake, bounce or lean.

## L29: Krakie the blacksmith (8 Nov 2026) {#l29-krakie-forgeronne-8-nov-2026}

- Krakie forges (two hammers on an anvil) during exports, analysis, shape generation and the draft from a document, in place of Krakie at the wheel. She then raises a graph-shaped trophy for about 2 s at the end of a successful run. Still frames with `prefers-reduced-motion`.
- New poses `forge` (8 frames) and `trophee` (4 frames). The "racer" pose stays in the sources of `design/krakie/` but is no longer displayed.

## L31: standard and target versions (8 Nov 2026) {#l31-versions-des-normes-et-des-cibles-8-nov-2026}

- Bundled `standards.json` reference (W3C, Neo4j, Cypher, Curiosity.Library, internal libraries); `GET /api/standards`.
- Versions per project with a global default in Settings; local check `versions/check`; Versions screen.
- Neo4j: `CYPHER 25` / `CYPHER 5` prefix query by query, constraints depending on the version. Curiosity: Curiosity.Library version in the headers and the README. The transposition report lists the versions. SHACL 1.2 features are disabled.
- Krakie: `quelles versions ?`, `mets à jour les versions`, and a gap bubble once per session.
- SHACL: the only published version is 1.0 (Recommendation of 20 July 2017). "SHACL 1.1" does not officially exist and is read only as a synonym of 1.0. Neo4j 4.4: only `schema.cypher` has a variant (ASSERT syntax, `À VÉRIFIER`).
- Krakie fix: a bare "help" now gets an English answer.

## 0.1.0: Iteration 1 (delivery planned for Tuesday 3 November 2026, ~7 pm, Paris, D-022) {#iteration-1-livraison-prevue-le-mardi-3-novembre-2026-19-h-paris-d-022}

> Status at the first L12 pass: the acceptance test at Jerem's (`docker compose up --build`, work package L7) has not happened yet and no work package has a `cloture.md` file. This version reflects the state of the repository on the evening of 3 November 2026.

### What's new {#nouveautes}

- Design: projects (empty, from the `automaint` and `trap` examples, or by file drop); a Protégé-style ontology editor; Quick input (DSL, one line = one axiom); import of Turtle, RDF/XML, JSON-LD, N-Triples, N3, TriG; export to Turtle, RDF/XML, JSON-LD, N-Triples, N3.
- Check: OWL 2 DL / EL / QL / RL conformance with specification references (W01 to W07) and best practices (BP01 to BP07).
- SHACL: import, generation from the ontology, validation of a data file (no inference by default).
- Transpose: an engine of 66 rules (+ S01, S02, G02) with *auto / to decide / lost* findings, options per target, a recommendation per target, decisions remembered and replayed, decisions grouped by rule, "Accept all recommendations".
- Generate: Curiosity (`Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `Connector.cs`), Neo4j (`schema.cypher`, `ingest.cypher`, `validation.cypher`, `model.mmd`), `schema.graphql`, transposition report, zip.
- Queries: SPARQL → Cypher / Curiosity / GraphQL translation with loss notes; competency questions.
- AI assistant: ontology draft from text, CSV or SQL, accepted element by element; proposed shapes; explanation of a finding; providers `anthropic`, `openai_compat`, `ollama`, `mock`.
- Docker: `docker compose up --build` (FastAPI backend + nginx frontend), projects persisted in the `ontoforge-data` volume.

### By work package {#par-lot}

| Package | Content | Reviews (verdicts) |
|---|---|---|
| L0 | Scoping: catalogue extended to 66 rules (36 + 30 added), severities of K02 and C05 corrected to `review`, oracle `samples/trap/expected-findings.yaml`, normative option vocabulary (D-031) | w3c: KO then fixes |
| L1 | Foundation: `core/*` (pydantic contracts), REST API (27 iteration 1 routes), project storage, RDF imports/exports, DSL, Dockerfile / compose | w3c it1: OK |
| L2 | Conformance (DL/EL/QL/RL profiles, W01 to W07, BP01 to BP07, optional reasoner), SHACL (import/export/generation/validation/translation to PG constraints); `validate` without inference by default (D-034, D-L2-01) | w3c it1: KO → it2: OK |
| L3 | Mapping engine: 66 rules implemented from iteration 1 (no `X00`), oracle 6/6 `must_not`, 66 expected findings, transposition report, grouping by rule, grouped decisions | w3c it1: KO → it2: OK |
| L4 | Curiosity, Neo4j and GraphQL generators; SPARQL translator; competency questions; xsd type maps per target | curiosity/neo4j cross it1: KO → it2: OK; w3c it1: KO, it2: KO |
| L5 | React interface: 7 screens + assistant panel, light/dark theme, screenshots in `journal/L5/screens/` | - |
| L6 | AI assistant: service, CSV/SQL parsers, JSON → `OntoModel` conversion, 4 providers | - |
| L7 | Acceptance plan (`journal/L7/plan-recette.md`) | acceptance at Jerem's to come |
| L13 (leftovers, iteration 2 brought forward) | `Decimal` (Curiosity without loss), reverse names (`mapping/reverse_names.py`), I01/C08 (reference nodes), readable diagram, script `tools/dotnet/check-curiosity.ps1` | w3c it1: KO (reverse name collisions) |

### L16 and L17 (4 November 2026) {#l16-et-l17-4-novembre-2026}

- L16: global Krakie (floating button, Ctrl+K, screen context, Apply / Undo cards, intents without an LLM).
- L17: rebuilt List view, rebuilt Shapes screen (inline editing, generation diff, validation), Queries: temporary endpoint, possible values without an endpoint, new logo. API: `dry_run` on `/shacl/generate`, `GET /query/options`, `POST /query/endpoint-test`. See `journal/L16/cloture.md` and `journal/L17/cloture.md`.

### Notable fixes from the reviews {#corrections-notables-issues-des-revues}

- Catalogue: `owl:hasKey` is never `auto` (K02, SS §9.5); a named `owl:equivalentClass` = `review` (C05); two `rdfs:domain` / `rdfs:range` = intersection (D12/O21), never union; a relation with 3 or more roles = R02, never R01.
- Engine: `some` / `min n` cardinalities are never read as "exactly 1"; flattened inheritance without a false obligation; non-simple properties without cardinality; property chains kept in order; complex domain/range → explicit G01.
- Generators: hexBinary / base64Binary and `rdf:langString` classified outside the OWL 2 map (loss); fallback key = IRI property, never an empty match pattern; Neo4j: Enterprise constraints separated.
- Translator: a class or property missing from the model = empty pattern + loss (never an untyped pattern); multiple types on the same discriminator = loss.
- Conformance: W07 ignores reused vocabularies (dcterms, skos...); `DisjointUnion` classified outside EL/QL/RL (confirmed).

### Structuring decisions {#decisions-structurantes}

D-002 (FastAPI + React), D-003 (Docker only), D-004 (SHACL from v0.1), D-005 (Curiosity first), D-006 (assistant subject to human review), D-028 (normative `core/*` contracts), D-031 (66 rules), D-034 (validation without inference), D-035 (finding identifier format), D-038 (no golden files), D-L13-01 (`Decimal`). Full list: `journal/decisions.md`.

### Known limits at delivery {#limites-connues-a-la-livraison}

Curiosity C# not compiled, Cypher not executed, external APIs `À VÉRIFIER`, no authentication. Details in [`limites.md`](limites.md).

## 0.2.0: Iteration 2 (delivery planned for Friday 6 November 2026) {#iteration-2-livraison-prevue-le-vendredi-6-novembre-2026}

> Status as of 4 November 2026: work packages L8, L9, L10, L11, L13, L14 (demo data, generation history) and L15 are delivered on the code side. The acceptance test (L14) and Jerem's validation are still to do. Backend tests: 528 green according to the L15 review (not rerun by the documentation writer). `npm run build` green according to the reports.

### What's new {#nouveautes-2}

- Path and dashboard: the interface follows Design → Check → Transpose → Generate; a dashboard per project (Krakie's next action, steps, findings per target, generations, perimeters); the "Abysse" design system (light / dark), IBM Plex; fr / en interface.
- Interactive graphical editor: canvas + collapsible inspector + tree + quick input; gestures (double-click = class, drag = subclass / property / disjointness, F2, Delete); undo / redo (200 levels); OWL 2 validation of each gesture (all or nothing); icons per class; semantic zoom.
- Perimeters: subsets of the ontology to transpose (several per project), `?perimeter=` on analysis and generation, findings P00 to P03.
- Settings: multiple LLM providers (type, URL, model, key encrypted on the server, connection test, default), languages, defaults (base IRI, prefixes, target, naming), multiple SPARQL endpoints (one active).
- Full-screen assistant: a conversation per project, provider choice, file upload (CSV, SQL, text, Markdown, 2 MB) with preview, quick actions, a proposal accepted or rejected element by element, also shown in the editor.
- Interactive querying: a guided sentence driven by the ontology and the shapes, value autocompletion from the endpoint, filters, columns, read-only execution, results as a table and a graph, SPARQL / Cypher / Curiosity / GraphQL side by side, saved queries, natural-language question (`POST /query/nl`, deterministic fallback).
- Krakie, an animated pixel-art mascot (8 poses).
- Generation history on the server (`GET /generations`); demo data `samples/automaint/automaint-demo-data.ttl` and `tools/demo/generate_demo_data.py`.
- Documentation: this guide updated (user, architecture, API, limits, glossary).

### By work package {#par-lot-2}

| Package | Content | Reviews |
|---|---|---|
| L8 | `settings/` (Fernet + HKDF, `ONTOFORGE_SECRET_KEY`, rotation), `api/settings.py`, multiple providers, `/assistant/chat` and `/upload`, Settings screen (CONTRACTS §4, D-L8-01) | - |
| L9 | `editing/` (operations, history, perimeters, graph, icons), `api/editing.py`, graphical editor (CONTRACTS §5, D-L9-01, D-L9-02) | - |
| L10 | Full-screen assistant, `lib/proposal.ts` store | - |
| L11 | Shell, kit, i18n, "Abysse" tokens, Krakie, dashboard | - |
| L13 | Iteration 1 leftovers: Decimal, reverse names (+ collision fix after the W3C review), I01 / C08, model diagram, `tools/dotnet/check-curiosity.ps1` | w3c it1 KO → fixed (475 tests green) |
| L14 | Generation history (§7), demo data (524 tests green) | - |
| L15 | Guided querying, multiple endpoints, `/query/nl` (CONTRACTS §6); engine fix (D-L15-01) | curiosity: approved with reservations (1 blocker fixed) |

### Notable fixes {#corrections-notables}

- Reverse: a derived return name can no longer reuse an existing OWL property (fallback `<Edge>Of<Source>`).
- Inheritance under an abstract class (D-L15-01): properties copied into each concrete leaf. Before, `DisplayName` disappeared from the C# schema of Technician / Garage / Customer / Brand. Rerun the analysis of existing projects.
- Decimal: Curiosity without loss; Neo4j `Float` with a flagged loss.
- I01 / C08: no more I01 finding for the members of `owl:oneOf`.
- Queries: discriminator filter kept by the translator; read-only safeguards.

### Structuring decisions {#decisions-structurantes-2}

D-L2-01, D-L4-02, D-L8-01 (encrypted settings), D-L9-01 (editor: all-or-nothing `/ops`), D-L9-02 (`NodeType.icon`, `info` severity: accepted, not yet implemented), D-L13-01 (`Decimal`), D-L15-01 (copy into the leaves). Plan: `docs/PLAN-IT2.md` (decisions of 3 and 4 November: Krakie, one active endpoint, Sparnatural-style querying with our own builder, natural language).

### Known limits {#limites-connues}

Curiosity C# and Query API not verified, Cypher not executed, external APIs `À VÉRIFIER`, no authentication, no SSRF filtering, real LLM providers not tried, no automated front-end test. Details: [`limites.md`](limites.md).

## 0.3.0 (in progress) {#en-cours}

Work packages L19 to L26, one per line. Details are in `journal/L<n>/rapport.md`.

- L19: embedded local triplestore per project (pyoxigraph 0.5.13), queries, RDFS / OWL RL inference, SHACL validation. Default graph = deduplicated union (D-L19-01). w3c and query reviews OK at iteration 2, documentation verified.
- L20: easter egg with Krakie, a small hidden game in the application (a hint is in Settings); scout review it1 OK.
- L21: standards and library watch (`docs/veille/`), Dependabot in flag-only mode (D-L21-01 to D-L21-03: no scheduled watch, no version bumps, manual Neo4j and Curiosity validation). w3c, neo4j and curiosity reviews OK.
- L22: built-in file editor ("Files" screen, CodeMirror 6, validation, diff preview, `/files` API); w3c and scout reviews OK at iteration 2.
- L23: humanizing the documentation and skills, step 1 (`humanizer` skill).
- L24: publishing, continuous integration (pytest, front-end build, manual acceptance runs) and supervised Dependabot.
- L25: start an ontology from a document (.txt, .md, .pdf) with a source excerpt, a "To confirm" badge and W3C checks; w3c and scout reviews it1.
- L32: reasoning with HermiT. A "Reason with HermiT" button in Conformance (consistency, unsatisfiable classes that you can click and that turn red in the editor, inferences you can add to the model through `/ops`, reclassified individuals; during the computation, Krakie the blacksmith and "HermiT is reasoning… (up to 30 s)", then a trophy if consistent or a worried Krakie otherwise), `POST /api/projects/{id}/reason`, Krakie intent `raisonne / vérifie la cohérence / run the reasoner`, Cloud Run image with Java by default (`WITH_REASONER=1`). Reviews: see `journal/L32/rapport.md`.
- L26: reading the ontology graph. A floating legend that shows only the encodings present, a "VOWL notation" mode (VOWL 2: classes as circles, external, equivalent and anonymous classes, datatypes, property characteristics), a "Show" menu with a density slider and a counter, SVG and PNG export of the graph as displayed, a "legend" step in the guided tour (19 steps). `GET /graph` stays backward compatible and gains (`external`, `equivalent`, `include=external,anonymous,thing`). w3c, scout, doc and humanizer reviews: see `journal/L26/rapport.md`.
- L28: built-in documentation (Documentation entry in the side menu, contents, search, links between files, offline), a "?" button per screen, Krakie `help` action, a tour step (20 steps). See "Built-in documentation and help" in `utilisateur.md`.
- L33: documentation in English. The user guide, limits, contributing, API and changelog pages exist as `.en.md` and are shown when the interface is in English. The "French only" banner now appears only on untranslated files (architecture, rules, glossary). Each heading of these files carries an explicit `{#id}`, identical in French and English, so the "?" button and Krakie open the right section in both languages. The `test_help_map.py` test checks the anchors in both versions.
