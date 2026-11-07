# Contrats d'interface — OntoForge itération 1

Propriétaire : lead. Toute modification passe par `journal/decisions.md`.
Modèles pydantic : `backend/ontoforge/core/` (onto_model.py, shapes_model.py, pg_model.py, project.py).

## 1. Fonctions de service (chaque module expose exactement ces signatures)

| Module (propriétaire) | Signature |
|---|---|
| `io/rdf_import.py` (w3c) | `parse_ontology(data: str \| bytes, format: str \| None = None, filename: str \| None = None) -> tuple[OntoModel, list[str]]` — formats : turtle, xml (RDF/XML), json-ld, nt, n3, trig ; détection par extension puis contenu. `graph_to_model(g: rdflib.Graph) -> tuple[OntoModel, list[str]]` |
| `io/rdf_export.py` (w3c) | `model_to_graph(m: OntoModel) -> rdflib.Graph` ; `serialize(m: OntoModel, format: str = "turtle") -> str`. Round-trip : `graph_to_model(model_to_graph(m))` ≡ `m` |
| `io/dsl.py` (w3c) | `parse_dsl(text: str, base: OntoModel \| None = None) -> tuple[OntoModel, list[dict]]` (erreurs `{line, message}`, jamais d'exception) ; `DSL_HELP: str` |
| `conformance/profiles.py` (w3c) | `check_conformance(onto: OntoModel, graph: rdflib.Graph \| None = None) -> ConformanceReport` (modèle pydantic défini dans `conformance/report.py` : `profiles: dict[str, bool]` pour DL/EL/QL/RL/RDFS, `issues: list[Issue{level: error\|warning\|info, code, message, subject, spec_ref}]`) |
| `shacl/import_shapes.py` (shacl) | `parse_shapes(data, format=None, filename=None) -> tuple[ShapesModel, list[str]]` ; `graph_to_shapes(g) -> tuple[ShapesModel, list[str]]` |
| `shacl/export_shapes.py` (shacl) | `shapes_to_graph(s: ShapesModel) -> rdflib.Graph` ; `serialize_shapes(s, format="turtle") -> str` |
| `shacl/validate.py` (shacl) | `validate(data: str \| bytes, shapes: ShapesModel, onto: OntoModel \| None = None, data_format: str \| None = None, inference: str = "none") -> ShaclReport` (pydantic : `conforms`, `results: list[{focus, path, severity, constraint, message, value, shape}]`) |
| `shacl/owl_to_shacl.py` (shacl) | `generate_shapes(onto: OntoModel) -> tuple[ShapesModel, list[str]]` (notes = ce qui n'est pas équivalent) |
| `mapping/engine.py` (lead) | `analyze(onto: OntoModel, shapes: ShapesModel \| None, target: Target, decisions: dict[str, str] \| None = None) -> PGModel` |
| `targets/curiosity.py` (curiosity) | `generate(pg: PGModel, onto: OntoModel \| None = None) -> dict[str, str]` (nom de fichier → contenu) |
| `targets/neo4j.py` (neo4j) | `generate(pg: PGModel, onto: OntoModel \| None = None) -> dict[str, str]` |
| `targets/graphql.py` (query) | `generate(pg: PGModel, onto: OntoModel \| None = None) -> dict[str, str]` (`schema.graphql`) |
| `targets/report.py` (lead) | `generate(pg: PGModel, onto: OntoModel \| None = None) -> dict[str, str]` (`rapport-transposition.md`) |
| `queries/translate.py` (query) | `translate(sparql: str, pg: PGModel, onto: OntoModel \| None = None) -> TranslationResult` (pydantic : `cypher`, `curiosity`, `graphql`, `notes: list[str]`, `lossy: bool`) ; `competency_questions(pg, onto) -> list[{question, sparql, cypher, curiosity}]` |
| `assistant/service.py` (lead) | voir L6 |
| `projects/store.py` (lead) | `list_projects()`, `get(id)`, `save(project)`, `delete(id)`, dossier `$ONTOFORGE_DATA/projects/<id>/` |

## 2. API REST (préfixe `/api`, JSON, erreurs `{detail}`)

| Méthode | Chemin | Entrée | Sortie |
|---|---|---|---|
| GET | `/health` | — | `{status, version}` |
| GET | `/samples` | — | `[{name, title, files}]` |
| GET | `/projects` | — | `[{id, name, updated_at, target, stats}]` |
| POST | `/projects` | `{name, description?, sample?}` | `Project` |
| GET / PUT / DELETE | `/projects/{id}` | `Project` (PUT) | `Project` |
| POST | `/projects/{id}/import` | multipart `file`, `kind=ontology\|shapes\|auto` | `{project, warnings}` |
| PUT | `/projects/{id}/onto` | `OntoModel` | `Project` |
| PUT | `/projects/{id}/shapes` | `ShapesModel` | `Project` |
| POST | `/projects/{id}/dsl` | `{text, merge: bool}` | `{project, errors}` |
| GET | `/projects/{id}/export/ontology?format=turtle\|xml\|json-ld` | — | texte |
| GET | `/projects/{id}/export/shapes?format=turtle` | — | texte |
| GET | `/projects/{id}/conformance` | — | `ConformanceReport` |
| POST | `/projects/{id}/shacl/generate` | `{merge: bool, dry_run: bool = false}` | `{project, notes}` ; avec `dry_run: true` : `{project, generated, notes, dry_run: true}` — `generated` = shapes produites, `project` inchangé, rien n'est enregistré (L17) |
| POST | `/projects/{id}/shacl/validate` | multipart `file` (données RDF) | `ShaclReport` |
| POST | `/projects/{id}/analyze?target=curiosity\|neo4j` | — | `PGModel` (décisions du projet appliquées) |
| PUT | `/projects/{id}/decisions/{target}` | `{finding_id: option_id \| null}` | `PGModel` |
| POST | `/projects/{id}/decisions/{target}/accept-recommended?include_lost=false` | — | `PGModel` — par défaut n'accepte que les constats `review` ; les `lost` restent à arbitrer par l'humain, sauf `include_lost=true` (D-L14-02) |
| GET | `/projects/{id}/generate/{target}` | — | `{files: {name: content}}` (cible + graphql + rapport) |
| GET | `/projects/{id}/generate/{target}/zip` | — | `application/zip` |
| GET | `/projects/{id}/generations` | — | `[{target, perimeter, at, files: [noms], findings_summary: {auto, review, lost, pending}, project_updated_at}]`, plus récente d'abord (L14) |
| POST | `/projects/{id}/queries/translate?target=` | `{sparql}` | `TranslationResult` |
| GET | `/projects/{id}/queries/competency?target=` | — | liste |
| POST | `/assistant/draft` | `{text, kind: text\|csv\|sql, base_iri?}` | `{proposal: OntoModel, explanation, warnings}` |
| POST | `/assistant/shapes` | `{project_id}` | `{proposal: ShapesModel, explanation}` |
| POST | `/assistant/explain` | `{project_id, target, finding_id}` | `{text}` |
| GET | `/assistant/status` | — | `{provider, model, configured}` |

## 3. Conventions
- Tests : `backend/tests/test_<module>.py`, pytest, fixtures dans `samples/` (chemins relatifs à la racine du dépôt via `tests/conftest.py`).
- IRIs absolues partout dans les modèles ; la compaction en CURIE est faite par l'export et le front.
- Pas d'accès réseau dans les tests (l'assistant a un fournisseur `mock`).
- **PGModel — conventions (D-L4-02, lead, 3/11)** :
  - `Materialization.chain` contient des **noms d'EdgeType du PGModel** (jamais des IRIs) ; l'IRI d'origine va dans `source`.
  - La propriété portant l'IRI d'origine d'un nœud est marquée `source = "urn:ontoforge:iri"` (son `name` dépend de la cible : `uri` pour Neo4j, `Uri` pour Curiosity). Les générateurs la retrouvent par ce marqueur, jamais par son nom.
  - Un NodeType sans `key` utilise cette propriété IRI comme clé de repli ; les générateurs n'émettent jamais de motif de correspondance vide.

## 4. Paramètres (L8, D-L8-01)
Code : `backend/ontoforge/settings/` (modèles, chiffrement, stockage), `api/settings.py`. Stockage : `$ONTOFORGE_DATA/settings.json` (écriture atomique, permissions 600).

**Modèle `Settings`** : `llm_providers: [{id, name, kind: anthropic|openai_compat|ollama|mock, base_url?, model, api_key, extra?}]`, `default_provider_id`, `language: {ui, labels, assistant: fr|en}`, `defaults: {base_iri, prefixes, target: curiosity|neo4j, naming}`, `sparql_endpoint: {url, auth?: {type: none|basic|bearer, username?, secret}}`.
Les secrets (`api_key`, `auth.secret`) ne sont **jamais** renvoyés : la vue publique expose `has_key`, `key_last4` (4 derniers caractères, seulement si la clé fait au moins 12 caractères), `key_unreadable` (clé stockée mais indéchiffrable), `configured`, et `auth.has_secret`. `extra` ne doit pas contenir de secret.

**Chiffrement** : Fernet (cryptography), clé dérivée par HKDF-SHA256 de `ONTOFORGE_SECRET_KEY`. Absente : clé générée au premier usage dans `$ONTOFORGE_DATA/.secret` (600) + avertissement dans les journaux. Sur disque : `api_key_enc` / `secret_enc` = `enc:v1:<jeton>`. **Rotation** : arrêter le backend, puis `ONTOFORGE_SECRET_KEY_OLD=<ancienne> ONTOFORGE_SECRET_KEY=<nouvelle> python -m ontoforge.settings rotate` (ancienne vide = fichier `.secret`) ; redémarrer avec la nouvelle clé. Une mauvaise ancienne clé annule l'opération sans rien écrire. Perdre la clé maître = ressaisir les clés d'API.

**Premier démarrage** : si `settings.json` n'existe pas, il est déduit de `ONTOFORGE_LLM_PROVIDER`, `ONTOFORGE_LLM_MODEL`, `ANTHROPIC_API_KEY`, `OPENAI_BASE_URL/KEY`, `OLLAMA_BASE_URL` (ids `anthropic`, `openai`, `ollama`) ; le fournisseur `mock` est toujours présent et non supprimable. Tant que le fichier n'existe pas, l'assistant garde le comportement historique piloté par l'environnement.

| Méthode | Chemin | Entrée | Sortie |
|---|---|---|---|
| GET | `/api/settings` | — | vue publique de `Settings` |
| PUT | `/api/settings` | sous-ensemble de `Settings` ; `llm_providers` : entrées `{id, …}` fusionnées par id (créées si inconnues) ; `language`/`defaults` fusionnés champ à champ ; `sparql_endpoint: null` = réinitialiser | vue publique |
| POST | `/api/settings/providers` | `{name, kind, id?, base_url?, model?, api_key?, extra?}` | 201 fournisseur (vue publique) ; 409 id existant |
| PUT | `/api/settings/providers/{id}` | champs à modifier | fournisseur |
| DELETE | `/api/settings/providers/{id}` | — | `{deleted, default_provider_id}` ; 409 pour `mock` ; le défaut retombe sur `mock` |
| POST | `/api/settings/providers/{id}/test` | corps optionnel `{api_key?, base_url?, model?}` (test sans enregistrer) | `{ok, latency_ms, model, message}` (timeout 15 s, message français sans secret) |
| POST | `/api/settings/sparql/test` | corps optionnel `{url?, auth?}` | `{ok, latency_ms, message}` (`ASK {}`) |

**Secrets dans PUT** : clé absente ou `""` = inchangée ; `null` explicite = supprimée ; chaîne = remplacée.

**Assistant (extension de §2)** : `GET /assistant/status` → `{provider, model, configured, default_provider_id, providers: [{id, name, kind, model, configured, default}]}`. `draft`, `shapes`, `explain` acceptent `provider_id?` (défaut : fournisseur par défaut ; inconnu → 404 ; non configuré → 503). Nouveau :
| POST | `/assistant/chat` | `{project_id, messages: [{role: user\|assistant, content}], provider_id?, attachments?: [{name, kind: csv\|sql\|text\|markdown, content}]}` | `{reply, proposal: OntoModel \| null, warnings}` |
| POST | `/assistant/upload` | multipart `file` (2 Mo max) | `{name, kind: csv\|sql\|text\|markdown, preview: {lines (20), total_lines, truncated, columns? (csv), tables? (sql)}, size, content}` |
`content` (texte décodé) est ajouté à l'upload pour que le front le renvoie tel quel dans `attachments`.

**Assistant global (L16, extension de §4, rétrocompatible)** : `POST /api/assistant/chat` accepte `context` (AssistantContext : `{screen, projectId?, target?, perimeter?, selection?: {kind,id,label?}, extra?, suggestions?}`). Avec `context` la réponse est `{reply, actions: [{kind: ops|proposal|shapes|guided_query|navigate, payload, summary}], warnings, proposal}` (sans `context` : ancien comportement + `actions` dérivées de `proposal`). Rien n'est appliqué par le serveur.
- `ops` : `payload = {ops: [...], preview: [{op, text}]}` ; les opérations sont celles de §5 (`POST /projects/{id}/ops`), validées par essai à blanc sur une copie du projet : une opération invalide est retirée avec un avertissement ; les entités existantes sont retrouvées par IRI, nom local ou libellé (rien n'est inventé) ; une nouvelle entité prend toujours l'IRI de base de l'ontologie + son nom.
- `proposal` : `payload.proposal` = OntoModel partiel (comme l'ancien `proposal`). `shapes` : `payload = {patches: [{class, property, constraints: {min_count|max_count|min_length|max_length|min_inclusive|max_inclusive|min_exclusive|max_exclusive|pattern}, message?}], preview}` ; application : `POST /api/assistant/shapes/apply {project_id, patches}` -> `{ok, applied, project, can_undo}` (revalidé, annulable par `POST /projects/{id}/ops/undo`). `guided_query` : `payload` = réponse de `/query/nl` (+ `sparql`, `cypher`, `curiosity`, `question`). `navigate` : `payload = {screen}` (clé de route).
- Repli déterministe sans LLM (mock / non configuré), en français : « ajoute la classe X [sous Y] [avec une propriété p [en unité] [de type T]] », « ajoute la propriété p [de type T] à X », « rends p obligatoire [dans X] », « supprime X », « ajoute une contrainte min|max n|motif m sur p dans la shape S », « cherche / trouve / liste / quels … » (-> `/query/nl`), « ouvre les shapes ». Code : `assistant/agent.py`.

## 5. Éditeur graphique (L9, D-L9-01)
Code : `backend/ontoforge/editing/` (ops, history, perimeter, graph, icons), `api/editing.py`. Extension **rétrocompatible** de `Project` : `view {icons: {iri: "fa-…"}, positions: {iri: {x, y}}, collapsed: [iri]}`, `perimeters: [{id, name, description, classes, properties, include_descendants}]`, `active_perimeter` (état d'interface : n'influe pas sur le backend). Les générateurs ne dépendent pas de `view`.

| Méthode | Chemin | Entrée | Sortie |
|---|---|---|---|
| POST | `/api/projects/{id}/ops` | `{ops: [...], label?}` (ou la liste seule), 500 opérations max | `{ok, project, applied, errors: [{index, message}], warnings, can_undo, can_redo}` — **tout ou rien**, HTTP 200 même si `ok=false` (projet inchangé) |
| POST | `/api/projects/{id}/ops/undo` · `/ops/redo` | — | idem + `label` ; 409 si pile vide |
| GET | `/api/projects/{id}/ops/history` | — | `{undo: [{id, ts, label, fields}], redo, limit: 200, can_undo, can_redo}` |
| GET | `/api/icons?q=` | — | `{icons: [{id: "fa-car", style, label: {fr, en}, keywords}], total}` (~80, recherche insensible aux accents) |
| GET / POST | `/api/projects/{id}/perimeters` | `{name, description?, classes, properties, include_descendants, id?}` | liste / 201 périmètre (classes et propriétés doivent exister : 422 sinon ; 409 si `id` pris) |
| GET / PUT / DELETE | `/api/projects/{id}/perimeters/{pid}` | idem | périmètre / `{deleted, active_perimeter}` |
| GET | `/api/projects/{id}/perimeters/{pid}/preview` | — | `{counts, excluded: [{id, rule, title, detail}]}` |
| PUT | `/api/projects/{id}/perimeters/active` | `{id: str \| null}` | `{active_perimeter}` |
| GET | `/api/projects/{id}/graph?perimeter=&lang=fr&include=datatypes,individuals` | — | `{nodes, edges, skipped}` |
| POST / GET | `/analyze`, `/generate/{target}`, `/generate/{target}/zip` | `?perimeter=<id>` | comme avant, sur l'ontologie restreinte |

**Opérations** (`op` + champs) — IRIs absolues ; `add_class`/`add_object_property`/`add_datatype_property` acceptent `name` (nom local ajouté à l'IRI de l'ontologie) à la place de `iri` :
`add_class {iri|name, label?, comment?, lang?="fr", parent?, icon?, x?, y?}` · `rename_entity {iri, new_iri}` (réécrit ontologie, vue, périmètres, shapes, décisions) · `delete_entity {iri}` (retire l'entité et ses références ; shapes non modifiées, avertissement) · `add_subclass {iri, parent}` · `remove_subclass {iri, parent}` · `add_object_property {iri|name, domain?, range?, label?, characteristics?, inverse_of?}` · `add_datatype_property {iri|name, domain?, range?=xsd:string, functional?, label?}` · `set_domain_range {iri, domain?, range?}` (clé présente = remplacement ; null/[] vide) · `set_restriction {iri(classe), property, kind: some|only|min|max|exactly|value|self, n?, filler?, value?, datatype?, inverse?}` (remplace la restriction de même propriété+sens+kind) · `remove_restriction {iri, property, kind?}` · `set_label` / `set_comment {iri, text, lang?}` (texte vide = suppression) · `set_characteristic {iri, characteristic, value?=true}` · `set_inverse {iri, inverse|null}` · `add_disjoint` / `remove_disjoint {iri, other}` · `set_key {iri, properties, index?=0}` (liste vide = suppression) · `set_icon {iri, icon|null}` · `move_node {iri, x, y}` · `set_collapsed {iri, collapsed?}`.

**Validations** : IRI absolue ; entités existantes ; une IRI = une sorte d'entité (pas de punning) ; pas de cycle de sous-classe ; pas de disjonction entre une classe et sa super-classe ; caractéristiques incompatibles (symétrique/asymétrique, réflexive/irréflexive, réflexive/asymétrique) ; **propriétés simples** (OWL 2 Structural Spec §11.2) : cardinalités, `self`, fonctionnelle, inverse fonctionnelle, asymétrique, irréflexive, disjonction exigent une propriété simple — non simple = transitive, cible d'une chaîne, ou super-propriété / inverse / équivalente d'une propriété non simple ; datatypes de la carte OWL 2 (xsd hors carte — `date`, `time`, `gYear`, `duration`… — acceptés avec avertissement ; inconnus refusés). Après le lot, seules les **nouvelles** violations d'intégrité sont bloquantes (une ontologie importée déjà fautive reste éditable).

**Annuler / rétablir** : fichier annexe `ops-history.json`, pile de 200 ; chaque entrée garde l'état avant des seuls champs modifiés (onto, view, perimeters, shapes, decisions). Le CRUD des périmètres est journalisé aussi. Les sauvegardes hors éditeur (PUT /onto, import…) ne le sont pas. Une opération réussie vide la pile « rétablir ».

**Périmètres** : (it2) une propriété dont le domaine ou la portée est un ancêtre unique hors périmètre est projetée sur ses descendants du périmètre (P01 « restreint ») ; classes = `classes` (+ descendants si `include_descendants`) ; propriété gardée si (liste `properties` vide ou la contenant) ET domaine et portée entièrement dans le périmètre. Sont aussi filtrés : superclasses, restrictions, expressions, disjonctions, clés, individus (typés hors périmètre → exclus), shapes ciblant une classe exclue. Constats d'information (`severity: info` (D-L9-02), sans options, hors compteurs) ajoutés au `PGModel.findings` : `P00:<id périmètre>` (bilan), `P01:<iri>` (relation exclue), `P02:<classe>:<parent>` (héritage coupé), `P03:<classe>:<…>` (restriction / axiome coupé). Les ids des constats du moteur ne changent pas : les décisions sont partagées entre périmètres. Sans `?perimeter` (ou `all`/`none`) : ontologie complète, `active_perimeter` n'est jamais appliqué implicitement ; id inconnu → 404.

**Graphe** : nœuds `{id: iri, label, kind: class|datatype|individual, icon, position|null, abstract, deprecated, collapsed}` ; `abstract` = `disjoint_union_of` non vide ou annotation `urn:ontoforge:abstract = "true"`. Arêtes `{id, source, target, kind, label, iri}` avec `id = kind|iri|source|target` ; tri par id (sortie stable). `subClassOf` enfant→parent ; `objectProperty` une arête par couple domaine×portée (propriétés sans domaine ou portée : listées dans `skipped`) ; `disjointWith` / `equivalentClass` dédupliquées (source < target) ; `inverseOf` relie les **ids des deux arêtes objectProperty** (`on: "edges"`) et chaque arête porte aussi `inverse_of`. Avec `include` : nœuds `datatype`/`individual`, arêtes `datatypeProperty` et `type`.

## 6. Requêtage guidé façon Sparnatural (L15, D-L15-01)
Code : `backend/ontoforge/queries/{builder,endpoint,saved}.py`, `api/queries.py` ; endpoints multiples dans `settings/` et `api/settings.py`.

**Paramètres (extension de §4, rétrocompatible)** : `Settings.sparql_endpoints: [{id, name, url, auth: none|basic|bearer, username?, secret, default_graph?, timeout_s (1-300, défaut 30)}]` + `active_endpoint_id`. Secret chiffré comme les clés LLM (`secret_enc` sur disque, jamais renvoyé : `has_secret`, `secret_unreadable`) ; la rotation couvre aussi les endpoints. L'ancien champ `sparql_endpoint` est migré au chargement vers l'endpoint `default` (actif) ; il reste accepté en PUT (miroir vers `default`).
| Méthode | Chemin | Entrée | Sortie |
|---|---|---|---|
| GET / POST | `/api/settings/endpoints` | POST `{name, url, auth?, username?, secret?, default_graph?, timeout_s?, id?}` | `{endpoints, active_endpoint_id}` / 201 endpoint (409 id pris, 422 URL) |
| PUT / DELETE | `/api/settings/endpoints/{id}` | champs à modifier (secret : absent ou `""` = inchangé, `null` = supprimé) | endpoint / `{deleted, active_endpoint_id}` |
| PUT | `/api/settings/endpoints/active` | `{id \| null}` | `{active_endpoint_id}` (404 inconnu) |
| POST | `/api/settings/endpoints/{id}/test` | corps optionnel (test sans enregistrer) | `{ok, latency_ms, message}` (`ASK {}`) |

**`GuidedQuery`** (pydantic, `builder.py`) : `root {var, class_iri?}`, `steps [{from_var, property_iri, inverse, to_var, to_class_iri?, optional, negated}]`, `filters [{var, kind: text_contains|equals|regex|lang|number_range|date_range|in_values, property_iri?, value, value2, values, lang, datatype, is_iri, case_insensitive, negate}]` (`property_iri` = propriété de données de `var` ; absent = `var` est la valeur), `select [{var, property_iri?, label}]` (vide = toutes les variables non niées ; propriété sélectionnée = OPTIONAL), `order_by [{var, property_iri?, desc}]`, `limit` (1-10000, défaut 100), `offset`, `distinct`, `subclasses` (`rdf:type/rdfs:subClassOf*`), `label_lang`. Variable invalide / inconnue / niée sélectionnée → 422.

| Méthode | Chemin | Entrée | Sortie |
|---|---|---|---|
| GET | `/api/projects/{id}/query/suggest?class=<iri>[&lang=]` | — | `{class, label, ancestors, subclasses, outgoing[], incoming[], data_properties[]}` ; objet : `{iri, label, direction, inverse, inverse_of, inherited_from, untyped, targets[{iri,label,direct}], targets_restricted, required, max_count}` ; données : `{iri, label, datatype, value_kind: text\|number\|date\|boolean\|other, filter_kinds[], required, max_count}` (+ `rdfs:label` synthétique) |
| GET | `/query/suggest?property=<iri>&from=<class>[&inverse=true]` | — | `{property, inverse, restricted, note, targets[]}` (portée + sous-classes, affinée par `sh:class`) |
| GET | `/query/suggest` | — | `{classes}` (racines possibles) |
| POST | `/query/build` | `{guided, target?}` | `{sparql, cypher, curiosity, graphql, notes, lossy, supported, warnings}` (traduction = `translate.translate`) |
| POST | `/query/run` | `{guided \| sparql, endpoint_id?, limit=100}` | `{columns, rows[{col: {type,value,datatype?,xml:lang?} \| null}], truncated, elapsed_ms, boolean?, sparql, endpoint_id, graph {nodes, edges}}` |
| GET | `/query/values?class=&property=&q=&endpoint_id=` | — | `{values[{value,label,is_iri,datatype,lang}], truncated, sparql}` (20 max) |
| GET / POST | `/queries/saved` | `{name, description?, guided \| sparql}` | liste / 201 `{id, name, description, guided, sparql, created_at, updated_at}` |
| GET / PUT / DELETE | `/queries/saved/{qid}` | idem | requête / `{deleted}` |
| GET | `/queries/competency/guided?target=` | — | `[{id, question, pattern, sparql, guided \| null, reason}]` |

| POST | `/query/nl` | `{question, provider_id?, lang?, target?}` | `{guided, explanation, confidence (0-1), unmatched[], mode: llm\|deterministic, provider, sparql, cypher, curiosity, notes, lossy, warnings}` |

**Langage naturel (`queries/nl.py`)** : (1) pré-analyse déterministe (libellés toutes langues, `skos:altLabel`, noms locaux, racinisation simple, petit lexique FR->EN de repli) ; (2) si le fournisseur choisi (ou par défaut) est réel et configuré, prompt `[TASK:nl]` avec schéma compact + indices, sortie JSON `GuidedQuery` ; (3) validation stricte (`sanitize`) : sens d'une relation corrigé si l'autre est valide, classe cible invalide retirée, étape / filtre / colonne inconnus retirés, termes écartés listés dans `unmatched` ; (4) repli 100 % déterministe (mock, fournisseur absent / non configuré, erreur ou JSON invalide) : classe de départ = première classe citée, plus courts chemins (4 sauts max, BFS multi-sources) vers les autres classes citées, « sans X » = étape niée, mots capitalisés ou entre guillemets = `text_contains` sur la propriété « nom » de la classe voisine, dates (« après le 1er octobre », « en 2024 », ISO) = `date_range` (année courante supposée, signalée dans `explanation`). Provider inconnu : 404 ; question vide : 422 ; aucune classe reconnue : racine vide, confiance 0.

**Garde-fous d'exécution** : lecture seule (SELECT / ASK / CONSTRUCT / DESCRIBE, vérifié par le parseur SPARQL : UPDATE → 403, syntaxe invalide → 422, aucun appel réseau) ; LIMIT de niveau supérieur plafonné à `limit`+1 (ajouté s'il manque) pour détecter `truncated` ; plafond dur 5000 ; délai = `timeout_s` de l'endpoint (504) ; pas d'endpoint actif → 409 ; erreurs endpoint → 502 sans secret. Stockage des requêtes sauvegardées : `$ONTOFORGE_DATA/projects/<id>/queries.json`.
Sans raisonnement côté endpoint, `a C` ne ramène pas les sous-classes : utiliser `subclasses: true`. Les sous-propriétés ne sont pas développées dans la requête (elles le sont dans les suggestions).

**Valeurs possibles et endpoint temporaire (L17)** :
| Méthode | Chemin | Entrée | Sortie |
|---|---|---|---|
| GET | `/api/projects/{id}/query/options?class=&property=&q=&lang=` | classe et/ou propriété (404 classe inconnue, 422 si aucune) | `{class, property, kind: class\|object\|data\|label, known_count, enumerated, values[{value,label,is_iri,source: enum\|individual\|sh:in\|DataOneOf\|PGModel}], truncated}` (500 max) — SANS endpoint, aucun appel réseau |
| POST | `/query/values` | `{class?, property?, q?, endpoint_id? \| endpoint?}` | idem GET (le secret ne passe pas par l'URL) |
| POST | `/query/endpoint-test` | `{url, auth?, username?, secret?, default_graph?, timeout_s?}` | `{ok, latency_ms, message}` |
Sources (`queries/options.py`) : classe énumérée `owl:oneOf`, individus typés de la classe et de ses sous-classes ; propriété objet = individus de sa portée ; propriété de données = `sh:in` des shapes de la classe, DataOneOf (propriété ou datatype), enum du PGModel ; `rdfs:label` ou autre = libellés des individus connus (`kind: label`). `/query/suggest` ajoute `known` (nombre d'individus connus) à chaque classe racine et à chaque cible.
`/query/run` et `/query/values` (POST) acceptent `endpoint: {url, auth?, username?, secret?, default_graph?, timeout_s?}` à la place de `endpoint_id` : mêmes garde-fous (lecture seule, timeout, LIMIT), jamais enregistré ni renvoyé ; `endpoint_id` du résultat = `temporaire`. Côté écran : état en mémoire du navigateur uniquement ; « Enregistrer dans les paramètres » passe par `POST /api/settings/endpoints`. Filtre « est l'un de » sur une entité : `{kind: in_values, is_iri: true, values: [IRI…]}` sans `property_iri`.

## 7. Historique des générations (L14)
- `Project.generations: list[GenerationRecord]` (rétrocompatible, défaut `[]`, 50 entrées max). Chaque `GET /generate/{target}` (pas le zip) ajoute `{target, perimeter, at, files, findings_summary, project_updated_at}` ; `findings_summary` = nombres de constats auto / review / lost et `pending` (non arbitrés).
- L'enregistrement n'avance pas `updated_at` ; `project_updated_at` permet de dire « obsolète » (projet modifié depuis). `PUT /projects/{id}` ignore `generations` du corps.
- `GET /projects` expose aussi `created_at` et `source_files` (exemple / fichiers d'origine).

**D-L9-02** : `NodeType.icon` (nom Font Awesome, repris de `Project.view.icons`) et `Severity` += `"info"` (jamais compté ni arbitré). Suppression d'entité = retrait des axiomes entiers qui la mentionnent ; IRIs rdf:/rdfs:/owl:/xsd: refusées pour les entités.
