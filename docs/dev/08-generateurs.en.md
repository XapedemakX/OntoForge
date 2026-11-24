# 08. Generators {#generateurs}

Generators turn a `PGModel` (chapter [07](07-moteur-analyse.en.md)) into ready-to-use files: Curiosity C# code, Neo4j Cypher scripts, a GraphQL schema, the transposition report and the justification file. They never read the ontology to decide anything: every decision is already in the `PGModel`. The ontology is only passed for labels and display details.

Sources read: `backend/ontoforge/targets/curiosity.py`, `backend/ontoforge/targets/neo4j.py`, `backend/ontoforge/targets/graphql.py`, `backend/ontoforge/targets/report.py`, `backend/ontoforge/targets/justification.py`, `backend/ontoforge/localize/gen.py`, `backend/ontoforge/standards/__init__.py`, `backend/ontoforge/projects/generations.py`, `backend/ontoforge/api/analysis.py`, `tools/dotnet/README.md`. Generation run on `samples/automaint/automaint.ttl` for both targets.

## Role and contract {#contrat}

Each target generator exposes `generate(pg, onto=None, lang=None) -> dict[str, str]` (file name → content, D-028, which replaces D-017). Output is deterministic (sorted by name or id), so tests need no reference files (D-038).

| Module | Files produced |
|---|---|
| `backend/ontoforge/targets/curiosity.py::generate` | `Schema.cs`, `Edges.cs`, `RegisterSchema.cs`, `Connector.cs`, `README-curiosity.md` |
| `backend/ontoforge/targets/neo4j.py::generate` | `schema.cypher`, `ingest.cypher`, `validation.cypher`, `model.mmd` (Mermaid), `README-neo4j.md` |
| `backend/ontoforge/targets/graphql.py::generate` | `schema.graphql`, `README-graphql.md` (for both targets) |
| `backend/ontoforge/targets/report.py::generate` | `rapport-transposition.md` (for both targets) |
| `backend/ontoforge/targets/justification.py::generate` | justification file, standalone HTML or Markdown (separate route) |

## Flow {#flux}

```mermaid
sequenceDiagram
  participant F as Front
  participant A as api/analysis.py
  participant E as run_analysis
  participant G as targets/<target>, graphql, report
  participant H as projects/generations.py
  F->>A: GET /generate/{target}?perimeter=&lang=
  A->>A: _gen_lang (fr|en, else UI language; 422 if unknown)
  A->>E: PGModel (decisions replayed)
  A->>A: lang=en → localize_pg_for_export (engine texts translated)
  loop targets.{target}, targets.graphql, targets.report
    A->>G: with gen.using_lang(gl): generate(pg, onto)
    G-->>A: {name: content}
  end
  A->>H: append(GenerationRecord) under lock → generations.json
  A-->>F: {files, missing}
```

- `backend/ontoforge/api/analysis.py::_generate` resolves each module with `optional_service`: a missing module is listed in `missing`; if all three are missing, 501.
- `GET /generate/{target}/zip` produces the same thing as an archive (`<pid>-<target>/<file>`), without a history entry.
- Rights: generation and its zip are classified as **write** (editor, owner) since D-L42-01: a reader does not generate. The route stays a `GET`; the CSRF token is required (chapter [12](12-comptes-partage-admin.en.md)).
- History: `backend/ontoforge/projects/generations.py` keeps `generations.json` next to the project (50 entries at most, `MAX_GENERATIONS`), under a lock, with atomic replacement. Since L41, a generation never writes `project.json` (it used to be able to overwrite a concurrent change). `GET /generations` reads it, most recent first.

## File language {#langue}

`backend/ontoforge/localize/gen.py` holds the context variable `GEN_LANG`. Generators write their texts (comments, headers, README, report) through `T(fr, en)`; `using_lang(lang)` sets the language during a call. Identifiers (types, edges, properties) and ontology labels are data and never go through `T`. Outside the API, the language is `fr`.

## Target versions {#versions}

Headers and the report show the versions used, taken from `PGMeta.target_versions` (set by `run_analysis` from `backend/ontoforge/standards/__init__.py::for_project`: factory values of `standards.json` < global settings default < project values). State of 23/11: Neo4j 5.26, Cypher 5, Curiosity.Library 26.11.7740, SHACL 1.0, SPARQL 1.1, RDF 1.1 (`standards.json` of 08/11). The Neo4j generator adapts its syntax to the version through `standards.neo4j_caps` (old `ASSERT` form, type constraints, relationship uniqueness…) and may prefix queries with `CYPHER n` (`cypher_prefix`).

## Curiosity {#curiosity}

`backend/ontoforge/targets/curiosity.py`: an intermediate plan (`_Plan`) computes C# names (identifiers escaped with `@` for reserved words, `cs_ident`, collisions with generated classes `GENERATED_CLASSES` resolved by appending `Node`), unique edge names, skipped abstract types. Then one renderer per file: `Schema.cs` (`[Node]` classes with `[Key]`, `[Property]`), `Edges.cs` (forward / reverse pair constants), `RegisterSchema.cs`, `Connector.cs` (ingestion skeleton with the validations, exit code 2 on violation), `README-curiosity.md`.

Curiosity.Library API calls not confirmed in any documentation read are listed in `TO_VERIFY` (and `TO_VERIFY_EN`) and carry `// À VÉRIFIER` in the code: return type of `Graph.Connect`, return value of `AddOrUpdate` / `TryAdd`, symmetric `Link`, `T[]` arrays, alignment of the NuGet package with the server… On `automaint`, the generated files contain 36 occurrences of `À VÉRIFIER`.

Real compilation is not done in CI (D-L21-03): `tools/dotnet/check-curiosity.ps1` (Windows, .NET 8 SDK, nuget.org access) compiles an exported zip against the real `Curiosity.Library` package and lists the errors, which are used to lift the `À VÉRIFIER` marks.

## Neo4j {#neo4j}

`backend/ontoforge/targets/neo4j.py`: an intermediate model `_Model` (versions, capabilities, Cypher prefix), then `schema.cypher` (uniqueness, key, existence, type constraints, indexes; whatever requires the Enterprise edition is commented out), `ingest.cypher` (`MERGE` templates per type and per relationship, type conversions through the profile's `PG_TO_CYPHER_CAST`), `validation.cypher` (one detection query per `Validation`, `_validation`), materializations (`_materialization`: transitive closure, chain, super-property…), `model.mmd` and the README. `quote` backtick-escapes an identifier if it is not a plain identifier or if it is reserved (`_RESERVED`); `literal` writes a Cypher value. The IRI property is found through the `IRI_MARKER` marker (`urn:ontoforge:iri`, D-L4-02), never by its name.

Real validation is done by manual import into Neo4j (D-L21-03); no testcontainers.

## GraphQL {#graphql}

`backend/ontoforge/targets/graphql.py`: one object type per `NodeType`, scalars (`SCALAR_MAP`, custom scalars `Date`, `DateTime`, `Decimal`…), lists, non-null for `required`, enums for enumerated properties; flattened inheritance → `interface` + concrete types; relationships in both directions (reverse field named after `reverse`); for Neo4j, `@relationship` directives of the Neo4j GraphQL Library (`À VÉRIFIER` in the code); `type Query` with lookup by key and paginated list.

## Transposition report {#rapport}

`backend/ontoforge/targets/report.py` writes `rapport-transposition.md`: figures summary, a single reminder of the closed-world assumption, nodes, relationships, what is lost or at risk (chosen option, or recommended one marked "not arbitrated", impact, compensation), what is transposed automatically, validations to implement, materializations, non-transposed findings, versions (`_versions_section`).

## Justification file {#justification}

`backend/ontoforge/targets/justification.py` (L47) produces a document for a client or reviewer: retained model, lost, compensated, human decisions (who, when, why, from `PGModel.decision_notes`), recommendations not followed, still to arbitrate, `auto` reclassifications. One plan (`build_blocks`) is rendered twice (`render_md`, `render_html`). Any text coming from the ontology, an account or an entered reason is **escaped** (`html.escape`; Markdown characters neutralized by `_md`). The HTML has no script, no remote resource and no event handler, and the route adds the module's `Content-Security-Policy` header (`CSP`) and `X-Content-Type-Options: nosniff`.

Route: `GET /justification/{target}?format=html|md&lang=`; read-only (available to readers), writes neither the project nor the history.

## Libraries {#librairies}

No dependency: generators are plain Python writing text. Syntax versions come from `backend/ontoforge/standards/standards.json`.

## Decisions {#decisions}

- D-005: Curiosity is the priority target.
- D-028: contract `generate(pg, onto) -> dict[str, str]`.
- D-038: no reference (golden) files; determinism, invariants and allowed shapes.
- D-L4-02: IRI property by marker, fallback key.
- D-L13-01: `Decimal` (C# `decimal`, GraphQL scalar `Decimal`, Neo4j `Float` with reported loss).
- D-L21-03: manual Neo4j and Curiosity validation.
- D-L42-01, D-L42-02: generation reserved to editor and owner, zip included.
- D-L47-02: justification file and decision trace.

## Pitfalls and limits {#pieges}

- Code not compiled in CI: the generated C# may not compile against a given Curiosity.Library version; the `À VÉRIFIER` marks are the list of known risks.
- Neo4j edition: existence and type constraints require Enterprise; they are emitted commented out, to be uncommented.
- Optional `onto`: a generator must work with `onto=None` (contract); whatever depends on it (GraphQL subtypes, report labels) needs a fallback.
- Translation: with `lang=en`, engine texts are translated by `localize_pg_for_export`; a text without a translation stays in French inside an English file.

## How to add a target or a file {#comment-ajouter}

**…a file to an existing target.** Add a render function in the module and the key in the dictionary returned by `generate`; keep a deterministic order; texts through `T(fr, en)`; shape and determinism tests in `backend/tests/test_target_<target>.py`.

**…a new target** (example: Memgraph). A generator is not enough: `Target` is a `Literal` in `backend/ontoforge/core/pg_model.py` (normative contract, recorded decision), the engine needs a profile `backend/ontoforge/mapping/profiles/<target>.py` and its adapter in `profile_api.py`, the rule catalog has recommendations per target (`reco`), `TARGETS` in `backend/ontoforge/api/_common.py` lists accepted targets, `Project.decisions` has one key per target, and the front has its own lists. The generator `targets/<target>.py` is found by name (`targets.{target}`).
