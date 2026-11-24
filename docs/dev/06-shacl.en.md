# 06. SHACL {#shacl}

The backend reads, writes, generates and runs SHACL shapes. It also derives hints for the transposition engine from them, since a shape is closer to a property graph schema than an OWL axiom is (D-004).

Sources read: `backend/ontoforge/shacl/import_shapes.py`, `backend/ontoforge/shacl/export_shapes.py`, `backend/ontoforge/shacl/owl_to_shacl.py`, `backend/ontoforge/shacl/validate.py`, `backend/ontoforge/shacl/_worker.py`, `backend/ontoforge/shacl/shacl_to_pg.py`, `backend/ontoforge/childproc.py`, `backend/ontoforge/editing/files.py`, `backend/ontoforge/api/analysis.py`, `backend/ontoforge/main.py`, `skills/shacl-modeling/SKILL.md`. Run through the test client on the `trap` sample.

## Role {#role}

| Function | Entry point | Route |
|---|---|---|
| Read a shapes file into a `ShapesModel` | `backend/ontoforge/shacl/import_shapes.py::parse_shapes` | `POST /api/projects/{pid}/import` (`kind=shapes` or detected) |
| Write a `ShapesModel` as RDF | `backend/ontoforge/shacl/export_shapes.py::serialize_shapes` | `GET /api/projects/{pid}/export/shapes` |
| Generate shapes from the ontology | `backend/ontoforge/shacl/owl_to_shacl.py::generate_shapes` | `POST /api/projects/{pid}/shacl/generate` (`merge`, `dry_run`) |
| Validate data | `backend/ontoforge/shacl/validate.py::validate` | `POST /api/projects/{pid}/shacl/validate` (data file) |
| Index constraints for the engine | `backend/ontoforge/shacl/shacl_to_pg.py::shape_constraints` | called by `backend/ontoforge/mapping/engine.py` |
| Meta-validate an edited shapes file | `backend/ontoforge/editing/files.py::shapes_diagnostics` | file editor (chapter 13) |

The `ShapesModel` is described in chapter [03](03-modele-interne.en.md#shapesmodel).

## Files {#fichiers}

| File | Responsibility |
|---|---|
| `backend/ontoforge/shacl/import_shapes.py` | `parse_shapes`, `graph_to_shapes`, `guess_format`, term encoding (`encode_term`, `decode_term`), `iter_all_property_shapes` |
| `backend/ontoforge/shacl/export_shapes.py` | `shapes_to_graph`, `shapes_to_graph_with_ids` (node → shape id table, to link results back), `serialize_shapes`, `path_to_sparql` |
| `backend/ontoforge/shacl/owl_to_shacl.py` | `_Gen` generator: one NodeShape `<Class>Shape` per named class, categorized notes |
| `backend/ontoforge/shacl/validate.py` | `validate`, `ShaclReport`, `ShaclResult`, isolated run `_run_isolated`, errors `ShaclLimitError` and `ShaclBusyError` |
| `backend/ontoforge/shacl/_worker.py` | child process script: pySHACL on three N-Triples graphs received as JSON |
| `backend/ontoforge/childproc.py` | `run_limited`: launches a capped Python script (memory, CPU, file size), minimal environment |
| `backend/ontoforge/shacl/shacl_to_pg.py` | `shape_constraints` (class → predicate → constraints index), `hints`, `PGHint` |

## Validation flow {#flux-validation}

```mermaid
sequenceDiagram
  participant F as Front
  participant A as api/analysis.py::shacl_validate
  participant V as validate.validate
  participant C as childproc.run_limited
  participant W as _worker.py (child process)
  F->>A: POST /shacl/validate (data file)
  A->>A: format from extension (DATA_FORMATS)
  A->>V: run_in_threadpool(validate, data, shapes, onto, format)
  V->>V: parse_into (safeguards); shapes_to_graph_with_ids
  V->>V: ont_graph = TBox only (individuals removed)
  V->>V: _SLOTS.acquire non-blocking (else ShaclBusyError → 503 + Retry-After)
  V->>C: JSON {data, shapes, ont: N-Triples, inference}
  C->>W: python -I -c <launcher>: setrlimit(AS, CPU, FSIZE) then runpy
  W->>W: pyshacl.validate(..., advanced=False, inplace=False)
  W-->>C: JSON {conforms, results (N-Triples), text}
  C-->>V: CompletedProcess (or TimeoutExpired)
  V->>V: results → ShaclResult (shape id, path, message in UI language), stable sort
  V-->>A: ShaclReport
```

Details:

- Isolation (SEC-05, L41). pySHACL runs in a child process started by `backend/ontoforge/childproc.py::run_limited`: `sys.executable -I -c <launcher>`; the launcher itself sets `RLIMIT_AS` (memory), `RLIMIT_CPU` and `RLIMIT_FSIZE` (0: no file writes) then runs the script with `runpy.run_path`. No `preexec_fn` (deadlock risk between `fork` and `exec` in a multi-threaded process). Environment reduced to `PATH`, `LANG`, `LC_ALL`, `PYTHONPATH`: no secret reaches the child. `cwd="/"`, `start_new_session=True`.
- Bounds: `ONTOFORGE_SHACL_TIMEOUT_S` (30 s), `ONTOFORGE_SHACL_MEMORY_MB` (2048), CPU = timeout + 2 s, `ONTOFORGE_SHACL_SLOTS` (2, between 1 and 32, read at import). Timeout, signal or `MemoryError`: `ShaclLimitError`, returned as a `conforms=false` report with a readable warning, not as an HTTP error.
- Busy: when all slots are taken, `ShaclBusyError` goes up to the handler in `backend/ontoforge/main.py`, which answers 503 with `Retry-After: 5`.
- Event loop: the route calls `validate` through `run_in_threadpool`, so the API stays responsive during a validation.
- Blank node labels: graphs travel as N-Triples; `_SameLabels` makes the reader keep labels, which lets the parent link `sh:sourceShape` back to the model's shape id (`shapes_to_graph_with_ids`).
- Supplied ontology: only the TBox (individuals removed) is passed as pySHACL `ont_graph`. The sample ontology's individuals produced one violation too many (D-L14-01).
- Inference: `none` by default (D-034, D-L2-01); `rdfs`, `owlrl` or `both` accepted by the function. The route does not offer the choice.

Run on the `trap` sample (`samples/trap/trap-data.ttl`): `conforms: false`, 8 results (the D-L14-01 oracle), about 0.3 s.

## Generation from OWL {#generation}

`backend/ontoforge/shacl/owl_to_shacl.py::generate_shapes` translates the ontology into a data contract (closed world). The full rules are in the module docstring; in short: one NodeShape `<Class>Shape` with `sh:targetClass` per named class; domain and range → property shape with `sh:datatype` or `sh:class`; property without domain → `<prop>UsageShape` with `sh:targetSubjectsOf`; functional → `sh:maxCount 1`; restrictions → `minCount` / `maxCount` (qualified if needed), `sh:class`, `sh:hasValue`; `oneOf` → `sh:in`; `hasKey` → `minCount 1` + `maxCount 1`; disjointness → `sh:not`; deprecated properties → deactivated shapes.

Every non-equivalent translation produces a **note** prefixed with a stable category (the front shows the notes as is, without filtering on these prefixes): `[OWA]`, `[RENFORCÉ]`, `[PARTIEL]`, `[NON-CORE]`, `[HÉRITAGE]`, `[IGNORÉ]`. On `trap`, generation gives 93 NodeShapes.

The route `POST /shacl/generate` accepts `dry_run` (preview, nothing written) and `merge` (default: existing shapes with the same id are kept, `setdefault`); without `merge`, generated shapes replace everything.

## Meta-validation {#meta-validation}

When the user edits a shapes file in the file editor, `backend/ontoforge/editing/files.py::shapes_diagnostics` validates the text against the `shacl-shacl.ttl` meta-shape shipped with pySHACL (`_shacl_shacl`), then reads it again with `parse_shapes`. Results are placed in the text (line, column); cascading findings of a malformed RDF list are reduced to one. If reading fails after meta-shape findings, these become blocking errors. This meta-validation runs **inside the server process** (not in the isolated child): the shapes are data at that point, their `sh:pattern` values are not executed.

## From SHACL to the property graph {#shacl-vers-pg}

`backend/ontoforge/shacl/shacl_to_pg.py::shape_constraints` indexes constraints **by target class then by predicate** (direct and inverse): `required`, `list` (true unless `maxCount 1`), `datatype`, `class`, `in`, `pattern`, `min_count`, `max_count`, shape ids. The engine calls it in `backend/ontoforge/mapping/engine.py` through a lazy import; if it fails, shapes are ignored with a warning and the analysis goes on. The engine rules that read this index are in `backend/ontoforge/mapping/rules/shacl.py` (chapter [07](07-moteur-analyse.en.md)).

## Libraries {#librairies}

| Library | Version | Why |
|---|---|---|
| pyshacl | 0.29.1 | SHACL Core and SHACL-SPARQL validation engine; also ships `shacl-shacl.ttl` |
| rdflib | 7.1.1 | graphs, N-Triples, `W3CNTriplesParser` reader |
| owlrl | 7.1.2 | used by pySHACL when `owlrl` inference is requested |

Versions pinned by D-L21-02.

## Decisions {#decisions}

- D-004: SHACL from v0.1.
- D-034, D-L2-01: no inference by default (`inference="none"`).
- D-L14-01: TBox only as `ont_graph` (8 violations on `trap`).
- D-L48-01: `xsd:string` enumerations as plain literals, otherwise `sh:in` compares badly under pySHACL.
- L39-secu (SEC-05) then L41: validation in a capped child process, slots and 503.

## Pitfalls and limits {#pieges}

- Inference and `sh:closed`: with `rdfs`, inferred triples are validated too; an inferred super-property makes a closed shape fail. This is the reason for D-034.
- Inheritance: `sh:targetClass` covers subclasses only if the `rdfs:subClassOf` triples are in the validated graph. Without a supplied ontology, instances of subclasses escape the superclass shapes.
- `python -I` ignores `PYTHON*` variables, including `PYTHONPATH`: the child only sees installed packages (pySHACL, rdflib), not OntoForge's code. This is intended, but a `_worker.py` importing `ontoforge` would fail outside an installation.
- Memory cap through `RLIMIT_AS`: it counts address space, not resident memory. 2048 MB of address space leave room for Python and pySHACL; a value that is too low makes the child fail at start with a "memory or time capped" message.
- **`RLIMIT_*` only exists on Unix**: `run_limited` is not meant for Windows (no `resource`). `À CONFIRMER`: exact behaviour on Windows not tested (the application runs in a Linux container).
- SHACL-SPARQL: run by pySHACL (`advanced=False` is enough for `sh:sparql`), with a warning in the report.

## How to add… {#comment-ajouter}

**…an OWL → SHACL translation.** Add the rule in the matching `_Gen` method (`gen_restriction`, `gen_properties`, `gen_classes`…), emit a note with an existing category if the translation is not equivalent, and a test in `backend/tests/test_shacl_owl_to_shacl.py`.

**…a SHACL constraint on reading.** Add it to the model (`Constraints` or `PropertyShape`, recorded decision), read it in `_Reader` of `import_shapes.py` (otherwise it goes to warnings), write it in `_Writer` of `export_shapes.py`, and index it in `shape_constraints` if the engine must take it into account.

**…another child-process job.** Reuse `backend/ontoforge/childproc.py::run_limited` with a standalone script (JSON input on stdin, JSON output on stdout, no `ontoforge` import), a non-blocking slot semaphore and a "busy" error turned into a 503, like `validate.py` and the local triplestore (chapter [10](10-triplestore-local.en.md)).
