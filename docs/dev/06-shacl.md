# 06. SHACL {#shacl}

Le backend lit, écrit, génère et exécute des shapes SHACL. Il en tire aussi des indices pour le moteur de transposition, car une shape est plus proche d'un schéma de property graph qu'un axiome OWL (D-004).

Sources lues : `backend/ontoforge/shacl/import_shapes.py`, `backend/ontoforge/shacl/export_shapes.py`, `backend/ontoforge/shacl/owl_to_shacl.py`, `backend/ontoforge/shacl/validate.py`, `backend/ontoforge/shacl/_worker.py`, `backend/ontoforge/shacl/shacl_to_pg.py`, `backend/ontoforge/childproc.py`, `backend/ontoforge/editing/files.py`, `backend/ontoforge/api/analysis.py`, `backend/ontoforge/main.py`, `skills/shacl-modeling/SKILL.md`. Exécution au client de test sur l'exemple `trap`.

## Rôle {#role}

| Fonction | Point d'entrée | Route |
|---|---|---|
| Lire un fichier de shapes en `ShapesModel` | `backend/ontoforge/shacl/import_shapes.py::parse_shapes` | `POST /api/projects/{pid}/import` (`kind=shapes` ou détecté) |
| Écrire un `ShapesModel` en RDF | `backend/ontoforge/shacl/export_shapes.py::serialize_shapes` | `GET /api/projects/{pid}/export/shapes` |
| Générer des shapes depuis l'ontologie | `backend/ontoforge/shacl/owl_to_shacl.py::generate_shapes` | `POST /api/projects/{pid}/shacl/generate` (`merge`, `dry_run`) |
| Valider des données | `backend/ontoforge/shacl/validate.py::validate` | `POST /api/projects/{pid}/shacl/validate` (fichier de données) |
| Indexer les contraintes pour le moteur | `backend/ontoforge/shacl/shacl_to_pg.py::shape_constraints` | appelé par `backend/ontoforge/mapping/engine.py` |
| Méta-valider un fichier de shapes édité | `backend/ontoforge/editing/files.py::shapes_diagnostics` | éditeur de fichiers (chapitre 13) |

Le modèle `ShapesModel` est décrit au chapitre [03](03-modele-interne.md#shapesmodel).

## Fichiers {#fichiers}

| Fichier | Responsabilité |
|---|---|
| `backend/ontoforge/shacl/import_shapes.py` | `parse_shapes`, `graph_to_shapes`, `guess_format`, encodage des termes (`encode_term`, `decode_term`), `iter_all_property_shapes` |
| `backend/ontoforge/shacl/export_shapes.py` | `shapes_to_graph`, `shapes_to_graph_with_ids` (table nœud → id de shape, pour relier les résultats), `serialize_shapes`, `path_to_sparql` |
| `backend/ontoforge/shacl/owl_to_shacl.py` | générateur `_Gen` : une NodeShape `<Classe>Shape` par classe nommée, notes catégorisées |
| `backend/ontoforge/shacl/validate.py` | `validate`, `ShaclReport`, `ShaclResult`, exécution isolée `_run_isolated`, erreurs `ShaclLimitError` et `ShaclBusyError` |
| `backend/ontoforge/shacl/_worker.py` | script du processus fils : pySHACL sur trois graphes N-Triples reçus en JSON |
| `backend/ontoforge/childproc.py` | `run_limited` : lancement d'un script Python plafonné (mémoire, CPU, taille de fichier), environnement minimal |
| `backend/ontoforge/shacl/shacl_to_pg.py` | `shape_constraints` (index classe → prédicat → contraintes), `hints`, `PGHint` |

## Flux de validation {#flux-validation}

```mermaid
sequenceDiagram
  participant F as Front
  participant A as api/analysis.py::shacl_validate
  participant V as validate.validate
  participant C as childproc.run_limited
  participant W as _worker.py (processus fils)
  F->>A: POST /shacl/validate (fichier de données)
  A->>A: format d'après l'extension (DATA_FORMATS)
  A->>V: run_in_threadpool(validate, données, shapes, onto, format)
  V->>V: parse_into (garde-fous) ; shapes_to_graph_with_ids
  V->>V: ont_graph = TBox seule (individus retirés)
  V->>V: _SLOTS.acquire non bloquant (sinon ShaclBusyError → 503 + Retry-After)
  V->>C: JSON {data, shapes, ont : N-Triples, inference}
  C->>W: python -I -c <lanceur> : setrlimit(AS, CPU, FSIZE) puis runpy
  W->>W: pyshacl.validate(..., advanced=False, inplace=False)
  W-->>C: JSON {conforms, results (N-Triples), text}
  C-->>V: CompletedProcess (ou TimeoutExpired)
  V->>V: résultats → ShaclResult (id de shape, chemin, message dans la langue de l'interface), tri stable
  V-->>A: ShaclReport
```

Détails :

- Isolation (SEC-05, L41). pySHACL tourne dans un processus fils lancé par `backend/ontoforge/childproc.py::run_limited` : `sys.executable -I -c <lanceur>` ; le lanceur pose lui-même `RLIMIT_AS` (mémoire), `RLIMIT_CPU` et `RLIMIT_FSIZE` (0 : aucune écriture de fichier) puis exécute le script par `runpy.run_path`. Pas de `preexec_fn` (risque de blocage entre `fork` et `exec` dans un processus à plusieurs fils). Environnement réduit à `PATH`, `LANG`, `LC_ALL`, `PYTHONPATH` : aucun secret n'arrive au fils. `cwd="/"`, `start_new_session=True`.
- Bornes : `ONTOFORGE_SHACL_TIMEOUT_S` (30 s), `ONTOFORGE_SHACL_MEMORY_MB` (2048), CPU = délai + 2 s, `ONTOFORGE_SHACL_SLOTS` (2, entre 1 et 32, lu à l'import). Dépassement de délai, signal ou `MemoryError` : `ShaclLimitError`, rendu comme un rapport `conforms=false` avec un avertissement lisible, et non comme une erreur HTTP.
- Occupé : tous les créneaux pris, `ShaclBusyError` remonte jusqu'au gestionnaire de `backend/ontoforge/main.py`, qui répond 503 avec `Retry-After: 5`.
- Boucle d'événements : la route appelle `validate` par `run_in_threadpool`, si bien que l'API reste réactive pendant une validation.
- Étiquettes de nœuds blancs : les graphes voyagent en N-Triples ; `_SameLabels` force le lecteur à garder les étiquettes, ce qui permet au parent de relier `sh:sourceShape` à l'id de shape du modèle (`shapes_to_graph_with_ids`).
- Ontologie fournie : seule la TBox (individus retirés) est passée comme `ont_graph` pySHACL. Les individus de l'ontologie d'exemple produisaient une violation de trop (D-L14-01).
- Inférence : `none` par défaut (D-034, D-L2-01) ; `rdfs`, `owlrl` ou `both` acceptés par la fonction. La route n'en propose pas le choix.

Exécution sur l'exemple `trap` (`samples/trap/trap-data.ttl`) : `conforms: false`, 8 résultats (l'oracle de D-L14-01), environ 0,3 s.

## Génération depuis OWL {#generation}

`backend/ontoforge/shacl/owl_to_shacl.py::generate_shapes` traduit l'ontologie en contrat de données (monde clos). Les règles complètes sont dans la docstring du module ; en résumé : une NodeShape `<Classe>Shape` avec `sh:targetClass` par classe nommée ; domaine et portée → property shape avec `sh:datatype` ou `sh:class` ; propriété sans domaine → `<prop>UsageShape` en `sh:targetSubjectsOf` ; fonctionnelle → `sh:maxCount 1` ; restrictions → `minCount` / `maxCount` (qualifiées si besoin), `sh:class`, `sh:hasValue` ; `oneOf` → `sh:in` ; `hasKey` → `minCount 1` + `maxCount 1` ; disjonction → `sh:not` ; propriétés dépréciées → shapes désactivées.

Chaque traduction non équivalente produit une **note** préfixée d'une catégorie stable (le front affiche les notes telles quelles, sans filtrer sur ces préfixes) : `[OWA]`, `[RENFORCÉ]`, `[PARTIEL]`, `[NON-CORE]`, `[HÉRITAGE]`, `[IGNORÉ]`. Sur `trap`, la génération donne 93 NodeShapes.

La route `POST /shacl/generate` accepte `dry_run` (aperçu, rien n'est écrit) et `merge` (par défaut, les shapes existantes du même id sont gardées : `setdefault`) ; sans `merge`, les shapes générées remplacent tout.

## Méta-validation {#meta-validation}

Quand l'utilisateur édite un fichier de shapes dans l'éditeur de fichiers, `backend/ontoforge/editing/files.py::shapes_diagnostics` valide le texte contre la méta-shape `shacl-shacl.ttl` livrée avec pySHACL (`_shacl_shacl`), puis le relit avec `parse_shapes`. Les résultats sont positionnés dans le texte (ligne, colonne) ; les constats en cascade d'une liste RDF mal formée sont réduits à un seul. Si la lecture échoue après des constats de la méta-shape, ceux-ci deviennent des erreurs bloquantes. Cette méta-validation tourne **dans le processus du serveur** (pas dans le fils isolé) : les shapes sont alors des données, leurs `sh:pattern` ne sont pas exécutés.

## Du SHACL vers le property graph {#shacl-vers-pg}

`backend/ontoforge/shacl/shacl_to_pg.py::shape_constraints` indexe les contraintes **par classe cible puis par prédicat** (directs et inverses) : `required`, `list` (vrai sauf `maxCount 1`), `datatype`, `class`, `in`, `pattern`, `min_count`, `max_count`, ids des shapes. Le moteur l'appelle dans `backend/ontoforge/mapping/engine.py` par import paresseux ; s'il échoue, les shapes sont ignorées avec un avertissement, l'analyse continue. Les règles du moteur qui lisent cet index sont dans `backend/ontoforge/mapping/rules/shacl.py` (chapitre [07](07-moteur-analyse.md)).

## Librairies {#librairies}

| Librairie | Version | Pourquoi |
|---|---|---|
| pyshacl | 0.29.1 | moteur de validation SHACL Core et SHACL-SPARQL ; fournit aussi `shacl-shacl.ttl` |
| rdflib | 7.1.1 | graphes, N-Triples, lecteur `W3CNTriplesParser` |
| owlrl | 7.1.2 | utilisé par pySHACL quand l'inférence `owlrl` est demandée |

Versions figées par D-L21-02.

## Décisions {#decisions}

- D-004 : SHACL dès la v0.1.
- D-034, D-L2-01 : pas d'inférence par défaut (`inference="none"`).
- D-L14-01 : TBox seule en `ont_graph` (8 violations sur `trap`).
- D-L48-01 : énumérations `xsd:string` en littéraux simples, sinon `sh:in` compare mal sous pySHACL.
- L39-secu (SEC-05) puis L41 : validation dans un processus fils plafonné, créneaux et 503.

## Pièges et limites {#pieges}

- Inférence et `sh:closed` : avec `rdfs`, les triplets déduits sont validés aussi ; une super-propriété déduite fait échouer une shape fermée. C'est la raison de D-034.
- Héritage : `sh:targetClass` ne couvre les sous-classes que si les `rdfs:subClassOf` sont dans le graphe validé. Sans ontologie fournie, les instances des sous-classes échappent aux shapes de la superclasse.
- `python -I` ignore les variables `PYTHON*`, dont `PYTHONPATH` : le fils ne voit que les paquets installés (pySHACL, rdflib), pas le code d'OntoForge. C'est voulu, mais un `_worker.py` qui importerait `ontoforge` échouerait hors installation.
- Plafond mémoire par `RLIMIT_AS` : il compte l'espace d'adressage, pas la mémoire résidente. 2048 Mo d'adressage laissent de la marge à Python et pySHACL ; une valeur trop basse fait échouer le fils au démarrage avec un message « mémoire ou temps plafonnés ».
- **`RLIMIT_*` n'existe que sous Unix** : `run_limited` n'est pas prévu pour Windows (`resource` absent). `À CONFIRMER` : comportement exact sous Windows non testé (l'application tourne en conteneur Linux).
- SHACL-SPARQL : exécuté par pySHACL (`advanced=False` suffit pour `sh:sparql`), avec un avertissement dans le rapport.

## Comment ajouter… {#comment-ajouter}

**…une traduction OWL → SHACL.** Ajouter la règle dans la méthode de `_Gen` qui correspond (`gen_restriction`, `gen_properties`, `gen_classes`…), émettre une note avec une catégorie existante si la traduction n'est pas équivalente, et un test dans `backend/tests/test_shacl_owl_to_shacl.py`.

**…une contrainte SHACL lue.** L'ajouter au modèle (`Constraints` ou `PropertyShape`, décision tracée), la lire dans `_Reader` de `import_shapes.py` (sinon elle part dans les avertissements), l'écrire dans `_Writer` de `export_shapes.py`, et l'indexer dans `shape_constraints` si le moteur doit en tenir compte.

**…un autre traitement en processus fils.** Réutiliser `backend/ontoforge/childproc.py::run_limited` avec un script autonome (entrée JSON sur stdin, sortie JSON sur stdout, aucune importation d'`ontoforge`), un sémaphore de créneaux non bloquant et une erreur « occupé » traduite en 503, comme `validate.py` et le triplestore local (chapitre [10](10-triplestore-local.md)).
