# API REST d'OntoForge

Préfixe `/api`, JSON, erreurs `{"detail": "…"}` (messages en français). Spécification OpenAPI complète : `GET /openapi.json` ; documentation interactive : `/docs` (FastAPI, port du backend 8000 ; derrière nginx, seul `/api` est proxifié). Contrat normatif : `docs/CONTRACTS.md`.

Les exemples ci-dessous sont des réponses réelles (backend lancé avec `ONTOFORGE_LLM_PROVIDER=mock`, exemple `automaint`, données dans un dossier temporaire). Les champs volumineux sont abrégés (`…`, `{…}` = objet abrégé, `[…]` = liste abrégée). Dans les commandes, `$P` est l'identifiant du projet et `$B` l'URL de base (`http://localhost:8000` en développement ; `http://localhost:8088` derrière nginx).

## Conventions

- Cible : `curiosity` ou `neo4j` (paramètre `target`, ou segment de chemin). Sur `analyze`, `queries/translate` et `queries/competency`, `target` est facultatif : défaut = cible du projet (`Project.target`). Toute autre valeur → `422 Cible inconnue « x » : attendu curiosity ou neo4j`.
- Erreurs : `404` projet / exemple / constat introuvable, `422` entrée invalide (corps, fichier vide ou illisible, format inconnu), `413` fichier trop volumineux (assistant), `501` module absent (`module … pas encore disponible`), `502` / `503` assistant (réponse LLM invalide / non configuré). Les erreurs de validation pydantic donnent `422` avec `detail` (résumé lisible) et `errors` (liste détaillée).
- Identifiants de constat : `<règle>:<IRI sujet>[:<suffixe>]` ; une décision groupée s'écrit `"<règle>:*"`.
- IRIs absolues dans tous les modèles.

## Récapitulatif des routes

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/api/health` | santé et version |
| GET | `/api/samples` | exemples disponibles |
| GET | `/api/projects` | liste des projets (résumés) |
| POST | `/api/projects` | créer un projet (vide ou depuis un exemple) |
| GET / PUT / DELETE | `/api/projects/{pid}` | lire / remplacer / supprimer |
| POST | `/api/projects/{pid}/import` | importer un fichier (ontologie ou shapes) |
| PUT | `/api/projects/{pid}/onto` | remplacer l'`OntoModel` |
| PUT | `/api/projects/{pid}/shapes` | remplacer le `ShapesModel` |
| POST | `/api/projects/{pid}/dsl` | appliquer la saisie rapide |
| GET | `/api/projects/{pid}/export/ontology` | ontologie sérialisée |
| GET | `/api/projects/{pid}/export/shapes` | shapes sérialisées |
| GET | `/api/projects/{pid}/conformance` | conformité OWL 2 |
| POST | `/api/projects/{pid}/shacl/generate` | générer des shapes depuis l'ontologie |
| POST | `/api/projects/{pid}/shacl/validate` | valider un fichier de données |
| POST | `/api/projects/{pid}/analyze` | analyser (cible) |
| PUT | `/api/projects/{pid}/decisions/{target}` | enregistrer des décisions |
| POST | `/api/projects/{pid}/decisions/{target}/accept-recommended` | accepter les recommandations des constats à arbitrer (`?include_lost=true` : aussi les perdus) |
| GET | `/api/projects/{pid}/generate/{target}` | fichiers générés |
| GET | `/api/projects/{pid}/generate/{target}/zip` | archive zip |
| POST | `/api/projects/{pid}/queries/translate` | traduire du SPARQL |
| GET | `/api/projects/{pid}/queries/competency` | questions de compétence |
| GET | `/api/assistant/status` | état du fournisseur LLM |
| POST | `/api/assistant/draft` | brouillon d'ontologie |
| POST | `/api/assistant/shapes` | proposition de shapes |
| POST | `/api/assistant/explain` | explication d'un constat |
| GET | `/api/projects/{pid}/generations` | historique des générations (itération 2, §7) |
| GET / PUT | `/api/settings` | paramètres (vue publique, secrets jamais renvoyés) |
| POST / PUT / DELETE | `/api/settings/providers[/{id}]` | fournisseurs LLM |
| POST | `/api/settings/providers/{id}/test` · `/api/settings/sparql/test` | tests de connexion |
| GET / POST / PUT / DELETE | `/api/settings/endpoints[/{id}]` · `PUT /endpoints/active` · `POST /endpoints/{id}/test` | endpoints SPARQL |
| POST | `/api/assistant/chat` · `/api/assistant/upload` | conversation, dépôt de fichier |
| POST | `/api/projects/{pid}/ops` · `/ops/undo` · `/ops/redo` · GET `/ops/history` | éditeur : opérations |
| GET | `/api/projects/{pid}/graph` · `/api/icons` | graphe du canvas, icônes |
| GET / POST / PUT / DELETE | `/api/projects/{pid}/perimeters[/{id}]` · `PUT /perimeters/active` · `GET /perimeters/{id}/preview` | périmètres |
| GET / POST | `/api/projects/{pid}/query/suggest` · `/query/build` · `/query/run` · `/query/values` · `/query/nl` | requêtage guidé |
| GET / POST / PUT / DELETE | `/api/projects/{pid}/queries/saved[/{qid}]` · GET `/queries/competency/guided` | requêtes sauvegardées |

## Système


### `GET /api/health`

Santé du backend (utilisée par le healthcheck Docker).

**Réponse 200**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### `GET /api/samples`

Exemples livrés dans `samples/` (les fichiers `*-nondl.*` sont ignorés, D-037).

**Réponse 200**

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

## Projets


### `POST /api/projects`

Crée un projet. `name` obligatoire ; `sample` (`automaint` | `trap`) charge ontologie, shapes et décisions initiales ; sans `sample`, projet vide. Réponse : `Project` complet (`onto`, `shapes`, `decisions`…).

**Requête**

```bash
curl -X POST $B/api/projects -H "Content-Type: application/json" \
  -d '{"name":"Demo","sample":"automaint"}'
```

**Réponse 201**

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

### `GET /api/projects`

Résumés (sans le contenu des modèles).

**Réponse 200**

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

### `GET /api/projects/{pid}`

Le `Project` complet. `404` si l'identifiant est inconnu :

**Réponse 200**

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

Exemple d'erreur :

```json
{
  "detail": "Projet « nope » introuvable"
}
```

### `PUT /api/projects/{pid}`

Remplace le projet (corps = `Project`, mêmes champs que la réponse de `GET`) ; `updated_at` est mis à jour. Sert au changement de cible par défaut (`target`). Réponse : `Project`.

### `DELETE /api/projects/{pid}`

Supprime le dossier du projet ; renvoie le `Project` supprimé.

### `POST /api/projects/{pid}/import`

Import multipart : champ `file` et `kind` = `ontology` | `shapes` | `auto` (détection par contenu). Formats d'ontologie : Turtle, RDF/XML, JSON-LD, N-Triples, N3, TriG ; `warnings` liste ce que l'import n'a pas pu structurer.

**Requête**

```bash
curl -X POST $B/api/projects/$P/import -F file=@samples/automaint/automaint.ttl -F kind=auto
```

**Réponse 200**

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

### `PUT /api/projects/{pid}/onto` et `PUT /api/projects/{pid}/shapes`

Remplacent respectivement l'`OntoModel` et le `ShapesModel` (corps = le modèle, cf. [`architecture.md`](architecture.md) §5). Réponse : `Project`. Utilisés par les écrans d'édition.

### `POST /api/projects/{pid}/dsl`

Applique la saisie rapide (une ligne = un axiome). `merge: true` fusionne avec l'ontologie existante, `false` la remplace. Les erreurs de syntaxe ne lèvent pas d'exception : elles sont renvoyées par ligne, le reste est appliqué.

**Requête**

```json
{"text": "Warehouse \"Entrepôt\"@fr\nStockItem < Part", "merge": true}
```

**Réponse 200**

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

Exemple d'erreur de ligne :

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

### `GET /api/projects/{pid}/export/ontology?format=turtle`

Ontologie sérialisée. `format` : `turtle` (défaut), `xml` (RDF/XML), `json-ld`, `nt`, `n3`. Réponse en texte (`text/turtle`, `application/rdf+xml`, `application/ld+json`, `application/n-triples`, `text/n3`). Format inconnu → `422`.

**Réponse 200**

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

### `GET /api/projects/{pid}/export/shapes?format=turtle`

Shapes du projet en Turtle.

**Réponse 200**

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

### `GET /api/projects/{pid}/conformance`

`ConformanceReport` : `profiles` (DL, EL, QL, RL, RDFS), `profile_violations` (raisons par profil), `issues` (`level` = `error` | `warning` | `info`, `code` W01–W07 / BP01–BP07, `message`, `subject`, `spec_ref`).

**Réponse 200**

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

### `POST /api/projects/{pid}/shacl/generate`

Génère des shapes depuis l'ontologie. `merge: true` conserve les shapes existantes, `false` les remplace. `notes` : ce qui n'est pas équivalent. Avec `dry_run: true`, rien n'est enregistré : la réponse est `{project, generated, notes, dry_run: true}` (`project` inchangé, `generated` = shapes produites), utilisé par l'aperçu de l'écran Shapes.

**Requête**

```json
{"merge": true, "dry_run": false}
```

**Réponse 200**

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

### `POST /api/projects/{pid}/shacl/validate`

Valide un fichier RDF (multipart `file`) contre les shapes du projet, sans inférence (D-034). Fichier vide → `422`.

**Requête**

```bash
curl -X POST $B/api/projects/$P/shacl/validate -F file=@samples/automaint/automaint-data.ttl
```

**Réponse 200**

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

## Analyse et arbitrage


### `POST /api/projects/{pid}/analyze?target=curiosity`

Lance le moteur sur l'ontologie et les shapes du projet ; les décisions enregistrées pour la cible sont appliquées. Réponse : `PGModel` (voir [`architecture.md`](architecture.md) §5). Sur l'exemple automaint : 18 types de nœuds, 24 relations, 83 validations, 159 constats ({'auto': 117, 'review': 41, 'lost': 1}).

**Réponse 200**

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

### `PUT /api/projects/{pid}/decisions/{target}`

Fusionne des décisions `{constat: option}` dans le projet et renvoie le `PGModel` recalculé. Une valeur `null` retire la décision. Clé groupée `"<règle>:*"` : appliquée à tous les constats de la règle sans décision individuelle. Option inconnue pour la cible → ignorée, constat `G02`.

**Requête**

```json
{
  "C07:https://w3id.org/ontoforge/automaint#ElectricVehicle": "validation",
  "D13:*": "validation"
}
```

**Réponse 200**

```json
{
  "decisions": {
    "C07:https://w3id.org/ontoforge/automaint#ElectricVehicle": "validation",
    "D13:*": "validation"
  },
  "…": "PGModel recalculé"
}
```

### `POST /api/projects/{pid}/decisions/{target}/accept-recommended`

Enregistre l'option recommandée des constats à arbitrer (`review`) comme décision. Les constats perdus (`lost`) restent à arbitrer par l'humain, sauf si `?include_lost=true` (mode « tout »). Réponse : `PGModel` ; sur automaint, `decisions` ne contient plus que les constats `review` (+ les `lost` avec `include_lost=true`).

**Réponse 200**

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

## Génération


### `GET /api/projects/{pid}/generate/{target}`

Fichiers de la cible + `schema.graphql` + `README-graphql.md` + `rapport-transposition.md`, en tenant compte des décisions. Réponse : `{files: {nom: contenu}}` (tailles en octets sur automaint : `Connector.cs` 65516, `Edges.cs` 7479, `README-curiosity.md` 22903, `RegisterSchema.cs` 1973, `Schema.cs` 18624, `schema.graphql` 26451, `README-graphql.md` 3106, `rapport-transposition.md` 33721).

**Réponse 200**

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

Pour Neo4j : `README-neo4j.md`, `ingest.cypher`, `model.mmd`, `schema.cypher`, `validation.cypher`, `schema.graphql`, `README-graphql.md`, `rapport-transposition.md`.

### `GET /api/projects/{pid}/generate/{target}/zip`

Les mêmes fichiers en archive. En-têtes réels : `content-type: application/zip`, `content-disposition: attachment; filename="<pid>-neo4j.zip"`.

## Requêtes


### `POST /api/projects/{pid}/queries/translate?target=neo4j`

Traduit une requête SPARQL `SELECT` en Cypher, Curiosity (pseudo-C# de la Query API, `À VÉRIFIER`) et GraphQL. `lossy: true` signale une perte ; `notes` détaille chaque perte (`[perte]`, `[curiosity]`, `[graphql]`).

**Requête**

```json
{
  "sparql": "PREFIX am: <https://w3id.org/ontoforge/automaint#>\nSELECT ?v ?vin WHERE { ?v a am:Vehicle ; am:vin ?vin } LIMIT 10"
}
```

**Réponse 200**

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

### `GET /api/projects/{pid}/queries/competency?target=neo4j`

Questions de compétence déduites du modèle : chacune porte sa traduction.

**Réponse 200**

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

## Assistant


### `GET /api/assistant/status`

Fournisseur actif.

**Réponse 200**

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

### `POST /api/assistant/draft`

Brouillon d'`OntoModel` depuis un texte (`kind` = `text`), un CSV (`csv`) ou un `CREATE TABLE` (`sql`). `base_iri` facultatif. **Ne modifie aucun projet** : le front applique les éléments acceptés via `PUT /onto`. Erreurs : `422` (texte vide / kind), `413` (trop long), `503` (non configuré), `502` (JSON du LLM invalide après relance).

**Requête**

```json
{"text": "Un client possède plusieurs véhicules", "kind": "text"}
```

**Réponse 200**

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

### `POST /api/assistant/shapes`

Shapes proposées pour un projet (génération déterministe `generate_shapes` + enrichissement LLM : motifs, plages, énumérations).

**Requête**

```json
{"project_id": "<pid>"}
```

**Réponse 200**

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

### `POST /api/assistant/explain`

Explication en langage naturel d'un constat (repli déterministe sans LLM). `404` si le constat n'existe pas.

**Requête**

```json
{
  "project_id": "<pid>",
  "target": "curiosity",
  "finding_id": "C02:https://w3id.org/ontoforge/automaint#Engine"
}
```

**Réponse 200**

```json
{
  "text": "Constat C02 — Héritage simple\n\nCe que cela signifie : Hiérarchie de am:Engine : 2 sous-classe(s) à parent unique (am:ElectricMotor, am:InternalCombustionEngine) ; une décision pour toute la hiérarchie..\nÉlément concerné : https://w3id.org/ontoforge/automaint#Engine.\n\nOptions possibles :\n- Multi-labels\n- Aplatir sur la racine concrète (recommandée)\n- Type de nœud distinct\n\nPourquoi pour Curiosity : l'option « flatten_…"
}
```

Les trois routes `POST /api/assistant/*` acceptent aussi un champ facultatif `provider_id` (fournisseur à utiliser) : fonctionnalité de l'itération 2 en cours de livraison.

## Itération 2 : paramètres, assistant, éditeur, requêtage

Contrats normatifs : `docs/CONTRACTS.md` §4 (paramètres, assistant), §5 (éditeur), §6 (requêtage), §7 (générations). Ces routes sont stabilisées à la clôture de L8, L9, L10, L15. Code : `api/settings.py`, `api/assistant.py`, `api/editing.py`, `api/queries.py`. Les exemples ci-dessous sont construits d'après les contrats et les modèles pydantic (ils n'ont pas été rejoués contre un backend lancé : `httpx` est absent de l'environnement du documentaliste). Les champs volumineux sont abrégés.

### Paramètres — `/api/settings`

| Méthode | Chemin | Remarques |
|---|---|---|
| GET | `/api/settings` | vue publique de `Settings` ; **crée `settings.json` au premier appel** |
| PUT | `/api/settings` | sous-ensemble ; `llm_providers` fusionnés par `id`, `language` / `defaults` champ à champ |
| POST | `/api/settings/providers` | 201 ; 409 si l'`id` existe |
| PUT / DELETE | `/api/settings/providers/{id}` | DELETE : 200 `{deleted, default_provider_id}` ; 409 pour `mock` ; le défaut retombe sur `mock` |
| POST | `/api/settings/providers/{id}/test` | corps facultatif `{api_key?, base_url?, model?}` (test sans enregistrer) → `{ok, latency_ms, model, message}` |
| POST | `/api/settings/sparql/test` | `{url?, auth?}` → `{ok, latency_ms, message}` (`ASK {}`) |
| GET / POST | `/api/settings/endpoints` | POST : 201 ; 409 id pris, 422 URL |
| PUT / DELETE | `/api/settings/endpoints/{id}` | secret : absent ou `""` = inchangé, `null` = supprimé |
| PUT | `/api/settings/endpoints/active` | `{id \| null}` ; 404 si inconnu |
| POST | `/api/settings/endpoints/{id}/test` | `{ok, latency_ms, message}` |

Les secrets ne sont jamais renvoyés : `has_key`, `key_last4`, `key_unreadable`, `auth.has_secret` / `has_secret`, `secret_unreadable`. Dans `PUT`, une clé absente ou `""` est inchangée, `null` la supprime, une chaîne la remplace. `kind` : `anthropic | openai_compat | ollama | mock`.

```bash
curl -s -X POST $B/api/settings/providers -H 'content-type: application/json' \
  -d '{"name":"Claude","kind":"anthropic","model":"<modèle>","api_key":"sk-ant-…"}'
# 201 → {"id":"claude","name":"Claude","kind":"anthropic","model":"…","has_key":true,"key_last4":"…","configured":true,…}

curl -s -X POST $B/api/settings/endpoints -H 'content-type: application/json' \
  -d '{"id":"local","name":"Local","url":"http://localhost:3030/sparql","timeout_s":30}'
curl -s -X PUT $B/api/settings/endpoints/active -H 'content-type: application/json' -d '{"id":"local"}'
# → {"active_endpoint_id":"local"}
```

L'ancien champ `sparql_endpoint` est migré vers l'endpoint `default` et reste accepté en `PUT` (miroir).

### Assistant (extension)

`GET /api/assistant/status` renvoie en plus `default_provider_id` et `providers: [{id, name, kind, model, configured, default}]`. `draft`, `shapes`, `explain` acceptent `provider_id?` (inconnu : 404 ; non configuré : 503).

| Méthode | Chemin | Entrée | Sortie |
|---|---|---|---|
| POST | `/api/assistant/chat` | `{project_id, messages:[{role, content}], provider_id?, attachments?:[{name, kind: csv\|sql\|text\|markdown, content}]}` | `{reply, proposal: OntoModel \| null, warnings}` |
| POST | `/api/assistant/upload` | multipart `file` (2 Mo max : 413 au-delà ; fichier vide : 422) | `{name, kind, preview:{lines (20), total_lines, truncated, columns?, tables?}, size, content}` |

`content` (texte décodé) est renvoyé pour que le front le remette tel quel dans `attachments`. Extensions reconnues : `.csv`, `.tsv`, `.sql`, `.md`, `.markdown`, `.txt`, sinon détection par le contenu.

### Éditeur — opérations, graphe, périmètres

```bash
curl -s -X POST $B/api/projects/$P/ops -H 'content-type: application/json' -d '{
  "label": "Nouvelle classe",
  "ops": [{"op":"add_class","name":"Trailer","label":"Remorque","parent":"https://w3id.org/ontoforge/automaint#Vehicle"}]}'
# → {"ok":true,"project":{…},"applied":1,"errors":[],"warnings":[],"can_undo":true,"can_redo":false}
```

`POST /ops` est tout ou rien : en cas d'erreur, HTTP **200** avec `ok=false`, `errors: [{index, message}]` et projet inchangé (500 opérations max par appel). Liste des opérations et règles de validation (IRI absolue, pas de cycle, propriétés simples, datatypes de la carte OWL 2…) : CONTRACTS §5. `POST /ops/undo` et `/ops/redo` répondent comme `/ops` plus `label` (409 si la pile est vide) ; `GET /ops/history` donne `{undo, redo, limit: 200, can_undo, can_redo}`.

`GET /api/projects/{pid}/graph?perimeter=&lang=fr&include=datatypes,individuals` → `{nodes, edges, skipped}` (nœuds `{id, label, kind, icon, position, abstract, deprecated, collapsed}` ; arêtes `{id, source, target, kind, label, iri}`, `id = kind|iri|source|target`, tri stable). `GET /api/icons?q=` → `{icons:[{id:"fa-car", style, label:{fr,en}, keywords}], total}` (recherche insensible aux accents).

Périmètres : `GET|POST /perimeters`, `GET|PUT|DELETE /perimeters/{id}`, `GET /perimeters/{id}/preview` → `{counts, excluded:[{id, rule, title, detail}]}`, `PUT /perimeters/active` `{id|null}` (état d'interface). Classes et propriétés inconnues : 422 ; identifiant pris : 409 ; périmètre inconnu : 404. `?perimeter=<id>` s'applique à `analyze`, `generate/{target}` et `generate/{target}/zip` (sans le paramètre, `all` ou `none` : ontologie complète ; l'état actif n'est jamais appliqué implicitement).

### Requêtage guidé

```bash
curl -s "$B/api/projects/$P/query/suggest?class=https://w3id.org/ontoforge/automaint%23Vehicle"
# → {"class":…,"label":"Véhicule","ancestors":[…],"subclasses":[…],"outgoing":[…],"incoming":[…],"data_properties":[…]}

curl -s -X POST $B/api/projects/$P/query/nl -H 'content-type: application/json' \
  -d '{"question":"véhicules réparés par Camille"}'
# → {"guided":{…},"explanation":"…","confidence":0.72,"unmatched":["réparés"],"mode":"deterministic","provider":"mock","sparql":"…","cypher":"…","curiosity":"…","notes":[…],"lossy":true,"warnings":[]}

curl -s -X POST $B/api/projects/$P/query/run -H 'content-type: application/json' -d '{"guided":{…},"limit":100}'
# → {"columns":[…],"rows":[{"vehicle":{"type":"uri","value":"…"},…}],"truncated":false,"elapsed_ms":42,"sparql":"…","endpoint_id":"local","graph":{"nodes":[…],"edges":[…]}}
```

| Méthode | Chemin | Rôle / erreurs |
|---|---|---|
| GET | `/query/suggest?class=` | relations sortantes / entrantes et propriétés de données d'une classe (404 classe inconnue) |
| GET | `/query/suggest?property=&from=[&inverse=true]` | classes cibles d'une propriété (404 propriété inconnue) |
| GET | `/query/suggest` | classes racines possibles |
| POST | `/query/build` | `{guided, target?}` → `{sparql, cypher, curiosity, graphql, notes, lossy, supported, warnings}` ; 422 variable invalide |
| POST | `/query/run` | `{guided \| sparql, endpoint_id?, limit}` : lecture seule (UPDATE → 403, syntaxe → 422), pas d'endpoint actif → 409, délai → 504, erreur endpoint → 502 ; plafond dur 5000 lignes |
| GET | `/query/values?class=&property=&q=&endpoint_id=` | 20 valeurs suggérées depuis l'endpoint |
| POST | `/query/nl` | `{question, provider_id?, lang?, target?}` ; fournisseur inconnu 404, question vide 422 ; `mode`: `llm` ou `deterministic` |
| GET / POST | `/queries/saved` | 201 `{id, name, description, guided, sparql, created_at, updated_at}` |
| GET / PUT / DELETE | `/queries/saved/{qid}` | — |
| GET | `/queries/competency/guided?target=` | questions de compétence avec version guidée quand elle existe |

Sans raisonnement côté endpoint, `a C` ne ramène pas les sous-classes : utiliser `subclasses: true`. Les sous-propriétés ne sont pas développées dans la requête générée.

### Historique des générations

`GET /api/projects/{pid}/generations` → liste, la plus récente d'abord : `{target, perimeter, at, files, findings_summary, project_updated_at}` (`findings_summary` : nombres auto / review / lost et `pending`). Chaque `GET /generate/{target}` (pas le zip) ajoute une entrée (50 maximum) sans avancer `updated_at` ; une génération est « obsolète » si `project_updated_at` est antérieur à la dernière modification du projet. `GET /api/projects` expose aussi `created_at` et `source_files`.

### Sémantique de `chosen` et des décisions

`Finding.chosen` vaut l'identifiant d'option décidée par l'humain (`None` = non arbitré) ; `Finding.recommended` est l'option appliquée par défaut. `PGModel.decisions` conserve aussi les décisions dont le constat a disparu, pour les rejouer s'il réapparaît (`mapping/decisions.py`, docstring).
