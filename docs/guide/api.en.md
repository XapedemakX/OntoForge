# OntoForge REST API {#api-rest-d-ontoforge}

Prefix `/api`, JSON, errors `{"detail": "…"}` (messages in French). Full OpenAPI specification: `GET /openapi.json`. Interactive documentation: `/docs` (FastAPI, backend port 8000; behind nginx, only `/api` is proxied). Normative contract: `docs/CONTRACTS.md`.

The examples below are real responses (backend started with `ONTOFORGE_LLM_PROVIDER=mock`, `automaint` example, data in a temporary folder). Large fields are abbreviated (`…`, `{…}` = abbreviated object, `[…]` = abbreviated list). In the commands, `$P` is the project identifier and `$B` the base URL (`http://localhost:8000` in development; `http://localhost:8088` behind nginx).

## Conventions {#conventions}

- Target: `curiosity` or `neo4j` (`target` parameter, or path segment). On `analyze`, `queries/translate` and `queries/competency`, `target` is optional: the default is the project's target (`Project.target`). Any other value → `422 Cible inconnue « x » : attendu curiosity ou neo4j`.
- Errors: `404` project / example / finding not found, `422` invalid input (body, empty or unreadable file, unknown format), `413` file too large (assistant), `501` module missing (`module … pas encore disponible`), `502` / `503` assistant (invalid LLM response / not configured). Pydantic validation errors give `422` with `detail` (readable summary) and `errors` (detailed list).
- Finding identifiers: `<règle>:<IRI sujet>[:<suffixe>]`. A grouped decision is written `"<règle>:*"`.
- Absolute IRIs in all models.

## Route summary {#recapitulatif-des-routes}

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | health and version |
| GET | `/api/samples` | available examples |
| GET | `/api/projects` | list of projects (summaries) |
| POST | `/api/projects` | create a project (empty or from an example) |
| GET / PUT / DELETE | `/api/projects/{pid}` | read / replace / delete |
| POST | `/api/projects/{pid}/import` | import a file (ontology or shapes) |
| PUT | `/api/projects/{pid}/onto` | replace the `OntoModel` |
| PUT | `/api/projects/{pid}/shapes` | replace the `ShapesModel` |
| POST | `/api/projects/{pid}/dsl` | apply quick input |
| GET | `/api/projects/{pid}/export/ontology` | serialised ontology |
| GET | `/api/projects/{pid}/export/shapes` | serialised shapes |
| GET | `/api/projects/{pid}/conformance` | OWL 2 conformance |
| POST | `/api/projects/{pid}/shacl/generate` | generate shapes from the ontology |
| POST | `/api/projects/{pid}/shacl/validate` | validate a data file |
| POST | `/api/projects/{pid}/analyze` | analyse (target) |
| PUT | `/api/projects/{pid}/decisions/{target}` | save decisions |
| POST | `/api/projects/{pid}/decisions/{target}/accept-recommended` | accept the recommendations of the findings to decide (`?include_lost=true`: the lost ones too) |
| GET | `/api/projects/{pid}/generate/{target}` | generated files |
| GET | `/api/projects/{pid}/generate/{target}/zip` | zip archive |
| POST | `/api/projects/{pid}/queries/translate` | translate SPARQL |
| GET | `/api/projects/{pid}/queries/competency` | competency questions |
| GET | `/api/assistant/status` | LLM provider status |
| POST | `/api/assistant/draft` | ontology draft |
| POST | `/api/assistant/shapes` | shapes proposal |
| POST | `/api/assistant/explain` | explanation of a finding |
| GET | `/api/projects/{pid}/generations` | generation history (iteration 2, §7) |
| GET / PUT | `/api/settings` | settings (public view, secrets never sent back) |
| POST / PUT / DELETE | `/api/settings/providers[/{id}]` | LLM providers |
| POST | `/api/settings/providers/{id}/test` · `/api/settings/sparql/test` | connection tests |
| GET / POST / PUT / DELETE | `/api/settings/endpoints[/{id}]` · `PUT /endpoints/active` · `POST /endpoints/{id}/test` | SPARQL endpoints |
| POST | `/api/assistant/chat` · `/api/assistant/upload` | conversation, file upload |
| POST | `/api/projects/{pid}/ops` · `/ops/undo` · `/ops/redo` · GET `/ops/history` | editor: operations |
| GET | `/api/projects/{pid}/graph` · `/api/icons` | canvas graph, icons |
| GET / POST / PUT / DELETE | `/api/projects/{pid}/perimeters[/{id}]` · `PUT /perimeters/active` · `GET /perimeters/{id}/preview` | perimeters |
| GET / POST | `/api/projects/{pid}/query/suggest` · `/query/build` · `/query/run` · `/query/values` · `/query/nl` | guided querying |
| GET / POST / PUT / DELETE | `/api/projects/{pid}/queries/saved[/{qid}]` · GET `/queries/competency/guided` | saved queries |

## System {#systeme}


### `GET /api/health` {#get-api-health}

Backend health (used by the Docker healthcheck).

**Response 200**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### `GET /api/samples` {#get-api-samples}

Examples shipped in `samples/` (files `*-nondl.*` are ignored, D-037).

**Response 200**

```json
[
  {
    "name": "automaint",
    "title": "Automaint",
    "files": [
      "automaint-data.ttl",
      "automaint-shapes.ttl",
      "… 3 autres"
    ],
    "ontology": [
      "automaint.owl",
      "automaint.ttl"
    ],
    "shapes": [
      "automaint-shapes.ttl"
    ],
    "data": [
      "automaint-data.ttl"
    ]
  },
  {
    "name": "trap",
    "title": "Trap",
    "files": [
      "expected-findings.yaml",
      "trap-data.ttl",
      "… 3 autres"
    ],
    "ontology": [
      "trap.ttl"
    ],
    "shapes": [
      "trap-shapes.ttl"
    ],
    "data": [
      "trap-data.ttl"
    ]
  }
]
```

## Projects {#projets}


### `POST /api/projects` {#post-api-projects}

Creates a project. `name` is required. `sample` (`automaint` | `trap`) loads the initial ontology, shapes and decisions. Without `sample`, the project is empty. Response: the full `Project` (`onto`, `shapes`, `decisions`…).

**Request**

```bash
curl -X POST $B/api/projects -H "Content-Type: application/json" \
  -d '{"name":"Demo","sample":"automaint"}'
```

**Response 201**

```json
{
  "id": "demo-abb898",
  "name": "Demo",
  "description": "",
  "created_at": "2026-11-03T21:37:43+00:00",
  "updated_at": "2026-11-03T21:37:43+00:00",
  "target": "curiosity",
  "onto": {
    "meta": {
      "iri": "https://w3id.org/ontoforge/automaint",
      "labels": "{…}",
      "comments": "{…}",
      "annotations": "[…]",
      "deprecated": false,
      "…": "3 autres champs"
    },
    "classes": {
      "https://w3id.org/ontoforge/automaint#ElectricVehicle": "{…}",
      "https://w3id.org/ontoforge/automaint#Organization": "{…}",
      "https://w3id.org/ontoforge/automaint#Brand": "{…}",
      "https://w3id.org/ontoforge/automaint#MileageReading": "{…}",
      "https://w3id.org/ontoforge/automaint#RepairOrder": "{…}",
      "…": "19 autres champs"
    },
    "object_properties": {
      "https://w3id.org/ontoforge/automaint#installedIn": "{…}",
      "https://w3id.org/ontoforge/automaint#partOf": "{…}",
      "https://w3id.org/ontoforge/automaint#assignedTo": "{…}",
      "https://w3id.org/ontoforge/automaint#addresses": "{…}",
      "https://w3id.org/ontoforge/automaint#usesPart": "{…}",
      "…": "20 autres champs"
    },
    "datatype_properties": {
      "https://w3id.org/ontoforge/automaint#standardDurationMin": "{…}",
      "https://w3id.org/ontoforge/automaint#brandName": "{…}",
      "https://w3id.org/ontoforge/automaint#readingMileageKm": "{…}",
      "https://w3id.org/ontoforge/automaint#orderNumber": "{…}",
      "https://w3id.org/ontoforge/automaint#closedAt": "{…}",
      "…": "20 autres champs"
    },
    "annotation_properties": {
      "http://purl.org/dc/terms/created": "{…}",
      "http://www.w3.org/2004/02/skos/core#definition": "{…}",
      "http://purl.org/dc/terms/title": "{…}",
      "http://purl.org/dc/terms/description": "{…}"
    },
    "datatypes": {
      "https://w3id.org/ontoforge/automaint#ModelYear": "{…}"
    },
    "individuals": {
      "https://w3id.org/ontoforge/automaint#Hydrogen": "{…}",
      "https://w3id.org/ontoforge/automaint#Diesel": "{…}",
      "https://w3id.org/ontoforge/automaint#Electric": "{…}",
      "https://w3id.org/ontoforge/automaint#Petrol": "{…}"
    },
    "all_different": [],
    "…": "1 autres champs"
  },
  "shapes": {
    "shapes": {
      "https://w3id.org/ontoforge/automaint-shapes#BrandShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#DtcShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#GarageShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#MileageReadingShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#PartReferenceShape": "{…}",
      "…": "6 autres champs"
    },
    "property_shapes": {},
    "prefixes": {
      "sh": "http://www.w3.org/ns/shacl#",
      "skos": "http://www.w3.org/2004/02/skos/core#",
      "owl": "http://www.w3.org/2002/07/owl#",
      "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
      "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
      "…": "3 autres champs"
    },
    "warnings": []
  },
  "…": "3 autres champs"
}
```

### `GET /api/projects` {#get-api-projects}

Summaries (without the model contents).

**Response 200**

```json
[
  {
    "id": "demo-abb898",
    "name": "Demo",
    "description": "",
    "updated_at": "2026-11-03T21:37:43+00:00",
    "target": "curiosity",
    "stats": {
      "classes": 24,
      "object_properties": 25,
      "datatype_properties": 25,
      "individuals": 4,
      "shapes": 11
    }
  }
]
```

### `GET /api/projects/{pid}` {#get-api-projects-pid}

The full `Project`. `404` if the identifier is unknown:

**Response 200**

```json
{
  "id": "demo-abb898",
  "name": "Demo",
  "description": "",
  "created_at": "2026-11-03T21:37:43+00:00",
  "updated_at": "2026-11-03T21:37:43+00:00",
  "target": "curiosity",
  "onto": {
    "meta": {
      "iri": "https://w3id.org/ontoforge/automaint",
      "labels": "{…}",
      "comments": "{…}",
      "annotations": "[…]",
      "deprecated": false,
      "…": "3 autres champs"
    },
    "classes": {
      "https://w3id.org/ontoforge/automaint#ElectricVehicle": "{…}",
      "https://w3id.org/ontoforge/automaint#Organization": "{…}",
      "https://w3id.org/ontoforge/automaint#Brand": "{…}",
      "https://w3id.org/ontoforge/automaint#MileageReading": "{…}",
      "https://w3id.org/ontoforge/automaint#RepairOrder": "{…}",
      "…": "19 autres champs"
    },
    "object_properties": {
      "https://w3id.org/ontoforge/automaint#installedIn": "{…}",
      "https://w3id.org/ontoforge/automaint#partOf": "{…}",
      "https://w3id.org/ontoforge/automaint#assignedTo": "{…}",
      "https://w3id.org/ontoforge/automaint#addresses": "{…}",
      "https://w3id.org/ontoforge/automaint#usesPart": "{…}",
      "…": "20 autres champs"
    },
    "datatype_properties": {
      "https://w3id.org/ontoforge/automaint#standardDurationMin": "{…}",
      "https://w3id.org/ontoforge/automaint#brandName": "{…}",
      "https://w3id.org/ontoforge/automaint#readingMileageKm": "{…}",
      "https://w3id.org/ontoforge/automaint#orderNumber": "{…}",
      "https://w3id.org/ontoforge/automaint#closedAt": "{…}",
      "…": "20 autres champs"
    },
    "annotation_properties": {
      "http://purl.org/dc/terms/created": "{…}",
      "http://www.w3.org/2004/02/skos/core#definition": "{…}",
      "http://purl.org/dc/terms/title": "{…}",
      "http://purl.org/dc/terms/description": "{…}"
    },
    "datatypes": {
      "https://w3id.org/ontoforge/automaint#ModelYear": "{…}"
    },
    "individuals": {
      "https://w3id.org/ontoforge/automaint#Hydrogen": "{…}",
      "https://w3id.org/ontoforge/automaint#Diesel": "{…}",
      "https://w3id.org/ontoforge/automaint#Electric": "{…}",
      "https://w3id.org/ontoforge/automaint#Petrol": "{…}"
    },
    "all_different": [],
    "…": "1 autres champs"
  },
  "shapes": {
    "shapes": {
      "https://w3id.org/ontoforge/automaint-shapes#BrandShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#DtcShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#GarageShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#MileageReadingShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#PartReferenceShape": "{…}",
      "…": "6 autres champs"
    },
    "property_shapes": {},
    "prefixes": {
      "sh": "http://www.w3.org/ns/shacl#",
      "skos": "http://www.w3.org/2004/02/skos/core#",
      "owl": "http://www.w3.org/2002/07/owl#",
      "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
      "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
      "…": "3 autres champs"
    },
    "warnings": []
  },
  "…": "3 autres champs"
}
```

Error example:

```json
{
  "detail": "Projet « nope » introuvable"
}
```

### `PUT /api/projects/{pid}` {#put-api-projects-pid}

Replaces the project (body = `Project`, same fields as the `GET` response); `updated_at` is updated. Used to change the default target (`target`). Response: `Project`.

### `DELETE /api/projects/{pid}` {#delete-api-projects-pid}

Deletes the project folder and returns the deleted `Project`.

### `POST /api/projects/{pid}/import` {#post-api-projects-pid-import}

Multipart import: field `file` and `kind` = `ontology` | `shapes` | `auto` (detection by content). Ontology formats: Turtle, RDF/XML, JSON-LD, N-Triples, N3, TriG. `warnings` lists what the import could not structure.

**Request**

```bash
curl -X POST $B/api/projects/$P/import -F file=@samples/automaint/automaint.ttl -F kind=auto
```

**Response 200**

```json
{
  "kind": "ontology",
  "warnings": [
    "[format] : format détecté turtle, 578 triplets"
  ],
  "project": {
    "id": "demo-abb898",
    "name": "Demo",
    "description": "",
    "created_at": "2026-11-03T21:37:43+00:00",
    "updated_at": "2026-11-03T21:37:43+00:00",
    "target": "curiosity",
    "onto": {
      "meta": "{…}",
      "classes": "{…}",
      "object_properties": "{…}",
      "datatype_properties": "{…}",
      "annotation_properties": "{…}",
      "…": "4 autres champs"
    },
    "shapes": {
      "shapes": "{…}",
      "property_shapes": "{…}",
      "prefixes": "{…}",
      "warnings": "[…]"
    },
    "…": "3 autres champs"
  }
}
```

### `PUT /api/projects/{pid}/onto` and `PUT /api/projects/{pid}/shapes` {#put-api-projects-pid-onto-et-put-api-projects-pid-shapes}

Replace the `OntoModel` and the `ShapesModel` respectively (body = the model, see [`architecture.en.md`](architecture.en.md) §5). Response: `Project`. Used by the editing screens.

### `POST /api/projects/{pid}/dsl` {#post-api-projects-pid-dsl}

Applies quick input (one line = one axiom). `merge: true` merges with the existing ontology, `false` replaces it. Syntax errors do not raise an exception: they are returned per line and the rest is applied.

**Request**

```json
{"text": "Warehouse \"Entrepôt\"@fr\nStockItem < Part", "merge": true}
```

**Response 200**

```json
{
  "errors": [],
  "project": {
    "id": "demo-abb898",
    "name": "Demo",
    "description": "",
    "created_at": "2026-11-03T21:37:43+00:00",
    "updated_at": "2026-11-03T21:37:43+00:00",
    "target": "curiosity",
    "onto": {
      "meta": "{…}",
      "classes": "{…}",
      "object_properties": "{…}",
      "datatype_properties": "{…}",
      "annotation_properties": "{…}",
      "…": "4 autres champs"
    },
    "shapes": {
      "shapes": "{…}",
      "property_shapes": "{…}",
      "prefixes": "{…}",
      "warnings": "[…]"
    },
    "…": "3 autres champs"
  }
}
```

Line error example:

```json
{
  "errors": [
    {
      "line": 1,
      "message": "ligne non reconnue (voir l'aide du DSL)"
    }
  ]
}
```

### `GET /api/projects/{pid}/export/ontology?format=turtle` {#get-api-projects-pid-export-ontology-format-turtle}

Serialised ontology. `format`: `turtle` (default), `xml` (RDF/XML), `json-ld`, `nt`, `n3`. Plain-text response (`text/turtle`, `application/rdf+xml`, `application/ld+json`, `application/n-triples`, `text/n3`). Unknown format → `422`.

**Response 200**

```text
# OntoForge — export Turtle de <https://w3id.org/ontoforge/automaint>
@prefix am: <https://w3id.org/ontoforge/automaint#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
…
```

### `GET /api/projects/{pid}/export/shapes?format=turtle` {#get-api-projects-pid-export-shapes-format-turtle}

The project's shapes in Turtle.

**Response 200**

```text
@prefix am: <https://w3id.org/ontoforge/automaint#> .
@prefix ams: <https://w3id.org/ontoforge/automaint-shapes#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ams:BrandShape a sh:NodeShape ;
    sh:property [ sh:datatype xsd:string ;
            sh:minCount 1 ;
            sh:path am:brandName ] ;
…
```

### `GET /api/projects/{pid}/conformance` {#get-api-projects-pid-conformance}

`ConformanceReport`: `profiles` (DL, EL, QL, RL, RDFS), `profile_violations` (reasons per profile), `issues` (`level` = `error` | `warning` | `info`, `code` W01–W07 / BP01–BP07, `message`, `subject`, `spec_ref`).

**Response 200**

```json
{
  "profiles": {
    "DL": true,
    "EL": false,
    "QL": false,
    "RL": false,
    "RDFS": false
  },
  "profile_violations": {
    "DL": [],
    "EL": [
      "Brand : cardinalité (exactement 1) dans SubClassOf (hors OWL 2 EL).",
      "MileageReading : cardinalité (exactement 1) dans SubClassOf (hors OWL …",
      "… 28 autres"
    ],
    "QL": [
      "Brand : cardinalité en position de super-classe dans SubClassOf (hors …",
      "MileageReading : cardinalité en position de super-classe dans SubClass…",
      "… 22 autres"
    ],
    "RL": [
      "ElectricVehicle : ObjectSomeValuesFrom en position de super-classe dan…",
      "Brand : cardinalité exactly 1 (seules max 0 et max 1 sont permises) da…",
      "… 19 autres"
    ],
    "RDFS": [
      "axiome anonyme : utilise owl:Restriction, construction OWL absente de …",
      "partOf : utilise owl:TransitiveProperty, construction OWL absente de R…",
      "… 12 autres"
    ]
  },
  "issues": [
    {
      "level": "warning",
      "code": "W07",
      "message": "Propriété objet hasMileageReading : label manquant en fr et en.",
      "subject": "https://w3id.org/ontoforge/automaint#hasMileageReading",
      "spec_ref": "Bonnes pratiques (rdfs:label)"
    }
  ],
  "reasoner": {
    "used": "owlrl",
    "consistent": true,
    "unsatisfiable": [],
    "notes": []
  }
}
```

### `POST /api/projects/{pid}/shacl/generate` {#post-api-projects-pid-shacl-generate}

Generates shapes from the ontology. `merge: true` keeps the existing shapes, `false` replaces them. `notes`: what is not equivalent. With `dry_run: true`, nothing is saved: the response is `{project, generated, notes, dry_run: true}` (`project` unchanged, `generated` = the shapes produced), used by the preview on the Shapes screen.

**Request**

```json
{"merge": true, "dry_run": false}
```

**Response 200**

```json
{
  "notes": [
    "[OWA] Les shapes valident les données explicites (monde clos) : un axi…",
    "[HÉRITAGE] sh:targetClass couvre les instances des sous-classes unique…",
    "… 189 autres"
  ],
  "project": {
    "id": "demo-ddcee2",
    "…": "Project complet"
  }
}
```

### `POST /api/projects/{pid}/shacl/validate` {#post-api-projects-pid-shacl-validate}

Validates an RDF file (multipart `file`) against the project's shapes, without inference (D-034). Empty file → `422`.

**Request**

```bash
curl -X POST $B/api/projects/$P/shacl/validate -F file=@samples/automaint/automaint-data.ttl
```

**Response 200**

```json
{
  "conforms": false,
  "results": [
    {
      "focus": "https://w3id.org/ontoforge/automaint#ro_no_garage",
      "path": "https://w3id.org/ontoforge/automaint#performedAt",
      "severity": "Violation",
      "constraint": "http://www.w3.org/ns/shacl#MinCountConstraintComponent",
      "message": "Less than 1 values on am:ro_no_garage->am:performedAt",
      "…": "2 autres champs"
    },
    {
      "focus": "https://w3id.org/ontoforge/automaint#tech_idle",
      "path": "https://w3id.org/ontoforge/automaint#worksAt",
      "severity": "Violation",
      "constraint": "http://www.w3.org/ns/shacl#MinCountConstraintComponent",
      "message": "Less than 1 values on am:tech_idle->am:worksAt",
      "…": "2 autres champs"
    },
    "… 2 autres"
  ],
  "inference": "none",
  "warnings": [],
  "text": "Validation Report\nConforms: False\nResults (4):\nConstraint Violation in…"
}
```

## Analysis and arbitration {#analyse-et-arbitrage}


### `POST /api/projects/{pid}/analyze?target=curiosity` {#post-api-projects-pid-analyze-target-curiosity}

Runs the engine on the project's ontology and shapes. The decisions saved for the target are applied. Response: `PGModel` (see [`architecture.en.md`](architecture.en.md) §5). On the automaint example: 18 node types, 24 relations, 83 validations, 159 findings ({'auto': 117, 'review': 41, 'lost': 1}).

**Response 200**

```json
{
  "target": "curiosity",
  "meta": {
    "name": "AutoMaint — ontologie de maintenance automobile",
    "iri": "https://w3id.org/ontoforge/automaint",
    "generated_at": null,
    "ontoforge_version": "0.1.0"
  },
  "node_types": {
    "Brand": {
      "name": "Brand",
      "labels": "[…]",
      "source": "[…]",
      "key": "[…]",
      "properties": "[…]",
      "…": "1 autres champs"
    }
  },
  "edge_types": [
    {
      "name": "Addresses",
      "from": "ServiceOperation",
      "to": "DiagnosticTroubleCode",
      "reverse": "AddressedBy",
      "source": "https://w3id.org/ontoforge/automaint#addresses",
      "…": "7 autres champs"
    }
  ],
  "validations": [
    {
      "id": "C08:https://w3id.org/ontoforge/automaint#FuelType#v1",
      "kind": "enum",
      "node_type": "FuelType",
      "edge_type": null,
      "property": null,
      "…": "4 autres champs"
    }
  ],
  "materializations": [
    {
      "id": "O06:https://w3id.org/ontoforge/automaint#partOf#m1",
      "kind": "transitiveClosure",
      "edge_type": "PartOfTransitive",
      "chain": "[…]",
      "parent": null,
      "…": "4 autres champs"
    }
  ],
  "findings": [
    {
      "id": "C07:https://w3id.org/ontoforge/automaint#ElectricVehicle",
      "rule": "C07",
      "severity": "auto",
      "title": "Disjonction de classes",
      "detail": "am:ElectricVehicle disjointe de am:CombustionVehicle. Garanti par construction (types de nœuds distincts ou di…",
      "…": "6 autres champs"
    }
  ],
  "decisions": {}
}
```

### `PUT /api/projects/{pid}/decisions/{target}` {#put-api-projects-pid-decisions-target}

Merges `{finding: option}` decisions into the project and returns the recomputed `PGModel`. A `null` value removes the decision. Grouped key `"<règle>:*"`: applied to all findings of the rule that have no individual decision. Unknown option for the target → ignored, finding `G02`.

**Request**

```json
{
  "C07:https://w3id.org/ontoforge/automaint#ElectricVehicle": "validation",
  "D13:*": "validation"
}
```

**Response 200**

```json
{
  "decisions": {
    "C07:https://w3id.org/ontoforge/automaint#ElectricVehicle": "validation",
    "D13:*": "validation"
  },
  "…": "PGModel recalculé"
}
```

### `POST /api/projects/{pid}/decisions/{target}/accept-recommended` {#post-api-projects-pid-decisions-target-accept-recommended}

Saves the recommended option of the findings to decide (`review`) as a decision. Lost findings (`lost`) stay for the human to decide, unless `?include_lost=true` ("all" mode). Response: `PGModel`. On automaint, `decisions` then contains only the `review` findings (+ the `lost` ones with `include_lost=true`).

**Response 200**

```json
{
  "target": "neo4j",
  "decisions": {
    "C02:https://w3id.org/ontoforge/automaint#Engine": "multi_label",
    "C02:https://w3id.org/ontoforge/automaint#Party": "multi_label",
    "C02:https://w3id.org/ontoforge/automaint#Vehicle": "multi_label"
  },
  "…": "PGModel"
}
```

## Generation {#generation}


### `GET /api/projects/{pid}/generate/{target}` {#get-api-projects-pid-generate-target}

The target's files + `schema.graphql` + `README-graphql.md` + `rapport-transposition.md`, taking the decisions into account. Response: `{files: {name: content}}` (sizes in bytes on automaint: `Connector.cs` 65516, `Edges.cs` 7479, `README-curiosity.md` 22903, `RegisterSchema.cs` 1973, `Schema.cs` 18624, `schema.graphql` 26451, `README-graphql.md` 3106, `rapport-transposition.md` 33721).

**Response 200**

```json
{
  "files": {
    "Connector.cs": "// <auto-generated>\n// Généré par OntoForge 0.1.0 — cible Cu…",
    "Edges.cs": "// <auto-generated>\n// Généré par OntoForge 0.1.0 — cible Cu…",
    "README-curiosity.md": "# Schéma Curiosity — AutoMaint — ontologie de maintenance au…",
    "…": "5 autres fichiers"
  }
}
```

For Neo4j: `README-neo4j.md`, `ingest.cypher`, `model.mmd`, `schema.cypher`, `validation.cypher`, `schema.graphql`, `README-graphql.md`, `rapport-transposition.md`.

**File language**: optional `?lang=fr|en` parameter (422 for any other value). Without it, the interface language (`settings.language.ui`). It sets the comments, headers, READMEs, the connector's run-time messages and the transposition report. Code (identifiers, node, edge and property names) and the ontology's labels or comments are never translated: they are data.

### `GET /api/projects/{pid}/generate/{target}/zip` {#get-api-projects-pid-generate-target-zip}

The same files as an archive (same `?lang=fr|en` parameter). Actual headers: `content-type: application/zip`, `content-disposition: attachment; filename="<pid>-neo4j.zip"`.

## Queries {#requetes}


### `POST /api/projects/{pid}/queries/translate?target=neo4j` {#post-api-projects-pid-queries-translate-target-neo4j}

Translates a SPARQL `SELECT` query into Cypher, Curiosity (Query API pseudo-C#, `À VÉRIFIER`) and GraphQL. `lossy: true` flags a loss. `notes` details each loss (`[perte]`, `[curiosity]`, `[graphql]`).

**Request**

```json
{
  "sparql": "PREFIX am: <https://w3id.org/ontoforge/automaint#>\nSELECT ?v ?vin WHERE { ?v a am:Vehicle ; am:vin ?vin } LIMIT 10"
}
```

**Response 200**

```json
{
  "sparql": "PREFIX am: <https://w3id.org/ontoforge/automaint#>\nSELECT ?v ?vin WHERE { ?v a am:Vehicle ; am:vin ?vin } LIMIT 10",
  "query_form": "select",
  "cypher": "MATCH (v)\nRETURN v.uri AS v, v.vin AS vin\nLIMIT 10",
  "curiosity": null,
  "graphql": null,
  "notes": [
    "[curiosity] Type du nœud de départ inconnu : StartAt impossible sans type.",
    "[graphql] Type de la racine ambigu : pas de requête GraphQL."
  ],
  "lossy": false,
  "supported": true,
  "…": "1 autres champs"
}
```

### `GET /api/projects/{pid}/queries/competency?target=neo4j` {#get-api-projects-pid-queries-competency-target-neo4j}

Competency questions deduced from the model, each with its translation.

**Response 200**

```json
[
  {
    "id": "CQ01",
    "question": "Quels sont les Vehicle et leur vin ?",
    "sparql": "SELECT ?x ?l WHERE { ?x a <https://w3id.org/ontoforge/automaint#Vehicle> ; <https://w3id.org/ontoforge/automaint#vin> ?l . } ORDER BY ?l LIM…",
    "cypher": "MATCH (x)\nRETURN x.uri AS x, x.vin AS l\nORDER BY l\nLIMIT 50",
    "curiosity": null,
    "lossy": false,
    "notes": [
      "[curiosity] Type du nœud de départ inconnu : StartAt impossible sans type.",
      "… 1 autres"
    ],
    "pattern": "list"
  },
  "… 8 autres"
]
```

## Assistant {#assistant}


### `GET /api/assistant/status` {#get-api-assistant-status}

Active provider.

**Response 200**

```json
{
  "provider": "mock",
  "model": "mock",
  "configured": true,
  "default_provider_id": "mock",
  "providers": [
    {
      "id": "mock",
      "name": "Mock (démonstration)",
      "kind": "mock",
      "model": "mock",
      "configured": true,
      "…": "1 autres champs"
    }
  ]
}
```

### `POST /api/assistant/draft` {#post-api-assistant-draft}

Ontology draft (`OntoModel`) from a text (`kind` = `text`), a CSV (`csv`) or a `CREATE TABLE` (`sql`). `base_iri` is optional. It changes no project: the front end applies the accepted elements through `PUT /onto`. Errors: `422` (empty text / kind), `413` (too long), `503` (not configured), `502` (invalid LLM JSON after a retry).

**Request**

```json
{"text": "Un client possède plusieurs véhicules", "kind": "text"}
```

**Response 200**

```json
{
  "proposal": {
    "meta": {
      "iri": "https://w3id.org/ontoforge/draft",
      "labels": "{…}",
      "comments": "{…}",
      "annotations": "[…]",
      "deprecated": false,
      "…": "3 autres champs"
    },
    "classes": {
      "https://w3id.org/ontoforge/draft#Vehicle": "{…}",
      "https://w3id.org/ontoforge/draft#Car": "{…}",
      "https://w3id.org/ontoforge/draft#Truck": "{…}",
      "https://w3id.org/ontoforge/draft#Person": "{…}",
      "https://w3id.org/ontoforge/draft#Owner": "{…}",
      "…": "3 autres champs"
    },
    "object_properties": {
      "https://w3id.org/ontoforge/draft#owns": "{…}",
      "https://w3id.org/ontoforge/draft#ownedBy": "{…}",
      "https://w3id.org/ontoforge/draft#concernsVehicle": "{…}",
      "https://w3id.org/ontoforge/draft#assignedTo": "{…}",
      "https://w3id.org/ontoforge/draft#usesPart": "{…}"
    },
    "datatype_properties": {
      "https://w3id.org/ontoforge/draft#vin": "{…}",
      "https://w3id.org/ontoforge/draft#mileage": "{…}",
      "https://w3id.org/ontoforge/draft#registrationDate": "{…}",
      "https://w3id.org/ontoforge/draft#name": "{…}",
      "https://w3id.org/ontoforge/draft#orderNumber": "{…}",
      "…": "3 autres champs"
    },
    "annotation_properties": {},
    "datatypes": {},
    "individuals": {},
    "all_different": [],
    "…": "1 autres champs"
  },
  "explanation": "Modèle minimal pour répondre à : quels véhicules, quels propriétaires,…",
  "warnings": [
    "Le rôle Owner/Technician en sous-classes impose une classification sta…",
    "… 1 autres"
  ]
}
```

### `POST /api/assistant/shapes` {#post-api-assistant-shapes}

Shapes proposed for a project (deterministic generation `generate_shapes` + LLM enrichment: patterns, ranges, enumerations).

**Request**

```json
{"project_id": "<pid>"}
```

**Response 200**

```json
{
  "proposal": {
    "shapes": {
      "https://w3id.org/ontoforge/automaint-shapes#BrandShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#DtcShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#GarageShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#MileageReadingShape": "{…}",
      "https://w3id.org/ontoforge/automaint-shapes#PartReferenceShape": "{…}",
      "…": "6 autres champs"
    },
    "property_shapes": {},
    "prefixes": {
      "sh": "http://www.w3.org/ns/shacl#",
      "skos": "http://www.w3.org/2004/02/skos/core#",
      "owl": "http://www.w3.org/2002/07/owl#",
      "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
      "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
      "…": "3 autres champs"
    },
    "warnings": [
      "[OWA] Les shapes valident les données explicites (monde clos) : un axi…",
      "… 191 autres"
    ]
  },
  "explanation": "Shapes générées depuis l'ontologie (domaines, portées, cardinalités, c…"
}
```

### `POST /api/assistant/explain` {#post-api-assistant-explain}

Natural-language explanation of a finding (deterministic fallback without an LLM). `404` if the finding does not exist.

**Request**

```json
{
  "project_id": "<pid>",
  "target": "curiosity",
  "finding_id": "C02:https://w3id.org/ontoforge/automaint#Engine"
}
```

**Response 200**

```json
{
  "text": "Constat C02 — Héritage simple\n\nCe que cela signifie : Hiérarchie de am:Engine : 2 sous-classe(s) à parent unique (am:ElectricMotor, am:InternalCombustionEngine) ; une décision pour toute la hiérarchie..\nÉlément concerné : https://w3id.org/ontoforge/automaint#Engine.\n\nOptions possibles :\n- Multi-labels\n- Aplatir sur la racine concrète (recommandée)\n- Type de nœud distinct\n\nPourquoi pour Curiosity : l'option « flatten_…"
}
```

The three `POST /api/assistant/*` routes also accept an optional `provider_id` field (the provider to use): an iteration 2 feature being delivered.

## Iteration 2: settings, assistant, editor, querying {#iteration-2-parametres-assistant-editeur-requetage}

Normative contracts: `docs/CONTRACTS.md` §4 (settings, assistant), §5 (editor), §6 (querying), §7 (generations). These routes are stabilised at the closure of L8, L9, L10, L15. Code: `api/settings.py`, `api/assistant.py`, `api/editing.py`, `api/queries.py`. The examples below are built from the contracts and the pydantic models (they were not replayed against a running backend: `httpx` is missing from the documentation writer's environment). Large fields are abbreviated.

### Settings: `/api/settings` {#parametres-api-settings}

| Method | Path | Notes |
|---|---|---|
| GET | `/api/settings` | public view of `Settings`; **creates `settings.json` on the first call** |
| PUT | `/api/settings` | subset; `llm_providers` merged by `id`, `language` / `defaults` field by field |
| POST | `/api/settings/providers` | 201; 409 if the `id` exists |
| PUT / DELETE | `/api/settings/providers/{id}` | DELETE: 200 `{deleted, default_provider_id}`; 409 for `mock`; the default falls back to `mock` |
| POST | `/api/settings/providers/{id}/test` | optional body `{api_key?, base_url?, model?}` (test without saving) → `{ok, latency_ms, model, message}` |
| POST | `/api/settings/sparql/test` | `{url?, auth?}` → `{ok, latency_ms, message}` (`ASK {}`) |
| GET / POST | `/api/settings/endpoints` | POST: 201; 409 id taken, 422 URL |
| PUT / DELETE | `/api/settings/endpoints/{id}` | secret: absent or `""` = unchanged, `null` = deleted |
| PUT | `/api/settings/endpoints/active` | `{id \| null}`; 404 if unknown |
| POST | `/api/settings/endpoints/{id}/test` | `{ok, latency_ms, message}` |

Secrets are never sent back: `has_key`, `key_last4`, `key_unreadable`, `auth.has_secret` / `has_secret`, `secret_unreadable`. In `PUT`, an absent or `""` key is unchanged, `null` deletes it, a string replaces it. `kind`: `anthropic | openai_compat | ollama | mock`.

```bash
curl -s -X POST $B/api/settings/providers -H 'content-type: application/json' \
  -d '{"name":"Claude","kind":"anthropic","model":"<modèle>","api_key":"sk-ant-…"}'
# 201 → {"id":"claude","name":"Claude","kind":"anthropic","model":"…","has_key":true,"key_last4":"…","configured":true,…}

curl -s -X POST $B/api/settings/endpoints -H 'content-type: application/json' \
  -d '{"id":"local","name":"Local","url":"http://localhost:3030/sparql","timeout_s":30}'
curl -s -X PUT $B/api/settings/endpoints/active -H 'content-type: application/json' -d '{"id":"local"}'
# → {"active_endpoint_id":"local"}
```

The old `sparql_endpoint` field is migrated to the `default` endpoint and is still accepted in `PUT` (mirror).

### Assistant (extension) {#assistant-extension}

`GET /api/assistant/status` also returns `default_provider_id` and `providers: [{id, name, kind, model, configured, default}]`. `draft`, `shapes` and `explain` accept `provider_id?` (unknown: 404; not configured: 503).

| Method | Path | Input | Output |
|---|---|---|---|
| POST | `/api/assistant/chat` | `{project_id, messages:[{role, content}], provider_id?, attachments?:[{name, kind: csv\|sql\|text\|markdown, content}]}` | `{reply, proposal: OntoModel \| null, warnings}` |
| POST | `/api/assistant/upload` | multipart `file` (2 MB max: 413 beyond; empty file: 422) | `{name, kind, preview:{lines (20), total_lines, truncated, columns?, tables?}, size, content}` |

`content` (decoded text) is returned so that the front end can put it back unchanged in `attachments`. Recognised extensions: `.csv`, `.tsv`, `.sql`, `.md`, `.markdown`, `.txt`; otherwise detection by content.

### Editor: operations, graph, perimeters {#editeur-operations-graphe-perimetres}

```bash
curl -s -X POST $B/api/projects/$P/ops -H 'content-type: application/json' -d '{
  "label": "Nouvelle classe",
  "ops": [{"op":"add_class","name":"Trailer","label":"Remorque","parent":"https://w3id.org/ontoforge/automaint#Vehicle"}]}'
# → {"ok":true,"project":{…},"applied":1,"errors":[],"warnings":[],"can_undo":true,"can_redo":false}
```

`POST /ops` is all or nothing: on error, HTTP 200 with `ok=false`, `errors: [{index, message}]` and the project unchanged (500 operations max per call). Messages follow the interface language. A subclass that would close a cycle is refused ("Subclass cycle: … would close the loop", with the path); `POST /dsl` does the same and returns the offending line. The list of operations and validation rules (absolute IRI, no cycle, simple properties, datatypes of the OWL 2 map…) is in CONTRACTS §5. `POST /ops/undo` and `/ops/redo` answer like `/ops` plus `label` (409 if the stack is empty). `GET /ops/history` gives `{undo, redo, limit: 200, can_undo, can_redo}`.

`GET /api/projects/{pid}/graph?perimeter=&lang=fr&include=datatypes,individuals` → `{nodes, edges, skipped}` (nodes `{id, label, kind, icon, position, abstract, deprecated, collapsed}`; edges `{id, source, target, kind, label, iri}`, `id = kind|iri|source|target`, stable sort). `GET /api/icons?q=` → `{icons:[{id:"fa-car", style, label:{fr,en}, keywords}], total}` (accent-insensitive search).

Perimeters: `GET|POST /perimeters`, `GET|PUT|DELETE /perimeters/{id}`, `GET /perimeters/{id}/preview` → `{counts, excluded:[{id, rule, title, detail}]}`, `PUT /perimeters/active` `{id|null}` (interface state). Unknown classes and properties: 422; identifier taken: 409; unknown perimeter: 404. `?perimeter=<id>` applies to `analyze`, `generate/{target}` and `generate/{target}/zip` (without the parameter, `all` or `none`: the full ontology; the active state is never applied implicitly).

### Guided querying {#requetage-guide}

```bash
curl -s "$B/api/projects/$P/query/suggest?class=https://w3id.org/ontoforge/automaint%23Vehicle"
# → {"class":…,"label":"Véhicule","ancestors":[…],"subclasses":[…],"outgoing":[…],"incoming":[…],"data_properties":[…]}

curl -s -X POST $B/api/projects/$P/query/nl -H 'content-type: application/json' \
  -d '{"question":"véhicules réparés par Camille"}'
# → {"guided":{…},"explanation":"…","confidence":0.72,"unmatched":["réparés"],"mode":"deterministic","provider":"mock","sparql":"…","cypher":"…","curiosity":"…","notes":[…],"lossy":true,"warnings":[]}

curl -s -X POST $B/api/projects/$P/query/run -H 'content-type: application/json' -d '{"guided":{…},"limit":100}'
# → {"columns":[…],"rows":[{"vehicle":{"type":"uri","value":"…"},…}],"truncated":false,"elapsed_ms":42,"sparql":"…","endpoint_id":"local","graph":{"nodes":[…],"edges":[…]}}
```

| Method | Path | Purpose / errors |
|---|---|---|
| GET | `/query/suggest?class=` | outgoing / incoming relations and data properties of a class (404 unknown class) |
| GET | `/query/suggest?property=&from=[&inverse=true]` | target classes of a property (404 unknown property) |
| GET | `/query/suggest` | possible root classes |
| POST | `/query/build` | `{guided, target?}` → `{sparql, cypher, curiosity, graphql, notes, lossy, supported, warnings}`; 422 invalid variable |
| POST | `/query/run` | `{guided \| sparql, endpoint_id?, limit}`: read-only (UPDATE → 403, syntax → 422), no active endpoint → 409, timeout → 504, endpoint error → 502; hard ceiling 5000 rows |
| GET | `/query/values?class=&property=&q=&endpoint_id=` | 20 values suggested from the endpoint |
| POST | `/query/nl` | `{question, provider_id?, lang?, target?}`; unknown provider 404, empty question 422; `mode`: `llm` or `deterministic` |
| GET / POST | `/queries/saved` | 201 `{id, name, description, guided, sparql, created_at, updated_at}` |
| GET / PUT / DELETE | `/queries/saved/{qid}` | - |
| GET | `/queries/competency/guided?target=` | competency questions with a guided version when one exists |

Without reasoning on the endpoint side, `a C` does not return the subclasses: use `subclasses: true`. Subproperties are not expanded in the generated query.

### Generation history {#historique-des-generations}

`GET /api/projects/{pid}/generations` → list, most recent first: `{target, perimeter, at, files, findings_summary, project_updated_at}` (`findings_summary`: auto / review / lost counts and `pending`). Each `GET /generate/{target}` (not the zip) adds an entry (50 at most) without advancing `updated_at`. A generation is "outdated" if `project_updated_at` is earlier than the project's last change. `GET /api/projects` also exposes `created_at` and `source_files`.

### Semantics of `chosen` and of decisions {#semantique-de-chosen-et-des-decisions}

`Finding.chosen` is the identifier of the option decided by the human (`None` = not decided). `Finding.recommended` is the option applied by default. `PGModel.decisions` also keeps the decisions whose finding has disappeared, so they can be replayed if it reappears (`mapping/decisions.py`, docstring).
