# 10. Local triplestore (pyoxigraph) {#triplestore-local}

Each project can have an embedded triplestore, with no external server. The ontology, individuals and data files are loaded into it. It is queried in SPARQL from guided querying (chapter [09](09-requetes.en.md)), RDFS or OWL RL inference is materialized in it, and its content is validated against the shapes.

Sources read: `backend/ontoforge/localstore/store.py`, `backend/ontoforge/localstore/runner.py`, `backend/ontoforge/localstore/_worker.py`, `backend/ontoforge/localstore/_infer_worker.py`, `backend/ontoforge/api/local_store.py`, `backend/ontoforge/api/queries.py`, `docs/CONTRACTS.md` §6.1, tests `backend/tests/test_local_store.py`, `backend/tests/test_local_store_review.py`, `backend/tests/test_local_store_union.py`.

## Files {#fichiers}

| File | Responsibility |
|---|---|
| `backend/ontoforge/localstore/store.py` | content and persistence: named graphs, per-project readers / writer lock, synchronization with the ontology (`ensure`), loading (`load_data`), inference (`materialize`), union (`rebuild_union`), statistics, caps (`limits`) |
| `backend/ontoforge/localstore/runner.py` | `run_local`: runs a query in a child process; `guard` (read-only, `SERVICE` rejected); `dataset_clause` (`FROM`, `FROM NAMED`) |
| `backend/ontoforge/localstore/_worker.py` | query child process: opens the database **read-only** (`Store.read_only`), imports only pyoxigraph |
| `backend/ontoforge/localstore/_infer_worker.py` | inference child process: owlrl on N-Triples received on stdin, returns only new and useful facts (`useful`) |
| `backend/ontoforge/api/local_store.py` | routes `/api/projects/{pid}/store`: `GET /stats`, `POST /load`, `DELETE`, `POST /validate` |

## Layout {#disposition}

On disk: `$ONTOFORGE_DATA/projects/<id>/triplestore/{db/, meta.json}` (Oxigraph RocksDB database and metadata). With `ONTOFORGE_LOCAL_STORE_DIR`, the triplestore lives in `<folder>/<id>` (instance local disk): on Cloud Run, `/data` is a Cloud Storage mount on which RocksDB (locks, `mmap`, renames) must not live. That folder is ephemeral and rebuilt on demand.

| Named graph | Content |
|---|---|
| `urn:ontoforge:graph:ontology` | TBox of the project ontology (without individuals), regenerated on every synchronization |
| `urn:ontoforge:graph:individuals` | editor individuals, with their linked anonymous nodes |
| `urn:ontoforge:graph:data:<name>` | one imported data file (name normalized by `slug`); all graphs of the file are flattened into it |
| `urn:ontoforge:graph:inferred` | triples materialized by owlrl, disposable |
| default graph | **deduplicated union** of the named graphs, rebuilt on every write (`rebuild_union`, D-L19-01) |

D-L19-01: Oxigraph 0.5.13 serves `use_default_graph_as_union` and multiple `FROM` as a multiset (a triple present in two graphs counts twice), unlike SPARQL 1.1 §13. The store therefore materializes the union as a set, and the child merges multiple `FROM` itself (`dataset_clause`).

## Query flow {#flux-requete}

```mermaid
sequenceDiagram
  participant A as api/queries.py (endpoint kind=local)
  participant R as runner.run_local
  participant S as store
  participant W as _worker.py (child)
  A->>R: sparql, limit, timeout_s
  R->>R: guard: query_form (UPDATE → 403, syntax → 422); SERVICE → 403
  R->>R: force_limit (limit + 1)
  R->>S: ensure(pid, p): creates or resynchronizes if the ontology digest changed
  R->>S: lock(pid).read()
  R->>W: childproc.run_limited (memory, CPU, no file writes, minimal environment)
  W->>W: Store.read_only(path); query; truncated cells
  W-->>R: JSON {form, columns, rows, truncated} or {error}
  R-->>A: QueryResult (same shape as a remote endpoint)
```

- Lazy synchronization: `ensure` compares a SHA-1 digest of the ontology (`signature`) with the one in `meta.json`; if it changed, it rewrites the ontology and individuals graphs, and marks the inference `stale`.
- Lock: one `_RWLock` per project (`lock(pid)`), several readers or a single writer. Deleting a project (`drop`) waits for running queries.
- Short opening: `_with_store` opens the database, calls the function, rebuilds the union after a write, then deletes the only reference and calls `gc.collect()`: Oxigraph only closes RocksDB when the object is destroyed. An exception's traceback is cleared for the same reason (it would keep the database open).
- Child process: the timeout is really enforced (the child is killed), caps set by `backend/ontoforge/childproc.py::run_limited` (chapter [06](06-shacl.en.md#flux-validation)). The number of children is bounded since L53 (DF-B13): `store.py::child_slot` (a `BoundedSemaphore` taken without waiting, `ONTOFORGE_LOCAL_STORE_SLOTS`, 2 by default, between 1 and 32, read at import) wraps every child launch, **queries and inference together, all projects together**. When full: `StoreBusy` (a `StoreError` subclass, 503, `retry_after = 5`), rendered as `Retry-After: 5` by `api/queries.py::_ep_error` and `api/local_store.py::_err`; a refused inference cancels the load (all or nothing, the previous graph is restored). The place is taken just before the launch and released after (also on timeout or error), never while waiting for the project lock.

## Loading and inference {#chargement}

`backend/ontoforge/localstore/store.py::load_data`: file size capped, **streamed** reading into a temporary in-memory store (`parse_to_store`, stops as soon as the triple cap is exceeded), total check, replacement of the file's graph, optional inference; if inference fails, the graph's previous content is restored (all or nothing). Before reading, `parse_to_store` applies the guards of `backend/ontoforge/io/safe_parse.py` (since L52, DF-B08). `check_xml(raw, strict=True)` rejects any `DOCTYPE` in RDF/XML, because Oxigraph 0.5.13 would expand internal entities. It fails closed: a document start that expat cannot read up to the first element, or an unknown declared encoding, is also rejected, because Oxigraph is more tolerant than expat and would carry on. Ontology import (`parse_into`) keeps the non-strict mode, rdflib being as strict as expat. `check_jsonld` rejects a remote JSON-LD context and nesting deeper than 200 levels. A refusal gives a 422 and nothing is written. Oxigraph's reader also rejects any remaining remote context itself (message translated by `_parse_error`).

`materialize` computes the owlrl closure (semantics `rdfs`, `owlrl`, `both`) of the ontology, individuals and data, in the `_infer_worker.py` child process, started by `backend/ontoforge/childproc.py::run_limited` like the queries (reduced environment, memory `ONTOFORGE_LOCAL_STORE_MEMORY_MB`, CPU = timeout + 2 s; since L52, DF-B07), then replaces the inferred graph. Timeout exceeded: 504; memory or CPU cap reached (child killed by a signal or `MemoryError`): 413 "memory or computation time limit reached". The child returns only useful facts about individuals (domain class types, property values; no vocabulary noise and no anonymous objects, which Oxigraph would rename on reload). It reports on stderr the ignored `owl:hasKey` axioms (prp-key too slow in owlrl) and the inferred `owl:sameAs`; these signals become French notes, translated in the response.

`POST /store/validate` validates individuals and data (without the TBox; with the inferred graph if `include_inferred`) against the project shapes, with the same `validate` function as chapter 06.

## Caps {#plafonds}

| Variable | Default | Effect |
|---|---|---|
| `ONTOFORGE_LOCAL_STORE_MAX_TRIPLES` | 1,000,000 (Cloud Run: 50,000) | triples in the store; beyond, 413 |
| `ONTOFORGE_LOCAL_STORE_MAX_UPLOAD_MB` | 25 (Cloud Run: 5) | size of a loaded file; 413 |
| `ONTOFORGE_LOCAL_STORE_MAX_INFERENCE_TRIPLES` | 30,000 | inference source triples (owlrl materializes in memory); 413 |
| `ONTOFORGE_LOCAL_STORE_MAX_VALIDATION_TRIPLES` | 60,000 | triples passed to SHACL validation |
| `ONTOFORGE_LOCAL_STORE_TIMEOUT_S` | 20 | query timeout (a query may ask for 1 to 120 s); 504 |
| `ONTOFORGE_LOCAL_STORE_INFERENCE_TIMEOUT_S` | 90 | inference timeout; 504 |
| `ONTOFORGE_LOCAL_STORE_MEMORY_MB` | 3072 (Cloud Run: 640) | address-space cap of each query and inference child; 413 if inference reaches it. Measured on 24/11: opening the database needs 576 MB for 4,700 triples (512 MB fails) and 640 MB for 1,000,000 triples, the store cap (32 MB resident); inference at 31,000 source triples fits in 576 MB (92 MB resident). This floor leaves little working memory: the Cloud Run value of 640 MB is the lowest setting that passed 10 runs out of 10 (aggregate query on a 50,000-triple database; 608 MB too, 512 MB fails 2 runs out of 10) |
| `ONTOFORGE_LOCAL_STORE_SLOTS` | 2 (Cloud Run: 1) | number of simultaneous children, queries and inference together, all projects; between 1 and 32, invalid value → 2; when full: 503 with `Retry-After: 5` |
| `ONTOFORGE_LOCAL_STORE_LOAD_SLOTS` | 4 (Cloud Run: 1) | simultaneous file loads (parsing and writing in the **server**, about 1.7 MB of memory per 1,000 triples); between 1 and 8; when full: 503 with `Retry-After: 5` (`load_slot`, taken by the route before the file is read) |
| `ONTOFORGE_LOCAL_STORE_TOTAL_MB` | 0 = no cap (Cloud Run: 64) | cap on the total size of the `ONTOFORGE_LOCAL_STORE_DIR` folder (in-memory disk on Cloud Run); a load for which `(folder size + 500 bytes × triples) × 1.25` would exceed it is refused: 413 "Local triplestore space full". No effect when the triplestore lives in the project folder |
| `ONTOFORGE_LOCAL_STORE_IDLE_MIN` | 0 = never (Cloud Run: 30) | minutes of inactivity after which a project's database is deleted (`purge_idle`). **Loaded data files are lost**; the ontology and individuals come back on demand. `stats` then returns `purged` (lost files, translated message) until a file is reloaded |
| `ONTOFORGE_LOCAL_STORE_DIR` | — | local (ephemeral) folder instead of `<project>/triplestore` |

`limits()` reads these variables again on every call (minimum 1, invalid value → default; 0 allowed for `TOTAL_MB` and `IDLE_MIN`). `LOAD_SLOTS` and `SLOTS` are read at import.

Ephemeral disk (D-L53-02): `purge_idle` runs at the start of `ensure` and `load_data` (so before any local query), with no background task. For each old database it takes `lock(pid).try_write()`: if a query, a load or an inference holds the lock, the database is left and purged later. The usage clock (`touch`) is updated by `ensure`; `stats` does not update it (an open page does not keep a database alive). `clear`, `drop` and `purge` also forget the purge notice. The clock is read a second time once the lock is held: a use that starts between the read and the lock saves the database; `stats` redoes `exists` under the read lock. The inferred graph counts toward the cap: `materialize` calls `check_disk_budget` (inferred triples minus those already there) BEFORE replacing the inferred graph, all-or-nothing 413 refusal (the old graph is kept; a load that asked for inference restores its file). The check is not atomic across projects (two size computations can cross): on Cloud Run a single load place and a single inference place serialize them, the rest fits in the 1.25 margin. Known limit: the load place is held while waiting for the project lock (the parsed file occupies server memory meanwhile), so a long query on one project makes the other loads answer 503; acceptable for a one-account demo. The test `test_b13_purge_and_loads_run_concurrently_without_error` runs loads, reads and purges together and checks the final state of the databases.

## Libraries {#librairies}

| Library | Version | Why |
|---|---|---|
| pyoxigraph | 0.5.13 | embedded SPARQL 1.1 Query engine (Oxigraph, RocksDB); evaluation in `docs/veille/triplestore-embarque.md` |
| owlrl | 7.1.2 | RDFS / OWL RL inference in the child |
| rdflib | 7.1.1 | ontology export, SPARQL parsing for the safeguards, graph passed to validation (`to_rdflib`) |

## Decisions {#decisions}

- D-L19-01: default graph = materialized deduplicated union; multiple `FROM` merged as a set.
- L41 (L39-02, L39-03): queries in a capped child process.

## Pitfalls and limits {#pieges}

- No SPARQL writes: the triplestore is filled through `POST /store/load`, never through `INSERT`.
- Union rebuilt on every write: cost proportional to the content; the price of a correct default graph.
- In-memory inference: 30,000 source triples at most; beyond that, an endpoint with reasoning.
- `owl:hasKey` is not applied by local inference (note in the response).
- A literal or IRI larger than 16 MiB makes Oxigraph's reader raise `MemoryError` (maximum size of its buffer), even under the 25 MB upload cap: `parse_to_store` answers 413 "element too large" (L52; before, 500).
- Anonymous nodes: Oxigraph renames them on every load; do not rely on their labels.
- `guard`, `_has_service` and `dataset_clause` in `localstore/runner.py` parse the query with rdflib in the server process: these calls go through `queries/sparql_lock.py` (L53, DF-B17), because the parser is not reentrant. Before, two simultaneous queries could fail with 422, and `_has_service` (second safety net on `SERVICE`) and `dataset_clause` (reading `FROM`), which swallow parse errors, were silently skipped.

## How to add… {#comment-ajouter}

**…an inference semantics.** Add it to `SEMANTICS`, handle it in `_infer_worker.py` (and in its `useful` filter), and offer it in the `POST /store/load` route (`inference`).

**…a file format.** Add it to `FORMATS` and `FORMAT_NAMES` (pyoxigraph format), and to `detect_format` if the content can reveal it. Route the content through the checks of `backend/ontoforge/io/safe_parse.py` if it is XML or JSON-LD.
